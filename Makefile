# ========= Global =========
SHELL := /bin/bash
.DEFAULT_GOAL := help

# 프로젝트 루트/프로필 (dbt가 ENV를 쓰는 경우 대비)
DBT_ROOT ?= $(CURDIR)
export DBT_ROOT
DBT_PROFILES_DIR ?= ./dbt
export DBT_PROFILES_DIR

# DuckDB 파일/엔진 URL
DUCKDB_FILE ?= ./data/nyc_taxi.duckdb
ENGINE_URL_DUCK := duckdb:///./data/nyc_taxi.duckdb

# Ollama 모델 (원하면 make 호출 시 OLLAMA_MODEL=... 덮어쓰기)
OLLAMA_MODEL ?= llama3.1:8b

# ========== HELP ==========
.PHONY: help
help: ## Show this help
	@grep -E '^[a-zA-Z0-9_.-]+:.*?##' Makefile | awk 'BEGIN {FS = ": .*?## "}; {printf "\033[36m%-26s\033[0m %s\n", $$1, $$2}'

# ========== Env / deps ==========
.PHONY: uv-setup uv-add-colibri uv-add-duckdb
uv-setup: ## Create venv and install deps via uv
	@if ! command -v uv >/dev/null 2>&1; then echo "[!] uv not found. Install with: pipx install uv  (or) brew install uv"; exit 1; fi
	uv venv
	uv sync

uv-add-colibri: ## Install dbt-colibri
	uv add dbt-colibri

uv-add-duckdb: ## Install dbt-duckdb
	uv add "dbt-duckdb>=1.9,<1.11"

# ========== NYC Taxi -> DuckDB ==========
.PHONY: sync-duckdb
nyc-duckdb: ## Build DuckDB from NYC Taxi 3M sample (data/nyc_taxi.duckdb)
	uv run python scripts/sync_to_duckdb.py

# ========== dbt (DuckDB target) ==========
.PHONY: dbt-seed-duck dbt-build-duck dbt-run-duck dbt-test-duck dbt-debug-duck dbt-compile-duck dbt-docs-duck
dbt-seed-duck: ## dbt seed (duck)
	DBT_PROFILES_DIR=$(DBT_PROFILES_DIR) uv run dbt seed --project-dir dbt --target duck

dbt-build-duck: ## dbt build (duck)
	DBT_PROFILES_DIR=$(DBT_PROFILES_DIR) uv run dbt build --project-dir dbt --target duck

dbt-run-duck: ## dbt run (duck)
	DBT_PROFILES_DIR=$(DBT_PROFILES_DIR) uv run dbt run --project-dir dbt --target duck

dbt-test-duck: ## dbt test (duck)
	DBT_PROFILES_DIR=$(DBT_PROFILES_DIR) uv run dbt test --project-dir dbt --target duck

dbt-debug-duck: ## dbt debug (duck)
	DBT_PROFILES_DIR=$(DBT_PROFILES_DIR) uv run dbt debug --project-dir dbt --target duck

dbt-compile-duck: ## Generate manifest.json (for colibri, duck)
	DBT_PROFILES_DIR=$(DBT_PROFILES_DIR) uv run dbt compile --project-dir dbt --target duck

dbt-docs-duck: ## Generate catalog.json (for colibri, duck)
	DBT_PROFILES_DIR=$(DBT_PROFILES_DIR) uv run dbt docs generate --project-dir dbt --target duck

# ========== Lineage (dbt-colibri) ==========
.PHONY: colibri-duck colibri-open colibri-clean colibri-copy-to-site
colibri-duck: dbt-compile-duck dbt-docs-duck ## Build lineage site -> dbt/dist (duck)
	cd dbt && uv run colibri generate --output-dir dist
	@echo "✅ Open dbt/dist/index.html"

colibri-open: ## Open lineage site
	@[ "$$(uname)" = "Darwin" ] && open dbt/dist/index.html || xdg-open dbt/dist/index.html 2>/dev/null || echo "Open dbt/dist/index.html in your browser"

colibri-clean: ## Remove dbt/dist
	rm -rf dbt/dist

colibri-copy-to-site: ## Copy lineage site into ./site/colibri
	rm -rf site/colibri && mkdir -p site/colibri
	cp -r dbt/dist/* site/colibri/

# ========== Predict (Ollama) & Evaluate ==========
.PHONY: nyc-predict-ollama-duck nyc-eval-duckdb
nyc-predict-ollama-duck: ## Generate predictions with Ollama (duck)
	uv run python tools/predict_ollama_nyc_duckdb.py \
	  --testcases data/testcases_nyc_duckdb.json \
	  --output    predictions/nyc_duckdb_preds.json \
	  --model     $(OLLAMA_MODEL)

nyc-eval-duckdb: ## Evaluate predictions on DuckDB with tsql-eval
	BACKEND=sqlalchemy ENGINE_URL=$(ENGINE_URL_DUCK) \
	uv run tsql-eval run \
	  --testcases data/testcases_nyc_duckdb.json \
	  --predictions predictions/nyc_duckdb_preds.json \
	  --dialect duckdb \
	  --report out/nyc_duckdb_report.json

# ========== Static site (GitHub Pages) ==========
.PHONY: site-build site-open site-clean site-all
site-build: ## Build ./site from reports in ./out (+ embed colibri if copied)
	uv run python scripts/build_site.py
	@echo "✅ Site generated. Open ./site/index.html"

site-open: ## Open ./site/index.html
	@[ "$$(uname)" = "Darwin" ] && open site/index.html || xdg-open site/index.html 2>/dev/null || echo "Open site/index.html in your browser"

site-clean: ## Remove ./site
	rm -rf site

site-all: ## NYC→DuckDB → dbt → lineage → predict → eval → site (one-shot)
	make nyc-duckdb
	make dbt-build-duck
	make colibri-duck
	make colibri-copy-to-site
	make nyc-predict-ollama-duck
	make nyc-eval-duckdb
	make site-build

# ========== Tests ==========
.PHONY: test
test: ## Run pytest
	uv run pytest
