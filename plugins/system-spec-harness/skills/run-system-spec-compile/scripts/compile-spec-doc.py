#!/usr/bin/env python3
# /// script
# name: compile-spec-doc
# version: 0.1.0
# purpose: run-system-spec-compile の決定論コンパイラ。収集済み spec-state.json と取得済み fetched-references.json・設計知識参照から、章別 Markdown 複数ファイル + index.md を組み立てる。各章 frontmatter に確定マーカー (status: confirmed/draft + spec_cells + category) を付与し (C11 hook の判定ソース)、カテゴリ別収集状態 (未着手/収集中/確定/対象外+理由) と最新ドキュメント出典を反映する。ヒアリング継続やドキュメント再取得はしない (入力を組み立てるのみ)。
# inputs:
#   - argv: compile --spec spec-state.json --references fetched-references.json [--out-dir system-spec]
# outputs:
#   - system-spec/<category>.md 章別 Markdown + system-spec/index.md
#   - exit: 0=OK / 1=入力/IO エラー / 2=usage error
# contexts: [C, E]
# network: false
# write-scope: system-spec/ (章別 Markdown + index.md のみ)
# dependencies: []
# requires-python: ">=3.9"
# ///
"""spec-state.json + fetched-references.json → 章立て仕様書ドキュメントセット (決定論)。

本モジュールは run-system-spec-compile の**単一 writer / 確定状態保全**の中核である。
確定章 (aggregate=確定/対象外 の終端カテゴリ) の frontmatter に `status: confirmed` を付与し、
C11 hook (guard-confirmed-chapter-overwrite) はこのマーカー + spec-state.json のセル状態を
判定ソースとして誤上書きを fail-closed で遮断する。本 writer は spec-state.json を書換えず
(ヒアリング継続やドキュメント再取得はしない)、入力を章へ組み立てる純関数群として実装する。

入力形状 (plugin 共有契約・apply-spec-transition.py / validate-coverage-matrix.py と一致):
  spec-state.json: categories / platforms / matrix / qa_log / approval_log /
                   category_aggregate / targets(target_id[, category])
  fetched-references.json: references[{target_id, source_url, official_host,
                   official_publisher, version|last_updated, retrieved_at, latest_checked_at, summary}]

出力形状 (C11 hook の判定ソース):
  各章 <category>.md の frontmatter に status(confirmed|draft) / category / aggregate /
  spec_cells([<cat>.<pf>, ...]) / serves_goals([G1, ...]) を付与し、本文にカテゴリ別収集状態表
  (未収集/対象外+理由/確定+qa_ref)・設計知識参照ポインタ・最新ドキュメント出典表を含める。
  index.md が全章と集約状態を相互参照する。

要件 C9 (上位概念 anchor): spec-state.json の requirements_foundation (U1-U9) を
`00-requirements-definition.md` (要件定義書=憲法) として**最初の章**に生成し、各技術章 frontmatter
の serves_goals (セル serves_goals の集約) で全章を上位概念へトレース (anchor) する。index.md は
要件定義書を先頭に相互参照する。requirements_foundation 不在の spec-state でも空落ちせず draft 章を出す。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

# --- plugin 共有定数 (apply-spec-transition.py / validate-coverage-matrix.py と SSOT 整合) ---
CANONICAL_PLATFORMS = (
    "web",
    "mobile",
    "tablet",
    "desktop-windows",
    "desktop-linux",
    "desktop-macos",
)
PLATFORM_LABELS = {
    "web": "Web",
    "mobile": "モバイル",
    "tablet": "タブレット",
    "desktop-windows": "デスクトップ (Windows)",
    "desktop-linux": "デスクトップ (Linux)",
    "desktop-macos": "デスクトップ (macOS)",
}
CELL_STATES = {"未収集", "対象外", "確定"}
# 集約状態 (真理値表 4 値)。confirmed 章 = 終端 (確定/対象外)、draft 章 = 進行中 (未着手/収集中)。
TERMINAL_AGGREGATES = {"確定", "対象外"}

# カテゴリ → 設計知識参照ポインタ。SSOT は ref-system-design-knowledge/references/resource-map.yaml
# の read_when 記述。ハードコード写像は resource-map とドリフトし「カテゴリは一例・マトリクスが本質」
# 原則 (8 例に閉じる) を破るため、該当カテゴリ id を read_when 文字列にマッチさせて設計知識 .md を
# 実行時導出する (category_design_refs)。非正準カテゴリでも空落ちさせず汎用ポインタを添える。
DESIGN_REF_BASE = "ref-system-design-knowledge/references"
_DESIGN_KNOWLEDGE_DIR = (
    Path(__file__).resolve().parents[2] / "ref-system-design-knowledge" / "references"
)
_READ_WHEN_PAIRS: list[tuple[str, str]] | None = None
_DOCTRINE_REGISTRY: dict | None = None


def _resource_map_read_when() -> list[tuple[str, str]]:
    """resource-map.yaml から (file, read_when) 対を stdlib 最小パーサで抽出する (キャッシュ)。

    resource-map の list 構造 (`- file:` / `topic:` / `read_when:`) だけを解釈し、外部依存
    (PyYAML) を増やさない。ファイル不在・IO エラーは空リスト (呼び出し側が汎用ポインタへ倒す)。
    """
    global _READ_WHEN_PAIRS
    if _READ_WHEN_PAIRS is None:
        pairs: list[tuple[str, str]] = []
        try:
            text = (_DESIGN_KNOWLEDGE_DIR / "resource-map.yaml").read_text(encoding="utf-8")
        except OSError:
            text = ""
        cur_file: str | None = None
        for raw in text.splitlines():
            s = raw.strip()
            if s.startswith("- "):
                s = s[2:].strip()
            if s.startswith("file:"):
                cur_file = s[len("file:") :].strip()
            elif s.startswith("read_when:") and cur_file:
                pairs.append((cur_file, s[len("read_when:") :].strip()))
                cur_file = None
        _READ_WHEN_PAIRS = pairs
    return _READ_WHEN_PAIRS


def category_design_refs(cat_id: str) -> list[str]:
    """resource-map.yaml の read_when にカテゴリ id が現れる設計知識 .md を実行時導出する。

    SSOT = ref-system-design-knowledge/references/resource-map.yaml。ハードコード写像を排し、
    read_when の対応関係のみを唯一の根拠にするため任意カテゴリへ開く (正準 8 例に閉じない)。
    無マッチは空 (呼び出し側 render_design_refs が汎用ポインタを添える = 空落ち防止)。
    """
    refs: list[str] = []
    for fname, read_when in _resource_map_read_when():
        if fname.endswith(".md") and cat_id in read_when and fname not in refs:
            refs.append(fname)
    return refs


def _canonical_category_ids() -> list[str]:
    """system-category-taxonomy.json (C04 SSOT) の正準カテゴリ id 群を返す。"""
    try:
        tax = json.loads(
            (_DESIGN_KNOWLEDGE_DIR / "system-category-taxonomy.json").read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError):
        return []
    return [c["id"] for c in tax.get("categories", []) if isinstance(c, dict) and c.get("id")]


# 正準カテゴリ (taxonomy SSOT) の materialized view。値は resource-map の read_when から導出され
# ハードコードでないためドリフトしない。描画は category_design_refs() を直接使い任意カテゴリへ開く
# ため、本 dict は正準集合の参照・検証用 (R2-render の「resource-map の read_when 対応を写像」)。
CATEGORY_DESIGN_REFS: dict[str, list[str]] = {
    cat_id: category_design_refs(cat_id) for cat_id in _canonical_category_ids()
}


class CompileError(Exception):
    """入力契約違反 (必須キー欠落等) を検出したときに送出する。"""


# --------------------------------------------------------------------------- #
# 集約状態 (真理値表・validate-coverage-matrix.py._derive_aggregate と同一定義)  #
# --------------------------------------------------------------------------- #
def derive_aggregate(cells: list[str]) -> str:
    """セル状態集合からカテゴリ集約状態を真理値表で導出する。

    全セル未収集 -> 未着手 / 全セル対象外 -> 対象外 /
    未収集混在 -> 収集中 / それ以外で未収集0 -> 確定。
    """
    if not cells:
        return "未着手"
    if all(c == "未収集" for c in cells):
        return "未着手"
    if all(c == "対象外" for c in cells):
        return "対象外"
    if any(c == "未収集" for c in cells):
        return "収集中"
    return "確定"


# --------------------------------------------------------------------------- #
# spec-state 読み取りヘルパ                                                     #
# --------------------------------------------------------------------------- #
def _category_ids(spec: dict) -> list[str]:
    cats = spec.get("categories")
    if not isinstance(cats, list) or not cats:
        raise CompileError("spec-state: categories が非空配列でない")
    ids: list[str] = []
    for c in cats:
        if not isinstance(c, dict) or not c.get("id"):
            raise CompileError(f"spec-state: categories に id 欠落エントリ ({c!r})")
        ids.append(c["id"])
    return ids


def category_label(spec: dict, cat_id: str) -> str:
    for c in spec.get("categories", []):
        if isinstance(c, dict) and c.get("id") == cat_id:
            return c.get("label") or cat_id
    return cat_id


def _row(spec: dict, cat_id: str) -> dict:
    matrix = spec.get("matrix")
    if not isinstance(matrix, dict):
        raise CompileError("spec-state: matrix がオブジェクトでない")
    row = matrix.get(cat_id)
    if not isinstance(row, dict):
        raise CompileError(f"spec-state: matrix[{cat_id}] 行が存在しない")
    return row


def present_platforms(spec: dict, cat_id: str) -> list[str]:
    """カテゴリ行に存在する platform を canonical 順で返す。"""
    row = _row(spec, cat_id)
    return [pf for pf in CANONICAL_PLATFORMS if pf in row]


def cell_states(spec: dict, cat_id: str) -> list[str]:
    row = _row(spec, cat_id)
    return [row[pf].get("state") for pf in CANONICAL_PLATFORMS if pf in row]


def category_aggregate(spec: dict, cat_id: str) -> str:
    """集約状態を真理値表から導出する (宣言値ではなくセルから再計算し確定性を担保)。"""
    return derive_aggregate([s for s in cell_states(spec, cat_id) if s])


def chapter_status(aggregate: str) -> str:
    """章 frontmatter の確定マーカー。終端 (確定/対象外) は confirmed、進行中は draft。"""
    return "confirmed" if aggregate in TERMINAL_AGGREGATES else "draft"


def spec_cell_ids(spec: dict, cat_id: str) -> list[str]:
    """章に対応する spec-state マトリクスセル id (<category>.<platform>) を canonical 順で返す。"""
    return [f"{cat_id}.{pf}" for pf in present_platforms(spec, cat_id)]


# --------------------------------------------------------------------------- #
# 上位概念 (requirements_foundation) / serves_goals トレース — 要件 C9          #
# --------------------------------------------------------------------------- #
REQUIREMENTS_CHAPTER = "00-requirements-definition.md"


def requirements_foundation(spec: dict) -> dict:
    """spec-state.json の requirements_foundation を返す (不在時は空 dict)。"""
    rf = spec.get("requirements_foundation")
    return rf if isinstance(rf, dict) else {}


def foundation_status(spec: dict) -> str:
    """要件定義章の確定マーカー。requirements_foundation.confirmed が真なら confirmed。"""
    return "confirmed" if requirements_foundation(spec).get("confirmed") else "draft"


def chapter_serves_goals(spec: dict, cat_id: str) -> list[str]:
    """章 (カテゴリ) の serves_goals を、各セルの serves_goals の和集合として順序保持で返す。

    確定セルに付与された上位概念トレース (serves_goals) をカテゴリ粒度へ集約する。
    canonical platform 順に走査し、初出順で重複除去する。
    """
    row = _row(spec, cat_id)
    out: list[str] = []
    for pf in CANONICAL_PLATFORMS:
        cell = row.get(pf)
        if not isinstance(cell, dict):
            continue
        for gid in cell.get("serves_goals") or []:
            if isinstance(gid, str) and gid and gid not in out:
                out.append(gid)
    return out


# --------------------------------------------------------------------------- #
# 出典記録 (fetched-references) の章割り当て                                    #
# --------------------------------------------------------------------------- #
def _target_category_map(spec: dict) -> dict[str, str]:
    """targets[{target_id, category}] から target_id -> category を作る (category 任意)。"""
    out: dict[str, str] = {}
    for t in spec.get("targets", []) or []:
        if isinstance(t, dict) and t.get("target_id") and t.get("category"):
            out[t["target_id"]] = t["category"]
    return out


def references_by_category(spec: dict, refs_data: dict) -> tuple[dict[str, list[dict]], list[dict]]:
    """fetched-references を章 (カテゴリ) 別に振り分ける。

    target の category が解決できる参照は該当章へ、解決できない参照は
    未割当 (index の全体出典一覧へ) として返す。戻り値は (章別 dict, 未割当 list)。
    """
    cat_map = _target_category_map(spec)
    by_cat: dict[str, list[dict]] = {}
    unassigned: list[dict] = []
    refs = refs_data.get("references")
    if not isinstance(refs, list):
        raise CompileError("fetched-references: references が配列でない")
    for ref in refs:
        if not isinstance(ref, dict) or not ref.get("target_id"):
            continue
        cat = cat_map.get(ref["target_id"])
        if cat:
            by_cat.setdefault(cat, []).append(ref)
        else:
            unassigned.append(ref)
    return by_cat, unassigned


def _ref_version(ref: dict) -> str:
    return str(ref.get("version") or ref.get("last_updated") or "-")


def _ref_host(ref: dict) -> str:
    host = ref.get("official_host") or ""
    if not host and ref.get("source_url"):
        host = urlparse(ref["source_url"]).netloc
    return host or "-"


# --------------------------------------------------------------------------- #
# レンダリング (章 / index) — 純関数                                            #
# --------------------------------------------------------------------------- #
def render_frontmatter(spec: dict, cat_id: str) -> str:
    """章 frontmatter (確定マーカー) を組み立てる (C11 hook 判定ソース)。"""
    agg = category_aggregate(spec, cat_id)
    status = chapter_status(agg)
    cells = spec_cell_ids(spec, cat_id)
    serves = chapter_serves_goals(spec, cat_id)
    lines = [
        "---",
        f"status: {status}",
        f"category: {cat_id}",
        f"aggregate: {agg}",
        f"spec_cells: [{', '.join(cells)}]",
        f"serves_goals: [{', '.join(serves)}]",
        "---",
    ]
    return "\n".join(lines)


def render_state_table(spec: dict, cat_id: str) -> str:
    """カテゴリ別収集状態表 (未収集/対象外+理由/確定+qa_ref) を組み立てる。"""
    row = _row(spec, cat_id)
    lines = [
        "## カテゴリ別収集状態",
        "",
        "| プラットフォーム | 状態 | 根拠 |",
        "|---|---|---|",
    ]
    for pf in CANONICAL_PLATFORMS:
        cell = row.get(pf)
        plabel = PLATFORM_LABELS.get(pf, pf)
        if not isinstance(cell, dict):
            lines.append(f"| {plabel} ({pf}) | 未収集 | — |")
            continue
        state = cell.get("state", "未収集")
        if state == "確定":
            basis = f"確定質疑: {cell.get('qa_ref', '-')}"
            # qa_refs (追加の裏付け質疑) も併記する。セルは qa_ref を 1 件しか持てないため、
            # 話題が積み重なると先行する根拠が章から見えなくなる。serves_goals が「どの目的に
            # 資するか」を示すのに対し、qa_refs は「その主張がどの質疑に遡れるか」を示す。
            extra = [r for r in cell.get("qa_refs") or [] if r != cell.get("qa_ref")]
            if extra:
                joined = ", ".join(f"`{r}`" for r in extra)
                basis += (
                    f"。裏付け質疑 (`qa_refs`): {joined}"
                    " — 本章の「確定内容 (質疑録)」へ接地根拠として併記"
                )
            # 資するゴールを本文へも出す。frontmatter の serves_goals だけだと、章を読む
            # 人にも同期ゲートにも「この確定がどの上位概念に紐づくか」が本文から辿れず、
            # 要件 C9 の anchor が frontmatter の宣言だけで終わる。
            serves = [g for g in cell.get("serves_goals") or [] if isinstance(g, str)]
            if serves:
                basis += "。資するゴール: " + ", ".join(serves)
        elif state == "対象外":
            reason = cell.get("reason") or f"承認: {cell.get('approval_ref', '-')}"
            basis = f"理由: {reason}"
        else:
            basis = "収集中 (未確定)"
        lines.append(f"| {plabel} ({pf}) | {state} | {basis} |")
    return "\n".join(lines)


_DEEP_CARD_SECTIONS = (
    ("目的", "目的"),
    ("解決する問題", "解決する問題"),
    ("適用条件", "適用条件"),
    ("非適用条件", "非適用条件"),
    ("トレードオフ・失敗モード", "トレードオフ・失敗モード"),
    ("目的達成への寄与", "goalへの寄与"),
)


def _markdown_sections(text: str) -> dict[str, str]:
    matches = list(re.finditer(r"^##\s+(.+?)\s*$", text, re.M))
    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections[match.group(1).strip()] = text[match.end() : end].strip()
    return sections


def _card_title(text: str, fallback: str) -> str:
    match = re.search(r"^#\s+(.+?)\s*$", text, re.M)
    return match.group(1).strip() if match else fallback


def _render_markdown_card(filename: str) -> list[str]:
    """C04 deep cardの目的適合情報を参照先から章本文へ実体化する。"""
    path = _DESIGN_KNOWLEDGE_DIR / filename
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise CompileError(f"設計知識cardを読めない: {filename}: {exc}") from exc
    sections = _markdown_sections(text)
    missing = [heading for heading, _ in _DEEP_CARD_SECTIONS if not sections.get(heading)]
    if missing:
        raise CompileError(f"設計知識card {filename} の深度項目欠落: {missing}")
    lines = [f"### {_card_title(text, filename)}", "", f"- 出典カード: `{DESIGN_REF_BASE}/{filename}`"]
    for heading, label in _DEEP_CARD_SECTIONS:
        lines.extend(["", f"#### {label}", "", sections[heading]])
    return lines


def _candidate_applies_to_chapter(spec: dict, candidate: dict, cat_id: str) -> bool:
    categories = candidate.get("categories")
    if isinstance(categories, list) and categories:
        return cat_id in categories
    candidate_goals = set(candidate.get("serves_goals") or [])
    return bool(candidate_goals.intersection(chapter_serves_goals(spec, cat_id)))


def _render_candidate_card(candidate: dict) -> list[str]:
    card = candidate.get("card") or {}
    title = candidate.get("topic") or candidate.get("id") or "knowledge candidate"
    lines = [
        f"### {title}",
        "",
        f"- project candidate: `{candidate.get('id', '-')}` (`{candidate.get('status', '-')}`)",
        f"- 解決対象: {candidate.get('problem', '-')}",
    ]
    fields = (
        ("purpose", "目的"),
        ("problems", "解決する問題"),
        ("applies_when", "適用条件"),
        ("does_not_apply_when", "非適用条件"),
        ("tradeoffs", "トレードオフ"),
        ("failure_modes", "失敗モード"),
        ("goal_contribution", "goalへの寄与"),
    )
    for key, label in fields:
        value = card.get(key)
        lines.extend(["", f"#### {label}", ""])
        if isinstance(value, list):
            lines.extend(f"- {item}" for item in value)
        else:
            lines.append(str(value or "(未記入)"))
    return lines


def _render_design_application(spec: dict | None, cat_id: str) -> list[str]:
    """「この章でどう適用したか」を出す。無ければ空洞であることを隠さず書く。

    以下に続く card 本文は共有資産の逐語であり、同じ card を引く章どうしは byte 単位で
    一致する。それは異常ではなく当然で、だからこそ card だけを並べた節は「適用した」
    証拠になり得ない (機械注入したものを自分で適用の証拠として数える自己循環)。
    章固有性を担えるのは spec-state 側に書かれたこの記述だけなので、未記入なら
    節が空洞であることを本文に出す。
    """
    record = ((spec or {}).get("design_applications") or {}).get(cat_id)
    heading = ["### 本章での適用", ""]
    if not isinstance(record, dict) or not str(record.get("text") or "").strip():
        return heading + [
            "> **未記入** — 本章固有の適用記述が spec-state に無い。"
            "以下の card 本文は共有資産の逐語であり、同じ card を引く他章と一致する。"
            "この節は現時点で「参照した」ことしか示しておらず、「適用した」証拠ではない。",
            "",
        ]
    meta = []
    if record.get("basis"):
        meta.append(f"根拠の性質: {BASIS_LABELS.get(record['basis'], record['basis'])}")
    if record.get("recorded_at"):
        meta.append(f"記録時刻: {record['recorded_at']}")
    body = heading + [str(record["text"]).strip(), ""]
    if meta:
        body.extend([f"- ({' / '.join(meta)})", ""])
    return body


def render_design_refs(cat_id: str, spec: dict | None = None) -> str:
    """設計知識をpathだけでなく、目的達成に使える意味項目まで章へ描画する。"""
    refs = category_design_refs(cat_id)
    lines = [
        "## 適用された設計知識",
        "",
        # card を実装証拠と読み違えると、設計採用のつもりで書いた `採否: applied` が
        # 「検証済み」の意味に育ってしまう。規範の所在を節の先頭で明示しておく。
        "> 以下の deep knowledge card は設計判断を支援する**非規範の参考資料**であり、"
        "実装済み・検証済みの証拠ではない。カード内の `採否: applied` は設計採用を意味し、"
        "実装状態は意味しない。規範となる差分は本章の To-Be / Delta 節と参照先仕様で管理する。",
        "",
    ]
    lines.extend(_render_design_application(spec, cat_id))
    if not refs:
        # card 0 件には意味の異なる2状態がある — まだ選んでいない (未着手) か、
        # 引ける card が無いと調べた上で確定した (不在の確定) か。両者を同じ文言に畳むと、
        # 章固有の適用記述が「0件は収集漏れではない」と述べている直下に
        # 「選定・深化してから確定する」という未着手の断り書きが並び、章が自分と矛盾する。
        # 適用記述の有無でどちらかを判別できるので、分岐して書き分ける。
        explained = str(
            (((spec or {}).get("design_applications") or {}).get(cat_id) or {}).get("text")
            or ""
        ).strip()
        if explained:
            lines.append(
                f"- `{DESIGN_REF_BASE}/resource-map.yaml` "
                "(本章へ引く card は 0 件。未着手ではなく、上の適用記述で"
                "0 件である理由を述べた上での確定である)"
            )
        else:
            lines.append(
                f"- `{DESIGN_REF_BASE}/resource-map.yaml` "
                "(resource-map 未定義。関連cardを選定・深化してから確定する)"
            )
    else:
        for index, filename in enumerate(refs):
            if index:
                lines.extend(["", "---", ""])
            lines.extend(_render_markdown_card(filename))

    if spec is not None:
        candidates = [
            candidate
            for candidate in spec.get("knowledge_candidates", []) or []
            if isinstance(candidate, dict)
            and candidate.get("status") in {"deepened", "promoted"}
            and _candidate_applies_to_chapter(spec, candidate, cat_id)
        ]
        for candidate in candidates:
            lines.extend(["", "---", ""])
            lines.extend(_render_candidate_card(candidate))
    return "\n".join(lines)


def render_citations(refs: list[dict], *, empty_note: str) -> str:
    """最新ドキュメント出典表を組み立てる (R2-render の最新ドキュメント出典反映)。"""
    lines = ["## 最新ドキュメント出典", ""]
    if not refs:
        lines.append(empty_note)
        return "\n".join(lines)
    lines.append("| 対象 | バージョン | 公式発行元 | 出典URL | 取得 | 最新確認 |")
    lines.append("|---|---|---|---|---|---|")
    for ref in refs:
        lines.append(
            "| {tid} | {ver} | {pub} ({host}) | {url} | {ret} | {chk} |".format(
                tid=ref.get("target_id", "-"),
                ver=_ref_version(ref),
                pub=ref.get("official_publisher", "-"),
                host=_ref_host(ref),
                url=ref.get("source_url", "-"),
                ret=ref.get("retrieved_at", "-"),
                chk=ref.get("latest_checked_at", "-"),
            )
        )
    return "\n".join(lines)


def _doctrine_registry() -> dict:
    """doctrine-anchor-registry.json (C04 SSOT) を読む (キャッシュ)。"""
    global _DOCTRINE_REGISTRY
    if _DOCTRINE_REGISTRY is None:
        path = _DESIGN_KNOWLEDGE_DIR / "doctrine-anchor-registry.json"
        try:
            _DOCTRINE_REGISTRY = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise CompileError(f"doctrine-anchor-registry.json を読めない: {exc}") from exc
    return _DOCTRINE_REGISTRY


def render_doctrine_anchors(cat_id: str, spec: dict | None = None) -> str:
    """章の上流指針 (category → concern → authority) を doctrine registry から描画する。

    registry 自身が "C03 が各章生成時に category→concern→authority を上流判断として反映する"
    と宣言しているのに、従来 compile は resource-map の `.md` card しか引かず registry を
    一度も読まなかった。その結果 Apple HIG / Clean Architecture / OWASP ASVS / Google SRE の
    4 authority が章本文に現れず、上流指針が宣言だけで終わっていた。ここが唯一の描画経路。

    registry の mapping_rule に従い、未帰属 category は pending 例外が無い限り
    CompileError で保留する (勝手に空節を出して被覆漏れを隠さない)。

    ただし registry の転記だけでは、authority が章に「現れた」ことしか示せない。
    card レベルで先に判明したのと同じ空洞 — 機械注入したものを自分で適用の証拠として
    数える自己循環 — が doctrine レベルにも残る。それを塞ぐのが最終列で、
    spec-state の doctrine_applications にある章固有の記述だけがそこを埋められる。
    未記入なら空欄で濁さず「未記入」と本文に出す。
    """
    reg = _doctrine_registry()
    concern_map = reg.get("category_concern_map") or {}
    by_id = {c.get("concern_id"): c for c in reg.get("concerns") or [] if isinstance(c, dict)}
    concern_ids = concern_map.get(cat_id)
    lines = ["## 上流指針 (doctrine anchors)", ""]
    if not concern_ids:
        pending = [
            e
            for e in reg.get("pending_exceptions") or []
            if isinstance(e, dict) and e.get("category") == cat_id
        ]
        if not pending:
            raise CompileError(
                f"doctrine anchor 未帰属カテゴリ: {cat_id} "
                "(category_concern_map に無く pending_exceptions にも無い。"
                "registry を更新してから compile する)"
            )
        lines.append(
            "> 本カテゴリは doctrine anchor 未帰属の pending 例外である "
            "(owner/reason/approval_state は registry を参照)。上流指針の確定まで"
            "本章の設計判断は暫定として扱う。"
        )
        for entry in pending:
            lines.append(
                f"- owner: {entry.get('owner', '-')} / reason: {entry.get('reason', '-')} "
                f"/ approval_state: {entry.get('approval_state', '-')}"
            )
        return "\n".join(lines)
    lines.extend(
        [
            "> 本章の設計判断が従う上流の正本 (1 concern 1 authority)。具体技術ではなく"
            "上流工程を導く規範であり、下位の技術選定は本節と矛盾してはならない。"
            f"正本: `{DESIGN_REF_BASE}/doctrine-anchor-registry.json`",
            "",
            "| 設計 concern | 上流の正本 (authority) | 導く範囲 | 出典 | 最終確認 "
            "| 本章の確定セルへの反映 |",
            "|---|---|---|---|---|---|",
        ]
    )
    applied = ((spec or {}).get("doctrine_applications") or {}).get(cat_id) or {}
    for cid in concern_ids:
        concern = by_id.get(cid)
        if not concern:
            raise CompileError(
                f"doctrine registry の整合性違反: category {cat_id} が参照する concern "
                f"{cid} が concerns に存在しない"
            )
        record = applied.get(cid) if isinstance(applied, dict) else None
        text = str((record or {}).get("text") or "").strip()
        # 表セルなので改行とパイプを潰す。原文は spec-state 側に残る。
        cell = text.replace("|", "\\|").replace("\n", " ") if text else "**未記入**"
        lines.append(
            "| {cid} | {auth} | {guides} | {src} | {chk} | {cell} |".format(
                cid=cid,
                auth=concern.get("authority", "-"),
                guides=concern.get("guides", "-"),
                src=concern.get("source_ref", "-"),
                chk=concern.get("last_checked_at", "-"),
                cell=cell,
            )
        )
    if any(
        not str((applied.get(cid) or {}).get("text") or "").strip() for cid in concern_ids
    ):
        lines.extend(
            [
                "",
                "> **未記入** の行は、上流の正本を掲げただけで本章の確定内容へ反映した箇所を"
                "示せていない。表への出現は反映の証拠ではない。",
            ]
        )
    return "\n".join(lines)


def _qa_index(spec: dict) -> dict[str, dict]:
    """qa_log を id 索引にする (不正 entry は落とす)。"""
    return {
        e["id"]: e
        for e in spec.get("qa_log", []) or []
        if isinstance(e, dict) and isinstance(e.get("id"), str)
    }


BASIS_LABELS = {
    "user-decision": "利用者が代替案を見たうえで明示選択した決定",
    "observed-fact": "コード・設定・公式文書で検証できる観測事実",
    "agent-inference": "アシスタントの推定 (利用者確認も検証可能な出典も経ていない)",
}


def _render_corrections(entry: dict) -> list[str]:
    """凍結された答の本文に対する訂正を、本文の直後へ出す。

    question / answer は改竄防止で凍結されている。そのため本文の散文へ誤った値を書くと、
    凍結がそのまま「訂正できない誤り」になる。章だけを読む利用者は、反証済みの値を
    唯一の事実として受け取ってしまう。訂正を本文から離れた場所に置くと同じことが起きる
    ので、必ず答の直後に、本文より訂正が優先することを明示して出す。
    """
    corrections = entry.get("corrections") or []
    if not isinstance(corrections, list) or not corrections:
        return []
    lines = [
        "> **訂正あり** — 直上の答は凍結された記録であり、後から次の訂正が入っている。",
        "> 本文中の記述と食い違う場合は、訂正側が正である。",
        ">",
    ]
    for c in corrections:
        if not isinstance(c, dict):
            continue
        when = str(c.get("corrected_at") or "(時刻不明)")
        note = str(c.get("note") or "").strip() or "(内容未記入)"
        lines.append(f"> - `{when}` — {note}")
        # 計測値時刻の訂正はフィールド自体を書き換える (誤値を機械可読な位置に残さない)。
        # 何をどう変えたかを散文任せにせず、旧値と新値をそのまま出す。
        field = c.get("corrected_field")
        if field:
            before = c.get("previous_value")
            after = c.get("corrected_value")
            lines.append(
                f">   - 変更: `{field}` `{before!r}` → `{after!r}` "
                "(フィールドは訂正後の値。旧値はこの行にのみ残る)"
            )
    lines.append("")
    return lines


def _render_qa_entry(entry: dict | None, ref_id: str, *, role: str) -> list[str]:
    """1 質疑を章本文へ実体化する。不在参照は隠さず欠落として明示する。"""
    if entry is None:
        return [
            f"- **{role}** `{ref_id}` — **参照先が qa_log に存在しない** "
            "(接地根拠を辿れない。elicit 側で質疑を復元すること)",
            "",
        ]
    lines = [f"#### {role}: `{ref_id}`", ""]
    for label, key in (("問", "question"), ("答", "answer")):
        value = str(entry.get(key) or "").strip() or "(未記入)"
        lines.extend([f"**{label}**", "", value, ""])
        if key == "answer":
            lines.extend(_render_corrections(entry))
    # provenance は writer が任意項目として保持する (出所不明の回答を確定根拠にしないため)。
    # basis は「その回答が誰の判断か」(利用者決定 / 観測事実 / アシスタントの推定) を
    # 機械可読に宣言する。章に出さないと、利用者が選んだ結論とアシスタントの推定が
    # 読者にとって同じ見た目になる。
    prov = entry.get("provenance")
    answered_at = entry.get("answered_at")
    basis = entry.get("basis")
    if prov or answered_at or basis:
        meta = []
        if basis:
            meta.append(f"根拠の性質: {BASIS_LABELS.get(basis, basis)}")
        if prov:
            meta.append(f"出所: {prov}")
        if answered_at:
            meta.append(f"回答時刻: {answered_at}")
        lines.extend([f"- ({' / '.join(meta)})", ""])
    return lines


def _chapter_approval_refs(spec: dict, cat_id: str) -> list[str]:
    """その章の対象外セルが引用している承認 id を、重複なく出現順で返す。"""
    row = _row(spec, cat_id)
    refs: list[str] = []
    for pf in CANONICAL_PLATFORMS:
        cell = row.get(pf)
        if not isinstance(cell, dict) or cell.get("state") != "対象外":
            continue
        ref = cell.get("approval_ref")
        if isinstance(ref, str) and ref and ref not in refs:
            refs.append(ref)
    return refs


def _approval_index(spec: dict) -> dict[str, dict]:
    """approval_log を id 索引にする (不正 entry は落とす)。"""
    return {
        e["id"]: e
        for e in spec.get("approval_log", []) or []
        if isinstance(e, dict) and isinstance(e.get("id"), str)
    }


def _qa_entries_naming(spec: dict, approval_id: str) -> list[tuple[str, dict]]:
    """その承認 id を逐語で名指ししている質疑を拾う。

    approval_log の entry は {id, note} だけで、どの質疑がその承認の実体かを指すキーを
    持たない。writer が承認と質疑を同じ turn で作る運用上、note か質疑側の本文の
    どちらかが相手の id を名指ししているのが常態なので、その名指しを関係として使う。
    推測で結び付けているのではなく「名指ししている」という検証可能な事実だけを根拠に
    する (節見出しでもそう呼ぶ)。
    """
    out = []
    for entry in spec.get("qa_log", []) or []:
        if not isinstance(entry, dict) or not isinstance(entry.get("id"), str):
            continue
        blob = "\n".join(str(v) for v in entry.values() if isinstance(v, str))
        if approval_id in blob:
            out.append((entry["id"], entry))
    return out


def render_approvals(spec: dict, ref_ids: list[str], *, heading: str, intro: str) -> str:
    """章が引用している承認の本文を実体化する。

    従来 compile は承認を `appr-xxx-007` という **id 文字列だけ**で出しており (対象外セルの
    「承認: <id>」、要件定義章の「確定マーカー: status: confirmed」)、その承認が何をどこまで
    認めたものかは spec-state.json を開かないと分からなかった。章だけを読む人にとって、
    利用者が範囲を見た上で認めた確定と、アシスタントが埋めた確定が同じ見た目になる。
    本節はその承認範囲の実体であり、確定質疑に対する「確定内容 (質疑録)」と同じ役割を
    承認に対して果たす。
    """
    lines = [f"## {heading}", "", f"> {intro}", ""]
    if not ref_ids:
        lines.append("- (本章が引用している承認記録なし)")
        return "\n".join(lines)
    index = _approval_index(spec)
    for ref in ref_ids:
        entry = index.get(ref)
        if entry is None:
            lines += [
                f"- **承認** `{ref}` — **参照先が approval_log に存在しない** "
                "(承認範囲を辿れない。elicit 側で承認記録を復元すること)",
                "",
            ]
            continue
        note = str(entry.get("note") or "").strip() or "(承認範囲が未記入)"
        lines += [f"### 承認: `{ref}`", "", note, ""]
        for qa_id, qa_entry in _qa_entries_naming(spec, ref):
            lines.extend(
                _render_qa_entry(qa_entry, qa_id, role="この承認を名指ししている質疑")
            )
    return "\n".join(lines)


def render_confirmed_content(spec: dict, cat_id: str) -> str:
    """確定セルの接地根拠 (質疑録) を章本文へ実体化する。

    従来 compile は「確定質疑: qa-xxx-001」という **id 文字列だけ**を状態表へ出し、その id が
    指す実際の問答を章のどこにも展開しなかった。状態表の但し書きが「本章の『確定内容
    (質疑録)』へ併記」と宣言している節がそもそも生成されておらず、章を読んでも何が確定した
    のか分からない (= 章本文の空洞化)。本節がその宣言先の実体である。
    """
    row = _row(spec, cat_id)
    qa = _qa_index(spec)
    lines = [
        "## 確定内容 (質疑録)",
        "",
        "> 本章の各確定セルが何を根拠に確定したかの実体。`qa_ref` が主たる接地根拠、"
        "`qa_refs` がそれを支える裏付け質疑であり、いずれも qa_log (spec-state.json) の"
        "逐語である。ここに現れない主張は本章の確定内容ではない。",
        "",
    ]
    confirmed = [
        pf
        for pf in CANONICAL_PLATFORMS
        if isinstance(row.get(pf), dict) and row[pf].get("state") == "確定"
    ]
    if not confirmed:
        lines.append("- (確定セルなし。全セルが対象外または未収集であり、確定内容を持たない)")
        return "\n".join(lines)
    seen: set[str] = set()
    for pf in confirmed:
        cell = row[pf]
        lines.extend([f"### {PLATFORM_LABELS.get(pf, pf)} ({pf})", ""])
        serves = [g for g in cell.get("serves_goals") or [] if isinstance(g, str)]
        if serves:
            lines.extend([f"- 資するゴール: {', '.join(serves)}", ""])
        primary = cell.get("qa_ref")
        if isinstance(primary, str) and primary:
            lines.extend(_render_qa_entry(qa.get(primary), primary, role="主たる接地根拠"))
            seen.add(primary)
        for ref in cell.get("qa_refs") or []:
            if not isinstance(ref, str) or ref == primary:
                continue
            if ref in seen:
                lines.extend([f"- 裏付け質疑 `{ref}` — 本章の上掲に既出", ""])
                continue
            lines.extend(_render_qa_entry(qa.get(ref), ref, role="裏付け質疑"))
            seen.add(ref)
    return "\n".join(lines).rstrip("\n")


def _chapter_decisions(spec: dict, cat_id: str, goals: list[str]) -> list[dict]:
    """章に効く確定意思決定 (category 一致、または serves_goals が章ゴールと交差) を返す。"""
    goalset = set(goals)
    out = []
    for dec in spec.get("decisions", []) or []:
        if not isinstance(dec, dict) or dec.get("status") != "confirmed":
            continue
        if dec.get("category") == cat_id or (set(dec.get("serves_goals") or []) & goalset):
            out.append(dec)
    return out


def render_to_be_delta(spec: dict, cat_id: str) -> str:
    """章が到達すべき状態 (To-Be) と、その達成を判定する受入条件 (Delta) を描画する。

    `render_design_refs` は「規範となる差分は本章の To-Be / Delta 節と参照先仕様で管理する」
    と本文で宣言しながら、その節を生成していなかった。参考資料 (非規範の card) しか本文が
    無ければ、何が規範なのか章から判別できない。本節は上位概念 U3/U4/U9 と確定 decisions を
    章ゴールで絞り込んだ射影であり、章の規範側の正本である。

    As-Is (現行実装の姿) は spec-state.json が保持しないため、ここでは創作しない。Delta は
    objectives の `measure` — 達成したことを機械的に判定できる観測点 — として描画する。
    """
    lines = ["## To-Be / Delta", ""]
    goals = chapter_serves_goals(spec, cat_id)
    if not goals:
        lines.append(
            "- (本章の確定セルに serves_goals が無く、上位概念への anchor を持たない。"
            "要件 C9 上これは drift 候補であり、確定前に serves_goals を付与すること)"
        )
        return "\n".join(lines)
    foundation = requirements_foundation(spec)
    goal_text = {
        g.get("id"): g.get("text", "")
        for g in foundation.get("goals") or []
        if isinstance(g, dict)
    }
    lines.extend(
        [
            "> 本章の**規範**。上位概念 (要件定義書 U3 ゴール / U4 目標 / U9 具体的やりたいこと) を"
            "本章の serves_goals で絞り込んだ射影であり、設計知識 card (非規範の参考資料) とは"
            "役割が異なる。As-Is (現行実装の姿) は spec-state.json の管轄外のため本節では断定せず、"
            "到達点と、その到達を判定する観測点だけを規範として置く。",
            "",
            "### 到達すべき状態 (To-Be)",
            "",
        ]
    )
    for gid in goals:
        lines.append(f"- **{gid}**: {goal_text.get(gid, '(要件定義書に該当ゴールなし)')}")

    objectives = [
        o
        for o in foundation.get("objectives") or []
        if isinstance(o, dict) and set(o.get("serves") or []) & set(goals)
    ]
    lines.extend(["", "### 受入条件 (Delta の判定点)", ""])
    if not objectives:
        lines.append("- (本章ゴールに紐づく目標 U4 が無い。受入条件が未定義である)")
    else:
        lines.extend(["| 目標 | 到達点 | 達成の観測点 (measure) |", "|---|---|---|"])
        for obj in objectives:
            lines.append(
                "| {oid} | {text} | {measure} |".format(
                    oid=obj.get("id", "-"),
                    text=str(obj.get("text", "-")).replace("|", "\\|"),
                    measure=str(obj.get("measure", "-")).replace("|", "\\|"),
                )
            )

    intents = [
        i
        for i in foundation.get("concrete_intents") or []
        if isinstance(i, dict) and set(i.get("serves") or []) & set(goals)
    ]
    if intents:
        lines.extend(["", "### 本章がかなえる具体的やりたいこと (U9)", ""])
        for intent in intents:
            lines.append(f"- **{intent.get('id', '-')}**: {intent.get('text', '-')}")

    decisions = _chapter_decisions(spec, cat_id, goals)
    lines.extend(["", "### 本章に効く確定意思決定", ""])
    if not decisions:
        lines.append("- (本章ゴールに効く確定 decision なし)")
    else:
        for dec in decisions:
            chosen_id = (dec.get("user_decision") or {}).get("option_id")
            chosen = next(
                (o for o in dec.get("options") or [] if o.get("id") == chosen_id), None
            )
            lines.append(f"- **{dec.get('id', '-')}**: {dec.get('question', '-')}")
            lines.append(
                f"  - 採択: {chosen.get('label') if chosen else chosen_id or '-'} "
                f"(`{chosen_id or '-'}`)"
            )
            if chosen and chosen.get("goal_fit"):
                lines.append(f"  - 目的適合: {chosen['goal_fit']}")
            if dec.get("qa_ref"):
                lines.append(f"  - 採択の接地根拠: `{dec['qa_ref']}`")
    return "\n".join(lines)


def render_chapter(spec: dict, cat_id: str, refs_by_cat: dict[str, list[dict]]) -> str:
    """1 カテゴリ章の完全な Markdown を組み立てる。

    節順は「状態 → 上流指針 → 確定内容 → 規範 (To-Be/Delta) → 参考 (設計知識) → 出典」。
    規範を参考資料より前に置くのは、章を上から読んだときに非規範の card を先に読ませて
    「採否: applied」を実装証拠と読み違えさせないため。
    """
    label = category_label(spec, cat_id)
    agg = category_aggregate(spec, cat_id)
    refs = refs_by_cat.get(cat_id, [])
    # 承認節は、対象外セルが承認 id を引いているときだけ置く。理由文で対象外にしたセルは
    # 状態表に理由の逐語が出ており空洞ではないので、そこへ空節を足しても情報が増えない。
    # 空洞になるのは状態表が「承認: <id>」としか言えないとき — すなわち approval_ref が
    # ある場合に限られる。
    appr_refs = _chapter_approval_refs(spec, cat_id)
    approvals = (
        [
            render_approvals(
                spec,
                appr_refs,
                heading="対象外の承認範囲",
                intro="本章の対象外セルが引用している承認の実体。状態表の「承認: <id>」だけでは、"
                "その承認が何をどこまで認めたものかを章から辿れない。",
            ),
            "",
        ]
        if appr_refs
        else []
    )
    parts = [
        render_frontmatter(spec, cat_id),
        "",
        f"# {label} ({cat_id})",
        "",
        f"- カテゴリ集約状態: **{agg}**",
        f"- 章確定マーカー: `status: {chapter_status(agg)}`",
        "",
        render_state_table(spec, cat_id),
        "",
        *approvals,
        render_doctrine_anchors(cat_id, spec),
        "",
        render_confirmed_content(spec, cat_id),
        "",
        render_to_be_delta(spec, cat_id),
        "",
        render_design_refs(cat_id, spec),
        "",
        render_citations(
            refs,
            empty_note="- (このカテゴリに割り当てた取得済みドキュメントなし。全体出典は index.md 参照)",
        ),
        "",
    ]
    return "\n".join(parts)


def _text_or_placeholder(s) -> str:
    if isinstance(s, dict) and s.get("status") == "not_applicable":
        return f"N/A — {s.get('reason') or '(理由未記入)'}"
    s = str(s or "").strip()
    return s if s else "(未記入)"


def _bullet_list(items) -> list[str]:
    if isinstance(items, dict) and items.get("status") == "not_applicable":
        return [f"- N/A — {items.get('reason') or '(理由未記入)'}"]
    items = items or []
    if not items:
        return ["- (未記入)"]
    return [f"- {x}" for x in items]


def _join_or_dash(items) -> str:
    items = items or []
    return ", ".join(str(x) for x in items) if items else "-"


def _list_value(value) -> list:
    """foundation の配列値を返す。明示N/A markerは空配列として扱う。"""
    return value if isinstance(value, list) else []


def render_decisions(spec: dict) -> str:
    """AI推奨とユーザー確認を分離した意思決定支援表を描画する。"""
    decisions = spec.get("decisions")
    lines = ["## 意思決定支援 (decisions)", ""]
    if not isinstance(decisions, list) or not decisions:
        lines.append("- (意思決定支援の記録なし)")
        return "\n".join(lines)
    lines += [
        "| ID | 論点 | 状態 | 選択肢 (費用・適合・注意点) | AI推奨 | ユーザー決定 | 資するゴール |",
        "|---|---|---|---|---|---|---|",
    ]
    for decision in decisions:
        options: list[str] = []
        for option in decision.get("options") or []:
            evidence = ", ".join(option.get("evidence_refs") or [])
            options.append(
                "{id}:{label} / cost={cost} / free={free} / fit={fit} / pros={pros} / "
                "cons={cons} / risks={risks} / lock-in={lock} / ops={ops} / evidence={evidence}".format(
                    id=option.get("id", "-"), label=option.get("label", "-"),
                    cost=option.get("cost_model", "-"), free=option.get("free_tier_limits", "-"),
                    fit=option.get("goal_fit", "-"), pros=", ".join(option.get("pros") or []),
                    cons=", ".join(option.get("cons") or []), risks=", ".join(option.get("risks") or []),
                    lock=option.get("lock_in", "-"), ops=option.get("ops_burden", "-"), evidence=evidence,
                )
            )
        rec = decision.get("recommendation") or {}
        rec_text = "-"
        if rec:
            rec_text = (
                f"{rec.get('option_id', '-')} — {rec.get('rationale', '-')} "
                f"(注意: {', '.join(rec.get('caveats') or [])}; confidence={rec.get('confidence', '-')}; "
                f"checked={rec.get('latest_checked_at', '-')})"
            )
        user = decision.get("user_decision") or {}
        user_text = (
            f"{user.get('option_id')} @ {user.get('confirmed_at')}"
            if isinstance(user, dict) and user.get("option_id") else "確認待ち"
        )
        lines.append(
            f"| {decision.get('id', '-')} | {decision.get('question', '-')} | "
            f"{decision.get('status', '-')} | {'<br>'.join(options)} | {rec_text} | {user_text} | "
            f"{', '.join(decision.get('serves_goals') or []) or '-'} |"
        )
    return "\n".join(lines)


def render_requirements_definition(spec: dict) -> str:
    """要件定義書 (上位概念 U1-U9) を先頭章として組み立てる (要件 C9・憲法)。

    requirements_foundation を正本とし、不在/空でも空落ちさせず (未記入) を明示した draft を出す。
    以降の各技術章はこの章の goals へ frontmatter serves_goals でトレース (anchor) する。
    """
    rf = requirements_foundation(spec)
    status = foundation_status(spec)
    parts = [
        "---",
        f"status: {status}",
        "category: requirements-definition",
        "---",
        "",
        "# 要件定義書 (上位概念)",
        "",
        "> 本章は spec-state.json の requirements_foundation を正本とする、システム構築の憲法。",
        "> 以降の各技術章は frontmatter の serves_goals でここ (ゴール) へトレース (anchor) する。",
        "> 上位概念がブレなければ、仕様が整った後もブレない。",
        "",
        f"- 確定マーカー: `status: {status}`",
        "",
        "## U1 本質的目的 (essential_purpose)",
        "",
        _text_or_placeholder(rf.get("essential_purpose")),
        "",
        "## U2 背景 (background)",
        "",
        _text_or_placeholder(rf.get("background")),
        "",
        "## U3 ゴール (goals)",
        "",
    ]
    goals = _list_value(rf.get("goals"))
    if goals:
        parts += ["| ID | ゴール |", "|---|---|"]
        for g in goals:
            parts.append(f"| {g.get('id', '-')} | {g.get('text', '')} |")
    else:
        parts.append("- (未記入)")
    parts += ["", "## U4 目標 (objectives)", ""]
    objectives = _list_value(rf.get("objectives"))
    if objectives:
        parts += ["| ID | 目標 | 測定基準 |", "|---|---|---|"]
        for o in objectives:
            parts.append(f"| {o.get('id', '-')} | {o.get('text', '')} | {o.get('measure') or '-'} |")
    else:
        parts.append("- (未記入)")
    parts += ["", "## U5 成功基準 (success_criteria)", ""]
    parts += _bullet_list(rf.get("success_criteria"))
    parts += ["", "## U6 ステークホルダー (stakeholders)", ""]
    parts += _bullet_list(rf.get("stakeholders"))
    scope = rf.get("scope") or {}
    parts += ["", "## U7 スコープ (scope)", ""]
    if isinstance(scope, dict) and scope.get("status") == "not_applicable":
        parts.append(f"- N/A — {scope.get('reason') or '(理由未記入)'}")
    else:
        parts += [
            f"- **対象 (in)**: {_join_or_dash(scope.get('in'))}",
            f"- **対象外 (out)**: {_join_or_dash(scope.get('out'))}",
        ]
    parts += ["", "## U8 制約 (constraints)", ""]
    parts += _bullet_list(rf.get("constraints"))
    parts += ["", "## U9 具体的にやりたいこと (concrete_intents)", ""]
    intents = _list_value(rf.get("concrete_intents"))
    if intents:
        parts += ["| ID | やりたいこと | 資するゴール |", "|---|---|---|"]
        for it in intents:
            serves = ", ".join(it.get("serves") or []) or "-"
            parts.append(f"| {it.get('id', '-')} | {it.get('text', '')} | {serves} |")
    else:
        parts.append("- (未記入)")
    # 憲法の確定根拠。status: confirmed という 1 語だけでは、誰がどの範囲を見た上で
    # 確定させたのかを章から辿れず、確定マーカーが自己申告になる。
    parts += [
        "",
        render_approvals(
            spec,
            [rf["approval_ref"]] if isinstance(rf.get("approval_ref"), str) and rf.get("approval_ref") else [],
            heading="確定の接地根拠 (承認)",
            intro="上の `status` を確定たらしめている利用者承認の実体。"
            "承認範囲がここに現れない項目は、本章の確定内容ではない。",
        ),
        "",
        render_decisions(spec),
        "",
    ]
    return "\n".join(parts)


def render_index(spec: dict, refs_by_cat: dict[str, list[dict]], unassigned: list[dict]) -> str:
    """全章 + カテゴリ集約状態を相互参照する index.md を組み立てる (R3-crosslink)。"""
    cat_ids = _category_ids(spec)
    rf = requirements_foundation(spec)
    lines = [
        "---",
        "kind: index",
        "---",
        "",
        "# システム構築仕様書 index",
        "",
        "収集マトリクス (カテゴリ×プラットフォーム) の各章と集約状態の相互参照。",
        "集約状態は 未着手 / 収集中 / 確定 / 対象外 の 4 値 (真理値表導出)。",
        "",
        "## 要件定義書 (上位概念・憲法)",
        "",
        f"- [要件定義書](./{REQUIREMENTS_CHAPTER}) — 上位概念 U1-U9 の正本 "
        f"(確定マーカー: `{foundation_status(spec)}`)。各技術章は serves_goals でここのゴールへ"
        "トレース (anchor) する。",
    ]
    ep = str(rf.get("essential_purpose") or "").strip()
    if ep:
        lines.append(f"- **本質的目的 (U1)**: {ep}")
    goals = rf.get("goals") or []
    if goals:
        gl = ", ".join(
            f"{g.get('id')}={g.get('text')}" for g in goals if isinstance(g, dict)
        )
        lines.append(f"- **ゴール (U3)**: {gl}")
    lines += [
        "",
        "## 章一覧と集約状態",
        "",
        "| カテゴリ | 章 | 集約状態 | 確定マーカー | 資するゴール | 対応セル |",
        "|---|---|---|---|---|---|",
    ]
    for cat_id in cat_ids:
        agg = category_aggregate(spec, cat_id)
        status = chapter_status(agg)
        label = category_label(spec, cat_id)
        cells = " ".join(spec_cell_ids(spec, cat_id))
        serves = " ".join(chapter_serves_goals(spec, cat_id)) or "—"
        lines.append(
            f"| {label} ({cat_id}) | [{cat_id}.md](./{cat_id}.md) | {agg} | `{status}` | {serves} | {cells} |"
        )
    lines.extend(["", "## 集約状態サマリ", ""])
    summary: dict[str, list[str]] = {"未着手": [], "収集中": [], "確定": [], "対象外": []}
    for cat_id in cat_ids:
        summary.setdefault(category_aggregate(spec, cat_id), []).append(cat_id)
    for label in ("未着手", "収集中", "確定", "対象外"):
        members = ", ".join(summary.get(label, [])) or "—"
        lines.append(f"- **{label}**: {members}")

    lines.extend(["", "## 全体ドキュメント出典 (未割当参照)", ""])
    if unassigned:
        lines.append(render_citations(unassigned, empty_note="").split("\n", 2)[2])
    else:
        lines.append("- (全ての取得済みドキュメントは各章へ割り当て済み)")
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- #
# コンパイル (組み立て) 本体                                                    #
# --------------------------------------------------------------------------- #
def compile_docset(spec: dict, refs_data: dict) -> dict[str, str]:
    """spec-state + fetched-references から {ファイル名: Markdown 本文} を組み立てる (純関数)。"""
    cat_ids = _category_ids(spec)
    refs_by_cat, unassigned = references_by_category(spec, refs_data)
    docset: dict[str, str] = {}
    # 要件定義書 (上位概念・憲法) を最初の章として生成 (要件 C9)
    docset[REQUIREMENTS_CHAPTER] = render_requirements_definition(spec)
    for cat_id in cat_ids:
        docset[f"{cat_id}.md"] = render_chapter(spec, cat_id, refs_by_cat)
    docset["index.md"] = render_index(spec, refs_by_cat, unassigned)
    return docset


def _split_preamble(text: str) -> tuple[str, list[tuple[str, str]]]:
    """本文を (前置き, [(## 見出し, 節本文), ...]) へ分ける。

    前置きは frontmatter + H1 + 集約サマリ (最初の ## より前) を指す。節は出現順を保つ。
    _markdown_sections が dict を返すのに対し、本関数は**順序**を保つため list を返す。
    章の構成 (節の並び) は既存章が権威、節の内容は compile が権威、という分離のため。
    """
    matches = list(re.finditer(r"^##\s+(.+?)\s*$", text, re.M))
    if not matches:
        return text, []
    preamble = text[: matches[0].start()]
    sections: list[tuple[str, str]] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections.append((match.group(1).strip(), text[match.end() : end].strip("\n")))
    return preamble, sections


def _split_blocks(body: str) -> list[tuple[str, str]]:
    """節本文を [(### 見出し行, ブロック本文)] へ分ける。### が無ければ空リスト。"""
    matches = list(re.finditer(r"^###\s+.+?\s*$", body, re.M))
    if not matches:
        return []
    blocks: list[tuple[str, str]] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        blocks.append((match.group(0).strip(), body[match.start() : end].strip("\n")))
    return blocks


def _card_source_file(block: str) -> str | None:
    """### ブロックが名指す出典カードのファイル名を返す (無ければ None)。

    見出しは版によって変わる (例: 「Information Design (画面情報設計)」→「(表現物の情報設計)」)
    が、出典カードのファイル名は変わらない。見出しではなくファイル名を同一性の鍵にすると、
    改題は更新として通し、参照先ごと消えたカードは消失として検出できる。
    """
    match = re.search(r"出典カード: `[^`]*?/([\w.-]+\.md)`", block)
    return match.group(1) if match else None


def _preserved_blocks(
    new_blocks: list[tuple[str, str]], old_blocks: list[tuple[str, str]]
) -> list[tuple[str, str]]:
    """既存ブロックのうち、再生成後も章へ残すべきものを選ぶ。

    new_blocks / old_blocks はいずれも [(### 見出し行, ブロック本文)]。
    返した順に、再生成ブロックの後ろへ連結される。

    判定は 2 段:
      1. 出典カードのファイル名を持つブロックは、そのファイル名が再生成側にあれば
         「改題を伴う更新」とみなして捨てる (二重掲載を避ける)。無ければ参照先ごと
         消えたカードなので残す。
      2. ファイル名を持たないブロック (手で足された記述) は、見出しが再生成側に
         無ければ残す。章が膨らむ方の損害は読めば済むが、失う方は復元できない。
    """
    new_files = {f for f in (_card_source_file(b) for _, b in new_blocks) if f}
    new_headings = {h for h, _ in new_blocks}
    keep: list[tuple[str, str]] = []
    for heading, block in old_blocks:
        source = _card_source_file(block)
        if source is not None:
            if source not in new_files:
                keep.append((heading, block))
        elif heading not in new_headings:
            keep.append((heading, block))
    return keep


def _carry_subblocks(new_block: str, old_block: str) -> str:
    """同一カードの新旧ブロック間で、章固有の追記 (#### 小節) を引き継ぐ。

    ### カードブロックには、再生成される内容 (カード本文) と章に蓄積される内容
    (「本章での適用」= 確定要件・原則の採否・トレードオフ・資するゴール) が同居する。
    カード更新で前者を差し替えるとき、後者まで巻き添えで消さないための引き継ぎ。
    """
    heads = list(re.finditer(r"^####\s+.+?\s*$", old_block, re.M))
    if not heads:
        return new_block
    new_heads = {m.group(0).strip() for m in re.finditer(r"^####\s+.+?\s*$", new_block, re.M)}
    carried: list[str] = []
    for index, match in enumerate(heads):
        if match.group(0).strip() in new_heads:
            continue
        end = heads[index + 1].start() if index + 1 < len(heads) else len(old_block)
        # 小節の直前にある水平線 (`---`) は章の視覚的な区切りなので引き継ぎ範囲へ含める。
        start = match.start()
        before = re.search(r"(?:^|\n)(---\s*\n\s*)\Z", old_block[:start])
        if before:
            start = before.start(1)
        carried.append(old_block[start:end].strip("\n"))
    if not carried:
        return new_block
    return "\n\n".join([new_block.strip("\n")] + carried)


def _split_frontmatter(text: str) -> tuple[str, str]:
    """先頭 frontmatter を (frontmatter ブロック, 残り) へ分ける。無ければ ("", text)。"""
    match = re.match(r"\A---\n.*?\n---\n", text, re.S)
    if not match:
        return "", text
    return match.group(0), text[match.end() :]


def _carry_prose(new_body: str, old_body: str) -> str:
    """### を持たない管理節で、既存の手書き注記を再生成本文へ引き継ぐ。

    U4 目標・U5 成功基準・index の凡例のような節は表が compile の正本だが、その周りに
    運用上の但し書き (「目標値は根拠のない数値を確定しない」「確定の意味は文書承認を
    表さない」など) が手で足される。表の行 (`|`) と見出し (`#`) は再生成側を採り、
    それ以外の行のうち**再生成本文のどこにも現れない**ものだけを末尾へ残す。

    判定を段落でなく行にし、包含 (`in`) で見るのは次の 2 つを同時に満たすため:
      - 内容が拡張された行 (旧文 + 追記) は新本文に部分一致するので二重掲載しない
      - 箇条書き・引用の形をした手書き注記も、消える側なら拾える
    """
    # compile が箇条書きを自分で組み立てている節では、旧本文の箇条書きも compile の
    # 過去の出力である。それを「消える側だから拾う」と、SSOT から取り下げられた項目
    # (改訂前の制約・割当が付いて不要になった空表示など) が章に残り続け、現行 SSOT と
    # **矛盾する記述**になる。実際、要件定義書には改訂前の制約が、章には割当済み後も
    # 「割り当てた取得済みドキュメントなし」が残っていた。
    # そこで、再生成側が箇条書き/表を持つ節では箇条書き行を引き継がない。段落・引用と
    # いった散文の注記 (compile が生成しない形) だけを引き継ぎ対象にする。
    new_has_list = any(
        line.lstrip().startswith(("-", "*", "|")) for line in new_body.splitlines()
    )
    carried = []
    for line in old_body.splitlines():
        stripped = line.strip()
        if not stripped or stripped in new_body:
            continue
        if line.lstrip().startswith(("|", "#")):
            continue
        if new_has_list and line.lstrip().startswith(("-", "*")):
            continue
        carried.append(line.rstrip())
    if not carried:
        return new_body
    return "\n\n".join([new_body.strip("\n")] + carried)


def _merge_managed_section(new_body: str, old_body: str) -> str:
    """compile 管轄節の内部を ### ブロック単位で統合する。

    ### を持たない節 (収集状態表・出典表など) は再生成内容をそのまま採る。
    ### を持つ節 (適用された設計知識) は、再生成ブロックを本体としつつ、
    _preserved_blocks が選んだ既存ブロックを後ろへ残す。
    """
    new_blocks = _split_blocks(new_body)
    old_blocks = _split_blocks(old_body)
    if not old_blocks:
        return _carry_prose(new_body, old_body)
    # 再生成側にブロックが 1 つも無い場合 (カード割当が外れた等) は、既存ブロックを
    # 全て残す。割当漏れは resource-map 側で直すべき事象であり、章の内容を削って
    # 表面上の整合を取ってはならない。

    # 同一カードの新旧ブロック間で、章に蓄積された #### 小節 (本章での適用など) を
    # 新ブロックへ引き継ぐ。カード本文は compile が権威だが、その中に書き足された
    # 章固有の適用記録は章が権威であり、カード更新の巻き添えで消してはならない。
    old_by_file: dict[str, str] = {}
    for _, block in old_blocks:
        source = _card_source_file(block)
        if source and source not in old_by_file:
            old_by_file[source] = block
    body = new_body
    for _, block in new_blocks:
        source = _card_source_file(block)
        if not source or source not in old_by_file:
            continue
        carried = _carry_subblocks(block, old_by_file[source])
        if carried != block:
            body = body.replace(block, carried, 1)

    keep = _preserved_blocks(new_blocks, old_blocks)
    if not keep:
        return body
    return "\n\n".join([body.strip("\n")] + [b for _, b in keep])


def merge_preserving(new_text: str, old_text: str) -> str:
    """再生成本文 new_text へ、既存章 old_text の構成と契約外の節を保存して統合する。

    compile が担当する節 (spec-state / fetched-references から導出できる節) は new_text の
    内容で更新し、compile の出力範囲外の節 (章に蓄積された質疑録・意思決定・履歴など) は
    old_text から引き継ぐ。前置き (frontmatter + H1 + 集約サマリ) は new_text を採る。

    **並び順**: compile 管轄節どうしの相対順序は new_text (compile) が権威、章に蓄積された
    管轄外節は「直前に来る管轄節の後ろ」という old_text 上の位置関係を保つ。当初は old_text
    の並びを全面的に基準にしていたが、そうすると compile が節を1つ増やしただけで規範節
    (To-Be / Delta・確定内容) が非規範の参考資料節の後ろへ落ち、読み順が壊れる。保護したい
    のは「章に溜まった管轄外の記述が消えないこと」であって、管轄節の並びまで既存章に
    決めさせることではない。

    これは「compile は節の内容の権威だが、章に蓄積された記述の権威ではない」という切り分けの
    実装で、SKILL.md が謳う「確定済み章の確定状態は保全され、勝手な巻き戻しをしない」を満たす。
    """
    new_pre, new_secs = _split_preamble(new_text)
    old_pre, old_secs = _split_preamble(old_text)
    if not old_secs:
        return new_text
    old_by_heading = dict(old_secs)
    managed = {h for h, _ in new_secs}
    # 管轄外節を「old_text 上で直前に来た管轄節」へぶら下げる。先頭側の管轄外節は None キー。
    trailing: dict[str | None, list[tuple[str, str]]] = {}
    anchor: str | None = None
    for heading, body in old_secs:
        if heading in managed:
            anchor = heading
            continue
        trailing.setdefault(anchor, []).append((heading, body))

    merged: list[tuple[str, str]] = list(trailing.get(None, []))
    for heading, body in new_secs:
        old_body = old_by_heading.get(heading)
        merged.append(
            (heading, _merge_managed_section(body, old_body) if old_body is not None else body)
        )
        merged.extend(trailing.get(heading, []))
    # 前置き (frontmatter + H1 + 集約サマリ) にも手書きの注記が足される (index の
    # 「確定の意味は文書承認を表さない」など)。frontmatter は再生成側が正本なので
    # 分離し、その後ろだけを引き継ぎ対象にする。
    new_front, new_lead = _split_frontmatter(new_pre)
    _, old_lead = _split_frontmatter(old_pre)
    parts = [(new_front + _carry_prose(new_lead, old_lead)).rstrip("\n"), ""]
    for heading, body in merged:
        parts.extend([f"## {heading}", "", body.strip("\n"), ""])
    return "\n".join(parts).rstrip("\n") + "\n"


def _lost_headings(merged_text: str, old_text: str) -> list[str]:
    """マージ結果から消えた既存見出し (## 〜 #####) を列挙する (保存則の検査)。

    ### の改題 (見出しは変わるが同じ出典カードを指す) は消失に数えない。見出し文字列で
    判定すると版更新のたびに保存則が誤検出し、compile が永久に走らなくなるため、
    ### については出典カードのファイル名が結果に残っているかを同一性の基準にする。

    走査範囲を compile が出力する階層 (## / ###) ではなく人が書き足しうる階層
    (##### まで) に取るのは、カード内へ蓄積された「本章での適用」(#### / #####) の
    消失を実際に見逃したため。守る範囲は書き手側の粒度で決める。
    """
    def headings(text: str) -> list[str]:
        return [m.group(0).strip() for m in re.finditer(r"^#{2,5}\s+.+?\s*$", text, re.M)]

    present = set(headings(merged_text))
    present_labels = {lab for lab in map(_heading_label, present) if lab}
    old_block_by_heading = dict(_split_blocks(old_text))
    lost: list[str] = []
    for heading in headings(old_text):
        if heading in present:
            continue
        if heading.startswith("###"):
            source = _card_source_file(old_block_by_heading.get(heading, ""))
            if source and source in merged_text:
                continue
        label = _heading_label(heading)
        if label and label in present_labels:
            # 同じラベルの見出しが別の値で存在する = 節の削除ではなく差し替え。
            # 例: `#### 主たる接地根拠: qa-A` → `#### 主たる接地根拠: qa-B`。
            # 根拠付き R4-reopen で確定セルの第一根拠を差し替えた場合に必ず起きる。
            # これを消失として拒むと、正規経路で reopen した章を二度と再生成できない。
            continue
        lost.append(heading)
    return lost


def _heading_label(heading: str) -> str:
    """見出しの『ラベル:』部分を返す (コロンが無ければ空)。

    見出しが担う**役割**を表す部分。値だけが変わった見出しを、節そのものの
    消失と取り違えないために使う。
    """
    m = re.match(r"^(#{2,5}\s+[^:：]+[:：])", heading)
    return m.group(1).strip() if m else ""


def write_docset(docset: dict[str, str], out_dir: Path) -> list[Path]:
    """組み立てた docset を out_dir へ書き出す。書き出したパス一覧を返す。

    既存章がある場合は上書きせず merge_preserving で統合し、統合後に既存見出しが
    1 つでも消えていれば書き込まず CompileError で異常終了する (保存則 / fail-closed)。
    再生成が章の蓄積を黙って削る事故を、書き込みの手前で止めるのが目的。
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name, content in docset.items():
        p = out_dir / name
        text = content if content.endswith("\n") else content + "\n"
        if p.exists():
            old_text = p.read_text(encoding="utf-8")
            text = merge_preserving(text, old_text)
            lost = _lost_headings(text, old_text)
            if lost:
                raise CompileError(
                    f"再生成で既存章の見出しが失われる: {p.name}: {lost}. "
                    "compile は節の内容のみを更新する。消失を伴う再生成は書き込まない"
                )
        p.write_text(text, encoding="utf-8")
        written.append(p)
    return written


# --------------------------------------------------------------------------- #
# CLI                                                                          #
# --------------------------------------------------------------------------- #
def load_json(path_str: str) -> dict:
    return json.loads(Path(path_str).read_text(encoding="utf-8"))


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(
        description="spec-state.json + fetched-references.json → 章立て仕様書ドキュメントセット"
    )
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_compile = sub.add_parser("compile", help="章別 Markdown + index.md を組み立てる")
    p_compile.add_argument("--spec", required=True, help="spec-state.json のパス")
    p_compile.add_argument("--references", required=True, help="fetched-references.json のパス")
    p_compile.add_argument("--out-dir", default="system-spec", help="出力ディレクトリ (既定 system-spec)")
    args = ap.parse_args(argv)

    try:
        spec = load_json(args.spec)
        refs_data = load_json(args.references)
        docset = compile_docset(spec, refs_data)
        written = write_docset(docset, Path(args.out_dir))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"IO/JSON error: {exc}", file=sys.stderr)
        return 1
    except CompileError as exc:
        print(f"CompileError: {exc}", file=sys.stderr)
        return 1
    print(f"OK: {len(written)} ファイルを {args.out_dir}/ へ生成 " f"({', '.join(p.name for p in written)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
