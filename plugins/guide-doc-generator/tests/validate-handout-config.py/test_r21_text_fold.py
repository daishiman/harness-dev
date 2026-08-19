# -*- coding: utf-8 -*-
"""R21 C52 / R25 REQ-7 説明文字数上限 (CR-TEXT-FOLD / A8c / N10b)。

出所は AC-C12-R21-52 と script-brief-C12.json:120 / :869 (R25/REQ-7・goal-spec C73)。

R25/REQ-7 で契約が変わった。旧仕様 (超過分を open=false の B10 へ分割退避し
exit 0) は撤回済みで、現行契約は次のとおり:

- 上限は assets/tokens/<theme>.json の text_limits.block_body_max_chars
  (水準別は block_body_max_chars_by_detail_level)。値の正本は
  script-brief-C11.json#theme_token_schema_ownership.added_block_r22_values。
- --normalize なしの検証は E-TEXT-OVERFLOW (level=error) で exit 1。
- --normalize でも畳まない。fold の実行回数上限は全経路で 0 であり、超過は
  E-TEXT-OVERFLOW (level=error) で exit 1。provenance.text_fold_count は常に 0。
  超過を実際に止めるのは E-TEXT-OVERFLOW (水準別上限で判定・level=error) で
  あり、E-TEXT-FOLDED は「折り畳みへ退避した回数 > 0」を禁じる二重化として
  残るだけで到達しない (validate-handout-config.py の fold_section 直前の
  注記が正本)。

- 1 文の上限と 1 body あたりの文数は config/handout-visual-policy.json の
  sentence 節が正本 (W-SENTENCE-LONG / E-TEXT-PARAGRAPH。いずれも level=error)。

上限の数値はテーマトークンと確定値ファイルから読み、テストソースへ書かない
(旧版は DEFAULT_LIMIT = 400 を直書きしており、R25 で予算が変わっても永久に
緑のままだった)。
"""

import json
import unittest

import _harness as H

BRIEFS_DIR = H.REPO_ROOT / "plugin-plans" / "guide-doc-generator" / "briefs"
C11_BRIEF = BRIEFS_DIR / "script-brief-C11.json"
TEXT_GATE_DECISION = (
    H.REPO_ROOT / "plugin-plans" / "guide-doc-generator" / "improvement"
    / "text-length-gate-decision.json"
)
VISUAL_POLICY_RELPATH = "config/handout-visual-policy.json"


def long_body(total_chars, sentence_len=40):
    """文末 (。) を含む決定論的な長文を作る。"""
    out = []
    n = 0
    while n < total_chars:
        body = "あ" * (sentence_len - 1)
        out.append(body + "。")
        n += sentence_len
    return "".join(out)[:total_chars]


def text_config(body):
    cfg = H.valid_config()
    cfg["sections"] = [H.section("intro", parts=[H.text_part("intro-t1", body)])]
    return H.with_visual_floor(cfg)


class TextBudgetTestCase(H.C12TestCase):
    """上限値を必ずデータ側から引くための足場。"""

    def relax_sentence_gates(self):
        """文の長さ・本数の上限だけを外す (字数予算を測るための足場)。

        字数予算と文の作り方は別の軸で、config/handout-visual-policy.json#sentence
        が後者の正本である。字数予算を上げた検査に固定長の文を並べると、上げた
        のは字数なのに文数・文長で落ちてしまい、何を測っているのか分からなくなる。
        ここでは前者だけを見たいので後者を無効化する (後者そのものは
        test_sentence_gate 系が固定する)。
        """
        path = self.root / "config/handout-visual-policy.json"
        policy = json.loads(path.read_text(encoding="utf-8"))
        sentence = policy.setdefault("sentence", {})
        sentence.setdefault("sentence_gate", {})["max_chars"] = 10000
        per_body = sentence.setdefault("sentences_per_body", {})
        per_body["max_sentences"] = 10000
        per_body.pop("max_sentences_by_detail_level", None)
        path.write_text(json.dumps(policy, ensure_ascii=False, indent=2), encoding="utf-8")

    def theme_name(self):
        tokens_dir = self.root / H.TOKENS_RELDIR
        self.assertTrue(tokens_dir.exists(), "テーマトークン置き場が無い: %s" % tokens_dir)
        names = sorted(p.stem for p in tokens_dir.glob("*.json"))
        self.assertTrue(names, "テーマトークンが 1 件も無い: %s" % tokens_dir)
        return names[0]

    def canonical_standard(self):
        """block_body_max_chars の確定値 (standard_equals_default により standard と同値)。"""
        self.assertTrue(C11_BRIEF.is_file(), "上限の正本が読めない: %s" % C11_BRIEF)
        data = json.loads(C11_BRIEF.read_text(encoding="utf-8"))
        values = (data.get("theme_token_schema_ownership") or {}).get("added_block_r22_values")
        self.assertIsInstance(values, dict, "script-brief-C11.json に added_block_r22_values が無い")
        value = values.get("standard")
        self.assertIsInstance(value, int, "added_block_r22_values.standard が整数でない: %r" % value)
        return value

    def default_limit(self, theme=None):
        """テーマトークンが持つ既定上限 (block_body_max_chars)。"""
        theme = theme or self.theme_name()
        path = self.root / H.TOKENS_RELDIR / ("%s.json" % theme)
        tokens = json.loads(path.read_text(encoding="utf-8"))
        limit = (tokens.get("text_limits") or {}).get("block_body_max_chars")
        self.assertIsInstance(limit, int, "text_limits.block_body_max_chars が無い: %s" % path)
        return limit

    def set_limit(self, theme, value):
        path = self.root / H.TOKENS_RELDIR / ("%s.json" % theme)
        tokens = json.loads(path.read_text(encoding="utf-8"))
        tokens.setdefault("text_limits", {})["block_body_max_chars"] = value
        path.write_text(json.dumps(tokens, ensure_ascii=False, indent=2), encoding="utf-8")

    def themed(self, body, theme):
        cfg = text_config(body)
        cfg["theme"] = theme
        return cfg


class TextOverflowValidation(TextBudgetTestCase):

    def test_within_limit_passes(self):
        """上限以下の TEXT は素通り。"""
        limit = self.default_limit()
        res, _ = self.validate(text_config(long_body(limit // 2)))
        self.assert_exit(res, 0)
        self.assert_no_diag(res, "E-TEXT-OVERFLOW")

    def test_overflow_without_normalize_fails(self):
        """AC-C12-R21-52 (a): --normalize なしの検証は畳まず E-TEXT-OVERFLOW で exit 1。"""
        limit = self.default_limit()
        res, _ = self.validate(text_config(long_body(limit * 2)))
        self.assert_fails_with(res, "E-TEXT-OVERFLOW", "/sections/0/parts/0")

    def test_validation_does_not_modify_input(self):
        """検証専用実行が入力を変えない。"""
        limit = self.default_limit()
        path = self.write_config(text_config(long_body(limit * 2)))
        before = path.read_bytes()
        self.run_cli("--config", path)
        self.assertEqual(before, path.read_bytes())


class FoldIsForbidden(TextBudgetTestCase):
    """R25/REQ-7: --normalize は超過を畳んで逃がさない (fold 実行回数上限 0)。

    旧テスト (TextFoldNormalize) は「exit 0 で B10 へ退避される」を期待値として
    固定していた。それは利用者最優先要件『長ったらしく何行も続く文章は絶対に
    防ぐ』に反する挙動そのものであり、期待値ごと撤回する。
    """

    def test_normalize_fails_closed_with_text_folded(self):
        limit = self.default_limit()
        res, _, _ = self.normalize(text_config(long_body(limit * 2)))
        self.assert_fails_with(res, "E-TEXT-OVERFLOW", "/sections/0/parts/0")

    def test_no_output_is_written_on_overflow(self):
        """fail-closed: 畳んだ結果を書き出さない。"""
        limit = self.default_limit()
        res, _, out = self.normalize(text_config(long_body(limit * 2)))
        self.assert_exit(res, 1)
        self.assertFalse(out.exists(), "超過したのに正規化済み構成が書き出されている: %s" % out)

    def test_no_accordion_part_is_generated(self):
        """B10 への切り出しが起きないこと (id -cont も生えない)。"""
        limit = self.default_limit()
        res, _, out = self.normalize(text_config(long_body(limit * 2)))
        self.assert_exit(res, 1)
        if out.exists():
            parts = json.loads(out.read_text(encoding="utf-8"))["sections"][0]["parts"]
            self.assertEqual(
                ["TEXT"], [p["part"] for p in parts],
                "折り畳み先が生成されている: %r" % [p["id"] for p in parts],
            )

    def test_overflow_is_reported_regardless_of_normalize(self):
        """検査を --normalize の有無で切り替えない (旧 report_overflow=not args.normalize)。"""
        limit = self.default_limit()
        body = long_body(limit * 2)
        res_validate, _ = self.validate(text_config(body))
        res_normalize, _, _ = self.normalize(text_config(body), out=self.tmp / "n.json")
        self.assert_exit(res_validate, 1)
        self.assert_exit(res_normalize, 1)

    def test_fold_count_is_zero_for_a_conforming_document(self):
        """provenance.text_fold_count が非 0 になる経路は残っていない。"""
        limit = self.default_limit()
        res, _, out = self.normalize(text_config(long_body(limit // 2)))
        self.assert_exit(res, 0)
        self.assertEqual(0, self.read_out(out)["provenance"]["text_fold_count"])

    def test_authored_accordion_is_left_alone(self):
        """著者が自分で置いた B10 は触らない (塞ぐのは fold 回数の側だけ)。"""
        limit = self.default_limit()
        cfg = text_config(long_body(limit // 2))
        accordion = {
            "part": "B10", "id": "intro-a1",
            "data": {"items": [{"summary": "補足", "body": "後で読めばよい話", "open": False}]},
        }
        cfg["sections"][0]["parts"].append(accordion)
        res, _, out = self.normalize(cfg)
        self.assert_exit(res, 0)
        parts = self.read_out(out)["sections"][0]["parts"]
        self.assertEqual(accordion, [p for p in parts if p["id"] == "intro-a1"][0])


class ThemeDrivenLimit(TextBudgetTestCase):
    """C52: 上限はテーマ設定 (assets/tokens/<theme>.json) で変えられる。"""

    def test_raised_limit_prevents_overflow(self):
        """AC-C12-R21-52 (c): 上限を上げると超過が解消し TEXT が元のまま。"""
        self.relax_sentence_gates()
        theme = self.theme_name()
        body = long_body(self.default_limit(theme) * 2)
        self.set_limit(theme, len(body) * 2)
        res, _, out = self.normalize(self.themed(body, theme))
        self.assert_exit(res, 0)
        parts = [p for p in self.read_out(out)["sections"][0]["parts"]
                 if p["part"] == "TEXT"]
        self.assertEqual(1, len(parts), "本文が分割されている: %r" % [p["id"] for p in parts])
        self.assertEqual(body, parts[0]["data"]["body"])

    def test_lowered_limit_triggers_overflow(self):
        """上限を下げると、既定では通っていた長さが E-TEXT-OVERFLOW になる。"""
        theme = self.theme_name()
        limit = self.default_limit(theme)
        body = long_body(limit // 2)
        self.set_limit(theme, len(body) // 2)
        res, _ = self.validate(self.themed(body, theme))
        self.assert_fails_with(res, "E-TEXT-OVERFLOW", "/sections/0/parts/0")

    def test_fallback_when_key_absent_is_the_canonical_standard(self):
        """text_limits キーが無いときの既定は standard の確定値と一致する。

        旧版は 400 をテストへ直書きしていた (関数名にまで入っていた)。予算を
        引き下げても関数名と期待値が古いまま緑になるため、確定値から導出する。
        """
        theme = self.theme_name()
        fallback = self.canonical_standard()
        path = self.root / H.TOKENS_RELDIR / ("%s.json" % theme)
        tokens = json.loads(path.read_text(encoding="utf-8"))
        tokens.pop("text_limits", None)
        path.write_text(json.dumps(tokens, ensure_ascii=False, indent=2), encoding="utf-8")

        res, _ = self.validate(self.themed(long_body(fallback * 2), theme))
        self.assert_fails_with(res, "E-TEXT-OVERFLOW")

        res, _ = self.validate(self.themed(long_body(max(1, fallback // 2)), theme))
        self.assert_exit(res, 0)
        self.assert_no_diag(res, "E-TEXT-OVERFLOW")

    def test_shipped_default_matches_the_canonical_standard(self):
        """standard_equals_default: 既定上限と水準別 standard は同じ値。"""
        self.assertEqual(self.canonical_standard(), self.default_limit())


class SentenceGate(TextBudgetTestCase):
    """R25/REQ-7: 文長と文数は警告でなく完了ゲート (level=error)。

    旧テストは test_long_sentences_are_warning_only という名で「45 字超が 3 つ
    以上でも exit 0 で通す」ことを期待値に固定していた。利用者最優先要件の
    違反を通すことをテストが守っていた形なので、期待値ごと撤回する。
    """

    def gate_values(self):
        """1 文上限と 1 body あたり文数上限 (config が正本・未整備なら確定値)。"""
        policy_path = self.root / VISUAL_POLICY_RELPATH
        self.assertTrue(policy_path.exists(), "視覚方針の正本が無い: %s" % policy_path)
        sentence = json.loads(policy_path.read_text(encoding="utf-8")).get("sentence")
        if isinstance(sentence, dict):
            max_chars = (sentence.get("sentence_gate") or {}).get("max_chars")
            max_sentences = (sentence.get("sentences_per_body") or {}).get("max_sentences")
        else:
            self.assertTrue(TEXT_GATE_DECISION.is_file(), "確定値が読めない: %s" % TEXT_GATE_DECISION)
            decision = json.loads(TEXT_GATE_DECISION.read_text(encoding="utf-8"))["decision"]
            max_chars = decision["sentence_gate"]["max_chars"]
            max_sentences = decision["sentences_per_body"]["max_sentences"]
        self.assertIsInstance(max_chars, int)
        self.assertIsInstance(max_sentences, int)
        return max_chars, max_sentences

    def test_canonical_location_is_the_visual_policy_config(self):
        """閾値の住所は config/handout-visual-policy.json#sentence (script の定数ではない)。"""
        policy_path = self.root / VISUAL_POLICY_RELPATH
        sentence = json.loads(policy_path.read_text(encoding="utf-8")).get("sentence")
        self.assertIsInstance(
            sentence, dict,
            "sentence 節が %s に無い — 閾値が script 側の定数のままである" % VISUAL_POLICY_RELPATH,
        )

    def test_one_over_limit_sentence_is_an_error(self):
        max_chars, _ = self.gate_values()
        body = "あ" * max_chars + "。"
        res, _ = self.validate(text_config(body))
        self.assert_fails_with(res, "W-SENTENCE-LONG", "/sections/0/parts/0")

    def test_sentence_at_the_limit_passes(self):
        max_chars, _ = self.gate_values()
        body = "あ" * (max_chars - 1) + "。"
        res, _ = self.validate(text_config(body))
        self.assert_exit(res, 0)
        self.assert_no_diag(res, "W-SENTENCE-LONG")

    def test_over_max_sentences_is_a_paragraph_error(self):
        _, max_sentences = self.gate_values()
        body = "短く書く。" * (max_sentences + 1)
        res, _ = self.validate(text_config(body))
        self.assert_fails_with(res, "E-TEXT-PARAGRAPH", "/sections/0/parts/0")

    def test_max_sentences_boundary_passes(self):
        _, max_sentences = self.gate_values()
        body = "短く書く。" * max_sentences
        res, _ = self.validate(text_config(body))
        self.assert_exit(res, 0)
        self.assert_no_diag(res, "E-TEXT-PARAGRAPH")

    def test_threshold_comes_from_config_not_from_the_script(self):
        """config の値を書き換えると判定が追従する (script 側は fallback 定数のみ)。"""
        max_chars, max_sentences = self.gate_values()
        policy_path = self.root / VISUAL_POLICY_RELPATH
        policy = json.loads(policy_path.read_text(encoding="utf-8"))
        tightened = max(2, max_chars // 2)
        policy["sentence"] = {
            "sentence_gate": {"code": "W-SENTENCE-LONG", "level": "error", "max_chars": tightened},
            "sentences_per_body": {
                "code": "E-TEXT-PARAGRAPH", "level": "error", "max_sentences": max_sentences,
            },
        }
        policy_path.write_text(json.dumps(policy, ensure_ascii=False, indent=2), encoding="utf-8")

        body = "あ" * tightened + "。"
        res, _ = self.validate(text_config(body))
        self.assert_fails_with(res, "W-SENTENCE-LONG", "/sections/0/parts/0")


if __name__ == "__main__":
    unittest.main()
