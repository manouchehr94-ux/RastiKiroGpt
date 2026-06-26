# RDOS v1.0 Stable Changelog

Date: 2026-06-26

## Purpose

This patch stabilizes the documentation and architecture layer before implementation tasks begin.

## Corrected

- Fixed terminology around payment mode and `CompanyPaymentSettings`.
- Completed platform commission rule in `SKILL.md`, `GLOSSARY.md`, and `PAYMENT_RULES.md`.
- Added `ARCHITECTURE_INDEX.md` to show where each source of truth lives.
- Clarified Phase 1 vs Phase 2 boundaries around `PaymentGateway.owner_type`.
- Identified legacy gateway models by exact class names.
- Clarified `DECISION_TEMPLATE.md` vs ADR template.
- Expanded domain model references.

## Freeze Rule

After this patch is applied, RDOS v1.0 is stable. Future architecture changes require ADR update or new ADR.
