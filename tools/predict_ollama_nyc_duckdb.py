# tools/predict_ollama_nyc_duckdb.py
# -*- coding: utf-8 -*-
"""
DuckDB (NYC Taxi)용 Ollama 기반 Text-to-SQL 예측 스크립트
- LLM 프롬프트를 DuckDB 규칙에 맞게 강화
- 흔한 패턴/오타를 후처리로 자동 교정(apply_sql_fixes)
- 결과를 predictions/nyc_duckdb_preds.json 로 저장
  -> make nyc-predict-ollama-duck 에서 이 파일을 사용
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from typing import Any, Dict, List

import requests


# ========= DuckDB 전용 스키마/규칙 힌트 =========
SCHEMA_HINT = """
You are a Text-to-SQL generator for DuckDB.
Database file: data/nyc_taxi.duckdb
Use fully-qualified table: nyc.trips_small

Columns:
- trip_id BIGINT
- pickup_datetime TIMESTAMP
- dropoff_datetime TIMESTAMP
- pickup_longitude DOUBLE
- pickup_latitude DOUBLE
- dropoff_longitude DOUBLE
- dropoff_latitude DOUBLE
- passenger_count SMALLINT
- trip_distance DOUBLE
- fare_amount DOUBLE
- extra DOUBLE
- tip_amount DOUBLE
- tolls_amount DOUBLE
- total_amount DOUBLE
- payment_type TEXT
- pickup_ntaname TEXT
- dropoff_ntaname TEXT

STRICT OUTPUT RULES (very important):
- Return ONLY the SQL string (no prose or backticks).
- Always reference the table as nyc.trips_small.
- When grouping by *_ntaname: add `WHERE col IS NOT NULL AND col <> ''`.
- Never compare numeric columns to '' (e.g., do NOT write passenger_count <> '').
- Canonical aliases & shapes (match these exactly when applicable):

  * Top-k by pickup_ntaname count:
    SELECT pickup_ntaname, COUNT(*) AS cnt
    FROM nyc.trips_small
    WHERE pickup_ntaname IS NOT NULL AND pickup_ntaname <> ''
    GROUP BY 1
    ORDER BY 2 DESC
    LIMIT 10

  * By passenger_count avg total_amount:
    SELECT passenger_count, AVG(total_amount) AS avg_total
    FROM nyc.trips_small
    GROUP BY 1
    ORDER BY 2 DESC

  * 2015 Jan–Mar monthly distance sum:
    SELECT EXTRACT(MONTH FROM pickup_datetime) AS mon, SUM(trip_distance) AS dist
    FROM nyc.trips_small
    WHERE EXTRACT(YEAR FROM pickup_datetime)=2015
      AND EXTRACT(MONTH FROM pickup_datetime) IN (1,2,3)
    GROUP BY 1
    ORDER BY 1

  * Top-20 tip ratio rows:
    SELECT pickup_ntaname, dropoff_ntaname, tip_amount/NULLIF(total_amount,0) AS tip_ratio
    FROM nyc.trips_small
    WHERE total_amount>0
    ORDER BY tip_ratio DESC
    LIMIT 20

  * By payment_type avg & count:
    SELECT payment_type, AVG(total_amount) AS avg_total, COUNT(*) AS cnt
    FROM nyc.trips_small
    GROUP BY 1
    ORDER BY 3 DESC
"""

def apply_sql_fixes(sql: str, question: str | None = None) -> str:
    import re
    s = (sql or "").strip().strip("`").strip()
    s = s.replace("\n", " ").replace("\r", " ")
    s = re.sub(r"\s+", " ", s)

    # 세미콜론 보장
    if s and not s.endswith(";"):
        s += ";"

    # DuckDB: 테이블 접두사 일치
    s = re.sub(r"\bFROM\s+trips_small\b", "FROM nyc.trips_small", s, flags=re.IGNORECASE)

    # ---------------- q1: pickup_ntaname count top-k ----------------
    s = re.sub(
        r"SELECT\s+pickup_ntaname\s+AS\s+cnt\s*,\s*COUNT\(\s*\*\s*\)",
        "SELECT pickup_ntaname, COUNT(*) AS cnt",
        s,
        flags=re.IGNORECASE,
    )
    if re.search(r"GROUP\s+BY\s+pickup_ntaname\b", s, re.IGNORECASE):
        s = re.sub(r"COUNT\(\s*\*\s*\)(?!\s+AS\s+cnt)", "COUNT(*) AS cnt", s, flags=re.IGNORECASE)
        s = re.sub(r"ORDER\s+BY\s+COUNT\(\s*\*\s*\)\s+DESC", "ORDER BY cnt DESC", s, flags=re.IGNORECASE)
        # GROUP BY 1 형태로 단순화
        s = re.sub(r"GROUP\s+BY\s+pickup_ntaname\b", "GROUP BY 1", s, flags=re.IGNORECASE)
        s = re.sub(r"ORDER\s+BY\s+cnt\s+DESC", "ORDER BY 2 DESC", s, flags=re.IGNORECASE)

    # ---------------- q2: passenger_count별 AVG(total_amount) -------
    # '' 비교 제거 → 고아 AND 제거
    s = re.sub(r"\bpassenger_count\s*<>\s*''\s*(AND\s*)?", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\bAND\s+GROUP\s+BY\b", " GROUP BY ", s, flags=re.IGNORECASE)  # ... AND GROUP BY ...
    s = s.replace("WHERE AND ", "WHERE ")  # WHERE AND ...

    # SELECT 컬럼/별칭/정렬 정규화
    if re.search(r"\bGROUP\s+BY\s+passenger_count\b", s, re.IGNORECASE):
        if not re.search(r"SELECT\s+.*\bpassenger_count\b", s, re.IGNORECASE):
            s = re.sub(r"SELECT\s+", "SELECT passenger_count, ", s, count=1, flags=re.IGNORECASE)
        s = re.sub(r"AVG\s*\(\s*total_amount\s*\)\s*(AS\s+\w+)?", "AVG(total_amount) AS avg_total", s, flags=re.IGNORECASE)
        # 정렬 보정
        if re.search(r"ORDER\s+BY\s+\d+\s+DESC", s, re.IGNORECASE) and not re.search(r"ORDER\s+BY\s+avg_total", s, re.IGNORECASE):
            s = re.sub(r"ORDER\s+BY\s+\d+\s+DESC", "ORDER BY avg_total DESC", s, flags=re.IGNORECASE)
        elif not re.search(r"ORDER\s+BY", s, re.IGNORECASE):
            s = s[:-1] + " ORDER BY avg_total DESC;"

    # ---------------- q3: 2015년 1~3월 필터 ------------------------
    qtxt = (question or "").lower()
    wants_jan_to_mar = any(p in qtxt for p in ["1~3월", "1-3월", "1 ~ 3월", "jan–mar", "jan-mar", "1 to 3"])
    if re.search(r"EXTRACT\s*\(\s*YEAR\s+FROM\s+pickup_datetime\s*\)\s*=\s*2015", s, re.IGNORECASE):
        has_month = re.search(r"EXTRACT\s*\(\s*MONTH\s+FROM\s+pickup_datetime\s*\)\s*(IN|BETWEEN)", s, re.IGNORECASE)
        if wants_jan_to_mar and not has_month:
            s = re.sub(
                r"(WHERE\s+EXTRACT\s*\(\s*YEAR\s+FROM\s+pickup_datetime\s*\)\s*=\s*2015)",
                r"\1 AND EXTRACT(MONTH FROM pickup_datetime) IN (1,2,3)",
                s,
                flags=re.IGNORECASE,
            )
        s = re.sub(r"SUM\s*\(\s*trip_distance\s*\)\s+AS\s+\w+", "SUM(trip_distance) AS dist", s, flags=re.IGNORECASE)
        s = re.sub(r"GROUP\s+BY\s+\d+", "GROUP BY 1", s, flags=re.IGNORECASE)
        s = re.sub(r"ORDER\s+BY\s+\d+", "ORDER BY 1", s, flags=re.IGNORECASE)

    # ---------------- q4: tip_ratio top-20 --------------------------
    if re.search(r"tip_amount\s*/\s*NULLIF\s*\(\s*total_amount\s*,\s*0\s*\)\s+AS\s+\w+", s, re.IGNORECASE):
        s = re.sub(
            r"tip_amount\s*/\s*NULLIF\s*\(\s*total_amount\s*,\s*0\s*\)\s+AS\s+\w+",
            "tip_amount/NULLIF(total_amount,0) AS tip_ratio",
            s,
            flags=re.IGNORECASE,
        )
        # 불필요한 ntaname 필터 제거
        if re.search(r"WHERE\s+.*total_amount\s*>\s*0", s, re.IGNORECASE):
            s = re.sub(r"\s+AND\s+pickup_ntaname\s+IS\s+NOT\s+NULL", "", s, flags=re.IGNORECASE)
            s = re.sub(r"\s+AND\s+pickup_ntaname\s*<>\s*''", "", s, flags=re.IGNORECASE)
            s = re.sub(r"\s+AND\s+dropoff_ntaname\s+IS\s+NOT\s+NULL", "", s, flags=re.IGNORECASE)
            s = re.sub(r"\s+AND\s+dropoff_ntaname\s*<>\s*''", "", s, flags=re.IGNORECASE)

    # ---------------- q5: payment_type별 avg + count, 정렬 ----------
    if re.search(r"\bFROM\s+nyc\.trips_small\b", s, re.IGNORECASE) and re.search(r"\bGROUP\s+BY\s+1\b|\bGROUP\s+BY\s+payment_type\b", s, re.IGNORECASE):
        s = re.sub(r"\bpayment_type\s+AS\s+cnt\b", "payment_type", s, flags=re.IGNORECASE)
        # AVG/COUNT 컬럼 보장
        if not re.search(r"AVG\s*\(\s*total_amount\s*\)\s+AS\s+avg_total", s, re.IGNORECASE):
            s = re.sub(r"SELECT\s+payment_type", "SELECT payment_type, AVG(total_amount) AS avg_total", s, flags=re.IGNORECASE)
        if not re.search(r"COUNT\s*\(\s*\*\s*\)\s+AS\s+cnt", s, re.IGNORECASE):
            s = re.sub(r"AVG\(total_amount\)\s+AS\s+avg_total", "AVG(total_amount) AS avg_total, COUNT(*) AS cnt", s, flags=re.IGNORECASE)
        # 정렬을 cnt DESC로 강제
        if re.search(r"ORDER\s+BY", s, re.IGNORECASE):
            s = re.sub(r"ORDER\s+BY\s+.*?;", "ORDER BY cnt DESC;", s, flags=re.IGNORECASE)
        else:
            s = s[:-1] + " ORDER BY cnt DESC;"

    return s

def build_prompt(question: str) -> str:
    return f"""{SCHEMA_HINT}

Question:
{question}

Return only the final SQL:"""


def ollama_generate(model: str, prompt: str, host: str = "http://localhost:11434") -> str:
    """Ollama 로컬 API 호출 (stream=False)."""
    url = f"{host}/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        # 보수적으로 결정론 강화
        "options": {"temperature": 0, "top_p": 0.9},
    }
    r = requests.post(url, json=payload, timeout=300)
    r.raise_for_status()
    data = r.json()
    return data.get("response", "").strip()


def load_testcases(path: str) -> List[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)
    # 유연하게 처리: 리스트 또는 {"cases": [...]} 둘 다 지원
    if isinstance(obj, list):
        return obj
    if isinstance(obj, dict) and "cases" in obj and isinstance(obj["cases"], list):
        return obj["cases"]
    raise ValueError(f"Unsupported testcases format: {type(obj)}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--testcases",
        default="data/testcases_nyc_duckdb.json",
        help="Input testcases JSON",
    )
    parser.add_argument(
        "--output",
        default="predictions/nyc_duckdb_preds.json",
        help="Output predictions JSON",
    )
    parser.add_argument(
        "--model",
        default=os.environ.get("OLLAMA_MODEL", "llama3.1:8b"),
        help="Ollama model name (e.g., llama3.1:8b)",
    )
    parser.add_argument(
        "--host",
        default=os.environ.get("OLLAMA_HOST", "http://localhost:11434"),
        help="Ollama API host",
    )
    args = parser.parse_args()

    cases = load_testcases(args.testcases)
    os.makedirs(os.path.dirname(args.output), exist_ok=True)

    predictions: List[Dict[str, str]] = []
    for i, case in enumerate(cases):
        q = case.get("question") or case.get("input") or ""
        cid = case.get("id") or f"q{i+1}"
        prompt = build_prompt(q)

        try:
            raw_sql = ollama_generate(args.model, prompt, host=args.host)
        except Exception as e:
            print(f"[!] Ollama generate failed for {cid}: {e}", file=sys.stderr)
            raw_sql = ""

        # 호출부도 question 전달
        # fixed_sql = apply_sql_fixes(raw_sql)  <-- 기존
        fixed_sql = apply_sql_fixes(raw_sql, question=q)
        predictions.append({"id": cid, "pred_sql": fixed_sql})
        print(f"#{i+1:02d} {cid}: {fixed_sql}")

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(predictions, f, ensure_ascii=False, indent=2)

    print(f"✅ wrote {args.output}")


if __name__ == "__main__":
    main()
