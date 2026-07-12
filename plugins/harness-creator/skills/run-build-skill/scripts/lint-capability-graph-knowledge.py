#!/usr/bin/env python3
# /// script
# name: lint-capability-graph-knowledge
# purpose: brief.goal_seek.engine=task-graph 指定で生成された harness が、ENG-C06 による cross-surface dependency graph 抽出、ENG-C07 による Loop A/Loop B knowledge 記録、各 surface の実行前 knowledge consult 指示を3段設計 (skill=hard gate / command・agent=warning / script=同梱 byte-parity) で検査する。checklist 順序実行だけで終わらず、依存グラフ由来 knowledge を各 surface が使うことの機械ゲートにする (H6 の実装物)。
# inputs:
#   - argv: <generated_harness_dir_or_skill_md> | --self-test (BUNDLED_SCRIPTS↔SKILL.md Step10.6 parity + regex 定義 drift 検査)
# outputs:
#   - stdout: OK / not-applicable
#   - stderr: missing token・dangling dependency・knowledge consult 未配線 violation 一覧
#   - exit: 0=OK / 1=violation / 2=usage/IO error
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""生成 task-graph harness の dependency graph knowledge 利用契約を検査する lint (ENG-C08)。

engine:task-graph 指定で生成された harness に対し、route C04 (lint-goal-seek.py) が goal-seek schema /
consumption verifier の SSOT drift を見るのと分離して、本 lint は「依存グラフ由来 knowledge を
各 surface が実際に使う」横断契約を検査する:
  1. 同梱 4 script (ENG-C01/ENG-C02/ENG-C06/ENG-C07) が生成先 scripts/ に実在し、テンプレ原本と
     byte 一致する (同梱 script は原本の無改変コピー。手改変は fail-closed 検出)。
  2. engine:task-graph を宣言する各 skill surface が dependency graph knowledge consult token を持つ。
  3. command/agent surface が存在する場合は advisory consult token 欠落を warning として収集する。
  4. 記録済み knowledge entry (knowledge-capability-graph.json) が全て source_ref を持つ (dangling
     gap entry を含め出所が追える)。

スコープ注記: consult token の hard 検査対象は「ループを回す skill surface」(engine:task-graph 宣言
SKILL.md)。command/agent surface は consult token の欠如を warning で報告する (skill 側 wiring が
consult の一次責務を負い、全 surface へトークンを強制するのは Goodhart 化するため)。script surface は
実体 (ENG-C01/ENG-C02/ENG-C06/ENG-C07) の同梱有無で担保する。

engine:task-graph を宣言する SKILL.md が 1 件も無ければ not-applicable として exit0。

Exit 0 = OK / not-applicable, 1 = violation, 2 = usage/IO error。
"""
from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

CONSULT_TOKEN = "dependency graph knowledge"
# 生成 SKILL.md の task-graph 変種配線が scripts/ 経由で参照する 4 本すべてを同梱ゲート対象にする
# (gate-coverage parity: 参照集合と検査集合を一致させ「ENG-C06/ENG-C07 だけコピーすれば緑」の誤メンタルモデルを排す)。
# ready-set-from-checklist.py(ENG-C01)/self-reflect-append.py(ENG-C02) が漏れると実行時 dangling するため
# build-time に fail-closed 検出する。
BUNDLED_SCRIPTS = (
    "ready-set-from-checklist.py",
    "self-reflect-append.py",
    "extract-capability-dependency-graph.py",
    "record-capability-graph-knowledge.py",
)
KNOWLEDGE_STORE = "knowledge-capability-graph.json"
# concrete な engine: task-graph 宣言 (frontmatter YAML 行・末尾コメント許容) のみに一致。
# 機能を説明する散文/コメント中の言及や template placeholder には誤発火しない。
_CONCRETE_TASK_GRAPH_ENGINE_RE = re.compile(
    r"^\s*engine:\s*task-graph\s*(?:#.*)?$", re.MULTILINE
)


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _frontmatter(text: str) -> str:
    if not text.startswith("---"):
        return ""
    parts = text.split("---", 2)
    return parts[1] if len(parts) >= 3 else ""


def resolve_harness_root(target: Path) -> Path:
    """入力が SKILL.md ファイルなら harness root (skills/ を持つ祖先) を、dir ならそのまま返す。"""
    if target.is_dir():
        return target
    # skills/<name>/SKILL.md → 祖先を辿り skills/ を持つディレクトリを root とする。
    for anc in target.parents:
        if (anc / "skills").is_dir() or (anc / "scripts").is_dir():
            return anc
    return target.parent


def collect_task_graph_skills(root: Path, single_file: Path | None) -> list[Path]:
    """engine:task-graph を concrete 宣言する SKILL.md 群を返す。"""
    if single_file is not None and single_file.is_file():
        candidates = [single_file]
    else:
        candidates = sorted(root.glob("skills/*/SKILL.md")) + sorted(root.glob("SKILL.md"))
    return [p for p in candidates if _CONCRETE_TASK_GRAPH_ENGINE_RE.search(_frontmatter(_read(p)))]


def _template_root() -> Path:
    """同梱原本の所在 (本 lint と同一 skill 配下の templates/task-graph-engine/scripts/)。"""
    return Path(__file__).resolve().parent.parent / "templates" / "task-graph-engine" / "scripts"


def check_bundling(skills: list[Path]) -> list[str]:
    """task-graph 宣言 skill ごとに4 script の実在と原本 byte 一致を検査する。

    別 skill や builder 自身の templates に同名資産があっても充足扱いしない。
    """
    findings: list[str] = []
    template_root = _template_root()
    for skill in skills:
        scripts_dir = skill.parent / "scripts"
        for name in BUNDLED_SCRIPTS:
            copy = scripts_dir / name
            if not copy.is_file():
                findings.append(
                    f"同梱欠落: {copy} が不在 (task-graph 宣言 skill ごとの scripts/ に必須)"
                )
                continue
            original = template_root / name
            if not original.is_file():
                findings.append(
                    f"テンプレ原本不在: {original} (byte-parity 検査不能 — run-build-skill の "
                    "templates/task-graph-engine/scripts/ を欠く破損配置)"
                )
                continue
            expected = original.read_bytes()
            if copy.read_bytes() != expected:
                findings.append(
                    f"byte-parity 違反: {copy} がテンプレ原本 {name} と不一致 "
                    "(同梱 script は原本の無改変コピーであること)"
                )
    return findings


def check_engine_profile(skills: list[Path]) -> list[str]:
    """full task-spec graph を誤申告しない checklist-graph 境界を hard gate。"""
    findings: list[str] = []
    profile_re = re.compile(r"^\s+engine_profile:\s*checklist-graph\s*(?:#.*)?$", re.MULTILINE)
    full_re = re.compile(r"^\s+full_task_spec_graph:\s*false\s*(?:#.*)?$", re.MULTILINE)
    for skill in skills:
        fm = _frontmatter(_read(skill))
        if not profile_re.search(fm):
            findings.append(
                f"engine profile 欠落/不正: {skill} は engine_profile: checklist-graph 必須 "
                "(planner full task-spec graph と非同等)"
            )
        if not full_re.search(fm):
            findings.append(
                f"capability claim 欠落/不正: {skill} は full_task_spec_graph: false 必須 "
                "(未実装機構を成功扱いしない fail-closed gate)"
            )
    return findings


def check_consult_tokens(skills: list[Path]) -> list[str]:
    """engine:task-graph skill が dependency graph knowledge consult token を持つか検査する。"""
    findings: list[str] = []
    for skill in skills:
        if CONSULT_TOKEN not in _read(skill):
            findings.append(
                f"consult 未配線: {skill} に '{CONSULT_TOKEN}' consult token が不在 "
                "(engine:task-graph skill は実行前に依存グラフ knowledge を consult すること)"
            )
    return findings


def collect_advisory_surfaces(root: Path) -> list[Path]:
    """command/agent surface を収集する。

    skill surface は hard gate、script surface は bundled script 実在で担保するためここでは扱わない。
    command/agent は routing surface であり、欠落は警告に留めて実行前 consult の改善余地として返す。
    """
    candidates: list[Path] = []
    for pattern in ("commands/*.md", "agents/*.md"):
        candidates.extend(sorted(root.glob(pattern)))
    return [p for p in candidates if p.is_file()]


def check_advisory_surface_consults(root: Path) -> list[str]:
    """command/agent surface の consult token 欠落を warning として返す。"""
    warnings: list[str] = []
    for surface in collect_advisory_surfaces(root):
        if CONSULT_TOKEN not in _read(surface):
            warnings.append(
                f"advisory consult 未配線: {surface} に '{CONSULT_TOKEN}' consult token が不在 "
                "(command/agent surface は warning。skill surface が hard gate)"
            )
    return warnings


def check_source_refs(root: Path) -> tuple[list[str], list[str]]:
    """記録済み knowledge store の各 entry が source_ref を持つか検査する。(findings, warnings)。"""
    findings: list[str] = []
    warnings: list[str] = []
    stores = sorted(root.glob(f"**/{KNOWLEDGE_STORE}"))
    if not stores:
        warnings.append(
            f"{KNOWLEDGE_STORE} が未生成 (record-capability-graph-knowledge.py 未実行)。"
            "runtime で記録されるため build 時点では warning 止まり"
        )
        return findings, warnings
    for store in stores:
        try:
            data = json.loads(store.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            findings.append(f"{store}: 読込/parse 失敗: {e}")
            continue
        for item in data.get("items", []):
            if not isinstance(item, dict):
                continue
            if not item.get("source_ref"):
                findings.append(
                    f"{store}: entry '{item.get('id')}' が source_ref を持たない "
                    "(Loop A/B knowledge entry は出所追跡のため source_ref 必須)"
                )
    return findings, warnings


def lint(target: Path) -> tuple[list[str], list[str], bool]:
    """(findings, warnings, applicable) を返す。"""
    root = resolve_harness_root(target)
    single = target if target.is_file() else None
    skills = collect_task_graph_skills(root, single)
    if not skills:
        return [], [], False  # not-applicable

    findings: list[str] = []
    findings.extend(check_engine_profile(skills))
    findings.extend(check_bundling(skills))
    findings.extend(check_consult_tokens(skills))
    sr_findings, warnings = check_source_refs(root)
    warnings.extend(check_advisory_surface_consults(root))
    findings.extend(sr_findings)
    return findings, warnings, True


def self_test() -> int:
    """同梱リスト・regex 定義の分散コピー drift を検査する (check_default_drift と同型の SSOT ガード)。

    1. BUNDLED_SCRIPTS ↔ SKILL.md Step 10.6 の列挙 script が集合一致する
       (同梱 4 本は本 lint / Step10.6 / render 配線 prose の 3 箇所ハードコードのため、
        1 本追加時の同期漏れを機械検出する)。
    2. validate-build-plan / render-combinators / 本 lint の同梱4資産集合が一致する。
    3. _CONCRETE_TASK_GRAPH_ENGINE_RE が lint-goal-seek.py 側の同名定義と文字列一致する。
    """
    findings: list[str] = []
    skill_md = Path(__file__).resolve().parent.parent / "SKILL.md"
    text = _read(skill_md)
    m = re.search(r"### Step 10\.6:.*?(?=\n### Step |\Z)", text, re.DOTALL)
    if not m:
        findings.append(f"self-test: {skill_md} に Step 10.6 節が見つからない")
    else:
        # 同梱列挙は `script.py`=ENG-Cxx 形式 (手順 3/4 の render/lint 言及と区別する)。
        listed = set(re.findall(r"`([a-z0-9-]+\.py)`=ENG-C", m.group(0)))
        expected = set(BUNDLED_SCRIPTS)
        if listed != expected:
            findings.append(
                "self-test: BUNDLED_SCRIPTS と SKILL.md Step10.6 の列挙が不一致: "
                f"lint側のみ={sorted(expected - listed)} / Step10.6側のみ={sorted(listed - expected)}"
            )
    for peer_name, constant_name in (
        ("validate-build-plan.py", "TASK_GRAPH_ENGINE_SCRIPTS"),
        ("render-combinators.py", "TASK_GRAPH_ENGINE_SCRIPTS"),
    ):
        peer_path = Path(__file__).resolve().parent / peer_name
        try:
            tree = ast.parse(_read(peer_path), filename=str(peer_path))
            value = None
            for node in tree.body:
                if not isinstance(node, ast.Assign):
                    continue
                if any(isinstance(t, ast.Name) and t.id == constant_name for t in node.targets):
                    value = ast.literal_eval(node.value)
                    break
            peer_set = set(value or ())
        except (SyntaxError, ValueError, TypeError) as exc:
            findings.append(f"self-test: {peer_path} の {constant_name} を読めない: {exc}")
            continue
        if peer_set != set(BUNDLED_SCRIPTS):
            findings.append(
                f"self-test: BUNDLED_SCRIPTS と {peer_name}:{constant_name} が不一致: "
                f"lint側のみ={sorted(set(BUNDLED_SCRIPTS) - peer_set)} / "
                f"peer側のみ={sorted(peer_set - set(BUNDLED_SCRIPTS))}"
            )
    peer = Path(__file__).resolve().parent / "lint-goal-seek.py"
    peer_src = _read(peer)
    pm = re.search(
        r'_CONCRETE_TASK_GRAPH_ENGINE_RE\s*=\s*re\.compile\(\s*r"([^"]+)"', peer_src
    )
    if not pm:
        findings.append(f"self-test: {peer} に _CONCRETE_TASK_GRAPH_ENGINE_RE 定義が見つからない")
    elif pm.group(1) != _CONCRETE_TASK_GRAPH_ENGINE_RE.pattern:
        findings.append(
            "self-test: _CONCRETE_TASK_GRAPH_ENGINE_RE が lint-goal-seek.py と drift: "
            f"本lint={_CONCRETE_TASK_GRAPH_ENGINE_RE.pattern!r} / peer={pm.group(1)!r}"
        )
    if findings:
        for f in findings:
            sys.stderr.write(f + "\n")
        return 1
    sys.stdout.write(
        "OK: self-test 通過 (Step10.6 + build-plan + materializer asset parity / regex 定義一致)\n"
    )
    return 0


def main(argv: list[str]) -> int:
    if argv == ["--self-test"]:
        return self_test()
    if len(argv) != 1 or argv[0] in ("-h", "--help"):
        sys.stderr.write(
            "usage: lint-capability-graph-knowledge.py <generated_harness_dir_or_skill_md> | --self-test\n"
        )
        return 0 if argv[:1] in (["-h"], ["--help"]) else 2
    target = Path(argv[0])
    if not target.exists():
        sys.stderr.write(f"対象が存在しない: {target}\n")
        return 2

    findings, warnings, applicable = lint(target)
    for w in warnings:
        sys.stderr.write(f"WARN: {w}\n")
    if not applicable:
        sys.stdout.write("not-applicable: engine:task-graph を宣言する skill surface が無い\n")
        return 0
    if findings:
        for f in findings:
            sys.stderr.write(f + "\n")
        return 1
    suffix = f" ({len(warnings)} warning(s))" if warnings else ""
    sys.stdout.write(f"OK: dependency graph knowledge 利用契約 準拠{suffix}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
