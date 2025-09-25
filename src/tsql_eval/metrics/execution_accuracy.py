try:
    from deepeval.metrics import BaseMetric
except Exception:
    class BaseMetric: pass
try:
    from deepeval.test_case import LLMTestCase
except Exception:
    class LLMTestCase:
        def __init__(self, input: str = "", output: str = ""):
            self.input = input
            self.output = output

import pandas as pd

class ExecutionAccuracyMetric(BaseMetric):
    def __init__(self, backend, gold_sql, ignore_order: bool = True, null_equal: bool = True):
        """gold_sql: str | list[str]"""
        self.name = "execution_accuracy"
        self.backend = backend
        self.gold_sql = gold_sql
        self.ignore_order = ignore_order
        self.null_equal = null_equal

    def _norm(self, df: pd.DataFrame) -> pd.DataFrame:
        df2 = df.copy()
        df2.columns = [str(c).strip().lower() for c in df2.columns]
        if self.ignore_order and len(df2.columns):
            df2 = df2.sort_values(by=list(df2.columns)).reset_index(drop=True)
        if self.null_equal:
            df2 = df2.fillna("__NULL__")
        return df2

    def _compare(self, gold_sql: str, pred_sql: str) -> bool:
        g = self.backend.fetch_df(gold_sql)
        p = self.backend.fetch_df(pred_sql)
        return self._norm(g).equals(self._norm(p))

    def measure(self, test_case: LLMTestCase) -> float:
        pred_sql = (getattr(test_case, "output", "") or "").strip()
        if not pred_sql:
            self.score, self.reason = 0.0, "empty sql"; return self.score
        try:
            candidates = [self.gold_sql] if isinstance(self.gold_sql, str) else list(self.gold_sql)
            for cand in candidates:
                try:
                    if self._compare(cand, pred_sql):
                        self.score, self.reason = 1.0, "match(candidate)"
                        return self.score
                except Exception:
                    continue
            self.score, self.reason = 0.0, "mismatch(all candidates)"
        except Exception as e:
            self.score, self.reason = 0.0, f"exec/compare error: {e}"
        return self.score

    def is_successful(self) -> bool:
        return self.score == 1.0
