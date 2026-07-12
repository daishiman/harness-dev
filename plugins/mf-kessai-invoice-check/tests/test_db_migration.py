#!/usr/bin/env python3
"""deprecated 旧列の移行 (build 自動削除 / verify residual 検出) を API なしで検証する。

顧客ID集約モデルへの移行で、旧『月次サマリ行』モデルの件数列は不要になった。
build_notion_db は既存 DB からこれらを whitelist 削除し、verify_db_schema は残存を
FAIL として検出する。誤って現行列を削除しない安全制約も検証する。
"""
import build_notion_db
import verify_db_schema

DEPRECATED = ["レコード種別", "発行漏れ件数", "金額変動件数", "チェック件数合計", "全体トータル",
              "対応状況", "チェック実行ID", "初回請求月(API推定)"]


def _existing_from_schema(schema, *, with_deprecated):
    """schema から Notion GET /databases のレスポンス形 (properties) を組み立てる。

    select は options まで再現し、ensure_schema が『追加なし』と判断できる完全形にする。
    with_deprecated=True なら旧列も number 型で含める。
    """
    props = {}
    for name, spec in schema["properties"].items():
        entry = {"type": spec["type"]}
        if spec["type"] == "select":
            entry["select"] = {"options": [{"name": o} for o in spec.get("options", [])]}
        elif spec["type"] == "number":
            entry["number"] = {"format": "yen"}
        else:
            entry[spec["type"]] = {}
        props[name] = entry
    if with_deprecated:
        for name in schema["deprecated_properties"]:
            props[name] = {"type": "number", "number": {}}
    return props


# --- schema 宣言 ---

def test_schema_declares_deprecated_properties():
    schema = build_notion_db.load_schema()
    assert schema["deprecated_properties"] == DEPRECATED
    # deprecated は現行 properties / fact / managed と重ならない (移行の整合)。
    assert not (set(schema["deprecated_properties"]) & set(schema["properties"]))
    assert not (set(schema["deprecated_properties"]) & set(schema["fact_columns"]))
    assert not (set(schema["deprecated_properties"]) & set(schema["managed_columns"]))


# --- build: 自動削除 ---

def test_build_deletes_deprecated_columns(monkeypatch):
    """既存 DB に旧列があれば PATCH で properties.{name}=null 削除する。"""
    schema = build_notion_db.load_schema()
    existing = _existing_from_schema(schema, with_deprecated=True)
    captured = {}

    def fake_req(method, path, token, body=None):
        if method == "GET":
            return {"title": [{"plain_text": "請求書チェック_DB"}], "properties": existing}
        if method == "PATCH":
            captured["body"] = body
            return {}
        raise AssertionError((method, path))

    monkeypatch.setattr(build_notion_db, "_req", fake_req)
    rc = build_notion_db.ensure_schema("db1", schema, "token")
    assert rc == 0
    props = captured["body"]["properties"]
    # schema で明示した旧サマリ/集計列のみが None (削除)。現行列は触らない。
    assert set(props) == set(DEPRECATED)
    assert all(v is None for v in props.values())


def test_build_noop_when_db_already_clean(monkeypatch):
    """旧列が無く schema 最新なら PATCH を一切送らない (冪等)。"""
    schema = build_notion_db.load_schema()
    existing = _existing_from_schema(schema, with_deprecated=False)
    calls = []

    def fake_req(method, path, token, body=None):
        calls.append(method)
        if method == "GET":
            return {"title": [{"plain_text": "DB"}], "properties": existing}
        raise AssertionError("clean な DB に PATCH してはいけない")

    monkeypatch.setattr(build_notion_db, "_req", fake_req)
    rc = build_notion_db.ensure_schema("db1", schema, "token")
    assert rc == 0
    assert calls == ["GET"]


def test_build_never_deletes_a_current_schema_column(monkeypatch):
    """deprecated に誤って現行列名が混入しても、現行列は決して削除しない (安全制約)。"""
    base = build_notion_db.load_schema()
    existing = _existing_from_schema(base, with_deprecated=True)
    schema = dict(base)
    schema["deprecated_properties"] = list(base["deprecated_properties"]) + ["顧客ID"]
    captured = {}

    def fake_req(method, path, token, body=None):
        if method == "GET":
            return {"title": [{"plain_text": "DB"}], "properties": existing}
        if method == "PATCH":
            captured["body"] = body
            return {}
        raise AssertionError((method, path))

    monkeypatch.setattr(build_notion_db, "_req", fake_req)
    build_notion_db.ensure_schema("db1", schema, "token")
    props = captured["body"]["properties"]
    assert "顧客ID" not in props          # 現行列は守られる
    assert set(props) == set(DEPRECATED)  # deprecated whitelist のみ削除


# --- verify: residual 検出 ---

def _patch_verify(monkeypatch, existing_props):
    monkeypatch.setattr(verify_db_schema, "load_config",
                        lambda: {"notion": {"database_id": "db1"}})
    monkeypatch.setattr(verify_db_schema, "_notion_token", lambda: "token")
    if not isinstance(existing_props, dict):
        existing_props = {k: {} for k in existing_props}
    monkeypatch.setattr(verify_db_schema, "_req",
                        lambda method, path, token, body=None: {"properties": existing_props})


def test_verify_passes_when_clean(monkeypatch):
    schema = verify_db_schema.load_schema()
    _patch_verify(monkeypatch, _existing_from_schema(schema, with_deprecated=False))
    assert verify_db_schema.main() == 0


def test_verify_fails_on_residual_deprecated(monkeypatch):
    schema = verify_db_schema.load_schema()
    existing = _existing_from_schema(schema, with_deprecated=False)
    existing["レコード種別"] = {"type": "number", "number": {"format": "yen"}}
    _patch_verify(monkeypatch, existing)
    assert verify_db_schema.main() == 1


def test_verify_fails_when_renamed_old_and_new_coexist(monkeypatch):
    schema = verify_db_schema.load_schema()
    existing = _existing_from_schema(schema, with_deprecated=False)
    existing["判定"] = {"type": "select", "select": {"options": [{"name": "発行漏れ候補"}]}}
    _patch_verify(monkeypatch, existing)
    assert verify_db_schema.main() == 1


def test_verify_fails_on_missing(monkeypatch):
    schema = verify_db_schema.load_schema()
    existing = _existing_from_schema(schema, with_deprecated=False)
    existing.pop("今月金額")
    _patch_verify(monkeypatch, existing)
    assert verify_db_schema.main() == 1


def test_verify_fails_on_type_mismatch(monkeypatch):
    schema = verify_db_schema.load_schema()
    existing = _existing_from_schema(schema, with_deprecated=False)
    existing["顧客ID"] = {"type": "number", "number": {"format": "yen"}}
    _patch_verify(monkeypatch, existing)
    assert verify_db_schema.main() == 1


def test_verify_fails_on_select_option_missing(monkeypatch):
    schema = verify_db_schema.load_schema()
    existing = _existing_from_schema(schema, with_deprecated=False)
    existing["今月の発行状況"]["select"]["options"] = [{"name": "発行漏れ候補"}]
    _patch_verify(monkeypatch, existing)
    assert verify_db_schema.main() == 1


def test_verify_fails_on_number_format_mismatch(monkeypatch):
    schema = verify_db_schema.load_schema()
    existing = _existing_from_schema(schema, with_deprecated=False)
    existing["今月金額"]["number"]["format"] = "number"
    _patch_verify(monkeypatch, existing)
    assert verify_db_schema.main() == 1


# --- 共有純関数: verify と sink 検知ゲートが同一の正本判定を使う (residual/extra 境界) ---

def test_verify_imports_shared_residual_extra_pure_fn():
    """verify_db_schema は lib 側 SSOT の residual_extra_columns を import して使う。"""
    import notion_invoice_sink
    assert verify_db_schema.residual_extra_columns is notion_invoice_sink.residual_extra_columns


def test_residual_extra_columns_boundaries():
    """純関数: deprecated 残存=residual、schema 未知=extra、現行のみ=両方空。"""
    schema = verify_db_schema.load_schema()
    clean = _existing_from_schema(schema, with_deprecated=False)
    assert verify_db_schema.residual_extra_columns(clean, schema) == ([], [])

    with_dep = _existing_from_schema(schema, with_deprecated=True)
    residual, extra = verify_db_schema.residual_extra_columns(with_dep, schema)
    assert residual == sorted(DEPRECATED)
    assert extra == []

    manual_summary = _existing_from_schema(schema, with_deprecated=False)
    manual_summary["全体トータル"] = {"type": "number"}
    residual, extra = verify_db_schema.residual_extra_columns(manual_summary, schema)
    assert residual == ["全体トータル"]
    assert extra == []

    manual_unknown = _existing_from_schema(schema, with_deprecated=False)
    manual_unknown["任意メモ"] = {"type": "rich_text"}
    residual, extra = verify_db_schema.residual_extra_columns(manual_unknown, schema)
    assert residual == []
    assert extra == ["任意メモ"]


# --- verify: 集計疑い extra は WARN するが exit FAIL に昇格しない (正当列を壊さない) ---

def test_verify_warns_suspect_summary_extra_without_failing(monkeypatch, capsys):
    """新名の集計列(月次サマリ)が DB に手動追加されても exit0 のまま WARN 行だけ出す。

    deprecated whitelist に無い集計列は residual に乗らず extra に落ちる。これを集計列の
    疑いとして強めに警告するが、正当な「合計確認メモ」等の偽陽性で恒常 FAIL になりオオカミ
    少年化するのを避けるため exit code は FAIL に昇格しない (WARN 止まり)。
    """
    schema = verify_db_schema.load_schema()
    existing = _existing_from_schema(schema, with_deprecated=False)
    existing["月次サマリ"] = {"type": "number", "number": {"format": "yen"}}
    _patch_verify(monkeypatch, existing)
    assert verify_db_schema.main() == 0  # FAIL に昇格しない
    out = capsys.readouterr().out
    assert "WARN 集計列の疑いがある追加列" in out
    assert "月次サマリ" in out


def test_verify_separates_suspect_and_other_extra(monkeypatch, capsys):
    """extra を集計疑い(WARN)とその他(参考)に分けて出力し、どちらも exit0。"""
    schema = verify_db_schema.load_schema()
    existing = _existing_from_schema(schema, with_deprecated=False)
    existing["総計"] = {"type": "number", "number": {"format": "yen"}}
    existing["任意メモ"] = {"type": "rich_text"}
    _patch_verify(monkeypatch, existing)
    assert verify_db_schema.main() == 0
    out = capsys.readouterr().out
    # 集計疑いは WARN 行、その他は参考行に分かれる。
    suspect_line = next(ln for ln in out.splitlines() if "集計列の疑い" in ln)
    assert "総計" in suspect_line and "任意メモ" not in suspect_line
    assert any("DBにのみ存在する追加列" in ln and "任意メモ" in ln for ln in out.splitlines())


def test_verify_suspect_extra_does_not_mask_real_fail(monkeypatch, capsys):
    """欠落など真の FAIL がある場合は集計疑い extra があっても FAIL(exit1) を維持する。"""
    schema = verify_db_schema.load_schema()
    existing = _existing_from_schema(schema, with_deprecated=False)
    existing.pop("今月金額")          # 真の欠落 → FAIL
    existing["月次サマリ"] = {"type": "number", "number": {"format": "yen"}}  # 集計疑い
    _patch_verify(monkeypatch, existing)
    assert verify_db_schema.main() == 1
    out = capsys.readouterr().out
    assert "FAIL 欠落プロパティ" in out
    assert "WARN 集計列の疑いがある追加列" in out  # WARN も併記される
