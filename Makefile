.PHONY: install install-all test test-sidecar test-mcp test-all lint lint-sidecar lint-mcp fmt typecheck typecheck-sidecar typecheck-mcp all

install:
	uv sync --extra dev

install-all:
	uv sync --all-packages --extra dev

test:
	uv run pytest --cov=src/saalis --cov-report=term-missing

test-sidecar:
	uv run --package saalis-sidecar pytest sidecar/tests/ --tb=short

test-mcp:
	uv run --package saalis-mcp pytest mcp/tests/ --tb=short

test-all: test test-sidecar test-mcp

lint:
	uv run ruff check src tests

lint-sidecar:
	uv run ruff check sidecar/src sidecar/tests

lint-mcp:
	uv run ruff check mcp/src mcp/tests

fmt:
	uv run ruff format src tests sidecar/src sidecar/tests mcp/src mcp/tests
	uv run ruff check --fix src tests sidecar/src sidecar/tests mcp/src mcp/tests

typecheck:
	uv run mypy

typecheck-sidecar:
	uv run --package saalis-sidecar mypy

typecheck-mcp:
	uv run --package saalis-mcp mypy

all: fmt lint lint-sidecar lint-mcp typecheck typecheck-sidecar typecheck-mcp test-all
