#!/usr/bin/env python3
"""guard-change-category.py

33章 Change Governance の自動分類器。git diff から変更ファイル一覧を取得し、
governance-policy.json の change_categories ルールに従って P0/P1/P2/P3 を推定する。
proposal_required カテゴリで未承認の場合 exit 1 (CI block)。

usage:
  python3 scripts/guard-change-category.py [--base origin/main] [--report] [--proposal-id ID]

承認と cooldown は同じ正規化された対象パスで判定する。現在の提案を明示するか、
承認済み記録の target_sha256 が現物と一致すれば、その記録だけを過去の変更から除く。
以前の変更の cooldown は維持し、incident_fix=true の承認だけを規約の例外とする。

exit code:
  0 承認済み or auto_apply 範囲のみ
  1 proposal/承認が必要な変更を検出 (CI block)
  2 設定エラー
"""
import json
import fnmatch
import hashlib
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


def _name_field_changed(path: str, base: str = "HEAD") -> bool:
    """SKILL.md の `name:` 行が変更されたか git diff で確認 (P0_breaking)。"""
    try:
        out = subprocess.check_output(
            ["git", "diff", "--unified=0", base, "--", path], text=True
        )
    except subprocess.CalledProcessError:
        return False
    return any(re.match(r"^[+-]name:\s", line) for line in out.splitlines())


def classify_change(path: str, status: str = "", *, name_changed: bool | None = None,
                    new_plugin: bool = False) -> str:
    """変更パスから P0/P1/P2/P3 を推定する (33章 Change Governance)。

    fallback は P2_content (Goodhart 罠回避のため P3 にしない)。
    Phase 0 省略検出: plugins/ 配下の新規ディレクトリは P0_breaking 扱いとする。
    """
    if new_plugin and path.startswith("plugins/"):
        return "P0_breaking"
    # Sink Contract I/F 変更
    if _SINK_ADAPTER_RE.match(path):
        return "P0_breaking"
    # 新 Skill 追加/削除/rename は git status で判定する。作業ツリー存在有無は追加後に True になるため使わない。
    if _SKILL_MD_RE.match(path) and status[:1] in {"A", "D", "R"}:
        return "P1_structural"
    # name の追加行は新 Skill の必須項目で、既存の公開名変更とは異なる。
    if _SKILL_DIR_RE.match(path) and path.endswith("/SKILL.md"):
        changed = _name_field_changed(path) if name_changed is None else name_changed
        return "P0_breaking" if changed else "P2_content"
    # 命名規則 / governance / script モデル / change governance ドキュメント
    if any(path.startswith(p) for p in _P1_DOC_PATHS):
        return "P1_structural"
    # manifest forbidden_dependencies
    if path.endswith(("/.claude-plugin/plugin.json", "/.codex-plugin/plugin.json")):
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


def load_policy(explicit_path: pathlib.Path | None = None):
    if explicit_path is not None and not explicit_path.is_absolute():
        print("ERROR: --policy requires an observed absolute path", file=sys.stderr)
        raise SystemExit(2)
    candidates = [explicit_path] if explicit_path is not None else POLICY_PATH_CANDIDATES
    for policy_path in candidates:
        if policy_path.is_file():
            try:
                policy = json.loads(policy_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                print(f"ERROR: policy cannot be read: {exc}", file=sys.stderr)
                raise SystemExit(2)
            if (not isinstance(policy, dict)
                    or not isinstance(policy.get("change_categories"), dict)
                    or not policy["change_categories"]
                    or not isinstance(policy.get("cooldown_rules"), dict)):
                print("ERROR: policy category/cooldown contract is invalid", file=sys.stderr)
                raise SystemExit(2)
            return policy
    print("ERROR: policy not found at any of: " + ", ".join(str(p) for p in candidates), file=sys.stderr)
    raise SystemExit(2)


def needs_proposal(category: str, policy: dict) -> bool:
    rule = policy["change_categories"].get(category, {})
    return "proposal_required" in rule.get("workflow", "")


def _entries() -> list[dict]:
    if not CHANGELOG_PATH.exists():
        return []
    entries = []
    for line in CHANGELOG_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(entry, dict):
            entries.append(entry)
    return entries


def _matches_target(target_path: str, entry: dict) -> bool:
    """Use the same file/directory/glob semantics for scalar and list targets."""
    targets = entry.get("target_path", [])
    if isinstance(targets, str):
        targets = targets.split(" + ")  # legacy logs used a human-readable list
    if not isinstance(targets, list):
        return False
    path = pathlib.PurePosixPath(target_path.replace("\\", "/")).as_posix()
    for target in targets:
        if not isinstance(target, str):
            continue
        target = re.sub(r"\s+[（(].*$", "", target).strip().replace("\\", "/").rstrip("/")
        if not target:
            continue
        if path == target or path.startswith(target + "/") or fnmatch.fnmatchcase(path, target):
            return True
    return False


def _approved(entry: dict) -> bool:
    approver = entry.get("approver")
    return (isinstance(approver, str) and bool(approver.strip())
            and approver not in {"auto", "pending"}
            and entry.get("status", "approved") == "approved")


def _approved_current_content(target_path: str, entry: dict) -> bool:
    hashes = entry.get("target_sha256")
    if not _approved(entry) or not isinstance(hashes, dict):
        return False
    expected = hashes.get(target_path)
    if not isinstance(expected, str):
        return False
    try:
        return hashlib.sha256(pathlib.Path(target_path).read_bytes()).hexdigest() == expected
    except OSError:
        return False


def has_recent_changelog(target_path: str, proposal_id: str | None = None) -> bool:
    return any(_approved(e) and _matches_target(target_path, e)
               and ((proposal_id is not None and e.get("proposal_id") == proposal_id
                     and ("target_sha256" not in e or _approved_current_content(target_path, e)))
                    or (proposal_id is None and _approved_current_content(target_path, e)))
               for e in _entries())


def check_cooldown(target_path: str, category: str, policy: dict, bypass: bool = False,
                   proposal_id: str | None = None) -> bool:
    """cooldown_rules に従い、直近変更から規定日数を過ぎているか確認する。
    
    戻り値: True=OK（cooldown クリア or 対象外）、False=cooldown 違反
    --bypass-cooldown は現物に束縛された承認済み incident 修正の場合だけ許可する。
    """
    entries = _entries()
    current = [e for e in entries if _approved(e) and _matches_target(target_path, e)
               and ((proposal_id and e.get("proposal_id") == proposal_id)
                    or (proposal_id is None and _approved_current_content(target_path, e)))
               and ("target_sha256" not in e or _approved_current_content(target_path, e))]
    approved_incident = any(e.get("incident_fix") is True for e in current)
    if bypass:
        return approved_incident
    cooldown_rules = policy.get("cooldown_rules", {})
    days_str = cooldown_rules.get(category, "なし")
    if days_str in ("なし", "", None):
        return True
    try:
        cooldown_days = int(re.search(r"(\d+)", str(days_str)).group(1))
    except (AttributeError, ValueError):
        return True

    # Only the policy's approved incident exception can bypass an earlier change.
    if approved_incident:
        return True

    import datetime
    now = datetime.datetime.now(datetime.timezone.utc)
    min_seconds = cooldown_days * 86400

    for entry in entries:
        if not _matches_target(target_path, entry):
            continue
        if entry in current:
            continue  # the operation being checked is not a previous operation
        ts_str = entry.get("timestamp") or entry.get("ts") or ""
        if not ts_str:
            continue
        try:
            ts = datetime.datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=datetime.timezone.utc)
            elapsed = (now - ts).total_seconds()
            if elapsed < min_seconds:
                return False  # cooldown 違反
        except (ValueError, TypeError):
            continue
    return True



def main(argv):
    if "--help" in argv or "-h" in argv:
        print("usage: guard-change-category.py [--policy ABSOLUTE_POLICY_JSON] [--base REF] [--report] [--proposal-id ID] [--bypass-cooldown]")
        print("Installed usage: resolve skill-governance-config root and pass its config/governance-policy.json with --policy. Bypass requires current approved incident content.")
        return 0
    policy_path = None
    base = "origin/main"
    report = False
    bypass_cooldown = False
    proposal_id = None
    for i, a in enumerate(argv):
        if a == "--policy":
            if i + 1 >= len(argv):
                print("ERROR: --policy requires an absolute file path", file=sys.stderr)
                return 2
            policy_path = pathlib.Path(argv[i + 1])
        if a == "--base" and i + 1 < len(argv):
            base = argv[i + 1]
        if a == "--report":
            report = True
        if a == "--bypass-cooldown":
            bypass_cooldown = True
        if a == "--proposal-id" and i + 1 < len(argv):
            proposal_id = argv[i + 1]
    policy = load_policy(policy_path) if policy_path is not None else load_policy()
    files = changed_files(base)
    statuses = changed_file_statuses(base)
    new_plugins = set()
    for path, status in statuses.items():
        match = re.fullmatch(r"(plugins/[^/]+)/\.claude-plugin/plugin\.json", path)
        if match and status[:1] == "A":
            codex_manifest = match[1] + "/.codex-plugin/plugin.json"
            if statuses.get(codex_manifest, "")[:1] == "A" or not pathlib.Path(codex_manifest).exists():
                new_plugins.add(match[1])
    results = []
    blocked = []
    for f in files:
        status = statuses.get(f, "")
        name_changed = (_name_field_changed(f, f"{base}...HEAD")
                        if _SKILL_MD_RE.match(f) and status[:1] not in {"A", "D", "R"} else False)
        new_plugin = any(f.startswith(prefix + "/") for prefix in new_plugins)
        cat = classify_change(f, status, name_changed=name_changed, new_plugin=new_plugin)
        proposal = needs_proposal(cat, policy)
        approved = (has_recent_changelog(f, proposal_id) if proposal_id else has_recent_changelog(f)) if proposal else True
        kwargs = {"bypass": bypass_cooldown}
        if proposal_id:
            kwargs["proposal_id"] = proposal_id
        cooldown_ok = check_cooldown(f, cat, policy, **kwargs)
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
