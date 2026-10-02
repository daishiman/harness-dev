"""system-briefing-book の slash command 契約を構造検証する repo-root テスト。

commands/briefing-build.md と commands/briefing-revise.md の frontmatter が
command 契約 (name=ファイル stem / kind=command / description / allowed-tools /
entrypoint 先 skill 実在) を満たし、本文が entrypoint へ渡すサブコマンドが
entrypoint skill の argument-hint に実在することを機械保証する。plugin 埋込テストは
repo-root tests/ から収集されないため、command 表面の回帰を repo-root 層でも
捕捉する (harness-coverage の commands/mechanical 被覆にも寄与する)。
"""
from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CMD_DIR = ROOT / "plugins" / "system-briefing-book" / "commands"
SKILLS_DIR = ROOT / "plugins" / "system-briefing-book" / "skills"

# (command stem, 期待 entrypoint skill, entrypoint へ渡すサブコマンド)
COMMANDS = [
    ("briefing-build", "run-briefing", "new"),
    ("briefing-revise", "run-briefing", "revise"),
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


@pytest.mark.parametrize("stem,entrypoint,subcommand", COMMANDS)
def test_command_contract(stem: str, entrypoint: str, subcommand: str):
    md = CMD_DIR / f"{stem}.md"
    assert md.is_file(), f"command {stem}.md が存在しない"
    fm = _frontmatter(md)
    assert fm.get("name") == stem, f"{stem}: frontmatter name={fm.get('name')!r} が stem と不一致"
    assert fm.get("kind") == "command", f"{stem}: kind != command"
    assert fm.get("description"), f"{stem}: description 欠落"
    assert fm.get("allowed-tools"), f"{stem}: allowed-tools 欠落"
    assert fm.get("entrypoint") == entrypoint, f"{stem}: entrypoint={fm.get('entrypoint')!r} 期待={entrypoint!r}"
    assert (SKILLS_DIR / entrypoint / "SKILL.md").is_file(), f"{stem}: entrypoint skill {entrypoint} が実在しない"


@pytest.mark.parametrize("stem,entrypoint,subcommand", COMMANDS)
def test_command_subcommand_matches_entrypoint_hint(stem: str, entrypoint: str, subcommand: str):
    body = (CMD_DIR / f"{stem}.md").read_text(encoding="utf-8")
    hint = _frontmatter(SKILLS_DIR / entrypoint / "SKILL.md").get("argument-hint", "")
    modes = {alt.split()[0] for alt in hint.split("|") if alt.strip()}
    assert subcommand in modes, f"{entrypoint} の argument-hint に {subcommand!r} が無い: {hint!r}"
    assert f"`{subcommand} " in body, f"{stem}: 本文が {entrypoint} へ {subcommand!r} を渡していない"


def test_every_command_file_is_covered():
    stems = {p.stem for p in CMD_DIR.glob("*.md")}
    assert stems == {stem for stem, _, _ in COMMANDS}, f"未検査の command がある: {sorted(stems)}"
