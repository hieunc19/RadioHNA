import tempfile
import unittest
from pathlib import Path
from unittest import mock

from app import config
from app.services.text_processor import (
    find_suspicious_ocr_dates,
    postprocess_ocr_text,
    prepare_speech_text,
    split_text_for_tts,
)


class TextProcessorTests(unittest.TestCase):
    def setUp(self):
        self._temp_dir = tempfile.TemporaryDirectory()
        self._dict_patch = mock.patch.object(
            config, "PRONUNCIATION_DICTIONARY_PATH", Path(self._temp_dir.name) / "test_dict.json"
        )
        self._dict_patch.start()

    def tearDown(self):
        self._dict_patch.stop()
        self._temp_dir.cleanup()
    def test_postprocesses_ocr_bullets_and_restores_speaking_pauses(self):
        raw = (
            "- Ủy ban nhân dân huyện\n"
            "- Trường Cao đẳng Nông Lâm;\n"
            "-----\n"
            "Nội dung dòng thứ nhất\n"
            "tiếp tục ở dòng thứ hai\n"
            "Mã A12-B, thời gian 08h30.-"
        )

        cleaned = postprocess_ocr_text(raw)

        self.assertEqual(
            cleaned,
            (
                "Ủy ban nhân dân huyện.\n"
                "Trường Cao đẳng Nông Lâm;\n"
                "Nội dung dòng thứ nhất tiếp tục ở dòng thứ hai "
                "Mã A12-B, thời gian 08h30."
            ),
        )

    def test_corrects_only_contextual_common_ocr_errors(self):
        raw = (
            "QUYÉT ĐỊNH\n\n"
            "Trường Cao đắng Nông Lâm Đông Băc đề quản lý.\n\n"
            "Bảo đảm quyên, lợi ích; quản lý đât đai."
        )

        cleaned = postprocess_ocr_text(raw)

        self.assertIn("QUYẾT ĐỊNH.", cleaned)
        self.assertIn("Cao đẳng Nông Lâm Đông Bắc để quản lý", cleaned)
        self.assertIn("quyền, lợi ích", cleaned)
        self.assertIn("đất đai", cleaned)

    def test_corrects_high_confidence_date_glyph_confusions(self):
        text = "ngày ló tháng 6 năm 2025; ngày 19 tháng ¡ J năm 2025"

        cleaned = postprocess_ocr_text(text)

        self.assertIn("ngày 16 tháng 6 năm 2025", cleaned)
        self.assertIn("ngày 19 tháng 11 năm 2025", cleaned)
        self.assertEqual(find_suspicious_ocr_dates(cleaned), ())

    def test_flags_other_unclear_dates_without_guessing_numbers(self):
        text = "ngày xy tháng ?? năm 2025"

        suspicious = find_suspicious_ocr_dates(text)

        self.assertEqual(suspicious, ("ngày xy tháng ?? năm 2025",))

    def test_corrects_structural_and_contextual_tesseract_errors(self):
        raw = (
            "Điều 2. Trách nhiệm của các cơ quan 1l. Bộ Nông nghiệp.\n"
            "Hiệu trưởng Trường Cạo đẳng chịu trách nhiệm thi hành "
            "Quyết định này Nơi nhận: Thủ tướng (đề b/c)."
        )

        cleaned = postprocess_ocr_text(raw)

        self.assertIn("các cơ quan.\n1. Bộ Nông nghiệp", cleaned)
        self.assertIn("Trường Cao đẳng", cleaned)
        self.assertIn("Quyết định này.\nNơi nhận:", cleaned)
        self.assertIn("để b/c", cleaned)

    def test_joins_lowercase_continuation_and_separates_structural_items(self):
        raw = (
            "Điều 1. Chuyển giao Trường Cao đẳng Nông Lâm\n\n"
            "từ Bộ Nông nghiệp và Môi trường về Ủy ban nhân dân quản lý.\n\n"
            "Điều 2. Trách nhiệm của các cơ quan\n"
            "1. Bộ Nông nghiệp và Môi trường\n\n"
            "c) Không làm gián đoạn hoạt động đào\n"
            "- tạo; bảo đảm quyền, lợi ích hợp pháp."
        )

        cleaned = postprocess_ocr_text(raw)

        self.assertIn("Nông Lâm từ Bộ", cleaned)
        self.assertIn("Điều 2. Trách nhiệm của các cơ quan.\n1. Bộ", cleaned)
        self.assertIn("hoạt động đào tạo;", cleaned)

    def test_removes_leading_decorative_rule_without_losing_following_text(self):
        cleaned = postprocess_ocr_text("—=\u2014——  Độc lập - Tự do - Hạnh phúc")

        self.assertEqual(cleaned, "Độc lập - Tự do - Hạnh phúc.")

    def test_postprocess_preserves_meaningful_leading_minus_and_internal_dashes(self):
        raw = "- 5 độ C\nMã A12-B và giai đoạn 2025-2026."

        cleaned = postprocess_ocr_text(raw)

        self.assertIn("- 5 độ C", cleaned)
        self.assertIn("A12-B", cleaned)
        self.assertIn("2025-2026", cleaned)

    def test_expands_unambiguous_time_and_date_without_mutating_original(self):
        original = "Thông báo\n08h30 ngày 15/10/2026."

        prepared = prepare_speech_text(original)

        self.assertEqual(original, prepared.original_text)
        self.assertIn("8 giờ 30 phút ngày 15 tháng 10 năm 2026", prepared.speech_text)

    def test_ambiguous_identifiers_are_preserved(self):
        original = "Hồ sơ số 08/30, mã A12-B và số điện thoại 0912 345 678."

        prepared = prepare_speech_text(original)

        self.assertIn("08/30", prepared.speech_text)
        self.assertIn("A12-B", prepared.speech_text)
        self.assertIn("0912 345 678", prepared.speech_text)

    def test_expands_administrative_abbreviations_only_in_speech_copy(self):
        original = (
            "Căn cứ Nghị định số 303/2025/NĐ-CP; UBND báo cáo CP. "
            "VPCP: BTCN, các PCN; Quyết định số 1811/QĐ-TTg. "
            "Các Bộ: GDĐT, NV, TC. KT. THỦ TƯỚNG."
        )

        prepared = prepare_speech_text(original)

        self.assertEqual(prepared.original_text, original)
        self.assertIn("Nghị định số 303 năm 2025", prepared.speech_text)
        self.assertIn("Ủy ban nhân dân báo cáo Chính phủ", prepared.speech_text)
        self.assertIn("Văn phòng Chính phủ: Bộ trưởng, Chủ nhiệm", prepared.speech_text)
        self.assertIn("các Phó Chủ nhiệm", prepared.speech_text)
        self.assertIn(
            "Quyết định số 1811 của Thủ tướng Chính phủ",
            prepared.speech_text,
        )
        self.assertIn("Giáo dục và Đào tạo, Nội vụ, Tài chính", prepared.speech_text)
        self.assertIn("Ký thay. THỦ TƯỚNG", prepared.speech_text)
        self.assertNotRegex(prepared.speech_text, r"\bCP\b")
        self.assertIn("Mở rộng từ viết tắt hành chính", " ".join(prepared.changes))

    def test_normalizes_national_motto_dashes_as_spoken_pauses(self):
        prepared = prepare_speech_text("Độc lập - Tự do - Hạnh phúc.")

        self.assertEqual(prepared.speech_text, "Độc lập, Tự do, Hạnh phúc.")

    def test_splits_only_at_word_boundaries_and_keeps_order(self):
        text = "Một câu ngắn. " * 80

        chunks = split_text_for_tts(text, max_chars=120)

        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(chunk) <= 120 for chunk in chunks))
        self.assertEqual(" ".join(chunks).replace("  ", " "), text.strip())

    def test_keeps_very_long_single_token_whole(self):
        token = "A" * 150

        self.assertEqual(split_text_for_tts(token, max_chars=100), [token])

    def test_long_sentence_prefers_a_comma_boundary(self):
        first_clause = "Nội dung hành chính cần đọc rõ ràng, " * 3
        text = first_clause + "và phần còn lại của câu vẫn tiếp tục bình thường."

        chunks = split_text_for_tts(text, max_chars=120)

        self.assertGreater(len(chunks), 1)
        self.assertTrue(chunks[0].endswith(","))
        self.assertEqual(" ".join(chunks), text)


if __name__ == "__main__":
    unittest.main()
