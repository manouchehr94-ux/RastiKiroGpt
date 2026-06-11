# -*- coding: utf-8 -*-
"""
Management command to test MeliPayamak pattern-based SMS sending.

Usage:
    python manage.py test_melipayamak_pattern --to 09170432500 --code 53233
    python manage.py test_melipayamak_pattern --to 09170432500 --code 53233 --template user_mobile_verification
    python manage.py test_melipayamak_pattern --to 09170432500 --code 53233 --expire 5 --dry-run
"""
import json

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Test MeliPayamak pattern send through owner-panel provider/template routing."

    def add_arguments(self, parser):
        parser.add_argument(
            "--to",
            required=True,
            help="Recipient mobile number (e.g. 09170432500)",
        )
        parser.add_argument(
            "--code",
            required=True,
            help="OTP code to send (e.g. 53233)",
        )
        parser.add_argument(
            "--template",
            default="user_mobile_verification",
            help="Template key (default: user_mobile_verification)",
        )
        parser.add_argument(
            "--expire",
            default="2",
            help="Expiration minutes (default: 2)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be sent without actually sending.",
        )

    def handle(self, *args, **options):
        from apps.sms.providers.melipayamak import (
            SMSProviderError,
            build_pattern_text,
            send_template_pattern_by_owner_route,
        )

        to = options["to"]
        code = options["code"]
        template_key = options["template"]
        expire = options["expire"]
        dry_run = options["dry_run"]

        variables = {
            "otp_code": code,
            "code": code,
            "expire_minutes": expire,
        }

        self.stdout.write(self.style.NOTICE("=" * 60))
        self.stdout.write(self.style.NOTICE("MeliPayamak Pattern SMS Test"))
        self.stdout.write(self.style.NOTICE("=" * 60))
        self.stdout.write(f"  Template key : {template_key}")
        self.stdout.write(f"  To           : {to}")
        self.stdout.write(f"  Variables    : {variables}")

        if dry_run:
            self.stdout.write(self.style.WARNING("\n[DRY RUN] No SMS will be sent."))
            self._show_routing_info(template_key, variables)
            return

        self.stdout.write(self.style.NOTICE("\nSending..."))

        try:
            result = send_template_pattern_by_owner_route(
                template_key=template_key,
                to=to,
                variables=variables,
            )
            self.stdout.write(self.style.SUCCESS("\nSMS sent successfully!"))
            self.stdout.write(self.style.SUCCESS("-" * 40))
            self.stdout.write(f"  Provider    : {result.get('provider', 'N/A')}")
            self.stdout.write(f"  Message ID  : {result.get('message_id', 'N/A')}")
            self.stdout.write(f"  Sent text   : {result.get('request_text', 'N/A')}")
            self.stdout.write(f"  Sent at     : {result.get('sent_at', 'N/A')}")
            self.stdout.write(f"  Endpoint    : {result.get('endpoint', 'N/A')}")
            self.stdout.write(f"\n  Full response:")
            self.stdout.write(
                f"  {json.dumps(result.get('response', {}), ensure_ascii=False, indent=2)}"
            )
        except SMSProviderError as exc:
            self.stdout.write(self.style.ERROR(f"\nSMS send FAILED: {exc}"))
        except Exception as exc:
            self.stdout.write(self.style.ERROR(f"\nUnexpected error: {exc}"))
            raise

    def _show_routing_info(self, template_key, variables):
        """Show routing configuration without sending."""
        try:
            from apps.sms.models_master import SMSMasterTemplate, SMSMasterTemplateProviderConfig
            from apps.platform_core.models import PlatformSMSProviderSetting
            from apps.sms.providers.melipayamak import build_pattern_text

            template = SMSMasterTemplate.objects.filter(
                key=template_key, is_active=True
            ).first()

            if not template:
                self.stdout.write(self.style.ERROR(
                    f"\n  No active SMSMasterTemplate found for key='{template_key}'"
                ))
                return

            self.stdout.write(f"\n  Master Template: {template.title}")
            self.stdout.write(f"  BodyId         : {template.melipayamak_body_id}")
            self.stdout.write(f"  Variables Order: {template.melipayamak_variables_order}")

            routes = SMSMasterTemplateProviderConfig.objects.filter(
                master_template=template, is_active=True
            ).order_by("-is_primary", "priority", "id")

            if routes.exists():
                self.stdout.write(f"\n  Provider Routes ({routes.count()}):")
                for r in routes:
                    provider = PlatformSMSProviderSetting.objects.filter(
                        id=r.provider_setting_id, is_active=True
                    ).first()
                    text = build_pattern_text(variables, r.variables_order)
                    self.stdout.write(
                        f"    - {r.provider_name or r.provider_type} "
                        f"(primary={r.is_primary}, fallback={r.is_fallback}, "
                        f"priority={r.priority}) "
                        f"pattern_code={r.pattern_code} "
                        f"text='{text}' "
                        f"provider_active={'YES' if provider else 'NO'}"
                    )
            else:
                self.stdout.write("\n  No specific routes. Will use default provider.")
                variables_order = (
                    template.melipayamak_variables_order
                    or template.allowed_variables
                )
                text = build_pattern_text(variables, variables_order)
                self.stdout.write(f"  Computed text: '{text}'")

                provider = PlatformSMSProviderSetting.objects.filter(
                    provider_type="melipayamak", is_active=True
                ).order_by("priority", "id").first()
                if provider:
                    self.stdout.write(
                        f"  Default provider: {provider.name} "
                        f"(username={provider.username or provider.sender_number})"
                    )
                else:
                    self.stdout.write(self.style.ERROR(
                        "  No active MeliPayamak provider found!"
                    ))

        except Exception as exc:
            self.stdout.write(self.style.ERROR(f"\n  Error reading config: {exc}"))
