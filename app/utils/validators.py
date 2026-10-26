"""Kiểm tra đầu vào trước khi OCR hoặc tổng hợp giọng nói."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from app.config import MAX_IMAGE_BYTES, MAX_PDF_BYTES
from app.services.errors import UserFacingError

ALLOWED_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}
ALLOWED_DOCUMENT_SUFFIXES = ALLOWED_IMAGE_SUFFIXES | {".pdf"}


def validate_document_paths(paths: Iterable[str | Path] | None) -> list[Path]:
    """Validate selected images/PDFs without changing their input order."""
    if not paths:
        raise UserFacingError("Hãy chọn ít nhất một ảnh JPG, PNG hoặc PDF trước khi nhận diện.")

    validated: list[Path] = []
    for value in paths:
        path = Path(value)
        extension = path.suffix.lower()
        if extension not in ALLOWED_DOCUMENT_SUFFIXES:
            raise UserFacingError(f"{path.name}: chỉ hỗ trợ ảnh JPG, PNG hoặc PDF.")
        if not path.is_file():
            raise UserFacingError(f"Không tìm thấy tệp: {path.name}.")
        maximum_bytes = MAX_PDF_BYTES if extension == ".pdf" else MAX_IMAGE_BYTES
        if path.stat().st_size > maximum_bytes:
            maximum_mb = maximum_bytes // (1024 * 1024)
            file_kind = "PDF" if extension == ".pdf" else "ảnh"
            raise UserFacingError(f"{path.name}: {file_kind} lớn hơn giới hạn {maximum_mb} MB.")
        validated.append(path)
    return validated


def validate_image_paths(paths: Iterable[str | Path] | None) -> list[Path]:
    """Backward-compatible alias retained for callers that only supplied images."""
    return validate_document_paths(paths)


def require_confirmed_text(text: str | None, confirmed: bool) -> str:
    """Require a deliberate human review before an MP3 can be created."""
    result = (text or "").strip()
    if not result:
        raise UserFacingError("Nội dung trống. Hãy nhận diện hoặc nhập nội dung trước khi tạo âm thanh.")
    if not confirmed:
        raise UserFacingError(
            "Hãy xác nhận đã kiểm tra nội dung, đặc biệt là ngày, giờ, số liệu và địa danh."
        )
    return result
