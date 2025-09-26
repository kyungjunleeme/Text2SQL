# scripts/build_site.py
from __future__ import annotations
import json, shutil, re
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime, timezone
from html import escape

ROOT = Path(".")
OUT_DIR = ROOT / "out"
SITE_DIR = ROOT / "site"
SITE_OUT_DIR = SITE_DIR / "out"
TITLE = "Text2SQL – Model Comparison (llama · chatgpt · genie)"

# ---- helpers ---------------------------------------------------------------

def now_utc_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S %Z")

MODEL_KEYS = ("llama", "chatgpt", "genie")

def detect_model_from_filename(name: str) -> str:
    low = name.lower()
    for k in MODEL_KEYS:
        if k in low:
            return k
    return "other"

def copy_reports_into_site() -> None:
    SITE_OUT_DIR.mkdir(parents=True, exist_ok=True)
    if OUT_DIR.exists():
        for p in OUT_DIR.glob("*.json"):
            shutil.copy2(p, SITE_OUT_DIR / p.name)

def load_reports() -> List[Dict[str, Any]]:
    reps: List[Dict[str, Any]] = []
    if not SITE_OUT_DIR.exists():
        return reps
    for p in sorted(SITE_OUT_DIR.glob("*.json")):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            model = detect_model_from_filename(p.name)
            reps.append({"path": p, "model": model, "data": data})
        except Exception:
            continue
    return reps

def summarize_one(rep: Dict[str, Any]) -> Dict[str, Any]:
    data = rep["data"]
    results = data.get("results", [])
    passed = sum(1 for r in results if r.get("passed_all") is True)
    total = len(results)
    # metric-level summary
    metric_pass: Dict[str, Dict[str, int]] = {}  # {name: {"pass":x,"total":y}}
    for r in results:
        for m in r.get("metrics", []):
            n = str(m.get("name", "metric"))
            ok = False
            score = m.get("score")
            thr = m.get("threshold")
            if score is not None and thr is not None:
                try:
                    ok = float(score) >= float(thr)
                except Exception:
                    ok = False
            d = metric_pass.setdefault(n, {"pass": 0, "total": 0})
            d["total"] += 1
            if ok:
                d["pass"] += 1
    return {
        "file": rep["path"].name,
        "model": rep["model"],
        "passed": passed,
        "total": total,
        "metric_pass": metric_pass,
    }

def pct(n: int, d: int) -> str:
    return "—" if d <= 0 else f"{(n/d)*100:.1f}%"

# ---- HTML ------------------------------------------------------------------

CSS = """
:root{--bg:#0b0f14;--panel:#0f172a;--card:#0f1321;--text:#e5e7eb;--muted:#94a3b8;
--accent:#22d3ee;--border:#1f2937;--ok:#10b981;--err:#ef4444}
*{box-sizing:border-box} html,body{height:100%}
body{margin:0;background:radial-gradient(1200px 600px at 50% -10%,#0f172a 0,var(--bg) 60%);
color:var(--text);font:16px/1.6 system-ui,-apple-system,Segoe UI,Roboto,'Noto Sans KR',Arial,'Apple SD Gothic Neo','맑은 고딕',sans-serif}
.container{width:min(1180px,100% - 2rem);margin:32px auto}
header{text-align:center;margin-bottom:24px}
header h1{margin:0 0 6px;font-size:clamp(20px,3vw,30px)}
header p{margin:0;color:var(--muted);font-size:14px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px}
.card{background:linear-gradient(180deg,var(--panel),var(--card));border:1px solid var(--border);
border-radius:16px;padding:16px 18px;box-shadow:0 10px 24px rgba(0,0,0,.25), inset 0 1px 0 rgba(255,255,255,.02)}
.card h2{margin:0 0 10px;font-size:clamp(16px,2.2vw,20px)}
.sub{color:var(--muted);font-size:12px}
.badge{display:inline-block;padding:2px 8px;border-radius:999px;font-size:12px;line-height:20px;border:1px solid var(--border)}
.ok{background:rgba(16,185,129,.15);border-color:rgba(16,185,129,.35);color:#a7f3d0}
.err{background:rgba(239,68,68,.15);border-color:rgba(239,68,68,.35);color:#fecaca}
.pill{display:inline-block;padding:4px 8px;border-radius:999px;border:1px solid var(--border);color:var(--muted);font-size:12px}
.table-wrap{overflow-x:auto}
table{width:100%;border-collapse:collapse;font-size:14px;background:var(--panel);
border:1px solid var(--border);border-radius:12px}
th,td{padding:10px 12px;border-bottom:1px solid var(--border);text-align:left;vertical-align:top;white-space:nowrap}
thead th{position:sticky;top:0;background:#0b1220;z-index:1}
pre,code{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,'Liberation Mono',monospace;font-size:13px}
pre{margin:0;padding:12px;background:#0b1220;border:1px solid var(--border);border-radius:12px;overflow:auto;white-space:pre-wrap}
.model-3col{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}
@media (max-width:980px){.model-3col{grid-template-columns:1fr}}
.model-card{background:#0b1220;border:1px solid var(--border);border-radius:12px;padding:12px}
.model-card h3{margin:0 0 8px;font-size:14px;display:flex;align-items:center;gap:8px}
.kv{display:flex;gap:8px;flex-wrap:wrap;margin:6px 0 10px}
.kv .badge{background:#0b1220}
ul{margin:0;padding-left:18px}
footer{margin:24px 0 8px;text-align:center;color:var(--muted);font-size:12px}
"""

def base_html(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{escape(title)}</title>
<style>{CSS}</style>
</head>
<body>
  <div class="container">
    <header>
      <h1>{escape(title)}</h1>
      <p class="sub">Compare LLM Text2SQL results across <b>llama</b>, <b>chatgpt</b>, <b>genie</b></p>
    </header>
    {body}
    <footer>Generated {now_utc_str()}</footer>
  </div>
</body>
</html>"""

def summary_cards(reports: List[Dict[str, Any]]) -> str:
    if not reports:
        return "<div class='card'><h2>Summary</h2><p class='pill'>No reports in <code>site/out</code></p></div>"
    rows = [summarize_one(r) for r in reports]
    # 모델별로 최신 1개만 보여주되(동명이 여럿이면 전부 보여도 무방)
    htmls = []
    for m in MODEL_KEYS:
        ms = [r for r in rows if r["model"] == m]
        if not ms:
            htmls.append(f"<div class='card'><h2>{m}</h2><p class='pill'>No report</p></div>")
            continue
        r = ms[-1]
        rate = pct(r["passed"], r["total"])
        metric_lines = []
        for k, v in sorted(r["metric_pass"].items()):
            metric_lines.append(f"<li>{escape(k)}: {v['pass']}/{v['total']} ({pct(v['pass'], v['total'])})</li>")
        htmls.append(
            f"<div class='card'><h2>{m}</h2>"
            f"<div class='kv'><span class='badge'>file: {escape(r['file'])}</span>"
            f"<span class='badge'>passed: {r['passed']} / {r['total']}</span>"
            f"<span class='badge'>rate: {rate}</span></div>"
            f"<div class='sub'>by metric</div>"
            f"<ul>{''.join(metric_lines) or '<li>—</li>'}</ul>"
            f"</div>"
        )
    return f"<div class='grid'>{''.join(htmls)}</div>"

def artifacts_list(reports: List[Dict[str, Any]]) -> str:
    if not reports:
        return ""
    items = "\n".join(
        f"<li><a href='out/{escape(r['path'].name)}' target='_blank' rel='noopener'>{escape(r['path'].name)}</a> <span class='pill'>{escape(r['model'])}</span></li>"
        for r in reports
    )
    return f"<div class='card'><h2>Artifacts</h2><ul>{items}</ul></div>"

def index_by_id(rep: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for r in rep["data"].get("results", []):
        qid = str(r.get("id", ""))
        if qid:
            out[qid] = r
    return out

def metric_badges(r: Dict[str, Any]) -> str:
    badges = []
    for m in r.get("metrics", []):
        name = str(m.get("name",""))
        score = m.get("score")
        thr = m.get("threshold")
        ok = False
        if score is not None and thr is not None:
            try:
                ok = float(score) >= float(thr)
            except Exception:
                ok = False
        label = f"{name}: {score if score is not None else '—'} / {thr if thr is not None else '—'}"
        badges.append(f"<span class='badge {'ok' if ok else 'err'}' title='{escape(str(m.get('reason','')))}'>{escape(label)}</span>")
    return " ".join(badges)

def compare_section(reports: List[Dict[str, Any]]) -> str:
    # 모델별 인덱스
    idx: Dict[str, Dict[str, Any]] = {}
    for rep in reports:
        if rep["model"] in MODEL_KEYS:
            idx[rep["model"]] = index_by_id(rep)

    # 모든 질문 id 합집합
    all_ids = set()
    for m in MODEL_KEYS:
        if m in idx:
            all_ids.update(idx[m].keys())
    all_ids = sorted(all_ids, key=lambda x: (re.sub(r"[^0-9]", "", x) or "999999", x))

    if not all_ids:
        return "<div class='card'><h2>Results</h2><p class='pill'>No comparable results found</p></div>"

    sections = []
    # 질문별 3-컬럼 비교 카드
    for qid in all_ids:
        # 질문 텍스트는 아무 모델에서나 먼저 찾음
        question = ""
        for m in MODEL_KEYS:
            r = idx.get(m, {}).get(qid)
            if r and r.get("question"):
                question = r["question"]
                break
        header = f"<div class='sub'>{escape(qid)}</div><h2 style='margin-top:4px'>{escape(question or '(no question)')}</h2>"

        cols = []
        for m in MODEL_KEYS:
            r = idx.get(m, {}).get(qid)
            if not r:
                cols.append(f"<div class='model-card'><h3>{m}</h3><div class='pill'>No result</div></div>")
                continue
            passed = r.get("passed_all") is True
            pred = str(r.get("pred_sql",""))
            cols.append(
                f"<div class='model-card'>"
                f"<h3>{m} {'<span class=\"badge ok\">PASS</span>' if passed else '<span class=\"badge err\">FAIL</span>'}</h3>"
                f"<div class='kv'>{metric_badges(r)}</div>"
                f"<pre>{escape(pred)}</pre>"
                f"</div>"
            )
        body = f"<div class='model-3col'>{''.join(cols)}</div>"
        sections.append(f"<div class='card'>{header}{body}</div>")

    return "\n".join(sections)

# ---- main ------------------------------------------------------------------

def main() -> None:
    SITE_DIR.mkdir(parents=True, exist_ok=True)
    copy_reports_into_site()  # copy out/*.json -> site/out/*.json
    reports = load_reports()

    body = summary_cards(reports)
    body += artifacts_list(reports)
    body += compare_section(reports)

    html = base_html(TITLE, body)
    (SITE_DIR / "index.html").write_text(html, encoding="utf-8")
    (SITE_DIR / ".nojekyll").write_text("", encoding="utf-8")
    print(f"✅ Site generated at: { (SITE_DIR / 'index.html').resolve() }")

if __name__ == "__main__":
    main()
