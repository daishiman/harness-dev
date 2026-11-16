#!/usr/bin/env python3
# /// script
# name: derive-verification-contract
# purpose: build unit（build plan・skill dir・brief）から、graph 単位の検証 obligation の contract を作る
# inputs:
#   - argv: --unit-manifest <json> または --build-plan・--skill-dir・--brief の3つ [--mode create|update] [--trace <json>] [--subject] [--repo-root] [--out <json>] [--evidence-dir <dir>]
#   - file: build trace（既定 <repo-root>/eval-log/skill-build-trace.json。skill_name が build plan と一致するときだけ build_mode を読む。--evidence-dir では lint・lint_target_sha256・lint_brief_sha256 も読む）
# outputs:
#   - stdout: contract JSON（--out を付けたときは同じ内容をそのファイルにも書く。--evidence-dir の有無で中身は変わらない）
#   - file: --evidence-dir を付け、trace の Step 4 lint PASS が今の skill dir・brief・mode と一致し、contract の checker argv をこの場で走らせて exit 0 だった unit だけ、build-conformance の PASS receipt（record-verification-evidence.py が書く）
#   - stderr: --evidence-dir のとき unit ごとに、receipt を書いたか、書かずに check のまま残した理由（checker が通らなかったときは exit code と出力の最後の行）
#   - exit: 0=OK（receipt を書けなかったときも 0 で、その obligation は check のまま） / 2=入力を読めない・引数の組が足りない・manifest や build plan の形が不正・subject が文字列でない・checker の validate-build-plan.py が同じ scripts/ に無い・mode が create/update 以外・明示した trace が無いか skill_name が食い違う・明示の mode と trace の build_mode が食い違う
# requires-python: ">=3.10"
# dependencies: [plan-verification-obligations.py, record-verification-evidence.py, validate-build-plan.py, ../../../scripts/feedback_contract_ssot.py]
# contexts: [A, C]
# network: false
# write-scope: --out の指定先・--evidence-dir 配下の build-conformance receipt（record-verification-evidence.py 経由）・一時 plan（終了時に消える）。checker の validate-build-plan --check は読むだけ
# ///
"""Derive a graph-level verification-obligation contract from build units.

One contract may contain many skills/routes.  Per-unit semantic claims remain
independently cacheable, while the resolver may batch all currently unresolved
claims into the minimum number of LLM contexts allowed by their actual context
size.  This breaks the old route -> review-session coupling.

checker の validate-build-plan.py は、この script と同じ scripts/ にある実物を指す
（SKILL.md Key Rules 6: plugin root を cwd や repo からの相対位置で推測しない）。
その実物が --repo-root の中にあれば repo 相対で書き、外（marketplace install など）に
あれば絶対パスで書く。argv は fingerprint に入るので、harness 自身の repo では
worktree ごとの絶対パスを焼き込まずに済み、consumer では install 先が変われば
checker が変わったとして再検査になる。

build-conformance の checker は、Step 4 と同じ mode で validate-build-plan.py を走らせる。
update では --mode update を付ける（今の SKILL.md の goal_seek を引き継いだ計画で検査する）。
mode は unit の mode か --mode、無ければ skill_name が build plan と一致する trace の
build_mode、どちらも無ければ create。create の argv は従来と同じなので、create の
fingerprint は変わらない。

--evidence-dir を付けると、Step 4 がすでに同じ検査を通した unit について、
Step 12 で agent が validate-build-plan を走らせて記録する往復を省けるよう build-conformance の
receipt を書く。trace は候補を絞るだけで、PASS の根拠にはしない。候補になるのは、skill_name が
build plan と一致する trace について次がすべて成り立つ unit: reproducibility_gates.lint が PASS・
build_mode が今の mode と同じ・lint_target_sha256 が今の skill dir の digest
(feedback_contract_ssot.directory_content_sha256) と同じ・lint_brief_sha256 が今の brief の bytes の
sha256 と同じ。さらに planner がその obligation を check (machine-proof-missing) と判定したときに限る。
そのうえで contract の checker argv をこの場で走らせ、exit 0 のときだけ receipt を書く。
digest は skill dir と brief しか見ないが、validate-build-plan は pair skill・plugin の agents・
templates・checker 自身も読む。それらが Step 4 の後に変わっても、走らせ直せば今の結果になる
(trace は agent が書く自己申告なので、それだけで PASS を書くと古い PASS や書き違いを引き継ぐ)。
今の receipt が PASS でも FAIL でも上書きしない。1つでも欠ければ receipt を書かず、planner は
従来どおり check を返す。contract 自体はこの指定の有無で変わらない。
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path


def _repo_rel(repo_root: Path, raw: str | Path) -> str:
    if not isinstance(raw, (str, Path)):
        raise ValueError(f"path は文字列でなければならない: {raw!r}")
    path = Path(raw)
    resolved = path.resolve() if path.is_absolute() else (repo_root / path).resolve()
    try:
        return resolved.relative_to(repo_root).as_posix()
    except ValueError as exc:
        raise ValueError(f"path is outside repo root: {raw}") from exc


def _unit_id(skill_dir: str) -> str:
    parts = Path(skill_dir).parts
    plugin = parts[parts.index("plugins") + 1] if "plugins" in parts and parts.index("plugins") + 1 < len(parts) else "plugin"
    skill = Path(skill_dir).name
    raw = f"{plugin}:{skill}"
    return re.sub(r"[^A-Za-z0-9:._-]+", "-", raw)


def _checker_script(repo_root: Path) -> str:
    """同じ scripts/ にある validate-build-plan.py を、repo の中なら repo 相対、外なら絶対パスで返す。"""
    validator = Path(__file__).resolve().with_name("validate-build-plan.py")
    if not validator.is_file():
        raise ValueError(f"checker の validate-build-plan.py が見つからない: {validator}")
    try:
        return validator.relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return validator.as_posix()


def _input(path: str, *, context: bool) -> dict:
    return {"path": path, "required": True, "context": context}


BUILD_MODES = {"create", "update"}
DEFAULT_TRACE = "eval-log/skill-build-trace.json"


def _check_mode(raw: object, where: str) -> str:
    if raw not in BUILD_MODES:
        raise ValueError(f"{where} の mode は create か update: {raw!r}")
    return str(raw)


def _resolve_mode(
    raw_unit: dict, repo_root: Path, plan_skill_name: str, unit_id: str
) -> tuple[str, tuple[str, dict] | None]:
    """unit の mode → skill_name が一致する trace の build_mode → create の順で決める。

    明示した trace は、無い・skill_name が違う・build_mode が不正なら入力不正にする。
    既定の trace は別の skill のものでありうるので、無いか skill_name が違えば読まない。
    2つ目の値は skill_name が一致した trace の (repo 相対パス, 中身) で、一致しなければ None。
    Step 4 の lint PASS を receipt に引き継ぐかどうかは、この trace だけで判断する。
    """
    explicit = raw_unit.get("mode")
    mode = _check_mode(explicit, unit_id) if explicit is not None else None
    trace_raw = raw_unit.get("trace")
    trace_rel = _repo_rel(repo_root, trace_raw if trace_raw is not None else DEFAULT_TRACE)
    trace_path = repo_root / trace_rel
    if trace_raw is None and not trace_path.is_file():
        return mode or "create", None
    trace = json.loads(trace_path.read_text(encoding="utf-8"))
    if not isinstance(trace, dict):
        raise ValueError(f"trace が object でない: {trace_path}")
    if not plan_skill_name or trace.get("skill_name") != plan_skill_name:
        if trace_raw is not None:
            raise ValueError(
                f"trace の skill_name {trace.get('skill_name')!r} が build plan の {plan_skill_name!r} と違う: {trace_path}")
        return mode or "create", None
    traced = trace.get("build_mode")
    if traced is None:
        return mode or "create", (trace_rel, trace)
    traced = _check_mode(traced, f"trace {trace_path}")
    if mode is not None and mode != traced:
        raise ValueError(f"{unit_id} の mode {mode} が trace の build_mode {traced} と違う")
    return traced, (trace_rel, trace)


def derive_contract(units: list[dict], repo_root: Path, subject: str) -> dict:
    return _derive(units, repo_root, subject)[0]


def _derive(units: list[dict], repo_root: Path, subject: str) -> tuple[dict, list[dict]]:
    """contract と、unit ごとの build-conformance の receipt 候補 (Step 4 の trace との照合用) を返す。"""
    if not units:
        raise ValueError("at least one build unit is required")
    obligations: list[dict] = []
    semantic_ids: list[str] = []
    terminal_ids: list[str] = []
    audit_inputs: dict[str, dict] = {}
    seen_units: set[str] = set()
    candidates: list[dict] = []
    validator = _checker_script(repo_root)

    for raw_unit in units:
        if not isinstance(raw_unit, dict):
            raise ValueError(f"build unit が object でない: {raw_unit!r}")
        for key in ("build_plan", "skill_dir", "brief"):
            if not raw_unit.get(key):
                raise ValueError(f"unit requires {key}: {raw_unit}")
        build_plan = _repo_rel(repo_root, raw_unit["build_plan"])
        skill_dir = _repo_rel(repo_root, raw_unit["skill_dir"])
        brief = _repo_rel(repo_root, raw_unit["brief"])
        unit_id = str(raw_unit.get("id") or _unit_id(skill_dir))
        unit_id = re.sub(r"[^A-Za-z0-9:._-]+", "-", unit_id)
        if unit_id in seen_units:
            raise ValueError(f"duplicate build unit id: {unit_id}")
        seen_units.add(unit_id)
        plan_doc = json.loads((repo_root / build_plan).read_text(encoding="utf-8"))
        if not isinstance(plan_doc, dict):
            raise ValueError(f"build plan が object でない: {build_plan}")
        tier = str(plan_doc.get("acceptance_tier") or "static")
        if tier not in {"static", "fork", "live"}:
            raise ValueError(f"invalid acceptance_tier for {unit_id}: {tier}")
        plan_skill_name = str(plan_doc.get("skill_name") or "")
        mode, trace = _resolve_mode(raw_unit, repo_root, plan_skill_name, unit_id)
        checker_argv = ["python3", validator, "--brief", brief, "--check", "--skill-dir", skill_dir]
        if mode == "update":
            checker_argv += ["--mode", "update"]

        machine_id = f"machine:{unit_id}:build-conformance"
        candidates.append({
            "obligation_id": machine_id,
            "mode": mode,
            "skill_name": plan_skill_name,
            "skill_dir": skill_dir,
            "brief": brief,
            "trace": trace,
        })
        semantic_id = f"semantic:{unit_id}:intent-fidelity"
        common_inputs = [_input(brief, context=False), _input(build_plan, context=False), _input(skill_dir, context=False)]
        obligations.append({
            "id": machine_id,
            "claim": "The built artifact satisfies its deterministic build plan, schema, naming, trace, and dependency checks.",
            "kind": "deterministic",
            "risk": "high",
            "activation": "changed",
            "depends_on": [],
            "inputs": common_inputs,
            "checker": {
                "id": "validate-build-plan",
                "argv": checker_argv,
            },
            "minimum_confidence": 1.0,
            "reuse": True,
        })
        semantic_inputs = [_input(brief, context=True), _input(build_plan, context=True), _input(skill_dir, context=True)]
        obligations.append({
            "id": semantic_id,
            "claim": "The artifact faithfully solves the stated intent with no contradiction or omission, follows conventions, and has valid dependencies; judge only meaning not already proven by deterministic checks.",
            "kind": "semantic",
            "risk": "high",
            "activation": "changed",
            "depends_on": [machine_id],
            "inputs": semantic_inputs,
            "minimum_confidence": 0.8,
            "reuse": True,
        })
        semantic_ids.append(semantic_id)
        terminal_id = semantic_id
        if tier in {"fork", "live"}:
            observation_id = f"behavior:{unit_id}:{tier}-acceptance"
            obligations.append({
                "id": observation_id,
                "claim": f"The artifact behaves correctly in the minimum required {tier} acceptance environment.",
                "kind": "observational",
                "risk": "high",
                "activation": "changed",
                "depends_on": [machine_id, semantic_id],
                "inputs": [_input(skill_dir, context=True), _input(build_plan, context=False)],
                "observation_tier": tier,
                "minimum_confidence": 0.9,
                "reuse": True,
            })
            terminal_id = observation_id
        terminal_ids.append(terminal_id)
        for entry in semantic_inputs:
            audit_inputs[entry["path"]] = entry

    obligations.append({
        "id": "audit:30-paradigm-adversarial-coverage",
        "claim": "An explicit exhaustive audit uses the 30 thought methods as a coverage catalog and reports a finding or skip reason for every method without multiplying normal runtime review sessions.",
        "kind": "audit",
        "risk": "medium",
        "activation": "exhaustive",
        "depends_on": sorted(set(terminal_ids)),
        "inputs": [audit_inputs[path] for path in sorted(audit_inputs)],
        "minimum_confidence": 0.8,
        "reuse": False,
    })
    return {"schema_version": 1, "subject": subject, "obligations": obligations}, candidates


SHA256_RE = re.compile(r"[0-9a-f]{64}")
STEP4_VERIFIER_ID = "step4-lint-trace:validate-build-plan"
RECORD_TIMEOUT_S = 120
CHECKER_TIMEOUT_S = 120


def _run_checker(argv: list[str], repo_root: Path) -> tuple[int, str]:
    """contract の checker argv を repo root で走らせ、(exit code, 出力の最後の行) を返す。

    argv の python3 は今の interpreter に置き換える (planner が agent に渡すのと同じ argv を、同じ cwd で)。
    """
    command = [sys.executable if index == 0 and value == "python3" else value for index, value in enumerate(argv)]
    proc = subprocess.run(command, cwd=repo_root, capture_output=True, text=True, check=False, timeout=CHECKER_TIMEOUT_S)
    tail = (proc.stdout + proc.stderr).strip().splitlines()
    return proc.returncode, tail[-1] if tail else ""


def _sibling(name: str) -> Path:
    path = Path(__file__).resolve().with_name(name)
    if not path.is_file():
        raise ValueError(f"{name} が同じ scripts/ に無い: {path}")
    return path


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ValueError(f"module を読めない: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_directory_digest():
    """Step 4 が lint_target_sha256 に使う digest 関数を、plugin の SSOT から読む。"""
    here = Path(__file__).resolve()
    if len(here.parents) < 4:
        raise ValueError(f"plugin root を辿れない: {here}")
    ssot = here.parents[3] / "scripts" / "feedback_contract_ssot.py"
    if not ssot.is_file():
        raise ValueError(f"feedback_contract_ssot.py が見つからない: {ssot}")
    return _load_module("feedback_contract_ssot", ssot).directory_content_sha256


def _step4_reuse_blocker(candidate: dict, repo_root: Path, directory_digest) -> str | None:
    """Step 4 の lint PASS をこの unit の receipt に引き継げない理由を返す。引き継げるなら None。"""
    found = candidate["trace"]
    if found is None:
        return "skill_name の一致する trace が無い"
    _, trace = found
    gates = trace.get("reproducibility_gates")
    if not isinstance(gates, dict) or gates.get("lint") != "PASS":
        return "trace の reproducibility_gates.lint が PASS でない"
    if not candidate["skill_name"] or trace.get("skill_name") != candidate["skill_name"]:
        return "trace の skill_name が build plan と違う"
    if trace.get("build_mode") != candidate["mode"]:
        return f"trace の build_mode {trace.get('build_mode')!r} が今の mode {candidate['mode']!r} と違う"
    target = trace.get("lint_target_sha256")
    if not isinstance(target, str) or not SHA256_RE.fullmatch(target):
        return "trace に lint_target_sha256 が無いか、64 桁の小文字 hex でない"
    if directory_digest(repo_root / candidate["skill_dir"]) != target:
        return "Step 4 の後に skill dir が変わった (lint_target_sha256 と違う)"
    brief_sha = trace.get("lint_brief_sha256")
    if not isinstance(brief_sha, str) or not SHA256_RE.fullmatch(brief_sha):
        return "trace に lint_brief_sha256 が無いか、64 桁の小文字 hex でない (古い trace など)"
    brief_path = repo_root / candidate["brief"]
    if not brief_path.is_file():
        return "brief がファイルでない"
    if hashlib.sha256(brief_path.read_bytes()).hexdigest() != brief_sha:
        return "Step 4 の後に brief が変わった (lint_brief_sha256 と違う)"
    return None


def record_step4_receipts(contract: dict, candidates: list[dict], repo_root: Path, evidence_dir: Path) -> list[str]:
    """条件を満たす unit だけ build-conformance の PASS receipt を書き、unit ごとの結果の行を返す。

    trace の一致は候補を絞るだけで、receipt の根拠は contract の checker argv をこの場で走らせた exit 0。
    どの段で失敗しても receipt を書かずに続ける (fail-closed)。その obligation は planner が
    check を返すので、validate-build-plan がいつもどおり走る。
    """
    lines: list[str] = []
    pending: list[dict] = []
    try:
        directory_digest = _load_directory_digest()
    except (OSError, ValueError, ImportError, SyntaxError, AttributeError) as exc:
        return [f"[WARN] {c['obligation_id']}: check のまま (digest の SSOT を読めない: {exc})" for c in candidates]
    for candidate in candidates:
        try:
            blocker = _step4_reuse_blocker(candidate, repo_root, directory_digest)
        except OSError as exc:
            blocker = f"読めない: {type(exc).__name__}: {exc}"
        if blocker:
            lines.append(f"[INFO] {candidate['obligation_id']}: check のまま ({blocker})")
        else:
            pending.append(candidate)
    if not pending:
        return lines
    try:
        planner = _load_module("verification_obligation_planner", _sibling("plan-verification-obligations.py"))
        record_script = _sibling("record-verification-evidence.py")
        # stage・profile は fingerprint に入らないので既定のままでよい
        plan = planner.build_plan(contract, repo_root, evidence_dir)
    except (OSError, ValueError, ImportError, SyntaxError, RecursionError) as exc:
        # planner の ContractError は ValueError の派生
        return lines + [f"[WARN] {c['obligation_id']}: check のまま (plan を作れない: {type(exc).__name__}: {exc})"
                        for c in pending]
    records = {item.get("id"): item for item in plan.get("obligations", []) if isinstance(item, dict)}
    with tempfile.TemporaryDirectory(prefix="derive-step4-") as tmp:
        plan_path = Path(tmp) / "plan.json"
        plan_path.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
        for candidate in pending:
            oid = candidate["obligation_id"]
            record = records.get(oid) or {}
            if (record.get("action"), record.get("reason")) != ("check", "machine-proof-missing"):
                # 今の receipt (PASS・FAIL・矛盾) があるか、依存で止まっている。どれも上書きしない
                lines.append(f"[INFO] {oid}: receipt を書かない (planner の action={record.get('action')!r})")
                continue
            checker_argv = (record.get("checker") or {}).get("argv")
            if not isinstance(checker_argv, list) or not checker_argv or not all(isinstance(a, str) for a in checker_argv):
                lines.append(f"[WARN] {oid}: check のまま (plan の checker.argv が文字列の配列でない)")
                continue
            try:
                checker_rc, checker_tail = _run_checker(checker_argv, repo_root)
            except (OSError, subprocess.SubprocessError) as exc:
                lines.append(f"[WARN] {oid}: check のまま (checker を起動できない: {type(exc).__name__}: {exc})")
                continue
            if checker_rc != 0:
                # trace と digest は一致したのに今の検査は通らない。skill dir の外の依存 (pair skill・agents・
                # templates・checker 自身) が Step 4 の後に変わったか、trace の PASS が古い。agent が走らせて直す
                lines.append(f"[INFO] {oid}: receipt を書かない (checker が今 exit {checker_rc}: {checker_tail})")
                continue
            argv = [
                sys.executable, str(record_script), "--plan", str(plan_path), "--obligation-id", oid,
                "--status", "PASS", "--verifier-kind", "deterministic", "--verifier-id", STEP4_VERIFIER_ID,
                "--evidence-path", candidate["trace"][0], "--evidence-dir", str(evidence_dir),
                "--repo-root", str(repo_root), "--keep-existing-non-pass",
                "--note", "Step 4 の trace (lint_target_sha256・lint_brief_sha256・build_mode が今の skill dir・"
                          "brief・mode と一致) を候補にし、contract の checker argv をこの場で走らせて exit 0 を確かめた",
            ]
            try:
                proc = subprocess.run(argv, capture_output=True, text=True, check=False, timeout=RECORD_TIMEOUT_S)
            except (OSError, subprocess.SubprocessError) as exc:
                lines.append(f"[WARN] {oid}: check のまま (record を起動できない: {type(exc).__name__}: {exc})")
                continue
            if proc.returncode == 3:
                # planner が一致から外した (証跡の変わった・壊れた) FAIL 等が同じ名前で残っている。上書きしない
                lines.append(f"[INFO] {oid}: receipt を書かない (既存の receipt が PASS でない: {proc.stderr.strip()})")
                continue
            if proc.returncode != 0:
                lines.append(f"[WARN] {oid}: check のまま (record が exit {proc.returncode}: {proc.stderr.strip()})")
                continue
            lines.append(f"[INFO] {oid}: checker が今 exit 0 なので receipt にした: {proc.stdout.strip()}")
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--subject")
    parser.add_argument("--unit-manifest", help="JSON: {subject?, units:[{build_plan,skill_dir,brief,id?,mode?,trace?}]} ")
    parser.add_argument("--build-plan")
    parser.add_argument("--skill-dir")
    parser.add_argument("--brief")
    parser.add_argument("--mode", help="create|update。省略時は trace の build_mode、無ければ create")
    parser.add_argument("--trace", help=f"build trace（省略時は {DEFAULT_TRACE} を、skill_name が一致するときだけ使う）")
    parser.add_argument("--out")
    parser.add_argument(
        "--evidence-dir",
        help="planner と同じ receipt の置き場。付けると、Step 4 の lint PASS が今の skill dir・brief・mode と"
             "一致する unit だけ build-conformance の receipt を書く（contract は変わらない）",
    )
    args = parser.parse_args(argv)
    try:
        repo_root = Path(args.repo_root).resolve()
        if args.unit_manifest:
            if args.mode is not None or args.trace is not None:
                raise ValueError("--mode と --trace は単発の引数用。--unit-manifest では各 unit の mode・trace に書く")
            manifest = json.loads(Path(args.unit_manifest).read_text(encoding="utf-8"))
            if not isinstance(manifest, dict):
                raise ValueError(f"unit manifest が object でない: {type(manifest).__name__}")
            units = manifest.get("units") or []
            if not isinstance(units, list):
                raise ValueError(f"unit manifest の units が配列でない: {type(units).__name__}")
            manifest_subject = manifest.get("subject")
            if manifest_subject is not None and not isinstance(manifest_subject, str):
                raise ValueError(f"unit manifest の subject が文字列でない: {type(manifest_subject).__name__}")
            subject = args.subject or manifest_subject or ""
        else:
            if not all((args.build_plan, args.skill_dir, args.brief)):
                raise ValueError("provide --unit-manifest or all of --build-plan --skill-dir --brief")
            unit = {"build_plan": args.build_plan, "skill_dir": args.skill_dir, "brief": args.brief}
            if args.mode is not None:
                unit["mode"] = args.mode
            if args.trace is not None:
                unit["trace"] = args.trace
            units = [unit]
            subject = args.subject or _unit_id(_repo_rel(repo_root, args.skill_dir))
        if not subject:
            raise ValueError("subject is required")
        contract, candidates = _derive(units, repo_root, subject)
        rendered = json.dumps(contract, ensure_ascii=False, indent=2) + "\n"
        if args.out:
            out = Path(args.out)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(rendered, encoding="utf-8")
    except (OSError, ValueError, RecursionError) as exc:
        # ValueError は JSONDecodeError・UnicodeDecodeError と形の不正を含む。RecursionError は深い入れ子の JSON
        print(f"[ERROR] {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    if args.evidence_dir:
        for line in record_step4_receipts(contract, candidates, repo_root, Path(args.evidence_dir).resolve()):
            print(line, file=sys.stderr)
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
