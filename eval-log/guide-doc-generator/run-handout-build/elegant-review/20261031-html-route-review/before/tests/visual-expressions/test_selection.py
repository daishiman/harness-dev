"""図解を検討せず通す・選定だけして配置しない経路を防ぐ。"""
import copy
import importlib.util
from pathlib import Path


spec = importlib.util.spec_from_file_location("visual_selection", Path(__file__).resolve().parents[2] / "scripts/validate-visual-selection.py")
selection = importlib.util.module_from_spec(spec)
spec.loader.exec_module(selection)


def fixture():
    config = {"sections": [{"id": "request", "parts": [{"id": "result", "part": "DIAGRAM"}]}]}
    receipt = {"config_sha256": selection.config_digest(config), "decision_log": [{
        "kind": "visual-selection", "section_id": "request", "source_excerpt": "依頼を送ると担当が結果を返す",
        "reader_question": "誰が何を受け渡すか", "relations": "担当間の受け渡しと順序",
        "candidates": [{"form": "sequence", "reason": "担当と時系列を同時に表せる"}, {"form": "flow", "reason": "順序は分かるが担当を追いにくい"}],
        "chosen": "sequence", "mode": "diagram", "target_part_ids": ["result"],
        "reason": "受け渡しが判断の中心", "preserved_facts": ["依頼を送る", "結果を返す"], "replaced_content": ["受け渡しを説明する段落"]
    }]}
    return config, receipt


def test_selection_is_bound_to_placed_content():
    config, receipt = fixture()
    assert selection.validate(config, receipt) == []


def test_missing_and_stale_selections_are_rejected():
    config, receipt = fixture()
    missing = copy.deepcopy(receipt); missing["decision_log"] = []
    assert selection.validate(config, missing)
    config["sections"][0]["heading"] = "内容を変更"
    assert selection.validate(config, receipt)


def test_unconnected_target_and_media_mismatch_are_rejected():
    config, receipt = fixture()
    receipt["decision_log"][0]["target_part_ids"] = ["missing"]
    assert selection.validate(config, receipt)
    receipt["decision_log"][0]["target_part_ids"] = ["result"]
    receipt["decision_log"][0]["mode"] = "image"
    assert selection.validate(config, receipt)


def test_catalog_outside_form_can_use_a_real_image_part():
    config, receipt = fixture()
    config["sections"][0]["parts"][0]["part"] = "IMG"
    receipt["config_sha256"] = selection.config_digest(config)
    receipt["decision_log"][0].update(chosen="専用作図した新しい表現", mode="image")
    assert selection.validate(config, receipt) == []
