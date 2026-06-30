# TASK-007A DEPLOYMENT GUIDE

## ⚠️ Mandatory Pre-Deploy Check

Run:

```bash
python scripts/invoice_migration_safety_check.py

If output is NOT empty → DO NOT DEPLOY.

📦 Step 1 — Seed Invoice Counters (Required for large DBs)

Run:

python scripts/seed_invoice_counter.py

This ensures:

InvoiceCounter starts from correct max values
Prevents cold-start O(N²) behavior
📦 Step 2 — Run Migration
python manage.py migrate
📦 Step 3 — Post Deploy Verification

Check:

Invoice creation works
No duplicate invoice numbers
Ledger writes succeed
PAID invoice is immutable
🚨 Rollback Plan

If migration fails:

python manage.py migrate invoices 0003

Then fix duplicate active invoices before retry.

🧠 Notes
Migration is safe if safety script passes
Seed script is optional but recommended for production-scale DB
No downtime required if steps are followed correctly