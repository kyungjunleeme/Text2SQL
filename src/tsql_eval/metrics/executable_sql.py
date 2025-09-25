try:
    from deepeval.metrics import BaseMetric
except Exception:
    class BaseMetric: ...
try:
    from deepeval.test_case import LLMTestCase
except Exception:
    class LLMTestCase:
        def __init__(self, input: str = "", output: str = ""):
            self.input = input
            self.output = output

class ExecutableSQLMetric(BaseMetric):
    def __init__(self, backend):
        self.name = "executable_sql"
        self.backend = backend
        # deepeval가 기대하는 표준 필드
        self.threshold = 1.0
        self.strict = False
        self.async_mode = False
        self.score = None
        self.reason = None

    def measure(self, test_case: LLMTestCase) -> float:
        sql = ((getattr(test_case,"actual_output",None) or getattr(test_case,"output","")) or "").strip()
        if not sql:
            self.score, self.reason = 0.0, "empty sql"
            return self.score
        try:
            self.backend.exec(sql)
            self.score, self.reason = 1.0, "ok"
        except Exception as e:
            self.score, self.reason = 0.0, f"exec error: {e}"
        return self.score

    async def a_measure(self, test_case: LLMTestCase):
        return self.measure(test_case)

    def is_successful(self) -> bool:
        return (self.score or 0.0) >= self.threshold
