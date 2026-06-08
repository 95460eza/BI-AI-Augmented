"""MCP client wiring (langchain-mcp-adapters).

Connects to the standalone MCP servers over streamable-HTTP and returns their
tools as LangChain tools that the agent nodes can call. HTTP transport is
stateless per call, so the returned tools are safe to reuse across the separate
asyncio runs that Streamlit triggers (discovery, then resume-after-approval).
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient

from bi.config import settings


def _server_config() -> Dict[str, Dict[str, str]]:
    return {
        "yugabyte": {  # MCP 1
            "url": settings.mcp_yugabyte_url,
            "transport": "streamable_http",
        },
        "ml": {  # MCP 3
            "url": settings.mcp_ml_url,
            "transport": "streamable_http",
        },
    }


async def get_mcp_tools() -> List[BaseTool]:
    """Load tools from each MCP server independently.

    Servers are queried one at a time so that an unreachable server (e.g. the ML
    server not yet started) only drops its own tools; the agents that depend on
    them fall back to local implementations and the graph still runs.
    """
    tools: List[BaseTool] = []
    for name, cfg in _server_config().items():
        try:
            client = MultiServerMCPClient({name: cfg})
            tools.extend(await client.get_tools())
        except Exception as exc:  # noqa: BLE001
            print(f"[mcp_client] WARNING: server {name!r} unavailable: {exc}")
    return tools


def tools_by_name(tools: List[BaseTool]) -> Dict[str, BaseTool]:
    return {t.name: t for t in tools}


def parse_tool_result(raw: Any) -> Any:
    """Normalize a LangChain MCP tool result into a Python object.

    The adapter may return a raw string, or a list of MCP content blocks like
    ``[{"type": "text", "text": "..."}]``. We extract the text and JSON-decode it.
    """
    text: str
    if isinstance(raw, str):
        text = raw
    elif isinstance(raw, list):
        parts = [
            b.get("text", "")
            for b in raw
            if isinstance(b, dict) and b.get("type") == "text"
        ]
        text = "".join(parts) if parts else json.dumps(raw)
    elif isinstance(raw, dict):
        return raw
    else:
        text = str(raw)

    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return text
