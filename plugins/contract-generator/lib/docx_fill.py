#!/usr/bin/env python3
# /// script
# name: docx_fill
# purpose: 黄色run差込・条項条件分岐・黄色二系統出力・ドリフト検知を行う差込エンジン(標準ライブラリのみ・docx_lib使用)。
# inputs:
#   - ひな形 .docx / template-mapping.json / row dict
# outputs:
#   - 黄色維持 .docx + 黄色除去 .docx / drift レポート
# contexts: [C]
# network: false
# write-scope: local-tmp
# dependencies: []
# requires-python: ">=3.11"
# ///
"""責務: select-and-fill のコア差込エンジン(標準ライブラリ docx_lib のみ・pip不要)。

設計方針(ひな形変更に強い二段構え):
  1. 差込位置は固定座標でなく anchor(安定テキスト) + placeholder(黄色run/プレースホルダ)で特定。
  2. 差込んだ値の run を黄色ハイライトで維持(AI記入の証跡) → Docs版。複製してハイライト除去 → PDF版。
  3. 差込後に未対応プレースホルダ(common.unfilled_markers)と未マップ黄色runを検知しドリフトとして報告。

注: read_file_content ではハイライトを取れないため、黄色判定は run.font.highlight_color で行う。
runtime 初回は scan_template.py でひな形の黄色run実体と template-mapping.json の差分を確認すること。
"""

import json
import logging
import os
import re

import docx_lib

_log = logging.getLogger(__name__)


def _find_mapping():
    """template-mapping.json(差込定義の正本)を探す。lib/ 移動後も解決できるよう候補探索。"""
    here = os.path.dirname(__file__)
    candidates = [
        os.environ.get("CONTRACT_TEMPLATE_MAPPING", ""),
        os.path.join(here, "..", "skills", "run-contract-generate", "references", "template-mapping.json"),
        os.path.join(here, "template-mapping.json"),
    ]
    for c in candidates:
        if c and os.path.isfile(c):
            return os.path.abspath(c)
    raise FileNotFoundError(
        "template-mapping.json が見つかりません(run-contract-generate/references/ を確認)"
    )


def load_mapping():
    with open(_find_mapping(), encoding="utf-8") as f:
        return json.load(f)


# ---------- セグメント方式の段落置換 ----------

def _iter_paragraphs(doc):
    yield from doc.paragraphs
    for t in doc.tables:
        for r in t.rows:
            for c in r.cells:
                yield from c.paragraphs


def _base_font(p):
    return p.runs[0].font if p.runs else None


def _render_segments(p, segments):
    """segments: list[(text, highlight_bool)]。段落を再構築し、highlight=True の run のみ黄色。"""
    base = _base_font(p)
    name = base.name if base else None
    p.clear_runs()
    for text, hl in segments:
        if text == "":
            continue
        run = p.add_run(text)
        if name:
            run.font.name = name
        if hl:
            run.font.highlight_color = docx_lib.YELLOW


def _apply_placeholder(segments, placeholder, value, highlight=True):
    """segments 内の placeholder を value に置換(value は highlight 指定)。

    既に黄色の bracket 選択肢内に placeholder がある場合も置換できるよう、
    before/after は元 segment の highlight を維持する。
    """
    out = []
    done = False
    for text, hl in segments:
        if done or placeholder not in text:
            out.append((text, hl))
            continue
        before, after = text.split(placeholder, 1)
        out.extend([(before, hl), (value, highlight), (after, hl)])
        done = True
    return out, done


# ---------- フォーマッタ ----------

def _fmt(value, fmt):
    v = (value or "").strip()
    if not v:
        return v
    if fmt == "currency_yen":
        n = re.sub(r"[^\d]", "", v)
        return f"金{int(n):,}円" if n else v
    if fmt in ("date_ja_from", "date_ja_to", "date_ja_full"):
        m = re.match(r"(\d{4})/(\d{1,2})/(\d{1,2})", v)
        if not m:
            return v
        y, mo, d = m.groups()
        ja = f"{y}年{int(mo)}月{int(d)}日"
        if fmt == "date_ja_from":
            return f"{ja}から"
        if fmt == "date_ja_to":
            return f"{ja}までの"
        return ja
    return v


def _placeholder_for_fmt(fmt, placeholder):
    return placeholder  # placeholder 自体が "金XXXX円" 等を含むため that を丸ごと置換


# ---------- 条項条件分岐 ----------

CONDITIONAL_VALUE_ALIASES = {
    "料金方式": {
        "固定報酬": "固定金額",
        "金額": "固定金額",
        "別紙２参照": "別紙2参照",
        "別紙２に定める金額": "別紙2参照",
        "別紙2に定める金額": "別紙2参照",
    },
    "業務内容方式": {
        "本文": "する",
        "本文に記載": "する",
        "別紙１に定める": "別紙1に定める",
        "し、その詳細は別紙１に定める": "別紙1に定める",
        "し、その詳細は別紙1に定める": "別紙1に定める",
    },
    "個人情報処分方法": {
        "別紙３に定める": "別紙3に定める",
        "甲が別途定める方法により": "別途定める",
    },
}

CONDITIONAL_ALLOWED_VALUES = {
    "成果物有無": {"あり", "なし"},
}


def normalize_conditional_value(column, value):
    v = (value or "").strip()
    return CONDITIONAL_VALUE_ALIASES.get(column, {}).get(v, v)


def _apply_conditionals(doc, type_map, row):
    removed = []
    for cond in type_map.get("conditionals", []):
        col = cond["column"]
        val = normalize_conditional_value(col, row.get(col, ""))
        if cond.get("when") != val:
            continue
        # 段落削除
        for anchor in cond.get("remove_paragraph_anchors", []):
            for p in list(_iter_paragraphs(doc)):
                if anchor in p.text:
                    p.delete()
                    removed.append(anchor)
        # ［A／B］選択(全角／半角ブラケット混在に対応)。anchor で段落を特定する。
        anchor = cond.get("anchor")
        if anchor:
            keep = cond.get("keep", "本文")
            for p in _iter_paragraphs(doc):
                if anchor in p.text and re.search(r"[［\[][^］\]]*[／/][^］\]]*[］\]]", p.text):
                    _select_bracket(p, keep)
                    break
    return removed


def _select_bracket(p, keep):
    """［A／B］ または [A／B](開き・閉じが全角/半角混在しても可)を keep に応じて選択。"""
    text = p.text
    m = re.search(r"[［\[]([^］\]]*)[］\]]", text)
    if not m:
        return
    options = re.split(r"／|/", m.group(1))
    chosen = (options[0] if keep == "本文" else options[-1]).strip()
    _render_segments(p, [(text[: m.start()], False), (chosen, True), (text[m.end():], False)])


# ---------- 署名欄(乙：ブロック) ----------

def _fill_signature(doc, type_map, row):
    cols = {f["column"] for f in type_map["fields"] if f.get("mode", "").startswith("append_signature")}
    if not cols:
        return
    name = row.get("乙氏名・名称") or row.get("乙法人名・名称") or ""
    addr = row.get("乙住所・連絡先") or row.get("乙本店所在地・連絡先") or ""
    rep = row.get("乙代表者役職・氏名") or ""
    for p in _iter_paragraphs(doc):
        if re.match(r"^\s*乙[：:]", p.text):
            lines = [addr]
            if rep:
                lines.append("")
            lines.append(name)
            if rep:
                lines.append(rep)
            _render_signature(p, "乙：", lines)
            return


def _render_signature(p, prefix, lines):
    base = _base_font(p)
    p.clear_runs()
    p.add_run(prefix)
    first = True
    for ln in lines:
        run = p.add_run()
        if not first:
            run.add_break()
        first = False
        if ln:
            r2 = p.add_run(ln)
            if base and base.name:
                r2.font.name = base.name
            r2.font.highlight_color = docx_lib.YELLOW


# ---------- メイン差込 ----------

def _strip_instruction_notes(doc, pattern):
    """ひな形の記入指示注記(例: 【…第3項を削除してください。】)を除去する。

    実ひな形(個人②)を python-docx で解析した結果、`【…】` 形式の指示文が黄色run として
    多数埋め込まれていることが判明(2026-05-29 裏取り)。これらは契約書本文に残してはならない。
    条件分岐(_apply_conditionals)の後・フィールド差込の前に実行する(差込済み黄色を壊さない)。
    """
    if not pattern:
        return []
    rx = re.compile(pattern)
    removed = []
    for p in _iter_paragraphs(doc):
        if rx.search(p.text):
            removed.extend(rx.findall(p.text))
            new_text = rx.sub("", p.text)
            _render_segments(p, [(new_text, False)])
    return removed


def _resolve_party_a_fixed_values(mapping):
    """mapping.common.fixed_values 内 {{party_a.X}} を lib.config_auth.load_party_a() で解決。

    WHY: template-mapping.json の {{party_a.*}} テンプレ変数は SSOT を 4 層 fallback で
    引く(env > ~/.config/contract-generator > ~/.config/tenant 後方互換 > 同梱 default)。
    解決責務がどこにも無いと差込時に文字列のまま流れ本番事故になる。
    fill 入口で解決し、未解決があれば ConfigError を即時 raise する(沈黙劣化防止)。
    返り値: {col_name: literal} 辞書(fields 経由ではなく detect_drift で未差込検知)。
    """
    fixed = (mapping.get("common", {}) or {}).get("fixed_values", {}) or {}
    if not fixed:
        return {}
    party_a = None
    resolved = {}
    for col, val in fixed.items():
        if isinstance(val, str) and val.startswith("{{party_a.") and val.endswith("}}"):
            if party_a is None:
                import config_auth  # 遅延 import: lib 同居
                party_a = config_auth.load_party_a()
            key = val[len("{{party_a."): -2]
            if key not in party_a:
                raise KeyError(f"party_a に {key} がありません(template-mapping.json {col})")
            resolved[col] = party_a[key]
        else:
            resolved[col] = val
    return resolved


_PARTY_A_TEMPLATE_RE = re.compile(r"\{\{party_a\.([a-zA-Z_][a-zA-Z0-9_]*)\}\}")


def _expand_party_a_template(text):
    """文字列内の `{{party_a.X}}` を lib.config_auth.load_party_a() で展開。

    WHY: template-mapping.json fields[] の value_template / default / placeholder 経由でも
    `{{party_a.*}}` が来る可能性があるため、_resolve_party_a_fixed_values の common.fixed_values
    解決と歩調を合わせて fields 側でも同経路で展開する(SSOT 一本化)。未解決キーは KeyError。
    """
    if not isinstance(text, str) or "{{party_a." not in text:
        return text
    import config_auth  # 遅延 import: lib 同居
    party_a = config_auth.load_party_a()

    def _sub(m):
        key = m.group(1)
        if key not in party_a:
            raise KeyError(f"party_a に {key} がありません(fields template)")
        return party_a[key]

    return _PARTY_A_TEMPLATE_RE.sub(_sub, text)


def fill_document(doc, type_map, row, mapping):
    """in-place 差込。returns drift report dict。"""
    # 0) 甲固定値 ({{party_a.*}}) を SSOT から解決し row に merge(row 側に同名キーがあれば row 優先)
    fixed = _resolve_party_a_fixed_values(mapping)
    if fixed:
        merged = dict(fixed)
        merged.update(row)
        row = merged
    # 1) 条項分岐(段落削除/[A/B]選択)を先に適用
    _apply_conditionals(doc, type_map, row)

    # 1.5) 記入指示注記【…】を除去(裏取りで判明した黄色指示文。本文に残さない)
    _strip_instruction_notes(doc, mapping.get("common", {}).get("instruction_note_pattern"))

    # 2) フィールド差込
    unmapped_placeholders = []
    fixed_cols = set((mapping.get("common", {}) or {}).get("fixed_values", {}) or {})
    template_blob = "\n".join(p.text for p in _iter_paragraphs(doc))
    for f in type_map.get("fields", []):
        mode = f.get("mode", "")
        if mode.startswith("append_signature"):
            continue  # 署名欄は後でまとめて処理
        col = f["column"]
        # 甲情報など common.fixed_values で解決される値は、ひな形側に
        # {{party_a.*}} placeholder がある場合だけ置換する。現在のtenantひな形のように
        # 甲情報が本文に固定記載済みの場合は drift 扱いしない。
        if col in fixed_cols and f.get("anchor_strategy") == "placeholder":
            ph = f.get("placeholder", "")
            if ph and ph not in template_blob:
                continue
        cond = f.get("condition")
        if cond and "==" in cond:
            c, cv = [s.strip() for s in cond.split("==", 1)]
            if (row.get(c, "") or "").strip() != cv:
                continue
        value = (row.get(col, "") or "").strip()
        if not value:
            if f.get("default"):
                value = f["default"]
            elif f.get("empty_action"):
                value = f["empty_action"]
            else:
                continue
        if f.get("format"):
            value = _fmt(value, f["format"])
        if f.get("value_template"):
            value = f["value_template"].format(v=value)
        # SSOT展開: fields[] 経路の {{party_a.*}} を解決(common.fixed_values と同じ責務を fields 側にも)
        value = _expand_party_a_template(value)
        anchor = f.get("anchor")
        placeholder = f.get("placeholder", "")
        placeholder_found = _apply_field(doc, anchor, placeholder, value, mode)
        if placeholder and placeholder != "$" and not placeholder_found:
            _log.warning("placeholder_not_found column=%s placeholder=%s anchor=%s", col, placeholder, anchor)
            unmapped_placeholders.append({"column": col, "placeholder": placeholder, "anchor": anchor})

    # 3) 署名欄
    _fill_signature(doc, type_map, row)

    # 4) ドリフト検知
    drift = detect_drift(doc, mapping)
    if unmapped_placeholders:
        drift["unmapped_placeholders"] = unmapped_placeholders
    return drift


def _apply_field(doc, anchor, placeholder, value, mode):
    """returns placeholder_found: bool。
    True = mode 完了 or placeholder 一致差込 完了 / False = どの段落でも placeholder 未一致。
    呼出元で unmapped_placeholders[] 集計に利用。"""
    anchor_re = re.compile(anchor) if anchor else None
    for p in _iter_paragraphs(doc):
        if anchor_re and not anchor_re.search(p.text):
            continue
        if mode == "fill_after_colon":
            # "銀行名：" の後ろに value(空欄補填)
            text = p.text
            m = re.match(r"^([^：:]*[：:])\s*(.*)$", text)
            if m:
                _render_segments(p, [(m.group(1), False), (value, True)])
            return True
        if mode == "date_signature":
            # 締結日 "２０XX年 月 日"(全角/半角スペース混在可)を value で置換
            text = p.text
            m = re.search(r"２０XX年[\s　]*月[\s　]*日", text)
            if m:
                _render_segments(p, [(text[: m.start()], False), (value, True), (text[m.end():], False)])
            return True
        if placeholder and placeholder != "$":
            segs = [(r.text, r.font.highlight_color == docx_lib.YELLOW) for r in p.runs]
            segs, done = _apply_placeholder(segs, placeholder, value, highlight=True)
            if not done and placeholder in p.text:
                segs, done = _apply_placeholder([(p.text, False)], placeholder, value, highlight=True)
            if done:
                _render_segments(p, segs)
                return True
    # anchor は見つかったが placeholder 未一致 → ドリフト候補(detect_drift で拾う)
    # anchor=None + anchor_strategy=placeholder の場合は全段落を placeholder 直走査
    if not anchor and placeholder and placeholder != "$":
        for p in _iter_paragraphs(doc):
            if placeholder in p.text:
                segs = [(r.text, r.font.highlight_color == docx_lib.YELLOW) for r in p.runs]
                segs, done = _apply_placeholder(segs, placeholder, value, highlight=True)
                if not done:
                    segs, done = _apply_placeholder([(p.text, False)], placeholder, value, highlight=True)
                if done:
                    _render_segments(p, segs)
                    return True
    return False


def detect_drift(doc, mapping):
    """未置換マーカー残存・黄色runの取りこぼしを検知。"""
    markers = mapping["common"]["unfilled_markers"]
    leftover = []
    yellow_unfilled = []
    full = "\n".join(p.text for p in _iter_paragraphs(doc))
    for mk in markers:
        if mk in full:
            leftover.append(mk)
    # 記入指示注記が残っていないか(除去漏れ検知)
    note_pat = mapping.get("common", {}).get("instruction_note_pattern")
    if note_pat and re.search(note_pat, full):
        leftover.append("【記入指示注記】")
    # 甲情報未挿入検知: markers と独立に {{party_a.*}} リテラル残存を全段落 blob スキャン
    # WHY: SSOT 解決失敗や ひな形側プレースホルダ表記ゆれで未差込のまま PDF 化される事故を阻止
    for m in _PARTY_A_TEMPLATE_RE.finditer(full):
        tok = m.group(0)
        if tok not in leftover:
            leftover.append(tok)
    for p in _iter_paragraphs(doc):
        for r in p.runs:
            if r.font.highlight_color == docx_lib.YELLOW:
                txt = r.text.strip()
                if any(mk in txt for mk in markers) or txt in ("", "●", "XXXX"):
                    yellow_unfilled.append(p.text[:40])
    return {"leftover_markers": sorted(set(leftover)), "yellow_unfilled": yellow_unfilled[:20]}


def strip_highlights(doc):
    """全 run のハイライトを除去(PDF=クリーン版用)。"""
    for p in _iter_paragraphs(doc):
        for r in p.runs:
            r.font.highlight_color = None


def fill_to_files(template_path, type_map, row, mapping, out_yellow, out_clean, post_fill=None):
    """ひな形 .docx を差込み、黄色維持版と黄色除去版を保存。

    post_fill: 差込後・保存前に doc(Document) を受け取り追記する任意コールバック(法人別紙生成など)。
    returns (drift, out_yellow, out_clean)。
    """
    doc = docx_lib.Document(template_path)
    drift = fill_document(doc, type_map, row, mapping)
    if post_fill:
        post_fill(doc)
    doc.save(out_yellow)
    clean = docx_lib.Document(out_yellow)
    strip_highlights(clean)
    clean.save(out_clean)
    return drift, out_yellow, out_clean
