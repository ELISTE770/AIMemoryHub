# -*- coding: utf-8 -*-
"""
Tests for contradiction detection at the moment a rule is added or edited.

The owner asked to be "warned and left to decide" when a profile rule contradicts a global
one. These tests cover the cheap local gate that decides whether there is anything to warn
about - it runs on every save, so it must be both accurate enough to be useful and quiet
enough not to nag.

Run with:  python -m unittest discover -s tests
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # allow "python -m unittest tests.x"

from conftest import IsolatedHubTestCase


class TestNormalisation(IsolatedHubTestCase):

    def test_final_letters_and_niqqud_fold_together(self):
        self.assertEqual(self.hub._normalize_he("שלום"), self.hub._normalize_he("שלומ"))
        self.assertEqual(self.hub._normalize_he("עִבְרִית"), self.hub._normalize_he("עברית"))

    def test_punctuation_and_spacing_are_ignored(self):
        self.assertEqual(self.hub._normalize_he("  האתר, שלי!  "), self.hub._normalize_he("האתר שלי"))


class TestContradictionGate(IsolatedHubTestCase):

    def test_same_subject_different_value_is_a_contradiction(self):
        a = {"name": "האתר שלי", "value": "https://my-domain.example"}
        b = {"name": "האתר שלי", "value": "example.com"}
        self.assertTrue(self.hub.items_contradict(a, b, "facts"))

    def test_same_subject_same_value_is_not(self):
        a = {"name": "האתר שלי", "value": "https://my-domain.example"}
        b = {"name": "האתר שלי", "value": "https://my-domain.example"}
        self.assertFalse(self.hub.items_contradict(a, b, "facts"))

    def test_different_subjects_are_not_a_contradiction(self):
        a = {"name": "האתר שלי", "value": "x"}
        b = {"name": "הטלפון שלי", "value": "y"}
        self.assertFalse(self.hub.items_contradict(a, b, "facts"))

    def test_a_missing_side_never_fires(self):
        self.assertFalse(self.hub.items_contradict({"name": "", "value": "x"}, {"name": "א", "value": "y"}, "facts"))
        self.assertFalse(self.hub.items_contradict({"name": "א", "value": ""}, {"name": "א", "value": "y"}, "facts"))

    def test_it_works_per_category_field_pair(self):
        a = {"aspect": "שפה", "instruction": "ענה בעברית"}
        b = {"aspect": "שפה", "instruction": "ענה באנגלית"}
        self.assertTrue(self.hub.items_contradict(a, b, "styles"))


class TestProfileVersusGlobal(IsolatedHubTestCase):

    def test_a_profile_rule_contradicting_the_main_profile_is_reported(self):
        self.hub.set_current_profile("default")
        self.hub.add_style("שפה", "ענה תמיד בעברית")

        self.hub.set_current_profile("business")
        conflicts = self.hub.detect_conflicts(
            proposed_item={"aspect": "שפה", "instruction": "ענה תמיד באנגלית"},
            category="styles")

        kinds = [c["type"] for c in conflicts]
        self.assertIn("profile_vs_global", kinds,
                      "profiles are siloed, but both rules land in the same generated file")

    def test_no_conflict_when_the_rules_agree(self):
        self.hub.set_current_profile("default")
        self.hub.add_style("שפה", "ענה תמיד בעברית")

        self.hub.set_current_profile("business")
        conflicts = self.hub.detect_conflicts(
            proposed_item={"aspect": "שפה", "instruction": "ענה תמיד בעברית"},
            category="styles")

        self.assertEqual([c for c in conflicts if c["type"] == "profile_vs_global"], [])

    def test_the_main_profile_is_not_compared_against_itself(self):
        self.hub.set_current_profile("default")
        self.hub.add_info("האתר שלי", "https://my-domain.example")

        conflicts = self.hub.detect_conflicts(
            proposed_item={"name": "האתר שלי", "value": "other.com"}, category="facts")

        self.assertEqual([c for c in conflicts if c["type"] == "profile_vs_global"], [])

    def test_an_inactive_rule_does_not_trigger_a_warning(self):
        self.hub.set_current_profile("default")
        item = self.hub.add_style("שפה", "ענה תמיד בעברית")
        self.hub.toggle_item("styles", item["id"], False)

        self.hub.set_current_profile("business")
        conflicts = self.hub.detect_conflicts(
            proposed_item={"aspect": "שפה", "instruction": "ענה תמיד באנגלית"},
            category="styles")

        self.assertEqual([c for c in conflicts if c["type"] == "profile_vs_global"], [],
                         "a disabled rule reaches no AI, so it cannot contradict anything")


class TestConflictResolution(IsolatedHubTestCase):

    def test_delete_removes_from_one_profile_only(self):
        self.hub.set_current_profile("default")
        mine = self.hub.add_info("משותף", "ערך ראשי")

        # Same id planted in another profile - the old code deleted it from both.
        db = self.hub.load_db()
        db["profiles"]["business"]["data"].setdefault("facts", []).append(
            {"id": mine["id"], "name": "משותף", "value": "ערך עסקי", "active": True, "scope": "global"})
        self.hub.save_db(db)

        ok, msg = self.hub.resolve_conflict("conf_x", "delete", target_item_id=mine["id"])
        self.assertTrue(ok, msg)

        db = self.hub.load_db()
        default_ids = [f["id"] for f in db["profiles"]["default"]["data"]["facts"]]
        business_ids = [f["id"] for f in db["profiles"]["business"]["data"]["facts"]]
        self.assertNotIn(mine["id"], default_ids)
        self.assertIn(mine["id"], business_ids, "only the current profile may be touched")

    def test_keep_both_is_remembered(self):
        ok, msg = self.hub.resolve_conflict("conf_abc", "keep_both")
        self.assertTrue(ok)
        self.assertIn("conf_abc", self.hub.load_db().get("acceptedConflicts", []))

    def test_unknown_action_is_rejected(self):
        ok, _ = self.hub.resolve_conflict("conf_abc", "explode")
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()
