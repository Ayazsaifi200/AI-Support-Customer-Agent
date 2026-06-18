# AI Customer Support Agent — Backend

A fully functional backend for an AI agent that **approves or denies e-commerce
refunds**. It combines:

- **FastAPI** — REST + WebSocket API
- **LangGraph** — a ReAct-style agent loop that dynamically calls tools
- **Groq (Llama 3.3 70B)** — fast LLM reasoning + tool calling for the agent
- **Deterministic policy engine** — strict refund rules the LLM cannot override
- **Supabase (PostgreSQL)** — CRM data (customers, orders, refund policy, refund requests)
- **ElevenLabs API** — voice pipeline (speech-to-text via Scribe + text-to-speech)

## Architecture

```
Client (text/voice)
      │
      ▼
FastAPI (app/main.py)
 ├── /agent/chat ────────► LangGraph agent loop (app/agent/graph.py)
 │                              │  reasons + calls tools
 │                              ▼
 │                         Tools (app/agent/tools.py)
 │                              │
 ├── /refunds/decide ──► Policy engine (app/policy.py)  ◄── strict rules
 │                              │
 ├── /crm/* ───────────► CRM data layer (app/crm.py)
 │                              │
 └── /voice/* ─────────► ElevenLabs STT + TTS (app/routers/voice.py)
                                ▼
                        Supabase PostgreSQL
```

The LLM never decides a refund. It must call `check_refund_eligibility`, which
runs the deterministic engine in [app/policy.py](app/policy.py). This keeps every
financial decision auditable and immune to prompt-injection.

## Data model (Supabase)

| Table | Columns |
|-------|---------|
| `customers` | id, name, email, phone, tier (gold/silver/bronze), total_orders, created_at |
| `orders` | id, customer_id, product_name, amount, order_date, status |
| `refund_policy` | id, rule_name, description, max_days, eligible_tiers |
| `refund_requests` | id, order_id, customer_id, reason, status, requested_at, resolved_at |

15 customer profiles and 5 policy rules already exist. Orders are seeded by
[seed_orders.py](seed_orders.py).

## Refund policy (strict)

See [data/refund_policy.md](data/refund_policy.md). Rule precedence:

1. **Order Status Guard** — cancelled/refunded → denied
2. **Digital Products** — never refundable
3. **Damaged Goods** — full refund within 90 days
4. **Late Delivery** — full refund if delivery > 14 business days
5. **Gold Member Bonus** — 60-day window for gold tier, unused items
6. **Standard Return** — 30 days, unused & original packaging, all tiers

## Setup

```powershell
# 1. Create & activate the virtual environment (already done in this workspace)
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
copy .env.example .env   # then fill in GROQ_API_KEY (Supabase values are pre-filled)

# 4. Seed orders (customers & policy already exist in Supabase)
python seed_orders.py

# 5. Run the server
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000/docs for interactive Swagger UI.

## Key endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/crm/customers` | List 15 customer profiles |
| GET | `/crm/customers/{id}/orders` | Orders for a customer |
| GET | `/crm/orders` | All orders |
| GET | `/crm/policy` | Refund policy rules |
| GET | `/crm/refund-requests` | Refund decision history |
| POST | `/refunds/decide` | Deterministic refund decision (no LLM) |
| POST | `/agent/chat` | Talk to the LangGraph agent (needs `GROQ_API_KEY`) |
| POST | `/voice/talk` | Voice turn: audio in → agent → spoken reply (audio out) |
| POST | `/voice/tts` | Text → spoken audio (ElevenLabs) |
| POST | `/voice/stt` | Audio → transcript (ElevenLabs Scribe) |

### Example: deterministic decision

```http
POST /refunds/decide
{
  "order_id": "<uuid>",
  "reason": "Arrived damaged",
  "product_type": "physical",
  "condition": "damaged"
}
```

### Example: agent chat

```http
POST /agent/chat
{
  "message": "I want to return order <uuid>, it arrived broken",
  "customer_id": "<uuid>"
}
```

The agent will look up the customer/order, call the policy engine, record the
decision in `refund_requests`, and reply citing the matched rule.

## Voice pipeline (ElevenLabs API)

The voice flow is: **audio in → STT (ElevenLabs Scribe) → LangGraph agent → TTS
(ElevenLabs) → audio out**.

- `POST /voice/stt` — upload audio, get a transcript (ElevenLabs Scribe).
- `POST /voice/tts` — send text, get spoken MP3 audio back.
- `POST /voice/talk` — upload a spoken refund request; the backend transcribes
  it, runs the LangGraph agent (which enforces the refund policy), and returns
  the agent's spoken reply as MP3. The transcript, text reply and decision are
  returned in the `X-Transcript`, `X-Reply` and `X-Decision` headers.

`/voice/stt` and `/voice/tts` require `ELEVENLABS_API_KEY`. `/voice/talk` also
needs `GROQ_API_KEY` for the agent's reasoning step.

> ElevenLabs free tier note: some premade "library" voices (e.g. Rachel) are
> blocked for free API users. The default `ELEVENLABS_VOICE_ID` is set to a
> free-tier-compatible voice (Adam). Change it in `.env` to any voice your plan
> allows.

## Security note

The Supabase **service/secret key** has full database access, and the Groq and
ElevenLabs keys are billable credentials. Keep `.env` out of version control (it
is git-ignored). Since these keys were shared in plain text, consider rotating
them in their respective dashboards.
