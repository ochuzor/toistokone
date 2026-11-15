import unittest

from backend.app.config import ConfigurationError, load_settings


class SettingsTests(unittest.TestCase):
    def test_default_batch_size_is_twenty(self) -> None:
        self.assertEqual(load_settings({}).quiz_batch_size, 20)

    def test_accepts_positive_batch_size(self) -> None:
        self.assertEqual(load_settings({"QUIZ_BATCH_SIZE": "7"}).quiz_batch_size, 7)

    def test_rejects_non_positive_batch_size(self) -> None:
        for value in ("0", "-1", "not-a-number"):
            with self.subTest(value=value):
                with self.assertRaises(ConfigurationError):
                    load_settings({"QUIZ_BATCH_SIZE": value})
