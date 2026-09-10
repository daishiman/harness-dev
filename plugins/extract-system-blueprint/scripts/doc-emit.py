#!/usr/bin/env python3
# /// script
# name: doc-emit
# purpose: fact/inference/observation_gap 区別済み抽出結果を system-blueprint 正本 (章別 md +
#          blueprint.json + design-tokens.json + (screen 提供時のみ) 画面別 layout.json/番号付き
#          layout-overlay.svg + site coverage manifest + sink-status) へテキスト演算のみで emit し、
#          非visual章/lane/schema parity と --check-screens / --check-apply の共有決定論検査を提供する。
#          外部サービス (Notion 等) へは一切書き込まず、成果物はローカルで完結する。
# inputs:
#   - argv: --extraction JSON --out-dir DIR --request-ledger FILE
#           [--check-screens] [--check-apply RECOMMENDATIONS_JSON --blueprint BLUEPRINT_JSON]
# outputs:
#   - stdout: emit=生成パス一覧+draft_hash+upsert_key+sink-status path(JSON) / check=検査サマリ(JSON)
#   - stderr: schema parity | nonvisual chapter/lane | provenance | screenshot-layout violation
#   - exit: 0=OK / 1=schema or completeness violation / 2=usage
# contexts: [C, E]
# network: false
# write-scope: --out-dir 配下の PLAN 成果物ファイルのみ (対象 origin・外部サービスへは書き込まない)
# dependencies: []
# requires-python: ">=3.10"
# ///
"""system-blueprint の決定論ライター兼共有検査 entrypoint (stdlib 完結・network なし)。

責務は 2 module に分かれる。

emit 系 (既定モード):
  抽出結果 (C03 の静的 HTTP 観測 content/tech_signals fact・C04/C05/C13 の inference・C06 合成の
  design_tokens/essence/mermaid・C09/C12 の site_inventory を統合した 1 オブジェクト) を、
  章別 Markdown 6 章 (Mermaid 埋込)・blueprint.json 正本・design-tokens.json・(screen が
  提供された場合のみ) 画面別 layout.json/番号付き注釈 layout-overlay.svg・site coverage manifest・
  sink-status へ整形して書き出す。screenshot/computed layout は R1 browser-render(C15) 取得時に
  screens[] へ populate され、ブラウザ不在 (exit3) 時のみ observation_gap で screens[] は空になる
  (提供時のみ layout 系を emit)。テキスト系 (layout/
  verbatim) の PII/機微は emit 時に redact し redaction_applied へ記録する。draft_hash /
  upsert_key を同一 shape から導出し冪等再開を可能にする。外部公開 sink は持たない。

検査系 (--check-screens / --check-apply):
  emit 系と同じ決定論ロジックを独立 entrypoint として提供する。生成側 (C01 自己検証) と
  承認側 (C02 独立評価)、および C14 (run-blueprint-apply) が同一判定を消費し基準乖離を防ぐ。
  --check-screens は screenshot/layout/coverage/redaction/visual formation field gap と
  観測色の palette 孤児 0・site coverage の pending 無言欠落 (部分クロールの完全被覆偽装) を
  fail-closed 検査し、同時に非 visual 章の欠落・fact/inference lane 混同・根拠0 inference・
  observed_scope/receipt 不備を拒否する。emit 後は canonical schema validator を別 process で
  必ず実行し、shape drift を fail-closed にする。--check-apply は apply-recommendations を schema 適合 (全項目
  kind=inference・kind=fact 新規 0・evidence_refs の blueprint 実在 anchor 解決率 100%・
  分類 adopt|avoid|differentiate のみ) で fail-closed 検査する (network なし・blueprint 非書込)。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

NOTICE = (
    "> 【参考・学習目的限定】本ドキュメントは対象システムの公開表層を受動観測した事実と、"
    "根拠つき推測を明示区別した参考資料です。実在個人/組織の代弁・推薦ではなく、"
    "認可外アクセス・侵入・模倣を意図しません。自社開発の学習・設計参考にのみ用いてください。"
)
FOUR_MIB = 4 * 1024 * 1024

# blueprint を emit する章別ドキュメント (順序 = 目次順)。
CHAPTERS = (
    "00-overview.md",
    "01-frontend-facts.md",
    "02-backend-inference.md",
    "03-uiux-rationale.md",
    "04-nonfunctional-compliance.md",
    "05-site-coverage.md",
)
# extraction.mermaid の必須図種キー (完全性判定は C10=mermaid-validate.py の責務・C11 は埋込のみ)。
MERMAID_KEYS = (
    "system_overview",
    "fact_inference_layers",
    "screen_flow",
    "data_flow_sequence",
    "data_model",
)
ANCHOR_KEYS = ("anchor", "id", "screen_id", "element_id", "record_id", "ref")
APPLY_CATEGORIES = ("adopt", "avoid", "differentiate")
CONFIDENCE_LEVELS = ("high", "medium", "low")
VISUAL_FORMATION_CATEGORIES = (
    "identity",
    "geometry",
    "layout",
    "paint",
    "typography",
    "media",
    "effects",
    "pseudo_elements",
    "state",
    "motion",
    "responsive",
    "a11y",
    "tokens",
)
GAP_STATUSES = ("not_observed", "blocked")
NONVISUAL_REQUIRED_SECTIONS = (
    "content",
    "tech_stack",
    "nonfunctional_baseline",
    "feature_map",
    "user_journeys",
    "security_design",
    "delivery_topology",
    "cwv_field_sample",
    "compliance_surfaces",
    "site_inventory",
)
FACT_SECTIONS = (
    "content",
    "nonfunctional_baseline",
    "feature_map",
    "cwv_field_sample",
    "compliance_surfaces",
    "site_inventory",
)
INFERENCE_SECTION_FIELDS = {
    "security_design": (
        "auth_method", "session_mgmt", "csrf_xss", "csp_eval", "attack_surface",
        "adopt_avoid_practices",
    ),
    "delivery_topology": ("cdn_edge_origin", "rendering", "cache_tiers"),
    "essence": (
        "core_problem_jtbd", "target_audience", "value_proposition", "key_messages",
        "tone_voice", "positioning_differentiation",
    ),
}
PROMPT_CONTRACT_REQUIRED_SECTIONS = (
    "Observations",
    "Cross-lens conflicts",
    "Neutral synthesis",
    "Confidence and gaps",
)
RECEIPT_STATUSES = ("pending", "success", "failed")

# text redact-on-emit のパターン (画像側 redaction は C03 の DOM マスクが担う)。
_REDACT_PATTERNS = (
    ("email", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")),
    ("token", re.compile(r"\b(?:sk|pk|ghp|xox[baprs])[-_][A-Za-z0-9]{16,}\b")),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b")),
    ("number", re.compile(r"\b\d[\d -]{11,}\d\b")),
)


class UsageError(Exception):
    """argv/入力ファイル起因の usage エラー (exit 2)。"""


# --------------------------------------------------------------------------- #
# 共有ヘルパー
# --------------------------------------------------------------------------- #
def _canonical_json(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise UsageError(f"入力ファイルが存在しない: {path}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise UsageError(f"入力 JSON を読めない: {path}: {exc}") from exc


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_json(path: Path, obj) -> None:
    _write_text(path, json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def _redact_text(text: str) -> tuple[str, int]:
    """PII/認証情報/機微をマスクし (redacted, hit数) を返す。"""
    if not isinstance(text, str) or not text:
        return text if isinstance(text, str) else "", 0
    hits = 0
    out = text
    for label, pat in _REDACT_PATTERNS:
        out, n = pat.subn(f"[REDACTED:{label}]", out)
        hits += n
    return out, hits


def _slug(value: str) -> str:
    s = re.sub(r"[^A-Za-z0-9._-]+", "-", str(value)).strip("-")
    return s or "screen"


def _screen_status(screen: dict) -> str:
    return str(screen.get("observation_status") or "observed")


def _nodes(screen: dict) -> list[dict]:
    """visual_formation_tree を平坦化 (children を再帰展開)。"""
    tree = screen.get("visual_formation_tree")
    if tree is None:
        tree = screen.get("layout")
    out: list[dict] = []

    def walk(node):
        if isinstance(node, dict):
            out.append(node)
            for child in node.get("children") or []:
                walk(child)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(tree)
    return [n for n in out if isinstance(n, dict) and n.get("identity") or n.get("element_id")]


def _element_id(node: dict) -> str | None:
    ident = node.get("identity")
    if isinstance(ident, dict) and ident.get("element_id"):
        return str(ident["element_id"])
    if node.get("element_id"):
        return str(node["element_id"])
    return None


def _parent_id(node: dict) -> str | None:
    ident = node.get("identity")
    if isinstance(ident, dict) and ident.get("parent_id"):
        return str(ident["parent_id"])
    return str(node["parent_id"]) if node.get("parent_id") else None


def _bbox(node: dict):
    """[x, y, w, h] を返す (取得不能は None)。"""
    geo = node.get("geometry") if isinstance(node.get("geometry"), dict) else node
    box = geo.get("bounding_box_px") if isinstance(geo, dict) else None
    if isinstance(box, dict):
        vals = [box.get("x"), box.get("y"), box.get("width"), box.get("height")]
    elif isinstance(box, (list, tuple)) and len(box) == 4:
        vals = list(box)
    else:
        return None
    try:
        x, y, w, h = (float(v) for v in vals)
    except (TypeError, ValueError):
        return None
    return [x, y, w, h]


def _canonical_color(value) -> str | None:
    """色値を比較用の canonical token へ正規化する (未観測/非色は None)。"""
    if isinstance(value, dict):
        if value.get("observation_status") in ("not_observed", "blocked"):
            return None
        for key in ("canonical_hex8", "exact", "value", "color"):
            token = _canonical_color(value.get(key))
            if token:
                return token
        return None
    if not isinstance(value, str):
        return None
    s = value.strip().lower()
    if not s or s in ("transparent", "none", "currentcolor", "inherit", "initial", "unset"):
        return None
    m = re.fullmatch(r"#([0-9a-f]{3,8})", s)
    if m:
        h = m.group(1)
        if len(h) == 3:
            h = "".join(c * 2 for c in h) + "ff"
        elif len(h) == 4:
            h = "".join(c * 2 for c in h)
        elif len(h) == 6:
            h = h + "ff"
        elif len(h) == 8:
            pass
        else:
            return s
        return "#" + h
    m = re.fullmatch(r"rgba?\(([^)]+)\)", s)
    if m:
        parts = [p.strip() for p in m.group(1).replace("/", ",").split(",") if p.strip()]
        try:
            r, g, b = (int(round(float(p.rstrip("%")))) for p in parts[:3])
            a = parts[3] if len(parts) > 3 else "1"
            av = float(a.rstrip("%"))
            av = av / 100 if "%" in a else av
            alpha = max(0, min(255, int(round(av * 255))))
            return "#{:02x}{:02x}{:02x}{:02x}".format(r & 255, g & 255, b & 255, alpha)
        except (TypeError, ValueError):
            return s
    return s  # oklch/名前付き色などは表記そのまま (両辺同一正規化で孤児判定は成立)


def _observed_colors(node: dict) -> set[str]:
    """1 node の paint/typography から観測色 canonical token を集める。"""
    colors: set[str] = set()
    paint = node.get("paint") if isinstance(node.get("paint"), dict) else {}
    for key in (
        "foreground_color", "background_color", "caret_color", "accent_color",
        "text_decoration_color", "outline_color", "border_color",
    ):
        tok = _canonical_color(paint.get(key))
        if tok:
            colors.add(tok)
    border = paint.get("border_width_style_color")
    if isinstance(border, dict):
        tok = _canonical_color(border.get("color"))
        if tok:
            colors.add(tok)
    for shadow_key in ("box_shadow", "text_shadow"):
        sh = paint.get(shadow_key)
        for entry in sh if isinstance(sh, list) else [sh]:
            if isinstance(entry, dict):
                tok = _canonical_color(entry.get("color"))
                if tok:
                    colors.add(tok)
    typo = node.get("typography") if isinstance(node.get("typography"), dict) else {}
    tok = _canonical_color(typo.get("color"))
    if tok:
        colors.add(tok)
    return colors


def _palette_tokens(design_tokens: dict) -> set[str]:
    tokens: set[str] = set()
    for entry in (design_tokens or {}).get("palette") or []:
        if isinstance(entry, dict):
            tok = _canonical_color(entry.get("canonical_hex8")) or _canonical_color(entry.get("value"))
        else:
            tok = _canonical_color(entry)
        if tok:
            tokens.add(tok)
    for tv in (design_tokens or {}).get("theme_variants") or []:
        if isinstance(tv, dict):
            for entry in tv.get("palette") or tv.get("colors") or []:
                if isinstance(entry, dict):
                    tok = _canonical_color(entry.get("canonical_hex8")) or _canonical_color(entry.get("value"))
                else:
                    tok = _canonical_color(entry)
                if tok:
                    tokens.add(tok)
    return tokens


# --------------------------------------------------------------------------- #
# emit 系 — layout.json + 番号付き注釈 SVG overlay
# --------------------------------------------------------------------------- #
def _numbered_elements(screen: dict) -> list[dict]:
    """reading_order で安定ソートした注釈対象要素 (番号 1..N を割当)。"""
    elems = []
    for node in _nodes(screen):
        eid = _element_id(node)
        if not eid:
            continue
        ro = node.get("reading_order")
        if not isinstance(ro, (int, float)):
            ro = float("inf")
        elems.append((ro, eid, node))
    elems.sort(key=lambda t: (t[0], t[1]))
    numbered = []
    for idx, (_, eid, node) in enumerate(elems, start=1):
        numbered.append({
            "annotation_number": idx,
            "element_id": eid,
            "parent_id": _parent_id(node),
            "bounding_box_px": _bbox(node),
            "reading_order": node.get("reading_order"),
            "role": (node.get("identity") or {}).get("role") if isinstance(node.get("identity"), dict) else None,
        })
    return numbered


def _emit_layout_json(screen: dict, numbered: list[dict], out_dir: Path) -> tuple[str, int]:
    sid = _slug(screen.get("screen_id", "screen"))
    rel = f"layout/{sid}.layout.json"
    redactions = 0
    safe = []
    for item in numbered:
        role, r = _redact_text(item.get("role") or "")
        redactions += r
        safe.append({**item, "role": role or None})
    payload = {
        "screen_id": screen.get("screen_id"),
        "viewport": screen.get("viewport"),
        "coverage": screen.get("coverage"),
        "elements": safe,
        "notice": NOTICE,
    }
    _write_json(out_dir / rel, payload)
    return rel, redactions


def _emit_overlay_svg(screen: dict, numbered: list[dict], out_dir: Path) -> str:
    sid = _slug(screen.get("screen_id", "screen"))
    rel = f"overlays/{sid}.layout-overlay.svg"
    vp = screen.get("viewport") if isinstance(screen.get("viewport"), dict) else {}
    width = int(float(vp.get("width") or 1280))
    height = int(float(vp.get("height") or 720))
    for item in numbered:
        box = item.get("bounding_box_px")
        if box:
            height = max(height, int(box[1] + box[3]) + 8)
            width = max(width, int(box[0] + box[2]) + 8)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" '
        f'aria-label="numbered layout overlay for {_xml(str(screen.get("screen_id", "")))}">',
        f'  <title>layout-overlay: {_xml(str(screen.get("screen_id", "")))} (参考・学習目的限定)</title>',
        '  <rect x="0" y="0" width="100%" height="100%" fill="none" stroke="#8888" stroke-width="1"/>',
    ]
    for item in numbered:
        box = item.get("bounding_box_px")
        num = item["annotation_number"]
        if not box:
            continue
        x, y, w, h = (int(round(v)) for v in box)
        cx, cy = x + 12, y + 12
        parts.append(
            f'  <g data-element-id="{_xml(item["element_id"])}" data-annotation="{num}">'
        )
        parts.append(
            f'    <rect x="{x}" y="{y}" width="{max(w, 1)}" height="{max(h, 1)}" '
            f'fill="none" stroke="#d6336c" stroke-width="1.5"/>'
        )
        parts.append(f'    <circle cx="{cx}" cy="{cy}" r="10" fill="#d6336c"/>')
        parts.append(
            f'    <text x="{cx}" y="{cy + 4}" font-size="12" fill="#ffffff" '
            f'text-anchor="middle" font-family="sans-serif">{num}</text>'
        )
        parts.append('  </g>')
    parts.append('</svg>')
    _write_text(out_dir / rel, "\n".join(parts) + "\n")
    return rel


def _xml(text: str) -> str:
    return (
        str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    )


# --------------------------------------------------------------------------- #
# emit 系 — 章別 Markdown
# --------------------------------------------------------------------------- #
def _md_kv(title: str, obj) -> list[str]:
    lines = [f"### {title}", ""]
    if not obj:
        lines.append("_未観測または該当なし (observation_gap)_")
        lines.append("")
        return lines
    lines.append("```json")
    lines.append(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True))
    lines.append("```")
    lines.append("")
    return lines


def _mermaid_block(diagram: str | None) -> list[str]:
    if not diagram:
        return []
    return ["```mermaid", str(diagram).strip(), "```", ""]


def _render_chapters(extraction: dict) -> dict[str, str]:
    meta = extraction.get("metadata") or {}
    # 図種キー→Mermaid本文の写像。schema 正本は mermaid_refs (list of {id/slug, mermaid}) で、
    # top-level additionalProperties:false のため `mermaid` dict は schema 上持てない。よって
    # `mermaid` dict があればそれを使い、無ければ mermaid_refs の id (=図種キー) から dict を組んで埋め込む。
    mermaid = extraction.get("mermaid")
    if not isinstance(mermaid, dict) or not mermaid:
        mermaid = {}
        for ref in extraction.get("mermaid_refs") or []:
            if isinstance(ref, dict) and ref.get("mermaid"):
                key = ref.get("id") or str(ref.get("slug", "")).replace("-", "_")
                if key:
                    mermaid[str(key)] = ref["mermaid"]
    title = meta.get("target_name") or meta.get("canonical_url") or "system-blueprint"
    chapters: dict[str, str] = {}

    # 00 — overview + essence + ①全体構成図 ②事実↔推測レイヤ図
    lines = [f"# {title} — システムブループリント", "", NOTICE, ""]
    lines += ["## メタデータ", ""]
    lines += _md_kv("source", {
        "canonical_url": meta.get("canonical_url"),
        "observation_snapshot_id": meta.get("observation_snapshot_id"),
        "schema_version": meta.get("schema_version"),
        "document_brand": meta.get("document_brand"),
    })
    lines += ["## 本質・目的 (essence — inference)", ""]
    lines += _md_kv("essence", extraction.get("essence"))
    lines += ["## 全体構成図", ""] + _mermaid_block(mermaid.get("system_overview"))
    lines += ["## 事実↔推測 区別レイヤ図", ""] + _mermaid_block(mermaid.get("fact_inference_layers"))
    chapters["00-overview.md"] = "\n".join(lines).rstrip() + "\n"

    # 01 — frontend facts + ③画面遷移図
    lines = ["# フロント表層の事実 (fact)", "", NOTICE, ""]
    lines += ["## 画面一覧", "", "| screen_id | screenshot | annotated | overlay | status |", "|---|---|---|---|---|"]
    for sc in extraction.get("screens") or []:
        lines.append(
            "| {sid} | {ss} | {an} | {ov} | {st} |".format(
                sid=sc.get("screen_id"),
                ss=sc.get("screenshot_ref") or "-",
                an=sc.get("annotated_screenshot_ref") or "-",
                ov=sc.get("layout_overlay_ref") or "-",
                st=_screen_status(sc),
            )
        )
    lines.append("")
    lines += ["## verbatim コンテンツ (redact 済み)", ""]
    lines += _md_kv("content", _redact_obj(extraction.get("content"))[0])
    lines += ["## 機能マップ (feature_map — fact 集約)", ""]
    lines += _md_kv("feature_map", extraction.get("feature_map"))
    lines += ["## 画面遷移図", ""] + _mermaid_block(mermaid.get("screen_flow"))
    chapters["01-frontend-facts.md"] = "\n".join(lines).rstrip() + "\n"

    # 02 — backend inference + ④データフローシーケンス ⑤データモデル
    lines = ["# バックエンド/設計意図の推測 (inference)", "", NOTICE, ""]
    lines += _md_kv("inferred_services", extraction.get("inferred_services"))
    lines += _md_kv("tech_stack (signals=fact / identified=inference)", extraction.get("tech_stack"))
    lines += _md_kv("security_design (OWASP 観点・受動観測のみ)", extraction.get("security_design"))
    lines += _md_kv("delivery_topology", extraction.get("delivery_topology"))
    lines += _md_kv("data_model", extraction.get("data_model"))
    lines += ["## データフロー (シーケンス図)", ""] + _mermaid_block(mermaid.get("data_flow_sequence"))
    lines += ["## データモデル図", ""] + _mermaid_block(mermaid.get("data_model"))
    chapters["02-backend-inference.md"] = "\n".join(lines).rstrip() + "\n"

    # 03 — uiux + user_journeys + design tokens 参照
    lines = ["# UI/UX 設計意図の推測 (inference)", "", NOTICE, ""]
    lines += _md_kv("uiux_rationale", extraction.get("uiux_rationale"))
    lines += _md_kv("user_journeys", extraction.get("user_journeys"))
    lines += ["## デザイントークン", "",
              "合成 design-tokens.json (`design-tokens.json`) を参照。観測色の palette 孤児 0 を "
              "`doc-emit.py --check-screens` が検査する。", ""]
    lines += _md_kv("design_tokens (summary)", _design_tokens_summary(extraction.get("design_tokens")))
    chapters["03-uiux-rationale.md"] = "\n".join(lines).rstrip() + "\n"

    # 04 — nonfunctional + compliance
    lines = ["# 非機能・コンプライアンス表面", "", NOTICE, ""]
    lines += _md_kv("nonfunctional_baseline (fact・observed_scope 明示)", extraction.get("nonfunctional_baseline"))
    lines += _md_kv("cwv_field_sample (fact・単一訪問参考値)", extraction.get("cwv_field_sample"))
    lines += _md_kv("security_observations (fact)", extraction.get("security_observations"))
    lines += _md_kv("compliance_surfaces (fact)", extraction.get("compliance_surfaces"))
    chapters["04-nonfunctional-compliance.md"] = "\n".join(lines).rstrip() + "\n"

    # 05 — site coverage
    lines = ["# サイト全域被覆 (site coverage)", "", NOTICE, ""]
    lines += _md_kv("site_inventory", extraction.get("site_inventory"))
    lines += ["", "被覆台帳の正本は `site-coverage-manifest.json`。pending 無言欠落 "
              "(部分クロールの完全被覆偽装) は `--check-screens` が検出する。", ""]
    chapters["05-site-coverage.md"] = "\n".join(lines).rstrip() + "\n"
    return chapters


def _design_tokens_summary(dt: dict | None) -> dict:
    dt = dt or {}
    return {
        "palette_roles": sorted({e.get("role") for e in dt.get("palette") or [] if isinstance(e, dict) and e.get("role")}),
        "palette_count": len(dt.get("palette") or []),
        "type_scale": bool(dt.get("type_scale")),
        "spacing_scale": bool(dt.get("spacing_scale")),
        "radius_scale": bool(dt.get("radius_scale")),
        "shadow_elevation_scale": bool(dt.get("shadow_elevation_scale")),
        "breakpoints": bool(dt.get("breakpoints")),
        "z_layers": bool(dt.get("z_layers")),
        "theme_variants": [tv.get("theme") for tv in dt.get("theme_variants") or [] if isinstance(tv, dict)],
    }


def _redact_obj(obj):
    """dict/list/str を再帰 redact し (redacted, hit数) を返す。"""
    if isinstance(obj, str):
        return _redact_text(obj)
    if isinstance(obj, list):
        out, hits = [], 0
        for item in obj:
            r, h = _redact_obj(item)
            out.append(r)
            hits += h
        return out, hits
    if isinstance(obj, dict):
        out, hits = {}, 0
        for k, v in obj.items():
            r, h = _redact_obj(v)
            out[k] = r
            hits += h
        return out, hits
    return obj, 0


# --------------------------------------------------------------------------- #
# 非 visual blueprint 契約 — 章/lane/evidence/receipt の決定論検査
# --------------------------------------------------------------------------- #
def _is_explicit_gap(value) -> bool:
    return (
        isinstance(value, dict)
        and value.get("kind") == "observation_gap"
        and value.get("observation_status") in GAP_STATUSES
        and isinstance(value.get("reason"), str)
        and bool(value["reason"].strip())
    )


def _present_or_gap(value) -> bool:
    if _is_explicit_gap(value):
        return True
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (dict, list)):
        return bool(value)
    return value is not None


def _check_confidence_and_refs(record: dict, path: str) -> list[str]:
    violations: list[str] = []
    if record.get("kind") not in (None, "inference"):
        violations.append(f"{path}.kind={record.get('kind')!r} (inference lane 必須)")
    if record.get("lane") not in (None, "inference"):
        violations.append(f"{path}.lane={record.get('lane')!r} (inference 必須)")
    refs = record.get("evidence_refs")
    if not isinstance(refs, list) or not refs or not all(isinstance(x, str) and x.strip() for x in refs):
        violations.append(f"{path}.evidence_refs は非空 string 配列が必須")
        refs = []
    conf = record.get("confidence")
    if not isinstance(conf, dict) or conf.get("level") not in CONFIDENCE_LEVELS:
        violations.append(f"{path}.confidence.level は high|medium|low が必須")
    elif not isinstance(conf.get("rationale"), str) or not conf["rationale"].strip():
        violations.append(f"{path}.confidence.rationale が欠落")
    elif conf.get("level") == "high" and len(set(refs)) < 2:
        violations.append(f"{path} high confidence は直接根拠 evidence_refs が2件以上必要")
    return violations


def _check_fact_lane(value, path: str) -> list[str]:
    """fact 集約章へ inference marker が混入していないことを再帰検査する。"""
    violations: list[str] = []
    if isinstance(value, dict):
        if value.get("kind") == "inference" or value.get("lane") == "inference":
            violations.append(f"{path} に inference が混入 (fact lane 必須)")
        if value.get("kind") not in (None, "fact", "observation_gap", "inference"):
            violations.append(f"{path}.kind={value.get('kind')!r} が fact|observation_gap 以外")
        if value.get("lane") not in (None, "fact", "observation", "inference"):
            violations.append(f"{path}.lane={value.get('lane')!r} が fact|observation 以外")
        for key, child in value.items():
            violations.extend(_check_fact_lane(child, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            violations.extend(_check_fact_lane(child, f"{path}[{index}]"))
    return violations


def _check_prompt_contract(value) -> list[str]:
    violations: list[str] = []
    if not isinstance(value, dict) or not value:
        return ["metadata.prompt_contract が欠落/空 (prompt parity violation)"]
    contracts = [value] if "required_sections" in value else list(value.values())
    if not contracts:
        return ["metadata.prompt_contract に analyzer 契約が無い"]
    for index, contract in enumerate(contracts):
        path = f"metadata.prompt_contract[{index}]"
        if not isinstance(contract, dict):
            violations.append(f"{path} が object でない")
            continue
        if contract.get("names_must_appear_in_prompt") is not True:
            violations.append(f"{path}.names_must_appear_in_prompt が true でない")
        sections = contract.get("required_sections")
        if not isinstance(sections, list):
            violations.append(f"{path}.required_sections が配列でない")
        else:
            missing = [name for name in PROMPT_CONTRACT_REQUIRED_SECTIONS if name not in sections]
            if missing:
                violations.append(f"{path}.required_sections 欠落: {', '.join(missing)}")
            if not any(isinstance(name, str) and name.startswith("Lens — ") for name in sections):
                violations.append(f"{path}.required_sections に実名 Lens 見出しが無い")
        guards = contract.get("guard_rules")
        if not isinstance(guards, list) or not guards or not all(isinstance(x, str) and x.strip() for x in guards):
            violations.append(f"{path}.guard_rules は非空 string 配列が必須")
    return violations


def check_nonvisual_contract(blueprint: dict) -> list[str]:
    """非 visual 章を soft-render せず、欠落・lane 混同・根拠0を拒否する。"""
    violations: list[str] = []
    meta = blueprint.get("metadata")
    if not isinstance(meta, dict):
        return ["metadata が欠落/非object (chapter parity violation)"]

    brand = meta.get("document_brand")
    if not isinstance(brand, dict):
        violations.append("metadata.document_brand が欠落/非object")
    else:
        for key in ("theme_color_meta", "favicon_dominant_colors", "root_background", "color_scheme_support"):
            if key not in brand or not _present_or_gap(brand.get(key)):
                violations.append(f"metadata.document_brand.{key} が欠落/空 (明示 gap 可)")
    violations.extend(_check_prompt_contract(meta.get("prompt_contract")))

    for section in NONVISUAL_REQUIRED_SECTIONS:
        if section not in blueprint or not _present_or_gap(blueprint.get(section)):
            violations.append(f"{section} 章が欠落/空 (明示 observation_gap なし)")

    for section in FACT_SECTIONS:
        if section in blueprint:
            violations.extend(_check_fact_lane(blueprint[section], section))

    tech = blueprint.get("tech_stack")
    if isinstance(tech, dict):
        signals = tech.get("signals")
        if not isinstance(signals, dict) or not signals:
            violations.append("tech_stack.signals fact lane が欠落/空")
        else:
            violations.extend(_check_fact_lane(signals, "tech_stack.signals"))
        identified = tech.get("identified")
        if not isinstance(identified, list):
            violations.append("tech_stack.identified inference lane が配列でない")
        for index, item in enumerate(identified if isinstance(identified, list) else []):
            if not isinstance(item, dict):
                violations.append(f"tech_stack.identified[{index}] が object でない")
            else:
                violations.extend(_check_confidence_and_refs(item, f"tech_stack.identified[{index}]"))

    for section in ("user_journeys",):
        records = blueprint.get(section)
        if isinstance(records, list):
            for index, record in enumerate(records):
                if not isinstance(record, dict):
                    violations.append(f"{section}[{index}] が object でない")
                else:
                    violations.extend(_check_confidence_and_refs(record, f"{section}[{index}]"))

    for section, fields in INFERENCE_SECTION_FIELDS.items():
        value = blueprint.get(section)
        if not isinstance(value, dict):
            if section == "essence" or section in blueprint:
                violations.append(f"{section} inference 章が object でない")
            continue
        section_has_evidence = isinstance(value.get("evidence_refs"), list) or "confidence" in value
        if section_has_evidence:
            violations.extend(_check_confidence_and_refs(value, section))
        for field in fields:
            if field not in value or not _present_or_gap(value.get(field)):
                violations.append(f"{section}.{field} が欠落/空")
                continue
            field_value = value[field]
            if isinstance(field_value, dict) and (
                "evidence_refs" in field_value or "confidence" in field_value or field_value.get("kind") == "inference"
            ):
                violations.extend(_check_confidence_and_refs(field_value, f"{section}.{field}"))
            elif not section_has_evidence:
                violations.append(
                    f"{section}.{field} は evidence_refs+confidence 付き inference envelope、"
                    f"または {section} 章共通根拠が必須"
                )

    baseline = blueprint.get("nonfunctional_baseline")
    if isinstance(baseline, dict) and not _present_or_gap(baseline.get("observed_scope")):
        violations.append("nonfunctional_baseline.observed_scope が欠落/空")

    return violations


# --------------------------------------------------------------------------- #
# emit 系 — manifest / payload / sink
# --------------------------------------------------------------------------- #
def _coverage_manifest(extraction: dict) -> dict:
    si = extraction.get("site_inventory") or {}
    discovered = list(si.get("discovered_urls") or [])
    in_scope = list(si.get("in_scope") or [])
    excluded = [e for e in (si.get("excluded") or []) if isinstance(e, dict)]
    extracted = list(si.get("extracted") or [sc.get("source_url") for sc in extraction.get("screens") or [] if sc.get("source_url")])
    excluded_urls = {e.get("url") for e in excluded}
    extracted_set = set(extracted)
    pending = [u for u in discovered if u not in extracted_set and u not in excluded_urls]
    cov = si.get("coverage") or {}
    return {
        "crawl_mode": si.get("crawl_mode") or "single",
        "discovered": sorted(discovered),
        "extracted": sorted(extracted_set),
        "pending": sorted(pending),
        "excluded": sorted(excluded, key=lambda e: str(e.get("url"))),
        "counts": {
            "discovered": len(discovered),
            "extracted": len(extracted_set),
            "pending": len(pending),
            "excluded": len(excluded),
        },
        "declared_counts": {
            "discovered": cov.get("discovered"),
            "extracted": cov.get("extracted"),
            "pending": cov.get("pending"),
            "excluded": cov.get("excluded"),
        },
        "notice": NOTICE,
    }


def _upsert_key(meta: dict) -> str:
    basis = "\n".join([
        str(meta.get("canonical_url") or ""),
        str(meta.get("observation_snapshot_id") or ""),
        str(meta.get("schema_version") or ""),
    ])
    return _sha256_text(basis)


def _validate_emitted_blueprint(blueprint_path: Path) -> tuple[bool, str]:
    """canonical validator を別 process で実行し、schema drift を fail-closed にする。"""
    validator = Path(__file__).resolve().parents[1] / "schemas" / "validate-system-blueprint.py"
    if not validator.is_file():
        return False, f"schema validator が存在しない: {validator}"
    try:
        completed = subprocess.run(
            [sys.executable, str(validator), "--blueprint", str(blueprint_path)],
            capture_output=True,
            check=False,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return False, f"schema validator を実行できない: {exc}"
    detail = "\n".join(part.strip() for part in (completed.stderr, completed.stdout) if part.strip())
    return completed.returncode == 0, detail or f"validator exit={completed.returncode}"


def _resolve_ref(ref: str, out_dir: Path) -> Path:
    p = Path(ref)
    return p if p.is_absolute() else out_dir / p


# --------------------------------------------------------------------------- #
# 検査系 — --check-screens
# --------------------------------------------------------------------------- #
def _has_observed_payload(value) -> bool:
    """category envelope の状態/根拠以外に実観測値があるか。"""
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (bool, int, float)):
        return True
    if isinstance(value, list):
        return bool(value)
    if not isinstance(value, dict):
        return True
    envelope_keys = {
        "kind", "observation_status", "reason", "attempted_method", "budget_state",
        "provenance", "evidence_ref", "evidence_refs", "captured_at",
    }
    for key, item in value.items():
        if key in envelope_keys:
            continue
        if item is None or item == "" or item == [] or item == {}:
            continue
        return True
    return False


def _visual_node_entries(screen: dict) -> tuple[list[tuple[str, dict]], list[str]]:
    """visual formation node を入力順の安定 path 付きで列挙する。"""
    tree = screen.get("visual_formation_tree")
    if tree is None:
        tree = screen.get("layout")  # 旧 input alias は読取のみ後方互換。
    entries: list[tuple[str, dict]] = []
    malformed: list[str] = []

    def walk(value, path: str) -> None:
        if isinstance(value, list):
            for index, item in enumerate(value):
                walk(item, f"{path}[{index}]")
            return
        if not isinstance(value, dict):
            malformed.append(f"{path} が object でない")
            return
        entries.append((path, value))
        children = value.get("children")
        if children is None:
            return
        if not isinstance(children, list):
            malformed.append(f"{path}.children が array でない")
            return
        for index, child in enumerate(children):
            walk(child, f"{path}.children[{index}]")

    if tree is not None:
        walk(tree, "visual_formation_tree")
    return entries, malformed


def _check_visual_formation_categories(screen: dict, sid: str) -> list[str]:
    """13 category を observed value または理由付き gap の二択で検査する。"""
    violations: list[str] = []
    entries, malformed = _visual_node_entries(screen)
    violations.extend(f"[{sid}] {message} (visual formation 構造違反)" for message in malformed)
    for path, node in entries:
        eid = _element_id(node) or path
        for category in VISUAL_FORMATION_CATEGORIES:
            tag = f"[{sid}] element {eid} category={category}"
            if category not in node:
                violations.append(f"{tag} が無い (無言欠落)")
                continue
            value = node[category]
            if isinstance(value, dict) and (
                value.get("kind") == "observation_gap" or "observation_status" in value
            ):
                status = value.get("observation_status")
                if status in GAP_STATUSES:
                    reason = value.get("reason")
                    if not isinstance(reason, str) or not reason.strip():
                        violations.append(
                            f"{tag} は observation_status={status} だが reason が無い (無言欠落)"
                        )
                    if value.get("kind") not in (None, "observation_gap"):
                        violations.append(f"{tag} gap の kind が observation_gap でない")
                    continue
                if status != "observed":
                    violations.append(
                        f"{tag} observation_status={status!r} が observed|not_observed|blocked 以外"
                    )
                    continue
                if value.get("kind") == "observation_gap":
                    violations.append(f"{tag} kind=observation_gap だが observation_status=observed")
                    continue
            if not _has_observed_payload(value):
                violations.append(f"{tag} に observed 値も理由付き observation_gap も無い")
    return violations


def check_screens(extraction: dict, out_dir: Path) -> list[str]:
    v: list[str] = []
    screens = extraction.get("screens")
    if not isinstance(screens, list):
        screens = []
    # screens[] 空は browser-render(C15) がブラウザ不在 (exit3) だった場合の正常状態 (screenshot/computed layout は observation_gap)。
    # 取得された screen がある場合のみ実体・redaction・palette 完全性を検査する。
    key_screens = set(extraction.get("key_screens") or [])
    seen_key = set()

    for sc in screens:
        sid = sc.get("screen_id")
        if not sid:
            v.append("screen に screen_id が無い (provenance violation)")
            continue
        status = _screen_status(sc)
        if status in ("not_observed", "blocked"):
            if not sc.get("reason"):
                v.append(f"[{sid}] observation_status={status} だが reason が無い (無言欠落)")
            continue  # 未観測画面は layout 必須から除外 (明示 gap のため OK)

        # screenshot 実体存在
        for ref_key in ("screenshot_ref", "annotated_screenshot_ref"):
            ref = sc.get(ref_key)
            if not ref:
                v.append(f"[{sid}] {ref_key} が無い (screenshot completeness violation)")
                continue
            path = _resolve_ref(ref, out_dir)
            if not path.is_file():
                v.append(f"[{sid}] {ref_key} の実体がローカルに存在しない: {ref}")
            elif ref_key == "annotated_screenshot_ref" and path.stat().st_size > FOUR_MIB:
                v.append(f"[{sid}] annotated PNG が 4MiB を超過: {path.stat().st_size} bytes")
        if not sc.get("layout_overlay_ref"):
            v.append(f"[{sid}] layout_overlay_ref が無い (SVG overlay 欠落)")
        elif not _resolve_ref(sc["layout_overlay_ref"], out_dir).is_file():
            v.append(f"[{sid}] layout_overlay_ref の実体が存在しない: {sc['layout_overlay_ref']}")

        # 観測済み画面の layout 欠落 0
        nodes = _nodes(sc)
        v.extend(_check_visual_formation_categories(sc, str(sid)))
        if not nodes:
            v.append(f"[{sid}] 観測済み画面の visual_formation_tree/layout が空 (layout 欠落)")
            continue

        # 番号↔element_id 1:1・親子解決・座標範囲・reading_order
        ids = [_element_id(n) for n in nodes]
        present_ids = [i for i in ids if i]
        if len(present_ids) != len(nodes):
            v.append(f"[{sid}] element_id を持たない node がある (注釈 1:1 不成立)")
        if len(set(present_ids)) != len(present_ids):
            v.append(f"[{sid}] element_id が重複 (注釈 1:1 不成立)")
        id_set = set(present_ids)
        for n in nodes:
            eid = _element_id(n) or "?"
            pid = _parent_id(n)
            if pid and pid not in id_set:
                v.append(f"[{sid}] element {eid} の parent_id={pid} が同一画面に解決できない")
            box = _bbox(n)
            if box is None:
                if _visual_observed(n):
                    v.append(f"[{sid}] element {eid} の bounding_box_px が無い/不正 (座標範囲欠落)")
            elif any((c < 0 for c in box)) or box[2] <= 0 or box[3] <= 0:
                v.append(f"[{sid}] element {eid} の座標範囲が不正: {box}")
            if n.get("reading_order") is None and _visual_observed(n):
                v.append(f"[{sid}] element {eid} に reading_order が無い")
            resp = n.get("responsive")
            if isinstance(resp, dict) and resp.get("breakpoint_or_container_change") and not resp.get("diff_from_profile"):
                v.append(f"[{sid}] element {eid} は breakpoint 変化ありだが diff_from_profile が無い (viewport 差分欠落)")

        if sid in key_screens:
            seen_key.add(sid)

    # 鍵画面捕捉
    for ks in sorted(key_screens - seen_key):
        v.append(f"鍵画面 {ks} が観測捕捉されていない (key-screen gap → C9 FAIL)")

    # redaction_applied 記録
    ra = extraction.get("redaction_applied")
    if ra is None:
        v.append("redaction_applied が記録されていない (text redact-on-emit 未証跡)")

    # 観測色の palette 孤児 0
    palette = _palette_tokens(extraction.get("design_tokens") or {})
    observed: set[str] = set()
    for sc in screens:
        if _screen_status(sc) in ("not_observed", "blocked"):
            continue
        for n in _nodes(sc):
            observed |= _observed_colors(n)
    orphans = sorted(observed - palette)
    if orphans:
        v.append(
            "観測色が design-tokens.json の palette に不在 (palette 孤児 != 0): "
            + ", ".join(orphans[:20]) + (" ..." if len(orphans) > 20 else "")
        )

    # site coverage: pending 無言欠落 / 完全被覆偽装
    v.extend(_check_coverage(extraction))
    # 非 visual: 章欠落/lane/evidence/observed_scope/sink receipt を共有ゲートでも再検査。
    v.extend(check_nonvisual_contract(extraction))
    return v


def _visual_observed(node: dict) -> bool:
    """paint/geometry のどれかが実観測値を持つ node か (完全 gap node は座標/順序を要求しない)。"""
    for key in ("paint", "geometry", "typography", "layout"):
        val = node.get(key)
        if isinstance(val, dict) and val.get("observation_status") not in ("not_observed", "blocked"):
            if any(vv is not None for vv in val.values()):
                return True
    return False


def _check_coverage(extraction: dict) -> list[str]:
    v: list[str] = []
    si = extraction.get("site_inventory")
    if not isinstance(si, dict):
        return v  # site_inventory 非対象の抽出 (単一画面) は被覆検査を課さない
    cov = si.get("coverage") or {}
    discovered = list(si.get("discovered_urls") or [])
    excluded = [e for e in (si.get("excluded") or []) if isinstance(e, dict)]
    excluded_urls = {e.get("url") for e in excluded}
    for e in excluded:
        if not e.get("reason"):
            v.append(f"excluded URL に reason が無い: {e.get('url')} (fail-closed 分類違反)")
    extracted = set(si.get("extracted") or [sc.get("source_url") for sc in extraction.get("screens") or [] if sc.get("source_url")])
    pending_computed = [u for u in discovered if u not in extracted and u not in excluded_urls]

    disc, extr, pend, excl = (cov.get(k) for k in ("discovered", "extracted", "pending", "excluded"))
    if all(isinstance(x, int) for x in (disc, extr, pend, excl)):
        if disc != extr + pend + excl:
            v.append(f"coverage 算術不整合: discovered({disc}) != extracted({extr})+pending({pend})+excluded({excl})")
        if discovered and disc != len(discovered):
            v.append(f"coverage.discovered({disc}) と discovered_urls 実数({len(discovered)}) 不一致")
        if pend != len(pending_computed):
            v.append(
                f"pending 無言欠落: coverage.pending({pend}) と実 pending({len(pending_computed)}) 不一致"
                " (部分クロールの完全被覆偽装疑い)"
            )
    else:
        v.append("site_inventory.coverage に discovered/extracted/pending/excluded の整数が揃っていない")
    if pending_computed and cov.get("pending", 0) == 0:
        v.append("未取得 URL があるのに coverage.pending=0 と主張 (完全被覆偽装)")
    return v


# --------------------------------------------------------------------------- #
# 検査系 — --check-apply
# --------------------------------------------------------------------------- #
def _collect_anchors(blueprint) -> set[str]:
    anchors: set[str] = set()

    def walk(node):
        if isinstance(node, dict):
            for k, val in node.items():
                if k in ANCHOR_KEYS and isinstance(val, str) and val:
                    anchors.add(val)
                walk(val)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(blueprint)
    if isinstance(blueprint, dict):
        anchors |= {str(x) for x in blueprint.get("anchors") or [] if isinstance(x, (str, int))}
        anchors |= {k for k in blueprint.keys()}  # top-level section anchors
    return anchors


def _recommendations(data) -> list:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("recommendations", "items", "apply_recommendations"):
            if isinstance(data.get(key), list):
                return data[key]
    return []


def check_apply(recommendations_data, blueprint) -> list[str]:
    v: list[str] = []
    recs = _recommendations(recommendations_data)
    if not recs:
        v.append("apply-recommendations が空 (schema violation)")
    anchors = _collect_anchors(blueprint)
    total_refs = 0
    resolved_refs = 0
    for idx, rec in enumerate(recs):
        tag = f"rec[{idx}]"
        if not isinstance(rec, dict):
            v.append(f"{tag} が object でない (schema violation)")
            continue
        if rec.get("kind") != "inference":
            v.append(f"{tag} kind={rec.get('kind')} (全項目 kind=inference 必須・kind=fact 新規禁止)")
        cat = rec.get("category")
        if cat not in APPLY_CATEGORIES:
            v.append(f"{tag} category={cat} が adopt|avoid|differentiate 以外")
        if not rec.get("claim"):
            v.append(f"{tag} claim が無い")
        if not rec.get("own_context_ref"):
            v.append(f"{tag} own_context_ref が無い (自社コンテキスト接地欠落)")
        conf = rec.get("confidence")
        if not isinstance(conf, dict) or conf.get("level") not in CONFIDENCE_LEVELS:
            v.append(f"{tag} confidence.level が high|medium|low 以外")
        elif not conf.get("rationale"):
            v.append(f"{tag} confidence.rationale が無い")
        refs = rec.get("evidence_refs")
        if not isinstance(refs, list) or not refs:
            v.append(f"{tag} evidence_refs が空 (blueprint 実在 anchor 必須)")
            continue
        for ref in refs:
            total_refs += 1
            if isinstance(ref, str) and ref in anchors:
                resolved_refs += 1
            else:
                v.append(f"{tag} evidence_ref が blueprint 実在 anchor へ解決できない: {ref}")
    if total_refs and resolved_refs != total_refs:
        v.append(f"evidence_refs anchor 解決率 {resolved_refs}/{total_refs} != 100%")
    return v


# --------------------------------------------------------------------------- #
# オーケストレーション
# --------------------------------------------------------------------------- #
def run_emit(args) -> int:
    out_dir = Path(args.out_dir)
    extraction = _load_json(Path(args.extraction))
    if not isinstance(extraction, dict):
        raise UsageError("--extraction のルートが object でない")
    meta = extraction.get("metadata") or {}
    for req in ("canonical_url", "observation_snapshot_id", "schema_version"):
        if not meta.get(req):
            sys.stderr.write(f"metadata.{req} が欠落 (schema violation)\n")
            return 1

    upsert_key = _upsert_key(meta)
    nonvisual_violations = check_nonvisual_contract(extraction)
    if nonvisual_violations:
        for msg in nonvisual_violations:
            sys.stderr.write(msg + "\n")
        sys.stdout.write(_canonical_json({
            "status": "fail",
            "stage": "nonvisual-preflight",
            "violations": nonvisual_violations,
        }) + "\n")
        return 1

    # request ledger を取り込み blueprint に接地する (network なし・値は入力そのまま)。
    ledger = _load_json(Path(args.request_ledger)) if args.request_ledger else None

    generated: list[str] = []
    redaction_hits = 0

    # 画面別 layout.json + 番号付き注釈 SVG overlay (C11 が overlay/layout の owner)。
    for sc in extraction.get("screens") or []:
        if _screen_status(sc) in ("not_observed", "blocked"):
            continue
        numbered = _numbered_elements(sc)
        rel_layout, r = _emit_layout_json(sc, numbered, out_dir)
        redaction_hits += r
        rel_svg = _emit_overlay_svg(sc, numbered, out_dir)
        sc["layout_overlay_ref"] = rel_svg  # 参照整合のため blueprint へ焼き戻す
        sc.setdefault("layout_ref", rel_layout)
        generated += [rel_layout, rel_svg]

    # 章別 Markdown (Mermaid 埋込)。
    chapters = _render_chapters(extraction)
    for name, text in chapters.items():
        _write_text(out_dir / name, text)
        generated.append(name)

    # design-tokens.json (C06 合成 palette を emit・観測色被覆は --check-screens が検査)。
    design_tokens = extraction.get("design_tokens") or {}
    _write_json(out_dir / "design-tokens.json", {**design_tokens, "notice": NOTICE})
    generated.append("design-tokens.json")

    # site coverage manifest。
    manifest = _coverage_manifest(extraction)
    _write_json(out_dir / "site-coverage-manifest.json", manifest)
    generated.append("site-coverage-manifest.json")

    # blueprint.json 正本は verbatim テキストを redact してから書く (正本自体が PII を持たない)。
    blueprint = dict(extraction)
    for field in ("content", "text_verbatim"):
        if extraction.get(field) is not None:
            redacted, hits = _redact_obj(extraction[field])
            blueprint[field] = redacted
            redaction_hits += hits

    # redaction 証跡を blueprint へ記録 (--check-screens が存在を検査)。
    redaction_applied = {"text_hits": redaction_hits, "emitter": "doc-emit.py", "targets": ["layout.json", "content_verbatim"]}
    extraction["redaction_applied"] = redaction_applied
    blueprint["redaction_applied"] = redaction_applied

    if ledger is not None:
        blueprint["request_ledger"] = ledger
    blueprint["notice"] = NOTICE
    blueprint_path = out_dir / "blueprint.json"
    _write_json(blueprint_path, blueprint)
    generated.append("blueprint.json")

    schema_valid, schema_detail = _validate_emitted_blueprint(blueprint_path)
    if not schema_valid:
        sys.stderr.write("emitted blueprint schema parity violation\n")
        if schema_detail:
            sys.stderr.write(schema_detail.rstrip() + "\n")
        sys.stdout.write(_canonical_json({
            "status": "fail",
            "stage": "schema-parity",
            "validator": "schemas/validate-system-blueprint.py",
        }) + "\n")
        return 1

    # draft_hash = 章別 md + blueprint + design-tokens + coverage の canonical 束縛。
    draft_basis = {
        "chapters": chapters,
        "blueprint": blueprint,
        "design_tokens": design_tokens,
        "coverage": manifest,
    }
    draft_hash = _sha256_text(_canonical_json(draft_basis))

    # sink-status (ローカル成果物のみ。外部公開 sink は持たない)。
    sink_status = {
        "upsert_key": upsert_key,
        "draft_hash": draft_hash,
        "sinks": {
            "local_draft": "success",
        },
    }
    sink_status_rel = "sink-status.json"
    _write_json(out_dir / sink_status_rel, sink_status)
    generated.append(sink_status_rel)

    # emit 時 completeness 検査 (--check-screens と同一ロジック)。
    violations = check_screens(extraction, out_dir)
    if violations:
        for msg in violations:
            sys.stderr.write(msg + "\n")
        sys.stdout.write(_canonical_json({"status": "fail", "stage": "emit-check", "violations": violations}) + "\n")
        return 1

    result = {
        "status": "ok",
        "out_dir": str(out_dir),
        "generated_paths": sorted(generated),
        "draft_hash": draft_hash,
        "upsert_key": upsert_key,
        "sink_status_path": str(out_dir / sink_status_rel),
        "redaction_applied": redaction_applied,
        "schema_validation": {
            "status": "pass",
            "validator": "schemas/validate-system-blueprint.py",
        },
    }
    sys.stdout.write(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return 0


def run_check_screens(args) -> int:
    extraction = _load_json(Path(args.extraction))
    if not isinstance(extraction, dict):
        raise UsageError("--extraction のルートが object でない")
    violations = check_screens(extraction, Path(args.out_dir))
    if violations:
        for msg in violations:
            sys.stderr.write(msg + "\n")
        sys.stdout.write(_canonical_json({"check": "screens", "status": "fail", "violations": violations}) + "\n")
        return 1
    sys.stdout.write(_canonical_json({"check": "screens", "status": "pass", "violations": []}) + "\n")
    return 0


def run_check_apply(args) -> int:
    if not args.blueprint:
        raise UsageError("--check-apply には --blueprint が必須")
    recs = _load_json(Path(args.check_apply))
    blueprint = _load_json(Path(args.blueprint))
    violations = check_apply(recs, blueprint)
    if violations:
        for msg in violations:
            sys.stderr.write(msg + "\n")
        sys.stdout.write(_canonical_json({"check": "apply", "status": "fail", "violations": violations}) + "\n")
        return 1
    sys.stdout.write(_canonical_json({"check": "apply", "status": "pass", "violations": []}) + "\n")
    return 0


def _parse_args(argv):
    ap = argparse.ArgumentParser(
        description="system-blueprint 決定論ライター兼共有検査 (emit / --check-screens / --check-apply)",
        add_help=True,
    )
    ap.add_argument("--extraction")
    ap.add_argument("--out-dir")
    ap.add_argument("--request-ledger")
    ap.add_argument("--check-screens", action="store_true")
    ap.add_argument("--check-apply")
    ap.add_argument("--blueprint")
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(list(sys.argv[1:] if argv is None else argv))
    try:
        if args.check_apply:
            return run_check_apply(args)
        if args.check_screens:
            if not args.extraction or not args.out_dir:
                raise UsageError("--check-screens には --extraction と --out-dir が必須")
            return run_check_screens(args)
        # emit モード
        missing = [
            flag for flag, val in (
                ("--extraction", args.extraction),
                ("--out-dir", args.out_dir),
                ("--request-ledger", args.request_ledger),
            ) if not val
        ]
        if missing:
            raise UsageError("emit モードに必須の引数が欠落: " + ", ".join(missing))
        return run_emit(args)
    except UsageError as exc:
        sys.stderr.write(str(exc) + "\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
