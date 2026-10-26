"""Đọc PDF hoặc nhận diện ảnh bằng các công cụ chạy cục bộ."""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app import config
from app.services.ai_ocr_service import get_local_ai_ocr
from app.services.errors import DependencyUnavailable, OCRProcessingError
from app.services.image_processor import prepare_for_ai_ocr, prepare_for_tesseract
from app.services.text_processor import find_suspicious_ocr_dates, postprocess_ocr_text
from app.utils.file_helper import new_job_directory
from app.utils.validators import validate_document_paths

ProgressCallback = Callable[[float, str], None]


@dataclass(frozen=True)
class OCRResult:
    text: str
    warnings: tuple[str, ...]
    page_count: int
    engine: str


def _has_meaningful_text(text: str) -> bool:
    """Avoid treating a tiny PDF footer/page number as extractable document text."""
    return len(re.sub(r"\s+", "", text)) >= 12


def _text_from_tesseract_data(data: dict[str, Sequence[Any]]) -> tuple[str, float]:
    """Rebuild ordered lines and calculate a character-weighted confidence."""
    lines: dict[tuple[int, int, int, int], list[str]] = {}
    weighted_score = 0.0
    weighted_length = 0
    texts = data.get("text", ())
    confidences = data.get("conf", ())
    for index, raw_text in enumerate(texts):
        word = str(raw_text).strip()
        if not word:
            continue
        key = tuple(
            int(data.get(field, [0] * len(texts))[index])
            for field in ("page_num", "block_num", "par_num", "line_num")
        )
        lines.setdefault(key, []).append(word)
        if index >= len(confidences):
            continue
        try:
            confidence = float(confidences[index])
        except (TypeError, ValueError):
            continue
        if confidence >= 0:
            weighted_score += confidence * len(word)
            weighted_length += len(word)
    text = "\n".join(" ".join(words) for words in lines.values()).strip()
    confidence = weighted_score / weighted_length if weighted_length else 0.0
    return text, confidence


def _read_pdf_text_pages(pdf_path: Path) -> list[str]:
    """Extract text-layer content page by page, without invoking OCR."""
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover - depends on environment
        raise DependencyUnavailable(
            "Chưa cài thư viện đọc PDF. Hãy cài requirements.txt hoặc dùng bộ cài đầy đủ."
        ) from exc

    try:
        reader = PdfReader(str(pdf_path))
        if reader.is_encrypted and reader.decrypt("") == 0:
            raise OCRProcessingError(f"{pdf_path.name}: PDF được bảo vệ bằng mật khẩu nên chưa thể đọc.")
        if len(reader.pages) > config.MAX_PDF_PAGES:
            raise OCRProcessingError(
                f"{pdf_path.name}: PDF có hơn {config.MAX_PDF_PAGES} trang, vượt giới hạn xử lý an toàn."
            )
        text_pages: list[str] = []
        for page in reader.pages:
            try:
                text = page.extract_text(extraction_mode="layout") or ""
            except TypeError:  # Backward compatibility with an older pypdf package.
                text = page.extract_text() or ""
            text_pages.append(text.strip())
        return text_pages
    except OCRProcessingError:
        raise
    except Exception as exc:  # noqa: BLE001 - PDF parser errors vary by producer and encryption mode.
        raise OCRProcessingError(f"Không thể đọc PDF {pdf_path.name}. Hãy thử một bản PDF hợp lệ khác.") from exc


def _render_pdf_page(pdf_path: Path, page_index: int, destination: Path) -> Path:
    """Render one scanned-PDF page to a local PNG for the existing OCR pipeline."""
    try:
        import pypdfium2 as pdfium
    except ImportError as exc:  # pragma: no cover - depends on environment
        raise DependencyUnavailable(
            "Chưa cài bộ render PDF. Hãy cài requirements.txt hoặc dùng bộ cài đầy đủ."
        ) from exc

    document: Any = None
    page: Any = None
    bitmap: Any = None
    image: Any = None
    try:
        document = pdfium.PdfDocument(str(pdf_path))
        page = document[page_index]
        # 4x PDFium scale is approximately 288 DPI, close to the resolution
        # at which Tesseract is most reliable for small Vietnamese diacritics.
        bitmap = page.render(scale=config.PDF_RENDER_SCALE)
        image = bitmap.to_pil()
        destination.parent.mkdir(parents=True, exist_ok=True)
        image.save(destination, format="PNG")
        return destination
    except Exception as exc:  # noqa: BLE001 - PDFium exposes version-dependent native errors.
        raise OCRProcessingError(f"Không thể chuyển {pdf_path.name} – trang {page_index + 1} thành ảnh.") from exc
    finally:
        for resource in (image, bitmap, page, document):
            close = getattr(resource, "close", None)
            if callable(close):
                close()


def iter_recognize_documents(
    document_paths: Sequence[str | Path] | None,
    progress: ProgressCallback | None = None,
) -> Iterator[OCRResult]:
    """Yield the current OCR result whenever a page has been processed.

    This lets an interactive caller reveal already-read pages while later pages
    are still being recognized.  The final yielded result includes document-wide
    checks such as suspicious date warnings.
    """
    paths = validate_document_paths(document_paths)
    job_dir = new_job_directory("ocr")
    pages: list[str] = []
    warnings: list[str] = []
    pytesseract: Any | None = None
    ai_ocr = get_local_ai_ocr()
    ai_error: str | None = None
    ai_used = False
    tesseract_primary_used = False
    tesseract_fallback_used = False
    pdf_text_used = False

    def snapshot(*, include_document_warnings: bool = False) -> OCRResult:
        raw_text = "\n\n".join(pages)
        cleaned_text = postprocess_ocr_text(raw_text)
        snapshot_warnings = list(warnings)
        if include_document_warnings:
            for fragment in find_suspicious_ocr_dates(cleaned_text):
                snapshot_warnings.append(f'Cần kiểm tra ngày/tháng OCR chưa rõ: “{fragment}”.')
        engines: list[str] = []
        if pdf_text_used:
            engines.append("trích xuất chữ PDF")
        if ai_used:
            engines.append("PaddleOCR + VietOCR")
        if tesseract_primary_used:
            engines.append("Tesseract tự động cho PDF scan")
        if tesseract_fallback_used:
            engines.append("Tesseract dự phòng")
        return OCRResult(
            text=cleaned_text,
            warnings=tuple(snapshot_warnings),
            page_count=len(pages),
            engine=" + ".join(engines) or "OCR cục bộ",
        )

    def get_tesseract() -> Any:
        nonlocal pytesseract
        if pytesseract is not None:
            return pytesseract
        try:
            import pytesseract as imported_tesseract
        except ImportError as exc:  # pragma: no cover - depends on environment
            raise DependencyUnavailable(
                "Chưa cài thư viện OCR. Hãy cài requirements.txt hoặc dùng bộ cài đầy đủ."
            ) from exc

        executable = config.find_tesseract()
        if not executable:
            raise DependencyUnavailable(
                "Không tìm thấy Tesseract cục bộ. Hãy đặt Tesseract vào bin/tesseract hoặc cấu hình TESSERACT_CMD."
            )
        config.configure_tesseract_environment()
        imported_tesseract.pytesseract.tesseract_cmd = executable
        try:
            languages = imported_tesseract.get_languages(config="")
        except imported_tesseract.TesseractNotFoundError as exc:
            raise DependencyUnavailable("Không khởi động được Tesseract cục bộ.") from exc
        if "vie" not in languages:
            raise DependencyUnavailable(
                "Tesseract chưa có dữ liệu tiếng Việt (vie.traineddata). Hãy bổ sung vào thư mục tessdata."
            )
        pytesseract = imported_tesseract
        return pytesseract

    def ocr_image(source: Path, output_name: str, label: str, *, prefer_tesseract: bool = False) -> str:
        nonlocal ai_error, ai_used, tesseract_primary_used, tesseract_fallback_used
        output_path = Path(output_name)
        tesseract_name = f"{output_path.stem}_tesseract{output_path.suffix or '.png'}"
        tesseract_prepared: Path | None = None
        tesseract_candidate = ""

        if prefer_tesseract:
            try:
                engine = get_tesseract()
                tesseract_prepared = prepare_for_tesseract(source, job_dir / tesseract_name)
                data = engine.image_to_data(
                    str(tesseract_prepared),
                    lang="vie",
                    config=config.OCR_TESSERACT_CONFIG,
                    output_type=engine.Output.DICT,
                )
                tesseract_candidate, confidence = _text_from_tesseract_data(data)
                if (
                    _has_meaningful_text(tesseract_candidate)
                    and confidence >= config.OCR_TESSERACT_AUTO_MIN_CONFIDENCE
                ):
                    tesseract_primary_used = True
                    return tesseract_candidate
            except (DependencyUnavailable, OCRProcessingError, OSError):
                # AI OCR remains available if Tesseract is absent or rejects the page.
                tesseract_candidate = ""

        if ai_error is None:
            try:
                ai_prepared = prepare_for_ai_ocr(source, job_dir / output_name)
                recognized = ai_ocr.recognize_image(ai_prepared)
                ai_used = True
                return recognized
            except (DependencyUnavailable, OCRProcessingError) as exc:
                ai_error = str(exc)
                warnings.append(f"OCR AI chưa khả dụng ({ai_error}). Đã chuyển sang Tesseract cục bộ.")

        if _has_meaningful_text(tesseract_candidate):
            tesseract_fallback_used = True
            warnings.append(
                f"{label}: Tesseract có độ tin cậy dưới "
                f"{config.OCR_TESSERACT_AUTO_MIN_CONFIDENCE:.0f}% nhưng được dùng vì OCR AI không khả dụng."
            )
            return tesseract_candidate

        engine = get_tesseract()
        try:
            if tesseract_prepared is None:
                tesseract_prepared = prepare_for_tesseract(source, job_dir / tesseract_name)
            recognized = engine.image_to_string(
                str(tesseract_prepared),
                lang="vie",
                config=config.OCR_TESSERACT_CONFIG,
            ).strip()
            tesseract_fallback_used = True
            return recognized
        except Exception as exc:  # noqa: BLE001 - one page failure must not discard other selected pages.
            raise OCRProcessingError(f"{label}: OCR không hoàn tất ({exc}).") from exc

    for source_index, source_path in enumerate(paths, start=1):
        source_fraction = (source_index - 1) / len(paths)
        if source_path.suffix.lower() != ".pdf":
            if progress:
                progress(source_fraction, f"Đang nhận diện ảnh {source_index}/{len(paths)}: {source_path.name}")
            try:
                text = ocr_image(source_path, f"image_{source_index:03d}.png", source_path.name)
            except OCRProcessingError as exc:
                warnings.append(str(exc))
                continue
            if text:
                pages.append(text)
                yield snapshot()
            else:
                warnings.append(f"{source_path.name}: không nhận diện được chữ. Hãy thử ảnh rõ hơn hoặc nhập tay.")
            continue

        if progress:
            progress(source_fraction, f"Đang đọc PDF {source_index}/{len(paths)}: {source_path.name}")
        text_pages = _read_pdf_text_pages(source_path)
        for page_index, text in enumerate(text_pages):
            label = f"{source_path.name} – trang {page_index + 1}"
            page_fraction = source_fraction + ((page_index + 1) / max(1, len(text_pages))) / len(paths)
            if _has_meaningful_text(text):
                pages.append(text)
                pdf_text_used = True
                if progress:
                    progress(page_fraction, f"Đã đọc văn bản từ {label}.")
                yield snapshot()
                continue

            if progress:
                progress(page_fraction, f"Đang OCR {label}…")
            try:
                rendered_path = job_dir / f"pdf_{source_index:03d}_{page_index:03d}.png"
                rendered = _render_pdf_page(source_path, page_index, rendered_path)
                recognized = ocr_image(
                    rendered,
                    f"pdf_ocr_{source_index:03d}_{page_index:03d}.png",
                    label,
                    prefer_tesseract=True,
                )
            except OCRProcessingError as exc:
                warnings.append(str(exc))
                continue
            if recognized:
                pages.append(recognized)
                yield snapshot()
            else:
                warnings.append(f"{label}: không nhận diện được chữ. Hãy thử PDF rõ hơn hoặc nhập tay.")

    if progress:
        progress(1.0, "Đã hoàn tất đọc văn bản.")
    if not pages:
        detail = " ".join(warnings) or "Không nhận diện được chữ từ các tệp đã chọn."
        raise OCRProcessingError(detail)
    yield snapshot(include_document_warnings=True)


def recognize_documents(
    document_paths: Sequence[str | Path] | None,
    progress: ProgressCallback | None = None,
) -> OCRResult:
    """Return the final result; retained for command-line and test callers."""
    result: OCRResult | None = None
    for snapshot in iter_recognize_documents(document_paths, progress):
        result = snapshot
    if result is None:  # Defensive: the iterator normally raises a user-facing error first.
        raise OCRProcessingError("Không nhận diện được chữ từ các tệp đã chọn.")
    return result


def recognize_images(
    image_paths: Sequence[str | Path] | None,
    progress: ProgressCallback | None = None,
) -> OCRResult:
    """Compatibility alias; the input now also supports PDF files."""
    return recognize_documents(image_paths, progress)
