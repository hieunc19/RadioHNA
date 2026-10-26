"""Điều phối pipeline văn bản đã xác nhận -> VieNeu local -> MP3."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from app import config
from app.services.audio_service import merge_wav_to_mp3
from app.services.errors import UserFacingError
from app.services.text_processor import (
    SpeechPreparation,
    prepare_speech_text,
    split_text_for_tts,
)
from app.services.tts_service import VieNeuLocalTTS
from app.utils.file_helper import new_job_directory, new_output_path
from app.utils.validators import require_confirmed_text

ProgressCallback = Callable[[float, str], None]


@dataclass(frozen=True)
class GenerationResult:
    mp3_path: Path
    preparation: SpeechPreparation
    segment_count: int
    voice: str


def generate_bulletin(
    confirmed_text: str | None,
    confirmed: bool,
    progress: ProgressCallback | None = None,
    *,
    voice: str = config.DEFAULT_VOICE,
) -> GenerationResult:
    """Generate a final MP3 without mutating the text displayed to the user."""
    original = require_confirmed_text(confirmed_text, confirmed)
    preparation = prepare_speech_text(original)
    segments = split_text_for_tts(preparation.speech_text)
    job_dir = new_job_directory("tts")

    def synthesis_progress(value: float, message: str) -> None:
        if progress:
            progress(value * 0.85, message)

    wavs = VieNeuLocalTTS(voice).synthesize_segments(segments, job_dir, synthesis_progress)
    if progress:
        progress(0.9, "Đang ghép các đoạn và xuất MP3…")
    output = merge_wav_to_mp3(wavs, new_output_path(), job_dir)
    if progress:
        progress(1.0, "Đã hoàn thành bản tin MP3.")
    return GenerationResult(
        mp3_path=output,
        preparation=preparation,
        segment_count=len(segments),
        voice=voice,
    )


def preview_voice(
    voice: str,
    progress: ProgressCallback | None = None,
) -> Path:
    """Create a short WAV preview for a selected local preset voice."""
    job_dir = new_job_directory("voice_preview")
    wavs = VieNeuLocalTTS(voice).synthesize_segments(
        [config.VOICE_PREVIEW_TEXT],
        job_dir,
        progress,
    )
    return wavs[0]


def preview_pronunciation(
    spoken_text: str,
    voice: str,
    progress: ProgressCallback | None = None,
) -> Path:
    """Synthesize exactly one dictionary pronunciation for immediate review."""
    normalized = " ".join((spoken_text or "").split())
    if not normalized:
        raise UserFacingError("Hãy nhập cách đọc trước khi nghe thử.")
    if len(normalized) > 300:
        raise UserFacingError("Cách đọc nghe thử không được dài quá 300 ký tự.")
    job_dir = new_job_directory("pronunciation_preview")
    wavs = VieNeuLocalTTS(voice).synthesize_segments([normalized], job_dir, progress)
    return wavs[0]
