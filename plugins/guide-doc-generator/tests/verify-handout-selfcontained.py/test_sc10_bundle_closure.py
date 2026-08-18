"""SC-10 (同梱閉包の包括規則) を赤で固定する。

SC-01..SC-04 の残余を塞ぐ。SC-01 は外部スキームしか見ず、SC-03 の対象属性列挙は
script@src を含まず、SC-04 は <link> と <style> 内の @import / @font-face しか見ない。
その結果 `<script src="./app.js">` や `<iframe src>` が全検査を通過してしまう。

SC-10 の考え方は **スキームの有無ではなく「data: であるか否か」** で判定すること。
利用者要件は「JS も CSS も画像も 1 つの HTML に入れ、デプロイするだけで完結する」。

境界は SC-02 が確定させたものを踏襲する:
**text node に現れる URL 文字列は違反にしない**。SC-10 も属性値と CSS 値のみを見る。

注意: SC-10 は script-brief-C16.json に未反映 (README の gaps 参照)。
実装より先にブリーフへ detections / stdout の 10 行 / CR-EXT の
implemented_by_detections を追記すること。
"""

import unittest

from hb_c16 import BIG_DATA_URI, C16TestCase, good_html


class TestSC10ScriptSrc(C16TestCase):
    """(a) <script> が src を持てば値によらず違反。JS はインライン本文で持つ。"""

    def test_relative_script_src_fails(self):
        self.assertDetectionFails(
            self.check(good_html(extra='<script src="./app.js"></script>')), "SC-10")

    def test_absolute_path_script_src_fails(self):
        self.assertDetectionFails(
            self.check(good_html(extra='<script src="/static/app.js"></script>')), "SC-10")

    def test_parent_relative_script_src_fails(self):
        self.assertDetectionFails(
            self.check(good_html(extra='<script src="../lib/app.js"></script>')), "SC-10")

    def test_https_script_src_also_fails_sc10(self):
        """SC-01 と二重に報告されてよい (同一規則の別断面ではなく別 detection)。"""
        res = self.check(good_html(extra='<script src="https://cdn.example/a.js"></script>'))
        self.assertDetectionFails(res, "SC-10")
        self.assertDetectionFails(res, "SC-01")

    def test_data_uri_script_src_fails(self):
        """src を持つこと自体が違反 (値によらず)。"""
        self.assertDetectionFails(
            self.check(good_html(extra='<script src="data:text/javascript,var a=1"></script>')),
            "SC-10")

    def test_module_type_script_src_fails(self):
        self.assertDetectionFails(
            self.check(good_html(extra='<script type="module" src="./app.mjs"></script>')), "SC-10")

    def test_inline_script_passes(self):
        self.assertAllPass(self.check(good_html(extra="<script>var a = 1;</script>")),
                           msg="インライン <script> 本文は同梱されている")

    def test_inline_module_script_passes(self):
        self.assertAllPass(self.check(
            good_html(extra='<script type="module">const a = 1;</script>')))

    def test_inline_json_script_passes(self):
        self.assertAllPass(self.check(
            good_html(extra='<script type="application/json">{"a":1}</script>')))


class TestSC10Frames(C16TestCase):
    """(b) iframe / frame / portal は存在自体が違反。"""

    def test_iframe_with_src_fails(self):
        self.assertDetectionFails(
            self.check(good_html(extra='<iframe src="./inner.html"></iframe>')), "SC-10")

    def test_iframe_with_remote_src_fails(self):
        self.assertDetectionFails(
            self.check(good_html(extra='<iframe src="https://example.com/e"></iframe>')), "SC-10")

    def test_bare_iframe_fails(self):
        """src が無くとも要素の存在自体が違反。"""
        self.assertDetectionFails(self.check(good_html(extra="<iframe></iframe>")), "SC-10")

    def test_frame_fails(self):
        self.assertDetectionFails(
            self.check(good_html(extra='<frame src="./inner.html">')), "SC-10")

    def test_portal_fails(self):
        self.assertDetectionFails(
            self.check(good_html(extra='<portal src="./inner.html"></portal>')), "SC-10")

    def test_figure_element_is_not_a_frame(self):
        """<figure> は <frame> ではない (前方一致で判定しないこと)。"""
        snippet = ('<figure data-hb-part="DIAGRAM"><svg data-hb-kind="decor" viewBox="0 0 40 40">'
                   '<rect x="1" y="1" width="9" height="9"/></svg><figcaption>図</figcaption></figure>')
        self.assertAllPass(self.check(good_html(extra=snippet)))

    def test_frameset_is_not_matched_as_frame(self):
        """<frameset> 単体の扱いはブリーフ未定義。frame の前方一致で拾わないことだけ固定する。"""
        self.assertDetectionPasses(
            self.check(good_html(extra="<frameset></frameset>")), "SC-10")

    def test_two_frames_counted_separately(self):
        self.assertDetectionFails(
            self.check(good_html(extra="<iframe></iframe><iframe></iframe>")), "SC-10", count=2)


class TestSC10LinkElement(C16TestCase):
    """(c) <link> は rel によらず href が data: 以外なら違反。"""

    def test_rel_icon_relative_href_fails(self):
        self.assertDetectionFails(
            self.check(good_html(head='<link rel="icon" href="./favicon.ico">')), "SC-10")

    def test_rel_icon_data_uri_passes(self):
        self.assertAllPass(
            self.check(good_html(head='<link rel="icon" href="data:image/svg+xml,%3Csvg/%3E">')))

    def test_rel_canonical_fragment_href_fails(self):
        """SC-04 の rel 6 種には含まれないが SC-10 が捕える。"""
        res = self.check(good_html(head='<link rel="canonical" href="#s1">'))
        self.assertDetectionFails(res, "SC-10")
        self.assertDetectionPasses(res, "SC-04")

    def test_rel_manifest_fails(self):
        self.assertDetectionFails(
            self.check(good_html(head='<link rel="manifest" href="./app.webmanifest">')), "SC-10")

    def test_rel_alternate_remote_fails(self):
        self.assertDetectionFails(
            self.check(good_html(head='<link rel="alternate" href="https://example.com/feed">')),
            "SC-10")

    def test_link_without_href_fails(self):
        self.assertDetectionFails(
            self.check(good_html(head='<link rel="preload" as="font">')), "SC-10")


class TestSC10CssUrl(C16TestCase):
    """(d) CSS の url() が data: 以外を指せば違反 (@font-face に限らない)。"""

    def test_background_image_relative_url_fails(self):
        self.assertDetectionFails(
            self.check(good_html(head='<style>.hero{background-image:url(./bg.png)}</style>')),
            "SC-10")

    def test_background_image_remote_url_fails(self):
        self.assertDetectionFails(
            self.check(good_html(head='<style>.hero{background-image:url(https://x.example/bg.png)}</style>')),
            "SC-10")

    def test_list_style_image_relative_url_fails(self):
        self.assertDetectionFails(
            self.check(good_html(head='<style>li{list-style-image:url("./dot.svg")}</style>')),
            "SC-10")

    def test_mask_image_relative_url_fails(self):
        self.assertDetectionFails(
            self.check(good_html(head="<style>.m{mask-image:url('./mask.svg')}</style>")), "SC-10")

    def test_cursor_relative_url_fails(self):
        self.assertDetectionFails(
            self.check(good_html(head='<style>.c{cursor:url(./c.cur),auto}</style>')), "SC-10")

    def test_inline_style_attribute_url_fails(self):
        self.assertDetectionFails(
            self.check(good_html(extra='<div style="background:url(./bg.png)">x</div>')), "SC-10")

    def test_data_uri_background_passes(self):
        self.assertAllPass(self.check(
            good_html(head='<style>.hero{background-image:url(data:image/svg+xml,%3Csvg/%3E)}</style>')))

    def test_inline_style_element_passes(self):
        self.assertAllPass(self.check(
            good_html(head="<style>.hero{background:linear-gradient(#fff,#eee)}</style>")))


class TestSC10DataUriIsTheOnlyPredicate(C16TestCase):
    """(e) スキームの有無ではなく data: か否かで判定する。"""

    def test_relative_use_href_fails(self):
        """SC-03 の属性列挙にも SC-01 のスキーム判定にも掛からない残余。"""
        snippet = '<svg data-hb-kind="decor" viewBox="0 0 24 24"><use href="./sprite.svg#ic"/></svg>'
        self.assertDetectionFails(self.check(good_html(extra=snippet)), "SC-10")

    def test_relative_svg_image_href_fails(self):
        snippet = '<svg data-hb-kind="decor" viewBox="0 0 24 24"><image href="./a.png"/></svg>'
        self.assertDetectionFails(self.check(good_html(extra=snippet)), "SC-10")

    def test_data_uri_img_passes(self):
        self.assertAllPass(self.check(good_html(extra='<img src="{}" alt="図">'.format(BIG_DATA_URI))))

    def test_fragment_anchor_passes(self):
        self.assertAllPass(self.check(good_html(extra='<a href="#s1">1 章へ</a>')))

    def test_mailto_anchor_passes(self):
        self.assertAllPass(self.check(good_html(extra='<a href="mailto:x@example.com">連絡</a>')))

    def test_tel_anchor_passes(self):
        self.assertAllPass(self.check(good_html(extra='<a href="tel:0312345678">電話</a>')))

    def test_data_uri_anchor_passes(self):
        self.assertAllPass(self.check(
            good_html(extra='<a href="data:application/zip;base64,UEsDBA==" download="m.zip">DL</a>')))


class TestSC10TextNodeBoundaryPreserved(C16TestCase):
    """SC-02 が確定させた境界を SC-10 が壊さないこと。"""

    def test_text_node_url_is_not_sc10_violation(self):
        html = good_html(extra='<p>配布元は https://portal.example.com です</p>')
        self.assertDetectionPasses(self.check(html), "SC-10")

    def test_text_node_relative_path_is_not_sc10_violation(self):
        html = good_html(extra="<p>素材は ./assets/ に同梱しています</p>")
        self.assertAllPass(self.check(html))

    def test_script_src_written_as_text_is_not_a_violation(self):
        """コード例として画面に出す文字列は取得を発生させない。"""
        html = good_html(extra="<pre><code>&lt;script src=&quot;./app.js&quot;&gt;&lt;/script&gt;</code></pre>")
        self.assertDetectionPasses(self.check(html), "SC-10")

    def test_alt_attribute_path_is_not_fetchable(self):
        html = good_html(extra='<img src="{}" alt="./assets/a.png の画面">'.format(BIG_DATA_URI))
        self.assertAllPass(self.check(html))


class TestSC10Reporting(C16TestCase):
    """SC-10 も他 detection と同じ出力契約に乗ること。"""

    HTML = good_html(extra='<script src="./app.js"></script><iframe src="./inner.html"></iframe>')

    def test_exit_one(self):
        self.assertEqual(1, self.check(self.HTML).rc)

    def test_summary_line_present(self):
        self.assertIn("SC-10", self.check(self.HTML).summary())

    def test_summary_line_is_last_in_fixed_order(self):
        self.assertEqual("SC-10", self.check(self.HTML).summary_order()[-1])

    def test_two_violations(self):
        self.assertDetectionFails(self.check(self.HTML), "SC-10", count=2)

    def test_violations_have_line_numbers(self):
        for row in self.check(self.HTML).violations("SC-10"):
            self.assertGreater(int(row["pos"].split(":")[0]), 0, row)

    def test_report_contains_sc10_detection(self):
        _, rep = self.report_for(self.HTML)
        ids = [d["id"] for d in rep["detections"]]
        self.assertIn("SC-10", ids)

    def test_report_sc10_violations_listed(self):
        _, rep = self.report_for(self.HTML)
        sc10 = [d for d in rep["detections"] if d["id"] == "SC-10"][0]
        self.assertEqual(2, len(sc10["violations"]))

    def test_baseline_document_passes_sc10(self):
        self.assertDetectionPasses(self.check(good_html()), "SC-10")


class TestSC10ModuleApi(C16TestCase):
    """SC-10 は CR-EXT の一部なので scan_external_references が返すこと。"""

    def test_scan_returns_script_src_violation(self):
        from hb_c16 import load_hb
        rows = list(load_hb().scan_external_references('<script src="./app.js"></script>'))
        self.assertTrue(rows, "SC-10 も module_api 経由で C10 / C11 へ届く必要がある")

    def test_scan_returns_iframe_violation(self):
        from hb_c16 import load_hb
        self.assertTrue(list(load_hb().scan_external_references('<iframe src="./x.html"></iframe>')))

    def test_scan_ignores_inline_script(self):
        from hb_c16 import load_hb
        self.assertEqual([], list(load_hb().scan_external_references("<script>var a=1;</script>")))

    def test_scan_ignores_text_node_url(self):
        from hb_c16 import load_hb
        self.assertEqual([], list(load_hb().scan_external_references("<p>./app.js を同梱</p>")))


if __name__ == "__main__":
    unittest.main()
