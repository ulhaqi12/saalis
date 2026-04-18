"""LangGraph adapter for Saalis.

Usage::

    from langgraph.graph import StateGraph
    from typing import TypedDict
    from saalis.integrations.langgraph import ArbitrationNode
    from saalis.strategy import WeightedVote

    class AgentState(TypedDict):
        question: str
        proposals: list
        agents: list
        verdict: object

    node = ArbitrationNode(strategies=[WeightedVote()])

    graph = StateGraph(AgentState)
    graph.add_node("arbitrate", node)

``ArbitrationNode`` is a plain async callable — it requires no LangGraph
import and works with any framework that follows the node protocol
(async function receiving a state dict, returning a partial state update).
"""

from __future__ import annotations

from typing import Any

from saalis.arbitrator import Arbitrator
from saalis.audit.base import AuditStore
from saalis.models import Agent, Decision, Proposal, Verdict
from saalis.policy import PolicyEngine
from saalis.strategy import Strategy, WeightedVote


class ArbitrationNode:
    """A LangGraph-compatible node that arbitrates between agent proposals.

    Reads ``question``, ``proposals``, and ``agents`` from the graph state,
    runs arbitration, and writes the resulting ``Verdict`` back under
    ``verdict_key``.

    All state keys are configurable so the node can be dropped into any
    existing graph state schema.
    """

    def __init__(
        self,
        strategies: list[Strategy] | None = None,
        policy_engine: PolicyEngine | None = None,
        audit_store: AuditStore | None = None,
        question_key: str = "question",
        proposals_key: str = "proposals",
        agents_key: str = "agents",
        verdict_key: str = "verdict",
        context_key: str | None = "context",
    ) -> None:
        self._arbitrator = Arbitrator(
            strategies=strategies or [WeightedVote()],
            policy_engine=policy_engine,
            audit_store=audit_store,
        )
        self._question_key = question_key
        self._proposals_key = proposals_key
        self._agents_key = agents_key
        self._verdict_key = verdict_key
        self._context_key = context_key

    async def __call__(self, state: dict[str, Any]) -> dict[str, Any]:
        question: str = state[self._question_key]

        raw_proposals: list[Any] = state.get(self._proposals_key, [])
        proposals = [
            p if isinstance(p, Proposal) else Proposal.model_validate(p)
            for p in raw_proposals
        ]

        raw_agents: list[Any] = state.get(self._agents_key, [])
        agents = [
            a if isinstance(a, Agent) else Agent.model_validate(a)
            for a in raw_agents
        ]

        context: dict[str, Any] = {}
        if self._context_key:
            raw_ctx = state.get(self._context_key)
            if isinstance(raw_ctx, dict):
                context = raw_ctx

        decision = Decision(
            question=question,
            proposals=proposals,
            agents=agents,
            context=context,
        )

        verdict: Verdict = await self._arbitrator.arbitrate(decision)
        return {self._verdict_key: verdict}
