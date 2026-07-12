"""run-build-skill/templates/knowledge-skeleton/scripts/search_knowledge.py の genuine 機能テスト。

knowledge/ を Stage1(global_keywords でカテゴリ絞り) + Stage2(フィールド重み付き
スコア) で検索する決定論スクリプト。純関数を実ファイルから importlib でロードして
実入力で assert し、main は subprocess(sys.executable) で exit code / 出力を確認する。

カバー分岐:
- load_index / load_category_file: 正常 JSON のパース、items 欠落時の [] フォールバック
- expand_synonyms: canonical 一致 / syn 一致 / 非該当 / 重複除去・順序保持
- stage1_filter_categories: マッチ有り(部分一致双方向) / スコア0で全カテゴリ返す
- build_search_text: 複数フィールド連結 / 欠落フィールドスキップ
- score_item: title/keywords/quote/voice/fulltext 各重み, expression.phrasing 経路,
  content/tags/expressions 別名フィールド, 頻度カウント
- search: query 経路 / keywords 経路 / category 経路 / id 直引き(ヒット/ミス) /
  キーワード無し(score 0) / deprecated 除外 / 欠落カテゴリファイル skip / limit
- find_index: knowledge/ サブディレクトリ / 直下 / 親遡上 / 不在 None
- self_test: 内蔵 4 テスト通過
- main(CLI): self-test / 引数なしエラー / --index / --dir(両解決) / index 不在 /
  不正 JSON / 正常検索の JSON 出力 / --id / --category

network: false, keychain: なし, 実 repo 書換: なし (tmp_path のみ)。
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "plugins"
    / "harness-creator"
    / "skills"
    / "run-build-skill"
    / "templates"
    / "knowledge-skeleton"
    / "scripts"
    / "search_knowledge.py"
)

SPEC = importlib.util.spec_from_file_location("search_knowledge_uut", SCRIPT)
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


# ── fixtures ────────────────────────────────────────────────────────────────
def _build_store(tmp_path, *, items=None, index_extra=None, with_index=True):
    """tmp_path/knowledge/ に index + 1 カテゴリファイルを作って index path を返す。"""
    kdir = tmp_path / "knowledge"
    kdir.mkdir()
    index_data = {
        "version": "1.0.0",
        "categories": [
            {"id": "mindset", "label": "心構え", "file": "knowledge-mindset.json", "keywords": ["心構え"]}
        ],
        "global_keywords": {"効率": ["mindset"]},
        "synonyms": {"改善策": ["改良案", "対策"]},
        "scoring_weights": {},
    }
    if index_extra:
        index_data.update(index_extra)
    if items is None:
        items = [
            {
                "id": "mindset_001",
                "title": "アルファ手法は効率を高める",
                "intent": "アルファ手法の有効性を認知させる",
                "background": "既存手法で成果が出なかった状況。",
                "keywords": ["アルファ手法", "効率改善"],
                "quote": ["効率は積み重ねで決まる"],
            }
        ]
    cat_data = {"category": "mindset", "label": "心構え", "items": items}
    if with_index:
        (kdir / "knowledge-index.json").write_text(json.dumps(index_data, ensure_ascii=False), encoding="utf-8")
    (kdir / "knowledge-mindset.json").write_text(json.dumps(cat_data, ensure_ascii=False), encoding="utf-8")
    return kdir / "knowledge-index.json"


# ── load_index / load_category_file ─────────────────────────────────────────
def test_load_index_parses_json(tmp_path):
    idx = _build_store(tmp_path)
    data = MOD.load_index(idx)
    assert data["version"] == "1.0.0"
    assert data["categories"][0]["id"] == "mindset"


def test_load_category_file_returns_items(tmp_path):
    _build_store(tmp_path)
    items = MOD.load_category_file(tmp_path / "knowledge" / "knowledge-mindset.json")
    assert items[0]["id"] == "mindset_001"


def test_load_category_file_missing_items_returns_empty(tmp_path):
    p = tmp_path / "cat.json"
    p.write_text(json.dumps({"category": "x"}), encoding="utf-8")
    assert MOD.load_category_file(p) == []


# ── expand_synonyms ─────────────────────────────────────────────────────────
def test_expand_synonyms_canonical_match():
    out = MOD.expand_synonyms(["改善策"], {"改善策": ["改良案", "対策"]})
    assert "改良案" in out and "対策" in out and "改善策" in out


def test_expand_synonyms_synonym_match_resolves_canonical():
    out = MOD.expand_synonyms(["改良案"], {"改善策": ["改良案", "対策"]})
    # syn から canonical+全 syn が展開される
    assert "改善策" in out and "対策" in out


def test_expand_synonyms_no_match_keeps_only_input():
    out = MOD.expand_synonyms(["無関係"], {"改善策": ["改良案"]})
    assert out == ["無関係"]


def test_expand_synonyms_dedup_preserves_order():
    out = MOD.expand_synonyms(["a", "a", "b"], {})
    assert out == ["a", "b"]


# ── stage1_filter_categories ────────────────────────────────────────────────
def test_stage1_filter_matches_global_keyword():
    index = {
        "global_keywords": {"効率": ["mindset"]},
        "categories": [{"id": "mindset"}, {"id": "other"}],
    }
    out = MOD.stage1_filter_categories(index, ["効率"])
    assert [c["id"] for c in out] == ["mindset"]


def test_stage1_filter_partial_match_reverse():
    # gk が kw を包含する経路 (gk.lower() in kw_lower の逆) も拾う
    index = {
        "global_keywords": {"効率": ["mindset"]},
        "categories": [{"id": "mindset"}],
    }
    out = MOD.stage1_filter_categories(index, ["効率改善"])  # kw が gk を包含
    assert [c["id"] for c in out] == ["mindset"]


def test_stage1_filter_no_match_returns_all_categories():
    index = {
        "global_keywords": {"効率": ["mindset"]},
        "categories": [{"id": "mindset"}, {"id": "other"}],
    }
    out = MOD.stage1_filter_categories(index, ["全く無関係"])
    assert {c["id"] for c in out} == {"mindset", "other"}


# ── build_search_text ───────────────────────────────────────────────────────
def test_build_search_text_concatenates_present_fields():
    txt = MOD.build_search_text({"background": "BG", "message": "MSG", "absent": None})
    assert "BG" in txt and "MSG" in txt


def test_build_search_text_skips_empty():
    assert MOD.build_search_text({}) == ""


# ── score_item ──────────────────────────────────────────────────────────────
def test_score_item_title_weight_dominates():
    item = {"title": "アルファ手法", "background": "アルファ手法 アルファ手法"}
    sc = MOD.score_item(item, ["アルファ手法"], MOD.DEFAULT_WEIGHTS)
    # title(5) + fulltext freq2(2) = 7
    assert sc == 5 + 2


def test_score_item_keywords_and_quote_and_voice():
    item = {
        "title": "T",
        "keywords": ["効率改善"],
        "quote": ["効率は重要"],
        "voice": "効率を語る声",
    }
    sc = MOD.score_item(item, ["効率"], MOD.DEFAULT_WEIGHTS)
    # keywords(3) + quote(2) + voice(2) = 7 (title に "効率" なし)
    assert sc == 3 + 2 + 2


def test_score_item_alt_fields_content_tags_expressions_phrasing():
    item = {
        "content": "効率の話",  # title 別名
        "tags": ["効率タグ"],  # keywords 別名
        "expressions": ["効率の表現"],  # quote 別名
        "expression": {"phrasing": "効率な言い回し"},  # voice 別名
    }
    sc = MOD.score_item(item, ["効率"], MOD.DEFAULT_WEIGHTS)
    # title(5)+keywords(3)+quote(2)+voice(2) = 12
    assert sc == 5 + 3 + 2 + 2


def test_score_item_zero_when_no_hit():
    assert MOD.score_item({"title": "x"}, ["存在しない語"], MOD.DEFAULT_WEIGHTS) == 0


# ── search ──────────────────────────────────────────────────────────────────
def test_search_by_query_returns_scored_results(tmp_path):
    idx = _build_store(tmp_path)
    res = MOD.search(idx, "アルファ手法 効率", None, None, None, 5)
    assert res and res[0]["item"]["id"] == "mindset_001"
    assert res[0]["score"] > 0


def test_search_by_keywords(tmp_path):
    idx = _build_store(tmp_path)
    res = MOD.search(idx, None, "効率改善, アルファ手法", None, None, 5)
    assert res[0]["item"]["id"] == "mindset_001"


def test_search_by_category_filter(tmp_path):
    idx = _build_store(tmp_path)
    res = MOD.search(idx, None, "効率", "mindset", None, 5)
    assert res[0]["category"] == "mindset"


def test_search_category_filter_nonexistent_returns_empty(tmp_path):
    idx = _build_store(tmp_path)
    res = MOD.search(idx, None, "効率", "nope", None, 5)
    assert res == []


def test_search_by_id_hit(tmp_path):
    idx = _build_store(tmp_path)
    res = MOD.search(idx, None, None, None, "mindset_001", 5)
    assert len(res) == 1
    assert res[0]["score"] == 999


def test_search_by_id_miss_returns_empty(tmp_path):
    idx = _build_store(tmp_path)
    assert MOD.search(idx, None, None, None, "missing_id", 5) == []


def test_search_no_keywords_returns_zero_scores(tmp_path):
    # query/keywords/category/id 全て None → 全件 score 0 で返る
    idx = _build_store(tmp_path)
    res = MOD.search(idx, None, None, None, None, 5)
    assert all(r["score"] == 0 for r in res)
    assert len(res) == 1


def test_search_excludes_deprecated(tmp_path):
    items = [
        {"id": "a", "title": "効率A"},
        {"id": "b", "title": "効率B", "status": "deprecated"},
    ]
    idx = _build_store(tmp_path, items=items)
    res = MOD.search(idx, None, "効率", None, None, 5)
    ids = [r["item"]["id"] for r in res]
    assert "a" in ids and "b" not in ids


def test_search_skips_missing_category_file(tmp_path):
    # index にカテゴリ登録があるが実ファイルが無い → Stage2 ループで skip (continue)。
    # ghost を Stage1 通過させるため global_keywords を空にして全カテゴリ対象にする。
    idx = _build_store(
        tmp_path,
        index_extra={
            "global_keywords": {},
            "categories": [
                {"id": "mindset", "label": "心構え", "file": "knowledge-mindset.json", "keywords": []},
                {"id": "ghost", "label": "幽霊", "file": "knowledge-ghost.json", "keywords": []},
            ],
        },
    )
    # keywords ありで Stage1 はスコア0→全カテゴリ返す。ghost の実ファイルが無いので continue 経路。
    res = MOD.search(idx, None, "効率", None, None, 5)
    cats = {r["category"] for r in res}
    assert "mindset" in cats and "ghost" not in cats


def test_search_id_skips_missing_category_file(tmp_path):
    idx = _build_store(
        tmp_path,
        index_extra={
            "categories": [
                {"id": "ghost", "label": "幽霊", "file": "knowledge-ghost.json", "keywords": []},
                {"id": "mindset", "label": "心構え", "file": "knowledge-mindset.json", "keywords": []},
            ]
        },
    )
    res = MOD.search(idx, None, None, None, "mindset_001", 5)
    assert len(res) == 1


def test_search_limit_truncates(tmp_path):
    items = [{"id": f"i{n}", "title": f"効率{n}"} for n in range(5)]
    idx = _build_store(tmp_path, items=items)
    res = MOD.search(idx, None, "効率", None, None, 2)
    assert len(res) == 2


# ── find_index ──────────────────────────────────────────────────────────────
def test_find_index_in_knowledge_subdir(tmp_path):
    _build_store(tmp_path)
    found = MOD.find_index(tmp_path)
    assert found == tmp_path / "knowledge" / "knowledge-index.json"


def test_find_index_direct_file(tmp_path):
    (tmp_path / "knowledge-index.json").write_text("{}", encoding="utf-8")
    found = MOD.find_index(tmp_path)
    assert found == tmp_path / "knowledge-index.json"


def test_find_index_walks_up_parents(tmp_path):
    _build_store(tmp_path)
    deep = tmp_path / "a" / "b" / "c"
    deep.mkdir(parents=True)
    found = MOD.find_index(deep)
    assert found == tmp_path / "knowledge" / "knowledge-index.json"


def test_find_index_returns_none_when_absent(tmp_path):
    assert MOD.find_index(tmp_path) is None


# ── self_test (in-process) ──────────────────────────────────────────────────
def test_self_test_passes(capsys):
    MOD.self_test()
    assert "PASS" in capsys.readouterr().out


# ── CLI subprocess ──────────────────────────────────────────────────────────
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
    assert "いずれか" in res.stderr


def test_cli_with_index_query_outputs_json(tmp_path):
    idx = _build_store(tmp_path)
    res = _run("--index", str(idx), "--query", "アルファ手法 効率", "--limit", "5")
    assert res.returncode == 0, res.stderr
    out = json.loads(res.stdout)
    assert out["count"] == 1
    assert out["results"][0]["id"] == "mindset_001"
    assert out["results"][0]["score"] > 0


def test_cli_with_dir_direct_index(tmp_path):
    _build_store(tmp_path)
    # --dir 指す先に knowledge-index.json 直下を置く
    flat = tmp_path / "flat"
    flat.mkdir()
    (flat / "knowledge-index.json").write_text(
        json.dumps({"categories": [], "global_keywords": {}, "synonyms": {}, "scoring_weights": {}}),
        encoding="utf-8",
    )
    res = _run("--dir", str(flat), "--query", "x")
    assert res.returncode == 0, res.stderr
    assert json.loads(res.stdout)["count"] == 0


def test_cli_with_dir_knowledge_subdir(tmp_path):
    _build_store(tmp_path)
    res = _run("--dir", str(tmp_path), "--keywords", "効率")
    assert res.returncode == 0, res.stderr
    assert json.loads(res.stdout)["count"] == 1


def test_cli_index_not_found_exit_1(tmp_path):
    res = _run("--index", str(tmp_path / "nope.json"), "--query", "x")
    assert res.returncode == 1
    # stderr は ensure_ascii の JSON (Unicode エスケープ) なのでパースして検証
    assert "見つかりません" in json.loads(res.stderr)["error"]


def test_cli_auto_discovery_via_cwd(tmp_path):
    _build_store(tmp_path)
    res = _run("--query", "効率", cwd=tmp_path)
    assert res.returncode == 0, res.stderr
    assert json.loads(res.stdout)["count"] == 1


def test_cli_invalid_json_exit_1(tmp_path):
    kdir = tmp_path / "knowledge"
    kdir.mkdir()
    (kdir / "knowledge-index.json").write_text("{ not valid json", encoding="utf-8")
    res = _run("--index", str(kdir / "knowledge-index.json"), "--query", "x")
    assert res.returncode == 1
    assert "JSON解析失敗" in json.loads(res.stderr)["error"]


def test_cli_id_lookup(tmp_path):
    idx = _build_store(tmp_path)
    res = _run("--index", str(idx), "--id", "mindset_001")
    assert res.returncode == 0, res.stderr
    out = json.loads(res.stdout)
    assert out["count"] == 1
    assert out["results"][0]["score"] == 999


def test_cli_category_filter(tmp_path):
    idx = _build_store(tmp_path)
    res = _run("--index", str(idx), "--category", "mindset")
    assert res.returncode == 0, res.stderr
    assert json.loads(res.stdout)["count"] == 1


def test_cli_output_uses_alt_fields_content_purpose_tags(tmp_path):
    # title/intent/keywords を欠き content/purpose/tags のみ持つ item で
    # main の出力フォールバック分岐 (r["item"].get("title") or get("content") 等) を踏む
    items = [{"id": "alt_001", "content": "代替コンテンツ", "purpose": "代替目的", "tags": ["tag1"]}]
    idx = _build_store(tmp_path, items=items)
    res = _run("--index", str(idx), "--category", "mindset")
    assert res.returncode == 0, res.stderr
    out = json.loads(res.stdout)["results"][0]
    assert out["title"] == "代替コンテンツ"
    assert out["intent"] == "代替目的"
    assert out["keywords"] == ["tag1"]


def test_cli_dir_auto_discovery_no_index_found(tmp_path, monkeypatch):
    # --query のみで cwd 配下に index 無し → 自動探索失敗 exit 1
    empty = tmp_path / "empty"
    empty.mkdir()
    res = _run("--query", "x", cwd=empty)
    assert res.returncode == 1
    assert "見つかりません" in json.loads(res.stderr)["error"]


# ── main() in-process (argv monkeypatch + SystemExit) ────────────────────────
# subprocess 経由のテストは `--cov` 単体実行では main 本体の行カバレッジが計上され
# ないため、in-process でも全終了経路 (271-330 行) を踏む。
def _call_main(monkeypatch, argv):
    # 成功経路の main() は sys.exit を呼ばず正常 return する (暗黙 exit 0)。
    # エラー/自己テスト経路は SystemExit を投げる。両方を扱い終了コードを返す。
    monkeypatch.setattr(MOD.sys, "argv", argv)
    try:
        MOD.main()
        return 0
    except SystemExit as exc:
        return exc.code if exc.code is not None else 0


def test_main_self_test_exit_zero_in_process(monkeypatch, capsys):
    code = _call_main(monkeypatch, ["search_knowledge.py", "--self-test"])
    assert code == 0
    assert "PASS" in capsys.readouterr().out


def test_main_no_selector_errors_exit_2_in_process(monkeypatch):
    # argparse parser.error → SystemExit(2)
    code = _call_main(monkeypatch, ["search_knowledge.py"])
    assert code == 2


def test_main_with_index_query_outputs_json_in_process(monkeypatch, tmp_path, capsys):
    idx = _build_store(tmp_path)
    code = _call_main(
        monkeypatch,
        ["search_knowledge.py", "--index", str(idx), "--query", "アルファ手法 効率"],
    )
    cap = capsys.readouterr()
    assert code == 0
    out = json.loads(cap.out)
    assert out["count"] == 1
    assert out["results"][0]["id"] == "mindset_001"


def test_main_with_dir_direct_index_in_process(monkeypatch, tmp_path, capsys):
    # <dir>/knowledge-index.json が直下に存在する経路 (cand.exists() True)
    flat = tmp_path / "flat"
    flat.mkdir()
    (flat / "knowledge-index.json").write_text(
        json.dumps({"categories": [], "global_keywords": {}, "synonyms": {}, "scoring_weights": {}}),
        encoding="utf-8",
    )
    code = _call_main(monkeypatch, ["search_knowledge.py", "--dir", str(flat), "--query", "x"])
    cap = capsys.readouterr()
    assert code == 0
    assert json.loads(cap.out)["count"] == 0


def test_main_with_dir_knowledge_subdir_in_process(monkeypatch, tmp_path, capsys):
    # <dir>/knowledge-index.json が無く <dir>/knowledge/knowledge-index.json へフォールバック
    _build_store(tmp_path)
    code = _call_main(monkeypatch, ["search_knowledge.py", "--dir", str(tmp_path), "--keywords", "効率"])
    cap = capsys.readouterr()
    assert code == 0
    assert json.loads(cap.out)["count"] == 1


def test_main_index_not_found_exit_1_in_process(monkeypatch, tmp_path, capsys):
    code = _call_main(
        monkeypatch,
        ["search_knowledge.py", "--index", str(tmp_path / "nope.json"), "--query", "x"],
    )
    cap = capsys.readouterr()
    assert code == 1
    assert "見つかりません" in json.loads(cap.err)["error"]


def test_main_auto_discovery_via_cwd_in_process(monkeypatch, tmp_path, capsys):
    # --index/--dir 無し → find_index(cwd) 経路
    _build_store(tmp_path)
    monkeypatch.chdir(tmp_path)
    code = _call_main(monkeypatch, ["search_knowledge.py", "--query", "効率"])
    cap = capsys.readouterr()
    assert code == 0
    assert json.loads(cap.out)["count"] == 1


def test_main_invalid_json_exit_1_in_process(monkeypatch, tmp_path, capsys):
    kdir = tmp_path / "knowledge"
    kdir.mkdir()
    (kdir / "knowledge-index.json").write_text("{ not valid json", encoding="utf-8")
    code = _call_main(
        monkeypatch,
        ["search_knowledge.py", "--index", str(kdir / "knowledge-index.json"), "--query", "x"],
    )
    cap = capsys.readouterr()
    assert code == 1
    assert "JSON解析失敗" in json.loads(cap.err)["error"]


def test_main_id_lookup_in_process(monkeypatch, tmp_path, capsys):
    idx = _build_store(tmp_path)
    code = _call_main(monkeypatch, ["search_knowledge.py", "--index", str(idx), "--id", "mindset_001"])
    cap = capsys.readouterr()
    assert code == 0
    out = json.loads(cap.out)
    assert out["count"] == 1
    assert out["results"][0]["score"] == 999
