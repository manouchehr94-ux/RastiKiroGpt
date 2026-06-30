# Safe Cleanup Report

**Date:** 2026-06-28  
**Source:** Full ZIP review  
**Rule:** No direct deletion is recommended before quarantine + test pass.

---

## 1. Cleanup Philosophy

This report separates files into three groups:

1. **Safe cleanup candidates:** likely artifacts/backups; move to quarantine first.
2. **Review before delete:** may be useful but should not live permanently in root/scripts.
3. **Do not delete:** migrations, tests, templates with uncertain dynamic references, `.git` in the real repo.

---

## 2. Safe Cleanup Candidates

| File | Status | Reason |
|---|---|---|
| `db_before_invoice_payment_test.sqlite3` | Safe cleanup candidate | Backup/dev/hotfix artifact; quarantine first |
| `db_before_p6_financial_settlement.sqlite3` | Safe cleanup candidate | Backup/dev/hotfix artifact; quarantine first |
| `LOCAL_HOTFIX_DEBUG_AND_TECH_NAV_REPORT.txt` | Safe cleanup candidate | Backup/dev/hotfix artifact; quarantine first |
| `TECH_ORDERS_404_FIX_REPORT.txt` | Safe cleanup candidate | Backup/dev/hotfix artifact; quarantine first |
| `templates/accounts/change_password_required.html.bak` | Safe cleanup candidate | Backup/dev/hotfix artifact; quarantine first |
| `templates/accounts/password_reset_otp.html.bak` | Safe cleanup candidate | Backup/dev/hotfix artifact; quarantine first |
| `templates/dashboard/home.html.bak` | Safe cleanup candidate | Backup/dev/hotfix artifact; quarantine first |
| `templates/invoices/public_detail.html.bak` | Safe cleanup candidate | Backup/dev/hotfix artifact; quarantine first |
| `templates/payments/invoice_checkout.html.bak` | Safe cleanup candidate | Backup/dev/hotfix artifact; quarantine first |
| `templates/payments/result.html.bak` | Safe cleanup candidate | Backup/dev/hotfix artifact; quarantine first |
| `templates/tenants/admin_customer_detail.html.bak` | Safe cleanup candidate | Backup/dev/hotfix artifact; quarantine first |
| `templates/tenants/admin_order_create.html.bak` | Safe cleanup candidate | Backup/dev/hotfix artifact; quarantine first |
| `templates/tenants/admin_order_detail.html.bak` | Safe cleanup candidate | Backup/dev/hotfix artifact; quarantine first |
| `templates/tenants/admin_sms_credit.html.bak` | Safe cleanup candidate | Backup/dev/hotfix artifact; quarantine first |
| `templates/tenants/admin_sms_invoice_detail.html.bak` | Safe cleanup candidate | Backup/dev/hotfix artifact; quarantine first |
| `templates/tenants/merchant_profile.html.bak` | Safe cleanup candidate | Backup/dev/hotfix artifact; quarantine first |
| `templates/tenants/request_disabled.html.bak` | Safe cleanup candidate | Backup/dev/hotfix artifact; quarantine first |
| `templates/tenants/request_status.html.bak` | Safe cleanup candidate | Backup/dev/hotfix artifact; quarantine first |
| `templates/tenants/request_success.html.bak` | Safe cleanup candidate | Backup/dev/hotfix artifact; quarantine first |
| `templates/includes/settings_center.html.bak5` | Safe cleanup candidate | Backup/dev/hotfix artifact; quarantine first |
| `templates/sms/diagnostics.html.bak5` | Safe cleanup candidate | Backup/dev/hotfix artifact; quarantine first |
| `templates/tenants/admin_base_categories.html.bak5` | Safe cleanup candidate | Backup/dev/hotfix artifact; quarantine first |
| `templates/tenants/admin_branding.html.bak5` | Safe cleanup candidate | Backup/dev/hotfix artifact; quarantine first |
| `templates/tenants/admin_company_settings.html.bak5` | Safe cleanup candidate | Backup/dev/hotfix artifact; quarantine first |
| `templates/tenants/admin_invoice_edit.html.bak5` | Safe cleanup candidate | Backup/dev/hotfix artifact; quarantine first |
| `templates/tenants/admin_operator_list.html.bak5` | Safe cleanup candidate | Backup/dev/hotfix artifact; quarantine first |
| `static/css/backup/rasti_sidebar_fix.css` | Safe cleanup candidate | Backup/dev/hotfix artifact; quarantine first |
| `static/css/backup/rasti_ui_core_consistency.css` | Safe cleanup candidate | Backup/dev/hotfix artifact; quarantine first |
| `static/css/backup/rasti_ui_hotfix.css` | Safe cleanup candidate | Backup/dev/hotfix artifact; quarantine first |
| `static/css/backup/theme.css` | Safe cleanup candidate | Backup/dev/hotfix artifact; quarantine first |

---

## 3. Review Before Delete / Archive

| File | Status | Reason |
|---|---|---|
| `db.sqlite3` | Review before delete | May be useful for local dev, onboarding, or maintenance |
| `COPY_INSTRUCTIONS.md` | Review before delete | May be useful for local dev, onboarding, or maintenance |
| `MANIFEST.md` | Review before delete | May be useful for local dev, onboarding, or maintenance |
| `PROJECT_STATUS_FA.md` | Review before delete | May be useful for local dev, onboarding, or maintenance |
| `README_FAST_DEV.md` | Review before delete | May be useful for local dev, onboarding, or maintenance |
| `SMOKE_CHECKLIST_FA.md` | Review before delete | May be useful for local dev, onboarding, or maintenance |
| `START_HERE_FA.md` | Review before delete | May be useful for local dev, onboarding, or maintenance |
| `scripts/apply_admin_status_dashboard_orders_6h.py` | Review before delete | May be useful for local dev, onboarding, or maintenance |
| `scripts/find_discount_code_for_local_test.py` | Review before delete | May be useful for local dev, onboarding, or maintenance |
| `scripts/fix_filters_status_jalali_6e.py` | Review before delete | May be useful for local dev, onboarding, or maintenance |
| `scripts/fix_jalali_filter_patch6d.py` | Review before delete | May be useful for local dev, onboarding, or maintenance |
| `scripts/fix_remove_template_tags_from_py.py` | Review before delete | May be useful for local dev, onboarding, or maintenance |
| `scripts/fix_status_badge_recursion_6k.py` | Review before delete | May be useful for local dev, onboarding, or maintenance |
| `scripts/fix_status_jalali_targeted_6g.py` | Review before delete | May be useful for local dev, onboarding, or maintenance |
| `scripts/test_sms_charge_2000_and_process.py` | Review before delete | May be useful for local dev, onboarding, or maintenance |
| `scripts/test_sms_credit_empty.py` | Review before delete | May be useful for local dev, onboarding, or maintenance |
| `scripts/invoice_migration_safety_check.py` | Review before delete | May be useful for local dev, onboarding, or maintenance |
| `scripts/seed_invoice_counter.py` | Review before delete | May be useful for local dev, onboarding, or maintenance |

---

## 4. Do Not Delete

| Item | Reason |
|---|---|
| `apps/**/migrations/*.py` | They are database history. Never delete after migrations have been applied. |
| `tests/test_*.py` | Even old-looking tests protect regressions. Remove only after mapping to replacement coverage. |
| `templates/components/*`, `templates/layouts/*`, `templates/includes/*` | Many may be included dynamically or planned design-system assets. |
| `static/css/base.css`, `components.css`, `layouts.css`, `pages.css`, `tokens.css` | Imported indirectly by `theme.css`; grep may show zero direct template refs. |
| `.git/` in the real project | Required for version control. It should only be excluded from ZIP exports. |
| `.claude/` | Ignore in Git/export if desired, but do not delete if Claude Code depends on it locally. |
| `media/` | Ignored runtime user uploads; keep locally if needed, never commit. |

---

## 5. Recommended Workflow

1. Create a cleanup branch.
2. Run the quarantine script, not direct deletion.
3. Run `python manage.py check --settings=config.settings.local`.
4. Run targeted smoke tests.
5. Run the full test suite if time permits.
6. If everything passes, replace quarantine with `git rm` for tracked files.

---

## 6. PowerShell Commands After Approval

Use the generated file:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\cleanup_quarantine_2026_06_28.ps1
python manage.py check --settings=config.settings.local
python manage.py test --settings=config.settings.local
```

If tests pass and the quarantine is approved, delete the quarantine folder and commit the removals.

---

## 7. Export Hygiene

When zipping the project for review, exclude:

```text
.git/
__pycache__/
*.pyc
db.sqlite3
db_*.sqlite3
media/
staticfiles/
*.bak
*.bak5
```

Recommended archive command from project parent folder:

```powershell
Compress-Archive -Path "Rasti chekFinal 5 tir" -DestinationPath "rasti_clean_snapshot.zip" -Force
```

For a truly clean archive, use `git archive` instead:

```bash
git archive --format=zip --output=rasti_source_only.zip HEAD
```
