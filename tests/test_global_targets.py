# -*- coding: utf-8 -*-
"""
Tests for user-level ("global") rule files.

Most AI tools read one rules file that applies to every project, so directives belong there
once instead of being copied into ~20 project folders. These tests pin the detection, the
per-tool enable switch, and the guarantee that nothing is written for a tool that is not
installed. They never touch the real home directory - USER_HOME is redirected per test.

Run with:  python -m unittest discover -s tests
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # allow "python -m unittest tests.x"

from conftest import IsolatedHubTestCase


class GlobalTargetTestCase(IsolatedHubTestCase):
    """Points every global target at a fake home directory inside the temp dir."""

    def setUp(self):
        super().setUp()
        self.fake_home = self.tmp_dir / "home"
        self.fake_home.mkdir(parents=True, exist_ok=True)

        home = self.fake_home
        self.hub.GLOBAL_TARGETS = [
            {
                "key": "claude_code", "name": "Claude Code", "ai_key": "claude",
                "detect": lambda: home / ".claude",
                "file": lambda: home / ".claude" / "CLAUDE.md",
                "note": "test",
            },
            {
                "key": "codex", "name": "Codex", "ai_key": "all",
                "detect": lambda: home / ".codex",
                "file": lambda: home / ".codex" / "AGENTS.md",
                "note": "test",
            },
        ]

    def install(self, tool_dir):
        (self.fake_home / tool_dir).mkdir(parents=True, exist_ok=True)


class TestDetection(GlobalTargetTestCase):

    def test_nothing_is_installed_by_default(self):
        targets = self.hub.get_global_targets()
        self.assertEqual([t["installed"] for t in targets], [False, False])

    def test_a_tool_counts_as_installed_once_its_config_dir_exists(self):
        self.install(".claude")
        targets = {t["key"]: t for t in self.hub.get_global_targets()}
        self.assertTrue(targets["claude_code"]["installed"])
        self.assertFalse(targets["codex"]["installed"])

    def test_written_flag_tracks_the_file(self):
        self.install(".claude")
        self.assertFalse(self.hub.get_global_targets()[0]["written"])
        self.hub.inject_global_targets()
        self.assertTrue(self.hub.get_global_targets()[0]["written"])


class TestInjection(GlobalTargetTestCase):

    def test_writes_only_for_installed_tools(self):
        self.install(".claude")
        self.hub.add_info("האתר שלי", "https://example.com")

        res = self.hub.inject_global_targets()

        self.assertEqual(res["written"], ["Claude Code"])
        self.assertEqual(res["failed"], [])
        self.assertTrue((self.fake_home / ".claude" / "CLAUDE.md").exists())
        self.assertFalse((self.fake_home / ".codex" / "AGENTS.md").exists(),
                         "a tool that is not installed must never get a file")

    def test_written_file_carries_the_directives_between_markers(self):
        self.install(".claude")
        self.hub.add_info("האתר שלי", "https://example.com")

        self.hub.inject_global_targets()
        text = (self.fake_home / ".claude" / "CLAUDE.md").read_text(encoding="utf-8")

        self.assertIn(self.hub.START_MARKER, text)
        self.assertIn(self.hub.END_MARKER, text)
        self.assertIn("example.com", text)

    def test_reinjection_replaces_the_block_and_keeps_the_users_own_text(self):
        self.install(".claude")
        target = self.fake_home / ".claude" / "CLAUDE.md"
        target.write_text("# ההערות שלי\n\nטקסט שאסור לאבד.\n", encoding="utf-8")

        self.hub.add_info("ראשון", "1")
        self.hub.inject_global_targets()
        self.hub.add_info("שני", "2")
        self.hub.inject_global_targets()

        text = target.read_text(encoding="utf-8")
        self.assertEqual(text.count(self.hub.START_MARKER), 1, "the block must be replaced, not appended")
        self.assertIn("טקסט שאסור לאבד.", text, "text outside the markers must survive")
        self.assertIn("שני", text)

    def test_a_disabled_target_is_skipped(self):
        self.install(".claude")
        db = self.hub.load_db()
        db["settings"]["disabledGlobalTargets"] = ["claude_code"]
        self.hub.save_db(db)

        res = self.hub.inject_global_targets()

        self.assertEqual(res["written"], [])
        self.assertFalse((self.fake_home / ".claude" / "CLAUDE.md").exists())

    def test_the_whole_feature_can_be_turned_off(self):
        self.install(".claude")
        db = self.hub.load_db()
        db["settings"]["injectGlobalTargets"] = False
        self.hub.save_db(db)

        res = self.hub.inject_global_targets()

        self.assertEqual(res["written"], [])
        self.assertFalse((self.fake_home / ".claude" / "CLAUDE.md").exists())

    def test_cleaning_removes_the_block_but_not_the_file_content(self):
        self.install(".claude")
        target = self.fake_home / ".claude" / "CLAUDE.md"
        target.write_text("# שלי\n\nשורה שנשארת.\n", encoding="utf-8")
        self.hub.add_info("עובדה", "ערך")
        self.hub.inject_global_targets()

        self.hub.clean_global_targets()

        text = target.read_text(encoding="utf-8")
        self.assertNotIn(self.hub.START_MARKER, text)
        self.assertIn("שורה שנשארת.", text)

    def test_inject_all_reports_the_global_targets(self):
        """A full sync must drive the global files too, and say so in its result."""
        self.install(".claude")
        inject_all = self.use_real_inject_all()  # safe: setUp cleared targetPaths

        res = inject_all()

        self.assertIn("global_written", res)
        self.assertEqual(res["global_written"], ["Claude Code"])
        self.assertEqual(res["failed_folders"], [])
        self.assertTrue((self.fake_home / ".claude" / "CLAUDE.md").exists())


if __name__ == "__main__":
    unittest.main()
