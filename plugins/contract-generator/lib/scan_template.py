#!/usr/bin/env python3
# /// script
# name: scan_template
# purpose: ひな形 .docx の黄色run/プレースホルダ実体を抽出し template-mapping.json と差分照合(drift検知)。
# inputs:
#   - argv: --type --docx --config / Drive ひな形
# outputs:
#   - stdout: 黄色run一覧/MISSING/UNMAPPED / exit: 0=整合 5=drift
# contexts: [C, E]
# network: true
# write-scope: local-tmp
# dependencies: []
# requires-python: ">=3.11"
# ///
"""責務: ひな形変更の検知(drift detector・標準ライブラリのみ)。

Drive 上のひな形 .docx を取得し、黄色run/プレースホルダの実体を抽出して
template-mapping.json と突合する。ひな形が構造変更された際に「黙って壊れる」のを防ぎ、
未対応(UNMAPPED)/消失(MISSING)を報告して停止させる。

使い方:
  python3 scan_template.py --type individual            # Drive の最新ひな形を取得して診断
  python3 scan_template.py --type corporate --docx a.docx  # ローカル .docx を診断
exit: 0=整合 / 5=ドリフト検出
"""

import argparse
import os
import re
import sys

# 起動方法に依存せず同じ lib/ 内モジュールを import できるよう自身のディレクトリを先頭追加。
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import docx_fill  # noqa: E402
import docx_lib  # noqa: E402
import ledger  # noqa: E402


def _anchor_found(anchor, paras):
    if not anchor or anchor == "$":
        return True
    for text in paras:
        try:
            if re.search(anchor, text):
                return True
        except re.error:
            if anchor in text:
                return True
    return False


def _context_is_covered(context, type_map, mapping):
    """黄色run/marker の文脈が fields/conditionals の管理対象かを判定する。

    WHY: 黄色run は Word の run 分割に依存し、`XXXX` のような断片だけで見ると
    mapping 未対応に見える。文脈段落が field anchor / conditional anchor / 指示注記に
    covered されていれば「管理対象」とみなす。
    """
    note_pat = mapping.get("common", {}).get("instruction_note_pattern")
    if note_pat and re.search(note_pat, context):
        return True
    for f in type_map.get("fields", []):
        anchor = f.get("anchor")
        if anchor and anchor != "$" and _anchor_found(anchor, [context]):
            return True
        ph = f.get("placeholder")
        if ph and ph != "$" and ph in context:
            return True
        mode = f.get("mode", "")
        if mode.startswith("append_signature") and re.search(r"^\s*乙[：:]", context):
            return True
    for cond in type_map.get("conditionals", []):
        anchor = cond.get("anchor")
        if anchor and anchor in context:
            return True
        for anchor in cond.get("remove_paragraph_anchors", []):
            if anchor in context:
                return True
    return False


def _ledger_coverage(type_map):
    """mapping が要求する入力列が ledger.HEADERS に存在するかを検査する。"""
    title = type_map.get("sheet")
    headers = set(ledger.HEADERS.get(title, []))
    fixed = set()
    # 甲など common.fixed_values から解決される列は台帳入力列ではない。
    # 呼び出し側で mapping を渡さないため、ここでは固定値命名規約で判定する。
    fixed.update({"甲名称", "甲住所", "甲代表者", "甲代表者役職", "甲代表者氏名", "準拠法", "管轄"})
    needed = []
    for f in type_map.get("fields", []):
        col = f["column"]
        if col not in fixed:
            needed.append(col)
    for c in type_map.get("conditionals", []):
        needed.append(c["column"])
    missing = []
    seen = set()
    for col in needed:
        if col not in headers and col not in seen:
            seen.add(col)
            missing.append(col)
    return missing


def extract_yellow_runs(doc):
    out = []
    for p in docx_fill._iter_paragraphs(doc):
        for r in p.runs:
            if r.font.highlight_color == docx_lib.YELLOW:
                out.append({"text": r.text, "context": p.text[:50]})
    return out


def extract_markers(doc, markers):
    found = []
    for p in docx_fill._iter_paragraphs(doc):
        for mk in markers:
            if mk in p.text:
                found.append({"marker": mk, "context": p.text[:50]})
    return found


def diff_against_mapping(doc, type_map, mapping):
    """returns (missing_anchors, unmapped_markers, missing_ledger_columns)。"""
    paras = [p.text for p in docx_fill._iter_paragraphs(doc)]
    blob = "\n".join(paras)
    missing = []
    fixed_cols = set((mapping.get("common", {}).get("fixed_values") or {}).keys())
    for f in type_map.get("fields", []):
        if f["column"] in fixed_cols:
            continue
        anchor = f.get("anchor")
        # anchor_strategy=placeholder の場合は anchor=None。placeholder リテラルがひな形 blob に
        # 存在するかで MISSING 判定する(甲情報 {{party_a.*}} 等の placeholder ベース差込検証)。
        if not anchor:
            if f.get("anchor_strategy") == "placeholder":
                ph = f.get("placeholder", "")
                if ph and ph not in blob:
                    missing.append({"column": f["column"], "anchor": f"placeholder:{ph}"})
            continue
        if anchor in ("$",):
            continue
        if not _anchor_found(anchor, paras):
            missing.append({"column": f["column"], "anchor": anchor})
    # placeholder マーカーで mapping に無いもの
    markers = mapping["common"]["unfilled_markers"]
    mapped_ph = {f.get("placeholder", "") for f in type_map.get("fields", [])}
    unmapped = []
    for mk in extract_markers(doc, markers):
        # mapping のどの placeholder にも含まれないマーカー文脈 → 新規プレースホルダの疑い
        if any(mk["marker"] in ph for ph in mapped_ph if ph):
            continue
        if _context_is_covered(mk["context"], type_map, mapping):
            continue
        else:
            unmapped.append(mk)
    return missing, unmapped, _ledger_coverage(type_map)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--type", choices=["individual", "corporate"], required=True)
    p.add_argument("--docx", help="ローカル .docx を診断(指定なければ Drive から取得)")
    p.add_argument("--config")
    a = p.parse_args()

    mapping = docx_fill.load_mapping()
    type_map = mapping[a.type]

    if a.docx:
        path = a.docx
    else:
        import config_auth
        import render

        cfg = config_auth.load_config(a.config)
        token = config_auth.get_access_token(cfg)
        path = render.fetch_template(token, cfg["templates_folder_id"], type_map["template_name_pattern"])

    doc = docx_lib.Document(path)
    yellow = extract_yellow_runs(doc)
    missing, unmapped, missing_ledger = diff_against_mapping(doc, type_map, mapping)

    print(f"[scan] type={a.type} file={os.path.basename(path)}")
    print(f"  黄色run: {len(yellow)} 個")
    for y in yellow:
        print(f"    - '{y['text']}' @ {y['context']}")
    print(f"  MISSING anchor(ひな形側で見つからない差込位置): {len(missing)}")
    for m in missing:
        print(f"    - {m['column']} (anchor={m['anchor']})")
    print(f"  UNMAPPED marker(マッピング未対応のプレースホルダ疑い): {len(unmapped)}")
    for u in unmapped:
        print(f"    - '{u['marker']}' @ {u['context']}")
    print(f"  LEDGER missing column(mappingにあるが台帳ヘッダに無い列): {len(missing_ledger)}")
    for col in missing_ledger:
        print(f"    - {col}")

    if missing or unmapped or missing_ledger:
        print("\nDRIFT 検出: template-mapping.json または台帳列を更新してください。")
        return 5
    print("\nOK: ひな形と template-mapping.json は整合。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
