# AI Customer Support Agent

An end-to-end AI agent that **approves or denies e-commerce refunds** over text
**and voice**, backed by a real database and a deterministic policy engine the
LLM cannot override.

🔗 **Repository:** https://github.com/Ayazsaifi200/AI-Support-Customer-Agent
🎥 **Loom walkthrough:** _<add your Loom/Drive video link here>_

### Highlights
- 💬 **Text + 🎤 voice chat** — speak a request and hear the spoken reply (full STT → agent → TTS loop)
- 🧠 **LangGraph ReAct agent** that looks up real CRM data and orchestrates 6 tools
- 🛡️ **"Holds the line"** — refund decisions come from a deterministic engine, so policy can't be bypassed by persuasion or prompt injection
- 📊 **Admin dashboard** with live agent reasoning logs and real-time refund decisions
- ♻️ **Graceful failure handling** — provider errors (rate limits, malformed tool calls) become clean user messages while the raw trace stays in the logs

It combines:

- **Next.js** — chat UI, voice recorder, and admin dashboard (`frontend/`)
- **FastAPI** — REST + Server-Sent Events streaming API
- **LangGraph** — a ReAct-style agent loop that dynamically calls tools
- **Groq (Llama 3.3 70B)** — fast LLM reasoning + tool calling for the agent
- **Deterministic policy engine** — strict refund rules the LLM cannot override
- **Supabase (PostgreSQL)** — CRM data (customers, orders, refund policy, refund requests)
- **ElevenLabs API** — voice pipeline (speech-to-text via Scribe + text-to-speech)

## Architecture

```
Next.js frontend (frontend/)
 ├── ChatPanel  (text + 🎤 voice: STT → agent → 🔊 TTS auto-play)
 └── AdminDashboard (live reasoning log + refund decisions)
      │  HTTP / SSE
      ▼
FastAPI (app/main.py)
 ├── /agent/chat, /agent/chat/stream ─► LangGraph agent loop (app/agent/graph.py)
 │                                          │  reasons + calls tools (streamed via SSE)
 │                                          ▼
 │                                     Tools (app/agent/tools.py)
 │                                          │
 ├── /refunds/decide ──────────────► Policy engine (app/policy.py)  ◄── strict rules
 │                                          │
 ├── /crm/* ───────────────────────► CRM data layer (app/crm.py)
 │                                          │
 └── /voice/* ─────────────────────► ElevenLabs STT + TTS (app/routers/voice.py)
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

### Backend (FastAPI)

```powershell
# 1. Create & activate the virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
copy .env.example .env   # then fill in GROQ_API_KEY + ELEVENLABS_API_KEY (Supabase values are pre-filled)

# 4. Seed orders (customers & policy already exist in Supabase)
python seed_orders.py

# 5. Run the API
uvicorn app.main:app --reload   # http://127.0.0.1:8000
```

Open http://127.0.0.1:8000/docs for interactive Swagger UI.

### Frontend (Next.js)

```powershell
cd frontend
npm install
npm run dev                          # http://localhost:3000
```

Create `frontend/.env.local` with:

```
NEXT_PUBLIC_API_BASE=http://127.0.0.1:8000
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-supabase-anon-key
```

Open http://localhost:3000 — the **Customer Chat** tab for text/voice, the
**Admin Dashboard** tab for live reasoning logs and refund decisions.

## Demo scenarios (for the walkthrough)

Pick the customer in the dropdown, then type or speak the message. Outcomes are
backed by real seeded orders.

| # | Customer | Message | Expected |
|---|----------|---------|----------|
| 1 — Standard refund ✅ | Bob Smith · silver | "I want a refund for my Wireless Headphones. They're unused and in original packaging." | **Approved** (Standard Return, within 30 days) |
| 2 — Policy violation ❌ | James Anderson · gold | "I bought the Online Course just 6 days ago and I want my money back." → then "Come on, I'm a gold member, make an exception." | **Denied** & holds the line (Digital Products rule, no override) |
| 3 — Voice 🎤🔊 | Alice Johnson · gold | _(spoken)_ "I want a refund for my damaged vase. It arrived broken." | **Approved** spoken reply (Damaged Goods, within 90 days) |

## Reasoning logs & failure handling

- **Live reasoning log** — the agent streams every step over Server-Sent Events
  (`POST /agent/chat/stream`): each `tool_call`, each `tool_result`, and the
  `final` decision. The **Admin Dashboard** renders this in real time, alongside
  refund decisions written to Postgres (with a live/polling indicator).
- **Graceful failures** — `stream_agent`/`run_agent` in
  [app/agent/graph.py](app/agent/graph.py) wrap the agent run; `_humanize_error()`
  converts raw provider errors (e.g. Groq rate limits or a `tool_use_failed`
  malformed tool call) into a clean customer-facing message, while the raw error
  is still surfaced in the reasoning log and the backend terminal trace for
  debugging.

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
