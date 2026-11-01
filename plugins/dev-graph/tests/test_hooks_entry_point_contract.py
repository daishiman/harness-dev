"""dev-graph の hook entry point は「宣言 = 登録 = hooks/ の実体」で一致する。

package-contract.json の entry_points.hooks・hooks/hooks.json (Claude Code)・codex/hooks.json (Codex)・
hooks/*.py の 4 者を突合する。guard の判定部品 (import 専用 module) は hooks/ ではなく lib/ に置くので、
hooks/ に entry point でない .py が混ざらないことも固定する。repo 全体の parity は
validate-plugin-completeness が見るが、dev-graph は guard を責務分割した plugin なので内訳まで明示する。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[1]
HOOK_SCRIPT = re.compile(r"/hooks/([A-Za-z0-9_.-]+\.py)")


def registered(config_path: Path) -> set[str]:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    names = set()
    for groups in config["hooks"].values():
        for group in groups:
            for hook in group["hooks"]:
                names.update(HOOK_SCRIPT.findall(hook["command"]))
    return names


def test_declared_registered_and_on_disk_hooks_are_the_same_set() -> None:
    contract = json.loads((PLUGIN / "references" / "package-contract.json").read_text(encoding="utf-8"))
    declared = set(contract["entry_points"]["hooks"])
    claude = registered(PLUGIN / "hooks" / "hooks.json")
    on_disk = {path.name for path in (PLUGIN / "hooks").glob("*.py")}

    assert claude, "hooks.json must register at least one hook entry point"
    assert declared == claude == on_disk
    # Codex は TaskCompleted を持たないが、登録する script は宣言の部分集合であること。
    assert registered(PLUGIN / "codex" / "hooks.json") <= declared


def test_guard_support_modules_live_in_lib_not_hooks() -> None:
    for name in ("guard_graph_commands.py", "guard_python_path_eval.py", "guard_python_writes.py", "graph_envelope.py"):
        assert (PLUGIN / "lib" / name).is_file(), name
        assert not (PLUGIN / "hooks" / name).exists(), f"{name} は entry point ではないので hooks/ に置かない"
