#!/usr/bin/env python3
# /// script
# name: build-slide-skeletons
# purpose: ページ単位のスライドひな形 HTML 22 種を frame-contract.json から決定論生成する。id は面が deck の中で果たす役割 (layout-cover / layout-profile など) で付け、通し番号にしない。枠 (chrome 予約帯・stage 矩形・スロット宣言・編集可否コメント) を 1 か所で持ち、各ひな形は stage 内の配置だけを固有に持つ。--check で再生成結果と現物の一致を検証する。
# inputs:
#   - assets/slide-templates/frame-contract.json
#   - CLI: [--root <plugin-root>] [--check]
# outputs:
#   - assets/slide-templates/layout-*.html
#   - exit: 0=生成成功/一致 / 1=--check で不一致 / 2=契約が読めない
# contexts: [glue]
# write-scope: assets/slide-templates/layout-*.html
# network: false
# dependencies: []
# requires-python: ">=3.10"
# ///
"""ページひな形 22 種を生成する。

## なぜ「ページごと」なのか

面全体のひな形を 1 枚にすると、図解の面・全面画像の面・箇条書きだけの面が
同じ骨格を共有できず、結局その場で組む羽目になる。逆にひな形を細かく割り
過ぎると、どれを使うかの判断が毎回ぶれる。そこで **配置の型を 22 種に固定し、
107 種の slideType をそこへ写像する** (写像表は registry.json)。同じ slideType
は常に同じ骨格に載るので、生成のたびに粒度が揺れない。

## なぜ id が通し番号でないのか

`p01`〜`p15` のような通し番号は「deck が 15 ページまで」という誤読を生むうえ、
種類を足すと番号と用途の対応が崩れる。id は**その面が deck の中で果たす役割**
(`layout-cover` / `layout-profile` / `layout-qa` …) で付ける。ひな形 1 枚は
1 ページではなく型なので、同じ `layout-diagram-main` を 1 つの deck で何枚
使っても構わない。

## 型の選び方 (どれも「並べ方」でなく「役割」で選ぶ)

- slideType を持つ面: `registry.json` の `map` で引く (勘で選ばない)。
- slideType を持たない面 (目次・自己紹介・登壇者一覧・KPI・想定質問・連絡先):
  `role_pages` で役割名から引く。ここが無いと、こうした面は毎回その場で
  組まれ、結局ひな形の外に落ちる。

## 空白過多・位置ズレが構造的に起きない理由

1. 空白: `.srg-slide__main` が `flex: 1 1 auto` で残り高さを必ず占める。要素が
   少ない面でも stage が縮まないので、「下半分が真っ白」が起きない。逆に多い
   面は `data-autofit` でフォントが下がり、下限 `typography.min` で止まる
   (実装は slide-skeleton.js)。
2. chrome の位置: インデックス帯・ページ番号・前後ナビは、ひな形が予約する
   帯と実物の描画が同じ `frame-contract.json` を読む。予約と実物を別管理に
   していたのが従来のズレの原因だった。
3. 印刷: 面の内部は 1280x720 の絶対座標のまま、`zoom` だけが印刷用に変わる
   (slide-skeleton.css)。画面と PDF はスケール係数が違うだけの同一物になる。

## ひな形の使い方 (LLM 向けの規律)

各ファイル冒頭のコメントが「書き換えてよい箇所」を明示する。骨格 (section の
class / chrome / stage / スロットの構造) は書き換えない。`data-slot` を持つ
要素の**中身**と、`data-media-kind` に宣言された種別の差し込み物だけを置く。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_CONTRACT = "assets/slide-templates/frame-contract.json"
_OUT_DIR = "assets/slide-templates"


# --- ひな形定義 ---------------------------------------------------------------
# stage: stage 内に置く HTML (インデント 4 で埋め込まれる)。
# media: data-media-kinds に宣言する種別 (frame-contract.media.kinds の部分集合)。
# slots: data-slot 名の一覧 (README と検査器が読む契約)。
# use:   どういう内容のときにこの面を選ぶか (判断のぶれを減らす一文)。

_SKELETONS = [
    {
        "id": "layout-cover",
        "title": "表紙",
        "use": "deck の 1 枚目。主題と発表者・日付だけを置き、本文は置かない。",
        "media": ["codex-image", "none"],
        "extra_class": "srg-slide--cover",
        "chrome": "none",
        "stage": """<div class="srg-slide__main" style="flex-direction: column; justify-content: center; gap: var(--srg-gap-loose);">
  <p class="srg-cover__eyebrow" data-slot="eyebrow" data-autofit="note">{{eyebrow}}</p>
  <h1 class="srg-cover__title" data-slot="title" data-autofit="title"
      style="font-size: var(--srg-fs-title); font-weight: 700; line-height: 1.25; margin: 0;">{{title}}</h1>
  <p class="srg-cover__subtitle" data-slot="subtitle" data-autofit="body"
     style="font-size: var(--srg-fs-subheading); margin: 0;">{{subtitle}}</p>
</div>
<p class="srg-slide__note" data-slot="meta" data-autofit="note">{{organization}} ／ {{date}}</p>""",
        # 背景画像を敷かない表紙では、この figure ごと削ってよい (唯一の例外)。
        "media_outside_stage": """<figure class="srg-media" data-slot="media" data-media-slot="background" style="margin: 0;">
  <!-- 表紙の背景画像 (任意)。文字の可読性を落とすなら敷かない方がよい。 -->
  <picture class="ai-slide-canvas">
    <source srcset="{{image_webp}}" type="image/webp">
    <img src="{{image_png}}" alt="{{image_alt}}">
  </picture>
</figure>""",
    },
    {
        "id": "layout-agenda",
        "title": "目次",
        "use": "deck 全体の道筋を最初に見せる面。章題と、その章で何が分かるかを 1 行ずつ。",
        "media": ["none"],
        "extra_class": "srg-slide--agenda",
        "chrome": "index-only",
        "stage": """<header class="srg-slide__title" data-slot="title" data-autofit="title">{{title}}</header>
<div class="srg-slide__main">
  <!-- 章が 5 つを超えるなら束ねる。目次で読み手を消耗させない。 -->
  <ol class="srg-list srg-list--agenda" data-slot="agenda" data-autofit="body"
      style="margin: 0; padding-left: 1.4em; display: flex; flex-direction: column; justify-content: space-evenly; width: 100%; line-height: 1.5;">
    <li><span data-slot="agenda-1-title" style="font-weight: 600;">{{section_1_title}}</span>
      <span data-slot="agenda-1-gain" style="color: var(--srg-fg-muted);">— {{section_1_what_reader_gets}}</span></li>
    <li><span data-slot="agenda-2-title" style="font-weight: 600;">{{section_2_title}}</span>
      <span data-slot="agenda-2-gain" style="color: var(--srg-fg-muted);">— {{section_2_what_reader_gets}}</span></li>
    <li><span data-slot="agenda-3-title" style="font-weight: 600;">{{section_3_title}}</span>
      <span data-slot="agenda-3-gain" style="color: var(--srg-fg-muted);">— {{section_3_what_reader_gets}}</span></li>
  </ol>
</div>
<p class="srg-slide__note" data-slot="note" data-autofit="note">{{how_long_or_who_for}}</p>""",
    },
    {
        "id": "layout-section-divider",
        "title": "章扉",
        "use": "章の切り替え。章番号と章題、その章で何が分かるかの 1 行だけ。",
        "media": ["none"],
        "extra_class": "srg-slide--divider",
        "chrome": "index-only",
        "stage": """<div class="srg-slide__main" style="flex-direction: column; justify-content: center; gap: var(--srg-gap);">
  <p class="srg-divider__no" data-slot="section-no" data-autofit="note"
     style="font-size: var(--srg-fs-note); letter-spacing: .08em; margin: 0;">{{section_no}}</p>
  <h2 class="srg-divider__title" data-slot="title" data-autofit="title"
      style="font-size: var(--srg-fs-title); font-weight: 700; line-height: 1.3; margin: 0;">{{section_title}}</h2>
  <p class="srg-divider__lead" data-slot="lead" data-autofit="body"
     style="font-size: var(--srg-fs-body); line-height: 1.6; margin: 0; max-width: 72%;">{{what_reader_gets}}</p>
</div>""",
    },
    {
        "id": "layout-message",
        "title": "1 メッセージ",
        "use": "主張 1 つを面いっぱいで言い切る。根拠は次の面へ回す。",
        "media": ["none"],
        "extra_class": "srg-slide--message",
        "chrome": "full",
        "stage": """<header class="srg-slide__title" data-slot="title" data-autofit="title">{{title}}</header>
<div class="srg-slide__main" style="align-items: center; justify-content: center;">
  <p class="srg-message__body" data-slot="message" data-autofit="title"
     style="font-size: var(--srg-fs-title); font-weight: 700; line-height: 1.45; text-align: center; margin: 0;">{{message}}</p>
</div>
<p class="srg-slide__note" data-slot="note" data-autofit="note">{{source_or_caveat}}</p>""",
    },
    {
        "id": "layout-lead-list",
        "title": "リード + 箇条",
        "use": "結論 1 行のあとに根拠を 3〜5 点。点が 6 つを超えるなら面を割る。",
        "media": ["none"],
        "extra_class": "srg-slide--lead-list",
        "chrome": "full",
        "stage": """<header class="srg-slide__title" data-slot="title" data-autofit="title">{{title}}</header>
<p class="srg-slide__lead" data-slot="lead" data-autofit="body">{{conclusion_one_line}}</p>
<div class="srg-slide__main">
  <ul class="srg-list" data-slot="list" data-autofit="body"
      style="margin: 0; padding-left: 1.4em; display: flex; flex-direction: column; justify-content: space-evenly; width: 100%; line-height: 1.6;">
    <li>{{point_1}}</li>
    <li>{{point_2}}</li>
    <li>{{point_3}}</li>
  </ul>
</div>
<p class="srg-slide__note" data-slot="note" data-autofit="note">{{source_or_caveat}}</p>""",
    },
    {
        "id": "layout-compare-2",
        "title": "左右対比",
        "use": "2 案・現状と理想・Before/After。3 つ以上の比較は layout-grid-cards の格子へ。",
        "media": ["none"],
        "extra_class": "srg-slide--compare",
        "chrome": "full",
        "stage": """<header class="srg-slide__title" data-slot="title" data-autofit="title">{{title}}</header>
<div class="srg-slide__main">
  <div class="srg-split srg-split--half">
    <section class="srg-card" data-slot="left">
      <h3 data-autofit="subheading" style="font-size: var(--srg-fs-subheading); margin: 0;">{{left_head}}</h3>
      <div data-autofit="body" style="flex: 1 1 auto; min-height: 0; line-height: 1.6;">{{left_body}}</div>
    </section>
    <section class="srg-card" data-slot="right">
      <h3 data-autofit="subheading" style="font-size: var(--srg-fs-subheading); margin: 0;">{{right_head}}</h3>
      <div data-autofit="body" style="flex: 1 1 auto; min-height: 0; line-height: 1.6;">{{right_body}}</div>
    </section>
  </div>
</div>
<p class="srg-slide__note" data-slot="note" data-autofit="note">{{takeaway}}</p>""",
    },
    {
        "id": "layout-profile",
        "title": "人物紹介",
        "use": "自己紹介・登壇者紹介・ペルソナ。1 人を顔と経歴で見せる面。複数人なら layout-team。",
        "media": ["codex-image", "svg-diagram", "none"],
        "extra_class": "srg-slide--profile",
        "chrome": "full",
        "stage": """<header class="srg-slide__title" data-slot="title" data-autofit="title">{{title}}</header>
<div class="srg-slide__main">
  <div class="srg-split srg-split--media-text">
    <figure class="srg-media" data-slot="media" data-media-slot="primary"
            style="flex-direction: column; margin: 0;">
      <!-- 顔写真・アバター・ペルソナ図のいずれか 1 つ。無い場合は figure ごと削り、
           下の本文側を srg-split ではなく単独ブロックにする。 -->
      <picture class="ai-slide-canvas">
        <source srcset="{{portrait_webp}}" type="image/webp">
        <img src="{{portrait_png}}" alt="{{portrait_alt}}">
      </picture>
      <figcaption class="srg-media__caption" data-slot="caption" data-autofit="caption">{{name_reading}}</figcaption>
    </figure>
    <div style="min-width: 0; display: flex; flex-direction: column; justify-content: center; gap: var(--srg-gap-tight);">
      <p data-slot="name" data-autofit="title"
         style="font-size: var(--srg-fs-heading); font-weight: 700; line-height: 1.3; margin: 0;">{{name}}</p>
      <p data-slot="role" data-autofit="body"
         style="font-size: var(--srg-fs-subheading); color: var(--srg-fg-muted); margin: 0;">{{role_and_affiliation}}</p>
      <ul data-slot="facts" data-autofit="body"
          style="margin: 0; padding-left: 1.4em; line-height: 1.7;">
        <!-- 経歴の羅列でなく、聞き手がこの人を信頼できる根拠を 3 点まで。 -->
        <li>{{fact_1}}</li>
        <li>{{fact_2}}</li>
        <li>{{fact_3}}</li>
      </ul>
    </div>
  </div>
</div>
<p class="srg-slide__note" data-slot="note" data-autofit="note">{{contact_or_handle}}</p>""",
    },
    {
        "id": "layout-team",
        "title": "複数人紹介",
        "use": "チーム・登壇者一覧・関係者の並置。3〜6 人。1 人だけなら layout-profile。",
        "media": ["codex-image", "none"],
        "extra_class": "srg-slide--team",
        "chrome": "full",
        "stage": """<header class="srg-slide__title" data-slot="title" data-autofit="title">{{title}}</header>
<div class="srg-slide__main">
  <!-- 人数で列数を選ぶ: 3 人 = srg-grid--3x1 / 4 人 = srg-grid--2x2 / 6 人 = srg-grid--3x2。
       枠を埋めるために架空の人を足さない。 -->
  <div class="srg-grid srg-grid--3x1" data-slot="members">
    <section class="srg-card" style="align-items: center; text-align: center;">
      <figure class="srg-media" data-media-slot="cell" style="margin: 0; width: 100%; flex: 1 1 auto;">
        <picture class="ai-slide-canvas">
          <source srcset="{{member_1_webp}}" type="image/webp">
          <img src="{{member_1_png}}" alt="{{member_1_alt}}">
        </picture>
      </figure>
      <p data-autofit="subheading" style="font-size: var(--srg-fs-subheading); font-weight: 600; margin: 0;">{{member_1_name}}</p>
      <p data-autofit="note" style="font-size: var(--srg-fs-note); color: var(--srg-fg-muted); margin: 0;">{{member_1_role}}</p>
    </section>
    <section class="srg-card" style="align-items: center; text-align: center;">
      <figure class="srg-media" data-media-slot="cell" style="margin: 0; width: 100%; flex: 1 1 auto;">
        <picture class="ai-slide-canvas">
          <source srcset="{{member_2_webp}}" type="image/webp">
          <img src="{{member_2_png}}" alt="{{member_2_alt}}">
        </picture>
      </figure>
      <p data-autofit="subheading" style="font-size: var(--srg-fs-subheading); font-weight: 600; margin: 0;">{{member_2_name}}</p>
      <p data-autofit="note" style="font-size: var(--srg-fs-note); color: var(--srg-fg-muted); margin: 0;">{{member_2_role}}</p>
    </section>
    <section class="srg-card" style="align-items: center; text-align: center;">
      <figure class="srg-media" data-media-slot="cell" style="margin: 0; width: 100%; flex: 1 1 auto;">
        <picture class="ai-slide-canvas">
          <source srcset="{{member_3_webp}}" type="image/webp">
          <img src="{{member_3_png}}" alt="{{member_3_alt}}">
        </picture>
      </figure>
      <p data-autofit="subheading" style="font-size: var(--srg-fs-subheading); font-weight: 600; margin: 0;">{{member_3_name}}</p>
      <p data-autofit="note" style="font-size: var(--srg-fs-note); color: var(--srg-fg-muted); margin: 0;">{{member_3_role}}</p>
    </section>
  </div>
</div>
<p class="srg-slide__note" data-slot="note" data-autofit="note">{{note}}</p>""",
    },
    {
        "id": "layout-diagram-main",
        "title": "図解が主役",
        "use": "図解そのものが主張。文字での説明は題と 1 行の読み取りに絞る。",
        "media": ["svg-diagram", "d3-diagram", "chart", "block"],
        "extra_class": "srg-slide--diagram-main",
        "chrome": "full",
        "stage": """<header class="srg-slide__title" data-slot="title" data-autofit="title">{{title}}</header>
<div class="srg-slide__main">
  <figure class="srg-media" data-slot="media" data-media-slot="primary"
          style="flex: 1 1 auto; flex-direction: column; margin: 0;">
    <!-- ここに図解を 1 つだけ差し込む。viewBox 必須・width/height 属性は付けない
         (親の 100% に追随させ、面から食み出させないため)。 -->
    {{diagram}}
    <figcaption class="srg-media__caption" data-slot="caption" data-autofit="caption">{{what_to_read}}</figcaption>
  </figure>
</div>""",
    },
    {
        "id": "layout-diagram-side",
        "title": "本文 + 図解",
        "use": "文で説明し、図解が補助する面。図解が主役なら layout-diagram-main を使う。",
        "media": ["svg-diagram", "d3-diagram", "chart", "block"],
        "extra_class": "srg-slide--diagram-side",
        "chrome": "full",
        "stage": """<header class="srg-slide__title" data-slot="title" data-autofit="title">{{title}}</header>
<div class="srg-slide__main">
  <div class="srg-split srg-split--text-media">
    <div data-slot="body" data-autofit="body"
         style="min-width: 0; display: flex; flex-direction: column; justify-content: center; gap: var(--srg-gap-tight); line-height: 1.7;">
      {{body}}
    </div>
    <figure class="srg-media" data-slot="media" data-media-slot="primary"
            style="flex-direction: column; margin: 0;">
      {{diagram}}
      <figcaption class="srg-media__caption" data-slot="caption" data-autofit="caption">{{what_to_read}}</figcaption>
    </figure>
  </div>
</div>""",
    },
    {
        "id": "layout-chart-main",
        "title": "チャート + 読み取り",
        "use": "定量データの面。グラフだけ置かず、そこから何が言えるかを必ず添える。",
        "media": ["chart", "d3-diagram"],
        "extra_class": "srg-slide--chart-main",
        "chrome": "full",
        "stage": """<header class="srg-slide__title" data-slot="title" data-autofit="title">{{title}}</header>
<div class="srg-slide__main">
  <figure class="srg-media" data-slot="media" data-media-slot="primary"
          style="flex: 3 1 0; flex-direction: column; margin: 0;">
    {{chart}}
    <figcaption class="srg-media__caption" data-slot="caption" data-autofit="caption">{{axis_and_unit}}</figcaption>
  </figure>
  <aside class="srg-card" data-slot="takeaway" data-autofit="body"
         style="flex: 2 1 0; justify-content: center; line-height: 1.7;">
    {{what_this_means}}
  </aside>
</div>
<p class="srg-slide__note" data-slot="note" data-autofit="note">出典: {{source}}（{{as_of}}）</p>""",
    },
    {
        "id": "layout-table",
        "title": "表・マトリクス",
        "use": "行と列の交点に意味がある面。項目が並ぶだけなら layout-grid-cards を使う。",
        "media": ["block"],
        "extra_class": "srg-slide--table",
        "chrome": "full",
        "stage": """<header class="srg-slide__title" data-slot="title" data-autofit="title">{{title}}</header>
<p class="srg-slide__lead" data-slot="lead" data-autofit="body">{{what_to_compare}}</p>
<div class="srg-slide__main">
  <div class="srg-media" data-slot="media" data-media-slot="primary" style="align-items: stretch;">
    <!-- 表は 6 行 x 5 列までに収める。それを超えたら列を束ねるか面を割る
         (縮めて詰め込むと下限 --srg-fs-min を割り、読めない表になる)。
         強調したいセルだけ color: var(--srg-focal) を付ける。 -->
    <table data-slot="table" data-autofit="body"
           style="width: 100%; border-collapse: collapse; line-height: 1.5;">
      <thead>
        <tr><th>{{col_0}}</th><th>{{col_1}}</th><th>{{col_2}}</th></tr>
      </thead>
      <tbody>
        <tr><th scope="row">{{row_1}}</th><td>{{cell_1_1}}</td><td>{{cell_1_2}}</td></tr>
        <tr><th scope="row">{{row_2}}</th><td>{{cell_2_1}}</td><td>{{cell_2_2}}</td></tr>
        <tr><th scope="row">{{row_3}}</th><td>{{cell_3_1}}</td><td>{{cell_3_2}}</td></tr>
      </tbody>
    </table>
  </div>
</div>
<p class="srg-slide__note" data-slot="note" data-autofit="note">出典: {{source}}（{{as_of}}）</p>""",
    },
    {
        "id": "layout-metrics",
        "title": "数値の強調",
        "use": "KPI・実績・規模を数値そのもので見せる面。3 つまで。推移を見せたいなら layout-chart-main。",
        "media": ["none"],
        "extra_class": "srg-slide--metrics",
        "chrome": "full",
        "stage": """<header class="srg-slide__title" data-slot="title" data-autofit="title">{{title}}</header>
<div class="srg-slide__main">
  <div class="srg-grid srg-grid--3x1" data-slot="metrics">
    <section class="srg-card" style="align-items: center; justify-content: center; text-align: center;">
      <p data-slot="metric-1-value" data-autofit="title"
         style="font-size: var(--srg-fs-title); font-weight: 700; color: var(--srg-focal); line-height: 1.1; margin: 0;">{{metric_1_value}}</p>
      <p data-slot="metric-1-label" data-autofit="body" style="margin: 0;">{{metric_1_label}}</p>
      <p data-slot="metric-1-note" data-autofit="note"
         style="font-size: var(--srg-fs-note); color: var(--srg-fg-muted); margin: 0;">{{metric_1_basis}}</p>
    </section>
    <section class="srg-card" style="align-items: center; justify-content: center; text-align: center;">
      <p data-slot="metric-2-value" data-autofit="title"
         style="font-size: var(--srg-fs-title); font-weight: 700; line-height: 1.1; margin: 0;">{{metric_2_value}}</p>
      <p data-slot="metric-2-label" data-autofit="body" style="margin: 0;">{{metric_2_label}}</p>
      <p data-slot="metric-2-note" data-autofit="note"
         style="font-size: var(--srg-fs-note); color: var(--srg-fg-muted); margin: 0;">{{metric_2_basis}}</p>
    </section>
    <section class="srg-card" style="align-items: center; justify-content: center; text-align: center;">
      <p data-slot="metric-3-value" data-autofit="title"
         style="font-size: var(--srg-fs-title); font-weight: 700; line-height: 1.1; margin: 0;">{{metric_3_value}}</p>
      <p data-slot="metric-3-label" data-autofit="body" style="margin: 0;">{{metric_3_label}}</p>
      <p data-slot="metric-3-note" data-autofit="note"
         style="font-size: var(--srg-fs-note); color: var(--srg-fg-muted); margin: 0;">{{metric_3_basis}}</p>
    </section>
  </div>
</div>
<p class="srg-slide__note" data-slot="note" data-autofit="note">出典: {{source}}（{{as_of}}）</p>""",
    },
    {
        "id": "layout-grid-cards",
        "title": "カード格子",
        "use": "並列な項目 4〜6 件。順序に意味があるなら layout-timeline を使う。",
        "media": ["none"],
        "extra_class": "srg-slide--grid-cards",
        "chrome": "full",
        "stage": """<header class="srg-slide__title" data-slot="title" data-autofit="title">{{title}}</header>
<div class="srg-slide__main">
  <!-- 列数は項目数で選ぶ: 4 件 = srg-grid--2x2 / 6 件 = srg-grid--3x2 / 3 件 = srg-grid--3x1。
       それ以外の件数にするために card を余らせない (空 card は空白過多そのもの)。 -->
  <div class="srg-grid srg-grid--2x2" data-slot="cards">
    <section class="srg-card">
      <h3 data-autofit="subheading" style="font-size: var(--srg-fs-subheading); margin: 0;">{{card_1_head}}</h3>
      <p data-autofit="body" style="margin: 0; line-height: 1.6;">{{card_1_body}}</p>
    </section>
    <section class="srg-card">
      <h3 data-autofit="subheading" style="font-size: var(--srg-fs-subheading); margin: 0;">{{card_2_head}}</h3>
      <p data-autofit="body" style="margin: 0; line-height: 1.6;">{{card_2_body}}</p>
    </section>
    <section class="srg-card">
      <h3 data-autofit="subheading" style="font-size: var(--srg-fs-subheading); margin: 0;">{{card_3_head}}</h3>
      <p data-autofit="body" style="margin: 0; line-height: 1.6;">{{card_3_body}}</p>
    </section>
    <section class="srg-card">
      <h3 data-autofit="subheading" style="font-size: var(--srg-fs-subheading); margin: 0;">{{card_4_head}}</h3>
      <p data-autofit="body" style="margin: 0; line-height: 1.6;">{{card_4_body}}</p>
    </section>
  </div>
</div>""",
    },
    {
        "id": "layout-timeline",
        "title": "時系列帯",
        "use": "順序・段階・年表。左から右へ 1 本の流れで読ませる面。",
        "media": ["svg-diagram", "d3-diagram"],
        "extra_class": "srg-slide--timeline",
        "chrome": "full",
        "stage": """<header class="srg-slide__title" data-slot="title" data-autofit="title">{{title}}</header>
<p class="srg-slide__lead" data-slot="lead" data-autofit="body">{{what_changes_over_time}}</p>
<div class="srg-slide__main">
  <figure class="srg-media srg-band" data-slot="media" data-media-slot="primary" style="margin: 0;">
    <!-- 時間軸は必ず左→右。逆流や折返しをさせない (読み順が壊れる)。 -->
    {{timeline}}
  </figure>
</div>
<p class="srg-slide__note" data-slot="note" data-autofit="note">{{source_or_caveat}}</p>""",
    },
    {
        "id": "layout-image-full",
        "title": "全面画像",
        "use": "Codex 生成画像を面いっぱいに置き、その上に短い題だけ重ねる。",
        "media": ["codex-image"],
        "extra_class": "srg-slide--image-full",
        "chrome": "minimal",
        "stage": """<div class="srg-slide__main" style="flex-direction: column; justify-content: flex-end;">
  <h2 class="srg-image-full__title" data-slot="title" data-autofit="title"
      style="font-size: var(--srg-fs-title); font-weight: 700; line-height: 1.3; margin: 0;
             padding: var(--srg-gap); border-radius: var(--srg-radius);
             background: var(--srg-scrim);">{{title}}</h2>
</div>
<p class="srg-slide__note" data-slot="note" data-autofit="note">{{credit}}</p>""",
        # media は stage の外 (絶対配置の背面) に置く。
        "media_outside_stage": """<figure class="srg-media" data-slot="media" data-media-slot="background" style="margin: 0;">
  <!-- Codex 生成画像。object-fit は contain 固定 (cover にすると端が切れ、
       図中の文字や人物が欠ける)。alt は必ず内容を説明する文にする。 -->
  <picture class="ai-slide-canvas">
    <source srcset="{{image_webp}}" type="image/webp">
    <img src="{{image_png}}" alt="{{image_alt}}">
  </picture>
</figure>""",
    },
    {
        "id": "layout-image-side",
        "title": "画像 + 本文",
        "use": "生成画像で情景を見せ、隣で言葉にする面。画像が主役なら layout-image-full。",
        "media": ["codex-image"],
        "extra_class": "srg-slide--image-side",
        "chrome": "full",
        "stage": """<header class="srg-slide__title" data-slot="title" data-autofit="title">{{title}}</header>
<div class="srg-slide__main">
  <div class="srg-split srg-split--media-text">
    <figure class="srg-media" data-slot="media" data-media-slot="primary"
            style="flex-direction: column; margin: 0;">
      <picture class="ai-slide-canvas">
        <source srcset="{{image_webp}}" type="image/webp">
        <img src="{{image_png}}" alt="{{image_alt}}">
      </picture>
      <figcaption class="srg-media__caption" data-slot="caption" data-autofit="caption">{{caption}}</figcaption>
    </figure>
    <div data-slot="body" data-autofit="body"
         style="min-width: 0; display: flex; flex-direction: column; justify-content: center; gap: var(--srg-gap-tight); line-height: 1.7;">
      {{body}}
    </div>
  </div>
</div>""",
    },
    {
        "id": "layout-image-grid",
        "title": "画像格子",
        "use": "生成画像 3 枚前後を並べて対比・列挙する。1 枚なら layout-image-full / layout-image-side。",
        "media": ["codex-image"],
        "extra_class": "srg-slide--image-grid",
        "chrome": "full",
        "stage": """<header class="srg-slide__title" data-slot="title" data-autofit="title">{{title}}</header>
<div class="srg-slide__main">
  <div class="srg-grid srg-grid--3x1" data-slot="cells">
    <figure class="srg-media" data-media-slot="cell" style="flex-direction: column; margin: 0;">
      <picture class="ai-slide-canvas">
        <source srcset="{{image_1_webp}}" type="image/webp">
        <img src="{{image_1_png}}" alt="{{image_1_alt}}">
      </picture>
      <figcaption class="srg-media__caption" data-autofit="caption">{{image_1_caption}}</figcaption>
    </figure>
    <figure class="srg-media" data-media-slot="cell" style="flex-direction: column; margin: 0;">
      <picture class="ai-slide-canvas">
        <source srcset="{{image_2_webp}}" type="image/webp">
        <img src="{{image_2_png}}" alt="{{image_2_alt}}">
      </picture>
      <figcaption class="srg-media__caption" data-autofit="caption">{{image_2_caption}}</figcaption>
    </figure>
    <figure class="srg-media" data-media-slot="cell" style="flex-direction: column; margin: 0;">
      <picture class="ai-slide-canvas">
        <source srcset="{{image_3_webp}}" type="image/webp">
        <img src="{{image_3_png}}" alt="{{image_3_alt}}">
      </picture>
      <figcaption class="srg-media__caption" data-autofit="caption">{{image_3_caption}}</figcaption>
    </figure>
  </div>
</div>""",
    },
    {
        "id": "layout-quote",
        "title": "引用",
        "use": "一次情報の言葉をそのまま見せる。要約したいなら layout-message を使う。",
        "media": ["none"],
        "extra_class": "srg-slide--quote",
        "chrome": "full",
        "stage": """<div class="srg-slide__main" style="flex-direction: column; justify-content: center; gap: var(--srg-gap);">
  <blockquote data-slot="quote" data-autofit="title"
              style="font-size: var(--srg-fs-heading); font-weight: 600; line-height: 1.55; margin: 0;
                     padding-left: var(--srg-gap); border-left: 4px solid var(--srg-focal);">{{quote}}</blockquote>
  <p data-slot="attribution" data-autofit="note"
     style="font-size: var(--srg-fs-note); margin: 0;">— {{speaker}}, {{affiliation}}（{{when}}）</p>
</div>
<p class="srg-slide__note" data-slot="note" data-autofit="note">出典: {{source}}</p>""",
    },
    {
        "id": "layout-qa",
        "title": "問いと答え",
        "use": "想定質問への回答、FAQ、論点の潰し込み。問い 1 つに答え 1 つを対で置く。",
        "media": ["none"],
        "extra_class": "srg-slide--qa",
        "chrome": "full",
        "stage": """<header class="srg-slide__title" data-slot="title" data-autofit="title">{{title}}</header>
<div class="srg-slide__main" style="flex-direction: column; justify-content: space-evenly;">
  <!-- 対は 3 組まで。増えるなら面を割る (問いと答えが離れると対応が読めない)。 -->
  <section class="srg-card" data-slot="pair-1">
    <p data-autofit="subheading" style="font-size: var(--srg-fs-subheading); font-weight: 700; color: var(--srg-focal); margin: 0;">Q. {{question_1}}</p>
    <p data-autofit="body" style="margin: 0; line-height: 1.6;">A. {{answer_1}}</p>
  </section>
  <section class="srg-card" data-slot="pair-2">
    <p data-autofit="subheading" style="font-size: var(--srg-fs-subheading); font-weight: 700; color: var(--srg-focal); margin: 0;">Q. {{question_2}}</p>
    <p data-autofit="body" style="margin: 0; line-height: 1.6;">A. {{answer_2}}</p>
  </section>
</div>
<p class="srg-slide__note" data-slot="note" data-autofit="note">{{where_to_ask_more}}</p>""",
    },
    {
        "id": "layout-contact",
        "title": "連絡先",
        "use": "問い合わせ先・申込導線。読み手が次に取る行動が別にあるなら layout-closing。",
        "media": ["codex-image", "none"],
        "extra_class": "srg-slide--contact",
        "chrome": "index-only",
        "stage": """<header class="srg-slide__title" data-slot="title" data-autofit="title">{{title}}</header>
<div class="srg-slide__main">
  <div class="srg-split srg-split--text-media">
    <div data-slot="contacts" data-autofit="body"
         style="min-width: 0; display: flex; flex-direction: column; justify-content: center; gap: var(--srg-gap-tight); line-height: 1.7;">
      <p style="margin: 0;">{{organization}}</p>
      <p style="margin: 0;">{{email}}</p>
      <p style="margin: 0;">{{url_or_handle}}</p>
      <p style="margin: 0; color: var(--srg-fg-muted);">{{best_time_or_channel}}</p>
    </div>
    <figure class="srg-media" data-slot="media" data-media-slot="primary"
            style="flex-direction: column; margin: 0;">
      <!-- QR コード・地図・ロゴなど。無いなら figure ごと削る。 -->
      <picture class="ai-slide-canvas">
        <source srcset="{{code_webp}}" type="image/webp">
        <img src="{{code_png}}" alt="{{code_alt}}">
      </picture>
      <figcaption class="srg-media__caption" data-slot="caption" data-autofit="caption">{{code_caption}}</figcaption>
    </figure>
  </div>
</div>""",
    },
    {
        "id": "layout-closing",
        "title": "締め",
        "use": "deck の最終面。言い切りと、読者が次に取る行動を置く。",
        "media": ["none"],
        "extra_class": "srg-slide--closing",
        "chrome": "index-only",
        "stage": """<header class="srg-slide__title" data-slot="title" data-autofit="title">{{title}}</header>
<div class="srg-slide__main" style="flex-direction: column; justify-content: center; gap: var(--srg-gap-loose);">
  <p data-slot="message" data-autofit="title"
     style="font-size: var(--srg-fs-title); font-weight: 700; line-height: 1.4; margin: 0;">{{closing_message}}</p>
  <ol data-slot="next-actions" data-autofit="body"
      style="margin: 0; padding-left: 1.4em; line-height: 1.7;">
    <li>{{next_action_1}}</li>
    <li>{{next_action_2}}</li>
  </ol>
</div>
<p class="srg-slide__note" data-slot="note" data-autofit="note">{{contact_or_appendix}}</p>""",
    },
]


# chrome の出し方。面の役割で変える (表紙にページ番号や前後ナビは出さない)。
_CHROME = {
    "full": ("index", "nav"),
    "index-only": ("index", "page"),
    "minimal": (None, "page"),
    "none": (None, None),
}

_CHROME_HTML = {
    "index": """  <nav class="srg-slide__chrome-top" data-chrome="index" data-slot="index-bar">
    <!-- 章インデックス。現在章に data-current="true" を付ける。位置は骨格が
         決めるので、面ごとに座標を書かない (書くとページ間でズレる)。 -->
    <ol class="srg-index" style="display: flex; gap: var(--srg-gap); margin: 0; padding: 0; list-style: none; font-size: var(--srg-fs-caption);">
      <li data-current="{{is_current_1}}">{{section_1}}</li>
      <li data-current="{{is_current_2}}">{{section_2}}</li>
    </ol>
  </nav>""",
    "nav": """  <nav class="srg-slide__chrome-bottom" data-chrome="nav" data-slot="nav-bar">
    <!-- 前後ナビとページ番号。href は生成時に前後の面の id を入れる。
         「戻る先が反映されない」を防ぐため、prev/next は必ず両方書き、
         端の面では data-disabled="true" にする (要素ごと消すと幅が変わる)。 -->
    <a class="srg-nav__prev" data-nav="prev" href="#{{prev_id}}" data-disabled="{{prev_disabled}}">前へ</a>
    <span class="srg-nav__page" data-nav="page" style="margin-left: auto; font-size: var(--srg-fs-caption);">{{page_no}} / {{page_total}}</span>
    <a class="srg-nav__next" data-nav="next" href="#{{next_id}}" data-disabled="{{next_disabled}}" style="margin-left: var(--srg-gap);">次へ</a>
  </nav>""",
    "page": """  <div class="srg-slide__chrome-bottom" data-chrome="page" data-slot="page-no">
    <span class="srg-nav__page" data-nav="page" style="margin-left: auto; font-size: var(--srg-fs-caption);">{{page_no}} / {{page_total}}</span>
  </div>""",
}


def _slots(spec: dict) -> list[str]:
    """ひな形本文から data-slot 名を出現順に拾う (契約を本文から導出する)。"""
    import re
    body = spec["stage"] + spec.get("media_outside_stage", "")
    top, bottom = _CHROME[spec["chrome"]]
    for c in (top, bottom):
        if c:
            body += _CHROME_HTML[c]
    seen: list[str] = []
    for m in re.finditer(r'data-slot="([a-z0-9-]+)"', body):
        if m.group(1) not in seen:
            seen.append(m.group(1))
    return seen


def render(spec: dict, c: dict) -> str:
    top, bottom = _CHROME[spec["chrome"]]
    chrome_top = _CHROME_HTML[top] + "\n" if top else ""
    chrome_bottom = "\n" + _CHROME_HTML[bottom] if bottom else ""
    stage = "\n".join(("    " + l) if l else "" for l in spec["stage"].split("\n"))
    outside = spec.get("media_outside_stage", "")
    outside = ("\n" + "\n".join(("  " + l) if l else "" for l in outside.split("\n"))) if outside else ""
    slots = _slots(spec)
    st, ch = c["stage"], c["chrome"]

    return f"""<!--
  {spec["id"]}.html — {spec["title"]}
  生成物。手で編集しない。正本: scripts/build-slide-skeletons.py + {_CONTRACT}
  再生成: python3 scripts/build-slide-skeletons.py

  ■ この面を選ぶとき
  {spec["use"]}

  ■ 書き換えてよいのは次の 2 種類だけ
  1. `data-slot` を持つ要素の**中身** ({{{{...}}}} のプレースホルダ)。
     使えるスロット: {", ".join(slots)}
  2. `data-media-slot` の中に置く差し込み物。
     この面が受け入れる種別: {", ".join(spec["media"])}

  ■ 書き換えてはいけないもの (書き換えると面がズレる)
  - section / chrome / stage の class と構造、data-* 属性そのもの
  - 座標・寸法の直書き (面の数値は {_CONTRACT} が単一の正本)
  - `.srg-slide__main` の `flex: 1 1 auto` (これが空白過多を止めている)
  - 画像の `object-fit`。contain 固定 (cover にすると端が切れる)

  ■ 文字が収まらないときの順序
  1. `data-autofit` を持つ要素は slide-skeleton.js が font-size を {c["typography"]["min"]}px まで下げる。
  2. 下限でなお溢れると data-overflow="true" が付く。これは表示であって修復ではない。
     **面を割る**か本文を削る。{c["typography"]["min"]}px 未満へ縮めない。

  ■ 幾何 (すべて {_CONTRACT} 由来)
  canvas {c["canvas"]["width"]}x{c["canvas"]["height"]}px / chrome top {ch["top"]} bottom {ch["bottom"]} side {ch["side"]}
  stage ({st["x"]}, {st["y"]}) {st["width"]}x{st["height"]}px — 本文はこの矩形の外へ出さない
  印刷は A4 横。zoom {c["print"]["zoom_factor"]} で {c["print"]["stage_width_mm"]}x{c["print"]["stage_height_mm"]}mm、
  上下 {c["print"]["letterbox_band_mm"]}mm がレターボックス帯。画面と PDF は同一物。
-->
<section class="srg-slide {spec["extra_class"]}"
         data-slide-skeleton="{spec["id"]}"
         data-media-kinds="{" ".join(spec["media"])}"
         id="{{{{slide_id}}}}">
{chrome_top}{outside}
  <div class="srg-slide__stage">
{stage}
  </div>{chrome_bottom}
</section>
"""


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="build-slide-skeletons")
    ap.add_argument("--root", default=None)
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)

    root = Path(args.root) if args.root else Path(__file__).resolve().parent.parent
    src = root / _CONTRACT
    if not src.is_file():
        sys.stderr.write(f"error: {_CONTRACT} が無い\n")
        return 2
    contract = json.loads(src.read_text(encoding="utf-8"))
    kinds = set(contract["media"]["kinds"])

    out_dir = root / _OUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    bad = []
    for spec in _SKELETONS:
        unknown = set(spec["media"]) - kinds
        if unknown:
            sys.stderr.write(f"error: {spec['id']} が未知の media 種別を宣言: {sorted(unknown)}\n")
            return 2
        html = render(spec, contract)
        path = out_dir / f"{spec['id']}.html"
        if args.check:
            cur = path.read_text(encoding="utf-8") if path.is_file() else ""
            if cur != html:
                bad.append(spec["id"])
        else:
            path.write_text(html, encoding="utf-8")

    if args.check:
        if bad:
            sys.stderr.write(
                "ひな形が生成結果と異なる: " + ", ".join(bad) + "\n"
                "手で編集した場合は編集を scripts/build-slide-skeletons.py の\n"
                "_SKELETONS へ移し、再生成する。\n")
            return 1
        sys.stdout.write(f"slide skeletons: {len(_SKELETONS)} 件すべて契約と一致 -> PASS\n")
        return 0

    sys.stdout.write(f"wrote {len(_SKELETONS)} skeletons to {_OUT_DIR}/\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
