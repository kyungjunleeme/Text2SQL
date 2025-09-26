#!/usr/bin/env python3
# coding: utf-8
"""
Build a static, responsive dashboard at ./site/index.html

- Scans ./out/*.json reports (tsql-eval output format)
- Groups by test case (id or question)
- Shows Gold SQL(s) alongside model predictions (Llama / ChatGPT / Genie ...)
- Renders pass/fail & scores per metric
- Adds copy-to-clipboard for SQL blocks
- Link out to /colibri/ lineage site if present

Usage:
  uv run python scripts/build_site.py
"""

from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "out"
SITE_DIR = ROOT / "site"
SITE_DIR.mkdir(parents=True, exist_ok=True)


def infer_model_label(p: Path) -> str:
    s = p.stem.lower()
    if "llama" in s:
        return "Llama"
    if "chatgpt" in s or "gpt" in s:
        return "ChatGPT"
    if "genie" in s:
        return "Genie"
    if "mistral" in s:
        return "Mistral"
    if "nyc_duckdb" in s:
        # generic name for single-run
        return "Model"
    # fallback: filename
    return p.stem


def ensure_list_gold(x: Any) -> List[str]:
    if x is None:
        return []
    if isinstance(x, list):
        return [str(i) for i in x if str(i).strip()]
    return [str(x)] if str(x).strip() else []


def load_reports() -> Tuple[Dict[str, Any], List[Path]]:
    """
    Returns:
      tests: {
        test_key: {
          'id': str|None,
          'question': str,
          'gold_sqls': [str, ...],
          'models': {
            model_label: {
              'pred_sql': str,
              'passed_all': bool,
              'metrics': [{name, score, threshold, reason}, ...]
            }
          }
        }
      }
      files: list of report paths used
    """
    tests: Dict[str, Any] = {}
    files: List[Path] = sorted(OUT_DIR.glob("*.json"))

    for f in files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        results = data.get("results") or []
        model = infer_model_label(f)

        for r in results:
            qid = r.get("id") or r.get("question") or f"{f.stem}-{len(tests)}"
            question = r.get("question") or ""
            gold_sqls = ensure_list_gold(r.get("gold_sql"))
            pred_sql = r.get("pred_sql") or ""
            metrics = r.get("metrics") or []
            passed = bool(r.get("passed_all"))

            if qid not in tests:
                tests[qid] = {
                    "id": r.get("id"),
                    "question": question,
                    "gold_sqls": gold_sqls[:],
                    "models": {},
                }
            else:
                # merge golds if missing on earlier file
                if not tests[qid]["gold_sqls"] and gold_sqls:
                    tests[qid]["gold_sqls"] = gold_sqls[:]

            tests[qid]["models"][model] = {
                "pred_sql": pred_sql,
                "metrics": metrics,
                "passed_all": passed,
            }

    return tests, files


def metric_badge(m: Dict[str, Any]) -> str:
    name = m.get("name", "")
    score = m.get("score")
    thr = m.get("threshold")
    reason = (m.get("reason") or "").replace("<", "&lt;").replace(">", "&gt;")
    ok = None
    try:
        if score is None or thr is None:
            ok = None
        else:
            ok = float(score) >= float(thr)
    except Exception:
        ok = None

    if ok is True:
        cls, icon, title = "ok", "✓", "pass"
    elif ok is False:
        cls, icon, title = "fail", "✗", "fail"
    else:
        cls, icon, title = "unk", "•", "n/a"

    s_score = "n/a" if score is None else f"{score:.3f}" if isinstance(score, (int, float)) else str(score)
    s_thr = "n/a" if thr is None else f"{thr:.3f}" if isinstance(thr, (int, float)) else str(thr)
    return f"""
      <div class="metric {cls}" title="{title}">
        <span class="metric-name">{name}</span>
        <span class="metric-icon">{icon}</span>
        <span class="metric-score">{s_score}</span>
        <span class="metric-thr">/ {s_thr}</span>
        <span class="metric-reason">{reason}</span>
      </div>
    """.strip()


def render_case(qkey: str, case: Dict[str, Any]) -> str:
    q = (case.get("question") or "").strip()
    golds: List[str] = case.get("gold_sqls") or []

    # Gold SQL blocks
    gold_blocks = ""
    if golds:
        blocks = []
        for i, g in enumerate(golds, 1):
            g_html = g.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            blocks.append(f"""
              <div class="code-card">
                <div class="code-card-head">
                  <span>Gold SQL #{i}</span>
                  <button class="copy" data-copy="{g_html}">Copy</button>
                </div>
                <pre><code>{g_html}</code></pre>
              </div>
            """)
        gold_blocks = "\n".join(blocks)
    else:
        gold_blocks = """
          <div class="code-card">
            <div class="code-card-head"><span>Gold SQL</span></div>
            <div class="muted">No gold SQL in report file</div>
          </div>
        """

    # Model cards
    model_cards = []
    for model, info in case.get("models", {}).items():
        pred = (info.get("pred_sql") or "").strip()
        pred_html = pred.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        passed = info.get("passed_all", False)
        metrics = info.get("metrics") or []

        metrics_html = "\n".join(metric_badge(m) for m in metrics)

        badge_cls = "pass" if passed else "fail"
        badge_text = "ALL PASS" if passed else "NOT PASS"

        model_cards.append(f"""
          <div class="card">
            <div class="card-head">
              <div class="model">{model}</div>
              <div class="pill {badge_cls}">{badge_text}</div>
            </div>
            <div class="code-card">
              <div class="code-card-head">
                <span>Prediction</span>
                <button class="copy" data-copy="{pred_html}">Copy</button>
              </div>
              <pre><code>{pred_html or "-- (empty) --"}</code></pre>
            </div>
            <div class="metrics">
              {metrics_html}
            </div>
          </div>
        """)

    if not model_cards:
        model_cards.append("""
          <div class="card">
            <div class="card-head"><div class="model">No models</div></div>
            <div class="muted">Place report JSONs under ./out to see predictions.</div>
          </div>
        """)

    return f"""
      <section class="case" id="{qkey}">
        <h3 class="q">Q. {q}</h3>
        <div class="gold-wrap">
          {gold_blocks}
        </div>
        <div class="grid">
          {''.join(model_cards)}
        </div>
      </section>
    """


def render_html(tests: Dict[str, Any], report_files: List[Path]) -> str:
    dt = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    # sort by key for stable order
    items = sorted(tests.items(), key=lambda kv: kv[0])

    cases_html = "\n".join(render_case(k, v) for k, v in items)

    has_colibri = (ROOT / "site" / "colibri" / "index.html").exists() or (ROOT / "dbt" / "dist" / "index.html").exists()

    # Tiny JS for copy & anchor scrolling
    js = """
    <script>
    document.addEventListener('click', (e) => {
      const btn = e.target.closest('.copy');
      if (!btn) return;
      const text = btn.getAttribute('data-copy') || '';
      navigator.clipboard.writeText(text.replaceAll('&lt;','<').replaceAll('&gt;','>').replaceAll('&amp;','&'))
        .then(() => { btn.textContent = 'Copied'; setTimeout(()=>btn.textContent='Copy', 1200); })
        .catch(() => { btn.textContent = 'Error'; setTimeout(()=>btn.textContent='Copy', 1200); });
    });
    </script>
    """

    css = """
    <style>
      :root { --bg:#0b0f14; --card:#111827; --muted:#9CA3AF; --fg:#E5E7EB; --pill:#374151; --ok:#10B981; --fail:#EF4444; --unk:#6B7280; --accent:#60A5FA; }
      * { box-sizing: border-box; }
      html, body { margin:0; padding:0; background:var(--bg); color:var(--fg); font: 16px/1.5 ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Noto Sans, Ubuntu; }
      a { color: var(--accent); text-decoration: none; }
      .container { max-width: 1100px; margin: 0 auto; padding: 24px 16px 80px; }
      header { display:flex; align-items:center; justify-content:space-between; gap:12px; margin-bottom: 18px; }
      header .title { font-size: 22px; font-weight: 700; letter-spacing:.2px; }
      header .links { display:flex; gap:10px; flex-wrap:wrap; }
      .btn { display:inline-flex; align-items:center; gap:8px; padding:8px 12px; border-radius:10px; background:#0f172a; border:1px solid #1f2937; color:#e5e7eb; font-size:13px; }
      .btn:hover { background:#111827; }
      .meta { color: var(--muted); font-size: 12px; margin-bottom: 18px; }

      .nav { display:flex; gap:8px; flex-wrap:wrap; margin: 8px 0 22px; }
      .chip { background:#0f172a; border:1px solid #1f2937; color:#cbd5e1; font-size:12px; padding:6px 10px; border-radius:999px; }
      .chip:hover { background:#111827; }

      section.case { background: #0c1220; border: 1px solid #1f2937; border-radius: 16px; padding:16px; margin: 14px 0 24px; }
      section .q { margin: 0 0 10px; font-size: 18px; font-weight: 700; }

      .gold-wrap { display:grid; grid-template-columns: 1fr; gap: 10px; margin: 10px 0 12px; }
      @media(min-width: 720px) { .gold-wrap { grid-template-columns: repeat(2, 1fr); } }

      .grid { display:grid; gap: 12px; grid-template-columns: 1fr; }
      @media(min-width: 820px) { .grid { grid-template-columns: repeat(3, 1fr); } }

      .card { background: var(--card); border:1px solid #1f2937; border-radius: 14px; padding: 12px; }
      .card-head { display:flex; align-items:center; justify-content:space-between; margin-bottom: 8px; }
      .card .model { font-weight: 700; letter-spacing: .2px; }
      .pill { font-size:11px; padding:3px 8px; border-radius: 999px; border:1px solid var(--pill); color:#e5e7eb; }
      .pill.pass { border-color: var(--ok); color: var(--ok); }
      .pill.fail { border-color: var(--fail); color: var(--fail); }

      .code-card { background:#0b1220; border:1px solid #1f2937; border-radius: 12px; }
      .code-card + .code-card { margin-top: 8px; }
      .code-card-head { display:flex; align-items:center; justify-content:space-between; padding:8px 10px; border-bottom:1px solid #1f2937; color:#cbd5e1; font-size:12px; }
      .copy { background:#0f172a; border:1px solid #334155; color:#cbd5e1; padding:6px 10px; border-radius: 8px; font-size:12px; cursor:pointer; }
      .copy:hover { background:#111827; }
      pre { margin:0; padding:12px; overflow:auto; font-size:13px; }
      code { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace; }

      .metrics { display:flex; flex-direction:column; gap:6px; margin-top:10px; }
      .metric { display:flex; align-items:center; gap:8px; font-size:12px; color:#cbd5e1; }
      .metric .metric-name { min-width: 140px; color:#e5e7eb; font-weight:600; }
      .metric .metric-icon { width:18px; text-align:center; }
      .metric.ok .metric-icon { color: var(--ok); }
      .metric.fail .metric-icon { color: var(--fail); }
      .metric.unk .metric-icon { color: var(--unk); }
      .metric .metric-score { font-variant-numeric: tabular-nums; }
      .metric .metric-thr { color: #94a3b8; font-variant-numeric: tabular-nums; }
      .metric .metric-reason { color:#9ca3af; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }

      .code-card .muted, .card .muted { color: var(--muted); padding: 10px; }
      footer { margin-top: 40px; color: #9CA3AF; font-size: 12px; text-align:center; }
    </style>
    """

    nav_html = ""
    if items:
        chips = []
        for k, v in items:
            title = (v.get("question") or "").strip()
            if len(title) > 40:
                title = title[:40] + "…"
            chips.append(f'<a class="chip" href="#{k}">{title}</a>')
        nav_html = f'<div class="nav">{"".join(chips)}</div>'

    colibri_link = ""
    # prefer site/colibri if already merged by workflow; fallback dbt/dist
    if (ROOT / "site" / "colibri" / "index.html").exists():
        colibri_link = '<a class="btn" href="./colibri/" target="_blank">Open Lineage (colibri)</a>'
    elif (ROOT / "dbt" / "dist" / "index.html").exists():
        colibri_link = '<a class="btn" href="../dbt/dist/" target="_blank">Open Lineage (colibri)</a>'

    files_list = "".join(f"<code>{f.name}</code> " for f in report_files) or "<span class='meta'>No report JSON found in ./out</span>"

    return f"""<!doctype html>
<html lang="ko">
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Text2SQL — Model Comparison Dashboard</title>
{css}
<body>
  <div class="container">
    <header>
      <div class="title">Text2SQL — Model Comparison</div>
      <div class="links">
        <a class="btn" href="https://github.com/kyungjunleeme/Text2SQL" target="_blank">GitHub</a>
        {colibri_link}
      </div>
    </header>

    <div class="meta">Built at {dt}. Reports loaded: {files_list}</div>

    {nav_html}

    {cases_html}

    <footer>
      Generated from ./out/*.json — each case shows Gold SQL and model predictions.<br/>
      Use the chips to jump between questions. Click “Copy” to copy SQL.
    </footer>
  </div>
  {js}
</body>
</html>
"""


def main() -> None:
    tests, files = load_reports()
    html = render_html(tests, files)
    out = SITE_DIR / "index.html"
    out.write_text(html, encoding="utf-8")
    print(f"✅ Site generated at: {out}")
    print("Open ./site/index.html")


if __name__ == "__main__":
    main()
