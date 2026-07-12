#!/usr/bin/env python3
# /// script
# name: mfk_period_report
# purpose: 既存 lib/mfk_reconcile.py の per-月 verdict を入力に取り、前月↔今月の発行状態遷移
#          だけを分類する薄い差分エンジン。取引先×商品を突合し 状態 (継続発行 / 新規・年→月切替 /
#          対象外(元々請求なし) / 前月あり今月なし / 継続漏れ=両月未発行だが今月GAP) へ分類し、前月あり今月なしは既存 verdict
#          (SUPPRESS_ENDED / SUPPRESS_ANNUAL / MATCH_ANNUAL / REVIEW_ENDED_NO_BASIS) を一次源に
#          正常な非請求事情の有無を確認して発行漏れ候補(要対応)を検出する。自由文の終了根拠は
#          再パースせず既存 verdict を消費するのみ (終了根拠判定 SSOT=mfk_reconcile)。
# inputs:
#   - argv: --curr-verdicts FILE (今月=target 請求対象月の per-月 verdict JSON)
#           --prev-verdicts FILE (先月=target-1ヶ月の per-月 verdict JSON)
#           --lookback-12mo FILE (差分該当取引先のみの12ヶ月発行履歴・任意)
#           --contract-end FILE  (契約終了月データ・任意)
#           --target-month YYMM  (対象月・省略時は curr-verdicts の target_month → 実行日から導出)
# outputs:
#   - stdout: 分類済みレポート行 JSON (list)。各行キー: customer / amount / prev_amount /
#             gap_check / period_diff / product / comment / contract_id / target_month
#   - stderr: violation 説明
#   - exit: 0=正常 / 1=分類上の要確認(要対応)あり / 2=fail-closed(入力欠落・読込失敗)
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: [mfk_reconcile]
# requires-python: ">=3.11"
# ///
"""前月↔今月の発行状態遷移を分類する薄い差分エンジン (C03)。

本スクリプトは新しい照合ロジックを持たない。既存 lib/mfk_reconcile.py が算出した per-月
verdict (MATCH_* / SUPPRESS_* / GAP / REVIEW_*) を入力に取り、前月集合と今月集合の
**発行状態遷移だけ** を分類する (SSOT 尊重: 終了根拠の再パースや金額照合の再発明はしない)。

『今月』は実行日カレンダー月ではなく直近締め済みの請求対象月。例: 2026-07-02 実行なら
今月=2026-06分(2606)・先月=2026-05分(2605)。resolve_target_months がこの対象月決定を担う。

分類ロジック (取引先×商品を突合し発行状態で分類):
  今月あり×前月あり → 継続発行 (正常)。全行 emit する (全請求書一覧を成す)。
  今月あり×前月なし → 新規/年→月切替。今月 verdict が年契約正常 (MATCH_ANNUAL/SUPPRESS_ANNUAL)
                    なら reconcile 判定済みとして即正常 (C3・lookback 不要)。それ以外は 12ヶ月前の
                    年契約一括が月額切替した可能性を lookback で補強し、裏付けなしは要確認。
  今月なし×前月あり → 正常な非請求事情 (年契約期間内 / トライアル完了 / 契約終了) の有無を
                    確認し、該当なしを発行漏れ候補(要対応)として分類する。
  今月なし×前月なし → 原則 対象外 (元々請求なし)。emit しない。ただし今月 curr が実 GAP
                    verdict の「継続漏れ」(前月も今月も未発行だが mfk_reconcile が今月を発行漏れ
                    と判定) は真の漏れなので要対応として残す (漏れを隠さない安全側)。
                    正常抑制 (SUPPRESS_* / 年契約 / 契約完了 / トライアル) や curr 不在は非 emit を維持。

正常事情の一次情報源 (自由文を再パースしない = SSOT 尊重):
  契約完了 : 既存 verdict SUPPRESS_ENDED を消費するのみ。C03 は確認内容/備考を再パースしない。
             構造化列『契約終了月』に値があっても、既存判定が REVIEW_ENDED_NO_BASIS
             (終了根拠 has_end_basis なし) なら抑制せず発行漏れ候補(要対応)として残す
             (mfk_reconcile の漏れ隠蔽防止 安全弁を保全)。
  年契約   : 既存 verdict SUPPRESS_ANNUAL / MATCH_ANNUAL を一次源にする。年契約の非請求月は
             reconcile が今月行を出さず curr=None になるため、curr が非情報的なときは先月
             (prev) の MATCH_ANNUAL / SUPPRESS_ANNUAL または 12ヶ月履歴の年契約一括を一次
             トリガーにして年契約周期の非請求月を正常へ分類する (GAP-C05-ANNUAL-STOPPED)。
             12ヶ月ルックバックは根拠コメント補強にも使い既存判定を上書きしない
             (precedence: 既存 verdict > 遡り推定)。年契約 verdict は識別的なので prev 参照で
             正常/漏れを分離できるが、隔月/単発 (prev=MATCH_MONTHLY 非識別的) には prev.verdict
             同型化を適用しない (真の月次漏れと衝突するため)。⑤隔月/単発の curr=None の根治は
             入力層 curr-present 化 (reconcile の SUPPRESS_OFFMONTH/ONESHOT を --curr-verdicts に
             含める) を要し、これは **C05 決定論 producer `mfk_verdict_export.py` が呼び出し側で
             実装済み** (reconcile().rows 全件=SUPPRESS_* 含むを persist・GAP-R1-COLLECT-CURR-PRESENT
             根治済み)。準拠経路 (run-mf-invoice-report R1-collect→C05) では⑤ curr=None は起きない。
             本 script は汎用 CLI で呼び出し元の curr-present 化を保証できないため、非準拠 caller が
             SUPPRESS_* を落として curr=None を渡した場合の**防御的 fallback** として下記の安全側
             (⑥要対応=漏れを隠さない側) 分岐を残す (curr が来ていれば正しく分類される)。
  トライアル: canon 前の生商品名 or MF 明細 desc を参照して判定する (shohin_canon の4値正規化後は
             『トライアル』信号が消えるため、正規化前の生名を見る)。

突合キーは既存 mfk_reconcile.normalize / extract_names を再利用して取引先名の表記揺れを吸収する
(自作正規化を発明しない)。最終分類とコメント根拠は取引先×商品単位で照合し、同一取引先・同一商品に
複数契約があるときのみ contract_id またはエンドクライアント名 (C5: 代理店が複数エンドクライアント
契約を contract_id 無しで持つケース) を disambiguator に使う。12ヶ月遡りは差分該当取引先のみに限定
(呼出側が --lookback-12mo に差分該当分だけを渡す前提。API 負荷最小化)。
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import sys
import unicodedata
from collections import defaultdict

# 既存 lib を単一 SSOT として消費する (normalize/extract_names/ym_int を再利用)。
# CLI 単体起動でも lib を解決できるよう path を通す (pytest.ini は既に lib を pythonpath 済)。
_HERE = os.path.dirname(os.path.abspath(__file__))
_PLUGIN_ROOT = os.path.dirname(_HERE)
_LIB = os.path.join(_PLUGIN_ROOT, "lib")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import mfk_reconcile as R  # noqa: E402

# C05: MF実績 carrier の供給状態語彙 (SUPPLY_ACTIVE 等) を SSOT 参照する (文字列リテラルのドリフト防止)。
# mfk_period_report は scripts/ 配下ゆえ mfk_actuals を同ディレクトリから import できる。
import mfk_actuals as R_ACTUALS  # noqa: E402


# ============================================================================
# 発行状態の語彙 (SSOT)
# ============================================================================
# 発行状態遷移の 4 分類 (内部コード)。
STATE_CONTINUED = "continued"      # 今月あり×前月あり = 継続発行 (正常)
STATE_NEW = "new_or_switch"        # 今月あり×前月なし = 新規/年→月切替
STATE_STOPPED = "stopped"          # 今月なし×前月あり = 非請求事情確認 → 発行漏れ候補
STATE_NONE = "none"                # 今月なし×前月なし = 対象外 (非 emit)

# 『発行あり(有効な MF 請求が当月に存在)』を表す既存 verdict 集合。これらは MF 側に有効供給
# (billing/evidence) がある = その月に発行された。SUPPRESS_* / GAP / REVIEW_ENDED_NO_BASIS /
# REVIEW_CANCELED 等は発行なし。判定は既存 verdict を消費するのみ (再照合しない)。
ISSUED_VERDICTS = frozenset({
    "MATCH_MONTHLY", "MATCH_ANNUAL", "MATCH_ENDED_FINAL",
    "REVIEW_AMOUNT_TYPO", "REVIEW_AMOUNT_MISMATCH",
    "REVIEW_ENDED_BUT_BILLED", "REVIEW_QTY_MISMATCH",
})

# 年契約期間内の正常抑制 (前月あり今月なしの一次源)。既存判定を上書きしない。
ANNUAL_NORMAL_VERDICTS = frozenset({"SUPPRESS_ANNUAL", "MATCH_ANNUAL"})

# その他の SUPPRESS_* (ENDED/ANNUAL 以外) の人間可読ラベル。verdict-mapping SSOT が
# SUPPRESS_*→対象外 と定めるため、これらは再判定せず『対象外=正常』として消費する。
_SUPPRESS_LABELS = {
    "SUPPRESS_OFFMONTH": "対象外月 (契約開始前/分割対象外月/隔月非請求月)",
    "SUPPRESS_ONESHOT": "単発発行済 (当月は対象外)",
}

# gap_check の分類値 (漏れチェック checkbox の元ラベル: 正常=✓ / 要対応=☐)。
GAP_OK = "正常"
GAP_ACTION = "要対応"


# ============================================================================
# 行フィールド抽出 (入力 verdict 行の別名を吸収・int 化)
# ============================================================================
def _to_int(v):
    """金額/件数を tax-excluded int へ堅牢に coerce (再パースはしない・単純 int 化のみ)。"""
    if v in (None, ""):
        return None
    try:
        return int(float(str(v).replace(",", "").replace("，", "")))
    except (TypeError, ValueError):
        return None


def _first(row, keys):
    """row から keys の最初の非空値を返す (別名吸収)。"""
    for k in keys:
        v = row.get(k)
        if v not in (None, ""):
            return v
    return None


def _customer(row):
    """行の取引先名 (customer/取引先)。空なら確認内容から extract_names で最尤候補を拾う。"""
    if not row:
        return ""
    v = _first(row, ("customer", "取引先"))
    if v:
        return str(v)
    names = R.extract_names("", row.get("確認内容", "") or "")
    return names[0] if names else ""


def _product(row):
    """行の商品名 (product/商品)。突合キーの一部。"""
    if not row:
        return ""
    v = _first(row, ("product", "商品"))
    return str(v) if v else ""


def _contract_id(row):
    """行の契約ID (contract_id/契約ID)。同一取引先×同一商品の disambiguator。

    NFKC 正規化のみ適用する (`_base_key` が使う `mfk_reconcile.normalize` は名寄せ用に大文字小文字
    や法人格まで畳むため契約IDには過剰・別契約IDを衝突させかねない)。MF API由来 (NFD) とシート由来
    (NFC) で同一契約IDがUnicode合成形だけ異なるケースを同一契約と誤区別しないため (未正規化のままだと
    curr/prev で別contract_id扱いされ、本来1行の継続契約が新規+発行漏れの2行へ分裂する)。
    """
    if not row:
        return None
    v = _first(row, ("contract_id", "契約ID"))
    return unicodedata.normalize("NFKC", str(v)) if v not in (None, "") else None


def _customer_id(row):
    """行の MF顧客ID (MF顧客ID/customer_id/mf_customer_id/顧客ID)。月跨ぎ突合の第一キー。

    取引先名は月をまたいで表記が揺れうる (name-drift) が MF顧客ID は MF が採番する永続識別子で
    安定する。sheet_to_master が C02 (mfk_customer_id_resolve) で解決して契約へ carry し、
    _new_row が dict(contract) で全 status 行へ載せる。解決できない契約は空 (=名前 fallback)。
    """
    if not row:
        return None
    v = _first(row, ("MF顧客ID", "customer_id", "mf_customer_id", "顧客ID"))
    return str(v) if v not in (None, "") else None


ANNUAL_BILLING_CYCLES = ("年間払い", "年間一括更新")


def _billing_cycle(row):
    """行の支払サイクル (支払サイクル/billing_cycle)。sheet_to_master が確認内容+MF実績から推定。

    年契約系 (年間払い/年間一括更新) は、12ヶ月履歴の裏付けが無い新規契約開始月でも
    『年契約開始=今月一括発行済み=正常』と判定する一次シグナル (D1 の履歴依存を補う)。
    """
    if not row:
        return None
    v = _first(row, ("支払サイクル", "billing_cycle"))
    return str(v) if v not in (None, "") else None


def _is_annual_cycle(row):
    """支払サイクルが年契約系 (年間払い/年間一括更新) か。"""
    cyc = _billing_cycle(row)
    return bool(cyc) and cyc in ANNUAL_BILLING_CYCLES


def _is_monthly_cycle(row):
    """支払サイクルが月払い (毎月請求されるべき regular billing) か。

    要因C の『長期未発行のアクティブ契約』surface は、この積極シグナルがある行だけに限定する
    (年契約/従量/分割/保留 の非請求月を過剰に要対応化しない安全側)。
    """
    return _billing_cycle(row) == "月払い"


def _end_client(row):
    """行のエンドクライアント名 (エンドクライアント名/end_client)。代理店契約の disambiguator (C5)。

    代理店が同一商品を複数の末端顧客(○○様)に契約する場合、contract_id が未設定でもこの名前で
    別契約と識別できる (lib/mfk_reconcile の『（NAME様…）』抽出と同じ語彙を消費するのみ)。
    """
    if not row:
        return None
    v = _first(row, ("エンドクライアント名", "end_client"))
    return str(v) if v not in (None, "") else None


def _amount_of(row):
    """行の金額 (税抜 int)。**MF実績 actual_amount を最優先**し期待額はオーバーレイ (D3 amount-gate 根治)。

    現行実装は期待単価優先で evidence 欠落=金額列空白 (症状①⑥) だったのを、canonical carrier
    `actual_amount` (MF が実発行した額・C05・active 供給限定) 優先へ**反転**する。優先順位:
      ① actual_amount (C05 carrier を持つ行=MF実績由来の実発行額)。
      ② actual_amount が明示 None かつ supply_state が active 以外 (inactive_*/none=未発行/取消/
         供給なし) → 金額列は空 (None)。取消前額 (evidence.amount) も期待額も出さない
         (K3: 未発行を金額列に出さない・ユーザー確定2026-07-10=「金額あり=発行済み」の直感を崩さない)。
      ③ actual_amount carrier 非保持の legacy 行 or active だが実額欠落 → 期待額 (現行単価等) へ fail-soft。
      ④ legacy evidence.amount fallback は supply_state==active or 未設定 (legacy) に限定 (取消前額を昇格させない)。
    """
    if not row:
        return None
    ss = row.get("supply_state")
    if "actual_amount" in row:  # C05 carrier を持つ行 (MF実績由来)
        iv = _to_int(row.get("actual_amount"))
        if iv is not None:
            return iv
        # actual_amount が明示 None かつ active でない (取消/pending/GAP・supply_state=none 含む) =
        # 未発行。金額列に期待額や取消前額を出さず空にする (K3・GAP でも期待額 fallback しない=
        # 前月GAP/今月GAP を「発行済みに見える」誤表示にしない)。
        if ss != R_ACTUALS.SUPPLY_ACTIVE:
            return None
    for k in ("現行単価", "amount", "expected_amount", "金額", "単価"):
        iv = _to_int(row.get(k))
        if iv is not None:
            return iv
    if ss is None or ss == R_ACTUALS.SUPPLY_ACTIVE:
        ev = row.get("evidence")
        if isinstance(ev, dict):
            return _to_int(ev.get("amount"))
    return None


def _raw_product_text(row):
    """canon 前の生商品名 + 確認内容/備考 + MF明細 desc を連結 (トライアル信号の探索源)。"""
    if not row:
        return ""
    parts = []
    for k in ("商品生名", "product_raw", "raw_product", "商品", "product", "確認内容", "備考"):
        v = row.get(k)
        if v:
            parts.append(str(v))
    ev = row.get("evidence")
    if isinstance(ev, dict) and ev.get("desc"):
        parts.append(str(ev.get("desc")))
    return " ".join(parts)


def _is_trial(row):
    """トライアル信号を canon 前の生商品名 / MF明細 desc から検出する。"""
    return "トライアル" in _raw_product_text(row)


def _is_issued(row):
    """当月に有効な MF 請求が発行されたか。**MF実績 reliable issued を最優先**する (amount-gate 根治)。

    優先順位:
      ① 明示 issued フラグ True (後方互換)。
      ② MF実績由来 reliable_issued True (C05: active 供給を実発行=期待額一致でなく実績)。症状③⑦根治。
      ③ C05 carrier を持つ行で supply_state が active 以外 (inactive_canceled/pending/none) なら
         **未発行と断定**して False を返す (verdict/evidence.amount による誤 issued を上書き=取消前額の
         issued 化を防ぐ K3 偽陰性隔離)。
      ④ legacy: verdict が ISSUED_VERDICTS か evidence に正の金額 (evidence.amount fallback は
         supply_state==active or 未設定=legacy 行に限定)。
    """
    if not row:
        return False
    if row.get("issued") is True:
        return True
    if row.get("reliable_issued") is True:
        return True
    ss = row.get("supply_state")
    if ss is not None and ss != R_ACTUALS.SUPPLY_ACTIVE:
        return False
    if row.get("verdict") in ISSUED_VERDICTS:
        return True
    ev = row.get("evidence")
    if isinstance(ev, dict) and _to_int(ev.get("amount")):
        return True
    return False


def _prev_continuity_issued(row):
    """prev 行が『継続性』の観点で前月発行済み相当か (C4: 取消の継続性・_is_issued とは別述語)。

    _is_issued の金額列セマンティクス (PR#85: actual_amount/reliable_issued 優先で取消前額を
    金額列に出さない K3) はそのまま消費するのみで変更しない。本述語は compare_periods の
    STATE_NEW/STATE_CONTINUED の分岐にのみ使う: prev が「前月に一度発行された取消行」
    (supply_state=inactive_canceled かつ canceled_at あり=REVIEW_CANCELED 相当) なら、当月
    curr が発行済みの継続契約を STATE_NEW と誤判定しないよう継続性上は発行済み相当として扱う。
    真の未発行 (supply_state=none・そもそも一度も発行されていない) はこの適用外で通常の
    _is_issued 判定に従う (安全側=真の新規と取消継続を混同しない)。
    """
    if _is_issued(row):
        return True
    if not row:
        return False
    return (row.get("supply_state") == R_ACTUALS.SUPPLY_INACTIVE_CANCELED
            and bool(row.get("canceled_at")))


# ============================================================================
# 突合キー (取引先×商品・複数契約時のみ contract_id で disambiguate)
# ============================================================================
def _base_key(row):
    """取引先×商品の突合キー (mfk_reconcile.normalize で表記揺れを吸収)。"""
    return (R.normalize(_customer(row)), R.normalize(_product(row)))


def _needs_disambiguation(rows):
    """同一 (取引先,商品) に複数の異なる contract_id またはエンドクライアント名が存在する base key
    を軸別に返す (C5: 代理店が同一商品を複数エンドクライアントに契約する幻遷移の封鎖)。

    返り値 = (cid_disambig, ec_disambig) の base key 集合ペア。エンドクライアント名の軸は
    contract_id が未設定の代理店契約でも発火する (代理店は複数エンドクライアントを同一商品名・
    contract_id 無しで持つことがあり、disambiguation 無しでは (取引先,商品) の setdefault で
    1 件のみ残り、他方の状態変化が隠蔽/幻の NEW+STOPPED を生むため)。両軸が同時に成立する base key
    は _match_key でエンドクライアント名を優先する (contract_id は月によって付与有無が揺れうる
    構造化列だが、エンドクライアント名は契約の本質的識別子で月をまたいで安定するため)。
    """
    cid_groups = defaultdict(set)
    ec_groups = defaultdict(set)
    for r in rows:
        base = _base_key(r)
        cid = _contract_id(r)
        if cid:
            cid_groups[base].add(cid)
        ec = _end_client(r)
        if ec:
            ec_groups[base].add(R.normalize(ec))
    cid_disambig = {k for k, ids in cid_groups.items() if len(ids) > 1}
    ec_disambig = {k for k, ecs in ec_groups.items() if len(ecs) > 1}
    return cid_disambig, ec_disambig


def _match_key(row, disambig):
    """disambig = (cid_disambig, ec_disambig) (_needs_disambiguation の返り値)。

    エンドクライアント名の軸を contract_id より優先する: contract_id は構造化列の入力揺れ
    (今月だけ付与される等) で月をまたいで不整合になりうるが、エンドクライアント名は代理店契約の
    本質的識別子で安定するため、両軸が同時に成立する base key では前者が後者の突合キー安定性を
    壊さないようにする (C5)。
    """
    cid_disambig, ec_disambig = disambig
    base = _base_key(row)
    if base in ec_disambig:
        return base + ("ec", R.normalize(_end_client(row) or ""))
    if base in cid_disambig:
        return base + ("cid", str(_contract_id(row) or ""))
    return base


# ============================================================================
# compare_periods — 前月集合と今月集合を突合し 4 状態のペアリングを返す純関数
# ============================================================================
def _pairing_entry(key, prev, curr):
    """(key, prev, curr) から 4 状態を判定して pairing dict を作る (compare_periods の 2 pass 共通)。

    STATE_NEW/STATE_CONTINUED の分岐は prev の『継続性』を _prev_continuity_issued で判定する
    (C4: _is_issued の金額列セマンティクスとは別 SSOT)。prev が前月に一度発行された取消行
    (supply_state=inactive_canceled かつ canceled_at あり) なら継続性上は発行済み相当とし、curr が
    発行済みの継続契約を STATE_NEW と誤判定しない。STATE_STOPPED の判定 (not curr_issued and
    prev_issued) は従来どおり _is_issued を使う。
    """
    prev_issued = _is_issued(prev)
    curr_issued = _is_issued(curr)
    prev_continuity = _prev_continuity_issued(prev)
    if curr_issued and prev_continuity:
        state = STATE_CONTINUED
    elif curr_issued and not prev_continuity:
        state = STATE_NEW
    elif not curr_issued and prev_issued:
        state = STATE_STOPPED
    else:
        state = STATE_NONE
    return {
        "key": key, "prev": prev, "curr": curr,
        "prev_issued": prev_issued, "curr_issued": curr_issued,
        "state": state,
    }


def _id_match_key(row, disambig, name_to_id):
    """MF顧客ID を第一に使った月跨ぎ突合キー。ID を解決できなければ None (=名前 pass へ回す)。

    顧客軸に MF顧客ID (月跨ぎで安定) を使うことで、取引先名 drift (日本語⇄英語表記・社名変更等)
    による先月/今月の分裂を防ぐ (要因A)。代理店 (同一 MF顧客ID×同一商品で複数エンドクライアント)
    は _match_key と同じ disambiguation (エンドクライアント名/契約ID) を ID キーにも重ね、
    幻の collapse を防ぐ。
    """
    cid = _customer_id(row)
    if not cid:
        # 明示 ID が無くても、同じ正規化取引先名で ID を持つ兄弟行があれば継承する
        # (片月だけ ID 解決できた契約が ID/名前の混在で再分裂しないように)。
        cid = name_to_id.get(R.normalize(_customer(row)))
    if not cid:
        return None
    cid_disambig, ec_disambig = disambig
    base = ("cid", str(cid), R.normalize(_product(row)))
    name_base = _base_key(row)
    if name_base in ec_disambig:
        return base + ("ec", R.normalize(_end_client(row) or ""))
    if name_base in cid_disambig:
        return base + ("cid2", str(_contract_id(row) or ""))
    return base


def compare_periods(prev_rows, curr_rows):
    """前月 verdict 行と今月 verdict 行を突合し 4 状態へペアリングする純関数。

    返り値 = list[dict]。各要素:
      {"key", "prev", "curr", "prev_issued", "curr_issued", "state"}。
      state は STATE_CONTINUED / STATE_NEW / STATE_STOPPED / STATE_NONE。

    突合は 2 pass: **Pass1 は MF顧客ID (月跨ぎで安定) を第一キー**にし、取引先名 drift による
    先月/今月の分裂を根治する (要因A)。ID を解決できない行だけ Pass2 で従来の取引先名×商品キー
    (_match_key・代理店 disambiguation 込み) へ fallback する。
    """
    prev_rows = prev_rows or []
    curr_rows = curr_rows or []
    all_rows = list(prev_rows) + list(curr_rows)
    disambig = _needs_disambiguation(all_rows)

    # 正規化取引先名 → MF顧客ID の bridge (どちらかの月で ID を持つ行から作る)。片月だけ
    # 明示 ID を持つ契約の兄弟行へ ID を継承させ、ID/名前の混在で再分裂しないようにする。
    name_to_id = {}
    for r in all_rows:
        cid = _customer_id(r)
        if cid:
            name_to_id.setdefault(R.normalize(_customer(r)), str(cid))

    pairing = []
    consumed = set()

    # Pass1: MF顧客ID 一致 (name-drift でも分裂しない)。ID キーを持つ行は全て consumed に入れ
    # (setdefault の敗者=重複行も含め)、Pass2 で名前突合として二重出現しないようにする。
    prev_id, curr_id = {}, {}
    for r in prev_rows:
        k = _id_match_key(r, disambig, name_to_id)
        if k is not None:
            consumed.add(id(r))
            prev_id.setdefault(k, r)
    for r in curr_rows:
        k = _id_match_key(r, disambig, name_to_id)
        if k is not None:
            consumed.add(id(r))
            curr_id.setdefault(k, r)
    for key in sorted(set(prev_id) | set(curr_id)):
        pairing.append(_pairing_entry(key, prev_id.get(key), curr_id.get(key)))

    # Pass2: ID を解決できなかった行のみ従来の取引先名×商品キーで突合。
    prev_map, curr_map = {}, {}
    for r in prev_rows:
        if id(r) in consumed:
            continue
        prev_map.setdefault(_match_key(r, disambig), r)
    for r in curr_rows:
        if id(r) in consumed:
            continue
        curr_map.setdefault(_match_key(r, disambig), r)
    for key in sorted(set(prev_map) | set(curr_map), key=lambda k: tuple(str(x) for x in k)):
        pairing.append(_pairing_entry(key, prev_map.get(key), curr_map.get(key)))

    return pairing


# ============================================================================
# 12ヶ月履歴 / 契約終了月 のインデックス (差分該当取引先のみ・呼出側で絞る前提)
# ============================================================================
def _index_lookback(lookback):
    """12ヶ月履歴を normalize(取引先) → [record] へ畳む (dict/list 双方の入力形を吸収)。"""
    idx = defaultdict(list)
    if not lookback:
        return idx
    if isinstance(lookback, dict):
        records = None
        for k in ("records", "history", "items"):
            if isinstance(lookback.get(k), list):
                records = lookback[k]
                break
        if records is not None:
            for rec in records:
                idx[R.normalize(rec.get("customer") or rec.get("取引先") or "")].append(rec)
        else:
            for cust, recs in lookback.items():
                for rec in (recs or []):
                    idx[R.normalize(cust)].append(rec)
    elif isinstance(lookback, list):
        for rec in lookback:
            idx[R.normalize(rec.get("customer") or rec.get("取引先") or "")].append(rec)
    return idx


def _rec_is_annual(rec):
    """12ヶ月履歴レコードが年契約一括発行か (annual フラグ or MATCH_ANNUAL verdict)。"""
    if not isinstance(rec, dict):
        return False
    if rec.get("annual") or rec.get("annual_lump"):
        return True
    return rec.get("verdict") == "MATCH_ANNUAL"


def _rec_month(rec):
    return str(rec.get("month") or rec.get("month_ym") or rec.get("target_month") or "")


def _index_contract_end(contract_end):
    """契約終了月データを base key → 終了月(YYMM) へ畳む (二次情報・cross-check 用)。"""
    idx = {}
    if not contract_end:
        return idx
    items = contract_end
    if isinstance(contract_end, dict):
        for k in ("records", "items", "contracts"):
            if isinstance(contract_end.get(k), list):
                items = contract_end[k]
                break
        else:
            # {customer: end_month} 形も許容 (product 無しは商品空キー)。
            for cust, end in contract_end.items():
                idx[(R.normalize(cust), R.normalize(""))] = str(end)
            return idx
    if isinstance(items, list):
        for rec in items:
            if not isinstance(rec, dict):
                continue
            end = rec.get("end_month") or rec.get("契約終了月")
            if not end:
                continue
            idx[_base_key(rec)] = str(end)
    return idx


def _end_month_for(prev, curr, end_idx):
    """行の契約終了月 (構造化列) を取得する。行の値 → contract_end データの順で解決。"""
    for r in (curr, prev):
        if r:
            v = r.get("契約終了月") or r.get("end_month")
            if v:
                return str(v)
    for r in (curr, prev):
        if r:
            k = _base_key(r)
            if k in end_idx:
                return end_idx[k]
    return None


# ============================================================================
# 対象月決定 (直近締め済みの請求対象月)
# ============================================================================
def _prev_month_ym(ym):
    """YYMM → 1ヶ月前の YYMM。不正は None。"""
    m = re.fullmatch(r"(\d{2})(\d{2})", str(ym or ""))
    if not m:
        return None
    yy, mm = int(m.group(1)), int(m.group(2))
    if mm == 1:
        yy, mm = yy - 1, 12
    else:
        mm -= 1
    return f"{yy:02d}{mm:02d}"


def _prev_year_month(ym):
    """YYMM → 12ヶ月前 (同月・前年) の YYMM。年→月切替の裏付け探索に使う。不正は None。"""
    m = re.fullmatch(r"(\d{2})(\d{2})", str(ym or ""))
    if not m:
        return None
    return f"{int(m.group(1)) - 1:02d}{m.group(2)}"


def resolve_target_months(today=None):
    """実行日から (今月=直近締め済みの請求対象月, 先月) を YYMM で返す。

    今月 = 実行日カレンダー月の前月 (直近で締め済みの請求対象月)。例: 2026-07-02 実行 →
    今月=2606 (2026-06分)・先月=2605 (2026-05分)。
    """
    d = today or datetime.date.today()
    y, mo = d.year, d.month
    if mo == 1:
        cy, cm = y - 1, 12
    else:
        cy, cm = y, mo - 1
    curr = f"{cy % 100:02d}{cm:02d}"
    return curr, _prev_month_ym(curr)


# ============================================================================
# classify_period_transition — ペアリング + 既存 verdict + 12ヶ月履歴から各行を決定する純関数
# ============================================================================
def _row_reliable_mf_issued(row):
    """行が MF実績由来で当月 active 発行済みか (C05 reliable_issued / supply_state==active)。

    C04 notion_report_sink の cross-run guard の『権威ある正常訂正』(K4) の根拠。verdict/evidence 由来の
    bare issued とは区別し、MF が実際に active 供給を発行した行のみ True (取消/供給なし/legacy は False)。
    """
    if not row:
        return False
    # 安全弁 (2026-07-10): category-agnostic fallback で得た非確定一致 (category_confirmed=False) は
    # 別 category/商品の供給を取り違えている可能性があるため権威判定から除外する。これがないと誤 reliable が
    # cross-run guard/collapse で真の月次漏れを正常✓へ上書きする (system-strategic 検証 HIGH)。既定 True。
    if row.get("category_confirmed", True) is False:
        return False
    if row.get("reliable_issued") is True:
        return True
    return row.get("supply_state") == R_ACTUALS.SUPPLY_ACTIVE


def _emit(customer, amount, prev_amount, gap_check, period_diff,
          product, comment, contract_id, target_month, reliable_issued=False,
          end_client=None):
    return {
        "customer": customer,
        "amount": amount,
        "prev_amount": prev_amount,
        "gap_check": gap_check,
        "period_diff": period_diff,
        "product": product,
        "comment": comment,
        "contract_id": contract_id,
        "target_month": target_month,
        # C05→C04: MF実績由来で当月 active 発行済みか。cross-run guard(K4)が前 run の要対応☐を
        # この権威ある実額訂正で正常☑へ上書きする根拠 (_STRUCTURAL_NORMAL_MARKERS と同格の bypass 事由)。
        "reliable_issued": bool(reliable_issued),
        # 契約の disambiguator (エンドクライアント名)。sink の collapse で「同一契約が ID↔名前照合で
        # 二重化した phantom」と「代理店の別エンドクライアント=真の別契約」を identity 判別するために
        # C04 へ透過する (非表示・Notion 列には出さない=既知キーのみ props 化)。contract_id と対で
        # 契約 identity を成し、別 identity の要対応を発行済みで黙って正常化する漏れ隠蔽を防ぐ。
        "end_client": end_client,
    }


def _continued_comment(pair, curr, prev):
    # 金額の物語は列 (Fix C) と同一 gate を使う: 実発行があった月のみ実額を語る (未発行月の期待額=
    # 現行単価をコメントに漏らさない=列とコメントの乖離根治・logical プロセス finding)。prev 取消継続
    # (prev_continuity=True かつ prev_issued=False) で legacy 取消 prev が現行単価を持つと、列は空なのに
    # コメントだけ「先月N円→今月M円」と期待額を語る乖離が出るのを防ぐ。
    ca = _amount_of(curr) if pair.get("curr_issued") else None
    pa = _amount_of(prev) if pair.get("prev_issued") else None
    if ca is not None and pa is not None and ca != pa:
        base = f"継続発行 (金額変動: 先月{pa:,}円→今月{ca:,}円)"
    else:
        base = "継続発行 (前月・今月とも発行あり)"
    # 継続発行でも当月 verdict が REVIEW_* (金額差/過剰請求/数量差/終了後請求等) なら、
    # 発行漏れではないが reconcile 側の要確認事項ゆえコメントに surface する (継続扱いで
    # 不可視化しない)。gap_check は発行漏れ判定なので正常のまま (漏れではない)。
    verdict = (curr or {}).get("verdict")
    if verdict and str(verdict).startswith("REVIEW_"):
        base += f" / 要確認: 上流 verdict={verdict} (金額差/過剰請求等・単月照合 reconcile で確認)"
    return base


def _annual_lookback_note(row, lookback_idx):
    """年契約期間内の根拠コメント補強 (既存判定は上書きしない・補強のみ)。"""
    recs = lookback_idx.get(R.normalize(_customer(row))) or []
    for rec in recs:
        if _rec_is_annual(rec):
            m = _rec_month(rec)
            return f"12ヶ月履歴に年契約一括発行あり({m})=年契約周期内 (遡りは補強・既存verdict優先)"
    return ""


def _customer_is_annual_in_lookback(row, lookback_idx):
    """12ヶ月履歴に当該取引先「かつ同一商品」の年契約一括発行があるか (curr=None の二次トリガー)。

    年契約の非請求月は reconcile が今月行を出さず curr=None になる。今月・先月 verdict で
    年契約と判定できない縁ケースでも、12ヶ月履歴に年契約一括 (MATCH_ANNUAL / annual フラグ) が
    あれば年契約周期と分類する裏付けにする (GAP-C05-ANNUAL-STOPPED の (b) 二次トリガー)。

    ★商品粒度で突合する (elegant-review F1 是正 + round2 残穴1 是正): 年契約性は「顧客属性」でなく
    「契約/商品属性」ゆえ、混在契約顧客 (年契約商品A + 月次商品B) で B の真の月次漏れを A の年契約
    履歴で誤抑制しないよう、**漏れ行に商品があるときは履歴レコードの商品が確定一致するものだけ**を
    採用する。履歴レコードに商品が無い/不一致=年契約性を当該商品で確認不能ゆえ抑制しない (安全側=
    漏れを隠さない)。これは「年契約履歴レコードは商品 (product/商品) を持つべき」というデータ契約を
    含意する。漏れ行に商品が無いとき (row_product 空) のみ顧客単位 best-effort へ fail-soft する。
    (b) は prev に dispositive verdict が無い縁ケースの best-effort トリガーであり、prev が月次
    verdict を持つ通常経路は呼出側の `not prev_verdict` ゲートで (b) 自体が発火しない。
    """
    recs = lookback_idx.get(R.normalize(_customer(row))) or []
    row_product = R.normalize(_product(row))
    for rec in recs:
        if not _rec_is_annual(rec):
            continue
        rec_product = R.normalize(str(rec.get("product") or rec.get("商品") or ""))
        if row_product:
            if rec_product == row_product:
                return True  # 商品確定一致の年契約履歴のみ抑制の裏付けにする。
            continue          # 商品が空 or 不一致=当該商品の年契約性を確認できない→抑制しない (安全側)。
        return True          # 漏れ行に商品が無いときのみ顧客単位 best-effort。
    return False


def _new_comment(row, lookback_idx, target_month, lookback_available=True):
    """新規/年→月切替のコメント。12ヶ月前の年契約一括発行を裏付けに年→月切替を推定 (補強)。

    lookback_available=False (12ヶ月ルックバックが未実行=--lookback-12mo 未指定) のときは、
    「12ヶ月確認したが年契約なし=真の新規」と「そもそも確認していない=未確認」を silent に
    同一視せず、**未確認である旨を明示**する。前月なし今月ありは年契約→月額切替の可能性が高い
    (ユーザー要件 C3) ため、確認できていない事実を隠して『新規発行』と断定しない。
    """
    recs = lookback_idx.get(R.normalize(_customer(row))) or []
    switch_month = _prev_year_month(target_month) if target_month else None
    for rec in recs:
        if _rec_is_annual(rec) and (switch_month is None or _rec_month(rec) == switch_month):
            return (f"12ヶ月前({_rec_month(rec)})に年契約一括発行→自動で月額切替した可能性 "
                    "(年→月切替・12ヶ月履歴で確認済み)")
    for rec in recs:
        if _rec_is_annual(rec):
            return (f"12ヶ月履歴に年契約一括発行あり({_rec_month(rec)})→年→月切替の可能性 "
                    "(12ヶ月履歴で確認済み)")
    if not lookback_available:
        # ルックバック自体が未実行 (--lookback-12mo 未指定 or 空データ)。年→月切替か真の新規かを
        # 未確認のまま『新規発行』と断定しない (確実性の開示)。データ源は MF 実績の12ヶ月履歴であり
        # 請求確認シートの開始月には依存しない。
        return ("⚠️ 12ヶ月ルックバック未実行 (12ヶ月履歴データなし)→年契約からの月額切替か"
                "真の新規発行か未確認。MF実績の12ヶ月履歴を渡して再実行し裏付けを取ること")
    # ルックバックは実行したが当該取引先に年契約一括の履歴なし=真の新規発行と確認できた。
    return "新規発行 (12ヶ月履歴を確認したが年契約一括の裏付けなし=真の新規)"


def _new_backing_found(row, lookback_idx):
    """STATE_NEW (前月なし今月あり) の『年→月切替』裏付けが 12ヶ月履歴にあるか (D1 gate の判定子)。

    裏付けあり=年契約→月額切替と推定でき正常☑・裏付けなし (ルックバック未実行 or 履歴なし=真の新規)
    は D1 で要確認 (GAP_ACTION) へ flip する。

    ★**商品粒度**で突合する (elegant-review F1/round2 是正を NEW 経路へ対称適用): 年契約性は「顧客属性」
    でなく「契約/商品属性」ゆえ、混在契約顧客 (年契約商品A + 今月新規の別商品B) で B の真の新規発行を
    A の年契約履歴で誤って正常化しない (漏れ隠蔽方向)。STOPPED 経路の `_customer_is_annual_in_lookback`
    と同一の商品確定一致ルール (商品ありは確定一致のみ採用・商品空は顧客単位 best-effort) を再利用し、
    STOPPED で塞いだ穴が NEW で開くのを防ぐ (SSOT 一本化)。
    """
    return _customer_is_annual_in_lookback(row, lookback_idx)


def _fidelity_lookback_partial(fidelity):
    """fetch fidelity report が lookback 部分欠損 (C06 exit3) を示すか。

    exit_code==3 または overall=='lookback_partial' を lookback 部分欠損とみなす。当該時は STATE_NEW の
    年→月切替裏付け (12ヶ月ルックバック依存) が未確定なので該当行を要確認へ降格する (安全側 over-report)。
    """
    if not isinstance(fidelity, dict):
        return False
    return fidelity.get("exit_code") == 3 or fidelity.get("overall") == "lookback_partial"


def _classify_stopped(prev, curr, lookback_idx, end_idx, target_month):
    """今月なし×前月ありの非請求事情を既存 verdict を一次源に分類する。

    返り値 = (gap_check, period_diff, comment)。
    自由文の終了根拠は再パースせず、既存 verdict (SUPPRESS_ENDED / REVIEW_ENDED_NO_BASIS /
    SUPPRESS_ANNUAL / MATCH_ANNUAL) を消費するのみ。契約終了月 (構造化列) は二次情報。
    """
    verdict = (curr or {}).get("verdict")
    prev_verdict = (prev or {}).get("verdict")
    end_month = _end_month_for(prev, curr, end_idx)

    # ① 契約完了 (終了根拠あり) = 既存 verdict SUPPRESS_ENDED を消費するのみ。
    if verdict == "SUPPRESS_ENDED":
        comment = "契約完了 (終了根拠あり・既存 verdict SUPPRESS_ENDED を消費)"
        if end_month:
            comment += f" 契約終了月={end_month}"
        return GAP_OK, "前月あり今月なし (契約完了)", comment

    # ② 根拠なき終了月 = 既存 verdict REVIEW_ENDED_NO_BASIS。安全弁: 抑制せず発行漏れ候補に残す。
    #    構造化列『契約終了月』に値があっても has_end_basis 根拠が無ければ漏れ隠蔽を防ぐため要対応。
    if verdict == "REVIEW_ENDED_NO_BASIS":
        if end_month:
            comment = (f"契約終了月={end_month} だが終了根拠なし (REVIEW_ENDED_NO_BASIS)"
                       "→継続契約の発行漏れの可能性・要対応")
        else:
            comment = ("終了根拠なし (REVIEW_ENDED_NO_BASIS)→継続契約の発行漏れの可能性・要対応")
        return GAP_ACTION, "前月あり今月なし (根拠なき終了月)", comment

    # ③ 年契約期間内 = 既存 verdict SUPPRESS_ANNUAL / MATCH_ANNUAL を一次源 (12ヶ月遡りは補強のみ)。
    #    curr.verdict を優先するが、年契約の非請求月は reconcile が今月行を出さず curr=None
    #    (verdict 欠落) になる (GAP-C05-ANNUAL-STOPPED: 金子金物型 systemic bug=全年契約の
    #    非請求月が⑥へ誤爆)。そこで curr が非情報的 (verdict 欠落) なときは、先月 verdict
    #    prev.verdict ∈ {MATCH_ANNUAL,SUPPRESS_ANNUAL} または 12ヶ月履歴の年契約一括
    #    (_customer_is_annual_in_lookback) を一次トリガーにして年契約周期の非請求月を GAP_OK へ
    #    分類する。年契約 verdict は識別的ゆえ prev 参照で正常/漏れを分離できる (⑤隔月の
    #    prev=MATCH_MONTHLY は非識別的で「隔月正常」と「月次の真の漏れ」が curr=None 空間で
    #    衝突するため prev.verdict 同型化は⑤へ横断適用しない。⑤の curr=None 根治は入力層
    #    curr-present 化=C05 producer が呼び出し側で実装済み (GAP-R1-COLLECT-CURR-PRESENT 根治済み)。
    #    準拠経路では⑤ curr=None は起きず、本 fallback は非準拠 caller 向けの安全側 (⑥要対応))。
    annual_source = None
    if verdict in ANNUAL_NORMAL_VERDICTS:
        annual_source = f"既存 verdict {verdict} を一次源"
    elif not verdict:  # curr=None / verdict 欠落 = 年契約の非請求月の疑い (curr 単独では判定不能)
        if prev_verdict in ANNUAL_NORMAL_VERDICTS:
            annual_source = (f"先月 verdict {prev_verdict} を一次源 "
                             "(今月は年契約の非請求月=行なし)")
        # (b) 12ヶ月履歴トリガーは prev に dispositive verdict が無い (issued だが verdict 不明) ときだけ。
        # prev=MATCH_MONTHLY 等の月次 issued verdict があるなら現在は月次発行=年→月切替後ゆえ、
        # 12ヶ月前の旧年契約履歴で正常化してはならない (真の月次漏れの隠蔽=elegant-review F1 是正)。
        elif not prev_verdict and _customer_is_annual_in_lookback(prev or curr, lookback_idx):
            annual_source = "12ヶ月履歴の年契約一括を一次源 (今月は年契約の非請求月=行なし)"
    if annual_source:
        # 経理向け平易文を先頭に置き、内部 verdict は根拠として併記する (F7)。
        comment = f"年間一括請求のため今月は請求なし=正常 ({annual_source})"
        # source 自体が履歴由来でないときだけ補強 note を足す (二重掲載を避ける)。
        if "12ヶ月履歴" not in annual_source:
            note = _annual_lookback_note(prev or curr, lookback_idx)
            if note:
                comment += " / " + note
        return GAP_OK, "前月あり今月なし (年契約周期)", comment

    # ③' 契約完了の curr=None 変種 = 先月が最終請求 (prev=MATCH_ENDED_FINAL=終端の識別的 verdict)・
    #    今月行なし → 契約終了後の非請求月=正常 (elegant-review F2: plan 明示の①契約完了 curr=None
    #    hard-gate 分岐)。年契約③と同型 (終端 issued verdict の翌月 curr=None) だが、MATCH_ENDED_FINAL
    #    は識別的ゆえ回避可能な誤爆を正しく正常化できる。⑤隔月の非識別 MATCH_MONTHLY とは別で、
    #    真の月次漏れ (prev=MATCH_MONTHLY・curr=None→⑥要対応) には適用しない。
    if not verdict and prev_verdict == "MATCH_ENDED_FINAL":
        comment = ("契約完了のため今月は請求なし=正常 "
                   "(先月 verdict MATCH_ENDED_FINAL=最終請求済・今月は契約終了後の非請求月)")
        if end_month:
            comment += f" 契約終了月={end_month}"
        return GAP_OK, "前月あり今月なし (契約完了)", comment

    # ④ トライアル完了 = canon 前の生商品名 / MF明細 desc の『トライアル』信号で判定。
    if _is_trial(prev) or _is_trial(curr):
        return GAP_OK, "前月あり今月なし (トライアル完了)", \
            "トライアル完了 (canon 前の生商品名/MF明細descで判定・正規化後は信号が消えるため)"

    # ⑤ その他の SUPPRESS_* (OFFMONTH=隔月/分割の対象外月・契約開始前 / ONESHOT=単発発行済 等)
    #    は reconcile が既に正常抑制と判定した『対象外』(verdict-mapping SSOT: SUPPRESS_*→対象外)。
    #    C05 はこの既存判定を消費するのみで再判定しない (再判定は SSOT 違反かつ隔月/単発契約の
    #    非請求月を偽陽性で漏れ扱いにする)。
    if verdict and str(verdict).startswith("SUPPRESS_"):
        label = _SUPPRESS_LABELS.get(verdict, "正常抑制 (対象外)")
        return GAP_OK, "前月あり今月なし (対象外)", \
            f"{label} (既存 verdict {verdict} を消費・対象外=正常)"

    # ⑥ 正常な非請求事情に該当せず (SUPPRESS_* でも年契約/契約終了でもトライアルでもない)
    #    → 発行漏れ候補 (要対応)。GAP verdict や verdict 欠落・REVIEW_* 等はここへ落ちる。
    tail = f" (既存 verdict {verdict})" if verdict else ""
    comment = ("正常な非請求事情 (年契約/トライアル/契約終了/対象外抑制) に該当せず"
               "→発行漏れ候補・要対応" + tail)
    # curr=None (今月行なし) の要対応は「安全側 over-report」の可能性がある。年契約初年度
    # (prev に MATCH_ANNUAL なし・DB1 支払サイクル未配線) / 契約完了 (MATCH_MONTHLY+終了注記) /
    # 隔月の対象外月 が収集層で curr=None に落ちた場合も⑥へ来るため、確認経路を runtime で開示する
    # (elegant-review F8/E: 安全側 over-report は理由と補強経路を開示して初めて運用できる)。
    if not verdict:
        comment += (" ｜ 確認: 今月行なし(curr=None)。年契約初年度(--lookback-12mo/DB1支払サイクル)・"
                    "契約完了(--contract-end)・隔月対象外月 の可能性は収集層 curr-present 化で切り分ける")
    return GAP_ACTION, "前月あり今月なし (発行漏れ候補)", comment


def _classify_continuing(pair, lookback_idx, end_idx, target_month):
    """STATE_NONE (両月未発行) のうち今月 curr が真の発行漏れ (継続漏れ) なら要対応行を返す。

    curr の既存 verdict を _classify_stopped と同じ SSOT で評価し、GAP_ACTION (年契約/契約完了/
    トライアル/SUPPRESS_* のいずれにも該当しない発行漏れ) のときだけ emit する。正常抑制や
    curr 不在 (元々請求なし=対象外) は None を返し従来どおり非 emit を維持する (漏れを隠さない
    が対象外を過剰報告もしない安全側)。
    """
    curr = pair.get("curr")
    if curr is None:
        return None  # 今月の verdict 行が無い = 元々請求なし (対象外)。
    prev = pair.get("prev")
    gap_check, _period, _comment = _classify_stopped(
        prev, curr, lookback_idx, end_idx, target_month)
    if gap_check != GAP_ACTION:
        return None  # 正常抑制 (年契約/契約完了/トライアル/対象外) は非 emit を維持。
    customer = _customer(curr)
    product = _product(curr)
    contract_id = _contract_id(curr) or _contract_id(prev)
    end_client = _end_client(curr) or _end_client(prev)
    comment = ("継続発行漏れ (前月も今月も未発行・今月 verdict が発行漏れ)"
               "→継続契約の請求漏れの可能性・要対応 (単月照合と整合)")
    return _emit(customer, _amount_of(curr), _amount_of(prev), GAP_ACTION,
                 "継続 (前月も今月も未発行)", product, comment, contract_id, target_month,
                 end_client=end_client)


def _classify_both_absent(pair, lookback_idx, end_idx, target_month):
    """STATE_NONE (先月も今月も未発行) のうち『契約完了でも年契約・対象外でもない、月払いの
    アクティブ契約が何ヶ月も請求されていない』行を継続発行漏れ候補として surface する (要因C)。

    curr が実 GAP verdict を持つ継続漏れは _classify_continuing が先に拾う。本関数はそれ以外
    (curr=None を含む) を対象に、契約完了 (終了 verdict/ステータス終了) / 年契約非請求月 / 対象外抑制
    (隔月・分割・単発) / トライアル完了 / 審査中(REVIEW_*) を正常・保留として除外し、残った
    『月払い×アクティブ×長期未発行』だけを要対応で可視化する (完了済みなら契約終了月の記入で正常化)。
    curr=None で _classify_stopped の ⑤ が curr の verdict しか見ない穴を、prev/curr 両側の verdict を
    見ることで塞ぐ。
    """
    prev = pair.get("prev")
    curr = pair.get("curr")
    rep = curr or prev
    if rep is None:
        return None
    verdicts = [(prev or {}).get("verdict"), (curr or {}).get("verdict")]
    # 契約完了 (終了/最終請求 verdict) = 正常 → 非 emit。
    if any(v in ("SUPPRESS_ENDED", "MATCH_ENDED_FINAL") for v in verdicts):
        return None
    # 対象外抑制 (隔月/分割/単発 SUPPRESS_*) と年契約 verdict = 正常 → 非 emit (prev/curr 両側を見る)。
    if any(v and (str(v).startswith("SUPPRESS_") or v in ANNUAL_NORMAL_VERDICTS) for v in verdicts):
        return None
    # 審査中/保留/データ不備 (REVIEW_*) は別途フラグ済み・確定漏れでない → 非 emit。
    if any(v and str(v).startswith("REVIEW_") for v in verdicts):
        return None
    # 年契約系 (支払サイクル or 12ヶ月履歴の年契約一括) は 11ヶ月の非請求が正常 → 非 emit。
    if _is_annual_cycle(rep) or _customer_is_annual_in_lookback(rep, lookback_idx):
        return None
    # トライアル完了 = 正常 → 非 emit。
    if _is_trial(prev) or _is_trial(curr):
        return None
    # ステータスが終了/完了/解約/停止 = 契約完了扱い → 非 emit。
    status = str(_first(rep, ("ステータス", "status")) or "")
    if any(t in status for t in ("終了", "完了", "解約", "停止")):
        return None
    # 積極シグナル: 月払い (毎月請求されるべき) のときだけ surface する (過剰報告回避)。
    if not _is_monthly_cycle(rep):
        return None
    customer = _customer(rep)
    product = _product(rep)
    contract_id = _contract_id(curr) or _contract_id(prev)
    end_client = _end_client(curr) or _end_client(prev)
    comment = ("契約完了の確認が取れず先月も今月も (2ヶ月以上) 請求書が発行されていない月払い契約"
               "=継続発行漏れの可能性・要対応 ｜ 完了済みなら契約終了月をシートへ記入すると正常化する")
    return _emit(customer, _amount_of(curr), _amount_of(prev), GAP_ACTION,
                 "継続 (先月も今月も未発行)", product, comment, contract_id, target_month,
                 end_client=end_client)


def classify_period_transition(pairing, lookback=None, contract_end=None, target_month=None,
                               fidelity=None):
    """ペアリング + 既存 verdict + 12ヶ月履歴 から各行の period_diff/gap_check/comment を決定する純関数。

    STATE_NONE (今月なし×前月なし) は原則 emit しないが、今月 curr が実 GAP verdict の継続漏れ
    なら要対応として emit する (_classify_continuing)。継続発行は全行 emit する。
    fidelity = C06 fetch fidelity report (任意)。lookback 部分欠損 (exit3) 時は STATE_NEW 該当行を
    要確認へ降格する (安全側 over-report・真の月次漏れは隠さない)。exit1 の fail-closed は main() 側で扱う。
    返り値 = list[dict] (I/O 契約のレポート行)。
    """
    lookback_idx = _index_lookback(lookback)
    # 12ヶ月ルックバックのデータが 1 件でも渡されたか (未指定=未実行を STATE_NEW コメントで可視化する)。
    lookback_available = bool(lookback)
    lookback_partial = _fidelity_lookback_partial(fidelity)
    end_idx = _index_contract_end(contract_end)
    out = []
    for pair in pairing:
        state = pair["state"]
        if state == STATE_NONE:
            # 原則 非 emit (元々請求なし=対象外)。ただし (1) 今月 curr が実 GAP verdict の継続漏れ、
            # (2) 契約完了でない月払いアクティブ契約が先月も今月も未発行 (要因C) は真の漏れの可能性
            # ゆえ要対応として surface する (漏れを隠さない・対象外は過剰報告しない安全側)。
            row = _classify_continuing(pair, lookback_idx, end_idx, target_month)
            if row is None:
                row = _classify_both_absent(pair, lookback_idx, end_idx, target_month)
            if row is not None:
                out.append(row)
            continue

        curr, prev = pair["curr"], pair["prev"]
        rep = curr or prev
        customer = _customer(rep)
        product = _product(rep)
        contract_id = _contract_id(curr) or _contract_id(prev)
        end_client = _end_client(curr) or _end_client(prev)  # sink の identity 判別用 (契約の disambiguator)
        # 金額列は**実発行があった月のみ**実額を表示する (Fix C・症状①の自己矛盾根治)。
        # _amount_of は未発行月でも期待額 (現行単価) を返すため、prev/curr_issued (=_is_issued
        # 由来の MF実発行 SSOT) で gate しないと「先月金額あるのに新規」「今月金額あるのに要対応」の
        # 矛盾行が出る。実発行のない月は空にし、金額列と漏れチェックの物語を一致させる。
        amount = _amount_of(curr) if pair.get("curr_issued") else None
        prev_amount = _amount_of(prev) if pair.get("prev_issued") else None
        mf_issued = _row_reliable_mf_issued(curr)  # C05→C04(K4): 当月 MF実績 active 発行の権威フラグ

        if state == STATE_CONTINUED:
            row = _emit(customer, amount, prev_amount, GAP_OK, "継続発行",
                        product, _continued_comment(pair, curr, prev), contract_id, target_month,
                        reliable_issued=mf_issued, end_client=end_client)
        elif state == STATE_NEW:
            curr_verdict = (curr or {}).get("verdict")
            if curr_verdict in ANNUAL_NORMAL_VERDICTS:
                # C3: 今月 verdict が年契約正常 (MATCH_ANNUAL=年一括発行/SUPPRESS_ANNUAL) なら
                # reconcile が既に当月の発行を正常と判定済み (STOPPED 側 ③ の一次源と同型)。
                # 12ヶ月ルックバックは年→月切替の裏付け探索が目的であり、この dispositive な
                # 既存 verdict には不要 (裏付けなしでも要確認へ落とさない・症状=100億ThinkTank利用料等)。
                gap = GAP_OK
                comment = (f"年間一括請求のため今月発行済み=正常 (既存 verdict {curr_verdict} を"
                          "一次源・新規契約の初回年契約でも12ヶ月ルックバック不要)")
                note = _annual_lookback_note(rep, lookback_idx)
                if note:
                    comment += " / " + note
            elif _is_annual_cycle(rep):
                # B: 支払サイクルが年契約系 (年間払い/年間一括更新) の新規は『年契約開始』と判定し
                # 正常☑にする。reconcile が MATCH_ANNUAL を付けられなかった新規年契約 (12ヶ月履歴
                # なし=真に初年度・DB1 支払サイクル未配線) も、シート推定の支払サイクルを一次シグナル
                # にして要確認☐への誤爆を防ぐ (要因B・ユーザー確定2026-07-10)。年→月切替 (支払サイクル
                # =月払い) は本分岐に来ず従来どおり D1 で 12ヶ月裏付けを要求する。
                gap = GAP_OK
                comment = (f"年契約開始のため今月一括発行済み=正常 (支払サイクル={_billing_cycle(rep)}・"
                           "先月なし今月あり=新規年契約の初回発行・12ヶ月履歴不要)")
                note = _annual_lookback_note(rep, lookback_idx)
                if note:
                    comment += " / " + note
            else:
                # 前月なし今月あり=**今月に実発行あり** (STATE_NEW は _pairing_entry の定義上
                # curr_issued=True が前提) ゆえ、定義上『発行漏れ』ではない → 漏れチェックは正常✓。
                # (要件1『今月に権威ある実発行がある行は必ず正常✓』の原則を STATE_CONTINUED から
                # NEW 経路へ拡張=症状①『金額あるのにチェックが入らない』の根治。)
                #
                # 旧 D1 は「年→月切替の12ヶ月裏付けなし」を GAP_ACTION(要対応☐) へ flip していたが、
                # これは『発行漏れ』(=今月未発行) と『内容の未確認』(=年→月切替か真の新規か) を
                # 混同していた。発行漏れ checkbox は**今月の発行の存在**に厳密に紐づけ、未確認は
                # checkbox を倒さず**コメントで開示**する (漏れは今月未発行の行=STATE_STOPPED/継続漏れ
                # だけに残す・OUT1 不変則: reliable/verdict-issued ⟹ 正常)。
                comment = _new_comment(rep, lookback_idx, target_month, lookback_available)
                backing = _new_backing_found(rep, lookback_idx)
                gap = GAP_OK
                if not backing:
                    comment += (" ｜ 注記: 今月は実発行あり=発行漏れではない (正常✓)。"
                                "年→月切替か真の新規かは12ヶ月履歴で未確認 "
                                "(checkbox は発行の存在に紐づけ・内容確認はコメントで開示)")
                elif lookback_partial:
                    comment += (" ｜ 注記: 12ヶ月ルックバック部分欠損 (fetch fidelity NG) だが"
                                "今月の実発行は確認済ゆえ正常✓。年→月切替の裏付けのみ未確定")
            row = _emit(customer, amount, prev_amount, gap, "新規/年→月切替",
                        product, comment, contract_id, target_month, reliable_issued=mf_issued,
                        end_client=end_client)
        else:  # STATE_STOPPED
            gap_check, period_diff, comment = _classify_stopped(
                prev, curr, lookback_idx, end_idx, target_month)
            row = _emit(customer, amount, prev_amount, gap_check, period_diff,
                        product, comment, contract_id, target_month, reliable_issued=mf_issued,
                        end_client=end_client)
        out.append(row)
    return out


# ============================================================================
# I/O (argv → JSON 読込 → 分類 → stdout。副作用なし・network なし)
# ============================================================================
def _load_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _rows_of(doc):
    """per-月 verdict JSON から行 list を取り出す (list そのもの or {rows/verdicts/...:[...]})。"""
    if isinstance(doc, list):
        return [r for r in doc if isinstance(r, dict)]
    if isinstance(doc, dict):
        for k in ("rows", "verdicts", "records", "items"):
            if isinstance(doc.get(k), list):
                return [r for r in doc[k] if isinstance(r, dict)]
    return []


def _target_of(doc, fallback):
    if isinstance(doc, dict):
        for k in ("target_month", "target_ym", "target"):
            v = doc.get(k)
            if v:
                return str(v)
    return fallback


def _orphan_rows(doc, target_month):
    """curr-verdicts の orphans (MF実績あり×請求確認シートに契約なし) を『要マスタ登録』行へ surface する。

    C05 producer (mfk_verdict_export.serialize_verdicts) が curr=None を避けて可視の逆方向行
    doc["orphans"] へ分離した要マスタ登録を、レポートへ 正常✓ (要マスタ登録) 行として emit する
    (GAP-ID-ALIAS-BACKFILL-PATH の closure: C02/C03 で寄らない残余を隠さずレポート可視化する)。
    orphans キーを持たない doc / list 入力では空を返す (後方互換・従来 rows-only 入力を壊さない)。
    orphan は MF が実際に発行済み (reliable_issued=True) なので発行漏れ (false-negative) ではなく、
    シート未登録=マスタ登録の action は要るが発行自体は正常ゆえ、漏れチェックは 正常✓ (GAP_OK)・
    period_diff=要マスタ登録・コメントに登録方法を保持して示す (ユーザー確定2026-07-10・要件3:
    請求確認シートの『契約なし』を漏れ=要対応として扱わない)。
    """
    if not isinstance(doc, dict):
        return []
    out = []
    for o in doc.get("orphans", []) or []:
        if not isinstance(o, dict):
            continue
        customer = o.get("customer") or o.get("cust") or o.get("取引先")
        if not customer:
            continue
        product = o.get("product") or o.get("desc") or o.get("商品")
        amount = o.get("actual_amount")
        if amount is None:
            amount = o.get("amount")
        comment = ("MF実績あり×請求確認シートに契約なし=要マスタ登録 "
                   "(シートへ契約を追加するか MF顧客ID を登録して名寄せを恒久化する)")
        # 要件3(2026-07-10): 発行自体は正常(MF実績あり)ゆえ漏れチェックは GAP_OK(正常✓)。
        # 名寄せ登録の action はコメントで保持し、契約なしを漏れ=要対応にはしない。
        out.append(_emit(customer, amount, None, GAP_OK, "要マスタ登録",
                         product, comment, None, target_month, reliable_issued=True))
    return out


def build_report(curr_doc, prev_doc, lookback=None, contract_end=None, target_month=None,
                 fidelity=None):
    """パース済みドキュメントからレポート行 list を組み立てる (I/O なしの純ロジック纏め)。"""
    curr_rows = _rows_of(curr_doc)
    prev_rows = _rows_of(prev_doc)
    if not target_month:
        target_month = _target_of(curr_doc, None) or resolve_target_months()[0]
    pairing = compare_periods(prev_rows, curr_rows)
    rows = classify_period_transition(
        pairing, lookback=lookback, contract_end=contract_end, target_month=target_month,
        fidelity=fidelity)
    # C05 producer が分離した逆方向 orphans (要マスタ登録) を surface し、curr=None でなく可視化する
    # (下流 _rows_of は rows のみ読むため build_report がここで orphans を消費する=seam の単一結線点)。
    rows.extend(_orphan_rows(curr_doc, target_month))
    return rows


def main(argv=None):
    p = argparse.ArgumentParser(
        description="前月↔今月の発行状態遷移分類 (既存 per-月 verdict を消費する薄い差分エンジン)")
    p.add_argument("--curr-verdicts", dest="curr_verdicts", required=True,
                   help="今月=target 請求対象月の per-月 verdict JSON")
    p.add_argument("--prev-verdicts", dest="prev_verdicts", required=True,
                   help="先月=target-1ヶ月の per-月 verdict JSON")
    p.add_argument("--lookback-12mo", dest="lookback",
                   help="差分該当取引先のみの12ヶ月発行履歴 JSON (任意)")
    p.add_argument("--contract-end", dest="contract_end",
                   help="契約終了月データ JSON (任意・二次情報)")
    p.add_argument("--fidelity-report", dest="fidelity_report", required=True,
                   help="C06 mfk_fetch_audit.py の fetch fidelity report JSON (必須入力)。"
                        "exit_code==1 (当月/先月 NG) で fail-closed 非emit・==3 (lookback 部分欠損) で "
                        "STATE_NEW 該当行を要確認へ降格する")
    p.add_argument("--target-month", dest="target_month",
                   help="対象月 YYMM (省略時は curr-verdicts の target_month→実行日から導出)")
    a = p.parse_args(argv)

    try:
        curr_doc = _load_json(a.curr_verdicts)
        prev_doc = _load_json(a.prev_verdicts)
    except (OSError, ValueError) as e:
        sys.stderr.write(f"[period-report] verdict 入力の読込に失敗 (fail-closed): {e}\n")
        return 2

    # fetch fidelity report は必須入力。MF実績起点の判定は最新性が担保されて初めて成立するため、
    # 読込失敗は fail-closed、当月/先月の fidelity 違反 (exit1) は漏れ確認処理そのものを実行しない。
    try:
        fidelity = _load_json(a.fidelity_report)
    except (OSError, ValueError) as e:
        sys.stderr.write(f"[period-report] fetch fidelity report の読込に失敗 (fail-closed): {e}\n")
        return 2
    if isinstance(fidelity, dict) and fidelity.get("exit_code") == 1:
        sys.stderr.write(
            "[period-report] ⛔ 当月/先月の fetch fidelity 違反 (C06 exit1) のため fail-closed。"
            f"漏れ確認レポートを emit しません (overall={fidelity.get('overall')})。"
            "最新の取得をやり直してから再実行してください。\n")
        return 1

    lookback = None
    if a.lookback:
        try:
            lookback = _load_json(a.lookback)
        except (OSError, ValueError) as e:
            sys.stderr.write(f"[period-report] 12ヶ月履歴の読込に失敗 (fail-closed): {e}\n")
            return 2

    contract_end = None
    if a.contract_end:
        try:
            contract_end = _load_json(a.contract_end)
        except (OSError, ValueError) as e:
            sys.stderr.write(f"[period-report] 契約終了月データの読込に失敗 (fail-closed): {e}\n")
            return 2

    report = build_report(curr_doc, prev_doc, lookback=lookback,
                          contract_end=contract_end, target_month=a.target_month,
                          fidelity=fidelity)

    # 12ヶ月ルックバック未実行の可視化 (ユーザー要件 C2/C3): --lookback-12mo 未指定のまま
    # 前月なし今月あり (新規/年→月切替) 行があると、年契約→月額切替の裏付けが未確認になる。
    # データ源は MF 実績の12ヶ月履歴であり請求確認シートの開始月には依存しない (源の取り違え防止)。
    # lookback は未指定 (a.lookback なし=None) でも空ファイル ([]/{}) でも「実質未実行」として
    # 一貫して警告する (loaded content の真偽で判定・空データ縁ケースの取りこぼしを防ぐ)。
    new_rows = sum(1 for r in report if r.get("period_diff") == "新規/年→月切替")
    if not lookback and new_rows:
        sys.stderr.write(
            f"[period-report] ⚠️ 12ヶ月履歴データなし (--lookback-12mo 未指定 or 空) のまま 前月なし今月あり "
            f"{new_rows} 件を分類しました。これらの『年契約→月額切替』裏付けは未確認です。MF実績(GET)の"
            "12ヶ月履歴を --lookback-12mo に渡して再実行してください (シート開始月とは無関係=省略しない)。\n")

    print(json.dumps(report, ensure_ascii=False, indent=2))

    if any(r.get("gap_check") == GAP_ACTION for r in report):
        return 1  # 分類上の要確認 (発行漏れ候補) あり。
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
