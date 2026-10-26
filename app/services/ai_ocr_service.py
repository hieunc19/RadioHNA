"""Offline Vietnamese OCR: Paddle line detection followed by VietOCR reading."""

from __future__ import annotations

import math
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from app import config
from app.services.errors import DependencyUnavailable, OCRProcessingError

_shared_engine: LocalVietnameseAIOCR | None = None


class LocalVietnameseAIOCR:
    """Lazy local OCR engine that never downloads models during application use."""

    def __init__(self) -> None:
        self._detector: Any | None = None
        self._recognizer: Any | None = None

    def _get_detector(self) -> Any:
        if self._detector is not None:
            return self._detector
        if not config.ai_ocr_models_present():
            raise DependencyUnavailable(
                "Thiếu model OCR AI cục bộ. Hãy chạy scripts/prepare_offline_assets.py "
                "trên máy có Internet trước khi phát hành."
            )
        config.configure_ocr_environment(offline=True)
        try:
            from paddleocr import TextDetection

            self._detector = TextDetection(model_dir=str(config.PADDLE_DETECTION_MODEL_DIR), device="cpu")
        except ImportError as exc:
            raise DependencyUnavailable("Thiếu PaddleOCR. Hãy cài requirements.txt của ứng dụng.") from exc
        except Exception as exc:  # Paddle native errors vary by CPU/runtime.
            raise DependencyUnavailable("Không thể nạp model phát hiện chữ PaddleOCR cục bộ.") from exc
        return self._detector

    def _get_recognizer(self) -> Any:
        if self._recognizer is not None:
            return self._recognizer
        if not config.ai_ocr_models_present():
            raise DependencyUnavailable(
                "Thiếu model VietOCR cục bộ. Hãy chạy scripts/prepare_offline_assets.py trước."
            )
        try:
            from vietocr.tool.config import Cfg
            from vietocr.tool.predictor import Predictor

            engine_config = Cfg.load_config_from_file(str(config.VIETOCR_CONFIG_PATH))
            engine_config["device"] = "cpu"
            engine_config["weights"] = str(config.VIETOCR_WEIGHTS_PATH)
            engine_config["quiet"] = True
            engine_config.setdefault("cnn", {})["pretrained"] = False
            self._recognizer = Predictor(engine_config)
        except ImportError as exc:
            raise DependencyUnavailable("Thiếu VietOCR. Hãy cài requirements.txt của ứng dụng.") from exc
        except Exception as exc:  # Torch/model errors need a short user-facing message.
            raise DependencyUnavailable("Không thể nạp model nhận dạng tiếng Việt VietOCR cục bộ.") from exc
        return self._recognizer

    @staticmethod
    def _sort_polygons(polygons: Sequence[Sequence[Sequence[float]]]) -> list[Sequence[Sequence[float]]]:
        """Cluster slightly misaligned polygons into rows, then read left-to-right."""
        measured: list[tuple[float, float, float, Sequence[Sequence[float]]]] = []
        for polygon in polygons:
            if len(polygon) == 0:
                continue
            xs = [float(point[0]) for point in polygon]
            ys = [float(point[1]) for point in polygon]
            measured.append((sum(ys) / len(ys), max(1.0, max(ys) - min(ys)), min(xs), polygon))

        rows: list[dict[str, Any]] = []
        for center_y, height, left_x, polygon in sorted(measured, key=lambda item: item[0]):
            matching_row = None
            matching_distance = float("inf")
            for row in rows:
                distance = abs(center_y - row["center_y"])
                tolerance = max(3.0, min(height, row["height"]) * 0.55)
                if distance <= tolerance and distance < matching_distance:
                    matching_row = row
                    matching_distance = distance
            if matching_row is None:
                rows.append(
                    {
                        "center_y": center_y,
                        "height": height,
                        "items": [(left_x, polygon)],
                    }
                )
                continue
            count = len(matching_row["items"])
            matching_row["center_y"] = (matching_row["center_y"] * count + center_y) / (count + 1)
            matching_row["height"] = (matching_row["height"] * count + height) / (count + 1)
            matching_row["items"].append((left_x, polygon))

        ordered: list[Sequence[Sequence[float]]] = []
        for row in sorted(rows, key=lambda item: item["center_y"]):
            ordered.extend(polygon for _, polygon in sorted(row["items"], key=lambda item: item[0]))
        return ordered

    @staticmethod
    def _filter_polygons(
        polygons: Sequence[Sequence[Sequence[float]]],
        scores: Sequence[Any] | None,
    ) -> list[Sequence[Sequence[float]]]:
        """Drop explicitly low-confidence detections without losing legacy payloads."""
        if scores is None:
            return list(polygons)
        try:
            score_values = list(scores)
        except TypeError:
            return list(polygons)
        if len(score_values) != len(polygons):
            return list(polygons)
        filtered: list[Sequence[Sequence[float]]] = []
        for index, polygon in enumerate(polygons):
            try:
                score = float(score_values[index])
                if not math.isfinite(score) or score >= config.OCR_DETECTION_MIN_SCORE:
                    filtered.append(polygon)
            except (TypeError, ValueError):
                # An unknown score format must not silently discard real text.
                filtered.append(polygon)
        return filtered

    @staticmethod
    def _crop_line(image: Any, polygon: Sequence[Sequence[float]]) -> Any | None:
        """Perspective-correct one Paddle quadrilateral into a VietOCR line image."""
        try:
            import cv2
            import numpy as np
            from PIL import Image
        except ImportError as exc:  # pragma: no cover - dependency check is environment-specific
            raise DependencyUnavailable("Thiếu thư viện xử lý ảnh cho OCR AI.") from exc

        if len(polygon) != 4:
            return None
        points = np.asarray(polygon, dtype="float32")
        sums = points.sum(axis=1)
        differences = np.diff(points, axis=1).reshape(-1)
        top_left = points[np.argmin(sums)]
        bottom_right = points[np.argmax(sums)]
        top_right = points[np.argmin(differences)]
        bottom_left = points[np.argmax(differences)]
        ordered = np.asarray((top_left, top_right, bottom_right, bottom_left), dtype="float32")

        width = int(max(np.linalg.norm(bottom_right - bottom_left), np.linalg.norm(top_right - top_left)))
        height = int(max(np.linalg.norm(top_right - bottom_right), np.linalg.norm(top_left - bottom_left)))
        if width < 4 or height < 4:
            return None

        padding = max(
            config.OCR_LINE_PADDING_MIN_PX,
            min(config.OCR_LINE_PADDING_MAX_PX, int(round(height * config.OCR_LINE_PADDING_RATIO))),
        )

        def unit(vector: Any) -> Any:
            length = float(np.linalg.norm(vector))
            return vector / length if length else vector

        horizontal = unit((top_right - top_left) + (bottom_right - bottom_left))
        vertical = unit((bottom_left - top_left) + (bottom_right - top_right))
        ordered = np.asarray(
            (
                top_left - horizontal * padding - vertical * padding,
                top_right + horizontal * padding - vertical * padding,
                bottom_right + horizontal * padding + vertical * padding,
                bottom_left - horizontal * padding + vertical * padding,
            ),
            dtype="float32",
        )
        ordered[:, 0] = np.clip(ordered[:, 0], 0, image.shape[1] - 1)
        ordered[:, 1] = np.clip(ordered[:, 1], 0, image.shape[0] - 1)

        top_left, top_right, bottom_right, bottom_left = ordered
        width = int(max(np.linalg.norm(bottom_right - bottom_left), np.linalg.norm(top_right - top_left)))
        height = int(max(np.linalg.norm(top_right - bottom_right), np.linalg.norm(top_left - bottom_left)))
        if width < 4 or height < 4:
            return None
        target = np.asarray(
            ((0, 0), (width - 1, 0), (width - 1, height - 1), (0, height - 1)), dtype="float32"
        )
        transform = cv2.getPerspectiveTransform(ordered, target)
        cropped = cv2.warpPerspective(image, transform, (width, height), borderValue=(255, 255, 255))
        if cropped.size == 0:
            return None
        return Image.fromarray(cv2.cvtColor(cropped, cv2.COLOR_BGR2RGB))

    def recognize_image(self, source: Path) -> str:
        """Read an already-prepared image with local models only."""
        try:
            import cv2
        except ImportError as exc:  # pragma: no cover - dependency check is environment-specific
            raise DependencyUnavailable("Thiếu OpenCV cho OCR AI.") from exc

        image = cv2.imread(str(source), cv2.IMREAD_COLOR)
        if image is None:
            raise OCRProcessingError(f"Không thể mở ảnh {source.name} để OCR AI.")
        try:
            results = self._get_detector().predict(str(source))
            payload = results[0].json["res"] if results else {}
            raw_polygons = payload.get("dt_polys")
            polygons = list(raw_polygons) if raw_polygons is not None else []
            raw_scores = payload.get("dt_scores")
            polygons = self._filter_polygons(polygons, raw_scores)
        except DependencyUnavailable:
            raise
        except Exception as exc:
            raise OCRProcessingError(f"PaddleOCR không nhận diện được {source.name}.") from exc

        crops = [
            crop
            for polygon in self._sort_polygons(polygons)
            if (crop := self._crop_line(image, polygon)) is not None
        ]
        if not crops:
            raise OCRProcessingError(f"PaddleOCR không tìm thấy dòng chữ nào trong {source.name}.")
        try:
            lines = self._get_recognizer().predict_batch(crops)
        except DependencyUnavailable:
            raise
        except Exception as exc:
            raise OCRProcessingError(f"VietOCR không đọc được nội dung của {source.name}.") from exc

        text = "\n".join(str(line).strip() for line in lines if str(line).strip())
        if not text:
            raise OCRProcessingError(f"VietOCR không nhận diện được chữ trong {source.name}.")
        return text


def get_local_ai_ocr() -> LocalVietnameseAIOCR:
    """Reuse loaded CPU models across OCR requests in the local web application."""
    global _shared_engine
    if _shared_engine is None:
        _shared_engine = LocalVietnameseAIOCR()
    return _shared_engine
