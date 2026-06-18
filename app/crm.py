"""CRM data-access helpers backed by Supabase."""
import uuid
from typing import Optional

from app.database import get_supabase


def _is_valid_uuid(value: object) -> bool:
    """Return True if `value` is a well-formed UUID string.

    Order/customer ids in this database are UUIDs. Passing a non-UUID (e.g. an
    id the LLM invented) straight to Postgres raises a 22P02 error, so we guard
    lookups and treat malformed ids as 'not found'.
    """
    try:
        uuid.UUID(str(value))
        return True
    except (ValueError, TypeError, AttributeError):
        return False


def list_customers() -> list[dict]:
    return get_supabase().table("customers").select("*").order("name").execute().data


def get_customer(customer_id: str) -> Optional[dict]:
    if not _is_valid_uuid(customer_id):
        return None
    res = get_supabase().table("customers").select("*").eq("id", customer_id).limit(1).execute()
    return res.data[0] if res.data else None


def find_customer_by_email(email: str) -> Optional[dict]:
    res = (
        get_supabase()
        .table("customers")
        .select("*")
        .ilike("email", email)
        .limit(1)
        .execute()
    )
    return res.data[0] if res.data else None


def list_orders(customer_id: Optional[str] = None) -> list[dict]:
    if customer_id is not None and not _is_valid_uuid(customer_id):
        return []
    q = get_supabase().table("orders").select("*")
    if customer_id:
        q = q.eq("customer_id", customer_id)
    return q.order("order_date", desc=True).execute().data


def get_order(order_id: str) -> Optional[dict]:
    if not _is_valid_uuid(order_id):
        return None
    res = get_supabase().table("orders").select("*").eq("id", order_id).limit(1).execute()
    return res.data[0] if res.data else None


def list_policy_rules() -> list[dict]:
    return get_supabase().table("refund_policy").select("*").order("max_days").execute().data


def create_refund_request(
    order_id: str, customer_id: str, reason: str, status: str
) -> dict:
    from datetime import datetime, timezone

    payload = {
        "order_id": order_id,
        "customer_id": customer_id,
        "reason": reason,
        "status": status,
    }
    if status in ("approved", "denied"):
        payload["resolved_at"] = datetime.now(timezone.utc).isoformat()
    res = get_supabase().table("refund_requests").insert(payload).execute()
    return res.data[0] if res.data else {}


def list_refund_requests(customer_id: Optional[str] = None) -> list[dict]:
    q = get_supabase().table("refund_requests").select("*")
    if customer_id:
        q = q.eq("customer_id", customer_id)
    return q.order("requested_at", desc=True).execute().data
