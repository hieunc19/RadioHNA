import tempfile
import unittest
from pathlib import Path

from PIL import Image

from app.services.image_processor import prepare_for_ai_ocr, prepare_for_tesseract


class ImageProcessorTests(unittest.TestCase):
    def test_ai_preparation_preserves_rgb_channels(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temporary:
            source = Path(temporary) / "source.png"
            destination = Path(temporary) / "ai.png"
            Image.new("RGB", (2000, 30), color=(210, 80, 30)).save(source)

            prepare_for_ai_ocr(source, destination)
            with Image.open(destination) as prepared:
                self.assertEqual(prepared.mode, "RGB")
                self.assertEqual(prepared.getpixel((100, 10)), (210, 80, 30))

    def test_tesseract_preparation_is_grayscale(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temporary:
            source = Path(temporary) / "source.png"
            destination = Path(temporary) / "tesseract.png"
            Image.new("RGB", (2000, 30), color=(210, 80, 30)).save(source)

            prepare_for_tesseract(source, destination)
            with Image.open(destination) as prepared:
                self.assertEqual(prepared.mode, "L")


if __name__ == "__main__":
    unittest.main()
