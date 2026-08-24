#!/usr/bin/env python3
"""Generate kami-styled static site from courses.json and review data."""

from __future__ import annotations

import html
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _paths import (  # noqa: E402
    COURSES_JSON,
    MSC_CURRICULUM_URL,
    PARTNER_REVIEW_NAME,
    PARTNER_REVIEW_SITE,
    REVIEWS_DIR,
    SITE_DIST,
    SITE_REPO,
    catalogue_url,
    ensure_dirs,
    load_courses,
)
from review_extract import FIELD_LABELS, clean_excerpt  # noqa: E402

BASE_PATH = "/CityU-CS-Guide"
SITE_ORIGIN = "https://null1024-ws.github.io"

CONF_LABELS = {
    "confirmed": "多源一致",
    "reported": "单源提及",
    "disputed": "存疑",
    "unknown": "暂无",
}


def link(path: str) -> str:
    """Build site path; empty BASE_PATH for local preview."""
    if not path.startswith("/"):
        path = f"/{path}"
    return f"{BASE_PATH}{path}" if BASE_PATH else path

KAMI_CSS = """
@font-face{font-family:"TsangerJinKai02";src:url("https://cdn.jsdelivr.net/gh/AlfredoSequeworthy/TsangerJinKai02@main/TsangerJinKai02-W04.woff2") format("woff2");font-weight:400;font-style:normal;font-display:swap}
@font-face{font-family:"TsangerJinKai02";src:url("https://cdn.jsdelivr.net/gh/AlfredoSequeworthy/TsangerJinKai02@main/TsangerJinKai02-W05.woff2") format("woff2");font-weight:500;font-style:normal;font-display:swap}
:root{--parchment:#f5f4ed;--ivory:#faf9f5;--brand:#1B365D;--brand-light:#2D5A8A;--brand-tint:#EEF2F7;--near-black:#141413;--olive:#504e49;--stone:#6b6a64;--border:#e8e6dc;--border-soft:#e5e3d8;--serif:"TsangerJinKai02","Source Han Serif SC","Noto Serif CJK SC",Georgia,serif;--latin-ui:"PingFang SC",system-ui,sans-serif;--measure:760px}
*{box-sizing:border-box}html,body{margin:0;padding:0}
body{background:var(--parchment);color:var(--near-black);font-family:var(--serif);font-size:17px;line-height:1.62;letter-spacing:.35px;-webkit-font-smoothing:antialiased}
a{color:var(--brand);text-decoration:none}a:hover{color:var(--brand-light)}
a:focus-visible,.chip:focus-visible{outline:2px solid var(--brand);outline-offset:2px}
.eyebrow{font-family:var(--latin-ui);font-size:12px;text-transform:uppercase;letter-spacing:1px;color:var(--stone);margin:0 0 8px}
.site-top{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:12px;margin-bottom:14px}
.site-top .eyebrow{margin:0}
.site-nav{font-family:var(--latin-ui);font-size:13px;color:var(--stone);display:flex;gap:14px;align-items:center}
.site-nav a{color:var(--stone)}.site-nav a:hover,.site-nav a[aria-current="page"]{color:var(--brand)}
.site-nav a[aria-current="page"]{font-weight:500}
.github-star,.partner-link{display:inline-flex;align-items:center;gap:5px;padding:6px 12px;border:1px solid var(--border);background:var(--ivory);font-family:var(--latin-ui);font-size:12px;font-weight:500;border-radius:999px;white-space:nowrap;line-height:1}
.github-star{color:var(--brand)}.github-star:hover{border-color:var(--brand);background:var(--brand-tint);color:var(--brand)}
.partner-link{color:var(--olive)}.partner-link:hover{border-color:var(--brand-light);background:var(--brand-tint);color:var(--brand)}
.github-star svg{width:14px;height:14px;fill:currentColor;flex-shrink:0}
.partner-toast{background:var(--brand-tint);border-bottom:1px solid var(--border-soft)}
.partner-toast[hidden]{display:none!important}
.partner-toast-inner{max-width:1140px;margin:0 auto;padding:9px 40px;display:flex;align-items:center;gap:14px}
.partner-toast p{margin:0;flex:1;min-width:0;font-family:var(--latin-ui);font-size:13px;color:var(--olive);line-height:1.45;letter-spacing:0}
.partner-toast a{font-weight:500;color:var(--brand)}
.partner-toast-close{flex-shrink:0;display:inline-flex;align-items:center;justify-content:center;width:28px;height:28px;margin:0 -6px 0 0;border:none;border-radius:999px;background:transparent;color:var(--stone);font-size:18px;line-height:1;cursor:pointer;font-family:var(--latin-ui)}
.partner-toast-close:hover{color:var(--brand);background:rgba(27,54,93,.08)}
.back-link{font-family:var(--latin-ui);font-size:14px;margin:0 0 22px}
.back-link a{color:var(--stone)}.back-link a:hover{color:var(--brand)}
.ext-link{font-family:var(--latin-ui);font-size:12px;margin-left:6px;color:var(--stone)}
.ext-link:hover{color:var(--brand)}
.page{max-width:1140px;margin:0 auto;padding:72px 40px 104px}
.hero{padding-bottom:0;border-bottom:none;margin-bottom:28px}
.hero h1{font-size:46px;line-height:1.1;font-weight:500;margin:0 0 18px;letter-spacing:-.3px}
.hero p{font-size:19px;color:var(--olive);max-width:var(--measure);margin:0}
.course-hero{margin-bottom:28px;padding-bottom:24px;border-bottom:1px solid var(--border-soft)}
.course-hero h1{font-size:34px;line-height:1.15;font-weight:500;margin:0 0 10px}
.course-hero .sub{color:var(--olive);margin:0 0 10px;font-size:16px}
.course-hero .links{font-family:var(--latin-ui);font-size:14px;margin:0}
.course-hero .updated{font-family:var(--latin-ui);font-size:13px;color:var(--stone);margin:8px 0 0}
.source-summary{font-family:var(--latin-ui);font-size:14px;color:var(--olive);margin:0 0 20px;padding:12px 16px;background:var(--ivory);border:1px solid var(--border-soft)}
.disclaimer{background:var(--brand-tint);border-left:3px solid var(--brand);padding:16px 20px;margin:24px 0;font-size:15px;color:var(--olive);line-height:1.55}
.legend{display:flex;flex-wrap:wrap;gap:12px 18px;margin:0 0 20px;padding:14px 16px;background:var(--ivory);border:1px solid var(--border-soft);font-family:var(--latin-ui);font-size:12px;color:var(--stone)}
.legend-item{display:flex;align-items:center;gap:6px}
.filters{display:flex;flex-wrap:wrap;gap:10px;margin:0 0 16px}
.chip{font-family:var(--latin-ui);font-size:13px;padding:8px 16px;border-radius:999px;border:1px solid var(--border);background:var(--ivory);cursor:pointer;color:var(--olive);transition:background .15s,border-color .15s,color .15s}
.chip:hover{border-color:var(--brand-light);color:var(--brand)}
.chip.active{background:var(--brand);color:var(--ivory);border-color:var(--brand)}
.table-wrap{overflow-x:auto;-webkit-overflow-scrolling:touch;border:1px solid var(--border-soft);background:var(--ivory)}
table{width:100%;min-width:860px;border-collapse:collapse;font-size:15px}
thead th{position:sticky;top:0;background:var(--ivory);z-index:1;box-shadow:0 1px 0 var(--border-soft)}
th,td{padding:12px 14px;border-bottom:1px solid var(--border-soft);text-align:left;vertical-align:top}
th{font-family:var(--latin-ui);font-size:11px;text-transform:uppercase;letter-spacing:.7px;color:var(--stone);font-weight:500}
tbody tr:last-child td{border-bottom:none}
tr:hover td{background:rgba(250,249,245,.85)}
#course-table th:nth-child(3),#course-table td:nth-child(3){min-width:96px;width:9%;white-space:nowrap}
#course-table th:nth-child(n+5),#course-table td:nth-child(n+5){white-space:nowrap}
.badge{display:inline-block;font-family:var(--latin-ui);font-size:12px;padding:3px 10px;border-radius:999px;white-space:nowrap;line-height:1.4}
.badge-confirmed{background:var(--brand);color:var(--ivory)}
.badge-reported{border:1px solid var(--brand);color:var(--brand);background:transparent}
.badge-disputed{border:1px solid var(--stone);color:var(--stone);background:transparent}
.badge-unknown{color:var(--stone);opacity:.75;font-size:13px;padding:0}
.conf-line{font-family:var(--latin-ui);font-size:12px;color:var(--stone);margin-top:8px;line-height:1.45}
.conf-line .conf-tag{font-weight:500}
.conf-line .conf-tag-confirmed{color:var(--brand)}
.conf-line .conf-tag-reported{color:var(--brand-light)}
.conf-line .conf-tag-disputed{color:var(--stone)}
.layout{display:grid;grid-template-columns:220px minmax(0,1fr);gap:48px;align-items:start}
.sidebar{position:sticky;top:28px;max-height:calc(100svh - 56px);overflow:auto;padding-right:8px}
.sidebar nav a{display:block;padding:8px 0 8px 14px;border-left:2px solid transparent;color:var(--olive);font-size:14px;line-height:1.35}
.sidebar nav a:hover{color:var(--brand)}
.sidebar nav a[aria-current="page"]{border-left-color:var(--brand);color:var(--brand);font-weight:500}
.prose{max-width:var(--measure);font-size:17px}
.prose h1{font-size:34px;font-weight:500}
.prose h2{font-size:24px;font-weight:500;margin:40px 0 16px;padding-top:12px;border-top:1px solid var(--border-soft);scroll-margin-top:24px}
.prose h3{font-size:20px;font-weight:500;margin:24px 0 10px}
.prose p,.prose li{color:var(--near-black)}
.prose .muted{color:var(--stone)}
.prose code,.prose pre{font-family:Consolas,"Courier New",monospace}
.prose code{font-size:.9em;background:var(--ivory);padding:2px 6px;border:1px solid var(--border-soft)}
.prose pre{background:var(--ivory);padding:16px 18px;border:1px solid var(--border-soft);font-size:13px;line-height:1.55;overflow-x:auto;margin:16px 0}
.meta-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(168px,1fr));gap:12px;margin:20px 0}
.meta-card{background:var(--ivory);border:1px solid var(--border-soft);padding:16px 16px 14px;border-top:2px solid var(--border-soft)}
.meta-card-disputed{border-top-color:var(--stone)}
.meta-card:has(.badge-confirmed){border-top-color:var(--brand)}
.meta-card .label{font-family:var(--latin-ui);font-size:11px;text-transform:uppercase;letter-spacing:.7px;color:var(--stone)}
.meta-card .value{font-size:18px;font-weight:500;margin-top:8px}
.meta-card .note{font-size:12px;color:var(--stone);margin-top:8px;line-height:1.5;padding-top:8px;border-top:1px solid var(--border-soft)}
.source-list{list-style:none;padding:0;margin:0}
.source-list li{padding:20px 0;border-bottom:1px solid var(--border-soft)}
.source-list li:last-child{border-bottom:none;padding-bottom:0}
.source-head{display:flex;flex-wrap:wrap;align-items:baseline;gap:8px 14px;margin-bottom:10px;font-family:var(--latin-ui);font-size:13px;color:var(--stone)}
.source-head a{color:var(--brand)}
.source-head .post-title{font-family:var(--serif);font-size:17px;font-weight:500;color:var(--near-black);flex:1 1 100%;line-height:1.4;margin-bottom:2px}
.excerpt{color:var(--near-black);font-size:15px;line-height:1.68}
.excerpt p{margin:0 0 8px}.excerpt p:last-child{margin-bottom:0}
.tips{list-style:none;padding:0;margin:0}
.tips li{padding:12px 0;border-bottom:1px solid var(--border-soft);line-height:1.6}
.tips li:last-child{border-bottom:none}
.site-footer{margin-top:72px;padding-top:28px;border-top:1px solid var(--border-soft);font-size:14px;color:var(--stone)}
.site-footer .visit-count{margin:0 0 10px;font-size:13px;color:var(--stone)}
@media(max-width:880px){.page{padding:48px 22px 72px}.partner-toast-inner{padding:8px 22px;gap:10px}.partner-toast p{font-size:12px;line-height:1.4}.layout{grid-template-columns:1fr;gap:28px}.sidebar{position:static;max-height:none;padding:0 0 8px;border-bottom:1px solid var(--border-soft)}.sidebar nav{display:flex;flex-wrap:wrap;gap:4px 2px}.sidebar nav a{border-left:none;border-bottom:2px solid transparent;padding:8px 10px;font-size:13px}.sidebar nav a[aria-current="page"]{border-bottom-color:var(--brand)}.hero h1{font-size:34px}.hero p{font-size:17px}.course-hero h1{font-size:28px}body{font-size:16px}.prose{font-size:16px}table{font-size:14px;min-width:760px}th,td{padding:10px 10px}.excerpt{font-size:14px}.site-top{align-items:flex-start}}
@media(max-width:480px){.page{padding:36px 16px 60px}.partner-toast-inner{padding:8px 16px}.hero h1{font-size:28px}.hero p{font-size:16px}.meta-grid{grid-template-columns:1fr 1fr}.chip{font-size:12px;padding:7px 12px}table{font-size:13px;min-width:680px}.legend{gap:8px 12px}}
@media(prefers-reduced-motion:reduce){*{transition:none!important}}
"""


def esc(text: str | None) -> str:
    return html.escape(str(text or ""), quote=True)


def render_excerpt_html(text: str) -> str:
    cleaned = clean_excerpt(str(text or ""), max_len=2000)
    parts = [p.strip() for p in cleaned.split("；") if p.strip()]
    if len(parts) <= 1:
        return f'<div class="excerpt"><p>{html.escape(cleaned, quote=True)}</p></div>'
    paras = "".join(f"<p>{html.escape(p, quote=True)}</p>" for p in parts)
    return f'<div class="excerpt">{paras}</div>'


ROLE_LABELS = {"supplement": "补充", "correction": "更正"}


def badge(field: dict | None) -> str:
    if not field or field.get("confidence") == "unknown":
        return '<span class="badge badge-unknown">暂无</span>'
    conf = field.get("confidence", "reported")
    label = field.get("label") or field.get("value") or "—"
    cls = f"badge-{conf}"
    return f'<span class="badge {cls}">{esc(label)}</span>'


def format_field_note(field: dict, field_key: str) -> str:
    variants = field.get("variants")
    if variants:
        label_map = FIELD_LABELS.get(field_key, {})
        parts = [
            f"{label_map.get(value, value)}×{count}"
            for value, count in sorted(variants.items(), key=lambda item: (-item[1], item[0]))
        ]
        return "来源说法不一：" + "、".join(parts)
    note = field.get("note", "")
    if note.startswith("存疑:"):
        return "来源说法不一，详见下方帖子来源"
    return note


def meta_field(field: dict | None, field_key: str) -> str:
    if not field or field.get("confidence") == "unknown":
        return '<div class="value"><span class="badge badge-unknown">暂无数据</span></div>'

    conf = field.get("confidence", "reported")
    label = field.get("label") or field.get("value") or "—"
    conf_text = CONF_LABELS.get(conf, conf)
    src_n = field.get("distinctSources") or field.get("sourceCount") or 0
    src_html = f' · <span class="conf-src">{src_n} 篇来源</span>' if src_n else ""
    note = format_field_note(field, field_key)
    note_html = f'<div class="note">{esc(note)}</div>' if note else ""
    return (
        f'<div class="value"><span class="badge badge-{conf}">{esc(label)}</span></div>'
        f'<div class="conf-line">置信度：<span class="conf-tag conf-tag-{conf}">{esc(conf_text)}</span>{src_html}</div>'
        f"{note_html}"
    )


def load_review(code: str) -> dict | None:
    path = REVIEWS_DIR / f"{code}.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if "fields" in data:
        return data
    return None


def head(title: str, desc: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<meta name="generator" content="Kami · CityU-CS-Guide">
<link rel="canonical" href="{SITE_ORIGIN}{BASE_PATH}/">
<style>{KAMI_CSS}</style>
</head>"""


STAR_SVG = (
    '<svg viewBox="0 0 16 16" aria-hidden="true" focusable="false">'
    '<path d="M8 .25a.75.75 0 0 1 .673.418l1.882 3.815 4.21.612a.75.75 0 0 1 .416 1.279l-3.045 2.97.719 4.192a.751.751 0 0 1-1.088.791L8 12.347l-3.767 1.98a.75.75 0 0 1-1.088-.79l.72-4.194L.818 6.374a.75.75 0 0 1 .416-1.28l4.21-.611L7.327.668A.75.75 0 0 1 8 .25Z"/>'
    "</svg>"
)


def partner_link(*, compact: bool = False) -> str:
    label = "复习资料 ↗" if compact else f"{PARTNER_REVIEW_NAME} ↗"
    return (
        f'<a class="partner-link" href="{esc(PARTNER_REVIEW_SITE)}" target="_blank" rel="noopener" '
        f'title="友情站点：课程复习资料与 past paper">{esc(label)}</a>'
    )


PARTNER_TOAST_KEY = "cityu-cs-guide-partner-toast"


def partner_toast() -> str:
    return (
        f'<div id="partner-toast" class="partner-toast" hidden role="region" aria-label="友情站点提示">'
        f'<div class="partner-toast-inner">'
        f"<p>选课后需要复习资料？友情站点 "
        f'<a href="{esc(PARTNER_REVIEW_SITE)}" target="_blank" rel="noopener">{esc(PARTNER_REVIEW_NAME)}</a>'
        f" 有 past paper、复习笔记等 · 关闭后请点右上角「复习资料」</p>"
        f'<button type="button" class="partner-toast-close" aria-label="关闭提示">×</button>'
        f"</div></div>"
    )


def partner_toast_script() -> str:
    return f"""<script>
(function(){{
  var key={json.dumps(PARTNER_TOAST_KEY)};
  var el=document.getElementById('partner-toast');
  if(!el||localStorage.getItem(key))return;
  el.hidden=false;
  el.querySelector('.partner-toast-close').addEventListener('click',function(){{
    localStorage.setItem(key,'1');
    el.hidden=true;
  }});
}})();
</script>"""


def site_header(active: str = "") -> str:
    links = [
        ("index.html", "课程列表"),
        ("about.html", "关于"),
    ]
    nav = "".join(
        f'<a href="{link(href)}"{" aria-current=\"page\"" if name == active else ""}>{name}</a>'
        for href, name in links
    )
    star = (
        f'<a class="github-star" href="{esc(SITE_REPO)}" target="_blank" rel="noopener" '
        f'aria-label="在 GitHub 上 Star 本项目">{STAR_SVG}Star</a>'
    )
    return (
        f'<div class="site-top">'
        f'<div class="eyebrow">CityU MSc CS · 选课参考</div>'
        f'<nav class="site-nav">{nav}{partner_link(compact=True)}{star}</nav>'
        f"</div>"
    )

def site_back_link(href: str = "index.html") -> str:
    return f'<p class="back-link"><a href="{link(href)}">← 返回课程列表</a></p>'


BUSUANZI_SCRIPT = '<script src="https://cdn.busuanzi.cc/busuanzi/3.6.9/busuanzi.min.js" defer></script>'


def site_footer(*, today: str = "") -> str:
    if not today:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return (
        f'<footer class="site-footer">'
        f'<p class="visit-count">Total visits: <span id="busuanzi_site_pv">Loading…</span></p>'
        f"<p>CityU-CS-Guide · 非官方选课参考 · {today}</p>"
        f"</footer>"
        f"{BUSUANZI_SCRIPT}"
    )


def render_index(courses: list[dict]) -> str:
    rows = []
    for c in courses:
        review = load_review(c["code"]) or {"fields": {}}
        f = review.get("fields", {})
        stream = c.get("stream") or "—"
        cat = "必修" if c["category"] == "core" else f"选修 {c.get('group') or ''}"
        src_n = len(review.get("sources", [])) + len(review.get("commentSources", []))
        cat_url = catalogue_url(c["code"])
        rows.append(
            f'<tr data-category="{esc(c["category"])}" data-stream="{esc(c.get("stream") or "none")}" data-group="{esc(c.get("group") or "none")}">'
            f'<td><a href="{link(f"course/{c["code"]}.html")}"><strong>{esc(c["code"])}</strong></a>'
            f'<a class="ext-link" href="{esc(cat_url)}" target="_blank" rel="noopener" title="CityU 官方课程页">↗</a></td>'
            f'<td>{esc(c["title"])}</td>'
            f'<td>{esc(cat)}</td>'
            f'<td>{esc(stream)}</td>'
            f'<td>{badge(f.get("difficulty"))}</td>'
            f'<td>{badge(f.get("grading"))}</td>'
            f'<td>{badge(f.get("workload"))}</td>'
            f'<td>{badge(f.get("hasRecording"))}</td>'
            f'<td>{badge(f.get("attendance"))}</td>'
            f'<td>{src_n or "—"}</td>'
            f"</tr>"
        )

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return f"""{head("城大 MSc CS 选课参考", "香港城市大学计算机科学硕士课程评价与选课攻略，数据来自小红书")}
<body>
{partner_toast()}
<div class="page">
{site_header("课程列表")}
<section class="hero">
<h1>城大 MSc CS 选课参考</h1>
<p>汇总 CityU 计算机科学硕士课程的小红书评价与评论区补充，涵盖难度、给分、作业量、回放与考勤等信息。MSc CS 课纲见 <a href="{MSC_CURRICULUM_URL}" target="_blank" rel="noopener">CityU CS 官网</a>，各课官方说明见课程代码旁的 ↗ 链接。</p>
<div class="disclaimer">信息来自小红书帖子及评论区，未经城大官方核实。请结合最新学期信息自行判断。最后更新：{today}</div>
</section>
<div class="legend" aria-label="表格说明">
<span class="legend-item">列表仅显示评价结论；详情页含置信度与来源</span>
<span class="legend-item"><span class="badge badge-confirmed">实色</span> 多源一致</span>
<span class="legend-item"><span class="badge badge-reported">描边</span> 单源提及</span>
<span class="legend-item"><span class="badge badge-disputed">灰描边</span> 存疑</span>
</div>
<div class="filters">
<button class="chip active" data-filter="all">全部</button>
<button class="chip" data-filter="core">必修</button>
<button class="chip" data-filter="elective">选修</button>
<button class="chip" data-filter="AI">AI Stream</button>
<button class="chip" data-filter="DS">DS Stream</button>
<button class="chip" data-filter="IS">IS Stream</button>
</div>
<div class="table-wrap">
<table id="course-table">
<thead><tr>
<th>课程</th><th>名称</th><th>类型</th><th>Stream</th>
<th>难度</th><th>给分</th><th>作业量</th><th>回放</th><th>考勤</th><th>来源</th>
</tr></thead>
<tbody>
{"".join(rows)}
</tbody>
</table>
</div>
{site_footer(today=today)}
</div>
{partner_toast_script()}
<script>
document.querySelectorAll('.chip').forEach(btn=>{{
  btn.addEventListener('click',()=>{{
    document.querySelectorAll('.chip').forEach(b=>b.classList.remove('active'));
    btn.classList.add('active');
    const f=btn.dataset.filter;
    document.querySelectorAll('#course-table tbody tr').forEach(row=>{{
      if(f==='all'){{row.style.display='';return}}
      if(f==='core'){{row.style.display=row.dataset.category==='core'?'':'none';return}}
      if(f==='elective'){{row.style.display=row.dataset.category==='elective'?'':'none';return}}
      row.style.display=row.dataset.stream===f?'':'none';
    }});
  }});
}});
</script>
</body></html>"""


def render_course(course: dict, courses: list[dict]) -> str:
    code = course["code"]
    review = load_review(code) or {"fields": {}, "tips": [], "sources": [], "commentSources": []}
    f = review.get("fields", {})
    nav = "".join(
        f'<a href="{link(f"course/{c["code"]}.html")}"{" aria-current=\"page\"" if c["code"]==code else ""}>{c["code"]}</a>'
        for c in courses
    )

    meta_cards = ""
    for key, label in [
        ("difficulty", "难度"), ("grading", "给分"), ("workload", "作业量"),
        ("hasRecording", "回放"), ("attendance", "考勤"), ("examFormat", "考试"),
    ]:
        field = f.get(key, {})
        conf = (field or {}).get("confidence", "unknown")
        card_cls = "meta-card meta-card-disputed" if conf == "disputed" else "meta-card"
        meta_cards += f'<div class="{card_cls}"><div class="label">{label}</div>{meta_field(field, key)}</div>'

    tips_html = ""
    if review.get("tips"):
        tips_html = "<ul class='tips'>" + "".join(
            f"<li>{esc(clean_excerpt(str(t), max_len=500))}</li>" for t in review["tips"]
        ) + "</ul>"
    else:
        tips_html = '<p class="muted">暂无选课建议，欢迎在小红书搜索后贡献来源。</p>'

    def render_sources(sources: list, title: str) -> str:
        if not sources:
            return f"<h2>{title}</h2><p class='muted'>暂无数据</p>"
        items = []
        for s in sources[:8]:
            url = s.get("url") or "#"
            excerpt_html = render_excerpt_html(s.get("excerpt", ""))
            post_title = s.get("postTitle")
            title_html = f'<div class="post-title">{esc(clean_excerpt(str(post_title), max_len=200))}</div>' if post_title else ""
            role = f'<span>{esc(ROLE_LABELS.get(s["role"], s["role"]))}</span>' if s.get("role") else ""
            author = f'<span>{esc(s["author"])}</span>' if s.get("author") else ""
            items.append(
                f'<li>{title_html}<div class="source-head">'
                f'<a href="{esc(url)}" target="_blank" rel="noopener">查看原帖 ↗</a>'
                f'{role}{author}</div>'
                f'{excerpt_html}</li>'
            )
        return f"<h2>{title}</h2><ul class='source-list'>{''.join(items)}</ul>"

    cat = "必修 Core" if course["category"] == "core" else f"选修 Group {course.get('group', '')}"
    stream = course.get("stream") or "无"
    cat_url = catalogue_url(code)
    post_n = len(review.get("sources", []))
    comment_n = len(review.get("commentSources", []))
    source_summary = ""
    if post_n or comment_n:
        source_summary = (
            f'<p class="source-summary">共 {post_n} 篇帖子来源'
            f"{f'、{comment_n} 条评论区补充' if comment_n else ''}"
            f' · 更新 {esc(review.get("lastUpdated", ""))}</p>'
        )
    updated_line = ""
    if review.get("lastUpdated") and not source_summary:
        updated_line = f'<p class="updated">数据更新：{esc(review["lastUpdated"])}</p>'

    return f"""{head(f"{code} · {course['title']}", f"CityU {code} 课程评价与选课攻略")}
<body>
<div class="page">
{site_header()}
{site_back_link()}
<div class="layout">
<aside class="sidebar"><nav>{nav}</nav></aside>
<article class="prose">
<div class="course-hero">
<h1>{esc(code)}</h1>
<p class="sub">{esc(course["title"])} · {esc(cat)} · {esc(stream)} Stream · {course["credits"]} 学分</p>
<p class="links"><a href="{esc(cat_url)}" target="_blank" rel="noopener">CityU 官方课程页 ↗</a></p>
{updated_line}
</div>
<div class="disclaimer">以下信息来自小红书社区，未经官方核实，仅供形成性参考。Programme 课纲见 <a href="{MSC_CURRICULUM_URL}" target="_blank" rel="noopener">MSc CS 官网</a>；请阅读原文自行判断。</div>
{source_summary}
<h2>课程概况</h2>
<div class="meta-grid">{meta_cards}</div>
<h2>选课建议</h2>
{tips_html}
{render_sources(review.get("sources", []), "帖子来源")}
{render_sources(review.get("commentSources", []), "评论区补充")}
</article>
</div>
{site_footer()}
</div>
</body></html>"""


def render_about() -> str:
    return f"""{head("关于 · 城大 MSc CS 选课参考", "数据来源、可信度说明与免责声明")}
<body>
<div class="page">
{site_header("关于")}
{site_back_link()}
<article class="prose">
<h1>关于本站</h1>
<h2>数据来源</h2>
<p>课程基本信息来自 <a href="https://www.cs.cityu.edu.hk/en/academic-programmes/msc-computer-science/curriculum/structures">CityU CS 官网</a>。评价信息来自小红书帖子及评论区，通过 <a href="https://github.com/jackwener/xhs-cli" target="_blank" rel="noopener">xhs-cli</a> 采集，经 <code>review_extract</code> 与 <code>credibility_score</code> 整理。</p>
<h2>形成性参考说明</h2>
<p>本站标签描述的是<strong>来源之间的说法一致程度</strong>，不是对课程质量的最终评判。选课决策请结合官方课纲、个人背景与下方原文摘录。</p>
<h2>可信度说明</h2>
<ul>
<li><span class="badge badge-confirmed">多源一致</span> — 2 篇及以上独立帖子说法一致，或帖子与评论区相互印证</li>
<li><span class="badge badge-reported">单源提及</span> — 仅 1 篇来源提及，或同一帖子内重复提及</li>
<li><span class="badge badge-disputed">存疑</span> — 帖子与评论区或其他来源说法冲突</li>
</ul>
<h2>友情链接</h2>
<p>
<a href="{esc(PARTNER_REVIEW_SITE)}" target="_blank" rel="noopener">{esc(PARTNER_REVIEW_NAME)}</a>
（<a href="https://github.com/SHANECHEN0722/cityu-CS-review" target="_blank" rel="noopener">cityu-CS-review</a>）
收录课程复习资料、past paper 与选课心得。本站侧重小红书选课评价，对方侧重复习备考，两者互补。
</p>
<h2>免责声明</h2>
<p>本站为非官方选课参考，不保证信息完整或最新。选课请以 CityU 官方通知与课程大纲为准。</p>
</article>
{site_footer()}
</div>
</body></html>"""


def main() -> None:
    global BASE_PATH
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--local", action="store_true", help="Build for local preview (root paths, no /CityU-CS-Guide prefix)")
    args = parser.parse_args()
    if args.local:
        BASE_PATH = ""

    ensure_dirs()
    courses = load_courses()
    SITE_DIST.mkdir(parents=True, exist_ok=True)
    (SITE_DIST / ".nojekyll").write_text("", encoding="utf-8")
    course_dir = SITE_DIST / "course"
    course_dir.mkdir(exist_ok=True)

    (SITE_DIST / "index.html").write_text(render_index(courses), encoding="utf-8")
    (SITE_DIST / "about.html").write_text(render_about(), encoding="utf-8")
    for course in courses:
        (course_dir / f"{course['code']}.html").write_text(render_course(course, courses), encoding="utf-8")

    print(f"Built site to {SITE_DIST}: {len(courses)} course pages + index + about")


if __name__ == "__main__":
    main()
