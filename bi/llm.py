"""LLM factory — the single provider-swap seam.

Agents 3 (Suggestion) and 6 (Insight) call `get_llm()` rather than importing a
provider directly. Switching to a local model later is a one-line env change
(`LLM_PROVIDER=ollama`), with no agent code touched.

Returns `None` when no real LLM is configured (e.g. ANTHROPIC_API_KEY unset), so
callers can fall back to deterministic mock output and the app still runs offline.

Note: newer Claude models (e.g. Opus 4.x) reject the `temperature` parameter, so
it is only sent when a caller explicitly passes one (default: omitted).
"""

from __future__ import annotations

from typing import Optional

from langchain_core.language_models import BaseChatModel

from bi.config import settings


def get_llm(
    role: str = "default", temperature: Optional[float] = None
) -> Optional[BaseChatModel]:
    provider = settings.llm_provider.lower()

    if provider == "anthropic":
        if not settings.anthropic_api_key:
            return None
        from langchain_anthropic import ChatAnthropic

        kwargs = {
            "model": settings.claude_model,
            "api_key": settings.anthropic_api_key,
            "max_tokens": 2048,
        }
        if temperature is not None:
            kwargs["temperature"] = temperature
        return ChatAnthropic(**kwargs)

    if provider == "ollama":
        from langchain_ollama import ChatOllama

        kwargs = {
            "model": settings.local_model,
            "base_url": settings.ollama_base_url,
        }
        if temperature is not None:
            kwargs["temperature"] = temperature
        return ChatOllama(**kwargs)

    raise ValueError(f"Unknown LLM_PROVIDER: {settings.llm_provider!r}")
