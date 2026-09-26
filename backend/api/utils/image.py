"""Image processing utilities."""

import asyncio
import base64
import io
import logging
import os
from typing import List

import numpy as np
from pdf2image import convert_from_bytes
from PIL import Image

logger = logging.getLogger("broker.api.utils.image")

# Lambda layer binary path for Poppler
POPPLER_PATH = os.getenv("POPPLER_PATH")


def get_dpi() -> int:
    """Read PDF_DPI from the environment at request time.

    Lambda environment variables are available during the init phase and
    remain available on every invocation, so reading inside a function
    (rather than at module-import time) keeps the value fresh even with
    SnapStart, where module-level code is captured in the snapshot.
    """
    return int(os.getenv("PDF_DPI", "350"))


def get_gpt_model() -> str:
    """Read GPT_MODEL from the environment at request time."""
    return os.getenv("GPT_MODEL", "gpt-4o-2024-11-20")


async def convert_pdf_to_images(pdf_bytes: bytes, dpi: int) -> List[Image.Image]:
    """Run the blocking Poppler conversion outside the event loop."""
    kwargs = {"dpi": dpi}
    if POPPLER_PATH:
        kwargs["poppler_path"] = POPPLER_PATH
    return await asyncio.to_thread(convert_from_bytes, pdf_bytes, **kwargs)


async def process_file_to_images(file, dpi: int):
    """Process uploaded file (PDF or image) and return list of PIL Images."""
    content = await file.read()
    content_type = file.content_type or ""
    filename = file.filename or ""

    # Check if it's an image file
    is_image = content_type.startswith("image/") or any(
        filename.lower().endswith(ext)
        for ext in [".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff"]
    )

    if is_image:
        # Process as image - upscale to match PDF render DPI for consistent OCR quality
        image = Image.open(io.BytesIO(content))
        # Convert to RGB if necessary (e.g., PNG with transparency)
        if image.mode in ("RGBA", "LA", "P"):
            background = Image.new("RGB", image.size, (255, 255, 255))
            if image.mode == "P":
                image = image.convert("RGBA")
            background.paste(
                image,
                mask=image.split()[-1] if image.mode in ("RGBA", "LA") else None,
            )
            image = background

        # Upscale small images to match PDF render resolution
        target_width = int(8.27 * dpi)  # A4 width in inches * DPI
        if image.width < target_width:
            scale = target_width / image.width
            new_size = (int(image.width * scale), int(image.height * scale))
            image = image.resize(new_size, Image.LANCZOS)
            logger.info(
                "Upscaled image from %dx%d to %dx%d for DPI=%d",
                image.width,
                image.height,
                new_size[0],
                new_size[1],
                dpi,
            )

        # Crop whitespace to reduce tokens
        image = crop_whitespace(image)
        logger.info("Cropped image to %dx%d", image.width, image.height)

        return [image]
    else:
        # Process as PDF
        images = await convert_pdf_to_images(content, dpi)
        # Crop whitespace from each page
        cropped_images = [crop_whitespace(img) for img in images]
        for i, img in enumerate(cropped_images):
            logger.info("Cropped page %d to %dx%d", i + 1, img.width, img.height)
        return cropped_images


def crop_whitespace(
    image: Image.Image,
    threshold: int = 245,
    noise_tolerance: float = 0.02,
    padding: int = 10,
) -> Image.Image:
    """Crop whitespace/margins from document image.

    Args:
        image: PIL Image to crop
        threshold: Pixel value threshold (0-255). Pixels with all RGB values
                   >= threshold are considered whitespace.
        noise_tolerance: Maximum fraction of noise pixels allowed per row/column
                         before that row/column is considered content. This filters
                         out isolated speckles, shadows, and compression artifacts
                         common in scanned documents.
        padding: Extra pixels to keep around the detected content area.

    Returns:
        Cropped PIL Image with whitespace removed.
    """
    if image.mode != "RGB":
        image = image.convert("RGB")

    # Convert to numpy array for efficient operations
    arr = np.array(image)
    height, width = arr.shape[:2]

    # Create a mask of non-whitespace pixels (any channel below threshold)
    non_whitespace = np.any(arr < threshold, axis=2)

    # Determine which rows and columns have enough content to be kept
    # A row/column is considered content if it has at least (noise_tolerance * width/height)
    # non-whitespace pixels. This filters out isolated noise pixels.
    row_content_counts = np.sum(non_whitespace, axis=1)
    col_content_counts = np.sum(non_whitespace, axis=0)

    min_row_pixels = max(1, int(width * noise_tolerance))
    min_col_pixels = max(1, int(height * noise_tolerance))

    content_rows = row_content_counts >= min_row_pixels
    content_cols = col_content_counts >= min_col_pixels

    # Find the bounding box of content rows/columns
    content_row_indices = np.where(content_rows)[0]
    content_col_indices = np.where(content_cols)[0]

    # If no content found, return original
    if len(content_row_indices) == 0 or len(content_col_indices) == 0:
        return image

    top = content_row_indices[0]
    bottom = content_row_indices[-1]
    left = content_col_indices[0]
    right = content_col_indices[-1]

    # Add padding to avoid cutting off edges
    top = max(0, top - padding)
    bottom = min(height - 1, bottom + padding)
    left = max(0, left - padding)
    right = min(width - 1, right + padding)

    return image.crop((left, top, right + 1, bottom + 1))


def encode_image_to_base64(image: Image.Image, quality: int = 100) -> str:
    buffered = io.BytesIO()
    image.save(buffered, format="JPEG", quality=quality, optimize=True)
    return base64.b64encode(buffered.getvalue()).decode("utf-8")


async def build_image_payload(images: List[Image.Image]) -> List[dict]:
    """Build image payload for Vision API using high-quality JPEG."""
    encoded_images = await asyncio.gather(
        *(asyncio.to_thread(encode_image_to_base64, image, 100) for image in images)
    )
    mime_type = "image/jpeg"
    return [
        {
            "type": "image_url",
            "image_url": {"url": f"data:{mime_type};base64,{encoded_image}"},
        }
        for encoded_image in encoded_images
    ]
