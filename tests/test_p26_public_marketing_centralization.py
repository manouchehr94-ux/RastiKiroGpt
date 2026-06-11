"""
P26-PUBLIC-MARKETING-PAGES-CENTRALIZATION: Tests for public page rendering.

Covers:
1. Public/marketing pages render 200
2. Pages include theme.css
3. Pages use central CSS classes
4. No sensitive admin/payment/KYC data exposed
5. No admin-only links on public pages
"""
from django.test import TestCase, override_settings


PUBLIC_URLS = [
    "/",
    "/pricing/",
    "/about/",
    "/features/",
    "/contact/",
    "/register/",
]


@override_settings(ROOT_URLCONF="config.urls")
class PublicPageRenderTest(TestCase):
    """Public/marketing pages render correctly after P26 migration."""

    def test_all_public_pages_render_200(self):
        """Each public page returns 200."""
        for url in PUBLIC_URLS:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200, f"Failed: {url}")

    def test_home_page_loads_theme_css(self):
        """Home page should load theme.css."""
        response = self.client.get("/")
        content = response.content.decode("utf-8")
        self.assertIn("theme.css", content)

    def test_pricing_uses_central_classes(self):
        """Pricing page should use central CSS classes."""
        response = self.client.get("/pricing/")
        content = response.content.decode("utf-8")
        # Accept either public-section-title or section-title as central class
        self.assertTrue(
            "public-section-title" in content or "section-title" in content,
            "Pricing page should use public-section-title or section-title"
        )
        self.assertIn("btn", content)

    def test_features_uses_central_classes(self):
        """Features page should use feature-item or feature-group-item class."""
        response = self.client.get("/features/")
        content = response.content.decode("utf-8")
        self.assertTrue(
            "feature-item" in content or "feature-group-item" in content,
            "Features page should use feature-item or feature-group-item class"
        )

    def test_no_sensitive_data_on_public_pages(self):
        """Public pages should not expose admin/KYC/payment data."""
        for url in PUBLIC_URLS:
            response = self.client.get(url)
            content = response.content.decode("utf-8")
            self.assertNotIn("shaba_number", content)
            self.assertNotIn("national_card_image", content)
            self.assertNotIn("/owner-platform/", content)
            self.assertNotIn("mark_paid", content)

    def test_no_admin_links_on_public(self):
        """Public pages should not contain admin panel links."""
        response = self.client.get("/")
        content = response.content.decode("utf-8")
        self.assertNotIn("/admin/payments/operations/", content)
        self.assertNotIn("/admin/financial-reports/", content)
