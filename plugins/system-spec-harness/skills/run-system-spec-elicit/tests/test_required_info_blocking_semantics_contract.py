"""required-info の blocking_items を未解決一覧と誤読しない契約を固定する。"""
from pathlib import Path


SKILL = Path(__file__).resolve().parents[1] / "SKILL.md"
R5 = Path(__file__).resolve().parents[1] / "prompts" / "R5-decision-guide.md"


def test_blocking_items_are_declared_required_ids_not_an_empty_completion_list() -> None:
    skill = SKILL.read_text(encoding="utf-8")
    r5 = R5.read_text(encoding="utf-8")

    for text in (skill, r5):
        assert "未解決一覧" in text
        assert "収集必須 item ID 一覧" in text
        assert "確定 foundation/matrix/decision の" in text
        assert "blocking_items` が空" not in text
        assert "blocking_items が未充足" not in text
        assert "missing_effect=block` の未充足 item" not in text
    assert "未接地 ID だけを block" in r5
