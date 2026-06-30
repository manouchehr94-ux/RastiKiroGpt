from django.db import connection

SQL = """
SELECT order_id, COUNT(*)
FROM invoices_invoice
WHERE status IN ('draft', 'issued')
GROUP BY order_id
HAVING COUNT(*) > 1;
"""

def run_check():
    with connection.cursor() as cursor:
        cursor.execute(SQL)
        rows = cursor.fetchall()

    if rows:
        print("❌ MIGRATION BLOCKED: Duplicate active invoices found")
        for r in rows:
            print(f"order_id={r[0]} count={r[1]}")
        exit(1)

    print("✅ SAFE: No duplicate active invoices found")

if __name__ == "__main__":
    run_check()