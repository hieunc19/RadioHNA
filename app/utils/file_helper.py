"""Quản lý thư mục tạm và file đầu ra cục bộ."""

from __future__ import annotations

import re
import shutil
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app import config


def new_job_directory(prefix: str = "job") -> Path:
    """Create an isolated, user-writable directory for one processing request."""
    config.ensure_runtime_directories()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    directory = config.TEMP_DIR / f"{prefix}_{timestamp}_{uuid.uuid4().hex[:8]}"
    directory.mkdir(parents=True, exist_ok=False)
    return directory


def new_output_path(prefix: str = "ban_tin_phat_thanh") -> Path:
    """Return a recognizable MP3 name without overwriting an earlier bulletin."""
    config.ensure_runtime_directories()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return config.OUTPUT_DIR / f"{prefix}_{timestamp}.mp3"


def safe_filename(value: str, fallback: str = "tep") -> str:
    """Sanitize a display name for Windows while keeping Vietnamese characters."""
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value).strip(" .")
    return name[:120] or fallback


def purge_expired_temp_files(hours: int = config.TEMP_RETENTION_HOURS) -> int:
    """Remove only old temporary job folders; user MP3 output is never touched."""
    if not config.TEMP_DIR.exists():
        return 0

    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    removed = 0
    for item in config.TEMP_DIR.iterdir():
        try:
            modified = datetime.fromtimestamp(item.stat().st_mtime, tz=timezone.utc)
            if modified >= cutoff:
                continue
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()
            removed += 1
        except OSError:
            # A previous process or antivirus may temporarily own a file. It is
            # safer to leave it for the next startup than to fail the app.
            continue
    return removed
