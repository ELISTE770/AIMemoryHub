"""Tests for UI design consistency, theme contrast, and HTML/CSS balance."""
import unittest
import os
import re

class TestDesignAndTheme(unittest.TestCase):
    def setUp(self):
        self.root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.web_html = os.path.join(self.root_dir, "web", "index.html")
        self.gui_py = os.path.join(self.root_dir, "gui.py")
        self.spotlight_py = os.path.join(self.root_dir, "spotlight.py")

    def test_web_html_sections_balanced(self):
        """Verifies that all <section> tags in web/index.html have corresponding closing </section> tags."""
        with open(self.web_html, "r", encoding="utf-8") as f:
            content = f.read()

        open_sections = len(re.findall(r"<section\b", content, re.IGNORECASE))
        close_sections = len(re.findall(r"</section>", content, re.IGNORECASE))
        self.assertEqual(open_sections, close_sections, f"Mismatched <section> tags: {open_sections} open vs {close_sections} close")
        self.assertGreaterEqual(open_sections, 12, "Expected at least 12 tab sections")

    def test_web_html_responsive_and_dark_mode_rules(self):
        """Ensures modern CSS responsive and dark mode accessibility fixes are present."""
        with open(self.web_html, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn('data-theme="dark"', content)
        self.assertIn('.badge-inst', content)
        self.assertIn('@media (max-width: 768px)', content)
        self.assertIn('max-height: 85vh;', content)
        self.assertIn('unicode-bidi: plaintext', content)

    def test_spotlight_explicit_dark_styling(self):
        """Ensures Spotlight search entry has explicit dark styling preventing light mode leakage."""
        with open(self.spotlight_py, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn('fg_color="#1e293b"', content)
        self.assertIn('text_color="#f8fafc"', content)

    def test_gui_statusbar_not_accent_blue(self):
        """Ensures the Desktop GUI statusbar does not use blinding solid blue ACCENT_COLOR."""
        with open(self.gui_py, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn('self.statusbar = ctk.CTkFrame(self, height=28, corner_radius=0, fg_color=GLASS_BG_SIDEBAR', content)

if __name__ == "__main__":
    unittest.main()
