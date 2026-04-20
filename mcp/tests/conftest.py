from __future__ import annotations

import pytest
from saalis.arbitrator import Arbitrator
from saalis.audit.sqlite import SQLiteAuditStore
from saalis.strategy import DeferToHuman, WeightedVote

from saalis_mcp.state import AppState


@pytest.fixture
async def sqlite_store(tmp_path):
    store = SQLiteAuditStore(f"sqlite+aiosqlite:///{tmp_path}/test.db")
    yield store
    await store.close()


@pytest.fixture
def weighted_state(sqlite_store):
    arb = Arbitrator(strategies=[WeightedVote()], audit_store=sqlite_store)
    return AppState(arbitrator=arb, audit_store=sqlite_store)


@pytest.fixture
def deferred_state(sqlite_store):
    arb = Arbitrator(
        strategies=[DeferToHuman(reason="Needs human review")], audit_store=sqlite_store
    )
    return AppState(arbitrator=arb, audit_store=sqlite_store)
