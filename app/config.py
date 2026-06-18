"""Application configuration loaded from environment variables."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Supabase
    supabase_url: str
    supabase_service_key: str

    # Groq (used for the LangGraph LLM reasoning / tool-calling)
    groq_api_key: str = ""
    groq_chat_model: str = "llama-3.3-70b-versatile"

    # ElevenLabs (voice pipeline: speech-to-text + text-to-speech)
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = "pNInz6obpgDQGcFmaJgB"  # "Adam" (works on free tier)
    elevenlabs_tts_model: str = "eleven_multilingual_v2"
    elevenlabs_stt_model: str = "scribe_v1"

    # App
    app_env: str = "development"


@lru_cache
def get_settings() -> Settings:
    return Settings()
