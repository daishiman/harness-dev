"""同一入力の再現性 — task-spec の受入判定「同一入力の再現性」と failure_modes。

生成 PNG のバイト一致は約束しない (gpt-image-2 に seed が無い)。約束するのは
**決定論変換の部分**、すなわち image-deck-plan.json の中身・slug の割り当て・
判定 JSON の形が同一入力に対して一致することである。
"""

import json
import tempfile
import unittest
from pathlib import Path

import _harness as H


SECTIONS = ("intro", "build", "wrap up")


def _sections():
    return [H.section(sid) for sid in SECTIONS]


class _Base(H.BridgeTestCase):
    def _run_once(self, tmp, name, *, extra=(), pngs="all"):
        tmp = Path(tmp)
        srg = H.make_srg(tmp)
        bin_dir = H.make_fake_bin(tmp)
        plan = H.write_plan(tmp / "plan.json", H.plan_payload(sections=_sections()))
        assets = H.make_assets_dir(tmp, name)
        proc = H.run(
            ["--image-plan", plan, "--assets-dir", assets, "--srg-root", srg, *extra],
            env=H.clean_env(
                tmp, bin_dir=bin_dir, log=tmp / (name + ".jsonl"), **{H.ENV_PNGS: pngs}
            ),
        )
        return proc, assets


def _normalise(data, assets_a, assets_b):
    """assets-dir 依存の文字列だけを畳んだ比較用の判定 JSON。"""
    text = json.dumps(data, ensure_ascii=False, sort_keys=True)
    return text.replace(str(assets_a), "<ASSETS>").replace(str(assets_b), "<ASSETS>")


class DeterministicConversionTest(_Base):
    def test_deck_plan_is_byte_identical_between_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, a = self._run_once(tmp, "a", extra=["--dry-run"])
            _, b = self._run_once(tmp, "b", extra=["--dry-run"])
            path = Path("srg-work") / "assets" / "generated" / "image-deck-plan.json"
            first, second = Path(a) / path, Path(b) / path
            self.assertTrue(first.is_file() and second.is_file(), "image-deck-plan.json が無い")
            self.assertEqual(
                json.loads(first.read_text(encoding="utf-8")),
                json.loads(second.read_text(encoding="utf-8")),
                "同一入力で image-deck-plan.json が一致しない",
            )

    def test_slug_assignment_is_stable(self):
        with tempfile.TemporaryDirectory() as tmp:
            first, _ = self._run_once(tmp, "a", extra=["--dry-run"])
            second, _ = self._run_once(tmp, "b", extra=["--dry-run"])
            self.assertEqual(
                [e["slug"] for e in H.stdout_json(self, first)["images"]],
                [e["slug"] for e in H.stdout_json(self, second)["images"]],
            )

    def test_stdout_verdict_is_stable_in_dry_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            first, a = self._run_once(tmp, "a", extra=["--dry-run"])
            second, b = self._run_once(tmp, "b", extra=["--dry-run"])
            self.assertEqual(
                _normalise(H.stdout_json(self, first), a, b),
                _normalise(H.stdout_json(self, second), a, b),
            )

    def test_exit_code_is_stable(self):
        with tempfile.TemporaryDirectory() as tmp:
            first, _ = self._run_once(tmp, "a")
            second, _ = self._run_once(tmp, "b")
            self.assertEqual(first.returncode, second.returncode, H.describe(second))

    def test_json_keys_are_ordered_stably(self):
        """同一入力で stdout がバイト一致する (キー順が実行ごとに揺れない)。"""
        with tempfile.TemporaryDirectory() as tmp:
            first, a = self._run_once(tmp, "a", extra=["--dry-run"])
            second, b = self._run_once(tmp, "b", extra=["--dry-run"])
            self.assertEqual(
                H.out_text(first).replace(str(a), "<ASSETS>"),
                H.out_text(second).replace(str(b), "<ASSETS>"),
            )


class RerunOnSameAssetsDirTest(_Base):
    """同じ assets-dir に対する 2 回目は冪等 (algorithm 12) で、結果も同じ。"""

    def _run_twice(self, tmp):
        tmp = Path(tmp)
        srg = H.make_srg(tmp)
        bin_dir = H.make_fake_bin(tmp)
        plan = H.write_plan(tmp / "plan.json", H.plan_payload(sections=_sections()))
        assets = H.make_assets_dir(tmp)
        env = H.clean_env(tmp, bin_dir=bin_dir, log=tmp / "log.jsonl", **{H.ENV_PNGS: "all"})
        args = ["--image-plan", plan, "--assets-dir", assets, "--srg-root", srg]
        first = H.run(args, env=env)
        images_after_first = H.tree_snapshot(Path(assets) / "images")
        second = H.run(args, env=env)
        return first, second, assets, images_after_first

    def test_second_run_returns_the_same_verdict(self):
        with tempfile.TemporaryDirectory() as tmp:
            first, second, _, _ = self._run_twice(tmp)
            self.assertEqual(first.returncode, second.returncode, H.describe(second))
            self.assertEqual(
                H.stdout_json(self, first)["status"], H.stdout_json(self, second)["status"]
            )

    def test_second_run_does_not_change_recovered_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, second, assets, before = self._run_twice(tmp)
            self.assertEqual(
                before, H.tree_snapshot(Path(assets) / "images"), "2 回目で素材が書き換わった:\n" + H.describe(second)
            )

    def test_second_run_reports_no_delegation(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, second, _, _ = self._run_twice(tmp)
            self.assertEqual(
                [], H.stdout_json(self, second)["delegated_commands"], H.describe(second)
            )


if __name__ == "__main__":
    unittest.main()
