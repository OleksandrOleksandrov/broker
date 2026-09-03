import asyncio
import base64
import io
import logging
import os
from typing import List, Optional
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from openai import OpenAI
import pandas as pd
from pdf2image import convert_from_bytes
from PIL import Image
from pydantic import BaseModel, Field

load_dotenv()

logger = logging.getLogger("broker.api")
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))

# Lambda layer binary path for Poppler
POPPLER_PATH = os.getenv("POPPLER_PATH")

app = FastAPI(
    title="Broker AI Assistant",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)


# Дозволяємо запити з Node.js фронтенду
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class PartyDetails(BaseModel):
    name: Optional[str] = Field(default=None, description="Найменування компанії / ФОП")
    address: Optional[str] = Field(
        default=None, description="Юридична та фактична адреса"
    )
    edrpou: Optional[str] = Field(default=None, description="Код за ЄДРПОУ / ІПН")
    ipn: Optional[str] = Field(
        default=None, description="Індивідуальний податковий номер"
    )
    iban: Optional[str] = Field(default=None, description="Розрахунковий рахунок IBAN")
    bank_name: Optional[str] = Field(
        default=None, description="Назва банківської установи"
    )
    mfo: Optional[str] = Field(default=None, description="МФО банку")
    email: Optional[str] = Field(default=None, description="Електронна адреса")
    phone: Optional[str] = Field(default=None, description="Контактний номер телефону")
    signatory_title: Optional[str] = Field(
        default=None, description="Посада уповноваженої особи"
    )
    signatory_name: Optional[str] = Field(
        default=None, description="ПІБ/ініціали уповноваженої особи"
    )


class ApplicationItem(BaseModel):
    application_number: Optional[str] = Field(default=None, description="Номер заявки")
    application_date: Optional[str] = Field(
        default=None, description="Дата оформлення заявки"
    )
    contract_number: Optional[str] = Field(
        default=None, description="Номер основного договору"
    )
    contract_date: Optional[str] = Field(
        default=None, description="Дата основного договору"
    )

    transport_type: Optional[str] = Field(default=None, description="Вид перевезення")
    route: Optional[str] = Field(default=None, description="Маршрут перевезення")
    shipper: Optional[str] = Field(
        default=None, description="Вантажовідправник (ПІБ, телефон, email)"
    )
    loading_address: Optional[str] = Field(
        default=None, description="Адреса завантаження"
    )
    loading_datetime: Optional[str] = Field(
        default=None, description="Дата та час завантаження"
    )
    cargo_name_and_packaging: Optional[str] = Field(
        default=None, description="Найменування та кількість вантажу, його пакування"
    )
    cargo_quantity_and_dimensions: Optional[str] = Field(
        default=None, description="Кількість вантажних місць, габарити Д*Ш*В / вага"
    )
    customs_outbound_address: Optional[str] = Field(
        default=None, description="Адреса замитнення, контактна особа"
    )
    border_crossing_point: Optional[str] = Field(
        default=None, description="Пункт перетину кордону"
    )
    customs_inbound_address: Optional[str] = Field(
        default=None,
        description="Адреса розмитнення, контактна особа, ЗВЕРНИ ОСОБЛИВУ УВАГУ НА АДРЕСИ: в українській нумерації будинків після скісної риски або дефісу часто йдуть літери (наприклад, 1/б, 25-А, 48В). КРИТИЧНО ВАЖЛИВО: строго розрізняй і не плутай кириличну малу літеру 'б' із цифрою '6'. Аналізуй візуальний контекст. Адреси можуть містити лише літери української абетки (а, б, в, г, ґ, д, е, є, ж, з, и, і, ї, й, к, л, м, н, о, п, р, с, т, у, ф, х, ц, ч, ш, щ, ь, ю, я), цифри та спецсимволи. Не вигадуй значень — якщо поле відсутнє, залиш null.",
    )
    unloading_address: Optional[str] = Field(
        default=None,
        description="Адреса розвантаження",
    )
    unloading_datetime: Optional[str] = Field(
        default=None, description="Дата та час розвантаження"
    )
    vehicle_requirements: Optional[str] = Field(
        default=None, description="Вимоги до транспортного засобу / тип кузова"
    )
    vehicle_info: Optional[str] = Field(
        default=None, description="Транспортний засіб (номери авто та причепа)"
    )
    driver_info: Optional[str] = Field(
        default=None,
        description="Прізвище, ім'я, по батькові водія, посвідчення, телефон",
    )
    customer_responsible_person: Optional[str] = Field(
        default=None, description="Відповідальна особа Замовника"
    )
    price_terms: Optional[str] = Field(
        default=None, description="Ціна послуг, валюта та умови розрахунку"
    )

    customer_details: Optional[PartyDetails] = Field(
        default=None, description="Юридичні реквізити Замовника"
    )
    carrier_details: Optional[PartyDetails] = Field(
        default=None, description="Юридичні реквізити Перевізника"
    )


# 1. Pydantic схеми
class UktZedSuggestion(BaseModel):
    code: str = Field(description="10-значний код УКТ ЗЕД (наприклад, 2710199900)")
    description: str = Field(description="Офіційне найменування групи/коду за Тарифом")
    justification: str = Field(
        description="Коротке обґрунтування вибору коду за Основними правилами інтерпретації"
    )


class InvoiceItem(BaseModel):
    item_number: Optional[int] = Field(
        default=None, description="Порядковий номер позиції"
    )
    article: Optional[str] = Field(
        default=None, description="Артикул, код або SKU товару"
    )
    description: str = Field(description="Повний опис товару/найменування з інвойсу")
    quantity: float = Field(description="Кількість товару")
    unit: str = Field(description="Одиниця виміру (шт, кг, м, pack тощо)")
    price_per_unit: float = Field(description="Ціна за одиницю")
    total_amount: float = Field(description="Загальна вартість позиції")
    country_of_origin: Optional[str] = Field(
        default=None, description="Країна походження товару"
    )
    uktzed_suggestion: Optional[UktZedSuggestion] = Field(
        default=None, description="Автоматично згенерована підказка УКТ ЗЕД"
    )


class InvoiceData(BaseModel):
    invoice_number: Optional[str] = Field(
        default=None,
        description=(
            "Locate the invoice number. To prevent tokenization errors with repeated zeros,"
            "transcribe the number exactly as it appears, separating every single character"
            "with a hyphen (e.g., A-C-Z-1-0-1-1-0-0-0-0-0-0-1-1-1). Count the characters to"
            "verify it is exactly 16 characters long."
            "number on a new line. If not found, write 'not found'."
        ),
    )
    invoice_date: Optional[str] = Field(default=None, description="Дата видачі інвойсу")
    currency: Optional[str] = Field(
        default=None, description="Валюта (USD, EUR, UAH тощо)"
    )
    seller_name: Optional[str] = Field(
        default=None, description="Назва продавця/експортера"
    )
    buyer_name: Optional[str] = Field(
        default=None, description="Назва покупця/імпортера"
    )
    total_invoice_amount: Optional[float] = Field(
        default=None, description="Загальна підсумкова сума інвойсу"
    )
    items: List[InvoiceItem] = Field(
        description="Список усіх позицій товарів у таблиці"
    )


def encode_image_to_base64(image: Image.Image) -> str:
    buffered = io.BytesIO()
    image.save(buffered, format="JPEG")
    return base64.b64encode(buffered.getvalue()).decode("utf-8")


def encode_lossless_image_to_base64(image: Image.Image) -> str:
    buffered = io.BytesIO()
    image.save(buffered, format="PNG", optimize=True)
    return base64.b64encode(buffered.getvalue()).decode("utf-8")


# 2. Функція підбору коду УКТ ЗЕД для конкретної позиції
def get_uktzed_code(
    client: OpenAI, item_description: str, article: Optional[str]
) -> UktZedSuggestion:
    prompt = f"Товар: {item_description}. Артикул: {article or 'не вказано'}."

    completion = client.beta.chat.completions.parse(
        model="gpt-4o-2024-11-20",
        messages=[
            {
                "role": "system",
                "content": "Ти експерт з митної класифікації товарів за митним тарифом України (УКТ ЗЕД). "
                "Визнач найбільш вірогідний 10-значний код УКТ ЗЕД та надай обґрунтування.",
            },
            {"role": "user", "content": prompt},
        ],
        response_format=UktZedSuggestion,
        temperature=0.0,
    )
    return completion.choices[0].message.parsed


# 3. Ендпоінт обробки PDF
@app.post("/api/parse-invoice", response_model=InvoiceData)
async def parse_invoice(
    file: UploadFile = File(...),
    parse_uktzed: bool = Form(False),
):
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=500, detail="OPENAI_API_KEY не знайдено в оточенні"
        )

    client = OpenAI(api_key=api_key)
    pdf_bytes = await file.read()
    dpi = 350  # Висока роздільна здатність для кращого OCR
    try:
        # На AWS Lambda використовуємо poppler з Layer; локально — системний pdftoppm
        if POPPLER_PATH:
            images = convert_from_bytes(pdf_bytes, dpi=dpi, poppler_path=POPPLER_PATH)
        else:
            images = convert_from_bytes(pdf_bytes, dpi=dpi)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Помилка зчитування PDF: {str(e)}")

    content_payload = [
        {
            "type": "text",
            "text": "Carefully extract all invoice data and line items in a structured format.",
        }
    ]

    for img in images:
        base64_img = encode_image_to_base64(img)
        content_payload.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{base64_img}"},
            }
        )

    # Витягуємо дані інвойсу через Vision API
    completion = client.beta.chat.completions.parse(
        model="gpt-4o-2024-11-20",
        messages=[
            {
                "role": "system",
                "content": "Ти професійний експерт з декларування та митного оформлення. "
                "Точно зчитуй дані з документів без фантазування.",
            },
            {"role": "user", "content": content_payload},
        ],
        response_format=InvoiceData,
        temperature=0.0,
    )

    parsed_data = completion.choices[0].message.parsed

    # Підбираємо коди УКТ ЗЕД лише за запитом користувача (чекбокс у фронтенді)
    if parse_uktzed and parsed_data.items:
        logger.info(
            "UKT ZED classification requested for %d item(s)", len(parsed_data.items)
        )

        async def classify(item: InvoiceItem) -> None:
            try:
                item.uktzed_suggestion = await asyncio.to_thread(
                    get_uktzed_code, client, item.description, item.article
                )
            except Exception as e:
                logger.exception("UKT ZED classification failed for item: %s", e)
                item.uktzed_suggestion = UktZedSuggestion(
                    code="0000000000",
                    description="Не вдалося визначити",
                    justification="Помилка при запиті класифікації",
                )

        await asyncio.gather(*(classify(item) for item in parsed_data.items))
    else:
        # Якщо класифікація не потрібна — явно очищаємо поле,
        # щоб клієнт не отримав застарілі дані
        for item in parsed_data.items:
            item.uktzed_suggestion = None

    return parsed_data


@app.post("/api/parse-application", response_model=ApplicationItem)
async def parse_application(
    file: UploadFile = File(...),
):
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=500, detail="OPENAI_API_KEY не знайдено в оточенні"
        )

    client = OpenAI(api_key=api_key)
    pdf_bytes = await file.read()
    dpi = 400
    try:
        if POPPLER_PATH:
            images = convert_from_bytes(pdf_bytes, dpi=dpi, poppler_path=POPPLER_PATH)
        else:
            images = convert_from_bytes(pdf_bytes, dpi=dpi)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Помилка зчитування PDF: {str(e)}")

    content_payload = [
        {
            "type": "text",
            "text": (
                "Це українська заявка на перевезення вантажу (транспортна заявка). "
                "Уважно витягни всі реквізити: номер і дату заявки, номер і дату договору, "
                "маршрут, адреси завантаження/розвантаження/замитнення/розмитнення, дати та час, "
                "дані про вантаж, транспортний засіб, водія, відповідальну особу Замовника, "
                "ціну та юридичні реквізити обох сторін (Замовника і Перевізника). "
                "Не вигадуй значень — якщо поле відсутнє, залиш null."
            ),
        }
    ]

    for img in images:
        base64_img = encode_lossless_image_to_base64(img)
        content_payload.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{base64_img}"},
            }
        )

    completion = client.beta.chat.completions.parse(
        model="gpt-4o-2024-11-20",
        messages=[
            {
                "role": "system",
                "content": (
                    "Ти професійний логіст та експерт з обробки українських транспортних документів. "
                    "Точно зчитуй дані з документів без фантазування. Якщо поле відсутнє або "
                    "нерозбірливе — повертай null."
                    "ЗВЕРНИ ОСОБЛИВУ УВАГУ НА АДРЕСИ: в українській нумерації будинків після скісної риски або дефісу часто йдуть літери (наприклад, 1/б, 25-А, 48В). КРИТИЧНО ВАЖЛИВО: строго розрізняй і не плутай кириличну малу літеру 'б' із цифрою '6'. Аналізуй візуальний контекст. Адреси можуть містити лише літери української абетки (а, б, в, г, ґ, д, е, є, ж, з, и, і, ї, й, к, л, м, н, о, п, р, с, т, у, ф, х, ц, ч, ш, щ, ь, ю, я), цифри та спецсимволи. Не вигадуй значень — якщо поле відсутнє, залиш null."
                ),
            },
            {"role": "user", "content": content_payload},
        ],
        response_format=ApplicationItem,
        temperature=0.0,
    )

    return completion.choices[0].message.parsed


@app.post("/api/export-excel")
async def export_excel(data: InvoiceData):
    rows = []
    for idx, item in enumerate(data.items, 1):
        uktzed_code = item.uktzed_suggestion.code if item.uktzed_suggestion else ""

        rows.append(
            {
                "№": item.item_number or idx,
                "Артикул": item.article or "",
                "Найменування товару (Графа 31)": item.description,
                "Код УКТ ЗЕД (Графа 33)": uktzed_code,
                "Кількість": item.quantity,
                "Од. виміру": item.unit,
                "Ціна": item.price_per_unit,
                "Фактурна вартість": item.total_amount,
                "Країна походження": item.country_of_origin or "",
                "Валюта": data.currency or "",
            }
        )

    df = pd.DataFrame(rows)

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Specification")
    output.seek(0)

    headers = {
        "Content-Disposition": 'attachment; filename="md_declaration_import.xlsx"'
    }
    return StreamingResponse(
        output,
        headers=headers,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
