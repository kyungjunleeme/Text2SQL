# Text2SQL

[![CI](https://github.com/kyungjunleeme/Text2SQL/actions/workflows/ci.yml/badge.svg)](https://github.com/kyungjunleeme/Text2SQL/actions/workflows/ci.yml) (SQLite / Trino / Databricks / Spark) — with dbt & pytest

Text-to-SQL 모델을 **DeepEval**로 평가하는 레퍼런스 레포입니다.  
- 백엔드: SQLite(기본) / Trino / Databricks(SQL Warehouse) / Spark Thrift Server(PyHive)  
- 메트릭: 실행 가능성, 실행 결과 일치, 파서 기반 의미 비교, **컴포넌트 부분 채점**  
- Spider2 연동: lite/snow/DBT → `testcases.json` + (옵션) SQLite 스키마/DB 생성  
- **dbt 통합**: `dbt-sqlite` 프로파일로 `data/sample.db` 위에서 모델 빌드  
- **pytest**: 메트릭 단위 테스트 제공

## Quickstart
```bash
make uv-setup
make db-setup
make eval-sqlite
```

## dbt
```bash
# dbt 모델 빌드 (dbt-sqlite, data/sample.db 사용)
make dbt-build
# 또는
DBT_PROFILES_DIR=./dbt uv run dbt build --project-dir dbt
```

## Pytest
```bash
make test
```

## Spider2 연동 (lite/snow/DBT)
- json/jsonl → `tools/spider2_prepare.py`
- DBT-style 디렉토리 → `tools/spider2_dbt_prepare.py`
- lite/snow + 스키마/CSV → `tools/spider2_lite_snow_prepare.py` + `tools/build_sqlite_from_schema.py`

## GitHub 업로드
```bash
make git-init
make github-push GIT_REMOTE=git@github.com:YOUR/REPO.git
```

## CI 비밀값(선택) — 실 환경 평가
GitHub Actions에서 다음 **Secrets**를 설정하면 해당 단계가 자동 실행됩니다(없으면 스킵).
- `TRINO_ENGINE_URL` — 예: `trino://user@host:8080/hive/default`
- `DATABRICKS_ENGINE_URL` — 예: `databricks+connector://token:...@HOST:443/DEFAULT?http_path=/sql/1.0/warehouses/WH_ID&catalog=main&schema=default`
- `SPARK_HOST`, `SPARK_PORT`, `SPARK_DB`, `SPARK_AUTH`, `SPARK_USER` — Spark Thrift Server 접속 정보

로컬에서 CI 유사 실행:
```bash
make ci-local
```
