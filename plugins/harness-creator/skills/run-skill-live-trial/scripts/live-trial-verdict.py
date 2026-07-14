#!/usr/bin/env python3
# /// script
# name: live-trial-verdict
# purpose: trial 成果 (transcript/成果物/判定入力) を回収し、schema 自己検証済みの live-trial verdict.json を生成する。
# inputs:
#   - argv: --workdir --target-skill --skill-dir --launch --completion --goal-result ほか (下記 usage)
#   - env: CLAUDE_PROJECTS_DIR ($HOME/.claude/projects)
# outputs:
#   - stdout: verdict 要約 + 書出パス
#   - exit: 0=生成成功 / 1=schema 不適合・回収失敗 / 2=usage・denylist
# contexts: [C, E]
# network: false
# write-scope: --workdir 配下のみ (transcript.jsonl / verdict.json)
# dependencies: []
# requires-python: ">=3.10"
# ///
"""live-trial の runtime-evidence 契約 (D10) を機械生成する。

- transcript 回収: ~/.claude/projects/*/<session-id>.jsonl → workdir/transcript.jsonl
- actual_model 抽出: transcript を json.loads ループで走査 (旧 AG 版の jq 代替) し
  assistant.message.model の unique 集合を得る。proof trial の唯一の実走 model 証明。
- skill_dir_tree_sha: 被験 skill の挙動閉包 (SKILL/scripts/prompts/宣言 refs と
  plugin manifest/hooks) の複合 sha256 (repo 相対パス + 内容)。
- 生成した verdict は同梱 schemas/live-trial-verdict.schema.json で自己検証してから
  書き出す (required / enum / additionalProperties false / pattern)。
- 被験 skill denylist (再帰遮断) は backend.deny_target_skill が正本。
"""
from __future__ import annotations

import argparse
import csv
import glob as globmod
import hashlib
import importlib.util
import json
import os
import re
import shutil
import sys
from pathlib import Path


def _load_sibling(stem: str):
    path = Path(__file__).resolve().parent / f"{stem}.py"
    spec = importlib.util.spec_from_file_location(stem.replace("-", "_"), path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _schema_path() -> Path:
    return Path(__file__).resolve().parent.parent / "schemas" / "live-trial-verdict.schema.json"


def find_transcript(projects_dir: str, session_id: str) -> Path | None:
    for p in globmod.glob(os.path.join(projects_dir, "*", f"{session_id}.jsonl")):
        if Path(p).is_file():
            return Path(p)
    return None


def iter_transcript(path: Path):
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            yield obj


def extract_models(path: Path) -> list[str]:
    models: set[str] = set()
    for obj in iter_transcript(path):
        if obj.get("type") == "assistant":
            model = (obj.get("message") or {}).get("model")
            if isinstance(model, str) and model:
                models.add(model)
    return sorted(models)


def extract_claude_version(path: Path) -> str | None:
    for obj in iter_transcript(path):
        ver = obj.get("version")
        if isinstance(ver, str) and ver:
            return ver
    return None


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


_BEHAVIOR_REF_KEYS = (
    "script_refs",
    "reference_refs",
    "responsibility_refs",
    "schema_refs",
)


def _frontmatter(text: str) -> str:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return ""
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return "\n".join(lines[1:index])
    raise ValueError("SKILL.md frontmatter is not terminated")


def _clean_yaml_scalar(value: str) -> str:
    value = value.split(" #", 1)[0].strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    return value.strip()


def _frontmatter_refs(skill_md: Path) -> list[str]:
    """Extract path-like *_refs without adding a PyYAML runtime dependency."""
    lines = _frontmatter(skill_md.read_text(encoding="utf-8")).splitlines()
    refs: list[str] = []
    for index, line in enumerate(lines):
        match = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if not match or match.group(1) not in _BEHAVIOR_REF_KEYS:
            continue
        value = match.group(2).strip()
        if value.startswith("["):
            if not value.endswith("]"):
                raise ValueError(f"unsupported multiline flow list: {match.group(1)}")
            body = value[1:-1].strip()
            if body:
                refs.extend(
                    _clean_yaml_scalar(item)
                    for item in next(csv.reader([body], skipinitialspace=True))
                    if _clean_yaml_scalar(item)
                )
            continue
        if value:
            refs.append(_clean_yaml_scalar(value))
            continue
        for child in lines[index + 1:]:
            if child and not child[0].isspace():
                break
            item = re.match(r"^\s+-\s+(.+?)\s*$", child)
            if item:
                cleaned = _clean_yaml_scalar(item.group(1))
                if cleaned:
                    refs.append(cleaned)
    return refs


def _plugin_context(skill_dir: Path) -> tuple[Path, Path] | None:
    """Return (repo root, plugin root) only for a canonical plugins/<name>/skills path."""
    for candidate in (skill_dir, *skill_dir.parents):
        if candidate.parent.name != "plugins":
            continue
        manifest = candidate / ".claude-plugin" / "plugin.json"
        if manifest.is_file():
            return candidate.parent.parent.resolve(), candidate.resolve()
    return None


def _read_package_contract(
    plugin_root: Path, skill_name: str,
) -> tuple[Path | None, tuple[str, ...]]:
    """Read and validate package dependencies, narrowed for one target skill.

    The package-level ``depends_on`` list is an allow-list.  If
    ``skill_dependencies`` is present, only the mapped subset participates in
    this skill's behavior closure.  Without the map, legacy all-dependency
    behavior is retained.
    """
    path = plugin_root / "references" / "package-contract.json"
    if not path.is_file():
        return None, ()
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"package contract read/parse error: {path}: {exc}") from exc
    depends = doc.get("depends_on", []) if isinstance(doc, dict) else None
    if not isinstance(depends, list) or not all(
        isinstance(item, str) and re.fullmatch(r"[a-z0-9][a-z0-9-]*", item)
        for item in depends
    ):
        raise ValueError(f"package contract depends_on must be plugin slug strings: {path}")
    if len(depends) != len(set(depends)):
        raise ValueError(f"package contract depends_on contains duplicates: {path}")
    scoped = doc.get("skill_dependencies")
    if scoped is None:
        return path, tuple(depends)
    if not isinstance(scoped, dict):
        raise ValueError(f"package contract skill_dependencies must be an object: {path}")
    entries = doc.get("entry_points", {})
    known_skills = set(entries.get("skills", [])) if isinstance(entries, dict) else set()
    for declared_skill, dependencies in scoped.items():
        if not isinstance(declared_skill, str) or not re.fullmatch(
            r"[a-z0-9][a-z0-9-]*", declared_skill
        ):
            raise ValueError(
                f"package contract skill_dependencies has invalid skill: {declared_skill!r}"
            )
        if known_skills and declared_skill not in known_skills:
            raise ValueError(
                "package contract skill_dependencies references an undeclared entry point: "
                f"{declared_skill}"
            )
        if not isinstance(dependencies, list) or not all(
            isinstance(item, str) and re.fullmatch(r"[a-z0-9][a-z0-9-]*", item)
            for item in dependencies
        ):
            raise ValueError(
                "package contract skill_dependencies values must be plugin slug arrays: "
                f"{declared_skill}"
            )
        if len(dependencies) != len(set(dependencies)):
            raise ValueError(
                f"package contract skill_dependencies contains duplicates: {declared_skill}"
            )
        undeclared = sorted(set(dependencies) - set(depends))
        if undeclared:
            raise ValueError(
                "package contract skill_dependencies must be a subset of depends_on: "
                f"{declared_skill} -> {undeclared}"
            )
    return path, tuple(scoped.get(skill_name, []))


def _contained(path: Path, root: Path, label: str) -> Path:
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise ValueError(f"declared behavior dependency missing: {label}: {path}") from exc
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"declared behavior dependency escapes repository: {label}: {resolved}") from exc
    return resolved


def _manifest_name(plugin_root: Path, expected: str) -> Path:
    manifest_path = plugin_root / ".claude-plugin" / "plugin.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"plugin manifest read/parse error: {manifest_path}: {exc}") from exc
    actual = manifest.get("name") if isinstance(manifest, dict) else None
    if actual != expected:
        raise ValueError(
            f"plugin manifest name mismatch: expected={expected} actual={actual}"
        )
    return manifest_path.resolve()


def _dependency_behavior_contract(plugin_root: Path, expected: str) -> tuple[Path, dict]:
    """Load the harness sidecar that identifies a dependency's behavior surface."""
    path = plugin_root / "references" / "package-contract.json"
    try:
        contract = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(
            f"dependency package contract read/parse error: {path}: {exc}"
        ) from exc
    if not isinstance(contract, dict) or contract.get("plugin_name") != expected:
        actual = contract.get("plugin_name") if isinstance(contract, dict) else None
        raise ValueError(
            "dependency package contract plugin_name mismatch: "
            f"expected={expected} actual={actual}"
        )
    entry_points = contract.get("entry_points")
    if not isinstance(entry_points, dict):
        raise ValueError(f"dependency package contract entry_points missing: {path}")
    for kind in ("skills", "agents", "commands", "hooks"):
        values = entry_points.get(kind, [])
        if not isinstance(values, list) or not all(
            isinstance(item, str) and item for item in values
        ):
            raise ValueError(
                f"dependency package contract entry_points.{kind} must be strings: {path}"
            )
    return path.resolve(), entry_points


def behavior_closure_files(skill_dir: Path) -> list[tuple[str, Path]]:
    """Resolve the declared behavior closure, fail-closed on missing/unsafe refs."""
    skill_dir = Path(skill_dir).resolve()
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        raise ValueError(f"skill dir has no SKILL.md: {skill_dir}")

    context = _plugin_context(skill_dir)
    repo_root, plugin_root = context or (skill_dir, skill_dir)
    files: dict[Path, str] = {}

    def add_file(path: Path, source: str) -> None:
        resolved = _contained(path, repo_root, source)
        if not resolved.is_file():
            raise ValueError(f"behavior dependency is not a file: {source}: {resolved}")
        label = (
            resolved.relative_to(repo_root).as_posix()
            if context else resolved.relative_to(skill_dir).as_posix()
        )
        files.setdefault(resolved, label)

    def add_tree(path: Path, source: str) -> None:
        resolved = _contained(path, repo_root, source)
        if not resolved.is_dir():
            raise ValueError(f"behavior dependency is not a directory: {source}: {resolved}")
        for child in sorted(resolved.rglob("*")):
            child_resolved = _contained(child, repo_root, source)
            if child_resolved.is_dir():
                if child.is_symlink():
                    raise ValueError(
                        f"behavior dependency directory symlink is not allowed: "
                        f"{source}: {child} -> {child_resolved}"
                    )
                continue
            if "__pycache__" in child.parts or child.suffix == ".pyc":
                continue
            add_file(child, source)

    add_file(skill_md, "SKILL.md")
    for dirname in ("scripts", "prompts"):
        directory = skill_dir / dirname
        if directory.is_dir():
            add_tree(directory, dirname)

    contract_path: Path | None = None
    declared_dependencies: tuple[str, ...] = ()
    if context:
        plugin_slug = plugin_root.name
        add_file(_manifest_name(plugin_root, plugin_slug), "native plugin manifest")
        hooks = plugin_root / "hooks"
        if hooks.is_dir():
            add_tree(hooks, "native plugin hooks")
        _contract_path, declared_dependencies = _read_package_contract(
            plugin_root, skill_dir.name
        )
        # Do not hash the raw target package contract.  The selected dependency
        # set below is the behavior-relevant projection; hashing unrelated
        # entry points or another skill's dependency map would invalidate every
        # trial in the plugin.
        # Bind exactly the dependency plugins boot loads for this skill.  A
        # package without skill_dependencies keeps the legacy all-dependency
        # closure; a scoped package avoids unrelated invalidation.
        for dependency in declared_dependencies:
            dep_root = _contained(
                repo_root / "plugins" / dependency, repo_root,
                f"declared plugin dependency {dependency}",
            )
            try:
                dep_root.relative_to(repo_root / "plugins")
            except ValueError as exc:
                raise ValueError(
                    f"declared plugin dependency escapes plugins root: {dependency}"
                ) from exc
            add_file(_manifest_name(dep_root, dependency), f"dependency manifest {dependency}")
            dep_contract, dep_entries = _dependency_behavior_contract(dep_root, dependency)
            add_file(dep_contract, f"dependency package contract {dependency}")
            dep_hooks = dep_root / "hooks"
            if dep_hooks.is_dir():
                add_tree(dep_hooks, f"dependency hooks {dependency}")
            for skill_name in dep_entries.get("skills", []):
                add_tree(
                    dep_root / "skills" / skill_name,
                    f"dependency skill {dependency}:{skill_name}",
                )
            for agent_name in dep_entries.get("agents", []):
                add_file(
                    dep_root / "agents" / f"{agent_name}.md",
                    f"dependency agent {dependency}:{agent_name}",
                )
            for command_name in dep_entries.get("commands", []):
                add_file(
                    dep_root / "commands" / f"{command_name}.md",
                    f"dependency command {dependency}:{command_name}",
                )
            # Shared runtime assets referenced by dependency entry points commonly
            # live at plugin root. Keep tests/docs outside the closure.
            for dirname in ("scripts", "schemas"):
                directory = dep_root / dirname
                if directory.is_dir():
                    add_tree(directory, f"dependency {dirname} {dependency}")

    declared_set = set(declared_dependencies)
    for ref in _frontmatter_refs(skill_md):
        raw = Path(ref)
        if raw.is_absolute():
            raise ValueError(f"declared behavior dependency must be relative: {ref}")
        if ref.startswith("plugins/"):
            candidate = repo_root / ref
        else:
            candidate = skill_dir / ref
        if not candidate.exists() and "/" not in ref and "." not in ref:
            candidate = plugin_root / "skills" / ref / "SKILL.md"
        resolved = _contained(candidate, repo_root, ref)
        if context:
            try:
                relative_plugins = resolved.relative_to(repo_root / "plugins")
            except ValueError:
                relative_plugins = None
            if relative_plugins and relative_plugins.parts:
                referenced_plugin = relative_plugins.parts[0]
                if referenced_plugin not in {plugin_root.name, *declared_set}:
                    raise ValueError(
                        "cross-plugin behavior dependency is not declared in "
                        f"package-contract.depends_on: {referenced_plugin} ({ref})"
                    )
        if resolved.is_dir():
            add_tree(resolved, ref)
        elif resolved.is_file():
            add_file(resolved, ref)
        else:
            raise ValueError(f"unsupported behavior dependency: {ref}: {resolved}")

    return sorted(((label, path) for path, label in files.items()), key=lambda item: item[0])


def skill_dir_tree_sha(skill_dir: Path) -> str:
    """Declared behavior closure digest (legacy field name retained for compatibility)."""
    h = hashlib.sha256()
    for label, path in behavior_closure_files(skill_dir):
        h.update(label.encode("utf-8"))
        h.update(b"\0")
        h.update(path.read_bytes())
        h.update(b"\0")
    return h.hexdigest()


def derive_overall(*, launch: str, completion: str, goal_result: str | None,
                   nudge: int, gate: int, proof: bool,
                   requested_model: str, actual_model: list[str],
                   blocked: bool) -> tuple[str, str, str | None]:
    """判定ロジック表 (SKILL.md) の機械実装。returns (goal_fit, verdict, downgrade_reason)。"""
    goal_fit = goal_result if goal_result else "NOT_EVALUATED"
    if blocked:
        return goal_fit, "BLOCKED", "tmux 不在 / HARD_CAP 超過等の fail-closed"
    if launch == "FAIL":
        return goal_fit, "FAIL", None
    if completion == "FAIL":
        return goal_fit, "FAIL", None
    if proof and actual_model != [requested_model]:
        return goal_fit, "FAIL", (
            f"proof trial: actual_model {actual_model} != requested_model "
            f"[{requested_model}] (transcript 機械 gate)"
        )
    degrade: list[str] = []
    if goal_fit == "FAIL":
        degrade.append("goal-proxy 乖離 (完走するが目的を果たさない)")
    if nudge > 0 or gate > 0:
        degrade.append(f"自走未達 (nudge={nudge} gate応答={gate} — 自動送信でも介入)")
    if degrade:
        reason = " / ".join(degrade)
        # proof trial は「人手介入なし PASS」が受け入れ条件 — ⚠️ 相当も不合格
        return goal_fit, ("FAIL" if proof else "DEGRADED"), reason
    if goal_fit == "NOT_EVALUATED":
        return goal_fit, "DEGRADED", "goal 判定未実施 (fresh evaluator 未起動)"
    return goal_fit, "PASS", None


def validate_schema(doc, schema, path: str = "$") -> list[str]:
    """同梱 schema 用の最小 validator (type/enum/required/properties/additionalProperties/items/pattern/minimum/minLength)。"""
    errs: list[str] = []
    types = schema.get("type")
    if types is not None:
        allowed = types if isinstance(types, list) else [types]
        ok = False
        for t in allowed:
            if (
                (t == "object" and isinstance(doc, dict))
                or (t == "array" and isinstance(doc, list))
                or (t == "string" and isinstance(doc, str))
                or (t == "integer" and isinstance(doc, int) and not isinstance(doc, bool))
                or (t == "number" and isinstance(doc, (int, float)) and not isinstance(doc, bool))
                or (t == "boolean" and isinstance(doc, bool))
                or (t == "null" and doc is None)
            ):
                ok = True
        if not ok:
            return [f"{path}: type {allowed} 不一致 (got {type(doc).__name__})"]
    if "enum" in schema and doc not in schema["enum"]:
        return [f"{path}: enum {schema['enum']} 外の値 {doc!r}"]
    if isinstance(doc, str):
        if "pattern" in schema and not re.search(schema["pattern"], doc):
            errs.append(f"{path}: pattern {schema['pattern']} 不一致")
        if "minLength" in schema and len(doc) < schema["minLength"]:
            errs.append(f"{path}: minLength {schema['minLength']} 未満")
    if isinstance(doc, int) and not isinstance(doc, bool) and "minimum" in schema:
        if doc < schema["minimum"]:
            errs.append(f"{path}: minimum {schema['minimum']} 未満")
    if isinstance(doc, dict):
        props = schema.get("properties", {})
        for key in schema.get("required", []):
            if key not in doc:
                errs.append(f"{path}: required key '{key}' 欠落")
        if schema.get("additionalProperties") is False:
            for key in doc:
                if key not in props:
                    errs.append(f"{path}: additionalProperties false 違反 '{key}'")
        for key, sub in props.items():
            if key in doc:
                errs.extend(validate_schema(doc[key], sub, f"{path}.{key}"))
    if isinstance(doc, list) and "items" in schema:
        for i, item in enumerate(doc):
            errs.extend(validate_schema(item, schema["items"], f"{path}[{i}]"))
    return errs


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--workdir", required=True, help="eval-log/<plugin>/<skill>/live-trial/<run-id>/")
    ap.add_argument("--target-skill", required=True, help="plugin:skill")
    ap.add_argument("--skill-dir", required=True, help="被験 skill のディレクトリ (tree sha 対象)")
    ap.add_argument("--args", default="", dest="trial_args")
    ap.add_argument("--requested-model", default="")
    ap.add_argument("--session-id", default="", help="transcript 回収用 UUID")
    ap.add_argument("--transcript", default="", help="回収済み transcript のパス (session-id 探索より優先)")
    ap.add_argument("--launch", required=True, choices=["PASS", "FAIL"])
    ap.add_argument("--completion", required=True, choices=["PASS", "FAIL"])
    ap.add_argument("--goal-result", default="", choices=["", "PASS", "FAIL"],
                    help="fresh evaluator の達成判定。未実施は省略 (--no-goal-eval 相当)")
    ap.add_argument("--blocker", action="append", default=[], help="goal 未達点 (複数可)")
    ap.add_argument("--nudge-count", type=int, default=0)
    ap.add_argument("--gate-response-count", type=int, default=0)
    ap.add_argument("--proof", action="store_true", help="proof trial (model 一致の機械 gate を厳格適用)")
    ap.add_argument("--blocked", action="store_true", help="tmux 不在 / HARD_CAP 超過等の fail-closed 記録")
    ap.add_argument("--scenario-origin", default="synthetic", choices=["synthetic", "replay"])
    ap.add_argument("--scenario-id", default="",
                    help="criteria receipt と実走を束縛する stable scenario id (任意)")
    ap.add_argument("--tier", default="live", choices=["static", "fork", "live"])
    ap.add_argument("--downgrade-reason", default="")
    ap.add_argument("--permissions-mode", default="bypassPermissions")
    ap.add_argument("--boot-s", type=float, default=None)
    ap.add_argument("--poll-exit", default="")
    ap.add_argument("--wall-clock-s", type=float, default=None)
    ns = ap.parse_args(argv)

    backend = _load_sibling("live-trial-backend")
    if backend.deny_target_skill(ns.target_skill):
        print(f"[ERROR] DENYLIST: 被験 skill {ns.target_skill} は再帰遮断対象 "
              f"({sorted(backend.DENY_TARGET_SKILLS)})", file=sys.stderr)
        return 2

    workdir = Path(ns.workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    skill_dir = Path(ns.skill_dir)
    if not (skill_dir / "SKILL.md").is_file():
        print(f"[ERROR] skill dir に SKILL.md がない: {skill_dir}", file=sys.stderr)
        return 1

    # transcript 回収 (一次証拠)
    projects_dir = os.environ.get(
        "CLAUDE_PROJECTS_DIR", str(Path.home() / ".claude" / "projects")
    )
    src: Path | None = Path(ns.transcript) if ns.transcript else None
    if src is None and ns.session_id:
        src = find_transcript(projects_dir, ns.session_id)
    transcript_dst: Path | None = None
    if src is not None and src.is_file():
        transcript_dst = workdir / "transcript.jsonl"
        if src.resolve() != transcript_dst.resolve():
            shutil.copyfile(src, transcript_dst)

    actual_model = extract_models(transcript_dst) if transcript_dst else []
    claude_version = extract_claude_version(transcript_dst) if transcript_dst else None
    transcript_sha = sha256_file(transcript_dst) if transcript_dst else None
    transcript_layer = "jsonl" if transcript_dst else "tui"

    goal_result = ns.goal_result or None
    blockers = list(ns.blocker)
    if goal_result is None and not blockers:
        blockers = ["goal 判定未実施 (trial が完走せず fresh evaluator を起動できない)"]
    goal_fit, verdict, auto_reason = derive_overall(
        launch=ns.launch, completion=ns.completion, goal_result=goal_result,
        nudge=ns.nudge_count, gate=ns.gate_response_count, proof=ns.proof,
        requested_model=ns.requested_model, actual_model=actual_model,
        blocked=ns.blocked,
    )
    doc = {
        "target_skill": ns.target_skill,
        "args": ns.trial_args,
        "requested_model": ns.requested_model,
        "actual_model": actual_model,
        "nudge_count": ns.nudge_count,
        "gate_response_count": ns.gate_response_count,
        "goal_verdict": {
            "result": goal_result or "FAIL",
            "blockers": blockers,
        },
        "overall": {
            "launch": ns.launch,
            "completion": ns.completion,
            "goal_fit": goal_fit,
            "verdict": verdict,
        },
        "skill_dir_tree_sha": skill_dir_tree_sha(skill_dir),
        "transcript_sha256": transcript_sha,
        "scenario_origin": ns.scenario_origin,
        "environment": {
            "claude_version": claude_version,
            "tmux": backend.tmux_available(),
            "transcript_layer": transcript_layer,
            "permissions_mode": ns.permissions_mode,
        },
        "tier": ns.tier,
        "downgrade_reason": ns.downgrade_reason or auto_reason,
        "timeline": {
            "boot_s": ns.boot_s,
            "poll_exit": ns.poll_exit or None,
            "wall_clock_s": ns.wall_clock_s,
        },
    }
    if ns.scenario_id:
        doc["scenario_id"] = ns.scenario_id

    schema = json.loads(_schema_path().read_text(encoding="utf-8"))
    errs = validate_schema(doc, schema)
    if errs:
        print("[ERROR] verdict が schema 不適合 (書き出し中止):", file=sys.stderr)
        for e in errs:
            print(f"  - {e}", file=sys.stderr)
        return 1

    out = workdir / "verdict.json"
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"VERDICT: {doc['overall']['verdict']} (launch={ns.launch} completion={ns.completion} "
          f"goal_fit={goal_fit} nudge={ns.nudge_count} gate={ns.gate_response_count})")
    print(f"WROTE: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
