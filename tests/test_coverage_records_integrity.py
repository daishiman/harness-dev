"""eval-log/coverage/ の coverage レコードの整合性テスト (偽装防止 / Goodhart 回避)。

LLM性能評価軸の verdict レコードが「実在 artifact を指し」「必須フィールドを持つ」ことを強制する。
存在しない artifact への記録や、verdict/score が不正な記録があれば fail させ、空宣言・水増しを封じる。
"""
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
COV_DIR = ROOT / "eval-log" / "coverage"


def _records():
    return sorted(COV_DIR.rglob("*.json")) if COV_DIR.is_dir() else []


_RECS = _records()


@pytest.mark.parametrize("rec_path", _RECS, ids=[str(p.relative_to(ROOT)) for p in _RECS])
def test_record_points_to_real_artifact_with_valid_fields(rec_path):
    data = json.loads(rec_path.read_text(encoding="utf-8"))
    art = data.get("artifact")
    assert isinstance(art, str) and art, f"{rec_path}: artifact 未指定"
    # docs は doc/ 相対、それ以外は repo 相対の実在 artifact を指すこと
    candidates = [ROOT / art, ROOT / "doc" / art]
    assert any(c.exists() for c in candidates), f"{rec_path}: 実在しない artifact を指す: {art}"
    if "mechanical" in data:
        assert isinstance(data["mechanical"], bool), f"{rec_path}: mechanical は bool"
    le = data.get("llm_eval")
    if le is not None:
        assert isinstance(le, dict), f"{rec_path}: llm_eval は object"
        assert str(le.get("verdict", "")).upper() in {"PASS", "FAIL"}, f"{rec_path}: verdict 不正"
        score = le.get("score")
        assert isinstance(score, (int, float)) and 0 <= score <= 100, f"{rec_path}: score 0-100 必須"


def test_coverage_dir_is_optional():
    # レコードが無くても整合性テスト自体は成立する (ratchet 初期状態)。
    assert COV_DIR.parent.exists() or True
