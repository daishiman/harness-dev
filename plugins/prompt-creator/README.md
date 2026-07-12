# prompt-creator

7 層プロンプトアーキテクチャで、プロンプトのヒアリング、生成、評価、governance までを実行する Claude Code plugin です。正本フローは `/prompt-creator:run-prompt-create` です。`run-prompt-creator-7layer` は Step 2 の生成 worker で、Markdown (`.md`) を既定成果物とし、YAML は内部正規形または legacy 互換に限定します。SubAgent `.md` の **Prompt Templates** / **Self-Evaluation** 注入は `owner_agent` 指定時だけの付随機能です。

**1 分判別表** — あなたの要望 → 使う skill:

| あなたの要望 | 使う skill |
| --- | --- |
| 迷ったら / ヒアリング→生成→評価→governance を一括 | `/prompt-creator:run-prompt-create` |
| brief 確定済みで 7 層プロンプトの単体生成のみ | `/prompt-creator:run-prompt-creator-7layer` |
| どの skill にも紐付かない汎用プロンプトの要望整理 | `/prompt-creator:run-prompt-elicit` (standalone モード。出力先はユーザー指定) |

---

## 目次

1. [動作要件](#1-動作要件)
2. [セットアップ (clone 開発環境)](#2-セットアップ-clone-開発環境)
3. [チーム共有](#3-チーム共有)
4. [利用確認](#4-利用確認)
5. [使い方](#5-使い方)
6. [harness-creator との連携](#6-harness-creator-との連携)
7. [構成ファイル一覧](#7-構成ファイル一覧)
8. [スクリプト一覧](#8-スクリプト一覧)
9. [トラブルシューティング](#9-トラブルシューティング)
10. [アップデート / アンインストール](#10-アップデート--アンインストール)
11. [メンテナ・ライセンス](#11-メンテナライセンス)

---

## 1. 動作要件

事前に次がインストール済みであること。バージョン確認コマンドを実行して結果が返れば OK です。

| ツール       | 必須バージョン | 確認コマンド          |
| ------------ | -------------- | --------------------- |
| Claude Code  | 最新           | `claude --version`    |
| Git          | 2.30+          | `git --version`       |
| Python       | 3.8+           | `python3 --version`   |
| GitHub CLI   | (任意) 2.0+    | `gh --version`        |

> **どれか欠けている場合**
> - Claude Code: https://claude.com/claude-code からインストール
> - Git: https://git-scm.com/downloads
> - Python: https://www.python.org/downloads/ (3.8 以上)

---

## 2. セットアップ (clone 開発環境)

prompt-creator は `distributable: false` の開発基盤 plugin です。marketplace 一覧・配布 bundle には出ず、`/plugin install` の対象ではありません。利用する場合はリポジトリを clone し、repo 内の正本を `.claude/` symlink 経由で使います。

### 手順 2-1. リポジトリを clone

```bash
git clone git@github.com:OWNER/harness.git
cd harness
```

(SSH 鍵未設定なら HTTPS でも可)

```bash
git clone https://github.com/OWNER/harness.git
cd harness
```

### 手順 2-2. 開発用 symlink を同期

```bash
make sync
```

---

## 3. チーム共有

チームで prompt-creator を使う場合も marketplace 配布ではなく、同じリポジトリを clone した開発環境で使います。`.claude/` 配下は `make sync` で `plugins/prompt-creator/` の正本へ symlink されます。

### 手順 3-1. 最新化

```bash
git pull
make sync
```

### 手順 3-2. チームメンバー側の作業

各メンバーは clone 済み worktree で `make sync` を実行します。配布ユーザー向けの marketplace install では prompt-creator は利用できません。

---

## 4. 利用確認

Claude Code 内で次を実行し、`prompt-creator` 関連のエントリが見えれば成功です。

```text
/plugin list
```

```text
/skill
```

`run-prompt-create` と `run-prompt-creator-7layer` が一覧に出ていれば OK。出ていない場合は [9. トラブルシューティング](#9-トラブルシューティング) を参照。

---

## 5. 使い方

### 5-0. 正本の位置づけ

- ユーザー向け正本フロー: `skills/run-prompt-create/workflow-manifest.json`
- ヒアリング raw data: `skills/run-prompt-elicit/schemas/hearing-result.schema.json` (`evaluation_priorities` enum / goals / checklist の SSOT)
- 生成 worker の legacy sheet input: `skills/run-prompt-creator-7layer/schemas/hearing-result.schema.json`
- 生成成果物: Markdown (`.md`) が既定。YAML は内部正規形または legacy 互換
- 重複判断の上位正本: `plugins/harness-creator/references/ssot-dedup-procedure.md`。prompt-creator 内の冪等更新要約は `skills/run-prompt-creator-7layer/references/idempotent-update-policy.md`

### 5-1. 正本フローで起動

```text
/prompt-creator:run-prompt-create
```

次の 6 フェーズを実行します。Gate 1 だけユーザー確認を行い、Gate 2-4 は `references/governance-params.json` と `workflow-manifest.json` の条件を満たす場合に自動承認します。

| Step | 役割 | 主な担当 |
| ---- | ---- | -------- |
| 1 | ヒアリングと `prompt-brief.json` 作成 | `run-prompt-elicit` |
| 2 | 7 層プロンプト生成 | `run-prompt-creator-7layer` |
| 3a | P0 lint | script |
| 3b | 設計評価 C1-C4 | `assign-prompt-design-evaluator` |
| 4 | elegant-review | `harness-creator:run-elegant-review` |
| 5 | governance 承認 | `governance-decide.md` |
| 6 | 完了レポート | `run-prompt-create` |

### 5-2. 生成 worker を直接起動

```text
/prompt-creator:run-prompt-creator-7layer
```

単体起動時の Phase 構成は `skills/run-prompt-creator-7layer/SKILL.md` を正本として参照してください (README への転記は二重管理になるため行いません)。ヒアリング (Phase 1) は `run-prompt-elicit` への委譲に一本化されています。

### 5-3. 出力物

- `eval-log/prompt-brief.json`: ヒアリング結果から構築した brief
- `eval-log/prompt-build-trace.json`: 生成・検証 trace
- `plugins/<plugin>/skills/<skill>/prompts/<R-id>-<slug>.md`: 既定成果物
- `tmp/prompt.yaml`: 内部正規形または中間成果物
- `LOGS.md`: 実行ログ (自動追記)

### 5-4. 宣言型 (ゴールシーク) 転換の概要

生成・評価・自己プロンプトの全層は **Layer 5 契約** (`skills/run-prompt-creator-7layer/references/seven-layer-format.md`「Layer 5 契約」= l5-contract v2.0.0) に従属します。

- Layer 5 は「5.2 ゴール定義 / 5.3 完了チェックリスト (停止条件) / 5.4 実行方式 (6 ステップ+Anchor のゴールシークループ)」で構成し、固定手順は書きません (旧「5.2 推論手順 / 5.3 自己検証 checklist」は廃止)。
- 評価 rubric (`prompt-rubric.json` v2.0.0) は数量レンジ基準を廃止し、非空 (構造下限) + 検証可能性 (質ベース) で判定します。
- ヒアリングは goals (達成ゴール=成果状態文) と checklist (YES/NO 判定文) を必須収集し、`evaluation_priorities` の語彙・上限は `skills/run-prompt-elicit/schemas/hearing-result.schema.json` の enum (5 値・最大 2) が正本 (SSOT) です。

---

## 6. harness-creator との連携

`harness-creator` の `run-build-skill` Step 7.5 で `--with-prompts` フラグ付き呼び出しがあると、本 plugin がループ起動します。`owner_agent` が渡された場合のみ、生成中の SubAgent `.md` の **Prompt Templates** と **Self-Evaluation** セクションを自動充填します。

連携が動作しているかは次のログで確認できます。

```bash
tail -n 20 plugins/prompt-creator/LOGS.md
```

---

## 7. 構成ファイル一覧

```text
plugins/prompt-creator/
├── .claude-plugin/
│   └── plugin.json                       # plugin manifest
├── README.md                             # 本ファイル
├── LOGS.md                               # 実行ログ (自動更新)
├── agents/
│   ├── prompt-creator-interview-user.md
│   ├── prompt-creator-generate-prompt.md
│   └── prompt-creator-review-prompt.md
└── skills/
    ├── run-prompt-create/                 # 正本 orchestrator
    │   ├── prompts/
    │   ├── references/
    │   ├── schemas/
    │   ├── scripts/                       # evaluate-create-gates.py
    │   └── workflow-manifest.json
    ├── run-prompt-elicit/                 # Step 1 worker
    ├── run-prompt-creator-7layer/         # Step 2 worker
    │   └── scripts/                       # 8 本の python3 スクリプト
    │       ├── merge-layers.py
    │       ├── validate-prompt.py
    │       ├── verify-completeness.py
    │       ├── convert-format.py
    │       ├── generate-sheet.py
    │       ├── validate-sheet.py
    │       ├── scaffold-prompt.py
    │       └── log-usage.py
    └── assign-prompt-design-evaluator/    # Step 3b evaluator
```

---

## 8. スクリプト一覧

すべて python3 標準ライブラリのみで動作 (外部依存ゼロ)。YAML は標準ライブラリのみで手書き処理する。配置先は `skills/run-prompt-creator-7layer/scripts/`。

| script                  | 役割                                                | 終了コード       |
| ----------------------- | --------------------------------------------------- | ---------------- |
| `generate-sheet.py`     | ヒアリング結果から 7 層シートを生成                 | 0=成功 / 1=失敗  |
| `validate-sheet.py`     | シートの充足度検証                                  | 0=valid          |
| `scaffold-prompt.py`    | シート→7 層プロンプト雛形変換                       | 0=成功           |
| `merge-layers.py`       | 7 層をマージし最終プロンプト生成                    | 0=成功           |
| `validate-prompt.py`    | 最終プロンプトの構造検証                            | 0=valid          |
| `verify-completeness.py`| 7 層すべてが充足しているか確認                      | 0=完全           |
| `convert-format.py`     | 内部正規形 YAML → Markdown / JSON / XML 変換         | 0=成功           |
| `log-usage.py`          | 実行結果を LOGS.md に追記                           | 0=記録完了       |

手動実行例:

```bash
python3 plugins/prompt-creator/skills/run-prompt-creator-7layer/scripts/generate-sheet.py --help
python3 plugins/prompt-creator/skills/run-prompt-creator-7layer/scripts/log-usage.py --result success --phase manual
```

---

## 9. トラブルシューティング

### Q1. marketplace に prompt-creator が出ない

正常です。prompt-creator は `distributable: false` のため marketplace 一覧・配布 bundle・`/plugin install` の対象外です。利用する場合は [セットアップ](#2-セットアップ-clone-開発環境) のとおり repo を clone して `make sync` を実行してください。

### Q2. `/skill` に `run-prompt-creator-7layer` が出ない

Claude Code を再起動 (`Ctrl+C` → `claude`) し、`.claude/skills/run-prompt-creator-7layer` が正本へ symlink されているか確認。

### Q3. script 実行で `python3: command not found` / モジュールエラー

`python3 --version` で 3.8 以上であることを確認。スクリプトは標準ライブラリのみで動作するため追加 install は不要。

### Q4. ローカル開発で symlink が動作しない

`.claude/skills/run-prompt-creator-7layer` が `plugins/prompt-creator/skills/run-prompt-creator-7layer` を指している必要があります。

```bash
readlink -f .claude/skills/run-prompt-creator-7layer
```

正本パスが返らない場合は再作成:

```bash
ln -sf ../../plugins/prompt-creator/skills/run-prompt-creator-7layer .claude/skills/run-prompt-creator-7layer
ln -sf ../../plugins/prompt-creator/agents/prompt-creator-interview-user.md .claude/agents/prompt-creator-interview-user.md
ln -sf ../../plugins/prompt-creator/agents/prompt-creator-generate-prompt.md .claude/agents/prompt-creator-generate-prompt.md
ln -sf ../../plugins/prompt-creator/agents/prompt-creator-review-prompt.md .claude/agents/prompt-creator-review-prompt.md
```

### Q5. LOGS.md が更新されない

`log-usage.py` の実行権限と書き込み権限を確認:

```bash
ls -l plugins/prompt-creator/LOGS.md plugins/prompt-creator/skills/run-prompt-creator-7layer/scripts/log-usage.py
```

---

## 10. アップデート / アンインストール

### アップデート

```bash
cd /path/to/harness
git pull
make sync
```

### アンインストール

prompt-creator は marketplace install されないため、通常のアンインストール操作はありません。使わない場合は clone 済み worktree から離れるか、`.claude/` symlink を再生成・削除してください。

---

## 11. メンテナ・ライセンス

- **メンテナ**: team-platform (`plugin.json` `owner` 参照)
- **since**: 2026-05-20 (`doc/prompt-creator/` から移植)
- **source of truth**: `plugins/prompt-creator/` (旧 `doc/prompt-creator/` は deprecated)
- **ライセンス**: リポジトリルートの `LICENSE` に従う

---

## 参考リンク

- Claude Code Plugin docs: https://code.claude.com/docs/en/plugins
- Plugin reference: https://code.claude.com/docs/en/plugins-reference
- Marketplace docs: https://code.claude.com/docs/en/plugin-marketplaces
- harness root README: `../../README.md`
- harness-creator: `../harness-creator/`
