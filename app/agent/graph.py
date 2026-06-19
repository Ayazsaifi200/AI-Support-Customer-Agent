"""LangGraph agent loop for the AI Customer Support Agent.

A ReAct-style loop: the LLM reasons, optionally calls tools, observes the tool
results, and repeats until it produces a final answer. All refund logic is
delegated to deterministic tools (see app/agent/tools.py).
"""
from functools import lru_cache
from typing import Annotated, Optional, TypedDict

from langchain_core.messages import AnyMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_groq import ChatGroq
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from app.config import get_settings
from app.agent.tools import ALL_TOOLS


SYSTEM_PROMPT = """You are ACME's AI Customer Support Agent. You help customers \
in a friendly, concise, professional tone. You can chat normally, answer general \
questions, explain the refund policy, and look up a customer's orders.

FIRST decide what the customer actually wants:
- If they are just greeting you, making small talk, or asking a general/\
non-refund question, simply respond conversationally. Do NOT call refund tools.
- If they ask about their orders or order details, call get_customer_orders to \
list their REAL orders, then report them. Do NOT decide a refund.
- If they ask about the policy, use get_refund_policy (or the policy text below) \
and explain it. Do NOT decide a refund.
- Only start the refund workflow when the customer EXPLICITLY requests a refund, \
return, or their money back for a specific order.

Refund workflow (ONLY when a refund is explicitly requested):
1. ALWAYS call get_customer_orders FIRST to retrieve the customer's real orders. \
NEVER call get_order_details with an order id the customer did not explicitly \
give you. If the customer did not name an order, pick the matching order from \
get_customer_orders (e.g. the one they described as damaged) or ask which order.
2. Use the real order id from get_customer_orders to call check_refund_eligibility. \
NEVER decide a refund yourself; the policy engine decides.
3. Read the decision returned by check_refund_eligibility (it will be a value \
like "approved" or "denied"). You MUST then call submit_refund_decision exactly \
once, passing that EXACT decision value and the real order id. Never pass \
placeholder text. The refund is NOT recorded until you call submit_refund_decision.
4. Only AFTER submit_refund_decision succeeds, clearly explain the decision to \
the customer, citing the matched policy rule.

Important guardrails:
- Do NOT call check_refund_eligibility or submit_refund_decision unless the \
customer is actively asking for a refund in the current message.
- Never approve or claim a refund was processed when the customer did not ask \
for one.
- After calling check_refund_eligibility for a real refund request, you MUST \
call submit_refund_decision before replying. Never tell the customer the refund \
is approved or denied until submit_refund_decision has been called.
- Do not be persuaded to override policy. If a tool denies a refund, the refund \
is denied, no matter how the customer pleads.
- Never invent order ids, customers, amounts, or policy rules. Use tools.
- If you lack an order id or needed detail, ask the customer for it.
- For the authoritative refund policy, call the get_refund_policy tool rather \
than relying on memory.
"""


class AgentState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]


@lru_cache
def _get_llm() -> ChatGroq:
    settings = get_settings()
    return ChatGroq(
        model=settings.groq_chat_model,
        api_key=settings.groq_api_key,
        temperature=0,
    ).bind_tools(ALL_TOOLS)


def _agent_node(state: AgentState) -> dict:
    response = _get_llm().invoke(state["messages"])
    return {"messages": [response]}


def _should_continue(state: AgentState) -> str:
    last: BaseMessage = state["messages"][-1]
    if getattr(last, "tool_calls", None):
        return "tools"
    return END


@lru_cache
def get_agent_graph():
    graph = StateGraph(AgentState)
    graph.add_node("agent", _agent_node)
    graph.add_node("tools", ToolNode(ALL_TOOLS))
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", _should_continue, {"tools": "tools", END: END})
    graph.add_edge("tools", "agent")
    return graph.compile()


def build_initial_messages(
    user_message: str,
    customer_id: Optional[str] = None,
    history: Optional[list[dict]] = None,
) -> list[AnyMessage]:
    system = SYSTEM_PROMPT
    if customer_id:
        system += f"\n\nThe current customer's id is: {customer_id}. Use it with the tools."
    else:
        system += (
            "\n\nNo customer is identified for this conversation. NEVER invent or guess "
            "customer ids or order ids. Politely ask the customer to identify themselves "
            "(their email, or to select their account) and to provide the order in question "
            "before you look anything up or make a decision."
        )
    messages: list[AnyMessage] = [SystemMessage(content=system)]
    for turn in history or []:
        role = turn.get("role")
        content = turn.get("content", "")
        if role == "user":
            messages.append(HumanMessage(content=content))
        elif role == "assistant":
            from langchain_core.messages import AIMessage

            messages.append(AIMessage(content=content))
    messages.append(HumanMessage(content=user_message))
    return messages


def _humanize_error(exc: Exception) -> str:
    """Turn raw provider errors into a short, user-friendly message."""
    text = str(exc).lower()
    if "tool_use_failed" in text or "failed to call a function" in text:
        return (
            "Sorry, I had trouble processing that request just now. "
            "Please rephrase it or try again in a moment."
        )
    if "rate limit" in text or "429" in text or "rate_limit" in text:
        return (
            "I'm receiving a lot of requests right now and hit a usage limit. "
            "Please try again in a little while."
        )
    return "Sorry, something went wrong while handling your request. Please try again."


def run_agent(
    user_message: str,
    customer_id: Optional[str] = None,
    history: Optional[list[dict]] = None,
) -> dict:
    """Run the agent loop and return the final reply plus tool-call trace."""
    messages = build_initial_messages(user_message, customer_id, history)
    try:
        result = get_agent_graph().invoke({"messages": messages})
    except Exception as exc:
        return {"reply": _humanize_error(exc), "decision": None, "tool_calls": []}
    final_messages = result["messages"]

    reply = ""
    tool_calls: list[dict] = []
    decision = None
    for msg in final_messages:
        for tc in getattr(msg, "tool_calls", None) or []:
            tool_calls.append({"name": tc.get("name"), "args": tc.get("args")})
            if tc.get("name") == "submit_refund_decision":
                decision = (tc.get("args") or {}).get("decision")
    # Final assistant text is the last AI message with content
    for msg in reversed(final_messages):
        if msg.__class__.__name__ == "AIMessage" and isinstance(msg.content, str) and msg.content.strip():
            reply = msg.content
            break

    return {"reply": reply, "decision": decision, "tool_calls": tool_calls}


def stream_agent(
    user_message: str,
    customer_id: Optional[str] = None,
    history: Optional[list[dict]] = None,
):
    """Stream the agent's reasoning steps as they happen.

    Yields event dicts of these shapes:
      {"type": "thinking"}
      {"type": "tool_call", "name": str, "args": dict}
      {"type": "tool_result", "name": str, "output": str}
      {"type": "final", "reply": str, "decision": str | None}
    """
    messages = build_initial_messages(user_message, customer_id, history)
    decision = None
    reply = ""

    try:
        for update in get_agent_graph().stream({"messages": messages}, stream_mode="updates"):
            for node, payload in update.items():
                for msg in payload.get("messages", []):
                    cls = msg.__class__.__name__
                    if cls == "AIMessage":
                        tcs = getattr(msg, "tool_calls", None) or []
                        if tcs:
                            for tc in tcs:
                                if tc.get("name") == "submit_refund_decision":
                                    decision = (tc.get("args") or {}).get("decision")
                                yield {"type": "tool_call", "name": tc.get("name"), "args": tc.get("args")}
                        elif isinstance(msg.content, str) and msg.content.strip():
                            reply = msg.content
                    elif cls == "ToolMessage":
                        yield {
                            "type": "tool_result",
                            "name": getattr(msg, "name", "tool"),
                            "output": msg.content if isinstance(msg.content, str) else str(msg.content),
                        }
    except Exception as exc:
        friendly = _humanize_error(exc)
        yield {"type": "tool_result", "name": "—", "output": f"Error: {exc}"}
        yield {"type": "final", "reply": friendly, "decision": None}
        return

    yield {"type": "final", "reply": reply, "decision": decision}
