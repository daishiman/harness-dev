#!/usr/bin/env python3
# /// script
# name: add_entry
# purpose: knowledge/ に新規エントリを安全に追加する決定論スクリプト (Loop A の「日々の追加」入口)。必須6フィールド検証・ID重複検査・カテゴリ/index 自動登録までを担い、本文の良し悪しは判定しない (二層分離)
# inputs:
#   - argv: --category / --id / --title / --intent / --background / --keywords / --source / --json / --file / --index / --dir / --consult-at / --self-test
# outputs:
#   - stdout: 追加結果 JSON (added + entry_id + category + counts)
#   - stderr: 必須フィールド欠落 / ID重複 / IO失敗の診断
# contexts: [C, E]
# network: false
# write-scope: knowledge/knowledge-<category>.json, knowledge/knowledge-index.json
# dependencies: []
# requires-python: ">=3.10"
# ///
# -*- coding: utf-8 -*-
"""
add_entry.py — knowledge/ 新規エントリ追加スクリプト (Loop A 追加入口)

exit_code:
  0 = 正常 (keywords 5語未満などの warn があっても 0)
  1 = 引数エラー / 必須フィールド欠落 / ID重複 / JSON解析失敗 / IO失敗

二層分離:
  本スクリプトは「検証・追記・登録」という決定論部分のみを担う。
  background の数値2つ等の品質ルーブリックの中身の良し悪しは判定しない (AI の自由度に残す)。

使用方法:
  # CLI 引数で追加 (index-search 型: knowledge-<category>.json)
  python3 add_entry.py --category mindset --id mindset_010 \\
      --title "..." --intent "..." --background "..." \\
      --keywords "kw1,kw2,kw3,kw4,kw5" --source "interview-2026.md"

  # JSON ファイル / 標準入力で追加
  python3 add_entry.py --category mindset --json entry.json
  cat entry.json | python3 add_entry.py --category mindset --json -

  # router 型: カテゴリファイルを直接指定して追記
  python3 add_entry.py --file knowledge-routing-a.json --json entry.json

  # Loop B ストアへ追加
  python3 add_entry.py --dir /path/to/store --category mindset --json entry.json

  python3 add_entry.py --self-test
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path


# 必須6フィールド (択一を含む)。search_knowledge / build_index の規約と一致させる。
REQUIRED_TITLE = ("title", "content")
REQUIRED_INTENT = ("intent", "purpose")
REQUIRED_KEYWORDS = ("keywords", "tags")
MIN_KEYWORDS_WARN = 5


def find_index(start_dir: Path) -> Path | None:
    """カレントまたは親ディレクトリから knowledge-index.json を探す。"""
    for d in [start_dir] + list(start_dir.parents):
        p = d / "knowledge" / "knowledge-index.json"
        if p.exists():
            return p
        p2 = d / "knowledge-index.json"
        if p2.exists():
            return p2
    return None


def resolve_index_path(index_arg: str | None, dir_arg: str | None) -> Path | None:
    """明示 --index > --dir > 自動探索 (cwd) の段階フォールバックで index パスを解決する。"""
    if index_arg:
        return Path(index_arg)
    if dir_arg:
        base = Path(dir_arg)
        cand = base / "knowledge-index.json"
        return cand if cand.exists() else base / "knowledge" / "knowledge-index.json"
    return find_index(Path.cwd())


def read_store_consult_at(index_path: Path) -> list | None:
    """対象ストアの宣言ファイルから consult_at を読む。

    index-search 型は knowledge-index.json、router 型は同階層の router.json を見る。
    宣言ファイルが無い / consult_at 不在の場合は None を返す。
    """
    knowledge_dir = index_path.parent
    for decl_name in ("knowledge-index.json", "router.json"):
        decl = knowledge_dir / decl_name
        if not decl.exists():
            continue
        try:
            data = json.loads(decl.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if isinstance(data, dict) and "consult_at" in data:
            return data["consult_at"]
    return None


def guard_consult_at(index_path: Path, requested: str | None) -> None:
    """書き込み前ガード: ストアの consult_at と --consult-at の整合を検査する。

    KL-007 (ストアの所在 = Loop 種別) を add_entry の入口でも強制し、
    不正ストアや種別取り違えへの追記を物理的に拒否する。
      - --consult-at 未指定: ストアが consult_at を宣言していなければ拒否
        (KL-007 違反ストアには追加させない)。宣言済みなら追加を許可。
      - --consult-at 指定: ストア宣言値と一致しなければ拒否。
    """
    store_consult_at = read_store_consult_at(index_path)

    if store_consult_at is None:
        raise ValueError(
            "ストアが consult_at を宣言していない。"
            "ストアの所在 = Loop 種別を固定するため、KL-007 違反のストアには追加できません "
            "(knowledge-index.json / router.json に consult_at: [\"runtime\"] または "
            "[\"build-time\"] を宣言してください)"
        )

    if requested is not None and requested not in (store_consult_at or []):
        raise ValueError(
            f"このストアは {store_consult_at} 用。--consult-at {requested} と矛盾するため追加を拒否します"
        )


def validate_entry(entry: dict) -> tuple[list[str], list[str]]:
    """必須6フィールド (択一考慮) を決定論チェックする。

    returns: (errors, warnings)
    内容の良し悪しは判定しない。keywords が少ない場合のみ warn。
    """
    errors: list[str] = []
    warnings: list[str] = []

    if not entry.get("id"):
        errors.append("id フィールドがない (または空)")
    if not any(entry.get(k) for k in REQUIRED_TITLE):
        errors.append("title または content フィールドがない")
    if not any(entry.get(k) for k in REQUIRED_INTENT):
        errors.append("intent または purpose フィールドがない")
    if not entry.get("background"):
        errors.append("background フィールドがない")
    kw = None
    for k in REQUIRED_KEYWORDS:
        if entry.get(k):
            kw = entry.get(k)
            break
    if kw is None:
        errors.append("keywords または tags フィールドがない")
    if not entry.get("source"):
        errors.append("source フィールドがない")

    # 軽い注意 (エラーにはしない)
    if kw is not None:
        kw_list = kw if isinstance(kw, list) else [k.strip() for k in str(kw).split(",") if k.strip()]
        if len(kw_list) < MIN_KEYWORDS_WARN:
            warnings.append(
                f"keywords が {len(kw_list)} 語です (推奨 {MIN_KEYWORDS_WARN} 語以上)。"
                "検索ヒット率向上のため追加を検討してください"
            )

    return errors, warnings


def normalize_keywords(value) -> list[str]:
    """keywords を文字列 (カンマ区切り) でもリストでも受け取り list[str] に正規化する。"""
    if value is None:
        return []
    if isinstance(value, list):
        return [str(k).strip() for k in value if str(k).strip()]
    return [k.strip() for k in str(value).split(",") if k.strip()]


def build_entry_from_args(args) -> dict:
    """CLI 引数からエントリ dict を組み立てる (--json 未指定時)。"""
    entry: dict = {}
    if args.id:
        entry["id"] = args.id
    if args.title:
        entry["title"] = args.title
    if args.intent:
        entry["intent"] = args.intent
    if args.background:
        entry["background"] = args.background
    if args.keywords:
        entry["keywords"] = normalize_keywords(args.keywords)
    if args.source:
        # source は文字列なら {"file": ...} に包む (search_knowledge は dict/str どちらも許容)
        entry["source"] = {"file": args.source} if isinstance(args.source, str) else args.source
    return entry


def load_entry_from_json(json_arg: str) -> dict:
    """--json <path> または --json - (stdin) からエントリ dict を読み込む。"""
    if json_arg == "-":
        raw = sys.stdin.read()
    else:
        raw = Path(json_arg).read_text(encoding="utf-8")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("--json は単一エントリの JSON オブジェクトである必要があります")
    # keywords/tags が文字列なら正規化
    for k in REQUIRED_KEYWORDS:
        if isinstance(data.get(k), str):
            data[k] = normalize_keywords(data[k])
    return data


def collect_existing_ids(index_path: Path) -> set[str]:
    """index に登録された全カテゴリファイルから既存 ID を収集する。"""
    ids: set[str] = set()
    if not index_path.exists():
        return ids
    index = json.loads(index_path.read_text(encoding="utf-8"))
    knowledge_dir = index_path.parent
    for cat in index.get("categories", []):
        cat_path = knowledge_dir / cat.get("file", "")
        if not cat_path.exists():
            continue
        try:
            data = json.loads(cat_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        for item in data.get("items", []):
            if item.get("id"):
                ids.add(item["id"])
    return ids


def collect_ids_in_file(cat_path: Path) -> set[str]:
    """単一カテゴリファイル内の既存 ID を収集する (router 型 --file 用)。"""
    ids: set[str] = set()
    if not cat_path.exists():
        return ids
    data = json.loads(cat_path.read_text(encoding="utf-8"))
    for item in data.get("items", []):
        if item.get("id"):
            ids.add(item["id"])
    return ids


def append_to_category_file(cat_path: Path, entry: dict, category_id: str | None,
                            label: str | None) -> int:
    """カテゴリファイルの items[] に追記する。無ければ作成する。追記後の件数を返す。"""
    if cat_path.exists():
        data = json.loads(cat_path.read_text(encoding="utf-8"))
        if "items" not in data or not isinstance(data["items"], list):
            data["items"] = []
    else:
        data = {
            "category": category_id or cat_path.stem.replace("knowledge-", ""),
            "label": label or (category_id or cat_path.stem),
            "version": "1.0.0",
            "created_at": date.today().isoformat(),
            "items": [],
        }
    data["items"].append(entry)
    cat_path.parent.mkdir(parents=True, exist_ok=True)
    cat_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return len(data["items"])


def register_category_in_index(index_path: Path, category_id: str, cat_filename: str,
                               label: str | None, keywords: list[str]) -> bool:
    """index の categories[] にカテゴリ未登録なら登録する。登録した場合 True。"""
    if index_path.exists():
        index = json.loads(index_path.read_text(encoding="utf-8"))
    else:
        index = {"version": "1.0.0", "categories": [], "global_keywords": {}, "synonyms": {}}
    categories = index.setdefault("categories", [])
    if any(c.get("id") == category_id or c.get("file") == cat_filename for c in categories):
        return False
    categories.append({
        "id": category_id,
        "label": label or category_id,
        "file": cat_filename,
        "keywords": keywords,
    })
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    return True


def category_counts(index_path: Path) -> dict:
    """index 経由で現在のカテゴリ別件数を集計する。"""
    counts: dict = {}
    if not index_path.exists():
        return counts
    index = json.loads(index_path.read_text(encoding="utf-8"))
    knowledge_dir = index_path.parent
    for cat in index.get("categories", []):
        cat_path = knowledge_dir / cat.get("file", "")
        if cat_path.exists():
            try:
                data = json.loads(cat_path.read_text(encoding="utf-8"))
                counts[cat.get("id")] = len(data.get("items", []))
            except json.JSONDecodeError:
                counts[cat.get("id")] = None
    return counts


def add_entry(index_path: Path, entry: dict, category_id: str | None,
              file_arg: str | None, label: str | None,
              consult_at: str | None = None) -> dict:
    """エントリ追加のオーケストレーション。ガード→検証→重複検査→追記→登録→件数集計。"""
    # 書き込み前ガード: ストアの consult_at (= Loop 種別) と整合しなければ拒否
    guard_consult_at(index_path, consult_at)

    errors, warnings = validate_entry(entry)
    if errors:
        raise ValueError("必須フィールド検証エラー:\n  - " + "\n  - ".join(errors))

    knowledge_dir = index_path.parent
    entry_id = entry["id"]

    if file_arg:
        # router 型: カテゴリファイル直指定。index は触らず当該ファイル内のみ重複検査。
        cat_path = (knowledge_dir / file_arg) if not Path(file_arg).is_absolute() else Path(file_arg)
        if entry_id in collect_ids_in_file(cat_path):
            raise ValueError(f"ID が重複しています: {entry_id} (file={cat_path.name})")
        count = append_to_category_file(cat_path, entry, category_id, label)
        return {
            "added": True,
            "entry_id": entry_id,
            "mode": "router-file",
            "file": cat_path.name,
            "file_item_count": count,
            "warnings": warnings,
        }

    # index-search 型: --category 必須。index 全体で重複検査。
    if not category_id:
        raise ValueError("--category または --file のいずれかを指定してください")
    if entry_id in collect_existing_ids(index_path):
        raise ValueError(f"ID が重複しています: {entry_id}")

    cat_filename = f"knowledge-{category_id}.json"
    cat_path = knowledge_dir / cat_filename
    kw = normalize_keywords(entry.get("keywords") or entry.get("tags"))
    registered = register_category_in_index(index_path, category_id, cat_filename, label, kw)
    count = append_to_category_file(cat_path, entry, category_id, label)

    return {
        "added": True,
        "entry_id": entry_id,
        "mode": "index-search",
        "category": category_id,
        "file": cat_filename,
        "category_registered": registered,
        "category_counts": category_counts(index_path),
        "warnings": warnings,
    }


def self_test() -> None:
    """tempfile で OK例/NG例を検証し、add_entry → search_knowledge の往復も確認する。"""
    import tempfile

    # テスト1: validate_entry が OK例を通す
    ok_entry = {
        "id": "t_001",
        "title": "テストタイトル",
        "intent": "テストを通すこと",
        "background": "tempfile 環境で 2 回実行し整合性を確認する背景。",
        "keywords": ["a", "b", "c", "d", "e"],
        "source": {"file": "t.md"},
    }
    errs, warns = validate_entry(ok_entry)
    assert errs == [], f"OK例でエラー: {errs}"
    assert warns == [], f"OK例で想定外 warn: {warns}"

    # テスト2: NG例 (必須欠落) を検出
    ng_entry = {"id": "t_002", "background": "背景のみ"}
    errs2, _ = validate_entry(ng_entry)
    assert len(errs2) >= 3, f"NG例でエラー検出不足: {errs2}"
    assert any("title" in e for e in errs2), f"title 欠落が検出されない: {errs2}"

    # テスト3: keywords 5語未満で warn (エラーにはしない)
    few_kw = {**ok_entry, "id": "t_003", "keywords": ["a", "b"]}
    errs3, warns3 = validate_entry(few_kw)
    assert errs3 == [], f"keywords 少でエラー化してしまった: {errs3}"
    assert len(warns3) >= 1, f"keywords 少で warn が出ない: {warns3}"

    # テスト4: 択一 (content/purpose/tags) でも通す
    alt_entry = {
        "id": "t_004",
        "content": "本文フィールド",
        "purpose": "目的フィールド",
        "background": "背景テキスト。数値 10 と 20 を含む。",
        "tags": ["x", "y", "z", "w", "v"],
        "source": "src.md",
    }
    errs4, _ = validate_entry(alt_entry)
    assert errs4 == [], f"択一フィールドでエラー: {errs4}"

    # テスト5: ファイルベース add_entry → 件数 + ID重複検出 + search 往復
    with tempfile.TemporaryDirectory() as tmpdir:
        kdir = Path(tmpdir) / "knowledge"
        kdir.mkdir()
        index_path = kdir / "knowledge-index.json"
        index_path.write_text(
            json.dumps({"version": "1.0.0", "consult_at": ["runtime"],
                        "categories": [], "global_keywords": {}, "synonyms": {}}),
            encoding="utf-8",
        )

        result = add_entry(index_path, dict(ok_entry), "mindset", None, "マインドセット")
        assert result["added"] is True, f"追加失敗: {result}"
        assert result["category_registered"] is True, f"カテゴリ未登録: {result}"
        assert result["category_counts"].get("mindset") == 1, f"件数不一致: {result}"

        # 同一 ID 再追加で重複検出
        dup_ok = False
        try:
            add_entry(index_path, dict(ok_entry), "mindset", None, "マインドセット")
        except ValueError as e:
            dup_ok = "重複" in str(e)
        assert dup_ok, "ID重複が検出されない"

        # search_knowledge で引けるか (往復確認)
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        try:
            import search_knowledge  # type: ignore
            results = search_knowledge.search(index_path, "テストタイトル", None, None, "t_001", 5)
            assert any(r["item"]["id"] == "t_001" for r in results), \
                f"add したエントリが search で引けない: {results}"
        except ImportError:
            pass  # search_knowledge.py が同階層に無い環境ではスキップ

        # テスト6: router 型 --file 直指定
        router_file = kdir / "knowledge-routing-a.json"
        r2 = add_entry(index_path, {**ok_entry, "id": "r_001"}, None,
                       "knowledge-routing-a.json", None)
        assert r2["mode"] == "router-file", f"router モードにならない: {r2}"
        assert r2["file_item_count"] == 1, f"router 件数不一致: {r2}"
        assert router_file.exists(), "router ファイルが作成されない"

    # テスト7: consult_at ガード (KL-007 を add_entry 入口で強制)
    with tempfile.TemporaryDirectory() as tmpdir:
        kdir = Path(tmpdir) / "knowledge"
        kdir.mkdir()
        idx = kdir / "knowledge-index.json"

        def write_store(extra: dict) -> None:
            idx.write_text(json.dumps({"version": "1.0.0", "categories": [],
                                       "global_keywords": {}, "synonyms": {}, **extra}),
                           encoding="utf-8")

        # 7a: ストアが consult_at 未宣言 → 追加拒否
        write_store({})
        rejected = False
        try:
            add_entry(idx, dict(ok_entry), "mindset", None, None)
        except ValueError as e:
            rejected = "consult_at を宣言していない" in str(e)
        assert rejected, "consult_at 未宣言ストアへの追加が拒否されない"

        # 7b: --consult-at がストア宣言と不一致 → 拒否
        write_store({"consult_at": ["runtime"]})
        mismatch = False
        try:
            add_entry(idx, dict(ok_entry), "mindset", None, None, consult_at="build-time")
        except ValueError as e:
            mismatch = "矛盾" in str(e)
        assert mismatch, "--consult-at 不一致が拒否されない"

        # 7c: --consult-at がストア宣言と一致 → 追加成功
        write_store({"consult_at": ["runtime"]})
        r = add_entry(idx, dict(ok_entry), "mindset", None, "マインドセット", consult_at="runtime")
        assert r["added"] is True, f"一致時に追加されない: {r}"

        # 7d: --consult-at 未指定でもストアが宣言済みなら追加成功
        write_store({"consult_at": ["build-time"]})
        r2 = add_entry(idx, {**ok_entry, "id": "t_010"}, "mindset", None, "マインドセット")
        assert r2["added"] is True, f"宣言済みストアへの未指定追加が失敗: {r2}"

    print("--self-test: PASS (全7テスト通過)")


def main() -> None:
    parser = argparse.ArgumentParser(description="knowledge/ 新規エントリ追加 (Loop A 追加入口)")
    parser.add_argument("--category", help="カテゴリID (index-search 型)。knowledge-<category>.json へ追記")
    parser.add_argument("--file", dest="file", help="カテゴリファイル名直指定 (router 型)。<dir>/knowledge/<file> へ追記")
    parser.add_argument("--id", help="エントリID")
    parser.add_argument("--title", help="タイトル (title|content の一方)")
    parser.add_argument("--intent", help="意図 (intent|purpose の一方)")
    parser.add_argument("--background", help="背景")
    parser.add_argument("--keywords", help="カンマ区切りキーワード (keywords|tags の一方)")
    parser.add_argument("--source", help="出典ファイル名等")
    parser.add_argument("--label", help="カテゴリ新規作成時のラベル (任意)")
    parser.add_argument("--json", dest="json_arg", help="エントリJSONのパス、または - で標準入力")
    parser.add_argument("--index", help="knowledge-index.json のパス (省略時は --dir / 自動探索)")
    parser.add_argument("--dir", dest="dir",
                        help="knowledge ストアのディレクトリ。<dir>/knowledge-index.json または "
                             "<dir>/knowledge/knowledge-index.json を解決 (Loop B / 別ストア用)")
    parser.add_argument("--consult-at", dest="consult_at", choices=["runtime", "build-time"],
                        help="追加先ストアの想定 Loop 種別 (任意)。指定時、ストア宣言の consult_at と "
                             "矛盾したら追加を拒否 (KL-007 を add_entry の入口で強制)")
    parser.add_argument("--self-test", action="store_true", help="内蔵テストを実行して exit")

    args = parser.parse_args()

    if args.self_test:
        self_test()
        sys.exit(0)

    # エントリ組み立て: --json 優先、なければ CLI 引数から
    try:
        if args.json_arg:
            entry = load_entry_from_json(args.json_arg)
        else:
            entry = build_entry_from_args(args)
    except (OSError, json.JSONDecodeError, ValueError) as e:
        print(json.dumps({"error": f"エントリ読み込み失敗: {e}"}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)

    if not entry:
        parser.error("エントリ内容を --json または各フィールド引数で指定してください")

    index_path = resolve_index_path(args.index, args.dir)
    if not index_path:
        print(json.dumps({"error": "knowledge-index.json が見つかりません (--index/--dir を指定してください)"},
                         ensure_ascii=False), file=sys.stderr)
        sys.exit(1)

    try:
        result = add_entry(index_path, entry, args.category, args.file, args.label, args.consult_at)
    except ValueError as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)
    except (OSError, json.JSONDecodeError) as e:
        print(json.dumps({"error": f"IO/JSON 失敗: {e}"}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
