"""Lightweight document parsers for fast extraction."""

import os
import re
import time
import unicodedata
from typing import List, Optional

from openai import AsyncOpenAI

from ..models import (
    LiteApplicationItem,
    LiteCMRDocument,
    LiteInvoiceData,
    TransportDocumentsRow,
    ApplicationItem,
)
from .image import build_image_payload, process_file_to_images
from .text import normalize_quotes
from .logging_config import get_logger

dpi = 400
gpt_model = os.getenv("GPT_MODEL", "gpt-4o-2024-11-20")

_SUSPICIOUS_ADDRESS_TOKEN = re.compile(r"(?<!\d)(\d{1,3})\s*([/\-])\s*(\d)(?!\d)")

_ADDRESS_FIELDS = (
    "loading_address",
    "customs_outbound_address",
    "customs_inbound_address",
    "unloading_address",
)

logger = get_logger("parsers")


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


async def parse_lite_invoice(file) -> LiteInvoiceData:
    """Parse invoice with lightweight model - only extracts contract_number, oil_group, net_weight_kg."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not found in environment")

    client = AsyncOpenAI(api_key=api_key)
    
    logger.info(
        "Starting lite invoice parsing",
        extra={
            "filename": getattr(file, 'filename', 'unknown'),
            "dpi": dpi,
            "model": gpt_model,
        }
    )
    start_time = time.perf_counter()
    
    images = await process_file_to_images(file, dpi=dpi)
    
    logger.info(
        "File converted to images",
        extra={
            "filename": getattr(file, 'filename', 'unknown'),
            "num_pages": len(images),
            "dpi": dpi,
        }
    )

    content_payload = [
        {
            "type": "text",
            "text": (
                "Extract only the contract/invoice number and line items with oil_group (petrochemical name like N700, DEG, SN 70, SN 80, SN 150) "
                "and net_weight_kg. Return only these fields, nothing else."
            ),
        }
    ]
    content_payload.extend(await build_image_payload(images))

    completion = await client.beta.chat.completions.parse(
        model=gpt_model,
        messages=[
            {
                "role": "system",
                "content": "Extract only contract_number, and for each line item: oil_group and net_weight_kg. Be precise.",
            },
            {"role": "user", "content": content_payload},
        ],
        response_format=LiteInvoiceData,
        temperature=0.0,
    )
    
    duration_ms = (time.perf_counter() - start_time) * 1000
    parsed = completion.choices[0].message.parsed
    
    logger.info(
        "Lite invoice parsing completed",
        extra={
            "filename": getattr(file, 'filename', 'unknown'),
            "contract_number": parsed.contract_number,
            "num_items": len(parsed.items) if parsed.items else 0,
            "duration_ms": round(duration_ms, 1),
            "dpi": dpi,
            "model": gpt_model,
        }
    )
    return parsed


async def parse_lite_application(file) -> LiteApplicationItem:
    """Parse application with lightweight model - only extracts border_crossing_point, unloading_city, vehicle_info, carrier name."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not found in environment")

    client = AsyncOpenAI(api_key=api_key)
    
    logger.info(
        "Starting lite application parsing",
        extra={
            "filename": getattr(file, 'filename', 'unknown'),
            "dpi": dpi,
            "model": gpt_model,
        }
    )
    start_time = time.perf_counter()
    
    images = await process_file_to_images(file, dpi=dpi)
    
    logger.info(
        "File converted to images",
        extra={
            "filename": getattr(file, 'filename', 'unknown'),
            "num_pages": len(images),
            "dpi": dpi,
        }
    )

    content_payload = [
        {
            "type": "text",
            "text": (
                "Extract only: border_crossing_point, unloading_city (city name only), "
                "vehicle_info (vehicle registration numbers), and carrier_details.name. "
                "Return only these fields, nothing else."
            ),
        }
    ]
    content_payload.extend(await build_image_payload(images))

    completion = await client.beta.chat.completions.parse(
        model=gpt_model,
        messages=[
            {
                "role": "system",
                "content": "Extract only border_crossing_point, unloading_city, vehicle_info, and carrier_details.name. Be precise.",
            },
            {"role": "user", "content": content_payload},
        ],
        response_format=LiteApplicationItem,
        temperature=0.0,
    )
    
    duration_ms = (time.perf_counter() - start_time) * 1000
    parsed = completion.choices[0].message.parsed
    
    logger.info(
        "Lite application parsing completed",
        extra={
            "filename": getattr(file, 'filename', 'unknown'),
            "border_crossing_point": parsed.border_crossing_point,
            "unloading_city": parsed.unloading_city,
            "duration_ms": round(duration_ms, 1),
            "dpi": dpi,
            "model": gpt_model,
        }
    )
    return parsed


async def parse_lite_cmr(file) -> LiteCMRDocument:
    """Parse CMR with lightweight model - only extracts delivery_city, cargo_items.name_of_goods, carrier name."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not found in environment")

    client = AsyncOpenAI(api_key=api_key)
    
    logger.info(
        "Starting lite CMR parsing",
        extra={
            "filename": getattr(file, 'filename', 'unknown'),
            "dpi": dpi,
            "model": gpt_model,
        }
    )
    start_time = time.perf_counter()
    
    images = await process_file_to_images(file, dpi=dpi)
    
    logger.info(
        "File converted to images",
        extra={
            "filename": getattr(file, 'filename', 'unknown'),
            "num_pages": len(images),
            "dpi": dpi,
        }
    )

    content_payload = [
        {
            "type": "text",
            "text": (
                "Extract only: delivery_city (city name only), cargo_items with name_of_goods, "
                "and carrier.name_and_address. Return only these fields, nothing else."
            ),
        }
    ]
    content_payload.extend(await build_image_payload(images))

    completion = await client.beta.chat.completions.parse(
        model=gpt_model,
        messages=[
            {
                "role": "system",
                "content": "Extract only delivery_city, cargo_items.name_of_goods, and carrier.name_and_address. Be precise.",
            },
            {"role": "user", "content": content_payload},
        ],
        response_format=LiteCMRDocument,
        temperature=0.0,
    )
    
    duration_ms = (time.perf_counter() - start_time) * 1000
    parsed = completion.choices[0].message.parsed
    
    logger.info(
        "Lite CMR parsing completed",
        extra={
            "filename": getattr(file, 'filename', 'unknown'),
            "delivery_city": parsed.delivery_city,
            "num_cargo_items": len(parsed.cargo_items) if parsed.cargo_items else 0,
            "duration_ms": round(duration_ms, 1),
            "dpi": dpi,
            "model": gpt_model,
        }
    )
    return parsed


def build_lite_transport_documents_row(
    invoice: LiteInvoiceData,
    application: LiteApplicationItem,
    cmr: LiteCMRDocument,
) -> List[str]:
    """Build transport documents row from lightweight parsed data."""
    # Contract from invoice
    contract = invoice.contract_number or ""

    # Net weight from invoice items
    net_weights = [
        item.net_weight_kg for item in invoice.items if item.net_weight_kg is not None
    ]
    net_weight_kg = str(sum(net_weights)) if net_weights else ""

    # Border crossing point from application
    border_crossing_point = application.border_crossing_point or ""

    # Carrier from application or CMR
    carrier = ""
    if application.carrier_details and application.carrier_details.name:
        carrier = normalize_quotes(application.carrier_details.name) or ""
    elif cmr.carrier and cmr.carrier.name:
        carrier = normalize_quotes(cmr.carrier.name) or ""

    # Nomenclature from invoice oil_group or CMR name_of_goods
    nomenclature_parts = []
    for item in invoice.items:
        if item.oil_group:
            nomenclature_parts.append(item.oil_group)
    if not nomenclature_parts:
        for item in cmr.cargo_items:
            if item.name_of_goods:
                nomenclature_parts.append(item.name_of_goods)
    nomenclature = ", ".join(nomenclature_parts)

    # Unloading city from CMR or application
    unloading_city = ""
    if cmr.delivery_city:
        unloading_city = cmr.delivery_city.upper()
    elif application.unloading_city:
        unloading_city = application.unloading_city.upper()

    # Vehicle number from application
    vehicle_number = (
        "".join(application.vehicle_info.split()) if application.vehicle_info else ""
    )

    return [
        contract,
        "",
        net_weight_kg,
        border_crossing_point,
        carrier,
        nomenclature,
        unloading_city,
        "",
        vehicle_number,
    ]
