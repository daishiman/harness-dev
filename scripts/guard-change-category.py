#!/usr/bin/env python3
"""guard-change-category.py

33章 Change Governance の自動分類器。git diff から変更ファイル一覧を取得し、
governance-policy.json の change_categories ルールに従って P0/P1/P2/P3 を推定する。
proposal_required カテゴリで未承認の場合 exit 1 (CI block)。

usage:
  python3 scripts/guard-change-category.py [--base origin/main] [--report]

exit code:
  0 承認済み or auto_apply 範囲のみ
  1 proposal/承認が必要な変更を検出 (CI block)
  2 設定エラー
"""
import json
import pathlib
import re
import subprocess
import sys

POLICY_PATH_CANDIDATES = (
    pathlib.Path("plugins/skill-governance-config/config/governance-policy.json"),
)
CHANGELOG_PATH = pathlib.Path(".claude/changelog/governance-log.jsonl")


def changed_files(base: str):
    try:
        out = subprocess.check_output(
            ["git", "diff", "--name-only", f"{base}...HEAD"],
            text=True,
        )
    except subprocess.CalledProcessError:
        return []
    return [line for line in out.splitlines() if line.strip()]


def changed_file_statuses(base: str) -> dict[str, str]:
    try:
        out = subprocess.check_output(
            ["git", "diff", "--name-status", f"{base}...HEAD"],
            text=True,
        )
    except subprocess.CalledProcessError:
        return {}
    statuses = {}
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            statuses[parts[-1]] = parts[0]
    return statuses


_SKILL_DIR_RE = re.compile(r"^plugins/[a-z0-9][a-z0-9-]*/skills/([a-z0-9][a-z0-9-]*)/")
_SKILL_MD_RE = re.compile(r"^plugins/[a-z0-9][a-z0-9-]*/skills/[a-z0-9][a-z0-9-]*/SKILL\.md$")
_SINK_ADAPTER_RE = re.compile(r"^(?:scripts|plugins/skill-governance-adapters/scripts)/adapters/sink_[a-z0-9_]+\.py$")
_P1_DOC_PATHS = (
    "doc/ClaudeCodeスキルの設計書/06-classification-and-naming",
    "doc/ClaudeCodeスキルの設計書/27-rubric-governance-runbook",
    "doc/ClaudeCodeスキルの設計書/28-script-execution-model",
    "doc/ClaudeCodeスキルの設計書/33-change-governance",
)
_P3_SUFFIXES = (".gitignore", ".editorconfig")


def _name_field_changed(path: str) -> bool:
    """SKILL.md の `name:` 行が変更されたか git diff で確認 (P0_breaking)。"""
    try:
        out = subprocess.check_output(
            ["git", "diff", "--unified=0", "HEAD", "--", path], text=True
        )
    except subprocess.CalledProcessError:
        return False
    return any(re.match(r"^[+-]name:\s", line) for line in out.splitlines())


def classify_change(path: str, status: str = "") -> str:
    """変更パスから P0/P1/P2/P3 を推定する (33章 Change Governance)。

    fallback は P2_content (Goodhart 罠回避のため P3 にしない)。
    Phase 0 省略検出: plugins/ 配下の新規ディレクトリは P0_breaking 扱いとする。
    """
    # Phase 0 不可逆移行検出 (PF2-D2 mitigation)
    if path.startswith("plugins/"):
        return "P0_breaking"
    # Sink Contract I/F 変更
    if _SINK_ADAPTER_RE.match(path):
        return "P0_breaking"
    # Skill name 変更 (frontmatter name: 行の diff)
    if _SKILL_MD_RE.match(path) and _name_field_changed(path):
        return "P0_breaking"
    # 新 Skill 追加/削除/rename は git status で判定する。作業ツリー存在有無は追加後に True になるため使わない。
    if _SKILL_MD_RE.match(path) and status[:1] in {"A", "D", "R"}:
        return "P1_structural"
    if _SKILL_DIR_RE.match(path) and path.endswith("/SKILL.md"):
        # 既存 SKILL.md の name 以外の変更
        return "P1_structural" if _name_field_changed(path) else "P2_content"
    # 命名規則 / governance / script モデル / change governance ドキュメント
    if any(path.startswith(p) for p in _P1_DOC_PATHS):
        return "P1_structural"
    # manifest forbidden_dependencies
    if path.endswith("/.claude-plugin/plugin.json"):
        return "P1_structural"
    # rubric 本体
    if path.endswith("/rubric.json"):
        return "P1_structural"
    # cosmetic
    if path.endswith(_P3_SUFFIXES):
        return "P3_cosmetic"
    # ドキュメント本文 / references / examples / templates
    if (
        path.startswith("doc/")
        or "/references/" in path
        or "/examples/" in path
        or "/templates/" in path
    ):
        return "P2_content"
    return "P2_content"


def load_policy():
    for policy_path in POLICY_PATH_CANDIDATES:
        if policy_path.exists():
            return json.loads(policy_path.read_text(encoding="utf-8"))
    print(
        "ERROR: policy not found at any of: "
        + ", ".join(str(p) for p in POLICY_PATH_CANDIDATES),
        file=sys.stderr,
    )
    sys.exit(2)


def needs_proposal(category: str, policy: dict) -> bool:
    rule = policy["change_categories"].get(category, {})
    return "proposal_required" in rule.get("workflow", "")


def has_recent_changelog(target_path: str) -> bool:
    if not CHANGELOG_PATH.exists():
        return False
    for line in CHANGELOG_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if target_path.split("/")[0] in entry.get("target_path", ""):
            return True
    return False


def check_cooldown(target_path: str, category: str, policy: dict, bypass: bool = False) -> bool:
    """cooldown_rules に従い、直近変更から規定日数を過ぎているか確認する。
    
    戻り値: True=OK（cooldown クリア or 対象外）、False=cooldown 違反
    --bypass-cooldown フラグが真の場合は常に True を返す。
    """
    if bypass:
        return True
    cooldown_rules = policy.get("cooldown_rules", {})
    days_str = cooldown_rules.get(category, "なし")
    if days_str in ("なし", "", None):
        return True
    try:
        cooldown_days = int(re.search(r"(\d+)", str(days_str)).group(1))
    except (AttributeError, ValueError):
        return True

    if not CHANGELOG_PATH.exists():
        return True

    import datetime
    now = datetime.datetime.now(datetime.timezone.utc)
    min_seconds = cooldown_days * 86400

    for line in CHANGELOG_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if target_path not in entry.get("target_path", ""):
            continue
        ts_str = entry.get("timestamp") or entry.get("ts") or ""
        if not ts_str:
            continue
        try:
            ts = datetime.datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            elapsed = (now - ts).total_seconds()
            if elapsed < min_seconds:
                return False  # cooldown 違反
        except (ValueError, TypeError):
            continue
    return True



def main(argv):
    base = "origin/main"
    report = False
    bypass_cooldown = False
    for i, a in enumerate(argv):
        if a == "--base" and i + 1 < len(argv):
            base = argv[i + 1]
        if a == "--report":
            report = True
        if a == "--bypass-cooldown":
            bypass_cooldown = True
    policy = load_policy()
    files = changed_files(base)
    statuses = changed_file_statuses(base)
    results = []
    blocked = []
    for f in files:
        cat = classify_change(f, statuses.get(f, ""))
        proposal = needs_proposal(cat, policy)
        approved = has_recent_changelog(f) if proposal else True
        cooldown_ok = check_cooldown(f, cat, policy, bypass=bypass_cooldown)
        results.append({"path": f, "category": cat, "proposal_required": proposal, "approved": approved, "cooldown_ok": cooldown_ok})
        if proposal and not approved:
            blocked.append({"path": f, "category": cat, "reason": "proposal/承認 changelog 未記録"})
        elif not cooldown_ok:
            blocked.append({"path": f, "category": cat, "reason": f"cooldown 違反（{cat} は cooldown 期間中）"})
    if report:
        print(json.dumps({
            "base": base,
            "changes": results,
            "blocked": blocked,
        }, indent=2, ensure_ascii=False))
    else:
        for b in blocked:
            reason = b.get("reason", "proposal/承認 changelog 未記録")
            print(f"BLOCK {b['path']} ({b['category']}): {reason}", file=sys.stderr)
        print(f"summary: total={len(results)} blocked={len(blocked)}")
    return 1 if blocked else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
