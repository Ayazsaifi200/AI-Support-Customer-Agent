"""FastAPI application entrypoint for the AI Customer Support Agent backend."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import chat, crm, refunds, voice

settings = get_settings()

app = FastAPI(
    title="AI Customer Support Agent",
    description=(
        "Backend for an AI agent that approves or denies e-commerce refunds using "
        "a LangGraph agent loop, a strict policy engine, Supabase CRM data, and an "
        "ElevenLabs voice pipeline (speech-to-text + text-to-speech)."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(crm.router)
app.include_router(refunds.router)
app.include_router(chat.router)
app.include_router(voice.router)


@app.get("/", tags=["health"])
def root():
    return {
        "name": "AI Customer Support Agent",
        "status": "ok",
        "env": settings.app_env,
        "docs": "/docs",
        "endpoints": {
            "agent_chat": "POST /agent/chat",
            "refund_decide": "POST /refunds/decide",
            "customers": "GET /crm/customers",
            "orders": "GET /crm/orders",
            "policy": "GET /crm/policy",
            "voice_talk": "POST /voice/talk",
            "voice_tts": "POST /voice/tts",
            "voice_stt": "POST /voice/stt",
        },
    }


@app.get("/health", tags=["health"])
def health():
    return {"status": "healthy"}
