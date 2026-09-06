# -*- coding: utf-8 -*-
"""
Tests for project-path validation and pruning.

Background: in a frozen (PyInstaller) build WORKSPACE_DIR resolves to %TEMP%\\_MEIxxxxx,
so every run of the packaged .exe registered a fresh throwaway folder as a "project" and
then wrote six rule files into it on every sync. Real databases accumulated several of
these; three of them no longer existed on disk.

Run with:  python -m unittest discover -s tests
"""

import os
import tempfile
import unittest
from pathlib import Path

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))  # allow "python -m unittest tests.x"

from conftest import IsolatedHubTestCase


class TestPathValidation(IsolatedHubTestCase):

    def test_rejects_pyinstaller_extraction_dirs(self):
        temp_root = Path(tempfile.gettempdir())
        self.assertFalse(self.hub.is_valid_project_path(temp_root / "_MEI123456"))
        self.assertFalse(self.hub.is_valid_project_path(str(temp_root / "_MEI999")))

    def test_rejects_anything_under_the_system_temp_dir(self):
        self.assertFalse(self.hub.is_valid_project_path(Path(tempfile.gettempdir()) / "whatever"))

    def test_accepts_a_normal_project_folder(self):
        project = self.tmp_dir.parent / "a_normal_project_folder"
        # tmp_dir itself lives under %TEMP% in tests, so use an explicitly non-temp path.
        self.assertTrue(self.hub.is_valid_project_path(Path.home() / "Projects" / "demo"))
        self.assertFalse(self.hub.is_valid_project_path(project))  # under temp -> rejected

    def test_add_path_refuses_a_temp_directory(self):
        temp_dir = Path(tempfile.mkdtemp(prefix="_MEI"))
        try:
            ok, msg = self.hub.add_path(str(temp_dir))
            self.assertFalse(ok)
            self.assertIn("זמנית", msg)
        finally:
            temp_dir.rmdir()

    def test_auto_discover_never_returns_a_temp_path(self):
        for path in self.hub.auto_discover_project_paths():
            self.assertTrue(self.hub.is_valid_project_path(path),
                            f"auto-discovery returned an invalid project path: {path}")


class TestPathPruning(IsolatedHubTestCase):

    def test_prunes_temp_and_missing_paths_but_keeps_real_ones(self):
        real_dir = Path.home() / "AIMemoryHubTestRealFolder"
        real_dir.mkdir(exist_ok=True)
        try:
            db = self.hub.load_db()
            db["targetPaths"] = [
                {"path": str(real_dir), "name": real_dir.name, "active": True, "lastSynced": None},
                {"path": str(Path(tempfile.gettempdir()) / "_MEI203602"), "name": "_MEI203602",
                 "active": True, "lastSynced": None},
                {"path": str(Path.home() / "definitely_does_not_exist_12345"),
                 "name": "ghost", "active": True, "lastSynced": None},
            ]
            self.hub.save_db(db)

            removed = self.hub.prune_invalid_paths()

            self.assertEqual(sorted(removed), ["_MEI203602", "ghost"])
            kept = [p["name"] for p in self.hub.load_db().get("targetPaths", [])]
            self.assertEqual(kept, [real_dir.name], "a real project folder must never be pruned")
        finally:
            try:
                real_dir.rmdir()
            except OSError:
                pass

    def test_pruning_is_a_no_op_when_everything_is_valid(self):
        db = self.hub.load_db()
        db["targetPaths"] = []
        self.hub.save_db(db)

        self.assertEqual(self.hub.prune_invalid_paths(), [])


if __name__ == "__main__":
    unittest.main()
