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

import sqlglot

class SQLSemanticMatchMetric(BaseMetric):
    def __init__(self, gold_sql, dialect: str | None = None):
        """gold_sql: str | list[str]"""
        self.name = "semantic_match_sql"
        self.gold_sql = gold_sql
        self.dialect = dialect

    def _normalize(self, sql: str) -> str:
        tree = sqlglot.parse_one(sql, read=self.dialect)
        return tree.to_sql(dialect=self.dialect, normalize=True, pretty=False)

    def measure(self, test_case: LLMTestCase) -> float:
        try:
            pred_norm = self._normalize((getattr(test_case, "output", "") or ""))
            candidates = [self.gold_sql] if isinstance(self.gold_sql, str) else list(self.gold_sql)
            best = 0.0
            for cand in candidates:
                try:
                    gold_norm = self._normalize(cand)
                    if gold_norm == pred_norm:
                        best = max(best, 1.0)
                    elif pred_norm in gold_norm or gold_norm in pred_norm:
                        best = max(best, 0.5)
                except Exception:
                    continue
            if best == 0.0:
                self.score, self.reason = 0.0, "different"
            elif best == 0.5:
                self.score, self.reason = 0.5, "partial(any candidate)"
            else:
                self.score, self.reason = 1.0, "equal(any candidate)"
        except Exception as e:
            self.score, self.reason = 0.0, f"parse/normalize error: {e}"
        return self.score

    def is_successful(self) -> bool:
        return self.score == 1.0
