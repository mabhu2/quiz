from __future__ import annotations

import os
import ssl
from functools import lru_cache
from pathlib import Path

import httpx
from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BACKEND_DIR / ".env")

DEFAULT_GROQ_BASE_URL = "https://api.groq.com/openai/v1"
DEFAULT_GROQ_MODEL = "llama-3.1-8b-instant"
DEFAULT_GROQ_FALLBACK_MODELS = "llama-3.1-8b-instant,llama-3.3-70b-versatile"


@lru_cache
def get_groq_api_key() -> str:
    return (os.getenv("GROQ_API_KEY") or "").strip()


@lru_cache
def get_groq_base_url() -> str:
    return (os.getenv("GROQ_BASE_URL") or DEFAULT_GROQ_BASE_URL).strip()


@lru_cache
def get_groq_model() -> str:
    return (os.getenv("GROQ_MODEL") or DEFAULT_GROQ_MODEL).strip()


@lru_cache
def get_groq_models() -> tuple[str, ...]:
    configured_models = [
        get_groq_model(),
        *(
            model.strip()
            for model in (
                os.getenv("GROQ_FALLBACK_MODELS") or DEFAULT_GROQ_FALLBACK_MODELS
            ).split(",")
        ),
    ]

    models: list[str] = []
    seen: set[str] = set()
    for model in configured_models:
        if model and model not in seen:
            models.append(model)
            seen.add(model)
    return tuple(models)


@lru_cache
def use_local_quiz_fallback() -> bool:
    value = (os.getenv("ENABLE_LOCAL_QUIZ_FALLBACK") or "true").strip().lower()
    return value not in {"0", "false", "no", "off"}


def require_groq_api_key() -> str:
    api_key = get_groq_api_key()
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is not configured.")
    return api_key


def create_groq_http_client() -> httpx.AsyncClient:
    timeout_seconds = float(os.getenv("GROQ_TIMEOUT_SECONDS", "75"))
    connect_timeout_seconds = float(os.getenv("GROQ_CONNECT_TIMEOUT_SECONDS", "20"))
    ca_bundle = (os.getenv("GROQ_CA_BUNDLE") or os.getenv("SSL_CERT_FILE") or "").strip()

    if ca_bundle:
        verify: str | ssl.SSLContext | bool = ca_bundle
    else:
        verify = _system_ssl_context()

    return httpx.AsyncClient(
        timeout=httpx.Timeout(timeout_seconds, connect=connect_timeout_seconds),
        verify=verify,
        trust_env=True,
    )


def _system_ssl_context() -> ssl.SSLContext | bool:
    try:
        import truststore
    except ImportError:
        return True

    return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
