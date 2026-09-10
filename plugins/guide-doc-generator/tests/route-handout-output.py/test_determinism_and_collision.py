"""再現性と衝突解決 — AC-C19-05、naming_rule.collision_rule (1)-(5)、C29。"""

import json
import tempfile
import unittest
from pathlib import Path

import _harness as H


class DeterminismTest(unittest.TestCase):
    def setUp(self):
        H.require_script(self)

    def test_same_config_twice_reuses_the_same_directory(self):
        """AC-C19-05: ディレクトリ名がバイト一致し、2 回目が連番を作らない。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "out"
            root.mkdir()
            cfg = H.write_config(Path(tmp) / "c.json", H.normalized_config(self))
            first = H.run(["--config", cfg, "--out-dir", root])
            second = H.run(["--config", cfg, "--out-dir", root])
            self.assertEqual(0, first.returncode, H.describe(first))
            self.assertEqual(0, second.returncode, H.describe(second))
            self.assertEqual(
                H.resolved_path(self, first).name.encode("utf-8"),
                H.resolved_path(self, second).name.encode("utf-8"),
            )
            self.assertEqual(
                1, len(list(root.iterdir())), "2 回目が新規ディレクトリを作った"
            )

    def test_stdout_is_byte_identical_across_runs(self):
        """C29: 同一入力に対する stdout がバイト一致する。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "out"
            root.mkdir()
            cfg = H.write_config(Path(tmp) / "c.json", H.normalized_config(self))
            first = H.run(["--config", cfg, "--out-dir", root])
            second = H.run(["--config", cfg, "--out-dir", root])
            self.assertEqual(first.stdout, second.stdout, H.describe(second))

    def test_directory_name_does_not_depend_on_the_root(self):
        """命名は構成データだけで決まる (ルートの違いで名前が変わらない)。"""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            cfg = H.write_config(base / "c.json", H.normalized_config(self))
            names = []
            for sub in ("a", "b"):
                root = base / sub
                root.mkdir()
                proc = H.run(["--config", cfg, "--out-dir", root])
                self.assertEqual(0, proc.returncode, H.describe(proc))
                names.append(H.resolved_path(self, proc).name)
            self.assertEqual(names[0], names[1])


class CollisionTest(unittest.TestCase):
    def setUp(self):
        H.require_script(self)

    def _first_run(self, tmp: Path, **overrides):
        root = tmp / "out"
        root.mkdir(exist_ok=True)
        cfg = H.write_config(
            tmp / "c-{}.json".format(len(list(tmp.glob("c-*.json")))),
            H.normalized_config(self, **overrides),
        )
        proc = H.run(["--config", cfg, "--out-dir", root])
        self.assertEqual(0, proc.returncode, H.describe(proc))
        return root, cfg, H.resolved_path(self, proc)

    def test_different_config_with_same_name_gets_next_sequence(self):
        """collision_rule (3): sha256 が異なるなら -2 の新規ディレクトリ。"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            root, _, first = self._first_run(tmp)
            cfg2 = H.write_config(
                tmp / "c2.json",
                H.normalized_config(self, purpose="別内容だがディレクトリ名は同じになる"),
            )
            proc = H.run(["--config", cfg2, "--out-dir", root])
            self.assertEqual(0, proc.returncode, H.describe(proc))
            second = H.resolved_path(self, proc)
            self.assertNotEqual(first, second)
            self.assertEqual(first.name + "-2", second.name)
            self.assertEqual(2, len(list(root.iterdir())))

    def test_existing_directory_content_is_not_destroyed(self):
        """collision_rule (5): 既存ファイルを削除しない。"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            root, _, first = self._first_run(tmp)
            keep = first / "handout.html"
            keep.write_text("<html>既存</html>\n", encoding="utf-8")
            cfg2 = H.write_config(
                tmp / "c2.json", H.normalized_config(self, purpose="別内容にして衝突させる")
            )
            proc = H.run(["--config", cfg2, "--out-dir", root])
            self.assertEqual(0, proc.returncode, H.describe(proc))
            self.assertEqual("<html>既存</html>\n", keep.read_text(encoding="utf-8"))

    def test_missing_route_marker_falls_back_to_sequence(self):
        """collision_rule (3) / failure_modes: 来歴が無ければ破壊より連番へ倒す。"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            root, cfg, first = self._first_run(tmp)
            (first / H.ROUTE_MARKER).unlink()
            proc = H.run(["--config", cfg, "--out-dir", root])
            self.assertEqual(0, proc.returncode, H.describe(proc))
            self.assertEqual(first.name + "-2", H.resolved_path(self, proc).name)

    def test_sequence_picks_the_smallest_unused_number(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            root, _, first = self._first_run(tmp)
            (root / (first.name + "-2")).mkdir()
            (root / (first.name + "-4")).mkdir()
            cfg2 = H.write_config(
                tmp / "c2.json", H.normalized_config(self, purpose="連番の最小未使用を検査する")
            )
            proc = H.run(["--config", cfg2, "--out-dir", root])
            self.assertEqual(0, proc.returncode, H.describe(proc))
            self.assertEqual(first.name + "-3", H.resolved_path(self, proc).name)

    def test_sequence_over_99_is_exit1(self):
        """collision_rule (4): 連番が 99 を超えたら exit 1。"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            root, _, first = self._first_run(tmp)
            for n in range(2, 100):
                (root / "{}-{}".format(first.name, n)).mkdir()
            cfg2 = H.write_config(
                tmp / "c2.json", H.normalized_config(self, purpose="連番上限を超えさせる")
            )
            before = len(list(root.iterdir()))
            proc = H.run(["--config", cfg2, "--out-dir", root])
            self.assertEqual(1, proc.returncode, H.describe(proc))
            self.assertIn(H.STDERR_PREFIX, H.err_text(proc), H.describe(proc))
            self.assertEqual(before, len(list(root.iterdir())), "上限超過でディレクトリを作った")

    def test_route_marker_sha256_identifies_regeneration(self):
        """collision_rule (2): 来歴の sha256 が一致するなら同一資料の再生成として再利用。"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            root, cfg, first = self._first_run(tmp)
            marker = json.loads((first / H.ROUTE_MARKER).read_text(encoding="utf-8"))
            self.assertIn(
                H.config_sha256(cfg),
                H.flatten_strings(marker),
                "来歴に config の sha256 が無い (再生成の同定ができない)",
            )
            proc = H.run(["--config", cfg, "--out-dir", root])
            self.assertEqual(0, proc.returncode, H.describe(proc))
            self.assertEqual(first, H.resolved_path(self, proc))

    def test_check_only_inspects_the_base_name_without_resolving_collisions(self):
        """algorithm 8: --check-only は衝突解決せず既存ディレクトリを検査対象にする。"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            root, cfg, first = self._first_run(tmp)
            proc = H.run(["--config", cfg, "--out-dir", root, "--check-only"])
            self.assertEqual(1, proc.returncode, H.describe(proc))
            self.assertEqual(first, H.resolved_path(self, proc))


if __name__ == "__main__":
    unittest.main()
