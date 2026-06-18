"""Pydantic schemas for API requests and responses."""
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


# ---------- Domain models ----------
class Customer(BaseModel):
    id: str
    name: str
    email: str
    phone: Optional[str] = None
    tier: str
    total_orders: int = 0
    created_at: Optional[datetime] = None


class Order(BaseModel):
    id: str
    customer_id: str
    product_name: str
    amount: float
    order_date: Optional[datetime] = None
    status: str


class PolicyRule(BaseModel):
    id: str
    rule_name: str
    description: str
    max_days: int
    eligible_tiers: str


class RefundRequest(BaseModel):
    id: str
    order_id: str
    customer_id: str
    reason: Optional[str] = None
    status: str
    requested_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None


# ---------- API payloads ----------
class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str


class ChatRequest(BaseModel):
    message: str = Field(..., description="Customer message to the support agent")
    customer_id: Optional[str] = Field(
        None, description="Optional known customer id for grounding the conversation"
    )
    history: list[ChatMessage] = Field(default_factory=list)


class ChatResponse(BaseModel):
    reply: str
    decision: Optional[str] = None  # approved | denied | needs_info | none
    tool_calls: list[dict] = Field(default_factory=list)


class RefundDecisionRequest(BaseModel):
    order_id: str
    reason: str = Field(..., description="Why the customer wants a refund")
    product_type: Literal["physical", "digital"] = "physical"
    condition: Literal["unused", "used", "damaged"] = "unused"
    delivery_days: Optional[int] = Field(
        None, description="Business days the delivery took, if relevant"
    )


class RefundDecisionResponse(BaseModel):
    decision: Literal["approved", "denied"]
    matched_rule: Optional[str] = None
    reason: str
    days_since_order: Optional[int] = None
    refund_request_id: Optional[str] = None
