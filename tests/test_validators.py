import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from app.services.errors import UserFacingError
from app.utils.validators import require_confirmed_text, validate_document_paths


class ValidatorTests(unittest.TestCase):
    def test_requires_explicit_confirmation(self):
        with self.assertRaises(UserFacingError):
            require_confirmed_text("Nội dung đã nhập", False)

    def test_accepts_confirmed_non_empty_text(self):
        self.assertEqual(require_confirmed_text("  Bản tin  ", True), "Bản tin")

    def test_rejects_empty_text(self):
        with self.assertRaises(UserFacingError):
            require_confirmed_text("   ", True)

    def test_accepts_pdf_input(self):
        with TemporaryDirectory(dir=Path(__file__).parent) as temporary:
            pdf_path = Path(temporary) / "thong_bao.pdf"
            pdf_path.write_bytes(b"%PDF-1.4\n")

            self.assertEqual(validate_document_paths([pdf_path]), [pdf_path])


if __name__ == "__main__":
    unittest.main()
