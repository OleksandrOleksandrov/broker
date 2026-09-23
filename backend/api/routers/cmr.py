"""CMR parsing router."""

import os

from fastapi import APIRouter, File, HTTPException, UploadFile
from openai import AsyncOpenAI

from ..models import CMRDocument
from ..utils import build_image_payload, process_file_to_images

router = APIRouter(prefix="/api", tags=["cmr"])

dpi = 350
gpt_model = os.getenv("GPT_MODEL", "gpt-4o-2024-11-20")


@router.post("/parse-cmr", response_model=CMRDocument)
async def parse_cmr(
    file: UploadFile = File(...),
):
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=500, detail="OPENAI_API_KEY не знайдено в оточенні"
        )

    client = AsyncOpenAI(api_key=api_key)
    images, is_original = await process_file_to_images(file, dpi=dpi)

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

    content_payload.extend(await build_image_payload(images, is_original))

    completion = await client.beta.chat.completions.parse(
        model=gpt_model,
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