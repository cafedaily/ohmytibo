#!/usr/bin/env python3
"""Render data/processed/*.json into a single static dashboard (site/index.html)."""
import html
import json
import math
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
PROC = ROOT / "data" / "processed"
SITE = ROOT / "site"

PALETTE = {
    "surface": "#1a1a19",
    "plane": "#0d0d0d",
    "ink": "#f0efec",
    "ink2": "#c3c2b7",
    "muted": "#898781",
    "grid": "#2c2c2a",
    "axis": "#383835",
    "s1": "#3987e5",
    "s2": "#d95926",
    "good": "#0ca30c",
    "warning": "#fab219",
}


def esc(s):
    return html.escape(str(s), quote=True)


def load(name):
    return json.loads((PROC / name).read_text(encoding="utf-8"))


def pct(x):
    return f"{x * 100:.0f}%"


# ------------------------------------------------------------------ charts

def forecast_chart(fc):
    """Cumulative probability by day: single series columns, modal day labeled."""
    rows = fc["weekly"]
    if not rows:
        return ""
    W, H = 720, 240
    ml, mr, mt, mb = 44, 16, 22, 46
    pw, ph = W - ml - mr, H - mt - mb
    n = len(rows)
    band = pw / n
    bar_w = min(24, band - 6)
    peak = max(range(n), key=lambda i: rows[i]["p"])
    parts = []
    for tick in (0, 0.25, 0.5, 0.75, 1.0):
        y = mt + ph * (1 - tick)
        parts.append(f'<line x1="{ml}" y1="{y:.1f}" x2="{W - mr}" y2="{y:.1f}" stroke="{PALETTE["grid"]}" stroke-width="1"/>')
        parts.append(f'<text x="{ml - 8}" y="{y + 4:.1f}" text-anchor="end" class="ax">{int(tick * 100)}%</text>')
    for i, r in enumerate(rows):
        x = ml + band * i + (band - bar_w) / 2
        h = max(1.5, ph * r["p"])
        y = mt + ph - h
        fill = PALETTE["s1"] if i != peak else PALETTE["s1"]
        parts.append(
            f'<g class="col" tabindex="0" data-tip="{esc(r["date"])} · 累计 {pct(r["p"])}">'
            f'<rect x="{x:.1f}" y="{mt}" width="{bar_w:.1f}" height="{ph}" fill="transparent"/>'
            f'<rect class="bar" x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{h:.1f}" rx="4" fill="{fill}"/>'
            f'<text x="{x + bar_w / 2:.1f}" y="{mt + ph + 18}" text-anchor="middle" class="ax">{esc(r["date"][5:])}</text>'
            f"</g>")
    px = ml + band * peak + band / 2
    py = mt + ph * (1 - rows[peak]["p"])
    parts.append(f'<text x="{px:.1f}" y="{py - 10:.1f}" text-anchor="middle" class="val">{pct(rows[peak]["p"])}</text>')
    parts.append(f'<line x1="{ml}" y1="{mt + ph}" x2="{W - mr}" y2="{mt + ph}" stroke="{PALETTE["axis"]}" stroke-width="1"/>')
    return (f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="未来 10 天每日累计重置概率">'
            + "".join(parts) + "</svg>")


def nice_step(top, target=4):
    raw = max(1, top / target)
    mag = 10 ** math.floor(math.log10(raw))
    for m in (1, 2, 2.5, 5, 10):
        if raw <= m * mag:
            return max(1, int(m * mag))
    return max(1, int(10 * mag))


def activity_chart(metrics):
    """Stacked daily columns: original posts vs replies; resets marked under the axis."""
    rows = metrics["daily"]
    W, H = 720, 260
    ml, mr, mt, mb = 40, 16, 20, 52
    pw, ph = W - ml - mr, H - mt - mb
    n = len(rows)
    band = pw / n
    bar_w = max(2.0, min(14, band - 2))
    top = max(r["posts"] for r in rows) or 1
    parts = []
    step = nice_step(top)
    for tick in range(0, top + step, step):
        y = mt + ph * (1 - tick / top)
        parts.append(f'<line x1="{ml}" y1="{y:.1f}" x2="{W - mr}" y2="{y:.1f}" stroke="{PALETTE["grid"]}" stroke-width="1"/>')
        parts.append(f'<text x="{ml - 8}" y="{y + 4:.1f}" text-anchor="end" class="ax">{tick}</text>')
    for i, r in enumerate(rows):
        x = ml + band * i + (band - bar_w) / 2
        orig = r["posts"] - r["replies"]
        reps = r["replies"]
        h_o = ph * orig / top
        h_r = ph * reps / top
        y_r = mt + ph - h_r
        y_o = y_r - h_o - (2 if orig and reps else 0)  # 2px surface gap inside the stack
        tip = f'{esc(r["date"])} · 原创 {orig} · 回复 {reps}' + (" · 重置" if r["reset"] else "")
        parts.append(f'<g class="col" tabindex="0" data-tip="{tip}">')
        parts.append(f'<rect x="{x - 1:.1f}" y="{mt}" width="{bar_w + 2:.1f}" height="{ph}" fill="transparent"/>')
        if reps:
            parts.append(f'<rect class="bar" x="{x:.1f}" y="{y_r:.1f}" width="{bar_w:.1f}" height="{max(1, h_r):.1f}" '
                         f'rx="{2 if h_r > 3 else 0}" fill="{PALETTE["s2"]}"/>')
        if orig:
            parts.append(f'<rect class="bar" x="{x:.1f}" y="{y_o:.1f}" width="{bar_w:.1f}" height="{max(1, h_o):.1f}" '
                         f'rx="{2 if h_o > 3 else 0}" fill="{PALETTE["s1"]}"/>')
        if r["reset"]:
            cx = x + bar_w / 2
            parts.append(f'<circle cx="{cx:.1f}" cy="{mt + ph + 10}" r="4" fill="{PALETTE["good"]}" '
                         f'stroke="{PALETTE["surface"]}" stroke-width="2"/>')
        parts.append("</g>")
    step = max(1, n // 8)
    for i in range(0, n, step):
        x = ml + band * i + band / 2
        parts.append(f'<text x="{x:.1f}" y="{mt + ph + 34}" text-anchor="middle" class="ax">{esc(rows[i]["date"][5:])}</text>')
    parts.append(f'<line x1="{ml}" y1="{mt + ph}" x2="{W - mr}" y2="{mt + ph}" stroke="{PALETTE["axis"]}" stroke-width="1"/>')
    return (f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="每日发帖量，按原创与回复拆分，重置日有标记">'
            + "".join(parts) + "</svg>")


def hotword_chart(hw):
    rows = hw["top"][:15]
    if not rows:
        return ""
    row_h, W = 26, 720
    ml, mr = 96, 64
    H = row_h * len(rows) + 16
    pw = W - ml - mr
    top = max(r["count_7d"] for r in rows) or 1
    parts = []
    for i, r in enumerate(rows):
        y = 8 + i * row_h
        w = pw * r["count_7d"] / top
        parts.append(f'<g class="col" tabindex="0" data-tip="{esc(r["term"])} · 7 天 {r["count_7d"]} 次 · 环比提升 {r["lift"]:+.1f} bit">')
        parts.append(f'<rect x="0" y="{y - 2}" width="{W}" height="{row_h}" fill="transparent"/>')
        parts.append(f'<text x="{ml - 10}" y="{y + 12}" text-anchor="end" class="lbl">{esc(r["term"])}</text>')
        parts.append(f'<rect class="bar" x="{ml}" y="{y + 1}" width="{max(2, w):.1f}" height="14" rx="4" fill="{PALETTE["s1"]}"/>')
        parts.append(f'<text x="{ml + w + 8:.1f}" y="{y + 12}" class="val">{r["count_7d"]}</text>')
        parts.append("</g>")
    return f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="最近 7 天高频词">' + "".join(parts) + "</svg>"


# ------------------------------------------------------------------ tables

def surge_table(hw):
    rows = hw["surge"][:18]
    body = "".join(
        f'<tr><td class="term">{esc(r["term"])}{" · 短语" if r["kind"] == "phrase" else ""}</td><td class="n">{r["count_7d"]}</td>'
        f'<td class="n">{r["count_28d_before"]}</td><td class="n">{r["lift"]:+.1f}</td>'
        f'<td class="ex">{esc(r["sample"][:110])}<a href="{esc(r["sample_url"])}" target="_blank" rel="noopener">↗</a></td></tr>'
        for r in rows)
    return ('<table><thead><tr><th>词</th><th class="n">7 天</th><th class="n">前 28 天</th>'
            '<th class="n">提升 (bit)</th><th>出处</th></tr></thead><tbody>' + body + "</tbody></table>")


def mentions_table(hw):
    body = "".join(
        f'<tr><td class="term">@{esc(r["handle"])}</td><td class="n">{r["replies"]}</td>'
        f'<td class="n">{r["named"]}</td></tr>' for r in hw["mentions"][:12])
    return ('<table><thead><tr><th>账号</th><th class="n">被回复</th><th class="n">被提及</th></tr></thead>'
            '<tbody>' + body + "</tbody></table>")


def topics_table(hw, total_posts):
    body = "".join(
        f'<tr><td class="term">{esc(t["topic"])}</td><td class="n">{t["posts"]}</td>'
        f'<td class="n">{t["share"] * 100:.0f}%</td></tr>' for t in hw["topics"])
    return ('<table><thead><tr><th>话题簇</th><th class="n">帖子</th><th class="n">占比</th></tr></thead>'
            '<tbody>' + body + "</tbody></table>")


def lexicon_table(hw):
    words = ["reset", "banked", "eod", "usage", "vote", "day"]
    head = "".join(f'<th class="n">{w}</th>' for w in words)
    body = "".join(
        f'<tr><td class="term">{esc(r["label"])}</td>' + "".join(f'<td class="n">{r.get(w, 0)}</td>' for w in words) + "</tr>"
        for r in hw["reset_lexicon"])
    return f'<table><thead><tr><th>窗口</th>{head}</tr></thead><tbody>{body}</tbody></table>'


def reset_posts_list(hw):
    items = "".join(
        f'<li><a href="{esc(p["url"])}" target="_blank" rel="noopener">{esc(p["ts"][:16].replace("T", " "))} UTC</a>'
        f'<span class="txt">{esc(p["text"])}</span></li>' for p in hw["reset_posts"])
    return f'<ol class="posts">{items}</ol>'


def forecast_rows(fc):
    return "".join(f'<tr><td class="term">{esc(r["date"])}</td><td class="n">{pct(r["p"])}</td></tr>'
                   for r in fc["weekly"])


# ------------------------------------------------------------------ page

def build():
    fc = load("forecast.json")
    hw = load("hotwords.json")
    metrics = load("metrics.json")
    bt = fc.get("backtest") or {}
    last_reset = fc["last_reset_local"]
    last_reset_utc = fc["last_reset"].replace("T", " ")[:16]
    modal = fc["modal_reset_local"]
    modal_utc = fc["modal_reset_at"].replace("T", " ")[:16]
    generated = metrics["generated_at_local"]
    promise = fc.get("pending_promise")

    hero = pct(fc["p_24h"])
    data = json.dumps({
        "generated_at": metrics["generated_at"],
        "forecast": {k: fc[k] for k in ("p_24h", "p_48h", "p_72h", "p_7d", "last_reset", "modal_reset_at")},
    }, ensure_ascii=False)

    page = f"""<!doctype html>
<html lang="zh-Hans" data-theme="dark">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ohmytibo · Tibo 重置预测与热点词</title>
<meta name="description" content="@thsottiaux 的公开推文与回复分析：Codex/ChatGPT 额度重置概率预测、重置节奏、热点词与话题分布。">
<style>
:root{{
  color-scheme: dark;
  --surface:{PALETTE["surface"]}; --plane:{PALETTE["plane"]};
  --ink:{PALETTE["ink"]}; --ink2:{PALETTE["ink2"]}; --muted:{PALETTE["muted"]};
  --grid:{PALETTE["grid"]}; --axis:{PALETTE["axis"]};
  --s1:{PALETTE["s1"]}; --s2:{PALETTE["s2"]}; --good:{PALETTE["good"]}; --warn:{PALETTE["warning"]};
  --ring:rgba(255,255,255,.10);
}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--plane);color:var(--ink);
  font:15px/1.55 system-ui,-apple-system,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;}}
.wrap{{max-width:1040px;margin:0 auto;padding:36px 20px 80px}}
header{{display:flex;gap:20px;align-items:flex-start;justify-content:space-between;flex-wrap:wrap;margin-bottom:28px}}
h1{{font-size:22px;margin:0 0 6px;font-weight:650;letter-spacing:-.01em}}
.sub{{color:var(--ink2);font-size:14px;margin:0}}
.chip{{display:inline-flex;align-items:center;gap:7px;border:1px solid var(--ring);border-radius:999px;
  padding:6px 12px;font-size:13px;color:var(--ink2)}}
.dot{{width:8px;height:8px;border-radius:50%;background:var(--good);flex:none}}
.dot.warn{{background:var(--warn)}}
.grid{{display:grid;gap:16px}}
.stats{{grid-template-columns:repeat(auto-fit,minmax(180px,1fr));margin-bottom:16px}}
.card{{background:var(--surface);border:1px solid var(--ring);border-radius:14px;padding:18px 18px 16px}}
.card h2{{font-size:14px;margin:0 0 2px;font-weight:600}}
.card .note{{color:var(--muted);font-size:12.5px;margin:0 0 14px}}
.hero{{padding:22px}}
.hero .k{{color:var(--ink2);font-size:13px;margin:0 0 6px}}
.hero .v{{font-size:52px;line-height:1.05;font-weight:650;letter-spacing:-.02em}}
.hero .d{{color:var(--muted);font-size:12.5px;margin-top:8px}}
.stat .v{{font-size:26px;font-weight:600;margin:2px 0 0}}
.stat .k{{color:var(--ink2);font-size:13px;margin:0}}
svg{{width:100%;height:auto;display:block;overflow:visible}}
.ax{{fill:var(--muted);font-size:11px;font-variant-numeric:tabular-nums}}
.lbl{{fill:var(--ink2);font-size:12.5px}}
.val{{fill:var(--ink);font-size:12px;font-variant-numeric:tabular-nums}}
.col{{cursor:default;outline:none}}
.col:hover .bar,.col:focus-visible .bar{{filter:brightness(1.18)}}
.col:focus-visible rect{{stroke:var(--ink);stroke-width:1;stroke-opacity:.35}}
.legend{{display:flex;gap:18px;flex-wrap:wrap;color:var(--ink2);font-size:12.5px;margin:10px 0 0}}
.legend span{{display:inline-flex;align-items:center;gap:7px}}
.sw{{width:11px;height:11px;border-radius:3px;flex:none}}
table{{width:100%;border-collapse:collapse;font-size:13px}}
th{{text-align:left;color:var(--muted);font-weight:500;padding:6px 8px;border-bottom:1px solid var(--axis);font-size:12px}}
td{{padding:7px 8px;border-bottom:1px solid var(--grid);vertical-align:top}}
td.n,th.n{{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}}
td.term{{font-weight:550;white-space:nowrap}}
td.ex{{color:var(--ink2);font-size:12.5px}}
td.ex a{{color:var(--s1);text-decoration:none;margin-left:4px}}
details{{margin-top:12px}}
summary{{cursor:pointer;color:var(--muted);font-size:12.5px;list-style:none}}
summary::-webkit-details-marker{{display:none}}
summary::before{{content:"▸ ";}}
details[open] summary::before{{content:"▾ ";}}
ol.posts{{margin:8px 0 0;padding-left:20px;color:var(--ink2);font-size:13px}}
ol.posts li{{margin:7px 0}}
ol.posts a{{color:var(--s1);text-decoration:none;font-variant-numeric:tabular-nums}}
ol.posts .txt{{display:block;color:var(--ink);margin-top:2px}}
.tip{{position:fixed;pointer-events:none;background:#000;color:var(--ink);border:1px solid var(--ring);
  border-radius:8px;padding:6px 9px;font-size:12px;opacity:0;transition:opacity .1s;z-index:9;white-space:nowrap}}
footer{{color:var(--muted);font-size:12px;margin-top:28px;line-height:1.7}}
footer a{{color:var(--ink2)}}
@media (prefers-reduced-motion:reduce){{*{{transition:none!important}}}}
</style>
</head>
<body>
<div class="wrap">
<header>
  <div>
    <h1>ohmytibo · Tibo 重置预测</h1>
    <p class="sub">@thsottiaux（OpenAI，Codex &amp; ChatGPT）的公开推文与回复 · 样本 {metrics["posts"]} 条 / {metrics["days_covered"]} 天</p>
  </div>
  <div class="chip"><span class="dot"></span>数据生成于 {generated} 北京时间</div>
</header>

<div class="grid stats">
  <div class="card hero">
    <p class="k">未来 24 小时出现重置的概率</p>
    <div class="v">{hero}</div>
    <div class="d">48 小时 {pct(fc["p_48h"])} · 72 小时 {pct(fc["p_72h"])} · 7 天 {pct(fc["p_7d"])}</div>
  </div>
  <div class="card stat"><p class="k">上次重置</p><div class="v">{last_reset[11:16]} <span style="font-size:14px;color:var(--ink2);font-weight:400">BJT</span></div>
    <div class="d" style="color:var(--muted);font-size:12.5px;margin-top:6px">{last_reset[:10]} · {fc["hours_since_last_reset"]:.1f} 小时前<br>UTC {last_reset_utc[11:16]}</div></div>
  <div class="card stat"><p class="k">最可能的重置时点</p><div class="v">{modal[11:16]} <span style="font-size:14px;color:var(--ink2);font-weight:400">BJT</span></div>
    <div class="d" style="color:var(--muted);font-size:12.5px;margin-top:6px">{modal[:10]} · 按日模型取概率峰值<br>UTC {modal_utc[11:16]}</div></div>
  <div class="card stat"><p class="k">平均间隔 / 近 6 次</p><div class="v">{fc["recent_mean_gap_days"]:.1f} 天</div>
    <div class="d" style="color:var(--muted);font-size:12.5px;margin-top:6px">全样本均值 {fc["mean_gap_days"]:.2f} 天 · 中位 {fc["median_gap_days"]:.2f} 天</div></div>
</div>

<div class="card" style="margin-bottom:16px">
  <h2>预测是怎么算出来的</h2>
  <p class="note">用「距离上次重置过去多少天」做离散风险模型（日粒度），再用历史小时分布把概率摊到 24 小时曲线上；
  若检测到新的前瞻性承诺（“by EOD”“明天”等），概率整体前移。回测 {bt.get("days", 0)} 天：
  对数损失 {bt.get("logloss", 0):.3f}，基准 {bt.get("logloss_baseline", 0):.3f}，技巧分 {bt.get("skill", 0):+.2f}
  （约等于基准，说明重置节奏本身有记忆性但噪声很大）。{'当前存在未兑现的承诺。' if promise else '当前没有新的未兑现承诺。'}</p>
</div>

<div class="grid" style="grid-template-columns:1fr;gap:16px">
  <div class="card">
    <h2>未来 10 天的累计重置概率</h2>
    <p class="note">截至当日结束至少发生一次重置的概率 · 峰值日直接标注</p>
    {forecast_chart(fc)}
    <details><summary>表格视图</summary><table><thead><tr><th>日期</th><th class="n">累计概率</th></tr></thead>
      <tbody>{forecast_rows(fc)}</tbody></table></details>
  </div>

  <div class="card">
    <h2>每日发帖节奏与重置标记</h2>
    <p class="note">最近 {metrics["days_covered"]} 天 · 按 UTC 日切分 · 轴下绿点 = 当日有全局重置</p>
    {activity_chart(metrics)}
    <div class="legend">
      <span><i class="sw" style="background:{PALETTE["s1"]}"></i>原创帖</span>
      <span><i class="sw" style="background:{PALETTE["s2"]}"></i>回复</span>
      <span><i class="sw" style="background:{PALETTE["good"]};border-radius:50%"></i>重置日</span>
    </div>
    <details><summary>表格视图（最近 10 天）</summary>
      <table><thead><tr><th>日期</th><th class="n">原创</th><th class="n">回复</th><th class="n">获赞</th><th class="n">重置</th></tr></thead>
      <tbody>{"".join(f'<tr><td class="term">{r["date"]}</td><td class="n">{r["posts"] - r["replies"]}</td><td class="n">{r["replies"]}</td><td class="n">{r["likes"]:,}</td><td class="n">{r["reset"]}</td></tr>' for r in metrics["daily"][-10:])}</tbody></table>
    </details>
  </div>

  <div class="card">
    <h2>最近 7 天高频词</h2>
    <p class="note">去掉链接、@ 与停用词后的正文词频（最近 {hw["window_days"]} 天共 {hw["tokens_recent"]:,} 个词元）· 悬停看提升幅度</p>
    {hotword_chart(hw)}
  </div>

  <div class="card">
    <h2>热词：相对前 28 天的异动</h2>
    <p class="note">提升 = 7 天词频 vs 前 28 天基线的对数提升（bit）· 含双词短语 · 7 天窗口样本小，波动大</p>
    {surge_table(hw)}
  </div>

  <div class="card">
    <h2>话题分布（最近 14 天）</h2>
    <p class="note">关键词规则归类 · 一条帖子可同时命中多个话题</p>
    {topics_table(hw, metrics["posts"])}
  </div>

  <div class="card">
    <h2>重置话语的密度变化</h2>
    <p class="note">每 7 天窗口内出现该词的帖子数 · 看“reset / banked / EOD”这类词何时抬升</p>
    {lexicon_table(hw)}
  </div>

  <div class="card">
    <h2>最近的重置相关发言</h2>
    <p class="note">重置日里带 reset 语义的帖子，按时间倒序</p>
    {reset_posts_list(hw)}
  </div>

  <div class="card">
    <h2>互动最多的账号（30 天）</h2>
    <p class="note">他回复过或正文里 @ 过的人</p>
    {mentions_table(hw)}
  </div>
</div>

<footer>
  数据来源：<a href="https://tiboreset.com/X-posts" target="_blank" rel="noopener">tiboreset.com</a>（推文镜像）与
  <a href="https://tiboreset.com/feed.xml" target="_blank" rel="noopener">其 Atom feed</a>（重置事件）。
  非 OpenAI 官方数据，概率为统计估计，不构成任何承诺。
  仓库：<a href="https://github.com/cafedaily/ohmytibo" target="_blank" rel="noopener">cafedaily/ohmytibo</a>。
</footer>
</div>
<div class="tip" id="tip" role="status"></div>
<script>
const tip = document.getElementById('tip');
function show(e, text){{
  tip.textContent = text; tip.style.opacity = '1';
  const pad = 14, w = tip.offsetWidth, h = tip.offsetHeight;
  let x = (e.clientX ?? 0) + pad, y = (e.clientY ?? 0) - h - pad;
  if (x + w > innerWidth - 8) x = innerWidth - w - 8;
  if (y < 8) y = (e.clientY ?? 0) + pad;
  tip.style.left = x + 'px'; tip.style.top = y + 'px';
}}
function hide(){{ tip.style.opacity = '0'; }}
document.querySelectorAll('[data-tip]').forEach(el => {{
  el.addEventListener('pointermove', e => show(e, el.dataset.tip));
  el.addEventListener('pointerleave', hide);
  el.addEventListener('focus', e => {{
    const r = el.getBoundingClientRect();
    show({{clientX: r.left + r.width / 2, clientY: r.top}}, el.dataset.tip);
  }});
  el.addEventListener('blur', hide);
}});
window.__OHMYTIBO__ = {data};
</script>
</body>
</html>
"""
    SITE.mkdir(parents=True, exist_ok=True)
    (SITE / "index.html").write_text(page, encoding="utf-8")
    print(f"wrote {SITE / 'index.html'} ({len(page):,} bytes)")


if __name__ == "__main__":
    build()
