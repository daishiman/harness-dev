#!/usr/bin/env python3
# /// script
# name: validate-prompt
# purpose: hearing/sheet/trace JSON のスキーマ必須項目、または生成プロンプトの7層マーカー・未展開placeholder・TODO残存を検証する
# inputs:
#   - argv: --input <file> [--phase hearing|sheet|trace|prompt] [--schema <path>]
#   - file: --input の JSON または prompt テキスト、解決された schema JSON
# outputs:
#   - stdout: OK サマリ
#   - stderr: FAIL 詳細（不足フィールド / 検証問題）
#   - exit: 0=OK / 1=検証失敗 / 2=引数・schema 不在
# contexts: [C]
# network: false
# write-scope: none
# dependencies: []
# ///
# validate-prompt.py — hearing JSON / trace JSON / generated prompt の最小検証 (Python 標準のみ)
"""validate_prompt.js の python 移植。元の検証ロジック・終了コードを維持する。"""
import argparse
import json
import os
import re
import sys

# 旧 plugin-level scripts/ から skills/run-prompt-creator-7layer/scripts/ へ移動したため、
# プラグインルートは 3 階層上 (scripts/ → run-prompt-creator-7layer/ → skills/ → root)。
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def parse_args():
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("--input")
    parser.add_argument("--phase")
    parser.add_argument("--schema")
    # A4-10: parse_known_args の黙殺を廃止 (failfast)。未知引数は argparse が exit 2。
    return parser.parse_args()


def load_json(p):
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def default_schema_for(phase):
    root = os.path.join(SCRIPT_DIR, "..", "..", "..")
    if phase == "hearing":
        return os.path.join(root, "skills", "run-prompt-elicit", "schemas", "hearing-result.schema.json")
    if phase == "sheet":
        return os.path.join(root, "skills", "run-prompt-creator-7layer", "schemas", "hearing-result.schema.json")
    if phase == "trace":
        return os.path.join(root, "skills", "run-prompt-create", "schemas", "build-trace.schema.json")
    return None


def check_required(obj, required, prefix):
    missing = []
    for k in required:
        v = obj.get(k) if isinstance(obj, dict) else None
        if v is None or v == "":
            missing.append(f"{prefix}.{k}")
    return missing


def detect_phase(input_path, explicit_phase):
    if explicit_phase:
        return explicit_phase
    ext = os.path.splitext(input_path)[1].lower()
    if ext == ".json":
        return "trace"
    return "prompt"


def validate_json_by_schema(input_path, phase, schema_path):
    data = load_json(input_path)
    sch = load_json(schema_path)
    target = data
    required = sch.get("required") or []

    if phase == "hearing":
        target = data.get("phase1") if isinstance(data, dict) and data.get("phase1") else data
        props = sch.get("properties") or {}
        phase1 = props.get("phase1") or {}
        required = phase1.get("required") or sch.get("required") or ["session_id", "timestamp", "answers"]

    missing = check_required(target, required, phase)
    if len(missing) > 0:
        sys.stderr.write("FAIL missing fields:\n")
        for m in missing:
            sys.stderr.write(f"  - {m}\n")
        sys.exit(1)
    print(f"OK phase={phase} schema={schema_path} required={len(required)} fields validated")


def validate_prompt_text(input_path):
    with open(input_path, "r", encoding="utf-8") as f:
        text = f.read()
    problems = []
    for n in range(1, 8):
        if re.search(rf"#+\s*Layer\s*{n}\s*[:：]", text) is None:
            problems.append(f"Layer {n}: marker missing")
    # 「出力指示」セクション以降は実行時入力プレースホルダー {{...}} を許可する
    # (seven-layer-markdown-template.md の「入力 placeholder は {{...}}」規定)。
    # それ以前の Layer 本文に残る {{...}} のみ未展開の骨格変数として検出する。
    layer_body = re.split(r"#+\s*出力指示", text, maxsplit=1)[0]
    if re.search(r"\{\{[^}]+\}\}", layer_body):
        problems.append("unexpanded placeholder remains")
    if re.search(r"TODO(?!\(human\))", text, re.IGNORECASE):
        problems.append("TODO remains without TODO(human)")
    if len(problems) > 0:
        sys.stderr.write("FAIL prompt validation:\n")
        for p in problems:
            sys.stderr.write(f"  - {p}\n")
        sys.exit(1)
    print(f"OK phase=prompt layers=7 file={input_path}")


def main():
    args = parse_args()
    input_path = args.input
    if not input_path:
        sys.stderr.write(
            "usage: validate-prompt.py --input <file> [--phase hearing|sheet|trace|prompt] [--schema <path>]\n"
        )
        sys.exit(2)
    resolved_phase = detect_phase(input_path, args.phase)
    if resolved_phase == "prompt":
        validate_prompt_text(input_path)
        return
    schema_path = args.schema or default_schema_for(resolved_phase)
    if not schema_path or not os.path.exists(schema_path):
        sys.stderr.write(
            f"schema not found for phase={resolved_phase}: {schema_path or '(none)'}\n"
        )
        sys.exit(2)
    validate_json_by_schema(input_path, resolved_phase, schema_path)


if __name__ == "__main__":
    main()
