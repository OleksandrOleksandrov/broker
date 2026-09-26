"""Invoice parsing router."""

import os
import time
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from openai import AsyncOpenAI

from ..models import InvoiceData, InvoiceItem, UktZedSuggestion
from ..utils import get_uktzed_code, build_image_payload, process_file_to_images, get_dpi, get_gpt_model
from ..utils.logging_config import get_logger

router = APIRouter(prefix="/api", tags=["invoice"])

logger = get_logger("invoice")


@router.post("/parse-invoice", response_model=InvoiceData)
async def parse_invoice(
    file: UploadFile = File(...),
    parse_uktzed: bool = Form(False),
):
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=500, detail="OPENAI_API_KEY не знайдено в оточенні"
        )

    client = AsyncOpenAI(api_key=api_key)

    dpi = get_dpi()
    gpt_model = get_gpt_model()

    logger.info(
        "Starting invoice parsing",
        extra={
            "filename": file.filename,
            "content_type": file.content_type,
            "dpi": dpi,
            "model": gpt_model,
        },
    )
    start_time = time.perf_counter()

    images = await process_file_to_images(file, dpi=dpi)

    logger.info(
        "File converted to images",
        extra={
            "filename": file.filename,
            "num_pages": len(images),
            "dpi": dpi,
        },
    )

    content_payload = [
        {
            "type": "text",
            "text": (
                "Carefully extract all invoice data and line items in a structured format. "
                "For every line item, extract net_weight_kg when the net weight is visible; "
                "otherwise leave it null."
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
                    "content": "Ти професійний експерт з декларування та митного оформлення. "
                    "Точно зчитуй дані з документів без фантазування.",
                },
                {"role": "user", "content": content_payload},
            ],
            response_format=InvoiceData,
            temperature=0.0,
        )
    except Exception as e:
        logger.exception(
            "Invoice parsing failed",
            extra={
                "filename": file.filename,
                "error": str(e),
                "duration_ms": (time.perf_counter() - start_time) * 1000,
            },
        )
        raise

    parsed_data = completion.choices[0].message.parsed

    duration_ms = (time.perf_counter() - start_time) * 1000
    logger.info(
        "Invoice parsing completed",
        extra={
            "filename": file.filename,
            "contract_number": parsed_data.contract_number,
            "num_items": len(parsed_data.items) if parsed_data.items else 0,
            "duration_ms": round(duration_ms, 1),
            "dpi": dpi,
            "model": gpt_model,
        },
    )

    if parse_uktzed and parsed_data.items:

        async def classify(item: InvoiceItem) -> None:
            try:
                item.uktzed_suggestion = await get_uktzed_code(
                    client, item.description, item.article
                )
            except Exception:
                item.uktzed_suggestion = UktZedSuggestion(
                    code="0000000000",
                    description="Не вдалося визначити",
                    justification="Помилка при запиті класифікації",
                )

        import asyncio

        await asyncio.gather(*(classify(item) for item in parsed_data.items))
    else:
        for item in parsed_data.items:
            item.uktzed_suggestion = None

    return parsed_data
