#!/usr/bin/env python3
"""Render data/processed/*.json into a static dashboard (site/index.html + site/data.json)."""
import html
import json
import pathlib

import state

ROOT = pathlib.Path(__file__).resolve().parent.parent
PROC = ROOT / "data" / "processed"
SITE = ROOT / "site"
REFRESH_MINUTES = 180  # cadence of .github/workflows/refresh.yml; drives the freshness light

PAL = {
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


# ------------------------------------------------------------------ server tables

def forecast_rows(fc):
    return "".join(f'<tr><td class="term">{esc(r["date"])}</td><td class="n">{pct(r["p"])}</td></tr>'
                   for r in fc["weekly"])


def surge_table(hw):
    rows = hw["surge"][:18]
    body = "".join(
        f'<tr><td class="term">{esc(r["term"])}{" · 短语" if r["kind"] == "phrase" else ""}</td>'
        f'<td class="n">{r["count_7d"]}</td><td class="n">{r["count_28d_before"]}</td>'
        f'<td class="n">{r["lift"]:+.1f}</td>'
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


def topics_table(hw):
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
        f'<li><a href="{esc(p["url"])}" target="_blank" rel="noopener">{esc(p["ts"][5:16])}</a>'
        f'<span class="txt">{esc(p["text"])}</span></li>' for p in hw["reset_posts"])
    return f'<ol class="posts">{items}</ol>'


def daily_table(metrics):
    rows = "".join(
        f'<tr><td class="term">{r["date"]}</td><td class="n">{r["posts"] - r["replies"]}</td>'
        f'<td class="n">{r["replies"]}</td><td class="n">{r["likes"]:,}</td><td class="n">{r["reset"]}</td></tr>'
        for r in metrics["daily"][-10:])
    return ('<table><thead><tr><th>日期</th><th class="n">原创</th><th class="n">回复</th>'
            '<th class="n">获赞</th><th class="n">重置</th></tr></thead><tbody>' + rows + "</tbody></table>")


# ------------------------------------------------------------------ template

TEMPLATE = r"""<!doctype html>
<html lang="zh-Hans" data-theme="dark">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>OH MY TIBO · 重置预测与热点词</title>
<meta name="description" content="OH MY TIBO — 跟踪 @thsottiaux 的公开推文与回复：Codex / ChatGPT 额度重置概率预测、重置节奏、热点词与话题分布。">
<meta name="theme-color" content="#0d0d0d">
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><circle cx='16' cy='16' r='13' fill='none' stroke='%233987e5' stroke-width='3'/><circle cx='16' cy='16' r='5' fill='%23d95926'/></svg>">
<style>
:root{
  color-scheme: dark;
  --surface: rgba(26,26,25,.82);
  --solid:#1a1a19;
  --plane:#0d0d0d;
  --ink:#f0efec; --ink2:#c3c2b7; --muted:#898781;
  --grid:#2c2c2a; --axis:#383835;
  --s1:#3987e5; --s2:#d95926; --good:#0ca30c; --warn:#fab219; --bad:#e5484d;
  --ring:rgba(255,255,255,.10);
}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;background:var(--plane);color:var(--ink);
  font:15px/1.55 system-ui,-apple-system,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;
  -webkit-font-smoothing:antialiased}
#bg{position:fixed;inset:0;width:100%;height:100%;z-index:0;pointer-events:none;opacity:.62}
.scrim{position:fixed;inset:0;z-index:0;pointer-events:none;
  background:radial-gradient(1100px 620px at 50% -8%,rgba(57,135,229,.13),transparent 62%),
             radial-gradient(820px 520px at 88% 12%,rgba(217,89,38,.08),transparent 60%),
             linear-gradient(180deg,rgba(13,13,13,.18),rgba(13,13,13,.78) 72%,#0d0d0d)}
.wrap{max-width:1080px;margin:0 auto;padding:34px 20px 96px;position:relative;z-index:1}
header{display:flex;gap:22px;align-items:flex-end;justify-content:space-between;flex-wrap:wrap;margin-bottom:26px}
.brand{font-size:clamp(30px,5.2vw,46px);line-height:1;letter-spacing:.14em;font-weight:750;margin:0;
  background:linear-gradient(96deg,#f0efec 8%,#9cc4f4 38%,#f0efec 58%,#e79a74 82%,#f0efec 98%);
  background-size:260% 100%;-webkit-background-clip:text;background-clip:text;color:transparent;
  animation:shimmer 14s linear infinite}
@keyframes shimmer{to{background-position:260% 0}}
.tagline{color:var(--ink2);font-size:13.5px;margin:9px 0 0;letter-spacing:.02em}
.tagline b{color:var(--ink);font-weight:600}
.live{display:flex;flex-direction:column;align-items:flex-end;gap:6px;font-size:12.5px;color:var(--muted)}
.chip{display:inline-flex;align-items:center;gap:8px;border:1px solid var(--ring);border-radius:999px;
  padding:6px 13px;color:var(--ink2);background:rgba(26,26,25,.55);backdrop-filter:blur(8px)}
.pulse{width:8px;height:8px;border-radius:50%;background:var(--good);flex:none;position:relative}
.pulse::after{content:"";position:absolute;inset:-4px;border-radius:50%;border:1px solid var(--good);
  opacity:.5;animation:pulse 2.4s ease-out infinite}
@keyframes pulse{0%{transform:scale(.6);opacity:.6}100%{transform:scale(1.9);opacity:0}}
.pulse.warn{background:var(--warn)}.pulse.warn::after{border-color:var(--warn)}
.pulse.bad{background:var(--bad)}.pulse.bad::after{border-color:var(--bad)}
.clock{font-variant-numeric:tabular-nums;letter-spacing:.04em}

.grid{display:grid;gap:16px}
.card{background:var(--surface);border:1px solid var(--ring);border-radius:18px;padding:20px;
  backdrop-filter:blur(16px);-webkit-backdrop-filter:blur(16px);
  box-shadow:0 18px 50px -30px rgba(0,0,0,.9), inset 0 1px 0 rgba(255,255,255,.035);
  min-width:0;overflow-x:auto}
.card h2{font-size:14.5px;margin:0 0 3px;font-weight:620;letter-spacing:.01em}
.card .note{color:var(--muted);font-size:12.5px;margin:0 0 14px}
.hero{display:grid;grid-template-columns:200px 1fr;gap:26px;align-items:center;padding:24px;margin-bottom:16px}
@media (max-width:700px){.hero{grid-template-columns:1fr;justify-items:start}}
.ring{position:relative;width:190px;height:190px;flex:none}
.ring svg{width:190px;height:190px;transform:rotate(-90deg);overflow:visible}
.ring .track{fill:none;stroke:#242422;stroke-width:11}
.ring .prog{fill:none;stroke:url(#ringGrad);stroke-width:11;stroke-linecap:round;
  transition:stroke-dashoffset 1.4s cubic-bezier(.16,.84,.24,1)}
.ring .halo{fill:none;stroke:rgba(57,135,229,.22);stroke-width:20;filter:blur(9px)}
.ring-num{position:absolute;inset:0;display:grid;place-content:center;text-align:center}
.ring-num .big{font-size:44px;font-weight:700;letter-spacing:-.03em;line-height:1}
.ring-num .cap{color:var(--muted);font-size:11.5px;letter-spacing:.12em;margin-top:6px}
.hero-body .k{color:var(--ink2);font-size:13px;margin:0}
.hero-body h3{margin:2px 0 12px;font-size:17px;font-weight:600;letter-spacing:-.01em}
.trio{display:flex;gap:26px;flex-wrap:wrap;margin:0 0 16px}
.trio div{min-width:78px}
.trio .v{font-size:20px;font-weight:620;font-variant-numeric:tabular-nums}
.trio .l{color:var(--muted);font-size:11.5px;letter-spacing:.06em}
.countdown{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap;font-size:12.5px;color:var(--ink2)}
.countdown .t{font-size:23px;font-weight:650;letter-spacing:.02em;font-variant-numeric:tabular-nums;color:var(--ink)}
.countdown .sub{color:var(--muted)}
.stats{grid-template-columns:repeat(auto-fit,minmax(180px,1fr));margin-bottom:16px}
.stat .k{color:var(--ink2);font-size:12.5px;margin:0}
.stat .v{font-size:25px;font-weight:620;margin:5px 0 0;letter-spacing:-.01em;font-variant-numeric:tabular-nums}
.stat .d{color:var(--muted);font-size:12px;margin-top:6px;line-height:1.5}

svg.chart{width:100%;height:auto;display:block;overflow:visible}
.ax{fill:var(--muted);font-size:11px;font-variant-numeric:tabular-nums}
.lbl{fill:var(--ink2);font-size:12.5px}
.val{fill:var(--ink);font-size:12px;font-variant-numeric:tabular-nums}
.col{cursor:crosshair;outline:none}
.col:focus-visible rect:not([fill="transparent"]){stroke:var(--ink);stroke-width:1;stroke-opacity:.5}
.bar{transform-box:fill-box;transform-origin:bottom;animation:grow .62s cubic-bezier(.2,.85,.25,1) both;
  animation-delay:calc(var(--i,0)*11ms)}
@keyframes grow{from{transform:scaleY(0)}}
.hbar{transform-box:fill-box;transform-origin:left;animation:growx .6s cubic-bezier(.2,.85,.25,1) both;
  animation-delay:calc(var(--i,0)*16ms)}
@keyframes growx{from{transform:scaleX(0)}}
.fade{animation:fade .5s ease both;animation-delay:calc(var(--i,0)*14ms)}
@keyframes fade{from{opacity:0}to{opacity:1}}
.legend{display:flex;gap:18px;flex-wrap:wrap;color:var(--ink2);font-size:12.5px;margin:12px 0 0}
.legend span{display:inline-flex;align-items:center;gap:7px}
.sw{width:11px;height:11px;border-radius:3px;flex:none}
.tools{display:flex;gap:8px;flex-wrap:wrap;margin:0 0 12px}
.seg{display:inline-flex;background:rgba(255,255,255,.04);border:1px solid var(--ring);border-radius:999px;padding:2px}
.seg button{appearance:none;border:0;background:transparent;color:var(--ink2);font:inherit;font-size:12.5px;
  padding:5px 12px;border-radius:999px;cursor:pointer;transition:color .18s,background .18s}
.seg button[aria-pressed="true"]{background:rgba(57,135,229,.18);color:var(--ink)}
.seg button:hover{color:var(--ink)}
table{width:100%;border-collapse:collapse;font-size:13px}
th{text-align:left;color:var(--muted);font-weight:500;padding:6px 8px;border-bottom:1px solid var(--axis);font-size:12px}
td{padding:7px 8px;border-bottom:1px solid var(--grid);vertical-align:top}
td.n,th.n{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
td.term{font-weight:550;white-space:nowrap}
td.ex{color:var(--ink2);font-size:12.5px}
td.ex a{color:var(--s1);text-decoration:none;margin-left:4px}
details{margin-top:12px}
summary{cursor:pointer;color:var(--muted);font-size:12.5px;list-style:none}
summary::-webkit-details-marker{display:none}
summary::before{content:"▸ "}
details[open] summary::before{content:"▾ "}
ol.posts{margin:8px 0 0;padding-left:20px;color:var(--ink2);font-size:13px}
ol.posts li{margin:8px 0}
ol.posts a{color:var(--s1);text-decoration:none;font-variant-numeric:tabular-nums}
ol.posts .txt{display:block;color:var(--ink);margin-top:3px}
.reveal{opacity:0;transform:translateY(16px);transition:opacity .7s ease,transform .7s cubic-bezier(.2,.8,.2,1)}
.reveal.in{opacity:1;transform:none}
.tip{position:fixed;pointer-events:none;background:rgba(8,8,8,.96);color:var(--ink);border:1px solid var(--ring);
  border-radius:9px;padding:6px 10px;font-size:12px;opacity:0;transition:opacity .12s;z-index:9;white-space:nowrap;
  box-shadow:0 10px 30px -12px #000}
footer{color:var(--muted);font-size:12px;margin-top:30px;line-height:1.8}
footer a{color:var(--ink2)}
.promise{margin:14px 0 0;font-size:12.5px;color:var(--ink2);border-left:2px solid var(--warn);padding:2px 0 2px 10px}
.promise a{color:var(--warn);text-decoration:none}
.sig-head{display:flex;gap:10px 22px;flex-wrap:wrap;align-items:center;margin:0 0 6px}
.level{display:inline-flex;align-items:center;gap:7px;border-radius:999px;padding:4px 12px;font-size:12.5px;
  border:1px solid var(--ring);background:rgba(255,255,255,.04)}
.level i{width:7px;height:7px;border-radius:50%;background:var(--muted)}
.level.elevated i{background:var(--warn)}.level.high i{background:var(--bad)}
.sig-n{font-size:12.5px;color:var(--muted)}
.sig-n b{color:var(--ink);font-size:17px;font-weight:620;font-variant-numeric:tabular-nums;margin-right:3px}
.sig-list{list-style:none;margin:6px 0 0;padding:0}
.sig-list li{display:grid;grid-template-columns:96px 1fr;gap:4px 14px;padding:10px 0;border-bottom:1px solid var(--grid);
  animation:fade .5s ease both;animation-delay:calc(var(--i,0)*30ms)}
.sig-list li.before{opacity:.5}
.sig-list time{color:var(--muted);font-size:12px;font-variant-numeric:tabular-nums;padding-top:2px}
.sig-list .txt{color:var(--ink);font-size:13px;overflow-wrap:anywhere}
.sig-list .txt a{color:var(--s1);text-decoration:none;margin-left:4px}
.sig-tags{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:4px}
.badge{font-size:11px;line-height:1.6;padding:0 7px;border-radius:999px;border:1px solid var(--ring);color:var(--ink2)}
.badge.k-announce,.badge.k-related{color:#9cc4f4;border-color:rgba(57,135,229,.5)}
.badge.k-reset_post{color:#7fd17f;border-color:rgba(12,163,12,.55)}
.badge.fwd{color:var(--warn);border-color:rgba(250,178,25,.5)}
.badge.after{color:var(--ink);border-color:rgba(240,239,236,.35)}
@media (max-width:560px){.sig-list li{grid-template-columns:1fr}}
.st-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px}
.st{border:1px solid var(--ring);border-radius:12px;padding:12px 14px;background:rgba(255,255,255,.02)}
.st.warn{border-color:rgba(250,178,25,.5)}.st.bad{border-color:rgba(229,72,77,.6)}
.st .k{color:var(--muted);font-size:12px;margin:0;display:flex;align-items:center;gap:7px}
.st .k i{width:7px;height:7px;border-radius:50%;background:var(--good)}
.st.warn .k i{background:var(--warn)}.st.bad .k i{background:var(--bad)}
.st .v{font-size:15px;font-weight:600;margin:5px 0 0}
.st .d{color:var(--muted);font-size:12px;margin-top:4px;line-height:1.5;overflow-wrap:anywhere}
.runs{display:flex;gap:3px;align-items:flex-end;height:26px;margin-top:8px}
.runs span{flex:1;max-width:12px;border-radius:2px;background:var(--good);min-height:6px}
.runs span.bad{background:var(--bad)}.runs span.warn{background:var(--warn)}
@media (prefers-reduced-motion:reduce){
  *,*::before,*::after{animation:none!important;transition:none!important}
  .reveal{opacity:1;transform:none}
  html{scroll-behavior:auto}
}
</style>
</head>
<body>
<canvas id="bg" aria-hidden="true"></canvas>
<div class="scrim" aria-hidden="true"></div>

<div class="wrap">
<header>
  <div>
    <h1 class="brand">OH MY TIBO</h1>
    <p class="tagline"><b>@thsottiaux</b> · OpenAI Codex &amp; ChatGPT · 公开推文 {POSTS} 条 / {DAYS} 天 · 全部时间为北京时间</p>
  </div>
  <div class="live">
    <div class="chip" id="freshChip"><span class="pulse" id="freshDot"></span><span id="freshLabel">数据更新于</span> <span id="updated">{GENERATED}</span></div>
    <div class="clock" id="clock">--:--:-- 北京时间</div>
  </div>
</header>

<section class="card hero reveal" aria-labelledby="hero-h">
  <div class="ring" aria-hidden="true">
    <svg viewBox="0 0 190 190">
      <defs>
        <linearGradient id="ringGrad" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stop-color="#3987e5"/><stop offset="100%" stop-color="#d95926"/>
        </linearGradient>
      </defs>
      <circle class="halo" cx="95" cy="95" r="78"/>
      <circle class="track" cx="95" cy="95" r="78"/>
      <circle class="prog" id="ring" cx="95" cy="95" r="78" stroke-dasharray="490" stroke-dashoffset="490"/>
    </svg>
    <div class="ring-num"><div class="big" id="heroNum">0%</div><div class="cap">24H</div></div>
  </div>
  <div class="hero-body">
    <p class="k">未来 24 小时出现全局重置的概率</p>
    <h3 id="hero-h">他下一步会按下重置按钮吗</h3>
    <div class="trio">
      <div><div class="v" id="p48">—</div><div class="l">48 小时</div></div>
      <div><div class="v" id="p72">—</div><div class="l">72 小时</div></div>
      <div><div class="v" id="p7d">—</div><div class="l">7 天</div></div>
      <div><div class="v" id="gap">—</div><div class="l">平均间隔</div></div>
    </div>
    <div class="countdown">
      <span>距概率峰值 <span class="t" id="countdown">--:--:--</span></span>
      <span class="sub" id="peakAt">—</span>
    </div>
    <p class="promise" id="promise" hidden></p>
  </div>
</section>

<div class="grid stats">
  <div class="card stat reveal"><p class="k">上次重置</p><div class="v" id="lastReset">—</div>
    <div class="d" id="lastResetSub">—</div></div>
  <div class="card stat reveal"><p class="k">最可能的重置时点</p><div class="v" id="modalAt">—</div>
    <div class="d" id="modalSub">—</div></div>
  <div class="card stat reveal"><p class="k">近 6 次平均间隔</p><div class="v" id="recentGap">—</div>
    <div class="d" id="gapSub">—</div></div>
  <div class="card stat reveal"><p class="k">样本内重置次数</p><div class="v" id="resetCount">—</div>
    <div class="d">来自独立追踪器的已核实全局重置</div></div>
</div>

<section class="card reveal" style="margin-bottom:16px" aria-labelledby="sig-h">
  <h2 id="sig-h">重置信号雷达</h2>
  <p class="note">最近提到重置的发言：镜像 feed 的公告 / 相关 / 备注条目，加上镜像标为 Reset、Reset talk 的帖子。
  与已验证重置分开列出，不计入概率模型。</p>
  <div class="sig-head" id="sigHead"></div>
  <ol class="sig-list" id="sigList"></ol>
  <details id="sigMore" hidden><summary>更早的信号</summary><ol class="sig-list" id="sigOlder"></ol></details>
</section>

<section class="card reveal" style="margin-bottom:16px">
  <h2>预测是怎么算出来的</h2>
  <p class="note">以「距离上次重置过去多少天」为状态的离散风险模型（日粒度），再用历史小时分布摊到 24 小时曲线上；
  检测到未兑现的前瞻承诺（“by EOD”“明天”等）时整体前移。回测 <span id="btDays">—</span> 天：
  对数损失 <span id="btLL">—</span>，基准 <span id="btBase">—</span>，技巧分 <span id="btSkill">—</span>。</p>
</section>

<div class="grid" style="gap:16px">
  <section class="card reveal">
    <h2>未来 10 天的累计重置概率</h2>
    <p class="note">截至当日结束至少发生一次重置的概率 · 峰值日直接标注</p>
    <div id="forecastChart"></div>
    <details><summary>表格视图</summary><table><thead><tr><th>日期</th><th class="n">累计概率</th></tr></thead>
      <tbody>{FORECAST_ROWS}</tbody></table></details>
  </section>

  <section class="card reveal">
    <h2>每日发帖节奏与重置标记</h2>
    <p class="note">按北京时间切分 · 轴下绿点 = 当日有全局重置，黄圈 = 当日有 banked 发放 · 点击图例可隐藏对应系列</p>
    <div class="tools">
      <div class="seg" id="rangeSeg" role="group" aria-label="时间范围">
        <button data-range="14" aria-pressed="false">14 天</button>
        <button data-range="30" aria-pressed="false">30 天</button>
        <button data-range="60" aria-pressed="true">60 天</button>
      </div>
    </div>
    <div id="dailyChart"></div>
    <div class="legend" id="dailyLegend">
      <span data-series="orig"><i class="sw" style="background:#3987e5"></i>原创帖</span>
      <span data-series="reps"><i class="sw" style="background:#d95926"></i>回复</span>
      <span><i class="sw" style="background:#0ca30c;border-radius:50%"></i>重置日</span>
      <span><i class="sw" style="border:1.5px solid #fab219;border-radius:50%"></i>banked 发放</span>
    </div>
    <details><summary>表格视图（最近 10 天）</summary>{DAILY_TABLE}</details>
  </section>

  <section class="card reveal">
    <h2>热词</h2>
    <p class="note">去掉链接、@ 与停用词后的词频 · 提升 = 7 天窗口相对前 28 天基线的对数提升</p>
    <div class="tools">
      <div class="seg" id="hotSeg" role="group" aria-label="热词模式">
        <button data-mode="top" aria-pressed="true">高频</button>
        <button data-mode="surge" aria-pressed="false">异动</button>
      </div>
      <span class="note" style="margin:3px 0 0 4px" id="hotHint"></span>
    </div>
    <div id="hotChart"></div>
    <details><summary>表格视图</summary>{SURGE_TABLE}</details>
  </section>

  <section class="card reveal">
    <h2>话题分布（最近 14 天）</h2>
    <p class="note">关键词规则归类 · 一条帖子可同时命中多个话题</p>
    {TOPICS_TABLE}
  </section>

  <section class="card reveal">
    <h2>重置话语的密度变化</h2>
    <p class="note">每 7 天窗口内出现该词的帖子数 · 看 “reset / banked / EOD” 这类词何时抬升</p>
    {LEXICON_TABLE}
  </section>

  <section class="card reveal">
    <h2>最近的重置相关发言</h2>
    <p class="note">重置日里带 reset 语义的帖子，按时间倒序 · 北京时间</p>
    {RESET_POSTS}
  </section>

  <section class="card reveal">
    <h2>互动最多的账号（30 天）</h2>
    <p class="note">他回复过或正文里 @ 过的人</p>
    {MENTIONS_TABLE}
  </section>
</div>

<section class="card reveal" style="margin-top:16px" aria-labelledby="st-h">
  <h2 id="st-h">监测状态</h2>
  <p class="note">定时任务每 {REFRESH_HOURS} 小时抓取一次镜像与 feed，重算预测并推送告警 · 北京时间</p>
  <div class="st-grid" id="statusGrid"></div>
</section>

<footer>
  数据来源：<a href="https://tiboreset.com/X-posts" target="_blank" rel="noopener">tiboreset.com</a>（推文镜像）与
  <a href="https://tiboreset.com/feed.xml" target="_blank" rel="noopener">其 Atom feed</a>（重置事件）。
  非 OpenAI 官方数据，概率为统计估计，不构成任何承诺。
  仓库：<a href="https://github.com/cafedaily/ohmytibo" target="_blank" rel="noopener">cafedaily/ohmytibo</a>。
</footer>
</div>

<div class="tip" id="tip" role="status"></div>

<script id="payload" type="application/json">{PAYLOAD}</script>
<script>
(() => {
  const PAL = {s1:'#3987e5', s2:'#d95926', good:'#0ca30c', warn:'#fab219', grid:'#2c2c2a', axis:'#383835',
               muted:'#898781', ink:'#f0efec', ink2:'#c3c2b7', solid:'#1a1a19'};
  let DATA = JSON.parse(document.getElementById('payload').textContent);
  const $ = (s, r = document) => r.querySelector(s);
  const bj = (iso, opts) => new Intl.DateTimeFormat('zh-CN', Object.assign(
      {timeZone:'Asia/Shanghai', month:'2-digit', day:'2-digit', hour:'2-digit', minute:'2-digit', hour12:false}, opts)
    ).format(new Date(iso));
  const num = n => n.toLocaleString('zh-CN');
  const pct = x => Math.round(x * 100) + '%';

  /* ---------------------------------------------------------------- tooltip */
  const tip = $('#tip');
  const showTip = (e, text) => {
    tip.textContent = text;
    tip.style.opacity = '1';
    const pad = 14, w = tip.offsetWidth, h = tip.offsetHeight;
    let x = (e.clientX || 0) + pad, y = (e.clientY || 0) - h - pad;
    if (x + w > innerWidth - 8) x = innerWidth - w - 8;
    if (y < 8) y = (e.clientY || 0) + pad;
    tip.style.left = x + 'px';
    tip.style.top = y + 'px';
  };
  const hideTip = () => { tip.style.opacity = '0'; };
  document.addEventListener('pointermove', e => {
    const el = e.target.closest && e.target.closest('[data-tip]');
    if (el) showTip(e, el.dataset.tip); else hideTip();
  });
  document.addEventListener('pointerleave', hideTip);
  document.addEventListener('focusin', e => {
    const el = e.target.closest && e.target.closest('[data-tip]');
    if (!el) return;
    const r = el.getBoundingClientRect();
    showTip({clientX: r.left + r.width / 2, clientY: r.top}, el.dataset.tip);
  });
  document.addEventListener('focusout', hideTip);

  /* ---------------------------------------------------------------- charts */
  const SVG_NS = 'http://www.w3.org/2000/svg';
  function mount(host, viewBox, label, inner) {
    host.innerHTML = '<svg class="chart" viewBox="' + viewBox + '" role="img" aria-label="' + label + '">' + inner + '</svg>';
    return host.firstChild;
  }
  const f1 = n => Math.round(n * 10) / 10;

  function renderForecast(fc) {
    const rows = fc.weekly || [];
    const host = $('#forecastChart');
    if (!rows.length) { host.textContent = '暂无数据'; return; }
    const W = 760, H = 260, ml = 46, mr = 16, mt = 26, mb = 48;
    const pw = W - ml - mr, ph = H - mt - mb, n = rows.length;
    const band = pw / n, bw = Math.min(24, band - 8);
    const peak = rows.reduce((b, r, i) => r.p > rows[b].p ? i : b, 0);
    let s = '';
    [0, .25, .5, .75, 1].forEach(t => {
      const y = mt + ph * (1 - t);
      s += '<line x1="' + ml + '" y1="' + f1(y) + '" x2="' + (W - mr) + '" y2="' + f1(y) +
           '" stroke="' + PAL.grid + '" stroke-width="1"/>' +
           '<text x="' + (ml - 9) + '" y="' + f1(y + 4) + '" text-anchor="end" class="ax">' + (t * 100) + '%</text>';
    });
    rows.forEach((r, i) => {
      const x = ml + band * i + (band - bw) / 2;
      const h = Math.max(2, ph * r.p), y = mt + ph - h;
      s += '<g class="col" tabindex="0" style="--i:' + i + '" data-tip="' + r.date + ' · 累计 ' + pct(r.p) + '">' +
           '<rect x="' + f1(x) + '" y="' + mt + '" width="' + f1(bw) + '" height="' + ph + '" fill="transparent"/>' +
           '<rect class="bar" x="' + f1(x) + '" y="' + f1(y) + '" width="' + f1(bw) + '" height="' + f1(h) +
           '" rx="4" fill="' + (i === peak ? PAL.s1 : PAL.s1) + '"/>' +
           '<text x="' + f1(x + bw / 2) + '" y="' + (mt + ph + 20) + '" text-anchor="middle" class="ax">' + r.date.slice(5) + '</text>' +
           '</g>';
    });
    const px = ml + band * peak + band / 2, py = mt + ph * (1 - rows[peak].p);
    s += '<text x="' + f1(px) + '" y="' + f1(py - 11) + '" text-anchor="middle" class="val">' + pct(rows[peak].p) + '</text>' +
         '<line x1="' + ml + '" y1="' + (mt + ph) + '" x2="' + (W - mr) + '" y2="' + (mt + ph) +
         '" stroke="' + PAL.axis + '" stroke-width="1"/>';
    mount(host, '0 0 ' + W + ' ' + H, '未来 10 天每日累计重置概率', s);
  }

  let dailyRange = 60, hidden = new Set();

  function renderDaily(rows) {
    const host = $('#dailyChart');
    if (!rows.length) { host.textContent = '暂无数据'; return; }
    const W = 760, H = 280, ml = 42, mr = 16, mt = 22, mb = 54;
    const pw = W - ml - mr, ph = H - mt - mb, n = rows.length;
    const band = pw / n, bw = Math.max(2, Math.min(14, band - 2));
    const top = Math.max(...rows.map(r => r.posts), 1);
    const raw = top / 4, mag = Math.pow(10, Math.floor(Math.log10(raw || 1)));
    const step = Math.max(1, [1, 2, 2.5, 5, 10].map(m => m * mag).find(v => v >= raw) || 10 * mag);
    let s = '';
    for (let t = 0; t <= top; t += step) {
      const y = mt + ph * (1 - t / top);
      s += '<line x1="' + ml + '" y1="' + f1(y) + '" x2="' + (W - mr) + '" y2="' + f1(y) +
           '" stroke="' + PAL.grid + '" stroke-width="1"/>' +
           '<text x="' + (ml - 9) + '" y="' + f1(y + 4) + '" text-anchor="end" class="ax">' + t + '</text>';
    }
    rows.forEach((r, i) => {
      const x = ml + band * i + (band - bw) / 2;
      const orig = r.posts - r.replies, reps = r.replies;
      const ho = orig ? ph * orig / top : 0, hr = reps ? ph * reps / top : 0;
      const yr = mt + ph - hr, yo = yr - ho - (orig && reps ? 2 : 0);
      const tipText = r.date + ' · 原创 ' + orig + ' · 回复 ' + reps + (r.reset ? ' · 重置日' : '') +
                      (r.banked ? ' · banked 发放' : '');
      s += '<g class="col" tabindex="0" style="--i:' + Math.min(i, 40) + '" data-tip="' + tipText + '">' +
           '<rect x="' + f1(x - 1) + '" y="' + mt + '" width="' + f1(bw + 2) + '" height="' + ph + '" fill="transparent"/>';
      if (reps && !hidden.has('reps'))
        s += '<rect class="bar" x="' + f1(x) + '" y="' + f1(yr) + '" width="' + f1(bw) + '" height="' + f1(Math.max(1, hr)) +
             '" rx="' + (hr > 4 ? 2 : 0) + '" fill="' + PAL.s2 + '"/>';
      if (orig && !hidden.has('orig'))
        s += '<rect class="bar" x="' + f1(x) + '" y="' + f1(yo) + '" width="' + f1(bw) + '" height="' + f1(Math.max(1, ho)) +
             '" rx="' + (ho > 4 ? 2 : 0) + '" fill="' + PAL.s1 + '"/>';
      if (r.reset)
        s += '<circle cx="' + f1(x + bw / 2) + '" cy="' + (mt + ph + 11) + '" r="4" fill="' + PAL.good +
             '" stroke="' + PAL.solid + '" stroke-width="2"/>';
      if (r.banked)
        s += '<circle cx="' + f1(x + bw / 2) + '" cy="' + (mt + ph + 11) + '" r="6.5" fill="none" stroke="' + PAL.warn +
             '" stroke-width="1.5"/>';
      s += '</g>';
    });
    const every = Math.max(1, Math.ceil(n / 8));
    for (let i = 0; i < n; i += every) {
      const x = ml + band * i + band / 2;
      s += '<text x="' + f1(x) + '" y="' + (mt + ph + 36) + '" text-anchor="middle" class="ax">' + rows[i].date.slice(5) + '</text>';
    }
    s += '<line x1="' + ml + '" y1="' + (mt + ph) + '" x2="' + (W - mr) + '" y2="' + (mt + ph) +
         '" stroke="' + PAL.axis + '" stroke-width="1"/>';
    mount(host, '0 0 ' + W + ' ' + H, '每日发帖量，按原创与回复拆分，重置日有标记', s);
  }

  function renderDailyRange() {
    const rows = DATA.daily.slice(-dailyRange);
    renderDaily(rows);
  }

  let hotMode = 'top';
  function renderHot() {
    const host = $('#hotChart');
    const rows = (DATA.hot[hotMode] || []).slice(0, 14);
    if (!rows.length) { host.textContent = '暂无数据'; return; }
    const W = 760, rowH = 27, ml = 118, mr = 70, H = rowH * rows.length + 14;
    const pw = W - ml - mr;
    const top = Math.max(...rows.map(r => r.count_7d), 1);
    let s = '';
    rows.forEach((r, i) => {
      const y = 8 + i * rowH, w = Math.max(2, pw * r.count_7d / top);
      const label = hotMode === 'surge' ? r.term + '  ' + (r.lift >= 0 ? '+' : '') + r.lift.toFixed(1) : r.term;
      s += '<g class="col" tabindex="0" style="--i:' + i + '" data-tip="' + r.term + ' · 7 天 ' + r.count_7d +
           ' 次 · 提升 ' + (r.lift >= 0 ? '+' : '') + r.lift.toFixed(1) + ' bit">' +
           '<rect x="0" y="' + (y - 2) + '" width="' + W + '" height="' + rowH + '" fill="transparent"/>' +
           '<text x="' + (ml - 12) + '" y="' + (y + 13) + '" text-anchor="end" class="lbl">' + label + '</text>' +
           '<rect class="hbar" x="' + ml + '" y="' + (y + 2) + '" width="' + f1(w) + '" height="14" rx="4" fill="' + PAL.s1 + '"/>' +
           '<text x="' + f1(ml + w + 9) + '" y="' + (y + 13) + '" class="val">' + r.count_7d + '</text>' +
           '</g>';
    });
    mount(host, '0 0 ' + W + ' ' + H, '热词频次', s);
    $('#hotHint').textContent = hotMode === 'top'
      ? '最近 7 天词频排名'
      : '相对前 28 天的异常抬升，越小众的抬升越靠前';
  }

  /* ---------------------------------------------------------------- signals + status */
  function el(tag, attrs, ...kids) {
    const n = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v == null || v === false) continue;
      if (k === 'class') n.className = v; else if (k === 'style') n.style.cssText = v; else n.setAttribute(k, v);
    }
    kids.flat().forEach(c => { if (c != null && c !== false) n.append(c.nodeType ? c : String(c)); });
    return n;
  }
  const LEVEL = {quiet: '安静', elevated: '活跃', high: '密集'};
  const ago = h => h < 1 ? Math.max(1, Math.round(h * 60)) + ' 分钟前' : h < 48 ? h.toFixed(h < 10 ? 1 : 0) + ' 小时前'
                                                                       : Math.round(h / 24) + ' 天前';
  const sinceH = iso => (Date.now() - new Date(iso).getTime()) / 3.6e6;

  function sigItem(it, i) {
    const tags = el('div', {class: 'sig-tags'},
      el('span', {class: 'badge k-' + it.kind}, it.label),
      it.forward ? el('span', {class: 'badge fwd'}, '前瞻') : null,
      it.after_last_reset ? el('span', {class: 'badge after'}, '上次重置后') : null);
    const link = /^https?:\/\//.test(it.url || '')
      ? el('a', {href: it.url, target: '_blank', rel: 'noopener', 'aria-label': '打开原帖'}, '↗') : null;
    return el('li', {class: it.after_last_reset ? '' : 'before', style: '--i:' + Math.min(i, 12)},
      el('time', {datetime: it.ts, title: ago(sinceH(it.ts))}, it.ts_local.slice(5)),
      el('div', {}, tags, el('div', {class: 'txt'}, it.text, link)));
  }

  function renderSignals(sg) {
    const head = $('#sigHead'), list = $('#sigList'), older = $('#sigOlder');
    head.replaceChildren(); list.replaceChildren(); older.replaceChildren();
    if (!sg) { list.append(el('li', {}, '暂无数据')); return; }
    const n = (v, label) => el('span', {class: 'sig-n'}, el('b', {}, v), label);
    head.append(
      el('span', {class: 'level ' + sg.level, title: '近 24 小时信号数相对前 28 天日均 ' + sg.baseline_per_day + ' 条'},
         el('i'), '近 24 小时 · ' + (LEVEL[sg.level] || sg.level)),
      n(sg.count_24h, '24 小时'), n(sg.count_72h, '72 小时'), n(sg.count_7d, '7 天'),
      n(sg.since_last_reset, '上次重置后'));
    const items = sg.items || [];
    const week = items.filter(it => sinceH(it.ts) <= 24 * 7);
    const shown = (week.length ? week : items).slice(0, 12);
    if (!shown.length) list.append(el('li', {}, el('time'), el('div', {class: 'txt'}, '最近没有提到重置的发言')));
    shown.forEach((it, i) => list.append(sigItem(it, i)));
    const rest = items.slice(shown.length);
    $('#sigMore').hidden = !rest.length;
    rest.forEach((it, i) => older.append(sigItem(it, i)));
  }

  function stCard(level, key, value, ...detail) {
    return el('div', {class: 'st ' + (level || '')},
      el('p', {class: 'k'}, el('i'), key), el('div', {class: 'v'}, value),
      ...detail.filter(Boolean).map(d => el('div', {class: 'd'}, d)));
  }

  function freshness() {
    const age = sinceH(DATA.generated_at) * 60, cad = (DATA.status && DATA.status.refresh_minutes) || 180;
    return {age, level: age <= cad * 1.5 ? '' : age <= cad * 3 ? 'warn' : 'bad'};
  }

  function paintFreshness() {
    const f = freshness();
    $('#freshDot').className = 'pulse ' + f.level;
    $('#freshLabel').textContent = f.level === 'bad' ? '数据可能已过期 · 更新于' : '数据更新于';
    $('#freshChip').title = '页面数据生成于 ' + ago(f.age / 60);
  }

  function renderStatus(st) {
    const grid = $('#statusGrid');
    grid.replaceChildren();
    st = st || {};
    const h = st.health || {}, al = st.alerts || {}, runs = st.runs || [];
    const f = freshness();
    grid.append(stCard(f.level, '页面数据', ago(f.age / 60), '生成于 ' + (DATA.generated_local || '—')));
    const feed = h.feed;
    if (feed) {
      const lvl = feed.ok ? '' : feed.consecutive_failures >= 3 ? 'bad' : 'warn';
      grid.append(stCard(lvl, '重置 feed', feed.ok ? '正常' : '抓取失败 ×' + feed.consecutive_failures,
        'feed ' + feed.entries + ' 条 · 本次新增 ' + feed.new + ' · 累计 ' + (feed.total ?? '—') + ' 条',
        feed.last_ok ? '上次成功 ' + bj(feed.last_ok) : '尚无成功记录',
        feed.ok ? null : feed.error));
    }
    const cp = h.corpus;
    if (cp) {
      const lvl = cp.ok ? '' : cp.consecutive_failures >= 3 ? 'bad' : 'warn';
      grid.append(stCard(lvl || (cp.failed ? 'warn' : ''), '推文镜像',
        cp.ok ? (cp.failed ? '正常（' + cp.failed + ' 天失败）' : '正常') : cp.failed + ' 天抓取失败',
        '本次抓取 ' + cp.fetched + ' 天 · 缓存 ' + cp.cached + ' · 空页 ' + cp.empty,
        cp.failed_days && cp.failed_days.length ? '失败：' + cp.failed_days.join('、') : null,
        cp.last_ok ? '上次成功 ' + bj(cp.last_ok) : null));
    }
    if (al.checked_at) {
      grid.append(al.configured
        ? stCard(al.undelivered_7d ? 'warn' : '', '告警推送', al.channels.join(' · '),
            al.last_sent ? '上次送达：' + al.last_sent.title + ' · ' + bj(al.last_sent.created_at) : '尚未触发告警',
            al.pending ? al.pending + ' 条待重试' : null,
            al.undelivered_7d ? '近 7 天 ' + al.undelivered_7d + ' 条未送达' : null)
        : stCard('warn', '告警推送', '告警通道未配置',
            '检测结果只写入日志，不会推送，也不会记为已发送。',
            al.pending ? al.pending + ' 条告警等待通道（12 小时内配置会补发）' : null,
            '在仓库 Secrets 中设置 TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID、DISCORD_WEBHOOK_URL、BARK_URL 或 ALERT_WEBHOOK_URL 之一。'));
    }
    if (runs.length) {
      const last = runs[runs.length - 1];
      const bad = runs.filter(r => !r.ok).length;
      const bars = el('div', {class: 'runs', 'aria-hidden': 'true'},
        runs.map(r => el('span', {class: !r.ok ? 'bad' : (r.warnings || []).length ? 'warn' : '',
                                  style: 'height:' + Math.max(25, Math.min(100, (r.seconds || 0) / 1.8)) + '%',
                                  title: bj(r.at) + ' · ' + (r.ok ? '成功' : '失败') + ' · ' + r.seconds + ' 秒'})));
      grid.append(stCard(bad ? (last.ok ? 'warn' : 'bad') : '', '最近运行',
        (last.ok ? '成功' : '失败：' + last.failed.join(', ')) + ' · ' + last.seconds + ' 秒',
        '近 ' + runs.length + ' 次中失败 ' + bad + ' 次 · 最近一次 ' + bj(last.at), bars));
    }
  }

  function paintPromise(fc) {
    const p = fc.pending_promise, box = $('#promise');
    box.hidden = !p;
    if (!p) return;
    box.replaceChildren('未兑现的重置承诺（' + bj(p.ts) + '）：', p.text + ' ',
      el('a', {href: 'https://x.com/thsottiaux/status/' + p.id, target: '_blank', rel: 'noopener'}, '原帖 ↗'));
  }

  /* ---------------------------------------------------------------- numbers */
  function countUp(el, target, fmt, ms = 900) {
    const start = performance.now();
    const from = 0;
    const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (reduce) { el.textContent = fmt(target); return; }
    (function tick(now) {
      const t = Math.min(1, (now - start) / ms);
      const e = 1 - Math.pow(1 - t, 3);
      el.textContent = fmt(from + (target - from) * e);
      if (t < 1) requestAnimationFrame(tick);
    })(start);
  }

  function setRing(p) {
    const c = 2 * Math.PI * 78;
    const ring = $('#ring');
    ring.setAttribute('stroke-dasharray', c.toFixed(1));
    ring.setAttribute('stroke-dashoffset', c.toFixed(1));
    requestAnimationFrame(() => {
      ring.setAttribute('stroke-dashoffset', (c * (1 - p)).toFixed(1));
    });
  }

  /* ---------------------------------------------------------------- paint */
  function paint(animate) {
    const fc = DATA.forecast, bt = fc.backtest || {}, last = fc.last_reset_local || '', modal = fc.modal_reset_local || '';
    const p24 = fc.p_24h || 0;
    if (animate) countUp($('#heroNum'), p24, v => Math.round(v * 100) + '%');
    else $('#heroNum').textContent = pct(p24);
    setRing(p24);
    $('#p48').textContent = pct(fc.p_48h || 0);
    $('#p72').textContent = pct(fc.p_72h || 0);
    $('#p7d').textContent = pct(fc.p_7d || 0);
    $('#gap').textContent = (fc.recent_mean_gap_days || 0).toFixed(1) + ' 天';
    $('#lastReset').textContent = last.slice(11, 16) + ' BJT';
    $('#lastResetSub').innerHTML = last.slice(0, 10) + ' · ' + (fc.hours_since_last_reset || 0).toFixed(1) + ' 小时前';
    $('#modalAt').textContent = modal.slice(11, 16) + ' BJT';
    $('#modalSub').textContent = modal.slice(0, 10) + ' · 按日模型取概率峰值';
    $('#recentGap').textContent = (fc.recent_mean_gap_days || 0).toFixed(1) + ' 天';
    $('#gapSub').textContent = '全样本均值 ' + (fc.mean_gap_days || 0).toFixed(2) + ' 天 · 中位 ' + (fc.median_gap_days || 0).toFixed(2) + ' 天';
    $('#resetCount').textContent = fc.reset_count || 0;
    $('#btDays').textContent = bt.days || '—';
    $('#btLL').textContent = (bt.logloss ?? 0).toFixed(3);
    $('#btBase').textContent = (bt.logloss_baseline ?? 0).toFixed(3);
    $('#btSkill').textContent = (bt.skill >= 0 ? '+' : '') + (bt.skill ?? 0).toFixed(2);
    $('#peakAt').textContent = modal ? bj(fc.modal_reset_at, {year:'numeric'}) : '—';
    $('#updated').textContent = DATA.generated_local || '';
    renderForecast(fc);
    renderDailyRange();
    renderHot();
    renderSignals(DATA.signals);
    renderStatus(DATA.status);
    paintPromise(fc);
    paintFreshness();
    startCountdown();
  }

  /* ---------------------------------------------------------------- countdown */
  let cdTimer = null;
  function startCountdown() {
    clearInterval(cdTimer);
    const target = new Date(DATA.forecast.modal_reset_at).getTime();
    const el = $('#countdown');
    const tick = () => {
      let d = target - Date.now();
      if (d < 0) { el.textContent = '窗口已过'; return; }
      const h = Math.floor(d / 3.6e6), m = Math.floor(d % 3.6e6 / 6e4), s = Math.floor(d % 6e4 / 1000);
      el.textContent = String(h).padStart(2, '0') + ':' + String(m).padStart(2, '0') + ':' + String(s).padStart(2, '0');
    };
    tick();
    cdTimer = setInterval(tick, 1000);
  }

  function clockTick() {
    const d = new Date();
    $('#clock').textContent = new Intl.DateTimeFormat('zh-CN', {
      timeZone: 'Asia/Shanghai', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false
    }).format(d) + ' 北京时间';
  }

  /* ---------------------------------------------------------------- controls */
  $('#rangeSeg').addEventListener('click', e => {
    const b = e.target.closest('button[data-range]');
    if (!b) return;
    dailyRange = +b.dataset.range;
    [...$('#rangeSeg').children].forEach(x => x.setAttribute('aria-pressed', String(x === b)));
    renderDailyRange();
  });
  $('#hotSeg').addEventListener('click', e => {
    const b = e.target.closest('button[data-mode]');
    if (!b) return;
    hotMode = b.dataset.mode;
    [...$('#hotSeg').children].forEach(x => x.setAttribute('aria-pressed', String(x === b)));
    renderHot();
  });
  $('#dailyLegend').addEventListener('click', e => {
    const s = e.target.closest('[data-series]');
    if (!s) return;
    const k = s.dataset.series;
    if (hidden.has(k)) hidden.delete(k); else hidden.add(k);
    s.style.opacity = hidden.has(k) ? '.35' : '1';
    renderDailyRange();
  });

  /* ---------------------------------------------------------------- reveal */
  const io = new IntersectionObserver(entries => {
    entries.forEach(en => {
      if (en.isIntersecting) { en.target.classList.add('in'); io.unobserve(en.target); }
    });
  }, {rootMargin: '0px 0px -8% 0px'});
  document.querySelectorAll('.reveal').forEach((el, i) => {
    el.style.transitionDelay = Math.min(i * 45, 240) + 'ms';
    io.observe(el);
  });

  /* ---------------------------------------------------------------- refresh */
  let lastRefresh = 0;
  async function refresh(force) {
    if (!force && Date.now() - lastRefresh < 60e3) return;
    lastRefresh = Date.now();
    try {
      const r = await fetch('data.json?ts=' + Date.now(), {cache: 'no-store'});
      if (!r.ok) return;
      const next = await r.json();
      const changed = next.generated_at !== DATA.generated_at;
      DATA = next;
      if (changed && !document.hidden) paint(false);
    } catch (_) { /* offline or first paint - keep the baked-in payload */ }
  }

  /* ---------------------------------------------------------------- boot */
  paint(true);
  clockTick();
  setInterval(clockTick, 1000);
  setInterval(paintFreshness, 60 * 1000);
  setInterval(() => refresh(), 10 * 60 * 1000);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) refresh(); });
})();
</script>

<script type="module">
const canvas = document.getElementById('bg');
let THREE;
try {
  THREE = await import('https://unpkg.com/three@0.160.0/build/three.module.js');
} catch (e) {
  canvas.remove();  // no network for the CDN: the CSS scrim alone still reads fine
  throw e;
}
const reduce = matchMedia('(prefers-reduced-motion: reduce)');
let renderer, scene, camera, points, group, raf = 0, clock;

function init() {
  try {
    renderer = new THREE.WebGLRenderer({canvas, antialias: true, alpha: true, powerPreference: 'low-power'});
  } catch (e) { canvas.remove(); return; }
  renderer.setPixelRatio(Math.min(devicePixelRatio || 1, 1.75));
  scene = new THREE.Scene();
  camera = new THREE.PerspectiveCamera(58, innerWidth / innerHeight, 0.1, 100);
  camera.position.set(0, 0, 15);

  const COUNT = 2200;
  const pos = new Float32Array(COUNT * 3);
  const col = new Float32Array(COUNT * 3);
  const seed = new Float32Array(COUNT);
  const blue = new THREE.Color('#3987e5');
  const orange = new THREE.Color('#d95926');
  for (let i = 0; i < COUNT; i++) {
    const r = 4.6 + Math.pow(Math.random(), 0.6) * 7.4;
    const th = Math.random() * Math.PI * 2;
    const ph = Math.acos(2 * Math.random() - 1);
    pos[i * 3] = r * Math.sin(ph) * Math.cos(th);
    pos[i * 3 + 1] = r * Math.cos(ph) * 0.55;
    pos[i * 3 + 2] = r * Math.sin(ph) * Math.sin(th);
    const t = Math.min(1, Math.max(0, (r - 4.6) / 7.4));
    const c = blue.clone().lerp(orange, t * 0.75);
    col[i * 3] = c.r; col[i * 3 + 1] = c.g; col[i * 3 + 2] = c.b;
    seed[i] = Math.random() * Math.PI * 2;
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  geo.setAttribute('color', new THREE.BufferAttribute(col, 3));
  const mat = new THREE.PointsMaterial({
    size: 0.045, vertexColors: true, transparent: true, opacity: 0.85,
    depthWrite: false, blending: THREE.AdditiveBlending, sizeAttenuation: true
  });
  points = new THREE.Points(geo, mat);

  const wire = new THREE.Mesh(
    new THREE.IcosahedronGeometry(9.4, 1),
    new THREE.MeshBasicMaterial({color: 0x3987e5, wireframe: true, transparent: true, opacity: 0.055})
  );
  group = new THREE.Group();
  group.add(points, wire);
  group.rotation.x = 0.35;
  scene.add(group);

  clock = new THREE.Clock();
  canvas.style.transition = 'opacity 1.2s ease';
  canvas.style.opacity = '0';
  requestAnimationFrame(() => { canvas.style.opacity = ''; });
  resize();
  addEventListener('resize', resize);
  if (reduce.matches) { renderer.render(scene, camera); return; }
  animate();
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) { cancelAnimationFrame(raf); raf = 0; }
    else if (!raf) animate();
  });
}

function resize() {
  const w = innerWidth, h = innerHeight;
  renderer.setSize(w, h, false);
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
  if (reduce.matches) renderer.render(scene, camera);
}

function animate() {
  raf = requestAnimationFrame(animate);
  const t = clock.getElapsedTime();
  group.rotation.y = t * 0.035;
  group.rotation.x = 0.35 + Math.sin(t * 0.12) * 0.06;
  const attr = points.geometry.attributes.position;
  const seed = attr.count;
  for (let i = 0; i < seed; i++) {
    const x = attr.getX(i), z = attr.getZ(i);
    const wave = Math.sin(x * 0.32 + t * 0.7) * Math.cos(z * 0.28 - t * 0.5) * 0.22;
    attr.setY(i, attr.getY(i) * 0.995 + wave * 0.02);
  }
  attr.needsUpdate = true;
  points.material.size = 0.042 + Math.sin(t * 0.9) * 0.006;
  renderer.render(scene, camera);
}

init();
</script>
</body>
</html>
"""


def status_block():
    health = state.load_json(state.HEALTH, {})
    alerts = state.load_json(state.STATE / "alerts.json", {}).get("summary") or {}
    runs = [{k: r.get(k) for k in ("at", "seconds", "ok", "failed", "warnings")}
            for r in state.recent_runs(n=16)]
    return {"refresh_minutes": REFRESH_MINUTES, "health": health, "alerts": alerts, "runs": runs}


def build():
    fc = load("forecast.json")
    hw = load("hotwords.json")
    metrics = load("metrics.json")

    payload = {
        "generated_at": metrics["generated_at"],
        "generated_local": metrics["generated_at_local"],
        "forecast": {k: fc[k] for k in (
            "p_24h", "p_48h", "p_72h", "p_7d", "last_reset", "last_reset_local",
            "modal_reset_at", "modal_reset_local", "hours_since_last_reset",
            "reset_count", "mean_gap_days", "median_gap_days", "recent_mean_gap_days",
            "backtest", "weekly", "pending_promise")},
        "daily": metrics["daily"],
        "hot": {"top": hw["top"][:20], "surge": hw["surge"][:20]},
        "signals": fc.get("signals"),
        "status": status_block(),
    }

    page = TEMPLATE
    tokens = {
        "POSTS": f"{metrics['posts']:,}",
        "DAYS": str(metrics["days_covered"]),
        "GENERATED": metrics["generated_at_local"],
        "REFRESH_HOURS": f"{REFRESH_MINUTES / 60:g}",
        "FORECAST_ROWS": forecast_rows(fc),
        "DAILY_TABLE": daily_table(metrics),
        "SURGE_TABLE": surge_table(hw),
        "TOPICS_TABLE": topics_table(hw),
        "LEXICON_TABLE": lexicon_table(hw),
        "RESET_POSTS": reset_posts_list(hw),
        "MENTIONS_TABLE": mentions_table(hw),
        "PAYLOAD": json.dumps(payload, ensure_ascii=False).replace("</", "<\\/"),
    }
    for key, val in tokens.items():
        page = page.replace("%%" + key + "%%", val)
    # template uses {TOKEN} braces for content slots, not f-strings
    for key, val in tokens.items():
        page = page.replace("{" + key + "}", val)

    SITE.mkdir(parents=True, exist_ok=True)
    (SITE / "index.html").write_text(page, encoding="utf-8")
    (SITE / "data.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote {SITE / 'index.html'} ({len(page):,} bytes) + data.json")


if __name__ == "__main__":
    build()
