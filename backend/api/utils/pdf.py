"""PDF processing utilities."""

import io
import logging
import os
from typing import Optional

from pdf2image import convert_from_bytes
from PIL import Image
from pypdf import PdfReader, PdfWriter

logger = logging.getLogger("broker.api.utils.pdf")

POPPLER_PATH = os.getenv("POPPLER_PATH")


def compress_single_pdf(pdf_bytes: bytes, max_size_kb: int, remove_color: bool) -> bytes:
    """Compress a single PDF to target size in KB."""
    DPI = 150
    max_size_bytes = max_size_kb * 1024

    reader = PdfReader(io.BytesIO(pdf_bytes))
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    for page in writer.pages:
        page.compress_content_streams()

    buf = io.BytesIO()
    writer.write(buf)
    compressed = buf.getvalue()

    def _try_grayscale(dpi: int) -> bytes:
        if POPPLER_PATH:
            images = convert_from_bytes(pdf_bytes, dpi=dpi, poppler_path=POPPLER_PATH)
        else:
            images = convert_from_bytes(pdf_bytes, dpi=dpi)
        gray_images = [img.convert("L") for img in images]
        out = io.BytesIO()
        gray_images[0].save(
            out,
            format="PDF",
            save_all=True,
            append_images=gray_images[1:],
            resolution=dpi,
            optimize=True,
        )
        return out.getvalue()

    def _try_quality(dpi: int, quality: int) -> bytes:
        if POPPLER_PATH:
            images = convert_from_bytes(pdf_bytes, dpi=dpi, poppler_path=POPPLER_PATH)
        else:
            images = convert_from_bytes(pdf_bytes, dpi=dpi)
        if remove_color:
            images = [img.convert("L") for img in images]
        out = io.BytesIO()
        images[0].save(
            out,
            format="PDF",
            save_all=True,
            append_images=images[1:],
            resolution=dpi,
            optimize=True,
            quality=quality,
        )
        return out.getvalue()

    if len(compressed) > max_size_bytes:
        logger.info(
            "Initial lossless size=%d bytes, target=%d bytes",
            len(compressed),
            max_size_bytes,
        )

        if remove_color:
            try:
                compressed = _try_grayscale(DPI)
                logger.info("Grayscale size=%d bytes", len(compressed))
            except Exception:
                logger.exception("Grayscale compression attempt failed")

        if len(compressed) > max_size_bytes:
            quality = 95
            while len(compressed) > max_size_bytes and quality >= 40:
                try:
                    compressed = _try_quality(DPI, quality)
                    logger.info("Quality=%d size=%d bytes", quality, len(compressed))
                    if len(compressed) <= max_size_bytes:
                        break
                except Exception:
                    logger.exception("Quality compression attempt failed")
                    break
                quality -= 5

        if len(compressed) > max_size_bytes:
            dpi = 150
            while len(compressed) > max_size_bytes and dpi >= 50:
                quality = 95
                while len(compressed) > max_size_bytes and quality >= 40:
                    try:
                        compressed = _try_quality(dpi, quality)
                        logger.info(
                            "DPI=%d quality=%d size=%d bytes",
                            dpi,
                            quality,
                            len(compressed),
                        )
                        if len(compressed) <= max_size_bytes:
                            break
                    except Exception:
                        logger.exception("DPI/quality compression attempt failed")
                        break
                    quality -= 5
                if len(compressed) <= max_size_bytes:
                    break
                dpi -= 25

    if len(compressed) > max_size_bytes:
        raise ValueError(f"Мінімальний досяжний розмір: {len(compressed) // 1024} KB")

    return compressed