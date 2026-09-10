"""
Generates a single self-contained static HTML dashboard
(docs/index.html) from the bot's own logs:

  - storage/run_log.jsonl   -> every processed result, signal or not
  - storage/signal_state.json -> the latest "live" signal per asset
  - storage/history/*.csv   -> how much market data has been collected

No server, no build step, no JS framework — just one HTML file with
Chart.js loaded from a CDN for the small chart. Because it's a static
file under docs/, GitHub Pages can serve it for free directly from the
repository (Settings -> Pages -> Deploy from branch -> /docs).

Run manually with: python -m dashboard.generate_dashboard
(The GitHub Actions workflow runs this automatically after every
signal pass.)
"""
from __future__ import annotations

import glob
import json
import os
from collections import Counter
from datetime import datetime, timezone

from storage import run_log
from storage.signal_store import SignalStore

OUTPUT_PATH = "docs/index.html"
MAX_TABLE_ROWS = 200


def _load_latest_per_asset() -> dict:
    store = SignalStore()
    return store._state  # {asset::timeframe: last-recorded-signal-dict}


def _dataset_summary() -> list[dict]:
    rows = []
    for path in sorted(glob.glob("storage/history/*.csv")):
        try:
            with open(path, "r") as f:
                line_count = max(sum(1 for _ in f) - 1, 0)  # minus header
            name = os.path.basename(path).replace(".csv", "")
            rows.append({"name": name, "rows": line_count})
        except Exception:
            continue
    return rows


def _badge_color(direction: str) -> str:
    return {"BUY": "#16a34a", "SELL": "#dc2626", "NEUTRAL": "#6b7280"}.get(direction, "#6b7280")


def generate() -> str:
    records = run_log.read_all()
    records_sorted = sorted(records, key=lambda r: r.get("logged_at", ""), reverse=True)
    latest_state = _load_latest_per_asset()
    dataset_rows = _dataset_summary()

    direction_counts = Counter(r.get("direction", "NEUTRAL") for r in records)
    notified_count = sum(1 for r in records if r.get("notified"))

    # Data for the small chart: signals per direction over the last N runs
    chart_labels = [r.get("logged_at", "")[:16] for r in records_sorted[:40]][::-1]
    chart_confidence = [r.get("confidence", 0) for r in records_sorted[:40]][::-1]

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    latest_cards_html = ""
    for key, sig in sorted(latest_state.items()):
        direction = sig.get("direction", "NEUTRAL")
        color = _badge_color(direction)
        asset, tf = key.split("::") if "::" in key else (key, "")
        latest_cards_html += f"""
        <div class="card">
          <div class="card-header">
            <span class="asset">{asset}</span>
            <span class="tf">{tf}</span>
            <span class="badge" style="background:{color}">{direction}</span>
          </div>
          <div class="card-body">
            <div>Regime: <b>{sig.get('regime', '-')}</b></div>
            <div>Confidence: <b>{sig.get('confidence', '-')}%</b></div>
            <div>Entry: {sig.get('entry_low', '-')} – {sig.get('entry_high', '-')}</div>
            <div>SL: {sig.get('stop_loss', '-')} | TP1: {sig.get('take_profit_1', '-')}</div>
            <div>R:R: 1:{sig.get('risk_reward', '-')}</div>
            <div class="muted">ID {sig.get('signal_id', '-')} · {sig.get('timestamp', '-')}</div>
          </div>
        </div>"""

    if not latest_cards_html:
        latest_cards_html = "<p class='muted'>هنوز هیچ اجرایی ثبت نشده — بعد از اولین اجرای ربات این بخش پر می‌شود.</p>"

    table_rows_html = ""
    for r in records_sorted[:MAX_TABLE_ROWS]:
        color = _badge_color(r.get("direction", "NEUTRAL"))
        notified = "✅" if r.get("notified") else "—"
        reason = (r.get("reason") or "")[:140]
        table_rows_html += f"""
        <tr>
          <td>{r.get('logged_at', '')[:19]}</td>
          <td>{r.get('asset', '')}</td>
          <td><span class="badge small" style="background:{color}">{r.get('direction', '')}</span></td>
          <td>{r.get('regime', '')}</td>
          <td>{r.get('confidence', '')}</td>
          <td>{r.get('ml_probability', '')}</td>
          <td>{notified}</td>
          <td class="muted">{reason}</td>
        </tr>"""

    dataset_rows_html = "".join(
        f"<tr><td>{row['name']}</td><td>{row['rows']}</td></tr>" for row in dataset_rows
    ) or "<tr><td colspan='2' class='muted'>هنوز داده‌ای ذخیره نشده</td></tr>"

    html = f"""<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Trading Signal Bot — Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
  body {{ font-family: -apple-system, Tahoma, Arial, sans-serif; background:#0b0f14; color:#e5e7eb; margin:0; padding:24px; }}
  h1 {{ font-size: 22px; margin-bottom:4px; }}
  .muted {{ color:#9ca3af; font-size:13px; }}
  .grid {{ display:flex; flex-wrap:wrap; gap:14px; margin:18px 0; }}
  .card {{ background:#151a21; border:1px solid #262b33; border-radius:10px; padding:14px; width:260px; }}
  .card-header {{ display:flex; align-items:center; gap:8px; margin-bottom:8px; }}
  .asset {{ font-weight:bold; font-size:15px; }}
  .tf {{ color:#9ca3af; font-size:12px; }}
  .badge {{ margin-right:auto; color:white; padding:3px 10px; border-radius:20px; font-size:12px; font-weight:bold; }}
  .badge.small {{ padding:2px 8px; font-size:11px; }}
  .card-body div {{ font-size:13px; margin:3px 0; }}
  .stats {{ display:flex; gap:24px; margin: 10px 0 24px; flex-wrap:wrap; }}
  .stat {{ background:#151a21; border:1px solid #262b33; border-radius:10px; padding:12px 18px; min-width:120px; }}
  .stat b {{ font-size:20px; display:block; }}
  table {{ width:100%; border-collapse:collapse; font-size:13px; }}
  th, td {{ padding:8px 10px; border-bottom:1px solid #262b33; text-align:right; }}
  th {{ color:#9ca3af; font-weight:600; }}
  .section {{ margin-top:36px; }}
  #chartWrap {{ background:#151a21; border:1px solid #262b33; border-radius:10px; padding:14px; max-width:900px; }}
</style>
</head>
<body>
  <h1>📊 Trading Signal Bot — Dashboard</h1>
  <div class="muted">آخرین بروزرسانی: {now} — این صفحه فقط تحلیل و سیگنال نشان می‌دهد؛ هیچ معامله‌ای اجرا نمی‌شود.</div>

  <div class="stats">
    <div class="stat">تعداد کل اجراها<b>{len(records)}</b></div>
    <div class="stat">سیگنال ارسال‌شده<b>{notified_count}</b></div>
    <div class="stat">BUY<b style="color:#16a34a">{direction_counts.get('BUY', 0)}</b></div>
    <div class="stat">SELL<b style="color:#dc2626">{direction_counts.get('SELL', 0)}</b></div>
    <div class="stat">NEUTRAL<b style="color:#9ca3af">{direction_counts.get('NEUTRAL', 0)}</b></div>
  </div>

  <div class="section">
    <h2>وضعیت فعلی هر نماد</h2>
    <div class="grid">{latest_cards_html}</div>
  </div>

  <div class="section">
    <h2>روند Confidence اخیر</h2>
    <div id="chartWrap"><canvas id="confChart" height="90"></canvas></div>
  </div>

  <div class="section">
    <h2>حجم دیتای ذخیره‌شده برای آموزش مدل</h2>
    <table>
      <tr><th>فایل (نماد_تایم‌فریم)</th><th>تعداد کندل ذخیره‌شده</th></tr>
      {dataset_rows_html}
    </table>
  </div>

  <div class="section">
    <h2>تاریخچه‌ی کامل اجراها (آخرین {MAX_TABLE_ROWS} مورد)</h2>
    <table>
      <tr>
        <th>زمان (UTC)</th><th>نماد</th><th>جهت</th><th>رژیم</th>
        <th>Confidence</th><th>ML%</th><th>ارسال شد؟</th><th>دلیل</th>
      </tr>
      {table_rows_html}
    </table>
  </div>

<script>
  const ctx = document.getElementById('confChart');
  new Chart(ctx, {{
    type: 'line',
    data: {{
      labels: {json.dumps(chart_labels)},
      datasets: [{{
        label: 'Confidence %',
        data: {json.dumps(chart_confidence)},
        borderColor: '#3b82f6',
        backgroundColor: 'rgba(59,130,246,0.15)',
        tension: 0.25,
        fill: true,
      }}]
    }},
    options: {{
      scales: {{ y: {{ beginAtZero: true, max: 100 }} }},
      plugins: {{ legend: {{ display: false }} }}
    }}
  }});
</script>
</body>
</html>"""

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(html)
    return OUTPUT_PATH


if __name__ == "__main__":
    path = generate()
    print(f"Dashboard written to {path}")
