#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# /// script
# name: compute-dogfooding-metrics
# version: 0.1.0
# purpose: plugins/harness-creator/ を走査し dogfooding メトリクス6種を集計、
#          EVALS.json の dogfooding_metrics キーへ upsert する自己適用計測器。
# inputs:
#   - argv: [--dry-run] [--plugin-root <dir>]
#   - files: lessons-learned/*.md / plugin-composition.yaml / .claude-plugin/plugin.json / rubric.json
#   - git: マージ commit 数・rubric version 変更履歴 (subprocess 経由 read-only)
# outputs:
#   - stdout: 集計サマリ JSON (--dry-run 時)
#   - exit: 0=集計成功 / 1=失敗 (traceback)
# contexts: [E]
# network: false
# write-scope: EVALS.json (dogfooding_metrics キーのみ upsert・--dry-run で抑止)
# dependencies: ["pyyaml; optional (不在時は capability_count_by_kind を skip)"]
# requires-python: ">=3.9"
# ///
"""
dogfooding メトリクス集計スクリプト。

plugins/harness-creator/ 配下を走査し、以下を EVALS.json の
`dogfooding_metrics` キーへ upsert する。

  1. lessons_per_pr            : lessons-learned ファイル数 / PR マージ commit 数
  2. review_cycle_time_ms      : lessons-learned frontmatter date と commit の差分平均
  3. rubric_bump_frequency     : 直近 30 日の rubric.json version 変更頻度
  4. capability_count_by_kind  : plugin-composition.yaml capabilities[] の kind 集計
  5. hook_wired_count          : plugin.json hooks[event][matcher].hooks[] 合計
  6. rubric_kind_coverage      : rubric.json applies_to_kinds の被覆率

例外発生時は stderr に出力して exit 0 (非ブロック)。
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import traceback
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

# yaml は任意依存。なければ簡易 parser でフォールバック。
try:
    import yaml  # type: ignore
    _HAS_YAML = True
except Exception:
    _HAS_YAML = False

# kind 8 種(rubric_kind_coverage の分母)。capability-manifest.schema.json の kind enum と同期。
KNOWN_KINDS = ("skill", "agent", "hook", "command", "plugin-composition", "prompt", "workflow", "script")

# このスクリプトを基準に plugin root を決定
PLUGIN_ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# git ヘルパ
# ---------------------------------------------------------------------------
def _git(args: list[str], cwd: Path) -> str | None:
    """git コマンド実行。失敗時 None。"""
    try:
        out = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            check=True,
            capture_output=True,
            text=True,
        )
        return out.stdout
    except Exception:
        return None


# ---------------------------------------------------------------------------
# 1. lessons_per_pr
# ---------------------------------------------------------------------------
def compute_lessons_per_pr(plugin_root: Path) -> dict[str, Any]:
    lessons_dir = plugin_root / "lessons-learned"
    lessons_files = (
        [p for p in lessons_dir.rglob("*") if p.is_file() and p.suffix in (".md", ".yaml", ".yml", ".json")]
        if lessons_dir.exists()
        else []
    )
    lessons_count = len(lessons_files)

    # PR マージ commit を --first-parent でカウント
    log = _git(["log", "--first-parent", "--merges", "--pretty=%H"], plugin_root)
    if log is None:
        return {"lessons_count": lessons_count, "pr_merge_count": 0, "ratio": 0.0}
    pr_count = len([l for l in log.splitlines() if l.strip()])
    ratio = (lessons_count / pr_count) if pr_count > 0 else 0.0
    return {
        "lessons_count": lessons_count,
        "pr_merge_count": pr_count,
        "ratio": round(ratio, 4),
    }


# ---------------------------------------------------------------------------
# 2. review_cycle_time_ms
# ---------------------------------------------------------------------------
_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_DATE_RE = re.compile(r"^date\s*:\s*['\"]?([^'\"\n]+)['\"]?\s*$", re.MULTILINE)


def _parse_iso(s: str) -> datetime | None:
    s = s.strip()
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(s, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            continue
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


def compute_review_cycle_time_ms(plugin_root: Path) -> int | None:
    lessons_dir = plugin_root / "lessons-learned"
    if not lessons_dir.exists():
        return None

    diffs: list[float] = []
    for p in lessons_dir.rglob("*.md"):
        try:
            text = p.read_text(encoding="utf-8")
        except Exception:
            continue
        m = _FRONTMATTER_RE.match(text)
        if not m:
            continue
        dm = _DATE_RE.search(m.group(1))
        if not dm:
            continue
        fm_dt = _parse_iso(dm.group(1))
        if fm_dt is None:
            continue
        # 該当ファイルの最新 commit 時刻 (ISO)
        log = _git(["log", "-1", "--pretty=%cI", "--", str(p.relative_to(plugin_root))], plugin_root)
        if not log:
            continue
        commit_dt = _parse_iso(log.strip())
        if commit_dt is None:
            continue
        diffs.append(abs((commit_dt - fm_dt).total_seconds()) * 1000.0)

    if not diffs:
        return None
    return int(sum(diffs) / len(diffs))


# ---------------------------------------------------------------------------
# 3. rubric_bump_frequency
# ---------------------------------------------------------------------------
def compute_rubric_bump_frequency(plugin_root: Path) -> dict[str, Any]:
    rubric_files = list((plugin_root / "skills").glob("ref-*-rubric/**/rubric.json"))
    since = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d")
    total_changes = 0
    per_file: dict[str, int] = {}
    for rf in rubric_files:
        rel = str(rf.relative_to(plugin_root))
        log = _git(
            ["log", "--follow", f"--since={since}", "--pretty=%H", "--", rel],
            plugin_root,
        )
        if log is None:
            per_file[rel] = 0
            continue
        # version 行が触れた commit 数を概算: -G で version フィールド変更を絞る
        log2 = _git(
            ["log", "--follow", f"--since={since}", "-G", "\"version\"", "--pretty=%H", "--", rel],
            plugin_root,
        )
        cnt = len([l for l in (log2 or "").splitlines() if l.strip()])
        per_file[rel] = cnt
        total_changes += cnt
    return {
        "window_days": 30,
        "total_bumps": total_changes,
        "per_file": per_file,
    }


# ---------------------------------------------------------------------------
# 4. capability_count_by_kind (plugin-composition.yaml)
# ---------------------------------------------------------------------------
def _load_yaml_capabilities(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    if _HAS_YAML:
        try:
            data = yaml.safe_load(text) or {}
            caps = data.get("capabilities") or []
            return [c for c in caps if isinstance(c, dict)]
        except Exception:
            pass
    # 簡易 line-based parser: capabilities: ブロック内の `- kind: xxx` を拾う
    caps: list[dict[str, Any]] = []
    in_caps = False
    base_indent = None
    current: dict[str, Any] | None = None
    for line in text.splitlines():
        stripped = line.rstrip()
        if not in_caps:
            if re.match(r"^capabilities\s*:\s*$", stripped):
                in_caps = True
            continue
        # capabilities 配下の indent を観測
        if stripped == "" or stripped.startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        if base_indent is None and stripped.lstrip().startswith("-"):
            base_indent = indent
        # トップレベルキー復帰で終了
        if indent == 0 and not stripped.startswith("-"):
            break
        m = re.match(r"^(\s*)-\s*(.*)$", line)
        if m and len(m.group(1)) == (base_indent or 0):
            if current is not None:
                caps.append(current)
            current = {}
            # `- kind: skill` 等の inline 形式
            rest = m.group(2)
            if ":" in rest:
                k, _, v = rest.partition(":")
                current[k.strip()] = v.strip().strip("'\"")
            continue
        m2 = re.match(r"^\s+([A-Za-z_][\w-]*)\s*:\s*(.*)$", line)
        if m2 and current is not None:
            current[m2.group(1).strip()] = m2.group(2).strip().strip("'\"")
    if current is not None:
        caps.append(current)
    return caps


def compute_capability_count_by_kind(plugin_root: Path) -> dict[str, int]:
    comp = plugin_root / "plugin-composition.yaml"
    caps = _load_yaml_capabilities(comp)
    counter: dict[str, int] = defaultdict(int)
    for c in caps:
        k = (c.get("kind") or "").strip()
        if k:
            counter[k] += 1
    # 既知 kind を 0 で埋めて返す
    out = {k: counter.get(k, 0) for k in KNOWN_KINDS}
    # 未知 kind も保持
    for k, v in counter.items():
        if k not in out:
            out[k] = v
    return out


# ---------------------------------------------------------------------------
# 5. hook_wired_count (plugin.json)
# ---------------------------------------------------------------------------
def compute_hook_wired_count(plugin_root: Path) -> int:
    # Claude Code 公式仕様では plugin.json は `.claude-plugin/plugin.json` 配下。
    # 旧構成 (plugin 直下) との両対応のためフォールバック順で探索する。
    candidates = [
        plugin_root / ".claude-plugin" / "plugin.json",
        plugin_root / "plugin.json",
    ]
    pj = next((p for p in candidates if p.exists()), None)
    if pj is None:
        return 0
    try:
        data = json.loads(pj.read_text(encoding="utf-8"))
    except Exception:
        return 0
    hooks = data.get("hooks") or {}
    total = 0
    if isinstance(hooks, dict):
        for _event, matchers in hooks.items():
            if isinstance(matchers, list):
                for m in matchers:
                    if isinstance(m, dict):
                        hs = m.get("hooks") or []
                        if isinstance(hs, list):
                            total += len(hs)
            elif isinstance(matchers, dict):
                # event -> { matcher: { hooks: [...] } } 形
                for _mk, mv in matchers.items():
                    if isinstance(mv, dict):
                        hs = mv.get("hooks") or []
                        if isinstance(hs, list):
                            total += len(hs)
    return total


# ---------------------------------------------------------------------------
# 6. rubric_kind_coverage
# ---------------------------------------------------------------------------
def compute_rubric_kind_coverage(plugin_root: Path) -> dict[str, Any]:
    rubric_files = list((plugin_root / "skills").glob("ref-*-rubric/**/rubric.json"))
    covered: set[str] = set()
    per_file: dict[str, list[str]] = {}
    for rf in rubric_files:
        try:
            data = json.loads(rf.read_text(encoding="utf-8"))
        except Exception:
            continue
        kinds: list[str] = []
        # トップレベル applies_to_kinds
        ak = data.get("applies_to_kinds")
        if isinstance(ak, list):
            kinds.extend([str(x) for x in ak])
        # rules[].applies_to_kinds
        for rule in data.get("rules", []) or []:
            if isinstance(rule, dict):
                ak2 = rule.get("applies_to_kinds")
                if isinstance(ak2, list):
                    kinds.extend([str(x) for x in ak2])
        per_file[str(rf.relative_to(plugin_root))] = sorted(set(kinds))
        for k in kinds:
            if k in KNOWN_KINDS:
                covered.add(k)
    return {
        "covered_kinds": sorted(covered),
        "coverage_ratio": round(len(covered) / len(KNOWN_KINDS), 4),
        "per_file": per_file,
    }


# ---------------------------------------------------------------------------
# 集計 & EVALS.json upsert
# ---------------------------------------------------------------------------
def collect_all(plugin_root: Path) -> dict[str, Any]:
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "plugin_root": str(plugin_root),
        "lessons_per_pr": compute_lessons_per_pr(plugin_root),
        "review_cycle_time_ms": compute_review_cycle_time_ms(plugin_root),
        "rubric_bump_frequency": compute_rubric_bump_frequency(plugin_root),
        "capability_count_by_kind": compute_capability_count_by_kind(plugin_root),
        "hook_wired_count": compute_hook_wired_count(plugin_root),
        "rubric_kind_coverage": compute_rubric_kind_coverage(plugin_root),
    }


def upsert_evals(plugin_root: Path, metrics: dict[str, Any]) -> Path:
    evals_path = plugin_root / "EVALS.json"
    data: dict[str, Any] = {}
    if evals_path.exists():
        try:
            data = json.loads(evals_path.read_text(encoding="utf-8")) or {}
        except Exception:
            data = {}
    data["dogfooding_metrics"] = metrics
    evals_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return evals_path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(
        description="dogfooding metrics aggregator for plugins/harness-creator/"
    )
    parser.add_argument("--dry-run", action="store_true", help="集計のみ表示し EVALS.json へ書き込まない")
    parser.add_argument("--self-test", action="store_true", help="自プラグイン群を対象に dogfooding 実行 (表示のみ)")
    args = parser.parse_args()

    try:
        plugin_root = PLUGIN_ROOT
        metrics = collect_all(plugin_root)
        summary = json.dumps(metrics, ensure_ascii=False, indent=2)
        if args.self_test:
            print(summary)
            return 0
        if not args.dry_run:
            evals_path = upsert_evals(plugin_root, metrics)
            print(f"[ok] wrote dogfooding_metrics -> {evals_path}", file=sys.stderr)
        print(summary)
        return 0
    except Exception as e:  # 非ブロック
        print(f"[warn] compute-dogfooding-metrics failed: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return 0


if __name__ == "__main__":
    sys.exit(main())
