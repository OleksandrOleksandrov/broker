"""CMR parsing router."""

import os
import time

from fastapi import APIRouter, File, HTTPException, UploadFile
from openai import AsyncOpenAI

from ..models import CMRDocument
from ..utils import build_image_payload, process_file_to_images
from ..utils.logging_config import get_logger

router = APIRouter(prefix="/api", tags=["cmr"])

dpi = int(os.getenv("PDF_DPI", "350"))
gpt_model = os.getenv("GPT_MODEL", "gpt-4o-2024-11-20")

logger = get_logger("cmr")


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
    
    logger.info(
        "Starting CMR parsing",
        extra={
            "filename": file.filename,
            "content_type": file.content_type,
            "dpi": dpi,
            "model": gpt_model,
        }
    )
    start_time = time.perf_counter()
    
    images = await process_file_to_images(file, dpi=dpi)
    
    logger.info(
        "File converted to images",
        extra={
            "filename": file.filename,
            "num_pages": len(images),
            "dpi": dpi,
        }
    )

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

    content_payload.extend(await build_image_payload(images))

    try:
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
    except Exception as e:
        logger.exception(
            "CMR parsing failed",
            extra={
                "filename": file.filename,
                "error": str(e),
                "duration_ms": (time.perf_counter() - start_time) * 1000,
            }
        )
        raise

    parsed_data = completion.choices[0].message.parsed
    
    duration_ms = (time.perf_counter() - start_time) * 1000
    logger.info(
        "CMR parsing completed",
        extra={
            "filename": file.filename,
            "cmr_number": getattr(parsed_data, 'cmr_number', None),
            "num_cargo_items": len(parsed_data.cargo_items) if parsed_data.cargo_items else 0,
            "duration_ms": round(duration_ms, 1),
            "dpi": dpi,
            "model": gpt_model,
        }
    )

    return parsed_data