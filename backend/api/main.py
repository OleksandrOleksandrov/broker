import base64
import io
import os
from typing import List, Optional
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from openai import OpenAI
import pandas as pd
from pdf2image import convert_from_bytes
from PIL import Image
from pydantic import BaseModel, Field

load_dotenv()

# Lambda layer binary path for Poppler
POPPLER_PATH = os.getenv("POPPLER_PATH", "/opt/bin/pdfinfo")

app = FastAPI(title="Customs Broker AI Assistant")

# Дозволяємо запити з Node.js фронтенду
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
        description="Invoice number. Read carefully, number by number, do not skip long numbers and do not skip repited zero in the middle of the number. It is 16 characters long. If you cannot find it, write 'not found'.",
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
async def parse_invoice(file: UploadFile = File(...)):
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=500, detail="OPENAI_API_KEY не знайдено в оточенні"
        )

    client = OpenAI(api_key=api_key)
    pdf_bytes = await file.read()

    try:
        # Вказуємо poppler_path для зчитування бінарників з Lambda Layer
        images = convert_from_bytes(pdf_bytes, dpi=300, poppler_path=POPPLER_PATH)
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

    # Автоматично підбираємо код УКТ ЗЕД для кожної позиції
    for item in parsed_data.items:
        try:
            item.uktzed_suggestion = get_uktzed_code(
                client, item.description, item.article
            )
        except Exception:
            item.uktzed_suggestion = UktZedSuggestion(
                code="0000000000",
                description="Не вдалося визначити",
                justification="Помилка при запиті класифікації",
            )

    return parsed_data


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
