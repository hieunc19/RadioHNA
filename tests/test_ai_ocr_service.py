import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import numpy as np
from PIL import Image

from app import config
from app.services.ai_ocr_service import LocalVietnameseAIOCR
from app.services.errors import DependencyUnavailable


class LocalVietnameseAIOCRTests(unittest.TestCase):
    def test_reports_missing_models_before_importing_ai_packages(self):
        with mock.patch.object(config, "ai_ocr_models_present", return_value=False):
            with self.assertRaises(DependencyUnavailable):
                LocalVietnameseAIOCR()._get_detector()

    @staticmethod
    def _rectangle(left, top, width, height):
        return [
            [left, top],
            [left + width, top],
            [left + width, top + height],
            [left, top + height],
        ]

    def test_clusters_same_row_before_sorting_left_to_right(self):
        left = self._rectangle(10, 13, 50, 10)
        right = self._rectangle(200, 10, 50, 10)
        below = self._rectangle(10, 35, 50, 10)

        ordered = LocalVietnameseAIOCR._sort_polygons([below, right, left])

        self.assertEqual(ordered, [left, right, below])

    def test_filters_low_confidence_polygons_from_numpy_payload(self):
        polygons = np.asarray(
            [self._rectangle(10, 10, 50, 12), self._rectangle(10, 40, 50, 12)],
            dtype="float32",
        )
        payload = {"dt_polys": polygons, "dt_scores": np.asarray([0.49, 0.90])}
        detector = SimpleNamespace(predict=lambda _path: [SimpleNamespace(json={"res": payload})])
        recognizer = SimpleNamespace(predict_batch=lambda crops: ["Dòng hợp lệ"] * len(crops))
        engine = LocalVietnameseAIOCR()
        engine._detector = detector
        engine._recognizer = recognizer

        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temporary:
            source = Path(temporary) / "page.png"
            Image.new("RGB", (100, 80), "white").save(source)
            with mock.patch.object(engine, "_crop_line", return_value=Image.new("RGB", (50, 20))) as crop:
                result = engine.recognize_image(source)

        self.assertEqual(result, "Dòng hợp lệ")
        self.assertEqual(crop.call_count, 1)

    def test_keeps_polygons_when_detector_does_not_return_scores(self):
        polygons = [self._rectangle(10, 10, 50, 12), self._rectangle(10, 40, 50, 12)]
        self.assertEqual(LocalVietnameseAIOCR._filter_polygons(polygons, None), polygons)
        self.assertEqual(LocalVietnameseAIOCR._filter_polygons(polygons, [0.9]), polygons)

    def test_crop_adds_padding_around_detected_text_line(self):
        image = np.full((80, 120, 3), 255, dtype=np.uint8)
        image[20:40, 20:90] = 0
        polygon = self._rectangle(20, 20, 70, 20)

        crop = LocalVietnameseAIOCR._crop_line(image, polygon)

        self.assertIsNotNone(crop)
        self.assertEqual(crop.mode, "RGB")
        self.assertGreater(crop.width, 70)
        self.assertGreater(crop.height, 20)


if __name__ == "__main__":
    unittest.main()
