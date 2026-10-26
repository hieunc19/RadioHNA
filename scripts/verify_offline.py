"""Smoke test the installed VieNeu and OCR caches with network use disabled."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import config  # noqa: E402 - the source root above must be importable when this script runs directly.


def main() -> int:
    config.configure_local_environment(offline=True)
    config.configure_ocr_environment(offline=True)
    if not config.model_cache_present():
        print("FAIL: Không tìm thấy cache VieNeu cục bộ.", file=sys.stderr)
        return 1
    try:
        from vieneu import Vieneu

        engine = Vieneu(
            mode=config.VIENEU_MODE,
            backbone_repo=config.VIENEU_MODEL_REPOSITORY,
            device="cpu",
            precision=config.VIENEU_PRECISION,
        )
        audio = engine.infer("Kiểm tra chạy ngoại tuyến.", voice=config.DEFAULT_VOICE)
        with tempfile.TemporaryDirectory(dir=config.HF_HOME) as temporary:
            target = Path(temporary) / "offline.wav"
            engine.save(audio, str(target))
            if not target.is_file() or target.stat().st_size == 0:
                raise RuntimeError("Không ghi được WAV kiểm tra.")
    except Exception as exc:  # noqa: BLE001 - an offline smoke test must return a readable failure, not a traceback.
        print(f"FAIL: VieNeu không chạy được ở chế độ offline: {exc}", file=sys.stderr)
        return 1
    if not config.ai_ocr_models_present():
        print("FAIL: Không tìm thấy model PaddleOCR/VietOCR cục bộ.", file=sys.stderr)
        return 1
    try:
        from app.services.ai_ocr_service import LocalVietnameseAIOCR

        engine = LocalVietnameseAIOCR()
        engine._get_detector()
        engine._get_recognizer()
    except Exception as exc:  # noqa: BLE001 - model/runtime errors vary across CPUs.
        print(f"FAIL: OCR AI không nạp được ở chế độ offline: {exc}", file=sys.stderr)
        return 1
    print("PASS: VieNeu, PaddleOCR và VietOCR nạp được hoàn toàn từ model cục bộ khi offline.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
