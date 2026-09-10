"""出力先ルートの解決 4 段と脱出防止 — AC-C19-01 / AC-C19-12、algorithm 6 / 7。

実ユーザーの既定出力先へ 1 バイトも書かないため、config 段の検査は
(a) --check-only (ディレクトリを作らない) か
(b) scripts+config を tmp へ複製した fixture ツリー
のいずれかでしか行わない。
"""

import json
import os
import tempfile
import unittest
from pathlib import Path

import _harness as H


class ResolutionOrderTest(unittest.TestCase):
    def setUp(self):
        H.require_script(self)

    def test_out_dir_argv_wins_over_env(self):
        """algorithm 6: --out-dir が最優先。"""
        with tempfile.TemporaryDirectory() as tmp:
            chosen = Path(tmp) / "chosen"
            ignored = Path(tmp) / "ignored"
            chosen.mkdir()
            ignored.mkdir()
            cfg = H.write_config(Path(tmp) / "c.json", H.normalized_config(self))
            proc = H.run(
                ["--config", cfg, "--out-dir", chosen],
                env=H.clean_env(HB_OUT_DIR=str(ignored)),
            )
            self.assertEqual(0, proc.returncode, H.describe(proc))
            self.assertEqual(chosen.resolve(), H.resolved_path(self, proc).parent)
            self.assertEqual([], list(ignored.iterdir()), "env 側にディレクトリを作った")

    def test_env_is_used_when_argv_absent(self):
        """algorithm 6 の 2 段目: HB_OUT_DIR。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "env-root"
            root.mkdir()
            cfg = H.write_config(Path(tmp) / "c.json", H.normalized_config(self))
            proc = H.run(["--config", cfg], env=H.clean_env(HB_OUT_DIR=str(root)))
            self.assertEqual(0, proc.returncode, H.describe(proc))
            self.assertEqual(root.resolve(), H.resolved_path(self, proc).parent)

    def test_config_default_is_used_when_argv_and_env_absent(self):
        """AC-C19-01: 3 段目 config/handout-output.json の default_out_dir。

        fixture ツリー側の default_out_dir を tmp へ差し替えて実行し、実既定出力先へは
        触れない。
        """
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "config-root"
            target.mkdir()

            def mutate(data):
                data["default_out_dir"] = str(target)

            root = H.make_fixture_tree(self, Path(tmp), mutate_output_config=mutate)
            cfg = H.write_config(Path(tmp) / "c.json", H.normalized_config(self))
            proc = H.run(["--config", cfg], script=H.fixture_script(root))
            self.assertEqual(0, proc.returncode, H.describe(proc))
            self.assertEqual(target.resolve(), H.resolved_path(self, proc).parent)

    def test_all_three_stages_absent_is_exit2(self):
        """AC-C19-01: 3 段いずれも欠けたときだけ exit 2。"""
        with tempfile.TemporaryDirectory() as tmp:

            def mutate(data):
                data.pop("default_out_dir", None)

            root = H.make_fixture_tree(self, Path(tmp), mutate_output_config=mutate)
            cfg = H.write_config(Path(tmp) / "c.json", H.normalized_config(self))
            proc = H.run(["--config", cfg], script=H.fixture_script(root))
            self.assertEqual(2, proc.returncode, H.describe(proc))
            self.assertIn(H.STDERR_PREFIX, H.err_text(proc), H.describe(proc))

    def test_empty_default_out_dir_is_exit2(self):
        with tempfile.TemporaryDirectory() as tmp:

            def mutate(data):
                data["default_out_dir"] = ""

            root = H.make_fixture_tree(self, Path(tmp), mutate_output_config=mutate)
            cfg = H.write_config(Path(tmp) / "c.json", H.normalized_config(self))
            proc = H.run(["--config", cfg], script=H.fixture_script(root))
            self.assertEqual(2, proc.returncode, H.describe(proc))

    def test_config_value_expands_tilde_and_env(self):
        """algorithm 6: config の値は ~ 展開と環境変数展開を行う。"""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "expanded"
            target.mkdir()

            def mutate(data):
                data["default_out_dir"] = "$HB_TEST_BASE/expanded"

            root = H.make_fixture_tree(self, Path(tmp), mutate_output_config=mutate)
            cfg = H.write_config(Path(tmp) / "c.json", H.normalized_config(self))
            proc = H.run(
                ["--config", cfg],
                env=H.clean_env(HB_TEST_BASE=tmp),
                script=H.fixture_script(root),
            )
            self.assertEqual(0, proc.returncode, H.describe(proc))
            self.assertEqual(target.resolve(), H.resolved_path(self, proc).parent)


class ResolutionStageIsRecordedTest(unittest.TestCase):
    """algorithm 6: どの段で解決したかを stdout と --json-report に記録する。"""

    def setUp(self):
        H.require_script(self)

    def _report_blob(self, args, env=None, script=None, tmp=None):
        report = Path(tmp) / "r.json"
        proc = H.run([*args, "--json-report", report], env=env, script=script)
        self.assertEqual(0, proc.returncode, H.describe(proc))
        blob = "\n".join(H.flatten_strings(H.load_report(self, report)))
        return proc, blob

    def test_argv_stage_recorded(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "out"
            root.mkdir()
            cfg = H.write_config(Path(tmp) / "c.json", H.normalized_config(self))
            proc, blob = self._report_blob(
                ["--config", cfg, "--out-dir", root], tmp=tmp
            )
            H.assert_stage_recorded(self, blob, "argv")
            H.assert_stage_recorded(self, H.out_text(proc), "argv")

    def test_env_stage_recorded(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "out"
            root.mkdir()
            cfg = H.write_config(Path(tmp) / "c.json", H.normalized_config(self))
            proc, blob = self._report_blob(
                ["--config", cfg], env=H.clean_env(HB_OUT_DIR=str(root)), tmp=tmp
            )
            H.assert_stage_recorded(self, blob, "env")
            H.assert_stage_recorded(self, H.out_text(proc), "env")


class RootEscapeTest(unittest.TestCase):
    """algorithm 7 / failure_modes: 結合後の realpath がルート配下から外れたら exit 2。"""

    def setUp(self):
        H.require_script(self)

    def _run_with_slug(self, tmp, slug):
        root = Path(tmp) / "out"
        root.mkdir(exist_ok=True)
        sentinel = Path(tmp) / "outside"
        sentinel.mkdir(exist_ok=True)
        cfg = H.write_config(
            Path(tmp) / "c.json", H.normalized_config(self, subject_slug=slug)
        )
        proc = H.run(["--config", cfg, "--out-dir", root])
        return root, sentinel, proc

    def test_parent_traversal_slug_is_exit2(self):
        """AC-C19-12: ../ を含む slug でルート外にディレクトリを作らない。"""
        with tempfile.TemporaryDirectory() as tmp:
            root, sentinel, proc = self._run_with_slug(tmp, "../escaped")
            self.assertEqual(2, proc.returncode, H.describe(proc))
            self.assertEqual([], list(root.iterdir()))
            self.assertEqual([], list(sentinel.iterdir()))
            self.assertFalse((Path(tmp) / "escaped").exists())

    def test_path_separator_slug_is_exit2(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, _, proc = self._run_with_slug(tmp, "nested/child")
            self.assertEqual(2, proc.returncode, H.describe(proc))
            self.assertEqual([], list(root.iterdir()))

    def test_absolute_slug_is_exit2(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, sentinel, proc = self._run_with_slug(tmp, "/absolute-escape")
            self.assertEqual(2, proc.returncode, H.describe(proc))
            self.assertEqual([], list(root.iterdir()))
            self.assertEqual([], list(sentinel.iterdir()))

    def test_symlinked_root_stays_inside_its_realpath(self):
        """ルート自体が symlink でも、解決先はその realpath 配下に収まる。"""
        with tempfile.TemporaryDirectory() as tmp:
            real = Path(tmp) / "real"
            real.mkdir()
            link = Path(tmp) / "link"
            os.symlink(real, link)
            cfg = H.write_config(Path(tmp) / "c.json", H.normalized_config(self))
            proc = H.run(["--config", cfg, "--out-dir", link])
            self.assertEqual(0, proc.returncode, H.describe(proc))
            resolved = H.resolved_path(self, proc).resolve()
            self.assertEqual(real.resolve(), resolved.parent)

    def test_unresolvable_out_dir_is_exit2(self):
        """exit_codes 2: 出力先ルートを解決できない。"""
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "no-such" / "deep" / "root"
            cfg = H.write_config(Path(tmp) / "c.json", H.normalized_config(self))
            blocker = Path(tmp) / "blocker"
            blocker.write_text("not a directory\n", encoding="utf-8")
            proc = H.run(["--config", cfg, "--out-dir", blocker])
            self.assertEqual(2, proc.returncode, H.describe(proc))
            self.assertIn(H.STDERR_PREFIX, H.err_text(proc), H.describe(proc))


if __name__ == "__main__":
    unittest.main()
