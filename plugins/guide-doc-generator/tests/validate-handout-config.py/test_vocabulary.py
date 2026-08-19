"""C12 が表示語彙正本 (config/handout-vocabulary.json) を突き合わせることの受入テスト。

守りたい性質は 2 つある。

1. **前提コネクタ (R25/REQ-9)**: 構成データが持つのは id だけで、読者に見える
   表記は語彙正本にしかない。語彙に無い id を書けたまま render まで通ると、
   C11 が引けずに落ちるか、あるいは id をそのまま描いて取り繕う。どちらも
   構成データの段階で止めるべきなので E-CONNECTOR-UNKNOWN を error にする。
2. **fail-closed**: 語彙正本が読めないとき既定値へ落ちない。落とすと未知の
   コネクタが素通りする fail-open になり、「正本を壊せば通る」抜け道ができる。
   これは視覚下限 (test_visual_density.py) と同じ規律で、正本不在はゲートを
   緩めるのでなく起動を止める。
"""

import json
import unittest

import _harness as H


CONNECTOR_UNKNOWN = "E-CONNECTOR-UNKNOWN"
ENUM_VOCAB_INCOMPLETE = "E-ENUM-VOCAB-INCOMPLETE"
VOCABULARY_RELPATH = "config/handout-vocabulary.json"


def with_connectors(cfg, connectors):
    cfg["prerequisite_connectors"] = connectors
    return cfg


class TestPrerequisiteConnectors(H.C12TestCase):

    def canon(self):
        return json.loads((self.root / VOCABULARY_RELPATH).read_text(encoding="utf-8"))

    def write_canon(self, data):
        (self.root / VOCABULARY_RELPATH).write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def test_user_specified_three_connectors_pass(self):
        """利用者指定の 3 件 (Google Drive / OneDrive / kintone) がそのまま通る。"""
        cfg = H.valid_config()
        with_connectors(cfg, [{"connector": "google-drive"},
                              {"connector": "onedrive"},
                              {"connector": "kintone"}])
        res, _ = self.validate(cfg)
        self.assert_exit(res, 0)

    def test_unknown_connector_id_stops_completion(self):
        cfg = H.valid_config()
        with_connectors(cfg, [{"connector": "google-drive"}, {"connector": "dropbox"}])
        res, _ = self.validate(cfg)
        self.assert_diag(res, CONNECTOR_UNKNOWN, "/prerequisite_connectors/1/connector")
        self.assert_exit(res, 1)

    def test_absent_field_is_not_a_diagnostic(self):
        """任意項目である。書かなかったことを違反にしない。"""
        cfg = H.valid_config()
        self.assertNotIn("prerequisite_connectors", cfg)
        res, _ = self.validate(cfg)
        self.assert_exit(res, 0)

    def test_note_is_authored_text_and_passes(self):
        cfg = H.valid_config()
        with_connectors(cfg, [{"connector": "kintone", "note": "レコード読み取りのみ"}])
        res, _ = self.validate(cfg)
        self.assert_exit(res, 0)

    def test_allowed_ids_come_from_canon_not_script(self):
        """語彙の追記だけで新しいコネクタが受理される (script へ列挙値を焼かない)。"""
        cfg = H.valid_config()
        with_connectors(cfg, [{"connector": "box"}])
        res, _ = self.validate(cfg)
        self.assert_exit(res, 1)

        canon = self.canon()
        canon["connectors"]["entries"].append({"id": "box", "label": "Box"})
        self.write_canon(canon)
        res, _ = self.validate(cfg)
        self.assert_exit(res, 0)

    def test_removing_an_id_from_canon_starts_rejecting_it(self):
        """逆向き。正本から落とした id は次の実行で拒まれる。"""
        cfg = H.valid_config()
        with_connectors(cfg, [{"connector": "onedrive"}])
        res, _ = self.validate(cfg)
        self.assert_exit(res, 0)

        canon = self.canon()
        canon["connectors"]["entries"] = [
            e for e in canon["connectors"]["entries"] if e["id"] != "onedrive"]
        self.write_canon(canon)
        res, _ = self.validate(cfg)
        self.assert_diag(res, CONNECTOR_UNKNOWN, "/prerequisite_connectors/0/connector")
        self.assert_exit(res, 1)


class TestVocabularyCanonFailsClosed(H.C12TestCase):

    def test_missing_canon_stops_launch(self):
        """正本が無いとき既定値へ落ちない。落ちると未知 id が素通りする。"""
        (self.root / VOCABULARY_RELPATH).unlink()
        cfg = H.valid_config()
        with_connectors(cfg, [{"connector": "dropbox"}])
        res, _ = self.validate(cfg)
        self.assertNotEqual(0, res.returncode,
                            "正本不在で exit=0 になった (fail-open)\nstderr=%r" % res.stderr)

    def test_malformed_canon_stops_launch(self):
        (self.root / VOCABULARY_RELPATH).write_text("{ not json", encoding="utf-8")
        cfg = H.valid_config()
        res, _ = self.validate(cfg)
        self.assertNotEqual(0, res.returncode,
                            "壊れた正本で exit=0 になった\nstderr=%r" % res.stderr)


class TestAttainmentVocabularyCompleteness(H.C12TestCase):
    """enum と表示語彙の対応漏れを C12 自身が自己検査する。

    C18 の E-ENUM-RAW は「生の enum 値が可視テキストへ出ている」を見る検査だが、
    対応表に欠落があると変換のしようが無く、C18 の側では直しようのない違反に
    なる。欠落は構成データでなく正本の不整合なので C12 が先に止める。
    """

    def canon_path(self):
        return self.root / VOCABULARY_RELPATH

    def test_level_without_label_stops_completion(self):
        canon = json.loads(self.canon_path().read_text(encoding="utf-8"))
        canon["attainment_level_labels"]["entries"] = [
            e for e in canon["attainment_level_labels"]["entries"] if e["enum"] != "operable"]
        self.canon_path().write_text(json.dumps(canon, ensure_ascii=False, indent=2),
                                     encoding="utf-8")
        cfg = H.valid_config()  # attainment_level == "operable"
        res, _ = self.validate(cfg)
        self.assert_diag(res, ENUM_VOCAB_INCOMPLETE, "/attainment_level")
        self.assert_exit(res, 1)

    def test_complete_mapping_is_silent(self):
        cfg = H.valid_config()
        res, _ = self.validate(cfg)
        self.assertNotIn(ENUM_VOCAB_INCOMPLETE, res.stderr)
        self.assert_exit(res, 0)


if __name__ == "__main__":
    unittest.main()
