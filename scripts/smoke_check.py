import os, json
from tsql_eval.backends.sqlalchemy_backend import SQLAlchemyBackend
from tsql_eval.metrics.executable_sql import ExecutableSQLMetric
from tsql_eval.metrics.execution_accuracy import ExecutionAccuracyMetric
from tsql_eval.metrics.sql_semantic_match import SQLSemanticMatchMetric
from tsql_eval.metrics.component_match import ComponentMatchMetric

def main():
    if not os.path.exists("data/sample.db"):
        import scripts.setup_db as setup
        setup.main()
    backend = SQLAlchemyBackend("sqlite:///./data/sample.db")
    tcs = json.load(open("data/testcases_sample.json","r",encoding="utf-8"))
    preds = {p["id"]: p["pred_sql"] for p in json.load(open("predictions/sample_preds.json","r",encoding="utf-8"))}
    tc = tcs[0]; pred_sql = preds[tc["id"]]
    case_like = type("Case",(),{})(); case_like.output = pred_sql
    m1 = ExecutableSQLMetric(backend)
    m2 = ExecutionAccuracyMetric(backend, tc["gold_sql"])
    m3 = SQLSemanticMatchMetric(tc["gold_sql"], dialect="spark")
    m4 = ComponentMatchMetric(tc["gold_sql"], dialect="spark")
    scores = { "executable_sql": m1.measure(case_like), "execution_accuracy": m2.measure(case_like),
               "semantic_match": m3.measure(case_like), "component_match": m4.measure(case_like) }
    print("SMOKE:", scores)
    assert all(0.0 <= s <= 1.0 for s in scores.values())
    print("✅ Smoke check passed.")

if __name__ == "__main__":
    main()
