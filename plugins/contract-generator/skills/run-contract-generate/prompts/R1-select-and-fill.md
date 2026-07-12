---
responsibility_id: R1-select-and-fill
skill: run-contract-generate
kind: prompt
layers_covered: [L1, L2, L3, L4, L5, L6, L7]
source: self (SSOT)
output_schema: N/A (完了レポートは Markdown。差込結果は engine が台帳へ書込)
context_fork: true (理由: 量産時に案件単位で親contextを汚さず並列実行。ただし欠損補完のAskUserQuestionは親へ委譲)
reproducible: true (同一台帳行・同一ひな形→同一Docs。日付のみ実行日)
---

# R1-select-and-fill (7 層本文 SSOT 正本)

本ファイルが R1-select-and-fill 責務の 7 層プロンプト本文の唯一の正本(SSOT)。実行アダプタは `../../../agents/contract-draft-agent.md`。

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール
- 法務承認済 `.docx` ひな形の条文本文を改変しない。差込は黄色プレースホルダ(`●`/`XXXX`/第6条記の空欄)のみ。
- 甲は SSOT (`lib/config_auth.load_party_a()` = `lib/ledger.get_party_a()`)。値はハードコードせず差込時に `{{party_a.name|address|title|rep_name}}` を展開(代表者は役職 title と氏名 rep_name に分けて差込む)。フォールバック優先順位の正本は `references/party_a-readme.md`。台帳に甲列を作らない。
- AI が記入した run は黄色ハイライトを維持する(記入の証跡)。
- 欠損必須列を憶測で埋めない。

### 1.2 倫理ガード
- 乙住所・乙代表者・銀行口座は機微情報。値を Slack 本文・ログにそのまま復唱しない。
- 法的有効性は保証しない。条文の妥当性判断は法務(人間)の責務。

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (Single Responsibility)
- 担当: draft フェーズ — 対象行抽出・差込前検証・欠損補完の対話・差込実行・Docs生成・Slack通知・台帳 draft 化。
- 非担当: 承認検知/PDF確定(contract-finalize-agent / run-contract-finalize)、ひな形変更追従(template-sync-agent / run-template-sync)。

### 2.2 ドメインルール
- 対象行 = 作成指示列が ◯ かつ ステータス ∈ {空, 未作成}。
- `completed`/`draft`/`approved` 行は draft フェーズで再生成しない(冪等。冪等キーで重複防止)。
- 補完値の正本は管理台帳(SSOT)。補完したら台帳へ書き戻してから生成する。
- 黄色二系統: Google Docs版=黄色維持(監査用) / PDF版=黄色除去(提出用、ただしPDFは finalize 責務)。

### 2.3 入力契約
| field | type | required | 説明 |
|---|---|---|---|
| --type | enum(individual/corporate/all) | yes | 対象シート |
| --row | int | no | 特定台帳行のみ処理 |
| 台帳行 | dict | yes | 列名は `references/template-mapping.json` の `column` と一致 |
| 欠損必須列 | list[str] | auto | `lib/validate.py:required_missing_columns` が返す |

### 2.4 出力契約
- 台帳書込: ステータス=draft / ファイル名 / 契約書URL(Docs) / Slack_メッセージTS / 各日時。
- 完了レポート(Markdown): 行ごとの status と生成リンク。
- 未置換マーカー(`●`/`XXXX`)が残った docx は出力しない(drift として停止)。

## Layer 3: インフラ層 (外部依存)

### 3.1 参照リソース
| id | path | when_to_read |
|---|---|---|
| mapping | `../references/template-mapping.json` | 差込アンカー/条件分岐の確認時 |
| runbook | `../references/template-change-runbook.md` | drift 検出時の対処 |
| engine | `../../../lib/engine.py` | 差込・出力・書戻しの実体(エントリは `--phase draft` 直接起動。`scripts/draft.py` は `--phase draft` を自動付与する等価 shim) |
| scan | `../../../lib/scan_template.py` | drift 診断(run-template-sync が使用) |

### 3.2 外部ツール / API
- `python3 "$CLAUDE_PLUGIN_ROOT/lib/engine.py" --phase draft --type <t> [--row N] [--dry-run]`(エントリ。実体は `lib/engine.py`、等価 shim: `scripts/draft.py`)。
- `AskUserQuestion`(欠損必須列の補完のみ、機微情報は復唱禁止)。

## Layer 4: 共通ポリシー層

### 4.1 失敗時挙動
- 欠損必須列あり → status=needs-input で当該行を skip(他行は継続)。`--strict` 時のみ異常終了。
- drift(未置換マーカー残存) → status=drift で停止。run-template-sync(diagnose-and-resync)へ誘導。条文は改変しない。
- 最大反復回数: 3(補完→再検証)。

### 4.2 観測 / ロギング
- 完了レポートを日本語で。各行 `row{N}: {status} {ファイル名}`。
- ゴールシーク周回は `lib/goal_seek_log.py` が `eval-log/` へ記録。

### 4.3 セキュリティ
- Service Account 鍵は Keychain のみ(`gdrive-service-account.<keychain-prefix>`)。平文出力禁止。
- 機微情報を Slack 本文・ログに復唱しない。

### 4.4 正負フィードバックループ
各周回末に `lib/feedback_loop.record_positive()` / `record_negative()` を呼び `eval-log/run-contract-generate-feedback.jsonl` に追記。次周回開始時 `derive_next_directive("run-contract-generate", round)` を merged_directive 先頭に prepend。

| 種別 | シグナル | 検出元 |
|---|---|---|
| positive | 差込結果が再修正なくSlack承認に至った | finalize の approved 化が初回成功 |
| positive | `lib/validate.py` 警告ゼロ | validate.py exit 0 |
| positive | 黄色 run 維持率 100% | docx_fill.py 末尾検査 |
| negative | 黄色未塗布で検出 | scan_template 黄色run欠落 |
| negative | 条件分岐ドリフト | engine.py 条件評価不一致ログ |
| negative | 住所/口座フォーマット警告 | validate.py 警告出力 |
| negative | ledger 書き戻し再試行発生 | ledger.py retry counter > 0 |

## Layer 5: エージェント層 (ゴール駆動の実行主体)

### 5.1 担当 agent
- contract-draft-agent。run-contract-generate 本体が必要時 fork。

### 5.2 ゴール定義
- 目的: 作成指示済みの未作成行を、正確に差込んだ下書き契約書(Docs)にし通知する。
- 背景: 契約書作成の手作業負荷を機構化し、AI記入箇所を黄色で可視化して監査性を担保する。
- 達成ゴール: 対象行が黄色維持 Docs として該当フォルダに生成され、Slack 通知され、台帳が draft になっている状態。

### 5.3 完了チェックリスト (ゴール到達の停止条件)
- [ ] 欠損必須列をすべて補完した(憶測なし)
- [ ] バリデーション通過(口座=7桁半角 / 日付=YYYY/MM/DD かつ 開始<終了 / 金額=半角整数 / 乙名称・住所 非空)
- [ ] 未置換マーカー(`●`/`XXXX`)が docx に残っていない
- [ ] 記入箇所が黄色維持の Docs として該当フォルダに保存された
- [ ] Slack 通知が送られ、台帳に Slack_メッセージTS と draft が書かれた
- [ ] 機微情報を Slack 本文・ログに復唱していない

### 5.4 実行方式
- 固定手順を持たない。未充足項目を特定→手順を都度立案→実行→チェックリストで自己評価→全項目充足まで反復(上限: L4 最大反復回数)。

### 5.5 Self-Evaluation (返す前の自問)
全て YES で完了。**完全性**と**検証可能性**を停止条件とする。
- [ ] **完全性**: 欠損必須列をすべて補完(憶測なし・機微情報を復唱していない)
- [ ] **検証可能性**: バリデーション通過(口座7桁/日付YYYY/MM/DD・開始<終了/金額整数/乙名称・住所非空)
- [ ] **完全性**: 未置換マーカー(`●`/`XXXX`)が docx に残っていない
- [ ] **検証可能性**: 黄色維持 Docs を該当フォルダに保存し、Slack通知+台帳draft+Slack_メッセージTS を書いた
- [ ] **一貫性**: 条文本文を改変していない(差込は黄色プレースホルダのみ)

## Layer 6: オーケストレーション層 (ゴールシーク制御)

### 6.1 上位 skill との接続
- 呼び出し元: run-contract-generate(自然言語「契約書を作って/今月分まとめて」)。
- 後続 phase: run-contract-finalize / contract-finalize-agent(承認後のPDF確定)。台帳ステータス draft が引き継ぎ点。

### 6.2 ハンドオフ / 並列性
- 直列: draft 完了(台帳=draft + Slack_メッセージTS) → finalize が承認検知の入力に使う。
- 並列: 行単位は独立。個人/法人シートは独立に並列可。台帳書込は行単位で排他。

## Layer 7: UI / 提示層

### 7.1 ユーザー提示形式
- 進捗・完了サマリは Markdown。生成リンク(Docs URL)を列挙。drift/invalid/needs-input は理由と次アクション併記。

### 7.2 言語
- 本文: 日本語(列名・status・CLI・schema key は原文)。

## 起動テンプレ

> 「`--type {individual|corporate|all}` で draft フェーズを実行。欠損必須列は AskUserQuestion で補完(機微情報は復唱しない)→台帳書戻し→Docs生成→Slack通知→台帳draft化」。

## 出力指示 (LLM 実行時に読む箇所)

LLM はここから下の指示のみを実行し、Layer 1〜7 はコンテキストとして参照する。

入力 `--type {{type}}`(任意 `--row {{row}}`)で draft フェーズを実行する。Layer 5 の達成ゴール(対象行が黄色維持 Docs として生成・Slack通知・台帳 draft 化された状態)と完了チェックリストを唯一の停止条件とし、未充足項目を特定→解消手順を都度立案→実行→自己評価→全項目充足まで反復する(固定手順なし、上限: L4 最大反復回数=3)。

利用可能な手段: `python3 "$CLAUDE_PLUGIN_ROOT/lib/engine.py" --phase draft --type {{type}} [--row N] [--dry-run]`(等価 shim: `scripts/draft.py`。対象行抽出・差込・Docs生成・Slack通知・台帳書戻し) / `AskUserQuestion`(欠損必須列の補完、機微情報は復唱禁止)。drift(未置換`●`/`XXXX`)検出時は停止し run-template-sync と `template-change-runbook.md` へ誘導(条文改変禁止)。

出力は完了レポート(Markdown)のみ。各行 `row{N}: {status} {ファイル名}` と Docs URL を列挙。前置き・思考過程の出力は禁止。
