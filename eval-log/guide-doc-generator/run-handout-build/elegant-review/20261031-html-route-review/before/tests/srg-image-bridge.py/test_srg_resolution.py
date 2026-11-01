"""SRG 実体の解決と fail-soft skip — algorithm 3 / AC-C21-2 / AC-C21-8 / C18。

解決順は (a) --srg-root、(b) 環境変数 SRG_ROOT、(c) handout plugin root の兄弟
../slide-report-generator。実体判定は名前ではなく vendor script 2 本の実在で行う。
どれも通らなければ skip (exit 0)。ただし (a) を明示して外したときだけ exit 2。
"""

import tempfile
import unittest
from pathlib import Path

import _harness as H


def _plan(tmp):
    return H.write_plan(Path(tmp) / "plan.json", H.plan_payload())


class AbsentSrgTest(H.BridgeTestCase):
    """AC-C21-2: SRG が無いときは起動を試みず skip を宣言して exit 0。"""

    def _run_with_absent_srg(self, tmp):
        tmp = Path(tmp)
        bogus = tmp / "not-srg"
        bogus.mkdir()
        bin_dir = H.make_fake_bin(tmp)
        log = tmp / "log.jsonl"
        proc = H.run(
            ["--image-plan", _plan(tmp), "--assets-dir", H.make_assets_dir(tmp)],
            env=H.clean_env(tmp, bin_dir=bin_dir, srg_root=bogus, log=log),
        )
        return proc, log

    def test_exit_code_is_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc, _ = self._run_with_absent_srg(tmp)
            self.assertEqual(0, proc.returncode, H.describe(proc))

    def test_status_is_skipped_with_srg_absent_reason(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc, _ = self._run_with_absent_srg(tmp)
            data = H.stdout_json(self, proc)
            self.assertEqual("skipped", data["status"], H.describe(proc))
            self.assertEqual("srg-absent", data["skip_reason"], H.describe(proc))

    def test_srg_root_is_null_when_unresolved(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc, _ = self._run_with_absent_srg(tmp)
            self.assertIsNone(H.stdout_json(self, proc)["srg_root"], H.describe(proc))

    def test_no_delegate_is_launched(self):
        """『起動を試みる前に』skip する。node も codex も動かない。"""
        with tempfile.TemporaryDirectory() as tmp:
            proc, log = self._run_with_absent_srg(tmp)
            self.assertEqual([], H.node_log(log), "委譲先を起動している:\n" + H.describe(proc))

    def test_no_delegated_commands_are_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc, _ = self._run_with_absent_srg(tmp)
            self.assertEqual([], H.stdout_json(self, proc)["delegated_commands"], H.describe(proc))

    def test_work_directory_is_not_created(self):
        """skip なら作業ディレクトリも作らない (何もしていないことが痕跡でも分かる)。"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            bogus = tmp / "not-srg"
            bogus.mkdir()
            assets = H.make_assets_dir(tmp)
            proc = H.run(
                ["--image-plan", _plan(tmp), "--assets-dir", assets],
                env=H.clean_env(tmp, bin_dir=H.make_fake_bin(tmp), srg_root=bogus, log=tmp / "log.jsonl"),
            )
            self.assertEqual(0, proc.returncode, H.describe(proc))
            self.assertEqual({}, H.tree_snapshot(assets), "skip なのに assets-dir へ書いている")


class SubstanceCheckTest(H.BridgeTestCase):
    """実体判定は名前ではなくファイルの実在 (algorithm 3)。"""

    def _run_with(self, tmp, srg_root, explicit):
        tmp = Path(tmp)
        args = ["--image-plan", _plan(tmp), "--assets-dir", H.make_assets_dir(tmp)]
        env_srg = None
        if explicit:
            args += ["--srg-root", srg_root]
        else:
            env_srg = srg_root
        return H.run(
            args,
            env=H.clean_env(tmp, bin_dir=H.make_fake_bin(tmp), srg_root=env_srg, log=tmp / "log.jsonl"),
        )

    def test_directory_named_like_srg_without_vendor_scripts_is_not_substance(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            fake = tmp / "slide-report-generator"
            fake.mkdir()
            proc = self._run_with(tmp, fake, explicit=False)
            self.assertEqual(0, proc.returncode, H.describe(proc))
            self.assertEqual("srg-absent", H.stdout_json(self, proc)["skip_reason"], H.describe(proc))

    def test_one_missing_vendor_script_is_not_substance(self):
        for omitted in H.SRG_VENDOR_SCRIPTS:
            with self.subTest(omitted=omitted):
                with tempfile.TemporaryDirectory() as tmp:
                    tmp = Path(tmp)
                    partial = H.make_srg(tmp, omit=(omitted,))
                    proc = self._run_with(tmp, partial, explicit=False)
                    self.assertEqual(0, proc.returncode, H.describe(proc))
                    self.assertEqual(
                        "srg-absent", H.stdout_json(self, proc)["skip_reason"], H.describe(proc)
                    )

    def test_explicit_srg_root_that_is_not_substance_is_exit2(self):
        """AC-C21-8: 明示指定の誤りを黙って skip へ畳まない。"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            bogus = tmp / "not-srg"
            bogus.mkdir()
            proc = self._run_with(tmp, bogus, explicit=True)
            self.assertEqual(2, proc.returncode, H.describe(proc))

    def test_explicit_srg_root_missing_one_script_is_exit2(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            partial = H.make_srg(tmp, omit=(H.SRG_VENDOR_SCRIPTS[1],))
            proc = self._run_with(tmp, partial, explicit=True)
            self.assertEqual(2, proc.returncode, H.describe(proc))

    def test_explicit_srg_root_that_does_not_exist_is_exit2(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            proc = self._run_with(tmp, tmp / "missing", explicit=True)
            self.assertEqual(2, proc.returncode, H.describe(proc))

    def test_explicit_failure_is_not_reported_as_skip(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            bogus = tmp / "not-srg"
            bogus.mkdir()
            proc = self._run_with(tmp, bogus, explicit=True)
            self.assertNotIn("srg-absent", H.out_text(proc), "明示指定の誤りを skip へ畳んでいる")


class ResolutionOrderTest(H.BridgeTestCase):
    def _run(self, tmp, *, argv_srg=None, env_srg=None, hb_root=None):
        tmp = Path(tmp)
        args = ["--image-plan", _plan(tmp), "--assets-dir", H.make_assets_dir(tmp)]
        if argv_srg is not None:
            args += ["--srg-root", argv_srg]
        return H.run(
            args,
            env=H.clean_env(
                tmp,
                bin_dir=H.make_fake_bin(tmp),
                srg_root=env_srg,
                hb_root=hb_root,
                log=tmp / "log.jsonl",
            ),
        )

    def test_argv_wins_over_environment(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            chosen = H.make_srg(tmp, name="chosen-srg")
            other = H.make_srg(tmp, name="other-srg")
            proc = self._run(tmp, argv_srg=chosen, env_srg=other, hb_root=H.make_fake_plugin_root(tmp))
            self.assertEqual(0, proc.returncode, H.describe(proc))
            self.assertEqual(str(chosen), H.stdout_json(self, proc)["srg_root"], H.describe(proc))

    def test_environment_wins_over_sibling(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            sibling_srg = H.make_srg(tmp, name="sibling-srg")
            hb_root = H.make_fake_plugin_root(tmp, srg=sibling_srg)
            chosen = H.make_srg(tmp, name="env-srg")
            proc = self._run(tmp, env_srg=chosen, hb_root=hb_root)
            self.assertEqual(0, proc.returncode, H.describe(proc))
            self.assertEqual(str(chosen), H.stdout_json(self, proc)["srg_root"], H.describe(proc))

    def test_sibling_of_hb_root_is_resolved(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            srg = H.make_srg(tmp, name="slide-report-generator")
            hb_root = H.make_fake_plugin_root(tmp, srg=srg)
            proc = self._run(tmp, hb_root=hb_root)
            self.assertEqual(0, proc.returncode, H.describe(proc))
            self.assertIsNotNone(H.stdout_json(self, proc)["srg_root"], H.describe(proc))

    def test_reported_srg_root_is_the_directory_holding_vendor_scripts(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            srg = H.make_srg(tmp)
            proc = self._run(tmp, argv_srg=srg, hb_root=H.make_fake_plugin_root(tmp))
            reported = Path(H.stdout_json(self, proc)["srg_root"])
            for relpath in H.SRG_VENDOR_SCRIPTS:
                self.assertTrue((reported / relpath).is_file(), "{} が無い".format(relpath))

    def test_search_path_is_written_to_stderr(self):
        """brief stderr: SRG 解決の探索経路を出す (なぜ skip したかを追える)。"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            proc = self._run(tmp, hb_root=H.make_fake_plugin_root(tmp))
            self.assertTrue(H.err_text(proc).strip(), "探索経路が stderr に無い")


class RealPluginNeighbourTest(H.BridgeTestCase):
    """委譲先が repo に実在することの確認 (再実装しないことの前提)。"""

    def test_real_srg_vendor_scripts_exist(self):
        for relpath in H.SRG_VENDOR_SCRIPTS:
            H.require_file(self, H.REAL_SRG_ROOT / relpath, "slide-report-generator")

    def test_real_srg_genome_exists(self):
        H.require_file(self, H.REAL_SRG_ROOT / H.SRG_GENOME_RELPATH, "slide-report-generator")

    def test_real_sibling_is_resolved_without_any_hint(self):
        """HB_ROOT を実 plugin root にすると兄弟の実 SRG が解決される (段 c)。"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            plan = H.write_plan(
                tmp / "plan.json",
                H.plan_payload(sections=[H.section("intro", motifs=H.real_genome_motifs()[:1])]),
            )
            proc = H.run(
                ["--image-plan", plan, "--assets-dir", H.make_assets_dir(tmp), "--dry-run"],
                env=H.clean_env(
                    tmp,
                    bin_dir=H.make_fake_bin(tmp),
                    hb_root=H.PLUGIN_ROOT,
                    log=tmp / "log.jsonl",
                ),
            )
            self.assertEqual(0, proc.returncode, H.describe(proc))
            self.assertEqual(
                str(H.REAL_SRG_ROOT), H.stdout_json(self, proc)["srg_root"], H.describe(proc)
            )


if __name__ == "__main__":
    unittest.main()
