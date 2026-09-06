# -*- coding: utf-8 -*-
"""
Tests for detecting rule files that were edited outside the app.

The owner named his worst case as "rules that got overwritten without me noticing".
These tests pin the guarantee: once a block has been written, a hand edit inside it is
detected, the file is NOT overwritten, and the change is reported.

Run with:  python -m unittest discover -s tests
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # allow "python -m unittest tests.x"

from conftest import IsolatedHubTestCase


class DriftTestCase(IsolatedHubTestCase):

    def setUp(self):
        super().setUp()
        self.project = self.tmp_dir / "project"
        self.project.mkdir(parents=True, exist_ok=True)
        self.hub.add_info("האתר שלי", "https://example.com")

    def claude_file(self):
        return self.project / "CLAUDE.md"


class TestFingerprinting(DriftTestCase):

    def test_extract_block_requires_both_markers_in_order(self):
        s, e = self.hub.START_MARKER, self.hub.END_MARKER
        self.assertIsNone(self.hub.extract_block("no markers here"))
        self.assertIsNone(self.hub.extract_block(f"only {s} start"))
        self.assertIsNone(self.hub.extract_block(f"{e} reversed {s}"),
                          "END before START must not be treated as a block")
        self.assertEqual(self.hub.extract_block(f"before {s}body{e} after"), f"{s}body{e}")

    def test_fingerprint_ignores_line_endings_and_outer_whitespace(self):
        s, e = self.hub.START_MARKER, self.hub.END_MARKER
        unix = f"{s}\nשורה\n{e}"
        windows = f"{s}\r\nשורה\r\n{e}"
        padded = f"\n\n{s}\nשורה\n{e}\n  "
        self.assertEqual(self.hub.block_fingerprint(unix), self.hub.block_fingerprint(windows),
                         "a CRLF rewrite must not read as a human edit")
        self.assertEqual(self.hub.block_fingerprint(unix), self.hub.block_fingerprint(padded))

    def test_fingerprint_changes_when_content_changes(self):
        s, e = self.hub.START_MARKER, self.hub.END_MARKER
        self.assertNotEqual(self.hub.block_fingerprint(f"{s}\nא\n{e}"),
                            self.hub.block_fingerprint(f"{s}\nב\n{e}"))

    def test_fingerprint_of_nothing_is_none(self):
        self.assertIsNone(self.hub.block_fingerprint(None))
        self.assertIsNone(self.hub.block_fingerprint(""))


class TestDriftDetection(DriftTestCase):

    def test_first_write_has_no_baseline_and_is_not_drift(self):
        ok, hashes = self.hub.inject_rules_into_folder(str(self.project))
        self.assertTrue(ok)
        self.assertIn("CLAUDE.md", hashes)
        self.assertEqual(self.hub.INJECTION_DRIFT, [])

    def test_untouched_file_syncs_again_cleanly(self):
        _, hashes = self.hub.inject_rules_into_folder(str(self.project))
        self.hub.INJECTION_DRIFT.clear()

        ok, new_hashes = self.hub.inject_rules_into_folder(str(self.project), known_hashes=hashes)

        self.assertTrue(ok)
        self.assertEqual(self.hub.INJECTION_DRIFT, [])
        self.assertIn("CLAUDE.md", new_hashes)

    def test_a_hand_edit_is_detected_and_the_file_is_not_overwritten(self):
        _, hashes = self.hub.inject_rules_into_folder(str(self.project))
        self.hub.INJECTION_DRIFT.clear()

        target = self.claude_file()
        text = target.read_text(encoding="utf-8")
        edited = text.replace(self.hub.END_MARKER, "השורה שהוספתי ביד\n" + self.hub.END_MARKER)
        target.write_text(edited, encoding="utf-8")

        ok, written = self.hub.inject_rules_into_folder(str(self.project), known_hashes=hashes)

        self.assertFalse(ok, "a drifted folder must not report success")
        self.assertNotIn("CLAUDE.md", written, "the drifted file must not be rewritten")
        self.assertIn("השורה שהוספתי ביד", target.read_text(encoding="utf-8"),
                      "the manual edit must survive")

        drift_files = [f["file"] for entry in self.hub.INJECTION_DRIFT for f in entry["files"]]
        self.assertIn("CLAUDE.md", drift_files)

    def test_force_overwrites_a_drifted_file(self):
        _, hashes = self.hub.inject_rules_into_folder(str(self.project))
        target = self.claude_file()
        target.write_text(
            target.read_text(encoding="utf-8").replace(
                self.hub.END_MARKER, "עריכה ידנית\n" + self.hub.END_MARKER),
            encoding="utf-8")

        ok, written = self.hub.inject_rules_into_folder(
            str(self.project), known_hashes=hashes, force=True)

        self.assertTrue(ok)
        self.assertIn("CLAUDE.md", written)
        self.assertNotIn("עריכה ידנית", target.read_text(encoding="utf-8"))

    def test_edits_outside_the_block_are_not_drift(self):
        _, hashes = self.hub.inject_rules_into_folder(str(self.project))
        self.hub.INJECTION_DRIFT.clear()

        target = self.claude_file()
        target.write_text("# הכותרת שלי\n\n" + target.read_text(encoding="utf-8"), encoding="utf-8")

        ok, _ = self.hub.inject_rules_into_folder(str(self.project), known_hashes=hashes)

        self.assertTrue(ok, "text outside the markers is the user's and is not a conflict")
        self.assertEqual(self.hub.INJECTION_DRIFT, [])
        self.assertIn("# הכותרת שלי", target.read_text(encoding="utf-8"))


class TestDriftThroughSync(DriftTestCase):

    def register_project(self):
        db = self.hub.load_db()
        db["targetPaths"] = [{"path": str(self.project), "name": "project",
                              "active": True, "lastSynced": None}]
        db.setdefault("settings", {})["syncScopeMode"] = "both"
        self.hub.save_db(db)

    def test_sync_records_baselines_then_reports_a_later_edit(self):
        self.register_project()
        inject_all = self.use_real_inject_all()

        first = inject_all()
        self.assertEqual(first["drifted_files"], [])
        stored = self.hub.get_paths()[0].get("injected", {})
        self.assertIn("CLAUDE.md", stored, "the sync must record what it wrote")

        target = self.claude_file()
        target.write_text(
            target.read_text(encoding="utf-8").replace(
                self.hub.END_MARKER, "שינוי ידני\n" + self.hub.END_MARKER),
            encoding="utf-8")

        second = inject_all()

        self.assertTrue(second["drifted_files"], "the edit must be reported to the user")
        self.assertIn("שינוי ידני", target.read_text(encoding="utf-8"))

    def test_force_resync_folder_clears_the_drift(self):
        self.register_project()
        inject_all = self.use_real_inject_all()
        inject_all()

        target = self.claude_file()
        target.write_text(
            target.read_text(encoding="utf-8").replace(
                self.hub.END_MARKER, "שינוי ידני\n" + self.hub.END_MARKER),
            encoding="utf-8")
        self.assertTrue(inject_all()["drifted_files"])

        self.hub.force_resync_folder(str(self.project))

        self.assertNotIn("שינוי ידני", target.read_text(encoding="utf-8"))
        self.assertEqual(inject_all()["drifted_files"], [],
                         "after an explicit overwrite the file must stop being flagged")


if __name__ == "__main__":
    unittest.main()
