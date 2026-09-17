import re
from typing import Optional

from pydantic import BaseModel, Field


_SUSPICIOUS_ADDRESS_TOKEN = re.compile(r"(?<!\d)(\d{1,3})\s*([/\-])\s*(\d)(?!\d)")

_ADDRESS_FIELDS = (
    "loading_address",
    "customs_outbound_address",
    "customs_inbound_address",
    "unloading_address",
)


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
    unloading_city: Optional[str] = Field(
        default=None,
        description="Адреса розвантаження. Take only the city name from the full address, e.g., 'Львів' or 'Lviv'.",
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


def find_suspicious_address_token(item: ApplicationItem) -> Optional[str]:
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
