"""D1-external-url-attr と output_contract.block / .pass を固定する。

正本:
  - hook-brief-C10.json#detection_rules[0] (D1) — 規則本体は持たず CR-EXT へ委譲
  - script-brief-C16.json#canonical_rules.external_reference_rule (CR-EXT)

ここで固定するのは「C10 が対象ファイルを同定して exit code と stderr へ写像する」
部分だけである。どの参照が違反かの網羅は C16 側のテストが持つ。
"""

import re

from hb_c10 import (BLOCK_PREFIX, C10TestCase, D1, clean_html, external_html,
                    line_of)


class TestD1Block(C10TestCase):
    """acceptance_checks[5]: 外部 CDN の link を含むとき exit2 + stderr。"""

    def test_google_fonts_link_blocks(self):
        self.assertBlocked(self.run_on(external_html()), D1)

    def test_cdn_script_src_blocks(self):
        html = clean_html(head='<script src="https://cdn.jsdelivr.net/npm/x.js"></script>')
        self.assertBlocked(self.run_on(html), D1)

    def test_protocol_relative_img_blocks(self):
        html = clean_html(extra='<img src="//example.com/a.png" alt="図">')
        self.assertBlocked(self.run_on(html), D1)

    def test_external_anchor_href_blocks(self):
        html = clean_html(extra='<a href="http://example.com/doc">資料</a>')
        self.assertBlocked(self.run_on(html), D1)

    def test_css_import_blocks(self):
        html = clean_html(head='<style>@import url("https://example.com/a.css");</style>')
        self.assertBlocked(self.run_on(html), D1)

    def test_stderr_carries_line_number(self):
        """違反ごとに 1 行 (検出規則 id / 行番号 / 抜粋)。"""
        html = external_html()
        expected = line_of(html, "fonts.googleapis.com")
        res = self.run_on(html)
        self.assertBlocked(res, D1)
        hit = [l for l in res.err.splitlines() if D1 in l]
        self.assertTrue(hit, "D1 の違反行が無い\n{}".format(res))
        self.assertTrue(
            any(re.search(r"(?<!\d){}(?!\d)".format(expected), l) for l in hit),
            "stderr の D1 行に書込先ファイルの行番号 {} が出ていない\n{}".format(expected, res))

    def test_block_header_is_first_line(self):
        res = self.run_on(external_html())
        self.assertEqual(2, res.rc, str(res))
        self.assertTrue(res.err.startswith(BLOCK_PREFIX),
                        "stderr 先頭は BLOCKED 見出し\n{}".format(res))

    def test_evidence_is_truncated_to_120_chars(self):
        """抜粋は 120 文字以内。長大な属性値をそのまま吐かない。"""
        filler = "a" * 400
        html = clean_html(extra='<a href="https://example.com/{}">長い</a>'.format(filler))
        res = self.run_on(html)
        self.assertBlocked(res, D1)
        self.assertNotIn(filler, res.err,
                         "抜粋が 120 文字へ切り詰められていない\n{}".format(res))

    def test_two_violations_produce_two_lines(self):
        html = clean_html(
            head=('<link rel="stylesheet" href="https://fonts.example.com/a.css">\n'
                  '<script src="https://cdn.example.com/b.js"></script>'))
        res = self.run_on(html)
        self.assertBlocked(res, D1)
        self.assertGreaterEqual(len([l for l in res.err.splitlines() if D1 in l]), 2,
                                "違反ごとに 1 行出す契約\n{}".format(res))

    def test_no_stdout_on_block(self):
        """block は stderr 経路。stdout の systemMessage は打ち切り専用。"""
        res = self.run_on(external_html())
        self.assertEqual(2, res.rc, str(res))
        self.assertEqual("", res.out.strip(),
                         "違反時に stdout へ書くと打ち切りと区別できない\n{}".format(res))


class TestD1Pass(C10TestCase):
    """acceptance_checks[7][8]: 自己完結 HTML と text node の URL は素通し。"""

    def test_data_uri_and_page_anchor_only(self):
        html = clean_html(extra='<a href="#s1">1. 導入</a>')
        self.assertPassSilently(self.run_on(html), "acceptance_checks[7]")

    def test_text_node_url_is_not_a_violation(self):
        """CR-EXT: 取得を発生させない URL 文字列は違反ではない。"""
        html = clean_html(extra="<p>配布元は https://example.com です</p>")
        self.assertPassSilently(self.run_on(html), "acceptance_checks[8]")

    def test_text_node_url_in_list(self):
        html = clean_html(extra="<ul><li>http://portal.example.com</li></ul>")
        self.assertPassSilently(self.run_on(html))

    def test_svg_namespace_uri_is_not_a_violation(self):
        html = clean_html(
            extra='<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"></svg>')
        self.assertPassSilently(self.run_on(html), "CR-EXT: 名前空間 URI は参照ではない")

    def test_mailto_and_tel(self):
        html = clean_html(extra='<a href="mailto:x@example.com">連絡</a>'
                                '<a href="tel:0300000000">電話</a>')
        self.assertPassSilently(self.run_on(html))

    def test_empty_html_file(self):
        self.assertPassSilently(self.run_on(""))
