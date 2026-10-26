import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from app import config, main


class ConfigTests(unittest.TestCase):
    def test_offline_configuration_sets_network_guards(self):
        config.configure_local_environment(offline=True)

        self.assertEqual(os.environ["HF_HUB_OFFLINE"], "1")
        self.assertEqual(os.environ["TRANSFORMERS_OFFLINE"], "1")
        self.assertEqual(os.environ["HF_HOME"], str(config.HF_HOME))

    def test_bundled_vietnamese_tessdata_is_configured(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            bin_dir = Path(temporary_directory)
            tessdata_dir = bin_dir / "tesseract" / "tessdata"
            tessdata_dir.mkdir(parents=True)
            (tessdata_dir / "vie.traineddata").touch()

            with mock.patch.object(config, "BIN_DIR", bin_dir), mock.patch.dict(
                os.environ, {}, clear=True
            ):
                config.configure_tesseract_environment()
                self.assertEqual(os.environ["TESSDATA_PREFIX"], str(tessdata_dir))

    def test_default_data_dir_uses_the_visible_public_data_folder(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(config._default_data_dir(), config.PUBLIC_DATA_DIR)

    def test_ocr_environment_uses_the_project_model_cache(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            config.configure_ocr_environment(offline=True)
            self.assertEqual(os.environ["PADDLE_PDX_CACHE_HOME"], str(config.PADDLE_CACHE_DIR))
            self.assertEqual(os.environ["PADDLE_PDX_MODEL_SOURCE"], "local")
            self.assertEqual(os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"], "True")

    def test_detects_an_existing_local_server(self):
        response = SimpleNamespace(
            status=200,
            read=lambda: (
                '{"app":"phat-thanh-ai","version":"'
                + config.RUNTIME_VERSION
                + '"}'
            ).encode(),
            close=lambda: None,
        )
        with mock.patch("app.main.urlopen", return_value=response):
            self.assertTrue(main._local_server_is_running())

    def test_rejects_a_stale_local_server(self):
        response = SimpleNamespace(
            status=200,
            read=lambda: b'{"app":"phat-thanh-ai","version":"old-build"}',
            close=lambda: None,
        )
        with mock.patch("app.main.urlopen", return_value=response):
            self.assertFalse(main._local_server_is_running())


if __name__ == "__main__":
    unittest.main()
