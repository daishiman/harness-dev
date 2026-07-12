#!/usr/bin/env python3
"""skill-intake SubAgent の 7-layer 準拠を機械検証する lint。

rubric: plugins/skill-intake/references/rubric.json
findings: findings.schema.json 準拠で stdout に JSON 出力。exit 1 if any error.

Layer 5 は l5-contract v2.0.0 (宣言型): `### 5.2 ゴール定義` + `### 5.3 実行方式` を必須とし、
固定手順見出し (推論手順/思考プロセス) を禁止する。完了チェックリストは本文末尾の
`## Self-Evaluation` セクション (checklist >= 5)。`{{var}}` は `## Prompt Templates`
節内のみ置換変数として許容し、節外は未展開プレースホルダとして error。

usage:
  python3 plugins/skill-intake/scripts/lint_subagent_seven_layer.py [paths...]
  (paths 省略時は plugins/skill-intake/agents/skill-intake-*.md 全件)
"""
from __future__ import annotations
import sys, re, json, glob, datetime, pathlib

REPO = pathlib.Path(__file__).resolve().parents[3]
RUBRIC = REPO / "plugins/skill-intake/references/rubric.json"

LAYER_HEADINGS = [
    "## Layer 1: 基本定義層",
    "## Layer 2: ドメイン層",
    "## Layer 3: インフラ層",
    "## Layer 4: 共通ポリシー層",
    "## Layer 5: エージェント層",
    "## Layer 6: オーケストレーション層",
    "## Layer 7: UI / 提示層",
]

FRONTMATTER_RE = re.compile(
    r"^---\nname:.*\ndescription:.*\ntools:.*\nmodel:.*\n---", re.MULTILINE
)
RID_RE = re.compile(r"responsibility_id\s*\|\s*(R[0-9]+-[a-z0-9-]+)")
SCHEMA_REF_RE = re.compile(r"(input_schema|output_schema)\s*\|\s*([^\s|]+\.schema\.json)")
TODO_BAD_RE = re.compile(r"\bTODO\b(?!\(human\))")
PLACEHOLDER_RE = re.compile(r"\{\{[^}]+\}\}")
GOALSEEK_L5_HEADINGS = ["### 5.2 ゴール定義", "### 5.3 実行方式"]
FIXED_STEPS_HEADING_RE = re.compile(r"^#{2,4} .*(推論手順|思考プロセス)", re.MULTILINE)
PROMPT_TEMPLATES_RE = re.compile(r"^## Prompt Templates", re.MULTILINE)


def _fence_spans(text: str) -> list[tuple[int, int]]:
    """fenced code block (```/~~~) の開始-終了スパンを列挙する。"""
    spans: list[tuple[int, int]] = []
    open_at = None
    for m in re.finditer(r"^(```|~~~).*$", text, re.MULTILINE):
        if open_at is None:
            open_at = m.start()
        else:
            spans.append((open_at, m.end()))
            open_at = None
    if open_at is not None:
        spans.append((open_at, len(text)))
    return spans


def emit_item(rule_id, severity, message, location=None, suggestion=None):
    item = {"rule_id": rule_id, "severity": severity, "message": message}
    if location:
        item["location"] = location
    if suggestion:
        item["suggestion"] = suggestion
    return item


def _normalize_target(path: pathlib.Path) -> pathlib.Path:
    if not path.is_absolute():
        repo_relative = REPO / path
        path = repo_relative if repo_relative.exists() else path.resolve()
    return path


def lint_file(path: pathlib.Path) -> list[dict]:
    path = _normalize_target(path)
    text = path.read_text(encoding="utf-8")
    items: list[dict] = []
    loc = str(path.relative_to(REPO))

    if not FRONTMATTER_RE.search(text):
        items.append(emit_item("SE-FM-required", "error",
            "frontmatter に name/description/tools/model のいずれかが欠落", loc))

    positions = []
    for h in LAYER_HEADINGS:
        idx = text.find(h)
        positions.append(idx)
    if any(p < 0 for p in positions) or positions != sorted(positions):
        missing = [LAYER_HEADINGS[i] for i, p in enumerate(positions) if p < 0]
        items.append(emit_item("SE-L1-L7-ordered", "error",
            f"Layer 1〜7 見出しが順序通り存在しない (missing={missing})", loc))

    sec_start = text.find("\n## Self-Evaluation")
    if sec_start < 0:
        items.append(emit_item("SE-L5-rubric-min5", "error",
            "Self-Evaluation セクション (goal-seek 完了チェックリスト) 欠落", loc))
    else:
        nxt = text.find("\n## ", sec_start + 1)
        body = text[sec_start: nxt if nxt > 0 else None]
        count = len(re.findall(r"^- \[ \]", body, re.MULTILINE))
        if count < 5:
            items.append(emit_item("SE-L5-rubric-min5", "error",
                f"Self-Evaluation checklist {count}/5 未満", loc))

    l5_start = text.find("## Layer 5")
    if l5_start >= 0:
        l6_start = text.find("## Layer 6", l5_start)
        l5_body = text[l5_start: l6_start if l6_start > 0 else None]
        for heading in GOALSEEK_L5_HEADINGS:
            if not re.search("^" + re.escape(heading), l5_body, re.MULTILINE):
                items.append(emit_item("SE-L5-goalseek", "error",
                    f"Layer 5 に `{heading}` 見出しがない (l5-contract v2.0.0: ゴール宣言+実行時の手順自律生成)", loc))
        m = FIXED_STEPS_HEADING_RE.search(l5_body)
        if m:
            line_no = text[:l5_start + m.start()].count("\n") + 1
            items.append(emit_item("SE-L5-goalseek", "error",
                "Layer 5 に固定手順見出し (推論手順/思考プロセス) が残置 (l5-contract v2.0.0 は宣言型)",
                f"{loc}:{line_no}"))

    if not RID_RE.search(text):
        items.append(emit_item("SE-meta-r-id", "error",
            "responsibility_id が R<n>-<slug> 形式でメタ表に存在しない", loc))

    for kind, ref in SCHEMA_REF_RE.findall(text):
        candidate = REPO / ref
        if not candidate.exists() and "(なし" not in ref and "未整備" not in ref:
            items.append(emit_item("SE-L2-io-schema", "error",
                f"{kind} で参照される schema が存在しない: {ref}", loc))

    for m in TODO_BAD_RE.finditer(text):
        line_no = text[:m.start()].count("\n") + 1
        items.append(emit_item("SE-no-todo", "error",
            "未対処の TODO が残置 (TODO(human) は許容)", f"{loc}:{line_no}"))
    # Prompt Templates 節内の {{var}} は置換変数 (定義済み用途) として許容する。
    # 節境界の `## ` はフェンス内 (テンプレ例示コード) の見出し風行を除外して判定する。
    fences = _fence_spans(text)
    pt_spans = []
    for pm in PROMPT_TEMPLATES_RE.finditer(text):
        end = len(text)
        search_from = pm.end()
        while True:
            cand = text.find("\n## ", search_from)
            if cand < 0:
                break
            if not any(s <= cand + 1 < e for s, e in fences):
                end = cand
                break
            search_from = cand + 1
        pt_spans.append((pm.start(), end))
    for m in PLACEHOLDER_RE.finditer(text):
        if any(s <= m.start() < e for s, e in pt_spans):
            continue
        line_no = text[:m.start()].count("\n") + 1
        items.append(emit_item("SE-no-todo", "error",
            f"未展開プレースホルダ {m.group(0)} が残置", f"{loc}:{line_no}"))

    return items


def main(argv: list[str]) -> int:
    if len(argv) > 1:
        targets = [pathlib.Path(p) for p in argv[1:]]
    else:
        targets = [pathlib.Path(p) for p in sorted(
            glob.glob(str(REPO / "plugins/skill-intake/agents/skill-intake-*.md")))]

    all_items: list[dict] = []
    per_file = {}
    for p in targets:
        p = _normalize_target(p)
        items = lint_file(p)
        per_file[str(p.relative_to(REPO))] = items
        all_items.extend(items)

    error_count = sum(1 for i in all_items if i["severity"] == "error")
    warn_count = sum(1 for i in all_items if i["severity"] == "warn")
    verdict = "fail" if error_count else ("warn" if warn_count else "pass")

    findings = {
        "produced_by": "lint_subagent_seven_layer.py",
        "target": {"kind": "subagent", "path": "plugins/skill-intake/agents/"},
        "verdict": verdict,
        "items": all_items,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "summary": {
            "files_checked": len(targets),
            "errors": error_count,
            "warns": warn_count,
            "per_file_counts": {k: len(v) for k, v in per_file.items()},
        },
    }
    json.dump(findings, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 1 if error_count else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
