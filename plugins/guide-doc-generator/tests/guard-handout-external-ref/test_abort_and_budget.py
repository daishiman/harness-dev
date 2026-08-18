"""output_contract.abort と fail_closed_scope (c) を固定する。

正本: hook-brief-C10.json#output_contract.abort / #fail_closed_scope / #failure_modes

- 検査を完走できないとき (予算超過・サイズ超過) は exit0
- ただし stdout へ {"systemMessage": "..."} の JSON を **1 行** 出して打ち切りを明示する
- 打ち切りを「exit0 かつ無出力」で行うと合格と区別できない (failure_modes 最終項)
"""

from hb_c10 import (BLOCK_PREFIX, C10TestCase, SIZE_LIMIT_BYTES, clean_html,
                    external_html)

# 1 行あたりの詰め物 (行数を増やしすぎないため長い行にする)
_PAD_LINE = "<!-- " + ("x" * 4000) + " -->\n"


def _padded_html(total_bytes, violating):
    """指定バイト数以上 (以下) の HTML を作る。"""
    base = external_html() if violating else clean_html()
    pad_needed = max(0, total_bytes - len(base.encode("utf-8")))
    reps = pad_needed // len(_PAD_LINE.encode("utf-8"))
    return base.replace("<!--EXTRA-->", "") + (_PAD_LINE * reps)


class TestOversizedFileAborts(C10TestCase):
    """acceptance_checks[10]: 8 MiB 超は exit0 + 打ち切り systemMessage。"""

    def setUp(self):
        super().setUp()
        self.res = self.run_on(_padded_html(SIZE_LIMIT_BYTES + 512 * 1024, True))

    def test_exit_code_is_zero(self):
        self.assertEqual(0, self.res.rc,
                         "打ち切りは exit2 を立てない (fail_closed_scope (c))\n{}".format(self.res))

    def test_stdout_has_exactly_one_json_line(self):
        lines = [l for l in self.res.out.splitlines() if l.strip()]
        self.assertEqual(1, len(lines),
                         "stdout は systemMessage の JSON 1 行\n{}".format(self.res))

    def test_stdout_json_has_system_message(self):
        obj = self.res.system_message()
        self.assertIsNotNone(obj,
                             "stdout が {{'systemMessage': ...}} の JSON 1 行になっていない\n{}".format(self.res))
        self.assertIsInstance(obj["systemMessage"], str)
        self.assertTrue(obj["systemMessage"].strip(),
                        "空の systemMessage では打ち切りを可視化できない")

    def test_not_silently_passing(self):
        """黙って合格に見せない (failure_modes 最終項)。"""
        self.assertNotEqual("", self.res.out.strip(), str(self.res))

    def test_no_block_header_on_abort(self):
        self.assertNotIn(BLOCK_PREFIX, self.res.err,
                         "打ち切りは BLOCKED ではない\n{}".format(self.res))


class TestUnderLimitIsInspected(C10TestCase):
    """閾値未満は打ち切らず通常検査する (打ち切りを既定動作にしない)。"""

    def test_large_but_under_limit_still_blocks(self):
        res = self.run_on(_padded_html(SIZE_LIMIT_BYTES - 1024 * 1024, True))
        self.assertEqual(2, res.rc,
                         "8 MiB 未満は完走して違反を報告する\n{}".format(res))

    def test_large_but_under_limit_clean_passes_silently(self):
        res = self.run_on(_padded_html(SIZE_LIMIT_BYTES - 1024 * 1024, False))
        self.assertPassSilently(res, "8 MiB 未満・違反なしは無出力")


class TestAbortIsDistinguishableFromPass(C10TestCase):
    """合格 (無出力) と打ち切り (systemMessage) が観測可能に別物であること。"""

    def test_pass_has_no_system_message(self):
        res = self.run_on(clean_html())
        self.assertIsNone(res.system_message(),
                          "合格時に systemMessage を出すと打ち切りと区別できない\n{}".format(res))

    def test_out_of_scope_has_no_system_message(self):
        res = self.run_on(external_html(), with_config=False)
        self.assertIsNone(res.system_message(),
                          "対象外の素通しは打ち切りではない\n{}".format(res))
