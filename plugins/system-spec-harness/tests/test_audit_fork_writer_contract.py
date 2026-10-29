"""R2 の audit fork 台帳 writer 契約を1正本に保つドキュメントテスト。"""

from pathlib import Path


R2_DELEGATE = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "assign-system-spec-completeness-evaluator"
    / "prompts"
    / "R2-delegate.md"
)


def test_ledger_writer_is_hook_layer_only_with_two_explicit_events() -> None:
    """R2/agent が writer に見えず、2つの hook event の責務が一意である。"""
    contract = R2_DELEGATE.read_text(encoding="utf-8")

    assert "台帳を書けるのは hook 層だけ" in contract
    assert "PostToolUse が dispatch 行" in contract
    assert "SubagentStop が completion 行" in contract
    assert "R2 および監査 agent は台帳を作成・追記・補正してはならない" in contract
    assert "PostToolUse hook だけが書く" not in contract
