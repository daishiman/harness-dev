"""C19 が writer である 2 点の配置 — AC-C19-15 / 16 / 17 / 18、algorithm 9b / 9c、P03 Y-04。"""

import os
import tempfile
import unittest
from pathlib import Path

import _harness as H


def _assets_src(tmp: Path) -> Path:
    """2 階層のファイルを持つ複製元。"""
    src = tmp / "assets-src"
    (src / "img" / "deep").mkdir(parents=True)
    (src / "top.png").write_bytes(b"\x89PNG-top")
    (src / "img" / "mid.svg").write_text("<svg/>\n", encoding="utf-8")
    (src / "img" / "deep" / "leaf.txt").write_text("葉\n", encoding="utf-8")
    return src


def _run(tc, tmp: Path, extra):
    root = tmp / "out"
    root.mkdir(exist_ok=True)
    cfg = H.write_config(tmp / "c.json", H.normalized_config(tc))
    proc = H.run(["--config", cfg, "--out-dir", root, *extra])
    return root, cfg, proc


class AssetsCopyTest(unittest.TestCase):
    def setUp(self):
        H.require_script(self)

    def test_two_level_tree_is_copied_preserving_relative_structure(self):
        """AC-C19-15: 出力先 assets/ に同じ相対構造で複製される。"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            src = _assets_src(tmp)
            before = H.tree_snapshot(src)
            _, _, proc = _run(self, tmp, ["--assets-src", src])
            self.assertEqual(0, proc.returncode, H.describe(proc))
            dest = H.resolved_path(self, proc) / "assets"
            self.assertEqual(before, H.tree_snapshot(dest), "相対構造かバイト列が一致しない")
            self.assertEqual(before, H.tree_snapshot(src), "複製元が変更された")

    def test_copy_is_idempotent(self):
        """AC-C19-16: 2 回続けて実行しても内容が変化しない。"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            src = _assets_src(tmp)
            root, cfg, first = _run(self, tmp, ["--assets-src", src])
            self.assertEqual(0, first.returncode, H.describe(first))
            after_first = H.tree_snapshot(root)
            second = H.run(["--config", cfg, "--out-dir", root, "--assets-src", src])
            self.assertEqual(0, second.returncode, H.describe(second))
            self.assertEqual(
                H.resolved_path(self, first), H.resolved_path(self, second)
            )
            after_second = H.tree_snapshot(root)
            self.assertEqual(
                {k: v for k, v in after_first.items() if H.ROUTE_MARKER not in k},
                {k: v for k, v in after_second.items() if H.ROUTE_MARKER not in k},
                "2 回目で内容が変化した (冪等でない)",
            )

    def test_changed_source_file_overwrites_destination(self):
        """algorithm 9b: 内容が異なるなら上書きする。"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            src = _assets_src(tmp)
            root, cfg, first = _run(self, tmp, ["--assets-src", src])
            self.assertEqual(0, first.returncode, H.describe(first))
            (src / "top.png").write_bytes(b"\x89PNG-updated")
            second = H.run(["--config", cfg, "--out-dir", root, "--assets-src", src])
            self.assertEqual(0, second.returncode, H.describe(second))
            dest = H.resolved_path(self, second) / "assets" / "top.png"
            self.assertEqual(b"\x89PNG-updated", dest.read_bytes())

    def test_assets_dir_is_created_empty_without_assets_src(self):
        """argv: --assets-src 未指定時は assets/ を空で作るだけ。"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            _, _, proc = _run(self, tmp, [])
            self.assertEqual(0, proc.returncode, H.describe(proc))
            dest = H.resolved_path(self, proc) / "assets"
            self.assertTrue(dest.is_dir())
            self.assertEqual([], list(dest.iterdir()), "空でない assets/ が作られた")

    def test_missing_assets_src_is_exit2(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            _, _, proc = _run(self, tmp, ["--assets-src", tmp / "no-such"])
            self.assertEqual(2, proc.returncode, H.describe(proc))
            self.assertIn(H.STDERR_PREFIX, H.err_text(proc), H.describe(proc))

    def test_assets_src_that_is_a_file_is_exit2(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            plain = tmp / "plain.txt"
            plain.write_text("ディレクトリではない\n", encoding="utf-8")
            _, _, proc = _run(self, tmp, ["--assets-src", plain])
            self.assertEqual(2, proc.returncode, H.describe(proc))

    def test_symlink_escaping_assets_is_exit2_and_not_followed(self):
        """algorithm 9b: assets/ の外へ出る経路は辿らず exit 2。"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            secret = tmp / "secret.txt"
            secret.write_text("外部の秘密\n", encoding="utf-8")
            src = _assets_src(tmp)
            os.symlink(secret, src / "img" / "escape.txt")
            root, _, proc = _run(self, tmp, ["--assets-src", src])
            self.assertEqual(2, proc.returncode, H.describe(proc))
            copied = list((root).rglob("escape.txt"))
            self.assertEqual([], copied, "脱出 symlink を辿って複製した")

    def test_symlinked_directory_escaping_assets_is_exit2(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            outside = tmp / "outside"
            outside.mkdir()
            (outside / "leak.txt").write_text("漏れ\n", encoding="utf-8")
            src = _assets_src(tmp)
            os.symlink(outside, src / "linked-dir")
            root, _, proc = _run(self, tmp, ["--assets-src", src])
            self.assertEqual(2, proc.returncode, H.describe(proc))
            self.assertEqual([], list(root.rglob("leak.txt")))

    def test_assets_content_is_not_transformed(self):
        """write_scope: 複製のみで内容の加工は行わない (C13 の data URI 化と混同しない)。"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            src = tmp / "assets-src"
            src.mkdir()
            payload = b"\x00\x01binary\xff\xfe"
            (src / "raw.bin").write_bytes(payload)
            _, _, proc = _run(self, tmp, ["--assets-src", src])
            self.assertEqual(0, proc.returncode, H.describe(proc))
            self.assertEqual(
                payload, (H.resolved_path(self, proc) / "assets" / "raw.bin").read_bytes()
            )


class PlaceConfigTest(unittest.TestCase):
    def setUp(self):
        H.require_script(self)

    def test_placed_config_is_byte_identical(self):
        """AC-C19-17: handout-config.json が --config とバイト一致 (無加工)。"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            _, cfg, proc = _run(self, tmp, ["--place-config"])
            self.assertEqual(0, proc.returncode, H.describe(proc))
            placed = H.resolved_path(self, proc) / H.PLACED_CONFIG_NAME
            self.assertTrue(placed.is_file(), "handout-config.json が置かれていない")
            self.assertEqual(cfg.read_bytes(), placed.read_bytes(), "バイト一致でない")

    def test_placed_config_keeps_unusual_bytes(self):
        """バイト列をそのまま複製する (再整形も改行変換もしない)。"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            root = tmp / "out"
            root.mkdir()
            cfg = tmp / "c.json"
            import json

            raw = (
                json.dumps(H.normalized_config(self), ensure_ascii=False)
                .replace("\n", "")
                .encode("utf-8")
            )
            cfg.write_bytes(raw + b"\r\n\r\n")
            proc = H.run(["--config", cfg, "--out-dir", root, "--place-config"])
            self.assertEqual(0, proc.returncode, H.describe(proc))
            placed = H.resolved_path(self, proc) / H.PLACED_CONFIG_NAME
            self.assertEqual(cfg.read_bytes(), placed.read_bytes())

    def test_fixed_name_is_used(self):
        """固定名 handout-config.json (--config のファイル名に引きずられない)。"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            root = tmp / "out"
            root.mkdir()
            cfg = H.write_config(tmp / "some-other-name.json", H.normalized_config(self))
            proc = H.run(["--config", cfg, "--out-dir", root, "--place-config"])
            self.assertEqual(0, proc.returncode, H.describe(proc))
            target = H.resolved_path(self, proc)
            self.assertTrue((target / H.PLACED_CONFIG_NAME).is_file())
            self.assertFalse((target / "some-other-name.json").exists())

    def test_place_config_is_off_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            _, _, proc = _run(self, tmp, [])
            self.assertEqual(0, proc.returncode, H.describe(proc))
            self.assertFalse(
                (H.resolved_path(self, proc) / H.PLACED_CONFIG_NAME).exists(),
                "既定で handout-config.json を置いた",
            )

    def test_place_config_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            root, cfg, first = _run(self, tmp, ["--place-config"])
            self.assertEqual(0, first.returncode, H.describe(first))
            placed = H.resolved_path(self, first) / H.PLACED_CONFIG_NAME
            before = placed.read_bytes()
            second = H.run(["--config", cfg, "--out-dir", root, "--place-config"])
            self.assertEqual(0, second.returncode, H.describe(second))
            self.assertEqual(before, placed.read_bytes())


class WriteScopeTest(unittest.TestCase):
    """write_scope: 出力先ディレクトリと --json-report 以外へ書かない。"""

    def setUp(self):
        H.require_script(self)

    def test_nothing_is_written_next_to_the_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            cfg_dir = tmp / "work"
            cfg_dir.mkdir()
            cfg = H.write_config(cfg_dir / "c.json", H.normalized_config(self))
            root = tmp / "out"
            root.mkdir()
            src = _assets_src(tmp)
            before = H.tree_snapshot(cfg_dir)
            proc = H.run(
                ["--config", cfg, "--out-dir", root, "--place-config", "--assets-src", src]
            )
            self.assertEqual(0, proc.returncode, H.describe(proc))
            self.assertEqual(before, H.tree_snapshot(cfg_dir), "--config の隣へ書き込んだ")

    def test_created_entries_are_confined_to_the_resolved_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            root, _, proc = _run(self, tmp, ["--place-config"])
            self.assertEqual(0, proc.returncode, H.describe(proc))
            target = H.resolved_path(self, proc)
            self.assertEqual([target.name], sorted(p.name for p in root.iterdir()))
            self.assertEqual(
                sorted([H.PLACED_CONFIG_NAME, "assets", H.ROUTE_MARKER]),
                sorted(p.name for p in target.iterdir()),
                "出力先に想定外のファイルがある",
            )


if __name__ == "__main__":
    unittest.main()
