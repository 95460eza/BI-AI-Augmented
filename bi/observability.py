"""Langfuse wiring.

One `CallbackHandler` is attached to each graph invocation. LangChain propagates
callbacks down the run tree, so every agent node, LLM call, and MCP tool call
becomes a nested span under a single trace — matching the per-agent span spec in
the architecture diagram (input prompt, output, latency, tokens, tool calls,
errors/retries, cost).

If Langfuse keys are not configured the app still runs; it is simply untraced.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any, Optional

from bi.config import settings


@lru_cache(maxsize=1)
def get_client() -> Optional[Any]:
    """Initialise (once) and return the default Langfuse client, or None."""
    if not settings.langfuse_configured:
        return None
    from langfuse import Langfuse

    return Langfuse(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key,
        host=settings.langfuse_host,
    )


def new_trace_id() -> Optional[str]:
    client = get_client()
    if client is None:
        return None
    return client.create_trace_id()


def get_callback_handler(trace_id: Optional[str] = None) -> Optional[Any]:
    """Return a Langfuse LangChain callback handler bound to `trace_id`, or None."""
    if get_client() is None:
        return None
    from langfuse.langchain import CallbackHandler

    if trace_id:
        return CallbackHandler(trace_context={"trace_id": trace_id})
    return CallbackHandler()


def trace_url(trace_id: Optional[str]) -> Optional[str]:
    client = get_client()
    if client is None or not trace_id:
        return None
    try:
        return client.get_trace_url(trace_id=trace_id)
    except Exception:
        return f"{settings.langfuse_host.rstrip('/')}/trace/{trace_id}"


def flush() -> None:
    client = get_client()
    if client is not None:
        client.flush()
