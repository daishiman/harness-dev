#!/usr/bin/env python3
"""請求確認シート(ユーザー入力) → 契約マスタ(AI自動生成) の純関数 + 冪等 upsert。

運用モデルの核心: 担当者は『請求確認シート』(取引先 / 商品 / 確認内容(自由文) / 契約開始日 /
契約終了月) を 1 明細 = 1 行で入力する。本モジュールはその 95 行クラスの行群を distinct
契約へ集約し、DB1『契約マスタ』のレコード(契約ID/取引先/商品/エンドクライアント名/現行単価/
契約開始日/契約終了月/支払サイクル/ステータス/期待明細数/備考/請求確認シートID)を生成する。

**支払サイクルはユーザーが入力しない** — 確認内容(自由文)+商品+MF掛け払い実績から自動推定する
(検証フェーズの AI 生成 inventory に依存していた load_db1.py のロジックを、再利用可能な推定内蔵の
純関数へ昇華した)。推定の正答(2606 実データ)= 月払い45 / 年間払い15 / 年間一括更新3 / 分割1 /
従量(都度)1 / 保留3 = 計68契約。

engine(lib/mfk_reconcile.py) の正規化/抽出ヘルパ(normalize / parse_amounts / extract_names /
category / ym_int) と cadence 定数(lib/mfk_invoice_diff.py)を再利用し、語彙を一本化する。
副作用は upsert_master の Notion 書込のみ(req は DI で差し替え可・テストは mock req)。
"""
from __future__ import annotations

import os
import re
import sys

from mfk_invoice_diff import (
    CADENCE_ANNUAL,
    CADENCE_ANNUAL_RENEWAL,
    CADENCE_METERED,
    CADENCE_MONTHLY,
    CADENCE_ONESHOT,
    CADENCE_SPLIT,
)
from mfk_reconcile import (
    category,
    extract_names,
    normalize,
    parse_amounts,
    ym_int,
)

# C02 (MF顧客ID解決 SSOT) は scripts/ 配下。名前→ID 解決は再発明せずここへ一本化する。
_SCRIPTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts")
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from mfk_customer_id_resolve import build_name_index, resolve_customer_id  # noqa: E402

# 商品 canon の正規 4 値(請求確認シートの 商品 列の表記ゆれを束ねる)。
PROD_BIZ = "チイキズカン業務委託費"            # 月次業務委託(原則 月払い)
PROD_THINKTANK = "100億ThinkTank利用料"        # ThinkTank 利用料(原則 年間一括更新)
PROD_RIYO_Y1 = "チイキズカン利用料（1年目）"   # 初年度利用料(原則 年間払い)
PROD_RIYO_Y2 = "チイキズカン利用料（2年目以降）"  # 2年目以降利用料(原則 月払い)

# 業務委託費の月額下限。これ未満の固定額は月次リテイナとして不自然で『保留(要確認)』へ倒す
# (2606 実データ: 正当な月払い業務委託費の最小は ¥70,000、保留候補は ¥41,000)。
_BIZ_MONTHLY_FLOOR = 50000


def shohin_canon(raw: str) -> str:
    """請求確認シートの 商品 文字列を正規 4 値へ写像。未知はカッコ前を strip して返す。"""
    s = raw or ""
    if "業務委託費" in s:
        return PROD_BIZ
    if "ThinkTank" in s or "100億" in s:
        return PROD_THINKTANK
    if "（2年目以降）" in s or "(2年目以降)" in s:
        return PROD_RIYO_Y2
    if "（1年目）" in s or "(1年目)" in s:
        return PROD_RIYO_Y1
    return s.split("(")[0].split("（")[0].strip()


def _clean_endclient(row: dict) -> str:
    """確認内容/取引先からエンドクライアント名候補を 1 つ返す(無ければ '')。

    extract_names の候補から、取引先自身と、コロン/円/スラッシュを含む偽候補
    (例『月額払い：150,000円』を人名と誤抽出する事故)を除いた先頭を採る。数字だけを含む
    候補(例『2H株式会社』)は正当な法人名なので除外しない。
    """
    tnorm = normalize(row.get("取引先", ""))
    for cand in extract_names(row.get("取引先", ""), row.get("確認内容", "")):
        if normalize(cand) == tnorm:
            continue
        if re.search(r"[：:円／/]", cand):
            continue
        return cand
    return ""


def _recurring_amount(content: str):
    """確認内容から「契約識別 / 現行単価」に使う代表金額を返す(無ければ None)。

    『月額/月払い』直後の金額があればそれ(=継続単価。初期費用と月額が併記された行でも
    月額側を採り、初期費用で契約が分裂するのを防ぐ)。無ければ parse_amounts の主値先頭。
    """
    m = re.search(r"(?:月額|月払い)[^0-9０-９]*([0-9０-９][0-9０-９,，]*)\s*円", content or "")
    if m:
        raw = m.group(1)
        for z, h in zip("０１２３４５６７８９", "0123456789"):
            raw = raw.replace(z, h)
        return int(raw.replace(",", "").replace("，", ""))
    primary, _ = parse_amounts(content)
    return primary[0] if primary else None


# ---------------------------------------------------------------------------
# MF 実績シグナル (支払サイクル推定の補助入力)
# ---------------------------------------------------------------------------
def build_mf_signals(mf_json: dict) -> dict:
    """MF掛け払い JSON を {normalize(取引先): signals} へ畳む(参照専用・副作用なし)。

    signals = {has_split, riyo_lump, riyo_monthly}:
      has_split    : desc に『分割』を含む注記がある(=年額の分割払い実態)。
      riyo_lump    : 利用料(category=='riyo')明細が年額一括らしい(qty>=10 or amount>=900000)。
      riyo_monthly : 利用料明細が『月分』ラベルの月次発行(qty12 一括でなく毎月請求)。
    desc の注記行(amount=None)も has_split 判定のため走査する(build_mf_index は落とすため
    ここでは raw を直接見る)。
    """
    out: dict = {}
    for cid, cust in (mf_json.get("customers") or {}).items():
        key = normalize(cust.get("name") or cid)
        sig = out.setdefault(key, {"has_split": False, "riyo_lump": False, "riyo_monthly": False})
        for ln in cust.get("lines", []):
            desc = ln.get("desc") or ""
            qty = ln.get("qty")
            amt = ln.get("amount")
            if "分割" in desc:
                sig["has_split"] = True
            if category(desc) == "riyo" and amt is not None:
                if (qty and qty >= 10) or amt >= 900000:
                    sig["riyo_lump"] = True
                elif "月分" in desc:
                    sig["riyo_monthly"] = True
    return out


def _as_signals(mf_index):
    """mf_index を {norm取引先: signals} へ解決。

    None → {}。raw MF JSON({'customers': ...}) → build_mf_signals で変換。
    既に signals dict ならそのまま。柔軟に受けて呼出側の負担を減らす。
    """
    if not mf_index:
        return {}
    if "customers" in mf_index:
        return build_mf_signals(mf_index)
    return mf_index


def _explicit_mf_customer_id(rows) -> str:
    """シート/DB由来の MF 顧客IDを返す。列名ゆれはここで吸収する。"""
    for row in rows:
        for key in ("MF顧客ID", "顧客ID", "customer_id", "mf_customer_id"):
            v = (row.get(key) or "").strip()
            if v:
                return v
    return ""


def _mf_customer_id_from_mf(tnorm: str, mf_index) -> str:
    """raw MF JSON から取引先名で一意に解決できる customer_id を返す。曖昧/無一致なら空。

    名前→ID 解決は scripts/mfk_customer_id_resolve.py(C02)へ一本化する(名寄せ境界=
    mfk_reconcile.normalize/_company_match の再発明を避ける)。
    """
    if not mf_index or "customers" not in mf_index:
        return ""
    name_by_id = build_name_index(mf_index)
    return resolve_customer_id(tnorm, name_by_id)["mf_customer_id"] or ""


def _mf_customer_id_for(rows, tnorm: str, mf_index) -> str:
    explicit = _explicit_mf_customer_id(rows)
    if explicit:
        return explicit
    return _mf_customer_id_from_mf(tnorm, mf_index)


# ---------------------------------------------------------------------------
# 契約期間 (確認内容『期間：A〜B』) 抽出
# ---------------------------------------------------------------------------
# ユーザー確定(2026-06-26): 確認内容に書かれた『期間：A〜B』= 作業開始から1年の契約期間。
# この期間が書かれた契約は『作業開始から1年間=年間払い(初年度一括→翌年月額)、以降=月払い』。
# 期間の有無を支払サイクル判定の一次シグナルにし、開始日 A を契約開始日の補完源にする。
# 終端 B は使わない — 年周期=ANNUAL_MONTHS(12)固定で _classify_annual が契約開始日からの
# elapsed により『start月=年額期待 / 途中月=対象外(SUPPRESS_ANNUAL) / 12月後=月額移行』を判定する
# (B が typo の行 例『2026/6/5〜2026/6/4』に依存せず堅牢)。
_PERIOD_RE = re.compile(r"期間[：:]\s*(\d{4})\s*[/／年]\s*(\d{1,2})\s*(?:[/／月]\s*(\d{1,2}))?")
# YYMM〜YYMM 形式 (例『期間：2606〜2608』)。4桁の直後が範囲記号(〜～~)であることで
# YYYY/M/D(『2026/6/22』=直後が/)と識別する。ユーザー確定(2026-06-27): 開始 2606 → 月初
# 2026-06-01 として契約開始日へ反映する(1日付)。
_PERIOD_YYMM_RE = re.compile(r"期間[：:]\s*(\d{2})(\d{2})\s*[〜～~]")


def has_period(content: str) -> bool:
    """確認内容に『期間：YYYY/M(/D)』形式の契約期間(=作業開始から1年の年間契約)が書かれているか。

    年間払い判定の一次シグナル。YYMM〜YYMM(例 2606〜2608)は短期レンジでありうるため年間化
    トリガーには含めない(契約開始日の補完だけ parse_period_start が行う)。
    """
    return bool(_PERIOD_RE.search(content or ""))


def parse_period_start(content: str):
    """『期間：A〜B』の開始日 A を ISO(YYYY-MM-DD) で返す。無ければ None。

    対応形式:
      - YYYY/M/D・YYYY/M (年月日/年月): 日が無ければ月初。
      - YYMM (例『期間：2606〜2608』): 開始 2606 → 2026-06-01 (月初・1日付)。
    """
    m = _PERIOD_RE.search(content or "")
    if m:
        y, mo = int(m.group(1)), int(m.group(2))
        d = int(m.group(3)) if m.group(3) else 1
        if 1 <= mo <= 12 and 1 <= d <= 31:
            return f"{y:04d}-{mo:02d}-{d:02d}"
    m2 = _PERIOD_YYMM_RE.search(content or "")
    if m2:
        yy, mo = int(m2.group(1)), int(m2.group(2))
        if 1 <= mo <= 12:
            return f"20{yy:02d}-{mo:02d}-01"
    return None


# ---------------------------------------------------------------------------
# 支払サイクル推定 (優先順ルール)
# ---------------------------------------------------------------------------
def infer_cycle(content: str, product: str, amount, sig: dict):
    """確認内容 + 商品canon + MFシグナルから支払サイクルを推定する。判別不能は None(=保留)。

    優先順(上から評価):
      1. 『/件』        → 従量(都度)           (件数次第で固定サイクルなし)
      2. 『分割』明記 or MF分割注記 → 分割
      3. 確認内容が空 / 『未締結』『未確定』 → None(保留)
      4. 『期間：A〜B』明記(作業開始から1年の契約) → 年間系。ユーザー確定2026-06-26。
         『月額』表記より優先 = ThinkTank 等で月額払い表記と期間が併記される行を年間へ正す。
         商品で出し分け: ThinkTank → 年間一括更新(毎年更新で再び年額) / それ以外 → 年間払い
         (初年度一括→翌年月額)。ただし商品『利用料(2年目以降)』は定義上すでに初年度経過後 =
         月払いフェーズのため期間に依らず月払い(=次のルール5へ素通し)。_classify_annual /
         _classify_annual_renewal が契約開始日(=期間開始)の elapsed で start月/途中月/12月後を判定。
      5. 『月額』『月払い』明記 or 商品(2年目以降) → 月払い
      6. 商品 ThinkTank → 年間一括更新           (ThinkTank は更新時も一括再請求 type(a))
      7. 商品(1年目): MF利用料が年額一括 → 年間払い / MF利用料が月次 → 月払い / それ以外 → 年間払い
      8. 商品 業務委託費: 金額なし or 月額下限未満 → None(保留) / それ以外 → 月払い
      9. fallback: 金額あり → 月払い / なし → None(保留)
    """
    c = content or ""
    sig = sig or {}
    if "/件" in c or "／件" in c:
        return CADENCE_METERED
    if "分割" in c or sig.get("has_split"):
        return CADENCE_SPLIT
    if (not c.strip()) or "未締結" in c or "未確定" in c:
        return None
    if has_period(c) and product != PROD_RIYO_Y2:
        return CADENCE_ANNUAL_RENEWAL if product == PROD_THINKTANK else CADENCE_ANNUAL
    if "月額" in c or "月払い" in c or product == PROD_RIYO_Y2:
        return CADENCE_MONTHLY
    if product == PROD_THINKTANK:
        return CADENCE_ANNUAL_RENEWAL
    if product == PROD_RIYO_Y1:
        if sig.get("riyo_lump"):
            return CADENCE_ANNUAL
        if sig.get("riyo_monthly"):
            return CADENCE_MONTHLY
        return CADENCE_ANNUAL
    if product == PROD_BIZ:
        if amount is None or amount < _BIZ_MONTHLY_FLOOR:
            return None
        return CADENCE_MONTHLY
    return CADENCE_MONTHLY if amount is not None else None


# ---------------------------------------------------------------------------
# 日付 / ステータス
# ---------------------------------------------------------------------------
def to_date(raw):
    """YYMM / ISO(YYYY-MM-DD) / YYYY/M/D / YYYY/M を ISO(YYYY-MM-DD)へ正規化。不正は None。"""
    s = (raw or "").strip()
    if not s:
        return None
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        return s
    m = re.fullmatch(r"(\d{4})-(\d{1,2})", s)  # YYYY-MM
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-01"
    m = re.match(r"^(\d{4})/(\d{1,2})/(\d{1,2})", s)  # YYYY/M/D
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    m = re.fullmatch(r"(\d{4})/(\d{1,2})", s)  # YYYY/M
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-01"
    if re.fullmatch(r"\d{4}", s) and 1 <= int(s[2:]) <= 12:  # YYMM (例 2606 → 2026-06-01)
        return f"20{s[:2]}-{s[2:]}-01"
    return None


def _end_yymm(row: dict, content: str):
    """契約終了月 (YYMM) は明示列だけを採用する。無ければ None。

    確認内容の自由文にある『（2605終了）』等は、請求メモ・明細単位の終了・Slack 転記を含み、
    正式な契約終了情報とは限らない。ここから契約終了月を推定すると、根拠のない終了扱いで
    請求漏れを隠すため採用しない。
    """
    col = (row.get("契約終了月") or "").strip()
    if re.fullmatch(r"\d{4}", col):
        return col
    return None


def _status(cycle, end_yymm, content: str, target_ym: str) -> str:
    """ステータスを決定: 終了(契約終了月<=対象月) > 保留(サイクルNone/未締結) > 有効。"""
    if end_yymm is not None:
        ev, tv = ym_int(end_yymm), ym_int(target_ym)
        if ev is not None and tv is not None and ev <= tv:
            return "終了"
    if cycle is None or "未締結" in (content or ""):
        return "保留"
    return "有効"


# ---------------------------------------------------------------------------
# 集約 → 契約レコード生成 (純関数・正本)
# ---------------------------------------------------------------------------
def build_contracts(sheet_rows, mf_index=None, target_ym: str = "2606"):
    """請求確認シート行群 → distinct 契約レコードのリスト(純関数・副作用なし)。

    集約キー = (normalize(取引先), normalize(エンドクライアント), 代表金額)。商品の表記ゆれ
    (同一エンドクライアント/同額で 業務委託費⇄ThinkTank が混在)は同一契約へ束ね、初期費用と
    月額が別額の行は月額側へ寄せる(_recurring_amount)。ただし集約元の商品 canon 集合は
    内部フィールド _source_products に保持し、後段のMF明細カテゴリ照合で代表商品だけに
    潰さない (mfk_reconcile._expected_categories が読む)。期待明細数 = 集約元の行数。

    各契約: 契約ID(取引先/エンドクライアント/商品canon[#枝番]) / 取引先 / 商品(canon) /
    エンドクライアント名 / 現行単価 / 契約開始日 / 契約終了月 / 請求確認シートID(代表 page_id) /
    備考(確認内容原文) / 支払サイクル(推定・保留は None) / ステータス / 期待明細数。

    mf_index: None / raw MF JSON / build_mf_signals 済み dict のいずれか(_as_signals が吸収)。
    """
    signals = _as_signals(mf_index)

    # 1) 集約
    buckets: dict = {}
    order = []
    for row in sheet_rows:
        content = row.get("確認内容", "") or ""
        ec = _clean_endclient(row)
        amount = _recurring_amount(content)
        key = (normalize(row.get("取引先", "")), normalize(ec), amount)
        if key not in buckets:
            buckets[key] = []
            order.append(key)
        buckets[key].append(row)

    # 2) (取引先, エンドクライアント, 商品canon) 衝突に枝番を割り当てる準備
    base_counts: dict = {}
    bucket_meta = {}
    for key in order:
        rows = buckets[key]
        canons = [shohin_canon(r.get("商品", "")) for r in rows]
        product = PROD_BIZ if PROD_BIZ in canons else _majority(canons)
        ec = _clean_endclient(rows[0])
        base = (key[0], normalize(ec), product)
        base_counts[base] = base_counts.get(base, 0) + 1
        bucket_meta[key] = (product, ec, base)

    # 3) レコード生成
    seen_base: dict = {}
    contracts = []
    for key in order:
        rows = buckets[key]
        product, ec, base = bucket_meta[key]
        amount = key[2]
        torihiki = (rows[0].get("取引先") or "").strip()
        tnorm = key[0]

        contents = []
        source_products = []
        for r in rows:
            t = (r.get("確認内容") or "").strip()
            if t and t not in contents:
                contents.append(t)
            p = shohin_canon(r.get("商品", ""))
            if p and p not in source_products:
                source_products.append(p)
        content_all = " ".join(contents)

        cycle = infer_cycle(content_all, product, amount, signals.get(tnorm))
        # 契約開始日: 列が空でも確認内容『期間：A〜B』の開始日 A で補完する(年払い判定の
        # elapsed 起点。年払い契約の契約開始日空欄 → REVIEW_DATA_INCOMPLETE 化を縮減)。
        start = _first(rows, "契約開始日", to_date) or parse_period_start(content_all)
        # ユーザー確定(2026-06-27): 期間も契約開始日も無い契約は月払い前提(毎月必ず請求が発生し
        # MF に反映されるべき)。時間アンカーが無いと年間/分割等は elapsed 算出不能で
        # REVIEW_DATA_INCOMPLETE(要確認)へ落ち、確実に発行される月次請求が埋もれる。アンカー
        # 無しの非月払い推定(従量・保留は各専用判定に残すため除外)は月払いへ降格する。
        if start is None and cycle not in (CADENCE_METERED, CADENCE_MONTHLY, None):
            cycle = CADENCE_MONTHLY
        end_yymm = _end_yymm_for(rows, content_all)
        end_date = to_date(end_yymm) if end_yymm else None
        status = _status(cycle, end_yymm, content_all, target_ym)
        sheet_id = next((r.get("page_id") for r in rows if r.get("page_id")), None)
        # 契約を構成する当月シート全行の page_id(畳み込み元)。シート『判定』書き戻しが
        # 代表1件でなく全行へ投影するために保持する。請求確認シートID(代表1件)は DB1 監査用。
        sheet_row_ids = [r.get("page_id") for r in rows if r.get("page_id")]
        mf_customer_id = _mf_customer_id_for(rows, tnorm, mf_index)

        # 枝番: 同一 (取引先, エンドクライアント, 商品) が複数契約に割れた時のみ付与。
        if base_counts[base] > 1:
            seen_base[base] = seen_base.get(base, 0) + 1
            suffix = f"#{seen_base[base]}"
        else:
            suffix = ""
        cid = "/".join([x for x in [torihiki, ec, product] if x]) + suffix

        contract = {
            "契約ID": cid,
            "取引先": torihiki,
            "商品": product,
            "エンドクライアント名": ec,
            "現行単価": amount,
            "契約開始日": start,
            "契約終了月": end_date,
            "請求確認シートID": sheet_id,
            "備考": content_all,
            "支払サイクル": cycle,
            "ステータス": status,
            "期待明細数": len(rows),
            # `_` 接頭 = DB1 へ投入しない派生・非永続の内部フィールド (SSOT は請求確認シート)。
            #   _sheet_row_ids   : シート『判定』書き戻しを代表1件でなく集約元全行へ投影する用。
            #   _source_products : 集約で代表商品(商品)に潰れる前の商品 canon 集合。
            #                      mfk_reconcile._expected_categories が商品照合のため読む。
            # 不変条件: contract は毎 run シートから再導出される前提。DB1 由来で contract を
            #   再構成する経路を将来足す場合、_source_products は DB1 に無いためシートから
            #   再導出が必須 (さもなくば商品照合が代表商品へ退化する)。
            "_sheet_row_ids": sheet_row_ids,
            "_source_products": source_products,
        }
        if mf_customer_id:
            contract["MF顧客ID"] = mf_customer_id
        contracts.append(contract)
    return contracts


def _majority(items):
    """最頻値を返す(同数なら先頭)。ただし空文字は実商品名(非空)へ劣後させる。

    集約キーが (取引先, エンドクライアント, 金額) のため、商品空のメモ行(連絡先変更等で
    金額なし)が、同一取引先・EC空・金額None の実商品行と同一バケツに入ることがある。
    素朴な多数決だと同数時に空文字を拾い product='' → Notion の空 select 拒否
    (validation_error) を招くため、非空を優先する (bool(x) を第一キーにする)。
    """
    counts: dict = {}
    for x in items:
        counts[x] = counts.get(x, 0) + 1
    return max(counts.items(), key=lambda kv: (bool(kv[0]), kv[1]))[0]


def _first(rows, field, conv):
    for r in rows:
        v = conv(r.get(field, ""))
        if v:
            return v
    return None


def _end_yymm_for(rows, content_all):
    for r in rows:
        y = _end_yymm(r, content_all)
        if y:
            return y
    return None


# ---------------------------------------------------------------------------
# Notion 冪等 upsert (I/O・req は DI)
# ---------------------------------------------------------------------------
def _to_props(contract: dict) -> dict:
    """契約レコードを Notion property 形式へ整形。空値はプロパティ自体を省略する。"""
    props: dict = {
        "契約ID": {"title": [{"text": {"content": (contract.get("契約ID") or "")[:1900]}}]},
        "取引先": {"rich_text": [{"text": {"content": contract.get("取引先") or ""}}]},
        # 商品空は Notion の空 select 拒否(validation_error: select.id undefined)を招くため
        # 『未分類』へ倒す(全行空のメモ的バケツでも投入を止めない最終防御。通常は _majority が
        # 非空商品を選ぶためここには到達しない)。
        "商品": {"select": {"name": contract.get("商品") or "未分類"}},
        "ステータス": {"select": {"name": contract.get("ステータス") or "有効"}},
        "期待明細数": {"number": int(contract.get("期待明細数") or 0)},
        "備考": {"rich_text": [{"text": {"content": (contract.get("備考") or "")[:1900]}}]},
    }
    ec = contract.get("エンドクライアント名")
    if ec:
        props["エンドクライアント名"] = {"rich_text": [{"text": {"content": ec}}]}
    if contract.get("支払サイクル"):
        props["支払サイクル"] = {"select": {"name": contract["支払サイクル"]}}
    if contract.get("現行単価") is not None:
        props["現行単価"] = {"number": int(contract["現行単価"])}
    if contract.get("契約開始日"):
        props["契約開始日"] = {"date": {"start": contract["契約開始日"]}}
    if contract.get("契約終了月"):
        props["契約終了月"] = {"date": {"start": contract["契約終了月"]}}
    if contract.get("請求確認シートID"):
        props["請求確認シートID"] = {"rich_text": [{"text": {"content": contract["請求確認シートID"]}}]}
    return props


def _existing_contract_ids(db1_id: str, token: str, req) -> dict:
    """DB1 を全件 query し {契約ID: page_id} を返す(冪等 upsert の既存判定)。

    pagination が同一 page を重複返却することがある (cursor 境界で起きる) ため、page_id で
    重複除去し、既に見た page は再処理しない。これにより重複/stale な契約ID で同じページが
    二重登録されるのを防ぐ。
    """
    out: dict = {}
    seen_pids: set = set()
    cursor = None
    while True:
        body = {"page_size": 100}
        if cursor:
            body["start_cursor"] = cursor
        res = req("POST", f"/databases/{db1_id}/query", token, body)
        for page in res.get("results", []):
            pid = page.get("id")
            if pid in seen_pids:
                continue  # pagination 重複: 同一 page は 1 度だけ処理する。
            seen_pids.add(pid)
            title = (page.get("properties", {}).get("契約ID", {}) or {}).get("title") or []
            cid = "".join(
                (t.get("plain_text") or (t.get("text") or {}).get("content") or "") for t in title
            )
            if cid:
                out[cid] = pid
        if not res.get("has_more"):
            break
        cursor = res.get("next_cursor")
    return out


def upsert_master(contracts, db1_id: str, token: str, req=None) -> dict:
    """契約レコードを 契約ID キーで DB1 へ冪等 upsert。{created, updated, failed} を返す。

    既存(同一 契約ID)は PATCH で更新、無ければ POST で作成。req は DI(既定
    notion_invoice_sink._req = notion_transport._req の re-export)でテスト時に mock 差し替え可能。
    既定 req は書き込み系で自動的にレート間隔を挟む (notion_transport._write_gap)。

    堅牢化 (2026-06-26 大量書込実証):
      - 各契約の upsert を try/except で囲み、**個別失敗は他をブロックせず** failed に記録して
        続行する (1 件の HTTP400/timeout で全 68 契約が落ちるのを防ぐ)。
      - failed = [{"契約ID": cid, "error": "..."}]。空なら []。
      - 備考/取引先/エンドクライアント等の rich_text は改行(\n)を保持して投入する
        (_to_props が content にそのまま入れ 1900 字で安全に切る)。
    """
    if req is None:
        from notion_invoice_sink import _req as req  # 遅延 import(import 時の連鎖を避ける)
    existing = _existing_contract_ids(db1_id, token, req)
    created = updated = 0
    failed: list = []
    for contract in contracts:
        cid = contract.get("契約ID")
        try:
            props = _to_props(contract)
            page_id = existing.get(cid)
            if page_id:
                req("PATCH", f"/pages/{page_id}", token, {"properties": props})
                updated += 1
            else:
                res = req("POST", "/pages", token,
                          {"parent": {"database_id": db1_id}, "properties": props})
                existing[cid] = (res or {}).get("id")
                created += 1
        except Exception as e:  # noqa: BLE001  個別失敗は記録して継続 (全体を止めない)。
            failed.append({"契約ID": cid, "error": str(e)[:200]})
    return {"created": created, "updated": updated, "failed": failed}
