from .groq_config import get_groq_api_key


def get_openai_key():
    """Backward-compatible shim for older imports."""
    return get_groq_api_key()
