import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
import memory_hub


class TestSyncScopeMode(unittest.TestCase):
    def setUp(self):
        self.tmpdir = TemporaryDirectory()
        self.db = memory_hub.get_default_database()
        self.db["settings"]["syncScopeMode"] = "macro"

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_default_scope_mode_is_macro(self):
        default_db = memory_hub.get_default_database()
        self.assertEqual(default_db.get("settings", {}).get("syncScopeMode"), "macro")

    def test_macro_mode_skips_project_folders(self):
        project_dir = Path(self.tmpdir.name) / "test_proj"
        project_dir.mkdir(parents=True, exist_ok=True)
        self.db["targetPaths"] = [{"path": str(project_dir), "name": "test_proj", "active": True}]
        self.db["settings"]["syncScopeMode"] = "macro"
        self.db["settings"]["injectGlobalTargets"] = False  # Keep test isolated
        self.db["settings"]["injectClaudeMcp"] = False
        self.db["settings"]["injectAntigravityKnowledge"] = False

        # Save to memory
        memory_hub.save_db(self.db)
        res = memory_hub.inject_all()

        self.assertEqual(res["sync_mode"], "macro")
        self.assertEqual(res["folders_synced"], 0)
        # Verify no GEMINI.md or CLAUDE.md was created in the project folder
        self.assertFalse((project_dir / "GEMINI.md").exists())
        self.assertFalse((project_dir / "CLAUDE.md").exists())

    def test_micro_mode_injects_project_folders_only(self):
        project_dir = Path(self.tmpdir.name) / "test_micro_proj"
        project_dir.mkdir(parents=True, exist_ok=True)
        self.db["targetPaths"] = [{"path": str(project_dir), "name": "test_micro_proj", "active": True}]
        self.db["settings"]["syncScopeMode"] = "micro"

        memory_hub.save_db(self.db)
        res = memory_hub.inject_all()

        self.assertEqual(res["sync_mode"], "micro")
        self.assertEqual(res["folders_synced"], 1)
        self.assertEqual(res["global_written"], [])
        self.assertTrue((project_dir / "GEMINI.md").exists() or (project_dir / "CLAUDE.md").exists())

    def test_clean_all_project_folders(self):
        project_dir = Path(self.tmpdir.name) / "test_clean_proj"
        project_dir.mkdir(parents=True, exist_ok=True)
        # Inject rules first
        memory_hub.inject_rules_into_folder(str(project_dir))
        self.assertTrue((project_dir / "GEMINI.md").exists())

        self.db["targetPaths"] = [{"path": str(project_dir), "name": "test_clean_proj", "active": True}]
        clean_res = memory_hub.clean_all_project_folders(db=self.db)

        self.assertGreaterEqual(clean_res["cleaned_count"], 1)
        # Since GEMINI.md only had the injected block, it should be deleted cleanly
        self.assertFalse((project_dir / "GEMINI.md").exists())


if __name__ == "__main__":
    unittest.main()
