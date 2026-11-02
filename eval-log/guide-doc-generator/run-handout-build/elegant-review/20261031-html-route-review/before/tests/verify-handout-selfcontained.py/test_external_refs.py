"""SC-01..SC-04 / CR-EXT (外部参照判定の単一正本) を赤で固定する。

最重要の境界: 『取得 (fetch) を発生させる参照』だけが違反であり、
text node に現れる URL 文字列は違反ではない (CR-EXT statement)。
例外は <script>/<style> 本文中の http(s) リテラル (SC-02)。
"""

import unittest

from hb_c16 import BIG_DATA_URI, C16TestCase, good_html


class TestSC01Attributes(C16TestCase):
    """URL を取り得る属性の値が外部スキームを持たないこと。"""

    def test_cdn_script_src(self):
        self.assertDetectionFails(
            self.check(good_html(head='<script src="https://cdn.jsdelivr.net/npm/x.js"></script>')),
            "SC-01")

    def test_protocol_relative_img_src(self):
        self.assertDetectionFails(
            self.check(good_html(extra='<img src="//example.com/a.png" alt="a">')), "SC-01")

    def test_http_anchor_href(self):
        self.assertDetectionFails(
            self.check(good_html(extra='<a href="http://example.com/doc">資料</a>')), "SC-01")

    def test_ftp_scheme(self):
        self.assertDetectionFails(
            self.check(good_html(extra='<a href="ftp://example.com/f">f</a>')), "SC-01")

    def test_ws_scheme(self):
        self.assertDetectionFails(
            self.check(good_html(extra='<a href="ws://example.com/s">s</a>')), "SC-01")

    def test_wss_scheme(self):
        self.assertDetectionFails(
            self.check(good_html(extra='<a href="wss://example.com/s">s</a>')), "SC-01")

    def test_scheme_is_case_insensitive(self):
        self.assertDetectionFails(
            self.check(good_html(extra='<a href="HTTPS://Example.COM/x">x</a>')), "SC-01")

    def test_leading_whitespace_is_stripped_before_judging(self):
        self.assertDetectionFails(
            self.check(good_html(extra='<a href="   https://example.com/x">x</a>')), "SC-01")

    def test_srcset_candidate_is_judged_individually(self):
        snippet = ('<picture><source srcset="{d} 1x, https://cdn.example/a@2x.png 2x">'
                   '<img src="{d}" alt="a"></picture>'.format(d=BIG_DATA_URI))
        self.assertDetectionFails(self.check(good_html(extra=snippet)), "SC-01")

    def test_video_poster(self):
        self.assertDetectionFails(
            self.check(good_html(extra='<video poster="https://example.com/p.jpg"></video>')), "SC-01")

    def test_object_data(self):
        self.assertDetectionFails(
            self.check(good_html(extra='<object data="https://example.com/o.pdf"></object>')), "SC-01")

    def test_form_action(self):
        self.assertDetectionFails(
            self.check(good_html(extra='<form action="https://example.com/post"></form>')), "SC-01")

    def test_formaction(self):
        self.assertDetectionFails(
            self.check(good_html(extra='<button formaction="https://example.com/p">送信</button>')), "SC-01")

    def test_blockquote_cite(self):
        self.assertDetectionFails(
            self.check(good_html(extra='<blockquote cite="https://example.com/c">引用</blockquote>')), "SC-01")

    def test_body_background_attribute(self):
        self.assertDetectionFails(
            self.check(good_html(extra='<table background="https://example.com/bg.png"><tr><td>x</td></tr></table>')),
            "SC-01")

    def test_use_xlink_href_external_file(self):
        snippet = ('<svg data-hb-kind="decor" viewBox="0 0 24 24">'
                   '<use xlink:href="https://example.com/sprite.svg#ic"/></svg>')
        self.assertDetectionFails(self.check(good_html(extra=snippet)), "SC-01")

    def test_svg_image_href_external(self):
        snippet = ('<svg data-hb-kind="decor" viewBox="0 0 24 24">'
                   '<image href="https://example.com/a.png"/></svg>')
        self.assertDetectionFails(self.check(good_html(extra=snippet)), "SC-01")


class TestSC01NamespaceWhitelist(C16TestCase):
    """名前空間宣言だけが除外され、完全一致でのみ通る。"""

    def test_svg_namespace_passes(self):
        snippet = ('<svg data-hb-kind="decor" xmlns="http://www.w3.org/2000/svg" '
                   'viewBox="0 0 24 24"><path d="M0 0L1 1"/></svg>')
        self.assertAllPass(self.check(good_html(extra=snippet)))

    def test_xlink_namespace_passes(self):
        snippet = ('<svg data-hb-kind="decor" xmlns:xlink="http://www.w3.org/1999/xlink" '
                   'viewBox="0 0 24 24"><use xlink:href="#ic-check"/></svg>')
        self.assertAllPass(self.check(good_html(extra=snippet)))

    def test_xml_namespace_passes(self):
        snippet = ('<svg data-hb-kind="decor" xmlns:xml="http://www.w3.org/XML/1998/namespace" '
                   'viewBox="0 0 24 24"><path d="M0 0L1 1"/></svg>')
        self.assertAllPass(self.check(good_html(extra=snippet)))

    def test_whitelist_is_exact_match_not_prefix(self):
        snippet = '<svg data-hb-kind="decor" xmlns:evil="http://www.w3.org/2000/svg/evil.js" viewBox="0 0 24 24"><path d="M0 0L1 1"/></svg>'
        self.assertDetectionFails(self.check(good_html(extra=snippet)), "SC-01",
                                  msg="前方一致で通してはいけない")

    def test_xml_base_is_not_exempt(self):
        self.assertDetectionFails(
            self.check(good_html(extra='<div xml:base="http://evil.example/">x</div>')), "SC-01")

    def test_mathml_namespace_is_reported(self):
        """false_positive_risk として明記された挙動 (3 値以外は違反)。"""
        self.assertDetectionFails(
            self.check(good_html(extra='<math xmlns="http://www.w3.org/1998/Math/MathML"><mi>x</mi></math>')),
            "SC-01")


class TestTextNodeUrlBoundary(C16TestCase):
    """CR-EXT の核心境界: text node の URL 文字列は違反にしない。"""

    PLAIN = '<p class="f-sub">配布元は社内ポータル (https://portal.example.com) です</p>'

    def test_text_node_url_is_not_a_violation_at_all(self):
        self.assertAllPass(self.check(good_html(extra=self.PLAIN)),
                           msg="表示するだけの URL は取得を発生させないので違反ではない")

    def test_text_node_url_does_not_trip_sc01(self):
        self.assertDetectionPasses(self.check(good_html(extra=self.PLAIN)), "SC-01")

    def test_text_node_url_does_not_trip_sc02(self):
        self.assertDetectionPasses(self.check(good_html(extra=self.PLAIN)), "SC-02")

    def test_text_node_url_does_not_trip_sc03(self):
        self.assertDetectionPasses(self.check(good_html(extra=self.PLAIN)), "SC-03")

    def test_text_node_url_does_not_trip_sc04(self):
        self.assertDetectionPasses(self.check(good_html(extra=self.PLAIN)), "SC-04")

    def test_multiple_text_node_urls_still_pass(self):
        extra = ("<p>http://a.example と https://b.example/c?d=1 を参照</p>"
                 "<li>ftp://c.example/x</li>")
        self.assertAllPass(self.check(good_html(extra=extra)))

    def test_same_url_becomes_violation_once_linked(self):
        """リンク化した瞬間 href となり SC-01 が捕える (fail-closed 性は失われない)。"""
        self.assertDetectionFails(
            self.check(good_html(extra='<p><a href="https://portal.example.com">ポータル</a></p>')),
            "SC-01")

    def test_title_attribute_url_is_not_fetchable_but_alt_text_passes(self):
        """URL を取り得る属性以外 (alt/title) の URL 文字列は取得を発生させない。"""
        self.assertAllPass(
            self.check(good_html(extra='<img src="{}" alt="https://example.com の画面" '
                                       'title="https://example.com">'.format(BIG_DATA_URI))))


class TestSC02ScriptAndStyleLiterals(C16TestCase):
    """例外: <script>/<style> 本文中の http(s) リテラルはコメントでも違反。"""

    def test_url_in_js_comment(self):
        snippet = "<script>// 詳細は https://docs.example.com を参照\nconst a=1;</script>"
        self.assertDetectionFails(self.check(good_html(extra=snippet)), "SC-02")

    def test_url_in_js_string_literal(self):
        snippet = "<script>fetch('https://api.example.com/x')</script>"
        self.assertDetectionFails(self.check(good_html(extra=snippet)), "SC-02")

    def test_http_url_in_style_body(self):
        snippet = "<style>/* http://example.com のテーマ由来 */ .x{color:#000}</style>"
        self.assertDetectionFails(self.check(good_html(extra=snippet)), "SC-02")

    def test_clean_script_passes(self):
        snippet = "<script>'use strict';document.querySelectorAll('.tab').forEach(function(e){e.tabIndex=0;});</script>"
        self.assertAllPass(self.check(good_html(extra=snippet)))

    def test_data_uri_inside_script_passes(self):
        snippet = "<script>var ICON='data:image/svg+xml;base64,AAAA';</script>"
        self.assertAllPass(self.check(good_html(extra=snippet)))


class TestSC03AssetClosure(C16TestCase):
    """アセット参照が単一ファイル内に閉じていること。"""

    def test_relative_img_src(self):
        self.assertDetectionFails(
            self.check(good_html(extra='<img src="./assets/screenshot.png" alt="画面">')), "SC-03")

    def test_absolute_path_img_src(self):
        self.assertDetectionFails(
            self.check(good_html(extra='<img src="/assets/screenshot.png" alt="画面">')), "SC-03")

    def test_relative_source_srcset(self):
        self.assertDetectionFails(
            self.check(good_html(extra='<picture><source srcset="./a.png 1x"><img src="{}" alt="a"></picture>'.format(BIG_DATA_URI))),
            "SC-03")

    def test_relative_video_poster(self):
        self.assertDetectionFails(
            self.check(good_html(extra='<video poster="./p.jpg"></video>')), "SC-03")

    def test_relative_object_data(self):
        self.assertDetectionFails(
            self.check(good_html(extra='<object data="./o.pdf"></object>')), "SC-03")

    def test_relative_embed_src(self):
        self.assertDetectionFails(
            self.check(good_html(extra='<embed src="./e.svg">')), "SC-03")

    def test_relative_anchor_href(self):
        self.assertDetectionFails(
            self.check(good_html(extra='<a href="../material/sheet.xlsx" download>DL</a>')), "SC-03")

    def test_fragment_anchor_passes(self):
        self.assertAllPass(self.check(good_html(extra='<a href="#s3">3 章へ</a>')))

    def test_mailto_anchor_passes(self):
        self.assertAllPass(self.check(good_html(extra='<a href="mailto:x@example.com">連絡</a>')))

    def test_tel_anchor_passes(self):
        self.assertAllPass(self.check(good_html(extra='<a href="tel:0312345678">電話</a>')))

    def test_data_uri_anchor_passes(self):
        self.assertAllPass(self.check(
            good_html(extra='<a class="dl-btn" href="data:application/zip;base64,UEsDBA==" download="m.zip">DL</a>')))

    def test_data_uri_img_passes(self):
        self.assertAllPass(self.check(good_html(extra='<img src="{}" alt="画面">'.format(BIG_DATA_URI))))

    def test_empty_href_is_reported(self):
        self.assertDetectionFails(self.check(good_html(extra='<a href="">空</a>')), "SC-03")


class TestSC04FontsAndStylesheets(C16TestCase):
    """外部フォント・外部スタイルシートの取得経路が存在しないこと。"""

    def test_link_rel_stylesheet_even_with_data_href(self):
        self.assertDetectionFails(
            self.check(good_html(head='<link rel="stylesheet" href="data:text/css,body{}">')),
            "SC-04", msg="href の値によらず rel=stylesheet は外部取得を前提とする指示")

    def test_link_rel_preconnect(self):
        self.assertDetectionFails(
            self.check(good_html(head='<link rel="preconnect" href="https://fonts.gstatic.com">')), "SC-04")

    def test_link_rel_dns_prefetch(self):
        self.assertDetectionFails(
            self.check(good_html(head='<link rel="dns-prefetch" href="https://fonts.gstatic.com">')), "SC-04")

    def test_link_rel_preload(self):
        self.assertDetectionFails(
            self.check(good_html(head='<link rel="preload" as="font" href="data:font/woff2,">')), "SC-04")

    def test_link_rel_prefetch(self):
        self.assertDetectionFails(
            self.check(good_html(head='<link rel="prefetch" href="data:text/css,">')), "SC-04")

    def test_link_rel_modulepreload(self):
        self.assertDetectionFails(
            self.check(good_html(head='<link rel="modulepreload" href="data:text/javascript,">')), "SC-04")

    def test_link_rel_icon_passes(self):
        self.assertAllPass(self.check(good_html(head='<link rel="icon" href="data:image/svg+xml,%3Csvg/%3E">')))

    def test_link_rel_canonical_is_out_of_sc04_scope(self):
        """SC-04 の rel 6 種に含まれないので SC-04 は PASS。

        取得経路としての疑いは SC-10 (c) が引き受ける (test_sc10_bundle_closure)。
        """
        self.assertDetectionPasses(
            self.check(good_html(head='<link rel="canonical" href="#s1">')), "SC-04")

    def test_at_import_is_always_violation(self):
        self.assertDetectionFails(
            self.check(good_html(head='<style>@import url(data:text/css,body{});</style>')),
            "SC-04", msg="@import は値によらず違反")

    def test_font_face_remote_src(self):
        snippet = '<style>@font-face{font-family:X;src:url(https://fonts.gstatic.com/a.woff2)}</style>'
        self.assertDetectionFails(self.check(good_html(head=snippet)), "SC-04")

    def test_font_face_relative_src(self):
        snippet = '<style>@font-face{font-family:X;src:url(./a.woff2)}</style>'
        self.assertDetectionFails(self.check(good_html(head=snippet)), "SC-04")

    def test_font_face_local_is_violation(self):
        snippet = '<style>@font-face{font-family:X;src:local("Hiragino Sans")}</style>'
        self.assertDetectionFails(self.check(good_html(head=snippet)), "SC-04",
                                  msg="端末フォント依存は機種差を生むので違反")

    def test_font_face_data_uri_src_passes(self):
        snippet = '<style>@font-face{font-family:X;src:url(data:font/woff2;base64,AAAA) format("woff2")}</style>'
        self.assertAllPass(self.check(good_html(head=snippet)))

    def test_font_family_fallback_list_passes(self):
        snippet = '<style>.b{font-family:system-ui,"Hiragino Sans","Noto Sans JP",sans-serif}</style>'
        self.assertAllPass(self.check(good_html(head=snippet)))

    def test_css_url_double_quoted(self):
        self.assertAnyDetectionFails(
            self.check(good_html(head='<style>.a{background:url("./bg.png")}</style>')),
            ["SC-04", "SC-10"])

    def test_css_url_single_quoted(self):
        self.assertAnyDetectionFails(
            self.check(good_html(head="<style>.a{background:url('./bg.png')}</style>")),
            ["SC-04", "SC-10"])

    def test_css_url_unquoted(self):
        self.assertAnyDetectionFails(
            self.check(good_html(head='<style>.a{background:url(./bg.png)}</style>')),
            ["SC-04", "SC-10"])

    def test_css_url_data_uri_passes(self):
        self.assertAllPass(
            self.check(good_html(head='<style>.a{background:url(data:image/svg+xml,%3Csvg/%3E)}</style>')))


class TestAcC16_02(C16TestCase):
    """AC-C16-02: CDN script 1 本 + Google Fonts link 1 本。"""

    HTML = good_html(head=('<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>\n'
                           '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP">'))

    def test_exit_one(self):
        self.assertEqual(1, self.check(self.HTML).rc)

    def test_sc01_violation_present(self):
        self.assertDetectionFails(self.check(self.HTML), "SC-01")

    def test_sc04_violation_present(self):
        self.assertDetectionFails(self.check(self.HTML), "SC-04")

    def test_violations_carry_line_numbers(self):
        res = self.check(self.HTML)
        for det in ("SC-01", "SC-04"):
            for row in res.violations(det):
                self.assertGreater(int(row["pos"].split(":")[0]), 0, row)


if __name__ == "__main__":
    unittest.main()
