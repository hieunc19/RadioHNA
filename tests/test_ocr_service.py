import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app.services.errors import OCRProcessingError
from app.services.ocr_service import _text_from_tesseract_data, iter_recognize_documents, recognize_documents


class _FakePdfPage:
    def extract_text(self, **_kwargs):
        return "Nội dung văn bản có sẵn trong tệp PDF."


class _FakePdfReader:
    is_encrypted = False
    pages = [_FakePdfPage()]

    def __init__(self, _path):
        pass


class OCRServiceTests(unittest.TestCase):
    def test_rebuilds_tesseract_lines_and_weighted_confidence(self):
        data = {
            "text": ["Căn", "cứ", "Luật", "Giáo", "dục"],
            "conf": [90, 80, 95, 90, 85],
            "page_num": [1, 1, 1, 1, 1],
            "block_num": [1, 1, 1, 1, 1],
            "par_num": [1, 1, 1, 1, 1],
            "line_num": [1, 1, 1, 2, 2],
        }

        text, confidence = _text_from_tesseract_data(data)

        self.assertEqual(text, "Căn cứ Luật\nGiáo dục")
        self.assertGreater(confidence, 85)

    def test_reads_text_layer_pdf_without_tesseract(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temporary:
            pdf_path = Path(temporary) / "thong_bao.pdf"
            pdf_path.write_bytes(b"%PDF-1.4\n")
            fake_pypdf = SimpleNamespace(PdfReader=_FakePdfReader)

            with (
                patch.dict(sys.modules, {"pypdf": fake_pypdf}),
                patch("app.services.ocr_service.new_job_directory", return_value=Path(temporary)),
            ):
                result = recognize_documents([pdf_path])

        self.assertEqual(result.page_count, 1)
        self.assertIn("Nội dung văn bản", result.text)
        self.assertEqual(result.warnings, ())

    def test_prefers_ai_ocr_for_scanned_images(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temporary:
            image_path = Path(temporary) / "thong_bao.png"
            image_path.write_bytes(b"not-an-image")
            ai_engine = SimpleNamespace(recognize_image=lambda _path: "Nội dung AI tiếng Việt.")

            with (
                patch("app.services.ocr_service.new_job_directory", return_value=Path(temporary)),
                patch("app.services.ocr_service.prepare_for_ai_ocr", return_value=image_path),
                patch("app.services.ocr_service.prepare_for_tesseract") as prepare_tesseract,
                patch("app.services.ocr_service.get_local_ai_ocr", return_value=ai_engine),
            ):
                result = recognize_documents([image_path])

        self.assertEqual(result.page_count, 1)
        self.assertIn("Nội dung AI tiếng Việt", result.text)
        self.assertEqual(result.warnings, ())
        prepare_tesseract.assert_not_called()

    def test_prepares_a_separate_grayscale_image_only_for_tesseract_fallback(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temporary:
            image_path = Path(temporary) / "thong_bao.png"
            ai_path = Path(temporary) / "ai.png"
            tesseract_path = Path(temporary) / "tesseract.png"
            image_path.write_bytes(b"not-an-image")

            class FailingAI:
                @staticmethod
                def recognize_image(path):
                    self.assertEqual(path, ai_path)
                    raise OCRProcessingError("AI test failure")

            tesseract = SimpleNamespace(
                pytesseract=SimpleNamespace(tesseract_cmd=""),
                TesseractNotFoundError=RuntimeError,
                get_languages=lambda config="": ["vie"],
                image_to_string=lambda path, **_kwargs: (
                    "Nội dung Tesseract." if Path(path) == tesseract_path else ""
                ),
            )
            with (
                patch("app.services.ocr_service.new_job_directory", return_value=Path(temporary)),
                patch("app.services.ocr_service.prepare_for_ai_ocr", return_value=ai_path),
                patch("app.services.ocr_service.prepare_for_tesseract", return_value=tesseract_path),
                patch("app.services.ocr_service.get_local_ai_ocr", return_value=FailingAI()),
                patch("app.config.find_tesseract", return_value="tesseract.exe"),
                patch.dict(sys.modules, {"pytesseract": tesseract}),
            ):
                result = recognize_documents([image_path])

        self.assertIn("Nội dung Tesseract", result.text)
        self.assertIn("Tesseract dự phòng", result.engine)

    def test_yields_text_when_each_pdf_page_is_ready(self):
        class TwoPageReader:
            is_encrypted = False
            pages = [_FakePdfPage(), _FakePdfPage()]

            def __init__(self, _path):
                pass

        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temporary:
            pdf_path = Path(temporary) / "thong_bao.pdf"
            pdf_path.write_bytes(b"%PDF-1.4\n")
            fake_pypdf = SimpleNamespace(PdfReader=TwoPageReader)
            with (
                patch.dict(sys.modules, {"pypdf": fake_pypdf}),
                patch("app.services.ocr_service.new_job_directory", return_value=Path(temporary)),
            ):
                snapshots = list(iter_recognize_documents([pdf_path]))

        self.assertEqual([item.page_count for item in snapshots], [1, 2, 2])
        self.assertIn("Nội dung văn bản", snapshots[0].text)


if __name__ == "__main__":
    unittest.main()
