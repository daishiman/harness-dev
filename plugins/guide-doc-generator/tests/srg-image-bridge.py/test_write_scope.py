"""書き込みスコープ — write_scope / single_writer / AC-C21-9。

書くのは <assets-dir> 配下だけ。SRG plugin 配下は read-only (vendor script を実行する
だけで 1 バイトも書かない)。構成データ JSON も出力 HTML も触らない。
"""

import tempfile
import unittest
from pathlib import Path

import _harness as H


class _Base(H.BridgeTestCase):
    def _setup(self, tmp):
        tmp = Path(tmp)
        srg = H.make_srg(tmp)
        bin_dir = H.make_fake_bin(tmp)
        log = tmp / "log.jsonl"
        plan = H.write_plan(tmp / "plan.json", H.plan_payload())
        assets = H.make_assets_dir(tmp)
        outside = tmp / "outside"
        (outside / "out").mkdir(parents=True)
        (outside / "handout-config.json").write_text("{}\n", encoding="utf-8")
        (outside / "out" / "handout.html").write_text("<html></html>\n", encoding="utf-8")
        return tmp, srg, bin_dir, log, plan, assets, outside


class WriteScopeTest(_Base):
    def test_srg_root_is_untouched(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp, srg, bin_dir, log, plan, assets, _ = self._setup(tmp)
            before = H.tree_snapshot(srg)
            proc = H.run(
                ["--image-plan", plan, "--assets-dir", assets, "--srg-root", srg],
                env=H.clean_env(tmp, bin_dir=bin_dir, log=log),
            )
            self.assertEqual(before, H.tree_snapshot(srg), "SRG 配下へ書いている:\n" + H.describe(proc))

    def test_config_and_html_outside_are_untouched(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp, srg, bin_dir, log, plan, assets, outside = self._setup(tmp)
            before = H.tree_snapshot(outside)
            proc = H.run(
                ["--image-plan", plan, "--assets-dir", assets, "--srg-root", srg],
                env=H.clean_env(tmp, bin_dir=bin_dir, log=log),
            )
            self.assertEqual(before, H.tree_snapshot(outside), "assets-dir の外へ書いている:\n" + H.describe(proc))

    def test_image_plan_file_is_not_rewritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp, srg, bin_dir, log, plan, assets, _ = self._setup(tmp)
            before = Path(plan).read_bytes()
            proc = H.run(
                ["--image-plan", plan, "--assets-dir", assets, "--srg-root", srg],
                env=H.clean_env(tmp, bin_dir=bin_dir, log=log),
            )
            self.assertEqual(before, Path(plan).read_bytes(), "入力の画像計画を書き換えている:\n" + H.describe(proc))

    def test_all_writes_stay_under_assets_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp, srg, bin_dir, log, plan, assets, _ = self._setup(tmp)
            env = H.clean_env(tmp, bin_dir=bin_dir, log=log)  # 偽 plugin root の作成を先に済ませる
            before = H.tree_snapshot(tmp)
            proc = H.run(
                ["--image-plan", plan, "--assets-dir", assets, "--srg-root", srg], env=env
            )
            after = H.tree_snapshot(tmp)
            changed = {
                path for path in set(before) | set(after) if before.get(path) != after.get(path)
            }
            allowed_prefix = str(Path(assets).relative_to(tmp)) + "/"
            offenders = sorted(
                path
                for path in changed
                if not path.startswith(allowed_prefix) and not path.startswith("log.jsonl")
            )
            self.assertEqual([], offenders, "assets-dir の外を変更した:\n" + H.describe(proc))

    def test_work_directory_layout_follows_srg_convention(self):
        """algorithm 5: SRG は <slide-dir>/assets/generated を固定で見る。"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp, srg, bin_dir, log, plan, assets, _ = self._setup(tmp)
            proc = H.run(
                ["--image-plan", plan, "--assets-dir", assets, "--srg-root", srg],
                env=H.clean_env(tmp, bin_dir=bin_dir, log=log),
            )
            self.assertTrue(
                (Path(assets) / "srg-work" / "assets" / "generated").is_dir(), H.describe(proc)
            )

    def test_slide_dir_passed_to_vendor_scripts_is_the_work_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp, srg, bin_dir, log, plan, assets, _ = self._setup(tmp)
            proc = H.run(
                ["--image-plan", plan, "--assets-dir", assets, "--srg-root", srg],
                env=H.clean_env(tmp, bin_dir=bin_dir, log=log),
            )
            work = (Path(assets) / "srg-work").resolve()
            entries = [e for e in H.node_log(log) if e.get("script")]
            self.assertTrue(entries, "委譲していない:\n" + H.describe(proc))
            for entry in entries:
                positional = entry.get("positional") or []
                self.assertTrue(positional, "slide-dir が渡っていない: {}".format(entry))
                self.assertEqual(str(work), str(Path(positional[0]).resolve()), entry)

    def test_no_config_json_is_written_into_assets_dir(self):
        """single_writer: 構成データ JSON は書かない (画像参照の反映は C01/C05)。"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp, srg, bin_dir, log, plan, assets, _ = self._setup(tmp)
            proc = H.run(
                ["--image-plan", plan, "--assets-dir", assets, "--srg-root", srg],
                env=H.clean_env(tmp, bin_dir=bin_dir, log=log),
            )
            offenders = [
                str(path.relative_to(assets))
                for path in Path(assets).rglob("handout-config.json")
            ]
            self.assertEqual([], offenders, H.describe(proc))

    def test_no_html_is_written(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp, srg, bin_dir, log, plan, assets, _ = self._setup(tmp)
            proc = H.run(
                ["--image-plan", plan, "--assets-dir", assets, "--srg-root", srg],
                env=H.clean_env(tmp, bin_dir=bin_dir, log=log),
            )
            offenders = [str(path) for path in Path(assets).rglob("*.html")]
            self.assertEqual([], offenders, H.describe(proc))


if __name__ == "__main__":
    unittest.main()
