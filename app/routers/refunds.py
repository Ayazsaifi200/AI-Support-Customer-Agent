"""Direct, deterministic refund-decision endpoint (no LLM).

Useful for programmatic integrations and for testing the policy engine in
isolation from the agent.
"""
from fastapi import APIRouter, HTTPException

from app import crm
from app.policy import evaluate_refund
from app.schemas import RefundDecisionRequest, RefundDecisionResponse

router = APIRouter(prefix="/refunds", tags=["refunds"])


@router.post("/decide", response_model=RefundDecisionResponse)
def decide(req: RefundDecisionRequest):
    order = crm.get_order(req.order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    customer = crm.get_customer(order["customer_id"])
    if not customer:
        raise HTTPException(status_code=404, detail="Customer for order not found")

    result = evaluate_refund(
        order=order,
        customer=customer,
        reason=req.reason,
        product_type=req.product_type,
        condition=req.condition,
        delivery_days=req.delivery_days,
    )

    record = crm.create_refund_request(
        order_id=req.order_id,
        customer_id=order["customer_id"],
        reason=req.reason,
        status=result["decision"],
    )

    return RefundDecisionResponse(
        decision=result["decision"],
        matched_rule=result.get("matched_rule"),
        reason=result["reason"],
        days_since_order=result.get("days_since_order"),
        refund_request_id=record.get("id"),
    )
