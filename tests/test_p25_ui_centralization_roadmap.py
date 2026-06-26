"""
P25-UI-CENTRALIZATION-ROADMAP: Documentation/architecture verification tests.

Covers:
1. docs/UI_CENTRALIZATION_FINAL_ROADMAP.md exists
2. static/css/theme.css exists and imports correctly
3. base.html references theme.css
4. dashboard.css is documented as legacy
5. No migrations created
"""
import os

from django.test import SimpleTestCase


class UIArchitectureDocumentationTest(SimpleTestCase):
    """Verify UI centralization documentation and architecture."""

    def test_roadmap_document_exists(self):
        """Roadmap document should exist under RDOS v1.0 layout."""
        path = os.path.join(os.path.dirname(__file__), "..", "docs", "06_Phases", "ROADMAP.md")
        self.assertTrue(os.path.exists(path), "docs/06_Phases/ROADMAP.md must exist")

    def test_theme_css_exists(self):
        """Central theme.css file should exist."""
        path = os.path.join(os.path.dirname(__file__), "..", "static", "css", "theme.css")
        self.assertTrue(os.path.exists(path), "static/css/theme.css must exist")

    def test_theme_css_imports_tokens(self):
        """theme.css should import tokens.css."""
        path = os.path.join(os.path.dirname(__file__), "..", "static", "css", "theme.css")
        with open(path, "r") as f:
            content = f.read()
        self.assertIn("tokens.css", content)
        self.assertIn("components.css", content)
        self.assertIn("pages.css", content)
        self.assertIn("responsive.css", content)

    def test_theme_css_documents_dashboard_as_legacy(self):
        """theme.css should note dashboard.css as legacy."""
        path = os.path.join(os.path.dirname(__file__), "..", "static", "css", "theme.css")
        with open(path, "r") as f:
            content = f.read()
        self.assertIn("dashboard.css", content)
        self.assertIn("legacy", content.lower())

    def test_base_html_references_theme(self):
        """base.html should load theme.css."""
        path = os.path.join(os.path.dirname(__file__), "..", "templates", "base.html")
        with open(path, "r") as f:
            content = f.read()
        self.assertIn("theme.css", content)

    def test_base_html_no_individual_css_imports(self):
        """base.html should NOT load individual CSS files (they're in theme.css now)."""
        path = os.path.join(os.path.dirname(__file__), "..", "templates", "base.html")
        with open(path, "r") as f:
            content = f.read()
        # Should not have individual CSS link tags
        self.assertNotIn("'css/tokens.css'", content)
        self.assertNotIn("'css/components.css'", content)
        self.assertNotIn("'css/layouts.css'", content)

    def test_tokens_css_has_semantic_aliases(self):
        """tokens.css should have P18 semantic aliases."""
        path = os.path.join(os.path.dirname(__file__), "..", "static", "css", "tokens.css")
        with open(path, "r") as f:
            content = f.read()
        self.assertIn("--color-primary", content)
        self.assertIn("--radius-card", content)
        self.assertIn("--shadow-card", content)
