"""
Seed InvoiceCounter from existing invoice_number values.

Purpose:
- Run this BEFORE deploying TASK-007A migration / before first production traffic
  that uses InvoiceCounter.
- Prevents cold-start O(N) skip-loop for companies with existing invoices.
- Seeds each company's counter from the largest numeric suffix found in existing
  invoice_number values.

Supported invoice_number patterns:
- INV-COMPANYCODE-00001
- any value ending with digits, for backward compatibility

Usage:
    python manage.py shell < scripts/seed_invoice_counter.py

Or:
    python scripts/seed_invoice_counter.py
"""

import os
import re
import sys
from pathlib import Path

import django
from django.db import transaction


def _bootstrap_django_if_needed() -> None:
    """
    Allows this script to run both as:
        python scripts/seed_invoice_counter.py
    and:
        python manage.py shell < scripts/seed_invoice_counter.py
    """
    if "DJANGO_SETTINGS_MODULE" not in os.environ:
        # Add project root to sys.path when executed directly.
        project_root = Path(__file__).resolve().parents[1]
        sys.path.insert(0, str(project_root))
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

    if not django.apps.apps.ready:
        django.setup()


def _extract_invoice_sequence(invoice_number: str) -> int | None:
    """
    Extract the numeric sequence from the end of invoice_number.

    Examples:
        INV-ABC-00001 -> 1
        INV-ABC-100000 -> 100000
        OLD-42 -> 42
        ABC -> None
    """
    if not invoice_number:
        return None

    match = re.search(r"(\d+)$", str(invoice_number).strip())
    if not match:
        return None

    return int(match.group(1))


def seed_invoice_counters() -> int:
    _bootstrap_django_if_needed()

    from apps.invoices.models import Invoice, InvoiceCounter

    # Aggregate in Python because invoice_number is a formatted string and older
    # data may not follow exactly one SQL-friendly pattern.
    max_by_company: dict[int, int] = {}

    invoices = (
        Invoice.objects
        .exclude(invoice_number__isnull=True)
        .exclude(invoice_number="")
        .values_list("company_id", "invoice_number")
        .iterator(chunk_size=2000)
    )

    skipped = 0

    for company_id, invoice_number in invoices:
        seq = _extract_invoice_sequence(invoice_number)
        if seq is None:
            skipped += 1
            continue

        current = max_by_company.get(company_id, 0)
        if seq > current:
            max_by_company[company_id] = seq

    created = 0
    updated = 0
    unchanged = 0

    with transaction.atomic():
        for company_id, max_seq in max_by_company.items():
            counter, was_created = InvoiceCounter.objects.select_for_update().get_or_create(
                company_id=company_id,
                defaults={"last_number": max_seq},
            )

            if was_created:
                created += 1
                continue

            if counter.last_number < max_seq:
                counter.last_number = max_seq
                counter.save(update_fields=["last_number"])
                updated += 1
            else:
                unchanged += 1

    print("✅ InvoiceCounter seed completed")
    print(f"companies_seen={len(max_by_company)}")
    print(f"created={created}")
    print(f"updated={updated}")
    print(f"unchanged={unchanged}")
    print(f"skipped_unparseable_invoice_numbers={skipped}")

    return 0


if __name__ == "__main__":
    raise SystemExit(seed_invoice_counters())
