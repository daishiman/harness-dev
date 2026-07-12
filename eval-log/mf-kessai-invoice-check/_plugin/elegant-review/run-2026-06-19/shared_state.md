# shared_state — mf-kessai-invoice-check elegant-review (Phase 1 俯瞰)

## 俯瞰要約 (200字以内 / Phase2 ファンアウト中継)

MF掛け払いの請求書発行漏れを月次検知しNotion管理する3スキル構成 (ref-mf-kessai-api / run-mf-invoice-db-setup / run-mf-invoice-check)。発行漏れ=前月発行−今月発行(issue_date帰属)の差集合。collect→diff(純関数)→verify(fork subagent)→sink(冪等upsert)。MF API はGET専用でPreToolUse hookが変更系を遮断。Notionは事実列のみ書き管理列は人領域。skill規約(frontmatter/7層prompt/schema/manifest)は概ね準拠。懸念はポータビリティ(出力先パス解決)と二段確認の機構強制。

## 観察した全ファイル

- `.claude-plugin/plugin.json` — hooks(PreToolUse Bash→guard-mfk-readonly.py, $CLAUDE_PLUGIN_ROOT), bundles, version 0.1.0
- `README.md` — セットアップ手順。`cd plugins/mf-kessai-invoice-check`・`python3 plugins/.../lib/...` ハードコードパス
- `.mf-kessai-config.example.json` / `.mf-kessai-config.json` — environment/base_url/keychain_service/keychain_account/notion{database_id,parent_page_id}
- `lib/mfk_keychain.py` — Keychain取得唯一経路。env/DEFAULT定数 (config の keychain_* キーは読まない)
- `lib/mfk_api.py` — GET薄ラッパ。load_config は plugin_root 相対 (移植性OK)
- `lib/mfk_invoice_diff.py` — 純関数 detect_gaps/amount_changed。pytest済
- `lib/notion_invoice_sink.py` — 冪等upsert。事実列のみ。重複検出でraise
- `skills/ref-mf-kessai-api/{SKILL.md,references/mf-kessai-api.md}` — API/判定アルゴリズム参照正本
- `skills/run-mf-invoice-db-setup/{SKILL.md,prompts/R1-R2,schemas/notion-db-schema.json,scripts/build_notion_db.py,verify_db_schema.py}`
- `skills/run-mf-invoice-check/{SKILL.md,prompts/R1-R4,schemas/invoice-gap-result.schema.json,scripts/check_invoice_gaps.py,workflow-manifest.json}`
- `hooks/guard-mfk-readonly.py` — 変更系正規表現遮断 (exit 2)
- `agents/mfk-gap-verifier.md` — R3 薄アダプタ (tools: Read, Bash(python3 *) ※Write無)
- `tests/test_invoice_diff.py` — 8 passed

## 第一印象の懸念点 (観点紐付け / 断定でなく観察)

### 観点2 ポータビリティ (任意 install パス)
- O2-a: `check_invoice_gaps.py` の `_REPO_ROOT = plugin_root/../..` は「plugin が <repo>/plugins/<name>/ 配下」前提。marketplace install では eval-log 出力先が install dir の2階層上の意図しない場所を指す疑い。
- O2-b: パス基準が文書間で不一致。prompts/agent は裸の相対 `eval-log/...` `scripts/...` `lib/...` (CWD依存)、README は `plugins/mf-kessai-invoice-check/...` (repo依存)、script は `_REPO_ROOT` 絶対。CWD前提が三者三様。
- O2-c: README は config を install dir 内へ `cp` する設計。read-only install 先で脆い可能性。
- O2-d: hook の `$CLAUDE_PLUGIN_ROOT` は正しい。scripts の `__file__` 相対 plugin_root 解決も移植性OK。NGは _REPO_ROOT 派生のみ。

### 観点1 run-goal-seek / skill-creator 規約適合
- O1-a: 3スキルとも frontmatter / responsibility_refs / schema_refs / manifest / prompts(7層) / ゴールシーク実行節を備え概ね準拠。
- O1-b: workflow skill の「ゴールシークループ」が固定4ステップ列挙。run-goal-seek の「手順を固定しない」思想との整合は要判断 (workflow skill では許容範囲か)。
- O1-c: 中間成果物アンカー (run-goal-seek-intermediate.jsonl) 機構は本workflow skillに無い。orchestrator限定機構かの判定要。

### 観点3 4条件 (矛盾/漏れ/整合/依存)
- O3-a (C4依存断線/C2漏れ): verify→sink の確定リスト永続化が欠落疑い。verifier は Write 無で返値のみ。`--sink` 既定は未検証 collect 出力を読む → 二段確認が既定でバイパスされうる。
- O3-b (C3整合): config の `keychain_service`/`keychain_account` はコードが未消費 (デッドキー)。
- O3-c (C3整合): README「構成(実装済み)」の `.../run-mf-invoice-check/...` 省略パス表記と実パスの突合要。
- O3-d (smell): `_REPO_ROOT` は check_invoice_gaps でのみ使用。他は plugin_root で完結 → 唯一の異物。
