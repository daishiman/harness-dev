#!/usr/bin/env python3
"""UserPromptSubmit hook: stale 時のみ cache refresh。常に exit 0。"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
NOTIFIER = HERE / "notifier-check.py"


# 本ファイル: plugins/harness-creator/skills/run-skill-update-notifier/scripts/hook-cache-refresh.py
# __file__.parents[3] = plugin-root (harness-creator)、parents[4] = plugins/。
PLUGIN_ROOT = Path(__file__).resolve().parents[3]


def _manifest_name(root: Path) -> str | None:
    """<root>/.claude-plugin/plugin.json の name。読めなければ None。"""
    try:
        manifest = json.loads(
            (root / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
        )
    except (OSError, ValueError):
        return None
    return manifest.get("name") if isinstance(manifest, dict) else None


def _self_plugin_name() -> str | None:
    """このファイル自身が属する plugin の manifest name。

    リテラル直書きは制御リテラル散在として禁止 (tests/test_dogfooding_boundary.py)、
    SSOT 定数は「SSOT を探すのに plugin root が要る」循環のため使えない。__file__ は
    循環せず改名にも自動追従する第三の出所。plugin は入れ子にならないので、上向きに
    最初に見つかる manifest が自 plugin のもので確定する。
    """
    for parent in Path(__file__).resolve().parents:
        name = _manifest_name(parent)
        if name:
            return name
    return None


def _hc_env_root() -> Path | None:
    """env から自 plugin root を得る。他 plugin を指す値は拒否する。

    他 repo が .claude 平置き projection で本 plugin を借用している場合、
    env CLAUDE_PLUGIN_ROOT は **別 plugin** を指していることがある
    (ObsidianMemo では ubm-goal-setting)。空ではなく「存在するが別物」なので
    `if env:` では弾けない。manifest の name で自 plugin か検証する。
    借用側は HC_ROOT を設定すれば明示指定できる。
    拒否するのは manifest が読めて **別 plugin と確認できた** 場合だけにする。
    判定材料が無い (manifest 不在) env は従来どおり採用し、既存挙動を後退
    させない。vendored コピー先 (company-master / skill-intake) でも同様。
    """
    expected = _self_plugin_name()
    if not expected:
        return None
    for _var in ("HC_ROOT", "CLAUDE_PLUGIN_ROOT"):
        raw = os.environ.get(_var)
        if not raw:
            continue
        root = Path(raw).expanduser()
        _name = _manifest_name(root)
        if _name is None or _name == expected:
            return root.resolve()
    return None


def _plugin_root() -> Path:
    return _hc_env_root() or PLUGIN_ROOT


def _plugins_root() -> Path:
    """notifier-check が走査する「複数 plugin を含む plugins/ ディレクトリ」を
    cwd 非依存で self-relative に解決する。

    解決順:
      1. env `CLAUDE_PLUGIN_ROOT` (= 単一 plugin ルート、慣習) があればその親 = plugins/。
         install 先 / dev いずれも同一の plugins/ を指す。
      2. 無ければ本ファイル位置から導出。plugin-root (parents[3]) の親 = plugins/。
    notifier-check.py:cmd_refresh は渡された root を glob("*/") で走査し各 subdir を
    plugin として扱うため、単一 plugin ルートではなく plugins/ を渡すのが正しい意味。
    """
    return _plugin_root().parent


def main() -> int:
    try:
        status = subprocess.run(
            ["python3", str(NOTIFIER), "cache-status"],
            capture_output=True, text=True, timeout=5,
        ).stdout.strip()
        if status in ("stale", "absent"):
            subprocess.run(
                ["python3", str(NOTIFIER), "refresh",
                 "--plugins-root", str(_plugins_root()),
                 "--plugin-root", str(_plugin_root())],
                capture_output=True, text=True, timeout=15,
            )
    except Exception as exc:
        print(f"[notifier-hook] skipped: {exc}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
