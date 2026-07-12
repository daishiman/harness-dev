#!/usr/bin/env python3
# /// script
# name: resolve_company
# purpose: 入力(法人番号/会社名/住所)から gBizINFO 照会で企業を同定し、確定13桁法人番号を信頼キーとして返す(不確実は未確定保留)。
# inputs:
#   - argv: --hojin-bango <13桁> | --name <会社名> | --address <住所> [--address-provenance user|master|web]
#   - env: gBizINFO token は notion_config.get_gbizinfo_token 経由(Keychain)
# outputs:
#   - stdout: JSON {entity|candidates, certainty, source_url, attempts}
#   - exit: 0=OK / 2=precondition 不成立(token不在)
# contexts: [C, E]
# network: true
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""resolve-identity 責務の決定論層 (R1)。

入力解決の優先順位は brief key_constraints[D] の正本に従う: 法人番号 > 会社名 > 住所。
- 法人番号入力: gBizINFO 法人詳細 API で直引きし、返却された 13 桁法人番号を信頼キーに確定。
- 会社名入力: gBizINFO 検索 API で候補取得。一次照会 0 件時は決定論フォールバックで
  正規化名 → 法人格除去名 (normalize 共有正本) の順に再照会する (fallback tier1 の
  検索パターン複数化。試行履歴は attempts に記録)。自動確定は会社名+住所 2 要素一致時のみ
  (会社名のみは単一ヒットでも候補列挙へ倒し『未確定(要確認)』)。
- 住所のみ入力: 会社名を推定せず候補列挙のみ返す (対話=一覧提示 / backfill=要確認保留)。

信頼キーの正本定義 (key_constraints[C]): gBizINFO が確定返却した 13 桁法人番号のみ。
Web 検索推定経由の法人番号は確定扱いせず『ネット検索(要確認)』止まり。

信頼キー不変条項 (data-sources.md 正本): address_provenance=web (Web 検索由来の住所) では
2 要素一致が成立しても自動確定しない (候補列挙へ降格・確度上限『ネット検索(要確認)』)。
再 resolve は最大 1 回・法人番号が初回確定値と不一致なら自動確定禁止 (agent/プロンプト側契約)。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import notion_config  # noqa: E402
import normalize as normalize_module  # noqa: E402  (会社名/住所正規化の共有正本)

GBIZINFO_BASE = "https://info.gbiz.go.jp/hojin/v1/hojin"  # V1。V2 利用時は本定数を差し替え
HOJIN_BANGO_RE = re.compile(r"^\d{13}$")

# gBizINFO レスポンスのフィールド名ゆれ吸収 (V1/V2 想定)。不明フィールドは保守的に空にする。
_FIELD_HOJIN_BANGO = ("corporate_number", "corporateNumber")
_FIELD_NAME = ("name", "corporateName")
_FIELD_LOCATION = ("location", "address")

# 情報の確かさ 4 ラベル (brief key_constraints[A] 正本 / 英語 enum 禁止)
CERTAINTY_PUBLIC_VERIFIED = "公的データで確認済み"
CERTAINTY_PUBLIC_FETCHED = "公的データ取得"
CERTAINTY_WEB = "ネット検索(要確認)"
CERTAINTY_UNRESOLVED = "未確定(要確認)"


def _request(url: str, token: str) -> dict:
    """gBizINFO REST を X-hojinInfo-api-token ヘッダ付きで叩く。"""
    req = urllib.request.Request(url, headers={"X-hojinInfo-api-token": token})
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
        return json.loads(resp.read().decode("utf-8"))


def detail_page_url(hojin_bango: str) -> str:
    """gBizINFO 法人詳細ページ URL (確認用URL 任意併記用)。"""
    return f"https://info.gbiz.go.jp/hojin/ichiran?hojinBango={hojin_bango}"


def _pick(info: dict, keys: tuple[str, ...], default: str = "") -> str:
    """フィールド名ゆれ (V1/V2) を吸収して最初に非空の値を返す。不明なら default。"""
    for k in keys:
        v = info.get(k)
        if v:
            return str(v)
    return default


def _to_entity(info: dict, fallback_hojin: str = "") -> dict:
    """gBizINFO 法人情報 dict を共通 entity へ保守的にマップする (不明は空)。

    source_url は per-value provenance (gBizINFO 法人詳細ページ) で、enrich が
    source_by_field の gBizINFO 由来 3 属性 (正式名称/住所/法人番号) の検証用 URL に使う。
    旧 replay JSONL の entity に source_url が無くても、読む側は .get() 既定で後方互換。
    """
    hojin_bango = _pick(info, _FIELD_HOJIN_BANGO, fallback_hojin)
    return {
        "hojin_bango": hojin_bango,
        "official_name": _pick(info, _FIELD_NAME),
        "address": _pick(info, _FIELD_LOCATION),
        "source_url": detail_page_url(hojin_bango) if hojin_bango else "",
    }


def resolve_by_hojin_bango(hojin_bango: str, token: str) -> dict:
    """法人番号直引き。返却 13 桁を信頼キーに確定 (gBizINFO 基本情報をマップ)。"""
    if not HOJIN_BANGO_RE.match(hojin_bango):
        return {"certainty": CERTAINTY_UNRESOLVED, "reason": "法人番号が13桁でない"}
    url = f"{GBIZINFO_BASE}/{urllib.parse.quote(hojin_bango)}"
    data = _request(url, token)
    infos = data.get("hojin-infos") or []
    if not infos:
        return {
            "certainty": CERTAINTY_UNRESOLVED,
            "reason": "gBizINFOデータに該当なし(未登録または同名複数で一意特定不可)",
        }
    return {
        "entity": _to_entity(infos[0], fallback_hojin=hojin_bango),
        "certainty": CERTAINTY_PUBLIC_VERIFIED,
        "source_url": detail_page_url(hojin_bango),
    }


def name_query_patterns(name: str) -> list[tuple[str, str]]:
    """gBizINFO 会社名検索の決定論パターン列 [(pattern_id, query)] を返す (fallback tier1)。

    原文 → 正規化名 (NFKC+法人格略記正式化+空白除去) → 法人格除去名 の順。空・重複は除外。
    パターン生成の正本は normalize 共有モジュール (二重定義しない)。
    """
    raw = (name or "").strip()
    candidates = [
        ("name_raw", raw),
        ("name_normalized", normalize_module.normalize_company_name(raw)),
        ("name_legal_form_stripped", normalize_module.strip_legal_form(raw)),
    ]
    seen: set[str] = set()
    patterns: list[tuple[str, str]] = []
    for pattern_id, query in candidates:
        if query and query not in seen:
            seen.add(query)
            patterns.append((pattern_id, query))
    return patterns


def resolve_by_name(name: str, token: str, address: str | None = None,
                    address_provenance: str = "user") -> dict:
    """会社名検索。自動確定は **会社名+住所 2 要素一致時のみ**、それ未満は候補列挙のみ。

    会社名のみ (address=None) 入力は、gBizINFO 単一ヒットでも自動確定しない
    (2 要素一致が成立し得ないため候補列挙へ倒す。誤値>>空欄の非対称コスト原則)。
    住所突合は共有正本 normalize の前方一致を用いる (enrich と同一正規化)。

    検索パターン複数化 (fallback tier1): 一次照会 (原文) が 0 件のときのみ、正規化名 →
    法人格除去名で決定論再照会する (有限 1 巡・同一パターン再試行なし)。試行履歴は
    attempts ([{source, pattern, result, reject_reason}]) で返す。

    信頼キー不変条項: address_provenance="web" (Web 検索由来の住所) では 2 要素一致が
    成立しても自動確定せず、候補列挙 + 確度上限『ネット検索(要確認)』へ降格する。
    """
    attempts: list[dict] = []
    infos: list = []
    for pattern_id, query in name_query_patterns(name):
        url = f"{GBIZINFO_BASE}?{urllib.parse.urlencode({'name': query})}"
        data = _request(url, token)
        infos = data.get("hojin-infos") or []
        attempts.append({"source": "gbizinfo", "pattern": pattern_id,
                         "result": f"hit:{len(infos)}" if infos else "miss",
                         "reject_reason": ""})
        if infos:
            break  # ヒットした最初のパターンで打ち切り (決定論・有限1巡)
    # 自動確定条件 (SKILL.md チェックリスト正本): 単一ヒット かつ address が与えられ
    # かつ住所前方一致が成立、の 3 条件すべて。address=None は常に候補列挙のみ。
    if (
        len(infos) == 1
        and address is not None
        and _address_match(_pick(infos[0], _FIELD_LOCATION), address)
    ):
        if address_provenance == "web":
            # 信頼キー不変条項: Web 由来住所では自動確定しない (候補列挙へ降格)。
            return {
                "candidates": [_to_entity(i) for i in infos],
                "certainty": CERTAINTY_WEB,
                "reason": "住所が Web 検索由来のため自動確定せず候補列挙 "
                          "(信頼キー不変条項: 確度上限ネット検索(要確認)・人間裁定へ)",
                "attempts": attempts,
            }
        entity = _to_entity(infos[0])
        return {
            "entity": entity,
            "certainty": CERTAINTY_PUBLIC_VERIFIED,
            "source_url": detail_page_url(entity["hojin_bango"]),
            "attempts": attempts,
        }
    return {
        "candidates": [_to_entity(i) for i in infos],
        "certainty": CERTAINTY_UNRESOLVED,
        "reason": "会社名+住所2要素一致が不成立のため未確定 (会社名のみ・同名複数・住所不一致は候補列挙のみ)",
        "attempts": attempts,
    }


def resolve_by_address(address: str, token: str) -> dict:
    """住所のみ入力。会社名を推定せず候補列挙のみ (1:N とみなす)。

    会社名候補の Web 検索は Claude が goal-seek ループで実施する責務 (Python は推定しない)。
    """
    return {
        "candidates": [],
        "certainty": CERTAINTY_UNRESOLVED,
        "reason": "住所のみ入力は会社名1:N。推定せず候補列挙(対話=一覧提示 / backfill=要確認保留)",
    }


def _address_match(a: str, b: str) -> bool:
    """軽量住所突合 (共有正本 normalize の前方一致に委譲)。"""
    return normalize_module.address_prefix_match(a, b)


def main() -> int:
    ap = argparse.ArgumentParser(description="resolve company identity via gBizINFO")
    ap.add_argument("--hojin-bango")
    ap.add_argument("--name")
    ap.add_argument("--address")
    ap.add_argument("--address-provenance", choices=("user", "master", "web"), default="user",
                    help="住所の出所。web は信頼キー不変条項により自動確定しない (候補列挙へ降格)")
    args = ap.parse_args()

    token = notion_config.get_gbizinfo_token(notion_config.load_config())
    if not token:
        sys.stderr.write(
            "[resolve_company] FATAL: gBizINFO トークン不在 (Keychain "
            "'gbizinfo-api-token.<keychain-prefix>')。precondition gate fail-closed。\n"
        )
        return 2

    try:
        # 優先順位: 法人番号 > 会社名 > 住所 (key_constraints[D] 正本)
        if args.hojin_bango:
            result = resolve_by_hojin_bango(args.hojin_bango, token)
        elif args.name:
            result = resolve_by_name(args.name, token, args.address,
                                     address_provenance=args.address_provenance)
        elif args.address:
            result = resolve_by_address(args.address, token)
        else:
            sys.stderr.write("usage: --hojin-bango | --name | --address のいずれか必須\n")
            return 2
    except (urllib.error.URLError, TimeoutError) as e:
        # 縮退: 外部障害は要確認保留で返す(誤値混入回避)
        result = {"certainty": CERTAINTY_UNRESOLVED, "reason": f"gBizINFO照会失敗: {e}"}

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
