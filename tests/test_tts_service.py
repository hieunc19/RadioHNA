import unittest
from unittest.mock import MagicMock, patch

from app.services.tts_service import VieNeuLocalTTS, _is_news_voice


class TTSServiceTests(unittest.TestCase):
    def test_is_news_voice_detects_news_keywords(self):
        self.assertTrue(_is_news_voice("⭐ Mai Anh — Nữ · Bắc · Phong cách tin tức"))
        self.assertTrue(_is_news_voice("Minh Đức — Nam · Bắc · Phong cách tin tức"))
        self.assertTrue(_is_news_voice("Thùy Dung — Nữ · Nam · Tin tức"))
        self.assertFalse(_is_news_voice("⭐ Trúc Ly — Nữ · Bắc · Phong cách tự nhiên"))
        self.assertFalse(_is_news_voice("⭐ Thiện Minh — Nam · Bắc · Phong cách kể chuyện"))
        self.assertFalse(_is_news_voice("Hải Đăng — Nam · Bắc · Giọng đọc tự nhiên"))

    def test_list_preset_voices_prioritizes_news_style_voices(self):
        fake_choices = [
            ("⭐ Trúc Ly — Nữ · Bắc · Phong cách tự nhiên", "truc_ly"),
            ("⭐ Thiện Minh — Nam · Bắc · Phong cách kể chuyện", "thien_minh"),
            ("⭐ Mai Anh — Nữ · Bắc · Phong cách tin tức", "mai_anh"),
            ("⭐ Hải Đăng — Nam · Bắc · Phong cách tự nhiên", "hai_dang"),
            ("⭐ Thùy Dung — Nữ · Nam · Phong cách tin tức", "thuy_dung"),
            ("Minh Đức — Nam · Bắc · Phong cách tin tức", "minh_duc"),
            ("Phạm Tuyên — Nam · Bắc · Phong cách tự nhiên", "pham_tuyen"),
            ("Minh Triết — Nam · Nam · Phong cách tin tức", "minh_triet"),
        ]

        fake_engine = MagicMock()
        fake_engine.list_preset_voices.return_value = fake_choices

        tts = VieNeuLocalTTS()
        with patch.object(tts, "_get_engine", return_value=fake_engine):
            ordered = tts.list_preset_voices()

        expected_values = [
            "mai_anh",
            "thuy_dung",
            "minh_duc",
            "minh_triet",
            "truc_ly",
            "thien_minh",
            "hai_dang",
            "pham_tuyen",
        ]
        actual_values = [voice_val for _label, voice_val in ordered]
        self.assertEqual(actual_values, expected_values)

        # Confirm all 4 news voices are at the top
        for label, _ in ordered[:4]:
            self.assertIn("tin tức", label.lower())

        # Confirm remaining voices are non-news
        for label, _ in ordered[4:]:
            self.assertNotIn("tin tức", label.lower())


if __name__ == "__main__":
    unittest.main()
