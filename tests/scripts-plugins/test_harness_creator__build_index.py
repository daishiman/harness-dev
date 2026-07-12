"""run-build-skill/templates/knowledge-skeleton/scripts/build_index.py の genuine 機能テスト。

knowledge-index.json とカテゴリファイル群の整合性を検証 (--stats) / 自動修正 (--fix) /
自検証 (--self-test) する決定論スクリプト。純関数を実ファイルから importlib でロードして
実入力で assert し、main は subprocess(sys.executable) で exit code / 出力を確認する。

カバー分岐:
- find_index: knowledge/ サブディレクトリ / 直下 / 親遡上 / 不在 None
- load_index: 正常 JSON のパース
- check_entry: 全フィールド充足で [] / 各欠落 (id/title|content/intent|purpose/
  background/keywords|tags/source) を個別検出 / content・tags・purpose の別名許容
- run_stats: 正常統計 / カテゴリファイル不在 error / 不正 JSON error /
  0件 warning / ID 重複 error / 必須フィールド欠落 error / 複数カテゴリ集計
- fix_index: 不在参照削除して index 書き換え / 削除対象なしで no-op
- self_test: 内蔵テスト全通過
- main(CLI): --self-test / セレクタ無しエラー / --index / --dir(両解決) /
  index 不在 exit1 / 不正 index JSON exit1 / --stats 正常 / errors 有りで exit2 /
  --fix の出力と exit / auto-discovery(cwd) 経路

network: false, keychain: なし, 実 repo 書換: なし (tmp_path のみ)。
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    ROOT
    / "plugins"
    / "harness-creator"
    / "skills"
    / "run-build-skill"
    / "templates"
    / "knowledge-skeleton"
    / "scripts"
    / "build_index.py"
)

SPEC = importlib.util.spec_from_file_location("build_index_uut", SCRIPT)
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


# ── fixtures ─────────────────────────────────────────────────────────────────

OK_ITEM = {
    "id": "ok_001",
    "title": "正常タイトル",
    "intent": "整合性を確認する",
    "background": "テスト環境で整合性検証を行う背景説明。",
    "keywords": ["検証", "整合性"],
    "source": {"file": "src.md", "type": "doc", "date": "2026-01-01", "section": "§1"},
}


def _build_store(base: Path, items=None, *, with_missing=False, extra_cats=None):
    """base/knowledge/ に index + カテゴリファイルを作り index path を返す。"""
    items = items if items is not None else [OK_ITEM]
    kdir = base / "knowledge"
    kdir.mkdir(parents=True, exist_ok=True)
    categories = [
        {"id": "exists", "label": "存在", "file": "knowledge-exists.json", "keywords": []}
    ]
    if with_missing:
        categories.append(
            {"id": "missing", "label": "不在", "file": "knowledge-missing.json", "keywords": []}
        )
    if extra_cats:
        categories.extend(extra_cats)
    index_data = {"version": "1.0.0", "categories": categories, "global_keywords": {}}
    cat_data = {"category": "exists", "label": "存在", "version": "1.0.0", "items": items}
    idx = kdir / "knowledge-index.json"
    idx.write_text(json.dumps(index_data, ensure_ascii=False), encoding="utf-8")
    (kdir / "knowledge-exists.json").write_text(
        json.dumps(cat_data, ensure_ascii=False), encoding="utf-8"
    )
    return idx


# ── find_index ───────────────────────────────────────────────────────────────

def test_find_index_in_knowledge_subdir(tmp_path):
    idx = _build_store(tmp_path)
    found = MOD.find_index(tmp_path)
    assert found == idx


def test_find_index_flat_alongside(tmp_path):
    # knowledge/ サブディレクトリでなく直下に置いたケース
    flat = tmp_path / "store"
    flat.mkdir()
    p = flat / "knowledge-index.json"
    p.write_text(json.dumps({"categories": []}), encoding="utf-8")
    found = MOD.find_index(flat)
    assert found == p


def test_find_index_walks_up_parents(tmp_path):
    idx = _build_store(tmp_path)
    deep = tmp_path / "knowledge" / "a" / "b"
    deep.mkdir(parents=True)
    # 子から親へ遡上して knowledge/knowledge-index.json を発見
    found = MOD.find_index(deep)
    assert found == idx


def test_find_index_returns_none_when_absent(tmp_path):
    empty = tmp_path / "void"
    empty.mkdir()
    assert MOD.find_index(empty) is None


# ── load_index ───────────────────────────────────────────────────────────────

def test_load_index_parses_json(tmp_path):
    idx = _build_store(tmp_path)
    data = MOD.load_index(idx)
    assert data["version"] == "1.0.0"
    assert isinstance(data["categories"], list)


def test_load_index_raises_on_bad_json(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("{ not valid", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        MOD.load_index(p)


# ── check_entry ──────────────────────────────────────────────────────────────

def test_check_entry_ok_returns_empty():
    assert MOD.check_entry(OK_ITEM) == []


def test_check_entry_accepts_content_tags_purpose_aliases():
    # title→content, keywords→tags, intent→purpose の別名でも合格する
    item = {
        "id": "alias_1",
        "content": "本文",
        "purpose": "目的",
        "background": "背景",
        "tags": ["a"],
        "source": {"file": "x"},
    }
    assert MOD.check_entry(item) == []


def test_check_entry_missing_id():
    item = {k: v for k, v in OK_ITEM.items() if k != "id"}
    issues = MOD.check_entry(item)
    assert any("id" in i for i in issues)


def test_check_entry_missing_title_or_content():
    item = {k: v for k, v in OK_ITEM.items() if k != "title"}
    issues = MOD.check_entry(item)
    assert any("title" in i or "content" in i for i in issues)


def test_check_entry_missing_intent_or_purpose():
    item = {k: v for k, v in OK_ITEM.items() if k != "intent"}
    issues = MOD.check_entry(item)
    assert any("intent" in i or "purpose" in i for i in issues)


def test_check_entry_missing_background():
    item = {k: v for k, v in OK_ITEM.items() if k != "background"}
    issues = MOD.check_entry(item)
    assert any("background" in i for i in issues)


def test_check_entry_missing_keywords_or_tags():
    item = {k: v for k, v in OK_ITEM.items() if k != "keywords"}
    issues = MOD.check_entry(item)
    assert any("keywords" in i or "tags" in i for i in issues)


def test_check_entry_missing_source():
    item = {k: v for k, v in OK_ITEM.items() if k != "source"}
    issues = MOD.check_entry(item)
    assert any("source" in i for i in issues)


def test_check_entry_empty_item_flags_all():
    issues = MOD.check_entry({})
    # 6 種すべて欠落 → 6 件
    assert len(issues) == 6


# ── run_stats ────────────────────────────────────────────────────────────────

def test_run_stats_clean_store_no_errors(tmp_path):
    idx = _build_store(tmp_path)
    stats = MOD.run_stats(idx)
    assert stats["category_count"] == 1
    assert stats["total_entries"] == 1
    assert stats["errors"] == []
    assert stats["warnings"] == []
    assert stats["index_path"] == str(idx)


def test_run_stats_missing_category_file_is_error(tmp_path):
    idx = _build_store(tmp_path, with_missing=True)
    stats = MOD.run_stats(idx)
    assert any("missing" in e for e in stats["errors"])
    assert stats["category_count"] == 2


def test_run_stats_invalid_category_json_is_error(tmp_path):
    idx = _build_store(tmp_path)
    # exists カテゴリファイルを破損させる
    (tmp_path / "knowledge" / "knowledge-exists.json").write_text("{ broken", encoding="utf-8")
    stats = MOD.run_stats(idx)
    assert any("JSON解析失敗" in e for e in stats["errors"])


def test_run_stats_empty_items_is_warning(tmp_path):
    idx = _build_store(tmp_path, items=[])
    stats = MOD.run_stats(idx)
    assert any("0件" in w for w in stats["warnings"])
    assert stats["total_entries"] == 0


def test_run_stats_duplicate_id_is_error(tmp_path):
    dup = {**OK_ITEM}
    idx = _build_store(tmp_path, items=[OK_ITEM, dup])
    stats = MOD.run_stats(idx)
    assert any("IDが重複" in e for e in stats["errors"])


def test_run_stats_field_violation_is_error(tmp_path):
    bad = {"id": "bad_1", "background": "背景のみ"}
    idx = _build_store(tmp_path, items=[bad])
    stats = MOD.run_stats(idx)
    # [exists/bad_1] プレフィクス付きエラーが立つ
    assert any("bad_1" in e for e in stats["errors"])
    assert any("title" in e or "content" in e for e in stats["errors"])


def test_run_stats_aggregates_multiple_categories(tmp_path):
    # 2 つ目の存在するカテゴリを追加し total_entries が合算されることを検証
    idx = _build_store(
        tmp_path,
        extra_cats=[{"id": "second", "label": "二", "file": "knowledge-second.json", "keywords": []}],
    )
    second = {
        "category": "second",
        "label": "二",
        "version": "1.0.0",
        "items": [{**OK_ITEM, "id": "ok_002"}],
    }
    (tmp_path / "knowledge" / "knowledge-second.json").write_text(
        json.dumps(second, ensure_ascii=False), encoding="utf-8"
    )
    stats = MOD.run_stats(idx)
    assert stats["total_entries"] == 2
    assert stats["errors"] == []


# ── fix_index ────────────────────────────────────────────────────────────────

def test_fix_index_removes_dangling_reference(tmp_path):
    idx = _build_store(tmp_path, with_missing=True)
    fixes = MOD.fix_index(idx)
    assert len(fixes) >= 1
    assert any("missing" in f for f in fixes)
    # 書き換え後は missing が消えている
    data = json.loads(idx.read_text(encoding="utf-8"))
    cat_ids = [c["id"] for c in data["categories"]]
    assert "missing" not in cat_ids
    assert "exists" in cat_ids


def test_fix_index_no_change_returns_empty(tmp_path):
    idx = _build_store(tmp_path)
    before = idx.read_text(encoding="utf-8")
    fixes = MOD.fix_index(idx)
    assert fixes == []
    # 変更が無ければファイルも不変
    assert idx.read_text(encoding="utf-8") == before


def test_fix_index_then_stats_is_clean(tmp_path):
    idx = _build_store(tmp_path, with_missing=True)
    MOD.fix_index(idx)
    stats = MOD.run_stats(idx)
    assert not any("missing" in e for e in stats["errors"])


# ── self_test ────────────────────────────────────────────────────────────────

def test_self_test_passes(capsys):
    MOD.self_test()
    assert "PASS" in capsys.readouterr().out


# ── CLI subprocess ───────────────────────────────────────────────────────────

def _run(*args, cwd=None):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        text=True,
        capture_output=True,
        cwd=str(cwd) if cwd else None,
    )


def test_cli_self_test_exit_zero():
    res = _run("--self-test")
    assert res.returncode == 0
    assert "PASS" in res.stdout


def test_cli_no_selector_errors_exit_2():
    # argparse parser.error → exit code 2
    res = _run()
    assert res.returncode == 2
    assert "--stats" in res.stderr or "指定" in res.stderr


def test_cli_stats_clean_exit_zero(tmp_path):
    idx = _build_store(tmp_path)
    res = _run("--stats", "--index", str(idx))
    assert res.returncode == 0, res.stderr
    out = json.loads(res.stdout)
    assert out["total_entries"] == 1
    assert out["errors"] == []


def test_cli_stats_with_errors_exit_2(tmp_path):
    idx = _build_store(tmp_path, with_missing=True)
    res = _run("--stats", "--index", str(idx))
    assert res.returncode == 2
    out = json.loads(res.stdout)
    assert any("missing" in e for e in out["errors"])


def test_cli_index_not_found_exit_1(tmp_path):
    res = _run("--stats", "--index", str(tmp_path / "nope.json"))
    assert res.returncode == 1
    assert "見つかりません" in json.loads(res.stderr)["error"]


def test_cli_invalid_index_json_exit_1(tmp_path):
    kdir = tmp_path / "knowledge"
    kdir.mkdir()
    p = kdir / "knowledge-index.json"
    p.write_text("{ not valid json", encoding="utf-8")
    res = _run("--stats", "--index", str(p))
    assert res.returncode == 1
    assert "JSON解析失敗" in json.loads(res.stderr)["error"]


def test_cli_fix_outputs_fixes_and_clean_stats(tmp_path):
    idx = _build_store(tmp_path, with_missing=True)
    res = _run("--fix", "--index", str(idx))
    # --fix は fixes JSON と stats JSON を続けて出力。fix 後 stats はクリーンなので exit 0
    assert res.returncode == 0, res.stderr
    # 2 つの JSON オブジェクトが順に出る
    assert '"fixes"' in res.stdout
    assert '"count"' in res.stdout
    # index が実際に書き換わっている
    data = json.loads(idx.read_text(encoding="utf-8"))
    assert "missing" not in [c["id"] for c in data["categories"]]


def test_cli_dir_resolves_flat(tmp_path):
    # --dir 直下に knowledge-index.json を置くケース
    flat = tmp_path / "store"
    flat.mkdir()
    idx = flat / "knowledge-index.json"
    idx.write_text(json.dumps({"version": "1.0.0", "categories": []}), encoding="utf-8")
    res = _run("--stats", "--dir", str(flat))
    assert res.returncode == 0, res.stderr
    assert json.loads(res.stdout)["category_count"] == 0


def test_cli_dir_resolves_knowledge_subdir(tmp_path):
    _build_store(tmp_path)
    res = _run("--stats", "--dir", str(tmp_path))
    assert res.returncode == 0, res.stderr
    assert json.loads(res.stdout)["total_entries"] == 1


def test_cli_auto_discovery_via_cwd(tmp_path):
    # --index/--dir 無し → cwd から search_knowledge.find_index で自動探索
    _build_store(tmp_path)
    res = _run("--stats", cwd=tmp_path)
    assert res.returncode == 0, res.stderr
    assert json.loads(res.stdout)["total_entries"] == 1


def test_cli_auto_discovery_no_index_exit_1(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    res = _run("--stats", cwd=empty)
    assert res.returncode == 1
    assert "見つかりません" in json.loads(res.stderr)["error"]


# ── main() in-process (coverage 計上のため argv を monkeypatch で駆動) ─────────
# subprocess は別プロセスのため `--cov` に計上されない。main() 本体 (引数解決 /
# 例外ハンドリング / exit code) を in-process で網羅する。


def _run_main(monkeypatch, *args):
    monkeypatch.setattr(sys, "argv", ["build_index.py", *args])
    with pytest.raises(SystemExit) as exc:
        MOD.main()
    return exc.value.code


def test_main_self_test_exit_zero(monkeypatch, capsys):
    code = _run_main(monkeypatch, "--self-test")
    assert code == 0
    assert "PASS" in capsys.readouterr().out


def test_main_no_selector_parser_error(monkeypatch):
    # parser.error は SystemExit(2)
    code = _run_main(monkeypatch, "--index", "x.json")
    assert code == 2


def test_main_stats_clean_exit_zero(monkeypatch, capsys, tmp_path):
    idx = _build_store(tmp_path)
    monkeypatch.setattr(sys, "argv", ["build_index.py", "--stats", "--index", str(idx)])
    # errors 無しなので sys.exit は呼ばれず main は正常 return する
    MOD.main()
    out = json.loads(capsys.readouterr().out)
    assert out["total_entries"] == 1
    assert out["errors"] == []


def test_main_stats_with_errors_exit_2(monkeypatch, capsys, tmp_path):
    idx = _build_store(tmp_path, with_missing=True)
    code = _run_main(monkeypatch, "--stats", "--index", str(idx))
    assert code == 2
    out = json.loads(capsys.readouterr().out)
    assert any("missing" in e for e in out["errors"])


def test_main_index_not_found_exit_1(monkeypatch, capsys, tmp_path):
    code = _run_main(monkeypatch, "--stats", "--index", str(tmp_path / "nope.json"))
    assert code == 1
    assert "見つかりません" in json.loads(capsys.readouterr().err)["error"]


def test_main_invalid_index_json_exit_1(monkeypatch, capsys, tmp_path):
    kdir = tmp_path / "knowledge"
    kdir.mkdir()
    p = kdir / "knowledge-index.json"
    p.write_text("{ not valid", encoding="utf-8")
    code = _run_main(monkeypatch, "--stats", "--index", str(p))
    assert code == 1
    assert "JSON解析失敗" in json.loads(capsys.readouterr().err)["error"]


def test_main_fix_writes_index_exit_zero(monkeypatch, capsys, tmp_path):
    idx = _build_store(tmp_path, with_missing=True)
    monkeypatch.setattr(sys, "argv", ["build_index.py", "--fix", "--index", str(idx)])
    # fix 後 stats はクリーン → exit せず return
    MOD.main()
    out = capsys.readouterr().out
    assert '"fixes"' in out
    data = json.loads(idx.read_text(encoding="utf-8"))
    assert "missing" not in [c["id"] for c in data["categories"]]


def test_main_dir_resolves_knowledge_subdir(monkeypatch, capsys, tmp_path):
    _build_store(tmp_path)
    monkeypatch.setattr(sys, "argv", ["build_index.py", "--stats", "--dir", str(tmp_path)])
    MOD.main()
    assert json.loads(capsys.readouterr().out)["total_entries"] == 1


def test_main_dir_resolves_flat(monkeypatch, capsys, tmp_path):
    flat = tmp_path / "store"
    flat.mkdir()
    idx = flat / "knowledge-index.json"
    idx.write_text(json.dumps({"version": "1.0.0", "categories": []}), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["build_index.py", "--stats", "--dir", str(flat)])
    MOD.main()
    assert json.loads(capsys.readouterr().out)["category_count"] == 0


def test_main_auto_discovery_via_cwd(monkeypatch, capsys, tmp_path):
    # --index/--dir 無し → search_knowledge.find_index を import して cwd 探索。
    # in-process では sibling の search_knowledge を import path に通す必要がある。
    _build_store(tmp_path)
    monkeypatch.syspath_prepend(str(SCRIPT.parent))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["build_index.py", "--stats"])
    MOD.main()
    assert json.loads(capsys.readouterr().out)["total_entries"] == 1


def test_main_auto_discovery_no_index_exit_1(monkeypatch, capsys, tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.syspath_prepend(str(SCRIPT.parent))
    monkeypatch.chdir(empty)
    code = _run_main(monkeypatch, "--stats")
    assert code == 1
    assert "見つかりません" in json.loads(capsys.readouterr().err)["error"]
