"""
Sync SMS master templates from code defaults into the database.

Usage:
    python manage.py sync_sms_master_templates --dry-run
    python manage.py sync_sms_master_templates
    python manage.py sync_sms_master_templates --force

Default behavior is safe:
- creates missing SMSMasterTemplate rows
- fills empty title/variables/template_text only
- does NOT overwrite edited template_text

--force behavior:
- updates title, scope, recipient_type, allowed_variables, and template_text from code defaults
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create/update SMSMasterTemplate rows from SMS_DEFAULT_TEMPLATES safely."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Show what would change without saving.")
        parser.add_argument("--force", action="store_true", help="Overwrite existing fields from code defaults.")

    def handle(self, *args, **options):
        from apps.sms.default_template_texts import get_default_templates
        from apps.sms.models_master import SMSMasterTemplate

        dry_run = bool(options.get("dry_run"))
        force = bool(options.get("force"))

        scope_map = {
            "company": SMSMasterTemplate.Scope.COMPANY,
            "platform": SMSMasterTemplate.Scope.PLATFORM,
        }
        recipient_map = {
            "customer": SMSMasterTemplate.RecipientType.CUSTOMER,
            "technician": SMSMasterTemplate.RecipientType.TECHNICIAN,
            "admin": SMSMasterTemplate.RecipientType.ADMIN,
            "operator": SMSMasterTemplate.RecipientType.ADMIN,
            "platform_admin": SMSMasterTemplate.RecipientType.PLATFORM_ADMIN,
        }

        created = 0
        updated = 0
        skipped = 0
        definitions = get_default_templates()

        for defn in definitions:
            key = defn["event_key"]
            variables = defn.get("template_variables") or []
            defaults = {
                "scope": scope_map.get(defn.get("scope"), SMSMasterTemplate.Scope.COMPANY),
                "recipient_type": recipient_map.get(defn.get("recipient_type"), SMSMasterTemplate.RecipientType.CUSTOMER),
                "title": defn.get("title") or key,
                "template_text": defn.get("template_text") or "",
                "allowed_variables": ",".join(variables),
                "is_active": True,
            }

            obj = SMSMasterTemplate.objects.filter(key=key).first()
            if obj is None:
                created += 1
                self.stdout.write(f"CREATE {key}")
                if not dry_run:
                    SMSMasterTemplate.objects.create(key=key, **defaults)
                continue

            update_fields = []
            if force:
                for field, value in defaults.items():
                    if getattr(obj, field, None) != value:
                        setattr(obj, field, value)
                        update_fields.append(field)
            else:
                if not (obj.title or "").strip() and defaults["title"]:
                    obj.title = defaults["title"]
                    update_fields.append("title")
                if not (obj.allowed_variables or "").strip() and defaults["allowed_variables"]:
                    obj.allowed_variables = defaults["allowed_variables"]
                    update_fields.append("allowed_variables")
                if not (obj.template_text or "").strip() and defaults["template_text"]:
                    obj.template_text = defaults["template_text"]
                    update_fields.append("template_text")

            if update_fields:
                updated += 1
                self.stdout.write(f"UPDATE {key}: {', '.join(update_fields)}")
                if not dry_run:
                    obj.save(update_fields=update_fields + ["updated_at"])
            else:
                skipped += 1

        self.stdout.write("")
        self.stdout.write(f"Total definitions: {len(definitions)}")
        self.stdout.write(f"Created: {created}")
        self.stdout.write(f"Updated: {updated}")
        self.stdout.write(f"Skipped: {skipped}")
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN: no database changes were saved."))
        else:
            self.stdout.write(self.style.SUCCESS("SMS master templates synced."))
