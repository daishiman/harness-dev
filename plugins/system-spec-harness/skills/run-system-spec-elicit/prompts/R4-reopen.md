# Prompt: R4-reopen

> 7 層プロンプト。確定済みセルを根拠付きで再オープンし追加質問サイクルへ戻す責務。再オープン経由でない確定セルの直接変更は writer (および C11 hook) が遮断する。

## メタ

| key | value |
|---|---|
| name | reopen |
| skill | run-system-spec-elicit |
| responsibility | R4-reopen (確定セル → 未収集 再ヒアリング) |
| layers_covered | [L1, L2, L3, L4, L5, L6, L7] |
| output_schema | references/spec-state-contract.md (reopen_log) |
| reproducible | true |

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール
- `確定` セルの状態を動かせるのは `action=reopen` (要 `reason` と `reopened_at`) だけ。
- `reopened_at` は `date -u +%Y-%m-%dT%H:%M:%SZ` の実測値を渡す。未来値は writer が拒否する。
  時刻が無いと「差し替え後の主根拠がこの reopen より後に取り直された回答か」を検査できず、
  先に確定を壊してから既存の回答を主根拠に流用した場合と正当な取り直しが同じ見た目になる。
- reopen 非経由の `確定`→`未収集`/`対象外` 直接変更は writer が `TransitionError` で拒否する (C11 hook も遮断)。
- reopen は当該セルを `未収集` へ戻し `reopen_log` に根拠を残す。

### 1.2 倫理ガード
- 根拠 (reason) なき再オープンをしない。確定を無断で消さない。

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (Single Responsibility)
- 担当: 確定済みセルの根拠付き再オープンと追加質問サイクルへの差し戻し。
- 非担当: 初期化 (R1)、一次ヒアリング (R2)、resume 保存 (R3)。

### 2.2 ドメインルール
- reopen 後のセルは `未収集`。以後 R2/R3 の対象に戻る。
- 再オープンは影響カテゴリ集約を writer が真理値表で再計算 (`確定`→`収集中` 等)。
- **誘導の疑いがある問が主根拠のとき**: 確定セルの `qa_ref` の問が N1-N4 (`references/neutral-question-criteria.md`) に違反していたら、reopen → 同じ論点を中立に問い直して回答を取り直す → 新しい qa で再確定 → `supersede-qa` op (`{"action":"supersede-qa","qa_id":"<旧>","superseded_by":"<新>","superseded_at":"<実測値>","note":"<旧い問のどの基準の違反を、どう問い直したか>"}`) で旧 entry に置き換えを記録する。旧 entry が主根拠のままでは writer が `supersede-qa` を拒否し、置き換え済みの entry を主根拠に戻す `confirm` も拒否する。
- **再確定で参照を結び直す**: reopen はセルを `{state, reopened_from, reopen_reason}` で置き換えるので、`qa_ref`・`qa_refs`・`serves_goals` が落ち、reopen 後の state からは読めない。reopen の前に対象セルのこれらの値を控える。再確定の turn では、(a) 前提が崩れた後も裏付けとして有効な旧参照 (旧 `qa_ref` と `qa_refs`。置き換えた entry は除く) を `confirm` に続く `add-qa-ref` で結び直し、(b) `serves_goals` を `confirm` に同時付与するか `set-serves` で付け直す。再確定が invocation をまたいでも同じである (未結の qa の拾い方は `references/elicit-question-bank.md` の手順 4)。結び直さない qa は required-info の接地にも章の根拠にも数えられず、`serves_goals` の無い確定セルは `--require-foundation` で落ちる。
- **裏付けの問を置き換えるとき**: 誘導の疑いがある問が `qa_refs` 側だけにあるなら reopen は要らない (writer は主根拠でない entry の `supersede-qa` を通す)。同じ論点を中立に問い直して回答を取り直し、`supersede-qa` で置き換えを記録し、新しい qa を `add-qa-ref` で同じセルへ結ぶ。旧 entry は `qa_refs` に残してよい (compile が旧版の印付きで描く)。

### 2.3 入力契約
| field | type | required | 説明 |
|---|---|---|---|
| spec_state | path | yes | 現在の spec-state.json |
| target_cell | {category, platform} | yes | 再オープン対象の確定セル |
| reason | string | yes | 再検討の根拠 |

### 2.4 出力契約
- 更新後 `spec-state.json` (対象セル `未収集`、`reopen_log` に entry 追加)。

## Layer 3: インフラ層

### 3.1 参照リソース
| id | path | when_to_read |
|---|---|---|
| contract | references/spec-state-contract.md | reopen 契約/ログ形状の確認時 |
| question_bank | references/elicit-question-bank.md | 追加質問設計時 |
| neutral | references/neutral-question-criteria.md | 利用者への問を作るとき (N1-N4: 推奨の印なし・利点と不利な点の対称・前提を埋め込まず決めない道を残す・1 問 1 論点) |

### 3.2 外部ツール
- `Bash`: `python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/skills/run-system-spec-elicit/scripts/apply-spec-transition.py" apply --state spec-state.json --op '{"action":"reopen","category":"<c>","platform":"<p>","reason":"<why>","reopened_at":"<date -u +%Y-%m-%dT%H:%M:%SZ の実測値>"}'`

## Layer 4: 共通ポリシー

### 4.1 失敗時挙動
- 対象が `確定` でない → writer が拒否。対象セル状態を確認して停止 (fail-closed)。
- reason 欠落 → writer が拒否。

### 4.2 最大反復
- 再オープンは根拠ごとに単発。連鎖再オープンは根拠を都度記録。

### 4.3 観測
- reopen 後 `validate-coverage-matrix.py` (loop) が exit0 を確認 (集約が真理値表一致)。

### 4.4 セキュリティ
- reopen_log に秘匿情報を残さない。

## Layer 5: エージェント層 (l5-contract v2.0.0)

### 5.1 担当 agent
- run-system-spec-elicit の R4 局面 (inline)。

### 5.2 ゴール定義
- 目的: 前提が崩れた確定要件を、監査可能な根拠付きで安全に再検討へ戻す。
- 背景: 確定の無断巻き戻しは仕様の信頼を毀損する。reopen 経路に一本化し reopen_log で追跡する。
- 達成ゴール: 対象セルが根拠付きで `未収集` に戻り、集約が真理値表と一致し、再ヒアリング対象になっている。

### 5.3 完了チェックリスト (停止条件)
- [ ] reopen対象の直前状態が`確定`である
- [ ] reopen 前の対象セルの `qa_ref`・`qa_refs`・`serves_goals` を控え、再確定する R2/R3 へ渡している
- [ ] reopen後の対象状態がreason付きの`未収集`である
- [ ] `reopen_log` に根拠 entry が残っている (`reason` と実測 `reopened_at` を伴う)
- [ ] 影響カテゴリの `category_aggregate` が真理値表と一致する
- [ ] `validate-coverage-matrix.py` (loop) が exit0

### 5.4 実行方式
- 固定手順を持たない。状況に応じて必要な再検討内容を都度設計し、5.3 の全停止条件を満たす場合だけR2/R3へ差し戻す。

## Layer 6: オーケストレーション

### 6.1 上位接続
- 呼び出し元: run-system-spec-elicit。後段: R2-interview / R3-reask (再ヒアリング)。

### 6.2 並列性
- 単発 (状態依存)。

## Layer 7: UI / 提示

### 7.1 提示形式
- 再オープン理由と対象セルを明示して提示する。

### 7.2 言語
- 日本語 (JSON キー/platform id は英語)。

---

## 出力指示

再検討の根拠を確認し、`python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/skills/run-system-spec-elicit/scripts/apply-spec-transition.py" apply --state spec-state.json --op '{"action":"reopen",...,"reason":"...","reopened_at":"<実測 RFC3339>"}'` で対象確定セルを `未収集` へ戻す。`reopen_log` の追記と `validate-coverage-matrix.py` (loop) の exit0 を確認し、R2/R3 へ差し戻す。確定の直接変更 (reopen 非経由) は writer が拒否する。余計な前置き・思考過程出力は禁止。
