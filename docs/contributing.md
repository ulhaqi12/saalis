# Contributing

Contributions are welcome — bug fixes, new strategies, integration adapters, docs improvements.

## Setup

```bash
git clone https://github.com/ulhaqi12/saalis
cd saalis
uv sync --all-packages --extra dev
```

This installs the core library, sidecar, MCP server, and all dev dependencies into a single virtual environment.

## Project layout

```
saalis/
├── src/saalis/              ← core library
│   ├── models.py            ← all Pydantic models
│   ├── strategy.py          ← Strategy ABC + built-in strategies
│   ├── arbitrator.py        ← Arbitrator orchestration
│   ├── policy.py            ← PolicyEngine + built-in rules
│   ├── wiring.py            ← build_arbitrator() factory
│   └── audit/               ← AuditStore implementations
│       ├── base.py
│       ├── jsonl.py
│       └── sqlite.py
│   └── integrations/        ← framework adapters
│       ├── langgraph.py
│       └── crewai.py
├── tests/                   ← core library tests
├── sidecar/                 ← HTTP REST transport
│   ├── src/saalis_sidecar/
│   └── tests/
├── mcp/                     ← MCP transport
│   ├── src/saalis_mcp/
│   └── tests/
└── examples/                ← runnable demos
```

## Before submitting a PR

```bash
make all   # fmt + lint + typecheck (lib + sidecar + mcp) + test (lib + sidecar + mcp)
```

All checks must pass. CI runs the same suite on Python 3.11 and 3.12.

Individual targets:

```bash
make test             # lib tests with coverage
make test-sidecar     # sidecar tests
make test-mcp         # MCP tests
make lint             # ruff on lib
make typecheck        # mypy on lib
make fmt              # auto-format everything
```

## Adding a strategy

1. Subclass `Strategy` in `src/saalis/strategy.py`
2. Implement `name: str` (class attribute) and `async def resolve(decision) -> Verdict`
3. Add the strategy to `build_strategy()` in `src/saalis/wiring.py` so it's available via `build_arbitrator()` and both transports
4. Add tests in `tests/`
5. Export from `src/saalis/__init__.py` if it should be part of the public API
6. Document in [Strategies](strategies.md)

## Adding a policy rule

1. Subclass `PolicyRule` in `src/saalis/policy.py`
2. Implement `check_pre` and/or `check_post` — return `None` to pass, `PolicyDecision(allowed=False, ...)` to block
3. Add tests in `tests/`
4. Document in [Policy Enforcement](policy.md)

## Adding an integration adapter

1. Create `src/saalis/integrations/<framework>.py`
2. Duck-type the framework's tool/node interface — **do not import the framework itself**
3. Add tests in `tests/test_<framework>_adapter.py`
4. Export from `src/saalis/integrations/__init__.py`
5. Document in `docs/integrations/<framework>.md` and add to `mkdocs.yml` nav

## Code style

- **No comments** unless the _why_ is non-obvious (a hidden constraint, a known bug workaround)
- **No docstrings** on simple methods where the name says it all
- `ruff` for formatting and linting — `make fmt` fixes everything automatically
- `mypy --strict` must pass — annotate all public functions

## Versioning

Bump the version in `pyproject.toml` (root, `sidecar/`, and `mcp/`) before merging. Follow semantic versioning:

- **patch** — bug fixes, no API changes
- **minor** — new features, backwards-compatible

Merging to `main` automatically publishes to PyPI if the version is new.

## Reporting issues

Open an issue at [github.com/ulhaqi12/saalis/issues](https://github.com/ulhaqi12/saalis/issues).
