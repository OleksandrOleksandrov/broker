"""Application parsing router."""

import os
from typing import Optional

from fastapi import APIRouter, File, HTTPException, UploadFile
from openai import AsyncOpenAI

from ..models import ApplicationItem
from ..utils import build_image_payload, process_file_to_images, find_suspicious_address_token

router = APIRouter(prefix="/api", tags=["application"])

dpi = 400
gpt_model = os.getenv("GPT_MODEL", "gpt-4o-2024-11-20")


@router.post("/parse-application", response_model=ApplicationItem)
async def parse_application(
    file: UploadFile = File(...),
):
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=500, detail="OPENAI_API_KEY не знайдено в оточенні"
        )

    client = AsyncOpenAI(api_key=api_key)
    images = await process_file_to_images(file, dpi=dpi)

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

    content_payload.extend(await build_image_payload(images))

    system_prompt = (
        "Ти професійний логіст. Точно зчитуй дані з документа без фантазування.\n"
        "ПРАВИЛО ЩОДО АДРЕС: в українських номерах будинків після '/' або '-' зазвичай "
        "стоїть ЛІТЕРА, а не цифра (1/б, 25-А, 48В). Копіюй символи як у документі, не "
        "замінюй кириличні літери на схожі цифри.\n"
        "Приклад: 'вул. Хмельницького, 1/б' — коректно як '1/б', НЕ як '1/6'."
    )

    async def _extract(retry_hint: Optional[str] = None) -> ApplicationItem:
        user_text = content_payload[0]["text"]
        if retry_hint:
            user_text = (
                user_text + "\n\nУВАГА: попередня відповідь містила підозрілий токен "
                f"{retry_hint!r} (цифра після '/' або '-' у номері будинку). "
                "Перечитай адресу в документі та виправ її. Після '/' або '-' має стояти ЛІТЕРА."
            )
        payload = [{"type": "text", "text": user_text}, *content_payload[1:]]
        completion = await client.beta.chat.completions.parse(
            model=gpt_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": payload},
            ],
            response_format=ApplicationItem,
            temperature=0.0,
        )
        return completion.choices[0].message.parsed

    parsed = await _extract()
    for _attempt in range(2):
        offending = find_suspicious_address_token(parsed)
        if not offending:
            break
        parsed = await _extract(retry_hint=offending)

    return parsed