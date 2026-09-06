# -*- coding: utf-8 -*-
"""
Tests for the Web Dashboard Analytics endpoint (/api/analytics) and multi-app miner chats.
"""

import json
import threading
import urllib.request
from http.server import HTTPServer
from pathlib import Path
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import web_server
import memory_hub


class TestWebAnalytics(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), web_server.MemoryHubHTTPHandler)
        cls.port = cls.server.server_port
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def test_analytics_endpoint(self):
        url = f"http://127.0.0.1:{self.port}/api/analytics"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=5) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertTrue(data.get("success"))
            self.assertIn("totals", data)
            self.assertIn("categories", data)
            self.assertIn("profiles", data)
            self.assertIn("active_profile", data)
            self.assertIn("scope_counts", data)

            totals = data["totals"]
            self.assertIn("total_directives", totals)
            self.assertIn("active_directives", totals)
            self.assertIn("total_projects", totals)

            categories = data["categories"]
            for cat in ["facts", "constraints", "commands", "styles", "rules", "contextFiles"]:
                self.assertIn(cat, categories)
                self.assertIn("total", categories[cat])
                self.assertIn("active", categories[cat])
                self.assertIn("color", categories[cat])

    def test_miner_chats_with_app_param(self):
        url = f"http://127.0.0.1:{self.port}/api/miner/chats?app=copilot"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=5) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertTrue(data.get("success"))
            self.assertIn("chats", data)
            self.assertEqual(data.get("app"), "copilot")


if __name__ == "__main__":
    unittest.main()
