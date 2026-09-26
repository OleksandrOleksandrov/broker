import unicodedata
from typing import List, Optional

from pydantic import BaseModel, Field

from .combined import CombinedDocumentData


class TransportDocumentsRow(BaseModel):
    contract: str = ""
    blank_1: str = ""
    net_weight_kg: Optional[int] = None
    border_crossing_point: str = ""
    carrier: str = ""
    nomenclature: str = ""
    unloading_city: str = ""
    blank_2: str = ""
    vehicle_number: str = ""
    values: List[str] = Field(
        default_factory=list,
        description="The same nine fields as a positional list, in order.",
    )


def _build_transport_documents_row(data: CombinedDocumentData) -> list[str]:
    summary = data.summary
    nomenclature = ", ".join(summary.nomenclature or [])
    return [
        summary.contract or "",
        "",
        str(summary.net_weight_kg) if summary.net_weight_kg is not None else "",
        summary.border_crossing_point or "",
        summary.carrier or "",
        nomenclature,
        summary.unloading_city or "",
        "",
        summary.vehicle_number or "",
    ]


def _identify_file_type(filename: str) -> str:
    """Identify document type from filename."""
    name = unicodedata.normalize("NFC", filename).lower()
    if "cmr" in name or unicodedata.normalize("NFC", "срм") in name:
        return "cmr"
    if (
        "invoice" in name
        or unicodedata.normalize("NFC", "інвойс") in name
        or unicodedata.normalize("NFC", "инвойс") in name
        or unicodedata.normalize("NFC", "накладна") in name
        or unicodedata.normalize("NFC", "счёт") in name
        or unicodedata.normalize("NFC", "счет") in name
    ):
        return "invoice"
    if (
        "application" in name
        or unicodedata.normalize("NFC", "заявка") in name
        or unicodedata.normalize("NFC", "заявление") in name
        or unicodedata.normalize("NFC", "заява") in name
    ):
        return "application"
    return "unknown"


# Lightweight models for fast parsing - only extract fields needed for TransportDocumentsRow
class LiteInvoiceItem(BaseModel):
    oil_group: str = Field(
        description="Description, if it's oil, take the petrochemicals, such as N700, DEG, SN 70, SN 80, SN 150 etc."
    )
    net_weight_kg: Optional[int] = Field(
        default=None, description="Загальна маса нетто в кілограмах"
    )


class LiteInvoiceData(BaseModel):
    contract_number: Optional[str] = Field(
        default=None,
        description=(
            "You are analyzing a potentially low-quality, blurry, or noisy scanned document. Locate and extract the primary contract number using the following instructions:"
            "1. Flexible Label Matching:"
            "- Look for terms like 'Contract №', 'Contract No.', 'Contract #', 'Agreement No.', 'Contr. No', 'Ref No.', or similar labels near document headers, title blocks, or top corners."
            "- Account for OCR artifacts where symbols or letters are distorted (e.g., '№' misread as 'N°', H°', 'S/N', or 'N.'; 'Contract' misread as 'C0ntract', 'Contr', or 'Cntract')."
            "2. Character Disambiguation:"
            "- Infer ambiguous characters based on common code structures (e.g., distinguishing digit '0' from letter 'O', or digit '1' from letter 'I'/'l')."
            "3. Spatial Fallback:"
            "- If the label is partially smudged or missing, look for prominent alphanumeric identifiers (e.g., '2024/CT-8891' or 'ABC-12345') located near the document title or header section."
            "4. Output Rules:"
            "- Output ONLY the extracted contract number itself (excluding the label like 'Contract No:')."
            "- Do not include extra commentary, punctuation, or formatting."
            "- If no contract number can be reliably identified, return strictly 'not found'."
        ),
    )
    items: List[LiteInvoiceItem] = Field(
        description="Список усіх позицій товарів у таблиці"
    )


class LiteApplicationItem(BaseModel):
    border_crossing_point: Optional[str] = Field(
        default=None, description="Пункт перетину кордону"
    )
    unloading_city: Optional[str] = Field(
        description="Адреса розвантаження. Take only the city name from the full address, e.g., 'Львів' or 'Lviv'.",
    )
    vehicle_info: Optional[str] = Field(
        default=None, description="Транспортний засіб (номери авто та причепа)"
    )
    carrier_details: Optional["LitePartyDetails"] = Field(
        default=None, description="Юридичні реквізити Перевізника"
    )


class LitePartyDetails(BaseModel):
    name: Optional[str] = Field(default=None, description="Найменування компанії / ФОП")


class LiteCMRCargoItem(BaseModel):
    name: Optional[str] = Field(
        default=None,
        description="9 Kravas nosaukums / Name of the goods[span_5](start_span)[span_5](end_span)",
    )


class LiteCMRDocument(BaseModel):
    delivery_city: Optional[str] = Field(
        default=None,
        description="3 Kravas izkraušanas vieta / Place of delivery of the goods. Take only the city name from the full address, e.g., 'Rīga' or 'Riga'.",
    )
    cargo_items: List[LiteCMRCargoItem] = Field(
        default_factory=list,
        description="Cargo details table (Fields 6-12)[span_19](start_span)[span_19](end_span)",
    )
    carrier: Optional[LitePartyDetails] = Field(
        default=None,
        description="16 Pārvadātājs / Carrier/forwarder[span_21](start_span)[span_21](end_span)",
    )


LiteApplicationItem.model_rebuild()
