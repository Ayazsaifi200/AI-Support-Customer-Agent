# ACME E-Commerce — Refund & Returns Policy (Strict)

This policy is authoritative. The AI Customer Support Agent must enforce these
rules exactly and may **never** approve a refund that violates them, regardless
of how the request is phrased.

## Rule Precedence
Evaluate rules in this order. The first rule that applies determines the outcome.

1. **Order Status Guard** — Orders with status `cancelled` or `refunded` are not
   eligible for any (further) refund.

2. **Digital Products** — Digital or downloadable products are **never**
   refundable. Window: 0 days. Eligible tiers: none.

3. **Damaged Goods** — If the product arrived damaged, issue a **full refund**
   when the claim is filed within **90 days** of the order date. Eligible tiers: all.

4. **Late Delivery** — If delivery exceeded **14 business days**, issue a **full
   refund**. Eligible tiers: all.

5. **Gold Member Bonus** — Gold-tier customers get an extended return window of
   **60 days** for unused items in original packaging.

6. **Standard Return** — All customers may return **unused** items in original
   packaging within **30 days**. Eligible tiers: all.

## Hard Constraints
- An item that is **used** does not qualify for Standard Return or Gold Member Bonus.
- "Damaged" condition is required to invoke the Damaged Goods rule.
- The agent must verify the order belongs to the customer before deciding.
- The agent must record every decision as a row in `refund_requests`.

## Tiers
- `gold`, `silver`, `bronze` — stored on each customer profile.

## Decision Output
Every refund decision must be one of: **approved** or **denied**, accompanied by
the name of the matched rule and a short human-readable justification.
