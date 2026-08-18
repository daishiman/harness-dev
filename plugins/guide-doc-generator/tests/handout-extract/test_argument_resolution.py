"""引数既定値と上書きの解決結果 (task-spec acceptance_criterion) を固定する。

前半 (OracleTest) は正解表そのものの性質で、実装に依存しないので緑。
後半 (DeclaredResolutionTest) は build_target が宣言する CR-EXTRACT-ARGS を
13 通り全件で正解表と突き合わせるので、実装前は赤。
"""

import posixpath
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import contract_lib  # noqa: E402
import resolution_spec as rspec  # noqa: E402

COMMAND_MD = contract_lib.build_target()


class OracleTest(unittest.TestCase):
    """正解表の性質 (brief から読み取れることの再確認)。"""

    def test_case_space_is_thirteen(self):
        self.assertEqual(13, len(rspec.enumerate_cases()))

    def test_entry_validation_always_stops_before_delegation(self):
        for case in rspec.enumerate_cases():
            if case.html_state in ("absent", "missing", "dir"):
                with self.subTest(case=case.name):
                    got = rspec.expected(case)
                    self.assertEqual("stop", got["action"])
                    self.assertIn(got["stop_reason"], rspec.STOP_REASONS)
                    self.assertIsNone(got["out"], "停止時は出力先を解決しない")

    def test_directory_is_never_expanded(self):
        """ディレクトリ指定はどの --out 指定でも停止する (どの HTML を正とするか推測しない)。"""
        for case in rspec.enumerate_cases():
            if case.html_state == "dir":
                self.assertEqual("html-path-is-directory", rspec.expected(case)["stop_reason"])

    def test_default_out_sits_next_to_input_html(self):
        for case in rspec.enumerate_cases():
            if case.html_state == "file" and not case.out_given:
                self.assertEqual(
                    posixpath.join(rspec.HTML_DIR, "handout-config.json"),
                    rspec.expected(case)["out"],
                )

    def test_out_override_changes_only_the_config_destination(self):
        for case in rspec.enumerate_cases():
            if case.html_state == "file" and case.out_given:
                self.assertEqual(rspec.OUT_ARG, rspec.expected(case)["out"])

    def test_report_is_placed_beside_out(self):
        for case in rspec.enumerate_cases():
            got = rspec.expected(case)
            if got["out"] is not None:
                self.assertEqual(posixpath.dirname(got["out"]), got["report_dir"])

    def test_existing_out_never_silently_overwrites(self):
        for case in rspec.enumerate_cases():
            if case.html_state == "file" and case.out_exists:
                self.assertEqual("confirm-overwrite", rspec.expected(case)["action"])

    def test_only_valid_input_delegates(self):
        delegating = [c for c in rspec.enumerate_cases() if rspec.expected(c)["action"] == "delegate"]
        self.assertEqual(
            2,
            len(delegating),
            "委譲するのは html-path が実在ファイルで --out 先が未作成の 2 通りだけ",
        )


class DeclaredResolutionTest(unittest.TestCase):
    """build_target が宣言する引数解決規則 (実装前は赤)。"""

    @classmethod
    def setUpClass(cls):
        cls.block = None
        cls.errors = []
        if COMMAND_MD.is_file():
            text = COMMAND_MD.read_text(encoding="utf-8")
            _, body = contract_lib.split_frontmatter(text)
            cls.block, cls.errors = contract_lib.extract_args_block(body)

    def _block(self):
        if not COMMAND_MD.is_file():
            self.fail(f"未実装: {COMMAND_MD}")
        if self.block is None:
            self.fail(
                f'CR-EXTRACT-ARGS を id に持つ fenced json ブロックが無い ({COMMAND_MD}) '
                f"/ JSON パースエラー: {self.errors}"
            )
        return self.block

    def test_declared_stop_reasons_match_vocabulary(self):
        block = self._block()
        self.assertEqual(
            set(rspec.STOP_REASONS),
            rspec.declared_stop_reasons(block),
            "停止理由は failure_modes 1 の 3 分岐に 1:1 で対応する",
        )

    def test_declared_resolution_matches_oracle_for_all_cases(self):
        block = self._block()
        try:
            mismatches = rspec.diff_against_oracle(block)
        except rspec.SpecError as exc:
            self.fail(f"宣言された引数解決規則が解釈できない: {exc}")
        self.assertEqual(
            [],
            [(c.name, w, g) for c, w, g in mismatches],
            "宣言された引数解決が正解表と食い違う",
        )

    def test_declared_default_out_is_a_template_not_a_fixed_path(self):
        block = self._block()
        default = ((block.get("flags") or {}).get("--out") or {}).get("default")
        self.assertIsInstance(default, str, "--out の既定値の宣言が無い")
        self.assertIn(
            "{html_dir}",
            default,
            "既定の出力先は入力 HTML のディレクトリに従属する (固定パスにしない)",
        )


if __name__ == "__main__":
    unittest.main()
