# src/tsql_eval/backends/sqlalchemy_backend.py
# -*- coding: utf-8 -*-
"""
SQLAlchemy 기반 백엔드.
- DuckDB 엔진일 때는 duckdb 네이티브 커넥터로 직접 실행하고
  결과를 파이썬 기본형(tuple)으로 정규화하여 반환한다.
  (DuckDBPyType 등의 unhashable 타입으로 인한 비교 오류 방지)
"""

from __future__ import annotations
from typing import Any, List, Tuple
import decimal
import os

import numpy as np
import pandas as pd  # 다른 DB용 경로에서 사용될 수 있어 import 유지


class Backend:
    def execute(self, sql: str) -> List[Tuple[Any, ...]]:
        raise NotImplementedError


def _to_python_scalar(x: Any) -> Any:
    """DuckDB/pandas/numpy 스칼라 등을 파이썬 기본형으로 변환."""
    if x is None:
        return None
    if x is pd.NA:
        return None
    if isinstance(x, np.generic):
        return x.item()
    if isinstance(x, decimal.Decimal):
        # 비교/해시 용이하도록 float로
        return float(x)
    try:
        hash(x)
        return x
    except TypeError:
        return str(x)


class SQLAlchemyBackend(Backend):
    """SQLAlchemy Engine을 이용해 쿼리를 실행하는 백엔드."""

    def __init__(self, engine_url: str):
        from sqlalchemy import create_engine
        self.engine = create_engine(engine_url)

        # duckdb 파일 경로 추출 (duckdb:///path/to.db)
        self._is_duckdb = getattr(self.engine, "dialect", None) and self.engine.dialect.name == "duckdb"
        self._duckdb_dbpath = None
        if self._is_duckdb:
            # 상대경로면 현재 작업 디렉토리 기준으로.
            db = (self.engine.url.database or ":memory:")
            if db not in (None, "", ":memory:"):
                self._duckdb_dbpath = os.path.abspath(db)
            else:
                self._duckdb_dbpath = ":memory:"

    def execute(self, sql: str) -> List[Tuple[Any, ...]]:
        """
        SQL 실행 후 결과를 리스트[튜플]로 반환.
        - DuckDB: duckdb.connect 로 직접 실행 (SQLAlchemy 경유 시 타입 메타 충돌 회피)
        - 그 외: 기존 exec_driver_sql 경로
        """
        if self._is_duckdb:
            import duckdb
            con = duckdb.connect(self._duckdb_dbpath)
            try:
                rows = con.execute(sql).fetchall()  # List[Tuple]
                # 각 셀을 파이썬 기본형으로 정규화
                return [tuple(_to_python_scalar(v) for v in row) for row in rows]
            finally:
                con.close()

        # 기타 DB는 기존 경로
        with self.engine.connect() as conn:
            res = conn.exec_driver_sql(sql)
            return [tuple(r) for r in res.fetchall()]

    # ✅ 호환용 별칭: 일부 코드가 .exec(...)를 호출함
    def exec(self, sql: str) -> List[Tuple[Any, ...]]:
        return self.execute(sql)
