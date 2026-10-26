"""Tiền xử lý ảnh riêng cho AI OCR và Tesseract cục bộ."""

from __future__ import annotations

from pathlib import Path

from app.services.errors import OCRProcessingError


def _upscale_small_image(image: object, target_width: int = 2000):
    """Upscale small document images while preserving their aspect ratio."""
    from PIL import Image

    if image.width >= target_width:
        return image
    ratio = target_width / image.width
    return image.resize(
        (target_width, max(1, int(image.height * ratio))),
        Image.Resampling.LANCZOS,
    )


def prepare_for_ai_ocr(source: Path, destination: Path) -> Path:
    """Correct orientation and retain RGB information for Paddle/VietOCR."""
    try:
        from PIL import Image, ImageOps
    except ImportError as exc:  # pragma: no cover - depends on environment
        raise OCRProcessingError("Thiếu Pillow để xử lý ảnh. Hãy cài các phụ thuộc của ứng dụng.") from exc

    try:
        with Image.open(source) as image:
            corrected = ImageOps.exif_transpose(image).convert("RGB")
            corrected = _upscale_small_image(corrected)
            destination.parent.mkdir(parents=True, exist_ok=True)
            corrected.save(destination, format="PNG", optimize=True)
    except (OSError, ValueError) as exc:
        raise OCRProcessingError(f"Không thể mở ảnh {source.name}. Hãy chọn lại ảnh JPG/PNG hợp lệ.") from exc
    return destination


def prepare_for_tesseract(source: Path, destination: Path) -> Path:
    """Create a moderate grayscale/contrast copy for Tesseract fallback."""
    try:
        from PIL import Image, ImageEnhance, ImageOps
    except ImportError as exc:  # pragma: no cover - depends on environment
        raise OCRProcessingError("Thiếu Pillow để xử lý ảnh. Hãy cài các phụ thuộc của ứng dụng.") from exc

    try:
        with Image.open(source) as image:
            corrected = ImageOps.exif_transpose(image).convert("L")
            corrected = ImageOps.autocontrast(corrected, cutoff=0.5)
            corrected = ImageEnhance.Contrast(corrected).enhance(1.15)
            corrected = _upscale_small_image(corrected)
            destination.parent.mkdir(parents=True, exist_ok=True)
            corrected.save(destination, format="PNG", optimize=True)
    except (OSError, ValueError) as exc:
        raise OCRProcessingError(f"Không thể mở ảnh {source.name}. Hãy chọn lại ảnh JPG/PNG hợp lệ.") from exc
    return destination


def prepare_for_ocr(source: Path, destination: Path) -> Path:
    """Backward-compatible alias for the AI OCR preparation path."""
    return prepare_for_ai_ocr(source, destination)
