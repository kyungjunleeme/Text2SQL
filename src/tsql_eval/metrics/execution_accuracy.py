# src/tsql_eval/metrics/execution_accuracy.py

from __future__ import annotations

from decimal import Decimal
from typing import Any, Iterable, List, Tuple

import numpy as np
import pandas as pd
from deepeval.metrics import BaseMetric
from deepeval.test_case import LLMTestCase


class ExecutionAccuracyMetric(BaseMetric):
    """
    Execute gold SQL vs. predicted SQL and compare results.

    - 1차: DataFrame 정규화 비교(_compare_df)
    - 실패 시: 행(tuple) 정규화 비교(_compare_rows) 폴백
    - float/Decimal/np.generic/NaN 정규화, 컬럼명 소문자화, 정렬 무시 옵션 지원
    """

    def __init__(
        self,
        backend: Any,
        gold_sql: str | List[str],
        ignore_order: bool = True,
        null_equal: bool = True,
    ) -> None:
        self.name = "execution_accuracy"
        self.backend = backend
        self.gold_sql = gold_sql
        self.ignore_order = ignore_order
        self.null_equal = null_equal

        # DeepEval BaseMetric 필수 속성
        self.threshold: float = 1.0
        self.strict: bool = False
        self.async_mode: bool = False
        self.evaluation_model = None

        # 결과 저장
        self.score: float | None = None
        self.reason: str | None = None

    # ----------------------- 내부 유틸 -----------------------

    def _norm_df(self, df: pd.DataFrame) -> pd.DataFrame:
        """타입/정밀도 차이를 흡수하도록 DF 정규화."""
        df2 = df.copy()

        # 1) 컬럼명 통일
        df2.columns = [str(c).strip().lower() for c in df2.columns]

        # 2) Decimal/np.generic/NaN → python 스칼라/None (+ float 반올림)
        def _cell(v: Any) -> Any:
            if v is None:
                return None
            if isinstance(v, float) and np.isnan(v):
                return None
            if isinstance(v, np.generic):  # numpy scalar → python scalar
                v = v.item()
            if isinstance(v, Decimal):
                v = float(v)
            if isinstance(v, float):
                v = round(v, 6)  # 정밀도 차이 흡수
            return v

        # pandas 2.1+ : DataFrame.map, 그 외 버전은 applymap 폴백
        if hasattr(pd.DataFrame, "map"):
            df2 = df2.map(_cell)  # type: ignore[attr-defined]
        else:  # pragma: no cover  (구버전 호환)
            df2 = df2.applymap(_cell)  # deprecated path

        # 3) NULL 동일시
        if self.null_equal:
            df2 = df2.fillna("__NULL__")

        # 4) 정렬 무시 옵션
        if self.ignore_order and len(df2.columns):
            df2 = df2.sort_values(by=list(df2.columns)).reset_index(drop=True)

        return df2

    def _fetch_df(self, sql: str) -> pd.DataFrame:
        """백엔드로부터 DataFrame 획득. fetch_df가 없으면 exec/execute 폴백."""
        if hasattr(self.backend, "fetch_df"):
            return self.backend.fetch_df(sql)  # type: ignore[attr-defined]

        rows: Iterable[Tuple[Any, ...]]
        if hasattr(self.backend, "exec"):
            rows = self.backend.exec(sql)  # type: ignore[attr-defined]
        elif hasattr(self.backend, "execute"):
            rows = self.backend.execute(sql)  # type: ignore[attr-defined]
        else:
            raise RuntimeError("Backend must provide fetch_df(), exec(), or execute().")

        return pd.DataFrame(list(rows))

    def _canon_rows(self, rows: Iterable[Tuple[Any, ...]]) -> List[Tuple[Any, ...]]:
        """행(tuple) 리스트를 타입/정밀도 제거 후 정렬하여 반환."""
        import math

        out: List[Tuple[Any, ...]] = []
        for r in rows:
            rr: List[Any] = []
            for v in r:
                if v is None:
                    rr.append(None)
                    continue
                if isinstance(v, float) and math.isnan(v):
                    rr.append(None)
                    continue
                if isinstance(v, np.generic):
                    v = v.item()
                if isinstance(v, Decimal):
                    v = float(v)
                if isinstance(v, float):
                    v = round(v, 6)
                rr.append(v)
            out.append(tuple(rr))
        return sorted(out)

    def _fetch_rows(self, sql: str) -> List[Tuple[Any, ...]]:
        """백엔드로부터 행(tuple) 리스트 획득."""
        if hasattr(self.backend, "exec"):
            return list(self.backend.exec(sql))  # type: ignore[attr-defined]
        if hasattr(self.backend, "execute"):
            return list(self.backend.execute(sql))  # type: ignore[attr-defined]
        # fetch_df만 있는 경우 DF → rows 변환
        df = self._fetch_df(sql)
        return [tuple(x) for x in df.itertuples(index=False, name=None)]

    # ----------------------- 비교 로직 -----------------------

    def _compare_df(self, gold_sql: str, pred_sql: str) -> bool:
        g = self._fetch_df(gold_sql)
        p = self._fetch_df(pred_sql)
        return self._norm_df(g).equals(self._norm_df(p))

    def _compare_rows(self, gold_sql: str, pred_sql: str) -> bool:
        grows = self._fetch_rows(gold_sql)
        prows = self._fetch_rows(pred_sql)
        return self._canon_rows(grows) == self._canon_rows(prows)

    def _compare(self, gold_sql: str, pred_sql: str) -> bool:
        # 1차: DF 비교, 실패 시 2차: 행 비교
        try:
            return self._compare_df(gold_sql, pred_sql)
        except Exception:
            return self._compare_rows(gold_sql, pred_sql)

    # --------------------- BaseMetric 구현 ---------------------

    def measure(self, test_case: LLMTestCase, **kwargs) -> float:
        """
        DeepEval이 grading_context 등 추가 인자를 전달할 수 있어 **kwargs 수용.
        """
        pred_sql = (
            (getattr(test_case, "actual_output", None) or getattr(test_case, "output", ""))
            or ""
        ).strip()

        if not pred_sql:
            self.score, self.reason = 0.0, "empty sql"
            return self.score

        try:
            candidates = (
                [self.gold_sql] if isinstance(self.gold_sql, str) else list(self.gold_sql)
            )
            for cand in candidates:
                try:
                    if self._compare(cand, pred_sql):
                        self.score, self.reason = 1.0, "match(candidate)"
                        return self.score
                except Exception:
                    # 개별 후보 비교 실패는 다음 후보로 진행
                    continue

            self.score, self.reason = 0.0, "mismatch(all candidates)"
        except Exception as e:
            self.score, self.reason = 0.0, f"exec/compare error: {e}"

        return self.score

    async def a_measure(self, test_case: LLMTestCase, **kwargs) -> float:
        """비동기 경로: 동기 measure를 호출하고 점수를 반환."""
        return self.measure(test_case, **kwargs)

    def is_successful(self) -> bool:
        return (self.score or 0.0) >= self.threshold
