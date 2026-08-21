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


# live-trial-status.GATE_TOOLS と同一。gate を上げる能力の frontmatter 宣言。
CONTRACT_GATE_TOOLS = ("AskUserQuestion", "ExitPlanMode")


def contract_gate_evidence(skill_md: Path) -> list[str]:
    """被験 skill が契約上の確認 gate を宣言している決定論的根拠を返す。

    ``--gate-kind contractual`` は「この gate 応答は受け入れ条件そのものだから
    降格根拠にならない」という主張だが、申告するのは trial を回す当人である。
    無検証で信じると、実際は stall 救済だった介入を contractual と言い換える
    だけで DEGRADED を PASS へ反転できる (受け入れ基準の自己申告による緩和)。
    そこで主張を被験 skill 側の宣言へ接地させ、根拠が 1 つも無い contractual は
    fail-closed で拒否する。

    根拠として認めるのは frontmatter の機械可読な宣言 2 種だけ:
    - ``external_mutation_guard``: 外部 mutation の人間確認 flow を宣言している
    - ``allowed-tools`` の ``AskUserQuestion`` / ``ExitPlanMode``

    本文の散文は根拠にしない。書き足すだけで主張が通るなら接地にならない。
    """
    lines = _frontmatter(skill_md.read_text(encoding="utf-8")).splitlines()
    evidence: list[str] = []
    for index, line in enumerate(lines):
        match = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if not match:
            continue
        key, value = match.group(1), match.group(2)
        if key == "external_mutation_guard" and value.strip():
            evidence.append("frontmatter.external_mutation_guard")
            continue
        if key != "allowed-tools":
            continue
        block = [value]
        for child in lines[index + 1:]:
            if child and not child[0].isspace():
                break
            block.append(child)
        joined = "\n".join(block)
        evidence.extend(
            f"frontmatter.allowed-tools:{tool}"
            for tool in CONTRACT_GATE_TOOLS
            if re.search(rf"\b{tool}\b", joined)
        )
    return sorted(set(evidence))


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


def _manifest_dependency_slugs(plugin_root: Path, expected: str) -> tuple[str, ...]:
    """Return the manifest ``dependencies`` boot pins into argv.

    ホストは未解決依存を持つ plugin を登録しないため、この集合は skill 単位へ
    narrowing できず、live-trial-boot は必ず ``--plugin-dir`` へ載せる
    (``_merge_dependency_slugs`` の union)。closure がこれを外すと、trial に
    実在して挙動へ効く plugin (hooks を出荷する dependency を含む) の変更が
    verdict を stale にせず、変更後も古い PASS が再利用される。
    「load される集合」と「digest される集合」は同一でなければならない。
    """
    manifest_path = plugin_root / ".claude-plugin" / "plugin.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"plugin manifest read/parse error: {manifest_path}: {exc}") from exc
    if not isinstance(manifest, dict) or manifest.get("name") != expected:
        actual = manifest.get("name") if isinstance(manifest, dict) else None
        raise ValueError(
            f"plugin manifest name mismatch: expected={expected} actual={actual}"
        )
    dependencies = manifest.get("dependencies", [])
    if not isinstance(dependencies, list) or not all(
        isinstance(item, str) and re.fullmatch(r"[a-z0-9][a-z0-9-]*", item)
        for item in dependencies
    ):
        raise ValueError(
            f"plugin manifest dependencies must be plugin slug strings: {manifest_path}"
        )
    if len(dependencies) != len(set(dependencies)):
        raise ValueError(f"plugin manifest dependencies contains duplicates: {manifest_path}")
    if expected in dependencies:
        raise ValueError(f"plugin manifest dependencies contains self: {manifest_path}")
    return tuple(sorted(dependencies))


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


# closure は「host が load する出荷バイト列」を digest する。ローカルのツール実行が
# 残す一時 cache は load されず出荷もされないが、tree 走査には引っかかる。除外しないと
# 依存 plugin で一度 pytest を回すだけで digest が動き、stale 判定が「テストを実行したか」
# に依存してしまう (CI は clone 直後なので再現せず、ローカルだけ落ちる非対称になる)。
# 除外は deny-list 方式にする。git 問い合わせに落とすと git 非在の runtime で digest が
# 変わり、決定性という closure の存在意義そのものを崩すため。
_EPHEMERAL_DIR_NAMES = frozenset({
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    ".benchmarks",
})
_EPHEMERAL_SUFFIXES = frozenset({".pyc", ".pyo"})
_EPHEMERAL_FILE_NAMES = frozenset({".DS_Store"})


def _is_ephemeral_artifact(path: Path) -> bool:
    """True for tool-generated files that are neither loaded nor shipped."""
    if _EPHEMERAL_DIR_NAMES & set(path.parts):
        return True
    return path.suffix in _EPHEMERAL_SUFFIXES or path.name in _EPHEMERAL_FILE_NAMES


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
            if _is_ephemeral_artifact(child):
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
        _contract_path, contract_dependencies = _read_package_contract(
            plugin_root, skill_dir.name
        )
        # Do not hash the raw target package contract.  The selected dependency
        # set below is the behavior-relevant projection; hashing unrelated
        # entry points or another skill's dependency map would invalidate every
        # trial in the plugin.
        # Bind exactly the dependency plugins boot loads for this skill.  A
        # package without skill_dependencies keeps the legacy all-dependency
        # closure; a scoped package avoids unrelated invalidation.
        # manifest dependencies は skill 単位へ narrowing できず boot が必ず
        # load するため、live-trial-boot._merge_dependency_slugs と同じ union を
        # 取る。closure が load 集合より狭いと、trial に実在する plugin の変更が
        # digest に出ず PASS が stale にならない (検査の素通り)。
        declared_dependencies = tuple(sorted(
            set(_manifest_dependency_slugs(plugin_root, plugin_slug))
            | set(contract_dependencies)
        ))
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
        if not candidate.exists() and context and not ref.startswith("plugins/"):
            # repo-root 配置の共有資産 (doc/notion-schema/*.schema.json など) を
            # skill 相対で書いた ref。run-skill-feedback は SKILL.md 本文で
            # 「repo-bundled 前提」と宣言済みだが、resolver が skill 相対しか
            # 試さないため missing 扱いになり、その 1 件で plan-live-trials が
            # plugin 全体に対して落ちていた。repo_root 内に収まることは
            # _contained() が引き続き保証する。
            repo_candidate = repo_root / ref
            if repo_candidate.exists():
                candidate = repo_candidate
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
                   nudge: int, gate: int, gate_kind: str, proof: bool,
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
    if nudge > 0:
        degrade.append(f"自走未達 (nudge={nudge} — 自動送信でも介入)")
    # gate 応答は 2 種ある。stall を解くための救済介入 (rescue) は自走未達だが、
    # 被験 skill が契約上要求する確認 gate (external mutation の人間確認等) への正規応答
    # (contractual) は、gate を通ること自体が受け入れ条件なので降格根拠にならない。
    # 契約上 gate を必須とする skill を rescue と同じ規則で裁くと、その skill は永久に PASS を
    # 取れない (gate 応答 0 での完走は guard が破れていることを意味する)。
    # ただし proof trial は「人手介入なし PASS」が受け入れ条件なので kind を問わず介入扱い。
    if gate > 0 and (proof or gate_kind != "contractual"):
        note = ("契約 gate だが proof trial は人手介入なしが受け入れ条件"
                if gate_kind == "contractual" else "自動送信でも介入")
        degrade.append(f"自走未達 (gate応答={gate}/{gate_kind} — {note})")
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
    ap.add_argument("--gate-kind", default="rescue", choices=["rescue", "contractual"],
                    help="gate 応答の種別。rescue=stall を解くための救済介入 (既定・降格対象)。"
                         "contractual=被験 skill が契約上要求する確認 gate への正規応答 "
                         "(例: external mutation の人間確認)。未指定は fail-closed に rescue 扱い")
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

    # contractual の申告を被験 skill 側の宣言へ接地させる。gate 応答が 0 なら区分に
    # 意味が無いので rescue へ正規化し、gate 応答があるのに根拠が無い contractual は
    # 受け入れ基準の自己申告による緩和なので fail-closed で拒否する。
    gate_kind = ns.gate_kind
    gate_evidence: list[str] = []
    if ns.gate_response_count == 0:
        gate_kind = "rescue"
    elif gate_kind == "contractual":
        gate_evidence = contract_gate_evidence(skill_dir / "SKILL.md")
        if not gate_evidence:
            print(
                f"[ERROR] --gate-kind contractual だが被験 skill {ns.target_skill} の "
                f"frontmatter に契約 gate の宣言が無い "
                f"(external_mutation_guard / allowed-tools の "
                f"{'|'.join(CONTRACT_GATE_TOOLS)})。"
                "宣言なき contractual は降格回避の自己申告になるため拒否する",
                file=sys.stderr,
            )
            return 2

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
        nudge=ns.nudge_count, gate=ns.gate_response_count,
        gate_kind=gate_kind, proof=ns.proof,
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
        "gate_kind": gate_kind,
        # 免除の根拠を verdict へ焼き付ける。lint と後続 reviewer が「誰の宣言に
        # 接地した contractual か」を verdict 単体で辿れる。
        **({"gate_contract_evidence": gate_evidence} if gate_evidence else {}),
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
          f"goal_fit={goal_fit} nudge={ns.nudge_count} "
          f"gate={ns.gate_response_count}/{gate_kind})")
    print(f"WROTE: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
