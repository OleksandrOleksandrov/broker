"""Utility functions for the Broker AI Assistant API."""

from .image import (
    crop_whitespace,
    encode_image_to_base64,
    encode_lossless_image_to_base64,
    build_image_payload,
    convert_pdf_to_images,
    process_file_to_images,
)
from .pdf import compress_single_pdf
from .text import normalize_quotes
from .uktzed import get_uktzed_code
from .parsers import (
    parse_lite_invoice,
    parse_lite_application,
    parse_lite_cmr,
    build_lite_transport_documents_row,
    find_suspicious_address_token,
    _identify_file_type,
)

__all__ = [
    "crop_whitespace",
    "encode_image_to_base64",
    "encode_lossless_image_to_base64",
    "build_image_payload",
    "convert_pdf_to_images",
    "process_file_to_images",
    "compress_single_pdf",
    "normalize_quotes",
    "get_uktzed_code",
    "parse_lite_invoice",
    "parse_lite_application",
    "parse_lite_cmr",
    "build_lite_transport_documents_row",
    "find_suspicious_address_token",
    "_identify_file_type",
]