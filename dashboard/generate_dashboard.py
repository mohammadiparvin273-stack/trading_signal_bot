"""
Generates a single self-contained static HTML dashboard
(docs/index.html) from the bot's own logs:

  - storage/run_log.jsonl     -> every processed result, signal or not
  - storage/signal_state.json -> the latest "live" signal per asset
  - storage/outcomes.json     -> what ACTUALLY happened to sent signals
                                 (TP1 hit / SL hit / expired / still open)
  - storage/history/*.csv     -> how much market data has been collected

No server, no build step, no JS framework — just one HTML file with
Chart.js loaded from a CDN for the charts. Because it's a static file
under docs/, GitHub Pages can serve it for free directly from the
repository (Settings -> Pages -> Deploy from branch -> /docs).

Run manually with: python -m dashboard.generate_dashboard
(The GitHub Actions workflow runs this automatically after every
signal pass.)
"""
from __future__ import annotations

import glob
import json
import os
from collections import Counter, defaultdict
from datetime import datetime, timezone

from storage import outcome_tracker, run_log
from storage.signal_store import SignalStore

OUTPUT_PATH = "docs/index.html"
MAX_TABLE_ROWS = 200
MAX_OUTCOME_ROWS = 150


def _load_latest_per_asset() -> dict:
    store = SignalStore()
    return store._state


def _latest_price_per_asset(records_sorted: list[dict]) -> dict:
    prices = {}
    for r in records_sorted:  # already newest-first
        key = r.get("asset")
        if key and key not in prices and r.get("current_price") is not None:
            prices[key] = r["current_price"]
    return prices


def _dataset_summary() -> list[dict]:
    rows = []
    for path in sorted(glob.glob("storage/history/*.csv")):
        try:
            with open(path, "r") as f:
                line_count = max(sum(1 for _ in f) - 1, 0)
            name = os.path.basename(path).replace(".csv", "")
            rows.append({"name": name, "rows": line_count})
        except Exception:
            continue
    return rows


def _badge_color(direction: str) -> str:
    return {"BUY": "#16a34a", "SELL": "#dc2626", "NEUTRAL": "#6b7280"}.get(direction, "#6b7280")


def _outcome_color(status: str, pnl_pct) -> str:
    # Color by the ACTUAL pnl sign for resolved trades, not just the status
    # label — a stop that locked in a profit (a legitimate trailing-stop
    # win) must render green, never red, however it's labeled.
    if status == "TP1_HIT":
        return "#16a34a"
    if status == "SL_HIT":
        return "#16a34a" if (pnl_pct or 0) >= 0 else "#dc2626"
    if status == "EXPIRED":
        return "#16a34a" if (pnl_pct or 0) >= 0 else "#a16207"
    if status == "OPEN":
        return "#3b82f6"
    return "#6b7280"  # SUPERSEDED


def _outcome_label_fa(status: str, pnl_pct) -> str:
    if status == "TP1_HIT":
        return "به هدف رسید"
    if status == "SL_HIT":
        return "با سود بسته شد" if (pnl_pct or 0) >= 0 else "حد ضرر خورد"
    if status == "EXPIRED":
        return "منقضی شد (سود)" if (pnl_pct or 0) >= 0 else "منقضی شد (ضرر)"
    if status == "OPEN":
        return "در حال انتظار"
    return "جایگزین شد"


def _per_strategy_breakdown(outcomes: list[dict]) -> list[dict]:
    """Win rate / avg pnl broken down by which strategy drove each signal
    — this is what tells you whether a specific strategy is the weak link."""
    buckets: dict[str, list[dict]] = defaultdict(list)
    for o in outcomes:
        if o["status"] not in ("TP1_HIT", "SL_HIT", "EXPIRED"):
            continue
        names = o.get("strategies") or ["(نامشخص)"]
        for name in names:
            buckets[name].append(o)

    rows = []
    for name, items in sorted(buckets.items(), key=lambda kv: -len(kv[1])):
        wins = [o for o in items if o["status"] == "TP1_HIT"]
        pnl_values = [o["pnl_pct"] for o in items if o.get("pnl_pct") is not None]
        win_rate = (len(wins) / len(items) * 100) if items else 0
        avg_pnl = (sum(pnl_values) / len(pnl_values)) if pnl_values else 0
        rows.append({
            "name": name, "count": len(items), "win_rate": round(win_rate, 1),
            "avg_pnl": round(avg_pnl, 3),
        })
    return rows


def _per_asset_breakdown(outcomes: list[dict]) -> list[dict]:
    buckets: dict[str, list[dict]] = defaultdict(list)
    for o in outcomes:
        if o["status"] not in ("TP1_HIT", "SL_HIT", "EXPIRED"):
            continue
        buckets[o["asset"]].append(o)

    rows = []
    for name, items in sorted(buckets.items()):
        wins = [o for o in items if o["status"] == "TP1_HIT"]
        pnl_values = [o["pnl_pct"] for o in items if o.get("pnl_pct") is not None]
        win_rate = (len(wins) / len(items) * 100) if items else 0
        avg_pnl = (sum(pnl_values) / len(pnl_values)) if pnl_values else 0
        rows.append({
            "name": name, "count": len(items), "win_rate": round(win_rate, 1),
            "avg_pnl": round(avg_pnl, 3),
        })
    return rows


def _ml_calibration(outcomes: list[dict]) -> dict:
    """Is the ML probability actually higher for winners than losers?
    If not, the ML layer isn't adding predictive value yet (usually
    means: not enough accumulated training data yet, or the market
    regime it trained on doesn't match current conditions)."""
    win_probs = [o["ml_probability"] for o in outcomes if o["status"] == "TP1_HIT" and o.get("ml_probability") is not None]
    loss_probs = [o["ml_probability"] for o in outcomes if o["status"] == "SL_HIT" and o.get("ml_probability") is not None]
    avg_win = round(sum(win_probs) / len(win_probs), 1) if win_probs else None
    avg_loss = round(sum(loss_probs) / len(loss_probs), 1) if loss_probs else None
    return {
        "avg_ml_on_wins": avg_win,
        "avg_ml_on_losses": avg_loss,
        "n_wins": len(win_probs),
        "n_losses": len(loss_probs),
    }


def generate() -> str:
    records = run_log.read_all()
    records_sorted = sorted(records, key=lambda r: r.get("logged_at", ""), reverse=True)
    latest_state = _load_latest_per_asset()
    latest_prices = _latest_price_per_asset(records_sorted)
    dataset_rows = _dataset_summary()

    direction_counts = Counter(r.get("direction", "NEUTRAL") for r in records)
    notified_count = sum(1 for r in records if r.get("notified"))

    outcomes_all = outcome_tracker.all_outcomes()
    perf = outcome_tracker.summary_stats()
    outcomes_sorted = sorted(outcomes_all, key=lambda o: o.get("opened_at", ""), reverse=True)
    strategy_rows = _per_strategy_breakdown(outcomes_all)
    asset_rows = _per_asset_breakdown(outcomes_all)
    ml_cal = _ml_calibration(outcomes_all)

    closed_chrono = sorted(
        [o for o in outcomes_sorted if o["status"] != "OPEN"],
        key=lambda o: o.get("closed_at") or o.get("opened_at") or "",
    )
    cum = 0.0
    pnl_curve_labels, pnl_curve_values = [], []
    for o in closed_chrono:
        cum += (o.get("pnl_pct") or 0)
        pnl_curve_labels.append((o.get("closed_at") or "")[:16])
        pnl_curve_values.append(round(cum, 2))

    chart_labels = [r.get("logged_at", "")[:16] for r in records_sorted[:60]][::-1]
    chart_confidence = [r.get("confidence", 0) for r in records_sorted[:60]][::-1]

    now_dt = datetime.now(timezone.utc)
    now_iso = now_dt.isoformat()
    now_str = now_dt.strftime("%Y-%m-%d %H:%M UTC")

    # ---- current-state cards ----
    latest_cards_html = ""
    for key, sig in sorted(latest_state.items()):
        direction = sig.get("direction", "NEUTRAL")
        color = _badge_color(direction)
        asset, tf = key.split("::") if "::" in key else (key, "")
        price = latest_prices.get(asset)
        price_html = f"<div>قیمت فعلی: <b>{price}</b></div>" if price is not None else ""
        latest_cards_html += f"""
        <div class="card">
          <div class="card-header">
            <span class="asset">{asset}</span>
            <span class="tf">{tf}</span>
            <span class="badge" style="background:{color}">{direction}</span>
          </div>
          <div class="card-body">
            <div>Regime: <b>{sig.get('regime', '-')}</b></div>
            {price_html}
            <div>Confidence: <b>{sig.get('confidence', '-')}%</b></div>
            <div>Entry: {sig.get('entry_low', '-')} - {sig.get('entry_high', '-')}</div>
            <div>SL: {sig.get('stop_loss', '-')} | TP1: {sig.get('take_profit_1', '-')}</div>
            <div>R:R: 1:{sig.get('risk_reward', '-')}</div>
            <div class="muted">ID {sig.get('signal_id', '-')} - {sig.get('timestamp', '-')}</div>
          </div>
        </div>"""
    if not latest_cards_html:
        latest_cards_html = "<p class='muted'>هنوز هیچ اجرایی ثبت نشده.</p>"

    # ---- full run history table ----
    table_rows_html = ""
    for r in records_sorted[:MAX_TABLE_ROWS]:
        color = _badge_color(r.get("direction", "NEUTRAL"))
        notified = "بله" if r.get("notified") else "-"
        reason = (r.get("reason") or "")[:140]
        strategies = ", ".join(r.get("strategies") or [])
        table_rows_html += f"""
        <tr>
          <td>{r.get('logged_at', '')[:19]}</td>
          <td>{r.get('asset', '')}</td>
          <td><span class="badge small" style="background:{color}">{r.get('direction', '')}</span></td>
          <td>{r.get('regime', '')}</td>
          <td>{r.get('confidence', '')}</td>
          <td>{r.get('ml_probability', '')}</td>
          <td>{r.get('current_price', '')}</td>
          <td>{notified}</td>
          <td class="muted">{strategies}</td>
          <td class="muted">{reason}</td>
        </tr>"""
    if not table_rows_html:
        table_rows_html = "<tr><td colspan='10' class='muted'>هنوز اجرایی ثبت نشده.</td></tr>"

    # ---- signal outcomes table ----
    outcome_rows_html = ""
    for o in outcomes_sorted[:MAX_OUTCOME_ROWS]:
        pnl = o.get("pnl_pct")
        color = _outcome_color(o["status"], pnl)
        label = _outcome_label_fa(o["status"], pnl)
        if pnl is not None:
            pnl_color = "#16a34a" if pnl >= 0 else "#dc2626"
            pnl_html = f"<b style='color:{pnl_color}'>{pnl}%</b>"
        else:
            pnl_html = "-"
        dir_color = _badge_color(o.get("direction", ""))
        strategies = ", ".join(o.get("strategies") or [])
        outcome_rows_html += f"""
        <tr>
          <td>{o.get('opened_at', '')[:16]}</td>
          <td>{o.get('asset', '')}</td>
          <td><span class="badge small" style="background:{dir_color}">{o.get('direction', '')}</span></td>
          <td class="muted">{strategies}</td>
          <td>{o.get('entry_ref', '')}</td>
          <td>{o.get('stop_loss', '')}</td>
          <td>{o.get('take_profit_1', '')}</td>
          <td><span class="badge small" style="background:{color}">{label}</span></td>
          <td>{pnl_html}</td>
          <td class="muted">{(o.get('closed_at') or '')[:16] or '-'}</td>
        </tr>"""
    if not outcome_rows_html:
        outcome_rows_html = "<tr><td colspan='10' class='muted'>هنوز هیچ سیگنالی ارسال نشده.</td></tr>"

    dataset_rows_html = "".join(
        f"<tr><td>{row['name']}</td><td>{row['rows']}</td></tr>" for row in dataset_rows
    ) or "<tr><td colspan='2' class='muted'>هنوز داده‌ای ذخیره نشده</td></tr>"

    def _breakdown_rows_html(rows):
        out = ""
        for r in rows:
            wr_color = "#16a34a" if r["win_rate"] >= 50 else "#dc2626"
            pnl_color = "#16a34a" if r["avg_pnl"] >= 0 else "#dc2626"
            out += (
                f"<tr><td>{r['name']}</td><td>{r['count']}</td>"
                f"<td style='color:{wr_color}'>{r['win_rate']}%</td>"
                f"<td style='color:{pnl_color}'>{r['avg_pnl']}%</td></tr>"
            )
        return out

    strategy_rows_html = _breakdown_rows_html(strategy_rows) or \
        "<tr><td colspan='4' class='muted'>هنوز داده‌ی کافی نیست.</td></tr>"
    asset_rows_html = _breakdown_rows_html(asset_rows) or \
        "<tr><td colspan='4' class='muted'>هنوز داده‌ی کافی نیست.</td></tr>"

    win_color = "#16a34a" if perf["win_rate"] >= 50 else "#dc2626"
    pnl_color2 = "#16a34a" if perf["avg_pnl_pct"] >= 0 else "#dc2626"

    if ml_cal["avg_ml_on_wins"] is not None and ml_cal["avg_ml_on_losses"] is not None:
        gap = ml_cal["avg_ml_on_wins"] - ml_cal["avg_ml_on_losses"]
        if gap > 3:
            ml_verdict = f"✓ ML بین برد و باخت تمایز قائل می‌شود (فاصله {round(gap,1)} درصد) — در حال اضافه‌کردن ارزش است."
            ml_verdict_color = "#16a34a"
        else:
            ml_verdict = f"⚠ فاصله‌ی ML بین برد/باخت فقط {round(gap,1)} درصد است — فعلاً تمایز معناداری نمی‌دهد (دیتای بیشتری لازم است)."
            ml_verdict_color = "#a16207"
    else:
        ml_verdict = "هنوز نمونه‌ی کافی (هم برد هم باخت) برای قضاوت درباره‌ی ML وجود ندارد."
        ml_verdict_color = "#9ca3af"

    html = f"""<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta http-equiv="refresh" content="300">
<title>Trading Signal Bot - Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
  body {{ font-family: -apple-system, Tahoma, Arial, sans-serif; background:#0b0f14; color:#e5e7eb; margin:0; padding:24px; }}
  h1 {{ font-size: 22px; margin-bottom:4px; }}
  h2 {{ font-size: 16px; }}
  .muted {{ color:#9ca3af; font-size:13px; }}
  .top-bar {{ display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px; }}
  .freshness {{ background:#151a21; border:1px solid #262b33; border-radius:20px; padding:6px 14px; font-size:13px; }}
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
  .chart-box {{ background:#151a21; border:1px solid #262b33; border-radius:10px; padding:14px; max-width:900px; }}
  .table-wrap {{ overflow-x:auto; }}
  .note {{ background:#151a21; border:1px solid #262b33; border-radius:10px; padding:12px 16px; font-size:13px; }}
  .two-col {{ display:flex; gap:20px; flex-wrap:wrap; }}
  .two-col > div {{ flex:1; min-width:320px; }}
</style>
</head>
<body>
  <div class="top-bar">
    <h1>Trading Signal Bot - Dashboard</h1>
    <span class="freshness" id="freshness" data-generated="{now_iso}">آخرین ساخت: {now_str}</span>
  </div>
  <div class="muted">این صفحه هر بار که ربات اجرا می‌شود (هر ۱۵ دقیقه) خودکار بازسازی می‌شود و هر ۵ دقیقه خودش را Refresh می‌کند. فقط تحلیل و سیگنال نشان می‌دهد؛ هیچ معامله‌ای اجرا نمی‌شود.</div>

  <div class="section">
    <h2>عملکرد واقعی سیگنال‌های ارسال‌شده</h2>
    <div class="stats">
      <div class="stat">کل سیگنال<b>{perf['total']}</b></div>
      <div class="stat">در حال انتظار<b style="color:#3b82f6">{perf['open']}</b></div>
      <div class="stat">به هدف رسیده<b style="color:#16a34a">{perf['wins']}</b></div>
      <div class="stat">حد ضرر خورده<b style="color:#dc2626">{perf['losses']}</b></div>
      <div class="stat">منقضی‌شده<b style="color:#a16207">{perf['expired']}</b></div>
      <div class="stat">جایگزین‌شده<b style="color:#6b7280">{perf['superseded']}</b></div>
      <div class="stat">Win Rate<b style="color:{win_color}">{perf['win_rate']}%</b></div>
      <div class="stat">میانگین سود/زیان<b style="color:{pnl_color2}">{perf['avg_pnl_pct']}%</b></div>
    </div>
  </div>

  <div class="section">
    <h2>عملکرد به تفکیک استراتژی (کدام استراتژی مشکل دارد؟)</h2>
    <div class="table-wrap">
    <table>
      <tr><th>استراتژی</th><th>تعداد</th><th>Win Rate</th><th>میانگین سود/زیان</th></tr>
      {strategy_rows_html}
    </table>
    </div>
  </div>

  <div class="two-col section">
    <div>
      <h2>عملکرد به تفکیک نماد</h2>
      <div class="table-wrap">
      <table>
        <tr><th>نماد</th><th>تعداد</th><th>Win Rate</th><th>میانگین سود/زیان</th></tr>
        {asset_rows_html}
      </table>
      </div>
    </div>
    <div>
      <h2>آیا بخش یادگیری (ML) واقعاً کمک می‌کند؟</h2>
      <div class="note" style="border-color:{ml_verdict_color}">
        میانگین احتمال ML روی سیگنال‌های برنده: <b>{ml_cal['avg_ml_on_wins']}%</b> (از {ml_cal['n_wins']} مورد)<br>
        میانگین احتمال ML روی سیگنال‌های بازنده: <b>{ml_cal['avg_ml_on_losses']}%</b> (از {ml_cal['n_losses']} مورد)<br><br>
        <span style="color:{ml_verdict_color}">{ml_verdict}</span><br><br>
        <span class="muted">یادآوری: ML جهت سیگنال را تعیین نمی‌کند، فقط روی Confidence استراتژی‌ها اثر می‌گذارد. اگر استراتژی‌ها جهت اشتباه بدهند، ML آن را درست نمی‌کند.</span>
      </div>
    </div>
  </div>

  <div class="section">
    <h2>روند سود/زیان تجمعی (سیگنال‌های بسته‌شده)</h2>
    <div class="chart-box"><canvas id="pnlChart" height="80"></canvas></div>
  </div>

  <div class="section">
    <h2>وضعیت فعلی هر نماد</h2>
    <div class="grid">{latest_cards_html}</div>
  </div>

  <div class="section">
    <h2>روند Confidence اخیر</h2>
    <div class="chart-box"><canvas id="confChart" height="80"></canvas></div>
  </div>

  <div class="section">
    <h2>نتیجه‌ی هر سیگنال (چی شد؟)</h2>
    <div class="stats">
      <div class="stat">تعداد کل اجراها<b>{len(records)}</b></div>
      <div class="stat">سیگنال ارسال‌شده<b>{notified_count}</b></div>
      <div class="stat">BUY<b style="color:#16a34a">{direction_counts.get('BUY', 0)}</b></div>
      <div class="stat">SELL<b style="color:#dc2626">{direction_counts.get('SELL', 0)}</b></div>
      <div class="stat">NEUTRAL<b style="color:#9ca3af">{direction_counts.get('NEUTRAL', 0)}</b></div>
    </div>
    <div class="table-wrap">
    <table>
      <tr>
        <th>زمان شروع</th><th>نماد</th><th>جهت</th><th>استراتژی</th><th>Entry</th><th>SL</th><th>TP1</th>
        <th>وضعیت</th><th>سود/زیان</th><th>زمان بسته‌شدن</th>
      </tr>
      {outcome_rows_html}
    </table>
    </div>
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
    <div class="table-wrap">
    <table>
      <tr>
        <th>زمان (UTC)</th><th>نماد</th><th>جهت</th><th>رژیم</th>
        <th>Confidence</th><th>ML%</th><th>قیمت</th><th>ارسال شد؟</th><th>استراتژی</th><th>دلیل</th>
      </tr>
      {table_rows_html}
    </table>
    </div>
  </div>

<script>
  new Chart(document.getElementById('confChart'), {{
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

  new Chart(document.getElementById('pnlChart'), {{
    type: 'line',
    data: {{
      labels: {json.dumps(pnl_curve_labels)},
      datasets: [{{
        label: 'Cumulative PnL %',
        data: {json.dumps(pnl_curve_values)},
        borderColor: '#16a34a',
        backgroundColor: 'rgba(22,163,74,0.15)',
        tension: 0.15,
        fill: true,
      }}]
    }},
    options: {{
      plugins: {{ legend: {{ display: false }} }}
    }}
  }});

  // Client-side "X minutes ago" so the freshness badge stays accurate
  // even while the tab sits open between auto-refreshes.
  (function() {{
    var el = document.getElementById('freshness');
    var generated = new Date(el.getAttribute('data-generated'));
    function tick() {{
      var mins = Math.max(0, Math.round((Date.now() - generated.getTime()) / 60000));
      el.textContent = mins <= 1 ? 'به‌روزرسانی شده: همین الان' : ('به‌روزرسانی شده: ' + mins + ' دقیقه پیش');
    }}
    tick();
    setInterval(tick, 30000);
  }})();
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
