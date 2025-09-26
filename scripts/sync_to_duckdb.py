#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import duckdb

# GCS 미러(인코딩 이슈 적고 안정적)
GCS_FILES = [
    "https://storage.googleapis.com/clickhouse-public-datasets/nyc-taxi/trips_0.gz",
    "https://storage.googleapis.com/clickhouse-public-datasets/nyc-taxi/trips_1.gz",
    "https://storage.googleapis.com/clickhouse-public-datasets/nyc-taxi/trips_2.gz",
]

DB_PATH = "data/nyc_taxi.duckdb"

def main():
    os.makedirs("data", exist_ok=True)
    con = duckdb.connect(DB_PATH)

    print("⏳ Preparing DuckDB extensions/schema...")
    # 여러 문장은 개별 호출로
    con.execute("INSTALL httpfs")
    con.execute("LOAD httpfs")
    con.execute("CREATE SCHEMA IF NOT EXISTS nyc")

    # 파일 리스트를 SQL 리터럴 리스트로 구성
    files_sql = ", ".join(f"'{u}'" for u in GCS_FILES)

    print("⏳ Loading raw TSV.GZ -> nyc._trips_raw (safe all_varchar) ...")
    con.execute(f"""
        CREATE OR REPLACE TABLE nyc._trips_raw AS
        SELECT *
        FROM read_csv_auto(
            [{files_sql}],
            delim='\t',
            header=TRUE,
            sample_size=-1,         -- 전체 샘플링
            all_varchar=TRUE,       -- 인코딩/타입 꼬임 방지
            ignore_errors=TRUE,     -- 깨진 라인 스킵
            compression='gzip'
        );
    """)

    print("⏳ Casting -> nyc.trips_small ...")
    con.execute("""
        CREATE OR REPLACE TABLE nyc.trips_small AS
        SELECT
            try_cast(trip_id AS BIGINT)                    AS trip_id,
            try_cast(pickup_datetime  AS TIMESTAMP)        AS pickup_datetime,
            try_cast(dropoff_datetime AS TIMESTAMP)        AS dropoff_datetime,
            try_cast(pickup_longitude  AS DOUBLE)          AS pickup_longitude,
            try_cast(pickup_latitude   AS DOUBLE)          AS pickup_latitude,
            try_cast(dropoff_longitude AS DOUBLE)          AS dropoff_longitude,
            try_cast(dropoff_latitude  AS DOUBLE)          AS dropoff_latitude,
            try_cast(passenger_count   AS SMALLINT)        AS passenger_count,
            try_cast(trip_distance     AS DOUBLE)          AS trip_distance,
            try_cast(fare_amount       AS DOUBLE)          AS fare_amount,
            try_cast(extra             AS DOUBLE)          AS extra,
            try_cast(tip_amount        AS DOUBLE)          AS tip_amount,
            try_cast(tolls_amount      AS DOUBLE)          AS tolls_amount,
            try_cast(total_amount      AS DOUBLE)          AS total_amount,
            nullif(payment_type, '')                        AS payment_type,
            nullif(pickup_ntaname, '')                      AS pickup_ntaname,
            nullif(dropoff_ntaname, '')                     AS dropoff_ntaname
        FROM nyc._trips_raw;
    """)

    print("🔧 Indexing ...")
    con.execute("CREATE INDEX IF NOT EXISTS idx_pickup_dt  ON nyc.trips_small(pickup_datetime)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_dropoff_dt ON nyc.trips_small(dropoff_datetime)")

    print("🧹 Cleaning raw table ...")
    con.execute("DROP TABLE IF EXISTS nyc._trips_raw")

    n = con.execute("SELECT COUNT(*) FROM nyc.trips_small").fetchone()[0]
    print(f"✅ Loaded nyc.trips_small rows: {n}  (db={DB_PATH})")

if __name__ == "__main__":
    main()
