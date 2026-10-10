# プロンプト: R4-sync-reconcile

> このファイルは 7 層プロンプトの Markdown 表現。`run-prompt-creator-7layer` の
> `seven-layer-format.md` を正本とする。Layer 番号と依存方向 (L1 ← L7) は不変。
> スケジューラから呼ぶ冪等な1回きりの実行で台帳と報告を更新する責務プロンプト正本。

## メタ

| 項目 | 値 |
|---|---|
| name | `sync-reconcile` |
| skill | `run-ubm-youtube-ingest` |
| responsibility | R4-sync-reconcile (1 プロンプト = 1 責務) |
| layers_covered | [L1, L2, L3, L4, L5, L6, L7] |
| output_schema | references/registry-ledger-schema.md (台帳) + references/sync-report-format.md (報告) |
| reproducible | true (冪等キー=`video_id`・実行権の占有（lease）/再試行は決定論的) |

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール
- 目的: 実行権の占有/再試行/警告と実行記録 (チャンネルごとの最終実行の目印) を持つ冪等な1回きりの実行 (`scripts/run-youtube-sync-oneshot.py`) をホストのスケジューラから実行し、動画の状態の台帳と同期の報告を更新する。
- 背景: 自動同期は長時間動く常駐プロセスでなく、実行権の占有付きの1回きりの実行をスケジューラが呼ぶ、環境を選ばない設計。新着が二重に取り込まれたり一時失敗が握り潰されると照合の信頼が崩れる。登録簿の `cursor` は増分の洗い出しではなく最終実行の記録で、差分性は `already_ingested` による読み飛ばしが担保する (洗い出しは毎回ページ送りを完走)。

### 1.2 倫理ガード
- 登録簿・報告に秘匿情報を書かない。`waived` はユーザー承認参照 (`waiver_ref`) がある動画に限る (無承認の握り潰し禁止)。

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (単一責務)
- 担当: 冪等な1回きりの実行 + 台帳の状態遷移 + 同期の報告の生成 + 警告。
- 非担当: 知識抽出/グラフ (R3)、取得/正規化 (R2)、モード確定 (R1)。

### 2.2 ドメインルール
- **冪等キー=video_id**: 既に `ingested` の動画を飛ばし、同一動画を二度取り込まない。二回目の実行の `ingested` は0件になる。
- **再試行**: `temporary_failure` の動画は次回の実行で再取得を試み、成功で `ingested` に回復する。`attempts` が `--max-retries` を超えたら警告する (状態は保持)。
- **実行権の占有**: `holder` は起動ごとに一意なトークン。取得直後に登録簿を原子的に書き込んで稼働中の占有をディスクへ載せ、期限切れでない占有を別の実行が持つ場合は何もせずに終了する (スケジューラの二重発火による多重処理の防止)。実行の終了時に占有を解放し、異常終了で残った占有は有効期限の失効後に次回の実行が奪取して回復する。
- **状態集合**: `ingested`/`temporary_failure`/`terminal_unavailable`/`waived`。取得不能を `ingested` にしない。
- **試し実行**: `--dry-run` は登録簿・`source-out`・ナレッジへ書込0 (反映予定件数は報告に出すが永続化しない)。

### 2.3 入力契約
| フィールド | 型 | 必須 | 説明 |
|---|---|---|---|
| graph_status | enum | はい | R3 の PASS を前提に同期を確定する |
| source_out | path | はい | R1 が解決した正規化ソースの親ルート。YouTube/ を付加しない |
| dry_run | bool | はい | `true` 時は書込禁止 |
| channel/fixture | string | はい | 対象のハンドルと、取得元に読ませる検証用の入力データ (実際の取得元は後から差し込む) |

### 2.4 出力契約
| フィールド | 型 | 説明 |
|---|---|---|
| sync_report | object | discovered/ingested/temporary_failure/terminal_unavailable/waived/alerts |
| ledger_delta | object | 動画の状態遷移の差分 |

## Layer 3: インフラ層 (外部依存)

### 3.1 参照リソース
| ID | パス | 読むとき |
|---|---|---|
| `ledger-schema` | `${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/skills/run-ubm-youtube-ingest/references/registry-ledger-schema.md` | 登録簿/台帳の形と状態集合を確認するとき |
| `report-format` | `${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/skills/run-ubm-youtube-ingest/references/sync-report-format.md` | 同期の報告の形を確認するとき |

### 3.2 外部ツール / API
- `scripts/run-youtube-sync-oneshot.py` (標準ライブラリのみ・冪等な1回きりの実行)。`scripts/youtube_provider.py` (取得の接続部)。

## Layer 4: 共通ポリシー層

### 4.1 共通ルールへの従属
- 冪等性・実行権の占有・全量性・信頼できない文字起こしの規範は SKILL.md `## 守ること` が正本。本プロンプトで再定義しない。

### 4.2 失敗時挙動
- `QuotaExceeded`/`AuthRequired`: 1回きりの実行は穏当に停止し `stopped_reason` と警告を報告へ残す (終了コード 0)。スケジューラが次の周期で再開する。
- 登録簿の破損: 1回きりの実行は終了コード 1。壊れた登録簿を上書きしない。

## Layer 5: エージェント層 (ゴール駆動の実行主体)

### 5.1 担当
- 実書き込みのpreviewでは登録簿・正規化ソースに加え、登録簿と同じ場所の `<registry名>.lock` の作成・保持を保存範囲と副作用説明に含める。実行権とロックの正本は `references/registry-ledger-schema.md`。
- `run-ubm-youtube-ingest` 本体の親が中央guard executeで承認済みargvの1回きりの実行を起動 (LLM 判断は不要な決定論処理)。

### 5.2 ゴール定義
- 目的: 新着が一度だけ反映され、二回目0件、一時失敗が再試行で回復する冪等な同期。
- 達成ゴール: `sync_report` が期待件数を示し台帳が整合した状態。固定手順は書かない。

### 5.3 完了チェックリスト (停止条件)
- [ ] 新着の動画が冪等キー=`video_id` で一度だけ取り込まれた
- [ ] 二回目の実行の `ingested` が0件 (冪等)
- [ ] `TemporaryFailure` 後の再試行の実行で `ingested` に回復した
- [ ] `--dry-run` が登録簿/`source-out`/ナレッジへ書込0

### 5.4 実行方式
- 現状評価→手順を都度立案→実行→検証→全項目充足まで反復する。

## Layer 6: オーケストレーション層 (ゴールシーク制御)

### 6.1 上位スキルとの接続
- 呼び出し元: R3-extract-graph の後続 (取込パイプラインの終端)。スケジューラ経路では本1回きりの実行が単独のエントリ。
- 後続ステップ: `--sync` で `sync_report.ingested>0` のとき、スキルのセッション経由なら同一セッションで R3-extract-graph 相当 (`knowledge-extractor`→C08→C06) を再実行してグラフまで反映する (ゴールシークの反復)。スケジューラがスキルの外で1回きりの実行を直接起動する経路では正規化ソース+登録簿までで止まり、グラフへの反映は次回のスキル実行に持ち越す。
- 出力: 引き継ぎに `sync_report` を残す。

### 6.2 ハンドオフ / 並列性
- 直列: グラフ更新 (R3 PASS) 後に台帳を確定する。実行権の占有により同一登録簿への並行実行は排他。

## Layer 7: UI / 提示層

### 7.1 提示の判断基準
| 状況 | 提示 |
|------|------|
| 新着あり | `ingested` 件数・状態内訳を要約 |
| 冪等 (0件) | 「更新なし」を正常終了として提示 |
| 停止/警告 | `stopped_reason` と `retry_exhausted` 等の警告を提示 |

### 7.2 言語
- 本文: 日本語 (フィールド名・CLI 引数は英語のまま)。

---

## 出力指示 (LLM 実行時に読む箇所)

LLM はここから下の指示のみを実行し、Layer 1〜7 はコンテキストとして参照する。

スキル経由では親が `run-youtube-sync-oneshot.py` の対象登録簿・チャンネル・取得元・`--source-out "$source_out"` を含むargv全体を中央preview→ユーザー確認→authorize→executeへ渡して起動し、`sync_report` を受け取る。新着が一度だけ取り込まれ二回目0件・`TemporaryFailure` からの回復を確認し、警告 (`temporary_failure`/`quota`/`auth`/`retry_exhausted`) を提示する。5.3 の完了チェックリスト充足で終了し、引き継ぎへ `sync_report` を残す。`--dry-run` 時は書込0を確認する。独立した無人スケジューラ運用をこのスキルから直接設定・起動しない。
