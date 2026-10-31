#!/usr/bin/env python3
# /// script
# name: validate-visual-selection
# version: 0.1.0
# purpose: 表現選定の被覆・参照・構成ハッシュを読み取り専用で検査する
# inputs: argv --config <json> [--decisions <json>] [--digest]
# outputs: 明示した出力先または検査結果の標準出力
# requires-python: ">=3.10"
# dependencies: []
# contexts: [C]
# network: false
# write-scope: none
# ///
"""図解選定の検討漏れ・参照切れ・古い構成への証跡を検出する。

--config <normalized.json> --decisions <visual-selection.json>
選定内容の最適性は意味レビューの責務。ここでは網羅と実際の配置を検査する。
標準ライブラリ限定、読取専用。0=検査通過 / 1=契約違反 / 2=読取不能。
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path


def config_digest(config):
    return hashlib.sha256(json.dumps(config, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def validate(config, receipt):
    errors = []
    if not isinstance(config, dict) or not isinstance(receipt, dict):
        return ["構成データと選定記録はJSONオブジェクトが要ります"]
    if receipt.get("config_sha256") != config_digest(config):
        errors.append("config_sha256: 選定記録が現在の構成データに結び付いていません")
    sections = {s["id"]: s for s in config.get("sections", []) if s.get("role", "main") == "main"}
    units = receipt.get("decision_log")
    if not isinstance(units, list):
        return errors + ["decision_log: C05の戻り値の配列が要ります"]
    coverage = {sid: set() for sid in sections}
    catalog = json.loads((Path(__file__).resolve().parent.parent / "config/handout-parts.json").read_text(encoding="utf-8"))
    types = {part["id"]: part.get("data_block_type") for part in catalog["parts"]}
    modes = {"diagram": {"diagram", "flow"}, "image": {"image"}, "text": {"text", "accordion", "prompt"}}
    for index, unit in enumerate(units):
        if not isinstance(unit, dict) or unit.get("kind") != "visual-selection":
            continue  # 既存の他の設計判断と共存する。
        where = "decision_log[%d]" % index
        sid = unit.get("section_id")
        if not isinstance(sid, str) or sid not in sections:
            errors.append(where + ": 本編に無いsection_idです")
            continue
        for key in ("source_excerpt", "reader_question", "relations", "chosen", "reason"):
            if not isinstance(unit.get(key), str) or not unit[key].strip():
                errors.append(where + "." + key + ": 空でない説明が要ります")
        candidates = unit.get("candidates")
        if not isinstance(candidates, list) or len(candidates) < 2 or any(
            not isinstance(c, dict) or any(not isinstance(c.get(k), str) or not c[k].strip()
                                           for k in ("form", "reason")) for c in candidates
        ):
            errors.append(where + ": 根拠つきの候補比較が2件以上要ります。短い文や表も候補にできます")
        facts = unit.get("preserved_facts")
        if not isinstance(facts, list) or not facts or any(not isinstance(f, str) or not f.strip() for f in facts):
            errors.append(where + ": preserved_factsへ保持した意味を列挙してください")
        if not isinstance(unit.get("replaced_content"), list) or any(not isinstance(x, str) for x in unit.get("replaced_content", [])):
            errors.append(where + ": replaced_contentへ図などが代替した説明を列挙してください（追加の場合は空配列）")
        parts = {p["id"]: types.get(p["part"]) for p in sections[sid].get("parts", [])}
        targets = unit.get("target_part_ids")
        if not isinstance(targets, list) or not targets or any(not isinstance(t, str) or t not in parts for t in targets):
            errors.append(where + ": target_part_idsが配置済み部品へ接続していません")
            continue
        mode = unit.get("mode")
        if not isinstance(mode, str) or mode not in ("diagram", "image", "part", "text"):
            errors.append(where + ": modeはdiagram/image/part/textが要ります")
        elif mode in modes and not any(parts[t] in modes[mode] for t in targets):
            errors.append(where + ": 採用した媒体と配置済み部品の種類が一致しません")
        elif mode == "part" and not any(parts[t] not in set().union(*modes.values()) for t in targets):
            errors.append(where + ": partはカード・表・手順などの構造部品を指してください")
        coverage[sid].update(targets)
    for sid, section in sections.items():
        # 先頭の場面画像だけで選定済みとしない。原文コピーは別目的なので除外。
        required = {p["id"] for p in section.get("parts", []) if types.get(p["part"]) not in ("image", "prompt")}
        if not coverage[sid] or required - coverage[sid]:
            errors.append(sid + ": 図解選定が未検討の本編・説明部品があります: " + ", ".join(sorted(required - coverage[sid])))
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--decisions")
    parser.add_argument("--digest", action="store_true", help="構成データへの結び付けに使うSHA256を表示する")
    args = parser.parse_args()
    try:
        with open(args.config, encoding="utf-8") as handle: config = json.load(handle)
        if args.digest:
            print(config_digest(config))
            return 0
        if not args.decisions:
            parser.error("--decisions は必須です (--digest を除く)")
        with open(args.decisions, encoding="utf-8") as handle: receipt = json.load(handle)
    except (OSError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 2
    errors = validate(config, receipt)
    print(json.dumps({"valid": not errors, "errors": errors}, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
