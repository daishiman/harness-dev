#!/usr/bin/env python3
# /// script
# name: lint-knowledge-loop
# purpose: knowledge-loop capability の KL-001..007 (index/router 存在・必須6フィールド・検索/記録/追加スクリプト・分割閾値・consult_at とストア位置の一致) を検査する lint。--self-test では schema↔定数の drift 検出と lint↔CI 配線のメタ検査も行う
# inputs:
#   - argv: skill_dir / --strict / --store-only / --self-test
# outputs:
#   - stdout: findings JSON (status / error_count / warn_count)
#   - stderr: ディレクトリ不在の診断
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
# -*- coding: utf-8 -*-
"""
lint-knowledge-loop.py — knowledge-loop capability lint スクリプト

exit_code (Claude Code Hook 準拠):
  0 = 正常 (skip/warn を含む)
  1 = --strict モードで違反あり / 引数エラー

検査ルール:
  KL-001: knowledge/ ディレクトリ内に index.json または router.json が存在し、
          合計エントリ数が 3 件以上であること
  KL-002: 各エントリが必須6フィールド (id/title|content/intent|purpose/background/keywords|tags/source) を持つこと
  KL-003: search_knowledge.py が scripts/ に存在すること (決定論段)
  KL-004: record_usage.py が scripts/ に存在すること (活用ログ経路)
  KL-005: 分割閾値 (500行/25エントリ) に関する記述が
          SKILL.md または knowledge-construction.md に存在すること
  KL-006: add_entry.py が scripts/ に存在すること (日々の追加の機械化, warn)
  KL-007: ストアの宣言ファイル (knowledge-index.json または router.json) が
          consult_at を宣言し、値が {runtime, build-time} の部分集合で空でないこと。
          かつ物理位置と一致すること:
            - store_only=True (Loop B / メタ側)  → consult_at == ["build-time"]
            - store_only=False (Loop A / 生成側) → consult_at == ["runtime"]
          「ストアの所在 = Loop 種別」を機械的に強制し、置き場所の裁量と矛盾を CI で fail させる。

--self-test 内メタ検査:
  - schema↔定数 drift 検出: knowledge-loop.schema.json の KnowledgeEntry.required +
    anyOf 群 (title|content / intent|purpose / keywords|tags) と本 lint の必須
    フィールド定数 (REQUIRED_ENTRY_ALWAYS/TITLE/INTENT/KW) が集合一致するか検証
    (SSOT drift 防止)。schema 不在時はスキップ。
  - lint↔CI 配線検査: governance-check.yml に本 lint スクリプト名が配線されて
    いるか検証 (宣言と実装の乖離防止)。CI ファイル不在時はスキップ。

使用方法:
  python3 lint-knowledge-loop.py {skill_dir}
  python3 lint-knowledge-loop.py {skill_dir} --strict
  python3 lint-knowledge-loop.py --self-test
"""

import argparse
import json
import sys
from pathlib import Path


REQUIRED_ENTRY_TITLE = {"title", "content"}
REQUIRED_ENTRY_INTENT = {"intent", "purpose"}
REQUIRED_ENTRY_KW = {"keywords", "tags"}
REQUIRED_ENTRY_ALWAYS = {"id", "background", "source"}

SPLIT_THRESHOLD_KEYWORDS = ["500行", "25エントリ", "25件", "500 lines", "25 entries", "split", "分割"]

# consult_at が取り得る値 (= Loop 種別)。schema の enum と一致させる。
VALID_CONSULT_AT = {"runtime", "build-time"}
# 物理位置 (store_only) → 期待される consult_at の一意対応。
#   store_only=True  (Loop B / メタ側 = harness-creator 自身のストア) → build-time
#   store_only=False (Loop A / 生成スキルが自前に持つ knowledge/)   → runtime
EXPECTED_CONSULT_AT = {True: ["build-time"], False: ["runtime"]}


def find_knowledge_dir(skill_dir: Path) -> Path | None:
    p = skill_dir / "knowledge"
    return p if p.is_dir() else None


def load_json_safe(path: Path) -> tuple[dict | None, str | None]:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f), None
    except json.JSONDecodeError as e:
        return None, f"JSON解析失敗: {e}"
    except OSError as e:
        return None, f"ファイル読み込みエラー: {e}"


def collect_entries(knowledge_dir: Path) -> tuple[list[dict], list[str]]:
    """knowledge/ からすべてのエントリを収集する。"""
    entries = []
    errors = []

    for json_file in knowledge_dir.glob("*.json"):
        if json_file.name in ("knowledge-index.json", "router.json", "schema.json", "registry.json"):
            continue
        data, err = load_json_safe(json_file)
        if err:
            errors.append(f"{json_file.name}: {err}")
            continue
        if isinstance(data, dict) and "items" in data:
            items = data.get("items", [])
            if isinstance(items, list):
                entries.extend(items)
        elif isinstance(data, list):
            entries.extend(data)

    return entries, errors


def _extract_anyof_required(node: object) -> list[set[str]]:
    """schema ノードを再帰的に走査し、anyOf 群の required 集合を抽出する。

    KnowledgeEntry の allOf > anyOf > {required: [...]} 構造から
    {title|content}, {intent|purpose}, {keywords|tags} 相当の集合を取り出す。
    """
    groups: list[set[str]] = []
    if isinstance(node, dict):
        if "anyOf" in node and isinstance(node["anyOf"], list):
            grp: set[str] = set()
            for sub in node["anyOf"]:
                if isinstance(sub, dict) and isinstance(sub.get("required"), list):
                    grp.update(sub["required"])
            if grp:
                groups.append(grp)
        for v in node.values():
            groups.extend(_extract_anyof_required(v))
    elif isinstance(node, list):
        for v in node:
            groups.extend(_extract_anyof_required(v))
    return groups


def check_schema_drift() -> None:
    """schema↔定数 drift 検出 (self-test 専用)。

    knowledge-loop.schema.json の KnowledgeEntry から必須フィールド集合を抽出し、
    本 lint の定数 (REQUIRED_ENTRY_ALWAYS/TITLE/INTENT/KW) と集合一致するか検証する。
    schema が見つからない場合はスキップ (ハードクラッシュさせない)。
    """
    schema_path = Path(__file__).parent.parent / "schemas" / "knowledge-loop.schema.json"
    if not schema_path.exists():
        print(f"  [drift検査] スキップ: schema が見つからない ({schema_path})")
        return

    data, err = load_json_safe(schema_path)
    if err or not isinstance(data, dict):
        print(f"  [drift検査] スキップ: schema 読み込み失敗 ({err})")
        return

    entry = data.get("definitions", {}).get("KnowledgeEntry", {})
    schema_always = set(entry.get("required", []))
    anyof_groups = _extract_anyof_required(entry)

    # lint 側の anyOf 相当の3群 (集合で比較するため順不同)
    lint_anyof = [REQUIRED_ENTRY_TITLE, REQUIRED_ENTRY_INTENT, REQUIRED_ENTRY_KW]

    # 1) required (常時必須) の集合一致
    assert schema_always == REQUIRED_ENTRY_ALWAYS, (
        f"schema↔定数 drift: KnowledgeEntry.required={sorted(schema_always)} だが "
        f"REQUIRED_ENTRY_ALWAYS={sorted(REQUIRED_ENTRY_ALWAYS)} (集合不一致)。"
        "schema を正本に定数を更新せよ。"
    )

    # 2) anyOf 群の集合一致 (群の集合同士を比較)
    schema_anyof_sorted = sorted([tuple(sorted(g)) for g in anyof_groups])
    lint_anyof_sorted = sorted([tuple(sorted(g)) for g in lint_anyof])
    assert schema_anyof_sorted == lint_anyof_sorted, (
        f"schema↔定数 drift: KnowledgeEntry の anyOf 群={schema_anyof_sorted} だが "
        f"lint 定数 (TITLE/INTENT/KW)={lint_anyof_sorted} (不一致)。"
        "schema を正本に定数を更新せよ。"
    )

    print(f"  [drift検査] PASS: required={sorted(schema_always)} / anyOf群={schema_anyof_sorted} が schema と一致")


def check_ci_wiring() -> None:
    """lint↔CI 配線メタ検査 (self-test 専用)。

    governance-check.yml に本 lint スクリプト名が配線されているか検証する。
    CI ファイルが見つからない場合はスキップ (テンプレ展開先など)。
    """
    # scripts/ → skills/run-build-skill → run-build-skill → harness-creator → plugins → repo root
    repo_root = Path(__file__).resolve().parents[5]
    ci_path = repo_root / ".github" / "workflows" / "governance-check.yml"
    if not ci_path.exists():
        print(f"  [CI配線検査] スキップ: CI ファイルが見つからない ({ci_path})")
        return

    try:
        text = ci_path.read_text(encoding="utf-8")
    except OSError as e:
        print(f"  [CI配線検査] スキップ: CI ファイル読み込み失敗 ({e})")
        return

    script_name = Path(__file__).name  # lint-knowledge-loop.py
    assert script_name in text, (
        f"lint↔CI 乖離: {script_name} が {ci_path} に配線されていない。"
        "governance-check.yml に self-test ステップを追加せよ。"
    )
    print(f"  [CI配線検査] PASS: {script_name} が governance-check.yml に配線済み")


def check_kl001(knowledge_dir: Path) -> list[dict]:
    """KL-001: index|router 存在 + >=3エントリ。"""
    findings = []
    index_path = knowledge_dir / "knowledge-index.json"
    router_path = knowledge_dir / "router.json"

    if not index_path.exists() and not router_path.exists():
        findings.append({
            "rule": "KL-001",
            "severity": "error",
            "message": "knowledge/ に knowledge-index.json または router.json が見つからない"
        })
        return findings

    entries, _ = collect_entries(knowledge_dir)

    # index/router 自体のエントリは除き、データファイルのみカウント
    if len(entries) < 3:
        findings.append({
            "rule": "KL-001",
            "severity": "error",
            "message": f"エントリ数が3件未満: {len(entries)} 件 (最低3件必要)"
        })

    return findings


def check_kl002(knowledge_dir: Path) -> list[dict]:
    """KL-002: 各エントリが必須6フィールドを持つ。"""
    findings = []
    entries, errors = collect_entries(knowledge_dir)

    for err in errors:
        findings.append({"rule": "KL-002", "severity": "error", "message": err})

    for item in entries:
        if not isinstance(item, dict):
            continue
        item_id = item.get("id", "NO_ID")

        if not REQUIRED_ENTRY_ALWAYS.issubset(item.keys()):
            missing = REQUIRED_ENTRY_ALWAYS - set(item.keys())
            findings.append({
                "rule": "KL-002",
                "severity": "error",
                "message": f"[{item_id}] 必須フィールドがない: {sorted(missing)}"
            })

        if not REQUIRED_ENTRY_TITLE.intersection(item.keys()):
            findings.append({
                "rule": "KL-002",
                "severity": "error",
                "message": f"[{item_id}] title または content がない"
            })

        if not REQUIRED_ENTRY_INTENT.intersection(item.keys()):
            findings.append({
                "rule": "KL-002",
                "severity": "error",
                "message": f"[{item_id}] intent または purpose がない"
            })

        if not REQUIRED_ENTRY_KW.intersection(item.keys()):
            findings.append({
                "rule": "KL-002",
                "severity": "error",
                "message": f"[{item_id}] keywords または tags がない"
            })

    return findings


def check_kl003(skill_dir: Path) -> list[dict]:
    """KL-003: search_knowledge.py が scripts/ に存在する。"""
    scripts_dir = skill_dir / "scripts"
    target = scripts_dir / "search_knowledge.py"
    if not target.exists():
        return [{
            "rule": "KL-003",
            "severity": "error",
            "message": f"search_knowledge.py が見つからない (期待パス: {target.relative_to(skill_dir)})"
        }]
    return []


def check_kl004(skill_dir: Path) -> list[dict]:
    """KL-004: record_usage.py が scripts/ に存在する。"""
    scripts_dir = skill_dir / "scripts"
    target = scripts_dir / "record_usage.py"
    if not target.exists():
        return [{
            "rule": "KL-004",
            "severity": "error",
            "message": f"record_usage.py が見つからない (期待パス: {target.relative_to(skill_dir)})"
        }]
    return []


def check_kl006(skill_dir: Path) -> list[dict]:
    """KL-006: add_entry.py が scripts/ に存在する (日々の追加の機械化, warn)。"""
    scripts_dir = skill_dir / "scripts"
    target = scripts_dir / "add_entry.py"
    if not target.exists():
        return [{
            "rule": "KL-006",
            "severity": "warn",
            "message": f"add_entry.py が見つからない (日々の追加の機械化を推奨。期待パス: {target.relative_to(skill_dir)})"
        }]
    return []


def check_kl005(skill_dir: Path, knowledge_dir: Path) -> list[dict]:
    """KL-005: 分割閾値の記述/設定が存在する。"""
    # 1) ドキュメントに閾値記述があるか
    check_paths = [
        skill_dir / "SKILL.md",
        skill_dir / "references" / "knowledge-construction.md",
        skill_dir / "references" / "knowledge-search-lifecycle.md",
        knowledge_dir / "README.md",
    ]
    for path in check_paths:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        if any(kw in text for kw in SPLIT_THRESHOLD_KEYWORDS):
            return []

    # 2) knowledge-index.json の lifecycle に閾値設定があるか (store のメタデータ)
    index_path = knowledge_dir / "knowledge-index.json"
    if index_path.exists():
        data, _ = load_json_safe(index_path)
        if isinstance(data, dict):
            lc = data.get("lifecycle")
            if isinstance(lc, dict) and ("split_threshold_lines" in lc or "split_threshold_entries" in lc):
                return []

    return [{
        "rule": "KL-005",
        "severity": "warn",
        "message": "分割閾値 (500行/25エントリ) の記述/設定が SKILL.md・references・knowledge/README.md・index.lifecycle のいずれにも見つからない"
    }]


def check_kl007(knowledge_dir: Path, store_only: bool) -> list[dict]:
    """KL-007: consult_at の宣言・妥当性・物理位置一致を検査する。

    ストアの宣言ファイル (knowledge-index.json があればそれ、無ければ router.json) から
    consult_at を読み、以下を error として検出する:
      1. 宣言ファイルが無い / consult_at が不在 or 空
      2. 値が {runtime, build-time} 以外を含む
      3. 物理位置 (store_only) と consult_at が不一致
         (Loop B=build-time / Loop A=runtime の一意対応に違反)
    「ストアの所在 = Loop 種別」を機械的に固定し、置き場所の裁量と矛盾を排除する。
    """
    findings: list[dict] = []
    index_path = knowledge_dir / "knowledge-index.json"
    router_path = knowledge_dir / "router.json"

    decl_path = index_path if index_path.exists() else (router_path if router_path.exists() else None)
    if decl_path is None:
        # KL-001 が宣言ファイル不在を error 済み。consult_at 検査は対象なしでスキップ。
        return findings

    data, err = load_json_safe(decl_path)
    if err or not isinstance(data, dict):
        findings.append({
            "rule": "KL-007",
            "severity": "error",
            "message": f"{decl_path.name}: consult_at を読むための JSON 解析に失敗 ({err})"
        })
        return findings

    consult_at = data.get("consult_at")
    if consult_at is None or (isinstance(consult_at, list) and len(consult_at) == 0):
        findings.append({
            "rule": "KL-007",
            "severity": "error",
            "message": (
                f"{decl_path.name}: consult_at が未宣言または空。"
                "ストアの所在 = Loop 種別を一意に固定するため、Loop A は [\"runtime\"]、"
                "Loop B は [\"build-time\"] を必ず宣言してください"
            )
        })
        return findings

    if not isinstance(consult_at, list):
        findings.append({
            "rule": "KL-007",
            "severity": "error",
            "message": f"{decl_path.name}: consult_at は配列である必要があります (現在値: {consult_at!r})"
        })
        return findings

    invalid = [v for v in consult_at if v not in VALID_CONSULT_AT]
    if invalid:
        findings.append({
            "rule": "KL-007",
            "severity": "error",
            "message": (
                f"{decl_path.name}: consult_at に不正な値 {invalid} が含まれます。"
                f"許可値は {sorted(VALID_CONSULT_AT)} のみです"
            )
        })
        return findings

    # 物理位置との一致検査
    expected = EXPECTED_CONSULT_AT[store_only]
    if consult_at != expected:
        if store_only:
            reason = "Loop B (--store-only) のストアは build-time でなければなりません"
        else:
            reason = "生成スキルの knowledge/ (Loop A) は runtime でなければなりません"
        findings.append({
            "rule": "KL-007",
            "severity": "error",
            "message": (
                f"{decl_path.name}: consult_at={consult_at} が物理位置と不一致。"
                f"期待値={expected}。{reason}"
            )
        })

    return findings


def run_lint(skill_dir: Path, strict: bool, store_only: bool = False) -> dict:
    """全ルールを実行してfindings辞書を返す。

    store_only=True: 検索/記録スクリプトを自前に持たず、正本テンプレ
      (templates/knowledge-skeleton/scripts/) を --dir 指定で共有するストア
      (例: harness-creator 自身の Loop B)。KL-003/KL-004 は SSOT 維持のため
      情報通知に格下げし error にしない。
    """
    knowledge_dir = find_knowledge_dir(skill_dir)

    if knowledge_dir is None:
        # knowledge/ がない場合はスキップ
        return {
            "skill_dir": str(skill_dir),
            "status": "skip",
            "message": "knowledge/ ディレクトリが存在しないためスキップ",
            "findings": []
        }

    findings = []
    findings.extend(check_kl001(knowledge_dir))
    findings.extend(check_kl002(knowledge_dir))
    if store_only:
        findings.append({
            "rule": "KL-003/004/006",
            "severity": "info",
            "message": "store-only: 検索/記録/追加スクリプトは正本テンプレを --dir 共有 (自前複製なし = SSOT)"
        })
    else:
        findings.extend(check_kl003(skill_dir))
        findings.extend(check_kl004(skill_dir))
        findings.extend(check_kl006(skill_dir))
    findings.extend(check_kl005(skill_dir, knowledge_dir))
    findings.extend(check_kl007(knowledge_dir, store_only))

    errors = [f for f in findings if f["severity"] == "error"]
    warnings = [f for f in findings if f["severity"] == "warn"]

    status = "pass"
    if errors:
        status = "fail" if strict else "warn"
    elif warnings:
        status = "warn"

    return {
        "skill_dir": str(skill_dir),
        "status": status,
        "error_count": len(errors),
        "warn_count": len(warnings),
        "findings": findings
    }


def self_test() -> None:
    """内蔵 OK例/NG例 で全ルールを検証する。

    KL-001..006 の検出/格下げに加え、schema↔定数 drift 検出と
    lint↔CI 配線のメタ検査も行う (SSOT/乖離の再発防止)。
    """
    import tempfile

    # --- メタ検査: schema↔定数 drift / lint↔CI 配線 ---
    check_schema_drift()
    check_ci_wiring()

    with tempfile.TemporaryDirectory() as tmpdir:
        skill_dir = Path(tmpdir)

        # --- NG例: knowledge/ がない → skip ---
        result = run_lint(skill_dir, strict=False)
        assert result["status"] == "skip", f"knowledge/ なしで skip にならない: {result}"

        # --- knowledge/ を作成 ---
        kdir = skill_dir / "knowledge"
        kdir.mkdir()
        scripts_dir = skill_dir / "scripts"
        scripts_dir.mkdir()

        # KL-001 NG: index も router もない
        result = run_lint(skill_dir, strict=False)
        kl001_findings = [f for f in result["findings"] if f["rule"] == "KL-001"]
        assert any("knowledge-index.json" in f["message"] for f in kl001_findings), \
            f"KL-001 が検出されない: {kl001_findings}"

        # index を作成
        index_data = {
            "version": "1.0.0",
            "consult_at": ["runtime"],
            "categories": [{"id": "test", "label": "テスト", "file": "knowledge-test.json", "keywords": []}],
            "global_keywords": {}
        }
        (kdir / "knowledge-index.json").write_text(json.dumps(index_data), encoding="utf-8")

        # KL-001 NG: エントリ3件未満
        cat_data = {"category": "test", "label": "テスト", "version": "1.0.0", "items": [
            {"id": "t_001", "title": "タイトル1", "intent": "意図1", "background": "背景1",
             "keywords": ["kw1"], "source": "test.md"},
            {"id": "t_002", "title": "タイトル2", "intent": "意図2", "background": "背景2",
             "keywords": ["kw2"], "source": "test.md"},
        ]}
        (kdir / "knowledge-test.json").write_text(json.dumps(cat_data), encoding="utf-8")
        result = run_lint(skill_dir, strict=False)
        kl001_findings = [f for f in result["findings"] if f["rule"] == "KL-001"]
        assert any("3件未満" in f["message"] for f in kl001_findings), \
            f"KL-001 エントリ不足が検出されない: {kl001_findings}"

        # 3件目追加
        cat_data["items"].append({
            "id": "t_003", "title": "タイトル3", "intent": "意図3", "background": "背景3",
            "keywords": ["kw3"], "source": "test.md"
        })
        (kdir / "knowledge-test.json").write_text(json.dumps(cat_data), encoding="utf-8")

        # KL-003/KL-004 NG: スクリプトがない / KL-006 warn: add_entry.py がない
        result = run_lint(skill_dir, strict=False)
        kl003 = [f for f in result["findings"] if f["rule"] == "KL-003"]
        kl004 = [f for f in result["findings"] if f["rule"] == "KL-004"]
        kl006 = [f for f in result["findings"] if f["rule"] == "KL-006"]
        assert len(kl003) > 0, f"KL-003 が検出されない"
        assert len(kl004) > 0, f"KL-004 が検出されない"
        assert len(kl006) > 0 and kl006[0]["severity"] == "warn", \
            f"KL-006 が warn で検出されない: {kl006}"

        # スクリプトを作成 (add_entry.py も含む)
        (scripts_dir / "search_knowledge.py").write_text("# stub", encoding="utf-8")
        (scripts_dir / "record_usage.py").write_text("# stub", encoding="utf-8")
        (scripts_dir / "add_entry.py").write_text("# stub", encoding="utf-8")

        # KL-006 解消確認: add_entry.py 存在で検出なし
        result = run_lint(skill_dir, strict=False)
        kl006 = [f for f in result["findings"] if f["rule"] == "KL-006"]
        assert len(kl006) == 0, f"add_entry.py 存在時に KL-006 が残存: {kl006}"

        # KL-005: 分割閾値の記述なし
        result = run_lint(skill_dir, strict=False)
        kl005 = [f for f in result["findings"] if f["rule"] == "KL-005"]
        assert len(kl005) > 0, f"KL-005 が検出されない"

        # SKILL.md に分割閾値を記述
        (skill_dir / "SKILL.md").write_text("# テスト\n\n分割閾値: 500行/25エントリ", encoding="utf-8")

        # OK例: 全ルール PASS
        result = run_lint(skill_dir, strict=False)
        errors = [f for f in result["findings"] if f["severity"] == "error"]
        assert len(errors) == 0, f"OK例でエラーが残存: {errors}"

        # --strict モードのテスト
        (scripts_dir / "search_knowledge.py").unlink()
        result_strict = run_lint(skill_dir, strict=True)
        assert result_strict["status"] == "fail", f"--strict モードで fail にならない: {result_strict}"

        result_non_strict = run_lint(skill_dir, strict=False)
        assert result_non_strict["status"] in ("warn", "pass"), \
            f"非 strict モードで warn/pass にならない: {result_non_strict}"

        # --- store-only モード: scripts が無くても KL-003/004 を error にしない ---
        # scripts/ を空にし、index に lifecycle 閾値を入れる
        for f in scripts_dir.glob("*.py"):
            f.unlink()
        index_data["lifecycle"] = {"split_threshold_lines": 500, "split_threshold_entries": 25}
        # store-only (Loop B) では consult_at は build-time でなければ KL-007 で fail する
        index_data["consult_at"] = ["build-time"]
        (kdir / "knowledge-index.json").write_text(json.dumps(index_data), encoding="utf-8")
        result_store = run_lint(skill_dir, strict=True, store_only=True)
        kl_scripts = [f for f in result_store["findings"]
                      if f["rule"].startswith("KL-003") or f["rule"] == "KL-004"
                      or "006" in f["rule"]]
        assert all(f["severity"] != "error" for f in kl_scripts), \
            f"store-only で KL-003/004/006 が error: {kl_scripts}"
        # store-only では検索/記録/追加スクリプトを info に集約 (KL-006 個別 warn を出さない)
        assert not [f for f in result_store["findings"] if f["rule"] == "KL-006"], \
            f"store-only で KL-006 個別 finding が残存: {result_store['findings']}"
        assert result_store["status"] == "pass", \
            f"store-only + lifecycle閾値 で pass にならない: {result_store}"
        # store-only (build-time) で KL-007 が pass することを明示確認
        kl007_store = [f for f in result_store["findings"] if f["rule"] == "KL-007"]
        assert len(kl007_store) == 0, \
            f"store-only + consult_at=[build-time] で KL-007 が残存: {kl007_store}"

    # --- KL-007: consult_at の宣言/妥当性/物理位置一致を専用ケースで検証 ---
    with tempfile.TemporaryDirectory() as tmpdir:
        skill_dir = Path(tmpdir)
        kdir = skill_dir / "knowledge"
        kdir.mkdir()
        scripts_dir = skill_dir / "scripts"
        scripts_dir.mkdir()
        for name in ("search_knowledge.py", "record_usage.py", "add_entry.py"):
            (scripts_dir / name).write_text("# stub", encoding="utf-8")
        (skill_dir / "SKILL.md").write_text("分割閾値: 500行/25エントリ", encoding="utf-8")

        base_index = {
            "version": "1.0.0",
            "categories": [{"id": "test", "label": "テスト", "file": "knowledge-test.json", "keywords": []}],
            "global_keywords": {},
        }
        cat = {"category": "test", "label": "テスト", "version": "1.0.0", "items": [
            {"id": f"t_{i:03d}", "title": f"タイトル{i}", "intent": f"意図{i}", "background": f"背景{i}",
             "keywords": [f"kw{i}"], "source": "test.md"} for i in range(1, 4)
        ]}
        (kdir / "knowledge-test.json").write_text(json.dumps(cat), encoding="utf-8")

        def write_index(extra: dict) -> None:
            (kdir / "knowledge-index.json").write_text(
                json.dumps({**base_index, **extra}), encoding="utf-8")

        # ケース1: consult_at 未宣言 → KL-007 error
        write_index({})
        r = run_lint(skill_dir, strict=False, store_only=False)
        k7 = [f for f in r["findings"] if f["rule"] == "KL-007"]
        assert k7 and "未宣言" in k7[0]["message"], f"consult_at 未宣言が KL-007 で検出されない: {k7}"

        # ケース2: 生成スキル (store_only=False) で consult_at=["build-time"] → mismatch error
        write_index({"consult_at": ["build-time"]})
        r = run_lint(skill_dir, strict=False, store_only=False)
        k7 = [f for f in r["findings"] if f["rule"] == "KL-007"]
        assert k7 and "不一致" in k7[0]["message"], f"Loop A の build-time mismatch が検出されない: {k7}"

        # ケース3: store_only=True で consult_at=["build-time"] → pass
        write_index({"consult_at": ["build-time"]})
        r = run_lint(skill_dir, strict=False, store_only=True)
        k7 = [f for f in r["findings"] if f["rule"] == "KL-007"]
        assert len(k7) == 0, f"Loop B の build-time が KL-007 で誤検出: {k7}"

        # ケース4: store_only=False で consult_at=["runtime"] → pass
        write_index({"consult_at": ["runtime"]})
        r = run_lint(skill_dir, strict=False, store_only=False)
        k7 = [f for f in r["findings"] if f["rule"] == "KL-007"]
        assert len(k7) == 0, f"Loop A の runtime が KL-007 で誤検出: {k7}"

        # ケース5: 不正値 → error
        write_index({"consult_at": ["sometime"]})
        r = run_lint(skill_dir, strict=False, store_only=False)
        k7 = [f for f in r["findings"] if f["rule"] == "KL-007"]
        assert k7 and "不正な値" in k7[0]["message"], f"consult_at 不正値が検出されない: {k7}"

    print("--self-test: PASS (全テスト通過)")


def main() -> None:
    parser = argparse.ArgumentParser(description="knowledge-loop capability lint")
    parser.add_argument("skill_dir", nargs="?", help="スキルディレクトリパス")
    parser.add_argument("--strict", action="store_true", help="error 時に exit 1 を返す")
    parser.add_argument("--store-only", dest="store_only", action="store_true",
                        help="検索/記録スクリプトを正本テンプレに --dir 共有するストア (Loop B 等)。KL-003/004 を情報通知に格下げ")
    parser.add_argument("--self-test", action="store_true", help="内蔵テストを実行して exit")

    args = parser.parse_args()

    if args.self_test:
        self_test()
        sys.exit(0)

    if not args.skill_dir:
        parser.error("skill_dir を指定してください")

    skill_dir = Path(args.skill_dir).resolve()
    if not skill_dir.is_dir():
        print(json.dumps({"error": f"ディレクトリが存在しない: {skill_dir}"}), file=sys.stderr)
        sys.exit(1)

    result = run_lint(skill_dir, args.strict, store_only=args.store_only)
    print(json.dumps(result, ensure_ascii=False, indent=2))

    if result["status"] == "fail":
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
