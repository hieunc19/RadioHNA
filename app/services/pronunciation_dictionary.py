"""Persistent user pronunciation rules shared by every TTS workflow."""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import asdict, dataclass
from threading import RLock
from typing import Any

from app import config
from app.services.errors import UserFacingError

MAX_ENTRIES = 500
MAX_SOURCE_LENGTH = 100
MAX_SPOKEN_LENGTH = 300
_dictionary_lock = RLock()


@dataclass(frozen=True)
class PronunciationEntry:
    id: str
    source: str
    spoken: str
    enabled: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _normalize_field(value: Any, *, label: str, maximum: int) -> str:
    normalized = " ".join(str(value or "").split())
    if not normalized:
        raise UserFacingError(f"{label} không được để trống.")
    if len(normalized) > maximum:
        raise UserFacingError(f"{label} không được dài quá {maximum} ký tự.")
    return normalized


def _entry_from_payload(payload: dict[str, Any]) -> PronunciationEntry:
    try:
        entry_id = str(payload["id"])
        source = _normalize_field(
            payload["source"], label="Từ hoặc cụm từ", maximum=MAX_SOURCE_LENGTH
        )
        spoken = _normalize_field(
            payload["spoken"], label="Cách đọc", maximum=MAX_SPOKEN_LENGTH
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise UserFacingError("Tệp từ điển phát âm có mục dữ liệu không hợp lệ.") from exc
    if not entry_id or len(entry_id) > 64:
        raise UserFacingError("Tệp từ điển phát âm có mã mục không hợp lệ.")
    return PronunciationEntry(entry_id, source, spoken, bool(payload.get("enabled", True)))


def _load_unlocked() -> list[PronunciationEntry]:
    path = config.PRONUNCIATION_DICTIONARY_PATH
    if not path.is_file():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        raw_entries = payload.get("entries", []) if isinstance(payload, dict) else payload
        if not isinstance(raw_entries, list):
            raise TypeError("entries must be a list")
        entries = [_entry_from_payload(item) for item in raw_entries if isinstance(item, dict)]
    except (OSError, UnicodeError, json.JSONDecodeError, TypeError) as exc:
        raise UserFacingError(
            "Không đọc được từ điển phát âm. Hãy kiểm tra tệp pronunciation_dictionary.json."
        ) from exc
    if len(entries) > MAX_ENTRIES:
        raise UserFacingError(f"Từ điển phát âm vượt quá giới hạn {MAX_ENTRIES} mục.")
    return entries


def _save_unlocked(entries: list[PronunciationEntry]) -> None:
    config.ensure_runtime_directories()
    path = config.PRONUNCIATION_DICTIONARY_PATH
    temporary = path.with_suffix(path.suffix + ".tmp")
    payload = {
        "version": 1,
        "entries": [entry.to_dict() for entry in entries],
    }
    try:
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)
    except OSError as exc:
        raise UserFacingError("Không thể lưu từ điển phát âm vào thư mục dữ liệu.") from exc


def list_pronunciations() -> list[PronunciationEntry]:
    with _dictionary_lock:
        return _load_unlocked()


def create_pronunciation(source: Any, spoken: Any, *, enabled: bool = True) -> PronunciationEntry:
    normalized_source = _normalize_field(
        source, label="Từ hoặc cụm từ", maximum=MAX_SOURCE_LENGTH
    )
    normalized_spoken = _normalize_field(spoken, label="Cách đọc", maximum=MAX_SPOKEN_LENGTH)
    with _dictionary_lock:
        entries = _load_unlocked()
        if len(entries) >= MAX_ENTRIES:
            raise UserFacingError(f"Từ điển chỉ hỗ trợ tối đa {MAX_ENTRIES} mục.")
        if any(entry.source.casefold() == normalized_source.casefold() for entry in entries):
            raise UserFacingError(f'“{normalized_source}” đã có trong từ điển.')
        entry = PronunciationEntry(
            id=uuid.uuid4().hex[:12],
            source=normalized_source,
            spoken=normalized_spoken,
            enabled=enabled,
        )
        entries.append(entry)
        _save_unlocked(entries)
        return entry


def update_pronunciation(
    entry_id: str,
    source: Any,
    spoken: Any,
    *,
    enabled: bool,
) -> PronunciationEntry:
    normalized_source = _normalize_field(
        source, label="Từ hoặc cụm từ", maximum=MAX_SOURCE_LENGTH
    )
    normalized_spoken = _normalize_field(spoken, label="Cách đọc", maximum=MAX_SPOKEN_LENGTH)
    with _dictionary_lock:
        entries = _load_unlocked()
        index = next((i for i, entry in enumerate(entries) if entry.id == entry_id), None)
        if index is None:
            raise UserFacingError("Không tìm thấy mục từ điển cần cập nhật.")
        if any(
            entry.id != entry_id and entry.source.casefold() == normalized_source.casefold()
            for entry in entries
        ):
            raise UserFacingError(f'“{normalized_source}” đã có trong từ điển.')
        updated = PronunciationEntry(entry_id, normalized_source, normalized_spoken, enabled)
        entries[index] = updated
        _save_unlocked(entries)
        return updated


def delete_pronunciation(entry_id: str) -> None:
    with _dictionary_lock:
        entries = _load_unlocked()
        retained = [entry for entry in entries if entry.id != entry_id]
        if len(retained) == len(entries):
            raise UserFacingError("Không tìm thấy mục từ điển cần xóa.")
        _save_unlocked(retained)


def apply_user_pronunciations(text: str) -> tuple[str, bool]:
    """Apply enabled entries once, longest source first, without replacement cascades."""
    entries = [entry for entry in list_pronunciations() if entry.enabled]
    if not text or not entries:
        return text, False

    ordered = sorted(entries, key=lambda entry: len(entry.source), reverse=True)
    by_source = {entry.source.casefold(): entry.spoken for entry in ordered}
    alternatives = "|".join(re.escape(entry.source) for entry in ordered)
    pattern = re.compile(rf"(?<!\w)(?:{alternatives})(?!\w)", flags=re.IGNORECASE)
    replaced = pattern.sub(lambda match: by_source[match.group(0).casefold()], text)
    return replaced, replaced != text
