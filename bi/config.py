"""Central configuration, loaded from environment / .env via pydantic-settings.

Both the app and the standalone MCP servers import `settings` from here so they
share one source of truth for the YugabyteDB connection and LLM/Langfuse keys.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- MCP 1: YugabyteDB ---
    yb_host: str = ""
    yb_port: int = 5433
    yb_database: str = "yugabyte"
    yb_user: str = "yugabyte"
    yb_password: str = ""
    yb_sslmode: str = "prefer"
    yb_sslrootcert: str = ""  # path to CA cert; required for verify-ca / verify-full
    yb_schema: str = "public"

    mcp_yugabyte_url: str = "http://127.0.0.1:8000/mcp"
    mcp_yugabyte_host: str = "127.0.0.1"
    mcp_yugabyte_port: int = 8000

    # --- MCP 3: Python/ML (forecasting) ---
    mcp_ml_url: str = "http://127.0.0.1:8001/mcp"
    mcp_ml_host: str = "127.0.0.1"
    mcp_ml_port: int = 8001

    # --- LLM (Agents 3 & 6) ---
    llm_provider: str = "anthropic"
    anthropic_api_key: str = ""
    claude_model: str = "claude-opus-4-8"
    local_model: str = "llama3.1"
    ollama_base_url: str = "http://localhost:11434"

    # --- Langfuse ---
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"

    # ------------------------------------------------------------------ #
    @property
    def db_configured(self) -> bool:
        """True when a real YugabyteDB host has been provided."""
        return bool(self.yb_host.strip())

    @property
    def langfuse_configured(self) -> bool:
        return bool(self.langfuse_public_key and self.langfuse_secret_key)

    @property
    def llm_configured(self) -> bool:
        """Whether a real (non-mock) LLM can be constructed."""
        if self.llm_provider == "anthropic":
            return bool(self.anthropic_api_key)
        return True  # local providers (ollama) need no key

    def conninfo(self) -> str:
        """libpq connection string for psycopg.

        `sslrootcert` is only appended when set — `verify-ca` / `verify-full`
        require it, while `require` and below do not.
        """
        parts = [
            f"host={self.yb_host}",
            f"port={self.yb_port}",
            f"dbname={self.yb_database}",
            f"user={self.yb_user}",
            f"password={self.yb_password}",
            f"sslmode={self.yb_sslmode}",
        ]
        if self.yb_sslrootcert:
            parts.append(f"sslrootcert={self.yb_sslrootcert}")
        return " ".join(parts)


settings = Settings()
