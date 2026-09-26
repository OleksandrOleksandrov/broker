"""UKT ZED classification utilities."""

from typing import Optional

from openai import OpenAI

from ..models import UktZedSuggestion
from .image import get_gpt_model


def get_uktzed_code(
    client: OpenAI, item_description: str, article: Optional[str]
) -> UktZedSuggestion:
    gpt_model = get_gpt_model()
    prompt = f"Товар: {item_description}. Артикул: {article or 'не вказано'}."

    completion = client.beta.chat.completions.parse(
        model=gpt_model,
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