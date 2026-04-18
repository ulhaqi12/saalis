"""CrewAI adapter for Saalis.

Usage::

    from crewai.tools import BaseTool  # only needed in your app, not here
    from saalis.integrations.crewai import ArbitrationTool
    from saalis.strategy import WeightedVote

    tool = ArbitrationTool(strategies=[WeightedVote()])

    # Attach to a CrewAI agent:
    agent = Agent(role="...", tools=[tool])

``ArbitrationTool`` duck-types CrewAI's ``BaseTool`` interface (``name``,
``description``, ``_run``, ``_arun``) without importing ``crewai``. It works
with any framework that follows the same tool protocol.
"""

from __future__ import annotations

import asyncio
from typing import Any

from saalis.arbitrator import Arbitrator
from saalis.audit.base import AuditStore
from saalis.models import Agent, Decision, Proposal, Verdict
from saalis.policy import PolicyEngine
from saalis.strategy import Strategy, WeightedVote


class ArbitrationTool:
    """CrewAI-compatible tool that runs Saalis arbitration.

    Compatible with CrewAI's ``BaseTool`` protocol — ``name``, ``description``,
    ``_run``, and ``_arun`` — without requiring ``crewai`` to be installed.

    Args:
        strategies: Arbitration strategies. Defaults to ``[WeightedVote()]``.
        policy_engine: Optional policy engine for pre/post checks.
        audit_store: Optional audit store for logging.
        output_format: Verdict render format — ``"text"``, ``"markdown"``, or ``"json"``.
    """

    name: str = "saalis_arbitrate"
    description: str = (
        "Arbitrate between multiple AI agent proposals and return the winning verdict. "
        "Input: question (str), proposals (list of dicts with agent_id/content/confidence), "
        "agents (list of dicts with id/name/weight). "
        "Output: arbitration verdict as text."
    )

    def __init__(
        self,
        strategies: list[Strategy] | None = None,
        policy_engine: PolicyEngine | None = None,
        audit_store: AuditStore | None = None,
        output_format: str = "text",
    ) -> None:
        self._arbitrator = Arbitrator(
            strategies=strategies or [WeightedVote()],
            policy_engine=policy_engine,
            audit_store=audit_store,
        )
        self._output_format = output_format

    async def _arun(
        self,
        question: str,
        proposals: list[dict[str, Any]] | list[Proposal],
        agents: list[dict[str, Any]] | list[Agent] | None = None,
        context: dict[str, Any] | None = None,
    ) -> str:
        """Async entry point — called by async-capable frameworks."""
        parsed_proposals = [
            p if isinstance(p, Proposal) else Proposal.model_validate(p)
            for p in proposals
        ]
        parsed_agents = [
            a if isinstance(a, Agent) else Agent.model_validate(a)
            for a in (agents or [])
        ]

        decision = Decision(
            question=question,
            proposals=parsed_proposals,
            agents=parsed_agents,
            context=context or {},
        )

        verdict: Verdict = await self._arbitrator.arbitrate(decision)
        return verdict.render(self._output_format)

    def _run(
        self,
        question: str,
        proposals: list[dict[str, Any]] | list[Proposal],
        agents: list[dict[str, Any]] | list[Agent] | None = None,
        context: dict[str, Any] | None = None,
    ) -> str:
        """Sync entry point — CrewAI calls this when running in a thread pool."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(
                    asyncio.run,
                    self._arun(question, proposals, agents, context),
                )
                return future.result()

        return asyncio.run(self._arun(question, proposals, agents, context))
