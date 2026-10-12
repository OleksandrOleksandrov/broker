"""Transport documents combined parsing router."""

import asyncio
import os
from typing import List

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from ..models import (
    CombinedDocumentData,
    CombinedDocumentSummary,
    LiteApplicationItem,
    LiteCMRDocument,
    LiteInvoiceData,
    TransportDocumentsRow,
)
from ..utils import (
    parse_lite_invoice,
    parse_lite_application,
    parse_lite_cmr,
    build_lite_transport_documents_row,
    _identify_file_type,
    normalize_quotes,
)
from .invoice import parse_invoice as parse_invoice_full
from .application import parse_application as parse_application_full
from .cmr import parse_cmr as parse_cmr_full
from ..models import _build_transport_documents_row


router = APIRouter(prefix="/api", tags=["transport"])


async def parse_transport_documents(
    invoice_file: UploadFile,
    application_file: UploadFile,
    cmr_file: UploadFile,
    parse_uktzed: bool = False,
) -> CombinedDocumentData:
    invoice, application, cmr = await asyncio.gather(
        parse_invoice_full(invoice_file, parse_uktzed),
        parse_application_full(application_file),
        parse_cmr_full(cmr_file),
    )

    net_weights = [
        item.net_weight_kg for item in invoice.items if item.net_weight_kg is not None
    ]

    carrier = (
        normalize_quotes(application.carrier_details.name)
        if application.carrier_details
        else normalize_quotes(cmr.carrier.name_and_address)
        if cmr.carrier
        else None
    )

    nomenclature = [item.oil_group for item in invoice.items]
    if not nomenclature:
        nomenclature = [
            item.name_of_goods for item in cmr.cargo_items if item.name_of_goods
        ]

    summary = CombinedDocumentSummary(
        contract=invoice.contract_number.replace("-", ""),
        net_weight_kg=sum(net_weights) if net_weights else None,
        border_crossing_point=application.border_crossing_point,
        carrier=carrier,
        nomenclature=nomenclature,
        unloading_city=cmr.delivery_city.upper() or application.unloading_city.upper(),
        invoice_number=invoice.contract_number.replace("-", ""),
        vn_number_pd=invoice.contract_number.replace("-", ""),
        vehicle_number="".join(application.vehicle_info.split()),
        tax_document_number=invoice.contract_number.replace("-", ""),
    )
    return CombinedDocumentData(
        summary=summary,
        invoice=invoice,
        application=application,
        cmr=cmr,
    )


@router.post("/parse-transport-documents", response_model=CombinedDocumentData)
async def parse_transport_documents_endpoint(
    invoice_file: UploadFile = File(...),
    application_file: UploadFile = File(...),
    cmr_file: UploadFile = File(...),
    parse_uktzed: bool = Form(False),
):
    return await parse_transport_documents(
        invoice_file=invoice_file,
        application_file=application_file,
        cmr_file=cmr_file,
        parse_uktzed=parse_uktzed,
    )


@router.post("/parse-transport-documents-row", response_model=TransportDocumentsRow)
async def parse_transport_documents_row(
    files: List[UploadFile] = File(...),
    parse_uktzed: bool = Form(False),
):
    """Parse three transport documents and return a flat row of strings
    matching the legacy Spark `val(...)` column layout.
    Files can be uploaded in any order; type is determined from filename.
    """
    if len(files) != 3:
        raise HTTPException(status_code=400, detail="Exactly 3 files are required")

    invoice_file = None
    application_file = None
    cmr_file = None

    for file in files:
        file_type = _identify_file_type(file.filename or "")
        if file_type == "invoice":
            invoice_file = file
        elif file_type == "application":
            application_file = file
        elif file_type == "cmr":
            cmr_file = file

    missing = []
    if not invoice_file:
        missing.append("invoice")
    if not application_file:
        missing.append("application")
    if not cmr_file:
        missing.append("cmr")

    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Could not identify file types for: {', '.join(missing)}. "
            f"Filenames must contain 'invoice'/'інвойс'/'инвойс'/'накладна'/'счёт', "
            f"'application'/'заявка'/'заявление', or 'cmr' respectively.",
        )

    data = await parse_transport_documents(
        invoice_file=invoice_file,
        application_file=application_file,
        cmr_file=cmr_file,
        parse_uktzed=parse_uktzed,
    )
    values = _build_transport_documents_row(data)
    return TransportDocumentsRow(
        contract=values[0],
        blank_1=values[1],
        net_weight_kg=values[2] or None,
        border_crossing_point=values[3],
        carrier=values[4],
        nomenclature=values[5],
        unloading_city=values[6],
        blank_2=values[7],
        vehicle_number=values[8],
        values=values,
    )


@router.post("/parse-transport-documents-row-lite", response_model=TransportDocumentsRow)
async def parse_transport_documents_row_lite(
    files: List[UploadFile] = File(...),
):
    """Parse three transport documents using lightweight models for fast extraction
    of only the fields needed for TransportDocumentsRow.
    Files can be uploaded in any order; type is determined from filename.
    """
    if len(files) != 3:
        raise HTTPException(status_code=400, detail="Exactly 3 files are required")

    invoice_file = None
    application_file = None
    cmr_file = None

    for file in files:
        file_type = _identify_file_type(file.filename or "")
        if file_type == "invoice":
            invoice_file = file
        elif file_type == "application":
            application_file = file
        elif file_type == "cmr":
            cmr_file = file

    missing = []
    if not invoice_file:
        missing.append("invoice")
    if not application_file:
        missing.append("application")
    if not cmr_file:
        missing.append("cmr")

    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Could not identify file types for: {', '.join(missing)}. "
            f"Filenames must contain 'invoice'/'інвойс'/'инвойс'/'накладна'/'счёт', "
            f"'application'/'заявка'/'заявление', or 'cmr' respectively.",
        )

    # Parse all three documents in parallel using lightweight models
    invoice, application, cmr = await asyncio.gather(
        parse_lite_invoice(invoice_file),
        parse_lite_application(application_file),
        parse_lite_cmr(cmr_file),
    )

    values = build_lite_transport_documents_row(invoice, application, cmr)
    return TransportDocumentsRow(
        contract=values[0],
        blank_1=values[1],
        net_weight_kg=values[2] or None,
        border_crossing_point=values[3],
        carrier=values[4],
        nomenclature=values[5],
        unloading_city=values[6],
        blank_2=values[7],
        vehicle_number=values[8],
        values=values,
    )