"""
EPIC-002 Wave 01, Issue 014: Remove native number-input spin buttons globally.

Fix: added a single global CSS rule in static/css/base.css suppressing
-webkit-inner/outer-spin-button and setting -moz-appearance: textfield on
input[type="number"]. No template changes were required since the selector
is a global type-selector, not a per-input class.
"""
from django.test import SimpleTestCase


class SpinButtonSuppressionCSSTest(SimpleTestCase):
    """Source-level regression guard: the global spin-button-removal rule must exist."""

    def test_base_css_suppresses_webkit_spin_buttons(self):
        with open("static/css/base.css", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("::-webkit-outer-spin-button", content)
        self.assertIn("::-webkit-inner-spin-button", content)
        self.assertIn("-webkit-appearance: none", content)

    def test_base_css_suppresses_firefox_spin_buttons(self):
        with open("static/css/base.css", encoding="utf-8") as f:
            content = f.read()
        self.assertIn('input[type="number"] {', content)
        self.assertIn("-moz-appearance: textfield", content)
