# -*- coding: utf-8 -*-
"""図解密度と散文量の検査 (W-VISUAL-ABSENT / W-DIAGRAM-FEW / E-IMAGE-ABSENT /
W-TEXT-HEAVY / W-TEXT-RUN)。

判定基準の出所は config/handout-visual-policy.json (閾値の正本) である。
本テストは閾値そのものを固定値で書かず、正本を書き換えて挙動が追従することを
検査する。script 側へ閾値が埋め戻された場合、その回帰をここが捕まえる。

重大度も接頭辞 (E-/W-) からは決めない。正本の各閾値が持つ level フィールドが
唯一の正本であり、level:"error" を宣言した code は W- 接頭辞でも完了を止める。
R25 で図解と画像は main セクション 1 個あたりそれぞれ 1 件以上の error 下限に
なったため (improvement/visual-per-section-decision.json)、W-DIAGRAM-FEW と
E-IMAGE-ABSENT は exit=1 を伴う。W-VISUAL-ABSENT / W-TEXT-HEAVY / W-TEXT-RUN は
warning のままで exit=0。
"""

import json
import unittest

from _harness import C12TestCase, asset, image_part, section, text_part, valid_config

VISUAL_POLICY_RELPATH = "config/handout-visual-policy.json"


def diagram(diagram_id="overview"):
    """concept 図解 1 枚 (C14 の flow パターン)。形の検査は C14 の担当。"""
    return {
        "id": diagram_id,
        "pattern": "flow",
        "title": "受注から加工予定までの流れ",
        "data": {"steps": [{"label": "受注"}, {"label": "加工予定"}]},
    }


def diagram_part(part_id, diagram_id="overview"):
    return {"part": "DIAGRAM", "id": part_id, "data": {"diagram_id": diagram_id}}


def table_part(part_id):
    """視覚部品として数えられる表 (B05 は列 2 件以上が必要)。"""
    return {
        "part": "B05",
        "id": part_id,
        "data": {
            "columns": ["項目", "内容"],
            "rows": [
                {"header": "受注", "cells": ["受注", "前日までに確定する"]},
                {"header": "加工", "cells": ["加工", "当日の朝に確定する"]},
            ],
        },
    }


class VisualDensityTestBase(C12TestCase):

    def visual_policy(self):
        path = self.root / VISUAL_POLICY_RELPATH
        self.assertTrue(path.exists(), "図解方針の正本が無い: %s" % path)
        return json.loads(path.read_text(encoding="utf-8"))

    def patch_visual_policy(self, **thresholds):
        """閾値正本を書き換える (script に閾値が埋まっていないことの回帰用)。

        キーは thresholds 直下の名前、値は差し込む value。
        """
        path = self.root / VISUAL_POLICY_RELPATH
        policy = self.visual_policy()
        for name, value in thresholds.items():
            policy.setdefault("thresholds", {}).setdefault(name, {})["value"] = value
        path.write_text(json.dumps(policy, ensure_ascii=False, indent=2), encoding="utf-8")

    def patch_visual_part_ids(self, ids):
        path = self.root / VISUAL_POLICY_RELPATH
        policy = self.visual_policy()
        policy["visual_parts"]["ids"] = ids
        path.write_text(json.dumps(policy, ensure_ascii=False, indent=2), encoding="utf-8")

    def visual_ok_config(self, **over):
        """図解密度の指摘が 1 件も出ない構成データ。

        main 2 セクションのそれぞれが概念図解 1 枚と画像 1 枚を持つ
        (R25 の per-section 下限)。判定単位は資料全体の総量比ではなく main
        セクション 1 個であり、枚数を資料全体で足し合わせても下限は満たせない。
        部品 4 件のうち TEXT は 1 件 (上限比率を超えない)。
        """
        cfg = valid_config(
            diagrams=[diagram(), diagram("detail")],
            assets=[asset("intro-shot", role="screenshot"),
                    asset("practice-shot", role="screenshot")],
            sections=[
                section("intro", parts=[diagram_part("intro-d1"),
                                        image_part("intro-i1", "intro-shot"),
                                        table_part("intro-b1"),
                                        text_part("intro-t1")]),
                section("practice", id="practice",
                        parts=[diagram_part("practice-d1", "detail"),
                               image_part("practice-i1", "practice-shot"),
                               table_part("practice-b1"),
                               text_part("practice-t1")]),
            ],
        )
        cfg.update(over)
        return cfg


class TestVisualDensityBaseline(VisualDensityTestBase):
    """警告が出ない状態を先に固定する (以降のテストの対照)。"""

    def test_visual_rich_config_emits_no_density_warning(self):
        res, _ = self.validate(self.visual_ok_config())
        self.assert_exit(res, 0)
        for code in ("W-VISUAL-ABSENT", "W-DIAGRAM-FEW", "W-TEXT-HEAVY", "W-TEXT-RUN"):
            self.assert_no_diag(res, code)


class TestVisualAbsent(VisualDensityTestBase):
    """W-VISUAL-ABSENT: 本文だけの main セクションを見つける。"""

    def test_text_only_main_section_warns(self):
        """本文だけの節には W-VISUAL-ABSENT が当たる。

        exit=1 になるのはこの警告のせいではなく、同じ節が図解と画像も欠く
        ためである (R25 の 2 つの error 下限)。W-VISUAL-ABSENT 自身は warning。
        """
        cfg = self.visual_ok_config()
        cfg["sections"][1]["parts"] = [text_part("practice-t1")]
        res, _ = self.validate(cfg)
        self.assert_diag(res, "W-VISUAL-ABSENT", "/sections/1/parts")

    def test_visual_absent_alone_does_not_stop_completion(self):
        """W-VISUAL-ABSENT が単独で出る状況を作り、exit=0 のままだと確かめる。

        視覚部品の下限だけを 4 件へ上げる。図解 1・画像 1 の下限は満たしたまま
        なので、鳴るのは W-VISUAL-ABSENT だけになる。この分離をしておかないと
        「exit=1 だから警告も完了を止めている」と読み違える余地が残る。
        """
        cfg = self.visual_ok_config()
        self.patch_visual_policy(min_visual_parts_per_main_section=4)
        res, _ = self.validate(cfg)
        self.assert_diag(res, "W-VISUAL-ABSENT", "/sections/0/parts")
        self.assert_exit(res, 0)

    def test_appendix_section_is_exempt(self):
        """付録は読み飛ばされてよい節であり、図解の下限を当てない。"""
        cfg = self.visual_ok_config()
        cfg["sections"][1]["parts"] = [text_part("practice-t1")]
        cfg["sections"][1]["role"] = "appendix"
        cfg["sections"][1]["ties_to"] = []
        res, _ = self.validate(cfg)
        self.assert_no_diag(res, "W-VISUAL-ABSENT")

    def test_threshold_comes_from_canon_not_script(self):
        """下限を 4 件へ上げると、視覚部品 3 件のセクションが新たに警告される。

        3 件は DIAGRAM・IMG・B05 で、TEXT は視覚部品に数えない。
        """
        cfg = self.visual_ok_config()
        self.patch_visual_policy(min_visual_parts_per_main_section=4)
        res, _ = self.validate(cfg)
        self.assert_diag(res, "W-VISUAL-ABSENT", "/sections/0/parts")

    def test_visual_part_ids_come_from_canon(self):
        """B05 を視覚部品の集合から外すと、表だけのセクションが警告される。"""
        cfg = self.visual_ok_config()
        cfg["sections"][1]["parts"] = [table_part("practice-b1"),
                                       table_part("practice-b2"),
                                       text_part("practice-t1")]
        self.patch_visual_part_ids(["DIAGRAM", "IMG"])
        res, _ = self.validate(cfg)
        self.assert_diag(res, "W-VISUAL-ABSENT", "/sections/1/parts")


class TestDiagramFew(VisualDensityTestBase):
    """W-DIAGRAM-FEW: 全体の関係を示す概念図解を main セクションごとに見る。

    出荷時の下限は 0 である (利用者指定 2026-08-19: SVG 図解は挿絵と重複する
    ため画像だけでよい)。よって「図解を欠いた節が落ちる」ことは既定では起きず、
    下限を 1 へ上げたときに節単位で効くことをここでは固定する。既定値そのものは
    test_shipped_default_is_zero が持つ。
    """

    def test_shipped_default_is_zero(self):
        """出荷時は図解を要求しない (挿絵が節の顔を担う)。"""
        self.assertEqual(
            self.visual_policy()["thresholds"]["min_diagrams_per_main_section"]["value"],
            0,
        )

    def test_section_without_diagram_fails(self):
        """図解を欠いた節が名指しで落ちる。指摘先は /diagrams でなくその節。"""
        cfg = self.visual_ok_config()
        self.patch_visual_policy(min_diagrams_per_main_section=1)
        cfg["sections"][1]["parts"] = [image_part("practice-i1", "practice-shot"),
                                       table_part("practice-b1"),
                                       text_part("practice-t1")]
        res, _ = self.validate(cfg)
        self.assert_fails_with(res, "W-DIAGRAM-FEW", "/sections/1/parts")

    def test_other_sections_diagrams_do_not_cover_a_bare_section(self):
        """総量では足りていても、欠けた節は救われない。

        判定単位が資料全体の総量比だった頃はこの構成が通っていた。節を単位に
        したことの回帰はここが捕まえる (図解 3 枚 / main 2 節でも 1 節が 0 枚)。
        """
        cfg = self.visual_ok_config()
        self.patch_visual_policy(min_diagrams_per_main_section=1)
        cfg["sections"][0]["parts"] = [diagram_part("intro-d1"),
                                       diagram_part("intro-d2", "detail"),
                                       diagram_part("intro-d3"),
                                       image_part("intro-i1", "intro-shot"),
                                       text_part("intro-t1")]
        cfg["sections"][1]["parts"] = [image_part("practice-i1", "practice-shot"),
                                       table_part("practice-b1"),
                                       text_part("practice-t1")]
        res, _ = self.validate(cfg)
        self.assert_fails_with(res, "W-DIAGRAM-FEW", "/sections/1/parts")
        self.assertFalse(
            [l for l in res.stderr.splitlines()
             if l.startswith("W-DIAGRAM-FEW") and "/sections/0/" in l],
            "図解 3 枚の節まで指摘されている: %r" % res.stderr,
        )

    def test_one_diagram_per_section_is_enough(self):
        res, _ = self.validate(self.visual_ok_config())
        self.assert_exit(res, 0)
        self.assert_no_diag(res, "W-DIAGRAM-FEW")

    def test_threshold_comes_from_canon_not_script(self):
        """下限を 2 枚へ上げると、1 枚しか持たない節が新たに落ちる。"""
        cfg = self.visual_ok_config()
        self.patch_visual_policy(min_diagrams_per_main_section=2)
        res, _ = self.validate(cfg)
        self.assert_diag(res, "W-DIAGRAM-FEW", "/sections/0/parts")


class TestImageAbsent(VisualDensityTestBase):
    """E-IMAGE-ABSENT: 画像を main セクションごとに見る。

    図解が構造を示すのに対し、画像は実物・画面・場面を見せる別の役割を持つ。
    どちらか一方では節の顔にならないので、両方を独立に数える。
    """

    def test_section_without_image_fails(self):
        cfg = self.visual_ok_config()
        cfg["sections"][1]["parts"] = [diagram_part("practice-d1", "detail"),
                                       table_part("practice-b1"),
                                       text_part("practice-t1")]
        res, _ = self.validate(cfg)
        self.assert_fails_with(res, "E-IMAGE-ABSENT", "/sections/1/parts")

    def test_diagram_does_not_substitute_for_an_image(self):
        """図解を何枚積んでも画像の代わりにはならない。"""
        cfg = self.visual_ok_config()
        cfg["sections"][1]["parts"] = [diagram_part("practice-d1", "detail"),
                                       diagram_part("practice-d2"),
                                       diagram_part("practice-d3", "detail"),
                                       text_part("practice-t1")]
        res, _ = self.validate(cfg)
        self.assert_fails_with(res, "E-IMAGE-ABSENT", "/sections/1/parts")

    def test_one_image_per_section_is_enough(self):
        res, _ = self.validate(self.visual_ok_config())
        self.assert_exit(res, 0)
        self.assert_no_diag(res, "E-IMAGE-ABSENT")

    def test_threshold_comes_from_canon_not_script(self):
        cfg = self.visual_ok_config()
        self.patch_visual_policy(min_images_per_main_section=2)
        res, _ = self.validate(cfg)
        self.assert_diag(res, "E-IMAGE-ABSENT", "/sections/0/parts")


class TestSeverityIsDeclaredNotInferred(VisualDensityTestBase):
    """重大度は接頭辞 (E-/W-) から推測しない。

    W-DIAGRAM-FEW は W- 接頭辞のまま error 扱いで完了を止める。接頭辞を根拠に
    した実装へ戻すと、ここが赤くなる。

    ただし level は「昇格だけができる」片方向の口である。script 側は
    FALLBACK_ERROR_CODES を下限として持ち、正本の level:"error" 宣言はそこへ
    足されるだけで、level:"warning" への書き換えでは外れない (方針ファイルを
    書き換えてゲートを緩める逃げ道を塞ぐため)。この非対称は意図であって
    実装漏れではないので、両方向を明示的に固定しておく。
    """

    def patch_level(self, name, level):
        path = self.root / VISUAL_POLICY_RELPATH
        policy = self.visual_policy()
        policy["thresholds"][name]["level"] = level
        path.write_text(json.dumps(policy, ensure_ascii=False, indent=2), encoding="utf-8")

    def bare_diagram_config(self):
        # 出荷時の図解下限は 0 なので、重大度の検査に必要な違反を作るために
        # 下限だけを 1 へ戻す (見るのは level の扱いであって既定値ではない)。
        cfg = self.visual_ok_config()
        self.patch_visual_policy(min_diagrams_per_main_section=1)
        cfg["sections"][1]["parts"] = [image_part("practice-i1", "practice-shot"),
                                       table_part("practice-b1"),
                                       text_part("practice-t1")]
        return cfg

    def test_w_prefixed_code_stops_completion(self):
        res, _ = self.validate(self.bare_diagram_config())
        self.assert_fails_with(res, "W-DIAGRAM-FEW")

    def test_downgrading_the_level_in_canon_does_not_loosen_the_gate(self):
        """正本を warning へ書き換えても error のまま止まる (昇格のみの片方向)。"""
        self.patch_level("min_diagrams_per_main_section", "warning")
        res, _ = self.validate(self.bare_diagram_config())
        self.assert_fails_with(res, "W-DIAGRAM-FEW")

    def test_promoting_a_warning_in_canon_stops_completion(self):
        """逆向きは効く。warning だった code に level:"error" を宣言すると止まる。"""
        cfg = self.visual_ok_config()
        self.patch_visual_policy(min_visual_parts_per_main_section=4)
        self.patch_level("min_visual_parts_per_main_section", "error")
        res, _ = self.validate(cfg)
        self.assert_fails_with(res, "W-VISUAL-ABSENT", "/sections/0/parts")


class TestTextHeavy(VisualDensityTestBase):
    """W-TEXT-HEAVY: セクションが実質的に文章の塊になっていないか。"""

    def test_majority_text_warns(self):
        cfg = self.visual_ok_config()
        cfg["sections"][0]["parts"] = [
            diagram_part("intro-d1"),
            image_part("intro-i1", "intro-shot"),
            text_part("intro-t1"),
            table_part("intro-b1"),
            text_part("intro-t2"),
            text_part("intro-t3"),
        ]
        res, _ = self.validate(cfg)
        self.assert_exit(res, 0)
        self.assert_diag(res, "W-TEXT-HEAVY", "/sections/0/parts")

    def test_ratio_at_limit_is_allowed(self):
        """上限比率は『超えたら』警告であり、部品 3 件中 TEXT 1 件 (0.33) は許す。"""
        cfg = self.visual_ok_config()
        cfg["sections"][0]["parts"] = [
            diagram_part("intro-d1"),
            image_part("intro-i1", "intro-shot"),
            text_part("intro-t1"),
        ]
        res, _ = self.validate(cfg)
        self.assert_no_diag(res, "W-TEXT-HEAVY")

    def test_ratio_comes_from_canon_not_script(self):
        cfg = self.visual_ok_config()
        self.patch_visual_policy(max_text_parts_ratio_per_section=0.2)
        res, _ = self.validate(cfg)
        self.assert_diag(res, "W-TEXT-HEAVY", "/sections/0/parts")


class TestTextRun(VisualDensityTestBase):
    """W-TEXT-RUN: 画面上で 1 つの長文に見える TEXT の連続。"""

    def test_consecutive_text_warns(self):
        cfg = self.visual_ok_config()
        cfg["sections"][0]["parts"] = [
            diagram_part("intro-d1"),
            image_part("intro-i1", "intro-shot"),
            text_part("intro-t1"),
            text_part("intro-t2"),
            table_part("intro-b1"),
        ]
        res, _ = self.validate(cfg)
        self.assert_exit(res, 0)
        self.assert_diag(res, "W-TEXT-RUN", "/sections/0/parts/3")

    def test_reported_once_per_section(self):
        """同じ節の連続は直す箇所が同じなので、1 件だけ報告する。"""
        cfg = self.visual_ok_config()
        cfg["sections"][0]["parts"] = [
            diagram_part("intro-d1"),
            image_part("intro-i1", "intro-shot"),
            text_part("intro-t1"),
            text_part("intro-t2"),
            text_part("intro-t3"),
            text_part("intro-t4"),
        ]
        res, _ = self.validate(cfg)
        lines = self.assert_diag(res, "W-TEXT-RUN")
        self.assertEqual(1, len(lines), "W-TEXT-RUN が節あたり 1 件に絞られていない: %r" % lines)

    def test_separated_text_is_allowed(self):
        cfg = self.visual_ok_config()
        cfg["sections"][0]["parts"] = [
            text_part("intro-t1"),
            diagram_part("intro-d1"),
            image_part("intro-i1", "intro-shot"),
            text_part("intro-t2"),
        ]
        res, _ = self.validate(cfg)
        self.assert_no_diag(res, "W-TEXT-RUN")

    def test_limit_comes_from_canon_not_script(self):
        cfg = self.visual_ok_config()
        cfg["sections"][0]["parts"] = [
            diagram_part("intro-d1"),
            image_part("intro-i1", "intro-shot"),
            text_part("intro-t1"),
            text_part("intro-t2"),
            table_part("intro-b1"),
        ]
        self.patch_visual_policy(max_consecutive_text_parts=2)
        res, _ = self.validate(cfg)
        self.assert_no_diag(res, "W-TEXT-RUN")


class TestCanonAbsenceFailsClosed(VisualDensityTestBase):
    """正本が読めないときも検査は動き、しかもゲートは緩まない。

    「正本が無いなら判定できないので通す」は、方針ファイルを消すだけで
    下限を無効化できる逃げ道になる。退避値は正本と同じ下限 (図解 1・画像 1)
    を保ち、error 宣言も保ったままにする。
    """

    def test_missing_canon_still_reports(self):
        (self.root / VISUAL_POLICY_RELPATH).unlink()
        cfg = self.visual_ok_config()
        cfg["sections"][1]["parts"] = [text_part("practice-t1")]
        res, _ = self.validate(cfg)
        self.assert_diag(res, "W-VISUAL-ABSENT", "/sections/1/parts")

    def test_missing_canon_does_not_loosen_the_gate(self):
        (self.root / VISUAL_POLICY_RELPATH).unlink()
        cfg = self.visual_ok_config()
        cfg["sections"][1]["parts"] = [text_part("practice-t1")]
        res, _ = self.validate(cfg)
        self.assert_fails_with(res, "W-DIAGRAM-FEW", "/sections/1/parts")
        self.assert_diag(res, "E-IMAGE-ABSENT", "/sections/1/parts")

    def test_missing_canon_does_not_manufacture_findings(self):
        """退避したからといって、満たしている構成が落ちるようになってもいけない。"""
        (self.root / VISUAL_POLICY_RELPATH).unlink()
        res, _ = self.validate(self.visual_ok_config())
        self.assert_exit(res, 0)


if __name__ == "__main__":
    unittest.main()
