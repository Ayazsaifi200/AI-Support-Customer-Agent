"""Deterministic refund-policy evaluation engine.

The LLM agent never decides refunds on its own. It calls these functions
(exposed as LangGraph tools) which enforce the strict policy rules stored in
the `refund_policy` table. This keeps the financial decision auditable and
prevents prompt-injection from overriding business rules.
"""
from datetime import datetime, timezone
from typing import Optional

from app import crm


def _parse_dt(value) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def days_since(value) -> Optional[int]:
    dt = _parse_dt(value)
    if dt is None:
        return None
    return (datetime.now(timezone.utc) - dt).days


def evaluate_refund(
    order: dict,
    customer: dict,
    reason: str,
    product_type: str = "physical",
    condition: str = "unused",
    delivery_days: Optional[int] = None,
) -> dict:
    """Evaluate a refund against all policy rules and return a decision.

    Returns a dict: {decision, matched_rule, reason, days_since_order}
    Decision precedence (most permissive winning rule applies):
      1. Digital products  -> always denied
      2. Damaged goods     -> approved within 90 days
      3. Late delivery     -> approved if delivery exceeded 14 business days
      4. Gold member bonus -> approved within 60 days (gold tier)
      5. Standard return   -> approved within 30 days, unused & original packaging
    """
    rules = {r["rule_name"]: r for r in crm.list_policy_rules()}
    tier = (customer.get("tier") or "").lower()
    age = days_since(order.get("order_date"))
    cond = (condition or "").lower()
    ptype = (product_type or "").lower()

    def deny(rule_name: str, msg: str) -> dict:
        return {"decision": "denied", "matched_rule": rule_name, "reason": msg, "days_since_order": age}

    def approve(rule_name: str, msg: str) -> dict:
        return {"decision": "approved", "matched_rule": rule_name, "reason": msg, "days_since_order": age}

    # Cancelled / already refunded orders cannot be refunded again.
    status = (order.get("status") or "").lower()
    if status in ("cancelled", "refunded"):
        return deny("Order Status", f"Order status is '{status}', so it is not eligible for a refund.")

    # 1. Digital products -> never refundable
    if ptype == "digital":
        rule = rules.get("Digital Products")
        return deny(
            "Digital Products",
            (rule or {}).get("description", "No refunds on digital or downloadable products."),
        )

    # 2. Damaged goods -> approved within 90 days
    if cond == "damaged":
        rule = rules.get("Damaged Goods", {})
        max_days = rule.get("max_days", 90)
        if age is not None and age <= max_days:
            return approve("Damaged Goods", f"Product reported damaged within the {max_days}-day window.")
        return deny("Damaged Goods", f"Damaged-goods claims must be filed within {max_days} days (order is {age} days old).")

    # 3. Late delivery -> approved if delivery exceeded threshold
    late_rule = rules.get("Late Delivery", {})
    late_threshold = late_rule.get("max_days", 14)
    if delivery_days is not None and delivery_days > late_threshold:
        return approve("Late Delivery", f"Delivery took {delivery_days} business days, exceeding the {late_threshold}-day limit.")

    if age is None:
        return deny("Standard Return", "Order date is unknown, so eligibility cannot be confirmed.")

    # 4. Gold member bonus -> 60-day window for gold tier
    if tier == "gold":
        gold_rule = rules.get("Gold Member Bonus", {})
        gold_days = gold_rule.get("max_days", 60)
        if age <= gold_days and cond in ("unused", "used"):
            if cond == "used":
                return deny("Standard Return", "Item must be unused and in original packaging for a standard return.")
            return approve("Gold Member Bonus", f"Gold member within the extended {gold_days}-day return window.")

    # 5. Standard return -> 30 days, unused & original packaging
    std_rule = rules.get("Standard Return", {})
    std_days = std_rule.get("max_days", 30)
    if age <= std_days:
        if cond != "unused":
            return deny("Standard Return", "Item must be unused and in original packaging for a standard return.")
        return approve("Standard Return", f"Within the standard {std_days}-day return window, item unused.")

    return deny(
        "Standard Return",
        f"Order is {age} days old, beyond the {std_days}-day standard window, and no other rule applies.",
    )
