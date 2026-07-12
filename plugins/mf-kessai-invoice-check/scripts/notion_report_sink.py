#!/usr/bin/env python3
# /// script
# name: notion_report_sink
# purpose: 前月↔今月の発行漏れ比較レポートを単一の恒久 DB へ非破壊冪等 upsert する決定論 sink
#          (Design D)。report_toggle_block は歴史的キー名のまま出力先ブロック/見出しとして扱い、
#          トグル内 DB (in-block) または見出し2直下 DB (under-heading) を最優先で更新対象にする。
#          API は block_id 親 DB を『作成』できないが既存 DB の『更新』はできる。既存 DB が無ければ
#          親ページ直下へ新規作成する (page-created)。単一 DB に複数月
#          を保持し、同一 (対象月,取引先,商品) の再実行のみ上書き・以前月の行は削除しない (deleted 0)。
# inputs:
#   - argv: --rows FILE (C03 分類済みレポート行 JSON list) --target YYMM [--apply --verified] [--config PATH]
#   - config: mf-kessai-config.default.json (配布既定) + .mf-kessai-config.json (ローカル上書き) の
#             notion.report_toggle_block (出力先ブロック/見出し) + notion.report_parent_page (新規作成/探索先ページ)
# outputs:
#   - stdout: upsert 結果 JSON {created, updated, skipped, deleted(=0), collapsed_multi_contract,
#             report_db_id, db_location(in-block/under-heading/page/page-created), db_created, placement}
#   - stderr: violation
#   - exit: 0=OK / 1=部分失敗 / 2=fail-closed (target/親ページ未設定・rows 不正)
# contexts: [C, E]
# network: true   # Notion REST (ブロック/ページ子ブロック list + DB 探索/作成/列 PATCH + 行 upsert)。MF へは書かない
# write-scope: notion:report-db-in-toggle (report_toggle_block に紐づく単一恒久レポート DB へ列 PATCH + 行 upsert・既存 DB が無ければ report_parent_page 直下へ)
# dependencies: [notion_transport, build_notion_db, mfk_api]
# requires-python: ">=3.11"
# ///
"""前月↔今月の発行漏れ比較レポートを単一恒久 DB へ非破壊冪等 upsert する決定論 sink (Design D)。

責務 (C04):
  1. **出力先 DB の解決 (指定ブロック/見出し優先・表示名非依存)**: ``report_toggle_block`` がトグル
     ならその中の child_database、プレーン見出し2ならその見出し直下 (次見出しまで) の child_database を
     最優先で更新対象にする。**指定トグル/見出しはこのレポート専用ゆえ、配下 DB は表示名に依存せず
     構造的位置で同定する** (ユーザーが『請求漏れ確認レポート』等どんな名前で手作りしても認識する・
     title 前方一致 _TITLE_PREFIX は同点解消/後方互換のヒントに留める)。無ければ親ページ
     (``report_parent_page``) 直下の既存 report DB (ここは無関係 DB が同居しうるので title 前方一致で
     限定)、どれも無ければ見出しの下 (ページ直下) へ新規作成する。**Notion API は database を block_id
     (トグル) 親で『作成』できないが、UI で作られたトグル内 DB の『更新』(行 upsert・列 PATCH) はできる**
     ため、ユーザーがトグル内に作った DB をそのまま更新できる。既存 DB の title 列名が『取引先名』でなく
     Notion 既定の『名前』等でも、_ensure_db_schema が title 型プロパティの実名を検出し行 upsert が正しい
     列へ書く。db_location (in-block/under-heading/page/page-created) を stdout で開示する。
  2. **8 列スキーマ (列順 SSOT)**: [取引先名(title), 対象月(rich_text/YYYY-MM), 漏れチェック(checkbox),
     商品名(rich_text), 先月の金額(number/yen), 今月の金額(number/yen), 先月と今月の比較(rich_text),
     コメント(rich_text)] をこの左→右順で固定する。title(=各行=ページ名)=取引先名を先頭に置き
     Notion の title 最左固定と定義順を一致させる。**対象月列**は単一 DB で複数月を区別する。既存 DB に
     対象月列が無ければ _ensure_db_schema が PATCH で後付けする (非破壊)。漏れチェックは checkbox
     (正常=✓ / 要対応=☐)。金額は税抜。列型写像は build_notion_db.build_property を再利用する。
  3. **非破壊冪等 upsert**: 単一 DB へレポート行を upsert する。行同定キー = (対象月 YYYY-MM,
     取引先名, 商品名)。同月内の 2/3 営業日目再実行は同一キーで 1 行へ収束させる (重複行 0)。固定列に
     契約IDは永続化しないため、契約ID違いは要対応優先で collapse し collapsed_multi_contract に計上する。
     **非破壊マージ = 以前 run で書いた行も別月の行も今回入力に無くても削除しない** (deleted 常時 0・
     全情報保持・clear-then-insert でない)。手動追記運用は無い前提ゆえ frozen 列は設けない。
  4. **折り返し (wrap)**: 全列の折り返し表示はビュー format 設定で API 非公開ゆえ、placement の
     view_format_note で UI 手順を毎回開示する (列順は properties 定義順で反映できるが wrap/幅は不能)。

設計背景 (Design B/C からの是正):
  当初は『月次スナップショット DB=毎月新規 DB をページ直下へ』(Design B)、次に『ページ直下 DB +
  トグル内 link_to_page 索引』(Design C) を採ったが、実運用でユーザーは Notion UI でトグル内に
  report DB を作って運用しており (API は block_id 親 DB を作成できないだけで更新はできる)、Design B/C は
  そのトグル内 DB を更新せず別 DB を作る乖離があった。Design D は出力先をトグル内 DB へ一本化し、
  複数月を『毎月新規 DB』でなく『単一 DB + 対象月列』で保持することで、API 制約 (block_id 親 DB を
  作れない) と『トグル内に反映』要件を両立する。トグル内に DB が無い新規セットアップ時のみ、見出しの
  下 (ページ直下) へ新規作成し、ユーザーが UI でトグルへドラッグすれば以後は自動更新される。
  全ての API 経路は notion_transport._req 経由で、テストは req 引数に fake-store を差し替えて
  network 非依存で検証する (既存 test_notion_reconcile_sink の offline 契約踏襲)。
"""
import argparse
import json
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_PLUGIN_ROOT = os.path.abspath(os.path.join(_HERE, ".."))
sys.path.insert(0, os.path.join(_PLUGIN_ROOT, "lib"))
sys.path.insert(0, os.path.join(_PLUGIN_ROOT, "skills", "run-mf-invoice-db-setup", "scripts"))

from notion_transport import _req, _notion_token, _rich_text_plain  # noqa: E402
from build_notion_db import build_property  # noqa: E402  DB 生成の列型写像を再利用 (SS-F2)
from mfk_api import load_config  # noqa: E402
from mfk_reconcile import normalize as _normalize_name  # noqa: E402  名寄せ SSOT (NFKC・SKILL Gotcha5)

# Notion rich_text の content は 1 要素あたり 2000 文字上限。超過は切り詰める。
_MAX_RICH_TEXT = 2000

# --- 8 列スキーマ (列順 SSOT: この左→右順で固定する) --------------------------------
# Design D (単一恒久 DB・対象月列で複数月を保持): トグル配下に置いた 1 つの DB を毎回上書き更新
# するため、月をまたいで行が共存する。対象月 (YYYY-MM) 列で月を区別し、以前月の行を非破壊保持する。
PROP_CUSTOMER = "取引先名"                 # title    (= 各行 = ページ名)
PROP_TARGET_MONTH = "対象月"               # rich_text (YYYY-MM・単一 DB で月を区別する)
PROP_MISSING_CHECK = "漏れチェック"       # checkbox (正常=✓チェックあり / 要対応=☐チェックなし)
PROP_PRODUCT = "商品名"                    # rich_text
PROP_PREV_AMOUNT = "先月の金額"            # number(yen)  税抜
PROP_CURR_AMOUNT = "今月の金額"            # number(yen)  税抜
PROP_COMPARISON = "先月と今月の比較"       # rich_text (テキスト説明)
PROP_COMMENT = "コメント"                  # rich_text

# 列順 SSOT の配列。DB 生成時の properties 構築順 = Notion 上の列の左→右順。
# 取引先名 (title) を先頭に置く: Notion は table view で title 列を最左に固定するため、title を
# COLUMN_ORDER 先頭に定義することで「定義順 = 実表示順」を一致させ、列順を確実に設定通りにする
# (title を非先頭に置くと Notion が最左へ引き上げ定義順と表示順がズレる)。対象月を title 直後の
# 2 列目に置き月でグルーピング/フィルタしやすくする。漏れチェック(checkbox)は 3 列目。
COLUMN_ORDER = [
    PROP_CUSTOMER,
    PROP_TARGET_MONTH,
    PROP_MISSING_CHECK,
    PROP_PRODUCT,
    PROP_PREV_AMOUNT,
    PROP_CURR_AMOUNT,
    PROP_COMPARISON,
    PROP_COMMENT,
]

# C03 producer (mfk_period_report.py) が emit する行キー → 本 sink の 8 列への写像 (SEAM SSOT)。
# producer/consumer のキー語彙をここで一元宣言し、seam 断裂 (キー名不一致で列が空になる) を防ぐ。
# _build_row_props はこの producer キー (各値の第一 alias) を読む。ROW_CONTRACT を SSOT として
# 実効化する担保は 2 段: (1) test_row_contract_maps_every_producer_key_to_column が本 dict の
# 各 producer キーを _build_row_props で辿り mapped 列へ着地することを assert し drift を検出する
# (宣言と実装の乖離を機械 fail させる)、(2) test_seam_c05_output_populates_all_seven_columns が
# C03 実出力 → 本 sink を実 pipe で貫通して 8 列全充足を検証する (isolation では捕捉不能)。
ROW_CONTRACT = {
    "gap_check": PROP_MISSING_CHECK,   # 漏れチェック (checkbox: 正常=✓/要対応=☐)
    "customer": PROP_CUSTOMER,         # 取引先名 (title)
    "target_month": PROP_TARGET_MONTH, # 対象月 (YYYY-MM・単一 DB で月を区別)
    "product": PROP_PRODUCT,           # 商品名
    "prev_amount": PROP_PREV_AMOUNT,   # 先月の金額 (税抜)
    "amount": PROP_CURR_AMOUNT,        # 今月の金額 (税抜・C03 の amount=当月期待/実額)
    "period_diff": PROP_COMPARISON,    # 先月と今月の比較 (テキスト説明)
    "comment": PROP_COMMENT,           # コメント (事情説明)
}

# 漏れチェックは checkbox: 正常=チェックあり(True) / 要対応(発行漏れ候補)=チェックなし(False)。
# チェックの有無だけで直感的に「請求できている(✓)/要対応(☐)」を判別できるようにする。

# 列名 -> build_notion_db.build_property が解釈する型 spec。
_COLUMN_SPECS = {
    PROP_MISSING_CHECK: {"type": "checkbox"},
    PROP_CUSTOMER: {"type": "title"},
    PROP_TARGET_MONTH: {"type": "rich_text"},
    PROP_PRODUCT: {"type": "rich_text"},
    PROP_PREV_AMOUNT: {"type": "number"},
    PROP_CURR_AMOUNT: {"type": "number"},
    PROP_COMPARISON: {"type": "rich_text"},
    PROP_COMMENT: {"type": "rich_text"},
}

# レポート DB の title 前方一致キー (『請求漏れ比較レポート』で始まる child_database を報告 DB とみなす)。
_TITLE_PREFIX = "請求漏れ比較レポート"

# 折り返し(wrap)/列幅はビュー format 設定で Notion 公開 API (2022-06-28) は操作不能
# (列順は DB 作成時の properties 定義順で既定ビューへ反映できるが、wrap/幅はビュー format ゆえ
# API 非公開=placement の append 制約と同じ能力境界)。placement で UI 手順を毎回開示する SSOT。
_VIEW_FORMAT_NOTE = (
    "全列の折り返し表示 (wrap) はプロパティ(スキーマ)設定でなくビュー表示設定で、"
    "Notion 公開 API では設定できない。Notion UI でこの DB ビューの『…』メニュー→"
    "『すべての列を折り返す (Wrap all columns)』を一度トグルすると以後ビューに永続する。")


class SinkError(RuntimeError):
    """fail-closed で停止すべき設定/前提エラー (main が exit 2 に写像する)。"""


# ---------------------------------------------------------------------------
# 純関数 (正規化 / タイトル / プロパティ整形)
# ---------------------------------------------------------------------------

def _norm(value):
    """None を '' に、他は str() + strip して返す (キー比較を安定化)。"""
    return "" if value is None else str(value).strip()


def _valid_target(target):
    """target が YYMM (数字 4 桁・月 01-12) かを判定する。"""
    t = _norm(target)
    if len(t) != 4 or not t.isdigit():
        return False
    return 1 <= int(t[2:]) <= 12


def target_to_yyyymm(target):
    """YYMM (例 '2607') を YYYY-MM (例 '2026-07') へ展開する。20xx を前置する。"""
    t = _norm(target)
    return f"20{t[:2]}-{t[2:]}"


def _child_db_title(block):
    """child_database ブロックの title (plain str) を返す (空/欠落は '')。"""
    if not isinstance(block, dict):
        return ""
    return (block.get("child_database") or {}).get("title") or ""


def _title_plain(prop):
    """Notion title プロパティを plain text へ連結する (空/欠落は '')。"""
    if not isinstance(prop, dict):
        return ""
    return "".join(
        (rt.get("text") or {}).get("content") or rt.get("plain_text") or ""
        for rt in (prop.get("title") or [])
    )


def _rt(value):
    """rich_text プロパティ。content の改行 \\n はそのまま保持する (split しない)。"""
    s = str(value if value is not None else "")
    return {"rich_text": [{"text": {"content": s[:_MAX_RICH_TEXT]}}]}


def _row_customer(row):
    return _norm(row.get("customer") or row.get("取引先名") or row.get("customer_name"))


def _row_product(row):
    return _norm(row.get("product") or row.get("商品名") or row.get("product_name"))


def _row_contract_id(row):
    return _norm(row.get("contract_id") or row.get("契約ID"))


def _row_end_client(row):
    """行のエンドクライアント名 (C03 が collapse identity 判別用に透過する非表示フィールド)。

    代理店が同一 (取引先,商品) を複数エンドクライアントへ契約する場合の契約 disambiguator。
    contract_id と対で『契約 identity』を成す (名寄せ SSOT で正規化)。
    """
    return _normalize_name(row.get("end_client") or row.get("エンドクライアント名") or "")


def _contract_identity(row):
    """行の契約 identity = (契約ID, エンドクライアント名)。collapse で phantom と別契約を判別する。

    同一 (対象月,取引先,商品) へ collapse する 2 行の identity が一致すれば、それは『同一契約が
    ID照合↔名前照合で二重化した phantom』(record2 型: contract_id/エンドクライアント共に空で一致)。
    identity が異なれば代理店の別エンドクライアント=真の別契約 (HOSONO 甲様/乙様 型)。この判別で
    別契約の発行漏れを発行済みで黙って正常化する漏れ隠蔽 (false-negative) を防ぐ。
    """
    return (_row_contract_id(row), _row_end_client(row))


def _same_contract_identity(a, b):
    """2 行が同一契約 (phantom 由来の二重化) か。identity 完全一致で True。

    どちらも contract_id/エンドクライアント未設定 (("","")) の場合も一致=phantom 扱い。これは安全:
    真に別契約が両方 disambiguator 無しなら C03 の compare_periods が (取引先,商品) キーの setdefault で
    1 ペアへ既に collapse 済ゆえ、sink へ 2 行として届く同一空 identity は ID↔名前 split の phantom に
    限られる (別契約が別々に届くのは disambiguator を持つときだけ)。
    """
    return _contract_identity(a) == _contract_identity(b)


def _amount(row, *keys):
    """row から金額を取り出す (最初に見つかった非 None を返す)。0 は有効値。"""
    for k in keys:
        if k in row and row[k] is not None:
            return row[k]
    return None


def _stored_key(target_month, customer, product):
    """単一恒久 DB の既存ページを索引する『回収可能』キー (対象月, 取引先名, 商品名)。

    Design D では 1 つの DB に複数月の行が共存するため、同定キーの先頭に対象月 (YYYY-MM) を含める。
    これにより 2026-06 の行と 2026-07 の行は別行として保持され (非破壊)、同一月・同一取引先・同一
    商品の再実行のみ 1 行へ収束する (月内冪等)。target_month は _norm で正規化する (空は '')。

    固定スキーマは contract_id を persist しないため (property_order に契約ID列なし)、既存ページから
    回収できる同定キーは (対象月, 取引先名, 商品名) に限られる。contract_id は C03 が同定に使う論理
    メタだが本 sink では persist しない (=recoverable でない)。

    設計判断 (記録): 同一対象月・同一取引先・同一商品に契約IDだけ異なる複数契約が同居する場合、
    このキーでは 1 行へ収束する (multi-contract collapse)。多契約×同一商品は稀という前提で
    8 列固定を優先した意思決定であり、collapse 時は要対応を優先保持 (_prefer_action) して
    真の発行漏れが正常行に上書きされる false-negative を防ぐ。collapse 件数は stdout の
    collapsed_multi_contract に計上し常態化を可観測にする (常態化すれば 8 列目 contract_id 追加へ
    の移行トリガ)。

    キーは名寄せ SSOT mfk_reconcile.normalize (NFKC + 敬称/法人格/空白/中黒除去 + lower) で
    正規化する (SKILL Gotcha5)。表示 title は raw のまま・キー算出だけ正規化することで、macOS/MF
    API 由来のカタカナ NFD↔NFC 揺れや全角半角差で同一取引先が別行に割れる (=同月2回実行で重複行が
    出て冪等保証 C7/OUT1 が崩れる) のを防ぐ。新規行キーと既存ページ回収キー (_page_match_key) は
    同じ正規化を通るため索引が一致する。
    """
    return (_norm(target_month), _normalize_name(customer), _normalize_name(product))


def _severity_rank(row):
    """行の漏れチェック severity。要対応(発行漏れ候補)=1 を正常=0 より優先する。"""
    check = _norm(row.get("gap_check") or row.get("check") or row.get("漏れチェック"))
    return 1 if check == "要対応" else 0


# C03 が構造的正常事由 (継続発行/年契約周期/契約完了/トライアル完了/対象外) で正常化した行の period_diff 標識。
# これらは「バグ由来 false-positive の権威ある訂正」であり、cross-run safe guard が前 run の
# 要対応を無条件保持して打ち消してはならない (例: 金子金物が C03 annual fix 前に 要対応 で
# persist 済みでも、fix 後の 年契約周期 正常化を反映する=elegant-review F-D 是正)。
# 『継続発行』(要件1・2026-07-10): 今月あり×前月あり=月契約の継続発行は権威ある月契約正常
# (両月に請求=定義上の月契約であり年契約でない) ゆえ、前 run が要対応☐でも今 run の継続発行で
# 正常✓へ訂正する。reliable_issued 未確定 (legacy/verdict-issued 行) でも確実に正常✓を反映し
# 『金額あるのにチェックが入らない』を根治する。金額 drift (過少請求等) は REVIEW_* コメント注記
# に留め正常✓は据え置く (主張範囲=発行の存在に限定・OQ-9)。
# 『新規/年→月切替』(2026-07-10・Fix A の cross-run 保全): 前月なし今月あり=今月に実発行あり=定義上
# 発行漏れでない (STATE_NEW は curr_issued=True 前提) ゆえ構造的正常。要件1の原則を STATE_CONTINUED
# から NEW 経路へ拡張した Fix A(mfk_period_report) が gap=正常✓ で emit する行を、cross-run guard が
# reliable_issued=False(legacy/verdict-issued の新規) のとき marker 非該当で☐へ再反転させる非対称
# (3体エレガント検証で収束検出) を解消し、record1(新規トライアル発行) が DB 上☐に残らないようにする。
_STRUCTURAL_NORMAL_MARKERS = ("継続発行", "新規/年→月切替", "年契約周期", "契約完了",
                              "トライアル完了", "対象外")


def _is_structural_normal(row):
    """行が構造的正常事由による正常化か (正常 かつ period_diff が上記標識を含む)。

    bare な 正常 (単に今月発行あり等) とは区別する: bare 正常は cross-run guard で前 run の
    要対応を保持するが、構造的正常事由は非請求が正常である積極的根拠ゆえ訂正を許す。
    """
    if _severity_rank(row) != 0:
        return False
    pd = _norm(row.get("period_diff") or row.get("先月と今月の比較") or row.get("comparison"))
    return any(m in pd for m in _STRUCTURAL_NORMAL_MARKERS)


def _is_reliable_mf_issued(row):
    """行が MF実績由来で当月 active 発行済みか (C05 reliable_issued=True) = 権威ある実額訂正 (K4)。

    _STRUCTURAL_NORMAL_MARKERS と**同格**の cross-run guard bypass 事由。前 run で要対応☐に立った行
    でも、今 run で MF が実際に発行済み (reliable_issued=True・supply_state==active) と確認できたなら、
    その権威ある実額訂正で正常☑へ上書きする (bare 正常=単に入力 gap_check が正常 とは区別する)。
    C05→C03 `_emit` が report 行 top-level へ `reliable_issued` を焼くのが源。
    """
    if _severity_rank(row) != 0:
        return False
    return bool(row.get("reliable_issued"))


# 要対応行へ畳み込んだ発行済み (reliable_issued) 実額の累計を保持する内部標識。
# 要対応行が source 由来で持つ「自己の今月金額」と、fold で別契約から畳み込んだ「発行済み実額」を
# 区別するために使う (両者は同じ number 列 amount に載るため、標識なしでは own を発行済みと誤って
# 合算してしまう)。_build_row_props は既知キーのみ読むため Notion props へは漏れない。
_ISSUED_CARRY_KEY = "_issued_carry"
# 上記の「先月の金額」版 (K-PREV: collapse が今月分だけΣ保全し先月分を保全しない非対称を根治・
# ユーザー確定2026-07-10=先月/今月どちらか一方だけ空欄に見える誤表示の温床だった)。
_ISSUED_CARRY_KEY_PREV = "_issued_carry_prev"


def _prefer_action(a, b):
    """同一 (取引先,商品) 衝突時に残す行を決める (F-α safe guard)。

    要対応(発行漏れ候補)を正常が上書きして漏れを隠す false-negative を防ぐため、severity の
    高い方 (要対応) を保持する。両方が同 severity の要対応 (契約ID違いの複数漏れが 1 行へ
    collapse) の場合は、後着を基に両者の comment を改行連結でマージして片方の漏れ詳細が消えない
    ようにする (F-17: 件数だけ数えて内容を捨てる情報損失を防ぐ)。正常×正常 (複数エンドクライアント/
    契約が全て発行済み) は _merge_issued_amounts で両者の発行済み実額を合算保全する (後着だけ残して
    先行の実額を黙って落とす=発行済み金額の過少表示を防ぐ・C5 sink側の正常×正常残穴の根治)。

    C03 (要因C5 sink側): severity が異なる collapse では要対応を保持しつつ、負ける正常行が
    発行済み (reliable_issued=True の実額) なら**その今月金額を要対応行へ Σ 引き継ぐ** (発行済み実額を
    要対応・null 行で潰さない=K4 権威訂正の対称適用)。発行済みが複数畳み込まれるときは総額を合算し、
    要対応が畳込順の最後でないと 2件目以降の実額が脱落する過少報告 (fold 順依存) を防ぐ (正常×正常
    と同じ Σ 不変則の対称適用)。代理店/複数エンドクライアントが 1 商品へ collapse するとき、
    発行済み実額保全 ∧ 漏れ隠蔽なし を両立させる。
    """
    ra, rb = _severity_rank(a), _severity_rank(b)
    if ra != rb:
        action, normal = (a, b) if ra > rb else (b, a)
        # K4 の同一run collapse への対称適用だが、**契約 identity で phantom と別契約を判別**する
        # (3体エレガント検証 CRITICAL の是正)。正常化して良いのは「同一契約が ID照合↔名前照合で
        # 二重化した phantom」(record2 型) に限る: その場合 negative(要対応) 側は実体のない重複ゆえ、
        # 当月の権威ある実発行 (reliable_issued) で正常✓へ収束させてよい (症状②の根治)。
        # 一方、identity が異なる=代理店の別エンドクライアント等の**真の別契約**では、負ける要対応が
        # 本物の発行漏れでありうるため正常化せず要対応を保持する (漏れ隠蔽 false-negative を防ぐ・
        # 「多契約×同一商品は稀」前提が HOSONO 甲様/乙様等の実データで反証されている安全側)。
        if _is_reliable_mf_issued(normal) and _same_contract_identity(action, normal):
            return _resolve_to_reliable_normal(normal, action)
        # 別契約 or 非 reliable → 要対応を保持し発行済み実額を保全 (漏れを隠さず金額も失わない)。
        return _preserve_issued_amount(action, normal)
    if ra == 1:  # 要対応×要対応 → comment をマージした後着行 (情報保全)。
        return _merge_action_comments(b, a)
    return _merge_issued_amounts(b, a)  # 正常×正常 → 発行済み実額を合算保全 (後着で先行を潰さない)。


def _resolve_to_reliable_normal(normal, action):
    """severity 混在 collapse で MF実発行 (reliable_issued) 正常が要対応に勝つ (K4 の同一run 対称適用)。

    今月に権威ある実発行がある (取引先,商品) は定義上『発行漏れ』でない → 正常✓ を採り、発行済み
    実額 (normal の今月金額) を保全する。負けた要対応候補 (別契約ID の phantom/重複 gap の可能性が
    高い=多契約×同一商品は稀という collapse 前提) はコメントに根拠を注記して黙殺しない (漏れ隠蔽と
    情報損失の両方を避ける)。bare 正常 (reliable_issued 無し) は本経路に来ず _preserve_issued_amount で
    要対応を保持するため、真の漏れが bare 正常で隠れることはない (安全側の非対称)。
    """
    merged = dict(normal)
    cn = _norm(normal.get("comment") or normal.get("コメント"))
    ca = _norm(action.get("comment") or action.get("コメント"))
    if ca:
        note = ("[複数契約の統合行] 当月は MF 実発行あり=正常✓ (発行漏れではない)。"
                f"同一取引先・商品に別契約の要対応候補があったが当月実発行で充足 (候補根拠: {ca})")
    else:
        note = "[複数契約の統合行] 当月は MF 実発行あり=正常✓ (発行漏れではない)"
    merged["comment"] = f"{cn} / {note}" if cn else note
    return merged


def _preserve_issued_amount(action, normal):
    """collapse で要対応 (action) を保持しつつ発行済み (normal) の今月/先月金額を Σ 保全する (C03)。

    代理店/複数エンドクライアントが同一 (対象月,取引先,商品) へ collapse するとき、要対応 severity は
    保持して漏れを隠さない一方、発行済み (reliable_issued) 行の実額が要対応・null 行で上書きされ
    今月金額=null になるのを防ぐ (実レポート: HOSONO/マルブン/芦田/野嵩商会/サクラパックス が
    今月金額=null だった症状の sink 側根治)。**発行済みが複数畳み込まれるときは総額を Σ 合算する**:
    要対応が畳込順の最後でないと 2件目以降の reliable 正常実額が今月金額から脱落する過少報告
    (fold 順依存) を防ぐため、畳み込んだ発行済み実額を内部標識 `_ISSUED_CARRY_KEY` に累計し、
    要対応行が source 由来で持つ自己金額とは区別する (自己金額は発行済み実額で上書きも合算もせず
    別途あることのみ注記する=own amount と発行済み実額を混同しない・注記と金額列の正確性)。
    正常×正常 `_merge_issued_amounts` の Σ 不変則を severity 混在経路へ対称適用した形。

    **先月金額も今月金額と対称的に Σ 保全する** (K-PREV・ユーザー確定2026-07-10): 今月分だけを
    保全し先月分を要対応行の null のまま放置すると、実際には先月も発行済みなのに「先月空欄・
    今月あり」という新規発行に見える誤表示になる (実例: ツネマツガス チイキズカン利用料
    (2年目以降) — 別契約が先月/今月とも 50000円発行済みなのに、collapse 後は先月だけ空欄に
    見えていた)。C03 (mfk_period_report.py) の `_amount_of` 是正により prev_amount が非 None
    なら常に「実際に発行された額」を意味するため (期待額 fallback を廃止済み)、今月側の
    reliable_issued 判定に相当する追加ゲートは不要 (非 None = 発行済みで十分)。
    """
    action_amt = _amount(action, "amount", "curr_amount", "今月の金額")
    normal_amt = _amount(normal, "amount", "curr_amount", "今月の金額")
    action_prev = _amount(action, "prev_amount", "先月の金額")
    normal_prev = _amount(normal, "prev_amount", "先月の金額")
    carried = action.get(_ISSUED_CARRY_KEY)
    carried_prev = action.get(_ISSUED_CARRY_KEY_PREV)

    notes = []
    merged = dict(action)

    if normal_amt is not None and _is_reliable_mf_issued(normal):
        if carried is not None:
            total = carried + normal_amt
            merged["amount"] = total
            merged[_ISSUED_CARRY_KEY] = total
            notes.append(f"別契約の発行済み実額を合算保全 {carried}円 + {normal_amt}円 = {total}円")
        elif action_amt is None:
            merged["amount"] = normal_amt
            merged[_ISSUED_CARRY_KEY] = normal_amt
            notes.append(f"別契約の発行済み実額 {normal_amt}円 を今月金額へ保全")
        else:
            notes.append(f"別契約に発行済み実額 {normal_amt}円 あり")

    if normal_prev is not None:
        if carried_prev is not None:
            total_p = carried_prev + normal_prev
            merged["prev_amount"] = total_p
            merged[_ISSUED_CARRY_KEY_PREV] = total_p
            notes.append(f"別契約の発行済み先月実額を合算保全 {carried_prev}円 + {normal_prev}円 = {total_p}円")
        elif action_prev is None:
            merged["prev_amount"] = normal_prev
            merged[_ISSUED_CARRY_KEY_PREV] = normal_prev
            notes.append(f"別契約の発行済み先月実額 {normal_prev}円 を先月金額へ保全")
        else:
            notes.append(f"別契約に発行済み先月実額 {normal_prev}円 あり")

    if not notes:
        # 保全すべき発行済み実額なし (今月/先月とも) → 要対応行をそのまま返す (従来挙動)。
        return action

    note = ("[複数契約の統合行] " + " / ".join(notes) +
            " (この取引先・商品には要対応の契約も含むため漏れチェックは要対応のまま)")
    ca = _norm(merged.get("comment") or merged.get("コメント"))
    merged["comment"] = f"{ca} / {note}" if ca else note
    return merged


def _merge_action_comments(base, other):
    """base を基に other の comment を連結マージした新 row を返す (要対応 collapse の情報保全)。

    3-way 以上の collapse でも発行済み実額の保全を維持する: 先行の _preserve_issued_amount が
    要対応行へ引き継いだ発行済み実額 (amount 非 None) を、後続の要対応×要対応マージで base 側の
    None が上書きして潰さないよう、非 None の amount を優先継承する (F-TRADE-1: 3者衝突で
    「発行済み実額保全 ∧ 要対応保持」の両立が処理順に依存して破れ、金額=null なのに注記だけ
    『保全』と主張する自己矛盾行が出るのを防ぐ・順序非依存化)。先月金額 (prev_amount) も
    今月と対称に非 None 優先継承する (K-PREV: 先月分だけ 3-way マージで脱落する非対称を防ぐ)。

    **両者が別契約の自己実額を持つ (base_amt/other_amt とも非 None) 場合は Σ 合算する**
    (K-SUM: 従来は base 側の実額だけ残し other 側の実額を注記もせず無言で捨てていた=同一
    (取引先,商品) に契約ID違いの新規契約が複数月内発行された場合の過少表示。近代プラント/OWB/
    マルワ/ミラタップ/京浜貿易/野嵩商会/マスヤ 等の「新規/年→月切替」複数契約 collapse で実額
    110,000円のところ 55,000円のみ表示される症状の根治・正常×正常 (_merge_issued_amounts) と
    同じ Σ 不変則の対称適用)。先月実額も同様に Σ 合算する。
    """
    cb = _norm(base.get("comment") or base.get("コメント"))
    co = _norm(other.get("comment") or other.get("コメント"))
    merged = dict(base)
    base_amt = _amount(base, "amount", "curr_amount", "今月の金額")
    other_amt = _amount(other, "amount", "curr_amount", "今月の金額")
    amt_note = None
    if base_amt is None and other_amt is not None:
        merged["amount"] = other_amt
        # 畳み込んだ発行済み実額の累計標識も引き継ぐ (要対応×要対応マージ後に更に発行済みが
        # 畳み込まれても _preserve_issued_amount の Σ 保全が継続する=4-way 経路での再脱落を防ぐ)。
        oc = other.get(_ISSUED_CARRY_KEY)
        if oc is not None:
            merged[_ISSUED_CARRY_KEY] = oc
    elif base_amt is not None and other_amt is not None:
        total = base_amt + other_amt
        merged["amount"] = total
        amt_note = f"要対応の別契約の今月実額を合算 {base_amt}円 + {other_amt}円 = {total}円"
    base_prev = _amount(base, "prev_amount", "先月の金額")
    other_prev = _amount(other, "prev_amount", "先月の金額")
    prev_note = None
    if base_prev is None and other_prev is not None:
        merged["prev_amount"] = other_prev
        op = other.get(_ISSUED_CARRY_KEY_PREV)
        if op is not None:
            merged[_ISSUED_CARRY_KEY_PREV] = op
    elif base_prev is not None and other_prev is not None:
        total_p = base_prev + other_prev
        merged["prev_amount"] = total_p
        prev_note = f"要対応の別契約の先月実額を合算 {base_prev}円 + {other_prev}円 = {total_p}円"
    cid_b, cid_o = _row_contract_id(base), _row_contract_id(other)
    if cid_b and cid_o and cid_b != cid_o:
        merged["comment"] = f"[複数契約の統合行] 契約{cid_b}: {cb} / 契約{cid_o}: {co}".strip()
    elif cb and co and cb != co:
        merged["comment"] = f"{cb} / {co}"
    else:
        merged["comment"] = cb or co
    extra = " / ".join(n for n in (amt_note, prev_note) if n)
    if extra:
        merged["comment"] = f"{merged['comment']} / {extra}" if merged.get("comment") else extra
    return merged


def _merge_issued_amounts(base, other):
    """正常×正常 collapse で両行の発行済み実額を合算保全する (C03・C5 sink側の正常×正常残穴の根治)。

    同一 (対象月,取引先,商品) に複数エンドクライアント/契約の発行済み (正常) 行が collapse するとき、
    後着 base だけ残して先行 other の実額を黙って落とすと発行済み金額が過少表示される (F-TRADE-1 の
    severity 混在修正が救わない正常×正常ケース: HOSONO 甲様 210000 + 乙様 70000 が 70000 のみ表示され
    210000 が注記もなく消失)。両者が非 None の実額を持つなら合算し内訳を comment へ注記して、発行済み
    金額が隠れない ∧ 実額完全性を両立する (合算=当該取引先・商品への当月発行総額)。片方のみ非 None なら
    それを採り (後着 None で発行済み実額を上書きしない)、両者 None なら base を返す (従来挙動)。
    左畳込 (_prefer_action の累積適用) でも 3 件以上のエンドクライアントの総額を順序非依存に保全する。
    先月分 (prev_amount) も今月分と対称に合算保全する (K-PREV: 今月分だけ合算し先月分を素通しする
    非対称が「先月空欄・今月金額あり」の一見矛盾行を生んでいたのを根治)。
    """
    base_amt = _amount(base, "amount", "curr_amount", "今月の金額")
    other_amt = _amount(other, "amount", "curr_amount", "今月の金額")
    base_prev = _amount(base, "prev_amount", "先月の金額")
    other_prev = _amount(other, "prev_amount", "先月の金額")
    merged = dict(base)

    if base_amt is None:
        if other_amt is not None:
            merged["amount"] = other_amt
    elif other_amt is not None:
        total = base_amt + other_amt
        merged["amount"] = total
        note = (f"[複数エンドクライアントの統合行] 当月発行 {other_amt}円 + {base_amt}円 = {total}円 "
                "(同一取引先・商品の複数契約の発行済み実額を合算・発行済み金額を隠さない)")
        cb = _norm(merged.get("comment") or merged.get("コメント"))
        merged["comment"] = f"{cb} / {note}" if cb else note

    if base_prev is None:
        if other_prev is not None:
            merged["prev_amount"] = other_prev
    elif other_prev is not None:
        merged["prev_amount"] = base_prev + other_prev

    return merged


def _page_gap_check(page):
    """既存ページの漏れチェック (checkbox) を 正常/要対応 に写像して返す (未設定は '')。

    checkbox True=正常 / False=要対応。cross-run safe guard (前 run の要対応=☐ を新 run の
    正常=✓ で無条件に上書きしない) が既存値を読むのに使う。
    """
    props = (page or {}).get("properties") or {}
    prop = props.get(PROP_MISSING_CHECK) or {}
    if "checkbox" not in prop:
        return ""
    return "正常" if prop.get("checkbox") else "要対応"


def _append_comment(props, note):
    """props のコメント列 rich_text 末尾へ note を追記する (freshly-built/read 両形式に対応)。"""
    prop = props.get(PROP_COMMENT) or {}
    existing = "".join(
        (rt.get("text") or {}).get("content") or rt.get("plain_text") or ""
        for rt in (prop.get("rich_text") or [])
    )
    props[PROP_COMMENT] = _rt(f"{existing} / {note}" if existing else note)


def _title_prop_value(props):
    """props から title 型プロパティ値を **列名非依存**で返す (無ければ None)。

    Notion は DB あたり title 列を必ず 1 つだけ持ち、その page プロパティ値 dict のみ "title" キーを
    持つ。ゆえに title 列名が『取引先名』でも Notion 既定の『名前』/『Name』でも同定できる
    (ユーザー手作り DB のタイトル列名ドリフトを吸収する)。
    """
    for v in (props or {}).values():
        if isinstance(v, dict) and "title" in v:
            return v
    return None


def _page_match_key(page):
    """既存ページの properties から _stored_key を回収する (対象月, 取引先名, 商品名)。

    取引先名 (title) は列名非依存で拾う (_title_prop_value)。
    """
    props = page.get("properties") or {}
    return _stored_key(
        _rich_text_plain(props.get(PROP_TARGET_MONTH)),
        _title_plain(_title_prop_value(props)),
        _rich_text_plain(props.get(PROP_PRODUCT)))


def schema_properties():
    """8 列スキーマの Notion properties dict を列順 SSOT の順で構築する。

    dict は挿入順を保持するので COLUMN_ORDER の順に build_property した結果が Notion 上の
    列の左→右順になる (列順固定)。
    """
    return {name: build_property(_COLUMN_SPECS[name]) for name in COLUMN_ORDER}


def _build_row_props(row, target=None, *, creating, title_prop=PROP_CUSTOMER):
    """row を単一恒久 DB の 8 列プロパティ dict へ整形する。

    creating=True (新規 POST) のときだけ title (= 取引先名) を載せる。title_prop は DB の title 列の
    実名 (既定『取引先名』・ユーザー手作り DB では『名前』等でありうるので呼出側が検出した実名を渡す)。
    更新 (PATCH) では title (不変な表示キー) に触れず、入力に無い nullable 事実列は明示クリアして stale を残さない
    (行そのものは削除しない=非破壊マージは行単位で成立)。対象月 (YYYY-MM) は行同定キーの一部
    ゆえ更新でも stale クリアせず、target (呼出側の対象月) or 行の target_month を書く。
    """
    props = {}

    # 対象月 (YYYY-MM): 単一 DB で月を区別する。target (run の --target 由来 YYYY-MM) を優先し、
    # 無ければ行の target_month を YYYY-MM 化して使う。同定キーの一部ゆえ空クリアはしない。
    tm = _norm(target) or _norm(row.get("対象月") or row.get("target_yyyymm"))
    if not tm:
        raw_tm = _norm(row.get("target_month") or row.get("target"))
        tm = target_to_yyyymm(raw_tm) if _valid_target(raw_tm) else raw_tm
    if tm:
        props[PROP_TARGET_MONTH] = _rt(tm)

    # 漏れチェック: C03 producer は `gap_check` を emit する (SSOT=ROW_CONTRACT)。
    # 別名 check/漏れチェック/missing_check も後方互換で受ける。checkbox へ写像:
    # 正常=✓(True) / 要対応(発行漏れ候補)=☐(False)。checkbox は空状態を持たないため、
    # 値が判明したとき (check 非空) のみ設定し、更新で不明なら既存チェックを温存する。
    check = _norm(row.get("gap_check") or row.get("check")
                  or row.get("漏れチェック") or row.get("missing_check"))
    if check:
        props[PROP_MISSING_CHECK] = {"checkbox": check == "正常"}

    product = _row_product(row)
    if product:
        props[PROP_PRODUCT] = _rt(product)
    elif not creating:
        props[PROP_PRODUCT] = {"rich_text": []}

    prev_amount = _amount(row, "prev_amount", "先月の金額")
    if prev_amount is not None:
        props[PROP_PREV_AMOUNT] = {"number": prev_amount}
    elif not creating:
        props[PROP_PREV_AMOUNT] = {"number": None}

    # 今月の金額: C03 producer は `amount` を emit する。別名 curr_amount/今月の金額も受ける。
    curr_amount = _amount(row, "amount", "curr_amount", "今月の金額")
    if curr_amount is not None:
        props[PROP_CURR_AMOUNT] = {"number": curr_amount}
    elif not creating:
        props[PROP_CURR_AMOUNT] = {"number": None}

    # 先月と今月の比較: C03 producer は `period_diff` を emit する。別名 comparison も受ける。
    comparison = _norm(row.get("period_diff") or row.get("comparison") or row.get("先月と今月の比較"))
    if comparison:
        props[PROP_COMPARISON] = _rt(comparison)
    elif not creating:
        props[PROP_COMPARISON] = {"rich_text": []}

    comment = _norm(row.get("comment") or row.get("コメント"))
    if comment:
        props[PROP_COMMENT] = _rt(comment)
    elif not creating:
        props[PROP_COMMENT] = {"rich_text": []}

    if creating:
        customer = _row_customer(row)[:_MAX_RICH_TEXT]
        props[title_prop] = {"title": [{"text": {"content": customer}}]}
    return props


# ---------------------------------------------------------------------------
# 子ブロック取得 (トグル/ページの child_database 探索に使う)
# ---------------------------------------------------------------------------

def list_block_children(block_id, token, req=None):
    """ブロック/ページの子ブロックを has_more/next_cursor を辿り全件取得する。

    GET /blocks/{id}/children は id がページ (page_id) でもブロックでも子を返す
    (ページは自身が 1 つのブロックであり page_id をそのまま渡せる)。Design D の探索/新規作成では
    指定見出しブロック ID または report_parent_page (page_id) を渡す。
    """
    req = req or _req
    out = []
    cursor = None
    while True:
        path = f"/blocks/{block_id}/children?page_size=100"
        if cursor:
            path += f"&start_cursor={cursor}"
        res = req("GET", path, token)
        out.extend(res.get("results", []))
        if not res.get("has_more"):
            break
        cursor = res.get("next_cursor")
    return out


_HEADING_TYPES = {"heading_1", "heading_2", "heading_3"}


def _is_report_db(block):
    """block が report DB (title が『請求漏れ比較レポート』で始まる child_database) か。

    page-level fallback (無関係 DB が同居しうる親ページ直下・step3) の限定にのみ使う。指定トグル/見出し
    配下 (step1/2) は専用領域ゆえ表示名非依存の _select_report_db で選ぶ。
    """
    return (block.get("type") == "child_database"
            and _child_db_title(block).startswith(_TITLE_PREFIX))


def _select_report_db(db_blocks):
    """指定トグル/見出し配下の child_database ブロック list から report DB の db_id を **表示名非依存**で選ぶ。

    指定トグル/見出しはこのレポート専用の器ゆえ、配下の child_database はその名前が何であれレポート DB と
    みなせる (ユーザーが『請求漏れ確認レポート』等どんな名前で手作りしても認識する=要件『有れば更新』の要)。
    優先順:
      1. title が _TITLE_PREFIX で始まる DB があればそれ (ツール作成 DB・後方互換で最優先=決定論の同点解消)。
      2. 無ければ child_database が配下に 1 つだけならそれを採用 (ユーザー命名 DB)。
      3. 複数あって一意に選べないときは先頭を採るが stderr へ警告する (silent 誤選択を可視化・姉妹
         notion_invoice_sink の ambiguity 安全弁に倣う)。
    child_database が無ければ None。
    """
    if not db_blocks:
        return None
    prefixed = [b for b in db_blocks if _child_db_title(b).startswith(_TITLE_PREFIX)]
    pool = prefixed or db_blocks
    if len(pool) > 1:
        sys.stderr.write(
            "[notion_report_sink] 指定トグル/見出し配下に report DB 候補が複数あります "
            f"(候補数={len(pool)})。先頭を採用しますが、1 つに整理することを推奨します。\n")
    return pool[0].get("id")


def _child_databases_in(container_id, token, req):
    """container (トグル見出し or ページ) 直下の child_database ブロック list を返す。"""
    return [b for b in list_block_children(container_id, token, req)
            if b.get("type") == "child_database"]


def _find_report_db_in(container_id, token, req):
    """親ページ直下 (step3・非スコープ) の report DB を title 前方一致で探し db_id を返す (無ければ None)。

    親ページには無関係な DB が同居しうるので、ここは表示名非依存でなく title 前方一致で限定する
    (トグル/見出し配下の表示名非依存な同定は _select_report_db が担う)。月サフィックス付き
    『… 2026-06』でも prefix 一致で拾う。
    """
    for block in list_block_children(container_id, token, req):
        if _is_report_db(block):
            return block.get("id")
    return None


def _find_report_db_below_heading(page_id, anchor_block_id, token, req):
    """ページ直下で anchor 見出しの直後〜次の見出しまでの区間にある report DB を返す (無ければ None)。

    トグル見出しをプレーン見出しに変えると、配下 DB はページ直下の兄弟 (見出しの下) へ移動する。
    その『見出しの下の DB』を、ページ子ブロックを順に辿り anchor の後ろから次セクション見出しの
    手前までの区間の child_database として集め、表示名非依存で選ぶ (_select_report_db)。この区間
    限定により、ページ上に別の report DB (旧重複等) があってもこの見出しに属する DB だけを拾える。
    """
    children = list_block_children(page_id, token, req)
    ids = [b.get("id") for b in children]
    if anchor_block_id not in ids:
        return None
    region = []
    for block in children[ids.index(anchor_block_id) + 1:]:
        if block.get("type") in _HEADING_TYPES:
            break  # 次セクション見出しに入った=この見出しの範囲外 → 打ち切り
        if block.get("type") == "child_database":
            region.append(block)
    return _select_report_db(region)


def _detect_title_prop(properties):
    """DB properties dict から title 型プロパティの実名を返す (無ければ既定 PROP_CUSTOMER)。

    Notion は DB あたり title 列を必ず 1 つ持つ。ツール作成 DB では『取引先名』だが、ユーザーが UI で
    手作りした DB は既定の『名前』/『Name』でありうる。その実名を検出して行 upsert の title 書込先に使う。
    判定は spec の "title" キー有無を主とする — GET /databases (実 Notion) の property は
    {"type":"title","title":{}}、build_property 生成物は {"title":{}} で、いずれも "title" キーを持つため
    両形式に忠実 (type だけを見ると build_property 形に type が無く取りこぼす)。
    """
    for name, spec in (properties or {}).items():
        if isinstance(spec, dict) and ("title" in spec or spec.get("type") == "title"):
            return name
    return PROP_CUSTOMER


def _ensure_db_schema(db_id, token, req):
    """既存 DB に不足プロパティ (特に 対象月) を PATCH で追加する (非破壊)。返り値=(追加列名 list, title列実名)。

    UI 手動作成 DB や旧 7 列スキーマ DB を単一恒久 DB 契約 (対象月を含む列) へ寄せる。既存プロパティは
    触らず、COLUMN_ORDER のうち DB に無い**非 title** 列だけを追加する (title 列は既存 DB に必ず在り、
    DB は title を 1 つしか持てないため追加対象から除く)。同時に GET したスキーマから title 列の実名
    (『取引先名』/『名前』等) を検出し返す — 行 upsert が title を正しい列名で書けるようにする。
    """
    db = req("GET", f"/databases/{db_id}", token)
    properties = db.get("properties") or {}
    have = set(properties.keys())
    title_prop = _detect_title_prop(properties)
    add_props = {name: build_property(_COLUMN_SPECS[name])
                 for name in COLUMN_ORDER if name not in have and name != PROP_CUSTOMER}
    if add_props:
        req("PATCH", f"/databases/{db_id}", token, {"properties": add_props})
    return list(add_props.keys()), title_prop


def resolve_report_db(anchor_block_id, parent_page_id, token, req=None, *, apply=True,
                      pinned_db_id=None, allow_create=True):
    """単一恒久レポート DB を解決する (Design D + 明示 pin・要件2)。返り値 (db_id, location, created, placement)。

    pinned_db_id = config の report_database_id (要件2・step0 の第一級解決経路)。指定時は構造同定を
    経ずその DB を直接更新対象にする (出力先が指定先へ確実に着地=phantom 回避の核)。
    anchor_block_id = config の report_toggle_block。**トグル見出しでもプレーン見出し2でも受ける**
    (ユーザーがトグル→見出し2 に変えても対応する)。出力先の優先順:
      0. **明示 pin (pinned_db_id)** = config report_database_id が set のとき。構造同定を経ず直接更新。
         location='pinned'。
      1. **anchor の子の report DB** = anchor がトグル見出し (is_toggleable=true) で DB を配下に持つ場合。
         API は block_id 親 DB を『作成』できないが既存 DB の『更新』(行 upsert・列 PATCH) はできる。
         location='in-block'。
      2. **anchor 見出しの直下 (ページ兄弟) の report DB** = anchor がプレーン見出しで、配下 DB が
         ページ直下の『見出しの下』へ移動している場合 (トグル→見出し2 変換時の実状態)。次セクション
         見出しの手前までで探し、ページ上の別 report DB (旧重複等) と区別する。location='under-heading'。
      3. **ページ直下の任意の既存 report DB** (どの見出しにも紐づかない既存)。location='page'。
      4. どれも無く apply=True **かつ allow_create=True** なら **見出しの下 (ページ直下) へ新規作成**。
         location='page-created'。**allow_create=False (要件2 の既定 phantom 抑止) なら作成せず
         (None, 'none', False) を返し、呼出側 (run) が fail-closed で停止する** (別 DB へ誤書込しない)。
      5. dry-run で未発見なら (None, 'none', False)。
    見つかった/作った DB は 対象月 列を含むスキーマへ揃える (_ensure_db_schema・apply 時のみ)。単一 DB
    に複数月を保持し、同一 (対象月,取引先,商品) の再実行のみ上書き=非破壊冪等。
    """
    req = req or _req
    placement = {
        "report_anchor_block": anchor_block_id,
        "report_parent_page": parent_page_id,
        "column_order_defined": list(COLUMN_ORDER),
        "view_format_note": _VIEW_FORMAT_NOTE,
        "wrap_all_columns_via_api": False,
    }

    def _resolved(db_id, location, note):
        # apply=True のときだけスキーマ列を PATCH で補い title 列実名を検出する
        # (dry-run は読み取り専用=列追加せず title 列は既定名を仮定)。
        if apply:
            schema_added, title_prop = _ensure_db_schema(db_id, token, req)
        else:
            schema_added, title_prop = [], PROP_CUSTOMER
        placement.update({"location": location, "created": False,
                          "schema_added": schema_added, "title_prop": title_prop,
                          "note": note})
        return db_id, location, False, placement

    # 0. 明示 pin (config report_database_id・要件2 step0): 構造同定を経ず直接更新対象にする。
    #    出力先が指定先へ確実に着地し、report_toggle_block の構造同定のズレで別 DB(phantom)へ
    #    書き込みチェックが本来 DB に反映されない症状を根治する。pin が不正 id なら _ensure_db_schema
    #    の GET が例外を投げ、呼出側 (run/main) が fail-closed=exit2 で停止する (別 DB へ誤書込しない)。
    if pinned_db_id:
        return _resolved(pinned_db_id, "pinned",
                         "config report_database_id で明示 pin された DB を直接更新する (step0・"
                         "構造同定を経ない確実な着地=出力先が指定先へ着地・phantom 回避)")

    # 1. anchor (トグル見出し) の子の report DB (表示名非依存・指定トグルはレポート専用)。
    db_id = (_select_report_db(_child_databases_in(anchor_block_id, token, req))
             if anchor_block_id else None)
    if db_id:
        return _resolved(db_id, "in-block",
                         "指定見出し (トグル) 配下の既存 DB を表示名非依存で更新対象にする (単一恒久 DB・対象月列で複数月を非破壊保持)")

    # 2. anchor 見出しの直下 (ページ兄弟) の report DB (トグル→プレーン見出し変換後の実配置)。
    db_id = (_find_report_db_below_heading(parent_page_id, anchor_block_id, token, req)
             if anchor_block_id else None)
    if db_id:
        return _resolved(db_id, "under-heading",
                         "指定見出しの直下 (ページ兄弟) の既存 DB を更新対象にする (見出しの下=次セクションまでで同定・重複 DB と区別)")

    # 3. ページ直下の任意の既存 report DB。
    db_id = _find_report_db_in(parent_page_id, token, req)
    if db_id:
        return _resolved(db_id, "page",
                         "指定見出しの直下には無く、ページ直下の既存 report DB を更新対象にする (見出しの下に置きたい場合は Notion UI で見出し直後へ移動)")

    # 4/5. 新規作成 (API は block_id 親 DB を作れないため見出しの下=ページ直下へ作る)。
    if not apply:
        placement.update({"location": "none", "created": False,
                          "note": "dry-run: 既存 report DB 未発見 (apply 時は明示 pin または --allow-create でのみ新規作成)"})
        return None, "none", False, placement

    # 要件2 phantom 抑止: 明示 pin なし かつ 既存 report DB 未発見のとき、既定 (allow_create=False) は
    # 新規作成せず (None,'none') を返し呼出側 run が fail-closed 停止する (構造同定のズレで誤って
    # 別 DB=phantom を作り、チェックが本来 DB に反映されない症状の根治)。新規作成は明示 opt-in
    # (--allow-create) 時のみ。初回セットアップは pin 設定 or --allow-create で行う。
    if not allow_create:
        placement.update({"location": "none", "created": False,
                          "note": ("明示 pin(report_database_id)なし かつ 既存 report DB 未発見。"
                                   "phantom DB を作らず停止 (要件2・新規作成は --allow-create opt-in 時のみ)")})
        return None, "none", False, placement

    res = req("POST", "/databases", token, {
        "parent": {"type": "page_id", "page_id": parent_page_id},
        "title": [{"text": {"content": _TITLE_PREFIX}}],
        "properties": schema_properties(),
    })
    placement.update({
        "location": "page-created", "created": True, "schema_added": list(COLUMN_ORDER),
        "title_prop": PROP_CUSTOMER,   # ツール作成 DB の title 列は schema_properties で『取引先名』
        "note": ("既存 report DB が無かったため見出しの下 (ページ直下) へ新規作成した (API は database を "
                 "block_id=見出し親で作れないため=トグル内に直接は作れない)。**初回のみ Notion UI で "
                 "この DB を指定トグル/見出しの直下へドラッグ移動**すれば、以後 in-block/under-heading "
                 "で表示名に関係なく自動更新される")})
    return res["id"], "page-created", True, placement


# ---------------------------------------------------------------------------
# 行 upsert (非破壊冪等)
# ---------------------------------------------------------------------------

def query_month(report_db_id, token, req=None):
    """単一恒久 report DB の全行を has_more/next_cursor を辿り取得し page_id で dedup する。

    Design D では同じ DB に複数月が共存するため、この query は全月の行を返す。呼び出し側は
    _page_match_key の対象月を含むキーで同月だけを更新対象にする。
    """
    req = req or _req
    out = {}
    cursor = None
    while True:
        body = {"page_size": 100}
        if cursor:
            body["start_cursor"] = cursor
        res = req("POST", f"/databases/{report_db_id}/query", token, body)
        for page in res.get("results", []):
            pid = page.get("id")
            if pid and pid not in out:
                out[pid] = page
        if not res.get("has_more"):
            break
        cursor = res.get("next_cursor")
    return list(out.values())


def upsert_report_rows(rows, report_db_id, target, token, req=None, *, title_prop=PROP_CUSTOMER):
    """rows を単一恒久 DB へ **非破壊冪等** upsert する。返り値 {created, updated, skipped, deleted}。

    target = 対象月 YYMM (この run が書く月)。行同定キーは (対象月 YYYY-MM, 取引先名, 商品名) で、
    別の月の行 (以前 run) は同キーに衝突しないため非破壊で共存する (単一 DB に複数月を保持)。
    title_prop = DB の title 列の実名 (既定『取引先名』・ユーザー手作り DB は『名前』等)。新規行 POST の
    title 書込先に使う (既定のままだとツール作成 DB の列名前提で、手作り DB は全行 skip になるのを防ぐ)。

    手順:
      1. query_month で DB 全行を取得し _page_match_key (対象月, 取引先名, 商品名) で索引化する。
      2. 入力 rows を _stored_key で収束させる (同月 2/3 営業日目の同一行再投入は 1 件に畳む・
         最後の値を採用)。取引先名が空の行は skip する (title=取引先名 が必須)。
      3. 既存行あり → PATCH 更新 (title は送らない)。無し → POST 新規作成。
      4. **削除はしない** (今回入力に無い既存行も・別月の行も残す=非破壊マージ・deleted 常時 0)。
      5. 各行は try/except で隔離し個別失敗は skipped に計上して継続する。
    """
    req = req or _req
    target_yyyymm = target_to_yyyymm(target) if _valid_target(target) else _norm(target)
    existing = query_month(report_db_id, token, req)
    index = {}
    migrate_fallback = {}   # (取引先名, 商品名) -> 対象月が空の既存行 (旧 DB/手作り DB 移行時の backfill 用)
    for page in existing:
        key = _page_match_key(page)   # (対象月, 取引先名, 商品名)
        if not key[1]:                # title (取引先名) がある行のみ対象
            continue
        if key[0]:                    # 対象月あり=通常の同定キーで索引
            index.setdefault(key, page)
        else:                         # 対象月が空=旧 DB/手作り DB の未 backfill 行。当月行の照合先候補にする
            migrate_fallback.setdefault((key[1], key[2]), page)

    created = updated = skipped = collapsed_multi = 0
    collapsed = {}
    for row in rows:
        customer = _row_customer(row)
        if not customer:
            skipped += 1
            sys.stderr.write("[notion_report_sink] 取引先名 (title) が空の行を skip しました\n")
            continue
        key = _stored_key(target_yyyymm, customer, _row_product(row))
        prev = collapsed.get(key)
        if prev is None:
            collapsed[key] = row
            continue
        # 同一 (対象月,取引先,商品) 衝突。契約 identity (契約ID+エンドクライアント) が異なる複数契約
        # なら multi-contract collapse を計上し、要対応を優先保持して漏れ隠蔽 (false-negative) を防ぐ
        # (F-α safe guard)。**判定は identity 差**にする: contract_id が両方空でもエンドクライアントが
        # 違えば別契約であり、旧来の contract_id 差だけの検出では counter/stderr が発火しない
        # 『ゼロテレメトリの漏れ隠蔽』(3体エレガント検証 abduction) を塞ぐ。identity 一致の phantom
        # (同一契約の ID↔名前 split) は multi-contract でないため計上しない (dedup であって collapse でない)。
        if not _same_contract_identity(prev, row):
            collapsed_multi += 1
            sys.stderr.write(
                "[notion_report_sink] 同一(取引先,商品)に別契約 (契約ID/エンドクライアント違い) を検出。"
                f"固定列に識別子列が無いため1行へ収束し要対応を優先保持: {key}\n")
        collapsed[key] = _prefer_action(prev, row)

    for key, row in collapsed.items():
        try:
            page = index.get(key)
            if page is None:
                # 対象月が空の既存行 (旧 DB/手作り DB からの移行) を当月行として backfill 更新し、
                # 同一 (取引先,商品) の二重作成を防ぐ (update が対象月列を書き込み以後は通常キーで一致)。
                # pop で 1 行につき 1 回だけ採用 (複数当月行が同じ空行を奪い合わないようにする)。
                page = migrate_fallback.pop((key[1], key[2]), None)
            if page is not None:
                props = _build_row_props(row, target_yyyymm, creating=False)
                # cross-run safe guard (F-2): 前 run で立てた要対応を新 run の正常で無条件に
                # 下げると前日フラグした漏れが消える (false-negative)。既存ページが要対応で新行が
                # 正常なら漏れチェックを要対応のまま保持し、正常化した旨を comment へ注記する
                # (intra-run の _prefer_action と cross-run を対称化)。
                if _page_gap_check(page) == "要対応" and _severity_rank(row) == 0:
                    # cross-run guard の bypass 事由は 2 つ (いずれも権威ある正常訂正)。checkbox は
                    # _build_row_props で既に True (正常) が入っているため、bypass 時は注記のみ足す。
                    if _is_reliable_mf_issued(row):
                        # K4: MF実績の権威ある実額訂正 (今 run で reliable MF-issued=True を確認)。
                        # 前 run のバグ由来 要対応☐ を MF実績由来の正常☑ へ訂正する (cross-run override)。
                        _append_comment(
                            props, "前 run の要対応を MF実績の権威ある実額訂正で正常へ訂正 "
                                   "(今 run で MF-issued 確認・cross-run override)")
                    elif _is_structural_normal(row):
                        # 構造的正常事由 (年契約周期/契約完了等) は権威ある訂正ゆえ guard を bypass し
                        # 正常へ更新する (C03 annual fix を cross-run guard が打ち消さない・F-D)。
                        _append_comment(
                            props, "前 run の要対応を構造的正常事由で訂正 (年契約/契約完了等・cross-run override)")
                    else:
                        props[PROP_MISSING_CHECK] = {"checkbox": False}  # 要対応を保持 (☐ チェックなし)
                        _append_comment(props, "前 run の要対応を保持 (今 run 入力は正常・cross-run safe guard)")
                req("PATCH", f"/pages/{page['id']}", token, {"properties": props})
                updated += 1
            else:
                props = _build_row_props(row, target_yyyymm, creating=True, title_prop=title_prop)
                req("POST", "/pages", token,
                    {"parent": {"database_id": report_db_id}, "properties": props})
                created += 1
        except Exception:  # noqa: BLE001  個別行の失敗は隔離し残りを継続する
            skipped += 1
            continue

    # K6: 今回 emit(incoming=collapsed)キー集合に無い**対象月**の既存行 = 真の orphan
    # (今月MF実績にも契約在籍にも無い旧行=旧バグ run の phantom / 誤☑)。行削除はせず残置理由を
    # 先月と今月の比較・コメントへ注記する (非破壊・deleted は常時 0)。対象月 (key[0]==target_yyyymm)
    # に限定し別月の行 (Design D の単一 DB 共存) には触れない。migrate_fallback (対象月空の旧 DB 未移行行)
    # は phantom ではなく backfill 候補なので対象外 (当月行に pop 消費されなければそのまま残す)。
    orphaned = 0
    incoming_keys = set(collapsed)
    _orphan_marker = "残置行 (今月の突合対象外)"
    _orphan_note = ("今月MF実績にも契約在籍にも無い旧行 (今回の突合キーに一致せず)。"
                    "発行漏れレポートの当月対象ではないため残置理由付きで注記 (行は非破壊で保持)")
    for key, page in index.items():
        if key[0] != target_yyyymm or key in incoming_keys:
            continue
        try:
            # 既存の 先月と今月の比較 / コメント を**読んで追記**する (上書きしない=非破壊注記・冪等)。
            # day1 に記録した要対応理由等を消さず末尾へ残置マーカーを足す。既注記なら再 PATCH しない。
            existing = page.get("properties") or {}
            props = {}
            ex_cmp = _rich_text_plain(existing.get(PROP_COMPARISON))
            if _orphan_marker not in ex_cmp:
                props[PROP_COMPARISON] = _rt(f"{ex_cmp} / {_orphan_marker}" if ex_cmp else _orphan_marker)
            ex_cmt = _rich_text_plain(existing.get(PROP_COMMENT))
            if _orphan_note not in ex_cmt:
                props[PROP_COMMENT] = _rt(f"{ex_cmt} / {_orphan_note}" if ex_cmt else _orphan_note)
            if props:  # 既に残置注記済みの行は冪等 skip (再実行で注記が増殖しない)
                req("PATCH", f"/pages/{page['id']}", token, {"properties": props})
            orphaned += 1
        except Exception:  # noqa: BLE001  orphan 注記の個別失敗も隔離し継続する
            skipped += 1
            continue

    return {"created": created, "updated": updated, "skipped": skipped,
            "deleted": 0, "collapsed_multi_contract": collapsed_multi, "orphaned": orphaned}


# ---------------------------------------------------------------------------
# orchestration
# ---------------------------------------------------------------------------

def _resolve_parent(cfg):
    return _norm((cfg.get("notion") or {}).get("report_parent_page"))


def _resolve_toggle(cfg):
    """report_toggle_block (Design D: 出力先 report DB を紐づける指定見出し) の block_id。

    キー名は歴史的に toggle だが、トグル見出しでもプレーン見出し2でも受ける。
    """
    return _norm((cfg.get("notion") or {}).get("report_toggle_block"))


def _extract_db_id(value):
    """明示 pin 値 (report_database_id) から Notion database_id を取り出す (要件2・OQ-10 (c) の最小実装)。

    値が (a) 生の database_id (dash 有無・32hex)、(b) DB/ビュー URL のいずれでも id を返す。
    URL は `?` の前 (path 部) から 32hex を抽出する — ビュー URL の `?v=<view-id>` は view id で
    実体 DB と異なるため path 側の DB id を採る。linked-database ビューの表示 id≠実体 data_source の
    完全解決は OQ-10 (c) で後続 (当面は生 database_id 指定を推奨)。抽出不能は原値をそのまま返す
    (呼出側 _ensure_db_schema の GET が不正 id を fail-closed で弾く)。
    """
    v = _norm(value)
    if not v:
        return ""
    # 最終 path セグメントに限定 (ビュー URL の ?v=<view-id> は path 外ゆえ除去される)。Notion の
    # 『リンクをコピー』は id を slug 末尾へ `-<32hex>` として付ける (notion.so/<Workspace>/<Title>-<id>)
    # ため、まず最終 dash 後トークンが 32hex ならそれを採る (タイトル内の偶発 hex トークンと id を
    # dash 区切りで分離=先頭マッチ誤爆の回避)。次に dashed-uuid をそのまま渡された形、最後に
    # フォールバックで最終セグメント内の末尾寄り 32hex 連を採る。抽出不能は原値 (GET が不正 id を弾く)。
    seg = v.split("?", 1)[0].rstrip("/").rsplit("/", 1)[-1]
    tail = seg.rsplit("-", 1)[-1]
    if re.fullmatch(r"[0-9a-f]{32}", tail, re.IGNORECASE):
        return tail
    compact = seg.replace("-", "")
    if re.fullmatch(r"[0-9a-f]{32}", compact, re.IGNORECASE):
        return compact
    ms = re.findall(r"[0-9a-f]{32}", compact, re.IGNORECASE)
    return ms[-1] if ms else v


def _resolve_report_db_id(cfg):
    """明示 pin された report DB id (step0・要件2)。未設定は '' (=構造同定へ fallback)。

    notion.report_database_id を第一級の解決経路にすることで、report_toggle_block の構造同定の
    ズレで別 DB (phantom) へ書き込みチェックが本来 DB に反映されない症状を根治する。
    """
    return _extract_db_id((cfg.get("notion") or {}).get("report_database_id"))


def run(rows, target, cfg, token, req=None, *, apply=True, allow_create=False):
    """単一恒久 report DB 解決 → 行 upsert を配線する (テスト可能な orchestration 本体)。

    apply=False (dry-run) は network を一切叩かず、計画のみを返す (書き込まない)。
    allow_create=False (要件2 の既定・phantom 抑止): 明示 pin (notion.report_database_id) なし かつ
    既存 report DB 未発見のとき、新規作成せず fail-closed (SinkError) で停止する。初回セットアップは
    pin 設定 or --allow-create=True (明示 opt-in) で行う (別 DB=phantom へ誤書込しない)。
    """
    if not _valid_target(target):
        raise SinkError(f"--target は YYMM (数字4桁・月01-12) を指定してください: {target!r}")
    # target_month cross-check (F-7): C03 が各行に付けた対象月と --target がズレたまま流すと
    # 誤月 DB へ silent 投入され冪等・非破壊ゆえ誤混入が残存する。不一致は fail-closed で拒否。
    _t = _norm(target)
    for r in rows:
        rt = _norm(r.get("target_month") or r.get("target"))
        if rt and rt != _t:
            raise SinkError(
                f"--target={target} と行の target_month={rt} が不一致です。誤った対象月の DB へ "
                "投入するのを防ぐため中止します (C03 の --target-month と C04 の --target を揃えてください)。")
    valid_rows = [r for r in rows if _row_customer(r)]

    parent_page = _resolve_parent(cfg)
    toggle_block = _resolve_toggle(cfg)
    pinned_db_id = _resolve_report_db_id(cfg)   # 要件2 step0: 明示 pin (未設定は '')

    if not apply:
        return {
            "created": 0, "updated": 0, "skipped": len(rows) - len(valid_rows), "deleted": 0,
            "report_db_id": None, "db_location": None, "db_created": False, "dry_run": True,
            "planned_rows": len(valid_rows),
            "placement": {
                "target_yyyymm": target_to_yyyymm(target),
                "report_database_id": pinned_db_id or None,   # 要件2: 明示 pin (step0) を開示
                "report_parent_page": parent_page,
                "report_toggle_block": toggle_block,
                "column_order_defined": list(COLUMN_ORDER),
                "view_format_note": _VIEW_FORMAT_NOTE,     # dry-run でも折り返し UI 手順を開示
                "wrap_all_columns_via_api": False,
                "note": ("dry-run (書き込みなし)。apply 時の出力先: 明示 pin (report_database_id) があれば "
                         "その DB へ直接 (step0) / 無ければ指定トグル内の既存 DB / 見出しの下 (ページ直下) の "
                         "既存 DB の順。明示 pin なし かつ 既存未発見時は phantom を作らず停止 (新規作成は "
                         "--allow-create 明示時のみ)。単一恒久 DB・対象月列で複数月を非破壊保持"),
            },
        }

    # 要件2: 明示 pin があれば parent_page 不要 (pin を直接更新)。pin なしのみ従来どおり
    # parent_page を必須にする (構造同定の探索/作成先ページが要るため)。
    if not pinned_db_id and not parent_page:
        raise SinkError(
            "notion.report_database_id (明示 pin) も notion.report_parent_page も未設定です。"
            "出力先 DB を pin するか、構造同定の探索/作成先ページ『請求書発行チェック』の page_id を "
            "mf-kessai-config.default.json または .mf-kessai-config.json に設定してください。")

    req = req or _req
    report_db_id, location, created, placement = resolve_report_db(
        toggle_block, parent_page, token, req, apply=True,
        pinned_db_id=pinned_db_id, allow_create=allow_create)
    # 要件2 phantom 抑止: 明示 pin なし かつ 既存 report DB 未発見 かつ allow_create=False で停止。
    if report_db_id is None:
        raise SinkError(
            "明示 pin (notion.report_database_id) 未設定 かつ 既存 report DB 未発見のため、"
            "phantom DB を作らず停止しました (要件2)。あなたのレポート DB を config の "
            "notion.report_database_id に設定 (ビュー/DB URL でも可) してください。初回セットアップで "
            "新規作成したい場合のみ --allow-create を付けて再実行してください。")
    placement["target_yyyymm"] = target_to_yyyymm(target)
    counts = upsert_report_rows(rows, report_db_id, target, token, req,
                                title_prop=placement.get("title_prop", PROP_CUSTOMER))

    counts.update({
        "report_db_id": report_db_id,
        "db_location": location,        # in-block / under-heading / page / page-created
        "db_created": created,
        "placement": placement,
        "dry_run": False,
    })
    return counts


def _load_rows(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise SinkError(f"--rows は JSON list を指定してください (先頭型={type(data).__name__})")
    return data


def main(argv=None):
    p = argparse.ArgumentParser(
        description="月次発行漏れ比較レポート DB へ分類済みレポート行を非破壊冪等 upsert する sink")
    p.add_argument("--rows", required=True, help="C03 分類済みレポート行 JSON list ファイル")
    p.add_argument("--target", required=True, help="対象月 YYMM (例 2607)")
    p.add_argument("--apply", action="store_true", help="実際に Notion へ書き込む (無指定は dry-run)")
    p.add_argument("--verified", action="store_true",
                   help="二段確認 (dry-run 内訳確認 + mfk-report-verifier) 完了の明示。--apply 時は必須")
    p.add_argument("--config", help="設定 JSON パス (省略時は既定 + ローカル上書き)")
    p.add_argument("--allow-create", dest="allow_create", action="store_true",
                   help="明示 pin (notion.report_database_id) なし かつ 既存 report DB 未発見時に "
                        "新規 DB を作成する opt-in (要件2・初回セットアップ用)。無指定時は phantom を "
                        "作らず fail-closed で停止する")
    a = p.parse_args(argv)

    try:
        # 書込ゲートを機械層で担保 (prose でなく exit2): --apply は --verified 必須。
        if a.apply and not a.verified:
            raise SinkError(
                "--apply には --verified が必須です (二段確認=dry-run 内訳確認 + "
                "mfk-report-verifier のゲート)。dry-run で内訳を確認し、二段確認後に "
                "--apply --verified を付けてください。")
        cfg = load_config(a.config)
        rows = _load_rows(a.rows)
        token = None
        if a.apply:
            # token 欠落は fail-closed=exit2 で担保する (F-15)。_notion_token は欠落時 RuntimeError を
            # 投げるが、これを未捕捉のまま素通しすると exit1 (=manifest 上 非致命/部分成功扱い) になり
            # 「何も書けていないのに継続」する。SinkError へ写像して exit2 に統一する。
            try:
                token = _notion_token(cfg)
            except RuntimeError as e:
                raise SinkError(f"Notion トークンが取得できません (fail-closed): {e}")
        result = run(rows, a.target, cfg, token, apply=a.apply, allow_create=a.allow_create)
    except SinkError as e:
        sys.stderr.write(f"[notion_report_sink] {e}\n")
        return 2
    except Exception as e:  # noqa: BLE001
        # apply 中の想定外失敗 (Notion API 拒否・DB 生成拒否等) を
        # exit1 (=manifest 上 非致命/部分成功) へ落とさず fail-closed=exit2 に統一する。write ツールで
        # 「エラーで何も書けていないのに部分成功」の誤認を防ぐ (F-15/F-B の runtime 失敗モード)。
        sys.stderr.write(f"[notion_report_sink] 想定外エラーで中止 (fail-closed): {e}\n")
        return 2

    print(json.dumps(result, ensure_ascii=False, indent=2))
    # 部分失敗 (行 skip) があれば exit 1 (fail-soft)。全成功/ dry-run は 0。
    return 1 if result.get("skipped") else 0


if __name__ == "__main__":
    sys.exit(main())
