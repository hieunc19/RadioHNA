"""VieNeu CPU/ONNX adapter with a strict offline runtime policy."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path
from threading import Lock
from typing import Any

from app import config
from app.services.errors import DependencyUnavailable, UserFacingError

ProgressCallback = Callable[[float, str], None]


# VieNeu's ONNX model is large and loading it for every preview/generation
# wastes several seconds.  Preset voices are selected at `infer()` time, so one
# engine can safely serve every selected voice.  The web layer serializes TTS
# operations; this lock also protects direct callers during engine creation.
_shared_engine: Any | None = None
_shared_engine_lock = Lock()


def _is_news_voice(label: str) -> bool:
    normalized = label.lower()
    return "tin tức" in normalized or "tin tuc" in normalized


class VieNeuLocalTTS:
    """Loads one local VieNeu engine and synthesizes ordered WAV segments."""

    def __init__(self, voice: str = config.DEFAULT_VOICE) -> None:
        self.voice = voice
        self._engine = None

    def _get_engine(self):
        if self._engine is not None:
            return self._engine

        global _shared_engine
        with _shared_engine_lock:
            if _shared_engine is None:
                config.configure_local_environment(offline=True)
                try:
                    from vieneu import Vieneu
                except ImportError as exc:  # pragma: no cover - environment-dependent
                    raise DependencyUnavailable(
                        "Chưa cài VieNeu local. Hãy cài requirements.txt hoặc dùng bộ cài đầy đủ."
                    ) from exc

                if not config.model_cache_present():
                    raise DependencyUnavailable(
                        "Thiếu model VieNeu cục bộ. Bản chạy đã khóa offline; "
                        "hãy chuẩn bị models/vieneu trên máy đóng gói."
                    )
                try:
                    # CPU is deliberately forced to the offline ONNX backend.
                    _shared_engine = Vieneu(
                        mode=config.VIENEU_MODE,
                        backbone_repo=config.VIENEU_MODEL_REPOSITORY,
                        device="cpu",
                        precision=config.VIENEU_PRECISION,
                        threads=config.VIENEU_CPU_THREADS,
                    )
                except Exception as exc:  # include missing model/cache errors in one actionable message
                    raise DependencyUnavailable(
                        "Không thể nạp VieNeu từ model cục bộ. "
                        "Hãy kiểm tra đầy đủ cache/model và khả năng tương thích CPU."
                    ) from exc
            self._engine = _shared_engine
        return self._engine

    def list_preset_voices(self) -> list[tuple[str, str]]:
        """Return the preset voices included in the currently cached VieNeu model."""
        try:
            choices = self._get_engine().list_preset_voices()
        except Exception as exc:
            raise DependencyUnavailable(
                "Không thể đọc danh sách giọng VieNeu cục bộ. Hãy kiểm tra model đã chuẩn bị đầy đủ."
            ) from exc

        normalized = [(str(label), str(voice)) for label, voice in choices if voice]
        if not normalized:
            raise DependencyUnavailable("Model VieNeu cục bộ không có giọng đọc để lựa chọn.")

        # Prioritize news style voices ("phong cách tin tức") at the top
        return sorted(normalized, key=lambda item: not _is_news_voice(item[0]))

    def synthesize_segments(
        self,
        segments: Sequence[str],
        directory: Path,
        progress: ProgressCallback | None = None,
    ) -> list[Path]:
        """Generate individual WAV files sequentially so failures identify a segment."""
        if not segments:
            raise UserFacingError("Không có nội dung hợp lệ để tạo giọng đọc.")
        directory.mkdir(parents=True, exist_ok=True)
        engine = self._get_engine()
        generated: list[Path] = []

        for index, segment in enumerate(segments, start=1):
            if progress:
                progress((index - 1) / len(segments), f"Đang tạo giọng đọc đoạn {index}/{len(segments)}…")
            try:
                audio = engine.infer(segment, voice=self.voice)
                output = directory / f"segment_{index:03d}.wav"
                engine.save(audio, str(output))
                generated.append(output)
            except Exception as exc:
                raise UserFacingError(
                    f"Không tạo được giọng đọc ở đoạn {index}/{len(segments)}. "
                    "Nội dung đã chỉnh sửa vẫn được giữ nguyên."
                ) from exc

        if progress:
            progress(1.0, "Đã tạo xong các đoạn âm thanh.")
        return generated
