from openai import OpenAI

from .config import get_settings


def get_llm_client() -> OpenAI:
    """OpenAI-compatible client. Set OPENAI_BASE_URL to use Gemini or another compatible provider."""
    s = get_settings()
    # Retries cover transient 429/503 responses from the provider (e.g. Gemini "high demand").
    return OpenAI(api_key=s.openai_api_key, base_url=s.openai_base_url or None, max_retries=4, timeout=60)
