"""請求確認シート『判定』(5値select) + 『AI確認』(checkbox) への片方向ミラー書き戻し。

責務分離ハイブリッド (reconcile-redesign-plan §2) のシート投影面。判定 SoR は裏方台帳 (DB2) で、
シートの『判定』『AI確認』はそこから決定論的に再計算した 5 値投影にすぎない (片方向ミラー)。
stale は再実行で自己修復する (冪等)。経理は『判定=発行漏れ』など色付き select の保存ビュー 1 枚で回せる。

『確認ポイント』(rich_text) には verdict ごとの「何を確認すべきか/なぜ対象外か」を行固有の警告
詳細つきで書く (要確認/発行漏れ で次の対応が分かり、対象外 でなぜ対象外かが分かるようにする。
『AIの確認OK』(MATCH_*) のみ空文字で stale を消す=確認不要の緑。集約MATCHの warning も漏らさない)。

非破壊規律 (managed 列):
  - 機械が常時上書きするのは『判定』(select) ・『AI確認』(checkbox) ・『確認ポイント』(rich_text) の 3 列。
  - 加えて『契約開始日』は **空欄セルのみ** 派生値 (確認内容の期間由来) で自動補完する
    (current_dates で現値を渡したとき)。人間が入力済みの非空値は上書きしない。
  - 『契約終了月』は自由文から誤推定しやすく、請求漏れを隠すため自動補完・伝播しない。
  - 人間列『チェック済み』『確認内容』『取引先』等には一切 PATCH しない。
  - 当月 (target_ym) の reconcile forward rows だけが入力なので、過去月のシート行は触れない。
  - ORPHAN (逆方向・シート行なし) は sheet_label=None で投影スキップ (verdict-mapping.json SSOT)。

判定→5値は verdict-mapping.json の sheet_label を唯一の正本とし、ここで別表記を作らない
(mfk_reconcile.sheet_label / is_check_verdict 経由で派生)。
"""
import re
import sys
import os
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mfk_reconcile  # noqa: E402
import sheet_to_master  # noqa: E402

# C02 (MF顧客ID解決 SSOT) は scripts/ 配下。名前→ID 解決は再発明せずここへ一本化する。
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import mfk_customer_id_resolve  # noqa: E402

PROP_JUDGE = "判定"        # シート 5 値 select (本 lib が新設・管理)
PROP_AI_CHECK = "AI確認"   # シート checkbox (既存・機械が片方向ミラー)
PROP_NOTE = "確認ポイント"  # シート rich_text (本 lib が新設・管理): 何を確認すべきかのガイダンス
PROP_START = "契約開始日"  # シート rich_text (既存・人間入力)。空欄のみ期間から自動補完する
PROP_END = "契約終了月"    # シート rich_text (既存・人間入力)。機械は自動補完しない


def _iso_to_yymm(iso):
    """ISO 'YYYY-MM-DD' → 'YYMM' (契約終了月 列の既存フォーマットに合わせる)。不正は None。"""
    m = re.match(r"(\d{4})-(\d{2})", iso or "")
    return f"{m.group(1)[2:]}{m.group(2)}" if m else None

# 5 値 SSOT は verdict-mapping.json の sheet_labels。読込失敗時だけ既定値へ fail-soft。
def _sheet_labels():
    path = mfk_reconcile.VERDICT_MAPPING_PATH
    try:
        import json
        with open(path, encoding="utf-8") as fh:
            labels = json.load(fh).get("sheet_labels") or []
        if labels:
            return labels
    except (OSError, ValueError):
        pass
    return ["未照合", "AIの確認OK", "対象外", "要確認", "発行漏れ"]


SHEET_LABELS = _sheet_labels()
LABEL_COLORS = {
    "未照合": "default",
    "AIの確認OK": "green",
    "対象外": "gray",
    "要確認": "yellow",
    "発行漏れ": "red",
}


def ensure_judgment_property(sheet_db_id, token, req):
    """シートに『判定』select(5値・色付き)を冪等に用意する。

    既存 option は消さず、不足している 5 値だけを色付きで追加する (非破壊)。
    返り値: "created" / "updated" / "ok"。
    """
    res = req("GET", f"/databases/{sheet_db_id}", token)
    existing = res.get("properties", {}).get(PROP_JUDGE)
    # SSOT(verdict-mapping.json sheet_labels)に色未定義の6値目が増えても KeyError で
    # writeback 全停止しないよう fail-soft (未知ラベルは default 色)。
    want = [{"name": n, "color": LABEL_COLORS.get(n, "default")} for n in SHEET_LABELS]
    if existing is None:
        req("PATCH", f"/databases/{sheet_db_id}", token,
            {"properties": {PROP_JUDGE: {"select": {"options": want}}}})
        return "created"
    by_name = {o["name"]: o for o in (existing.get("select") or {}).get("options", [])}
    merged = list(by_name.values())
    changed = False
    for n in SHEET_LABELS:
        if n not in by_name:
            merged.append({"name": n, "color": LABEL_COLORS.get(n, "default")})
            changed = True
    if changed:
        req("PATCH", f"/databases/{sheet_db_id}", token,
            {"properties": {PROP_JUDGE: {"select": {"options": merged}}}})
        return "updated"
    return "ok"


def ensure_note_property(sheet_db_id, token, req):
    """シートに『確認ポイント』rich_text を冪等に用意する (無ければ追加)。"""
    res = req("GET", f"/databases/{sheet_db_id}", token)
    if PROP_NOTE not in res.get("properties", {}):
        req("PATCH", f"/databases/{sheet_db_id}", token,
            {"properties": {PROP_NOTE: {"rich_text": {}}}})
        return "created"
    return "ok"


def compose_note(verdict, warning, mapping=None):
    """『確認ポイント』本文 = verdict 定型ガイダンス + 行固有の警告詳細。

    分岐軸は sheet_label。『AIの確認OK』(=MATCH_*)だけ常に空文字を返す(確認不要・緑)。これは
    集約請求の MATCH_MONTHLY が engine(quantity_downgrade)で warning="MF 1明細に期待N件分が
    集約…" を持っても、判定が『AIの確認OK』である以上シートの確認ポイントへ漏らさないため
    (warning は DB2『警告』列に別途残るので情報は失われない=関心の分離)。

    『対象外』(SUPPRESS_*)はなぜ対象外か(年間前払い/契約終了/単発/非請求月)の理由を
    確認ポイントへ出す(ユーザー決定2: 全対象外に理由明記)。『要確認』『発行漏れ』系は定型
    ガイダンス + 行固有警告を返す。警告がガイダンスに未包含なら全角括弧で連結する(取消日時・
    取消前金額・数量差の想定漏れ額等の行固有情報を残す)。
    """
    mp = mapping if mapping is not None else mfk_reconcile.load_verdict_mapping()
    # 緑(AIの確認OK=MATCH_*)だけ warning の有無に関わらず空 = stale を消す(集約MATCHの
    # warning 漏洩防止)。対象外/要確認/発行漏れ は理由・確認事項を確認ポイントへ出す。
    if mfk_reconcile.sheet_label(verdict, mp) == "AIの確認OK":
        return ""
    hint = mfk_reconcile.action_hint(verdict, mp)
    w = (warning or "").strip()
    if hint and w and w not in hint:
        return f"{hint}（{w}）"
    return hint or w


def build_writeback(forward_rows, mapping=None):
    """forward reconcile rows → [{page_id, sheet_label, ai_check, note, verdict, start}]。

    sheet_label が None (ORPHAN/未定義) の行は投影しない。1 契約=複数シート行は全行へ展開する。
    同一 page_id が複数契約に現れることは契約境界キー上ないが、保険で重複除去する。
    note は『確認ポイント』本文。AIの確認OK(MATCH_*)だけ空にして stale を消し、対象外
    (SUPPRESS_*)・要確認・発行漏れは理由/確認事項を出す。start(契約開始日 ISO) は空欄セルの
    自動補完候補 (派生値。writeback が空欄のみ書く)。契約終了月は補完しない。
    """
    mp = mapping if mapping is not None else mfk_reconcile.load_verdict_mapping()
    out, seen = [], set()
    for r in forward_rows or []:
        verdict = r.get("verdict")
        label = mfk_reconcile.sheet_label(verdict, mp)
        if not label:
            continue
        ai = mfk_reconcile.is_check_verdict(verdict, mp)
        note = compose_note(verdict, r.get("warning"), mp)
        start = r.get("契約開始日") or None
        for pid in (r.get("_sheet_row_ids") or []):
            if not pid or pid in seen:
                continue
            seen.add(pid)
            out.append({"page_id": pid, "sheet_label": label, "ai_check": bool(ai),
                        "note": note, "verdict": verdict, "start": start})
    return out


def writeback(forward_rows, sheet_db_id, token, req, mapping=None, current_dates=None):
    """シート各行へ『判定』『AI確認』『確認ポイント』を冪等 PATCH し、空欄の『契約開始日』
    を派生値で自動補完する (非破壊: 人間入力の非空値は上書きしない)。

    current_dates: {page_id: {"契約開始日": raw, "契約終了月": raw}}。当月シートの現値。これが
    空欄のセルにのみ派生 start(ISO) を書く。None なら日付補完をスキップ
    (後方互換・判定3列のみ)。契約終了月・人間列 (チェック済み/確認内容/取引先/商品) には一切触れない。

    返り値: {"updated", "failed"(list), "targeted", "schema"}。個別失敗は握りつぶさず
    failed に積み、呼び出し側で stderr 可視化する (silent cap 禁止)。
    """
    schema_state = ensure_judgment_property(sheet_db_id, token, req)
    ensure_note_property(sheet_db_id, token, req)
    items = build_writeback(forward_rows, mapping)
    updated, failed = 0, []
    for it in items:
        props = {
            PROP_JUDGE: {"select": {"name": it["sheet_label"]}},
            PROP_AI_CHECK: {"checkbox": it["ai_check"]},
            # 確認ポイント: 空でも投入し stale を消す (片方向ミラー一貫性)。
            PROP_NOTE: {"rich_text": [{"text": {"content": it["note"][:1900]}}]},
        }
        # 契約開始日: 当月シートで空欄のセルだけ派生値で自動補完。current_dates が
        # None(現値不明)、または当該 page_id の現値が無いときは補完しない (非空=人間入力は不可侵)。
        rc = current_dates.get(it["page_id"]) if current_dates is not None else None
        if rc is not None:
            if it.get("start") and not (rc.get("契約開始日") or "").strip():
                props[PROP_START] = {"rich_text": [{"text": {"content": it["start"]}}]}
        try:
            req("PATCH", f"/pages/{it['page_id']}", token, {"properties": props})
            updated += 1
        except Exception as e:  # noqa: BLE001 — 1 行失敗で全体を止めない
            failed.append({"page_id": it["page_id"], "error": str(e)[:200]})
    return {"updated": updated, "failed": failed,
            "targeted": len(items), "schema": schema_state}


# ===========================================================================
# 同一取引先への契約開始日 伝播 backfill (独立パス)
# ===========================================================================
# 当月ミラー writeback とは別の経路。請求確認シート全行を横断し、同一取引先の既知の
# 契約開始日を空欄行へ伝播する。契約終了月は自由文・同一取引先伝播から誤って入ると
# 請求漏れを隠すため、機械では伝播しない。
#
# 安全設計 (複数契約の誤伝播=請求漏れ事故を構造的に防ぐ):
#   - 取引先 (normalize で表記ゆれ吸収) 単位で group。
#   - グループ内で契約開始日が正規化後 2 種類以上 = 同一取引先に複数契約 (別期間) が
#     混在する兆候。この場合は開始日も伝播を止め conflicts に記録する。
#   - 契約終了月は正当に空欄の継続契約があるため、値が 1 種類に収束しても伝播しない。
#   - 既に非空の行は触らない (空欄のみ)。冪等 (再実行で差分ゼロ)。人間入力は不可侵。


def _canon_start(raw):
    """契約開始日を ISO (YYYY-MM-DD) へ正規化。YYMM/ISO/YYYY-MM/YYYY/M/D を吸収。不正は None。"""
    return sheet_to_master.to_date(raw)


def _canon_end(raw):
    """契約終了月を YYMM へ正規化 (列の既存フォーマット)。不正は None。"""
    iso = sheet_to_master.to_date(raw)
    return _iso_to_yymm(iso) if iso else None


_BACKFILL_COLS = (("契約開始日", _canon_start),)


def plan_contract_date_propagation(sheet_rows):
    """同一取引先のシート行群で契約開始日の既知値を空欄行へ伝播する計画を返す。

    sheet_rows: [{page_id, 取引先, 契約開始日, 契約終了月, ...}] (請求確認シート全行)。

    戻り値:
      {
        "updates": {page_id: {"契約開始日"?: ISO}},  # 空欄セルのみ
        "conflicts": [{"取引先", "列", "values": [正規化値...]}],          # 複数契約で食い違い
        "stats": {"groups", "start_filled", "end_filled", "conflicts"},  # end_filled は常に 0
      }

    限界: 同一取引先に複数契約が混在しても、全行が契約開始日とも空欄の場合は
    識別の手掛かりが無く単一契約とみなす (この稀なケースのみ既知値が漏れうるが、検知可能な
    複数契約の兆候=非空値の食い違い は全て両列停止で塞ぐ)。
    """
    groups = defaultdict(list)
    for row in sheet_rows:
        tnorm = mfk_reconcile.normalize(row.get("取引先", ""))
        if not tnorm:
            continue
        groups[tnorm].append(row)

    updates = defaultdict(dict)
    conflicts = []
    filled = {"契約開始日": 0, "契約終了月": 0}
    for _tnorm, rows in groups.items():
        # 伝播対象列の既知値 (正規化・重複除去)。契約終了月は対象外。
        known = {col: [] for col, _ in _BACKFILL_COLS}
        for col, canon in _BACKFILL_COLS:
            for r in rows:
                cv = canon(r.get(col))
                if cv and cv not in known[col]:
                    known[col].append(cv)
        # 開始日が 2 種類以上 = 同一取引先に複数契約 (別期間) が混在する兆候。
        # 誤伝播より非伝播を選ぶ (fail-safe)。
        if any(len(known[col]) >= 2 for col, _ in _BACKFILL_COLS):
            for col, _ in _BACKFILL_COLS:
                if len(known[col]) >= 2:
                    conflicts.append({
                        "取引先": (rows[0].get("取引先") or "").strip(),
                        "列": col,
                        "values": sorted(known[col]),
                    })
            continue
        # 単一契約とみなせるグループ: 開始日が 1 種類に収束していれば空欄行へ伝播する。
        for col, _ in _BACKFILL_COLS:
            vals = known[col]
            if len(vals) != 1:
                continue
            value = vals[0]
            for r in rows:
                if (r.get(col) or "").strip():
                    continue  # 非空 (人間入力) は不可侵
                pid = r.get("page_id")
                if pid:
                    updates[pid][col] = value
                    filled[col] += 1
    return {
        "updates": {pid: cols for pid, cols in updates.items()},
        "conflicts": conflicts,
        "stats": {
            "groups": len(groups),
            "start_filled": filled["契約開始日"],
            "end_filled": filled["契約終了月"],
            "conflicts": len(conflicts),
        },
    }


def apply_contract_date_propagation(updates, sheet_db_id, token, req):
    """plan_contract_date_propagation の updates を空欄セルへ冪等 PATCH する (rich_text)。

    updates は純関数が既に空欄のみへ絞り込んだ計画。判定 3 列 (判定/AI確認/確認ポイント) と
    契約終了月には触れない (契約開始日のみ)。個別失敗は握りつぶさず failed に積む (silent cap 禁止)。
    返り値: {"written", "failed"(list), "targeted"}。
    """
    written, failed = 0, []
    for pid, cols in updates.items():
        props = {}
        if cols.get("契約開始日"):
            props[PROP_START] = {"rich_text": [{"text": {"content": cols["契約開始日"]}}]}
        if not props:
            continue
        try:
            req("PATCH", f"/pages/{pid}", token, {"properties": props})
            written += 1
        except Exception as e:  # noqa: BLE001 — 1 行失敗で全体を止めない
            failed.append({"page_id": pid, "error": str(e)[:200]})
    return {"written": written, "failed": failed, "targeted": len(updates)}


# ===========================================================================
# 確認内容に終了根拠の無い契約終了月のクリア (健全性回復)
# ===========================================================================
# 契約終了月は、自由文からの誤推定や同一取引先伝播で「終了根拠が無いのに値が入る」と、
# 継続契約を終了扱いにして請求漏れを隠す。確認内容に終了注記が無い行の契約終了月は
# 機械が空欄へ戻す (人間が確認内容に終了を明記した行のみ残す)。冪等 (再実行で差分ゼロ)。

# 契約終了の根拠注記の判定は engine(mfk_reconcile)を唯一の SSOT とする。
# build_contracts/classify(生成辺)と本 lib の clear(再同期辺)が同一述語を共有し、
# 規約の二重定義 (例「まで」の扱い) を構造的に排除する (両辺 SSOT)。曖昧語「まで」を
# 終了根拠に含めない誤検出回避は mfk_reconcile._END_BASIS_PAT 側で保証する。
has_end_basis = mfk_reconcile.has_end_basis


def plan_unsupported_end_date_clear(sheet_rows):
    """確認内容に終了根拠が無いのに契約終了月が入っている行を検出する (純関数・副作用なし)。

    sheet_rows: [{page_id, 確認内容, 契約終了月, ...}] (請求確認シート全行)。

    契約終了月は伝播・誤入力で根拠なく入ると継続契約を終了扱いにして請求漏れを隠すため、
    確認内容に終了注記 (has_end_basis) が無い行の契約終了月を空欄へ戻す対象とする。
    人間が確認内容に終了を明記した行は残す。

    戻り値: {"clears": [page_id], "stats": {"with_end", "grounded", "unsupported"}}
    """
    with_end = [r for r in sheet_rows if (r.get("契約終了月") or "").strip()]
    clears, grounded = [], 0
    for r in with_end:
        if has_end_basis(r.get("確認内容")):
            grounded += 1
        elif r.get("page_id"):
            clears.append(r["page_id"])
    return {"clears": clears,
            "stats": {"with_end": len(with_end), "grounded": grounded,
                      "unsupported": len(clears)}}


def apply_end_date_clear(clears, sheet_db_id, token, req):
    """plan_unsupported_end_date_clear の clears の契約終了月を空欄へ戻す (rich_text [])。

    個別失敗は握りつぶさず failed に積む (silent cap 禁止)。
    返り値: {"cleared", "failed"(list), "targeted"}。
    """
    cleared, failed = 0, []
    for pid in clears:
        try:
            req("PATCH", f"/pages/{pid}", token, {"properties": {PROP_END: {"rich_text": []}}})
            cleared += 1
        except Exception as e:  # noqa: BLE001 — 1 行失敗で全体を止めない
            failed.append({"page_id": pid, "error": str(e)[:200]})
    return {"cleared": cleared, "failed": failed, "targeted": len(clears)}


# ===========================================================================
# MF顧客ID backfill (独立パス・C02)
# ===========================================================================
# 請求確認シート 665 行全ての MF顧客ID が空(0% 充足)なため、lib/mfk_reconcile._boundary_customers
# の「MF顧客ID優先」経路が一度も発火せず、名前一致 fallback(name-drift で false GAP)に依存して
# いた。名前→ID解決は scripts/mfk_customer_id_resolve.py(C02)へ一本化し、一意確定分だけを
# 空欄セルへ backfill する(既存の片方向ミラー方針=空欄のみ補完・非破壊 を継承)。
#
# 安全設計 (契約開始日 propagation と同型の誤結線防止):
#   - 取引先 (normalize で表記ゆれ吸収) 単位で group。
#   - グループ内の 1 行でも MF顧客ID が非空なら、そのグループ全体を backfill 対象外にする
#     (既に人間確認済み/前回 backfill 済みの値を誤上書きしない)。
#   - 一意解決(method="unique_name")できたグループのみ書く。ambiguous/none は誤結線
#     (別会社への誤紐付け)を避けるため書かない(要マスタ登録は C02 側の可視化に委ねる)。


PROP_MF_CUSTOMER_ID = "MF顧客ID"  # シート rich_text (既存列・人間入力 or backfill が書く)


def plan_customer_id_backfill_writeback(sheet_rows, name_by_id):
    """請求確認シート全行を横断し、MF顧客ID 空欄行へ C02 の一意解決結果を backfill する計画を
    返す(純関数・副作用なし)。

    sheet_rows: [{page_id, 取引先, MF顧客ID, ...}] (請求確認シート全行)。
    name_by_id: {customer_id: 会社名} (mfk_customer_id_resolve.build_name_index の出力)。

    戻り値: {"updates": {page_id: mf_customer_id}, "stats": {"groups", "resolved",
             "skipped_explicit", "unresolved"}}
    """
    groups = defaultdict(list)
    for row in sheet_rows:
        tnorm = mfk_reconcile.normalize(row.get("取引先", ""))
        if tnorm:
            groups[tnorm].append(row)

    updates = {}
    resolved, skipped_explicit, unresolved = 0, 0, 0
    for tnorm, rows in groups.items():
        if any((r.get("MF顧客ID") or "").strip() for r in rows):
            skipped_explicit += 1
            continue
        res = mfk_customer_id_resolve.resolve_customer_id(tnorm, name_by_id)
        if not res["confirmed"]:
            unresolved += 1
            continue
        resolved += 1
        for r in rows:
            pid = r.get("page_id")
            if pid:
                updates[pid] = res["mf_customer_id"]
    return {
        "updates": updates,
        "stats": {"groups": len(groups), "resolved": resolved,
                   "skipped_explicit": skipped_explicit, "unresolved": unresolved},
    }


def apply_customer_id_backfill(updates, sheet_db_id, token, req):
    """plan_customer_id_backfill_writeback の updates を空欄の MF顧客ID 列へ冪等 PATCH する。

    個別失敗は握りつぶさず failed に積む (silent cap 禁止)。
    返り値: {"written", "failed"(list), "targeted"}。
    """
    written, failed = 0, []
    for pid, cid in updates.items():
        try:
            req("PATCH", f"/pages/{pid}", token, {
                "properties": {PROP_MF_CUSTOMER_ID: {"rich_text": [{"text": {"content": cid}}]}}
            })
            written += 1
        except Exception as e:  # noqa: BLE001 — 1 行失敗で全体を止めない
            failed.append({"page_id": pid, "error": str(e)[:200]})
    return {"written": written, "failed": failed, "targeted": len(updates)}
