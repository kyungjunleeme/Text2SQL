import json, argparse, os, glob

def to_testcases(records):
    out = []
    for r in records:
        rid = r.get("id") or r.get("qid") or r.get("task_id")
        q = r.get("question") or r.get("nl") or r.get("utterance")
        gold = r.get("gold_sql") or r.get("sql") or r.get("gold")
        alts = r.get("gold_sql_list") or r.get("sql_variants") or r.get("gold_candidates")
        gold_sql = alts if isinstance(alts, list) and alts else ([gold] if isinstance(gold, str) else gold)
        if rid and q and gold_sql:
            out.append({"id": str(rid), "question": q, "gold_sql": gold_sql})
    return out

def read_all(path: str):
    recs = []
    if os.path.isfile(path):
        if path.endswith(".jsonl"):
            with open(path,"r",encoding="utf-8") as f:
                recs = [json.loads(line) for line in f]
        else:
            with open(path,"r",encoding="utf-8") as f:
                data = json.load(f)
                recs = data if isinstance(data,list) else data.get("data",[])
    else:
        for p in glob.glob(os.path.join(path, "*.json*")):
            recs.extend(read_all(p))
    return recs

def main():
    ap = argparse.ArgumentParser(description="Prepare Spider2-like json/jsonl into testcases")
    ap.add_argument("--input", required=True, help="File or folder")
    ap.add_argument("--output", default="out/spider2_testcases.json", help="Output JSON path")
    args = ap.parse_args()

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    recs = read_all(args.input)
    tcs = to_testcases(recs)
    with open(args.output,"w",encoding="utf-8") as f:
        json.dump(tcs,f,ensure_ascii=False,indent=2)
    print(f"✅ Wrote {len(tcs)} testcases -> {args.output}")

if __name__ == "__main__":
    main()
