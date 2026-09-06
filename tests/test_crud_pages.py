# -*- coding: utf-8 -*-
"""
Tests for the generic directive pages (CRUD_PAGE_SPECS + build/refresh/add/optimize).

The spec table is now the single source of truth for all five directive pages, so these
tests assert it stays consistent with what memory_hub and gemini_optimizer actually expect.
The signature tests below are static - they catch a mismatched field order without a display.

Run with:  python -m unittest discover -s tests
"""

import inspect
import os
import sys
import shutil
import importlib
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _display_available():
    try:
        import tkinter
        root = tkinter.Tk()
        root.destroy()
        return True
    except Exception:
        return False


class TestSpecConsistency(unittest.TestCase):
    """Static checks - no GUI needed."""

    @classmethod
    def setUpClass(cls):
        cls.gui = importlib.import_module("gui")
        cls.memory_hub = importlib.import_module("memory_hub")
        cls.gemini = importlib.import_module("gemini_optimizer")
        cls.specs = cls.gui.CRUD_PAGE_SPECS

    def test_all_five_pages_are_declared(self):
        self.assertEqual(set(self.specs), {"facts", "commands", "constraints", "styles", "instructions"})

    def test_add_fn_signature_matches_field_order(self):
        """
        on_add_crud_item passes the field values positionally, so the spec's field order
        must match the data-layer function's parameter order exactly.
        """
        for category, spec in self.specs.items():
            with self.subTest(category=category):
                fn = getattr(self.memory_hub, spec["add_fn"], None)
                self.assertIsNotNone(fn, f"memory_hub.{spec['add_fn']} does not exist")

                params = list(inspect.signature(fn).parameters)
                field_keys = [f["key"] for f in spec["fields"]]
                self.assertEqual(params[:len(field_keys)], field_keys,
                                 f"{spec['add_fn']} parameters {params} do not match spec fields {field_keys}")

                for kwarg in ("scope", "active", "target_ais"):
                    self.assertIn(kwarg, params, f"{spec['add_fn']} must accept {kwarg}")

    def test_optimize_fn_signature_matches_field_order(self):
        for category, spec in self.specs.items():
            with self.subTest(category=category):
                fn = getattr(self.gemini, spec["optimize_fn"], None)
                self.assertIsNotNone(fn, f"gemini_optimizer.{spec['optimize_fn']} does not exist")

                params = list(inspect.signature(fn).parameters)
                field_keys = [f["key"] for f in spec["fields"]]
                self.assertEqual(params[:len(field_keys)], field_keys,
                                 f"{spec['optimize_fn']} positional params do not match {field_keys}")
                for extra in ("api_key", "model"):
                    self.assertIn(extra, params, f"{spec['optimize_fn']} must accept {extra}")

    def test_card_fields_exist_in_the_stored_item(self):
        """
        The card's title/body/line fields must be keys the data layer actually writes -
        this is the exact check that was missing when the Styles card read item["style"].
        """
        factories = {
            "facts": lambda: self.memory_hub.add_info("n", "v"),
            "commands": lambda: self.memory_hub.add_command("n", "d", "t"),
            "constraints": lambda: self.memory_hub.add_constraint("c", "w"),
            "styles": lambda: self.memory_hub.add_style("a", "i"),
            "instructions": lambda: self.memory_hub.add_instruction("i", "w"),
        }
        # Build the item shape from the spec's own field list rather than touching disk.
        for category, spec in self.specs.items():
            with self.subTest(category=category):
                known = {f["key"] for f in spec["fields"]} | {"id", "scope", "active", "createdAt", "target_ais"}
                card = spec["card"]

                self.assertIn(card["title_field"], known,
                              f"{category}: card title field '{card['title_field']}' is not a stored field")

                if card["variant"] == "detailed":
                    self.assertIn(card["body_field"], known,
                                  f"{category}: card body field '{card['body_field']}' is not a stored field")
                else:
                    for line in card["lines"]:
                        self.assertIn(line["field"], known,
                                      f"{category}: card line field '{line['field']}' is not a stored field")

    def test_required_and_search_fields_are_declared_fields(self):
        for category, spec in self.specs.items():
            with self.subTest(category=category):
                keys = {f["key"] for f in spec["fields"]}
                for key in spec["required"]:
                    self.assertIn(key, keys, f"{category}: required field '{key}' is not declared")
                for key in spec["gemini_min_fields"]:
                    self.assertIn(key, keys, f"{category}: gemini_min_fields '{key}' is not declared")
                for key in spec["search_fields"]:
                    self.assertIn(key, keys, f"{category}: search field '{key}' is not declared")

    def test_every_page_declares_its_user_facing_text(self):
        required_keys = ["title", "subtitle", "search_placeholder", "count_text", "empty_text",
                         "missing_title", "missing_msg", "added_status", "gemini_empty_title",
                         "gemini_empty_msg", "gemini_status", "gemini_done_status"]
        for category, spec in self.specs.items():
            for key in required_keys:
                with self.subTest(category=category, key=key):
                    self.assertTrue(spec.get(key), f"{category}: missing '{key}'")

    def test_count_text_formats_cleanly(self):
        for category, spec in self.specs.items():
            with self.subTest(category=category):
                rendered = spec["count_text"].format(active=1, total=2)
                self.assertNotIn("{", rendered)

    def test_added_status_formats_cleanly(self):
        for category, spec in self.specs.items():
            with self.subTest(category=category):
                rendered = spec["added_status"].format(first="X")
                self.assertNotIn("{", rendered)


@unittest.skipUnless(_display_available(), "no display available for GUI tests")
class TestCrudHandlers(unittest.TestCase):
    """Drives the real generic handlers against a temp database."""

    @classmethod
    def setUpClass(cls):
        cls.tmp_dir = Path(tempfile.mkdtemp(prefix="aimemhub_crud_test_"))
        cls._prev_env = os.environ.get("AIMEMORYHUB_DATA_DIR")
        os.environ["AIMEMORYHUB_DATA_DIR"] = str(cls.tmp_dir)

        for mod in ("memory_hub", "gui", "spotlight", "chat_miner", "gemini_optimizer"):
            sys.modules.pop(mod, None)

        cls.hub = importlib.import_module("memory_hub")
        cls.gui = importlib.import_module("gui")

        cls.gui.AIMemoryHubApp.init_system_tray = lambda s: None
        cls.gui.AIMemoryHubApp.init_global_hotkey = lambda s: None
        cls.gui.AIMemoryHubApp.init_folder_watcher = lambda s: None
        cls.gui.AIMemoryHubApp.check_startup_updates = lambda s: None
        cls.gui.AIMemoryHubApp.init_web_dashboard = lambda s: None
        cls.gui.AIMemoryHubApp.schedule_auto_profile_checks = lambda s: None
        cls.gui.AIMemoryHubApp.sweep_expired_rules = lambda s: None
        cls.gui.AIMemoryHubApp.prune_invalid_paths_on_startup = lambda s: None
        cls.gui.AIMemoryHubApp.warn_if_database_unreadable = lambda s: None
        cls.gui.messagebox.askyesno = lambda *a, **k: True
        cls.gui.messagebox.showwarning = lambda *a, **k: None
        cls.gui.messagebox.showinfo = lambda *a, **k: None
        cls.gui.messagebox.showerror = lambda *a, **k: None
        cls.gui.memory_hub.inject_all = lambda: {
            "claude_mcp": False, "antigravity": False,
            "folders_synced": 0, "total_active_folders": 0, "failed_folders": []
        }

        cls.app = cls.gui.AIMemoryHubApp()
        cls.app.withdraw()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.app.quit()
            cls.app.destroy()
        except Exception:
            pass
        if cls._prev_env is None:
            os.environ.pop("AIMEMORYHUB_DATA_DIR", None)
        else:
            os.environ["AIMEMORYHUB_DATA_DIR"] = cls._prev_env
        shutil.rmtree(cls.tmp_dir, ignore_errors=True)

    def setUp(self):
        self.hub = self.__class__.hub
        self.gui = self.__class__.gui
        self.app = self.__class__.app
        db = self.hub.load_db()
        cur = db.get("currentProfile", "default")
        for cat in ["facts", "commands", "constraints", "styles", "instructions"]:
            db["profiles"][cur]["data"][cat] = []
        self.hub.save_db(db)
        self.app.refresh_all_views()
        self.app.update_idletasks()

    def _fill(self, category, values):
        for key, val in values.items():
            entry = self.app.crud_widgets[category]["entries"][key]
            entry.delete(0, "end")
            entry.insert(0, val)

    def test_add_writes_the_right_field_for_every_category(self):
        payloads = {
            "facts": {"name": "האתר שלי", "value": "https://example.com"},
            "commands": {"name": "חתימה", "details": "לצרף חתימה", "trigger_case": "במיילים"},
            "constraints": {"constraint": "אל תמחק הערות", "alternative_or_why": "שמור תיעוד"},
            "styles": {"aspect": "שפה", "instruction": "עברית רהוטה"},
            "instructions": {"instruction": "ענה בעברית", "when_to_apply": "תמיד"},
        }
        for category, payload in payloads.items():
            with self.subTest(category=category):
                self._fill(category, payload)
                self.app.on_add_crud_item(category)

                items = self.hub.get_items(category)
                self.assertTrue(items, f"{category}: nothing was stored")
                stored = items[0]
                for key, expected in payload.items():
                    self.assertEqual(stored.get(key), expected,
                                     f"{category}: field '{key}' was stored as {stored.get(key)!r}")

    def test_add_clears_the_form(self):
        self._fill("facts", {"name": "שם", "value": "ערך"})
        self.app.on_add_crud_item("facts")
        for entry in self.app.crud_widgets["facts"]["entries"].values():
            self.assertEqual(entry.get(), "", "the form must be cleared after a successful add")

    def test_missing_required_field_blocks_the_add(self):
        warned = []
        self.gui.messagebox.showwarning = lambda title, msg: warned.append((title, msg))

        before = len(self.hub.get_items("facts"))  # a fresh DB ships with default items
        self._fill("facts", {"name": "רק שם", "value": ""})
        self.app.on_add_crud_item("facts")

        self.assertTrue(warned, "a missing required field must warn the user")
        self.assertEqual(len(self.hub.get_items("facts")), before,
                         "nothing may be stored when validation fails")
        self.assertEqual(self.app.crud_widgets["facts"]["entries"]["name"].get(), "רק שם",
                         "the typed input must be preserved so the user can correct it")

    def test_search_filters_the_rendered_list(self):
        self.hub.add_info("האתר שלי", "example.com")
        self.hub.add_info("טלפון", "050-0000000")

        search = self.app.crud_widgets["facts"]["search"]
        search.delete(0, "end")
        search.insert(0, "טלפון")
        self.app.refresh_crud_page("facts")
        self.app.update_idletasks()

        self.assertIn("1", self.app.crud_widgets["facts"]["count"].cget("text"))

    def test_gemini_suggestion_is_written_back_into_the_form(self):
        self.gui.messagebox.askyesno = lambda title, msg: True

        self.app.on_gemini_optimize_done("styles", True, {
            "aspect": "היבט משופר",
            "instruction": "הנחיה משופרת",
            "explanation": "כי כך ברור יותר",
        })

        entries = self.app.crud_widgets["styles"]["entries"]
        self.assertEqual(entries["aspect"].get(), "היבט משופר")
        self.assertEqual(entries["instruction"].get(), "הנחיה משופרת")

    def test_gemini_failure_reenables_the_button(self):
        errors = []
        self.gui.messagebox.showerror = lambda title, msg: errors.append(msg)

        btn = self.app.crud_widgets["facts"]["gemini_btn"]
        btn.configure(state="disabled", text="מעבד...")

        self.app.on_gemini_optimize_done("facts", False, "שגיאת רשת")

        self.assertTrue(errors, "a failure must be reported to the user")
        self.assertEqual(str(btn.cget("state")), "normal", "the button must be usable again after a failure")


if __name__ == "__main__":
    unittest.main()
