from __future__ import annotations

from dataclasses import dataclass

from saalis.arbitrator import Arbitrator
from saalis.audit.sqlite import SQLiteAuditStore
from saalis.policy import BlocklistAgentRule, MinConfidenceRule, PolicyEngine
from saalis.strategy import DeferToHuman, LLMJudge, WeightedVote

from saalis_sidecar.settings import Settings


@dataclass
class AppState:
    arbitrator: Arbitrator
    audit_store: SQLiteAuditStore


def build_state(settings: Settings) -> AppState:
    audit_store = SQLiteAuditStore(
        f"sqlite+aiosqlite:///{settings.audit_path}"
    )

    rules = []
    if settings.min_confidence is not None:
        rules.append(MinConfidenceRule(threshold=settings.min_confidence))
    if settings.blocklist():
        rules.append(BlocklistAgentRule(blocklist=settings.blocklist()))
    policy = PolicyEngine(rules=rules)

    strategy_name = settings.strategy.lower()
    if strategy_name == "llm_judge":
        strategy = LLMJudge(
            model=settings.llm_model,
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
        )
    elif strategy_name == "defer_to_human":
        strategy = DeferToHuman()
    else:
        strategy = WeightedVote()

    arbitrator = Arbitrator(
        strategies=[strategy],
        policy_engine=policy,
        audit_store=audit_store,
    )
    return AppState(arbitrator=arbitrator, audit_store=audit_store)
