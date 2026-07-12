---
responsibility_id: R1-diagnose-and-resync
skill: run-template-sync
kind: prompt
layers_covered: [L1, L2, L3, L4, L5, L6, L7]
source: self (SSOT)
output_schema: N/A (template-mapping.json/台帳更新 + 診断レポート Markdown)
context_fork: true (理由: ひな形差分解消の試行錯誤を独立 context で。親へは最終差分のみ返す)
reproducible: true (同一ひな形・同一マッピング→同一 diff 判定)
---

# R1-diagnose-and-resync (7 層本文 SSOT 正本)

本ファイルが R1-diagnose-and-resync 責務の 7 層プロンプト本文の唯一の正本(SSOT)。実行アダプタは `../../../agents/template-sync-agent.md`。

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール
- 「ひな形が変わった」という明示意図でのみ発火する。作成フロー(draft)では発火しない。
- 条文本文は改変しない。更新対象は差込アンカー定義(`template-mapping.json`)と台帳列のみ。
- 黙って壊すより、差分を検知して報告し作り直しを促す(検知優先)。

### 1.2 倫理ガード
- 再生成フラグの一括付与は completed 行に限る。承認待ち(draft/approved)を巻き戻さない。
- ひな形の黄色 run 確認は標準ライブラリ実装(`scan_template`/`docx_lib`)で行う。テキスト表現での推測でアンカーを書き換えない。

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (Single Responsibility)
- 担当: ひな形差分診断(MISSING/UNMAPPED)・マッピング/台帳列の追従提案・影響 completed 行への再生成フラグ付与(未作成へ差し戻し)。
- 非担当: 下書き生成(contract-draft-agent / run-contract-generate)、承認/PDF 確定(contract-finalize-agent / run-contract-finalize)。

### 2.2 ドメインルール (用語集)
- **MISSING** = `template-mapping.json` の anchor がひな形側に見つからない(条文・文言が変わった)。
- **UNMAPPED** = ひな形に新しいプレースホルダ(`●`/`XXXX` 等)が増えた(新しい差込項目)。
- **再生成** = completed 行のステータスを「未作成」に戻し再生成フラグ◯を立てる(→次回 draft が拾う)。
- 差分が exit 0(整合)になるまでマッピング/台帳を更新してから再生成する。

### 2.3 入力契約
CLI は責務ごとに 2 本に分かれる(診断=`scan_template.py` / 一括+付与=`sync.py`)。`--type all` と `--apply` は `sync.py` のみ、`--docx` は `scan_template.py` のみ。

| field | type | required | 対応 CLI | 説明 |
|---|---|---|---|---|
| --type | enum | yes | 両方 | 対象ひな形/シート。scan_template=individual/corporate、sync=individual/corporate/all(既定 all) |
| --docx | path | no | scan_template のみ | ローカル .docx を診断(未指定は Drive 最新版) |
| --apply | flag | no | sync のみ | 診断後に影響 completed 行へ再生成フラグを付与 |

### 2.4 出力契約
- 診断レポート(Markdown): 黄色 run 一覧 / MISSING / UNMAPPED。
- `--apply` 時: 該当 completed 行を ステータス=未作成 + 再生成フラグ◯ に書込。
- exit: 診断 `scan_template.py` 直接実行時のみ 0=整合 / 5=drift 検出。`sync.py` は scan を集約実行するため drift もメッセージ出力のみで常に exit 0(exit code をゲートに使うなら scan_template.py を直接叩く)。

## Layer 3: インフラ層 (外部依存)

### 3.1 参照リソース
| id | path | when_to_read |
|---|---|---|
| mapping | `../../run-contract-generate/references/template-mapping.json` | 差込アンカー正本(更新対象) |
| runbook | `../../run-contract-generate/references/template-change-runbook.md` | 差分解消の手順 |
| scan | `../../../lib/scan_template.py` | 黄色 run/プレースホルダ差分検知 |
| ledger | `../../../lib/ledger.py` (`HEADERS`) | 台帳列定義(コード内 SSOT=手編集) |
| docx | `../../../lib/docx_lib.py` | docx 構造アクセス |

### 3.2 外部ツール / API
- 診断: `python3 "$CLAUDE_PLUGIN_ROOT/lib/scan_template.py" --type <t> [--docx <path>]`(MISSING/UNMAPPED 検知、exit 0=整合 / 5=drift。`--apply`/`--type all` 非対応)。
- 一括診断+付与: `python3 "$CLAUDE_PLUGIN_ROOT/skills/run-template-sync/scripts/sync.py" --type {individual|corporate|all} [--apply] [--dry-run]`(scan_template を集約呼出し。`--apply` で該当 completed 行へ再生成フラグ書込。`--docx` 非対応・drift 時も exit 0)。scan_template の等価 shim ではない(フラグ・exit 挙動が異なる)。
- Drive API: ひな形 .docx 最新版取得。Sheets API: 再生成フラグ書込。

## Layer 4: 共通ポリシー層

### 4.1 失敗時挙動
- MISSING/UNMAPPED 検出時は `--apply` を即実行せず、まずマッピング/台帳更新を案内(条文改変禁止)。
- 大改訂(条の追加/削除・章立て再編・条項番号の繰り上げを伴う変更)は anchor だけでなく `conditionals` の手修正が必要 → runbook へ誘導。

### 4.2 観測 / ロギング
- 診断レポートに黄色 run 数・MISSING/UNMAPPED の文脈を列挙。
- ゴールシーク周回は `eval-log/run-template-sync-*` に記録。

### 4.3 セキュリティ
- SA 鍵は Keychain のみ(`gdrive-service-account.<keychain-prefix>`)。平文出力禁止。
- 機微情報を含む台帳行の値は診断レポートに展開しない。

### 4.4 正負フィードバックループ
各周回末に `lib/feedback_loop.record_positive()` / `record_negative()` を呼び `eval-log/run-template-sync-feedback.jsonl` に追記。次周回開始時 `derive_next_directive("run-template-sync", round)` を merged_directive 先頭に prepend。

| 種別 | シグナル | 検出元 |
|---|---|---|
| positive | `scan_template` diff=0 で完了 | scan_template.py exit 0 |
| positive | MAPPING_DRIFT 解消 | template-mapping.json と scan_template の整合 |
| negative | MAPPING_DRIFT 再発 | scan_template.py exit 5 連続 |
| negative | UNMAPPED 列残存 | ledger.HEADERS 未追加列の検出 |
| negative | completed 行差し戻し過剰 | --apply で対象外行(draft/approved)誤巻戻し |

## Layer 5: エージェント層 (ゴール駆動の実行主体)

### 5.1 担当 agent
- template-sync-agent 本体(必要時 SubAgent に fork)。

### 5.2 ゴール定義
- 目的: ひな形変更を検知し、差込定義と台帳を追従させ、影響契約書を作り直し可能にする。
- 背景: ひな形は法務課により随時更新される。変更に「黙って壊れず」追従し再生成する運用が必要。
- 達成ゴール: ひな形と `template-mapping.json` の差分が解消(整合)し、影響 completed 行が再生成対象(未作成+再生成フラグ)になっている状態。

### 5.3 完了チェックリスト (停止条件 / Self-Evaluation)
返す前に自問する(全て YES で完了)。**完全性**と**一貫性**を停止条件とする。
- [ ] **完全性**: `scan_template`(個人/法人)で MISSING/UNMAPPED を診断した
- [ ] MISSING アンカーを新しい安定テキストに更新した
- [ ] UNMAPPED プレースホルダに対応する台帳列を追加した(`lib/ledger.py` の `HEADERS` はコード内 SSOT=手編集。scan_template は HEADERS しか見ないため、HEADERS 追加後 `ledger.py --ensure-schema` で実シートへも非破壊反映する)
- [ ] **検証可能性**: 再診断で `scan_template` が exit 0(整合)になった
- [ ] **一貫性**: `--apply` で影響 completed 行のみ 未作成+再生成フラグ◯ にした(draft/approved を巻き戻していない)
- [ ] **一貫性**: 条文本文を改変していない(更新はアンカー定義と台帳列のみ)
- [ ] **完全性**: 作成意図の入力では発火しない(description が「ひな形変更」に限定)

### 5.4 実行方式
- 固定手順を持たない。未充足項目を特定→手順を都度立案→実行→チェックリストで自己評価→全項目充足まで反復(上限: L4 最大反復回数)。

## Layer 6: オーケストレーション層 (ゴールシーク制御)

### 6.1 上位 skill との接続
- 呼び出し元: 自然言語「ひな形が変わった/テンプレ更新された」。
- 後続: contract-draft-agent / run-contract-generate(draft)が 未作成+再生成フラグ 行を作り直す。

### 6.2 ハンドオフ / 並列性
- 直列ゲート: 差分解消(再診断 exit 0=整合) → `--apply` 再生成フラグ → draft が拾う。
- 並列: 個人/法人ひな形は独立に診断可。

## Layer 7: UI / 提示層

### 7.1 ユーザー提示形式
- 診断レポート(Markdown): MISSING/UNMAPPED とその文脈、推奨アクション(マッピング/台帳更新)。

### 7.2 言語
- 本文: 日本語(列名・status・CLI・schema key は原文)。

## 起動テンプレ

> 「ユーザーが『ひな形が変わった/テンプレ更新された』と述べたとき、診断=`scan_template.py --type {individual|corporate}`(任意 `--docx PATH`)で差分診断(MISSING/UNMAPPED)→マッピング/台帳更新→再診断 exit 0 →付与=`sync.py --type {individual|corporate|all} --apply` で再生成フラグ付与」。

## 出力指示 (LLM 実行時に読む箇所)

LLM はここから下の指示のみを実行し、Layer 1〜7 はコンテキストとして参照する。

ユーザーが「ひな形が変わった/テンプレ更新された」と明示したときのみ実行する。作成意図の入力では発火しない。Layer 5 の達成ゴール(ひな形と `template-mapping.json` の差分が解消され、影響 completed 行が 未作成+再生成フラグ◯ になっている状態)と完了チェックリストを唯一の停止条件とし、未充足項目を特定→解消手順を都度立案→実行→自己評価→全項目充足まで反復する(固定手順なし、上限: L4 最大反復回数)。

利用可能な手段: 診断=`python3 "$CLAUDE_PLUGIN_ROOT/lib/scan_template.py" --type {individual|corporate} [--docx PATH]`(MISSING/UNMAPPED 差分診断、exit 0=整合 / 5=drift。`--apply`/`--type all` 非対応) / 一括診断+フラグ付与=`python3 "$CLAUDE_PLUGIN_ROOT/skills/run-template-sync/scripts/sync.py" --type {individual|corporate|all} [--apply] [--dry-run]`(影響 completed 行へ再生成フラグを書込、draft/approved は巻き戻さない。`--docx` 非対応) / `template-mapping.json` と `lib/ledger.py:HEADERS` の手編集(条文本文は改変禁止、anchor 定義と台帳列のみ更新。HEADERS へ列追加した場合は `python3 "$CLAUDE_PLUGIN_ROOT/lib/ledger.py" --ensure-schema` で実シートへ非破壊反映)。大改訂(条の追加削除・章立て再編)は `template-change-runbook.md` の手順へ誘導。

出力は診断レポート(Markdown)のみ。MISSING/UNMAPPED の文脈・推奨アクション・再診断結果を列挙、機微情報は展開しない。前置き・思考過程の出力は禁止。
