"""run-build-skill/templates/knowledge-skeleton/scripts/add_entry.py の genuine 機能テスト。

add_entry.py を実ファイルパスから importlib でロードし、純関数 (validate_entry /
normalize_keywords / find_index / resolve_index_path / guard_consult_at /
build_entry_from_args / load_entry_from_json / collect_* / append_to_category_file /
register_category_in_index / category_counts / add_entry / self_test) を tmp_path 上の
実 JSON ストアで駆動する。さらに main を subprocess (sys.executable) で起動し、
exit code / stdout JSON / stderr 診断 (必須欠落 / ID重複 / 不正JSON / index 不在 /
consult_at ガード) を assert する。network なし、実 repo 非汚染。
"""
import importlib.util
import json
import subprocess
import sys
from argparse import Namespace
from datetime import date
from pathlib import Path

import pytest

SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "plugins" / "harness-creator" / "skills" / "run-build-skill"
    / "templates" / "knowledge-skeleton" / "scripts" / "add_entry.py"
)

SPEC = importlib.util.spec_from_file_location("add_entry_uut", SCRIPT)
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


OK_ENTRY = {
    "id": "k_001",
    "title": "テストタイトル",
    "intent": "テストを通すこと",
    "background": "tempfile 環境で背景を記述。数値 10 と 20 を含む。",
    "keywords": ["a", "b", "c", "d", "e"],
    "source": {"file": "t.md"},
}


# --- helpers -----------------------------------------------------------------

def _make_store(tmp_path: Path, consult_at=("runtime",), categories=None) -> Path:
    """tmp_path/knowledge/knowledge-index.json を作って index パスを返す。"""
    kdir = tmp_path / "knowledge"
    kdir.mkdir(parents=True, exist_ok=True)
    idx = kdir / "knowledge-index.json"
    data = {"version": "1.0.0", "categories": categories or [],
            "global_keywords": {}, "synonyms": {}}
    if consult_at is not None:
        data["consult_at"] = list(consult_at)
    idx.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return idx


# ============================================================================
# normalize_keywords
# ============================================================================

def test_normalize_keywords_none():
    assert MOD.normalize_keywords(None) == []


def test_normalize_keywords_list_strips_and_drops_empty():
    assert MOD.normalize_keywords([" a ", "b", "", "  "]) == ["a", "b"]


def test_normalize_keywords_comma_string():
    assert MOD.normalize_keywords("a, b ,c,,") == ["a", "b", "c"]


# ============================================================================
# validate_entry
# ============================================================================

def test_validate_entry_ok_no_errors_no_warn():
    errs, warns = MOD.validate_entry(dict(OK_ENTRY))
    assert errs == []
    assert warns == []


def test_validate_entry_missing_all_required():
    errs, _ = MOD.validate_entry({})
    # id / title|content / intent|purpose / background / keywords|tags / source = 6 個
    assert len(errs) == 6
    assert any("id" in e for e in errs)
    assert any("source" in e for e in errs)


def test_validate_entry_alternate_fields_accepted():
    alt = {
        "id": "x",
        "content": "本文",
        "purpose": "目的",
        "background": "背景",
        "tags": ["x", "y", "z", "w", "v"],
        "source": "src.md",
    }
    errs, _ = MOD.validate_entry(alt)
    assert errs == []


def test_validate_entry_few_keywords_warns_not_errors():
    few = {**OK_ENTRY, "keywords": ["a", "b"]}
    errs, warns = MOD.validate_entry(few)
    assert errs == []
    assert len(warns) == 1
    assert "2 語" in warns[0]


def test_validate_entry_keywords_as_comma_string_counted():
    e = {**OK_ENTRY, "keywords": "a,b,c"}
    errs, warns = MOD.validate_entry(e)
    assert errs == []
    assert len(warns) == 1  # 3 語 < 5


# ============================================================================
# find_index / resolve_index_path
# ============================================================================

def test_find_index_in_knowledge_subdir(tmp_path):
    idx = _make_store(tmp_path)
    found = MOD.find_index(tmp_path)
    assert found == idx


def test_find_index_flat(tmp_path):
    flat = tmp_path / "knowledge-index.json"
    flat.write_text("{}", encoding="utf-8")
    assert MOD.find_index(tmp_path) == flat


def test_find_index_none_when_absent(tmp_path):
    assert MOD.find_index(tmp_path) is None


def test_resolve_index_path_explicit_index_wins(tmp_path):
    assert MOD.resolve_index_path("/explicit/path.json", "/ignored") == Path("/explicit/path.json")


def test_resolve_index_path_dir_flat(tmp_path):
    base = tmp_path / "store"
    base.mkdir()
    flat = base / "knowledge-index.json"
    flat.write_text("{}", encoding="utf-8")
    assert MOD.resolve_index_path(None, str(base)) == flat


def test_resolve_index_path_dir_nested_fallback(tmp_path):
    base = tmp_path / "store"
    base.mkdir()
    # flat が無い -> <dir>/knowledge/knowledge-index.json を返す
    expected = base / "knowledge" / "knowledge-index.json"
    assert MOD.resolve_index_path(None, str(base)) == expected


def test_resolve_index_path_autodetect_cwd(tmp_path, monkeypatch):
    idx = _make_store(tmp_path)
    monkeypatch.chdir(tmp_path)
    assert MOD.resolve_index_path(None, None) == idx


# ============================================================================
# read_store_consult_at / guard_consult_at
# ============================================================================

def test_read_store_consult_at_from_index(tmp_path):
    idx = _make_store(tmp_path, consult_at=["build-time"])
    assert MOD.read_store_consult_at(idx) == ["build-time"]


def test_read_store_consult_at_from_router_json(tmp_path):
    kdir = tmp_path / "knowledge"
    kdir.mkdir()
    idx = kdir / "knowledge-index.json"
    idx.write_text(json.dumps({"version": "1.0.0", "categories": []}), encoding="utf-8")
    (kdir / "router.json").write_text(json.dumps({"consult_at": ["runtime"]}), encoding="utf-8")
    assert MOD.read_store_consult_at(idx) == ["runtime"]


def test_read_store_consult_at_none_when_unset(tmp_path):
    idx = _make_store(tmp_path, consult_at=None)
    assert MOD.read_store_consult_at(idx) is None


def test_read_store_consult_at_skips_broken_json(tmp_path):
    kdir = tmp_path / "knowledge"
    kdir.mkdir()
    idx = kdir / "knowledge-index.json"
    idx.write_text("{broken", encoding="utf-8")  # JSONDecodeError -> continue
    assert MOD.read_store_consult_at(idx) is None


def test_guard_consult_at_undeclared_raises(tmp_path):
    idx = _make_store(tmp_path, consult_at=None)
    with pytest.raises(ValueError, match="consult_at を宣言していない"):
        MOD.guard_consult_at(idx, None)


def test_guard_consult_at_mismatch_raises(tmp_path):
    idx = _make_store(tmp_path, consult_at=["runtime"])
    with pytest.raises(ValueError, match="矛盾"):
        MOD.guard_consult_at(idx, "build-time")


def test_guard_consult_at_match_ok(tmp_path):
    idx = _make_store(tmp_path, consult_at=["runtime"])
    MOD.guard_consult_at(idx, "runtime")  # 例外なし


def test_guard_consult_at_declared_unspecified_ok(tmp_path):
    idx = _make_store(tmp_path, consult_at=["runtime"])
    MOD.guard_consult_at(idx, None)  # 宣言済みなら未指定でも OK


# ============================================================================
# build_entry_from_args / load_entry_from_json
# ============================================================================

def test_build_entry_from_args_full():
    ns = Namespace(id="x", title="t", intent="i", background="b",
                   keywords="a,b,c", source="s.md")
    e = MOD.build_entry_from_args(ns)
    assert e["id"] == "x"
    assert e["keywords"] == ["a", "b", "c"]
    assert e["source"] == {"file": "s.md"}


def test_build_entry_from_args_partial():
    ns = Namespace(id="x", title=None, intent=None, background=None,
                   keywords=None, source=None)
    e = MOD.build_entry_from_args(ns)
    assert e == {"id": "x"}


def test_load_entry_from_json_file(tmp_path):
    jp = tmp_path / "e.json"
    jp.write_text(json.dumps({**OK_ENTRY, "keywords": "p,q,r"}), encoding="utf-8")
    e = MOD.load_entry_from_json(str(jp))
    # 文字列 keywords は正規化される
    assert e["keywords"] == ["p", "q", "r"]


def test_load_entry_from_json_stdin(monkeypatch):
    import io
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(OK_ENTRY)))
    e = MOD.load_entry_from_json("-")
    assert e["id"] == "k_001"


def test_load_entry_from_json_non_object_raises(tmp_path):
    jp = tmp_path / "arr.json"
    jp.write_text("[1,2,3]", encoding="utf-8")
    with pytest.raises(ValueError, match="JSON オブジェクト"):
        MOD.load_entry_from_json(str(jp))


# ============================================================================
# collect_existing_ids / collect_ids_in_file / category_counts
# ============================================================================

def test_collect_existing_ids_empty_when_no_index(tmp_path):
    assert MOD.collect_existing_ids(tmp_path / "nope.json") == set()


def test_collect_existing_ids_across_categories(tmp_path):
    idx = _make_store(tmp_path, categories=[{"id": "m", "file": "knowledge-m.json"}])
    (tmp_path / "knowledge" / "knowledge-m.json").write_text(
        json.dumps({"items": [{"id": "a"}, {"id": "b"}, {"no_id": 1}]}), encoding="utf-8")
    assert MOD.collect_existing_ids(idx) == {"a", "b"}


def test_collect_existing_ids_skips_broken_category(tmp_path):
    idx = _make_store(tmp_path, categories=[
        {"id": "m", "file": "knowledge-m.json"},
        {"id": "n", "file": "missing.json"},
    ])
    (tmp_path / "knowledge" / "knowledge-m.json").write_text("{broken", encoding="utf-8")
    # broken -> JSONDecodeError で continue、missing -> exists False で continue
    assert MOD.collect_existing_ids(idx) == set()


def test_collect_ids_in_file_empty_when_absent(tmp_path):
    assert MOD.collect_ids_in_file(tmp_path / "x.json") == set()


def test_collect_ids_in_file(tmp_path):
    f = tmp_path / "cat.json"
    f.write_text(json.dumps({"items": [{"id": "z"}, {"nope": 1}]}), encoding="utf-8")
    assert MOD.collect_ids_in_file(f) == {"z"}


def test_category_counts_empty_when_no_index(tmp_path):
    assert MOD.category_counts(tmp_path / "nope.json") == {}


def test_category_counts_aggregates(tmp_path):
    idx = _make_store(tmp_path, categories=[{"id": "m", "file": "knowledge-m.json"}])
    (tmp_path / "knowledge" / "knowledge-m.json").write_text(
        json.dumps({"items": [{"id": "a"}, {"id": "b"}]}), encoding="utf-8")
    assert MOD.category_counts(idx) == {"m": 1 + 1}


def test_category_counts_broken_category_yields_none(tmp_path):
    idx = _make_store(tmp_path, categories=[{"id": "m", "file": "knowledge-m.json"}])
    (tmp_path / "knowledge" / "knowledge-m.json").write_text("{broken", encoding="utf-8")
    assert MOD.category_counts(idx) == {"m": None}


# ============================================================================
# append_to_category_file / register_category_in_index
# ============================================================================

def test_append_to_category_file_creates_new(tmp_path):
    cat = tmp_path / "knowledge" / "knowledge-new.json"
    n = MOD.append_to_category_file(cat, dict(OK_ENTRY), "new", "新カテゴリ")
    assert n == 1
    data = json.loads(cat.read_text())
    assert data["category"] == "new"
    assert data["label"] == "新カテゴリ"
    assert data["created_at"] == date.today().isoformat()
    assert data["items"][0]["id"] == "k_001"


def test_append_to_category_file_appends_existing(tmp_path):
    cat = tmp_path / "knowledge" / "knowledge-x.json"
    cat.parent.mkdir(parents=True)
    cat.write_text(json.dumps({"items": [{"id": "old"}]}), encoding="utf-8")
    n = MOD.append_to_category_file(cat, dict(OK_ENTRY), "x", None)
    assert n == 2


def test_append_to_category_file_repairs_missing_items(tmp_path):
    cat = tmp_path / "knowledge" / "knowledge-y.json"
    cat.parent.mkdir(parents=True)
    cat.write_text(json.dumps({"category": "y"}), encoding="utf-8")  # items 無し
    n = MOD.append_to_category_file(cat, dict(OK_ENTRY), "y", None)
    assert n == 1


def test_append_to_category_file_default_category_from_stem(tmp_path):
    cat = tmp_path / "knowledge" / "knowledge-derived.json"
    MOD.append_to_category_file(cat, dict(OK_ENTRY), None, None)
    data = json.loads(cat.read_text())
    assert data["category"] == "derived"  # stem から knowledge- 除去


def test_register_category_new(tmp_path):
    idx = _make_store(tmp_path)
    added = MOD.register_category_in_index(idx, "m", "knowledge-m.json", "M", ["k"])
    assert added is True
    index = json.loads(idx.read_text())
    assert any(c["id"] == "m" for c in index["categories"])


def test_register_category_already_present(tmp_path):
    idx = _make_store(tmp_path, categories=[{"id": "m", "file": "knowledge-m.json"}])
    added = MOD.register_category_in_index(idx, "m", "knowledge-m.json", "M", ["k"])
    assert added is False


def test_register_category_creates_index_if_absent(tmp_path):
    idx = tmp_path / "knowledge" / "knowledge-index.json"  # 存在しない
    added = MOD.register_category_in_index(idx, "m", "knowledge-m.json", None, [])
    assert added is True
    index = json.loads(idx.read_text())
    assert index["categories"][0]["label"] == "m"  # label 省略時は id


# ============================================================================
# add_entry : オーケストレーション (index-search / router / 重複 / ガード)
# ============================================================================

def test_add_entry_index_search_success(tmp_path):
    idx = _make_store(tmp_path)
    r = MOD.add_entry(idx, dict(OK_ENTRY), "mindset", None, "マインドセット")
    assert r["added"] is True
    assert r["mode"] == "index-search"
    assert r["category_registered"] is True
    assert r["category_counts"]["mindset"] == 1


def test_add_entry_duplicate_id_rejected(tmp_path):
    idx = _make_store(tmp_path)
    MOD.add_entry(idx, dict(OK_ENTRY), "mindset", None, "マインドセット")
    with pytest.raises(ValueError, match="重複"):
        MOD.add_entry(idx, dict(OK_ENTRY), "mindset", None, "マインドセット")


def test_add_entry_validation_error_raises(tmp_path):
    idx = _make_store(tmp_path)
    with pytest.raises(ValueError, match="必須フィールド検証エラー"):
        MOD.add_entry(idx, {"id": "x"}, "mindset", None, None)


def test_add_entry_requires_category_or_file(tmp_path):
    idx = _make_store(tmp_path)
    with pytest.raises(ValueError, match="--category または --file"):
        MOD.add_entry(idx, dict(OK_ENTRY), None, None, None)


def test_add_entry_router_file_mode(tmp_path):
    idx = _make_store(tmp_path)
    r = MOD.add_entry(idx, {**OK_ENTRY, "id": "r_001"}, None,
                      "knowledge-routing-a.json", None)
    assert r["mode"] == "router-file"
    assert r["file_item_count"] == 1
    assert (tmp_path / "knowledge" / "knowledge-routing-a.json").exists()


def test_add_entry_router_file_duplicate(tmp_path):
    idx = _make_store(tmp_path)
    MOD.add_entry(idx, {**OK_ENTRY, "id": "r_001"}, None, "knowledge-routing-a.json", None)
    with pytest.raises(ValueError, match="重複"):
        MOD.add_entry(idx, {**OK_ENTRY, "id": "r_001"}, None, "knowledge-routing-a.json", None)


def test_add_entry_router_absolute_file(tmp_path):
    idx = _make_store(tmp_path)
    abs_cat = tmp_path / "abs-cat.json"
    r = MOD.add_entry(idx, {**OK_ENTRY, "id": "abs_1"}, None, str(abs_cat), None)
    assert r["mode"] == "router-file"
    assert abs_cat.exists()


def test_add_entry_consult_at_guard_undeclared(tmp_path):
    idx = _make_store(tmp_path, consult_at=None)
    with pytest.raises(ValueError, match="consult_at を宣言していない"):
        MOD.add_entry(idx, dict(OK_ENTRY), "mindset", None, None)


def test_add_entry_consult_at_match(tmp_path):
    idx = _make_store(tmp_path, consult_at=["runtime"])
    r = MOD.add_entry(idx, dict(OK_ENTRY), "mindset", None, "M", consult_at="runtime")
    assert r["added"] is True


# ============================================================================
# self_test : 内蔵テストを直接呼ぶ (全7テスト)
# ============================================================================

def test_self_test_passes(capsys):
    MOD.self_test()  # 例外なく完了すれば PASS
    assert "PASS" in capsys.readouterr().out


def test_self_test_search_knowledge_import_fallback(capsys, monkeypatch):
    # search_knowledge を import 不可にして ImportError フォールバック (line 430-431) を踏む。
    # sys.modules に None を仕込むと `import search_knowledge` が ImportError を送出する。
    monkeypatch.setitem(sys.modules, "search_knowledge", None)
    MOD.self_test()  # ImportError を握り潰して残りのテストが通り PASS
    assert "PASS" in capsys.readouterr().out


# ============================================================================
# main : subprocess で exit code / stdout / stderr / 各異常系
# ============================================================================

def _run_cli(args: list[str], stdin: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        input=stdin, capture_output=True, text=True, timeout=60,
    )


def test_cli_self_test():
    proc = _run_cli(["--self-test"])
    assert proc.returncode == 0
    assert "PASS" in proc.stdout


def test_cli_add_via_args(tmp_path):
    idx = _make_store(tmp_path)
    proc = _run_cli([
        "--index", str(idx), "--category", "mindset",
        "--id", "c_001", "--title", "T", "--intent", "I",
        "--background", "B 数値 1 2", "--keywords", "a,b,c,d,e",
        "--source", "s.md",
    ])
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert out["added"] is True
    assert out["entry_id"] == "c_001"


def test_cli_add_via_json_file(tmp_path):
    idx = _make_store(tmp_path)
    jp = tmp_path / "e.json"
    jp.write_text(json.dumps({**OK_ENTRY, "id": "j_001"}), encoding="utf-8")
    proc = _run_cli(["--index", str(idx), "--category", "mindset", "--json", str(jp)])
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["entry_id"] == "j_001"


def test_cli_add_via_stdin_json(tmp_path):
    idx = _make_store(tmp_path)
    payload = json.dumps({**OK_ENTRY, "id": "s_001"})
    proc = _run_cli(["--index", str(idx), "--category", "mindset", "--json", "-"],
                    stdin=payload)
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["entry_id"] == "s_001"


def test_cli_missing_required_field_exit1(tmp_path):
    idx = _make_store(tmp_path)
    # title 欠落 -> 検証エラー
    proc = _run_cli([
        "--index", str(idx), "--category", "mindset",
        "--id", "x_001", "--intent", "I", "--background", "B",
        "--keywords", "a,b", "--source", "s.md",
    ])
    assert proc.returncode == 1
    assert "error" in json.loads(proc.stderr)


def test_cli_duplicate_id_exit1(tmp_path):
    idx = _make_store(tmp_path)
    args = ["--index", str(idx), "--category", "mindset", "--json", "-"]
    payload = json.dumps({**OK_ENTRY, "id": "d_001"})
    p1 = _run_cli(args, stdin=payload)
    assert p1.returncode == 0, p1.stderr
    p2 = _run_cli(args, stdin=payload)
    assert p2.returncode == 1
    assert "重複" in json.loads(p2.stderr)["error"]


def test_cli_broken_json_exit1(tmp_path):
    idx = _make_store(tmp_path)
    proc = _run_cli(["--index", str(idx), "--category", "mindset", "--json", "-"],
                    stdin="{not json")
    assert proc.returncode == 1
    assert "エントリ読み込み失敗" in json.loads(proc.stderr)["error"]


def test_cli_missing_json_file_exit1(tmp_path):
    idx = _make_store(tmp_path)
    proc = _run_cli(["--index", str(idx), "--category", "mindset",
                     "--json", str(tmp_path / "nope.json")])
    assert proc.returncode == 1
    assert "エントリ読み込み失敗" in json.loads(proc.stderr)["error"]


def test_cli_no_entry_content_argparse_error(tmp_path):
    idx = _make_store(tmp_path)
    # --json も各フィールドも無い -> parser.error (exit 2)
    proc = _run_cli(["--index", str(idx), "--category", "mindset"])
    assert proc.returncode == 2
    assert "エントリ内容を" in proc.stderr


def test_cli_index_not_found_exit1(tmp_path, monkeypatch):
    # --index/--dir 無し + cwd に index なし -> 見つからず exit 1
    empty = tmp_path / "empty"
    empty.mkdir()
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--category", "mindset",
         "--id", "n_001", "--title", "T", "--intent", "I",
         "--background", "B", "--keywords", "a,b,c,d,e", "--source", "s.md"],
        capture_output=True, text=True, timeout=60, cwd=str(empty),
    )
    assert proc.returncode == 1
    assert "knowledge-index.json が見つかりません" in json.loads(proc.stderr)["error"]


def test_cli_consult_at_mismatch_exit1(tmp_path):
    idx = _make_store(tmp_path, consult_at=["runtime"])
    proc = _run_cli([
        "--index", str(idx), "--category", "mindset", "--json", "-",
        "--consult-at", "build-time",
    ], stdin=json.dumps({**OK_ENTRY, "id": "cm_1"}))
    assert proc.returncode == 1
    assert "矛盾" in json.loads(proc.stderr)["error"]


def test_cli_router_file_mode(tmp_path):
    idx = _make_store(tmp_path)
    proc = _run_cli([
        "--index", str(idx), "--file", "knowledge-routing-a.json", "--json", "-",
    ], stdin=json.dumps({**OK_ENTRY, "id": "rf_1"}))
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert out["mode"] == "router-file"


def test_cli_dir_resolves_store(tmp_path):
    # --dir で <dir>/knowledge/knowledge-index.json を解決
    _make_store(tmp_path, consult_at=["runtime"])
    proc = _run_cli([
        "--dir", str(tmp_path), "--category", "mindset", "--json", "-",
    ], stdin=json.dumps({**OK_ENTRY, "id": "dd_1"}))
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["entry_id"] == "dd_1"


# ============================================================================
# main : in-process (sys.argv monkeypatch) で main() 本体を直接カバー
# ============================================================================

def _argv(monkeypatch, args: list[str]) -> None:
    monkeypatch.setattr(sys, "argv", [str(SCRIPT), *args])


def test_main_inproc_self_test_exit0(monkeypatch, capsys):
    _argv(monkeypatch, ["--self-test"])
    with pytest.raises(SystemExit) as ei:
        MOD.main()
    assert ei.value.code == 0
    assert "PASS" in capsys.readouterr().out


def test_main_inproc_add_via_args_success(tmp_path, monkeypatch, capsys):
    idx = _make_store(tmp_path)
    _argv(monkeypatch, [
        "--index", str(idx), "--category", "mindset",
        "--id", "ip_001", "--title", "T", "--intent", "I",
        "--background", "B 1 2", "--keywords", "a,b,c,d,e", "--source", "s.md",
    ])
    MOD.main()  # 正常系は sys.exit を呼ばず print して return
    out = json.loads(capsys.readouterr().out)
    assert out["added"] is True
    assert out["entry_id"] == "ip_001"


def test_main_inproc_add_via_json_file(tmp_path, monkeypatch, capsys):
    idx = _make_store(tmp_path)
    jp = tmp_path / "e.json"
    jp.write_text(json.dumps({**OK_ENTRY, "id": "ipj_1"}), encoding="utf-8")
    _argv(monkeypatch, ["--index", str(idx), "--category", "mindset", "--json", str(jp)])
    MOD.main()
    assert json.loads(capsys.readouterr().out)["entry_id"] == "ipj_1"


def test_main_inproc_broken_json_exit1(tmp_path, monkeypatch, capsys):
    idx = _make_store(tmp_path)
    jp = tmp_path / "bad.json"
    jp.write_text("{broken", encoding="utf-8")
    _argv(monkeypatch, ["--index", str(idx), "--category", "mindset", "--json", str(jp)])
    with pytest.raises(SystemExit) as ei:
        MOD.main()
    assert ei.value.code == 1
    assert "エントリ読み込み失敗" in json.loads(capsys.readouterr().err)["error"]


def test_main_inproc_no_entry_content_errors(tmp_path, monkeypatch):
    idx = _make_store(tmp_path)
    _argv(monkeypatch, ["--index", str(idx), "--category", "mindset"])
    # parser.error は SystemExit(2)
    with pytest.raises(SystemExit) as ei:
        MOD.main()
    assert ei.value.code == 2


def test_main_inproc_index_not_found_exit1(tmp_path, monkeypatch, capsys):
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.chdir(empty)
    _argv(monkeypatch, [
        "--category", "mindset", "--id", "nf_1", "--title", "T", "--intent", "I",
        "--background", "B", "--keywords", "a,b,c,d,e", "--source", "s.md",
    ])
    with pytest.raises(SystemExit) as ei:
        MOD.main()
    assert ei.value.code == 1
    assert "見つかりません" in json.loads(capsys.readouterr().err)["error"]


def test_main_inproc_validation_error_exit1(tmp_path, monkeypatch, capsys):
    idx = _make_store(tmp_path)
    _argv(monkeypatch, [
        "--index", str(idx), "--category", "mindset",
        "--id", "ve_1", "--intent", "I", "--background", "B",
        "--keywords", "a,b", "--source", "s.md",  # title 欠落
    ])
    with pytest.raises(SystemExit) as ei:
        MOD.main()
    assert ei.value.code == 1
    assert "error" in json.loads(capsys.readouterr().err)


def test_main_inproc_broken_index_jsondecode_via_valueerror_branch(tmp_path, monkeypatch, capsys):
    # 壊れた JSON の index -> collect_existing_ids が JSONDecodeError を送出。
    # JSONDecodeError は ValueError サブクラスなので main の except ValueError (line 531-533)
    # が先に捕捉し、raw メッセージを {"error": ...} で stderr に出して exit 1。
    kdir = tmp_path / "knowledge"
    kdir.mkdir()
    idx = kdir / "knowledge-index.json"
    (kdir / "router.json").write_text(json.dumps({"consult_at": ["runtime"]}), encoding="utf-8")
    idx.write_text("{broken json", encoding="utf-8")
    _argv(monkeypatch, [
        "--index", str(idx), "--category", "mindset",
        "--id", "io_1", "--title", "T", "--intent", "I",
        "--background", "B", "--keywords", "a,b,c,d,e", "--source", "s.md",
    ])
    with pytest.raises(SystemExit) as ei:
        MOD.main()
    assert ei.value.code == 1
    err = json.loads(capsys.readouterr().err)
    assert "error" in err  # ValueError 経路で raw JSONDecodeError メッセージが入る


def test_main_inproc_oserror_branch_index_is_dir(tmp_path, monkeypatch, capsys):
    # index パスがディレクトリ -> read_text() が IsADirectoryError (OSError, not ValueError)
    # -> main の except (OSError, json.JSONDecodeError) 分岐 (line 534-536) を踏む。
    kdir = tmp_path / "knowledge"
    kdir.mkdir()
    idx = kdir / "knowledge-index.json"
    idx.mkdir()  # index がディレクトリ実体
    (kdir / "router.json").write_text(json.dumps({"consult_at": ["runtime"]}), encoding="utf-8")
    _argv(monkeypatch, [
        "--index", str(idx), "--category", "mindset",
        "--id", "od_1", "--title", "T", "--intent", "I",
        "--background", "B", "--keywords", "a,b,c,d,e", "--source", "s.md",
    ])
    with pytest.raises(SystemExit) as ei:
        MOD.main()
    assert ei.value.code == 1
    assert "IO/JSON 失敗" in json.loads(capsys.readouterr().err)["error"]
