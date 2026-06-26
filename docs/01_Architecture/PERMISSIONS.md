# Permission Rules

## Platform owner

Can:
- activate/deactivate payment mode
- approve KYC
- create/activate gateways
- run reconciliation
- resolve `NEEDS_RECONCILIATION`
- record platform fee settlement

## Company admin

Can:
- manage company users and technicians
- manage orders/invoices within company
- submit KYC
- view payment status
- record manual/cash payments according to policy

Cannot:
- activate online payment mode
- set gateway `owner_type`
- create platform-owned gateway
- run platform reconciliation
