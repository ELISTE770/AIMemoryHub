# -*- coding: utf-8 -*-
"""
Tests for automatic profile switching.

Three strategies, each independently switchable:
  schedule - the app switches by time ("בשעות העבודה תחשוב עסקי")
  folder   - the app switches by the project folder in use
  keywords - the AI switches itself from the trigger words written into the rules block
             ("מה המייל העסקי שלי" -> business); the app never sees the conversation,
             so these tests assert the keywords actually reach the generated file.

Run with:  python -m unittest discover -s tests
"""

import sys
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # allow "python -m unittest tests.x"

from conftest import IsolatedHubTestCase

MONDAY_10AM = datetime(2026, 9, 7, 10, 0)    # weekday() == 0
MONDAY_11PM = datetime(2026, 9, 7, 23, 0)
SATURDAY_10AM = datetime(2026, 9, 12, 10, 0)  # weekday() == 5


class TestSchedule(IsolatedHubTestCase):

    def test_schedule_defaults_to_off(self):
        sched = self.hub.get_profile_schedule("business")
        self.assertFalse(sched["enabled"])
        self.assertEqual(self.hub.resolve_scheduled_profile(MONDAY_10AM), None)

    def test_profile_matches_inside_its_window_only(self):
        self.hub.set_profile_schedule("business", enabled=True, start="09:00", end="18:00",
                                      days=[0, 1, 2, 3, 6])

        self.assertTrue(self.hub.profile_matches_now("business", MONDAY_10AM))
        self.assertFalse(self.hub.profile_matches_now("business", MONDAY_11PM))

    def test_days_are_respected(self):
        self.hub.set_profile_schedule("business", enabled=True, start="09:00", end="18:00",
                                      days=[0])  # Monday only
        self.assertTrue(self.hub.profile_matches_now("business", MONDAY_10AM))
        self.assertFalse(self.hub.profile_matches_now("business", SATURDAY_10AM))

    def test_a_window_may_cross_midnight(self):
        self.hub.set_profile_schedule("code", enabled=True, start="22:00", end="04:00", days=[])
        self.assertTrue(self.hub.profile_matches_now("code", MONDAY_11PM))
        self.assertFalse(self.hub.profile_matches_now("code", MONDAY_10AM))

    def test_a_malformed_time_does_not_crash(self):
        self.hub.set_profile_schedule("business", enabled=True, start="לא שעה", end="18:00", days=[])
        self.assertIsInstance(self.hub.profile_matches_now("business", MONDAY_10AM), bool)


class TestFolderStrategy(IsolatedHubTestCase):

    def test_folder_pattern_selects_the_profile(self):
        self.hub.set_profile_folder_patterns("business", "clients, work")

        self.assertEqual(self.hub.resolve_profile_for_folder(r"C:\dev\clients\acme"), "business")
        self.assertEqual(self.hub.resolve_profile_for_folder(r"C:\dev\work"), "business")
        self.assertIsNone(self.hub.resolve_profile_for_folder(r"C:\dev\hobby"))

    def test_patterns_accept_a_comma_string_or_a_list(self):
        ok, patterns = self.hub.set_profile_folder_patterns("code", ["src", "lib"])
        self.assertTrue(ok)
        self.assertEqual(patterns, ["src", "lib"])

    def test_no_folder_means_no_match(self):
        self.assertIsNone(self.hub.resolve_profile_for_folder(None))
        self.assertIsNone(self.hub.resolve_profile_for_folder(""))


class TestApplyAutoProfile(IsolatedHubTestCase):

    def test_nothing_happens_while_auto_switching_is_off(self):
        self.hub.set_profile_schedule("business", enabled=True, start="00:00", end="23:59", days=[])
        before = self.hub.get_current_profile_id()

        changed, pid, _ = self.hub.apply_auto_profile(MONDAY_10AM)

        self.assertFalse(changed)
        self.assertEqual(self.hub.get_current_profile_id(), before)

    def test_schedule_switches_the_active_profile(self):
        self.hub.set_auto_switch_settings(enabled=True)
        self.hub.set_profile_schedule("business", enabled=True, start="09:00", end="18:00", days=[0])

        changed, pid, reason = self.hub.apply_auto_profile(MONDAY_10AM)

        self.assertTrue(changed)
        self.assertEqual(pid, "business")
        self.assertEqual(self.hub.get_current_profile_id(), "business")
        self.assertIn("לוח", reason)

    def test_folder_wins_over_schedule(self):
        self.hub.set_auto_switch_settings(enabled=True)
        self.hub.set_profile_schedule("business", enabled=True, start="09:00", end="18:00", days=[0])
        self.hub.set_profile_folder_patterns("code", "src")

        changed, pid, reason = self.hub.apply_auto_profile(MONDAY_10AM, folder_path=r"C:\dev\src")

        self.assertTrue(changed)
        self.assertEqual(pid, "code", "the folder you are actually working in is the stronger signal")

    def test_each_strategy_can_be_disabled_on_its_own(self):
        self.hub.set_auto_switch_settings(enabled=True, useSchedule=False)
        self.hub.set_profile_schedule("business", enabled=True, start="09:00", end="18:00", days=[0])

        changed, _, _ = self.hub.apply_auto_profile(MONDAY_10AM)

        self.assertFalse(changed, "schedule switching was turned off")

    def test_no_switch_when_already_on_the_target_profile(self):
        self.hub.set_auto_switch_settings(enabled=True)
        self.hub.set_current_profile("business")
        self.hub.set_profile_schedule("business", enabled=True, start="09:00", end="18:00", days=[0])

        changed, pid, _ = self.hub.apply_auto_profile(MONDAY_10AM)

        self.assertFalse(changed)
        self.assertEqual(pid, "business")


class TestKeywordStrategyReachesTheAI(IsolatedHubTestCase):
    """The app cannot see the conversation - the keywords must reach the generated file."""

    def test_trigger_keywords_are_written_into_the_rules_block(self):
        self.hub.set_profile_triggers("business", "מייל עסקי, האתר העסקי, לקוח")
        self.hub.add_info("מייל עסקי", "biz@example.com")

        md = self.hub.generate_prompt_markdown(target_folder_path=None)

        self.assertIn("מייל עסקי", md,
                      "the AI can only switch on its own if the trigger words are in the file")

    def test_setting_triggers_accepts_a_comma_separated_string(self):
        ok, _ = self.hub.set_profile_triggers("code", "מצב קוד, דיבאג")
        self.assertTrue(ok)
        keywords, _, _ = self.hub.get_profile_triggers("code")
        self.assertEqual(keywords, ["מצב קוד", "דיבאג"])


if __name__ == "__main__":
    unittest.main()
