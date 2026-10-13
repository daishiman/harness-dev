#!/usr/bin/env python3
# /// script
# name: lint-skill-dep-step7
# purpose: Validate doc/20 Step 7 dependency constraints and command Skill routes for migrated skills.
# inputs:
#   - argv: --skills-dir or skill paths
# outputs:
#   - stdout: OK status
#   - stderr: dependency constraint findings
#   - exit: 0=PASS / 1=findings / 2=usage error or the canonical external-workflow checker cannot be loaded
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.9"
# ///
"""doc/20-migration-path.md Step 7「依存関係を lint する」の5条件と、command の Skill 経路を機械検証する。

検査対象:
  (1) wrap-* に base: フィールドがある
  (2) assign-*-evaluator に pair: フィールドがある
  (3) pair: の相手スキルが plugins/*/skills か .claude/skills に存在する
  (4) dangerous run-* に disable-model-invocation: true がある
      ("dangerous" の判定は frontmatter に danger: true / effect: external-mutation
       のいずれかを持つこと)。例外として、正規の外部変更 workflow を
      root の scripts/lint-entrypoint-artifact-first.py (lint_guarded_external_entrypoint)
      で確かめられた skill は、disable-model-invocation: false でも許す。
  (5) ref-* が disable-model-invocation: true で到達不能になっていない
      (ref-* は model から explicit に呼ばれる必要があるため、user-invocable: false
       かつ disable-model-invocation: true は到達不能)
  (6) allowed-tools に Skill を含む command (skills dir の隣の commands/*.md) が呼ぶ run-* が
      実在し、モデルから起動できる (disable-model-invocation: true でない)。
      呼び先は `Skill(name` と、バッククォートで囲んだ run-* の名前 (`plugin:` の prefix 付きも可)。
      prefix 付きは plugins/<plugin>/skills を、prefix なしは同じ plugin、無ければ
      plugins/*/skills と .claude/skills を探す。表の行は、Skill と書いた行だけを
      呼び出しの表として扱う (依存や参照を並べた表を呼び出しと取り違えない)。

frontmatter は簡易に読む。先頭の `---` 行から次の `---` だけの行までを frontmatter とし
(値の途中の `---` では切らない。先頭の BOM は読み飛ばす)、引用符の外の行末コメント (空白 + #) は値に含めない。
danger は true / yes / on を真とみなす (YAML 1.1 の真偽値。危険側に倒す)。

この lint 自身は Python 3.9+ 標準ライブラリのみ (設計書22 no-deps 原則)。ただし (4) の例外を
確かめる正規の checker は PyYAML と jsonschema を使う。それらが無い環境では、例外を確かめられない
ことを理由つきで stderr に出して exit 2 にする (違反と取り違えて exit 1 にしない。黙って PASS にもしない)。

exit: 0=全条件 PASS / 1=違反あり / 2=usage エラー、または (4) の例外を確かめられない

Usage:
  lint-skill-dep-step7.py --skills-dir plugins/harness-creator/skills [--allow-partial]
  lint-skill-dep-step7.py /path/to/SKILL.md ...
"""
from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path

# (4) の例外を確かめる正規の checker (lint-entrypoint-artifact-first.py と、それが読み込む
# build-artifact-delivery.py) が import する標準ライブラリ外の module。
_CHECKER_DEPENDENCIES = ("yaml", "jsonschema")
_CHECKERS: dict[Path, object] = {}

_SKILL_CALL_RE = re.compile(r"Skill\(\s*(?:([a-z0-9-]+):)?(run-[a-z0-9-]+)")
_BACKTICK_RUN_RE = re.compile(r"`(?:([a-z0-9-]+):)?(run-[a-z0-9-]+)`")


class CheckerUnavailable(RuntimeError):
    """正規の checker を読み込めず、(4) の例外を確かめられない (違反とは区別する)。"""


# danger の真値。YAML 1.1 では yes / on も真になるので、危険側に倒して真とみなす。
_TRUTHY = {"true", "yes", "on"}


def _fm_block(text: str) -> str | None:
    """先頭の `---` 行から次の `---` だけの行までの本文を返す。frontmatter が無ければ None。

    値の途中に `---` があっても切らないよう、`---` だけの行を区切りとして数える。先頭の BOM は読み飛ばす。
    """
    lines = text.lstrip("\ufeff").splitlines()
    if not lines or lines[0].rstrip() != "---":
        return None
    for index in range(1, len(lines)):
        if lines[index].rstrip() == "---":
            return "\n".join(lines[1:index])
    return None


def _strip_comment(value: str) -> str:
    """引用符の外にある行末コメント (行頭か空白の直後の #) を除く。

    `effect: external-mutation  # 理由` を external-mutation と読めないと、(4) の危険判定から漏れる。
    引用符は値や flow list の要素の先頭にあるときだけ数える (Claude's のような語中の ' は引用符でない)。
    """
    quote = None
    i = 0
    while i < len(value):
        ch = value[i]
        if quote:
            if quote == '"' and ch == "\\":
                i += 1
            elif ch == quote:
                if quote == "'" and value[i + 1:i + 2] == "'":
                    i += 1  # '' は単引用符の中の ' そのもの
                else:
                    quote = None
        elif ch in "'\"" and (i == 0 or value[i - 1] in " \t[,"):
            quote = ch
        elif ch == "#" and (i == 0 or value[i - 1] in " \t"):
            return value[:i].rstrip()
        i += 1
    return value.rstrip()


def _scalar(value: str) -> str:
    return _strip_comment(value.strip()).strip().strip('"').strip("'")


def parse_fm(text: str) -> dict:
    """簡易 YAML frontmatter パーサ。scalar のみ対応で十分。"""
    block = _fm_block(text)
    if block is None:
        return {}
    fm: dict = {}
    for raw in block.splitlines():
        line = raw.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        m = re.match(r"^([a-zA-Z_-]+):\s*(.*)$", line)
        if m:
            fm[m.group(1)] = _scalar(m.group(2))
    return fm


def _fm_list(text: str, key: str) -> list[str]:
    """frontmatter の key を、カンマ区切りの scalar・flow list・block list のどれでも要素の列で返す。"""
    block = _fm_block(text)
    if block is None:
        return []
    lines = block.splitlines()
    for index, raw in enumerate(lines):
        m = re.match(rf"^{re.escape(key)}:\s*(.*)$", raw.rstrip())
        if not m:
            continue
        value = _strip_comment(m.group(1).strip())
        if value:
            value = value[1:-1] if value.startswith("[") and value.endswith("]") else value
            return [item.strip().strip('"').strip("'") for item in value.split(",") if item.strip()]
        items = []
        for follow in lines[index + 1:]:
            item = re.match(r"^\s+-\s+(.+?)\s*$", follow)
            if item:
                value = _scalar(item.group(1))
                if value:
                    items.append(value)
            elif follow.strip() and not follow.lstrip().startswith("#"):
                break
        return items
    return []


def _repo_root(p: Path) -> Path:
    cur = p.resolve()
    for parent in [cur, *cur.parents]:
        if (parent / ".git").exists():
            return parent
    return cur.parent


def skill_exists(name: str, repo: Path) -> bool:
    if (repo / ".claude" / "skills" / name).is_dir():
        return True
    return any(path.is_dir() for path in (repo / "plugins").glob(f"*/skills/{name}"))


def _load_checker(checker: Path):
    """正規の checker を1回だけ読み込む。読み込めないときは CheckerUnavailable。"""
    key = checker.resolve()
    if key in _CHECKERS:
        return _CHECKERS[key]
    missing = [name for name in _CHECKER_DEPENDENCIES if importlib.util.find_spec(name) is None]
    if missing:
        raise CheckerUnavailable(
            f"{checker} needs {', '.join(missing)} (not installed for {sys.executable})"
        )
    spec = importlib.util.spec_from_file_location(f"_step7_artifact_first_{len(_CHECKERS)}", checker)
    if spec is None or spec.loader is None:
        raise CheckerUnavailable(f"cannot load {checker}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as exc:  # 構文エラーや import 失敗は「確かめられない」として表に出す
        sys.modules.pop(spec.name, None)
        raise CheckerUnavailable(f"cannot import {checker}: {type(exc).__name__}: {exc}") from exc
    if not callable(getattr(module, "lint_guarded_external_entrypoint", None)):
        raise CheckerUnavailable(f"{checker} has no lint_guarded_external_entrypoint")
    _CHECKERS[key] = module
    return module


def _guarded_external_workflow(skill_md: Path, repo: Path) -> bool:
    """Share the canonical delivery checker; a missing checker never grants access.

    checker のファイルが無い repo では例外を認めない (False)。checker はあるのに読み込めない
    (依存 module が無いなど) ときは CheckerUnavailable を投げ、呼び出し側が exit 2 で理由を出す。
    """
    checker = repo / "scripts/lint-entrypoint-artifact-first.py"
    if not checker.is_file():
        return False
    module = _load_checker(checker)
    return not module.lint_guarded_external_entrypoint(skill_md)


def _command_targets(text: str) -> set[tuple[str | None, str]]:
    """command 本文から Skill の呼び先 (plugin prefix, run-* 名) を集める。"""
    targets: set[tuple[str | None, str]] = set()
    for line in text.splitlines():
        targets.update(_SKILL_CALL_RE.findall(line))
        if line.lstrip().startswith("|") and "Skill" not in line:
            continue  # 依存や参照を並べた表の行は呼び出しではない
        targets.update(_BACKTICK_RUN_RE.findall(line))
    return {(prefix or None, name) for prefix, name in targets}


def _target_candidates(prefix: str | None, name: str, skills_dir: Path, repo: Path) -> list[Path]:
    if prefix:
        return [path for path in [repo / "plugins" / prefix / "skills" / name / "SKILL.md"] if path.is_file()]
    local = skills_dir / name / "SKILL.md"
    if local.is_file():
        return [local]
    found = sorted(path for path in (repo / "plugins").glob(f"*/skills/{name}/SKILL.md") if path.is_file())
    claude = repo / ".claude" / "skills" / name / "SKILL.md"
    return found + ([claude] if claude.is_file() else [])


def check_command_routes(skills_dir: Path) -> list[str]:
    """A command using Skill must route to an existing, model-invocable target."""
    errors = []
    repo = _repo_root(skills_dir)
    for command in sorted((skills_dir.parent / "commands").glob("*.md")):
        try:
            text = command.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            errors.append(f"{command.name}: cannot read command as UTF-8 ({type(exc).__name__})")
            continue
        tools = _fm_list(text, "allowed-tools")
        if not any(tool == "Skill" or tool.startswith("Skill(") for tool in tools):
            continue
        for prefix, name in sorted(_command_targets(text), key=lambda item: (item[1], item[0] or "")):
            label = f"{prefix}:{name}" if prefix else name
            candidates = _target_candidates(prefix, name, skills_dir, repo)
            if not candidates:
                errors.append(f"{command.name}: Skill target {label} does not exist")
                continue
            try:
                invocable = [
                    path for path in candidates
                    if parse_fm(path.read_text(encoding="utf-8")).get("disable-model-invocation", "false").lower() != "true"
                ]
            except (OSError, UnicodeDecodeError) as exc:
                errors.append(f"{command.name}: cannot read Skill target {label} ({type(exc).__name__})")
                continue
            if not invocable:
                errors.append(f"{command.name}: Skill target {label} rejects model invocation")
    return errors


def _collect_inbound_refs(repo: Path) -> set[str]:
    """全 SKILL.md を走査し、reference_refs / script_refs / rubric_refs に
    現れるスキル名 (ref-/run-/assign-/wrap-/delegate-) の集合を返す。
    Step 7-5 の到達可能性判定で、disable-model-invocation=true かつ
    user-invocable=false の ref-* でも、他スキルから参照されていれば到達可能とみなす。
    """
    inbound: set[str] = set()
    skill_name_re = re.compile(r"(ref|run|assign|wrap|delegate)-[a-z0-9-]+")
    skills_roots = [repo / ".claude" / "skills"]
    skills_roots.extend((repo / "plugins").glob("*/skills"))
    for skills_root in skills_roots:
        if not skills_root.is_dir():
            continue
        for skill_md in skills_root.glob("*/SKILL.md"):
            try:
                txt = skill_md.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            # frontmatter 内の list 値全てを対象に走査 (コメントに書いた名前は参照に数えない)
            fm_block = _fm_block(txt)
            if fm_block is None:
                continue
            current_key: str | None = None
            for raw in fm_block.splitlines():
                line = raw.rstrip()
                m_kv = re.match(r"^([a-zA-Z_-]+):\s*(.*)$", line)
                if m_kv:
                    current_key = m_kv.group(1)
                    val = _strip_comment(m_kv.group(2).strip())
                    if current_key in {"reference_refs", "script_refs", "rubric_refs"} and val:
                        for m in skill_name_re.finditer(val):
                            inbound.add(m.group(0))
                m_item = re.match(r"^\s+-\s+(.+?)\s*$", line)
                if m_item and current_key in {"reference_refs", "script_refs", "rubric_refs"}:
                    for m in skill_name_re.finditer(_strip_comment(m_item.group(1))):
                        inbound.add(m.group(0))
    return inbound


def check_skill(
    skill_md: Path,
    inbound_refs: set[str] | None = None,
    allow_partial: bool = False,
) -> list[str]:
    fm = parse_fm(skill_md.read_text(encoding="utf-8"))
    name = fm.get("name", skill_md.parent.name)
    errs: list[str] = []
    repo = _repo_root(skill_md)
    if inbound_refs is None:
        inbound_refs = _collect_inbound_refs(repo)

    # (1) wrap-* に base: があるか
    if name.startswith("wrap-"):
        if not fm.get("base"):
            if not allow_partial:
                errs.append(f"{name}: wrap-* requires 'base:' field (doc/20 Step 7-1)")

    # (2) assign-*-evaluator に pair: があるか
    if name.startswith("assign-") and name.endswith("-evaluator"):
        if not fm.get("pair"):
            if not allow_partial:
                errs.append(
                    f"{name}: assign-*-evaluator requires 'pair:' field (doc/20 Step 7-2)"
                )

    # (3) pair: の相手スキルが存在するか
    pair = fm.get("pair", "")
    if pair and not skill_exists(pair, repo):
        errs.append(
            f"{name}: pair target '{pair}' not found under "
            f"plugins/*/skills or .claude/skills (doc/20 Step 7-3)"
        )

    # (4) dangerous run-* に disable-model-invocation: true があるか
    if name.startswith("run-"):
        danger = fm.get("danger", "false").lower() in _TRUTHY
        effect = fm.get("effect", "")
        is_dangerous = danger or effect == "external-mutation"
        dmi = fm.get("disable-model-invocation", "false").lower() == "true"
        if is_dangerous and not dmi and not _guarded_external_workflow(skill_md, repo):
            errs.append(
                f"{name}: dangerous run-* (danger/effect=external-mutation) "
                f"requires disable-model-invocation: true or a verified canonical external-mutation workflow (doc/20 Step 7-4)"
            )

    # (5) ref-* が到達不能になっていないか
    # 到達経路: (a) model自律呼び出し  (b) user-invocable slash command
    # (c) 他スキルの reference_refs/script_refs/rubric_refs からの参照
    # (a)(b)を両方無効にしても、(c)があれば到達可能とみなす。
    if name.startswith("ref-"):
        dmi = fm.get("disable-model-invocation", "false").lower() == "true"
        ui_false = fm.get("user-invocable", "true").lower() == "false"
        inbound = name in inbound_refs
        if dmi and ui_false and not inbound:
            errs.append(
                f"{name}: ref-* is unreachable "
                f"(disable-model-invocation=true AND user-invocable=false AND "
                f"not referenced by any other skill's reference_refs/script_refs/rubric_refs) "
                f"(doc/20 Step 7-5)"
            )

    return errs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="*", help="SKILL.md ファイル群")
    ap.add_argument("--skills-dir", help="スキル群ディレクトリ (各サブディレクトリの SKILL.md を検査)")
    ap.add_argument(
        "--allow-partial",
        action="store_true",
        help="移行途中の skeleton で wrap base / evaluator pair 未確定を一時許容する",
    )
    args = ap.parse_args()

    targets: list[Path] = []
    if args.skills_dir:
        d = Path(args.skills_dir)
        if not d.is_dir():
            print(f"not a directory: {d}", file=sys.stderr)
            return 2
        targets.extend(sorted(d.glob("*/SKILL.md")))
    for s in args.paths:
        targets.append(Path(s))

    if not targets:
        print("usage: lint-skill-dep-step7.py [SKILL.md ...] [--skills-dir DIR]", file=sys.stderr)
        return 2

    all_errs: list[str] = []
    unverifiable: list[str] = []
    # 全スキル走査時は inbound_refs を一度だけ構築して使い回す（N+1走査を避ける）
    inbound_refs = _collect_inbound_refs(_repo_root(targets[0]))
    for t in targets:
        if not t.exists():
            all_errs.append(f"not found: {t}")
            continue
        try:
            all_errs.extend(
                check_skill(t, inbound_refs=inbound_refs, allow_partial=args.allow_partial)
            )
        except (OSError, UnicodeDecodeError) as exc:
            all_errs.append(f"cannot read {t} as UTF-8 ({type(exc).__name__})")
        except CheckerUnavailable as exc:
            unverifiable.append(f"{t}: cannot verify the guarded external workflow (Step 7-4): {exc}")
    for skills_dir in sorted({t.parent.parent for t in targets}):
        all_errs.extend(check_command_routes(skills_dir))

    for e in all_errs + unverifiable:
        print(e, file=sys.stderr)
    if all_errs:
        return 1
    if unverifiable:
        return 2
    suffix = " (partial allowed)" if args.allow_partial else ""
    print(f"ok: doc/20 Step 7 全5条件 PASS・command の Skill 経路 PASS ({len(targets)} skills){suffix}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
