# System Architecture

Rasti Service is a Django multi-tenant SaaS.

## Layers

1. Models — data and constraints
2. Services — business logic
3. Selectors — read/query logic
4. Views — HTTP/UI only, thin layer
5. Templates — presentation only
6. Tests — behavior guarantee

## Rule

Business decisions must live in services, not in views/templates.
