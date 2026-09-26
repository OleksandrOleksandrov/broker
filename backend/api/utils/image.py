"""Image processing utilities."""

import asyncio
import base64
import io
import logging
import os
from typing import List

from pdf2image import convert_from_bytes
from PIL import Image

logger = logging.getLogger("broker.api.utils.image")

# Lambda layer binary path for Poppler
POPPLER_PATH = os.getenv("POPPLER_PATH")


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

        return [image], True  # Return flag indicating it's an original image
    else:
        # Process as PDF
        images = await convert_pdf_to_images(content, dpi)
        # Crop whitespace from each page
        cropped_images = [crop_whitespace(img) for img in images]
        for i, img in enumerate(cropped_images):
            logger.info("Cropped page %d to %dx%d", i + 1, img.width, img.height)
        return cropped_images, False


def crop_whitespace(image: Image.Image, threshold: int = 250) -> Image.Image:
    """Crop whitespace/margins from document image.

    Args:
        image: PIL Image to crop
        threshold: Pixel value threshold (0-255) to consider as whitespace.
                   Pixels with all RGB values >= threshold are considered whitespace.
    Returns:
        Cropped PIL Image with whitespace removed.
    """
    if image.mode != "RGB":
        image = image.convert("RGB")

    arr = image.load()
    width, height = image.size

    # Find bounding box of non-whitespace pixels
    left = width
    right = 0
    top = height
    bottom = 0

    for y in range(height):
        for x in range(width):
            r, g, b = arr[x, y]
            if r < threshold or g < threshold or b < threshold:
                if x < left:
                    left = x
                if x > right:
                    right = x
                if y < top:
                    top = y
                if y > bottom:
                    bottom = y

    # If no content found, return original
    if left > right or top > bottom:
        return image

    # Add small padding to avoid cutting off edges
    padding = 10
    left = max(0, left - padding)
    top = max(0, top - padding)
    right = min(width - 1, right + padding)
    bottom = min(height - 1, bottom + padding)

    return image.crop((left, top, right + 1, bottom + 1))


def encode_image_to_base64(image: Image.Image, quality: int = 100) -> str:
    buffered = io.BytesIO()
    image.save(buffered, format="JPEG", quality=quality, optimize=True)
    return base64.b64encode(buffered.getvalue()).decode("utf-8")


def encode_lossless_image_to_base64(image: Image.Image) -> str:
    buffered = io.BytesIO()
    image.save(buffered, format="PNG", optimize=True)
    return base64.b64encode(buffered.getvalue()).decode("utf-8")


async def build_image_payload(
    images: List[Image.Image], is_original_image: bool = False
) -> List[dict]:
    """Build image payload for Vision API. Use lossless PNG for original images, high-quality JPEG for PDF renders."""
    if is_original_image:
        # Use lossless PNG for original image uploads to preserve quality
        encoded_images = await asyncio.gather(
            *(
                asyncio.to_thread(encode_lossless_image_to_base64, image)
                for image in images
            )
        )
        mime_type = "image/png"
    else:
        # Use high-quality JPEG for PDF renders
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
