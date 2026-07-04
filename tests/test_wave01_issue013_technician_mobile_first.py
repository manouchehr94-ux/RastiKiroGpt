"""
EPIC-002 Wave 01, Issue 013: Technician panel must become Mobile First.

Scope note: the technician panel (templates/layouts/technician.html) was
already substantially mobile-first (sticky bottom nav, single-column-first
content, auto-fit/minmax filter grids). This wave's fix is deliberately
narrow, per "only improve responsiveness, do not redesign UX":

1. static/css/responsive.css — added `.tech-content .btn-sm { min-height: 42px; }`
   inside the existing @media (max-width: 639px) block, following the exact
   precedent already set at static/css/dashboard.css for
   `.technician-card-actions .btn` (small buttons on technician-facing pages,
   e.g. print/PDF buttons on statement/ledger pages, were below the ~44px
   recommended minimum touch target size). Scoped to `.tech-content` only,
   so desktop admin `.btn-sm` usage elsewhere is untouched.
2. static/css/dashboard.css — normalized a stray `max-width: 640px` media
   query to `max-width: 639px` to match the project's documented breakpoint
   convention used everywhere else in responsive.css (cosmetic-only, no
   functional change at that boundary).

No template restructuring was performed — this issue's fix is CSS-only.
"""
from django.test import SimpleTestCase


class TechnicianTapTargetCSSTest(SimpleTestCase):
    def test_responsive_css_has_tech_content_btn_sm_rule(self):
        with open("static/css/responsive.css", encoding="utf-8") as f:
            content = f.read()
        self.assertIn(".tech-content .btn-sm", content)
        self.assertIn("min-height: 42px;", content)

    def test_tech_content_rule_is_inside_639px_breakpoint(self):
        with open("static/css/responsive.css", encoding="utf-8") as f:
            content = f.read()
        breakpoint_start = content.index("@media (max-width: 639px)")
        rule_index = content.index(".tech-content .btn-sm")
        # The next @media block after 639px (if any) must come after our rule.
        next_media_index = content.find("@media", rule_index)
        self.assertGreater(rule_index, breakpoint_start)
        self.assertTrue(next_media_index == -1 or next_media_index > rule_index)


class BreakpointConsistencyCSSTest(SimpleTestCase):
    def test_dashboard_css_no_longer_uses_stray_640px_breakpoint(self):
        with open("static/css/dashboard.css", encoding="utf-8") as f:
            content = f.read()
        self.assertNotIn("@media (max-width: 640px)", content)
        self.assertIn("@media (max-width: 639px)", content)
