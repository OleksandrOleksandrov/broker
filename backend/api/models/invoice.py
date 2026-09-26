from typing import List, Optional

from pydantic import BaseModel, Field


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
    oil_group: str = Field(
        description="Description, if it's oil, take the petrochemicals, such as N700, DEG, SN 70, SN 80, SN 150 etc."
    )
    quantity: float = Field(description="Кількість товару")
    unit: str = Field(description="Одиниця виміру (шт, кг, м, pack тощо)")
    price_per_unit: float = Field(description="Ціна за одиницю")
    total_amount: float = Field(description="Загальна вартість позиції")
    country_of_origin: Optional[str] = Field(
        default=None, description="Країна походження товару"
    )
    net_weight_kg: Optional[int] = Field(
        default=None, description="Маса нетто позиції в кілограмах"
    )
    uktzed_suggestion: Optional[UktZedSuggestion] = Field(
        default=None, description="Автоматично згенерована підказка УКТ ЗЕД"
    )


class InvoiceData(BaseModel):
    contract_number: Optional[str] = Field(
        default=None,
        description=(
            "Locate the contract number. Usually it followed by 'Contract №' or 'Contract NO' or something similar. If not found, write 'not found'."
        ),
    )
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
