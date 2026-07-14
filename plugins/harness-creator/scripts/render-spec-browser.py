#!/usr/bin/env python3
# /// script
# name: render-spec-browser
# purpose: plan dir の仕様書 (13 フェーズ仕様書 phase-01..13 + タスク別仕様書 task-specs/*.md) の本文を、
#   サイドバー index → 各仕様書へページ遷移 → ブラウザ back で戻れる自己完結 HTML ブラウザへ決定論 render する。
#   実行記録/計画構造レポート (project-task-status.py) が「構造・依存・価値」を見せるのに対し、本 script は
#   「各仕様書の中身」を読める形にする補完ビュー。外部 CDN/JS 依存なし (hash ナビはインライン JS + :target)。
# inputs:
#   - argv: --plan-dir <dir> [--out <html>] [--title <str>]
#           (--out 省略時 <plan-dir>/task-specs.html。phase-*.md と task-specs/*.md を自動収集)
# outputs:
#   - stdout: 生成先パス + 収集した仕様書件数の JSON
#   - exit: 0=OK / 2=usage/IO error
# contexts: [C, E]
# network: false
# write-scope: <plan-dir>/task-specs.html (既定・--out で上書き)
# requires-python: ">=3.10"
# dependencies: []
# ///
"""仕様書ブラウザ HTML 生成器 (自己完結・ページ遷移/戻る対応)。

「タスク仕様書で作成している 13 個の仕様書の中身を HTML で読めて、ページ遷移や戻るができる」
ことを、外部依存なしで実現する。plan dir から phase-01..13 の 13 フェーズ仕様書と task-specs/ の
タスク別仕様書を収集し、frontmatter をメタ表・本文を最小 Markdown レンダラで HTML 化し、サイドバー
index からハッシュ遷移 (#P01 等) で各仕様書へ移動する単一 HTML を書き出す。ブラウザの戻る/進むは
ハッシュ変化で自動的に効く。project-task-status.py (構造/依存/価値ビュー) の姉妹で、こちらは中身閲覧。
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path

_H = html.escape


# ── Markdown → HTML (最小・自己完結・外部依存なし) ─────────────────────────
def _inline(text: str) -> str:
    """インライン装飾 (エスケープ後に code/bold/em/link を復元)。"""
    out = _H(text)
    # `code`
    out = re.sub(r"`([^`]+)`", lambda m: f"<code>{m.group(1)}</code>", out)
    # [label](url)
    out = re.sub(
        r"\[([^\]]+)\]\(([^)\s]+)\)",
        lambda m: f'<a href="{m.group(2)}">{m.group(1)}</a>',
        out,
    )
    # **bold**
    out = re.sub(r"\*\*([^*]+)\*\*", lambda m: f"<strong>{m.group(1)}</strong>", out)
    # *em* / _em_ (単純ケース)
    out = re.sub(r"(?<![\w*])\*([^*\n]+)\*(?![\w*])", lambda m: f"<em>{m.group(1)}</em>", out)
    return out


def _md_to_html(body: str) -> str:
    """ブロックレベルの最小 Markdown レンダラ (heading/list/code/quote/hr/table/段落)。"""
    lines = body.split("\n")
    out: list[str] = []
    i, n = 0, len(lines)
    while i < n:
        line = lines[i]
        stripped = line.strip()
        # fenced code block
        if stripped.startswith("```"):
            code: list[str] = []
            i += 1
            while i < n and not lines[i].strip().startswith("```"):
                code.append(lines[i])
                i += 1
            i += 1  # closing fence
            out.append("<pre><code>" + _H("\n".join(code)) + "</code></pre>")
            continue
        # blank
        if not stripped:
            i += 1
            continue
        # horizontal rule
        if re.fullmatch(r"-{3,}|\*{3,}|_{3,}", stripped):
            out.append("<hr>")
            i += 1
            continue
        # heading (# 個数でレベル。ページ h1 があるので 1 段下げて h2 以降)
        hm = re.match(r"(#{1,6})\s+(.*)", stripped)
        if hm:
            level = min(len(hm.group(1)) + 1, 6)
            out.append(f"<h{level}>{_inline(hm.group(2))}</h{level}>")
            i += 1
            continue
        # table (| a | b | 行が連続し、2 行目が区切り)
        if stripped.startswith("|") and i + 1 < n and re.match(r"^\|[\s:|-]+\|?$", lines[i + 1].strip()):
            header = [c.strip() for c in stripped.strip("|").split("|")]
            i += 2
            rows = []
            while i < n and lines[i].strip().startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            thead = "".join(f"<th>{_inline(c)}</th>" for c in header)
            tbody = "".join(
                "<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in r) + "</tr>" for r in rows
            )
            out.append(f'<div class="tbl"><table><thead><tr>{thead}</tr></thead><tbody>{tbody}</tbody></table></div>')
            continue
        # blockquote
        if stripped.startswith(">"):
            quote = []
            while i < n and lines[i].strip().startswith(">"):
                quote.append(lines[i].strip()[1:].strip())
                i += 1
            out.append(f"<blockquote>{_inline(' '.join(quote))}</blockquote>")
            continue
        # unordered list
        if re.match(r"[-*+]\s+", stripped):
            items = []
            while i < n and re.match(r"[-*+]\s+", lines[i].strip()):
                items.append(_inline(re.sub(r"^[-*+]\s+", "", lines[i].strip())))
                i += 1
            out.append("<ul>" + "".join(f"<li>{it}</li>" for it in items) + "</ul>")
            continue
        # ordered list
        if re.match(r"\d+[.)]\s+", stripped):
            items = []
            while i < n and re.match(r"\d+[.)]\s+", lines[i].strip()):
                items.append(_inline(re.sub(r"^\d+[.)]\s+", "", lines[i].strip())))
                i += 1
            out.append("<ol>" + "".join(f"<li>{it}</li>" for it in items) + "</ol>")
            continue
        # paragraph (連続する非空行を束ねる)
        para = []
        while i < n and lines[i].strip() and not re.match(r"(#{1,6}\s|[-*+]\s|\d+[.)]\s|>|```)", lines[i].strip()):
            para.append(lines[i].strip())
            i += 1
        out.append(f"<p>{_inline(' '.join(para))}</p>")
    return "\n".join(out)


def _split_frontmatter(text: str) -> tuple[list[tuple[str, str]], str]:
    """先頭 YAML frontmatter を scalar key:value のリスト + 本文へ分離する (最小・非 YAML 依存)。"""
    if not text.startswith("---"):
        return [], text
    end = text.find("\n---", 3)
    if end == -1:
        return [], text
    fm_block = text[3:end].strip("\n")
    body = text[end + 4:].lstrip("\n")
    meta: list[tuple[str, str]] = []
    for line in fm_block.split("\n"):
        m = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if m and m.group(2) and not line.startswith(" "):
            meta.append((m.group(1), m.group(2).strip().strip('"')))
    return meta, body


# ── 仕様書収集 ────────────────────────────────────────────────────────────
def _collect_specs(plan_dir: Path) -> list[dict]:
    """plan dir から 13 フェーズ仕様書 + タスク別仕様書 (+ index) を順序付きで収集する。"""
    specs: list[dict] = []
    index_md = plan_dir / "index.md"
    if index_md.is_file():
        specs.append({"id": "index-doc", "group": "概要", "label": "index (目次)", "path": index_md})
    for phase in sorted(plan_dir.glob("phase-*.md")):
        stem = phase.stem  # phase-01-requirements
        specs.append({"id": stem, "group": "ライフサイクル 13 フェーズ仕様書",
                      "label": stem.replace("phase-", "P").replace("-", " ", 1), "path": phase})
    specs_dir = plan_dir / "task-specs"
    if specs_dir.is_dir():
        for spec in sorted(specs_dir.glob("*.md")):
            specs.append({"id": f"task-{spec.stem}", "group": "タスク別仕様書",
                          "label": spec.stem, "path": spec})
    return specs


def _render_page(spec: dict, prev_id: str | None, next_id: str | None) -> str:
    """1 仕様書を 1 ページ (section) として render する (メタ表 + 本文 + 前後ナビ)。"""
    text = spec["path"].read_text(encoding="utf-8")
    meta, body = _split_frontmatter(text)
    title = next((v for k, v in meta if k == "title"), spec["label"])
    meta_rows = "".join(
        f'<div class="meta-pair"><dt>{_H(k)}</dt><dd>{_H(v)}</dd></div>' for k, v in meta[:12]
    )
    meta_html = f'<dl class="spec-meta">{meta_rows}</dl>' if meta_rows else ""
    prev_link = f'<a class="pn" href="#{_H(prev_id)}">← 前の仕様書</a>' if prev_id else '<span></span>'
    next_link = f'<a class="pn" href="#{_H(next_id)}">次の仕様書 →</a>' if next_id else '<span></span>'
    return (
        f'<section class="spec-page" id="{_H(spec["id"])}" hidden>'
        '<div class="spec-top"><a class="back" href="#index">☰ 一覧へ戻る</a>'
        f'<span class="grp">{_H(spec["group"])}</span></div>'
        f'<h1>{_H(str(title))}</h1><p class="spec-src">出典: <code>{_H(str(spec["path"].name))}</code></p>'
        f'{meta_html}<div class="spec-body">{_md_to_html(body)}</div>'
        f'<div class="pn-row">{prev_link}{next_link}</div></section>'
    )


def _render_index(specs: list[dict], plan_name: str) -> str:
    """ランディング (index) ページ: グループ別に全仕様書へのリンクを並べる。"""
    groups: dict[str, list[dict]] = {}
    for s in specs:
        groups.setdefault(s["group"], []).append(s)
    blocks = []
    for grp, items in groups.items():
        links = "".join(
            f'<li><a href="#{_H(s["id"])}">{_H(s["label"])}</a></li>' for s in items
        )
        blocks.append(f'<div class="idx-group"><h2>{_H(grp)}</h2><ul>{links}</ul></div>')
    return (
        '<section class="spec-page spec-index" id="index" hidden>'
        f'<h1>{_H(plan_name)} · タスク仕様書ブラウザ</h1>'
        '<p class="lead">各仕様書のタイトルをクリックすると本文へ移動します。ブラウザの「戻る」で'
        'この一覧へ戻れます。左のサイドバーからも直接ジャンプできます。</p>'
        f'{"".join(blocks)}</section>'
    )


def _render_nav(specs: list[dict], related: list[tuple[str, str]]) -> str:
    groups: dict[str, list[dict]] = {}
    for s in specs:
        groups.setdefault(s["group"], []).append(s)
    parts = ['<a class="nav-home" href="#index">🏠 一覧トップ</a>']
    if related:
        links = "".join(f'<a class="nav-ext" href="{_H(href)}">{_H(label)}</a>' for href, label in related)
        parts.append(f'<div class="nav-group"><span class="nav-grp">関連レポート</span>{links}</div>')
    for grp, items in groups.items():
        links = "".join(
            f'<a href="#{_H(s["id"])}">{_H(s["label"])}</a>' for s in items
        )
        parts.append(f'<div class="nav-group"><span class="nav-grp">{_H(grp)}</span>{links}</div>')
    return "".join(parts)


_JS = """
(function(){
  function ids(){return Array.prototype.map.call(document.querySelectorAll('.spec-page'),function(s){return s.id;});}
  function show(){
    var h=(location.hash||'#index').slice(1); if(!document.getElementById(h)){h='index';}
    document.querySelectorAll('.spec-page').forEach(function(s){s.hidden=(s.id!==h);});
    document.querySelectorAll('.spec-nav a, .idx-group a').forEach(function(a){
      a.classList.toggle('active', a.getAttribute('href')==='#'+h);});
    window.scrollTo(0,0);
  }
  window.addEventListener('hashchange', show);
  document.addEventListener('DOMContentLoaded', show); show();
})();
"""


def render_html(specs: list[dict], plan_name: str, title: str,
                related: list[tuple[str, str]] | None = None) -> str:
    pages = [_render_index(specs, plan_name)]
    ids = [s["id"] for s in specs]
    for idx, spec in enumerate(specs):
        prev_id = ids[idx - 1] if idx > 0 else "index"
        next_id = ids[idx + 1] if idx + 1 < len(ids) else None
        pages.append(_render_page(spec, prev_id, next_id))
    nav = _render_nav(specs, related or [])
    body = "".join(pages)
    return f'''<!doctype html>
<html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light">
<title>{_H(title)}</title>
<style>
:root{{--ink:#242330;--muted:#666477;--paper:#f6f3ec;--panel:#fffdf7;--line:#ded8cb;--navy:#26334a;--blue:#376b8c;--green:#27745c;--shadow:0 10px 30px rgba(45,42,50,.08)}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--paper);color:var(--ink);font-family:Inter,"Noto Sans JP","Hiragino Sans",system-ui,sans-serif;font-size:16px;line-height:1.8}}
a{{color:var(--blue);text-decoration:none}} a:hover{{text-decoration:underline}} code{{font-family:"SFMono-Regular",Consolas,monospace;font-size:.88em;background:#efeadf;padding:.05em .35em;border-radius:5px;overflow-wrap:anywhere}}
.layout{{display:grid;grid-template-columns:260px minmax(0,1fr);gap:0;min-height:100vh}}
.spec-nav{{position:sticky;top:0;align-self:start;height:100vh;overflow-y:auto;background:var(--navy);color:#eef2f5;padding:20px 14px}}
.spec-nav a{{display:block;color:#d7dde3;padding:5px 10px;border-radius:8px;font-size:.9rem;overflow-wrap:anywhere}} .spec-nav a:hover{{background:rgba(255,255,255,.08);text-decoration:none}} .spec-nav a.active{{background:var(--blue);color:#fff}}
.nav-home{{font-weight:800;margin-bottom:10px}} .nav-ext{{color:#bfe3d3!important;font-weight:700}} .nav-group{{margin:14px 0}} .nav-grp{{display:block;font-size:.72rem;text-transform:uppercase;letter-spacing:.06em;color:#9fb0bd;padding:0 10px;margin-bottom:4px}}
main{{padding:34px clamp(18px,4vw,56px);width:min(920px,100%);margin:auto}}
.spec-page[hidden]{{display:none}} .spec-page:target{{display:block}}
.spec-top{{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px}} .back{{font-weight:700}} .grp{{font-size:.78rem;color:var(--muted);background:var(--panel);border:1px solid var(--line);border-radius:999px;padding:3px 12px}}
h1{{font-size:clamp(1.5rem,3.4vw,2.3rem);line-height:1.25;margin:.2em 0 .1em}} .spec-src{{color:var(--muted);font-size:.85rem;margin:.2em 0 1.2em}} .lead{{color:var(--muted);max-width:60ch}}
.spec-meta{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:8px 20px;background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:16px 20px;margin:0 0 24px}} .meta-pair{{display:flex;gap:8px;font-size:.85rem;border-bottom:1px dotted var(--line);padding-bottom:5px}} .meta-pair dt{{color:var(--muted);font-weight:700;min-width:110px;margin:0}} .meta-pair dd{{margin:0;overflow-wrap:anywhere}}
.spec-body h2{{font-size:1.4rem;margin:1.6em 0 .5em;padding-bottom:.25em;border-bottom:2px solid var(--line)}} .spec-body h3{{font-size:1.15rem;margin:1.3em 0 .4em;color:var(--navy)}} .spec-body h4{{margin:1.1em 0 .3em}}
.spec-body ul,.spec-body ol{{padding-left:1.4rem}} .spec-body li{{margin:.3em 0}} .spec-body pre{{background:#2a2735;color:#f3f1ea;padding:16px;border-radius:12px;overflow:auto;font-size:.82rem}} .spec-body pre code{{background:none;color:inherit;padding:0}}
.spec-body blockquote{{border-left:4px solid var(--green);margin:1em 0;padding:.4em 1em;background:#eef4f1;color:#33463f;border-radius:0 10px 10px 0}} .tbl{{overflow:auto;margin:1em 0}} .spec-body table{{width:100%;border-collapse:collapse;font-size:.9rem}} .spec-body th,.spec-body td{{border:1px solid var(--line);padding:8px 12px;text-align:left;vertical-align:top}} .spec-body th{{background:var(--panel)}} .spec-body hr{{border:none;border-top:1px solid var(--line);margin:1.6em 0}}
.pn-row{{display:flex;justify-content:space-between;margin-top:40px;padding-top:18px;border-top:1px solid var(--line)}} .pn{{font-weight:700}}
.idx-group{{margin:1.4em 0}} .idx-group h2{{font-size:1.1rem;border-bottom:2px solid var(--line);padding-bottom:.25em}} .idx-group ul{{list-style:none;padding:0;display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:6px}} .idx-group li a{{display:block;background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:10px 14px}}
@media(max-width:820px){{.layout{{grid-template-columns:1fr}}.spec-nav{{position:static;height:auto;max-height:220px}}}}
@media print{{.spec-nav{{display:none}}.spec-page[hidden]{{display:block!important}}.pn-row,.spec-top .back{{display:none}}body{{background:#fff}}}}
</style></head>
<body>
<div class="layout">
<nav class="spec-nav">{nav}</nav>
<main>{body}</main>
</div>
<script>{_JS}</script>
</body></html>'''


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="render-spec-browser.py",
                                     description="仕様書ブラウザ HTML (ページ遷移/戻る対応・自己完結) を生成する")
    parser.add_argument("--plan-dir", required=True, help="仕様書を含む plan dir (phase-*.md / task-specs/*.md)")
    parser.add_argument("--out", default=None, help="出力 HTML。省略時 <plan-dir>/task-specs.html")
    parser.add_argument("--title", default=None, help="ページタイトル")
    args = parser.parse_args(list(sys.argv[1:] if argv is None else argv))

    plan_dir = Path(args.plan_dir)
    if not plan_dir.is_dir():
        print(f"plan-dir が存在しません: {plan_dir}", file=sys.stderr)
        return 2
    specs = _collect_specs(plan_dir)
    if not specs:
        print(f"仕様書が見つかりません (phase-*.md / task-specs/*.md): {plan_dir}", file=sys.stderr)
        return 2
    plan_name = plan_dir.name
    title = args.title or f"{plan_name} · タスク仕様書ブラウザ"
    out = Path(args.out) if args.out else plan_dir / "task-specs.html"
    # 相互リンク: 同 plan dir に存在する構造/依存/価値レポートをサイドバーへ載せる (往復ナビ)。
    related = [
        (name, label) for name, label in (
            ("plan-structure-report.html", "📊 構造・依存レポート"),
            ("task-execution-report.html", "📊 実行記録レポート"),
        ) if (plan_dir / name).exists()
    ]
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(render_html(specs, plan_name, title, related), encoding="utf-8")
    except OSError as exc:
        print(f"write error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"spec_browser_html": str(out), "spec_count": len(specs)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
