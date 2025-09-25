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

import sqlglot
from sqlglot import expressions as exp

def _safe_parse(sql: str, dialect: str | None):
    return sqlglot.parse_one(sql, read=dialect)

def _collect_components(tree: exp.Expression):
    comps = {"tables": set(), "columns": set(), "aggregates": set(), "joins": set(), "predicates": set(), "group_by": set(), "order_by": set()}
    if tree is None: return comps
    for t in tree.find_all(exp.Table):
        comps["tables"].add((t.alias_or_name or t.name or "").lower())
    for se in tree.find_all(exp.Select):
        for sel in se.expressions:
            agg = sel.find(exp.AggFunc)
            if agg: comps["aggregates"].add(agg.key.lower())
            for ident in sel.find_all(exp.Identifier):
                comps["columns"].add(ident.name.lower())
    for j in tree.find_all(exp.Join):
        kind = (j.kind or "join").lower()
        on = j.args.get("on")
        key = kind + (":" + on.sql(dialect=None, normalize=True) if on else "")
        comps["joins"].add(key)
    where = tree.args.get("where")
    if where: comps["predicates"].add(where.sql(dialect=None, normalize=True))
    having = tree.args.get("having")
    if having: comps["predicates"].add(having.sql(dialect=None, normalize=True))
    gb = tree.args.get("group")
    if gb:
        for e in gb.expressions:
            comps["group_by"].add(e.sql(dialect=None, normalize=True).lower())
    ob = tree.args.get("order")
    if ob:
        for e in ob.expressions:
            comps["order_by"].add(e.sql(dialect=None, normalize=True).lower())
    return comps

def _jaccard(a:set, b:set) -> float:
    if not a and not b: return 1.0
    if not a or not b: return 0.0
    inter = len(a & b); union = len(a | b)
    return inter / union if union else 0.0

class ComponentMatchMetric(BaseMetric):
    """Partial scoring metric: weighted Jaccard over SQL components.
       gold_sql: str | list[str]
    """
    def __init__(self, gold_sql, dialect: str | None = None, weights: dict | None = None):
        self.name = "component_match_sql"
        self.gold_sql = gold_sql
        self.dialect = dialect
        self.weights = weights or {"tables":0.2,"columns":0.2,"aggregates":0.15,"joins":0.2,"predicates":0.15,"group_by":0.05,"order_by":0.05}
        self.threshold = 0.85
        self.strict = False
        self.async_mode = False
        self.score = None
        self.reason = None
        self.details = None

    def measure(self, test_case: LLMTestCase) -> float:
        pred_sql = ((getattr(test_case,"actual_output",None) or getattr(test_case,"output","")) or "").strip()
        try:
            pred_t = _safe_parse(pred_sql, self.dialect)
            p = _collect_components(pred_t)
            candidates = [self.gold_sql] if isinstance(self.gold_sql, str) else list(self.gold_sql)
            best_score = 0.0; best_detail = None
            for cand in candidates:
                try:
                    gold_t = _safe_parse(cand, self.dialect); g = _collect_components(gold_t)
                    scores = {}; total_w = 0.0; acc = 0.0
                    for k, w in self.weights.items():
                        s = _jaccard(p.get(k,set()), g.get(k,set()))
                        scores[k] = s; total_w += w; acc += s * w
                    score = acc / total_w if total_w else 0.0
                    if score > best_score: best_score, best_detail = score, scores
                except Exception:
                    continue
            self.score = best_score; self.reason = f"weighted jaccard; best={best_score:.3f}"; self.details = {"per_component": best_detail}
        except Exception as e:
            self.score, self.reason = 0.0, f"parse/compare error: {e}"; self.details = {"error": str(e)}
        return self.score

    async def a_measure(self, test_case: LLMTestCase):
        return self.measure(test_case)

    def is_successful(self) -> bool:
        return (self.score or 0.0) >= self.threshold
