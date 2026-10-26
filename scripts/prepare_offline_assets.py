"""Explicitly hydrate the VieNeu and Vietnamese OCR assets on a staging machine.

This is deliberately not invoked by the application.  Run it once before a
release, then include ``models/vieneu/huggingface`` in the one-folder build.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import config  # noqa: E402 - the source root above must be importable when this script runs directly.


def _prepare_ai_ocr() -> None:
    """Download OCR assets once, then save only local paths for runtime."""
    config.configure_ocr_environment(offline=False)
    config.VIETOCR_DIR.mkdir(parents=True, exist_ok=True)
    try:
        from paddleocr import TextDetection
        from vietocr.tool.config import Cfg
    except ImportError as exc:
        raise RuntimeError("Thiếu PaddleOCR hoặc VietOCR. Hãy cài requirements.txt trước.") from exc

    # Constructing the detector explicitly downloads its official inference
    # files into PADDLE_PDX_CACHE_HOME (models/ocr/paddlex) on the staging PC.
    TextDetection(model_name=config.PADDLE_DETECTION_MODEL_NAME, device="cpu")

    if not config.VIETOCR_CONFIG_PATH.is_file():
        vietocr_config = Cfg.load_config_from_name("vgg_seq2seq")
        vietocr_config["device"] = "cpu"
        vietocr_config["quiet"] = True
        vietocr_config.setdefault("cnn", {})["pretrained"] = False
        vietocr_config.save(str(config.VIETOCR_CONFIG_PATH))
    else:
        vietocr_config = Cfg.load_config_from_file(str(config.VIETOCR_CONFIG_PATH))

    if not config.VIETOCR_WEIGHTS_PATH.is_file():
        try:
            import requests
        except ImportError as exc:
            raise RuntimeError("Thiếu requests để tải model VietOCR.") from exc
        source_url = str(vietocr_config.get("weights", ""))
        if not source_url.startswith("https://"):
            raise RuntimeError("Không tìm thấy địa chỉ tải trọng số VietOCR chính thức.")
        response = requests.get(source_url, stream=True, timeout=120)
        response.raise_for_status()
        with config.VIETOCR_WEIGHTS_PATH.open("wb") as target:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    target.write(chunk)

    if not config.ai_ocr_models_present():
        raise RuntimeError("Model OCR AI chưa đầy đủ sau khi tải.")

    # Validate both local model loaders before operators disconnect the network.
    from app.services.ai_ocr_service import LocalVietnameseAIOCR

    engine = LocalVietnameseAIOCR()
    engine._get_detector()
    engine._get_recognizer()


def main() -> int:
    parser = argparse.ArgumentParser(description="Chuẩn bị model VieNeu và OCR AI để phát hành offline")
    parser.add_argument(
        "--allow-network",
        action="store_true",
        help="Xác nhận đây là máy staging được phép tải model một lần.",
    )
    args = parser.parse_args()
    if not args.allow_network:
        parser.error("Cần --allow-network.  Ứng dụng phát hành không bao giờ tự tải model.")

    config.HF_HOME.mkdir(parents=True, exist_ok=True)
    config.configure_local_environment(offline=False)
    try:
        from vieneu import Vieneu
    except ImportError:
        print("Thiếu package vieneu. Hãy cài requirements.txt trước.", file=sys.stderr)
        return 2

    print(f"Đang chuẩn bị cache VieNeu tại: {config.HF_HOME}")
    try:
        engine = Vieneu(
            mode=config.VIENEU_MODE,
            backbone_repo=config.VIENEU_MODEL_REPOSITORY,
            device="cpu",
            precision=config.VIENEU_PRECISION,
        )
        # A short inference makes the SDK fetch every asset required at first use,
        # including engine graphs and the selected built-in voice.
        audio = engine.infer("Đây là câu kiểm tra cho bộ phát hành ngoại tuyến.", voice=config.DEFAULT_VOICE)
        with tempfile.TemporaryDirectory(dir=config.HF_HOME) as temporary:
            check_file = Path(temporary) / "smoke-test.wav"
            engine.save(audio, str(check_file))
            if not check_file.is_file() or check_file.stat().st_size == 0:
                raise RuntimeError("VieNeu không tạo được WAV kiểm tra.")
    except Exception as exc:  # noqa: BLE001 - report any SDK/model initialization error to the release operator.
        print(f"Chuẩn bị model thất bại: {exc}", file=sys.stderr)
        return 1

    if not config.model_cache_present():
        print("Cache model chưa xuất hiện sau khi kiểm tra.", file=sys.stderr)
        return 1
    try:
        print(f"Đang chuẩn bị model OCR AI tại: {config.OCR_MODELS_DIR}")
        _prepare_ai_ocr()
    except Exception as exc:  # noqa: BLE001 - show a clear staging failure rather than a traceback.
        print(f"Chuẩn bị model OCR AI thất bại: {exc}", file=sys.stderr)
        return 1
    print("Hoàn tất. Hãy chạy scripts/verify_offline.py sau khi ngắt mạng trước khi đóng gói.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
