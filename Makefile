SHELL := /bin/bash
.DEFAULT_GOAL := help

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?##' Makefile | awk 'BEGIN {FS = ": .*?## "}; {printf "\033[36m%-24s\033[0m %s\n", $$1, $$2}'

EXTRAS ?=
uv-setup: ## Create venv and install deps via uv
	@if ! command -v uv >/dev/null 2>&1; then echo "[!] uv not found. Install with: pipx install uv  (or) brew install uv"; fi
	uv venv
	if [ -n "$(EXTRAS)" ]; then uv sync $(foreach e,$(EXTRAS),--extra $(e)); else uv sync; fi

db-setup: ## Create sample SQLite DB (data/sample.db) + sample testcases/preds
	uv run python scripts/setup_db.py

eval-sqlite: ## Run evaluation against local SQLite (default)
	BACKEND=sqlalchemy ENGINE_URL=sqlite:///./data/sample.db uv run tsql-eval run --testcases data/testcases_sample.json --predictions predictions/sample_preds.json --report out/sqlite_report.json

eval-trino: ## Run evaluation against Trino (set ENGINE_URL)
	@if [ -z "$$ENGINE_URL" ]; then echo "Set ENGINE_URL=trino://user@host:8080/catalog/schema"; exit 1; fi
	BACKEND=sqlalchemy ENGINE_URL=$$ENGINE_URL uv run tsql-eval run --testcases data/testcases_sample.json --predictions predictions/sample_preds.json --dialect trino --report out/trino_report.json

eval-databricks: ## Run evaluation against Databricks (set ENGINE_URL)
	@if [ -z "$$ENGINE_URL" ]; then echo "Set ENGINE_URL=databricks+connector://token:...@host:443/DEFAULT?http_path=/sql/1.0/warehouses/<id>&catalog=main&schema=default"; exit 1; fi
	BACKEND=sqlalchemy ENGINE_URL=$$ENGINE_URL uv run tsql-eval run --testcases data/testcases_sample.json --predictions predictions/sample_preds.json --dialect spark --report out/dbx_report.json

eval-spark: ## Run evaluation against Spark Thrift Server
	BACKEND=spark SPARK_HOST=$${SPARK_HOST:-localhost} SPARK_PORT=$${SPARK_PORT:-10000} SPARK_DB=$${SPARK_DB:-default} SPARK_AUTH=$${SPARK_AUTH:-NONE} SPARK_USER=$${SPARK_USER:-kyungjun} uv run tsql-eval run --testcases data/testcases_sample.json --predictions predictions/sample_preds.json --dialect spark --report out/spark_report.json

# --- Spider2 helpers ---
spider2-prepare: ## Convert Spider2 (lite/snow/dbt/custom json) -> testcases JSON
	uv run python tools/spider2_prepare.py --help

spider2-dbt-sample: ## Build sample Spider2-DBT-like testcases and run (SQLite)
	uv run python tools/spider2_dbt_prepare.py --root tools/examples/spider2_dbt_sample --output out/spider2_dbt_testcases.json
	BACKEND=sqlalchemy ENGINE_URL=sqlite:///./data/sample.db uv run tsql-eval run --testcases out/spider2_dbt_testcases.json --predictions predictions/sample_preds.json --dialect spark --report out/report_spider2_dbt.json

spider2-lite-prepare: ## Convert Spider2 lite/snow to testcases + SQLite DDL
	uv run python tools/spider2_lite_snow_prepare.py --tasks /path/to/spider2_lite_or_snow --schema-json /path/to/schema.json --ddl-out out/spider2_sqlite_schema.sql --testcases-out out/spider2_testcases.json

spider2-build-sqlite: ## Build SQLite DB from Spider2 DDL (and optional CSVs)
	uv run python tools/build_sqlite_from_schema.py --ddl out/spider2_sqlite_schema.sql --db data/spider2.db --csv-folder /path/to/csvs

eval-spider2-lite: ## Run eval using built Spider2 SQLite DB
	BACKEND=sqlalchemy ENGINE_URL=sqlite:///./data/spider2.db uv run tsql-eval run --testcases out/spider2_testcases.json --predictions predictions/sample_preds.json --dialect spark --report out/spider2_report.json

# --- dbt ---
dbt-build: ## dbt build (dbt-sqlite; uses data/sample.db)
	DBT_PROFILES_DIR=./dbt uv run dbt build --project-dir dbt
dbt-run: ## dbt run
	DBT_PROFILES_DIR=./dbt uv run dbt run --project-dir dbt
dbt-test: ## dbt test
	DBT_PROFILES_DIR=./dbt uv run dbt test --project-dir dbt

# --- tests ---
test: ## Run pytest
	uv run pytest

# --- git ---
git-init: ## Initialize git repo and make initial commit
	git init
	git add .
	git commit -m "Init: DeepEval Text-to-SQL demo v3.1"

github-push: ## Push to GitHub (default: kyungjunleeme/Text2SQL)
	@remote=$${GIT_REMOTE:-git@github.com:kyungjunleeme/Text2SQL.git}; \
	git remote add origin $$remote || true; \
	git branch -M main; \
	git push -u origin main

dbt-debug: ## dbt debug (checks profile/connection)
	DBT_PROFILES_DIR=./dbt uv run dbt debug --project-dir dbt

# ensure sample.db exists automatically before dbt-build