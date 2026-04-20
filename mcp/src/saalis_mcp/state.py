from __future__ import annotations

from dataclasses import dataclass, field

from saalis.arbitrator import Arbitrator
from saalis.audit.sqlite import SQLiteAuditStore
from saalis.models import Verdict
from saalis.wiring import build_arbitrator

from saalis_mcp.settings import Settings


@dataclass
class AppState:
    arbitrator: Arbitrator
    audit_store: SQLiteAuditStore
    verdict_cache: dict[str, Verdict] = field(default_factory=dict)


def build_state(settings: Settings) -> AppState:
    audit_store = SQLiteAuditStore(f"sqlite+aiosqlite:///{settings.audit_path}")
    arbitrator = build_arbitrator(
        strategy=settings.strategy,
        audit_store=audit_store,
        llm_model=settings.llm_model,
        llm_base_url=settings.llm_base_url,
        llm_api_key=settings.llm_api_key,
        min_confidence=settings.min_confidence,
        blocklist_agents=settings.blocklist(),
    )
    return AppState(arbitrator=arbitrator, audit_store=audit_store)
