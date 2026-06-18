"""CRM endpoints: customers, orders, policy and refund history (read-only)."""
from fastapi import APIRouter, HTTPException

from app import crm

router = APIRouter(prefix="/crm", tags=["crm"])


@router.get("/customers")
def get_customers():
    return crm.list_customers()


@router.get("/customers/{customer_id}")
def get_customer(customer_id: str):
    customer = crm.get_customer(customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer


@router.get("/customers/{customer_id}/orders")
def get_customer_orders(customer_id: str):
    if not crm.get_customer(customer_id):
        raise HTTPException(status_code=404, detail="Customer not found")
    return crm.list_orders(customer_id)


@router.get("/orders")
def get_orders():
    return crm.list_orders()


@router.get("/orders/{order_id}")
def get_order(order_id: str):
    order = crm.get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@router.get("/policy")
def get_policy():
    return crm.list_policy_rules()


@router.get("/refund-requests")
def get_refund_requests():
    return crm.list_refund_requests()
