# -*- coding: utf-8 -*-
"""section_kind ごとの追加制約 (A9 / N8)。

AC-C12-15 / 16 と part_data_schema の notes、および R21 C53 由来の
handson / anticipated-qa の必須条件が出所。用途固有の要求を共通スキーマの
分岐 1 点 (section_kind) で表現していることを固定する。
"""

import unittest

import _harness as H


def one_section(section_kind, parts, **over):
    cfg = H.valid_config()
    sec = H.section("s1", section_kind=section_kind, parts=parts)
    sec.update(over)
    cfg["sections"] = [sec]
    return H.with_visual_floor(cfg)


class ActionItems(H.C12TestCase):

    def _b16(self, rows):
        return {"part": "B16", "id": "ai", "data": {"rows": rows}}

    def test_owner_missing(self):
        """AC-C12-15: owner を欠く B16 行は E-SECTIONKIND-CONSTRAINT。"""
        cfg = one_section("action-items", [self._b16([
            {"key": "a1", "text": "台帳を更新する", "due": "2026/08/20"}
        ])])
        res, _ = self.validate(cfg)
        self.assert_fails_with(res, "E-SECTIONKIND-CONSTRAINT", "/sections/0")

    def test_due_missing(self):
        """due も必須メタ。"""
        cfg = one_section("action-items", [self._b16([
            {"key": "a1", "text": "台帳を更新する", "owner": "田中"}
        ])])
        res, _ = self.validate(cfg)
        self.assert_exit(res, 1)

    def test_complete_row_passes(self):
        cfg = one_section("action-items", [self._b16([
            {"key": "a1", "text": "台帳を更新する", "owner": "田中", "due": "2026/08/20"}
        ])])
        res, _ = self.validate(cfg)
        self.assert_exit(res, 0)

    def test_due_accepts_undecided(self):
        """due は yyyy/mm/dd または '未定'。"""
        cfg = one_section("action-items", [self._b16([
            {"key": "a1", "text": "台帳を更新する", "owner": "田中", "due": "未定"}
        ])])
        res, _ = self.validate(cfg)
        self.assert_exit(res, 0)


class KnownUnknownNext(H.C12TestCase):

    def _b04(self, cards):
        return {"part": "B04", "id": "trio", "data": {"cards": cards}}

    def _card(self, label, tone, note_key="k"):
        return {"label": label, "body": "内容の説明", "tone": tone, "note_key": note_key}

    def test_two_cards_rejected(self):
        """AC-C12-16: 2 枚構成は E-SECTIONKIND-CONSTRAINT (3 分割の担保)。"""
        cfg = one_section("known-unknown-next", [self._b04([
            self._card("分かっている", "today", "k1"),
            self._card("分からない", "rest", "k2"),
        ])])
        res, _ = self.validate(cfg)
        self.assert_fails_with(res, "E-SECTIONKIND-CONSTRAINT", "/sections/0")

    def test_three_cards_with_note_keys_pass(self):
        cfg = one_section("known-unknown-next", [self._b04([
            self._card("分かっている", "today", "k1"),
            self._card("分からない", "rest", "k2"),
            self._card("次に調べる", "neutral", "k3"),
        ])])
        res, _ = self.validate(cfg)
        self.assert_exit(res, 0)

    def test_note_key_required(self):
        """メモ機構への結線として全 card の note_key が非空。"""
        cfg = one_section("known-unknown-next", [self._b04([
            self._card("分かっている", "today", "k1"),
            self._card("分からない", "rest", None),
            self._card("次に調べる", "neutral", "k3"),
        ])])
        res, _ = self.validate(cfg)
        self.assert_fails_with(res, "E-SECTIONKIND-CONSTRAINT")


class Decisions(H.C12TestCase):

    def test_decided_null_rejected(self):
        """decisions では全 row の decided が bool (null 不可)。"""
        cfg = one_section("decisions", [{"part": "B09", "id": "chk", "data": {
            "rows": [{"key": "d1", "text": "来月から適用する", "decided": None}],
            "show_counter": True,
        }}])
        res, _ = self.validate(cfg)
        self.assert_fails_with(res, "E-SECTIONKIND-CONSTRAINT", "/sections/0")

    def test_decided_bool_passes(self):
        cfg = one_section("decisions", [{"part": "B09", "id": "chk", "data": {
            "rows": [{"key": "d1", "text": "来月から適用する", "decided": True}],
            "show_counter": True,
        }}])
        res, _ = self.validate(cfg)
        self.assert_exit(res, 0)


class Sources(H.C12TestCase):

    def test_footnote_required(self):
        """sources では少なくとも 1 card の footnote が非空。"""
        cfg = one_section("sources", [{"part": "B07", "id": "f", "data": {
            "cards": [{"title": "社内規程", "body": "第 3 版", "icon": None, "footnote": None}],
        }}])
        res, _ = self.validate(cfg)
        self.assert_fails_with(res, "E-SECTIONKIND-CONSTRAINT", "/sections/0")

    def test_footnote_present_passes(self):
        cfg = one_section("sources", [{"part": "B07", "id": "f", "data": {
            "cards": [{"title": "社内規程", "body": "第 3 版", "icon": None,
                       "footnote": "総務部 2026 年 4 月改訂"}],
        }}])
        res, _ = self.validate(cfg)
        self.assert_exit(res, 0)


class Handson(H.C12TestCase):
    """R21 C53: handson は B17 を 1 件以上必要とする。"""

    def _b17(self, steps, **over):
        data = {"steps": steps, "asset_id": None, "live_demo": False}
        data.update(over)
        return {"part": "B17", "id": "hs", "data": data}

    def _step(self, operation="画面右上の実行を押す", expected="集計結果が表に出る", stuck_hint=None):
        return {"operation": operation, "expected": expected, "stuck_hint": stuck_hint}

    def test_handson_without_b17(self):
        """B17 が無い handson は E-SECTIONKIND-HANDSON。"""
        cfg = one_section("handson", [H.text_part("t1")])
        res, _ = self.validate(cfg)
        self.assert_fails_with(res, "E-SECTIONKIND-HANDSON", "/sections/0")

    def test_handson_with_b17_passes(self):
        cfg = one_section("handson", [self._b17([self._step()])])
        res, _ = self.validate(cfg)
        self.assert_exit(res, 0)

    def test_b17_expected_is_required(self):
        """operation と expected は対で必須 (expected が無いと読み手が正誤を判定できない)。"""
        cfg = one_section("handson", [self._b17([
            {"operation": "画面右上の実行を押す", "stuck_hint": None}
        ])])
        res, _ = self.validate(cfg)
        self.assert_exit(res, 1)

    def test_b17_operation_is_required(self):
        cfg = one_section("handson", [self._b17([
            {"expected": "集計結果が表に出る", "stuck_hint": None}
        ])])
        res, _ = self.validate(cfg)
        self.assert_exit(res, 1)

    def test_b17_asset_id_dangling(self):
        """asset_id は assets への参照なので dangling は E-REF-DANGLING。"""
        cfg = one_section("handson", [self._b17([self._step()], asset_id="nope")])
        res, _ = self.validate(cfg)
        self.assert_fails_with(res, "E-REF-DANGLING")

    def test_b17_live_demo_default_false(self):
        """live_demo の既定は false (推測で true にしない)。"""
        cfg = one_section("handson", [{"part": "B17", "id": "hs", "data": {
            "steps": [self._step()], "asset_id": None}}])
        res, _, out = self.normalize(cfg)
        self.assert_exit(res, 0)
        self.assertIs(False, self.read_out(out)["sections"][0]["parts"][0]["data"]["live_demo"])


class AnticipatedQa(H.C12TestCase):
    """R21 C53: 先回り Q&A は既定で畳んで冒頭の情報量を増やさない。"""

    def _b10(self, items):
        return {"part": "B10", "id": "qa", "data": {"items": items}}

    def _item(self, summary, open_=False):
        return {"summary": summary, "body": "その場での回答", "open": open_}

    def test_single_item_rejected(self):
        cfg = one_section("anticipated-qa", [self._b10([self._item("精度はどれくらい?")])])
        res, _ = self.validate(cfg)
        self.assert_exit(res, 1)

    def test_two_closed_items_pass(self):
        cfg = one_section("anticipated-qa", [self._b10([
            self._item("精度はどれくらい?"), self._item("費用はどれくらい?")])])
        res, _ = self.validate(cfg)
        self.assert_exit(res, 0)

    def test_open_true_rejected(self):
        """全件 open=false であること。"""
        cfg = one_section("anticipated-qa", [self._b10([
            self._item("精度はどれくらい?", True), self._item("費用はどれくらい?")])])
        res, _ = self.validate(cfg)
        self.assert_exit(res, 1)

    def test_open_true_allowed_in_other_kinds(self):
        """他の section_kind では open=true を許す (制約は種別に紐づく)。"""
        cfg = one_section("standard", [self._b10([self._item("補足", True)])])
        res, _ = self.validate(cfg)
        self.assert_exit(res, 0)


if __name__ == "__main__":
    unittest.main()
