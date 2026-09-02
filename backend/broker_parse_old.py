import os
import base64
import io
import json
from typing import List, Optional
from pdf2image import convert_from_path
from PIL import Image
from pydantic import BaseModel, Field
from openai import OpenAI

from dotenv import load_dotenv

load_dotenv()


# 1. Опис структури даних через Pydantic
class InvoiceItem(BaseModel):
    item_number: Optional[int] = Field(
        default=None, description="Порядковий номер позиції"
    )
    article: Optional[str] = Field(
        default=None, description="Артикул, код або SKU товару"
    )
    description: str = Field(description="Повний опис товару/найменування")
    quantity: float = Field(description="Кількість товару")
    unit: str = Field(description="Одиниця виміру (шт, кг, м, pack тощо)")
    price_per_unit: float = Field(description="Ціна за одиницю")
    total_amount: float = Field(description="Загальна вартість позиції")
    country_of_origin: Optional[str] = Field(
        default=None, description="Країна походження товару (якщо вказана)"
    )


class InvoiceData(BaseModel):
    invoice_number: Optional[str] = Field(
        default=None,
        description="Invoice number. Read carefully, number by number, do not skip long numbers and do not skip repited zero in the middle of the number. It is 16 characters long. If you cannot find it, write 'not found'.",
    )
    print(f"Parsing invoice data...{invoice_number}")
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


# 2. Допоміжна функція конвертації зображення в base64
def encode_image_to_base64(image: Image.Image) -> str:
    buffered = io.BytesIO()
    image.save(buffered, format="JPEG")
    return base64.b64encode(buffered.getvalue()).decode("utf-8")


# 3. Основна функція екстракції даних з PDF
def extract_invoice_data(pdf_path: str, api_key: str) -> InvoiceData:
    client = OpenAI(api_key=api_key)

    # Конвертуємо сторінки PDF у зображення (для точного зчитування складних таблиць)
    images = convert_from_path(pdf_path, dpi=500)

    content_payload = [
        {
            "type": "text",
            "text": "Carefully extract all invoice data and line items in a structured format.",
        }
    ]

    # Додаємо всі сторінки документа як зображення
    for img in images:
        base64_img = encode_image_to_base64(img)
        content_payload.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{base64_img}"},
            }
        )

    # Виклик OpenAI з гарантованим форматом Pydantic (Structured Outputs)
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

    return completion.choices[0].message.parsed


# Приклад використання
if __name__ == "__main__":
    API_KEY = os.getenv("OPENAI_API_KEY")
    PDF_FILE_PATH = "invoice.pdf"

    try:
        parsed_invoice = extract_invoice_data(PDF_FILE_PATH, API_KEY)

        # Вивід у форматі JSON
        json_output = json.dumps(
            parsed_invoice.model_dump(), indent=2, ensure_ascii=False
        )
        # json_output = parsed_invoice.model_dump_json(indent=2, ensure_ascii=False)
        print(json_output)

        # Збереження результату у файл
        with open("extracted_invoice.json", "w", encoding="utf-8") as f:
            f.write(json_output)

    except Exception as e:
        print(f"Помилка при обробці: {e}")
