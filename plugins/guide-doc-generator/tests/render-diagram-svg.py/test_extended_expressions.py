"""文章の関係を保持する図解と、入力誤りを黙って図にしないことを確認する。"""
import importlib.util
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

ROOT = Path(__file__).resolve().parents[2]


def renderer():
    spec = importlib.util.spec_from_file_location("extended_diagrams", ROOT / "scripts/render-diagram-svg.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def catalog():
    return json.loads((ROOT / "config/handout-diagrams.json").read_text())


def test_catalog_examples_render_and_preserve_labels():
    module = renderer()
    entries = catalog()["patterns"]
    assert set(entries) == set(module.BUILDERS)
    for pattern, entry in entries.items():
        sample = dict(entry["example"], id="sample-" + pattern, title=entry["title"])
        svg = module.render_diagram(sample, pattern)
        root = ET.fromstring(svg)
        assert root.attrib["role"] == "img"
        assert root.find("title").text == entry["title"]
        assert root.findall(".//text")
        assert svg == module.render_diagram(sample, pattern)
        assert "http" not in svg and "<script" not in svg


def test_native_schema_and_catalog_do_not_drift():
    schema = json.loads((ROOT / "schemas/handout-config.schema.json").read_text())
    assert set(schema["$defs"]["diagram"]["properties"]["pattern"]["enum"]) == set(catalog()["patterns"])
    for entry in catalog()["intents"]:
        for pattern in entry.get("patterns", []):
            assert pattern in catalog()["patterns"]


@pytest.mark.parametrize("pattern,data", [
    ("relationship", {"nodes": [{"id": "a", "label": "受付", "row": 0, "col": 0}], "edges": [{"from": "a", "to": "missing"}]}),
    ("relationship", {"nodes": [{"id": "a", "label": "受付", "row": 0, "col": 0}, {"id": "b", "label": "承認", "row": 0, "col": 0}], "edges": []}),
    ("relationship", {"nodes": [{"id": "a", "label": "受付", "row": 0, "col": 0}, {"id": "b", "label": "承認", "row": 1, "col": 0}], "edges": []}),
    ("relationship", {"nodes": [{"id": "a", "label": "確認", "row": 0, "col": 0, "shape": "decision"}, {"id": "b", "label": "承認", "row": 1, "col": 0}], "edges": [{"from": "a", "to": "b"}]}),
    ("relationship", {"nodes": [{"id": "a", "label": "受付", "row": 0, "col": 0}, {"id": "b", "label": "確認", "row": 1, "col": 0}, {"id": "c", "label": "承認", "row": 2, "col": 0}], "edges": [{"from": "a", "to": "c"}, {"from": "b", "to": "c"}]}),
    ("bar", {"items": [{"label": "実績", "value": float("nan")}], "unit": "件"}),
    ("bar", {"items": [{"label": "実績", "value": -1}], "unit": "件"}),
    ("line", {"items": [{"label": "月曜", "value": 1}], "unit": "件"}),
    ("gantt", {"tasks": [{"label": "準備", "start": "2026-02-30", "end": "2026-03-02"}]}),
    ("gantt", {"tasks": [{"label": "準備", "start": "2026-03-02", "end": "2026-03-01"}]}),
    ("sequence", {"actors": ["受付", "担当"], "messages": [{"from": "受付", "to": "不在", "label": "依頼"}]}),
])
def test_invalid_relations_and_quantities_fail_with_actionable_error(pattern, data):
    module = renderer()
    assert pattern in module.BUILDERS
    with pytest.raises(module.DiagramError):
        module.render_diagram(dict(data, title="入力誤り"), pattern)


def test_chart_has_unit_and_zero_baseline_without_invented_values():
    module = renderer()
    svg = module.render_diagram({"title": "件数比較", "unit": "件", "items": [{"label": "受付", "value": 0}, {"label": "完了", "value": 12}]}, "bar")
    labels = " ".join(ET.fromstring(svg).itertext())
    assert "0件" in labels and "12件" in labels
