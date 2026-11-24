PY ?= .venv/bin/python
BACKEND := backend
SRC := $(BACKEND)/src
TESTS := $(BACKEND)/tests

.PHONY: help venv test lint fmt typecheck compose-config up down logs build clean

help:
	@echo "make venv          — создать .venv и установить backend[dev]"
	@echo "make test          — pytest"
	@echo "make lint          — ruff + black --check"
	@echo "make fmt           — ruff --fix + black"
	@echo "make typecheck     — mypy"
	@echo "make compose-config— валидация docker-compose.yml"
	@echo "make up            — docker compose up -d --build"
	@echo "make down          — docker compose down -v"
	@echo "make logs          — docker compose logs -f"
	@echo "make build         — собрать образы"

venv:
	python3 -m venv .venv
	$(PY) -m pip install --upgrade pip
	$(PY) -m pip install -e "$(BACKEND)[dev]"

test:
	$(PY) -m pytest $(TESTS) -q

lint:
	$(PY) -m ruff check $(SRC) $(TESTS)
	$(PY) -m black --check $(SRC) $(TESTS)

fmt:
	$(PY) -m ruff check --fix $(SRC) $(TESTS)
	$(PY) -m black $(SRC) $(TESTS)

typecheck:
	$(PY) -m mypy --config-file $(BACKEND)/pyproject.toml $(SRC)

compose-config:
	docker compose config -q

up:
	docker compose up -d --build

down:
	docker compose down -v

logs:
	docker compose logs -f

build:
	docker compose build

clean:
	rm -rf .venv .pytest_cache .mypy_cache .ruff_cache backend/*.egg-info
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
