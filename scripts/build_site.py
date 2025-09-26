# scripts/build_site.py
from __future__ import annotations

import json
import os
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Any
from html import escape


SITE_DIR = Path("site")
OUT_DIR = Path("out")
TITLE = "Text2SQL Report"


# ---------- HTML skeleton (responsive + centered + cards/grid) ----------
def base_html(title: str, body: str) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S %Z")
    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{escape(title)}</title>
  <style>
    :root {{
      --bg: #0b0f14;
      --panel: #0f172a;
      --card: #111827;
      --text: #e5e7eb;
      --muted: #94a3b8;
      --accent: #22d3ee;
      --border: #1f2937;
      --ok: #10b981;
      --warn: #f59e0b;
      --err: #ef4444;
    }}
    * {{ box-sizing: border-box; }}
    html, body {{ height: 100%; }}
    body {{
      margin: 0;
      font: 16px/1.6 system-ui, -apple-system, Segoe UI, Roboto, 'Noto Sans KR', Arial, 'Apple SD Gothic Neo', '맑은 고딕', sans-serif;
      color: var(--text);
      background: radial-gradient(1200px 600px at 50% -10%, #0f172a 0, var(--bg) 60%);
    }}

    /* 가운데 정렬 + 반응형 폭 */
    .container {{
      width: min(1100px, 100% - 2rem);
      margin: 32px auto;
    }}

    header {{
      text-align: center;
      margin-bottom: 24px;
    }}
    header h1 {{
      margin: 0 0 6px;
      font-size: clamp(20px, 3vw, 32px);
      letter-spacing: .2px;
    }}
    header p {{
      margin: 0;
      color: var(--muted);
      font-size: 14px;
    }}

    /* 카드 & 그리드 레이아웃 */
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: 16px;
    }}
    .card {{
      background: linear-gradient(180deg, var(--panel), var(--card));
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 16px 18px;
      box-shadow: 0 10px 24px rgba(0,0,0,.25), inset 0 1px 0 rgba(255,255,255,.02);
    }}
    .card h2 {{
      margin: 0 0 10px;
      font-size: clamp(16px, 2.2vw, 20px);
    }}

    /* 표: 모바일 스크롤 대응 */
    .table-wrap {{ overflow-x: auto; }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 14px;
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 12px;
    }}
    th, td {{
      padding: 10px 12px;
      border-bottom: 1px solid var(--border);
      text-align: left;
      white-space: nowrap;
      vertical-align: top;
    }}
    thead th {{
      position: sticky;
      top: 0;
      background: #0b1220;
      z-index: 1;
    }}

    /* 코드 블록 */
    pre, code {{
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace;
      font-size: 13px;
    }}
    pre {{
      margin: 0;
      padding: 12px;
      background: #0b1220;
      border: 1px solid var(--border);
      border-radius: 12px;
      overflow: auto;
    }}

    .pill {{
      display: inline-block;
      padding: 4px 8px;
      border-radius: 999px;
      border: 1px solid var(--border);
      color: var(--muted);
      font-size: 12px;
    }}

    .badge {{
      display: inline-block;
      padding: 2px 8px;
      border-radius: 999px;
      font-size: 12px;
      line-height: 20px;
      border: 1px solid var(--border);
      color: #fff;
    }}
    .ok  {{ background: rgba(16,185,129,.15); border-color: rgba(16,185,129,.35); color: #a7f3d0; }}
    .err {{ background: rgba(239,68,68,.15);  border-color: rgba(239,68,68,.35); color: #fecaca; }}

    a {{ color: var(--accent); text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}

    footer {{
      margin: 24px 0 8px;
      text-align: center;
      color: var(--muted);
      font-size: 12px;
    }}

    @media (max-width: 520px) {{
      th, td {{ padding: 8px 10px; }}
    }}
  </style>
</head>
<body>
  <div class="container">
    <header>
      <h1>{escape(title)}</h1>
      <p>Text2SQL Evaluation Dashboard</p>
    </header>
    {body}
    <footer>Generated {ts}</footer>
  </div>
</body>
</html>
"""


# ---------- helpers ----------
def read_reports() -> List[Dict[str, Any]]:
    reports = []
    if not OUT_DIR.exists():
        return reports
    for p in sorted(OUT_DIR.glob("*.json")):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            reports.append({"path": p, "data": data})
        except Exception:
            continue
    return reports


def fmt_pct(n: int, d: int) -> str:
    if d <= 0:
        return "0%"
    return f"{(n/d)*100:.1f}%"


def summarize_report(rep: Dict[str, Any]) -> Dict[str, Any]:
    data = rep["data"]
    results = data.get("results", [])
    passed = sum(1 for r in results if (r.get("passed_all") is True))
    total = len(results)
    return {
        "file": rep["path"].name,
        "passed": passed,
        "total": total,
        "rate": fmt_pct(passed, total),
    }


def html_summary_table(reports: List[Dict[str, Any]]) -> str:
    rows = [summarize_report(r) for r in reports]
    if not rows:
        return "<p class='pill'>No reports found in ./out</p>"
    trs = "\n".join(
        f"<tr><td>{escape(r['file'])}</td>"
        f"<td>{r['passed']}/{r['total']}</td>"
        f"<td>{r['rate']}</td></tr>"
        for r in rows
    )
    return f"""
<div class="table-wrap">
<table>
  <thead><tr><th>Report</th><th>Passed</th><th>Pass Rate</th></tr></thead>
  <tbody>
    {trs}
  </tbody>
</table>
</div>
"""


def html_artifacts(reports: List[Dict[str, Any]]) -> str:
    if not reports:
        return "<p class='pill'>No artifacts</p>"
    lis = "\n".join(
        f"<li><a href='../out/{escape(r['path'].name)}' target='_blank' rel='noopener'>{escape(r['path'].name)}</a></li>"
        for r in reports
    )
    return f"<ul>{lis}</ul>"


def html_results_table(rep: Dict[str, Any]) -> str:
    data = rep["data"]
    results = data.get("results", [])
    if not results:
        return "<p class='pill'>No test results</p>"

    def metric_badge(m: Dict[str, Any]) -> str:
        name = m.get("name", "")
        score = m.get("score", None)
        thr = m.get("threshold", None)
        reason = m.get("reason", "")
        ok = score is not None and thr is not None and score >= thr
        label = f"{name}: {score if score is not None else '—'} / {thr if thr is not None else '—'}"
        title = escape(reason or "")
        cls = "ok" if ok else "err"
        return f"<span class='badge {cls}' title='{title}'>{escape(label)}</span>"

    trs = []
    for r in results:
        qid = escape(str(r.get("id", "")))
        q = escape(str(r.get("question", "")))
        pred = escape(str(r.get("pred_sql", "")))
        passed_all = r.get("passed_all") is True
        passed_badge = "<span class='badge ok'>PASS</span>" if passed_all else "<span class='badge err'>FAIL</span>"
        metrics_html = " ".join(metric_badge(m) for m in r.get("metrics", []))
        trs.append(
            f"<tr>"
            f"<td style='min-width:80px'>{qid}<br/>{passed_badge}</td>"
            f"<td style='min-width:260px'>{q}</td>"
            f"<td><pre>{pred}</pre></td>"
            f"<td>{metrics_html}</td>"
            f"</tr>"
        )

    return f"""
<div class="table-wrap">
<table>
  <thead>
    <tr><th>ID</th><th>Question</th><th>Pred SQL</th><th>Metrics</th></tr>
  </thead>
  <tbody>
    {''.join(trs)}
  </tbody>
</table>
</div>
"""


def build_body(reports: List[Dict[str, Any]]) -> str:
    # 상단: Summary / Artifacts 카드 (그리드)
    top = f"""
<div class="grid">
  <div class="card">
    <h2>Summary</h2>
    {html_summary_table(reports)}
  </div>
  <div class="card">
    <h2>Artifacts</h2>
    {html_artifacts(reports)}
  </div>
</div>
"""

    # 하단: 각 리포트별 Results 카드
    sections = []
    for rep in reports:
        title = escape(rep["path"].name)
        sections.append(
            f"""
<div class="card" style="margin-top:16px;">
  <h2>{title}</h2>
  {html_results_table(rep)}
</div>
"""
        )

    if not sections:
        sections.append(
            """
<div class="card" style="margin-top:16px;">
  <h2>Results</h2>
  <p class="pill">아직 생성된 평가 리포트가 없습니다. <code>out/*.json</code>을 만들어주세요.</p>
</div>
"""
        )

    return top + "\n".join(sections)


def main() -> None:
    SITE_DIR.mkdir(parents=True, exist_ok=True)
    reports = read_reports()
    body = build_body(reports)
    html = base_html(TITLE, body)
    out_path = SITE_DIR / "index.html"
    out_path.write_text(html, encoding="utf-8")
    print(f"✅ Site generated at: {out_path.resolve()}")
    print("Open ./site/index.html")


if __name__ == "__main__":
    main()
