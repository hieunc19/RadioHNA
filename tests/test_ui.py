import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import config
from app.services.ocr_service import OCRResult
from app.ui.web import create_web_app


class WebUITests(unittest.TestCase):
    def test_local_html_interface_and_health_endpoint_load(self):
        client = TestClient(create_web_app())
        page = client.get("/")
        health = client.get("/api/health")

        self.assertEqual(page.status_code, 200)
        self.assertIn("PHÁT THANH AI", page.text)
        self.assertIn('id="previewStatus"', page.text)
        self.assertIn('id="ttsStatus"', page.text)
        self.assertIn('id="pronunciationForm"', page.text)
        self.assertIn('id="editorOcrBadge"', page.text)
        self.assertIn('id="ocrProgressLine"', page.text)
        self.assertIn('id="navTabBulletin"', page.text)
        self.assertIn('id="navTabPronunciation"', page.text)
        self.assertIn('id="viewBulletin"', page.text)
        self.assertIn('id="viewPronunciation"', page.text)
        self.assertIn('id="navDictionaryCount"', page.text)
        self.assertIn('id="pronunciationSearch"', page.text)
        self.assertEqual(
            health.json(),
            {
                "app": "phat-thanh-ai",
                "status": "ok",
                "version": config.RUNTIME_VERSION,
            },
        )

    def test_ocr_stream_sends_page_text_before_completion(self):
        partial = OCRResult("Trang một.", (), 1, "OCR AI")
        final = OCRResult("Trang một.\n\nTrang hai.", (), 2, "OCR AI")

        def fake_ocr(_paths, progress):
            progress(0.5, "Đã xong trang một")
            yield partial
            progress(1.0, "Đã xong trang hai")
            yield final

        with (
            patch("app.ui.web._save_uploads", return_value=[Path("notice.png")]),
            patch("app.ui.web.iter_recognize_documents", side_effect=fake_ocr),
        ):
            response = TestClient(create_web_app()).post(
                "/api/ocr/stream",
                files={"files": ("notice.png", b"image", "image/png")},
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn("event: page", response.text)
        self.assertIn("Trang một.", response.text)
        self.assertIn("event: complete", response.text)
        self.assertIn("Trang hai.", response.text)

    def test_voices_api_returns_preset_voices_with_news_first(self):
        fake_voices = [
            ("⭐ Mai Anh — Nữ · Bắc · Phong cách tin tức", "mai_anh"),
            ("⭐ Trúc Ly — Nữ · Bắc · Phong cách tự nhiên", "truc_ly"),
        ]
        with patch("app.ui.web.VieNeuLocalTTS.list_preset_voices", return_value=fake_voices):
            response = TestClient(create_web_app()).get("/api/voices")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("voices", data)
        self.assertEqual(len(data["voices"]), 2)
        self.assertEqual(data["voices"][0]["value"], "mai_anh")
        self.assertIn("tin tức", data["voices"][0]["label"].lower())

    def test_open_output_uses_platform_directory_helper(self):
        with patch("app.ui.web._open_directory") as open_directory:
            response = TestClient(create_web_app()).post("/api/open-output")

        self.assertEqual(response.status_code, 200)
        open_directory.assert_called_once_with(config.OUTPUT_DIR)
        self.assertIn("Đã mở thư mục", response.json()["message"])

    def test_pronunciation_dictionary_api_crud(self):
        with tempfile.TemporaryDirectory() as temporary_directory, patch.object(
            config,
            "PRONUNCIATION_DICTIONARY_PATH",
            Path(temporary_directory) / "pronunciation.json",
        ):
            client = TestClient(create_web_app())
            created = client.post(
                "/api/pronunciations",
                json={"source": "CP", "spoken": "Chính phủ", "enabled": True},
            )
            self.assertEqual(created.status_code, 200)
            entry = created.json()["entry"]

            listed = client.get("/api/pronunciations")
            self.assertEqual(listed.json()["entries"], [entry])

            updated = client.put(
                f"/api/pronunciations/{entry['id']}",
                json={"source": "CP", "spoken": "Chính phủ Việt Nam", "enabled": False},
            )
            self.assertEqual(updated.status_code, 200)
            self.assertFalse(updated.json()["entry"]["enabled"])

            deleted = client.delete(f"/api/pronunciations/{entry['id']}")
            self.assertEqual(deleted.status_code, 200)
            self.assertEqual(client.get("/api/pronunciations").json()["entries"], [])

    def test_pronunciation_preview_returns_audio(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            preview = Path(temporary_directory) / "preview.wav"
            preview.write_bytes(b"RIFF-test")
            with patch("app.ui.web.preview_pronunciation", return_value=preview) as synthesize:
                response = TestClient(create_web_app()).post(
                    "/api/pronunciations/preview",
                    json={"spoken": "Chính phủ", "voice": "hai_dang"},
                )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "audio/wav")
        synthesize.assert_called_once_with("Chính phủ", "hai_dang")


if __name__ == "__main__":
    unittest.main()
