.PHONY: install test lint fmt typecheck all

install:
	uv sync --extra dev

test:
	uv run pytest

lint:
	uv run ruff check src tests

fmt:
	uv run ruff format src tests
	uv run ruff check --fix src tests

typecheck:
	uv run mypy

all: fmt lint typecheck test
