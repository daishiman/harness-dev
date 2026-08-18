"""D2-emoji を固定する。旧 denylist 撤去の回帰テストを含む。

正本:
  - hook-brief-C10.json#detection_rules[1] (D2) — 規則本体は持たず CR-EMOJI へ委譲
  - script-brief-C16.json#canonical_rules.emoji_rule (CR-EMOJI = SC-05 の二層規則)

最重要 (P03 Y-03):
  Unicode ブロック丸ごとの denylist (旧記述の U+2600-U+27BF / U+2B00-U+2BFF 等) は
  撤去済み。★ U+2605 / ✔ U+2714 (VS16 なし) は絵文字ではなく pass する。
  ここが赤のまま実装されると、C10 だけが落とす構造的な偽陽性が復活する。
"""

from hb_c10 import C10TestCase, D2, clean_html, emoji_html


class TestD2Block(C10TestCase):
    """acceptance_checks[6]: 絵文字を含むとき exit2 + stderr に D2-emoji。"""

    def test_rocket_in_heading(self):
        self.assertBlocked(self.run_on(emoji_html()), D2)

    def test_pointing_hand(self):
        html = clean_html(extra="<p>まずはここから \U0001F449 触ってみる</p>")
        self.assertBlocked(self.run_on(html), D2)

    def test_white_check_mark_u2705(self):
        """U+2705 は層 1 (単独で違反)。✔ U+2714 と混同しない。"""
        html = clean_html(extra="<span>✅ 完了</span>")
        self.assertBlocked(self.run_on(html), D2)

    def test_regional_indicator_flag(self):
        html = clean_html(extra="<li>\U0001F1EF\U0001F1F5 日本語版</li>")
        self.assertBlocked(self.run_on(html), D2)

    def test_layer2_codepoint_with_vs16(self):
        """層 2 (U+2699) は VS16 を伴ったときだけ違反。"""
        html = clean_html(extra="<button>⚙️ 設定</button>")
        self.assertBlocked(self.run_on(html), D2)

    def test_copyright_with_vs16(self):
        html = clean_html(extra="<p>©️ 2026</p>")
        self.assertBlocked(self.run_on(html), D2)

    def test_keycap_sequence(self):
        html = clean_html(extra="<span>1️⃣</span>")
        self.assertBlocked(self.run_on(html), D2)

    def test_emoji_inside_attribute_value(self):
        """判定対象は属性値も含む (CR-EMOJI は文書全体のコードポイント列)。"""
        html = clean_html(extra='<img src="data:image/png;base64,AA==" alt="完了 ✅">')
        self.assertBlocked(self.run_on(html), D2)

    def test_numeric_character_reference_emoji(self):
        """文字参照で書かれた絵文字も復号後に捕まる (CR-EMOJI の convert_charrefs)。"""
        html = clean_html(extra="<p>&#128640; 起動</p>")
        self.assertBlocked(self.run_on(html), D2)

    def test_stderr_carries_codepoints(self):
        res = self.run_on(clean_html(extra="<p>\U0001F449 ここ</p>"))
        self.assertBlocked(res, D2)
        self.assertIn("U+1F449", res.err.upper(),
                      "違反コードポイントを stderr に出す (C16 と突き合わせるため)\n{}".format(res))


class TestD2SymbolRegression(C10TestCase):
    """acceptance_checks[11]: 旧 denylist U+2600-U+27BF 撤去の回帰テスト。

    ここが落ちるということは、hook が CR-EMOJI ではなくブロック denylist を
    持ってしまったということである (P03 Y-03 の再発)。
    """

    def _pass(self, ch, name):
        html = clean_html(extra="<p>{} 重要</p>".format(ch))
        self.assertPassSilently(self.run_on(html),
                                "{} (U+{:04X}) は絵文字ではない".format(name, ord(ch)))

    def test_black_star_u2605(self):
        self._pass("★", "★")

    def test_white_star_u2606(self):
        self._pass("☆", "☆")

    def test_heavy_check_mark_u2714_without_vs16(self):
        self._pass("✔", "✔")

    def test_copyright_u00a9_without_vs16(self):
        self._pass("©", "©")

    def test_registered_u00ae_without_vs16(self):
        self._pass("®", "®")

    def test_trademark_u2122_without_vs16(self):
        self._pass("™", "™")

    def test_eighth_note_u266a(self):
        self._pass("♪", "♪")

    def test_black_square_u25a0(self):
        self._pass("■", "■")

    def test_black_right_pointing_triangle_u25b6_without_vs16(self):
        self._pass("▶", "▶")

    def test_gear_u2699_without_vs16(self):
        self._pass("⚙", "⚙")

    def test_all_three_regression_symbols_together(self):
        """acceptance_checks[11] の原文どおり ★ ✔ © を同時に含む。"""
        html = clean_html(extra="<p>★ 重要 / ✔ 完了 / © 2026</p>")
        self.assertPassSilently(self.run_on(html), "acceptance_checks[11]")

    def test_japanese_punctuation_set(self):
        html = clean_html(
            extra="<p>まずはここから。触ってみる、そして「慣れる」。所要 〜30 分…〆</p>")
        self.assertPassSilently(self.run_on(html), "CR-EMOJI: 約物を殺さない")

    def test_variation_selector_1_to_15_pass(self):
        """U+FE00-U+FE0E は字形指定であって絵文字ではない。"""
        html = clean_html(extra="<p>✔︎ 完了</p>")
        self.assertPassSilently(self.run_on(html))

    def test_isolated_zwj_passes(self):
        html = clean_html(extra="<p>あ‍い</p>")
        self.assertPassSilently(self.run_on(html), "孤立 ZWJ は絵文字ではない")
