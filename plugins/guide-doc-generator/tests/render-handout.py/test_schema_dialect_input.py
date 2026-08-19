"""C11 が C12 schema 正本の構成データをそのまま受理することの受入 (P05-x-20)。

裁定は schemas/INPUT-CONTRACT-RESOLUTION.md。schema (handout-config.schema.json)
に適合する構成データ = sections[].parts / normalized なし / nav なし を
render-handout.py へ渡すと exit 0 で全部品が描画されることを検査する。

構成データが schema に適合していることは自分で判定せず C12
(validate-handout-config.py --config が exit 0) に判定させる。
部品の網羅はカタログから導出するので、部品を足して fixture を足さなければ赤になる。
"""

import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import _harness as H

VALIDATOR = H.PLUGIN_ROOT / "scripts" / "validate-handout-config.py"

SCHEMA_VERSION_POINTER = ("properties", "schema_version", "const")
NORMALIZED_BY_POINTER = ("$defs", "provenance", "properties", "normalized_by", "const")

# schema の $defs.part_data が定める data の形の fixture。
# 鍵は部品カタログの data_block_type であり part id をここへ列挙しない。
PART_DATA_FIXTURES = {
    "steps": {"rows": [
        {"key": "st1", "text": "資料を開く", "sub": "手元で開く"},
        {"key": "st2", "text": "設定を確認する"},
    ]},
    "trio": {"cards": [
        {"label": "分かっている", "body": "既知の範囲", "tone": "today", "note_key": "tr1"},
        {"label": "分からない", "body": "未知の範囲", "tone": "rest"},
    ]},
    "table": {
        "columns": ["案A", "案B"],
        "rows": [
            {"header": "速さ", "cells": ["速い", "遅い"], "highlight": [0]},
            {"header": "費用", "cells": ["高い", "安い"]},
        ],
    },
    "versus": {
        "left": {"label": "自前で作る", "items": ["自由度が高い"]},
        "right": {"label": "既製品を使う", "items": ["早く始められる"]},
    },
    "features": {"cards": [
        {"title": "自動化", "body": "手作業を減らす", "footnote": "社内検証 2026", "icon": "check"},
        {"title": "共有", "body": "同じ資料を配る"},
    ]},
    "map": {"items": [
        {"key": "mp1", "title": "調べる", "detail": "検索して確かめる"},
        {"key": "mp2", "title": "聞く", "detail": "担当者に確認する"},
    ]},
    "checklist": {"rows": [
        {"key": "ck1", "text": "権限を確認した"},
        {"key": "ck2", "text": "配布先を決めた"},
    ]},
    "accordion": {"items": [{"summary": "補足", "body": "詳しい説明の本文", "open": False}]},
    "prompt": {"label": "貼り付けるプロンプト", "body": "次の資料を要約してください", "copyable": True},
    "download": {"attachment_id": "att-1", "label": "手順書をダウンロードする"},
    "tabs": {"tabs": [
        {"key": "tb1", "label": "概要", "panel_parts": [
            {"part": None, "id": "p-tab-text", "data": {"body": "タブ内の地の文をここへ置く。"}},
        ]},
        {"key": "tb2", "label": "詳細", "panel_parts": [
            {"part": None, "id": "p-tab-text2", "data": {"body": "2 枚目のタブの地の文。"}},
        ]},
    ]},
    "flow": {"steps": [{"title": "受付", "body": "窓口で受ける"}, {"title": "確認"}]},
    "chips": {"key": "cp", "single": True, "chips": [
        {"key": "cp1", "label": "はい"},
        {"key": "cp2", "label": "いいえ"},
    ]},
    "action-items": {"rows": [
        {"key": "ai1", "text": "議事録を配布する", "owner": "山田", "due": "2026/01/09"},
    ]},
    "handson": {
        "steps": [{"operation": "画面右上のボタンを押す", "expected": "一覧が表示される",
                   "stuck_hint": "権限設定を見直す"}],
        "asset_id": "asset-1",
        "live_demo": True,
    },
    "image": {"asset_id": "asset-1", "lightbox": True},
    "diagram": {"diagram_id": "dg-1"},
    "text": {"body": "どの型にも当てはまらない地の文をここへ置く。"},
}


def schema_const(pointer):
    node = H.load_config_schema()
    for key in pointer:
        node = node[key]
    return node


def in_section_catalog_parts():
    return [p for p in H.catalog_parts()
            if p["section_scope"] == "in-section" and p["data_block_type"]]


def part_id_for(block_type):
    for part in H.catalog_parts():
        if part["data_block_type"] == block_type:
            return part["id"]
    raise AssertionError("data_block_type=%s の部品がカタログに無い" % block_type)


def schema_parts():
    """カタログ順に全 in-section 部品を 1 件ずつ並べた parts[]。"""
    text_part_id = part_id_for("text")
    parts = []
    for index, entry in enumerate(in_section_catalog_parts()):
        data = copy.deepcopy(PART_DATA_FIXTURES[entry["data_block_type"]])
        for tab in data.get("tabs") or []:
            for inner in tab.get("panel_parts") or []:
                inner["part"] = text_part_id
        parts.append({"part": entry["id"], "id": "p-%d" % (index + 1), "data": data})
    return parts


def schema_config(parts=None):
    """schema (C12) に適合する構成データ。normalized / nav / blocks を持たない。"""
    section = {
        "id": "s1",
        "heading": "全体の流れ",
        "goal": "このセクションのゴールをここに書く",
        "lead_line": "このセクションで押さえる 1 行の抽象",
        "judgment_axis": "迷ったら手戻りの少ない方を選ぶ",
        "role": "main",
        "ties_to": ["goal", "target_task:tt1"],
        "attainment_step": "operable",
        "section_kind": "standard",
        "parts": schema_parts() if parts is None else parts,
        "glossary": [],
    }
    return {
        "schema_version": schema_const(SCHEMA_VERSION_POINTER),
        "title": "配布資料のサンプル",
        "subject_slug": "handout-sample",
        "date": H.DEFAULT_DATE,
        "doc_type": "guide",
        "purpose": "同じ手順で誰でも同じ結果に届くようにする",
        "background": "これまで口頭で共有しており、抜けが起きていた",
        "goal": "配布後 1 週間で全員が自力で最後まで実施できる",
        "reader": "はじめて触る担当者",
        "prior_knowledge_level": "none",
        "detail_level": "standard",
        "evidence_depth": "cited",
        "essential_problem": "手順が人によって違い、結果がそろわない",
        "focus_theme": ["手順をそろえて同じ結果に届く"],
        "target_tasks": [{"id": "tt1", "label": "週次レポートを自分で作る"}],
        "presentation_order": "demo_first",
        "attainment_level": "operable",
        "must_remember": ["最初に権限を確認する"],
        "must_remember_max": 2,
        "no_need_to_remember": ["画面の細かい配置はこの資料を見返せばよい"],
        "glossary": [{"term": "権限", "plain": "その操作をしてよいかどうかの設定"}],
        "notes_enabled": True,
        "sections": [section],
        "assets": [{
            "id": "asset-1", "kind": "image", "src": H.PNG_DATA_URI,
            "alt": "操作画面のスクリーンショット", "caption": "実際の画面", "role": "screenshot",
        }],
        "attachments": [{
            "id": "att-1", "filename": "sample.txt", "mime": "text/plain",
            "src": "data:text/plain;base64,YQ==",
            "fallback_hint": "保存できないときは本文をコピーする",
        }],
        "diagrams": [{
            "id": "dg-1", "pattern": "flow", "title": "処理の流れ",
            "data": {"steps": [{"key": "dg1", "label": "入力"}, {"key": "dg2", "label": "出力"}]},
        }],
        "provenance": {
            "normalized_by": schema_const(NORMALIZED_BY_POINTER),
            "schema_version": "1.0",
            "date_source": "config",
            "presentation_order_source": "derived-from-prior-knowledge",
        },
    }


def run_validator(config_path):
    return subprocess.run(
        [sys.executable, str(VALIDATOR), "--config", str(config_path)],
        capture_output=True, text=True,
        env={**os.environ, "HB_ROOT": str(H.PLUGIN_ROOT)},
    )


class FixtureCoverageTest(unittest.TestCase):
    def test_every_in_section_part_has_a_schema_data_fixture(self):
        missing = [p["id"] for p in in_section_catalog_parts()
                   if p["data_block_type"] not in PART_DATA_FIXTURES]
        self.assertEqual([], missing, "schema 方言の fixture が無い部品: %r" % missing)


class SchemaDialectAcceptanceTest(unittest.TestCase):
    """AC (P05-x-20): schema 適合の構成データが exit 0 で全部品を描画する。"""

    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.addCleanup(self._td.cleanup)
        self.config = schema_config()
        self.cfg_path = H.write_config(Path(self._td.name) / "config.json", self.config)

    def test_fixture_is_accepted_by_c12_as_schema_conformant(self):
        """schema 適合の判定は C12 に委ねる (テスト側で schema を解釈しない)。"""
        proc = run_validator(self.cfg_path)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)

    def test_render_exits_zero_and_draws_every_part(self):
        out = Path(self._td.name) / "handout.html"
        res = H.run_render(["--config", self.cfg_path, "--out", out])
        self.assertEqual(0, res.returncode, res.stderr)
        html_text = out.read_text(encoding="utf-8")

        parts = self.config["sections"][0]["parts"]
        drawn = H.elements_with(html_text, "data-hb-part")
        self.assertGreaterEqual(
            len(drawn), len(parts),
            "data-hb-part 要素が parts の件数に満たない: %d < %d" % (len(drawn), len(parts)))
        for part in parts:
            with self.subTest(part=part["part"]):
                self.assertTrue(
                    H.part_elements(html_text, part["part"]),
                    "部品 %s が描画されていない" % part["part"])
                self.assertTrue(
                    H.elements_with(html_text, "data-hb-part-id", part["id"]),
                    "部品 id %s が描画されていない" % part["id"])

        payload = res.json_line()
        self.assertTrue(payload["blocks_by_type"], "blocks_by_type が空 (部品が 1 件も描画されていない)")

    def test_nav_is_derived_from_sections(self):
        """nav は構成データに持たせず sections から導出する (二名簿を作らない)。"""
        self.assertNotIn("nav", self.config)
        out = Path(self._td.name) / "handout.html"
        res = H.run_render(["--config", self.cfg_path, "--out", out])
        self.assertEqual(0, res.returncode, res.stderr)
        html_text = out.read_text(encoding="utf-8")
        links = [el for el in H.parse(html_text)
                 if el.tag == "a" and el.get("href") == "#s1"]
        self.assertTrue(links, "sections から導出した目次項目が無い")
        self.assertEqual(self.config["sections"][0]["goal"], links[0].get("data-hb-nav-goal"))

    def test_config_out_writes_back_the_input_dialect(self):
        """書き戻しは投影前の入力そのもの (描画モデルを構成データとして保存しない)。"""
        target = Path(self._td.name) / "config-out.json"
        res = H.run_render([
            "--config", self.cfg_path, "--out", Path(self._td.name) / "o.html",
            "--theme", "pop", "--config-out", target,
        ])
        self.assertEqual(0, res.returncode, res.stderr)
        written = json.loads(target.read_text(encoding="utf-8"))
        self.assertNotIn("nav", written)
        self.assertNotIn("normalized", written)
        self.assertIn("parts", written["sections"][0])
        self.assertNotIn("blocks", written["sections"][0])


class SchemaDialectGateTest(unittest.TestCase):
    """正規化済みの証拠を弱めない: 証拠が無い schema 方言は exit 1。"""

    def _render(self, config):
        with tempfile.TemporaryDirectory() as td:
            cfg = H.write_config(Path(td) / "config.json", config)
            return H.run_render(["--config", cfg, "--out", Path(td) / "o.html"])

    def test_missing_provenance_is_exit1(self):
        config = schema_config()
        del config["provenance"]
        res = self._render(config)
        self.assertEqual(1, res.returncode, res.stderr)
        self.assertIn("normalized_by", res.stderr)

    def test_wrong_normalized_by_is_exit1(self):
        config = schema_config()
        config["provenance"]["normalized_by"] = "someone-else.py"
        res = self._render(config)
        self.assertEqual(1, res.returncode, res.stderr)
        self.assertIn("normalized_by", res.stderr)

    def test_unknown_part_id_is_exit1(self):
        config = schema_config(parts=[{"part": "B99", "id": "p-1", "data": {"body": "本文"}}])
        res = self._render(config)
        self.assertEqual(1, res.returncode, res.stderr)
        self.assertIn("B99", res.stderr)

    def test_generated_chrome_part_in_parts_is_exit1(self):
        chrome = [p["id"] for p in H.catalog_parts() if p["section_scope"] == "document"]
        config = schema_config(parts=[{"part": chrome[0], "id": "p-1", "data": {}}])
        res = self._render(config)
        self.assertEqual(1, res.returncode, res.stderr)
        self.assertIn(chrome[0], res.stderr)

    def test_dangling_asset_reference_is_exit1(self):
        parts = [{"part": part_id_for("image"), "id": "p-1",
                  "data": {"asset_id": "no-such-asset"}}]
        res = self._render(schema_config(parts=parts))
        self.assertEqual(1, res.returncode, res.stderr)
        self.assertIn("no-such-asset", res.stderr)

    def test_dangling_diagram_reference_is_exit1(self):
        parts = [{"part": part_id_for("diagram"), "id": "p-1",
                  "data": {"diagram_id": "no-such-diagram"}}]
        res = self._render(schema_config(parts=parts))
        self.assertEqual(1, res.returncode, res.stderr)
        self.assertIn("no-such-diagram", res.stderr)

    def test_dangling_attachment_reference_is_exit1(self):
        parts = [{"part": part_id_for("download"), "id": "p-1",
                  "data": {"attachment_id": "no-such-attachment", "label": "落とす"}}]
        res = self._render(schema_config(parts=parts))
        self.assertEqual(1, res.returncode, res.stderr)
        self.assertIn("no-such-attachment", res.stderr)


if __name__ == "__main__":
    unittest.main()
