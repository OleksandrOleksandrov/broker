from typing import List, Optional

from pydantic import BaseModel, Field

from .application import ApplicationItem
from .cmr import CMRDocument
from .invoice import InvoiceData


class CombinedDocumentSummary(BaseModel):
    contract: Optional[str] = Field(default=None, description="Номер контракту")
    net_weight_kg: Optional[int] = Field(
        default=None, description="Загальна маса нетто в кілограмах"
    )
    border_crossing_point: Optional[str] = Field(
        default=None, description="Попередня декларация"
    )
    carrier: Optional[str] = Field(default=None, description="Перевізник")
    nomenclature: List[str] = Field(
        default_factory=list, description="Номенклатура товарів"
    )
    unloading_city: Optional[str] = Field(
        default=None,
        description="Місто розвантаження, тільки назва міста без вулиці та номера будинку",
    )
    invoice_number: Optional[str] = Field(
        default=None, description="Номер інвойсу / ВН номер (ПД)"
    )
    vn_number_pd: Optional[str] = Field(default=None, description="ВН номер (ПД)")
    vehicle_number: Optional[str] = Field(default=None, description="Номер машини")
    tax_document_number: Optional[str] = Field(
        default=None, description="Попередня декларация"
    )


class CombinedDocumentData(BaseModel):
    summary: CombinedDocumentSummary
    invoice: InvoiceData
    application: ApplicationItem
    cmr: CMRDocument
