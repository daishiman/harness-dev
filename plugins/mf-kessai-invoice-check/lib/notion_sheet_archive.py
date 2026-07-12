"""請求書確認シート (sheet_db_id) の月次アーカイブ&ロールオーバー エンジン。

run-mf-invoice-report の `--apply --verified` 完了後に自動連鎖する末尾工程 (R5)。
対象月 (`年月` select == YYMM) のシート行を、シートと同じ親ページ配下の月別 DB
『請求書確認シートYYMM』へ**完全移行**し、**検証成功時のみ**元シート行を削除
(Notion archive) して正本シートから当月分を切り出す (ロールオーバー)。

責務境界: 本エンジンは行の move / verify / delete のみを行い、verdict 分類・照合は
一切しない (状態遷移分類の正本は C03 scripts/mfk_period_report.py)。ゆえに
guard-mfk-no-reinvent の再実装遮断語幹 (compare/period_diff/classify/reconcile) を
関数名に用いない。

安全設計 (「もれなくすべて移行→検証→削除」を機械層で保証):
  - 冪等: 写像先へ `元ページID` (provenance rich_text) を持たせ 1:1 対応させる。再実行は
    既存行を PATCH (重複0)、削除済み行は元シートに存在しないため再処理されない
    (crash-safe / 途中再開可能)。Notion の「削除=物理でなく archive(trash)」がこの
    再開安全性を後押しする。
  - verify-then-delete: 各行を移行後に写像先ページを読み戻し、全写像列の plain-text 一致を
    検証する。1 列でも不一致なら元行を削除しない (fail-closed・過少移行での喪失を防ぐ)。
  - 削除は Notion archive (in_trash・30日復元可) であり物理削除ではない (可逆)。
  - DB 作成は Notion API 制約で page_id 親のみ (block/database 親は 400)。既定は
    シート自身の親ページ (兄弟として作成)。

network は req(method, path, token, body) 注入でオフライン単体テスト可能にする
(notion_report_sink / reconcile_invoices と同じ mock 契約)。
"""

PROP_SOURCE_ID = "元ページID"   # 写像先 DB の provenance rich_text (冪等 upsert キー)。
PROP_MONTH = "年月"             # シートの対象月 select (query フィルタキー・reconcile と同一)。

# --- 写像先で「元の型のまま」再生できる型 (Notion API で作成・書込可能) --------------------
_SAME_TYPE = {
    "title", "rich_text", "number", "select", "multi_select",
    "date", "checkbox", "url", "email", "phone_number",
}
# _SAME_TYPE 以外 (status/formula/rollup/people/files/relation/created_time/
# last_edited_time/created_by/last_edited_by/unique_id/button/verification 等) は
# Notion API で同型作成できない or 計算列のため、値を失わないよう rich_text へ**降格**して
# plain-text スナップショットを温存する (もれなく移行の担保・降格列は summary で開示)。

# 型降格しても plain-text で**忠実にスナップショットできない**型 (実体=バイナリ/失効URL を text で
# 保てない)。この型に非空値を持つ行は archive(元行削除)を保留する — 「もれなく移行」を満たせない
# 行を消さない fail-closed 安全弁。files のみ (relation は関連ページID・people は氏名/ID・
# formula/rollup は計算値をそれぞれ text で忠実に snapshot できるため hold 対象外)。
_LOSSY_HOLD_TYPES = {"files"}


# ===========================================================================
# プロパティ値の plain-text 抽出 (写像先降格 + 検証の両方が使う SSOT)
# ===========================================================================
def _num_str(n):
    """number を正規化文字列へ (1000 と 1000.0 を同一視して検証の偽不一致を防ぐ)。"""
    if n is None:
        return ""
    try:
        f = float(n)
    except (TypeError, ValueError):
        return str(n)
    return str(int(f)) if f == int(f) else repr(f)


def _prop_type(prop):
    """property dict の型を返す。'type' キーが無い payload はキー集合から推測する。"""
    if not isinstance(prop, dict):
        return None
    t = prop.get("type")
    if t:
        return t
    for k in ("title", "rich_text", "number", "select", "multi_select", "status",
              "date", "checkbox", "url", "email", "phone_number", "people", "files",
              "formula", "rollup", "created_time", "last_edited_time", "created_by",
              "last_edited_by", "unique_id", "relation", "verification", "button"):
        if k in prop:
            return k
    return None


def prop_plain_text(prop):
    """Notion property を素のテキストへ落とす (降格値の生成 + 移行検証の一致比較に使う単一正本)。

    型ごとに人が読める plain-text を返す。number は _num_str で正規化 (1000==1000.0)。
    select/status は name、multi_select は '、' 連結、date は start(〜end)、checkbox は
    'true'/'false'、people/files/relation/unique_id 等は最善努力で識別文字列化する。
    """
    if not isinstance(prop, dict):
        return ""
    t = _prop_type(prop)
    if t in ("title", "rich_text"):
        return "".join(
            (rt.get("text") or {}).get("content") or rt.get("plain_text") or ""
            for rt in (prop.get(t) or [])
        )
    if t == "number":
        return _num_str(prop.get("number"))
    if t in ("select", "status"):
        return ((prop.get(t) or {}).get("name")) or ""
    if t == "multi_select":
        return "、".join(o.get("name", "") for o in (prop.get("multi_select") or []))
    if t == "date":
        d = prop.get("date") or {}
        start = d.get("start") or ""
        end = d.get("end")
        return f"{start}〜{end}" if end else start
    if t == "checkbox":
        return "true" if prop.get("checkbox") else "false"
    if t in ("url", "email", "phone_number"):
        return prop.get(t) or ""
    if t == "people":
        return "、".join(
            (p.get("name") or p.get("id") or "") for p in (prop.get("people") or [])
        )
    if t == "files":
        out = []
        for f in prop.get("files") or []:
            out.append(f.get("name") or ((f.get("external") or f.get("file") or {}).get("url") or ""))
        return "、".join(x for x in out if x)
    if t == "formula":
        fo = prop.get("formula") or {}
        ft = fo.get("type")
        if ft == "number":
            return _num_str(fo.get("number"))
        if ft == "boolean":
            return "true" if fo.get("boolean") else "false"
        if ft == "date":
            return (fo.get("date") or {}).get("start") or ""
        return fo.get("string") or ""
    if t == "rollup":
        ro = prop.get("rollup") or {}
        rt = ro.get("type")
        if rt == "number":
            return _num_str(ro.get("number"))
        if rt == "date":
            return (ro.get("date") or {}).get("start") or ""
        if rt == "array":
            return "、".join(prop_plain_text(x) for x in (ro.get("array") or []))
        return ""
    if t in ("created_time", "last_edited_time"):
        return prop.get(t) or ""
    if t in ("created_by", "last_edited_by"):
        u = prop.get(t) or {}
        return u.get("name") or u.get("id") or ""
    if t == "unique_id":
        u = prop.get("unique_id") or {}
        num = u.get("number")
        prefix = u.get("prefix")
        if num is None:
            return ""
        return f"{prefix}-{num}" if prefix else str(num)
    if t == "relation":
        # 関連先ページ ID を列挙する (archive は関連の参照 ID を text で忠実 snapshot する)。
        return "、".join(r.get("id", "") for r in (prop.get("relation") or []) if r.get("id"))
    if t == "verification":
        return (prop.get("verification") or {}).get("state") or ""
    if t == "button":
        return ""  # button は値を持たない (押下トリガのみ)。snapshot 対象なし。
    return ""


# ===========================================================================
# スキーマ写像 (source DB properties → 写像先 DB 作成用 properties + per-column plan)
# ===========================================================================
def _target_type(source_type):
    """source プロパティ型 → 写像先で用いる型。_SAME_TYPE はそのまま、外は rich_text へ降格。"""
    return source_type if source_type in _SAME_TYPE else "rich_text"


def _build_property_def(source_type, spec):
    """写像先 DB 作成時の 1 プロパティ定義を組む (select/multi_select は options を継承)。"""
    tt = _target_type(source_type)
    if tt == "title":
        return {"title": {}}
    if tt == "rich_text":
        return {"rich_text": {}}
    if tt == "number":
        fmt = ((spec or {}).get("number") or {}).get("format") or "number"
        return {"number": {"format": fmt}}
    if tt == "date":
        return {"date": {}}
    if tt == "checkbox":
        return {"checkbox": {}}
    if tt in ("url", "email", "phone_number"):
        return {tt: {}}
    if tt == "select":
        opts = ((spec or {}).get("select") or {}).get("options") or []
        return {"select": {"options": [
            {"name": o.get("name", ""), "color": o.get("color", "default")} for o in opts]}}
    if tt == "multi_select":
        opts = ((spec or {}).get("multi_select") or {}).get("options") or []
        return {"multi_select": {"options": [
            {"name": o.get("name", ""), "color": o.get("color", "default")} for o in opts]}}
    return {"rich_text": {}}


def _provenance_key(source_props):
    """冪等 upsert の provenance キー列名を、元シート列と**衝突しない**名前で決定する。

    既定は PROP_SOURCE_ID (元ページID)。元シートに同名列があれば `元ページID_2`,`_3`… と退避し、
    源データ列と冪等キーの上書き衝突 (=検証が恒久不一致で stall する) を構造的に防ぐ。
    """
    key = PROP_SOURCE_ID
    n = 2
    existing = source_props or {}
    while key in existing:
        key = f"{PROP_SOURCE_ID}_{n}"
        n += 1
    return key


def mirror_schema(source_props):
    """source DB の properties → (写像先 properties dict, plan list, provenance_key)。

    - title 型は 1 つだけ title として写す (Notion DB は title を必ず 1 列だけ持つ不変)。
      それ以外は _SAME_TYPE ならその型、外は rich_text へ降格。
    - provenance 用の冪等キー列 (`_provenance_key` で元列と衝突しない名前) を rich_text で追加する。
    - plan の各要素: {name, source_type, target_type, demoted}。demoted=True は型降格した列。
      **plan には provenance キー列を含めない** (源データ列のみを写像/検証対象にする)。
    """
    properties, plan = {}, []
    for name, spec in (source_props or {}).items():
        stype = (spec or {}).get("type")
        if not stype:
            continue
        ttype = _target_type(stype)
        properties[name] = _build_property_def(stype, spec)
        plan.append({
            "name": name, "source_type": stype, "target_type": ttype,
            "demoted": ttype != stype,
        })
    prov = _provenance_key(source_props)
    properties[prov] = {"rich_text": {}}  # 冪等キー列 (源列と非衝突・plan に含めない)
    return properties, plan, prov


# ===========================================================================
# ページ値の組み立て (source page property → 写像先 create/patch payload)
# ===========================================================================
_RICH_TEXT_CHUNK = 2000  # Notion rich_text 1 要素あたりの content 上限 (文字)。


def _text_items(plain):
    """plain-text を Notion rich_text/title の text 要素 list へ分割する (1 要素 <=2000 文字)。

    2000 文字超も複数要素へ chunk して**全文を保持**する (単純 truncate だと長文 (例『確認内容』)
    が検証で不一致→滞留するため。要素を並べれば総量は伸ばせる)。空文字は空 list を返す。
    """
    if not plain:
        return []
    return [{"text": {"content": plain[i:i + _RICH_TEXT_CHUNK]}}
            for i in range(0, len(plain), _RICH_TEXT_CHUNK)]


def build_prop_value(target_type, source_prop):
    """写像先プロパティ (target_type) の書込 payload を source_prop から組む。

    同型は値を保ちつつ target_type へ整形、降格列 (target=rich_text) は plain-text を載せる。
    長文は _text_items で複数要素へ chunk して全文保持する (truncate による移行滞留を避ける)。
    Notion は select/multi_select の未知 option をページ作成時に自動追加するため、写像先 DB に
    option 未定義でも書込は通る。
    """
    plain = prop_plain_text(source_prop)
    if target_type == "title":
        return {"title": _text_items(plain)}
    if target_type == "rich_text":
        return {"rich_text": _text_items(plain)}
    if target_type == "number":
        raw = (source_prop or {}).get("number") if isinstance(source_prop, dict) else None
        try:
            return {"number": float(raw) if raw is not None else None}
        except (TypeError, ValueError):
            return {"number": None}
    if target_type == "checkbox":
        val = bool((source_prop or {}).get("checkbox")) if isinstance(source_prop, dict) else False
        return {"checkbox": val}
    if target_type == "select":
        name = ((source_prop or {}).get("select") or {}).get("name") if isinstance(source_prop, dict) else None
        return {"select": {"name": name} if name else None}
    if target_type == "multi_select":
        opts = (source_prop or {}).get("multi_select") or [] if isinstance(source_prop, dict) else []
        return {"multi_select": [{"name": o.get("name", "")} for o in opts if o.get("name")]}
    if target_type == "date":
        d = (source_prop or {}).get("date") if isinstance(source_prop, dict) else None
        if d and d.get("start"):
            payload = {"start": d.get("start")}
            if d.get("end"):
                payload["end"] = d["end"]
            return {"date": payload}
        return {"date": None}
    if target_type in ("url", "email", "phone_number"):
        return {target_type: plain or None}
    # 未知の target_type は安全側で rich_text 化。
    return {"rich_text": _text_items(plain)}


def build_page_props(source_page, plan, provenance_key=PROP_SOURCE_ID):
    """source page の全写像列 → 写像先 create/patch 用 properties dict (+ 冪等キー)。

    provenance_key は `_provenance_key` が決めた非衝突キー列名。plan は源列のみ (provenance を含まない)
    ため、源列を上書きせずに provenance を最後に載せられる。
    """
    src_props = source_page.get("properties") or {}
    out = {}
    for col in plan:
        out[col["name"]] = build_prop_value(col["target_type"], src_props.get(col["name"]))
    out[provenance_key] = {"rich_text": [{"text": {"content": source_page.get("id", "")}}]}
    return out


def lossy_hold_columns(source_page, plan):
    """source page が非空値を持つ lossy 型 (_LOSSY_HOLD_TYPES=files) 列名 list を返す。

    非空ならその行は archive(元行削除)を保留する対象 (実体を text で保てないため消さない)。
    """
    src_props = source_page.get("properties") or {}
    held = []
    for col in plan:
        if col["source_type"] in _LOSSY_HOLD_TYPES:
            if prop_plain_text(src_props.get(col["name"])):
                held.append(col["name"])
    return held


# ===========================================================================
# Notion I/O (すべて req 注入・オフラインテスト可能)
# ===========================================================================
def archive_db_title(target_ym):
    """写像先 DB のタイトル (『請求書確認シートYYMM』)。"""
    return f"請求書確認シート{target_ym}"


def query_month_pages(sheet_db, target_ym, token, req):
    """シート DB の `年月` select == target_ym のページ全件を page オブジェクトのまま返す
    (properties 込み・pagination 全周・page_id dedup)。"""
    pages, seen, cursor = [], set(), None
    while True:
        body = {"page_size": 100,
                "filter": {"property": PROP_MONTH, "select": {"equals": target_ym}}}
        if cursor:
            body["start_cursor"] = cursor
        res = req("POST", f"/databases/{sheet_db}/query", token, body)
        for page in res.get("results", []):
            pid = page.get("id")
            if pid and pid not in seen:
                seen.add(pid)
                pages.append(page)
        if not res.get("has_more"):
            break
        cursor = res.get("next_cursor")
    return pages


def _list_child_databases(parent_page_id, token, req):
    """親ページ直下の child_database ブロック list を全ページ取得して返す。"""
    out, cursor = [], None
    while True:
        q = "?page_size=100" + (f"&start_cursor={cursor}" if cursor else "")
        res = req("GET", f"/blocks/{parent_page_id}/children{q}", token)
        for b in res.get("results", []):
            if b.get("type") == "child_database":
                out.append(b)
        if not res.get("has_more"):
            break
        cursor = res.get("next_cursor")
    return out


def find_child_database(parent_page_id, title, token, req):
    """親ページ直下でこの月別アーカイブ器 (title で始まる child_database) を構造的に同定し
    database_id を返す (無ければ None)。

    Design D と同じ「表示名に依存しない構造的同定」の思想で、完全一致を最優先しつつ、ユーザーが
    写像先 DB を『請求書確認シート2606 (確認用)』等へ**リネームしても**同一器として再利用する
    (title 前方一致 fallback)。これにより名前ドリフトでの**二重作成**を防ぐ (report sink の Design D
    構造的同定の教訓を踏襲)。月別 title は 4 桁 YYMM 込みゆえ別月 DB と前方一致で混ざらない。
    複数併存時は先頭を決定論選択し stderr へ警告する (silent に取り違えない)。
    """
    if not parent_page_id:
        return None
    dbs = _list_child_databases(parent_page_id, token, req)
    # 1) 完全一致を最優先 (通常経路)。
    for b in dbs:
        if (b.get("child_database") or {}).get("title") == title:
            return b.get("id")
    # 2) 前方一致 fallback (リネーム耐性)。複数併存は先頭決定論選択 + 警告。
    prefixed = [b for b in dbs if ((b.get("child_database") or {}).get("title") or "").startswith(title)]
    if not prefixed:
        return None
    if len(prefixed) > 1:
        import sys
        titles = [(b.get("child_database") or {}).get("title") for b in prefixed]
        sys.stderr.write(
            f"[archive] 警告: '{title}' で始まる写像先 DB が複数あります {titles}。"
            "先頭を決定論選択します (重複を整理してください)。\n")
    return prefixed[0].get("id")


def create_archive_db(parent_page_id, title, properties, token, req):
    """親ページ配下へ写像先 DB を新規作成し database_id を返す (parent は page_id 親)。"""
    body = {
        "parent": {"type": "page_id", "page_id": parent_page_id},
        "title": [{"text": {"content": title}}],
        "properties": properties,
    }
    res = req("POST", "/databases", token, body)
    return res["id"]


def ensure_archive_schema(archive_db, properties, token, req):
    """既存写像先 DB に不足プロパティだけを追加する (非破壊・列削除しない)。追加列名 list を返す。"""
    res = req("GET", f"/databases/{archive_db}", token)
    existing = res.get("properties") or {}
    add = {}
    for name, definition in properties.items():
        if "title" in definition:
            continue  # title は作成時に確定済み・既存 DB では追加/改名しない
        if name not in existing:
            add[name] = definition
    if add:
        req("PATCH", f"/databases/{archive_db}", token, {"properties": add})
    return sorted(add.keys())


def index_archive_by_source(archive_db, provenance_key, token, req):
    """写像先 DB 全ページを {provenance 値(元ページID): archive_page_id} で索引する (冪等 upsert 用)。"""
    idx, cursor = {}, None
    while True:
        body = {"page_size": 100}
        if cursor:
            body["start_cursor"] = cursor
        res = req("POST", f"/databases/{archive_db}/query", token, body)
        for page in res.get("results", []):
            src = prop_plain_text((page.get("properties") or {}).get(provenance_key))
            if src:
                idx[src] = page.get("id")
        if not res.get("has_more"):
            break
        cursor = res.get("next_cursor")
    return idx


def upsert_archive_page(archive_db, source_page, existing_id, plan, token, req,
                        provenance_key=PROP_SOURCE_ID):
    """source page を写像先 DB へ冪等 upsert する。existing_id があれば PATCH、無ければ create。
    写像先ページ id を返す。"""
    props = build_page_props(source_page, plan, provenance_key)
    if existing_id:
        req("PATCH", f"/pages/{existing_id}", token, {"properties": props})
        return existing_id
    res = req("POST", "/pages", token, {
        "parent": {"type": "database_id", "database_id": archive_db},
        "properties": props,
    })
    return res["id"]


def verify_page_migrated(source_page, archive_page_id, plan, token, req):
    """写像先ページを読み戻し、全写像列の plain-text が source と一致するか検証する。

    返り値: (ok: bool, mismatches: [{col, source, archive}])。1 列でも不一致なら ok=False。
    これが「もれなくすべて移行できたか」の機械ゲート (これを満たさない元行は削除しない)。
    """
    res = req("GET", f"/pages/{archive_page_id}", token)
    ap = res.get("properties") or {}
    sp = source_page.get("properties") or {}
    mism = []
    for col in plan:
        name = col["name"]
        s = prop_plain_text(sp.get(name))
        a = prop_plain_text(ap.get(name))
        if s != a:
            mism.append({"col": name, "source": s, "archive": a})
    return (not mism, mism)


def archive_source_page(page_id, token, req):
    """元シートページを Notion archive (in_trash) する (物理削除でなく 30日復元可)。"""
    req("PATCH", f"/pages/{page_id}", token, {"archived": True})


# ===========================================================================
# オーケストレーション (plan = dry-run 書込ゼロ / apply = 移行+検証+削除)
# ===========================================================================
def preflight_source_schema(source_props):
    """写像前に元シートのスキーマを検査する。(ok: bool, reason: str) を返す。

    - `年月` (PROP_MONTH) 列が存在し select 型であること (query フィルタが select equals 固定のため)。
    - title 型の列が 1 つ以上あること (Notion DB は title 必須・写像先作成が 400 になるのを防ぐ)。
    未充足なら CLI が exit 2 (fail-closed) にし、Notion 400 の traceback でなく明示エラーで止める。
    """
    props = source_props or {}
    month = props.get(PROP_MONTH)
    if not isinstance(month, dict):
        return False, f"元シートに『{PROP_MONTH}』列がありません (対象月フィルタ不能)"
    if (month.get("type") or _prop_type(month)) != "select":
        return False, f"『{PROP_MONTH}』列が select 型ではありません (対象月フィルタは select equals 固定)"
    if not any((s or {}).get("type") == "title" for s in props.values()):
        return False, "元シートに title 型の列がありません (写像先 DB 作成に title 必須)"
    return True, ""


def plan_archive(sheet_db, target_ym, parent_page_id, source_props, token, req):
    """dry-run: Notion へ一切書き込まずに移行計画を作る (query + schema 写像 + 既存写像先 find-only)。

    DB 作成もページ書込もしない。返り値 dict は apply_archive がそのまま消費する。
    """
    pages = query_month_pages(sheet_db, target_ym, token, req)
    properties, plan, provenance_key = mirror_schema(source_props)
    title = archive_db_title(target_ym)
    existing_db = find_child_database(parent_page_id, title, token, req) if parent_page_id else None
    # 削除保留 (lossy=files 非空) になる行数を dry-run でも予告する。
    held_preview = sum(1 for p in pages if lossy_hold_columns(p, plan))
    # 削除対象の取引先名プレビュー (title 列の plain-text・先頭数件)。
    title_col = next((c["name"] for c in plan if c["source_type"] == "title"), None)
    customers = []
    if title_col:
        for p in pages:
            nm = prop_plain_text((p.get("properties") or {}).get(title_col))
            if nm:
                customers.append(nm)
    return {
        "target_ym": target_ym,
        "source_count": len(pages),
        "archive_db_title": title,
        "archive_db_id": existing_db,
        "archive_db_exists": bool(existing_db),
        "parent_page_id": parent_page_id,
        "columns": [c["name"] for c in plan],
        "demoted_columns": [c["name"] for c in plan if c["demoted"]],
        "lossy_hold_preview": held_preview,
        "customers_preview": customers,
        "provenance_key": provenance_key,
        "pages": pages,
        "plan": plan,
        "properties": properties,
    }


def apply_archive(planned, token, req):
    """apply: 写像先 DB を find-or-create し、各行を upsert→verify→(検証OKなら)archive-source。

    fail-closed: 検証に失敗した行は元シートから削除しない (failed に積んで元行を温存)。
    例外行も同様に温存する (1 行失敗で全体を止めない・silent cap 禁止)。
    返り値 summary dict。
    """
    pages = planned["pages"]
    plan = planned["plan"]
    title = planned["archive_db_title"]
    parent = planned["parent_page_id"]
    db_id = planned["archive_db_id"]
    provenance_key = planned.get("provenance_key", PROP_SOURCE_ID)
    created = False

    if not db_id:
        db_id = create_archive_db(parent, title, planned["properties"], token, req)
        created = True
    else:
        ensure_archive_schema(db_id, planned["properties"], token, req)

    src_index = index_archive_by_source(db_id, provenance_key, token, req)
    migrated, verified, archived, failed = 0, 0, 0, []
    for page in pages:
        pid = page.get("id")
        try:
            apage = upsert_archive_page(db_id, page, src_index.get(pid), plan, token, req,
                                        provenance_key)
            migrated += 1
            ok, mism = verify_page_migrated(page, apage, plan, token, req)
            if not ok:
                # 検証不一致: 移行が不完全ゆえ元行を削除しない (温存)。
                failed.append({"page_id": pid, "stage": "verify", "mismatches": mism})
                continue
            verified += 1
            held = lossy_hold_columns(page, plan)
            if held:
                # 検証は通ったが text で保てない実体 (files 等) を持つため元行を削除しない。
                # 写像先へのコピー (name snapshot) は済んでいる。
                failed.append({"page_id": pid, "stage": "lossy-hold", "cols": held})
                continue
            archive_source_page(pid, token, req)
            archived += 1
        except Exception as e:  # noqa: BLE001 — 1 行失敗で全体を止めない (元行は温存)
            failed.append({"page_id": pid, "stage": "error", "error": str(e)[:300]})

    return {
        "archive_db_id": db_id,
        "archive_db_created": created,
        "source_count": len(pages),
        "migrated": migrated,
        "verified": verified,
        "archived_source": archived,
        "failed": failed,
        # 全対象月行を漏れなく元シートから切り出せたか (F-SS-3: 未移行残存を「完了」と誤提示しない)。
        "status": "complete" if archived == len(pages) else "incomplete",
    }
