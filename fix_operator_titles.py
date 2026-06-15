import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.local')

f = "apps/accounts/operator_access.py"
with open(f, 'r', encoding='utf-8') as fp:
    content = fp.read()

# پیدا کردن TITLE_MAP و اضافه کردن عنوان‌های فارسی
extra_titles = '''
    # عمومی
    "home": "داشبورد",
    "admin_page": "صفحه اصلی ادمین",
    "admin_branding": "برندینگ و صفحه عمومی",
    "admin_customers": "مشتریان",
    "admin_customer_detail": "جزئیات مشتری",
    "admin_customer_lookup": "جستجوی مشتری",
    "admin_requests": "درخواست‌های فرم عمومی",
    "admin_gallery": "گالری تصاویر",
    "admin_gallery_create": "افزودن تصویر گالری",
    "admin_gallery_edit": "ویرایش تصویر گالری",
    "admin_gallery_delete": "حذف تصویر گالری",
    # نیروهای خدماتی
    "admin_technicians": "لیست نیروهای خدماتی",
    "admin_technician_create": "ساخت نیروی خدماتی",
    "admin_technician_edit": "ویرایش نیروی خدماتی",
    "admin_technician_delete": "حذف نیروی خدماتی",
    "admin_technician_toggle_active": "فعال/غیرفعال نیرو",
    "admin_technician_ledger": "دفتر حساب نیرو",
    "admin_technician_settlement": "تسویه نیرو",
    # سفارش‌ها
    "admin_order_create": "افزودن سفارش",
    "admin_order_edit": "ویرایش سفارش",
    "admin_order_assign": "تخصیص نیرو به سفارش",
    "admin_order_return_to_cycle": "بازگشت سفارش به چرخه",
    "admin_cancel_request_approve": "تأیید لغو سفارش",
    "admin_cancel_request_reject": "رد درخواست لغو",
    # فاکتورها
    "admin_invoice_create_from_order": "افزودن فاکتور از سفارش",
    "admin_invoice_print": "چاپ و مشاهده فاکتور",
    "financial_invoice_settlement": "تسویه فاکتور",
    "admin_sms_invoice_detail": "جزئیات فاکتور پیامک",
    "admin_sms_invoices": "فاکتورهای پیامک",
    # پرداخت‌ها
    "admin_payment_operations": "عملیات پرداخت",
    "admin_payment_gateway": "درگاه پرداخت",
    "admin_payment_gateway_test": "تست درگاه پرداخت",
    "admin_merchant_profile": "پروفایل پذیرنده",
    "admin_merchant_profile_document": "مدارک پذیرنده",
    "admin_merchant_profile_edit_request": "ویرایش پروفایل پذیرنده",
    "admin_split_snapshots": "لیست تسهیم پرداخت",
    "admin_split_snapshot_detail": "جزئیات تسهیم پرداخت",
    # پیامک
    "template_list": "قالب‌های پیامک",
    "template_create": "افزودن قالب پیامک",
    "template_edit": "ویرایش قالب پیامک",
    "template_toggle": "فعال/غیرفعال قالب",
    "outbox": "صندوق ارسال پیامک",
    "outbox_list": "لیست پیامک‌ها",
    "outbox_detail": "جزئیات پیامک",
    "outbox_send_now": "ارسال فوری پیامک",
    "outbox_bulk_retry": "ارسال مجدد پیامک‌ها",
    "inbox_list": "صندوق دریافت پیامک",
    "inbox_detail": "جزئیات پیامک دریافتی",
    "diagnostics": "تشخیص و تست پیامک",
    "admin_sms_credit": "اعتبار پیامک",
    "admin_sms_recharge": "شارژ اعتبار پیامک",
    "admin_sms_transactions": "تراکنش‌های پیامک",
    "admin_sms_template_view": "مشاهده قالب پیامک",
    "admin_sms_template_request": "درخواست تغییر قالب",
    "admin_communication_settings": "تنظیمات ارتباط",
    # گزارش‌ها
    "financial_summary": "گزارش مالی خلاصه",
    "financial_technician_breakdown": "گزارش مالی تکنسین‌ها",
    "financial_cash_control": "کنترل نقدی",
    "financial_platform_fees": "کارمزد پلتفرم",
    "financial_audit": "حسابرسی مالی",
    "customer_segments": "بخش‌بندی مشتریان",
    "discount_campaign_list": "کمپین‌های تخفیف",
    "discount_campaign_new": "کمپین تخفیف جدید",
    "discount_campaign_detail": "جزئیات کمپین تخفیف",
    "discount_campaign_manual": "ارسال دستی کد تخفیف",
    "discount_campaign_single_customer": "کد تخفیف تک مشتری",
    "list": "لیست گزارش‌ها",
    # اطلاعات پایه
    "admin_base_data": "داشبورد اطلاعات پایه",
    "admin_base_items": "آیتم‌های سفارش",
    "admin_base_item_create": "افزودن آیتم سفارش",
    "admin_base_item_edit": "ویرایش آیتم سفارش",
    "admin_base_item_delete": "حذف آیتم سفارش",
    # نوتیفیکیشن
    "mark_read": "علامت خواندن اعلان",
'''

# اضافه کردن به TITLE_MAP
old = 'TITLE_MAP = {'
new = 'TITLE_MAP = {' + extra_titles

if old in content and extra_titles.strip()[:20] not in content:
    content = content.replace(old, new)
    with open(f, 'w', encoding='utf-8') as fp:
        fp.write(content)
    print("TITLE_MAP updated OK")
else:
    print("Already updated or pattern not found")
