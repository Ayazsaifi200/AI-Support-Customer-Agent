"""Seed the `orders` table with realistic data covering every policy scenario.

Idempotent-ish: skips seeding if orders already exist. Run with:
    python seed_orders.py
"""
import random
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv

load_dotenv()

from app.database import get_supabase  # noqa: E402

NOW = datetime.now(timezone.utc)

# Product catalogue (physical + digital)
PHYSICAL = [
    "Wireless Headphones", "Running Shoes", "Coffee Maker", "Yoga Mat",
    "Backpack", "Desk Lamp", "Bluetooth Speaker", "Water Bottle",
    "Mechanical Keyboard", "Office Chair",
]
DIGITAL = ["E-book: Python Mastery", "Online Course: UX Design", "Software License Key", "Stock Photo Pack"]


def _order(customer_id: str, product: str, amount: float, days_ago: int, status: str) -> dict:
    return {
        "customer_id": customer_id,
        "product_name": product,
        "amount": round(amount, 2),
        "order_date": (NOW - timedelta(days=days_ago)).isoformat(),
        "status": status,
    }


def main() -> None:
    sb = get_supabase()
    existing = sb.table("orders").select("id", count="exact").execute()
    if existing.count and existing.count > 0:
        print(f"Orders already present ({existing.count}). Skipping seed.")
        return

    customers = sb.table("customers").select("id,tier,name").order("name").execute().data
    if not customers:
        print("No customers found. Seed customers first.")
        return

    random.seed(42)
    rows: list[dict] = []

    # Give every customer a spread of orders across time windows.
    # day buckets chosen to exercise each policy rule:
    #   5  -> standard window (eligible)
    #   25 -> standard window edge (eligible if unused)
    #   45 -> only gold eligible (60d), others denied (>30d)
    #   80 -> only damaged-goods eligible (90d)
    #   120 -> beyond all windows
    day_buckets = [5, 25, 45, 80, 120]

    for i, cust in enumerate(customers):
        n_orders = random.randint(1, 3)
        for j in range(n_orders):
            is_digital = (i + j) % 5 == 0
            product = random.choice(DIGITAL if is_digital else PHYSICAL)
            amount = random.uniform(15, 350)
            days_ago = day_buckets[(i + j) % len(day_buckets)]
            status = random.choice(["delivered", "delivered", "delivered", "shipped"])
            rows.append(_order(cust["id"], product, amount, days_ago, status))

    # Add a couple of guaranteed edge cases on the first customer.
    first = customers[0]["id"]
    rows.append(_order(first, "E-book: Advanced LangGraph", 29.99, 3, "delivered"))  # digital -> deny
    rows.append(_order(first, "Damaged Vase", 89.50, 40, "delivered"))  # damaged path

    res = sb.table("orders").insert(rows).execute()
    print(f"Inserted {len(res.data)} orders for {len(customers)} customers.")


if __name__ == "__main__":
    main()
