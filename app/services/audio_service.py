"""Ghép WAV theo thứ tự và xuất MP3 bằng FFmpeg cục bộ."""

from __future__ import annotations

import subprocess
import wave
from collections.abc import Iterable
from pathlib import Path

from app import config
from app.services.errors import AudioProcessingError, DependencyUnavailable


def _create_silence(reference_wav: Path, output: Path, duration_ms: int) -> Path:
    """Create PCM silence matching a VieNeu WAV's basic audio parameters."""
    try:
        with wave.open(str(reference_wav), "rb") as source:
            channels = source.getnchannels()
            sample_width = source.getsampwidth()
            frame_rate = source.getframerate()
            compression = source.getcomptype()
            if compression != "NONE":
                raise AudioProcessingError("Đoạn WAV không ở định dạng PCM nên không thể chèn khoảng nghỉ an toàn.")
            frames = round(frame_rate * duration_ms / 1000)
        with wave.open(str(output), "wb") as target:
            target.setnchannels(channels)
            target.setsampwidth(sample_width)
            target.setframerate(frame_rate)
            target.writeframes(b"\x00" * frames * channels * sample_width)
    except (wave.Error, OSError) as exc:
        raise AudioProcessingError("Không thể tạo khoảng nghỉ giữa các đoạn âm thanh.") from exc
    return output


def _ffconcat_escape(path: Path) -> str:
    # FFmpeg concat demuxer accepts POSIX separators on Windows as well.
    return str(path.resolve()).replace("\\", "/").replace("'", "\\'")


def merge_wav_to_mp3(
    wav_paths: Iterable[Path],
    output_path: Path,
    work_dir: Path,
    pause_ms: int = 450,
) -> Path:
    """Join ordered local WAV files, add short pauses, and encode mono 128 kbps MP3."""
    wavs = [Path(path) for path in wav_paths]
    if not wavs or any(not item.is_file() for item in wavs):
        raise AudioProcessingError("Thiếu một hoặc nhiều đoạn WAV cần để ghép bản tin.")
    ffmpeg = config.find_ffmpeg()
    if not ffmpeg:
        raise DependencyUnavailable(
            "Không tìm thấy FFmpeg cục bộ. Hãy đặt ffmpeg vào bin/ffmpeg hoặc cấu hình FFMPEG_CMD."
        )

    work_dir.mkdir(parents=True, exist_ok=True)
    concat_items: list[Path] = []
    for index, wav in enumerate(wavs, start=1):
        concat_items.append(wav)
        if index < len(wavs) and pause_ms:
            concat_items.append(_create_silence(wav, work_dir / f"pause_{index:03d}.wav", pause_ms))

    manifest = work_dir / "audio.ffconcat"
    lines = ["ffconcat version 1.0", *[f"file '{_ffconcat_escape(item)}'" for item in concat_items]]
    manifest.write_text("\n".join(lines) + "\n", encoding="utf-8")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(manifest),
        "-vn",
        "-ac",
        "1",
        "-b:a",
        "128k",
        str(output_path),
    ]
    try:
        completed = subprocess.run(command, capture_output=True, text=True, check=False, timeout=300)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise AudioProcessingError("FFmpeg không thể hoàn tất việc xuất MP3.") from exc
    if completed.returncode != 0 or not output_path.is_file() or output_path.stat().st_size == 0:
        detail = completed.stderr.strip() or "FFmpeg không tạo được file MP3."
        raise AudioProcessingError(f"Không thể ghép MP3: {detail}")
    return output_path
