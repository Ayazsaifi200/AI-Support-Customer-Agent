export type Tier = "gold" | "silver" | "bronze";

export interface Customer {
  id: string;
  name: string;
  email: string;
  phone?: string;
  tier: Tier;
  total_orders: number;
  created_at?: string;
}

export interface Order {
  id: string;
  customer_id: string;
  product_name: string;
  amount: number;
  order_date?: string;
  status: string;
}

export interface PolicyRule {
  id: string;
  rule_name: string;
  description: string;
  max_days: number;
  eligible_tiers: string;
}

export interface RefundRequest {
  id: string;
  order_id: string;
  customer_id: string;
  reason?: string;
  status: string;
  requested_at?: string;
  resolved_at?: string;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export type AgentEvent =
  | { type: "tool_call"; name: string; args: Record<string, unknown> }
  | { type: "tool_result"; name: string; output: string }
  | { type: "final"; reply: string; decision: string | null }
  | { type: "error"; message: string };

export type ReasoningLog = AgentEvent & {
  id: string;
  ts: number;
};
