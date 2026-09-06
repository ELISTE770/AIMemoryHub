# -*- coding: utf-8 -*-
"""
Shared test helpers.

The suite is written against the standard library's unittest so it runs on a plain
Python install with no extra packages (`python -m unittest discover -s tests`).
pytest, if installed, discovers and runs these TestCases natively as well.

Every test runs against an isolated temporary data directory: memory_hub resolves
MEMORY_FILE at import time, so AIMEMORYHUB_DATA_DIR must be set BEFORE the module is
imported - otherwise the tests would read and overwrite the real memory.json.
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


class IsolatedHubTestCase(unittest.TestCase):
    """Base class giving each test a fresh memory_hub bound to a temp database."""

    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="aimemhub_test_"))
        self._prev_env = os.environ.get("AIMEMORYHUB_DATA_DIR")
        os.environ["AIMEMORYHUB_DATA_DIR"] = str(self.tmp_dir)

        sys.modules.pop("memory_hub", None)
        self.hub = importlib.import_module("memory_hub")

        self.assertEqual(Path(self.hub.DATA_DIR), self.tmp_dir,
                         "memory_hub must use the temp data dir, never the real database")

        # A fresh database is seeded from auto_discover_project_paths(), i.e. the developer's
        # REAL project folders. Clear them before anything can write rule files into them.
        db = self.hub.load_db()
        db["targetPaths"] = []
        db["settings"]["injectClaudeMcp"] = False
        db["settings"]["injectAntigravityKnowledge"] = False
        db["settings"]["injectGlobalTargets"] = True
        self.hub.save_db(db)

        # Belt and braces: also stub the fan-out entry point by default.
        self._real_inject_all = self.hub.inject_all
        self.hub.inject_all = lambda: {
            "claude_mcp": False, "antigravity": False,
            "folders_synced": 0, "total_active_folders": 0, "failed_folders": [],
            "global_written": [], "global_failed": []
        }

    def use_real_inject_all(self):
        """
        Restores the real inject_all for a test that needs it. Safe only because setUp
        emptied targetPaths and disabled the Claude/Antigravity system-wide injections.
        """
        self.hub.inject_all = self._real_inject_all
        return self._real_inject_all

    def tearDown(self):
        self.hub.inject_all = self._real_inject_all
        sys.modules.pop("memory_hub", None)

        if self._prev_env is None:
            os.environ.pop("AIMEMORYHUB_DATA_DIR", None)
        else:
            os.environ["AIMEMORYHUB_DATA_DIR"] = self._prev_env

        shutil.rmtree(self.tmp_dir, ignore_errors=True)
