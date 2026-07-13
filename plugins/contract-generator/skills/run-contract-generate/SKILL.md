---
name: run-contract-generate
description: tenantの業務委託契約書の下書きを作成・量産したいとき、管理台帳から個人/法人のひな形に差込みDocs生成してSlack通知したいときに使う。
disable-model-invocation: true
user-invocable: true
allowed-tools: [Read, Write, Edit, Bash(python3 *), AskUserQuestion]
kind: run
version: 0.3.0
owner: harness maintainers
since: 2026-05-29
role_suffix: generator
hierarchy_level: L1
rubric_refs:
  - "../../../harness-creator/skills/run-elegant-review/references/thought-methods.yaml"
  - "references/concept.md"
  - "../../lib/validate.py"
  - "../../lib/scan_template.py"
responsibility_refs: [prompts/R1-select-and-fill.md, ../../agents/contract-draft-agent.md, scripts/draft.py, references/template-mapping.json]
prompt_ssot: prompts/R1-select-and-fill.md
effect: external-mutation
source: doc/参考Skill/contract-generator/ + output/contract-generator-v2/(concept.md, refactor-plan.md, ledger-*-schema.md)
source-tier: internal
last-audited: 2026-05-30
audit-trigger: on-change
feedback_contract: # per-skill 評価基準(SSOT=scripts/feedback_contract_ssot.py)
  max_iterations: 3
  criteria:
    - id: IN1
      loop_scope: inner
      text: 生成後の Docs/別紙に未置換プレースホルダ(`●`/`XXXX`/第6条記の空欄)が一切残っていないこと(docx_fill.py 末尾の残存チェックで機械検証)。
      verify_by: lint
    - id: IN2
      loop_scope: inner
      text: 差込は黄色 run(highlight_color==YELLOW)のみを対象とし、法務承認済 .docx の条文本文・レイアウトを改変しないこと(validate.py 差込前検証+アンカー機械抽出で担保)。
      verify_by: lint
    - id: OUT1
      loop_scope: outer
      text: draft の停止条件が「Docs黄色版生成+Slack通知+台帳draft化」までに限定され、PDF確定/completed書戻し(run-contract-finalize)・ひな形追従(run-template-sync)へ責務分離されている設計が、契約書作成負荷削減という目的を最適に反映していること。
      verify_by: elegant-review
---

# run-contract-generate

## Purpose & Output Contract
管理台帳(Google Sheets)の「作成指示◯ かつ 未作成」行ごとに、契約タイプ(個人/法人)に応じた Drive 上の `.docx` ひな形を差込・条項分岐し、**AI記入箇所を黄色化した Google Docs 版(下書き・要確認)** を個人/法人フォルダへ保存→**Slackに通知**→台帳を `draft` 化(ファイル名/契約書URL/Slack TS/日時)。承認後の提出用PDFは `run-contract-finalize` が担う(責務分離)。実体は共有エンジン `../../lib/engine.py --phase draft`。法務承認済の条文は改変しない。概念は `references/concept.md`、差込仕様は `references/injection-mapping.md`、設定は plugin直下 `README.md`。

## 境界
下書き生成(Docs黄色版)+法人別紙1-3生成+Slack通知+台帳draft化まで。**承認検知・PDF確定・共有は `run-contract-finalize`**、**ひな形変更追従は `run-template-sync`** に分離。7専門家による法的レビュー/Notion連携/Markdown副系は対象外。後方互換: `--phase` 未指定で従来の1パス(Docs+PDF即時)も可。

## 主要ルール
- **ひな形不改変**: 法務承認済 `.docx` の条文本文は変更しない。黄色プレースホルダ(`●`/`XXXX`/第6条記の空欄)のみ差込む。
- **甲はSSOT**: `lib/config_auth.load_party_a()` から取得(台帳/Drive/直書きより `lib/config_auth` が優先)。台帳に甲列を作らない。具体値は config_auth に集約。
- **黄色二系統**: 差込んだ run は黄色維持→Google Docs版。複製してハイライト除去→PDF版。
- **個人/法人分離**: 台帳は同一スプレッドシート内の `個人`/`法人` 2シート。列構成・ひな形・出力フォルダを分ける(法人①は成果物/検収を別紙委譲・署名欄に代表者)。
- **認証と機密**: Service Account 鍵は macOS Keychain(`gdrive-service-account.<keychain-prefix>` / `contract-generate/service-account-json`)。環境依存IDは `google-config.json`(gitignore)。乙住所/代表者/口座は機微情報、台帳・出力フォルダの共有を最小化。
- **冪等性**: 台帳の冪等キーで重複生成を防止。`completed` 行は既定スキップ。
- **セットアップは `references/README-setup.md`**(GCP有効化・SA作成・Keychain登録コマンド・フォルダ共有・config記入)。

## ゴールシーク実行
> 固定手順は書かない。毎周「ゴール・目的/背景・チェックリスト」を読み、その時点で最適な手順を AI が生成・実行する。詳細は run-build-skill `references/goal-seek-paradigm.md`。重い周回は SubAgent に fork し親へは要約のみ返す。

### ゴール (Goal)
管理台帳の作成指示◯行が、個人/法人それぞれのひな形から**黄色維持 Google Docs 版(下書き・要確認)**として該当フォルダに生成され、Slack通知のうえ台帳へ ファイル名・契約書URL・Slack_メッセージTS・ステータス=`draft`・日時が書き戻された状態。黄色除去 PDF 化・ステータス=`completed` 書戻しは **`run-contract-finalize` の責務**(本スキルの draft 停止条件には含めない)。後方互換の1パス(legacy)モード(`--phase` 未指定で Docs+PDF即時・completed)を明示利用した場合のみ PDF/completed まで一括する。

### 目的・背景 (Why)
1人事業の契約書作成負荷を機構に肩代わりさせ本業(AIコンサル)へ時間を再配分する。法務承認済 `.docx` ひな形と都度変わりうる台帳を単一の照合エンジンで結び、二重管理とレイアウト崩れを排除する。

### 完了チェックリスト (Checklist)
- [ ] `google-config.json` と Keychain 鍵を読み込み Service Account で認証できる(`python3 $CLAUDE_PLUGIN_ROOT/lib/config_auth.py --check`。セットアップ全体は `python3 $CLAUDE_PLUGIN_ROOT/lib/setup_doctor.py` で横断診断)
- [ ] 管理台帳に `個人`/`法人` 2シートが存在し各スキーマのヘッダを持つ(無ければ整備・既存サンプル行は保持)
- [ ] 作成指示◯かつステータス∈{空,未作成} の行を冪等キー付きで抽出できる(既定の draft phase の `_PHASE_STATUS_FILTER`。後方互換の legacy 1パスのみ ステータス≠completed)
- [ ] 契約タイプに応じ法人①/個人②の `.docx` を名前パターンで取得できる
- [ ] 標準ライブラリ実装(docx_lib)で黄色run置換・条件分岐(業務内容方式/料金方式/個人情報処分・個人のみ成果物有無)・AI記入の黄色維持ができる
- [ ] 黄色維持版を Google Docs 化し該当フォルダへ保存できる
- [ ] ファイル名 `{No}_{乙名}_業務委託契約書_{YYYYMMDD}` で生成される
- [ ] 欠損必須列は AskUserQuestion で補完してから生成する
- [ ] 生成後に未置換プレースホルダ(`●`/`XXXX`)が残っていない
- [ ] Slack 通知のうえ 台帳へ ファイル名/契約書URL/Slack_メッセージTS/ステータス=`draft`/作成・更新日時 を書き戻せる(draft の停止条件はここまで)
- [ ] (legacy 1パスモード専用) 黄色除去版を PDF 化し該当フォルダへ保存・台帳へ PDF_URL/ステータス=`completed` を書き戻せる ※既定の draft 経路では `run-contract-finalize` の責務であり本チェックは対象外

### ゴールシークループ
1. 未達 `[ ]` を特定 → 2. 手順を都度生成(固定化禁止)→ 3. 実行 → 4. チェックリスト再評価し `[x]` 更新 → 全 `[x]` まで反復。規定周回(3)で未達なら open_issues に差し戻す。

### ゴールシーク配線
量産案件(複数行)を多周回す場合の周回状態とドリフト圧縮の配線。周回末に `eval-log/run-contract-generate-intermediate.jsonl` へ `{iteration, original_goal, current_goal_snapshot, delta_from_original, merged_directive_for_next, drift_signal}` を1行追記する。`original_goal` は全周回で不変(SHA-256 を `eval-log/run-contract-generate-progress.json` の `original_goal_hash` に固定し毎周回照合)。次周回の手順生成は直前の `merged_directive_for_next` と `original_goal` を必須入力として読む(AI 単独再導出禁止)。重い周回は `Skill(run-goal-seek)` に fork 委譲する。

```bash
python3 "$CLAUDE_PLUGIN_ROOT/lib/check_intermediate.py" run-contract-generate
# → eval-log/run-contract-generate-intermediate.jsonl の original_goal_hash 不変・required_keys 充足を検査
# 不整合は exit 2 で次周回を停止
```

## ゴールシーク品質ループ (正負フィードバック)

各周回末に `lib/feedback_loop.py` の `record_positive()` / `record_negative()` を呼び、シグナルを `eval-log/run-contract-generate-feedback.jsonl` に追記。次周回開始時に `derive_next_directive("run-contract-generate", round)` を参照し、戻り値を `merged_directive_for_next` の先頭に prepend する(過去周回の負シグナルを次手順に必ず反映)。

### 正負シグナル定義表 (run-contract-generate)

> 正負シグナルの定義(positive/negative の各シグナルと検出元)は、責務単位 7 層プロンプト `prompts/R1-select-and-fill.md` §4.4「正負フィードバックループ」を**正本(SSOT)**とする。本スキルは重複定義せず同表を参照する。

反映タイミング: 周回末 `record_*` → 次周回開始時 `derive_next_directive` → merged_directive に prepend。

## 検証
- `口座番号`=7桁半角数字 / `口座種類`∈{普通,当座}
- `契約開始日`<`契約終了日` かつ両者 `YYYY/MM/DD`
- `金額`=半角整数(差込時 `100,000円` へ整形)
- 必須非空: 乙名称 / 乙住所(法人は代表者役職・氏名も)
- 生成後に未置換プレースホルダ(`●`/`XXXX`)残存なし
- 実装は `$CLAUDE_PLUGIN_ROOT/lib/validate.py`(差込前)+ `$CLAUDE_PLUGIN_ROOT/lib/docx_fill.py` 末尾の残存チェック(差込後)

## Gotchas
- `read_file_content` 系ではハイライト属性を取得できない。差込アンカーは `$CLAUDE_PLUGIN_ROOT/lib/docx_fill.py` が `run.font.highlight_color==WD_COLOR_INDEX.YELLOW` を機械抽出して特定する。
- PDF は Drive 上で Google Docs 変換→`export(application/pdf)` で生成する(LibreOffice 不要)。
- 機微情報(住所/代表者/口座)を扱うため、台帳・出力フォルダの共有範囲を最小化する。
- 副作用(外部書込)を伴う。`--dry-run` で台帳書込・Drive保存を抑止して検証可能。

## 変数化契約
`契約タイプ(個人/法人)` / `ひな形DocID(個人②/法人①)` / `台帳シート名` / `出力フォルダID` を `google-config.json` と台帳から注入。具体値は本文に直書きせず config と台帳に置く。

## 追加リソース
- `references/README-setup.md` — スキル内部参照用の技術要約(CI/pre-commit配線・template-mapping二重定義注意)。**セットアップ手順の正本は plugin直下 `README.md`(Task 0-14)**
- `lib/setup_doctor.py` — セットアップ総合診断(cwd/Python/gcloud/env/Keychain/config/Drive/Sheets/Slack を横断点検し未完了 Task を名指し)
- `references/concept.md` — 概念設計(参考スキル継承/転換・概念図)
- `references/injection-mapping.md` — 個人/法人の台帳列⇄ひな形プレースホルダ差込マッピング
- `references/legal-knowledge-index.md` — 法令ナレッジ(参考スキル references/00-11)索引
- `references/google-config.sample.json` — `google-config.json` のひな形
- `prompts/R1-select-and-fill.md` — 行選択・差込・欠損補完の責務単位7層プロンプト(SSOT正本)。`../../agents/contract-draft-agent.md` は本プロンプトを参照する薄い実行アダプタ(本文を持たない)。
- 追加リソースは plugin 直下 `lib/` ディレクトリ全体を参照。各ファイルは PEP723 風メタブロックで purpose を記載。
- 本 skill が強く依存する lib: `engine.py`(--phase draft 委譲先) / `docx_fill.py`(黄色 run 差込) / `scan_template.py`(差込アンカー抽出) / `validate.py`(差込前検証) / `config_auth.py`(SSOT 甲情報)
- `scripts/draft.py` — 薄い shim(`lib/engine.py --phase draft` への委譲のみ)

## セキュリティと権限
本Skillは外部書込(Drive/Sheets, `effect=external-mutation`)を伴うため二段防御を**実装済み**:
- **動的層(実装)**: `hooks/hook-guard-secret.py`(PreToolUse/Bash, plugin.json 配線済)が SA 鍵の平文出力経路(廃止済 `--print-unsafe` 含む再導入防御)・誤削除(`delete-generic-password`)をブロック。`keychain_get_secret.py` は `CLAUDE_HOOK_INVOKED=1` 必須化で直接呼び出しを exit 2 で拒否。
- **静的層(ユーザー適用)**: `references/settings-hardening.json` の `permissions.deny` を `.claude/settings.json` にマージすると鍵流出系コマンドを拒否。
- **設計上の保護**: 書込先は `google-config.json` の許可ID(台帳/個人・法人フォルダ)に限定(`config_auth.load_config` が必須キー検証)、鍵は Keychain のみ・平文保存禁止、`--dry-run` で副作用抑止、`ensure_schema` は非破壊追記。
- **将来拡張**: spreadsheetId/folderId の config 許可値を実行時照合する追加 PreToolUse hook(現状は config 経由注入のため CLI に ID は露出しない)。
