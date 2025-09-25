import json, os

def load_json(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def build_backend():
    from .backends.sqlalchemy_backend import SQLAlchemyBackend
    from .backends.spark_backend import SparkBackend
    backend = os.getenv("BACKEND", "sqlalchemy").lower()
    if backend == "sqlalchemy":
        engine_url = os.getenv("ENGINE_URL", "sqlite:///./data/sample.db")
        return SQLAlchemyBackend(engine_url)
    elif backend == "spark":
        host = os.getenv("SPARK_HOST", "localhost")
        port = int(os.getenv("SPARK_PORT", "10000"))
        db   = os.getenv("SPARK_DB", "default")
        auth = os.getenv("SPARK_AUTH", "NONE")
        user = os.getenv("SPARK_USER", None)
        return SparkBackend(host=host, port=port, username=user, database=db, auth=auth)
    else:
        raise ValueError(f"Unknown BACKEND={backend}")

def run_eval(testcases_path: str, predictions_path: str, dialect: str | None = None, component_weights: dict | None = None):
    # import deepeval lazily
    from deepeval import evaluate
    from deepeval.test_case import LLMTestCase
    from .metrics.executable_sql import ExecutableSQLMetric
    from .metrics.execution_accuracy import ExecutionAccuracyMetric
    from .metrics.sql_semantic_match import SQLSemanticMatchMetric
    from .metrics.component_match import ComponentMatchMetric

    tcs = load_json(testcases_path)
    preds_list = load_json(predictions_path)
    preds = {p["id"]: p["pred_sql"] for p in preds_list}

    backend = build_backend()

    all_results = []
    success_all = 0

    for tc in tcs:
        qid = tc["id"]; question = tc["question"]; gold_sql = tc["gold_sql"]
        pred_sql = preds.get(qid, "")
        case = LLMTestCase(input=question, output=pred_sql)
        metrics = [
            ExecutableSQLMetric(backend),
            ExecutionAccuracyMetric(backend, gold_sql),
            SQLSemanticMatchMetric(gold_sql, dialect=dialect),
            ComponentMatchMetric(gold_sql, dialect=dialect, weights=component_weights),
        ]
        res = evaluate(test_cases=[case], metrics=metrics)

        out = {"id": qid, "question": question, "gold_sql": gold_sql, "pred_sql": pred_sql, "metrics": []}
        if res and isinstance(res, list) and res[0].get("metrics"):
            for m in res[0]["metrics"]:
                out["metrics"].append({"name": m.get("name"), "score": m.get("score"), "reason": m.get("reason")})

        passed = all((m.get("score") == 1.0) for m in out["metrics"] if m.get("score") is not None)
        out["passed_all"] = passed
        success_all += 1 if passed else 0
        all_results.append(out)

    summary = {"passed_all": success_all, "total": len(all_results)}
    print(f"Done. {summary['passed_all']}/{summary['total']} passed (all metrics).")
    return {"summary": summary, "results": all_results}
