---
Title: Architecture — README
Layer: Architecture
Audience: Human + AI
Status: Active
Last Verified: 2026-07-01
Source of Truth: Code
Reusable Across Projects: No
---

# 03 — Architecture

Technical architecture documentation for the Rasti SaaS platform.

---

## Files in This Folder

| File | Contents | Status |
|---|---|---|
| [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md) | High-level architecture, URL structure, tech stack, data flow | Active |
| [DJANGO_APP_ARCHITECTURE.md](DJANGO_APP_ARCHITECTURE.md) | Per-app responsibilities, model locations | Active |
| [MULTI_TENANCY.md](MULTI_TENANCY.md) | URL-based tenancy, TenantMiddleware, isolation rules | Active |
| [PERMISSIONS.md](PERMISSIONS.md) | Roles, decorators, known P0-1 security bug | Active |
| [SERVICE_LAYER.md](SERVICE_LAYER.md) | Service-layer pattern, financial service rules | Active |
| [TEMPLATE_ARCHITECTURE.md](TEMPLATE_ARCHITECTURE.md) | Template hierarchy, layouts, known duplicates | Active |
| [DATABASE_MODEL.md](DATABASE_MODEL.md) | Model relationships, money fields, immutability | Active |
| [DOMAIN_MODEL.md](DOMAIN_MODEL.md) | Business domain entities and relationships | Active |
| [API_ARCHITECTURE.md](API_ARCHITECTURE.md) | REST API rules (future scope) | Active |

---

## Reading Order

1. [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md) — start here for full picture
2. [MULTI_TENANCY.md](MULTI_TENANCY.md) — read before any data access code
3. [PERMISSIONS.md](PERMISSIONS.md) — read before any auth/access code
4. [SERVICE_LAYER.md](SERVICE_LAYER.md) — read before any business logic code
5. [DATABASE_MODEL.md](DATABASE_MODEL.md) — read before touching models

---

## Related Documents

- [../04_Business_Rules/](../04_Business_Rules/) — business rules that derive from this architecture
- [../07_ADR/](../07_ADR/) — architectural decisions that established these rules
- [../11_Project_Knowledge/KNOWN_CONSTRAINTS.md](../11_Project_Knowledge/KNOWN_CONSTRAINTS.md) — non-negotiable development constraints

---

## Maintenance Notes

Architecture documents should be updated when an ADR changes an architectural decision. Always create or update an ADR first, then update the relevant architecture document to reference it.
