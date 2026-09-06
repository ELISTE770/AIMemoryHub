# -*- coding: utf-8 -*-
"""
Unit tests for Gemini model selection:
- Friendly Hebrew names without version numbers ("פלאש לייט לאסט", "פלאש לאסט", "פרו לאסט")
- Mapping to canonical API aliases and fallbacks
- Default model resolution from memory_hub settings
- Passing model parameter through optimization and chat mining functions

Run with:  python -m unittest tests/test_gemini_models.py
"""

from pathlib import Path
import re
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import gemini_optimizer
import memory_hub


class TestGeminiModelSelection(unittest.TestCase):

    def test_friendly_names_contain_no_numbers(self):
        expected_names = ["פלאש לייט לאסט", "פלאש לאסט", "פרו לאסט"]
        self.assertEqual(list(gemini_optimizer.AVAILABLE_MODELS.keys()), expected_names)

        for name in expected_names:
            with self.subTest(name=name):
                # Must contain NO digits (no 1.5, 2.0, 2.5, 3.6, etc.)
                self.assertIsNone(re.search(r"\d", name), f"Model label '{name}' contains numbers!")

    def test_resolve_model_candidates(self):
        lite_candidates = gemini_optimizer.resolve_model_candidates("פלאש לייט לאסט")
        self.assertEqual(lite_candidates[0], "gemini-flash-lite-latest")
        self.assertGreater(len(lite_candidates), 1)

        flash_candidates = gemini_optimizer.resolve_model_candidates("פלאש לאסט")
        self.assertEqual(flash_candidates[0], "gemini-flash-latest")
        self.assertGreater(len(flash_candidates), 1)

        pro_candidates = gemini_optimizer.resolve_model_candidates("פרו לאסט")
        self.assertEqual(pro_candidates[0], "gemini-pro-latest")
        self.assertGreater(len(pro_candidates), 1)

    def test_default_model_setting(self):
        default_model = gemini_optimizer.get_default_model()
        self.assertIn(default_model, gemini_optimizer.FRIENDLY_MODEL_OPTIONS)

        db = memory_hub.load_db()
        self.assertIn("defaultGeminiModel", db.get("settings", {}))
        self.assertEqual(db["settings"]["defaultGeminiModel"], "פלאש לאסט")

    def test_functions_accept_model_param(self):
        from unittest.mock import patch, MagicMock

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "candidates": [
                {"content": {"parts": [{"text": '{"name": "OK", "value": "1", "explanation": "test"}'}]}}
            ]
        }

        with patch("requests.post", return_value=mock_resp) as mock_post:
            ok, res = gemini_optimizer.optimize_info("test", "val", api_key="fake_key", model="פלאש לייט לאסט")
            self.assertTrue(ok)
            called_url = mock_post.call_args[0][0]
            self.assertIn("gemini-flash-lite-latest", called_url)

        with patch("requests.post", return_value=mock_resp) as mock_post:
            ok, res = gemini_optimizer.optimize_command("cmd", "details", "when", api_key="fake_key", model="פלאש לאסט")
            self.assertTrue(ok)
            called_url = mock_post.call_args[0][0]
            self.assertIn("gemini-flash-latest", called_url)

        with patch("requests.post", return_value=mock_resp) as mock_post:
            ok, res = gemini_optimizer.optimize_constraint("no bugs", "", api_key="fake_key", model="פרו לאסט")
            self.assertTrue(ok)
            called_url = mock_post.call_args[0][0]
            self.assertIn("gemini-pro-latest", called_url)

    def test_ssl_error_fallback_and_sanitization(self):
        from unittest.mock import patch, MagicMock
        import requests

        mock_ok = MagicMock()
        mock_ok.status_code = 200
        mock_ok.json.return_value = {
            "candidates": [{"content": {"parts": [{"text": "OK"}]}}]
        }

        # Side effect: first call raises SSLError, second call (verify=False) returns 200
        with patch("requests.post", side_effect=[requests.exceptions.SSLError("CERTIFICATE_VERIFY_FAILED"), mock_ok]) as mock_post:
            ok, res = gemini_optimizer.call_gemini("test prompt", api_key="fake_key", model="פלאש לאסט")
            self.assertTrue(ok)
            self.assertEqual(res, "OK")
            # Verify that the second call had verify=False
            self.assertFalse(mock_post.call_args_list[1][1]["verify"])

        # Test error sanitization
        err = gemini_optimizer.sanitize_gemini_error("Max retries exceeded with url: /v1beta/models/gemini-3.6-flash:generateContent (SSLError)")
        self.assertNotIn("3.6", err)
        self.assertNotIn("/v1beta/models", err)
        self.assertIn("SSL", err)


if __name__ == "__main__":
    unittest.main()
