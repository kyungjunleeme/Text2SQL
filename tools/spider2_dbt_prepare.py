import os, json, argparse, re

def read_text(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        return None

def extract_from_dir(task_dir):
    candidates_q = ["question.txt", "query.txt", "nl.txt", "prompt.txt", "task.txt", "readme.md"]
    candidates_sql = ["gold.sql", "answer.sql", "sql.sql", "target.sql", "gold_query.sql"]

    q = None
    for c in candidates_q:
        p = os.path.join(task_dir, c)
        t = read_text(p)
        if t:
            if c.lower() == "readme.md":
                m = re.search(r"(?im)^q[:\-]\s*(.+)$", t)
                q = m.group(1).strip() if m else None
            else:
                q = t
        if q: break

    gold = None
    for c in candidates_sql:
        p = os.path.join(task_dir, c)
        t = read_text(p)
        if t: gold = t; break

    if q and gold:
        task_id = os.path.basename(task_dir.rstrip(os.sep))
        return {"id": task_id, "question": q, "gold_sql": gold}
    return None

def main():
    ap = argparse.ArgumentParser(description="Prepare Spider2-DBT-style tasks (directory layout) into testcases JSON")
    ap.add_argument("--root", required=True, help="Root folder containing many task subdirectories")
    ap.add_argument("--output", default="out/spider2_dbt_testcases.json", help="Output JSON path")
    args = ap.parse_args()

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    tasks = []
    for entry in sorted(os.listdir(args.root)):
        d = os.path.join(args.root, entry)
        if os.path.isdir(d):
            rec = extract_from_dir(d)
            if rec: tasks.append(rec)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2)
    print(f"✅ Wrote {len(tasks)} testcases -> {args.output}")

if __name__ == "__main__":
   main()
