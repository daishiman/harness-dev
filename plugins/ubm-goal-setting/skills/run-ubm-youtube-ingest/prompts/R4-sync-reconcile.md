# Prompt: R4-sync-reconcile

> このファイルは 7 層プロンプトの Markdown 表現。`run-prompt-creator-7layer` の
> seven-layer-format.md を正本とする。Layer 番号と依存方向 (L1 ← L7) は不変。
> scheduler から呼ぶ冪等 one-shot で ledger と report を更新する責務プロンプト正本。

## メタ

| key | value |
|---|---|
| name | sync-reconcile |
| skill | run-ubm-youtube-ingest |
| responsibility | R4-sync-reconcile (1 prompt = 1 責務) |
| layers_covered | [L1, L2, L3, L4, L5, L6, L7] |
| output_schema | references/registry-ledger-schema.md (ledger) + references/sync-report-format.md (report) |
| reproducible | true (idempotency key=video_id・lease/retry は決定論的) |

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール
- 目的: lease/retry/alert と run 記録 (per-channel last-run watermark) を持つ冪等 one-shot (`scripts/run-youtube-sync-oneshot.py`) を host scheduler から実行し、video 状態 ledger と sync report を更新する。
- 背景: 自動同期は長時間 daemon でなく lease 付き one-shot を scheduler が呼ぶ portable 設計。新着が二重 ingest されたり一時失敗が握り潰されると reconciliation の信頼が崩れる。registry の `cursor` は増分 discovery ではなく last-run 記録で、差分性は `already_ingested` skip が担保する (discovery は毎回 pagination 完走)。

### 1.2 倫理ガード
- registry・report に秘匿情報を書かない。`waived` はユーザー承認参照 (`waiver_ref`) がある動画に限る (無承認の握り潰し禁止)。

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (Single Responsibility)
- 担当: 冪等 one-shot の実行 + ledger 状態遷移 + sync report 生成 + alert。
- 非担当: 知識抽出/graph (R3)、取得/正規化 (R2)、モード確定 (R1)。

### 2.2 ドメインルール
- **idempotency key=video_id**: 既 `ingested` を skip し同一動画を二度 ingest しない。二回目 run の ingested は0件になる。
- **retry**: `temporary_failure` の video は次 run で再取得を試み、成功で `ingested` に回復する。attempts が `--max-retries` を超えたら alert する (状態は保持)。
- **lease**: holder は invocation ごとに一意な token。取得直後に registry を atomic write して稼働中 lease を disk へ載せ、未失効 lease を別 run が持つ場合は no-op で終了する (scheduler 二重発火の多重処理防止)。run 終了時に lease を解放し、異常終了で残った lease は TTL 失効後に次 run が奪取して回復する。
- **状態集合**: `ingested`/`temporary_failure`/`terminal_unavailable`/`waived`。取得不能を ingested にしない。
- **dry-run**: `--dry-run` は registry・source-out・knowledge へ書込0 (反映予定件数は report に出すが永続化しない)。

### 2.3 入力契約
| field | type | required | 説明 |
|---|---|---|---|
| graph_status | enum | yes | R3 の PASS を前提に sync を確定する |
| dry_run | bool | yes | true 時は書込禁止 |
| channel/fixture | string | yes | 対象 handle と provider fixture (実 provider は late-bind) |

### 2.4 出力契約
| フィールド | 型 | 説明 |
|---|---|---|
| sync_report | object | discovered/ingested/temporary_failure/terminal_unavailable/waived/alerts |
| ledger_delta | object | video 状態遷移の差分 |

## Layer 3: インフラ層 (外部依存)

### 3.1 参照リソース
| id | path | when_to_read |
|---|---|---|
| ledger-schema | `$CLAUDE_PLUGIN_ROOT/skills/run-ubm-youtube-ingest/references/registry-ledger-schema.md` | registry/ledger の形と状態集合を確認するとき |
| report-format | `$CLAUDE_PLUGIN_ROOT/skills/run-ubm-youtube-ingest/references/sync-report-format.md` | sync report の形を確認するとき |

### 3.2 外部ツール / API
- `scripts/run-youtube-sync-oneshot.py` (stdlib・冪等 one-shot)。`scripts/youtube_provider.py` (取得 adapter)。

## Layer 4: 共通ポリシー層

### 4.1 共通ルールへの従属
- idempotency・lease・全量性・untrusted transcript 規範は SKILL.md `## Key Rules` が正本。本プロンプトで再定義しない。

### 4.2 失敗時挙動
- QuotaExceeded/AuthRequired: one-shot は graceful stop し stopped_reason と alert を report へ残す (exit0)。scheduler が次 cadence で再開する。
- registry 破損: one-shot は exit1。壊れた registry を上書きしない。

## Layer 5: エージェント層 (ゴール駆動の実行主体)

### 5.1 担当
- `run-ubm-youtube-ingest` 本体が Bash で one-shot を起動 (LLM 判断は不要な決定論処理)。

### 5.2 ゴール定義
- 目的: 新着が一度だけ反映され、二回目0件、一時失敗が retry で回復する冪等 sync。
- 達成ゴール: sync_report が期待件数を示し ledger が整合した状態。固定手順は書かない。

### 5.3 完了チェックリスト (停止条件)
- [ ] 新着 video が idempotency key=video_id で一度だけ ingest された
- [ ] 二回目 run の ingested が0件 (冪等)
- [ ] TemporaryFailure 後の retry run で ingested に回復した
- [ ] --dry-run が registry/source-out/knowledge へ書込0

### 5.4 実行方式
- 現状評価→手順を都度立案→実行→検証→全項目充足まで反復する。

## Layer 6: オーケストレーション層 (ゴールシーク制御)

### 6.1 上位 skill との接続
- 呼び出し元: R3-extract-graph の後続 (取込パイプラインの終端)。scheduler 経路では本 one-shot が単独 entry。
- 後続 Step: `--sync` で `sync_report.ingested>0` のとき、skill セッション経由なら同一セッションで R3-extract-graph 相当 (knowledge-extractor→C08→C06) を再実行して graph まで反映する (goal-seek 反復)。scheduler が skill 外で one-shot を直接起動する経路では正規化ソース+registry までで止まり、graph 反映は次回 skill 実行に持ち越す。
- 出力: handoff に sync_report を残す。

### 6.2 ハンドオフ / 並列性
- 直列: graph 更新 (R3 PASS) 後に ledger を確定する。lease により同一 registry への並行 run は排他。

## Layer 7: UI / 提示層

### 7.1 提示の判断基準
| 状況 | 提示 |
|------|------|
| 新着あり | ingested 件数・状態内訳を要約 |
| 冪等 (0件) | 「更新なし」を正常終了として提示 |
| stop/alert | stopped_reason と retry_exhausted 等 alert を提示 |

### 7.2 言語
- 本文: 日本語 (フィールド名・CLI 引数は英語のまま)。

---

## 出力指示 (LLM 実行時に読む箇所)

LLM はここから下の指示のみを実行し、Layer 1〜7 はコンテキストとして参照する。

`run-youtube-sync-oneshot.py` を対象 registry・channel・provider で起動し、sync_report を受け取る。新着が一度だけ ingest され二回目0件・TemporaryFailure 回復を確認し、alert (temporary_failure/quota/auth/retry_exhausted) を提示する。5.3 の完了チェックリスト充足で終了し handoff へ sync_report を残す。--dry-run 時は書込0を確認する。
