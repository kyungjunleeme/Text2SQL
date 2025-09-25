import json, os

def load_json(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def build_backend():
    backend = os.getenv("BACKEND", "sqlalchemy").lower()
    if backend == "sqlalchemy":
        from .backends.sqlalchemy_backend import SQLAlchemyBackend
        engine_url = os.getenv("ENGINE_URL", "sqlite:///./data/sample.db")
        return SQLAlchemyBackend(engine_url)
    elif backend == "spark":
        try:
            from .backends.spark_backend import SparkBackend
        except Exception as e:
            raise RuntimeError(
                "Spark backend requested but missing deps. Install with: uv sync --extra spark"
            ) from e
        host = os.getenv("SPARK_HOST", "localhost")
        port = int(os.getenv("SPARK_PORT", "10000"))
        db   = os.getenv("SPARK_DB", "default")
        auth = os.getenv("SPARK_AUTH", "NONE")
        user = os.getenv("SPARK_USER", None)
        return SparkBackend(host=host, port=port, username=user, database=db, auth=auth)
    else:
        raise ValueError(f"Unknown BACKEND={backend}")

def run_eval(testcases_path: str, predictions_path: str, dialect: str | None = None, component_weights: dict | None = None):
    # DeepEval import은 'BaseMetric' 타입 호환 위해서만 남겨둠 (실행은 수동으로)
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
        pred_sql = (preds.get(qid, "") or "").strip()
        case = LLMTestCase(input=question, actual_output=pred_sql)

        metrics = [
            ExecutableSQLMetric(backend),
            ExecutionAccuracyMetric(backend, gold_sql),
            SQLSemanticMatchMetric(gold_sql, dialect=dialect),
            ComponentMatchMetric(gold_sql, dialect=dialect, weights=component_weights),
        ]
        # 모든 메트릭 동기 강제 + 직접 측정
        for m in metrics:
            try: m.async_mode = False
            except Exception: pass
            m.measure(case)

        out = {"id": qid, "question": question, "gold_sql": gold_sql, "pred_sql": pred_sql, "metrics": []}
        pass_map = {}
        for m in metrics:
            name = getattr(m, "name", type(m).__name__)
            score = getattr(m, "score", None)
            thr = getattr(m, "threshold", 1.0)
            reason = getattr(m, "reason", None)
            ok = (score is not None and score >= thr)
            pass_map[name] = ok
            out["metrics"].append({"name": name, "score": score, "threshold": thr, "reason": reason})

        # 합격 기준:
        # 1) 실행 가능 + 실행 일치 = 필수
        # 2) (선택) 나머지 2개는 참고용이므로 전체 판정에서 필수 아님
        must_ok = pass_map.get("executable_sql", False) and pass_map.get("execution_accuracy", False)
        out["passed_all"] = bool(must_ok)
        if out["passed_all"]:
            success_all += 1

        all_results.append(out)

    summary = {"passed_all": success_all, "total": len(all_results)}
    print(f"Done. {summary['passed_all']}/{summary['total']} passed (required metrics).")
    return {"summary": summary, "results": all_results}
