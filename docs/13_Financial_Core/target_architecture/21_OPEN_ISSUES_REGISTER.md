# 21 — ثبت مسائل باز (Open Issues Register)

**Version:** v1.0 — Draft — Pending Clarification

---

## OI-01 — قابلیت Split Payment

**Current Status:**
`PaymentSplitDecisionService` و `PaymentSplitSnapshot` طراحی شده. `Technician.sub_merchant_id` field موجود. اما split واقعی Shaparak (TASK-010C) هنوز planned.

**Architectural Clue:**
Implementation نشان می‌دهد که تیم split payment را در نظر گرفته و مدل داده را آماده کرده.

**Impact on Architecture:**
- اگر PSP از split پشتیبانی کند: Model C فعال می‌شود
- اگر نکند: Model A/B باقی می‌ماند و settlement batch جایگزین

**Question for Product Owner:**
آیا PSP انتخاب‌شده (Shaparak) از Split Payment real-time بین چند ذینفع پشتیبانی می‌کند؟

---

## OI-02 — مدل‌سازی حمل‌ونقل

**Current Status:**
فعلاً `InvoiceItem.RowType.TRAVEL` — یک ردیف فاکتور مجزا.

**Architectural Clue:**
پیاده‌سازی فعلی نشان می‌دهد travel به عنوان line item مدل شده — نه field مستقل.

**Impact on Architecture:**
تصمیم بر settlement calculation تأثیر ندارد (هر دو approach با category subtotals سازگار).

**Question for Product Owner:**
آیا حمل‌ونقل باید ردیف مجزا بماند یا فیلد ثابت فاکتور شود؟

---

## OI-03 — توزیع تخفیف

**Current Status:**
`CompanyFinancialPolicy` چهار policy (COMPANY/TECHNICIAN/HALF_HALF/PROPORTIONAL) دارد. extra و campaign جداگانه. اما سایر انواع تخفیف (line, rounding, loyalty) policy مشخصی ندارند.

**Impact on Architecture:**
- Line discount: قبلاً در item.total_price بازتاب داده شده → proportional impact
- Rounding discount: R29 → field جدید لازم
- Loyalty discount: mapping to campaign policy یا policy مجزا؟

**Question for Product Owner:**
دقیقاً کدام ذینفع هزینه هر نوع تخفیف را تحمل می‌کند؟

---

## OI-04 — فرمول محاسبه بدهی تکنسین

**Current Status:**
Balance = SUM(credits) - SUM(debits). Negative = technician owes company.

**Architectural Clue:**
فرمول ضمنی: technician collects cash (DEBIT total_amount) → balance goes negative → owes company the difference (total - wage).

**Impact on Architecture:**
فرمول از ledger قابل استخراج. اما فرمول رسمی document نشده.

**Question for Product Owner:**
فرمول رسمی محاسبه بدهی تکنسین بعد از دریافت نقد چیست؟

---

## OI-05 — اصلاحات مالی مشتری

**Current Status:**
هیچ مکانیزم customer credit/debit وجود ندارد.

**Impact on Architecture:**
بلاک‌کننده `AdjustmentDocument` + `CustomerFinancialAccount` models.

**Question for Product Owner:**
دقیقاً در چه سناریوهایی مشتری بستانکار یا بدهکار می‌شود؟

---

## OI-06 — پرداخت بیشتر از مبلغ فاکتور

**Current Status:**
`PaymentVerifyService`: amount mismatch → NEEDS_RECONCILIATION. Overpayment explicitly handled نیست.

**Impact on Architecture:**
اگر wallet → نیاز به `CustomerWallet` model. اگر refund → نیاز به gateway refund API.

**Question for Product Owner:**
Overpayment: Wallet، Refund، یا Credit Balance؟

---

## OI-07 — تعریف بازپرداخت

**Current Status:**
`TechnicianLedgerEntry.Source.REFUND` تعریف شده. هیچ service پیاده‌سازی نشده.

**Impact on Architecture:**
بلاک‌کننده تمام Sprint 6 (Refund Engine). بدون تعریف، هیچ refund logic قابل پیاده‌سازی نیست.

**Question for Product Owner:**
تعریف بصری و تصمیم‌گیری: Full Refund, Partial Refund, Manual Adjustment — هرکدام چه اثری بر ledger و stakeholders دارد؟

---

## OI-08 — تأیید تغییر سیاست

**Current Status:**
تغییرات policy فوری و بدون approval workflow. فقط platform owner مجاز.

**Impact on Architecture:**
اگر two-step approval → `PolicyChangeRequest` model + approval workflow.

**Question for Product Owner:**
آیا تغییر commission/revenue-sharing policies نیاز به تأیید توسط چند admin دارد؟

---

## OI-09 — KPI مالی

**Current Status:**
`Report` model stub. هیچ KPI implementation واقعی.

**Impact on Architecture:**
بلاک‌کننده Sprint 7 (KPI Dashboard). بدون catalog، scope نامشخص.

**Question for Product Owner:**
کدام KPIهای مالی الزامی هستند؟ (GMV, Commission Rate, Settlement Velocity, ...)

---

## OI-10 — گزارش‌گیری تکنسین

**Current Status:**
`TechnicianStatementService` + export views exist. اما limited to ledger entries.

**Impact on Architecture:**
ممکن است نیاز به dashboard/portal مخصوص تکنسین باشد.

**Question for Product Owner:**
دقیقاً کدام گزارش‌ها باید به تکنسین نمایش داده شود؟ (balance, history, PDF, period summary?)
