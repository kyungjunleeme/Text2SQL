import os, json, argparse, glob, csv

TYPE_MAP_SQLITE = {
    "int": "INTEGER","integer": "INTEGER","bigint": "INTEGER","smallint": "INTEGER",
    "float": "REAL","double": "REAL","real": "REAL","numeric": "REAL","decimal": "REAL",
    "bool": "INTEGER","boolean": "INTEGER","text": "TEXT","string": "TEXT","varchar": "TEXT","char": "TEXT",
    "date": "TEXT","timestamp": "TEXT","datetime": "TEXT",
}
def norm_type(t: str) -> str:
    if not t: return "TEXT"
    t = t.lower()
    for k, v in TYPE_MAP_SQLITE.items():
        if k in t: return v
    return "TEXT"

def load_schema_from_json(path: str):
    with open(path, "r", encoding="utf-8") as f: data = json.load(f)
    tables = []
    if isinstance(data, dict) and "tables" in data:
        for t in data["tables"]:
            cols = [(c["name"], norm_type(c.get("type"))) for c in t.get("columns", [])]
            tables.append({"name": t["name"], "columns": cols})
    else:
        for name, cols in data.items():
            if isinstance(cols, list):
                tables.append({"name": name, "columns": [(c if isinstance(c,str) else c.get("name"), norm_type(None)) for c in cols]})
    return tables

def infer_schema_from_csv_folder(folder: str):
    tables = []
    for p in glob.glob(os.path.join(folder, "*.csv")):
        tname = os.path.splitext(os.path.basename(p))[0]
        with open(p, "r", encoding="utf-8") as f:
            reader = csv.reader(f); header = next(reader, [])
        cols = [(h, "TEXT") for h in header]
        tables.append({"name": tname, "columns": cols})
    return tables

def write_sqlite_ddl(tables, out_sql_path: str):
    os.makedirs(os.path.dirname(out_sql_path), exist_ok=True)
    lines = []
    for t in tables:
        cols = ",\n    ".join([f"{cname} {ctype}" for cname, ctype in t["columns"]])
        lines.append(f"DROP TABLE IF EXISTS {t['name']};")
        lines.append(f"CREATE TABLE {t['name']} (\n    {cols}\n);\n")
    ddl = "\n".join(lines)
    with open(out_sql_path, "w", encoding="utf-8") as f: f.write(ddl)
    return out_sql_path

def read_tasks_generic(path: str):
    recs = []
    if os.path.isfile(path):
        if path.endswith(".jsonl"):
            with open(path, "r", encoding="utf-8") as f: recs = [json.loads(line) for line in f]
        else:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f); recs = data if isinstance(data, list) else data.get("data", [])
    else:
        for p in glob.glob(os.path.join(path, "*.json*")): recs.extend(read_tasks_generic(p))
    return recs

def to_testcases(records, allow_multi_gold: bool = True):
    out = []
    for r in records:
        rid = r.get("id") or r.get("qid") or r.get("task_id") or r.get("question_id")
        q = r.get("question") or r.get("nl") or r.get("utterance") or r.get("prompt")
        gold = r.get("gold_sql") or r.get("sql") or r.get("gold")
        gold_alts = r.get("gold_sql_list") or r.get("sql_variants") or r.get("gold_candidates")
        if allow_multi_gold and isinstance(gold_alts, list) and gold_alts:
            gold_sql = gold_alts
        else:
            gold_sql = [gold] if isinstance(gold, str) else gold
        if rid and q and gold_sql: out.append({"id": str(rid), "question": q, "gold_sql": gold_sql})
    return out

def main():
    ap = argparse.ArgumentParser(description="Prepare Spider2 (lite/snow) to testcases + SQLite DDL")
    ap.add_argument("--tasks", required=True, help="Path to Spider2 tasks (json/jsonl or folder)")
    ap.add_argument("--schema-json", required=False, help="Optional schema JSON describing tables/columns")
    ap.add_argument("--csv-folder", required=False, help="Optional CSV folder to infer schema (if no schema-json)")
    ap.add_argument("--ddl-out", default="out/spider2_sqlite_schema.sql", help="Output DDL SQL for SQLite")
    ap.add_argument("--testcases-out", default="out/spider2_testcases.json", help="Output testcases JSON")
    args = ap.parse_args()

    tables = []
    if args.schema_json and os.path.exists(args.schema_json):
        tables = load_schema_from_json(args.schema_json)
    elif args.csv_folder and os.path.isdir(args.csv_folder):
        tables = infer_schema_from_csv_folder(args.csv_folder)

    if tables:
        write_sqlite_ddl(tables, args.ddl_out); print(f"✅ Wrote SQLite DDL -> {args.ddl_out}")
    else:
        print("[i] No schema provided/inferred; skipping DDL.")

    recs = read_tasks_generic(args.tasks)
    tcs = to_testcases(recs, allow_multi_gold=True)
    os.makedirs(os.path.dirname(args.testcases_out), exist_ok=True)
    with open(args.testcases_out, "w", encoding="utf-8") as f: json.dump(tcs, f, ensure_ascii=False, indent=2)
    print(f"✅ Wrote {len(tcs)} testcases -> {args.testcases_out}")

if __name__ == "__main__":
    main()
