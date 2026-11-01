# -*- coding: utf-8 -*-
"""C12 の 1 文長ゲートの受入テスト (R25 / 利用者要求 R7)。

R7 は「文章が長ったらしく何行も続く」状態を**絶対に**防ぐことを求めている。
その受け皿が config/handout-visual-policy.json#sentence であり、ここで固定するのは
次の 3 点。

1. **境界**: 正本が `max_chars=60` と宣言したとき、読み手が目にする 61 文字目で
   落ちる。句点は読み手に見えているので 1 文の一部として数える。落として数えると
   上限が実質 1 文字ぶん緩む (off-by-one)。
2. **正本が効く**: 上限値を正本側で動かすと判定も動く。script の定数が実質の
   正本になっていないことの陽性・陰性対照。
3. **鏡が食い違わない**: script が持つ fallback 定数は正本が読めないときの
   退避であり、出荷している正本と同じ値でなければならない。値がずれたまま
   出荷されると、正本を読めた経路と読めなかった経路で通る文の長さが変わる。

なお `TestCanonAbsenceFailsClosed` (test_visual_density.py) が「正本が消えても
ゲートは緩まない」を固定しているため、fallback 定数そのものは削除できない。
「重複保持 0 件」は定数を消すことでは達成できないので、**ずれたまま出荷できない**
ことをテストで固定する形にしてある。
"""

import importlib.util
import json
import unittest

import _harness as H


def load_script_module():
    """ハイフンを含むファイル名なので importlib で直接読む。"""
    spec = importlib.util.spec_from_file_location("hb_c12", str(H.SRC_SCRIPT))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def body_of(chars):
    """句点込みで chars 文字ちょうどの 1 文を作る。"""
    return "あ" * (chars - 1) + "。"


def config_with_body(body):
    cfg = H.with_visual_floor(H.valid_config())
    # visual_section の 4 番目が TEXT 部品 (先頭は図解・画像・表)
    cfg["sections"][0]["parts"][3]["data"]["body"] = body
    return cfg


class SentenceLengthBoundary(H.C12TestCase):
    """正本の宣言値ちょうどまでが通り、1 文字超えたら落ちる。"""

    def canon_max_chars(self):
        path = self.root / "config" / "handout-visual-policy.json"
        policy = json.loads(path.read_text(encoding="utf-8"))
        return policy["sentence"]["sentence_gate"]["max_chars"]

    def test_exactly_at_the_limit_passes(self):
        limit = self.canon_max_chars()
        res, _ = self.validate(config_with_body(body_of(limit)))
        self.assert_no_diag(res, "W-SENTENCE-LONG")
        self.assert_exit(res, 0)

    def test_one_character_over_the_limit_fails(self):
        limit = self.canon_max_chars()
        res, _ = self.validate(config_with_body(body_of(limit + 1)))
        self.assert_fails_with(res, "W-SENTENCE-LONG", "/sections/0/parts/3")

    def test_the_terminator_counts_as_part_of_the_sentence(self):
        """句点を落として数えていると、この 1 件だけが通ってしまう。"""
        limit = self.canon_max_chars()
        over = body_of(limit + 1)
        self.assertEqual(limit + 1, len(over))
        self.assertTrue(over.endswith("。"))
        res, _ = self.validate(config_with_body(over))
        self.assert_diag(res, "W-SENTENCE-LONG")

    def test_a_sentence_without_a_terminator_is_measured_too(self):
        limit = self.canon_max_chars()
        res, _ = self.validate(config_with_body("あ" * (limit + 1)))
        self.assert_diag(res, "W-SENTENCE-LONG")


class SentenceLimitComesFromTheCanon(H.C12TestCase):
    """閾値の出所が正本であって script の定数でないことの対照。"""

    def patch_sentence(self, **attrs):
        path = self.root / "config" / "handout-visual-policy.json"
        policy = json.loads(path.read_text(encoding="utf-8"))
        policy["sentence"]["sentence_gate"].update(attrs)
        path.write_text(json.dumps(policy, ensure_ascii=False, indent=2), encoding="utf-8")

    def test_raising_the_canon_lets_a_longer_sentence_through(self):
        self.patch_sentence(max_chars=120)
        res, _ = self.validate(config_with_body(body_of(80)))
        self.assert_no_diag(res, "W-SENTENCE-LONG")

    def test_lowering_the_canon_rejects_a_previously_accepted_sentence(self):
        self.patch_sentence(max_chars=20)
        res, _ = self.validate(config_with_body(body_of(30)))
        self.assert_fails_with(res, "W-SENTENCE-LONG")

    def test_demoting_the_level_does_not_re_open_the_gate(self):
        """正本で level を下げても error のままであること。

        重大度は FALLBACK_ERROR_CODES との和集合で決まり、正本は昇格だけを
        できる (降格経路は意図的に無い。F-C1201SFV-LEVEL-01 / P05-x-115)。
        R7 は「絶対に防ぐ」なので、設定で緩められる方が事故になる。
        """
        self.patch_sentence(level="warning")
        res, _ = self.validate(config_with_body(body_of(200)))
        self.assert_fails_with(res, "W-SENTENCE-LONG")


class FallbackMirrorsTheShippedCanon(unittest.TestCase):
    """script の fallback 定数と出荷中の正本が同じ値であること。

    正本が読めないときだけ使う退避なので削除はできない (test_visual_density.py
    ::TestCanonAbsenceFailsClosed)。削除できない以上、**ずれたまま出荷できない**
    ことを機械で押さえるのがここの役目。正本を書き換えて定数を直し忘れると赤くなる。
    """

    @classmethod
    def setUpClass(cls):
        cls.module = load_script_module()
        path = H.SRC_PLUGIN_ROOT / "config" / "handout-visual-policy.json"
        cls.sentence = json.loads(path.read_text(encoding="utf-8"))["sentence"]

    def test_max_chars_mirror(self):
        self.assertEqual(self.sentence["sentence_gate"]["max_chars"],
                         self.module.FALLBACK_LONG_SENTENCE_CHARS)

    def test_count_threshold_mirror(self):
        self.assertEqual(self.sentence["sentence_gate"]["max_count"],
                         self.module.FALLBACK_LONG_SENTENCE_COUNT)

    def test_max_sentences_per_body_mirror(self):
        self.assertEqual(self.sentence["sentences_per_body"]["max_sentences"],
                         self.module.FALLBACK_MAX_SENTENCES_PER_BODY)

    def test_codes_are_error_regardless_of_the_canon(self):
        """正本が読めない経路でも、この 2 つの code は error 側にいること。"""
        for code in ("W-SENTENCE-LONG", "E-TEXT-PARAGRAPH"):
            self.assertIn(code, self.module.FALLBACK_ERROR_CODES)


class SentenceCountBoundary(H.C12TestCase):
    """1 本文あたりの文数の上限も正本から引く (E-TEXT-PARAGRAPH)。"""

    def canon_max_sentences(self):
        path = self.root / "config" / "handout-visual-policy.json"
        policy = json.loads(path.read_text(encoding="utf-8"))
        return policy["sentence"]["sentences_per_body"]["max_sentences"]

    def test_at_the_limit_passes(self):
        limit = self.canon_max_sentences()
        res, _ = self.validate(config_with_body("短い文。" * limit))
        self.assert_no_diag(res, "E-TEXT-PARAGRAPH")

    def test_one_sentence_over_the_limit_fails(self):
        limit = self.canon_max_sentences()
        res, _ = self.validate(config_with_body("短い文。" * (limit + 1)))
        self.assert_fails_with(res, "E-TEXT-PARAGRAPH", "/sections/0/parts/3")


if __name__ == "__main__":
    unittest.main()
