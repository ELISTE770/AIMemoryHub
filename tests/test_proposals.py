# -*- coding: utf-8 -*-
"""
Tests for the approval queue that stands between an AI and the user's memory.

The owner's rule is "the AI proposes, I approve". These tests are what keeps that true:
they assert the MCP `remember` tool cannot write a directive, that approval is what writes
it, and that an approved AI item never outranks the owner's own rules.

Run with:  python -m unittest discover -s tests
"""

import importlib
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # allow "python -m unittest tests.x"

from conftest import IsolatedHubTestCase


class TestProposalQueue(IsolatedHubTestCase):

    def _propose(self, text="האתר שלי הוא https://example.com"):
        ok, parsed, conflicts, msg = self.hub.add_conversational_memory(text, auto_save=False)
        self.assertTrue(ok, msg)
        return self.hub.add_proposal(parsed, origin="mcp", raw_text=text, conflicts=conflicts)

    def test_proposing_does_not_touch_memory(self):
        before = {c: len(self.hub.get_items(c)) for c in
                  ["facts", "commands", "constraints", "styles", "instructions"]}

        prop = self._propose()

        self.assertEqual(prop["status"], "pending")
        after = {c: len(self.hub.get_items(c)) for c in before}
        self.assertEqual(after, before, "a proposal must not add anything to memory")

    def test_pending_count_and_listing(self):
        self.assertEqual(self.hub.count_pending_proposals(), 0)
        self._propose()
        self._propose("אל תשתמש באימוג'ים")
        self.assertEqual(self.hub.count_pending_proposals(), 2)
        self.assertEqual(len(self.hub.get_proposals("pending")), 2)

    def test_approval_is_what_writes_the_item(self):
        prop = self._propose("אל תמחק הערות קוד קיימות")
        category = prop["category"]
        before = len(self.hub.get_items(category))

        ok, item = self.hub.approve_proposal(prop["id"])
        self.assertTrue(ok, item)

        self.assertEqual(len(self.hub.get_items(category)), before + 1)
        self.assertEqual(self.hub.count_pending_proposals(), 0)
        self.assertEqual(self.hub.get_proposals("approved")[0]["id"], prop["id"])

    def test_approved_ai_item_does_not_outrank_the_owners_rules(self):
        """
        Injection order follows list order, so an AI item inserted at the top would take
        priority over the owner's own directives. It must be appended, never prepended.
        """
        mine = self.hub.add_info("שלי", "ערך שלי")
        prop = self._propose("האתר שלי הוא https://example.com")
        self.hub.approve_proposal(prop["id"])

        facts = self.hub.get_items("facts")
        ids = [f["id"] for f in facts]
        self.assertLess(ids.index(mine["id"]), len(ids) - 1,
                        "the owner's item must not be last-resort ordered behind the AI's")
        self.assertEqual(facts[-1].get("origin"), "mcp",
                         "the approved AI item must be appended at the end")

    def test_rejection_leaves_memory_untouched(self):
        prop = self._propose()
        category = prop["category"]
        before = len(self.hub.get_items(category))

        ok, msg = self.hub.reject_proposal(prop["id"])
        self.assertTrue(ok, msg)

        self.assertEqual(len(self.hub.get_items(category)), before)
        self.assertEqual(self.hub.count_pending_proposals(), 0)
        self.assertEqual(self.hub.get_proposals("rejected")[0]["id"], prop["id"])

    def test_a_proposal_cannot_be_approved_twice(self):
        prop = self._propose()
        self.hub.approve_proposal(prop["id"])
        ok, msg = self.hub.approve_proposal(prop["id"])
        self.assertFalse(ok)

    def test_unknown_proposal_id_is_reported(self):
        ok, msg = self.hub.approve_proposal("prop_does_not_exist")
        self.assertFalse(ok)
        ok, msg = self.hub.reject_proposal("prop_does_not_exist")
        self.assertFalse(ok)

    def test_clearing_resolved_keeps_pending(self):
        keep = self._propose("אל תשתמש באימוג'ים")
        drop = self._propose("האתר שלי הוא https://example.com")
        self.hub.reject_proposal(drop["id"])

        removed = self.hub.clear_resolved_proposals()
        self.assertEqual(removed, 1)
        remaining = [p["id"] for p in self.hub.get_proposals(None)]
        self.assertEqual(remaining, [keep["id"]])


class TestMcpServerCannotWrite(IsolatedHubTestCase):
    """Drives the actual MCP tool handlers, the surface an AI client reaches."""

    def setUp(self):
        super().setUp()
        sys.modules.pop("mcp_server", None)
        self.mcp = importlib.import_module("mcp_server")
        # The module swaps sys.stdout at import to protect the protocol channel.
        self.addCleanup(setattr, sys, "stdout", self.mcp._PROTOCOL_OUT)

    def tearDown(self):
        sys.modules.pop("mcp_server", None)
        super().tearDown()

    def test_remember_queues_instead_of_saving(self):
        before = len(self.hub.get_items("facts"))

        res = self.mcp.handle_tool_call("remember", {"text": "האתר שלי הוא https://example.com"})

        self.assertTrue(res["success"])
        self.assertEqual(res["status"], "pending_approval")
        self.assertIn("proposal_id", res)
        self.assertEqual(len(self.hub.get_items("facts")), before,
                         "the MCP tool must not write a directive into memory")
        self.assertEqual(self.hub.count_pending_proposals(), 1)

    def test_remember_rejects_empty_and_oversized_text(self):
        self.assertFalse(self.mcp.handle_tool_call("remember", {"text": "   "})["success"])
        self.assertFalse(self.mcp.handle_tool_call("remember", {"text": "x" * 2001})["success"])
        self.assertEqual(self.hub.count_pending_proposals(), 0)

    def test_switch_mode_is_blocked_by_default(self):
        before = self.hub.get_current_profile_id()

        res = self.mcp.handle_tool_call("switch_mode", {"mode_name": "code"})

        self.assertFalse(res["success"])
        self.assertEqual(res["status"], "not_allowed")
        self.assertEqual(self.hub.get_current_profile_id(), before,
                         "an AI must not be able to switch the active profile by default")

    def test_switch_mode_works_once_the_owner_enables_it(self):
        db = self.hub.load_db()
        db["settings"]["allowMcpModeSwitch"] = True
        self.hub.save_db(db)

        res = self.mcp.handle_tool_call("switch_mode", {"mode_name": "code"})

        self.assertTrue(res["success"], res)
        self.assertEqual(self.hub.get_current_profile_id(), "code")

    def test_unknown_category_is_an_explicit_error(self):
        res = self.mcp.handle_tool_call("get_active_memory", {"category": "not_a_category"})
        self.assertIn("error", res)
        self.assertIn("valid_categories", res)

    def test_protocol_channel_is_kept_separate_from_prints(self):
        """A stray print() on stdout would corrupt the JSON-RPC stream."""
        self.assertIsNot(sys.stdout, self.mcp._PROTOCOL_OUT,
                         "module-level stdout must be redirected away from the protocol channel")


if __name__ == "__main__":
    unittest.main()
