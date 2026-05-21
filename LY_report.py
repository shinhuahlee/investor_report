
# %%
"""
generate_report.py
------------------
執行後會在 C:\GitHub\investor_report 產生 index.html，
並自動 commit / push 到 GitHub repo，讓 GitHub Pages 更新。
"""

import pandas as pd
import numpy as np
import datetime
import os
import json
import subprocess
from pathlib import Path

# ── 1. 設定 ──────────────────────────────────────────────────────────────────

# ★ 策略 CSV 資料夾
CSV_PATH = r"C:\GitHub\lily_PL_OI"

# ★ GitHub Pages repo 路徑
REPO_PATH = r"C:\GitHub\investor_report"

# ★ 報告標題
REPORT_TITLE = "投組績效報告"
REPORT_SUBTITLE = "多策略量化交易投資組合<br>總金額: 200 萬台幣"

# ★ 匯率
usd, hkd, euro, jpy = 31, 4, 33, 0.27

exchange = {
    'NQ':  [20,   usd * 0.1,  20 * usd * 0.1],
    'HSI': [50,   hkd,        50 * hkd],
    'GC':  [100,  usd * 0.1,  100 * usd * 0.1],
    'CL':  [1000, usd,        1000 * usd],
    'TXF': [200,  1 / 4 / 5,  200 * 1 / 4 / 5],
    'ES':  [50,   usd * 0.1,  50 * usd * 0.1],
    'DAX': [5,    euro * 0.2, 5 * euro],
    'YM':  [5,    usd * 0.1,  5 * usd * 0.1],
    'SCN': [1,    usd,        1 * usd],
    'HO':  [42000, usd,       42000 * usd],
    'KC':  [375,  usd,        375 * usd],
    'SB':  [1120, usd,        1120 * usd],
    'RB':  [42000, usd,       42000 * usd],
    'HG':  [25000, usd,       25000 * usd],
    'SSI': [500,  jpy,        500 * jpy],
    'CT':  [500,  usd,        500 * usd],
    'EXF': [4000, 1,          4000],
    'NG':  [10000, usd,       10000 * usd],
    'SIN': [2,    usd,        2 * usd],
    'PL':  [50,   usd,        50 * usd],
    'SI':  [1000, usd,        1000 * usd],
}

# ★ 權重調整
stgy_dict_plus = {
    'NQ_btm.csv': 1,
    'TXF_upweek.csv': 1,
}

# ★ 只讀取名單資料夾（僅讀此資料夾內的策略檔名）
WHITELIST_PATH = r'C:\GitHub\python_winner\2026_Lily_yang\swing_NQ2'
allowlist = set(os.listdir(WHITELIST_PATH))

# ★ 歷年績效熱圖資料夾
SWING_NQ_PATH  = r'C:\GitHub\python_winner\2026_Lily_yang\swing_NQ'
HEATMAP_START  = '2020-01-01'   # ★ 熱圖起始日
HEATMAP_END    = f'{datetime.date.today().year - 1}-12-31'   # 自動取上一年底

# ★ 顯示區間（Portfolio 圖的起始日）
DISPLAY_START = '2026-01-01'

# ── 2. 工具函式 ──────────────────────────────────────────────────────────────

def fmt_ntd(v):
    sign = '' if v >= 0 else '-'
    if abs(v) >= 10_000:
        return f'{sign}NT${abs(v) / 10000:,.1f}萬'
    return f'{sign}NT${abs(v):,.0f}'

def cls(v):
    if v > 0:
        return 'pos'
    elif v < 0:
        return 'neg'
    return 'neu'

def git_auto_push(repo_path, target_file="index.html"):
    subprocess.run(["git", "-C", repo_path, "add", target_file], check=True)

    commit_message = f"Auto update {target_file} {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

    commit_result = subprocess.run(
        ["git", "-C", repo_path, "commit", "-m", commit_message],
        capture_output=True,
        text=True
    )

    if commit_result.returncode != 0:
        print("ℹ️ 沒有檔案變更，不需要 commit / push")
        return

    # fetch 更新遠端追蹤快取，避免 --force-with-lease 回傳 stale info
    subprocess.run(["git", "-C", repo_path, "fetch", "origin"], check=True)
    subprocess.run(["git", "-C", repo_path, "push", "--force-with-lease", "origin", "main"], check=True)
    print(f"🚀 {target_file} 已自動 push 到 GitHub")

def read_swing_nq():
    """讀取 swing_NQ 資料夾所有策略，合併成台幣 dailyPL 序列，依 HEATMAP_START/END 篩選"""
    base_index = pd.date_range(HEATMAP_START, HEATMAP_END)
    combined = pd.Series(0.0, index=base_index)
    for fname in os.listdir(SWING_NQ_PATH):
        if not fname.endswith('.csv'):
            continue
        sym = fname.split('_', 1)[0]
        if sym not in exchange:
            continue
        df = pd.read_csv(os.path.join(SWING_NQ_PATH, fname), header=0)
        df = df.iloc[:, [0, 2]].copy()          # 取日期欄(0)與 DailyPL 欄(2)
        df.columns = ['date', 'dailyPL']
        df['dailyPL'] = pd.to_numeric(df['dailyPL'], errors='coerce').fillna(0)
        df.index = pd.to_datetime(df['date'].astype(str), format='%Y%m%d')
        df = df.loc[~df.index.duplicated()]
        s = (df['dailyPL'] * exchange[sym][1]).reindex(base_index).fillna(0)
        combined = combined + s
    return combined

def calc_heatmap_data(daily_pl):
    """按年計算 heatmap 所需指標，回傳 list of dict（供 JSON 序列化）"""
    rows = []
    for year, data in daily_pl.groupby(daily_pl.index.year):
        cumpl = data.cumsum()
        mdd   = (cumpl - cumpl.cummax()).min()
        last_pl = cumpl.iloc[-1]
        s_nz = data[data != 0]
        if len(s_nz) > 1 and s_nz.std() != 0:
            sharpe = float(s_nz.mean() / s_nz.std() * np.sqrt(252))
        else:
            sharpe = None
        downside = s_nz[s_nz < 0]
        if len(downside) > 0 and downside.std() != 0:
            sortino = float(s_nz.mean() / downside.std() * np.sqrt(252))
        else:
            sortino = None
        pl_mdd = float(last_pl / abs(mdd)) if mdd != 0 else None
        rows.append({
            'year':    year,
            'pl':      round(float(last_pl) / 10000, 1),
            'mdd':     round(float(mdd) / 10000, 1),
            'pl_mdd':  round(pl_mdd, 2) if pl_mdd is not None else None,
            'sharpe':  round(sharpe, 2) if sharpe is not None else None,
            'sortino': round(sortino, 2) if sortino is not None else None,
        })
    return rows

# ── 3. 讀資料 ────────────────────────────────────────────────────────────────

def read_strategies():
    sheets = {}
    for fname in os.listdir(CSV_PATH):
        if fname not in allowlist or fname.startswith('~$') or not fname.endswith('.csv'):
            continue

        sym = fname.split('_', 1)[0]
        if sym not in exchange:
            print(f'  ⚠ 找不到 exchange 設定，跳過: {fname}')
            continue

        df = pd.read_csv(
            os.path.join(CSV_PATH, fname),
            index_col=None,
            header=0
        ).dropna(how='all')

        df.columns = ['date', 'netprofit', 'dailyPL', 'OI']
        df['profit_NTD'] = df['dailyPL'] * exchange[sym][1]
        df['netprofit_NTD'] = df['netprofit'] * exchange[sym][1]
        df['OI'] = pd.to_numeric(df['OI'], errors='coerce').fillna(0)
        df.index = pd.to_datetime(df['date'], format='%Y%m%d')

        sheets[fname] = df

    print(f'共讀入 {len(sheets)} 個策略')
    return sheets

def build_combined(strategy_dict):
    start = '2015-1-1'
    today = str(datetime.date.today())
    base = pd.DataFrame(index=pd.date_range(start, today))

    pl_df = base.copy()
    oi_df = base.copy()
    names = []

    for fname, df in strategy_dict.items():
        df = df.loc[~df.index.duplicated()]
        pl_df = pd.concat([pl_df, df['profit_NTD']], axis=1)
        oi_df = pd.concat([oi_df, df['OI']], axis=1)
        names.append(fname)

    pl_df.columns = names
    oi_df.columns = names
    return pl_df.fillna(0).astype(float), oi_df.fillna(0).astype(float)

# ── 4. 計算指標 ───────────────────────────────────────────────────────────────

def calc_metrics(daily_pl_series):
    s = daily_pl_series
    cumsum = s.cumsum()
    running_max = cumsum.cummax()
    dd = cumsum - running_max
    mdd = dd.min()

    trading_days = (s != 0).sum()
    total = cumsum.iloc[-1] if len(cumsum) > 0 else 0
    annual_return = (total / trading_days * 252) if trading_days > 0 else 0
    calmar = annual_return / abs(mdd) if mdd != 0 else np.nan

    s_nz = s[s != 0]
    sharpe = (s_nz.mean() / s_nz.std() * np.sqrt(252)) if len(s_nz) > 1 and s_nz.std() != 0 else np.nan

    wins = (s[s != 0] > 0).sum()
    total_trades = (s != 0).sum()
    win_rate = wins / total_trades if total_trades > 0 else 0

    losing = (s < 0).astype(int)
    max_consec = 0
    cur = 0
    for v in losing:
        cur = cur + 1 if v else 0
        max_consec = max(max_consec, cur)

    winning = (s > 0).astype(int)
    max_consec_win = 0
    cur_w = 0
    for v in winning:
        cur_w = cur_w + 1 if v else 0
        max_consec_win = max(max_consec_win, cur_w)

    yearly = s.groupby(s.index.year).sum()

    return {
        'total': total,
        'annual_return': annual_return,
        'mdd': mdd,
        'calmar': calmar,
        'sharpe': sharpe,
        'win_rate': win_rate,
        'max_consec_loss': max_consec,
        'max_consec_win': max_consec_win,
        'yearly': yearly,
        'cumsum': cumsum,
        'dd': dd,
    }

# ── 5. HTML 模板 ──────────────────────────────────────────────────────────────

HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<script src="https://cdn.plot.ly/plotly-2.32.0.min.js"></script>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=DM+Serif+Display&family=DM+Sans:wght@300;400;500;600&display=swap" rel="stylesheet">
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

  :root {{
    --ink:      #0f1923;
    --ink-60:   #5a6472;
    --ink-20:   #dce1e7;
    --paper:    #f8f7f4;
    --white:    #ffffff;
    --accent:   #1a3c5e;
    --accent2:  #c8922a;
    --green:    #2a7c5e;
    --red:      #c0392b;
    --radius:   4px;
    --shadow:   0 1px 3px rgba(0,0,0,.08), 0 4px 16px rgba(0,0,0,.05);
  }}

  body {{
    font-family: 'DM Sans', sans-serif;
    background: var(--paper);
    color: var(--ink);
    font-size: 14px;
    line-height: 1.6;
  }}

  header {{
    background: var(--accent);
    color: #fff;
    padding: 48px 64px 40px;
    position: relative;
    overflow: hidden;
  }}
  header::after {{
    content: '';
    position: absolute;
    right: -80px; bottom: -80px;
    width: 320px; height: 320px;
    border-radius: 50%;
    background: rgba(200,146,42,.15);
    pointer-events: none;
  }}
  header .eyebrow {{
    font-size: 11px;
    letter-spacing: .15em;
    text-transform: uppercase;
    color: rgba(255,255,255,.55);
    margin-bottom: 10px;
  }}
  header h1 {{
    font-family: 'DM Serif Display', serif;
    font-size: clamp(26px, 4vw, 42px);
    font-weight: 400;
    line-height: 1.15;
    margin-bottom: 6px;
  }}
  header .sub {{
    font-size: 13px;
    color: rgba(255,255,255,.6);
  }}
  header .date-badge {{
    position: absolute;
    top: 48px; right: 64px;
    font-size: 12px;
    color: rgba(255,255,255,.55);
    text-align: right;
    line-height: 1.8;
  }}

  main {{ max-width: 1200px; margin: 0 auto; padding: 48px 32px 80px; }}
  section {{ margin-bottom: 56px; }}
  section h2 {{
    font-family: 'DM Serif Display', serif;
    font-size: 22px;
    font-weight: 400;
    color: var(--accent);
    margin-bottom: 20px;
    padding-bottom: 10px;
    border-bottom: 1px solid var(--ink-20);
  }}

  .kpi-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
    gap: 16px;
    margin-bottom: 8px;
  }}
  .kpi {{
    background: var(--white);
    border: 1px solid var(--ink-20);
    border-radius: var(--radius);
    padding: 20px 20px 16px;
    box-shadow: var(--shadow);
  }}
  .kpi .label {{
    font-size: 11px;
    letter-spacing: .08em;
    text-transform: uppercase;
    color: var(--ink-60);
    margin-bottom: 8px;
  }}
  .kpi .value {{
    font-size: clamp(16px, 1.8vw, 24px);
    font-weight: 600;
    letter-spacing: -.5px;
    line-height: 1.2;
    white-space: nowrap;
  }}
  .kpi .value.pos {{ color: var(--green); }}
  .kpi .value.neg {{ color: var(--red); }}
  .kpi .value.neu {{ color: var(--ink); }}
  .kpi .sub-value {{
    font-size: 11px;
    color: var(--ink-60);
    margin-top: 6px;
  }}

  .chart-card {{
    background: var(--white);
    border: 1px solid var(--ink-20);
    border-radius: var(--radius);
    box-shadow: var(--shadow);
    padding: 24px 24px 16px;
    margin-bottom: 20px;
  }}
  .chart-card h3 {{
    font-size: 13px;
    font-weight: 500;
    letter-spacing: .04em;
    text-transform: uppercase;
    color: var(--ink-60);
    margin-bottom: 16px;
  }}

  .table-wrap {{ overflow-x: auto; }}
  table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
  }}
  thead tr {{
    background: var(--accent);
    color: #fff;
  }}
  th, td {{
    padding: 10px 16px;
    text-align: right;
    white-space: nowrap;
  }}
  th:first-child, td:first-child {{ text-align: left; }}
  tbody tr:nth-child(even) {{ background: #f2f4f6; }}
  .pos {{ color: var(--green); font-weight: 500; }}
  .neg {{ color: var(--red); font-weight: 500; }}

  footer {{
    text-align: center;
    font-size: 11px;
    color: var(--ink-60);
    padding: 24px;
    border-top: 1px solid var(--ink-20);
    margin-top: 32px;
  }}
  footer strong {{ color: var(--accent); }}

  @media (max-width: 640px) {{
    header {{
      padding: 28px 20px 28px;
    }}
    header .date-badge {{
      position: static;
      text-align: left;
      margin-top: 10px;
      font-size: 11px;
      color: rgba(255,255,255,.50);
    }}
    main {{ padding: 20px 12px 60px; }}
    section {{ margin-bottom: 36px; }}
    section h2 {{ font-size: 18px; margin-bottom: 14px; }}
    .kpi-grid {{
      grid-template-columns: repeat(2, 1fr);
      gap: 10px;
    }}
    .kpi {{ padding: 14px 12px 12px; }}
    .kpi .label {{ font-size: 10px; }}
    .kpi .value {{
      font-size: clamp(15px, 5vw, 22px);
      white-space: normal;
      word-break: break-word;
    }}
    .kpi .sub-value {{ font-size: 10px; }}
    .chart-card {{ padding: 14px 10px 10px; }}
    .chart-card h3 {{ font-size: 11px; }}
    #chart-equity {{ height: 240px !important; }}
    #chart-dd     {{ height: 140px !important; }}
  }}

  /* ── Heatmap ── */
  .hm-wrap {{ overflow-x: auto; -webkit-overflow-scrolling: touch; }}
  .heatmap-tbl {{ border-collapse: collapse; font-size: 12px; white-space: nowrap; width: 100%; }}
  .hm-label-cell {{
    text-align: left;
    padding: 8px 14px 8px 4px;
    font-weight: 600;
    font-size: 11px;
    color: var(--ink-60);
    background: var(--white);
    position: sticky;
    left: 0;
    z-index: 2;
    border-right: 2px solid var(--ink-20);
  }}
  .hm-year-cell {{
    text-align: center;
    padding: 7px 10px;
    font-size: 11px;
    font-weight: 600;
    background: var(--accent);
    color: #fff;
    min-width: 56px;
  }}
  .hm-cell {{
    text-align: center;
    padding: 7px 6px;
    font-size: 12px;
    font-weight: 500;
    min-width: 56px;
    border: 1px solid rgba(255,255,255,.35);
  }}
  .hm-stats {{
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    padding: 14px 0 4px;
  }}
  .hm-stat {{
    display: flex;
    flex-direction: column;
    background: var(--paper);
    border: 1px solid var(--ink-20);
    border-radius: var(--radius);
    padding: 10px 14px;
    min-width: 90px;
  }}
  .hm-stat-lbl {{
    font-size: 10px;
    color: var(--ink-60);
    text-transform: uppercase;
    letter-spacing: .06em;
    margin-bottom: 4px;
  }}
  .hm-stat-val {{ font-size: 17px; font-weight: 600; }}
  @media (max-width: 640px) {{
    .hm-label-cell {{ font-size: 10px; padding: 5px 8px 5px 2px; }}
    .hm-cell {{ min-width: 40px; padding: 5px 2px; font-size: 11px; }}
    .hm-year-cell {{ min-width: 40px; padding: 5px 2px; font-size: 10px; }}
    .hm-stat {{ padding: 8px 10px; min-width: 80px; }}
    .hm-stat-val {{ font-size: 15px; }}
  }}
</style>
</head>
<body>

<header>
  <p class="eyebrow">量化策略</p>
  <h1>{title}</h1>
  <p class="sub">{subtitle}</p>
  <div class="date-badge">
    產生日期<br><strong>{gen_date}</strong>
  </div>
</header>

<main>
  <section>
    <h2>績效摘要</h2>
    <div class="kpi-grid">
      <div class="kpi">
        <div class="label">今年累計損益（台幣）</div>
        <div class="value {total_cls}">{total_fmt}</div>
      </div>
      <div class="kpi">
        <div class="label">今年最大回撤</div>
        <div class="value neg">{mdd_fmt}</div>
      </div>
      <div class="kpi">
        <div class="label">今年 Sharpe 比率</div>
        <div class="value neu">{sharpe_fmt}</div>
      </div>
      <div class="kpi">
        <div class="label">今年 Calmar 比率</div>
        <div class="value neu">{calmar_fmt}</div>
      </div>
      <div class="kpi">
        <div class="label">今年最長連續獲利天數</div>
        <div class="value pos">{mcw_fmt}</div>
      </div>
      <div class="kpi">
        <div class="label">今年最長連續虧損天數</div>
        <div class="value neg">{mcl_fmt}</div>
      </div>
    </div>
  </section>

  <section>
    <h2>策略損益</h2>
    <div class="chart-card">
      <h3>累計損益 — {display_start} 至今</h3>
      <div id="chart-equity" style="height:360px"></div>
    </div>
    <div class="chart-card">
      <h3>回撤</h3>
      <div id="chart-dd" style="height:200px"></div>
    </div>
  </section>

  <section>
    <h2>近 60 天每日損益</h2>
    <div class="chart-card">
      <h3>每日損益（台幣）</h3>
      <div id="chart-daily30" style="height:220px"></div>
    </div>
    <div class="chart-card table-wrap">
      <table id="daily60-table">
        <thead><tr><th>日期</th><th>損益（台幣）</th></tr></thead>
        <tbody id="daily60-tbody"></tbody>
      </table>
      <div id="daily60-pagination" style="display:flex;justify-content:center;align-items:center;gap:8px;padding:14px 0 4px;"></div>
    </div>
  </section>

  <!-- 歷年績效熱圖 -->
  <section>
    <h2>歷年損益分布 <span style="font-size:13px;font-weight:400;color:var(--ink-60);font-family:'DM Sans'">{heatmap_start} ～ {heatmap_end}</span></h2>
    <div class="chart-card">
      <div class="hm-wrap" id="heatmap-container"></div>
      <div id="heatmap-summary"></div>
    </div>
  </section>

</main>

<footer>
  <p><strong>{title}</strong> &nbsp;|&nbsp; 本報告僅供專業投資人參閱 &nbsp;|&nbsp; {gen_date}</p>
  <p style="margin-top:6px">過去績效不代表未來獲利之保證。</p>
</footer>

<script>
const EQUITY   = {equity_json};
const DD       = {dd_json};
const DAILY60  = {daily60_json};
const HEATMAP  = {heatmap_json};

const ACCENT = '#1a3c5e';
const GREEN  = '#2a7c5e';
const RED    = '#c0392b';

const baseLayout = {{
  font: {{ family: 'DM Sans, sans-serif', size: 12, color: '#0f1923' }},
  paper_bgcolor: 'rgba(0,0,0,0)',
  plot_bgcolor: 'rgba(0,0,0,0)',
  margin: {{ t: 8, b: 40, l: 90, r: 24 }},
  xaxis: {{ showgrid: false, zeroline: false, tickfont: {{ size: 11 }} }},
  yaxis: {{
    gridcolor: '#dce1e7',
    zeroline: true,
    zerolinecolor: '#bbb',
    tickfont: {{ size: 11 }},
    tickformat: ',.0f'
  }},
  legend: {{
    bgcolor: 'rgba(0,0,0,0)',
    font: {{ size: 11 }},
    orientation: 'h',
    x: 0.5,
    y: -0.18,
    xanchor: 'center',
    yanchor: 'top'
  }},
  hovermode: 'x unified',
}};

const cfg = {{ responsive: true, displayModeBar: false }};

const initMargin = window.innerWidth <= 640
  ? {{ t: 6, b: 36, l: 58, r: 6 }}
  : {{ t: 8, b: 40, l: 90, r: 24 }};

(function () {{
  let peak = -Infinity;
  const nhX = [], nhY = [];

  EQUITY.x.forEach((d, i) => {{
    const v = EQUITY.y[i];
    if (v > peak) {{
      peak = v;
      nhX.push(d);
      nhY.push(v);
    }}
  }});

  Plotly.newPlot('chart-equity', [
    {{
      x: EQUITY.x,
      y: EQUITY.y,
      type: 'scatter',
      mode: 'lines',
      name: '累計損益',
      line: {{ color: ACCENT, width: 2 }},
      fill: 'tozeroy',
      fillcolor: 'rgba(26,60,94,.07)',
    }},
    {{
      x: nhX,
      y: nhY,
      type: 'scatter',
      mode: 'markers',
      name: '創新高',
      marker: {{
        color: '#00e676',
        size: 7,
        symbol: 'circle',
        line: {{ color: '#fff', width: 1.5 }}
      }},
      hovertemplate: '%{{x}}<br>NT$%{{y:,.0f}}<extra>創新高</extra>',
    }},
  ], {{
    ...baseLayout,
    margin: initMargin,
    yaxis: {{ ...baseLayout.yaxis, tickprefix: 'NT$' }},
  }}, cfg);
}})();

Plotly.newPlot('chart-dd', [{{
  x: DD.x,
  y: DD.y,
  type: 'scatter',
  mode: 'lines',
  name: '回撤',
  line: {{ color: RED, width: 1.5 }},
  fill: 'tozeroy',
  fillcolor: 'rgba(192,57,43,.12)',
}}], {{
  ...baseLayout,
  margin: initMargin,
  yaxis: {{ ...baseLayout.yaxis, tickprefix: 'NT$' }},
}}, cfg);

window.addEventListener('resize', () => {{
  const m = window.innerWidth <= 640
    ? {{ t: 6, b: 36, l: 58, r: 6 }}
    : {{ t: 8, b: 40, l: 90, r: 24 }};

  ['chart-equity', 'chart-dd', 'chart-daily30'].forEach(id => {{
    Plotly.relayout(id, {{ margin: m }});
  }});
}});

Plotly.newPlot('chart-daily30', [{{
  x: DAILY60.map(r => r.date),
  y: DAILY60.map(r => r.pl),
  type: 'bar',
  marker: {{
    color: DAILY60.map(r => r.pl >= 0 ? GREEN : RED),
    line: {{ color: '#fff', width: 0.5 }}
  }},
}}], {{
  ...baseLayout,
  margin: initMargin,
  yaxis: {{ ...baseLayout.yaxis, tickprefix: 'NT$' }},
  bargap: 0.25,
}}, cfg);

(function () {{
  const PAGE_SIZE = 30;
  const rows = [...DAILY60].reverse();
  let currentPage = 1;
  const totalPages = Math.ceil(rows.length / PAGE_SIZE);
  const tbody = document.getElementById('daily60-tbody');
  const pagination = document.getElementById('daily60-pagination');

  function renderPage(page) {{
    currentPage = page;
    tbody.innerHTML = '';
    const start = (page - 1) * PAGE_SIZE;
    rows.slice(start, start + PAGE_SIZE).forEach(row => {{
      const c = row.pl >= 0 ? 'pos' : 'neg';
      tbody.innerHTML += `<tr>
        <td>${{row.date}}</td>
        <td class="${{c}}">${{row.pl >= 0 ? '' : '-'}}NT$${{Math.abs(row.pl).toLocaleString('zh-TW', {{ maximumFractionDigits: 0 }})}}</td>
      </tr>`;
    }});
    renderPagination();
  }}

  function renderPagination() {{
    const btnStyle = (active) => `style="padding:4px 12px;border-radius:4px;border:1px solid #dce1e7;
      background:${{active ? '#1a3c5e' : '#fff'}};color:${{active ? '#fff' : '#0f1923'}};
      font-size:12px;cursor:${{active ? 'default' : 'pointer'}};font-family:inherit;"`;
    let html = '';
    html += `<button ${{btnStyle(false)}} ${{currentPage===1?'disabled':''}} onclick="d60GoPage(${{currentPage-1}})">&#8249;</button>`;
    for (let p = 1; p <= totalPages; p++) {{
      html += `<button ${{btnStyle(p===currentPage)}} onclick="d60GoPage(${{p}})">${{p}}</button>`;
    }}
    html += `<button ${{btnStyle(false)}} ${{currentPage===totalPages?'disabled':''}} onclick="d60GoPage(${{currentPage+1}})">&#8250;</button>`;
    pagination.innerHTML = html;
  }}

  window.d60GoPage = function(p) {{
    if (p < 1 || p > totalPages) return;
    renderPage(p);
  }};

  renderPage(1);
}})();

// ── Heatmap ──────────────────────────────────────────────────────────────────
(function() {{
  const metrics = [
    {{ key: 'pl',      label: '年度損益(萬)',  higherBetter: true  }},
    {{ key: 'mdd',     label: 'MDD(萬)',        higherBetter: true  }},
    {{ key: 'pl_mdd',  label: '風報比',          higherBetter: true  }},
    {{ key: 'sharpe',  label: 'Sharpe',          higherBetter: true  }},
    {{ key: 'sortino', label: 'Sortino',         higherBetter: true  }},
  ];
  function heatColor(val, min, max, higherBetter) {{
    if (val === null || isNaN(val)) return '#eef0f2';
    let t = (max === min) ? 0.5 : (val - min) / (max - min);
    if (!higherBetter) t = 1 - t;
    t = Math.max(0, Math.min(1, t));
    return `hsl(${{Math.round(t * 120)}}, 58%, 83%)`;
  }}
  const years = HEATMAP.map(r => r.year);
  let html = '<table class="heatmap-tbl"><thead><tr><th class="hm-label-cell"></th>';
  years.forEach(y => {{ html += `<th class="hm-year-cell">${{y}}</th>`; }});
  html += '</tr></thead><tbody>';
  metrics.forEach(m => {{
    const vals = HEATMAP.map(r => r[m.key]);
    const valid = vals.filter(v => v !== null && !isNaN(v));
    const minV = valid.length ? Math.min(...valid) : 0;
    const maxV = valid.length ? Math.max(...valid) : 0;
    const dec = (m.key === 'pl' || m.key === 'mdd') ? 1 : 2;
    html += `<tr><td class="hm-label-cell">${{m.label}}</td>`;
    vals.forEach(v => {{
      const bg  = heatColor(v, minV, maxV, m.higherBetter);
      const txt = (v !== null && !isNaN(v)) ? v.toFixed(dec) : '–';
      html += `<td class="hm-cell" style="background:${{bg}}">${{txt}}</td>`;
    }});
    html += '</tr>';
  }});
  html += '</tbody></table>';
  document.getElementById('heatmap-container').innerHTML = html;
  const pls      = HEATMAP.map(r => r.pl);
  const mdds     = HEATMAP.map(r => r.mdd);
  const sharpes  = HEATMAP.map(r => r.sharpe).filter(v => v !== null);
  const sortinos = HEATMAP.map(r => r.sortino).filter(v => v !== null);
  const lossYrs  = HEATMAP.filter(r => r.pl < 0).map(r => r.year);
  const avgPl   = (pls.reduce((a,b) => a+b, 0) / pls.length).toFixed(1);
  const maxMdd  = Math.min(...mdds).toFixed(1);
  const avgSh   = sharpes.length  ? (sharpes.reduce((a,b)=>a+b,0)/sharpes.length).toFixed(2)  : '–';
  const avgSo   = sortinos.length ? (sortinos.reduce((a,b)=>a+b,0)/sortinos.length).toFixed(2) : '–';
  document.getElementById('heatmap-summary').innerHTML = `
    <p style="margin-top:14px;font-size:13px;line-height:2;color:var(--ink)">
      每年平均損益：<strong style="color:var(--green)">${{avgPl}} 萬</strong>　
      最大 MDD：<strong style="color:var(--red)">${{maxMdd}} 萬</strong>　
      平均 Sharpe：<strong style="color:var(--ink)">${{avgSh}}</strong>　
      平均 Sortino：<strong style="color:var(--ink)">${{avgSo}}</strong>　
      虧損年份：<strong style="color:var(--red)">${{lossYrs.length ? lossYrs.join(', ') : '無'}}</strong>
    </p>
  `;
}})();
</script>
</body>
</html>
"""

# ── 6. 主程式 ─────────────────────────────────────────────────────────────────

print('📂 讀取策略資料...')
strategy_dict = read_strategies()

print('🔧 合併績效...')
pl_df, oi_df = build_combined(strategy_dict)

for fname, w in stgy_dict_plus.items():
    if fname in pl_df.columns:
        pl_df[fname] *= w

daily_pl = pl_df.sum(axis=1)
plt_pl = daily_pl[daily_pl.index >= DISPLAY_START]

print('📊 計算指標...')
m = calc_metrics(plt_pl)

plt_cumsum = plt_pl.cumsum()
plt_max = plt_cumsum.cummax()
plt_dd = plt_cumsum - plt_max

total = m['total']
mdd = m['mdd']
calmar = m['calmar']
sharpe = m['sharpe']
mcl = m['max_consec_loss']
mcw = m['max_consec_win']

recent60 = plt_pl[plt_pl != 0].tail(60)
daily60_data = [
    {'date': str(d.date()), 'pl': round(float(v), 0)}
    for d, v in zip(recent60.index, recent60.values)
]

print('📊 計算歷年熱圖資料...')
swing_nq_pl = read_swing_nq()
heatmap_rows = calc_heatmap_data(swing_nq_pl)

print('✍️ 產生 HTML...')
html = HTML_TEMPLATE.format(
    title=REPORT_TITLE,
    subtitle=REPORT_SUBTITLE,
    gen_date=datetime.date.today().strftime('%Y-%m-%d'),
    display_start=DISPLAY_START,
    total_fmt=fmt_ntd(total),
    total_cls=cls(total),
    mdd_fmt=fmt_ntd(mdd),
    calmar_fmt=f'{calmar:.2f}' if not np.isnan(calmar) else 'N/A',
    sharpe_fmt=f'{sharpe:.2f}' if not np.isnan(sharpe) else 'N/A',
    mcl_fmt=str(int(mcl)),
    mcw_fmt=str(int(mcw)),
    daily60_json=json.dumps(daily60_data, ensure_ascii=False),
    equity_json=json.dumps({
        'x': [str(d.date()) for d in plt_cumsum.index],
        'y': [round(float(v), 2) for v in plt_cumsum.values],
    }, ensure_ascii=False),
    dd_json=json.dumps({
        'x': [str(d.date()) for d in plt_dd.index],
        'y': [round(float(v), 2) for v in plt_dd.values],
    }, ensure_ascii=False),
    heatmap_json=json.dumps(heatmap_rows, ensure_ascii=False),
    heatmap_start=HEATMAP_START,
    heatmap_end=HEATMAP_END,
)

out = Path(REPO_PATH) / 'index.html'
out.write_text(html, encoding='utf-8')

print(f'\n✅ 完成！報告已輸出到: {out.resolve()}')

git_auto_push(REPO_PATH, "index.html")
print('👉 GitHub Pages 會在 push 後自動更新。')



#%%
import requests

def LY_TG(token='6750173248:AAG94afLxKmzY86uOQdz7hPdom8Kp5hayD8', 
                                   chat_ids=['-1002697555642'], 
                                   message=None, photo_path=None):
    """
    通用函數，用於發送 Telegram 文字消息或圖片。

    :param token: Telegram Bot 的 API Token
    :param chat_ids: 目標聊天的 chat_id 列表
    :param message: 要發送的文字消息（可選）
    :param photo_path: 要發送的圖片路徑（可選）
    """
    if not message and not photo_path:
        raise ValueError("至少需要提供 message 或 photo_path 其中之一！")
    
    # 發送文字消息
    if message:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        for chat_id in chat_ids:
            data = {
                'chat_id': chat_id,
                'text': message
            }
            response = requests.post(url, data=data)
            if response.status_code == 200:
                print(f"文字消息已成功發送到 chat_id: {chat_id}")
            else:
                print(f"發送文字消息到 chat_id {chat_id} 失敗: {response.status_code}, {response.text}")

    # 發送圖片
    if photo_path:
        url = f"https://api.telegram.org/bot{token}/sendPhoto"
        for chat_id in chat_ids:
            with open(photo_path, "rb") as photo:
                data = {"chat_id": chat_id}
                files = {"photo": photo}
                response = requests.post(url, data=data, files=files)
                if response.status_code == 200:
                    print(f"圖片已成功發送到 chat_id: {chat_id}")
                else:
                    print(f"發送圖片到 chat_id {chat_id} 失敗: {response.status_code}, {response.text}")


# %%
LY_TG(message="投組績效報告已更新！請前往 GitHub Pages 查看最新報告。")
# %%
