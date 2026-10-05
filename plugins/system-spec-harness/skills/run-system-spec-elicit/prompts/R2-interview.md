# Prompt: R2-interview

> 7 層プロンプト。未収集セルを対象に「質問→回答→仕様反映」の往復ヒアリングで各セルを `確定`(qa_ref 付き) または `対象外+理由` へ遷移させる責務。

## メタ

| key | value |
|---|---|
| name | interview |
| skill | run-system-spec-elicit |
| responsibility | R2-interview (未収集セル → 確定/対象外) |
| layers_covered | [L1, L2, L3, L4, L5, L6, L7] |
| output_schema | references/spec-state-contract.md (spec-state.json) |
| reproducible | true |

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール
- 状態書込は writer (`scripts/apply-spec-transition.py`) の一経路のみ。直接 JSON 編集禁止。
- `確定` は `qa_ref` (qa_log entry) 必須、`対象外` は `reason` か `approval_ref` 必須。
- 確定/対象外済みセルの要件を聞き直さない (未収集セルのみ対象。セルの論点を補う問は確定前に聞き終える)。確定の後に収集ゲートが未接地の必須情報を返したときに、その item だけを補う問は聞き直しに当たらない (2.2)。

### 1.2 倫理ガード
- ユーザー回答原文を改変しない。推測を確定として書かない。
- 問は `references/neutral-question-criteria.md` の N1-N4 を満たす形で投げる。問の文面は qa_log に凍結され、後から直せない。

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (Single Responsibility)
- 担当: 未収集セルへの往復ヒアリングと writer による `確定`/`対象外` 反映。
- 非担当: 初期化 (R1)、5 loop 到達時の resume 保存 (R3)、確定の再オープン (R4)。

### 2.2 ドメインルール
- **platform 一括判断を優先**: 非対象 platform は一括承認 (approval_log) で列を `対象外` にし turn 数を圧縮する。
- 対象 platform だけ各カテゴリ要件を確定する。
- 1 turn = 質問→回答→反映。反映は writer の `chunk` / `apply` で行う。
- **問の単位は論点**: セルの要件は開いた 1 問で聞いてよく、回答に欠けた論点だけを 1 論点ずつ別の問で補う。どの turn で `confirm` し、どの qa を `qa_ref` にし、開いた問の qa を含む残りの qa をどう `add-qa-ref` で同じセルへ結ぶかは `references/elicit-question-bank.md` の手順 4 が正本。結ばない qa は required-info の接地にも章の根拠にも数えられない。
- **確定後に収集ゲートが未接地を返したとき**: reopen せず、残った item を 1 item ずつ補う問で聞き、`add-qa-ref` で確定セルへ結ぶ (`references/elicit-question-bank.md` の手順 5)。回答が確定の内容と食い違うときだけ R4-reopen へ委譲する。
- **出典 producer (要件 C5)**: 確定 (`確定`) した qa に外部技術/ツール/フレームワーク (例: React, PostgreSQL) が現れたら、その技術を `set-targets` op で `targets[]` へ反映する (`target_id` は安定 kebab-case・重複禁止・分かれば `category` も付与。同じ公式文書が別の章の判断も支えるなら、その章を `also_categories` で宣言する)。これが後段 C02 (`run-system-spec-doc-fetch`) の取得対象と C13 (`validate-source-citation.py`) の全件突合の発生源になる。
- **未知知識 producer (要件 open-world)**: ヒアリング中に既知 seed (clean-arch / DDD 等 C04 の 6 枚) に無い未知の設計領域・技術・パターンを検出したら、`set-knowledge-candidate` op で `status=discovered` として `spec-state` へ記録する (id は安定 kebab-case・`topic`・`problem`・実在 goal を指す `serves_goals` を付与)。これが open-world knowledge lifecycle の入口 (discover) で、後段の qualify/deepen/promote はこの discovered を起点に進む。

### 2.3 入力契約
| field | type | required | 説明 |
|---|---|---|---|
| spec_state | path | yes | 現在の spec-state.json |
| answers | turns | yes | ユーザー回答 (turn 列) |

各 turn の形状 (writer `chunk` が受理するキー):

| key | required | 説明 |
|---|---|---|
| `qa_id` / `question` / `answer` | yes | qa_log entry の本体 (`qa_id` が entry の `id` になる)。確定後の問答本文の変更は writer が拒否する。 |
| `ops` | 任意 | セル op の列 (`confirm` / `exclude` / `add-qa-ref` など)。`confirm` の `qa_ref` と、`qa_refs` を省いた `add-qa-ref` は turn の `qa_id` で補完される。論点が揃う前の turn は省く。 |
| `basis` | yes (確定に紐づく turn) | `user-decision` / `observed-fact` / `agent-inference` の enum。設計判断は `user-decision`、検証可能な観測は `observed-fact`、未確認の推定は `agent-inference` を正直に付ける (推定を観測と偽らない)。 |
| `required_info_items` | yes (block item を答える turn) | `references/required-info-catalog.json` の `item_id` 配列。この turn がどの必須情報を回答したかを**機械可読**に結び付ける唯一の手段で、未指定の回答はどの item も接地させない。 |
| `provenance` / `answered_at` | 任意 | 出所と回答時刻 (RFC3339・未来時刻は拒否)。 |

### 2.4 出力契約
- 更新後 `spec-state.json` (未収集セルが `確定`/`対象外` へ前進)。

## Layer 3: インフラ層

### 3.1 参照リソース
| id | path | when_to_read |
|---|---|---|
| question_bank | references/elicit-question-bank.md | 質問設計時 |
| neutral | references/neutral-question-criteria.md | 利用者への問を作るとき (N1-N4: 推奨の印なし・利点と不利な点の対称・前提を埋め込まず決めない道を残す・1 問 1 論点) |
| contract | references/spec-state-contract.md | セル/ログ形状の確認時 |

### 3.2 外部ツール
- `AskUserQuestion` / `Task`: 対話ヒアリング。
- `Bash`: セル反映 `python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/skills/run-system-spec-elicit/scripts/apply-spec-transition.py" chunk --state spec-state.json --turns <turns.json> --max-loops 5`
- `Bash`: 出典対象反映 `python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/skills/run-system-spec-elicit/scripts/apply-spec-transition.py" set-targets --state spec-state.json --targets '[{"target_id":"<id>","category":"<category_id>"}]'`
- `Bash`: 未知知識記録 `python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/skills/run-system-spec-elicit/scripts/apply-spec-transition.py" set-knowledge-candidate --state spec-state.json --candidate <candidate.json>` (`status=discovered`)

## Layer 4: 共通ポリシー

### 4.1 失敗時挙動
- 回答が「不明」→ 当該セルは `未収集` のまま残し次周へ (勝手に確定/対象外にしない)。
- 確定セルへ変更が要る場合 → R4-reopen へ委譲 (直接変更は writer が拒否)。

### 4.2 最大反復
- 1 invocation 最大 5 turn (per-invocation chunk limit)。超過は R3 が resume 保存。

### 4.3 観測
- 反映のたび `validate-coverage-matrix.py` (loop) が exit0 を確認。

### 4.4 セキュリティ
- 秘匿情報を answers / logs に格納しない。

## Layer 5: エージェント層 (l5-contract v2.0.0)

### 5.1 担当 agent
- run-system-spec-elicit の R2 局面 (inline、必要時 subagent fork)。

### 5.2 ゴール定義
- 目的: 未収集セルを、根拠 (qa_ref / reason) を伴って `確定`/`対象外` へ埋めていく。
- 背景: 網羅ヒアリングは負担が大きい。platform 一括判断と対象列の要件確定で最小 turn で前進する。
- 達成ゴール: 対象 platform の各カテゴリセルが `確定`(qa_ref 付き)、非対象が `対象外`(理由付き) になっている。

### 5.3 完了チェックリスト (停止条件)
- [ ] 非対象platformの全セルがapproval_refまたは具体的reason付きの`対象外`である
- [ ] 対象platformの回答済みセルがqa_ref付きの`確定`であり、そのセルのために記録した他の qa (開いた問の qa と補った論点の qa) が `add-qa-ref` で同じセルの `qa_refs` に結ばれている
- [ ] `確定`/`対象外` の付帯 (qa_ref / reason) が全て埋まっている
- [ ] 確定へ紐づく qa_log entry に `basis` (enum 3値) が付いている (`validate-coverage-matrix.py --require-basis` が exit0)
- [ ] `missing_effect=block` の必須情報を答えた turn に `required_info_items` が付き、`validate-knowledge-graph.py --profile required-info --state <spec-state>` の `ungrounded_blocking_items` が空である
- [ ] 確定qaに現れた外部技術/ツール/フレームワークが`set-targets`で`targets[]`へ反映されている
- [ ] seedに無い未知の設計領域/技術/パターンを検出した場合`set-knowledge-candidate`(status=discovered)で記録されている
- [ ] `validate-coverage-matrix.py` (loop) が exit0

### 5.4 実行方式
- 固定手順を持たない。状況に応じて必要な質問を都度設計し、5.3 の全停止条件を満たすstateだけをwriter経由で確定する。

## Layer 6: オーケストレーション

### 6.1 上位接続
- 呼び出し元: run-system-spec-elicit。前段: R1-init。後段: R3-reask (未達残)/R4-reopen (見直し)。

### 6.2 並列性
- turn は逐次 (状態依存)。

## Layer 7: UI / 提示

### 7.1 提示形式
- `AskUserQuestion` (4 件以内)。platform スコープ→カテゴリ要件の順で聞く。

### 7.2 言語
- 日本語 (JSON キー/platform id は英語)。

---

## 出力指示

references/elicit-question-bank.md の論点に沿って未収集セルへ質問し (問の文面は references/neutral-question-criteria.md の N1-N4 を満たす形にする。この基準が question bank より上位)、回答を turn 列にまとめて `python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/skills/run-system-spec-elicit/scripts/apply-spec-transition.py" chunk --state spec-state.json --turns <turns.json> --max-loops 5` で反映する。確定 qa に外部技術/ツール/フレームワークが現れたら `set-targets` で `targets[]` へ反映し、seed に無い未知の設計領域/技術/パターンを検出したら `set-knowledge-candidate` (status=discovered) で記録する。反映後 `validate-coverage-matrix.py` (loop) の exit0 を確認する。確定セルの変更が要るときは R4-reopen を使う。余計な前置き・思考過程出力は禁止。
