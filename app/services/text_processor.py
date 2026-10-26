"""Chuẩn hóa thận trọng nội dung OCR và nội dung trước khi đưa vào TTS.

OCR cleanup happens before the result is shown for confirmation.  Later TTS
transformations use a separate speech copy, so the user-confirmed text is not
mutated.  Identifiers, abbreviations and numbers without context are
intentionally left unchanged for human review.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.config import MAX_TTS_CHARS_PER_SEGMENT
from app.services.pronunciation_dictionary import apply_user_pronunciations


@dataclass(frozen=True)
class SpeechPreparation:
    original_text: str
    speech_text: str
    changes: tuple[str, ...]


_DATE_WITH_PREFIX = re.compile(
    r"\bngày\s+(?P<day>0?[1-9]|[12]\d|3[01])\s*/\s*"
    r"(?P<month>0?[1-9]|1[0-2])\s*/\s*(?P<year>\d{4})\b",
    flags=re.IGNORECASE,
)
_TIME_WITH_H = re.compile(
    r"\b(?P<hour>[01]?\d|2[0-3])\s*[hH]\s*(?P<minute>[0-5]\d)\b"
)
_WHITESPACE = re.compile(r"[\t \f\v]+")
_EXCESS_NEWLINES = re.compile(r"\n{3,}")
_SENTENCE_BREAK = re.compile(r"(?<=[.!?…;:])\s+")
_OCR_SEPARATOR_LINE = re.compile(r"^(?:[-–—_=•·]\s*)+$")
_OCR_BULLET_PREFIX = re.compile(r"^(?:[•●▪◦]\s*|[-–—]\s+)(?=[^\W\d_])")
_OCR_LEADING_DECORATION = re.compile(r"^(?:[-–—_=]{2,})\s*")
_OCR_TRAILING_DASH = re.compile(r"(?:\s+[-–—]+|(?<=[.!?…,;:])[-–—]+)$")
_OCR_STRUCTURAL_PREFIX = re.compile(
    r"^(?:Điều\s+\d+[.:]|\d+\.\s+|[a-zđ]\)\s+)", flags=re.IGNORECASE
)
_CLOSING_MARKS = "\"'”’)]}"
_PAUSE_MARKS = ".,;:!?…"
_OCR_DATE_CANDIDATE = re.compile(
    r"\bngày\s+(?P<day>\S{1,4})\s+tháng\s+(?P<month>.+?)\s+năm\s+(?P<year>\d{4})\b",
    flags=re.IGNORECASE,
)
_COMMON_OCR_PHRASE_FIXES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bQUYÉT ĐỊNH\b"), "QUYẾT ĐỊNH"),
    (re.compile(r"\bbồ\s+[Ss]ung\b"), "bổ sung"),
    (re.compile(r"\bCao\s+(?:đắng|đăng)\b"), "Cao đẳng"),
    (re.compile(r"\bCạo\s+đẳng\b"), "Cao đẳng"),
    (re.compile(r"\bĐông\s+Băc\b"), "Đông Bắc"),
    (re.compile(r"\bđề\s+quản\s+lý\b"), "để quản lý"),
    (re.compile(r"\btiền\s+hành\b"), "tiến hành"),
    (re.compile(r"\btình\s+gọn\b"), "tinh gọn"),
    (re.compile(r"\bquyên(?=,\s+lợi\s+ích)"), "quyền"),
    (re.compile(r"\bđât\s+đai\b"), "đất đai"),
    (re.compile(r"\bđề\s+xuât\b"), "đề xuất"),
    (re.compile(r"\bTờ\s+trình\s+sô\b"), "Tờ trình số"),
    (re.compile(r"\bviệc\s+chuyên\s+giao\b"), "việc chuyển giao"),
    (re.compile(r"\bvề\s+Uy\s+ban\b"), "về Ủy ban"),
    (re.compile(r"\bthành\s+phô\b"), "thành phố"),
    (re.compile(r"\bhiệu\s+lực\s+thi\s+hành\s+kề\s+từ\b"), "hiệu lực thi hành kể từ"),
    (re.compile(r"\bVề\s+việc\s+[“\"]chuyển\s+giao\b"), "Về việc chuyển giao"),
    (
        re.compile(r"(?<=Tờ trình số )(\d+)/T(?:TY|11|7r)-", flags=re.IGNORECASE),
        r"\1/TTr-",
    ),
    (re.compile(r"\bTrường\s+œ\s+đẳng\s+Nông\s+Lâm\b"), "Trường Cao đẳng Nông Lâm"),
    (re.compile(r"\bPHO\s+THỦ\s+TƯỚNG\b"), "PHÓ THỦ TƯỚNG"),
    (re.compile(r"\bđề\s+b/c\b"), "để b/c"),
    (re.compile(r"\bTổ\s+quốc\.\s+Việt\s+Nam\b"), "Tổ quốc Việt Nam"),
    # These substitutions are deliberately constrained by full Vietnamese
    # date/list context.  Applying character replacements globally would risk
    # changing document identifiers and valid names.
    (
        re.compile(r"\bngày\s+ló\s+tháng\b", flags=re.IGNORECASE),
        "ngày 16 tháng",
    ),
    (
        re.compile(
            r"\btháng\s+[¡!|Il1]\s*[JIl1]\s+năm\b",
            flags=re.IGNORECASE,
        ),
        "tháng 11 năm",
    ),
    (
        re.compile(r"\bcác\s+cơ\s+quan\s+1[lI]\.\s+", flags=re.IGNORECASE),
        "các cơ quan.\n1. ",
    ),
    (
        re.compile(r"\bQuyết\s+định\s+này\s+Nơi\s+nhận:", flags=re.IGNORECASE),
        "Quyết định này.\nNơi nhận:",
    ),
)

# Document codes are expanded before individual abbreviations so a domain
# model never has to guess that "CP" means "cổ phần".  The replacements only
# affect the private speech copy, not the text confirmed by the operator.
_ADMIN_DOCUMENT_CODE_FIXES: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(
            r"(?<=Nghị định số )(\d+)\s*/\s*(\d{4})\s*/\s*NĐ-CP\b",
            flags=re.IGNORECASE,
        ),
        r"\1 năm \2",
    ),
    (
        re.compile(
            r"(?<=Nghị quyết số )(\d+)\s*/\s*(\d{4})\s*/\s*NQ-CP\b",
            flags=re.IGNORECASE,
        ),
        r"\1 năm \2",
    ),
    (
        re.compile(
            r"(?<=Quyết định số )(\d+)\s*/\s*QĐ-TTg\b",
            flags=re.IGNORECASE,
        ),
        r"\1 của Thủ tướng Chính phủ",
    ),
    (
        re.compile(
            r"(?<=Tờ trình số )(\d+)\s*/\s*TTr-BNNMT\b",
            flags=re.IGNORECASE,
        ),
        r"\1 của Bộ Nông nghiệp và Môi trường",
    ),
    (
        re.compile(r"\b(\d+)\s*/\s*QĐ-TTg\b", flags=re.IGNORECASE),
        r"\1, Quyết định của Thủ tướng Chính phủ",
    ),
    (
        re.compile(r"\b(\d+)\s*/\s*TTr-BNNMT\b", flags=re.IGNORECASE),
        r"\1, Tờ trình Bộ Nông nghiệp và Môi trường",
    ),
)

_ADMIN_ABBREVIATIONS: tuple[tuple[str, str], ...] = (
    ("NĐ-CP", "Nghị định Chính phủ"),
    ("NQ-CP", "Nghị quyết Chính phủ"),
    ("QĐ-TTg", "Quyết định Thủ tướng Chính phủ"),
    ("TTr-BNNMT", "Tờ trình Bộ Nông nghiệp và Môi trường"),
    ("UBND", "Ủy ban nhân dân"),
    ("VPCP", "Văn phòng Chính phủ"),
    ("BNNMT", "Bộ Nông nghiệp và Môi trường"),
    ("GDĐT", "Giáo dục và Đào tạo"),
    ("BTCN", "Bộ trưởng, Chủ nhiệm"),
    ("PCN", "Phó Chủ nhiệm"),
    ("TTg", "Thủ tướng"),
    ("TCCV", "Tổ chức cán bộ"),
    ("KTTH", "Kinh tế tổng hợp"),
    ("QHĐP", "Quan hệ địa phương"),
    ("KGVX", "Khoa giáo Văn xã"),
    ("CTTCP", "Cổng Thông tin điện tử Chính phủ"),
    ("NNMT", "Nông nghiệp và Môi trường"),
    ("PL", "Pháp luật"),
    ("NC", "Nội chính"),
    ("NV", "Nội vụ"),
    ("TC", "Tài chính"),
    ("VT", "Văn thư"),
    ("CP", "Chính phủ"),
)

_SPOKEN_ABBREVIATION_FIXES: tuple[tuple[re.Pattern[str], str], ...] = tuple(
    (
        re.compile(
            rf"(?<![\wÀ-ỹ]){re.escape(abbreviation)}(?![\wÀ-ỹ])",
            flags=re.IGNORECASE if abbreviation in {"TTg"} else 0,
        ),
        spoken,
    )
    for abbreviation, spoken in _ADMIN_ABBREVIATIONS
)
_REPORT_ABBREVIATION = re.compile(r"(?<!\w)b\s*/\s*c(?!\w)", flags=re.IGNORECASE)
_SIGNATURE_MARKERS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bKT\.\s*(?=[A-ZÀ-ỸĐ])"), "Ký thay. "),
    (re.compile(r"\bTM\.\s*(?=[A-ZÀ-ỸĐ])"), "Thay mặt. "),
    (re.compile(r"\bTL\.\s*(?=[A-ZÀ-ỸĐ])"), "Thừa lệnh. "),
    (re.compile(r"\bTUQ\.\s*(?=[A-ZÀ-ỸĐ])"), "Thừa ủy quyền. "),
)
_MOTTO_DASHES = re.compile(
    r"\bĐộc lập\s*[-–—]\s*Tự do\s*[-–—]\s*Hạnh phúc\b",
    flags=re.IGNORECASE,
)


def _strip_ocr_artifacts(line: str) -> tuple[str, bool]:
    """Return one OCR line without decorative bullets or dangling dashes."""
    normalized = _WHITESPACE.sub(" ", line).strip().replace("\u00ad", "")
    if not normalized or _OCR_SEPARATOR_LINE.fullmatch(normalized):
        return "", False

    normalized = _OCR_LEADING_DECORATION.sub("", normalized, count=1).strip()
    bullet_match = _OCR_BULLET_PREFIX.match(normalized)
    bullet = False
    if bullet_match:
        normalized = _OCR_BULLET_PREFIX.sub("", normalized, count=1).strip()
        first_letter = next((character for character in normalized if character.isalpha()), "")
        bullet = bool(first_letter and first_letter.isupper())
    normalized = _OCR_TRAILING_DASH.sub("", normalized).rstrip()
    return normalized, bullet


def _ends_with_pause(text: str) -> bool:
    core = text.rstrip().rstrip(_CLOSING_MARKS).rstrip()
    return bool(core) and core[-1] in _PAUSE_MARKS


def _finish_ocr_block(text: str) -> str:
    """Give each detected paragraph/list item a useful TTS pause."""
    text = text.strip()
    if not text:
        return ""

    closers = ""
    while text and text[-1] in _CLOSING_MARKS:
        closers = text[-1] + closers
        text = text[:-1].rstrip()
    if text and text[-1] not in _PAUSE_MARKS:
        text += "."
    return text + closers


def _correct_common_ocr_phrases(text: str) -> str:
    """Correct only high-confidence Vietnamese administrative collocations."""
    corrected = text
    for pattern, replacement in _COMMON_OCR_PHRASE_FIXES:
        corrected = pattern.sub(replacement, corrected)
    return corrected


def find_suspicious_ocr_dates(text: str) -> tuple[str, ...]:
    """Find date fragments whose day/month is not a valid decimal number."""
    suspicious: list[str] = []
    for match in _OCR_DATE_CANDIDATE.finditer(text or ""):
        day_text = match.group("day")
        month_text = match.group("month").strip()
        valid_day = day_text.isdecimal() and 1 <= int(day_text) <= 31
        valid_month = month_text.isdecimal() and 1 <= int(month_text) <= 12
        if not (valid_day and valid_month):
            fragment = _WHITESPACE.sub(" ", match.group(0)).strip()
            if fragment not in suspicious:
                suspicious.append(fragment)
    return tuple(suspicious[:5])


def _is_ocr_heading(text: str) -> bool:
    letters = [character for character in text if character.isalpha()]
    return 2 < len(letters) <= 100 and all(not character.islower() for character in letters)


def postprocess_ocr_text(text: str) -> str:
    """Clean OCR layout artifacts and restore conservative speaking pauses.

    Printed line wraps are joined without inventing punctuation. Blank lines,
    headings, bullet boundaries and separator lines end a logical block, where
    a final full stop is added only when punctuation is absent. Identifiers with
    meaningful internal dashes (for example ``A12-B``) are kept unchanged.
    """
    raw_lines = (text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    blocks: list[str] = []
    fragments: list[str] = []
    current_is_bullet = False
    saw_blank = False

    def flush() -> None:
        nonlocal fragments, current_is_bullet, saw_blank
        if not fragments:
            current_is_bullet = False
            return
        combined = " ".join(fragments)
        combined = _correct_common_ocr_phrases(combined)
        finished = _finish_ocr_block(combined)
        if finished:
            blocks.append(finished)
        fragments = []
        current_is_bullet = False
        saw_blank = False

    for raw_line in raw_lines:
        stripped_raw = _WHITESPACE.sub(" ", raw_line).strip().replace("\u00ad", "")
        if not stripped_raw or _OCR_SEPARATOR_LINE.fullmatch(stripped_raw):
            if fragments and _ends_with_pause(fragments[-1]):
                flush()
            saw_blank = True
            continue

        line, is_bullet = _strip_ocr_artifacts(stripped_raw)
        if not line:
            saw_blank = True
            continue
        if line.isdecimal() and len(line) <= 3 and not fragments and saw_blank:
            saw_blank = False
            continue
        if _is_ocr_heading(line):
            flush()
            blocks.append(_finish_ocr_block(_correct_common_ocr_phrases(line)))
            continue
        is_structural = bool(_OCR_STRUCTURAL_PREFIX.match(line))
        first_letter = next((character for character in line if character.isalpha()), "")
        starts_new_paragraph = bool(saw_blank and first_letter and first_letter.isupper())
        if is_bullet or is_structural or starts_new_paragraph:
            flush()
            current_is_bullet = is_bullet
            fragments.append(line)
        elif current_is_bullet or fragments:
            fragments.append(line)
        else:
            fragments = [line]
        saw_blank = False

    flush()
    return "\n".join(blocks).strip()


def _normalize_layout(text: str) -> str:
    lines = [_WHITESPACE.sub(" ", line).strip() for line in text.replace("\r\n", "\n").split("\n")]
    result: list[str] = []
    for line in lines:
        if not line:
            if result and result[-1] != "":
                result.append("")
            continue

        # OCR commonly breaks a visual line in the middle of a sentence.  A
        # line ending in sentence punctuation or a colon remains a boundary.
        if result and result[-1] and not re.search(r"[.!?…:;]$", result[-1]):
            result[-1] = f"{result[-1]} {line}"
        else:
            result.append(line)
    return _EXCESS_NEWLINES.sub("\n\n", "\n".join(result)).strip()


def _prepare_administrative_speech(text: str) -> tuple[str, bool]:
    """Expand unambiguous public-administration shorthand for VieNeu."""
    prepared = text
    for pattern, replacement in _ADMIN_DOCUMENT_CODE_FIXES:
        prepared = pattern.sub(replacement, prepared)
    for pattern, replacement in _SPOKEN_ABBREVIATION_FIXES:
        prepared = pattern.sub(replacement, prepared)
    for pattern, replacement in _SIGNATURE_MARKERS:
        prepared = pattern.sub(replacement, prepared)
    prepared = _REPORT_ABBREVIATION.sub("báo cáo", prepared)
    prepared = _MOTTO_DASHES.sub("Độc lập, Tự do, Hạnh phúc", prepared)
    return prepared, prepared != text


def prepare_speech_text(original_text: str) -> SpeechPreparation:
    """Create an independent speech version while retaining the confirmed text."""
    original = (original_text or "").strip()
    speech = _normalize_layout(original)
    changes: list[str] = []

    def replace_time(match: re.Match[str]) -> str:
        hour = int(match.group("hour"))
        minute = int(match.group("minute"))
        return f"{hour} giờ {minute} phút"

    converted = _TIME_WITH_H.sub(replace_time, speech)
    if converted != speech:
        changes.append("Chuẩn hóa định dạng giờ h-phút rõ nghĩa")
    speech = converted

    def replace_date(match: re.Match[str]) -> str:
        day = int(match.group("day"))
        month = int(match.group("month"))
        return f"ngày {day} tháng {month} năm {match.group('year')}"

    converted = _DATE_WITH_PREFIX.sub(replace_date, speech)
    if converted != speech:
        changes.append("Chuẩn hóa định dạng ngày/tháng/năm có tiền tố 'ngày'")
    speech = converted

    speech, dictionary_changed = apply_user_pronunciations(speech)
    if dictionary_changed:
        changes.append("Áp dụng từ điển phát âm cá nhân")

    speech, administrative_changed = _prepare_administrative_speech(speech)
    if administrative_changed:
        changes.append("Mở rộng từ viết tắt hành chính và chuẩn hóa nhịp đọc")

    if speech != original and not changes:
        changes.append("Loại bỏ khoảng trắng và xuống dòng do bố cục OCR")

    return SpeechPreparation(original_text=original, speech_text=speech, changes=tuple(changes))


def split_text_for_tts(text: str, max_chars: int = MAX_TTS_CHARS_PER_SEGMENT) -> list[str]:
    """Split long content on sentence and word boundaries, preserving order.

    A very long token (for example a malformed OCR string) is kept whole rather
    than silently cutting an identifier in half; the TTS engine will then report
    a clear error for that segment if it cannot accept it.
    """
    if max_chars < 100:
        raise ValueError("max_chars must be at least 100")
    normalized = (text or "").strip()
    if not normalized:
        return []

    sentences = [part.strip() for part in _SENTENCE_BREAK.split(normalized) if part.strip()]
    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        if len(sentence) > max_chars:
            if current:
                chunks.append(current)
                current = ""
            chunks.extend(_split_long_sentence(sentence, max_chars))
            continue
        candidate = f"{current} {sentence}".strip()
        if current and len(candidate) > max_chars:
            chunks.append(current)
            current = sentence
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


def _split_long_sentence(sentence: str, max_chars: int) -> list[str]:
    chunks: list[str] = []
    remaining = sentence.strip()
    while len(remaining) > max_chars:
        window = remaining[: max_chars + 1]
        minimum_preferred = max_chars // 2
        preferred_breaks = [
            match.end()
            for match in re.finditer(r"[,;:]\s+", window)
            if match.end() >= minimum_preferred
        ]
        if preferred_breaks:
            split_at = preferred_breaks[-1]
        else:
            whitespace = window.rfind(" ")
            if whitespace <= 0:
                # Keep a malformed overlong token intact rather than changing
                # an identifier or silently dropping characters.
                next_space = remaining.find(" ", max_chars)
                if next_space < 0:
                    chunks.append(remaining)
                    return chunks
                split_at = next_space + 1
            else:
                split_at = whitespace + 1
        chunks.append(remaining[:split_at].strip())
        remaining = remaining[split_at:].strip()
    if remaining:
        chunks.append(remaining)
    return chunks
