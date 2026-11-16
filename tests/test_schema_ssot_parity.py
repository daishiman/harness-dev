"""JSON schema が Python 正本から写した値の drift を機械検出するテスト。

harness-hxi の baseline 実走で、schema の写しが正本から外れて生成が止まる事故が 2 件出た:
- capability-manifest の feedback_contract が activation_state / derived_from を知らず、
  lint-entrypoint-artifact-first が必須とする欄を書くと schema 違反になった (Step 12.4 停止)。
- 3 つの schema の verify_by enum が feedback_contract_ssot.CRITERIA_VERIFY_BY の
  "verification-obligation" を欠き、正本どおりの SKILL.md が schema で落ちた。

schema は JSON なので正本を import できない。写しを残す代わりに、ここで正本と挙動で突き合わせる。
"""
from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

import jsonschema
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
RUN_BUILD = ROOT / "plugins" / "harness-creator" / "skills" / "run-build-skill"
CAPABILITY_MANIFEST_SCHEMA = RUN_BUILD / "references" / "capability-manifest.schema.json"
TRACE_SCHEMA = RUN_BUILD / "schemas" / "skill-build-trace.schema.json"
BUILD_FLAGS_SCHEMA = RUN_BUILD / "schemas" / "build-flags.schema.json"
CRITERIA_SCHEMAS = (CAPABILITY_MANIFEST_SCHEMA, TRACE_SCHEMA, BUILD_FLAGS_SCHEMA)
VALIDATE_BUILD_TRACE = RUN_BUILD / "scripts" / "validate-build-trace.py"
SSOT_COPIES = (
    ROOT / "scripts" / "feedback_contract_ssot.py",
    ROOT / "plugins" / "harness-creator" / "scripts" / "feedback_contract_ssot.py",
)
ENTRYPOINT_LINT = ROOT / "scripts" / "lint-entrypoint-artifact-first.py"
CRITERIA_PROVENANCE_LINT = (
    ROOT / "plugins" / "skill-governance-lint" / "scripts" / "lint-criteria-provenance.py"
)

# 既知の schema 違反。ここに載せた SKILL.md は「今も落ちる」ことも確かめる (直ったら削除を強制)。
KNOWN_FEEDBACK_CONTRACT_VIOLATIONS = {
    # max_iterations を置かない理由の散文。読む lint が無く、schema に欄を足すか本文へ移すかは
    # capability-manifest の残 schema 違反と一緒に follow-up で決める。
    "plugins/guide-doc-generator/skills/run-handout-build/SKILL.md": "iteration_note",
}


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def _criteria_item_schemas(node, path=""):
    """schema 中で criteria の 1 件を表す subschema (properties に verify_by を持つ) を全て返す。"""
    found = []
    if isinstance(node, dict):
        props = node.get("properties")
        if isinstance(props, dict) and "verify_by" in props:
            found.append((path, node))
        for key, value in node.items():
            found.extend(_criteria_item_schemas(value, f"{path}/{key}"))
    elif isinstance(node, list):
        for i, value in enumerate(node):
            found.extend(_criteria_item_schemas(value, f"{path}[{i}]"))
    return found


def _feedback_contract_validator():
    full = json.loads(CAPABILITY_MANIFEST_SCHEMA.read_text(encoding="utf-8"))
    # draft-07 では $ref の兄弟 keyword は無視されるので、root の definitions を残したまま
    # commonCore.feedback_contract だけを検証の入口にできる。
    wrapper = {
        "$schema": full["$schema"],
        "definitions": full["definitions"],
        "$ref": "#/definitions/commonCore/properties/feedback_contract",
    }
    return jsonschema.validators.validator_for(full)(wrapper)


def _skill_feedback_contracts():
    for skill_md in sorted(ROOT.glob("plugins/*/skills/*/SKILL.md")):
        match = re.match(r"---\n(.*?)\n---\n", skill_md.read_text(encoding="utf-8"), re.S)
        if not match:
            continue
        frontmatter = yaml.safe_load(match.group(1)) or {}
        contract = frontmatter.get("feedback_contract")
        if contract is not None:
            # YAML の date 等を JSON と同じ型へ寄せる (schema 検証は JSON 前提)
            yield skill_md.relative_to(ROOT).as_posix(), json.loads(json.dumps(contract, default=str))


def test_ssot_copies_agree():
    """vendored 2 部の criteria 定数が一致する (schema との比較の前提)。"""
    a, b = (_load(p, f"fc_ssot_{i}") for i, p in enumerate(SSOT_COPIES))
    assert a.CRITERIA_VERIFY_BY == b.CRITERIA_VERIFY_BY
    assert a.CRITERIA_ID_RE.pattern == b.CRITERIA_ID_RE.pattern
    assert a.LOOP_SCOPES == b.LOOP_SCOPES


@pytest.mark.parametrize("schema_path", CRITERIA_SCHEMAS, ids=lambda p: p.name)
def test_criteria_enums_match_ssot(schema_path: Path):
    fc = _load(SSOT_COPIES[0], "fc_ssot")
    items = _criteria_item_schemas(json.loads(schema_path.read_text(encoding="utf-8")))
    assert items, f"{schema_path.name}: criteria の subschema が見つからない (検査が空振りする)"
    for path, item in items:
        props = item["properties"]
        assert set(props["verify_by"]["enum"]) == fc.CRITERIA_VERIFY_BY, f"{schema_path.name}{path}"
        assert props["id"]["pattern"] == fc.CRITERIA_ID_RE.pattern, f"{schema_path.name}{path}"
        if "loop_scope" in props and "enum" in props["loop_scope"]:
            assert set(props["loop_scope"]["enum"]) == fc.LOOP_SCOPES, f"{schema_path.name}{path}"
        for key in fc.REQUIRED_CRITERION_KEYS:
            assert key in item.get("required", []), f"{schema_path.name}{path}: {key} が required に無い"


def test_activation_state_enum_is_what_the_lint_requires():
    """schema の activation_state enum は契約ごとのループ開始状態の集合と同じで、
    各契約は自分の状態だけを通し、他の契約の状態や選択前の状態では落ちる。"""
    schema = json.loads(CAPABILITY_MANIFEST_SCHEMA.read_text(encoding="utf-8"))
    enum = schema["definitions"]["commonCore"]["properties"]["feedback_contract"]["properties"][
        "activation_state"
    ]["enum"]
    lint = _load(ENTRYPOINT_LINT, "lint_entrypoint_artifact_first")
    assert set(enum) == set(lint.LOOP_ACTIVATION_STATES.values())

    def feedback_errors(activation, state):
        errors = lint._lint_frontmatter_control_flow(
            {"feedback_contract": {"max_iterations": 2, "activation_state": state}}, activation
        )
        return [e for e in errors if "feedback" in e]

    for activation, loop_state in lint.LOOP_ACTIVATION_STATES.items():
        assert loop_state in lint.CONTRACTS[activation]["state_machine"]["states"]
        assert not feedback_errors(activation, loop_state)
        for other in [*enum, "artifact_presented"]:
            if other != loop_state:
                assert feedback_errors(activation, other), (activation, other)


def test_derived_from_pattern_matches_criteria_provenance_lint():
    """derived_from の pattern と CL_ID_RE が同じ文字列集合を受理する (\\d と [0-9] の表記差を吸収)。"""
    schema = json.loads(CAPABILITY_MANIFEST_SCHEMA.read_text(encoding="utf-8"))
    pattern = schema["definitions"]["commonCore"]["properties"]["feedback_contract"]["properties"][
        "criteria"
    ]["items"]["properties"]["derived_from"]["items"]["pattern"]
    lint = _load(CRITERIA_PROVENANCE_LINT, "lint_criteria_provenance")
    schema_re = re.compile(pattern)
    samples = ["CL-1", "CL-12", "CL-0", "CL-", "CL-a", "XCL-1", "CL-1 ", "cl-1", "CL-1a", "CL--1"]
    for s in samples:
        assert bool(schema_re.match(s)) == bool(lint.CL_ID_RE.match(s)), s


def test_trace_schema_declares_every_key_validate_build_trace_reads():
    """validate-build-trace main() から辿れる data.get("x") が全て trace schema に宣言されている。

    schema は additionalProperties:false なので、宣言漏れのキーを書いた trace は
    validator を通っても schema で落ちる (baseline で skill_path ほか 11 キーが該当)。
    """
    src = VALIDATE_BUILD_TRACE.read_text(encoding="utf-8").splitlines()
    starts = [(i, re.match(r"def (\w+)", line).group(1)) for i, line in enumerate(src) if line.startswith("def ")]
    bodies = {}
    for k, (i, name) in enumerate(starts):
        end = starts[k + 1][0] if k + 1 < len(starts) else len(src)
        bodies[name] = "\n".join(src[i:end])
    reachable, stack = set(), ["main"]
    while stack:
        name = stack.pop()
        if name in reachable:
            continue
        reachable.add(name)
        stack.extend(m for m in re.findall(r"\b(_\w+)\(", bodies[name]) if m in bodies)
    keys = set()
    for name in reachable:
        # trace 本体 (data: dict) を受け取る関数だけ。brief や manifest を読む関数は別の文書を見ている
        if name == "main" or re.search(r"\(data: dict", bodies[name]):
            keys |= set(re.findall(r'data\.get\("([a-z_0-9]+)"', bodies[name]))
    assert len(keys) > 10, "キー抽出が空振りしている"
    schema = json.loads(TRACE_SCHEMA.read_text(encoding="utf-8"))
    assert schema.get("additionalProperties") is False
    assert sorted(keys - set(schema["properties"])) == []


def test_every_skill_feedback_contract_validates_against_manifest_schema():
    validator = _feedback_contract_validator()
    unexpected, still_failing = [], set()
    checked = 0
    for rel, contract in _skill_feedback_contracts():
        checked += 1
        errors = [e.message for e in validator.iter_errors(contract)]
        known = KNOWN_FEEDBACK_CONTRACT_VIOLATIONS.get(rel)
        if known and errors and all(known in e for e in errors):
            still_failing.add(rel)
        elif errors:
            unexpected.append((rel, errors))
    assert checked > 50, "SKILL.md の走査が空振りしている"
    assert unexpected == []
    fixed = set(KNOWN_FEEDBACK_CONTRACT_VIOLATIONS) - still_failing
    assert not fixed, f"直った既知違反を KNOWN_FEEDBACK_CONTRACT_VIOLATIONS から外す: {sorted(fixed)}"
