#!/usr/bin/env python3
"""feedback_protocol SSOT 整合 lint (オフライン、NOTION_TOKEN 不要)。

検証:
  R1. skill-list.schema.json#feedback_protocol が必須キーを満たす
  R2. page_body_sections に id=feedback (renderer_ref=feedback_protocol) が含まれる
  R3. run-skill-feedback/SKILL.md が schema を SSOT として参照している
  R4. run-skill-feedback/SKILL.md の triggers が firing_conditions を包含する近似 (各 firing_condition の主要キーワードが triggers のいずれかに含まれる)
  R5. notion-upsert-plugin.py が _load_feedback_protocol() を経由している
  R6. 量産プラグイン (plugins/*/plugin.json 保持) の README/plugin.json/commands/agents に run-skill-feedback 発火経路が周知されている
      (default warn / --strict で exit 1)
  R7. 量産プラグイン (生成器自身=feedback_contract_ssot.is_feedback_deploy_exempt で除外) の skills/run-skill-feedback/ が symlink/実体で配備されている
      (default warn / --strict で exit 1)

Usage:
  python3 scripts/lint-feedback-protocol.py [--strict]
"""
import argparse, json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# dogfooding 除外境界は SSOT (FC.is_feedback_deploy_exempt) が単一正本。
sys.path.insert(0, str(ROOT / "scripts"))
import feedback_contract_ssot as FC  # noqa: E402
SCHEMA = ROOT / "doc" / "notion-schema" / "skill-list.schema.json"
SKILL_MD = ROOT / "plugins" / "harness-creator" / "skills" / "run-skill-feedback" / "SKILL.md"
UPSERT = ROOT / "scripts" / "notion-upsert-plugin.py"


PLUGINS_DIR = ROOT / "plugins"
FEEDBACK_KEYWORD = "run-skill-feedback"


def _target_plugins():
    """検査対象 plugin (manifest を持ち、生成器自身=配備除外プラグインは除外)。

    除外境界は SSOT 述語 (FC.is_feedback_deploy_exempt) に委譲する。
    """
    if not PLUGINS_DIR.exists():
        return []
    out = []
    for plugin_dir in sorted(PLUGINS_DIR.iterdir()):
        if not plugin_dir.is_dir():
            continue
        if FC.is_feedback_deploy_exempt(plugin_dir.name):
            continue
        manifests = [
            plugin_dir / ".claude-plugin" / "plugin.json",
            plugin_dir / "plugin.json",
            plugin_dir / "plugin-composition.yaml",
        ]
        if not any(p.exists() for p in manifests):
            continue
        out.append(plugin_dir)
    return out


def check_plugin_awareness():
    """R6: 量産プラグイン側に発火経路 (run-skill-feedback) の周知文言があるか。

    haystack: manifest (plugin.json / .claude-plugin/plugin.json / plugin-composition.yaml)
              + README.md + commands/*.md + agents/*.md
    """
    warnings = []
    for plugin_dir in _target_plugins():
        haystack = ""
        candidates = [
            plugin_dir / ".claude-plugin" / "plugin.json",
            plugin_dir / "plugin.json",
            plugin_dir / "plugin-composition.yaml",
            plugin_dir / "README.md",
        ]
        for sub in ("commands", "agents"):
            d = plugin_dir / sub
            if d.is_dir():
                candidates.extend(sorted(d.glob("*.md")))
        for p in candidates:
            if p.exists():
                try:
                    haystack += p.read_text()
                except Exception:
                    pass
        if FEEDBACK_KEYWORD not in haystack:
            warnings.append(f"R6: {plugin_dir.name} に '{FEEDBACK_KEYWORD}' 発火経路の周知記載が無い (manifest/README/commands/agents)")
    return warnings


def check_plugin_deployment():
    """R7: 量産プラグインに skills/run-skill-feedback/ が symlink/実体で配備されているか。"""
    warnings = []
    for plugin_dir in _target_plugins():
        target = plugin_dir / "skills" / "run-skill-feedback"
        # symlink でも実体でも存在すれば OK (broken symlink は exists() が False)
        if not (target.exists() or target.is_symlink()):
            warnings.append(f"R7: {plugin_dir.name} に skills/run-skill-feedback/ 配備なし")
            continue
        if target.is_symlink() and not target.exists():
            warnings.append(f"R7: {plugin_dir.name}/skills/run-skill-feedback/ が broken symlink")
    return warnings


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", action="store_true", help="R6/R7 を fail (exit 1) として扱う")
    args = ap.parse_args()
    violations = []
    sc = json.loads(SCHEMA.read_text())

    # R1
    fp = sc.get("feedback_protocol")
    required = {"command", "firing_conditions", "intake_fields", "status_lifecycle",
                "open_statuses", "promise_to_reporter", "callout_summary"}
    if not fp:
        violations.append("R1: skill-list.schema.json に feedback_protocol が無い")
    else:
        missing = required - set(fp.keys())
        if missing:
            violations.append(f"R1: feedback_protocol に必須キー欠落: {sorted(missing)}")

    # R2
    sections = sc.get("page_body_sections", [])
    fb_sec = next((s for s in sections if s.get("id") == "feedback"), None)
    if not fb_sec:
        violations.append("R2: page_body_sections に id=feedback が無い")
    elif fb_sec.get("renderer_ref") != "feedback_protocol":
        violations.append("R2: feedback section の renderer_ref が feedback_protocol を指していない")

    # R3
    md = SKILL_MD.read_text() if SKILL_MD.exists() else ""
    if "feedback_protocol" not in md or "skill-list.schema.json" not in md:
        violations.append("R3: run-skill-feedback/SKILL.md が schema feedback_protocol を参照していない")

    # R4: firing_conditions の主要語が triggers に存在
    if fp:
        tr_match = re.search(r"^triggers:\s*\n((?:\s+-.*\n)+)", md, re.M)
        triggers_blob = tr_match.group(1) if tr_match else ""
        keywords = ["分かりにくい", "直してほしい", "バグ", "改善", "要望"]
        missing_kw = [k for k in keywords if k not in triggers_blob and k not in md]
        if missing_kw:
            violations.append(f"R4: SKILL.md triggers/本文に発火キーワード欠落: {missing_kw}")

    # R5
    src = UPSERT.read_text() if UPSERT.exists() else ""
    if "_load_feedback_protocol" not in src:
        violations.append("R5: notion-upsert-plugin.py が _load_feedback_protocol() を未使用")

    if violations:
        print(f"[FAIL] feedback_protocol SSOT lint: {len(violations)} violation(s)")
        for v in violations:
            print(f"  - {v}")
        sys.exit(1)

    r6_warnings = check_plugin_awareness()
    r7_warnings = check_plugin_deployment()
    has_warn = bool(r6_warnings or r7_warnings)
    label = "FAIL" if args.strict else "WARN"
    if r6_warnings:
        print(f"[{label}] R6 周知 lint: {len(r6_warnings)} 件")
        for w in r6_warnings:
            print(f"  - {w}")
    if r7_warnings:
        print(f"[{label}] R7 配備 lint: {len(r7_warnings)} 件")
        for w in r7_warnings:
            print(f"  - {w}")
    if has_warn and args.strict:
        sys.exit(1)

    print("[OK] feedback_protocol SSOT lint: all checks passed")


if __name__ == "__main__":
    main()
