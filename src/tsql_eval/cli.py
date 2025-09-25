import click, json, os
from .runner import run_eval

@click.group()
def main():
    """Text-to-SQL evaluation CLI (DeepEval-based)."""

@main.command()
@click.option("--testcases", "testcases_path", required=True, type=click.Path(exists=True), help="JSON list of {id, question, gold_sql}")
@click.option("--predictions", "predictions_path", required=True, type=click.Path(exists=True), help="JSON list of {id, pred_sql}")
@click.option("--dialect", default=None, help="SQL dialect hint for parser (e.g., trino, spark, snowflake, bigquery)")
@click.option("--weights", default=None, help="JSON dict of component weights for ComponentMatchMetric")
@click.option("--report", "report_path", default=None, help="Write detailed JSON report to this path")
def run(testcases_path, predictions_path, dialect, weights, report):
    """Run evaluation over testcases and predictions."""
    weights_dict = json.loads(weights) if weights else None
    results = run_eval(testcases_path, predictions_path, dialect=dialect, component_weights=weights_dict)
    if report:
        os.makedirs(os.path.dirname(report), exist_ok=True)
        with open(report, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"Report written to {report}")

if __name__ == "__main__":
    main()
