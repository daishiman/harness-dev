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


def render_design_refs(cat_id: str, spec: dict | None = None) -> str:
    """設計知識をpathだけでなく、目的達成に使える意味項目まで章へ描画する。"""
    refs = category_design_refs(cat_id)
    lines = ["## 適用された設計知識", ""]
    if not refs:
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


def render_chapter(spec: dict, cat_id: str, refs_by_cat: dict[str, list[dict]]) -> str:
    """1 カテゴリ章の完全な Markdown を組み立てる (frontmatter + 状態表 + 設計知識 + 出典)。"""
    label = category_label(spec, cat_id)
    agg = category_aggregate(spec, cat_id)
    refs = refs_by_cat.get(cat_id, [])
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
    parts += ["", render_decisions(spec), ""]
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


def write_docset(docset: dict[str, str], out_dir: Path) -> list[Path]:
    """組み立てた docset を out_dir へ書き出す。書き出したパス一覧を返す。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name, content in docset.items():
        p = out_dir / name
        text = content if content.endswith("\n") else content + "\n"
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
