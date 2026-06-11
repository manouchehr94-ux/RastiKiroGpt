# -*- coding: utf-8 -*-
"""
Management command to fetch incoming SMS messages and match to companies.

Usage:
    python manage.py fetch_sms_inbox
    python manage.py fetch_sms_inbox --dry-run
    python manage.py fetch_sms_inbox --count 50
    python manage.py fetch_sms_inbox --window 48

Designed for cron:
    */5 * * * * cd /path/to/project && python manage.py fetch_sms_inbox
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Fetch incoming SMS from provider inboxes, match to companies, and store."

    def add_arguments(self, parser):
        parser.add_argument(
            "--count",
            type=int,
            default=100,
            help="Messages to fetch per provider (default: 100, max: 100)",
        )
        parser.add_argument(
            "--window",
            type=int,
            default=None,
            help="Reply window in hours (default: from settings, fallback 24)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show provider info without fetching.",
        )

    def handle(self, *args, **options):
        count = min(options["count"], 100)
        window = options["window"]
        dry_run = options["dry_run"]

        self.stdout.write(self.style.NOTICE("=" * 50))
        self.stdout.write(self.style.NOTICE("SMS Inbox Fetch"))
        self.stdout.write(self.style.NOTICE("=" * 50))

        if dry_run:
            self._dry_run()
            return

        from apps.sms.services_inbox import SMSInboxFetchService

        self.stdout.write(f"  Count: {count}, Window: {window or 'default'}h")
        self.stdout.write(self.style.NOTICE("  Fetching...\n"))

        results = SMSInboxFetchService.fetch_all(
            count=count,
            reply_window_hours=window,
        )

        self.stdout.write(self.style.SUCCESS("  Results:"))
        self.stdout.write(f"    Providers checked : {results['providers_checked']}")
        self.stdout.write(f"    Total fetched     : {results['total_fetched']}")
        self.stdout.write(f"    Total ingested    : {results['total_ingested']}")
        self.stdout.write(f"    Matched           : {results['total_matched']}")
        self.stdout.write(f"    Unmatched         : {results['total_unmatched']}")
        self.stdout.write(f"    Ambiguous         : {results['total_ambiguous']}")
        self.stdout.write(f"    Duplicates        : {results['total_duplicates']}")
        self.stdout.write(f"    Errors            : {results['total_errors']}")

        for pr in results.get("provider_results", []):
            if pr["error_message"]:
                self.stdout.write(self.style.ERROR(
                    f"    [{pr['provider_id']}] {pr['provider_name']}: {pr['error_message']}"
                ))

    def _dry_run(self):
        from apps.platform_core.models import PlatformSMSProviderSetting

        self.stdout.write(self.style.WARNING("\n  [DRY RUN] No messages will be fetched.\n"))

        providers = PlatformSMSProviderSetting.objects.filter(
            is_active=True,
            provider_type="melipayamak",
        ).order_by("priority", "id")

        if not providers.exists():
            self.stdout.write(self.style.ERROR("  No active MeliPayamak providers found."))
            return

        self.stdout.write(f"  Eligible providers: {providers.count()}")
        for p in providers:
            self.stdout.write(
                f"    - [{p.id}] {p.name} (username={p.username or p.sender_number})"
            )
