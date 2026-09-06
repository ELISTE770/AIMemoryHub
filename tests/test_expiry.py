# -*- coding: utf-8 -*-
"""
Tests for rule expiry ("כללים עם תאריך תפוגה מפורש").

An expired rule must disappear from every generated rule file while remaining visible in
the app, and a malformed date must never silently drop a directive.

Run with:  python -m unittest discover -s tests
"""

import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # allow "python -m unittest tests.x"

from conftest import IsolatedHubTestCase


def iso_in(days):
    return (datetime.now() + timedelta(days=days)).isoformat()


class TestExpiryPredicate(IsolatedHubTestCase):

    def test_no_expiry_never_expires(self):
        self.assertFalse(self.hub.item_is_expired({}))
        self.assertFalse(self.hub.item_is_expired({"expiresAt": None}))
        self.assertFalse(self.hub.item_is_expired({"expiresAt": ""}))

    def test_future_date_is_live_past_date_is_expired(self):
        self.assertFalse(self.hub.item_is_expired({"expiresAt": iso_in(1)}))
        self.assertTrue(self.hub.item_is_expired({"expiresAt": iso_in(-1)}))

    def test_a_malformed_date_fails_open(self):
        """A bad value must not remove a directive from every project file."""
        self.assertFalse(self.hub.item_is_expired({"expiresAt": "לא תאריך"}))
        self.assertFalse(self.hub.item_is_expired({"expiresAt": 12345}))


class TestExpiryStorage(IsolatedHubTestCase):

    def test_every_category_accepts_an_expiry(self):
        cases = [
            ("facts", lambda d: self.hub.add_info("n", "v", expires_at=d)),
            ("commands", lambda d: self.hub.add_command("n", "det", "t", expires_at=d)),
            ("constraints", lambda d: self.hub.add_constraint("c", "w", expires_at=d)),
            ("styles", lambda d: self.hub.add_style("a", "i", expires_at=d)),
            ("instructions", lambda d: self.hub.add_instruction("i", "w", expires_at=d)),
        ]
        when = iso_in(30)
        for category, factory in cases:
            with self.subTest(category=category):
                item = factory(when)
                self.assertEqual(item.get("expiresAt"), when)

    def test_items_without_an_expiry_get_the_key_anyway(self):
        item = self.hub.add_info("שם", "ערך")
        self.assertIn("expiresAt", item)
        self.assertIsNone(item["expiresAt"])


class TestExpiryFiltersInjection(IsolatedHubTestCase):

    def test_expired_rule_is_dropped_from_the_generated_block(self):
        self.hub.add_info("כלל חי", "נשאר", expires_at=iso_in(30))
        self.hub.add_info("כלל שפג", "נעלם", expires_at=iso_in(-1))

        md = self.hub.generate_prompt_markdown(target_folder_path=None)

        self.assertIn("נשאר", md)
        self.assertNotIn("נעלם", md, "an expired rule must not reach any AI")

    def test_expired_rule_still_exists_in_the_app(self):
        expired = self.hub.add_info("כלל שפג", "ערך", expires_at=iso_in(-1))
        ids = [f["id"] for f in self.hub.get_items("facts")]
        self.assertIn(expired["id"], ids,
                      "expiry hides a rule from the AI - it must not delete the user's data")

    def test_expiry_applies_across_every_category(self):
        self.hub.add_constraint("איסור שפג", "חלופה", expires_at=iso_in(-1))
        self.hub.add_style("סגנון שפג", "הנחיה", expires_at=iso_in(-1))
        self.hub.add_instruction("הוראה שפגה", "מתי", expires_at=iso_in(-1))
        self.hub.add_command("פקודה שפגה", "פירוט", "מקרה", expires_at=iso_in(-1))

        md = self.hub.generate_prompt_markdown(target_folder_path=None)

        for text in ["איסור שפג", "סגנון שפג", "הוראה שפגה", "פקודה שפגה"]:
            self.assertNotIn(text, md)

    def test_item_matches_target_is_the_single_gate(self):
        live = {"expiresAt": iso_in(5), "scope": "global"}
        dead = {"expiresAt": iso_in(-5), "scope": "global"}
        self.assertTrue(self.hub.item_matches_target(live))
        self.assertFalse(self.hub.item_matches_target(dead))


class TestExpirySweep(IsolatedHubTestCase):

    def test_sweep_finds_expired_items_across_profiles(self):
        self.hub.add_info("פג", "ערך", expires_at=iso_in(-1))
        self.hub.add_info("חי", "ערך", expires_at=iso_in(10))

        expired = self.hub.get_expired_items()

        names = [e["item"].get("name") for e in expired]
        self.assertIn("פג", names)
        self.assertNotIn("חי", names)

    def test_sweep_reinjects_only_when_something_expired(self):
        calls = []
        self.hub.inject_all = lambda: calls.append(1)

        self.hub.sweep_expired_items()
        self.assertEqual(calls, [], "nothing expired - no need to rewrite every project")

        self.hub.add_info("פג", "ערך", expires_at=iso_in(-1))
        calls.clear()  # adding an item syncs on its own; count only the sweep's call
        self.hub.sweep_expired_items()
        self.assertEqual(len(calls), 1, "an expired rule must trigger a re-sync")


if __name__ == "__main__":
    unittest.main()
