"""Factory helpers for assembling an Arbitrator from flat config values.

Both the REST sidecar and MCP server share identical strategy-selection and
policy-construction logic. This module owns that logic once; each transport's
``state.py`` calls ``build_arbitrator()`` with the values it reads from env vars.
"""
from __future__ import annotations

from saalis.arbitrator import Arbitrator
from saalis.audit.base import AuditStore, NullAuditStore
from saalis.policy import BlocklistAgentRule, MinConfidenceRule, PolicyEngine, PolicyRule
from saalis.strategy import DeferToHuman, LLMJudge, Strategy, WeightedVote


def build_strategy(
    strategy: str = "weighted_vote",
    llm_model: str = "gpt-4o",
    llm_base_url: str | None = None,
    llm_api_key: str | None = None,
) -> Strategy:
    name = strategy.lower()
    if name == "llm_judge":
        return LLMJudge(model=llm_model, base_url=llm_base_url, api_key=llm_api_key)
    if name == "defer_to_human":
        return DeferToHuman()
    return WeightedVote()


def build_policy(
    min_confidence: float | None = None,
    blocklist_agents: list[str] | None = None,
) -> PolicyEngine:
    rules: list[PolicyRule] = []
    if min_confidence is not None:
        rules.append(MinConfidenceRule(threshold=min_confidence))
    if blocklist_agents:
        rules.append(BlocklistAgentRule(blocklist=blocklist_agents))
    return PolicyEngine(rules=rules)


def build_arbitrator(
    strategy: str = "weighted_vote",
    audit_store: AuditStore | None = None,
    llm_model: str = "gpt-4o",
    llm_base_url: str | None = None,
    llm_api_key: str | None = None,
    min_confidence: float | None = None,
    blocklist_agents: list[str] | None = None,
) -> Arbitrator:
    return Arbitrator(
        strategies=[build_strategy(strategy, llm_model, llm_base_url, llm_api_key)],
        policy_engine=build_policy(min_confidence, blocklist_agents),
        audit_store=audit_store or NullAuditStore(),
    )
