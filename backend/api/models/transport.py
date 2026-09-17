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
    name = filename.lower()
    if "cmr" in name or "срм" in name:
        return "cmr"
    if (
        "invoice" in name
        or "інвойс" in name
        or "инвойс" in name
        or "накладна" in name
        or "счёт" in name
        or "счет" in name
    ):
        return "invoice"
    if (
        "application" in name
        or "заявка" in name
        or "заявление" in name
        or "заява" in name
    ):
        return "application"
    return "unknown"
