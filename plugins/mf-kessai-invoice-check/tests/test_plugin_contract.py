#!/usr/bin/env python3
"""mf-kessai-invoice-check plugin package contract regression tests."""
import ast
import json
import os
import stat
import sys


PLUGIN_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# 本番ランタイムが置かれるディレクトリ (テスト/開発専用の tests/ は含めない)。
RUNTIME_DIRS = [
    "lib",
    "hooks",
    "scripts",
    "skills/run-mf-invoice-check/scripts",
    "skills/run-mf-invoice-db-setup/scripts",
    "skills/run-mf-initial-month-enrich/scripts",
]


def _json(rel_path):
    with open(os.path.join(PLUGIN_ROOT, rel_path), encoding="utf-8") as f:
        return json.load(f)


def test_plugin_manifest_bundle_contract():
    manifest = _json(".claude-plugin/plugin.json")
    assert manifest["name"] == "mf-kessai-invoice-check"
    assert manifest["package_mode"] == "bundle"
    assert manifest["entry_points"]["skills"] == [
        "run-mf-invoice-check",
        "run-mf-invoice-db-setup",
        "ref-mf-kessai-api",
        "run-mf-initial-month-enrich",
        "run-mf-invoice-reconcile",
        "run-mf-invoice-report",
    ]
    assert manifest["entry_points"]["agents"] == [
        "mfk-gap-verifier", "mfk-reconcile-verifier", "mfk-report-verifier"]
    assert manifest["entry_points"]["hooks"] == ["guard-mfk-readonly", "guard-mfk-no-reinvent"]
    # Claude Code 予約フィールド (skills/agents/commands) はトップレベルに置かない。
    # entry_points で宣言し、詳細メタは各 SKILL.md / agents/*.md frontmatter が SSOT。
    assert "skills" not in manifest
    assert "agents" not in manifest
    assert "commands" not in manifest


def test_run_skills_are_exposed_as_slash_commands():
    """各 run-* スキルに commands/ のブリッジ (entrypoint→skill) があり実体も存在する。

    Claude Code はプラグインのスキルを `/<plugin>:<skill>` (名前空間付き) でしか
    自動露出しない。短い `/run-mf-invoice-reconcile` を出すには commands/*.md が要る。
    これが無いと install 後にスラッシュコマンドが「表示されない」(回帰防止)。

    doctor (`run-mf-invoice-doctor`) は skill を持たず lib/mfk_doctor.py を直接叩く
    「直接 lib 実行コマンド」(company-master の doctor サブコマンドと同型) なので、
    skill ブリッジ検査の対象からは分離し、末尾に別枠で並べる。
    """
    manifest = _json(".claude-plugin/plugin.json")
    # skill-backed コマンド: entrypoint→skill のブリッジ + skill 実体を持つ。
    skill_commands = [
        "run-mf-invoice-reconcile",
        "run-mf-invoice-check",
        "run-mf-invoice-db-setup",
        "run-mf-initial-month-enrich",
        "run-mf-invoice-report",
    ]
    # 直接 lib 実行コマンド: skill を持たず lib スクリプトを $CLAUDE_PLUGIN_ROOT fallback 形で叩く。
    direct_lib_commands = ["run-mf-invoice-doctor"]
    assert manifest["entry_points"]["commands"] == skill_commands + direct_lib_commands
    for cmd in skill_commands:
        path = os.path.join(PLUGIN_ROOT, "commands", f"{cmd}.md")
        assert os.path.exists(path), f"commands/{cmd}.md が無い (スラッシュ非表示の原因)"
        with open(path, encoding="utf-8") as f:
            text = f.read()
        # frontmatter が skill へブリッジしていること (company-master と同型)。
        assert f"name: {cmd}" in text
        assert f"entrypoint: {cmd}" in text
        # entrypoint 先の skill 実体が存在すること。
        assert os.path.isdir(os.path.join(PLUGIN_ROOT, "skills", cmd))
    for cmd in direct_lib_commands:
        path = os.path.join(PLUGIN_ROOT, "commands", f"{cmd}.md")
        assert os.path.exists(path), f"commands/{cmd}.md が無い (スラッシュ非表示の原因)"
        with open(path, encoding="utf-8") as f:
            text = f.read()
        assert f"name: {cmd}" in text
        # skill ブリッジではなく lib スクリプトを install パス非依存の fallback 形で叩く。
        assert '${CLAUDE_PLUGIN_ROOT:-plugins/mf-kessai-invoice-check}/lib/mfk_doctor.py' in text
        # doctor は skill を持たない (skill ブリッジと混同させない)。
        assert not os.path.isdir(os.path.join(PLUGIN_ROOT, "skills", cmd))


def _skill_frontmatter(skill_name):
    """skills/<name>/SKILL.md の frontmatter を素朴な key: value で読む (PyYAML 非依存)。"""
    path = os.path.join(PLUGIN_ROOT, "skills", skill_name, "SKILL.md")
    with open(path, encoding="utf-8") as f:
        text = f.read()
    assert text.startswith("---"), f"{skill_name}/SKILL.md に frontmatter が無い"
    body = text.split("---", 2)[1]
    fm = {}
    for line in body.splitlines():
        if ":" in line and not line.lstrip().startswith("#"):
            k, _, v = line.partition(":")
            fm[k.strip()] = v.split("#", 1)[0].strip()
    return fm


def test_reconcile_is_model_invocable_from_natural_language():
    """run-mf-invoice-reconcile は自然文で自動起動できること (事故Aの再発防止・恒久ロック)。

    事故: ユーザーが自然文で照合を頼んだら、正規スキルが起動せず AI が自前スクリプトを
    書き判定を TODO(human) で人間に丸投げした。根本原因(A) = SKILL.md が
    disable-model-invocation: true で自然文起動を殺していたこと。README が約束する
    「ふだんの言葉で頼むだけで動く」と設定を一致させ、将来 true へ回帰したら CI で気づく。
    書き込み安全は dry-run 既定 + --apply の --verified 必須ゲートで担保 (起動可否では縛らない)。
    """
    fm = _skill_frontmatter("run-mf-invoice-reconcile")
    assert fm.get("disable-model-invocation") == "false", (
        "run-mf-invoice-reconcile を自然文起動不可 (true) へ戻すと事故A(再発明+TODO(human))が"
        "再発する。安全は dry-run + --verified ゲートで担保済みなので false を維持すること。"
    )


def test_report_is_model_invocable_from_natural_language():
    """run-mf-invoice-report も自然文で自動起動できること (reconcile 旗艦 precedent と対称の恒久ロック)。

    external-mutation な run-* だが disable-model-invocation: false を維持する。generic な
    lint-skill-dep-step7 (external-mutation→true 要求) は本 plugin CI 非配線で、reconcile/report
    ファミリは『自然文自動起動 + 書込安全=dry-run 既定 + --apply の --verified 必須ゲート
    (notion_report_sink.py が exit2 で機械強制)』という documented deviation を採る。
    false→true への回帰を CI で検知する (reconcile と非対称に保護が欠けていた finding の解消)。
    """
    fm = _skill_frontmatter("run-mf-invoice-report")
    assert fm.get("disable-model-invocation") == "false", (
        "run-mf-invoice-report を自然文起動不可 (true) へ戻すと trigger_conditions の自然文自動"
        "起動が壊れる。書込安全は dry-run + --apply の --verified 必須ゲート (機械層) で担保済み"
        "ゆえ false を維持すること (reconcile 旗艦と同じ documented deviation)。"
    )


def test_manifest_hook_points_to_packaged_file():
    manifest = _json(".claude-plugin/plugin.json")
    command = manifest["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
    assert "$CLAUDE_PLUGIN_ROOT/hooks/guard-mfk-readonly.py" in command
    assert os.path.exists(os.path.join(PLUGIN_ROOT, "hooks", "guard-mfk-readonly.py"))


def test_manifest_reinvent_guard_is_wired_for_write_and_bash_paths():
    """再発明/TODO(human) 遮断 hook が Write/Edit/MultiEdit/Bash 経路に配線される。"""
    manifest = _json(".claude-plugin/plugin.json")
    pretooluse = manifest["hooks"]["PreToolUse"]
    # 第1層 (Bash MF変更系) は Bash hook の先頭のまま温存し、同じ Bash 入口に
    # 再発明 guard を追記して heredoc/tee/redirection 迂回も捕捉する。
    # matcher を完全一致で固定 (set 等価でエントリ数も暗黙固定し、余計な 3 つ目や
    # MultiEdit 脱落を契約で捕捉する)。
    matchers = {entry["matcher"]: entry for entry in pretooluse}
    assert set(matchers) == {"Bash", "Write|Edit|MultiEdit"}
    assert pretooluse[0]["matcher"] == "Bash"  # 第1層の順序を温存
    bash_commands = [h["command"] for h in matchers["Bash"]["hooks"]]
    assert "$CLAUDE_PLUGIN_ROOT/hooks/guard-mfk-readonly.py" in bash_commands[0]
    assert "$CLAUDE_PLUGIN_ROOT/hooks/guard-mfk-no-reinvent.py" in bash_commands[1]
    write_command = matchers["Write|Edit|MultiEdit"]["hooks"][0]["command"]
    assert "$CLAUDE_PLUGIN_ROOT/hooks/guard-mfk-no-reinvent.py" in write_command
    assert os.path.exists(os.path.join(PLUGIN_ROOT, "hooks", "guard-mfk-no-reinvent.py"))


def test_workflow_manifest_commands_are_install_path_independent():
    workflow = _json("skills/run-mf-invoice-check/workflow-manifest.json")
    commands = [p.get("command", "") for p in workflow["phases"] if p.get("command")]
    assert commands
    assert all("$CLAUDE_PLUGIN_ROOT/" in command for command in commands)
    assert not any(command.startswith("python3 scripts/") for command in commands)


def test_workflow_manifest_orchestrates_full_monthly_flow():
    workflow = _json("skills/run-mf-invoice-check/workflow-manifest.json")
    phases = workflow["phases"]
    assert [p["id"] for p in phases] == ["collect", "diff", "verify", "finalize", "sink"]
    by_id = {p["id"]: p for p in phases}
    assert by_id["verify"]["delegateAgent"] == "mfk-gap-verifier"
    assert by_id["finalize"]["dependsOn"] == ["verify"]
    assert by_id["sink"]["dependsOn"] == ["finalize"]
    assert by_id["sink"]["consumes"] == "eval-log/mfk-gap-verified.json"
    assert "fail-closed" in by_id["sink"]["note"]


def test_package_contract_exists_for_bundle_mode():
    contract = _json("references/package-contract.json")
    assert contract["package_mode"] == "bundle"
    checks = contract["pkg_checks"]
    for key in [f"PKG-{i:03d}" for i in range(1, 16)]:
        assert key in checks
        assert checks[key]["status"] in {"pass", "fail", "skip", "not_applicable"}


def test_notion_schema_customer_aggregated_snapshot():
    """顧客ID集約モデル: upsert キー=顧客ID単独、最新月スナップショットの事実列のみ。

    月次履歴はページ本文の table block に移したため、月次サマリ関連の列
    (レコード種別/件数3列) は schema から削除済み。
    """
    schema = _json("skills/run-mf-invoice-db-setup/schemas/notion-db-schema.json")
    props = schema["properties"]
    # upsert キーは顧客ID単独。
    assert schema["upsert_key"] == ["顧客ID"]
    # 事実列スナップショットは残る。
    assert props["確認済み日時"]["type"] == "date"
    assert "確認済み日時" in schema["fact_columns"]
    # 今月の発行状況 (旧 判定) の select は月次サマリを廃した3値で不変。
    assert props["今月の発行状況"]["options"] == ["発行漏れ候補", "継続発行", "今月新規"]
    assert "今月の発行状況" in schema["fact_columns"]
    # 改名: 旧 判定 キーは消え、renames に由来が残る。
    assert "判定" not in props
    assert "判定" not in schema["fact_columns"]
    assert schema["renames"] == {"判定": "今月の発行状況"}
    # 月次サマリ廃止 + 今回の削除に伴い消した列を schema が持たず deprecated に入ること。
    for removed in ["レコード種別", "発行漏れ件数", "金額変動件数", "チェック件数合計", "全体トータル",
                    "対応状況", "チェック実行ID", "初回請求月(API推定)"]:
        assert removed not in props
        assert removed not in schema["fact_columns"]
        assert removed in schema["deprecated_properties"]
    # 管理列 (人の運用) は不可侵。初回契約月は API 由来ではなく人が YYYY-MM で補う。
    # 支払サイクル (select: 月払い/年間払い) を新設し managed に入れる。
    assert props["初回契約月"]["type"] == "rich_text"
    assert "初回契約月" not in schema["fact_columns"]
    assert props["支払サイクル"]["type"] == "select"
    assert props["支払サイクル"]["options"] == ["月払い", "年間払い"]
    assert schema["managed_columns"] == ["初回契約月", "請求要否", "支払サイクル", "チェック済", "備考"]


def test_invoice_gap_schema_describes_all_monthly_check_rows():
    """schema 説明は collect の現行契約 (全チェック対象顧客を毎月 rows 化) と一致する。"""
    schema = _json("skills/run-mf-invoice-check/schemas/invoice-gap-result.schema.json")
    text = json.dumps(schema, ensure_ascii=False)
    assert "全チェック対象顧客" in schema["description"]
    assert "継続発行全件" in schema["description"]
    assert "今月新規" in schema["items"]["properties"]["verdict"]["description"]
    assert "collect 出力には含めない" not in text
    assert "金額変動した『継続発行』のみ" not in text


def test_r3_verify_contract_only_verifies_gap_rows_and_passthroughs_history_rows():
    paths = [
        "skills/run-mf-invoice-check/prompts/R3-verify.md",
        "agents/mfk-gap-verifier.md",
    ]
    for rel_path in paths:
        with open(os.path.join(PLUGIN_ROOT, rel_path), encoding="utf-8") as f:
            text = f.read()
        assert "verdict=発行漏れ候補" in text
        assert "passthrough" in text
        assert "継続発行" in text and "今月新規" in text
        assert "誤検出除外の対象にしない" in text or "検証対象にしない" in text


def test_scripts_are_executable_for_install_smoke():
    rel_paths = [
        "hooks/guard-mfk-readonly.py",
        "hooks/guard-mfk-no-reinvent.py",
        "lib/mfk_api.py",
        "lib/mfk_keychain.py",
        "lib/mfk_doctor.py",
        "scripts/reconcile_invoices.py",
        "skills/run-mf-invoice-check/scripts/check_invoice_gaps.py",
        "skills/run-mf-invoice-db-setup/scripts/build_notion_db.py",
        "skills/run-mf-invoice-db-setup/scripts/verify_db_schema.py",
        # enrich の実行エントリ (RUNTIME_DIRS に含まれるのに本テストにだけ無い非対称を解消)。
        # 純ライブラリ mf_invoice_names.py は実行エントリでないため除外。
        "skills/run-mf-initial-month-enrich/scripts/mf_invoice_oauth.py",
        "skills/run-mf-initial-month-enrich/scripts/mf_invoice_api.py",
        "skills/run-mf-initial-month-enrich/scripts/mf_invoice_enrich.py",
        "skills/run-mf-initial-month-enrich/scripts/mf_invoice_csv_match.py",
    ]
    for rel_path in rel_paths:
        mode = os.stat(os.path.join(PLUGIN_ROOT, rel_path)).st_mode
        assert mode & stat.S_IXUSR, f"{rel_path} is not executable"


def test_readme_direct_commands_delegate_to_doctor_not_bare_plugin_root():
    """README の一次セットアップ導線は doctor 委譲へ寄せ、脆弱な裸表記の存在強制を撤廃する。

    なぜ反転したか (因果ループの結節点):
      旧テストは README が `python3 "$CLAUDE_PLUGIN_ROOT/lib/mfk_api.py" --smoke` 等の
      **裸 `$CLAUDE_PLUGIN_ROOT` 実行行を一次手順として持つこと**を assert で固定していた。
      ところが `$CLAUDE_PLUGIN_ROOT` は Claude Code の実行環境でしか解決されず、素の
      ターミナルでは空展開して `can't open file '/lib/mfk_api.py'` になる。README が
      「ターミナルで疎通確認」と促し、テストがその脆弱表記を強制していたため、README を
      安全化しようとすると必ずこのテストが赤化する = 欠陥を固定する因果ループの結節点だった。
      そこで「脆弱表記の存在強制」を除去し、代わりに「doctor 委譲が一次導線に在ること」と
      「repo 相対直書きが無いこと (堅牢性の正しい不変条件)」を固定する向きへ反転する。
    """
    with open(os.path.join(PLUGIN_ROOT, "README.md"), encoding="utf-8") as f:
        readme = f.read()
    # 維持: repo 相対直書きは禁止 (install パス非依存を守る正しい不変条件)。
    assert "python3 plugins/mf-kessai-invoice-check/" not in readme
    # 追加: 一次セットアップ導線に doctor 委譲 (スラッシュコマンド or 自然文) が在ること。
    assert "/run-mf-invoice-doctor" in readme
    assert "MF掛け払いのセットアップを確認して" in readme
    # 追加 (軽い横展開ガード): ```bash コードブロック内に、fallback も `#` 開発者補足注記も
    # 無い純粋な裸 `$CLAUDE_PLUGIN_ROOT` 実行行が一次手順として残っていないこと。
    # (裸 `$CLAUDE_PLUGIN_ROOT/...` は fallback 形 `${CLAUDE_PLUGIN_ROOT:-...}` か
    #  「# 開発者向け」補足の文脈でのみ許可する。厳密な横展開 lint は別 executor が担う。)
    for block in _readme_bash_blocks(readme):
        stripped_lines = [ln.strip() for ln in block.splitlines()]
        has_dev_note = any(ln.startswith("#") and ("開発者" in ln or "clone" in ln) for ln in stripped_lines)
        for ln in stripped_lines:
            if ln.startswith("#") or not ln:
                continue
            if '"$CLAUDE_PLUGIN_ROOT/' in ln and "${CLAUDE_PLUGIN_ROOT:-" not in ln:
                assert has_dev_note, (
                    "```bash 一次手順に裸 $CLAUDE_PLUGIN_ROOT 実行行が残存 "
                    f"(fallback も開発者補足注記も無い): {ln!r}")


def _readme_bash_blocks(readme):
    """README の ```bash フェンス内テキストを列挙する (裸 $CLAUDE_PLUGIN_ROOT 検査用)。"""
    blocks = []
    lines = readme.splitlines()
    in_block = False
    buf = []
    for line in lines:
        if line.strip().startswith("```"):
            if in_block:
                blocks.append("\n".join(buf))
                buf = []
                in_block = False
            elif line.strip() in ("```bash", "```sh"):
                in_block = True
            continue
        if in_block:
            buf.append(line)
    return blocks


def test_prompts_do_not_use_bare_script_paths():
    checked = []
    for dirpath, _, filenames in os.walk(os.path.join(PLUGIN_ROOT, "skills")):
        for filename in filenames:
            if not filename.endswith(".md"):
                continue
            path = os.path.join(dirpath, filename)
            with open(path, encoding="utf-8") as f:
                text = f.read()
            checked.append(path)
            assert "python3 scripts/" not in text
            assert "python3 plugins/mf-kessai-invoice-check/" not in text
    assert checked


def _runtime_py_files():
    files = []
    for rel in RUNTIME_DIRS:
        base = os.path.join(PLUGIN_ROOT, rel)
        if not os.path.isdir(base):
            continue
        for dirpath, _, filenames in os.walk(base):
            for filename in filenames:
                if filename.endswith(".py"):
                    files.append(os.path.join(dirpath, filename))
    return files


def _top_level_imports(tree):
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:  # 絶対 import のみ (相対は対象外)
                names.add(node.module.split(".")[0])
    return names


def test_runtime_imports_are_stdlib_or_in_plugin_only():
    """I3 移植性: 本番ランタイムは標準ライブラリ + プラグイン内モジュールのみに依存する。

    第三者パッケージ (requests / jinja2 等) を runtime に混入させると install 先で手動
    pip が必要になり移植性が壊れる。AST 走査で import を機械的に検査し、将来の混入を
    CI で検出する (grep でなく AST なので import 文を正確に同定)。
    許可基盤は sys.stdlib_module_names (標準機構) を使い自前メンテを避ける。
    """
    files = _runtime_py_files()
    assert files, "ランタイム .py が見つからない (RUNTIME_DIRS の設定ミス)"
    in_plugin = {os.path.splitext(os.path.basename(f))[0] for f in files}
    allowed = set(sys.stdlib_module_names) | in_plugin
    violations = {}
    for path in files:
        with open(path, encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=path)
        bad = sorted(_top_level_imports(tree) - allowed)
        if bad:
            violations[os.path.relpath(path, PLUGIN_ROOT)] = bad
    assert not violations, f"標準ライブラリ/プラグイン内 以外の import を検出: {violations}"
