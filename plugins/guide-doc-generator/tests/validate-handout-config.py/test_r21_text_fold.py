# -*- coding: utf-8 -*-
"""R21 C52 説明文字数上限と折り畳み (CR-TEXT-FOLD / A8c / N10b)。

AC-C12-R21-52 が出所。上限は assets/tokens/<theme>.json の
text_limits.block_body_max_chars (既定 400)。検証専用実行は畳まず E-TEXT-OVERFLOW、
--normalize は残余を open=false の B10 へ移し provenance.text_fold_count を記録する。
"""

import json
import unittest

import _harness as H

DEFAULT_LIMIT = 400


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
    return cfg


class TextOverflowValidation(H.C12TestCase):

    def test_within_limit_passes(self):
        """上限以下の TEXT は素通り。"""
        res, _ = self.validate(text_config(long_body(DEFAULT_LIMIT - 40)))
        self.assert_exit(res, 0)
        self.assert_no_diag(res, "E-TEXT-OVERFLOW")

    def test_overflow_without_normalize_fails(self):
        """AC-C12-R21-52 (a): --normalize なしの検証は畳まず E-TEXT-OVERFLOW で exit 1。"""
        res, _ = self.validate(text_config(long_body(DEFAULT_LIMIT + 120)))
        self.assert_fails_with(res, "E-TEXT-OVERFLOW", "/sections/0/parts/0")

    def test_validation_does_not_modify_input(self):
        """検証専用実行が入力を変えない (畳むのは --normalize だけ)。"""
        path = self.write_config(text_config(long_body(DEFAULT_LIMIT + 120)))
        before = path.read_bytes()
        self.run_cli("--config", path)
        self.assertEqual(before, path.read_bytes())


class TextFoldNormalize(H.C12TestCase):

    def _fold(self, body, out_name="out.json", cfg=None):
        cfg = cfg or text_config(body)
        out = self.tmp / out_name
        res, _, out = self.normalize(cfg, out=out)
        return res, out

    def test_fold_moves_remainder_to_accordion(self):
        """AC-C12-R21-52 (b): body が上限以下へ縮み、直後に open=false の B10 が 1 件増える。"""
        res, out = self._fold(long_body(DEFAULT_LIMIT + 120))
        self.assert_exit(res, 0)
        data = self.read_out(out)
        parts = data["sections"][0]["parts"]
        self.assertEqual(2, len(parts), "B10 が 1 件だけ増えていない: %r" % [p["part"] for p in parts])
        self.assertEqual("TEXT", parts[0]["part"])
        self.assertLessEqual(len(parts[0]["data"]["body"]), DEFAULT_LIMIT)
        self.assertEqual("B10", parts[1]["part"])
        items = parts[1]["data"]["items"]
        self.assertEqual(1, len(items))
        self.assertIs(False, items[0]["open"])
        self.assertEqual("詳しい説明 (続き)", items[0]["summary"])
        self.assertEqual(1, data["provenance"]["text_fold_count"])

    def test_no_content_is_lost(self):
        """分割は欠落を伴わない (先頭部分 + 残余 = 元の body)。"""
        body = long_body(DEFAULT_LIMIT + 120)
        res, out = self._fold(body)
        self.assert_exit(res, 0)
        parts = self.read_out(out)["sections"][0]["parts"]
        joined = parts[0]["data"]["body"] + parts[1]["data"]["items"][0]["body"]
        self.assertEqual(body, joined)

    def test_split_point_is_after_last_sentence_end(self):
        """分割点は上限位置以前で最後に現れる文末 (。!?) の直後。"""
        res, out = self._fold(long_body(DEFAULT_LIMIT + 120, sentence_len=50))
        self.assert_exit(res, 0)
        head = self.read_out(out)["sections"][0]["parts"][0]["data"]["body"]
        self.assertTrue(head.endswith(("。", "!", "?")), "文末で切れていない: ...%r" % head[-10:])
        self.assertLessEqual(len(head), DEFAULT_LIMIT)
        self.assertGreater(len(head), DEFAULT_LIMIT - 50)

    def test_split_without_sentence_end_cuts_at_limit(self):
        """文末が 1 つも無ければ上限位置の直後で切る (決定論)。"""
        body = "あ" * (DEFAULT_LIMIT + 120)
        res, out = self._fold(body)
        self.assert_exit(res, 0)
        head = self.read_out(out)["sections"][0]["parts"][0]["data"]["body"]
        self.assertEqual(DEFAULT_LIMIT, len(head))

    def test_generated_part_id_suffix(self):
        """N10b: 生成する B10 の id は元 TEXT の id + '-cont'。"""
        res, out = self._fold(long_body(DEFAULT_LIMIT + 120))
        self.assert_exit(res, 0)
        parts = self.read_out(out)["sections"][0]["parts"]
        self.assertEqual("intro-t1-cont", parts[1]["id"])

    def test_generated_part_id_collision_gets_serial(self):
        """N10b: セクション内一意性が破れる場合は -cont2, -cont3 と伸ばす。"""
        cfg = text_config("")
        cfg["sections"][0]["parts"] = [
            H.text_part("intro-t1", long_body(DEFAULT_LIMIT + 120)),
            {"part": "B10", "id": "intro-t1-cont", "data": {
                "items": [{"summary": "既存の畳み", "body": "既にある内容", "open": False}]}},
        ]
        res, out = self._fold(None, cfg=cfg)
        self.assert_exit(res, 0)
        ids = [p["id"] for p in self.read_out(out)["sections"][0]["parts"]]
        self.assertIn("intro-t1-cont2", ids, "連番へ退避していない: %r" % ids)
        self.assertEqual(len(ids), len(set(ids)), "id が衝突している: %r" % ids)

    def test_folded_body_also_within_limit(self):
        """N10b: 折り畳み後の body も上限を超えない。"""
        res, out = self._fold(long_body(DEFAULT_LIMIT * 3))
        self.assert_exit(res, 0)
        data = self.read_out(out)
        for part in data["sections"][0]["parts"]:
            if part["part"] == "TEXT":
                self.assertLessEqual(len(part["data"]["body"]), DEFAULT_LIMIT)
            if part["part"] == "B10":
                for item in part["data"]["items"]:
                    self.assertLessEqual(len(item["body"]), DEFAULT_LIMIT)

    def test_fold_count_zero_when_nothing_folded(self):
        """折り畳みが起きなければ text_fold_count は 0。"""
        res, out = self._fold(long_body(DEFAULT_LIMIT - 40))
        self.assert_exit(res, 0)
        self.assertEqual(0, self.read_out(out)["provenance"]["text_fold_count"])

    def test_fold_is_byte_identical_across_runs(self):
        """AC-C12-R21-52 (b): 折り畳みを含む出力も 2 回実行でバイト一致。"""
        cfg = text_config(long_body(DEFAULT_LIMIT + 120))
        out1 = self.tmp / "f1.json"
        out2 = self.tmp / "f2.json"
        r1, path, _ = self.normalize(cfg, out=out1)
        r2 = self.run_cli("--config", path, "--normalize", "--out", out2)
        self.assert_exit(r1, 0)
        self.assert_exit(r2, 0)
        self.assertEqual(out1.read_bytes(), out2.read_bytes())


class ThemeDrivenLimit(H.C12TestCase):
    """C52: 上限はテーマ設定 (assets/tokens/<theme>.json) で変えられる。"""

    def _theme_name(self):
        tokens_dir = self.root / H.TOKENS_RELDIR
        self.assertTrue(tokens_dir.exists(), "テーマトークン置き場が無い: %s" % tokens_dir)
        names = sorted(p.stem for p in tokens_dir.glob("*.json"))
        self.assertTrue(names, "テーマトークンが 1 件も無い: %s" % tokens_dir)
        return names[0]

    def _set_limit(self, theme, value):
        path = self.root / H.TOKENS_RELDIR / ("%s.json" % theme)
        tokens = json.loads(path.read_text(encoding="utf-8"))
        tokens.setdefault("text_limits", {})["block_body_max_chars"] = value
        path.write_text(json.dumps(tokens, ensure_ascii=False, indent=2), encoding="utf-8")

    def test_raised_limit_prevents_fold(self):
        """AC-C12-R21-52 (c): 上限を上げると折り畳みが起きず TEXT が元のまま。"""
        theme = self._theme_name()
        self._set_limit(theme, 2000)
        body = long_body(DEFAULT_LIMIT + 120)
        cfg = text_config(body)
        cfg["theme"] = theme
        res, _, out = self.normalize(cfg)
        self.assert_exit(res, 0)
        parts = self.read_out(out)["sections"][0]["parts"]
        self.assertEqual(1, len(parts), "折り畳みが起きている: %r" % [p["part"] for p in parts])
        self.assertEqual(body, parts[0]["data"]["body"])
        self.assertEqual(0, self.read_out(out)["provenance"]["text_fold_count"])

    def test_lowered_limit_triggers_overflow(self):
        """上限を下げると、既定では通っていた長さが E-TEXT-OVERFLOW になる。"""
        theme = self._theme_name()
        self._set_limit(theme, 100)
        cfg = text_config(long_body(200))
        cfg["theme"] = theme
        res, _ = self.validate(cfg)
        self.assert_fails_with(res, "E-TEXT-OVERFLOW", "/sections/0/parts/0")

    def test_limit_falls_back_to_400_when_key_absent(self):
        """text_limits キー自体が無ければ 400 を用いる。"""
        theme = self._theme_name()
        path = self.root / H.TOKENS_RELDIR / ("%s.json" % theme)
        tokens = json.loads(path.read_text(encoding="utf-8"))
        tokens.pop("text_limits", None)
        path.write_text(json.dumps(tokens, ensure_ascii=False, indent=2), encoding="utf-8")
        cfg = text_config(long_body(DEFAULT_LIMIT + 120))
        cfg["theme"] = theme
        res, _ = self.validate(cfg)
        self.assert_fails_with(res, "E-TEXT-OVERFLOW")


class SentenceLengthWarning(H.C12TestCase):

    def test_long_sentences_are_warning_only(self):
        """failure_modes: 45 文字超の文が 3 つ以上で W-SENTENCE-LONG (既定では通す)。"""
        body = ("あ" * 50 + "。") * 3
        res, _ = self.validate(text_config(body))
        self.assert_exit(res, 0)
        self.assert_diag(res, "W-SENTENCE-LONG", "/sections/0/parts/0")

    def test_two_long_sentences_do_not_warn(self):
        """2 つまでは助言を出さない (閾値は 3 つ以上)。"""
        body = ("あ" * 50 + "。") * 2
        res, _ = self.validate(text_config(body))
        self.assert_exit(res, 0)
        self.assert_no_diag(res, "W-SENTENCE-LONG")


if __name__ == "__main__":
    unittest.main()
