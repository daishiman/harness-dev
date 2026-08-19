"""output_contract.abort と fail_closed_scope (c) を固定する。

正本: hook-brief-C10.json#output_contract.abort / #fail_closed_scope / #failure_modes

- 検査を完走できないとき (予算超過・サイズ超過) は exit0
- ただし stdout へ {"systemMessage": "..."} の JSON を **1 行** 出して打ち切りを明示する
- 打ち切りを「exit0 かつ無出力」で行うと合格と区別できない (failure_modes 最終項)
"""

import json
import shutil

from hb_c10 import (BLOCK_PREFIX, BUDGET_CONFIG, BUDGET_KEY,
                    BUDGET_SECTION_KEY, C10TestCase, PLUGIN_ROOT, clean_html,
                    external_html, size_limit_bytes)

# 1 行あたりの詰め物 (行数を増やしすぎないため長い行にする)
_PAD_LINE = "<!-- " + ("x" * 4000) + " -->\n"


def _padded_html(total_bytes, violating):
    """指定バイト数以上 (以下) の HTML を作る。"""
    base = external_html() if violating else clean_html()
    pad_needed = max(0, total_bytes - len(base.encode("utf-8")))
    reps = pad_needed // len(_PAD_LINE.encode("utf-8"))
    return base.replace("<!--EXTRA-->", "") + (_PAD_LINE * reps)


class TestOversizedFileAborts(C10TestCase):
    """acceptance_checks[10]: max_bytes 超は exit0 + 打ち切り systemMessage。

    閾値は config/handout-output.json#size_limits.hook_scan_budget.max_bytes
    から読む (テストへ数値を焼かない)。
    """

    def setUp(self):
        super().setUp()
        self.res = self.run_on(_padded_html(size_limit_bytes() + 512 * 1024, True))

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
        res = self.run_on(_padded_html(size_limit_bytes() - 1024 * 1024, True))
        self.assertEqual(2, res.rc,
                         "max_bytes 未満は完走して違反を報告する\n{}".format(res))

    def test_large_but_under_limit_clean_passes_silently(self):
        res = self.run_on(_padded_html(size_limit_bytes() - 1024 * 1024, False))
        self.assertPassSilently(res, "max_bytes 未満・違反なしは無出力")


class TestMissingBudgetKeyIsVisible(C10TestCase):
    """acceptance_checks[11]: 予算キーを config から抜くと未検査 + 欠落キー名。

    hook-brief-C10.json#budget_thresholds.if_key_missing は「ソース側の既定値へ
    倒さず exit0 + 欠落キー名つき systemMessage」を指定している。この検査は
    同時に、予算検査が空ゲートでないこと (config を壊すと挙動が変わること) の
    実測でもある — 正本ツリーは触らず、複製 plugin root 上で行う。
    """

    #: 複製する最小の plugin root (self-resolve に要るものだけ)
    _COPY = (".claude-plugin/plugin.json",
             "config/handout-output.json",
             "hooks/guard-handout-external-ref.py",
             "scripts/verify-handout-selfcontained.py")

    def _clone_root(self, mutate):
        root = self.tmp / "_plugin-root"
        for rel in self._COPY:
            dst = root / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(PLUGIN_ROOT / rel, dst)
        cfg = root / "config" / "handout-output.json"
        data = json.loads(cfg.read_text(encoding="utf-8"))
        mutate(data)
        cfg.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                       encoding="utf-8")
        return root

    def _run_with_root(self, mutate):
        root = self._clone_root(mutate)
        target = self.make_target(external_html())
        return self.run_hook(self.payload(target),
                             hook_path=root / "hooks" / "guard-handout-external-ref.py")

    def test_intact_clone_still_blocks(self):
        """複製そのものは正本と同じ挙動 (複製手順が結果を作っていないこと)。"""
        res = self._run_with_root(lambda data: None)
        self.assertEqual(2, res.rc,
                         "無改変の複製 root では通常どおり違反を報告する\n{}".format(res))

    def test_missing_budget_key_aborts_with_key_name(self):
        def drop(data):
            data[BUDGET_SECTION_KEY].pop(BUDGET_KEY)

        res = self._run_with_root(drop)
        self.assertEqual(0, res.rc,
                         "予算宣言の不在は exit2 を立てない (if_key_missing)\n{}".format(res))
        obj = res.system_message()
        self.assertIsNotNone(
            obj, "予算宣言が無いのに黙って素通しした (合格と区別できない)\n{}".format(res))
        self.assertIn("{}.{}".format(BUDGET_SECTION_KEY, BUDGET_KEY),
                      obj["systemMessage"],
                      "systemMessage に欠落キー名が出ていない\n{}".format(res))

    def test_missing_budget_key_does_not_fall_back_to_source_default(self):
        """ソース側の既定値へ倒れていないこと (倒れていれば検査が走り exit2 になる)。"""
        def drop(data):
            data[BUDGET_SECTION_KEY].pop(BUDGET_KEY)

        res = self._run_with_root(drop)
        self.assertNotIn(BLOCK_PREFIX, res.err,
                         "予算不在なのに検査が走った = ソース側に第 2 正本がある\n{}".format(res))


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
