# Prompt: R3-reask

> 7 層プロンプト。未確定セルを再質問する責務。1 invocation の 5 loop 到達時は未完了状態と next_question を保存し resumable な結果を返す。未収集セルを完了扱いしない。

## メタ

| key | value |
|---|---|
| name | reask |
| skill | run-system-spec-elicit |
| responsibility | R3-reask (未確定セル再質問 + resume 保存) |
| layers_covered | [L1, L2, L3, L4, L5, L6, L7] |
| output_schema | references/spec-state-contract.md (hearing_progress) |
| reproducible | true |

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール
- 未収集セルを完了扱いしない (`complete=true` は未収集0のときだけ)。
- 5 loop (per-invocation chunk limit) 到達で未収集が残れば `complete=false`・`next_question` 非 null を保存し resumable に返す。
- 状態書込は writer の一経路のみ。

### 1.2 倫理ガード
- 未回答を勝手に確定/対象外へ埋めない。

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (Single Responsibility)
- 担当: 未確定セルの再質問と、chunk 上限到達時の状態保存 (resume)。
- 非担当: 初期化 (R1)、新規セルの一次ヒアリング設計 (R2)、reopen (R4)。

### 2.2 ドメインルール
- `next_question` は最初の未収集セル (カテゴリ順→platform 正順) の質問。writer が決定論導出する。
- 既に確定/対象外のセルは再質問対象にしない。

### 2.3 入力契約
| field | type | required | 説明 |
|---|---|---|---|
| spec_state | path | yes | 現在の spec-state.json (未収集残あり) |
| answers | turns | no | 追加回答 (resume 継続時) |

### 2.4 出力契約
- 更新後 `spec-state.json`。`hearing_progress = {loop_count, next_question, complete}`。

## Layer 3: インフラ層

### 3.1 参照リソース
| id | path | when_to_read |
|---|---|---|
| question_bank | references/elicit-question-bank.md | 再質問設計時 |
| contract | references/spec-state-contract.md | hearing_progress 形状の確認時 |

### 3.2 外部ツール
- `Bash`: `python3 scripts/apply-spec-transition.py chunk --state spec-state.json --turns <turns.json> --max-loops 5`

## Layer 4: 共通ポリシー

### 4.1 失敗時挙動
- 5 loop 到達で未達 → 未完了として保存し呼出元へ resumable に返す (次 invocation で `--resume`)。

### 4.2 最大反復
- 1 invocation 最大 5 loop。累積は invocation を跨いで継続 (状態を保存)。

### 4.3 観測
- 各 invocation 末に `validate-coverage-matrix.py` (loop) が exit0 を確認。

### 4.4 セキュリティ
- 秘匿情報を保存しない。

## Layer 5: エージェント層 (l5-contract v2.0.0)

### 5.1 担当 agent
- run-system-spec-elicit の R3 局面 (inline)。

### 5.2 ゴール定義
- 目的: 未確定セルを潰しつつ、chunk 上限で安全に中断・再開できる状態を保つ。
- 背景: 長い往復を 1 invocation で回すとコンテキストが枯渇する。per-invocation chunk limit で分割し状態を永続化する。
- 達成ゴール: 未収集0に到達するか、5 loop 到達時に `complete=false`・`next_question` 非 null で保存されている。

### 5.3 完了チェックリスト (停止条件)
- [ ] 回答済みの再質問対象セルが根拠付きで更新されている
- [ ] 未収集0なら `complete=true`・`next_question=null`
- [ ] 未収集残なら `complete=false`・`next_question` 非 null を保存 (resumable)
- [ ] 未収集セルを確定/完了扱いしていない
- [ ] `validate-coverage-matrix.py` (loop) が exit0

### 5.4 実行方式
- 固定手順を持たない。状況に応じて必要な再質問を都度設計し、5.3 の全停止条件を満たす再開可能stateを保持する。

## Layer 6: オーケストレーション

### 6.1 上位接続
- 呼び出し元: run-system-spec-elicit。前段: R2-interview。resume 時に自己継続。

### 6.2 並列性
- 逐次 (状態依存)。

## Layer 7: UI / 提示

### 7.1 提示形式
- 再開時は保存済み `next_question` を提示して継続する。

### 7.2 言語
- 日本語 (JSON キー/platform id は英語)。

---

## 出力指示

未確定セルへ再質問し、回答を turn 列にまとめて `python3 scripts/apply-spec-transition.py chunk --state spec-state.json --turns <turns.json> --max-loops 5` で反映する。5 loop 到達で未収集が残れば `hearing_progress.complete=false`・`next_question` 非 null が保存されていることを確認し、resumable に返す。未収集0なら `complete=true` を確認する。余計な前置き・思考過程出力は禁止。
