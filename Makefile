.PHONY: install install-all test test-sidecar test-all lint lint-sidecar fmt typecheck typecheck-sidecar all

install:
	uv sync --extra dev

install-all:
	uv sync --all-packages --extra dev

test:
	uv run pytest --cov=src/saalis --cov-report=term-missing

test-sidecar:
	uv run --package saalis-sidecar pytest sidecar/tests/ --tb=short

test-all: test test-sidecar

lint:
	uv run ruff check src tests

lint-sidecar:
	uv run ruff check sidecar/src sidecar/tests

fmt:
	uv run ruff format src tests sidecar/src sidecar/tests
	uv run ruff check --fix src tests sidecar/src sidecar/tests

typecheck:
	uv run mypy

typecheck-sidecar:
	uv run --package saalis-sidecar mypy

all: fmt lint lint-sidecar typecheck typecheck-sidecar test-all
