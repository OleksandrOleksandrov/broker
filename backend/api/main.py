import asyncio
import base64
import io
import logging
import os
import re
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


# Suspicious tokens: e.g. "1/6", "25-6" — looks like a Cyrillic letter
# ('б', 'А', 'В', ...) was misread as a digit. The original Ukrainian
# numbering uses "<digits><sep><letter>" very commonly.
_SUSPICIOUS_ADDRESS_TOKEN = re.compile(r"(?<!\d)(\d{1,3})\s*([/\-])\s*(\d)(?!\d)")


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
    loading_address_source: Optional[str] = Field(
        default=None,
        description="Raw OCR substring from the document that loading_address was transcribed from",
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
    customs_outbound_address_source: Optional[str] = Field(
        default=None,
        description="Raw OCR substring from the document that customs_outbound_address was transcribed from",
    )
    border_crossing_point: Optional[str] = Field(
        default=None, description="Пункт перетину кордону"
    )
    customs_inbound_address: Optional[str] = Field(
        default=None, description="Адреса розмитнення, контактна особа"
    )
    customs_inbound_address_source: Optional[str] = Field(
        default=None,
        description="Raw OCR substring from the document that customs_inbound_address was transcribed from",
    )
    unloading_address: Optional[str] = Field(
        default=None, description="Адреса розвантаження"
    )
    unloading_address_source: Optional[str] = Field(
        default=None,
        description="Raw OCR substring from the document that unloading_address was transcribed from",
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


# Suspicious tokens: e.g. "1/6", "25-6" — looks like a Cyrillic letter
# ('б', 'А', 'В', ...) was misread as a digit. The original Ukrainian
# numbering uses "<digits><sep><letter>" very commonly.
_SUSPICIOUS_ADDRESS_TOKEN = re.compile(r"(?<!\d)(\d{1,3})\s*([/\-])\s*(\d)(?!\d)")

_ADDRESS_FIELDS = (
    "loading_address",
    "customs_outbound_address",
    "customs_inbound_address",
    "unloading_address",
)


def find_suspicious_address_token(item: "ApplicationItem") -> Optional[str]:
    """Return the first suspicious `<num>/<digit>` token across all address fields,
    or None if no field has one."""
    for name in _ADDRESS_FIELDS:
        value = getattr(item, name, None)
        if not value:
            continue
        m = _SUSPICIOUS_ADDRESS_TOKEN.search(value)
        if m:
            return m.group(0)
    return None


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
    dpi = 350
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
                "Для кожної адреси (loading_address, customs_outbound_address, "
                "customs_inbound_address, unloading_address) продублюй також точний "
                "фрагмент тексту з документа, з якого ти її прочитав, у відповідному "
                "*_source полі. Не вигадуй значень — якщо поле відсутнє, залиш null."
            ),
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

    system_prompt = (
        "Ти професійний логіст. Точно зчитуй дані з документа без фантазування.\n"
        "ПРАВИЛО ЩОДО АДРЕС: в українських номерах будинків після '/' або '-' зазвичай "
        "стоїть ЛІТЕРА, а не цифра (1/б, 25-А, 48В). Копіюй символи як у документі, не "
        "замінюй кириличні літери на схожі цифри.\n"
        "Приклад: 'вул. Хмельницького, 1/б' — коректно як '1/б', НЕ як '1/6'."
    )

    def _extract(retry_hint: Optional[str] = None) -> ApplicationItem:
        user_text = content_payload[0]["text"]
        if retry_hint:
            user_text = (
                user_text + "\n\nУВАГА: попередня відповідь містила підозрілий токен "
                f"{retry_hint!r} (цифра після '/' або '-' у номері будинку). "
                "Перечитай адресу в документі та виправ її. Після '/' або '-' має стояти ЛІТЕРА."
            )
        payload = [{"type": "text", "text": user_text}, *content_payload[1:]]
        completion = client.beta.chat.completions.parse(
            model="gpt-4o-2024-11-20",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": payload},
            ],
            response_format=ApplicationItem,
            temperature=0.0,
        )
        return completion.choices[0].message.parsed

    parsed = _extract()
    for _attempt in range(2):
        offending = find_suspicious_address_token(parsed)
        if not offending:
            break
        logger.warning(
            "parse_application: suspicious address token %r, retrying with hint",
            offending,
        )
        parsed = _extract(retry_hint=offending)

    return parsed


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


class CMRParty(BaseModel):
    name_and_address: Optional[str] = Field(
        default=None,
        description="Nosaukums, adrese, valsts / Name, address, state[span_0](start_span)[span_0](end_span)",
    )
    tax_id: Optional[str] = Field(
        default=None,
        description="Tax or VAT ID, e.g., SELCUK V.D.[span_1](start_span)[span_1](end_span)",
    )


class CMRCargoItem(BaseModel):
    marks_and_numbers: Optional[str] = Field(
        default=None,
        description="6 Zīmes un numuri / Marks and numbers[span_2](start_span)[span_2](end_span)",
    )
    number_of_packs: Optional[str] = Field(
        default=None,
        description="7 Vietu skaits / Number of packs[span_3](start_span)[span_3](end_span)",
    )
    type_of_packing: Optional[str] = Field(
        default=None,
        description="8 Iepakojuma veids / Type of packing[span_4](start_span)[span_4](end_span)",
    )
    name_of_goods: Optional[str] = Field(
        default=None,
        description="9 Kravas nosaukums / Name of the goods[span_5](start_span)[span_5](end_span)",
    )
    statistic_number: Optional[str] = Field(
        default=None,
        description="10 Statist.Nr. / Statistic.Nr.[span_6](start_span)[span_6](end_span)",
    )
    gross_weight_kg: Optional[float] = Field(
        default=None,
        description="11 Bruto svars / Brutto weight in (kg)[span_7](start_span)[span_7](end_span)",
    )
    volume_m3: Optional[float] = Field(
        default=None,
        description="12 Apjoms (m3) / Volume in (m3)[span_8](start_span)[span_8](end_span)",
    )


class CMRVehicle(BaseModel):
    tractor_registration: Optional[str] = Field(
        default=None,
        description="25 Registr Nr. Vilcējs/Car[span_9](start_span)[span_9](end_span)",
    )
    trailer_registration: Optional[str] = Field(
        default=None,
        description="25 Registr Nr. Puspiekabe/Sidecar[span_10](start_span)[span_10](end_span)",
    )
    tractor_brand: Optional[str] = Field(
        default=None,
        description="26 Marka/type Vilcējs/Car[span_11](start_span)[span_11](end_span)",
    )
    trailer_brand: Optional[str] = Field(
        default=None,
        description="26 Marka/type Puspiekabe/Sidecar[span_12](start_span)[span_12](end_span)",
    )


class CMRDocument(BaseModel):
    cmr_number: Optional[str] = Field(
        default=None,
        description="CMR Number (e.g., TR 10-05/2025)[span_13](start_span)[span_13](end_span)",
    )
    consignor: Optional[CMRParty] = Field(
        default=None,
        description="1 Nosūtītājs / Consignor[span_14](start_span)[span_14](end_span)",
    )
    consignee: Optional[CMRParty] = Field(
        default=None,
        description="2 Saņēmējs / Consignee[span_15](start_span)[span_15](end_span)",
    )
    delivery_place: Optional[str] = Field(
        default=None,
        description="3 Kravas izkraušanas vieta / Place of delivery of the goods[span_16](start_span)[span_16](end_span)",
    )
    taking_over_place: Optional[str] = Field(
        default=None,
        description="4 Kravas iekraušanas vieta un datums / Place and date of taking over of the goods[span_17](start_span)[span_17](end_span)",
    )
    annexed_documents: Optional[str] = Field(
        default=None,
        description="5 Pievienotie dokumenti / Annexed documents Locate the invoice number. To prevent tokenization errors with repeated zeros,"
        "transcribe the number exactly as it appears, separating every single character"
        "with a hyphen (e.g., A-C-Z-1-0-1-1-0-0-0-0-0-0-1-1-1). Count the characters to"
        "verify it is exactly 16 characters long."
        "number on a new line. If not found, write 'not found'.",
    )
    cargo_items: Optional[List[CMRCargoItem]] = Field(
        default_factory=list,
        description="Cargo details table (Fields 6-12)[span_19](start_span)[span_19](end_span)",
    )
    senders_instructions: Optional[str] = Field(
        default=None,
        description="13 Nosūtītāja norādijumi / Sender's instructions (Customs and other formalitis)[span_20](start_span)[span_20](end_span)",
    )
    carrier: Optional[CMRParty] = Field(
        default=None,
        description="16 Pārvadātājs / Carrier/forwarder[span_21](start_span)[span_21](end_span)",
    )
    successive_carriers: Optional[CMRParty] = Field(
        default=None,
        description="17 Turpmakais pārvadātājs / Successive carriers[span_22](start_span)[span_22](end_span)",
    )
    carriers_reservations: Optional[str] = Field(
        default=None,
        description="18 Pārvadātāja aizradījumi un piezīmes / Carrier's reservations and observation[span_23](start_span)[span_23](end_span)",
    )
    freight_payment_instructions: Optional[str] = Field(
        default=None,
        description="15 Apmaksas noteikumi / Directions and freight payment[span_24](start_span)[span_24](end_span)",
    )
    special_agreements: Optional[str] = Field(
        default=None,
        description="20 Īpaši saskaņoti noteikumi / Special agreements[span_25](start_span)[span_25](end_span)",
    )
    established_in_place: Optional[str] = Field(
        default=None,
        description="21 Sastādīts / Established in[span_26](start_span)[span_26](end_span)",
    )
    established_in_date: Optional[str] = Field(
        default=None,
        description="21 Datums / Date of establishment[span_27](start_span)[span_27](end_span)",
    )
    arrival_to_loading_time: Optional[str] = Field(
        default=None,
        description="22 Ierašanās iekraušanai / Arrival to loading time[span_28](start_span)[span_28](end_span)",
    )
    departure_from_loading_time: Optional[str] = Field(
        default=None,
        description="22 Aizbraukšana / Departure time[span_29](start_span)[span_29](end_span)",
    )
    waybill_number: Optional[str] = Field(
        default=None,
        description="23 Ceļazīme Nr. / Waybill Nr.[span_30](start_span)[span_30](end_span)",
    )
    drivers_names: Optional[str] = Field(
        default=None,
        description="23 Vadītāju uzvārdi / Drivers names[span_31](start_span)[span_31](end_span)",
    )
    goods_received_date: Optional[str] = Field(
        default=None,
        description="24 Krava saņemta Datums / Goods received Date[span_32](start_span)[span_32](end_span)",
    )
    arrival_to_unloading_time: Optional[str] = Field(
        default=None,
        description="24 Ierašanās iekraušanai / Arrival to unloading time[span_33](start_span)[span_33](end_span)",
    )
    departure_from_unloading_time: Optional[str] = Field(
        default=None,
        description="24 Aizbraukšana / Departure time from unloading[span_34](start_span)[span_34](end_span)",
    )
    vehicle_info: Optional[CMRVehicle] = Field(
        default=None,
        description="25-26 Vehicle registration and type information[span_35](start_span)[span_35](end_span)",
    )
    consignee_signature_and_stamp: Optional[str] = Field(
        default=None,
        description="24 Saņēmēja paraksts un zīmogs / Signature and stamp of the consignee block text[span_36](start_span)[span_36](end_span)",
    )


@app.post("/api/parse-cmr", response_model=CMRDocument)
async def parse_cmr(
    file: UploadFile = File(...),
):
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=500, detail="OPENAI_API_KEY не знайдено в оточенні"
        )

    client = OpenAI(api_key=api_key)
    pdf_bytes = await file.read()
    dpi = 350
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
                "Це міжнародна транспортна накладна CMR. Уважно витягни всі видимі "
                "реквізити документа у структурований формат. Зчитай номер CMR, "
                "відправника, одержувача, місця завантаження та доставки, додані "
                "документи, усі рядки вантажу, інструкції, перевізників, умови "
                "оплати, застереження, спеціальні умови, дати й час, номери "
                "дорожнього листа, водіїв, дані автомобіля та підпис одержувача. "
                "Для полів, яких немає або які неможливо прочитати, поверни null; "
                "cargo_items має містити лише фактично наявні рядки вантажу. "
                "Не вигадуй значень і не виправляй написання назв, номерів чи адрес."
            ),
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

    completion = client.beta.chat.completions.parse(
        model="gpt-4o-2024-11-20",
        messages=[
            {
                "role": "system",
                "content": (
                    "Ти професійний фахівець з міжнародних вантажних перевезень. "
                    "Точно зчитуй дані з CMR без фантазування. Зберігай оригінальне "
                    "написання та одиниці виміру."
                ),
            },
            {"role": "user", "content": content_payload},
        ],
        response_format=CMRDocument,
        temperature=0.0,
    )

    return completion.choices[0].message.parsed
