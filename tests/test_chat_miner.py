# -*- coding: utf-8 -*-
"""
Tests for the upgraded Chat & Email Miner:
- Multi-app chat discovery (Antigravity, Claude, Cursor, Windsurf, ChatGPT)
- Folder batch parsing
- Email file (.eml) and raw email parsing
- Heuristic memory extraction (offline fallback)
- Gemini optimizer fallback to heuristics

Run with:  python -m unittest tests/test_chat_miner.py
"""

import email
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
import sys
import tempfile
import unittest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import chat_miner
import gemini_optimizer


class TestChatMinerDiscovery(unittest.TestCase):

    def test_discover_chats_all_apps(self):
        apps = [
            "Google Antigravity",
            "VS Code Copilot",
            "GitHub Copilot",
            "Cline",
            "Roo",
            "Claude Code",
            "Cursor IDE",
            "Windsurf IDE",
            "ChatGPT Export",
            "all",
            "NonExistentApp"
        ]
        for app in apps:
            with self.subTest(app=app):
                results = chat_miner.discover_chats(app_name=app, max_results=5)
                self.assertIsInstance(results, list)
                for item in results:
                    self.assertIn("path", item)
                    self.assertIn("title", item)
                    self.assertIn("app", item)
                    self.assertIn("size_kb", item)
                    self.assertIn("time_str", item)


class TestFolderAndEmailParsing(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.dir_path = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_parse_folder_chats(self):
        (self.dir_path / "chat1.txt").write_text("User: Hello\nAI: Hi there", encoding="utf-8")
        (self.dir_path / "notes.md").write_text("# Project Notes\nAlways keep documentation", encoding="utf-8")
        (self.dir_path / "ignored.exe").write_bytes(b"\x00\x01\x02")

        merged = chat_miner.parse_folder_chats(str(self.dir_path), max_files=10)
        self.assertIn("chat1.txt", merged)
        self.assertIn("Hello", merged)
        self.assertIn("notes.md", merged)
        self.assertIn("Project Notes", merged)

    def test_parse_email_file(self):
        msg = MIMEMultipart()
        msg["From"] = "boss@example.com"
        msg["To"] = "dev@example.com"
        msg["Subject"] = "Project Rules"
        msg["Date"] = "Thu, 04 Sep 2026 10:00:00 +0000"
        body = "שלום רב,\nנא לא למחוק הערות בקוד.\nבברכה,\nדניאל כהן"
        msg.attach(MIMEText(body, "plain", "utf-8"))

        eml_path = self.dir_path / "test.eml"
        with open(eml_path, "wb") as f:
            f.write(msg.as_bytes())

        parsed = chat_miner.parse_email_file(str(eml_path))
        self.assertIn("boss@example.com", parsed)
        self.assertIn("Project Rules", parsed)
        self.assertIn("דניאל כהן", parsed)

    def test_parse_raw_email(self):
        raw = """From: customer@shop.com
To: info@company.co.il
Subject: Inquiry
Date: 2026-09-04

היי,
האם האתר שלכם הוא https://myshop.co.il?
בברכה,
רוני לוי
"""
        parsed = chat_miner.parse_raw_email(raw)
        self.assertIn("customer@shop.com", parsed)
        self.assertIn("https://myshop.co.il", parsed)

    def test_parse_copilot_chat(self):
        # Create a mock copilot jsonl file
        copilot_file = self.dir_path / "copilot_session.jsonl"
        lines = [
            '{"v": {"customTitle": "Refactor Architecture", "message": {"text": "How do I optimize performance?"}}}',
            '{"k": ["requests", 0, "response"], "v": [{"value": "You can use async operations."}]}'
        ]
        copilot_file.write_text("\n".join(lines), encoding="utf-8")
        parsed = chat_miner.parse_copilot_chat(str(copilot_file))
        self.assertIn("How do I optimize performance?", parsed)
        self.assertIn("async operations", parsed)

    def test_parse_cline_chat(self):
        # Create a mock cline ui_messages.json file
        cline_file = self.dir_path / "ui_messages.json"
        content = [
            {"say": "task", "text": "Create a new database migration"},
            {"say": "text", "text": "I will generate the SQL migration file for you."}
        ]
        import json
        cline_file.write_text(json.dumps(content), encoding="utf-8")
        parsed = chat_miner.parse_cline_chat(str(cline_file))
        self.assertIn("Create a new database migration", parsed)
        self.assertIn("SQL migration file", parsed)


class TestHeuristicMemoryExtraction(unittest.TestCase):

    def test_extract_heuristic_from_chat(self):
        sample_chat = """
משתמש: האתר הרשמי שלי הוא https://mycoolsite.com והאימייל שלי ליצירת קשר הוא contact@cool.org.
משתמש: אל תמחק שום הערה קיימת בקוד הפרויקט.
משתמש: תקפיד לכתוב בדיקות יחידה מקיפות לכל מודול.
משתמש: תענה תמיד בעברית רהוטה וברורה.
"""
        ok, memories = chat_miner.extract_heuristic_memories(sample_chat, source_type="chat")
        self.assertTrue(ok)
        self.assertIsInstance(memories, list)
        self.assertGreaterEqual(len(memories), 2)

        categories = {m["category"] for m in memories}
        # We expect facts (URL or email), constraints, or commands
        self.assertTrue("facts" in categories or "constraints" in categories or "commands" in categories)

        # Check structure of items
        for m in memories:
            self.assertIn("category", m)
            self.assertIn("title", m)
            self.assertIn("data", m)
            self.assertIn("confidence", m)

    def test_extract_heuristic_from_email_signature(self):
        email_text = """From: manager@biz.com
Subject: Weekly Update

בוקר טוב לכולם,
נא לוודא שכל המשימות מתועדות.

בברכה,
יוסי כהן - מנכ"ל החברה
טלפון: 050-1234567
"""
        ok, memories = chat_miner.extract_heuristic_memories(email_text, source_type="email")
        self.assertTrue(ok)
        self.assertIsInstance(memories, list)
        self.assertGreaterEqual(len(memories), 1)

        found_signature = any("יוסי כהן" in str(m.get("data", {})) for m in memories)
        self.assertTrue(found_signature)


class TestGeminiOptimizerFallback(unittest.TestCase):

    def test_fallback_when_empty_or_offline(self):
        text = "אל תשתמש ב-any ב-TypeScript. האתר הרשמי הוא https://safe-domain.org"
        old_call = gemini_optimizer.call_gemini
        gemini_optimizer.call_gemini = lambda *a, **k: (False, "Offline / API unavailable")
        try:
            ok, res = gemini_optimizer.extract_memories_from_chat(text, source_type="chat")
            self.assertTrue(ok)
            self.assertIsInstance(res, list)
            self.assertGreaterEqual(len(res), 1)
        finally:
            gemini_optimizer.call_gemini = old_call


if __name__ == "__main__":
    unittest.main()
