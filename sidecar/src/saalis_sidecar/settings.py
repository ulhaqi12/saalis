from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SAALIS_", case_sensitive=False)

    strategy: str = "weighted_vote"
    audit_store: str = "sqlite"
    audit_path: str = "./saalis_audit.db"

    llm_model: str = "gpt-4o"
    llm_base_url: str | None = None
    llm_api_key: str | None = None

    min_confidence: float | None = None
    blocklist_agents: str = ""

    # Empty string = auth disabled (dev mode)
    bearer_token: str = ""

    def blocklist(self) -> list[str]:
        return [a.strip() for a in self.blocklist_agents.split(",") if a.strip()]
