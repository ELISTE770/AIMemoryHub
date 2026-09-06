# -*- coding: utf-8 -*-
"""
GUI smoke test: builds the full application window against a temporary database and
renders every page, then tears it down.

This is the test that catches the class of bug that took the app down before - e.g.
refresh_page_styles() reading item["style"] when style items only have aspect/instruction,
which raised KeyError during __init__ and crashed the app on launch. It needs a display
(a normal Windows desktop session) and is skipped automatically when none is available.

Run with:  python -m unittest discover -s tests
"""

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


@unittest.skipUnless(_display_available(), "no display available for GUI tests")
class TestGuiSmoke(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tmp_dir = Path(tempfile.mkdtemp(prefix="aimemhub_gui_test_"))
        cls._prev_env = os.environ.get("AIMEMORYHUB_DATA_DIR")
        os.environ["AIMEMORYHUB_DATA_DIR"] = str(cls.tmp_dir)

        for mod in ("memory_hub", "gui", "spotlight", "chat_miner", "gemini_optimizer"):
            sys.modules.pop(mod, None)

        cls.hub = importlib.import_module("memory_hub")

        # Seed one item in every category so each page renders a populated card.
        cls.hub.add_info("האתר שלי", "https://example.com")
        cls.hub.add_command("חתימה", "לצרף חתימה", "במיילים")
        cls.hub.add_constraint("אל תמחק הערות", "שמור על התיעוד")
        cls.hub.add_style("שפה וניסוח", "עברית רהוטה")
        cls.hub.add_instruction("ענה בעברית", "בכל שיחה")

        cls.gui = importlib.import_module("gui")

        # Keep the smoke test from touching the user's real machine state.
        cls.gui.AIMemoryHubApp.init_system_tray = lambda self_: None
        cls.gui.AIMemoryHubApp.init_global_hotkey = lambda self_: None
        cls.gui.AIMemoryHubApp.init_folder_watcher = lambda self_: None
        cls.gui.AIMemoryHubApp.check_startup_updates = lambda self_: None
        cls.gui.AIMemoryHubApp.init_web_dashboard = lambda self_: None
        cls.gui.AIMemoryHubApp.schedule_auto_profile_checks = lambda self_: None
        cls.gui.AIMemoryHubApp.sweep_expired_rules = lambda self_: None
        cls.gui.AIMemoryHubApp.prune_invalid_paths_on_startup = lambda self_: None
        cls.gui.AIMemoryHubApp.warn_if_database_unreadable = lambda self_: None
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
        if cls.app is not None:
            try:
                cls.app.quit()
                cls.app.destroy()
            except Exception:
                pass

        for mod in ("memory_hub", "gui", "spotlight", "chat_miner", "gemini_optimizer"):
            sys.modules.pop(mod, None)

        if cls._prev_env is None:
            os.environ.pop("AIMEMORYHUB_DATA_DIR", None)
        else:
            os.environ["AIMEMORYHUB_DATA_DIR"] = cls._prev_env

        shutil.rmtree(cls.tmp_dir, ignore_errors=True)

    def test_app_builds_and_all_pages_render(self):
        """Constructing the app runs create_*/build_page_*/refresh_all_views for real."""
        self.assertTrue(self.app.pages, "no pages were registered")

        for page_key in list(self.app.pages.keys()):
            with self.subTest(page=page_key):
                self.app.show_page(page_key)
                self.app.update_idletasks()

    def test_refresh_all_views_is_repeatable(self):
        """refresh_all_views runs on every data change - it must survive being re-run."""
        for _ in range(3):
            self.app.refresh_all_views()
            self.app.update_idletasks()

    def test_pages_render_with_an_empty_database(self):
        """The empty-state path of every page must render too (no items in any category)."""
        db = self.hub.load_db()
        cur = db.get("currentProfile", "default")
        for cat in ["facts", "commands", "constraints", "styles", "instructions", "context_files"]:
            db["profiles"][cur]["data"][cat] = []
        self.hub.save_db(db)

        self.app.refresh_all_views()
        self.app.update_idletasks()

        for page_key in list(self.app.pages.keys()):
            with self.subTest(page=page_key):
                self.app.show_page(page_key)
                self.app.update_idletasks()


if __name__ == "__main__":
    unittest.main()
