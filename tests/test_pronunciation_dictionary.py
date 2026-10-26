import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from app import config
from app.services.pronunciation_dictionary import (
    apply_user_pronunciations,
    create_pronunciation,
    delete_pronunciation,
    list_pronunciations,
    update_pronunciation,
)
from app.services.text_processor import prepare_speech_text


class PronunciationDictionaryTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.dictionary_path = Path(self.temporary_directory.name) / "pronunciation.json"
        self.path_patch = mock.patch.object(
            config, "PRONUNCIATION_DICTIONARY_PATH", self.dictionary_path
        )
        self.path_patch.start()

    def tearDown(self):
        self.path_patch.stop()
        self.temporary_directory.cleanup()

    def test_create_update_toggle_and_delete_entry(self):
        created = create_pronunciation("  CP  ", " Chính phủ ")
        self.assertEqual(created.source, "CP")
        self.assertTrue(self.dictionary_path.is_file())

        updated = update_pronunciation(created.id, "CP", "Chính phủ Việt Nam", enabled=False)
        self.assertFalse(updated.enabled)
        self.assertEqual(list_pronunciations(), [updated])

        delete_pronunciation(created.id)
        self.assertEqual(list_pronunciations(), [])

    def test_longest_enabled_rule_wins_without_cascading(self):
        create_pronunciation("CP", "Chính phủ")
        create_pronunciation("NĐ-CP", "Nghị định của Chính phủ")
        disabled = create_pronunciation("UBND", "Ủy ban nhân dân")
        update_pronunciation(disabled.id, disabled.source, disabled.spoken, enabled=False)

        result, changed = apply_user_pronunciations("NĐ-CP của CP và UBND")

        self.assertTrue(changed)
        self.assertEqual(result, "Nghị định của Chính phủ của Chính phủ và UBND")

    def test_user_rule_overrides_builtin_speech_rule_without_mutating_original(self):
        create_pronunciation("CP", "Chính phủ trung ương")
        original = "Văn bản của CP."

        prepared = prepare_speech_text(original)

        self.assertEqual(prepared.original_text, original)
        self.assertEqual(prepared.speech_text, "Văn bản của Chính phủ trung ương.")
        self.assertIn("Áp dụng từ điển phát âm cá nhân", prepared.changes)

    def test_file_is_valid_utf8_json(self):
        create_pronunciation("ĐHQG", "Đại học Quốc gia")

        payload = json.loads(self.dictionary_path.read_text(encoding="utf-8"))

        self.assertEqual(payload["version"], 1)
        self.assertEqual(payload["entries"][0]["spoken"], "Đại học Quốc gia")


if __name__ == "__main__":
    unittest.main()
