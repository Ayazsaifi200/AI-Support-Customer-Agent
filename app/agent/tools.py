"""LangGraph tools the agent uses to validate and act on refund requests.

Each tool is a thin, audited wrapper over the CRM data layer and the
deterministic policy engine. The LLM decides *which* tools to call and in what
order, but the tools themselves enforce the business rules.
"""
import json
from typing import Optional

from langchain_core.tools import tool

from app import crm
from app.policy import days_since, evaluate_refund


@tool
def lookup_customer(customer_id: Optional[str] = None, email: Optional[str] = None) -> str:
    """Look up a customer profile by id or email. Returns name, tier and total_orders."""
    customer = None
    if customer_id:
        customer = crm.get_customer(customer_id)
    elif email:
        customer = crm.find_customer_by_email(email)
    if not customer:
        return json.dumps({"found": False, "message": "No customer matched the given id/email."})
    return json.dumps({"found": True, "customer": customer}, default=str)


@tool
def get_customer_orders(customer_id: str) -> str:
    """List all orders for a customer, including product_name, amount, status and order_date."""
    orders = crm.list_orders(customer_id)
    return json.dumps({"count": len(orders), "orders": orders}, default=str)


@tool
def get_order_details(order_id: str) -> str:
    """Fetch a single order plus how many days have passed since it was placed."""
    order = crm.get_order(order_id)
    if not order:
        return json.dumps({"found": False, "message": "Order not found."})
    order = dict(order)
    order["days_since_order"] = days_since(order.get("order_date"))
    return json.dumps({"found": True, "order": order}, default=str)


@tool
def get_refund_policy() -> str:
    """Return the strict refund policy rules (name, description, max_days, eligible_tiers)."""
    return json.dumps({"rules": crm.list_policy_rules()}, default=str)


@tool
def check_refund_eligibility(
    order_id: str,
    reason: str,
    product_type: str = "physical",
    condition: str = "unused",
    delivery_days: Optional[int] = None,
) -> str:
    """Evaluate whether an order qualifies for a refund under the strict policy.

    Args:
        order_id: The order to evaluate.
        reason: Customer's stated reason for the refund.
        product_type: 'physical' or 'digital'.
        condition: 'unused', 'used' or 'damaged'.
        delivery_days: Business days the delivery took, if the complaint is about lateness.

    Returns a JSON decision: {decision, matched_rule, reason, days_since_order}.
    This does NOT persist anything — call submit_refund_decision to record it.
    """
    order = crm.get_order(order_id)
    if not order:
        return json.dumps({"error": "Order not found."})
    customer = crm.get_customer(order["customer_id"])
    if not customer:
        return json.dumps({"error": "Customer for this order not found."})
    result = evaluate_refund(order, customer, reason, product_type, condition, delivery_days)
    return json.dumps(result, default=str)


@tool
def submit_refund_decision(order_id: str, decision: str, reason: str) -> str:
    """Persist the final refund decision ('approved' or 'denied') to refund_requests.

    Only call this AFTER check_refund_eligibility. The `decision` must match the
    eligibility result. Returns the created refund_request record.
    """
    decision = decision.lower().strip()
    if decision not in ("approved", "denied"):
        return json.dumps({"error": "decision must be 'approved' or 'denied'."})
    order = crm.get_order(order_id)
    if not order:
        return json.dumps({"error": "Order not found."})
    record = crm.create_refund_request(
        order_id=order_id,
        customer_id=order["customer_id"],
        reason=reason,
        status=decision,
    )
    return json.dumps({"saved": True, "refund_request": record}, default=str)


ALL_TOOLS = [
    lookup_customer,
    get_customer_orders,
    get_order_details,
    get_refund_policy,
    check_refund_eligibility,
    submit_refund_decision,
]
