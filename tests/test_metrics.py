import os, json
from tsql_eval.backends.sqlalchemy_backend import SQLAlchemyBackend
from tsql_eval.metrics.executable_sql import ExecutableSQLMetric
from tsql_eval.metrics.execution_accuracy import ExecutionAccuracyMetric
from tsql_eval.metrics.sql_semantic_match import SQLSemanticMatchMetric
from tsql_eval.metrics.component_match import ComponentMatchMetric

def setup_module():
    if not os.path.exists("data/sample.db"):
        import scripts.setup_db as setup
        setup.main()

def test_metrics_smoke():
    backend = SQLAlchemyBackend("sqlite:///./data/sample.db")
    tcs = json.load(open("data/testcases_sample.json","r",encoding="utf-8"))
    preds = {p["id"]: p["pred_sql"] for p in json.load(open("predictions/sample_preds.json","r",encoding="utf-8"))}
    for tc in tcs:
        dummy = type("Case",(),{})(); dummy.output = preds[tc["id"]]
        assert 0.0 <= ExecutableSQLMetric(backend).measure(dummy) <= 1.0
        assert 0.0 <= ExecutionAccuracyMetric(backend, tc["gold_sql"]).measure(dummy) <= 1.0
        assert 0.0 <= SQLSemanticMatchMetric(tc["gold_sql"], dialect="spark").measure(dummy) <= 1.0
        assert 0.0 <= ComponentMatchMetric(tc["gold_sql"], dialect="spark").measure(dummy) <= 1.0
