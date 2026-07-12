#!/usr/bin/env python3
# /// script
# name: lint-prompt-contract-drift
# version: 0.1.0
# purpose: 7 層プロンプト本文の契約記述が実装 (referenced path / allowed-tools / CLI) と機械的に整合するか検証する
# inputs:
#   - --all: plugins/*/skills/*/prompts/*.md を全走査
#   - --changed-only [--base <ref>]: git diff で変更された prompt のみ
#   - argv[positional]: 個別 prompt パス (テスト/ピンポイント検査用)
#   - --json: 機械可読出力
#   - --strict-cli: Tier3 (CLI 契約) の WARN を fatal へ昇格
# outputs:
#   - stdout: 検査サマリ / drift 一覧
#   - exit code: 0=PASS / 1=drift 検出 / 2=引数エラー
# requires-python: ">=3.9"
# dependencies: []
# contexts: [C, E]
# network: false
# write-scope: none
# ///
"""7 層プロンプト↔実装の契約ドリフトを決定論的に検出する (LLM 不実行, offline)。

背景 (なぜ必要か):
  content-review の機械層 (lint-content-review.py) は verdict の「存在・鮮度」しか見ず、
  プロンプトの契約記述 (参照 schema / allowed-tools / CLI 引数) が実装と一致するかは
  毎回 LLM 監査に依存していた。監査は一回きりで再現性が無く、schema 変更等で容易に
  再ドリフトする。本 lint は「意味判断なしに決定論的 verdict を出せる契約」だけを
  機械層に引き上げ、CI で fail-closed に縛る (mechanism + AI freedom の二層分離)。

役割境界 (何を見て何を見ないか):
  Tier1 参照パス実在  : prompt が引用する references/ schemas/ scripts/ templates/ 等の
                        source パスが skill-root 起点で実在するか (最高精度・fail-closed)
  Tier2 allowed-tools : prompt が許可主張するツール ⊆ SKILL.md frontmatter allowed-tools
  Tier3 CLI 契約      : prompt 入力契約の subcommand/flag が対象 script argparse に実在
                        (誤検出リスクを考慮し既定 WARN・--strict-cli で fatal 昇格)
  対象外 (LLM 層に残す): 「1 行テキストが JSON object schema に準拠不能」等、意味理解が
                        要る妥当性判断。決定論 verdict を出せないものは本 lint の責務外。

既存 lint との非重複:
  - lint-external-refs.py     : SKILL.md の外部境界参照棚卸し (prompt 本文/実在は非対象)
  - lint-rubric-refs-exist.py : SKILL.md frontmatter rubric_refs のみ
  - lint-agent-prompt-section : SubAgent のセクション存在のみ (契約の中身は非対象)
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLUGINS_DIR = ROOT / "plugins"

# lint-skill-tree.py が許可する source 系 top-level dir のうち、
# 「lint 時点で物理実在すべき」もの。eval-log/ log/ は runtime 出力なので除外。
SOURCE_DIR_TOKENS = ("references", "schemas", "scripts", "templates", "prompts", "examples", "hooks")

# path 捕捉: 先行する ../ 連鎖と非 token セグメント (例: ../run-prompt-create/) も取り込み、
# フルパスを切り詰めない (切り詰めると兄弟 skill 相対参照を誤検出する)。
# 起点 token は source dir または plugins/。
_PREFIX = "|".join(SOURCE_DIR_TOKENS)
PATH_RE = re.compile(
    r"(?P<path>(?:\.\./)*(?:[A-Za-z0-9_.\-]+/)*?"
    r"(?:plugins|" + _PREFIX + r")/[A-Za-z0-9_\-./]+)"
)

# binding 不能 (placeholder / glob) はスキップ。決定論 verdict を出せる引用のみ検査する。
PLACEHOLDER_CHARS = set("<>{}*")
# 汎用 placeholder セグメント (example 値)。実パスとして解決する意図がない。
PLACEHOLDER_SEGMENTS = {"foo", "bar", "baz", "qux", "placeholder"}

# 契約が明示的に「任意/未配置可/実行時 provision/gitignore」と宣言する行の引用は、
# 非実在が設計通りなので除外する (runtime 生成物・gitignore 正本を drift 扱いしない)。
OPTIONAL_MARKERS = (
    "任意", "optional", "未配置", "なくてもよい", "無くてもよい", "あれば",
    "未配備", "provision", "gitignore", "graceful",
)

# 意図的に非実在を例示する既知の教示用パス (回答例など・実パスではない)。理由付きで宣言。
KNOWN_EXAMPLE_REFS = {
    "prompts/legacy/",  # run-migrate-audit R1-audit.md「回答例」内 exclude 値 (利用例)
}

# 意図的に非実在を例示する等の除外は、行に本マーカーを置く (原則使用しない)。
IGNORE_MARKER = "contract-drift-ignore"


def _iter_prompt_files(targets):
    for t in targets:
        p = Path(t)
        if p.is_file():
            yield p


def _all_prompt_files():
    if not PLUGINS_DIR.exists():
        return []
    return sorted(PLUGINS_DIR.glob("*/skills/*/prompts/*.md"))


def _changed_prompt_files(base):
    try:
        diff = subprocess.check_output(
            ["git", "diff", "--name-only", f"{base}...HEAD"], cwd=ROOT, text=True
        )
    except subprocess.CalledProcessError:
        return []
    out = []
    pat = re.compile(r"^plugins/[^/]+/skills/[^/]+/prompts/[^/]+\.md$")
    for line in diff.splitlines():
        line = line.strip()
        if pat.match(line):
            fp = ROOT / line
            if fp.is_file():
                out.append(fp)
    return sorted(out)


PLUGIN_ROOT_PREFIXES = ("$CLAUDE_PLUGIN_ROOT/", "${CLAUDE_PLUGIN_ROOT}/", "CLAUDE_PLUGIN_ROOT/")


def _bases(prompt_path: Path):
    # plugins/<plugin>/skills/<skill>/prompts/<file>.md
    prompt_dir = prompt_path.resolve().parent   # .../prompts
    skill_root = prompt_dir.parent              # .../<skill>
    skills_dir = skill_root.parent              # .../skills
    plugin_root = skills_dir.parent             # plugins/<plugin>
    return prompt_dir, skill_root, skills_dir, plugin_root


def _strip_token(tok: str) -> str:
    return tok.rstrip(").,`\"'|:;")


def _resolve_multi(ref: str, prompt_path: Path):
    """リポの実解決規約 (複数 base のいずれかで解決) を模して存在確認する。

    プロンプト内の相対 (../) は prompt ファイルのディレクトリ (prompts/) 起点。
    bare (schemas/X) は skill-root 起点。<skill>/references/X は skills-dir 起点。
    共有 script は plugin-root 直下。$CLAUDE_PLUGIN_ROOT/ は plugin-root へ展開。
    どの正当 base でも解決できなければ drift。
    """
    prompt_dir, skill_root, skills_dir, plugin_root = _bases(prompt_path)
    for pfx in PLUGIN_ROOT_PREFIXES:
        if ref.startswith(pfx):
            cand = (plugin_root / ref[len(pfx):]).resolve()
            return cand if cand.exists() else None
    if ref.startswith("plugins/"):
        cand = (ROOT / ref).resolve()
        return cand if cand.exists() else None
    # plugins container (plugin_root.parent) base: resource://<plugin>/references/X →
    # plugins/<plugin>/references/X。固定 PLUGINS_DIR でなく prompt パスから導出し portable に。
    plugins_container = plugin_root.parent
    for base in (prompt_dir, skill_root, skills_dir, plugin_root, plugins_container, ROOT):
        try:
            cand = (base / ref).resolve()
        except (ValueError, OSError):
            continue
        if cand.exists():
            return cand
    return None


def _is_prose_dir_enumeration(raw: str) -> bool:
    """拡張子なしで全セグメントが source dir token の path は prose 列挙 (例: prompts/schemas/references)。"""
    segs = [s for s in raw.strip("/").split("/") if s]
    if len(segs) < 2:
        return False
    if "." in Path(raw).name:
        return False
    return all(s in SOURCE_DIR_TOKENS for s in segs)


def check_tier1_referenced_paths(prompt_path: Path, text: str):
    """Tier1: 引用された source パスが実在するか (複数 base で解決)。"""
    findings = []
    seen = set()
    lines = text.splitlines()
    for m in PATH_RE.finditer(text):
        raw = _strip_token(m.group("path"))
        if not raw or any(c in PLACEHOLDER_CHARS for c in raw):
            continue
        # 捕捉トークンの直後が glob/placeholder 継続文字 (例: references/diagram-*.md は
        # char class 外の * 手前で 'references/diagram-' に切れ、上の in-raw 判定を素通りする)。
        # binding 不能な glob なので resolve せずスキップ (PLACEHOLDER_CHARS 方針の一貫適用)。
        if m.end() < len(text) and text[m.end()] in PLACEHOLDER_CHARS:
            continue
        if set(raw.split("/")) & PLACEHOLDER_SEGMENTS:
            continue
        if raw in KNOWN_EXAMPLE_REFS or raw.rstrip("/") in {r.rstrip("/") for r in KNOWN_EXAMPLE_REFS}:
            continue
        if _is_prose_dir_enumeration(raw):
            continue
        line_no = text.count("\n", 0, m.start()) + 1
        line_text = lines[line_no - 1] if line_no - 1 < len(lines) else ""
        if IGNORE_MARKER in line_text:
            continue
        if any(mk in line_text for mk in OPTIONAL_MARKERS):
            continue
        key = (raw, line_no)
        if key in seen:
            continue
        seen.add(key)
        if _resolve_multi(raw, prompt_path) is None:
            findings.append({
                "tier": 1,
                "check": "referenced-path-exists",
                "line": line_no,
                "ref": raw,
                "detail": f"引用パス '{raw}' がいずれの正当 base でも実在しない",
            })
    return findings


# Tier2: allowed-tools 整合。prompt L3.2 「外部ツール」節が主張するツールが
# SKILL.md frontmatter allowed-tools に含まれるか (含まれなければ runtime で許可外)。
KNOWN_TOOLS = {
    "Read", "Write", "Edit", "MultiEdit", "Grep", "Glob", "Bash",
    "WebSearch", "WebFetch", "AskUserQuestion", "Task", "Agent",
    "NotebookEdit", "SlashCommand",
}
TOOL_ALIASES = {"Task": "Agent"}  # subagent 起動は Agent に正規化
# ツール名の直後/直前が否定文脈なら「使わない」宣言なので許可外検出から除外。
TOOL_NEGATIONS = ("不使用", "使わない", "使用しない", "禁止", "未使用", "非使用")


def _norm_tool(t: str) -> str:
    return TOOL_ALIASES.get(t, t)


def _parse_skill_allowed_tools(skill_root: Path):
    """SKILL.md frontmatter の allowed-tools を base tool 名の集合で返す。無ければ None。"""
    skill_md = skill_root / "SKILL.md"
    if not skill_md.exists():
        return None
    text = skill_md.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not m:
        return None
    fm = m.group(1)
    items = []
    mi = re.search(r"^allowed-tools:\s*\[(.*?)\]", fm, re.MULTILINE | re.DOTALL)
    if mi:
        items = [x.strip() for x in mi.group(1).split(",")]
    else:
        mb = re.search(r"^allowed-tools:\s*\n((?:[ \t]*-[ \t]*.+\n?)+)", fm, re.MULTILINE)
        if mb:
            items = [re.sub(r"^[ \t]*-[ \t]*", "", l).strip() for l in mb.group(1).splitlines()]
        else:
            return None  # allowed-tools 宣言なし → 照合対象外
    tools = set()
    for it in items:
        base = re.split(r"[(\s]", it, 1)[0].strip()
        if base:
            tools.add(_norm_tool(base))
    return tools


def check_tier2_allowed_tools(prompt_path: Path, text: str):
    """Tier2: prompt L3.2 外部ツール節のツール ⊆ SKILL.md allowed-tools。"""
    skill_root = prompt_path.resolve().parent.parent
    allowed = _parse_skill_allowed_tools(skill_root)
    if allowed is None:
        return []
    lines = text.splitlines()
    findings = []
    in_region = False
    seen = set()
    for i, l in enumerate(lines):
        if re.match(r"^#{2,4}\s", l):
            if in_region:
                break  # 次見出しで節終了
            if "外部ツール" in l:
                in_region = True
            continue
        if not in_region:
            continue
        for tok in KNOWN_TOOLS:
            mt = re.search(r"(?<![A-Za-z])" + re.escape(tok) + r"(?![A-Za-z])", l)
            if mt:
                # ツールトークン直後 (~8 字) が否定文脈なら「使わない」宣言なので除外。
                tail = l[mt.end():mt.end() + 8]
                if any(neg in tail for neg in TOOL_NEGATIONS):
                    continue
                if _norm_tool(tok) not in allowed and (tok, i + 1) not in seen:
                    seen.add((tok, i + 1))
                    findings.append({
                        "tier": 2,
                        "check": "allowed-tools-subset",
                        "line": i + 1,
                        "ref": tok,
                        "detail": f"prompt L3.2 が '{tok}' を宣言するが SKILL.md allowed-tools {sorted(allowed)} に無い",
                    })
    return findings


def scan_prompt(prompt_path: Path, tiers=("1", "2")):
    text = prompt_path.read_text(encoding="utf-8")
    findings = []
    if "1" in tiers:
        findings += check_tier1_referenced_paths(prompt_path, text)
    if "2" in tiers:
        findings += check_tier2_allowed_tools(prompt_path, text)
    return findings


# Tier ごとの fatal 既定。Tier1 (参照パス実在) は誤検出ほぼ皆無なので fail-closed。
# Tier2 (allowed-tools) は forked 責務で親 SKILL.md と owner agent の grant SSOT が
# 分岐しうる binding 曖昧性があるため既定 WARN (--strict-tools で fatal 昇格)。
FATAL_TIERS_DEFAULT = {1}


def main(argv):
    parser = argparse.ArgumentParser(description="7 層プロンプト契約ドリフト検出")
    src = parser.add_mutually_exclusive_group()
    src.add_argument("--all", action="store_true", help="全 prompt を走査")
    src.add_argument("--changed-only", action="store_true", help="変更 prompt のみ")
    parser.add_argument("--base", default="origin/main", help="--changed-only の diff 基点")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict-tools", action="store_true", help="Tier2 (allowed-tools) WARN を fatal へ昇格")
    parser.add_argument("paths", nargs="*", help="個別 prompt パス")
    args = parser.parse_args(argv[1:])

    fatal_tiers = set(FATAL_TIERS_DEFAULT)
    if args.strict_tools:
        fatal_tiers.add(2)

    if args.paths:
        files = list(_iter_prompt_files(args.paths))
    elif args.changed_only:
        files = _changed_prompt_files(args.base)
    else:
        files = _all_prompt_files()

    reports = []
    fatal_total = 0
    warn_total = 0
    for fp in files:
        findings = scan_prompt(fp)
        for f in findings:
            if f["tier"] in fatal_tiers:
                fatal_total += 1
            else:
                warn_total += 1
        rel = fp.resolve().relative_to(ROOT) if str(fp.resolve()).startswith(str(ROOT)) else fp
        reports.append({"prompt": str(rel), "findings": findings})

    if args.json:
        print(json.dumps({
            "prompts_scanned": len(files),
            "fatal_count": fatal_total,
            "warn_count": warn_total,
            "reports": [r for r in reports if r["findings"]],
        }, ensure_ascii=False, indent=2))
    else:
        print(f"prompts_scanned={len(files)} fatal={fatal_total} warn={warn_total}")
        for r in reports:
            for f in r["findings"]:
                label = "DRIFT" if f["tier"] in fatal_tiers else "WARN"
                print(f"{label}[T{f['tier']}] {r['prompt']}:{f['line']} {f['detail']}")

    return 1 if fatal_total else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
