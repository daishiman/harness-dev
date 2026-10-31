"""flyer-studio の plugin-composition.yaml が登録簿 (references/registry.json) の射影であることを検証する。

flyer は部品の登録簿を references/registry.json に持ち、harness 書式の plugin-composition.yaml は
scripts/build-local-package.py --write-composition が生成する写しである。本 test は生成器を使わずに
射影を組み立て直し、YAML として読んだ composition と照合する (生成器と同じ誤りを共有しない独立の oracle)。
あわせて、harness の lint-plugin-composition が flyer の composition と、配布キットで作り直した composition を
例外なしに通すこと、生成器の YAML の値が読み戻すと元の文字列になること、生成物の手直し・再生成忘れを
flyer 自身の check_composition が検出することを確かめる。
"""
from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "flyer-studio"
COMPOSITION = PLUGIN / "plugin-composition.yaml"
REGISTRY = PLUGIN / "references" / "registry.json"
MANIFEST = PLUGIN / ".claude-plugin" / "plugin.json"
LINT = ROOT / "plugins" / "skill-governance-lint" / "scripts" / "lint-plugin-composition.py"
BUILDER = PLUGIN / "scripts" / "build-local-package.py"

# repo 専用で実体を置き、独立キットでは外す skill。登録簿には載せず、harness の公開面には載せる。
REPO_ONLY_SKILLS = ["run-skill-feedback"]
# 外した skill だけが要る plugin。キットの package-contract.json の depends_on から落ちる（harness-creator は composition の外部依存からも、
# skill-governance-adapters は manifest の dependencies からも落ちる）。
REPO_ONLY_DEPENDENCIES = ["harness-creator", "skill-governance-adapters"]

# plain で書くと文字列以外 (数・日付・null・真偽・merge key) に読まれる形、YAML の記号で始まる形、改行や制御文字を含む形。
# 生成器はどれも、読み戻すと元の文字列になる形で書かなければならない。
YAML_SAMPLES = [
    "flyer-studio", "skills/run-create-flyer", "1.3.0", "10.20.30.40", "部品の登録簿", "harness maintainers", "", "x",
    " lead", "trail ", "a\u3000", "_u", "0b101", "0x1_F", "0o17", "017", "1_000", "1_000.5", "1.5_0", "1e3", ".5", "-1",
    "+1", ".inf", "-.inf", ".NaN", "190:20:30", "2026-10-31", "2026-10-31T03:11:53Z", "~", "null", "Null", "NULL",
    "true", "False", "yes", "No", "on", "OFF", "y", "N", "=", "<<", "a: b", "a #b", "#x", "-x", "- x", "? x", ":x",
    "[x]", "{x}", "a,b", "*ref", "&anc", "!tag", "|", ">", "%d", "@a", "`b`", "it's", 'say "hi"', "back\\slash",
    "line\nbreak", "tab\there", "cr\rhere", "nel\x85here", "ls\u2028here", "ps\u2029here", "del\x7fhere", "é",
    "a?b", "a\ufffeb", "a\uffffb",
]
# git に入れない素材の画像 (plugin の .gitignore)。CI の checkout には無いので、キットの写しでも外す。
ASSET_IMAGES = shutil.ignore_patterns("*.png", "*.jpg", "*.jpeg", "*.webp", "*.svg")


def _builder():
    spec = importlib.util.spec_from_file_location("flyer_build_local_package", BUILDER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load() -> tuple[dict, dict, dict]:
    comp = yaml.safe_load(COMPOSITION.read_text(encoding="utf-8"))
    reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    return comp, reg, manifest


def _lift(ref: str) -> str:
    """skill 内の agent (skills/<s>/agents/<a>) の端を、その skill へ寄せる。"""
    parts = ref.split("/")
    return "/".join(parts[:2]) if parts[0] == "skills" and len(parts) > 2 else ref


def test_composition_header_follows_manifest():
    comp, reg, manifest = _load()
    assert comp["kind"] == "plugin-composition"
    assert comp["name"] == manifest["name"] == "flyer-studio"
    # 版は manifest が正本。登録簿は版を持たない (release が上げるのは manifest と composition の版行)。
    assert comp["version"] == manifest["version"]
    assert isinstance(comp["version"], str)
    assert "version" not in reg and "kind" not in reg
    assert comp["description"] == reg["description"]


def test_composition_contract_matches_registry():
    comp, reg, _ = _load()
    assert comp["contract"]["intent"] == reg["contract"]["intent"]
    assert comp["contract"]["interface"]["inputs"] == reg["contract"]["interface"]["inputs"]
    assert comp["contract"]["interface"]["outputs"] == reg["contract"]["interface"]["outputs"]
    assert comp["contract"]["invariant"] == reg["contract"]["invariant"]
    assert comp["eval_sinks"] == reg["eval_sinks"]


def test_capabilities_are_the_public_surface_of_the_registry():
    comp, reg, _ = _load()
    expected = {
        (c["kind"], c["ref"], c["tier"])
        for c in reg["capabilities"]
        if c["kind"] == "skill" or c["ref"].startswith("agents/")
    }
    expected |= {("skill", f"skills/{name}", "core") for name in REPO_ONLY_SKILLS}
    declared = [(c["kind"], c["ref"], c["tier"]) for c in comp["capabilities"]]
    assert len(declared) == len(set(declared)), "capabilities に重複"
    assert set(declared) == expected
    # skill 内の agent は harness の公開面ではない (lint の public-surface-parity は agents/*.md だけを数える)。
    assert not any(ref.startswith("skills/") and "/agents/" in ref for _, ref, _ in declared)


def test_dependencies_are_the_lifted_dag_without_revision_edges():
    comp, reg, _ = _load()
    expected: list[tuple[str, str, str]] = []
    for dep in reg["dependencies"]:
        if dep["type"] == "revision":
            continue
        edge = (_lift(dep["from"]), _lift(dep["to"]), dep["type"])
        if edge[0] != edge[1] and edge not in expected:
            expected.append(edge)
    declared = [(d["from"], d["to"], d["type"]) for d in comp["dependencies"]]
    assert declared == expected
    assert all(set(d) == {"from", "to", "type"} for d in comp["dependencies"])
    # FIX の戻り (revision) と非FIXの差し戻しは登録簿にだけ残る。
    assert any(d["type"] == "revision" for d in reg["dependencies"])
    assert reg["nonFixReturns"], "登録簿の nonFixReturns が空"


def test_external_dependencies_match_registry():
    comp, reg, _ = _load()
    assert comp["external_dependencies"] == reg["external_dependencies"]
    assert comp["external_dependencies"]["harness-creator"]["required_entry_points"] == REPO_ONLY_SKILLS


def test_public_lint_passes_flyer_composition():
    proc = subprocess.run(
        [sys.executable, str(LINT), str(COMPOSITION)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "OK: 1 composition file(s) passed" in proc.stdout


def test_builder_scalars_read_back_as_the_same_strings():
    module = _builder()
    for value in YAML_SAMPLES:
        assert yaml.safe_load("k: " + module.scalar(value))["k"] == value, repr(value)
        assert yaml.safe_load("k: " + module.flow([value, value]))["k"] == [value, value], repr(value)
        assert yaml.safe_load("k: " + module.mapping({"a": value}, ["a"]))["k"] == {"a": value}, repr(value)
    # release は版の行を引用なしで書き換える。版を plain で書かないと、上げた後の composition が生成と byte で一致しない。
    assert module.scalar("1.3.0") == "1.3.0"
    assert module.scalar("skills/run-create-flyer") == "skills/run-create-flyer"


def test_kit_composition_passes_public_lint_without_repo_only_parts(tmp_path):
    # package() と同じ IGNORE で写し、同じ narrow_kit() で直す。package() は素材の検査 (check) を先に通すので、
    # 素材の画像が無い CI では使えない。素材は composition と台帳の絞り込みに関わらない。
    module = _builder()
    shipped = tmp_path / "kit" / "plugins" / "flyer-studio"

    def ignore(directory, names):
        skipped = set(module.IGNORE(directory, names, PLUGIN))
        if (PLUGIN / "assets") in [Path(directory).resolve(), *Path(directory).resolve().parents]:
            skipped |= set(ASSET_IMAGES(directory, names))
        return skipped

    shutil.copytree(PLUGIN, shipped, ignore=ignore)
    module.narrow_kit(shipped, PLUGIN)
    assert not (shipped / "skills" / REPO_ONLY_SKILLS[0]).exists()
    lint = subprocess.run(
        [sys.executable, str(LINT), str(shipped / "plugin-composition.yaml")],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert lint.returncode == 0, lint.stdout + lint.stderr
    assert "OK: 1 composition file(s) passed" in lint.stdout
    comp = yaml.safe_load((shipped / "plugin-composition.yaml").read_text(encoding="utf-8"))
    refs = {c["ref"] for c in comp["capabilities"]}
    assert not refs & {f"skills/{name}" for name in REPO_ONLY_SKILLS}, refs
    assert not set(comp.get("external_dependencies", {})) & set(REPO_ONLY_DEPENDENCIES), comp.get("external_dependencies")
    # キットの台帳も、キットが解決できない依存を宣言しない。repo の台帳はそのまま残る。
    contract = json.loads((shipped / "references" / "package-contract.json").read_text(encoding="utf-8"))
    assert not set(contract["depends_on"]) & set(REPO_ONLY_DEPENDENCIES), contract["depends_on"]
    assert not {d["required_entry_point"] for d in contract["runtime_dependencies"]} & set(REPO_ONLY_SKILLS)
    assert not set(contract["entry_points"]["skills"]) & set(REPO_ONLY_SKILLS)
    repo = json.loads((PLUGIN / "references" / "package-contract.json").read_text(encoding="utf-8"))
    assert set(REPO_ONLY_DEPENDENCIES) <= set(repo["depends_on"])
    assert {d["required_entry_point"] for d in repo["runtime_dependencies"]} >= set(REPO_ONLY_SKILLS)


def test_builder_detects_hand_edits_and_missing_regeneration(tmp_path):
    module = _builder()
    assert module.check_composition(PLUGIN) == []
    # 生成器の出力は、置かれている composition と byte 単位で一致する。
    assert module.render_composition(PLUGIN) == COMPOSITION.read_text(encoding="utf-8")

    # 生成に要るファイルだけを写した plugin で、手直しと再生成忘れを検出させる。
    root = tmp_path / "flyer-studio"
    for rel in ["references/registry.json", "references/package-contract.json", ".claude-plugin/plugin.json",
                "plugin-composition.yaml", *(f"skills/{n}/SKILL.md" for n in REPO_ONLY_SKILLS)]:
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_bytes((PLUGIN / rel).read_bytes())
    assert module.check_composition(root) == []
    composed = root / "plugin-composition.yaml"
    composed.write_text(composed.read_text(encoding="utf-8").replace("tier: extension", "tier: core", 1), encoding="utf-8")
    errors = module.check_composition(root)
    assert len(errors) == 1 and "--write-composition" in errors[0], errors
    composed.write_text(module.render_composition(root), encoding="utf-8")
    reg = json.loads((root / "references/registry.json").read_text(encoding="utf-8"))
    reg["dependencies"].append({"from": "skills/run-learn-flyer", "to": "agents/flyer-color-reviewer", "type": "delegates"})
    (root / "references/registry.json").write_text(json.dumps(reg, ensure_ascii=False), encoding="utf-8")
    assert len(module.check_composition(root)) == 1, "登録簿を変えて再生成しなかった composition を通した"
