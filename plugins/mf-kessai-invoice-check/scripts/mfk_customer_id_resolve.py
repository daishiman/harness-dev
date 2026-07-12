#!/usr/bin/env python3
# /// script
# name: mfk_customer_id_resolve
# purpose: 契約の取引先名から MF顧客ID(customer_id) を一意解決し、backfill 提案と
#          要マスタ登録(ambiguous/none)の可視化(近接候補付き)を行う純関数 SSOT (C02)。
# inputs:
#   - resolve_customer_id(): 取引先名(normalize済み) + {customer_id: 会社名}
#   - plan_customer_id_backfill(): 契約 list + {customer_id: 会社名} → 一意確定分の backfill 提案
#   - unresolved_registry_candidates(): 未解決契約 → 要マスタ登録 + 近接候補
# outputs:
#   - resolve_customer_id(): {mf_customer_id, confirmed, method, matches}
#   - plan_customer_id_backfill(): [{契約ID, 取引先, mf_customer_id}]
#   - unresolved_registry_candidates(): [{契約ID, 取引先, method, matches, candidates}]
# contexts: [C]
# network: false
# write-scope: none
# dependencies: [mfk_reconcile]  # normalize / _company_match を再利用 (名寄せ境界の再発明禁止)
# requires-python: ">=3.11"
# ///
"""会社名 → MF顧客ID の解決を一本化する純関数モジュール (C02: 要因C6 顧客ID 0% 充足の根治)。

請求確認シート 665 行全ての MF顧客ID が空のため、lib/mfk_reconcile._boundary_customers の
「MF顧客ID優先」経路が一度も発火せず、全契約が会社名 normalize 一致に依存していた(名前drift時
false GAP)。本 module は MF 実績(customer_id → 会社名)から解決マップを構築し、**一意に確定できる
契約だけ** を自動 backfill 提案する。曖昧/不明な契約は silent に名前依存へ戻さず「要マスタ登録」
として可視化し、近接候補(境界外だが近い社名)を併記する(GAP-ID-ALIAS-BACKFILL-PATH の closure)。

設計上の不変則:
- 会社名一致は lib/mfk_reconcile.normalize / _company_match を import して再利用する(完全一致 or
  3文字以上包含という既存の名寄せ境界を再発明しない)。本 module 自身は個社の会社名リテラルを
  一切持たない(C14: 対症療法の frozenset ハードコード撤去の受け皿としての一般解)。
- 一意解決(method="unique_name")のみ confirmed=True として自動 backfill 対象にする。複数一致
  (ambiguous)・無一致(none)は自動確定しない(誤結線=誤った請求先への名寄せ事故を避ける)。
- 近接候補(nearby_candidates)は境界確定に使わない補助指標(可視化専用)。確定は _company_match
  のみが担う。
"""
from __future__ import annotations

import os
import sys

_LIB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

from mfk_reconcile import _company_match, normalize  # noqa: E402


def build_name_index(mf_raw):
    """MF 生 JSON({'customers': {cid: {'name': ...}}}) から {customer_id: 会社名} を作る。

    会社名が欠落する customer は cid 自体を会社名として使う(build_mf_index と同じ fallback)。
    """
    customers = (mf_raw or {}).get("customers") or {}
    return {cid: (c.get("name") or cid) for cid, c in customers.items()}


def resolve_customer_id(tnorm, name_by_id):
    """取引先名(normalize済み)を name_by_id({customer_id: 会社名})へ境界一致(_company_match)で
    解決する。

    戻り値: {"mf_customer_id": str|None, "confirmed": bool, "method": str, "matches": [cid, ...]}
      method: "unique_name"(一意確定・confirmed=True) / "ambiguous"(複数一致) / "none"(無一致)。
    """
    if not tnorm or not name_by_id:
        return {"mf_customer_id": None, "confirmed": False, "method": "none", "matches": []}
    matches = [cid for cid, name in name_by_id.items() if _company_match(tnorm, normalize(name))]
    if len(matches) == 1:
        return {"mf_customer_id": matches[0], "confirmed": True,
                "method": "unique_name", "matches": matches}
    if len(matches) >= 2:
        return {"mf_customer_id": None, "confirmed": False,
                "method": "ambiguous", "matches": matches}
    return {"mf_customer_id": None, "confirmed": False, "method": "none", "matches": []}


def _proximity_score(a, b):
    """2 正規化文字列の近接度(0.0-1.0) = 最長共通部分文字列長 / 長い方の文字列長。

    _company_match の境界(完全一致 or 3文字以上包含)に届かない候補を「要マスタ登録」画面で
    近い順に提示するための補助指標であり、境界確定(自動 backfill)には使わない。
    """
    if not a or not b:
        return 0.0
    la, lb = len(a), len(b)
    best = 0
    for i in range(la):
        for j in range(lb):
            k = 0
            while i + k < la and j + k < lb and a[i + k] == b[j + k]:
                k += 1
            best = max(best, k)
    return best / max(la, lb)


def nearby_candidates(tnorm, name_by_id, exclude=(), limit=3, min_score=0.34):
    """境界確定に届かない取引先向けに、正規化名が近い MF顧客を近い順で上位提示する。

    要マスタ登録(ambiguous/none)の可視化補助。exclude で確定済み matches を除ける。
    """
    excl = set(exclude)
    scored = []
    for cid, name in name_by_id.items():
        if cid in excl:
            continue
        score = _proximity_score(tnorm, normalize(name))
        if score >= min_score:
            scored.append({"mf_customer_id": cid, "name": name, "score": round(score, 2)})
    scored.sort(key=lambda x: -x["score"])
    return scored[:limit]


def plan_customer_id_backfill(contracts, name_by_id):
    """契約 list を走査し、MF顧客ID 未設定 & 一意解決できた分の backfill 提案を返す。

    既に MF顧客ID を carry する契約(シート明示済み)はスキップする(非破壊)。ambiguous/none は
    誤結線を避けるため提案しない(unresolved_registry_candidates 側で可視化する)。
    """
    out = []
    for c in contracts:
        if (c.get("MF顧客ID") or "").strip():
            continue
        res = resolve_customer_id(normalize(c.get("取引先") or ""), name_by_id)
        if res["confirmed"]:
            out.append({"契約ID": c.get("契約ID"), "取引先": c.get("取引先"),
                        "mf_customer_id": res["mf_customer_id"]})
    return out


def unresolved_registry_candidates(contracts, name_by_id):
    """MF顧客ID が確定できない契約(ambiguous/none)を近接候補付きで「要マスタ登録」可視化する。

    自動 backfill(plan_customer_id_backfill)の対象外分がここに現れる。人間がマスタへ MF顧客ID
    を明示登録する際の手掛かり(候補社名+近接度)を添える。
    """
    out = []
    for c in contracts:
        if (c.get("MF顧客ID") or "").strip():
            continue
        tnorm = normalize(c.get("取引先") or "")
        res = resolve_customer_id(tnorm, name_by_id)
        if res["confirmed"]:
            continue
        out.append({
            "契約ID": c.get("契約ID"), "取引先": c.get("取引先"), "method": res["method"],
            "matches": res["matches"],
            "candidates": nearby_candidates(tnorm, name_by_id, exclude=res["matches"]),
        })
    return out


def _self_test():
    name_by_id = {"c1": "アルファ商事株式会社", "c2": "ベータ工業株式会社"}
    r1 = resolve_customer_id(normalize("アルファ商事株式会社"), name_by_id)
    assert r1 == {"mf_customer_id": "c1", "confirmed": True,
                  "method": "unique_name", "matches": ["c1"]}, r1

    ambi_by_id = {"c1": "アルファ商事株式会社", "c2": "アルファ商事関西株式会社"}
    r2 = resolve_customer_id(normalize("アルファ商事株式会社"), ambi_by_id)
    assert r2["confirmed"] is False and r2["method"] == "ambiguous", r2

    r3 = resolve_customer_id(normalize("見知らぬ株式会社"), name_by_id)
    assert r3 == {"mf_customer_id": None, "confirmed": False, "method": "none", "matches": []}, r3

    contracts = [
        {"契約ID": "k1", "取引先": "アルファ商事株式会社"},
        {"契約ID": "k2", "取引先": "ガンマ通商株式会社", "MF顧客ID": "explicit"},
        {"契約ID": "k3", "取引先": "見知らぬ株式会社"},
    ]
    backfill = plan_customer_id_backfill(contracts, name_by_id)
    assert backfill == [{"契約ID": "k1", "取引先": "アルファ商事株式会社", "mf_customer_id": "c1"}], backfill

    unresolved = unresolved_registry_candidates(contracts, name_by_id)
    assert [u["契約ID"] for u in unresolved] == ["k3"], unresolved
    assert unresolved[0]["method"] == "none"

    idx = build_name_index({"customers": {"c1": {"name": "アルファ商事株式会社"}}})
    assert idx == {"c1": "アルファ商事株式会社"}, idx

    cand = nearby_candidates(normalize("アルファ商事株式会社"), {"c9": "アルファ商事関連株式会社"})
    assert cand and cand[0]["mf_customer_id"] == "c9", cand

    print("mfk_customer_id_resolve: self-test OK")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(_self_test())
    except AssertionError as e:
        print(f"mfk_customer_id_resolve: self-test FAILED: {e}", file=sys.stderr)
        raise SystemExit(1)
    except Exception as e:  # noqa: BLE001 — fail-closed で exit 2 (想定外エラー)
        print(f"mfk_customer_id_resolve: unexpected error: {e}", file=sys.stderr)
        raise SystemExit(2)
