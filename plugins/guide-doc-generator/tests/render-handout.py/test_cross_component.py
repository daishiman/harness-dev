"""生成物が下流ゲートを通ることの受入 (AC-C11-2/3/4/15/20 と AC-C11-14)。

いずれも C11 が未実装なら赤になる (先頭で run_render を呼ぶため)。
相手側 script が未実装のあいだは skip し、両方そろった時点で本判定が効く。
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

SCRIPTS = H.PLUGIN_ROOT / "scripts"
PURPOSES = H.PLUGIN_ROOT / "config" / "handout-purposes.json"


def run_peer(name, args):
    script = SCRIPTS / name
    proc = subprocess.run(
        [sys.executable, str(script)] + [str(a) for a in args],
        capture_output=True, text=True,
        env={**os.environ, "HB_ROOT": str(H.PLUGIN_ROOT)},
    )
    return proc


def peer_available(name):
    return (SCRIPTS / name).is_file()


def schema_dialect_config():
    """schema 方言 (sections[].parts) の全カタログ部品 fixture。

    round-trip の相手は schema 方言でなければならないため、方言側の正本
    fixture を持つ test_schema_dialect_input から借りる。ここで作り直すと
    「部品カタログの全件」という同じ名簿が 2 つになる。
    """
    import test_schema_dialect_input as SD
    return SD.schema_config()


def rich_config():
    return H.base_config(
        sections=[
            # presentation_order=demo_first (prior_knowledge_level=none からの導出) を
            # 名乗る構成データなので、最初の提示物は screenshot の実画面にする
            # (C22 NAR-07 / R21 CR-DEMO1)。
            H.base_section(1, blocks=[
                H.BLOCK_FIXTURES["image"],
                H.BLOCK_FIXTURES["steps"],
                H.BLOCK_FIXTURES["table"],
            ]),
            H.base_section(2, id="s2", blocks=[H.BLOCK_FIXTURES["checklist"]]),
        ]
    )


class GateHandoffTest(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.addCleanup(self._td.cleanup)
        self.cfg_path = H.write_config(Path(self._td.name) / "config.json", rich_config())
        self.out = Path(self._td.name) / "handout.html"
        res = H.run_render(["--config", self.cfg_path, "--out", self.out])
        self.assertEqual(0, res.returncode, res.stderr)

    def _require_peer(self, name):
        if not peer_available(name):
            self.skipTest("%s が未実装 (P05 で実装され次第この判定が効く)" % name)

    def test_selfcontained_gate_passes(self):
        """AC-C11-2: C16 verify-handout-selfcontained.py が exit 0。"""
        self._require_peer("verify-handout-selfcontained.py")
        proc = run_peer("verify-handout-selfcontained.py", ["--html", self.out])
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)

    def test_a11y_print_gate_passes(self):
        """AC-C11-3: C17 verify-handout-a11y-print.py が exit 0。"""
        self._require_peer("verify-handout-a11y-print.py")
        proc = run_peer("verify-handout-a11y-print.py", ["--html", self.out])
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)

    def test_language_gate_passes(self):
        """AC-C11-4 前半: C18 verify-handout-language.py が exit 0。"""
        self._require_peer("verify-handout-language.py")
        proc = run_peer("verify-handout-language.py", ["--html", self.out, "--config", self.cfg_path])
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)

    def test_narrative_gate_passes(self):
        """AC-C11-4 後半: C22 verify-handout-narrative.py が exit 0。"""
        self._require_peer("verify-handout-narrative.py")
        proc = run_peer("verify-handout-narrative.py", ["--html", self.out, "--config", self.cfg_path])
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)

    def test_round_trip_equivalence(self):
        """AC-C11-15: C20 で逆抽出した構成データが正規化後の入力と等価。

        比較の相手は **C12 --normalize を通した構成データ** である。
        描画モデル方言 (sections[].blocks) の fixture をそのまま相手にすると、
        C20 が復元するのは schema 方言 (sections[].parts) なので、
        方言が違うものを突き合わせて必ず落ちる検査になる。
        逆抽出の出発点として使えることまで測るため、復元結果が
        `--config` を exit 0 で通ることも併せて固定する
        (ROUNDTRIP-CONTRACT.md §1: 出発点とは --config を通る構成データのこと)。
        """
        self._require_peer("extract-handout-config.py")
        self._require_peer("validate-handout-config.py")
        work = Path(self._td.name)
        source_path = H.write_config(work / "schema-dialect.json", schema_dialect_config())
        normalized = work / "normalized.json"
        proc = run_peer("validate-handout-config.py",
                        ["--config", source_path, "--normalize", "--out", normalized])
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        html = work / "roundtrip.html"
        res = H.run_render(["--config", normalized, "--out", html])
        self.assertEqual(0, res.returncode, res.stderr)

        extracted = work / "extracted.json"
        proc = run_peer("extract-handout-config.py", ["--html", html, "--out", extracted])
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        source = json.loads(normalized.read_text(encoding="utf-8"))
        got = json.loads(extracted.read_text(encoding="utf-8"))
        for key in ("sections", "assets", "attachments", "diagrams"):
            self.assertEqual(source.get(key), got.get(key), key)

        proc = run_peer("validate-handout-config.py", ["--config", extracted])
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)

    def test_external_reference_violations_match_c16_exactly(self):
        """AC-C11-20: C11 の exit 1 と C16 の違反リストが件数・箇所ともに一致する。"""
        self._require_peer("verify-handout-selfcontained.py")
        cfg = rich_config()
        cfg["assets"][0]["data_uri"] = "https://example.com/a.png"
        # 位置ではなく「data_uri を持つブロック」で特定する (fixture の並び順に依存しない)
        targets = [b for b in cfg["sections"][0]["blocks"] if "data_uri" in b]
        self.assertTrue(targets, "fixture に data_uri を持つブロックが無い")
        for block in targets:
            block["data_uri"] = "https://example.com/a.png"
        cfg_path = H.write_config(Path(self._td.name) / "bad.json", cfg)
        res = H.run_render(["--config", cfg_path, "--out", Path(self._td.name) / "bad.html"])
        self.assertEqual(1, res.returncode, "外部参照を含む生成物は exit 1")
        self.assertIn("https://example.com/a.png", res.stderr)


class PresetSharedShapeTest(unittest.TestCase):
    """AC-C11-14 / checklist C44: 用途を変えても共有の型が保たれる。"""

    def _purposes(self):
        if not PURPOSES.is_file():
            raise AssertionError("用途語彙正本が未実装: %s (owner C23)" % PURPOSES)
        return json.loads(PURPOSES.read_text(encoding="utf-8"))

    def _purpose_ids(self):
        data = self._purposes()
        presets = data.get("purposes") or data.get("presets") or []
        if isinstance(presets, dict):
            return sorted(presets)
        return [p["id"] for p in presets]

    def test_every_purpose_keeps_the_shared_shape(self):
        ids = self._purpose_ids()
        self.assertTrue(ids, "用途語彙が空")
        for doc_type in ids:
            with self.subTest(doc_type=doc_type):
                cfg = rich_config()
                cfg["doc_type"] = doc_type
                with tempfile.TemporaryDirectory() as td:
                    res, html_text, _ = H.render_html(td, cfg)
                self.assertEqual(0, res.returncode, res.stderr)
                # sticky 目次 / 日付の運び手 / 目的・背景・ゴール
                self.assertTrue(H.elements_with(html_text, "data-hb-nav-goal"))
                self.assertIsNotNone(H.doc_date(html_text))
                for field in ("purpose", "background", "goal"):
                    self.assertTrue(H.field_elements(html_text, field))
                # セクション内の固定順序
                self.assertLess(
                    html_text.index('data-hb-field="section_goal"'),
                    html_text.index('data-hb-field="lead_line"'),
                )
                self.assertLess(
                    html_text.index('data-hb-field="lead_line"'),
                    html_text.index('data-hb-field="judgment_axis"'),
                )
                # 外部参照 0
                self.assertNotIn('src="http', html_text)
                self.assertNotIn('href="http', html_text)


class DelegationTest(unittest.TestCase):
    """invocation_style_rationale: C14 / C15 は module import で呼ぶ (subprocess でない)。"""

    def test_diagram_and_sprite_are_imported_not_spawned(self):
        src = H.source_text()
        self.assertIn("render_diagram", src)
        self.assertIn("build_sprite", src)
        for peer in ("render-diagram-svg.py", "build-icon-sprite.py"):
            self.assertNotIn(
                'subprocess.run([sys.executable, %r' % peer, src,
                "%s を subprocess で起動してはならない" % peer,
            )

    def test_embed_assets_is_not_invoked(self):
        """not_invoked: C13 は上流のデータ加工であり C11 から呼ばない。"""
        self.assertNotIn("embed-assets", H.source_text())

    def test_c14_c15_exit1_is_relayed_as_exit1(self):
        """failure_modes: 委譲先が exit 1 相当を返したら診断を転記して exit 1。"""
        block = copy.deepcopy(H.BLOCK_FIXTURES["diagram"])
        block["pattern"] = "no-such-pattern"
        with tempfile.TemporaryDirectory() as td:
            cfg = H.write_config(Path(td) / "config.json", H.config_with_block(block))
            res = H.run_render(["--config", cfg, "--out", Path(td) / "o.html"])
        self.assertEqual(1, res.returncode, res.stderr)
        self.assertIn("no-such-pattern", res.stderr)


class OversizeWarningTest(unittest.TestCase):
    def test_large_embedded_payload_warns_without_failing(self):
        """failure_modes: サイズ上限判断は C13。C11 は実測値の報告に留め exit 0。"""
        big = "data:text/plain;base64," + ("QQ" * 200000)
        block = {
            "id": "blk-download",
            "type": "download",
            "attachments": [{
                "id": "att-big", "name": "big.txt", "mime": "text/plain",
                "data_uri": big, "bytes": len(big), "fallback_hint": "本文をコピーする",
            }],
        }
        with tempfile.TemporaryDirectory() as td:
            res, html_text, _ = H.render_html(td, H.config_with_block(block))
            self.assertEqual(0, res.returncode, res.stderr)
            payload = res.json_line()
        self.assertGreater(payload["embedded_bytes"], 0)
        self.assertTrue(payload["warnings"], "肥大時は warnings へ実測値を報告する")


if __name__ == "__main__":
    unittest.main()
