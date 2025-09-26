{{ config(materialized='view') }}

-- DuckDB: scripts/nyc_to_duckdb.py 가 만든 nyc.trips_small을 소스로 잡아옵니다.
select *
from {{ source('nyc', 'trips_small') }}