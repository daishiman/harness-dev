# -*- coding: utf-8 -*-
"""R21 C59 所要時間 (A9d / N7c)。

AC-C12-R21-59 が出所。section.duration が時間の唯一の正本で、
B03 rows[].time は「そのセクション内の内訳」。割合の分母は sections[].duration の総和
(document.duration ではない)。下限割合は config/handout-sections.json の min_duration_share。
"""

import unittest

import _harness as H


def b03(part_id, rows):
    return {"part": "B03", "id": part_id, "data": {"rows": rows}}


def row(num, text, time=None, sub=None):
    return {"num": num, "text": text, "time": time, "sub": sub}


def timed_config(specs):
    """specs: [(section_id, section_kind, duration), ...] から 6 セクション程度の資料を作る。"""
    cfg = H.valid_config()
    cfg["sections"] = [
        H.section(sid, section_kind=kind, duration=duration)
        for sid, kind, duration in specs
    ]
    return cfg


BALANCED = [
    ("intro", "standard", "10分"),
    ("basics", "standard", "10分"),
    ("demo", "standard", "10分"),
    ("practice", "standard", "10分"),
    ("talk", "dialogue", "10分"),
    ("wrap", "standard", "10分"),
]


class DurationFormat(H.C12TestCase):

    def test_valid_section_duration(self):
        cfg = H.valid_config()
        cfg["sections"][0]["duration"] = "45分"
        res, _ = self.validate(cfg)
        self.assert_exit(res, 0)

    def test_range_notation_is_rejected(self):
        """AC-C12-R21-59: 範囲表記はセクション単位では受け付けない。"""
        cfg = H.valid_config()
        cfg["sections"][0]["duration"] = "30〜45分"
        res, _ = self.validate(cfg)
        self.assert_fails_with(res, "E-SECTION-DURATION-FORMAT", "/sections/0/duration")

    def test_page_count_notation_is_rejected(self):
        """'A4 n 枚相当' もセクション単位では不可。"""
        cfg = H.valid_config()
        cfg["sections"][0]["duration"] = "A4 2 枚相当"
        res, _ = self.validate(cfg)
        self.assert_fails_with(res, "E-SECTION-DURATION-FORMAT", "/sections/0/duration")

    def test_hour_notation_is_reshaped_by_normalize(self):
        """N7c: '1時間' → '60分' / '90 分' → '90分' / '1時間30分' → '90分' の純変換。"""
        for given, expected in (("1時間", "60分"), ("90 分", "90分"), ("1時間30分", "90分")):
            with self.subTest(given=given):
                cfg = H.valid_config()
                cfg["sections"][0]["duration"] = given
                out = self.tmp / ("o-%s.json" % expected)
                res, _, out = self.normalize(cfg, out=out)
                self.assert_exit(res, 0)
                self.assertEqual(expected, self.read_out(out)["sections"][0]["duration"])

    def test_range_is_not_converted_by_normalize(self):
        """N7c: 範囲表記は変換せず E-SECTION-DURATION-FORMAT。"""
        cfg = H.valid_config()
        cfg["sections"][0]["duration"] = "30〜45分"
        res, _, out = self.normalize(cfg)
        self.assert_fails_with(res, "E-SECTION-DURATION-FORMAT")
        self.assertFalse(out.exists())

    def test_duration_is_optional_without_share_kinds(self):
        """min_duration_share を持つ種別が無ければ duration 未設定でも通る。"""
        cfg = H.valid_config()
        for sec in cfg["sections"]:
            sec["duration"] = None
        res, _ = self.validate(cfg)
        self.assert_exit(res, 0)


class DurationShare(H.C12TestCase):

    def test_dialogue_share_below_minimum(self):
        """AC-C12-R21-59: 全 60 分中 dialogue 5 分 (0.083 < 0.15) は E-SECTIONKIND-DURATION-SHARE。"""
        specs = [
            ("intro", "standard", "10分"),
            ("basics", "standard", "10分"),
            ("demo", "standard", "10分"),
            ("practice", "standard", "15分"),
            ("talk", "dialogue", "5分"),
            ("wrap", "standard", "10分"),
        ]
        res, _ = self.validate(timed_config(specs))
        self.assert_fails_with(res, "E-SECTIONKIND-DURATION-SHARE")

    def test_dialogue_share_at_or_above_minimum(self):
        """10/60 = 0.167 は下限 0.15 以上なので通る。"""
        res, _ = self.validate(timed_config(BALANCED))
        self.assert_exit(res, 0)

    def test_share_threshold_comes_from_catalog(self):
        """下限値は config/handout-sections.json 側 (script に 0.15 を書かない)。"""
        cfg = timed_config(BALANCED)
        res_before, _ = self.validate(cfg)
        self.assert_exit(res_before, 0)

        self.patch_sections_catalog("dialogue", min_duration_share=0.5)
        res_after, _ = self.validate(cfg)
        self.assert_fails_with(res_after, "E-SECTIONKIND-DURATION-SHARE")

    def test_share_is_summed_per_kind(self):
        """同種別のセクションが複数あれば合計で判定する。"""
        specs = [
            ("intro", "standard", "40分"),
            ("talk1", "dialogue", "5分"),
            ("talk2", "dialogue", "5分"),
        ]
        res, _ = self.validate(timed_config(specs))
        self.assert_exit(res, 0)

    def test_denominator_is_sections_not_document_duration(self):
        """分母は sections[].duration の総和。document.duration を変えても判定は動かない。"""
        cfg = timed_config(BALANCED)
        cfg["duration"] = "A4 3 枚相当"
        res, _ = self.validate(cfg)
        self.assert_exit(res, 0)

    def test_zero_minute_dialogue_does_not_pass(self):
        """名目上の枠 (0 分) では下限を満たさない。"""
        specs = [
            ("intro", "standard", "30分"),
            ("talk", "dialogue", "0分"),
        ]
        res, _ = self.validate(timed_config(specs))
        self.assert_fails_with(res, "E-SECTIONKIND-DURATION-SHARE")


class DurationCompleteness(H.C12TestCase):

    def test_incomplete_duration_when_share_kind_present(self):
        """AC-C12-R21-59: dialogue がある資料で 1 セクションの duration が空なら E-DURATION-INCOMPLETE。"""
        cfg = timed_config(BALANCED)
        cfg["sections"][1]["duration"] = None
        res, _ = self.validate(cfg)
        self.assert_fails_with(res, "E-DURATION-INCOMPLETE", "/sections/1/duration")

    def test_missing_key_counts_as_incomplete(self):
        """キー自体が無い場合も同じ (割合が計算できない)。"""
        cfg = timed_config(BALANCED)
        del cfg["sections"][2]["duration"]
        res, _ = self.validate(cfg)
        self.assert_fails_with(res, "E-DURATION-INCOMPLETE", "/sections/2/duration")


class TimeboxSum(H.C12TestCase):

    def _agenda(self, section_duration, times):
        cfg = H.valid_config()
        cfg["sections"] = [
            H.section("agenda", section_kind="agenda-timebox", duration=section_duration,
                      parts=[b03("agenda-rows", [row(i + 1, "項目 %d" % (i + 1), time=t)
                                                 for i, t in enumerate(times)])]),
        ]
        return cfg

    def test_row_time_sum_matches(self):
        """行 time の総和が section.duration と一致すれば通る。"""
        res, _ = self.validate(self._agenda("30分", ["10分", "20分"]))
        self.assert_exit(res, 0)

    def test_row_time_sum_mismatch(self):
        """AC-C12-R21-59: 総和が食い違えば E-TIMEBOX-SUM。"""
        res, _ = self.validate(self._agenda("30分", ["10分", "15分"]))
        self.assert_fails_with(res, "E-TIMEBOX-SUM", "/sections/0")

    def test_agenda_row_time_required(self):
        """agenda-timebox では全 row の time が非空。"""
        res, _ = self.validate(self._agenda("30分", ["10分", None]))
        self.assert_exit(res, 1)

    def test_normalize_derives_section_duration_from_rows(self):
        """N7c: section.duration が空で行 time が全て埋まっていれば総和を充填する。"""
        cfg = self._agenda(None, ["10分", "20分"])
        res, _, out = self.normalize(cfg)
        self.assert_exit(res, 0)
        self.assertEqual("30分", self.read_out(out)["sections"][0]["duration"])

    def test_normalize_does_not_distribute_section_duration_to_rows(self):
        """導出は 1 方向のみ (セクション → 行 の割り振りはしない)。"""
        cfg = self._agenda("30分", [None, None])
        res, _, out = self.normalize(cfg)
        self.assert_exit(res, 1)
        self.assertFalse(out.exists())


class SingleTimeFieldInSchema(H.C12TestCase):

    def test_schema_has_no_second_duration_field(self):
        """AC-C12-R21-59: 所要時間フィールドが section.duration の 1 系統だけであることを schema で確認。"""
        schema_path = self.root / H.SCHEMA_RELPATH
        self.assertTrue(schema_path.exists(), "スキーマ正本が無い: %s" % schema_path)
        text = schema_path.read_text(encoding="utf-8")
        for forbidden in ("estimated_time", "time_budget", "section_minutes",
                          "duration_minutes", "elapsed", "timebox"):
            self.assertNotIn(forbidden, text, "第 2 の時間フィールド %s が schema にある" % forbidden)

    def test_normalized_output_has_no_second_time_field(self):
        """正規化済み構成データにも第 2 の時間フィールドが現れない。"""
        res, _, out = self.normalize(timed_config(BALANCED))
        self.assert_exit(res, 0)
        data = self.read_out(out)
        doc_time_keys = [k for k in data if "time" in k.lower() or "duration" in k.lower()]
        self.assertEqual(["duration"], sorted(doc_time_keys))
        for sec in data["sections"]:
            sec_time_keys = [k for k in sec if "time" in k.lower() or "duration" in k.lower()]
            self.assertEqual(["duration"], sorted(sec_time_keys))


if __name__ == "__main__":
    unittest.main()
