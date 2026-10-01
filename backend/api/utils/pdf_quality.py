"""Document readability scoring for adaptive GPT model selection.

Scanned documents vary wildly in quality. A crisp 300 DPI scan is parsed
reliably by a cheap model, while a blurry, noisy or faded fax-quality scan
needs the expensive multimodal model. Rather than approximating image quality
with proxy statistics, this module asks the question that actually matters:
how much text can an OCR engine recover from the page?

The score (0-100) combines two signals from a Tesseract pass:
  - Confidence - the mean confidence Tesseract reports across the words it
    found. This is the direct, empirical measure of how legible the text is,
    and it responds to blur, noise, fading and low resolution alike.
  - Volume     - how much text was recovered at all, so a page that is sharp
    but nearly blank does not score as highly readable.

The score is 0.70 * confidence + 0.30 * volume. Documents scoring at or above
``PDF_QUALITY_THRESHOLD`` (default 75) use the cheap model (``GPT_CHEAP_MODEL``,
default ``gpt-4o-2024-11-20``); anything below uses the expensive ``GPT_MODEL``.

The reference constants were calibrated against the sample scans in
``pdf_examples/`` and their artificially blurred, noised and faded variants.

Dependencies are deliberately minimal: numpy, Pillow and pytesseract only.
Otsu binarization is implemented here rather than via OpenCV, whose binary
would add roughly 120 MB to the Lambda deployment package and push it past
the function size limit. Tesseract itself is supplied by the Poppler Lambda
layer rather than the package.

If OCR cannot run at all - pytesseract missing, no Tesseract binary, or no
usable language data - the document scores 0 and is sent to the expensive
model. That is deliberate: OCR is now the only signal, so there is nothing
left to fall back on, and defaulting to the expensive model keeps an
unreadable document off the cheap model.
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from functools import cache
from typing import List, Optional

import numpy as np
from PIL import Image

from .image import build_image_payload

logger = logging.getLogger("broker.api.utils.pdf_quality")

try:
    import pytesseract
except ImportError:  # pragma: no cover - depends on env
    pytesseract = None  # type: ignore[assignment]

# Sentinel for one-time pytesseract configuration: ``None`` = not yet
# attempted, ``False`` = pytesseract or Tesseract binary unavailable,
# ``True`` = configured and ready.
_pytesseract_configured: Optional[bool] = None

# OCR render size. Tesseract accuracy plateaus well below the 350 DPI render
# size and the full-size run would dominate request latency.
OCR_MAX_SIDE = 1400

# Tesseract confidence that maps to a perfect OCR score, and the confidence
# that maps to zero. Clean 300 DPI scans measure 60-92 on these documents.
OCR_CONF_ZERO = 40.0
OCR_CONF_FULL = 90.0

# Characters expected on a normal page, where the volume term saturates.
OCR_CHARS_FULL = 600
# Below this an OCR pass recovered essentially nothing, which is treated as a
# hard failure regardless of the reported confidence.
OCR_CHARS_FLOOR = 150

# Maximum fraction of ink (black pixels after Otsu binarization) a page may
# carry and still be considered blank. A real document page is well above this;
# a blank page, a stray speckle, or a nearly-empty footer lands below it and is
# skipped without invoking Tesseract. Calibrated against pdf_examples/.
OCR_BLANK_INK_FRACTION = 0.005

# Relative importance of the two signals. Confidence dominates because it is
# the direct measure of legibility; volume guards against a nearly blank page
# being scored as clean.
CONFIDENCE_WEIGHT = 0.70
VOLUME_WEIGHT = 0.30

# A document is consistent across its pages, so only the first few are scored.
# Scoring every page of a 20-page scan would dominate request latency.
MAX_SCORED_PAGES = 3


@cache
def _tesseract_cmd() -> Optional[str]:
    """Locate the Tesseract binary.

    ``TESSERACT_CMD`` is honoured when it points at a real executable, but a
    stale or misconfigured value must not silently disable the readability
    check - falling back to the known Lambda layer locations and to PATH means
    a wrong environment variable degrades to "found it anyway" rather than
    routing every document to the expensive model.

    The result is cached: the binary location does not change during a
    container's lifetime, and re-running filesystem checks on every scored
    page is wasteful.
    """
    configured = os.getenv("TESSERACT_CMD")
    if configured and os.path.isfile(configured) and os.access(configured, os.X_OK):
        return configured

    # The Lambda layer is mounted at /opt, so its binaries land in /opt/bin.
    candidates = ["/opt/bin/tesseract", "/opt/poppler/bin/tesseract"]
    for candidate in candidates:
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            if configured:
                logger.warning(
                    "TESSERACT_CMD=%r is not executable, using %s instead",
                    configured,
                    candidate,
                )
            return candidate

    return shutil.which("tesseract")


def get_cheap_model() -> str:
    """Model used for documents that pass the quality threshold."""
    return os.getenv("GPT_CHEAP_MODEL", "gpt-4o-2024-11-20")


def get_expensive_model() -> str:
    """Model used for documents below the quality threshold (GPT_MODEL)."""
    return os.getenv("GPT_MODEL", "gpt-6.1-sol")


def get_quality_threshold() -> float:
    """Minimum quality score (0-100) required to use the cheap model."""
    raw = os.getenv("PDF_QUALITY_THRESHOLD", "75")
    try:
        return float(raw)
    except ValueError:
        logger.warning("Invalid PDF_QUALITY_THRESHOLD=%r, falling back to 75", raw)
        return 75.0


def _to_gray_array(image: Image.Image) -> np.ndarray:
    """Convert a PIL image to a writable uint8 grayscale numpy array.

    ``np.asarray`` on a PIL image can hand back a read-only view of the
    decoder buffer, so the result is always copied into owned memory.
    """
    if image.mode != "L":
        image = image.convert("L")
    return np.array(image, dtype=np.uint8, copy=True)


def _downscale(image: Image.Image, max_side: int = OCR_MAX_SIDE) -> Image.Image:
    """Downscale a PIL image so its longest side is at most max_side."""
    width, height = image.size
    longest = max(width, height)
    if longest <= max_side:
        return image
    scale = max_side / float(longest)
    return image.resize(
        (max(1, int(width * scale)), max(1, int(height * scale))), Image.LANCZOS
    )


def _otsu_threshold(gray: np.ndarray) -> int:
    """Return Otsu's optimal threshold for a uint8 grayscale array.

    Implemented directly on the histogram so that the readability check does
    not pull in OpenCV: its only use here was binarization, and the binary is
    worth roughly 120 MB in a Lambda deployment package.
    """
    hist = np.bincount(gray.ravel(), minlength=256).astype(np.float64)
    levels = np.arange(256, dtype=np.float64)

    weight_bg = np.cumsum(hist)
    weight_fg = weight_bg[-1] - weight_bg
    sum_bg = np.cumsum(hist * levels)
    sum_fg = sum_bg[-1] - sum_bg

    mean_bg = np.divide(sum_bg, weight_bg, out=np.zeros_like(sum_bg), where=weight_bg > 0)
    mean_fg = np.divide(sum_fg, weight_fg, out=np.zeros_like(sum_fg), where=weight_fg > 0)

    # Between-class variance is maximised at the best split.
    between_class = weight_bg * weight_fg * (mean_bg - mean_fg) ** 2
    return int(np.argmax(between_class))


def _prepare_for_ocr(image: Image.Image) -> tuple[Image.Image, float]:
    """Binarize and downscale a page for a fast, reliable OCR pass.

    Returns the prepared image together with the fraction of ink (black pixels
    after Otsu binarization) it carries. The ink fraction is used to skip blank
    pages before invoking Tesseract: a real document page sits well above
    ``OCR_BLANK_INK_FRACTION``, while a blank page, stray speckle or nearly-empty
    footer lands below it and is short-circuited.
    """
    gray = _to_gray_array(image)

    # Otsu separates text from background and neutralises uneven scanner
    # illumination and faded backgrounds, which is what keeps a washed-out
    # page from being misread as illegible. Text ends up black on white.
    threshold = _otsu_threshold(gray)
    binary = np.where(gray > threshold, 255, 0).astype(np.uint8)

    ink_fraction = float(np.mean(binary == 0))
    return _downscale(Image.fromarray(binary), OCR_MAX_SIDE), ink_fraction


def _configure_pytesseract() -> Optional[object]:
    """Return a configured pytesseract module, or None if unavailable.

    The pytesseract import and the ``tesseract_cmd`` assignment are performed
    once and reused across every page, instead of repeating the import
    machinery and the binary lookup on each scored page.
    """
    global _pytesseract_configured
    if _pytesseract_configured is not None:
        return pytesseract

    if pytesseract is None:
        logger.warning("pytesseract unavailable, readability not assessed")
        _pytesseract_configured = False
        return None

    cmd = _tesseract_cmd()
    if cmd:
        pytesseract.pytesseract.tesseract_cmd = cmd
        _pytesseract_configured = True
        return pytesseract

    logger.warning("Tesseract binary not found, readability not assessed")
    _pytesseract_configured = False
    return None


def _ocr_languages(pytesseract, prepared: Image.Image) -> Optional[dict]:
    """Run OCR, degrading to a simpler language set if one is unavailable.

    The Lambda layer may ship only a subset of the trained data requested via
    ``OCR_LANG``, so the configured language list is tried in full first and
    then narrowed. Readability does not depend on recognising the script
    correctly: the confidence and volume of the detected words are what
    matter, so English-only is a perfectly usable fallback.
    """
    configured = os.getenv("OCR_LANG", "eng+ukr")
    candidates = [configured]
    primary = configured.split("+")[0]
    if primary and primary != configured:
        candidates.append(primary)
    if "eng" not in candidates:
        candidates.append("eng")

    for lang in candidates:
        try:
            return pytesseract.image_to_data(
                prepared, output_type=pytesseract.Output.DICT, lang=lang
            )
        except Exception as exc:
            logger.warning("OCR with lang=%s failed: %s", lang, exc)

    return None


def _ocr_measurements(image: Image.Image) -> Optional[dict]:
    """Return OCR character count and mean confidence for one page.

    Returns None when pytesseract or the Tesseract binary is unavailable, or
    when OCR fails for any other reason. Pages that carry essentially no ink
    are treated as unreadable (zero characters) without invoking Tesseract.
    """
    configured = _configure_pytesseract()
    if configured is None:
        return None

    try:
        prepared, ink_fraction = _prepare_for_ocr(image)
    except Exception as exc:
        logger.warning("Page preprocessing failed, readability not assessed: %s", exc)
        return None

    if ink_fraction < OCR_BLANK_INK_FRACTION:
        # Nothing to read: skip the Tesseract subprocess entirely.
        logger.info(
            "Skipping OCR on blank page (ink fraction %.4f < %.4f)",
            ink_fraction,
            OCR_BLANK_INK_FRACTION,
        )
        return {"chars": 0, "mean_conf": 0.0}

    try:
        data = _ocr_languages(configured, prepared)
    except Exception as exc:
        logger.warning("OCR failed, readability not assessed: %s", exc)
        return None

    if data is None:
        return None

    confidences = []
    char_count = 0
    for text, conf in zip(data.get("text", []), data.get("conf", []), strict=False):
        text = (text or "").strip()
        if not text:
            continue
        char_count += len(text)
        try:
            conf_value = float(conf)
        except (TypeError, ValueError):
            continue
        # Tesseract reports -1 for non-text regions.
        if conf_value >= 0:
            confidences.append(conf_value)

    mean_conf = float(np.mean(confidences)) if confidences else 0.0
    return {"chars": char_count, "mean_conf": mean_conf}


def readability_score(image: Image.Image) -> Optional[float]:
    """Score how much text an OCR engine can actually recover from the page.

    Blends OCR confidence with the volume of text found, so a page that is
    legible but nearly blank does not score as highly readable. Returns None
    when OCR is unavailable.
    """
    measurements = _ocr_measurements(image)
    if measurements is None:
        return None

    mean_conf = measurements["mean_conf"]
    char_count = measurements["chars"]

    if char_count < OCR_CHARS_FLOOR:
        # Tesseract found almost nothing. Whether it reports low confidence or
        # a few spurious glyphs, the page is effectively unreadable.
        return 0.0

    confidence_component = (
        float(
            np.clip(
                (mean_conf - OCR_CONF_ZERO) / (OCR_CONF_FULL - OCR_CONF_ZERO),
                0.0,
                1.0,
            )
        )
        * 100.0
    )
    volume_component = float(np.clip(char_count / OCR_CHARS_FULL, 0.0, 1.0)) * 100.0
    return CONFIDENCE_WEIGHT * confidence_component + VOLUME_WEIGHT * volume_component


@dataclass
class QualityReport:
    """Aggregated quality assessment for a single document."""

    score: float
    threshold: float
    metrics: dict = field(default_factory=dict)
    num_pages: int = 0

    @property
    def is_good_quality(self) -> bool:
        return self.score >= self.threshold

    @property
    def model(self) -> str:
        """Model chosen for this document's quality."""
        if self.is_good_quality:
            return get_cheap_model()
        return get_expensive_model()


def _score_page(image: Image.Image, page_index: int) -> Optional[float]:
    """Score a single page, logging and swallowing any errors."""
    try:
        return readability_score(image)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning(
            "Readability check failed on page %d: %s", page_index + 1, exc
        )
        return None


def _score_document(images: List[Image.Image]) -> QualityReport:
    """Compute the aggregated quality report for a list of page images."""
    pages = images[:MAX_SCORED_PAGES]

    if not pages:
        logger.warning("Readability could not be assessed, defaulting to low score")
        return QualityReport(
            score=0.0,
            threshold=get_quality_threshold(),
            metrics={},
            num_pages=len(images),
        )

    # OCR spawns a Tesseract subprocess per page and releases the GIL while
    # waiting on it, so the pages can be scored concurrently. This overlaps
    # the subprocess wall time rather than paying it one page at a time.
    with ThreadPoolExecutor(max_workers=len(pages)) as executor:
        futures = [
            executor.submit(_score_page, image, page_index)
            for page_index, image in enumerate(pages)
        ]
        scored = [f.result() for f in futures]

    scores = [s for s in scored if s is not None]

    if not scores:
        # OCR could not run on any page. Default to the worst case rather than
        # silently sending an unassessed document to the cheap model.
        logger.warning("Readability could not be assessed, defaulting to low score")
        return QualityReport(
            score=0.0,
            threshold=get_quality_threshold(),
            metrics={},
            num_pages=len(images),
        )

    return QualityReport(
        score=round(float(np.mean(scores)), 1),
        threshold=get_quality_threshold(),
        metrics={"readability": round(float(np.mean(scores)), 1)},
        num_pages=len(images),
    )


async def pdf_score(images: List[Image.Image]) -> QualityReport:
    """Score the readability of a document's rendered pages.

    Args:
        images: Page images produced by ``process_file_to_images``.

    Returns:
        A QualityReport with a 0-100 score and the model it maps to. The score
        is 0 when OCR could not run, which routes the document to the
        expensive model.
    """
    if not images:
        logger.warning("No pages to score, defaulting to low quality")
        return QualityReport(
            score=0.0, threshold=get_quality_threshold(), metrics={}, num_pages=0
        )

    return await asyncio.to_thread(_score_document, images)


async def select_model_for_images(images: List[Image.Image]) -> tuple[str, QualityReport]:
    """Return the GPT model to use for a document plus its quality report.

    Documents at or above the quality threshold go to the cheap model;
    everything else goes to the expensive ``GPT_MODEL``.
    """
    report = await pdf_score(images)

    logger.info(
        "Document readability assessed",
        extra={
            "quality_score": report.score,
            "quality_threshold": report.threshold,
            "quality_metrics": report.metrics,
            "num_pages": report.num_pages,
            "selected_model": report.model,
        },
    )

    return report.model, report


async def select_model_and_payload(
    images: List[Image.Image],
) -> tuple[str, QualityReport, List[dict]]:
    """Score document quality and build the vision payload concurrently.

    The chosen GPT model depends only on OCR readability, while the JPEG
    payload depends only on the page images themselves. The two passes are
    independent, so running them in parallel hides the JPEG encoding cost behind
    the OCR cost rather than adding it to the tail of the request.
    """
    (model, report), payload = await asyncio.gather(
        select_model_for_images(images),
        build_image_payload(images),
    )
    return model, report, payload
