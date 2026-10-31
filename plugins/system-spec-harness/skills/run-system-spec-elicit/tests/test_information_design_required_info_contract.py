"""人が読む表現物の情報設計を frontend のクライアント構成より先に確かめる契約を固定する。"""

import json
import subprocess
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
CATALOG = SKILL_DIR / "references" / "required-info-catalog.json"
QUESTION_BANK = SKILL_DIR / "references" / "elicit-question-bank.md"
SKILL = SKILL_DIR / "SKILL.md"
R2 = SKILL_DIR / "prompts" / "R2-interview.md"
R3 = SKILL_DIR / "prompts" / "R3-reask.md"
R5 = SKILL_DIR / "prompts" / "R5-decision-guide.md"
VALIDATOR = SKILL_DIR.parents[1] / "scripts" / "validate-knowledge-graph.py"


def _catalog_items() -> dict[str, dict]:
    payload = json.loads(CATALOG.read_text(encoding="utf-8"))
    return {item["item_id"]: item for item in payload["items"]}


def _validator_report() -> dict:
    result = subprocess.run(
        [
            "python3",
            str(VALIDATOR),
            "--profile",
            "required-info",
            "--input",
            str(CATALOG),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def test_information_priority_precedes_frontend_arch() -> None:
    items = _catalog_items()
    context = items["context-of-use"]
    priority = items["information-priority"]
    frontend = items["frontend-arch"]

    # 利用文脈は常に必須 (block)。取捨と順位は非適用理由を許す degrade のまま
    # (SKILL.md の『情報優先度の責務境界』が正本)。
    assert context["missing_effect"] == "block"
    assert context["required_when"] == "always"
    assert priority["missing_effect"] == "degrade"
    assert "context-of-use" in priority["depends_on"]
    assert "非適用" in priority["completion_rule"]
    # 取捨と順位が決まる前にクライアント構成を確定しないことを依存辺で保証する
    # (Kahn 法の同順位 id 昇順に頼らない)。
    assert "information-priority" in frontend["depends_on"]

    report = _validator_report()
    assert "context-of-use" in report["coverage_certificate"]["blocking_items"]
    order = report["collection_order"]
    assert order.index("context-of-use") < order.index("information-priority")
    assert order.index("information-priority") < order.index("frontend-arch")


def test_catalog_and_question_bank_cover_usage_context_and_visual_devices() -> None:
    items = _catalog_items()
    context = items["context-of-use"]
    priority = items["information-priority"]
    question_bank = QUESTION_BANK.read_text(encoding="utf-8")

    context_terms = ("端末", "支援技術", "データ量", "件数・項目数", "比較・一括操作")
    for term in context_terms:
        assert term in context["question"], term
        assert term in question_bank, term
    priority_terms = ("情報密度", "ラベル", "区切り線", "アイコン", "画像", "強調", "操作可能性")
    for term in priority_terms:
        assert term in priority["question"], term
        assert term in question_bank, term
    assert "情報密度" in priority["completion_rule"]
    assert "視覚装置" in priority["completion_rule"]

    for item_id in ("context-of-use", "information-priority", "frontend-arch"):
        assert f"`{item_id}`" in question_bank, item_id
    assert "クライアント構成より先" in question_bank
    # 情報設計の論点も表の論点と同じく束ねて 1 問にしない (N4)。
    assert "並べて 1 問にしない" in question_bank
    assert "CLI・機械間 API・batch を無理に画面へ読み替えない" in question_bank


def test_prompts_consume_required_info_catalog() -> None:
    assert "required-info-catalog.json" in R2.read_text(encoding="utf-8")
    assert "required-info-catalog.json" in R3.read_text(encoding="utf-8")
    r5 = R5.read_text(encoding="utf-8")
    assert "collection_order" in r5
    assert "required-info-catalog.json" in r5
    assert "情報優先度の責務境界" in SKILL.read_text(encoding="utf-8")
