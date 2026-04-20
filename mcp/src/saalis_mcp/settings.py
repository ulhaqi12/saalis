from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SAALIS_MCP_", case_sensitive=False)

    transport: str = "stdio"   # "stdio" | "http"
    host: str = "0.0.0.0"
    port: int = 3000

    strategy: str = "weighted_vote"
    audit_path: str = "./saalis_mcp_audit.db"

    llm_model: str = "gpt-4o"
    llm_base_url: str | None = None
    llm_api_key: str | None = None

    min_confidence: float | None = None
    blocklist_agents: str = ""

    def blocklist(self) -> list[str]:
        return [a.strip() for a in self.blocklist_agents.split(",") if a.strip()]
