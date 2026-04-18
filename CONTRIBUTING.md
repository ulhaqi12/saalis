# Contributing to Saalis

## Setup

```bash
git clone https://github.com/ulhaqi12/saalis
cd saalis
uv sync --all-packages --extra dev
```

## Making changes

- `src/saalis/` — core library
- `sidecar/src/saalis_sidecar/` — HTTP sidecar
- `tests/` — library tests
- `sidecar/tests/` — sidecar tests

## Before submitting a PR

```bash
make all   # fmt + lint + typecheck (lib + sidecar) + test (lib + sidecar)
```

All checks must pass. CI runs the same suite on Python 3.11 and 3.12.

## Adding a strategy

1. Subclass `Strategy` in `src/saalis/strategy.py`
2. Implement `name: str` (class attribute) and `async def resolve(decision) -> Verdict`
3. Add tests in `tests/`
4. Export from `src/saalis/__init__.py` if it should be part of the public API

## Adding an integration adapter

1. Create `src/saalis/integrations/<framework>.py`
2. Duck-type the framework's tool/node interface — do **not** import the framework itself
3. Add tests in `tests/test_<framework>_adapter.py`
4. Export from `src/saalis/integrations/__init__.py`

## Versioning and releases

Bump the version in `pyproject.toml` before merging. Merging to `main` automatically publishes to PyPI if the version is new.

## Reporting issues

Open an issue at https://github.com/ulhaqi12/saalis/issues.
