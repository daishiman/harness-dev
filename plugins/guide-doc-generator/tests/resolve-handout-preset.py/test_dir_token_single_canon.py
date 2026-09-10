"""dir_token の正本が 1 つであることを固定する (P03-x-03 DT-1 / F-P03X03-01)。

出荷 config/handout-purposes.json は `_meta.source_of_truth` で
plugin-plans/guide-doc-generator/briefs/script-brief-C23.json の
`vocabulary_ssot.entries` を正本に指名している。指名しているということは、
config 側の値はその写しでなければならない。

本ファイルは **意図的に赤で固定してある**。測定時点で dir_token は全 slug で
正本と食い違っており (正本は機械 id 形の slug、出荷は読み手向けの和文)、
`_meta.source_of_truth` の指名だけが残って実体が 2 つに割れている。

修正方向はまだ裁定されていない (F-P03X03-02):
  (a) 出荷を正本へ合わせる — R25/REQ-6 で dir_token はディレクトリ名から外れ、
      日本語のディレクトリ名は subject_slug が運ぶため、R5 を壊さずに戻せる。
  (b) 正本を出荷へ合わせる — dir_token は索引メタデータであり、
      パス安全性を根拠にした字種制限は REQ-6 で失効している。
どちらを採るにせよ「正本が 2 つある」状態は不正であり、本テストはその状態だけを
落とす。値そのものはどちらのファイルにも書かず、両方から実測して突き合わせる
(値を写すと、このテスト自体が 3 つ目の正本になる)。
"""

import json
import unittest

import _harness as H

C23_BRIEF = H.REPO_ROOT / "plugin-plans" / "guide-doc-generator" / "briefs" / "script-brief-C23.json"


def canon_entries(tc):
    """正本 (brief vocabulary_ssot.entries) の slug -> entry。"""
    if not C23_BRIEF.is_file():
        tc.fail("語彙の正本が読めない: {}".format(C23_BRIEF))
    data = json.loads(C23_BRIEF.read_text(encoding="utf-8"))
    entries = (data.get("vocabulary_ssot") or {}).get("entries")
    if not isinstance(entries, list) or not entries:
        tc.fail("script-brief-C23.json に vocabulary_ssot.entries が無い")
    return {entry.get("slug"): entry for entry in entries}


def shipped_entries(tc):
    """出荷 config の slug -> entry。"""
    catalog = H.load_catalog(tc) if hasattr(H, "load_catalog") else None
    if catalog is None:
        H.require_file(tc, H.CATALOG, "C23")
        catalog = json.loads(H.CATALOG.read_text(encoding="utf-8"))
    vocabulary = catalog.get("vocabulary")
    if not isinstance(vocabulary, list) or not vocabulary:
        tc.fail("出荷 config に vocabulary が無い: {}".format(H.CATALOG))
    return {entry.get("slug"): entry for entry in vocabulary}


class DirTokenSingleCanonTest(unittest.TestCase):
    """出荷 config が正本の写しになっていること。"""

    def setUp(self):
        self.canon = canon_entries(self)
        self.shipped = shipped_entries(self)

    def test_source_of_truth_names_the_brief(self):
        """出荷側が正本を指名していること (指名が無ければ写しの義務も生じない)。"""
        catalog = json.loads(H.CATALOG.read_text(encoding="utf-8"))
        declared = (catalog.get("_meta") or {}).get("source_of_truth")
        self.assertIsInstance(declared, str, "_meta.source_of_truth が無い")
        self.assertIn(
            "script-brief-C23.json", declared,
            "_meta.source_of_truth が C23 の brief を指名していない: {}".format(declared),
        )

    def test_slug_sets_are_identical(self):
        self.assertEqual(sorted(self.canon), sorted(self.shipped))

    def test_dir_token_matches_the_canon_for_every_slug(self):
        """赤で固定: 正本と出荷の dir_token が slug ごとに一致すること。

        現状は全 slug で不一致。どちらを正本とするかの裁定が付いた側へ
        片方を寄せた時点で緑になる。片方だけを直しても、もう片方が残る限り
        このテストは落ち続ける (それが単一正本原則の機械表現である)。
        """
        mismatched = {}
        for slug, entry in sorted(self.canon.items()):
            shipped = self.shipped.get(slug) or {}
            if entry.get("dir_token") != shipped.get("dir_token"):
                mismatched[slug] = (entry.get("dir_token"), shipped.get("dir_token"))
        self.assertEqual(
            {}, mismatched,
            "dir_token の正本が 2 つある (slug: (正本, 出荷)) = {}。"
            "出荷 _meta.source_of_truth は brief を正本に指名しているのに"
            "写しになっていない".format(mismatched),
        )

    def test_label_and_aliases_match_the_canon(self):
        """同じ写しの義務が他のフィールドでも守られているかの対照。

        dir_token だけが割れているのか、語彙全体が割れているのかを分ける。
        """
        mismatched = {}
        for slug, entry in sorted(self.canon.items()):
            shipped = self.shipped.get(slug) or {}
            for field in ("label_ja", "aliases"):
                if entry.get(field) != shipped.get(field):
                    mismatched.setdefault(slug, {})[field] = (
                        entry.get(field), shipped.get(field))
        self.assertEqual({}, mismatched, "語彙の写しが正本とずれている: {}".format(mismatched))


class DirTokenCliTest(unittest.TestCase):
    """CLI が返す dir_token も正本の写しであること。"""

    def setUp(self):
        H.require_script(self)
        self.canon = canon_entries(self)

    def test_cli_dir_token_matches_the_canon(self):
        """赤で固定: --purpose の出力 dir_token が正本と一致すること。

        利用者が実際に受け取るのは CLI 出力であり、config を直接読むのは
        テストだけである。config だけを直して CLI 経路が別の値を返す状態を
        作らないために、config 比較とは別に固定する。
        """
        mismatched = {}
        for slug, entry in sorted(self.canon.items()):
            proc = H.run(["--purpose", slug])
            self.assertEqual(0, proc.returncode, H.describe(proc))
            payload = json.loads(H.out_text(proc))
            if payload.get("dir_token") != entry.get("dir_token"):
                mismatched[slug] = (entry.get("dir_token"), payload.get("dir_token"))
        self.assertEqual(
            {}, mismatched,
            "CLI が返す dir_token が正本と食い違う (slug: (正本, CLI)) = {}".format(mismatched),
        )


if __name__ == "__main__":
    unittest.main()
