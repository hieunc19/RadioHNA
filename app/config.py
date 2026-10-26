"""Cấu hình đường dẫn và chính sách chạy offline của ứng dụng."""

from __future__ import annotations

import os
import shutil
import sys
from hashlib import sha256
from pathlib import Path

APP_NAME = "PHÁT THANH AI"
SERVER_HOST = "127.0.0.1"
SERVER_PORT = 7860
MAX_IMAGE_BYTES = 20 * 1024 * 1024
MAX_PDF_BYTES = 50 * 1024 * 1024
MAX_PDF_PAGES = 50
PDF_RENDER_SCALE = 4
OCR_TESSERACT_CONFIG = "--oem 1 --psm 3 -c preserve_interword_spaces=1"
OCR_TESSERACT_AUTO_MIN_CONFIDENCE = 80.0
OCR_DETECTION_MIN_SCORE = 0.50
OCR_LINE_PADDING_MIN_PX = 4
OCR_LINE_PADDING_MAX_PX = 12
OCR_LINE_PADDING_RATIO = 0.18
MAX_TTS_CHARS_PER_SEGMENT = 700
DEFAULT_VOICE = "Hải Đăng"
VOICE_PREVIEW_TEXT = (
    "Kính chào quý vị và các bạn. Đây là câu nghe thử giọng đọc của hệ thống phát thanh AI."
)
VIENEU_MODEL_REPOSITORY = "pnnbao-ump/VieNeu-TTS-v3-Turbo"
VIENEU_MODE = "v3turbo"
VIENEU_PRECISION = "fp32"
# VieNeu defaults to half the available logical CPUs.  A local benchmark on the
# target machine (12 logical CPUs) showed 4 ONNX intra-op workers were slightly
# faster than the default 6 for Vietnamese bulletin-sized text.  The setting is
# intentionally overridable for a different deployment machine.
VIENEU_CPU_THREADS = int(os.environ.get("PHAT_THANH_AI_TTS_THREADS", "4"))
TEMP_RETENTION_HOURS = 48


def _bundle_root() -> Path:
    """Trả về thư mục chứa tài nguyên cả khi chạy source và PyInstaller."""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parents[1]


BUNDLE_ROOT = _bundle_root()
ASSETS_DIR = BUNDLE_ROOT / "assets"
WEB_UI_DIR = BUNDLE_ROOT / "app" / "ui"
MODELS_DIR = BUNDLE_ROOT / "models" / "vieneu"
OCR_MODELS_DIR = BUNDLE_ROOT / "models" / "ocr"
PADDLE_CACHE_DIR = OCR_MODELS_DIR / "paddlex"
PADDLE_DETECTION_MODEL_NAME = "PP-OCRv6_medium_det"
PADDLE_DETECTION_MODEL_DIR = PADDLE_CACHE_DIR / "official_models" / PADDLE_DETECTION_MODEL_NAME
VIETOCR_DIR = OCR_MODELS_DIR / "vietocr"
VIETOCR_CONFIG_PATH = VIETOCR_DIR / "vgg_seq2seq.yml"
VIETOCR_WEIGHTS_PATH = VIETOCR_DIR / "vgg_seq2seq.pth"
BIN_DIR = BUNDLE_ROOT / "bin"


def _runtime_version() -> str:
    """Create a short fingerprint for the code and web assets being launched.

    A launcher can otherwise mistake an older process on the same port for the
    current build and silently keep serving stale OCR code.
    """
    if getattr(sys, "frozen", False):
        return os.environ.get("PHAT_THANH_AI_BUILD", "packaged")

    digest = sha256()
    source_patterns = ("*.py", "*.html", "*.css", "*.js")
    source_files = {
        path
        for pattern in source_patterns
        for path in (BUNDLE_ROOT / "app").rglob(pattern)
        if path.is_file()
    }
    launcher = BUNDLE_ROOT / "launcher.py"
    if launcher.is_file():
        source_files.add(launcher)
    for path in sorted(source_files, key=lambda item: item.as_posix()):
        digest.update(path.relative_to(BUNDLE_ROOT).as_posix().encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()[:12]


RUNTIME_VERSION = _runtime_version()


def _public_data_dir() -> Path:
    """Return the visible local data folder, outside PyInstaller internals."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / "data" / "public data"
    return BUNDLE_ROOT / "data" / "public data"


PUBLIC_DATA_DIR = _public_data_dir()


def _default_data_dir() -> Path:
    configured = os.environ.get("PHAT_THANH_AI_DATA_DIR")
    if configured:
        return Path(configured).expanduser().resolve()

    return PUBLIC_DATA_DIR


DATA_DIR = _default_data_dir()
TEMP_DIR = DATA_DIR / "temp"
OUTPUT_DIR = DATA_DIR / "output"
LOG_DIR = DATA_DIR / "logs"
PRONUNCIATION_DICTIONARY_PATH = DATA_DIR / "pronunciation_dictionary.json"
HF_HOME = MODELS_DIR / "huggingface"


def ensure_runtime_directories() -> None:
    """Create only user-writable runtime directories, never model directories."""
    for directory in (DATA_DIR, TEMP_DIR, OUTPUT_DIR, LOG_DIR):
        directory.mkdir(parents=True, exist_ok=True)


def configure_local_environment(*, offline: bool) -> None:
    """Configure third-party libraries before they are imported.

    Runtime always calls this with ``offline=True``.  Provisioning is a separate,
    deliberate action and may call it with ``offline=False`` while preparing a
    release machine.
    """
    os.environ["HF_HOME"] = str(HF_HOME)
    os.environ["HF_HUB_CACHE"] = str(HF_HOME / "hub")
    os.environ["NO_PROXY"] = "127.0.0.1,localhost"
    os.environ["no_proxy"] = "127.0.0.1,localhost"

    if offline:
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
    else:
        os.environ.pop("HF_HUB_OFFLINE", None)
        os.environ.pop("TRANSFORMERS_OFFLINE", None)


def configure_ocr_environment(*, offline: bool) -> None:
    """Keep Paddle/VietOCR assets in the application bundle.

    PaddleOCR otherwise defaults to ``~/.paddlex``.  The application must not
    create a user-profile cache or contact a model host while it is running.
    """
    os.environ["PADDLE_PDX_CACHE_HOME"] = str(PADDLE_CACHE_DIR)
    os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"
    # PaddlePaddle 3.x can fail on some Windows CPUs when oneDNN is enabled.
    os.environ.setdefault("PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT", "0")
    if offline:
        os.environ["PADDLE_PDX_MODEL_SOURCE"] = "local"
    else:
        os.environ.pop("PADDLE_PDX_MODEL_SOURCE", None)


def find_tesseract() -> str | None:
    """Find only an explicitly configured or bundled Tesseract executable."""
    program_files = Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
    program_files_x86 = Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"))
    candidates = [
        os.environ.get("TESSERACT_CMD"),
        str(BIN_DIR / "tesseract" / "tesseract.exe"),
        str(BIN_DIR / "tesseract" / "tesseract"),
        str(program_files / "Tesseract-OCR" / "tesseract.exe"),
        str(program_files_x86 / "Tesseract-OCR" / "tesseract.exe"),
        shutil.which("tesseract"),
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    return None


def configure_tesseract_environment() -> None:
    """Prefer bundled Vietnamese tessdata without overriding an explicit setting."""
    bundled_tessdata = BIN_DIR / "tesseract" / "tessdata"
    if (bundled_tessdata / "vie.traineddata").is_file():
        os.environ.setdefault("TESSDATA_PREFIX", str(bundled_tessdata))


def find_ffmpeg() -> str | None:
    """Find only an explicitly configured, bundled, or PATH FFmpeg executable."""
    candidates = [
        os.environ.get("FFMPEG_CMD"),
        str(BIN_DIR / "ffmpeg" / "ffmpeg.exe"),
        str(BIN_DIR / "ffmpeg" / "ffmpeg"),
        shutil.which("ffmpeg"),
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    return None


def model_cache_present() -> bool:
    """A light-weight readiness check; the engine performs final validation."""
    cache = HF_HOME / "hub"
    return cache.is_dir() and any(cache.iterdir())


def ai_ocr_models_present() -> bool:
    """Return whether every runtime asset for Paddle detection + VietOCR exists."""
    detector_files = (
        PADDLE_DETECTION_MODEL_DIR / "inference.json",
        PADDLE_DETECTION_MODEL_DIR / "inference.pdiparams",
        PADDLE_DETECTION_MODEL_DIR / "inference.yml",
    )
    return all(path.is_file() for path in (*detector_files, VIETOCR_CONFIG_PATH, VIETOCR_WEIGHTS_PATH))
