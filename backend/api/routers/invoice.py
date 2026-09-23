"""Invoice parsing router."""

import os
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from openai import AsyncOpenAI

from ..models import InvoiceData, InvoiceItem, UktZedSuggestion
from ..utils import get_uktzed_code, build_image_payload, process_file_to_images

router = APIRouter(prefix="/api", tags=["invoice"])

dpi = 350
gpt_model = os.getenv("GPT_MODEL", "gpt-4o-2024-11-20")


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
    images, is_original = await process_file_to_images(file, dpi=dpi)

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

    content_payload.extend(await build_image_payload(images, is_original))

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
    except Exception:
        raise

    parsed_data = completion.choices[0].message.parsed

    if parse_uktzed and parsed_data.items:
        async def classify(item: InvoiceItem) -> None:
            try:
                item.uktzed_suggestion = await get_uktzed_code(client, item.description, item.article)
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