"""system-spec-harness の slash command 契約を構造検証する repo-root テスト。

commands/spec-hearing-start.md と commands/spec-compile.md の frontmatter が
command 契約 (name=ファイル stem / kind=command / description / allowed-tools /
entrypoint 先 skill 実在) を満たすことを機械保証する。plugin 埋込テストは
repo-root tests/ から収集されないため、command 表面の回帰を repo-root 層でも
捕捉する (harness-coverage の commands/mechanical 被覆にも寄与する)。
"""
from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CMD_DIR = ROOT / "plugins" / "system-spec-harness" / "commands"
SKILLS_DIR = ROOT / "plugins" / "system-spec-harness" / "skills"

# (command stem, 期待 entrypoint skill)
COMMANDS = [
    ("spec-hearing-start", "run-system-spec-elicit"),
    ("spec-compile", "run-system-spec-compile"),
]


def _frontmatter(md: Path) -> dict:
    """--- 区切りの flat な key: value frontmatter を辞書化する。"""
    text = md.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    block = text[3:end] if end != -1 else ""
    out: dict[str, str] = {}
    for line in block.splitlines():
        if ":" in line and not line.lstrip().startswith("#"):
            k, _, v = line.partition(":")
            out[k.strip()] = v.strip().strip('"')
    return out


@pytest.mark.parametrize("stem,entrypoint", COMMANDS)
def test_command_contract(stem: str, entrypoint: str):
    md = CMD_DIR / f"{stem}.md"
    assert md.is_file(), f"command {stem}.md が存在しない"
    fm = _frontmatter(md)
    assert fm.get("name") == stem, f"{stem}: frontmatter name={fm.get('name')!r} が stem と不一致"
    assert fm.get("kind") == "command", f"{stem}: kind != command"
    assert fm.get("description"), f"{stem}: description 欠落"
    assert fm.get("allowed-tools"), f"{stem}: allowed-tools 欠落"
    assert fm.get("entrypoint") == entrypoint, f"{stem}: entrypoint={fm.get('entrypoint')!r} 期待={entrypoint!r}"
    assert (SKILLS_DIR / entrypoint).is_dir(), f"{stem}: entrypoint skill {entrypoint} が実在しない"
