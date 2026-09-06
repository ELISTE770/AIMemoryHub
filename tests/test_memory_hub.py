# -*- coding: utf-8 -*-
"""
Tests for the data layer (memory_hub.py) - CRUD, persistence safety, validation and the
concurrency guard. These cover the paths where a silent failure destroys saved directives.

Run with:  python -m unittest discover -s tests
"""

import json
import threading
import unittest

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))  # allow "python -m unittest tests.x"

from conftest import IsolatedHubTestCase


class TestCrud(IsolatedHubTestCase):

    def test_add_and_get_item_roundtrip(self):
        self.hub.add_info("האתר שלי", "https://example.com")
        facts = self.hub.get_facts()
        self.assertTrue(any(f["name"] == "האתר שלי" and f["value"] == "https://example.com"
                            for f in facts))

    def test_toggle_item_flips_active_flag(self):
        item = self.hub.add_style("שפה", "עברית רהוטה")

        self.hub.toggle_item("styles", item["id"], False)
        stored = [s for s in self.hub.get_styles() if s["id"] == item["id"]][0]
        self.assertFalse(stored["active"])

        self.hub.toggle_item("styles", item["id"], True)
        stored = [s for s in self.hub.get_styles() if s["id"] == item["id"]][0]
        self.assertTrue(stored["active"])

    def test_remove_item(self):
        item = self.hub.add_constraint("אל תמחק הערות", "שמור על התיעוד")
        self.assertTrue(any(c["id"] == item["id"] for c in self.hub.get_constraints()))

        self.hub.remove_item("constraints", item["id"])
        self.assertFalse(any(c["id"] == item["id"] for c in self.hub.get_constraints()))

    def test_update_item_changes_fields(self):
        item = self.hub.add_command("חתימה", "לצרף חתימה בסוף", "במיילים")
        ok, updated = self.hub.update_item("commands", item["id"], {"details": "טקסט חדש"})
        self.assertTrue(ok)
        self.assertEqual(updated["details"], "טקסט חדש")

    def test_update_missing_item_reports_failure(self):
        ok, msg = self.hub.update_item("facts", "does-not-exist", {"value": "x"})
        self.assertFalse(ok)

    def test_reorder_item_moves_entry_up(self):
        first = self.hub.add_info("א", "1")
        second = self.hub.add_info("ב", "2")
        # Newest is inserted at the top, so `second` starts above `first`.
        self.assertEqual([f["id"] for f in self.hub.get_facts()][:2], [second["id"], first["id"]])

        self.hub.reorder_item("facts", first["id"], "up")
        self.assertEqual([f["id"] for f in self.hub.get_facts()][:2], [first["id"], second["id"]])

    def test_every_category_uses_its_documented_fields(self):
        """
        Guards the class of bug where a UI copy-paste reads a field the data layer never
        writes (e.g. item["style"] on a styles item, which crashed the Styles page).
        """
        expected = {
            "facts": ({"name", "value"}, lambda: self.hub.add_info("n", "v")),
            "commands": ({"name", "details", "trigger_case"},
                         lambda: self.hub.add_command("n", "d", "t")),
            "constraints": ({"constraint", "alternative_or_why"},
                            lambda: self.hub.add_constraint("c", "why")),
            "styles": ({"aspect", "instruction"}, lambda: self.hub.add_style("a", "i")),
            "instructions": ({"instruction", "when_to_apply"},
                             lambda: self.hub.add_instruction("i", "when")),
        }
        for category, (fields, factory) in expected.items():
            with self.subTest(category=category):
                item = factory()
                self.assertTrue(fields.issubset(item.keys()),
                                f"{category}: expected fields {fields}, got {set(item.keys())}")


class TestPersistenceSafety(IsolatedHubTestCase):

    def test_save_db_is_atomic_and_leaves_no_temp_file(self):
        self.hub.add_info("בדיקה", "ערך")
        leftovers = list(self.hub.DATA_DIR.glob("*.tmp"))
        self.assertEqual(leftovers, [], f"temp files left behind: {leftovers}")
        self.assertTrue(self.hub.MEMORY_FILE.exists())
        json.loads(self.hub.MEMORY_FILE.read_text(encoding="utf-8"))  # must be valid JSON

    def test_save_db_keeps_a_backup_copy(self):
        self.hub.add_info("ראשון", "1")
        self.hub.add_info("שני", "2")
        backup = self.hub.MEMORY_FILE.with_name(self.hub.MEMORY_FILE.name + ".bak")
        self.assertTrue(backup.exists(), "save_db must keep a .bak copy of the previous database")
        json.loads(backup.read_text(encoding="utf-8"))

    def test_corrupt_database_is_preserved_not_discarded(self):
        self.hub.add_info("חשוב מאוד", "אסור לאבד")
        self.hub.MEMORY_FILE.write_text("{ this is not valid json", encoding="utf-8")

        db = self.hub.load_db()
        self.assertIn("profiles", db, "load_db must fall back to a usable default database")

        preserved = list(self.hub.DATA_DIR.glob("memory.json.corrupt-*"))
        self.assertTrue(preserved, "the unreadable file must be preserved before defaults take over")
        self.assertIn("not valid json", preserved[0].read_text(encoding="utf-8"))
        self.assertTrue(self.hub.LAST_LOAD_ERROR["error"],
                        "the failure must be recorded so the GUI can surface it")


class TestStructureValidation(IsolatedHubTestCase):

    def test_accepts_valid_db(self):
        ok, err = self.hub.validate_db_structure(self.hub.get_default_database())
        self.assertTrue(ok)
        self.assertEqual(err, "")

    def test_rejects_malformed_structures(self):
        cases = [
            {"profiles": {"default": {"data": {"facts": "not-a-list"}}}},
            {"profiles": "nope"},
            {"profiles": {}},
            {"something": "else"},
            "not-a-dict",
        ]
        for bad in cases:
            with self.subTest(bad=str(bad)[:40]):
                ok, _ = self.hub.validate_db_structure(bad)
                self.assertFalse(ok)

    def test_accepts_legacy_flat_format(self):
        ok, _ = self.hub.validate_db_structure({"facts": []})
        self.assertTrue(ok, "the pre-v5 flat format is migrated by load_db and must be accepted")


class TestImportBackup(IsolatedHubTestCase):

    def test_invalid_json_is_rejected_without_touching_db(self):
        self.hub.add_info("קיים", "ערך מקורי")
        before = self.hub.MEMORY_FILE.read_text(encoding="utf-8")

        bad_file = self.tmp_dir / "bad_backup.json"
        bad_file.write_text("{ broken", encoding="utf-8")

        ok, msg = self.hub.import_backup(str(bad_file))
        self.assertFalse(ok)
        self.assertTrue(msg)
        self.assertEqual(self.hub.MEMORY_FILE.read_text(encoding="utf-8"), before,
                         "a bad import must not overwrite the database")

    def test_missing_file_is_reported_not_raised(self):
        ok, msg = self.hub.import_backup(str(self.tmp_dir / "nope.json"))
        self.assertFalse(ok)
        self.assertTrue(msg)

    def test_valid_backup_restores_and_keeps_pre_import_copy(self):
        self.hub.add_info("ישן", "ערך ישן")

        good = self.hub.get_default_database()
        good["profiles"]["default"]["data"]["facts"] = [
            {"id": "f1", "name": "חדש", "value": "ערך חדש", "scope": "global", "active": True}
        ]
        good_file = self.tmp_dir / "good_backup.json"
        good_file.write_text(json.dumps(good, ensure_ascii=False), encoding="utf-8")

        ok, msg = self.hub.import_backup(str(good_file))
        self.assertTrue(ok, msg)
        self.assertTrue(any(f["name"] == "חדש" for f in self.hub.get_facts()))
        self.assertTrue(list(self.hub.DATA_DIR.glob("memory.json.before-import-*")),
                        "a pre-import copy must be kept so a bad restore is recoverable")


class TestConcurrency(IsolatedHubTestCase):

    def test_concurrent_adds_do_not_lose_writes(self):
        """
        Without DB_LOCK the interleaved load->mutate->save cycles overwrite each other and
        items silently vanish. Every write must survive.
        """
        errors = []

        def worker(i):
            try:
                self.hub.add_info(f"פריט-{i}", str(i))
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(errors, [], f"threads raised: {errors}")
        names = {f["name"] for f in self.hub.get_facts()}
        missing = {f"פריט-{i}" for i in range(20)} - names
        self.assertFalse(missing, f"writes lost under concurrency: {sorted(missing)}")


class TestPromptGeneration(IsolatedHubTestCase):

    def test_prompt_contains_active_items_only(self):
        self.hub.add_info("מוצג", "ערך גלוי")
        hidden = self.hub.add_info("מוסתר", "ערך מוסתר")
        self.hub.toggle_item("facts", hidden["id"], False)

        md = self.hub.generate_prompt_markdown(target_folder_path=None)
        self.assertIn("ערך גלוי", md)
        self.assertNotIn("ערך מוסתר", md)

    def test_inject_then_clean_restores_original_text(self):
        original = "# הקובץ שלי\n\nתוכן קיים שאסור לאבד.\n"
        block = self.hub.generate_prompt_markdown(target_folder_path=None)
        injected = self.hub.inject_into_text(original, block)

        self.assertIn(self.hub.START_MARKER, injected)
        self.assertIn(self.hub.END_MARKER, injected)
        self.assertIn("תוכן קיים שאסור לאבד.", injected)

        cleaned = self.hub.clean_text_memory(injected)
        self.assertNotIn(self.hub.START_MARKER, cleaned)
        self.assertIn("תוכן קיים שאסור לאבד.", cleaned)

    def test_inject_is_idempotent(self):
        block = self.hub.generate_prompt_markdown(target_folder_path=None)
        once = self.hub.inject_into_text("תוכן\n", block)
        twice = self.hub.inject_into_text(once, block)
        self.assertEqual(twice.count(self.hub.START_MARKER), 1,
                         "re-injecting must replace the block, not append a second one")
        self.assertIn("תוכן", twice, "the user's own file content must survive re-injection")

    def test_unmarked_block_is_wrapped_so_it_stays_removable(self):
        """
        Defensive: a caller passing raw text (no markers) must still produce a replaceable
        region - otherwise every sync would append another copy into the user's CLAUDE.md.
        """
        once = self.hub.inject_into_text("תוכן\n", "כללים ללא סימון")
        twice = self.hub.inject_into_text(once, "כללים ללא סימון")
        self.assertEqual(twice.count(self.hub.START_MARKER), 1)
        self.assertNotIn(self.hub.START_MARKER, self.hub.clean_text_memory(twice))


class TestCloudPayload(IsolatedHubTestCase):

    def test_credentials_are_stripped_before_upload(self):
        """The Gist backup must never carry the API key / access token."""
        db = self.hub.load_db()
        db["settings"]["geminiApiKey"] = "SECRET-GEMINI-KEY"
        db["settings"]["githubGistToken"] = "ghp_SECRETTOKEN"
        self.hub.save_db(db)

        captured = {}

        class FakeResponse:
            status_code = 201

            @staticmethod
            def json():
                return {"id": "gist123"}

        def fake_post(url, json=None, headers=None, timeout=None, verify=None):
            captured["body"] = json["files"]["universal_ai_memory.json"]["content"]
            captured["verify"] = verify
            return FakeResponse()

        self.hub.requests.post = fake_post
        try:
            ok, msg, gid = self.hub.push_to_cloud(token="ghp_SECRETTOKEN", gist_id="")
        finally:
            import requests as _r
            self.hub.requests.post = _r.post

        self.assertTrue(ok, msg)
        self.assertNotIn("SECRET-GEMINI-KEY", captured["body"])
        self.assertNotIn("ghp_SECRETTOKEN", captured["body"])
        self.assertNotEqual(captured["verify"], False, "TLS verification must never be disabled")


if __name__ == "__main__":
    unittest.main()
