"""C02 mfk_customer_id_resolve のユニットテスト。

会社名→MF顧客ID の一意解決・backfill 提案・要マスタ登録の可視化(近接候補)を検証する。
名寄せ境界は lib/mfk_reconcile の normalize/_company_match を再利用し、本 module 自身は
個社会社名リテラルを一切持たない(C14 の一般解の受け皿)。
"""
import subprocess
import sys
from pathlib import Path

import mfk_customer_id_resolve as C
from mfk_reconcile import normalize


# ---------------------------------------------------------------------------
# resolve_customer_id — 一意/曖昧/無一致の3方式
# ---------------------------------------------------------------------------
def test_resolve_unique_name_confirmed():
    name_by_id = {"c1": "アルファ商事株式会社", "c2": "ベータ工業株式会社"}
    r = C.resolve_customer_id(normalize("アルファ商事株式会社"), name_by_id)
    assert r == {"mf_customer_id": "c1", "confirmed": True,
                 "method": "unique_name", "matches": ["c1"]}


def test_resolve_ambiguous_not_confirmed():
    """複数一致は誤結線を避けるため confirmed=False(自動 backfill 対象外)。"""
    name_by_id = {"c1": "アルファ商事株式会社", "c2": "アルファ商事関西株式会社"}
    r = C.resolve_customer_id(normalize("アルファ商事株式会社"), name_by_id)
    assert r["confirmed"] is False
    assert r["method"] == "ambiguous"
    assert set(r["matches"]) == {"c1", "c2"}
    assert r["mf_customer_id"] is None


def test_resolve_none_when_no_match():
    name_by_id = {"c1": "アルファ商事株式会社"}
    r = C.resolve_customer_id(normalize("見知らぬ株式会社"), name_by_id)
    assert r == {"mf_customer_id": None, "confirmed": False, "method": "none", "matches": []}


def test_resolve_empty_inputs():
    assert C.resolve_customer_id("", {"c1": "x"})["method"] == "none"
    assert C.resolve_customer_id(normalize("A社"), {})["method"] == "none"


# ---------------------------------------------------------------------------
# build_name_index — MF 生 JSON から {cid: 会社名}
# ---------------------------------------------------------------------------
def test_build_name_index_uses_name_then_cid_fallback():
    idx = C.build_name_index({"customers": {
        "c1": {"name": "アルファ商事株式会社"},
        "c2": {},  # name 欠落 → cid を会社名 fallback
    }})
    assert idx == {"c1": "アルファ商事株式会社", "c2": "c2"}


def test_build_name_index_empty():
    assert C.build_name_index({}) == {}
    assert C.build_name_index(None) == {}


# ---------------------------------------------------------------------------
# plan_customer_id_backfill — 一意確定分のみ提案(明示済み/曖昧はスキップ)
# ---------------------------------------------------------------------------
def test_plan_backfill_only_unique_and_skips_explicit():
    name_by_id = {"c1": "アルファ商事株式会社", "c2": "ベータ工業株式会社"}
    contracts = [
        {"契約ID": "k1", "取引先": "アルファ商事株式会社"},              # 一意 → 提案
        {"契約ID": "k2", "取引先": "ガンマ通商株式会社", "MF顧客ID": "explicit"},  # 明示済 → skip
        {"契約ID": "k3", "取引先": "見知らぬ株式会社"},                 # 無一致 → skip
    ]
    backfill = C.plan_customer_id_backfill(contracts, name_by_id)
    assert backfill == [{"契約ID": "k1", "取引先": "アルファ商事株式会社", "mf_customer_id": "c1"}]


def test_plan_backfill_skips_ambiguous():
    name_by_id = {"c1": "アルファ商事株式会社", "c2": "アルファ商事関西株式会社"}
    contracts = [{"契約ID": "k1", "取引先": "アルファ商事株式会社"}]
    assert C.plan_customer_id_backfill(contracts, name_by_id) == []


# ---------------------------------------------------------------------------
# unresolved_registry_candidates — 要マスタ登録の可視化 + 近接候補併記
# ---------------------------------------------------------------------------
def test_unresolved_surfaces_none_with_candidates():
    """一意確定できない契約を『要マスタ登録』として可視化し近接候補を併記する
    (silent に名前依存へ戻さない = GAP-ID-ALIAS-BACKFILL-PATH の closure)。"""
    name_by_id = {"c1": "アルファ商事株式会社", "c9": "アルファ商事関連株式会社"}
    # 「アルファ商事」は c1(完全一致含む包含)にも c9 にも境界一致し ambiguous になる。
    contracts = [{"契約ID": "k1", "取引先": "アルファ商事"}]
    out = C.unresolved_registry_candidates(contracts, name_by_id)
    assert len(out) == 1
    assert out[0]["契約ID"] == "k1"
    assert out[0]["method"] in {"ambiguous", "none"}
    # candidates は補助指標(可視化専用)。matches に含まれない近接候補を提示。
    assert isinstance(out[0]["candidates"], list)


def test_unresolved_skips_confirmed_and_explicit():
    name_by_id = {"c1": "アルファ商事株式会社", "c2": "ベータ工業株式会社"}
    contracts = [
        {"契約ID": "k1", "取引先": "アルファ商事株式会社"},               # 一意 → 対象外
        {"契約ID": "k2", "取引先": "既知株式会社", "MF顧客ID": "explicit"},  # 明示済 → 対象外
        {"契約ID": "k3", "取引先": "見知らぬ株式会社"},                  # none → 要マスタ登録
    ]
    out = C.unresolved_registry_candidates(contracts, name_by_id)
    assert [u["契約ID"] for u in out] == ["k3"]
    assert out[0]["method"] == "none"


# ---------------------------------------------------------------------------
# nearby_candidates — 近接度で上位提示(境界確定には使わない補助指標)
# ---------------------------------------------------------------------------
def test_nearby_candidates_ranked_and_excludes():
    name_by_id = {"c1": "アルファ商事関連株式会社", "c2": "全然違う会社"}
    cand = C.nearby_candidates(normalize("アルファ商事株式会社"), name_by_id)
    assert cand and cand[0]["mf_customer_id"] == "c1"
    # exclude で確定済み matches を除ける。
    assert C.nearby_candidates(normalize("アルファ商事株式会社"), name_by_id,
                               exclude=("c1",))[0]["mf_customer_id"] != "c1" \
        if len(cand) > 1 else True


def test_no_hardcoded_company_literals_in_module():
    """C14: 本 module 自身が個社会社名リテラルを持たない(一般解の受け皿である担保)。"""
    src = Path(C.__file__).read_text(encoding="utf-8").lower()
    for lit in ("2ndcommunity", "secondcommunity", "セカンドコミュニティ",
                "hosono", "細野", "paws", "パウズ", "ポーズ"):
        assert lit.lower() not in src, f"C02 に個社会社名リテラル {lit!r} が混入 (C14 違反)"


# ---------------------------------------------------------------------------
# CLI self-test — exit 0 (in-process でカバレッジ計上 + subprocess で実 exit code)
# ---------------------------------------------------------------------------
def test_self_test_in_process_returns_zero():
    """_self_test を in-process で実行し全アサーションが通る (subprocess はカバレッジ非計上のため)。"""
    assert C._self_test() == 0


def test_cli_self_test_exits_zero():
    r = subprocess.run([sys.executable, C.__file__], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert "self-test OK" in r.stdout
