# Prompt: R0-foundation

> 7 層プロンプト。カテゴリ×プラットフォームの技術マトリクス収集 (R1-init) の**手前**で、本質的目的・背景・ゴール・目標・成功基準・具体的やりたいこと (上位概念 U1-U9) を深掘りヒアリングで抽出し、`spec-state.json` の `requirements_foundation` へ確定する責務 (要件 C9)。上位概念がブレると、仕様が整ってもブレる — ここを最初にしっかり固定し、以降の全技術決定をここへトレース (anchor) する。

## メタ

| key | value |
|---|---|
| name | elicit-foundation |
| skill | run-system-spec-elicit |
| responsibility | R0-foundation (深掘りヒアリング → requirements_foundation 確定) |
| layers_covered | [L1, L2, L3, L4, L5, L6, L7] |
| output_schema | references/spec-state-contract.md (requirements_foundation) |
| reproducible | true |

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール
- 上位概念 (U1-U9) の抽出は技術マトリクス収集 (R1-init) の**手前**で行う。上位概念が曖昧なままマトリクスへ進まない。
- `requirements_foundation` の書込は writer (`scripts/apply-spec-transition.py set-foundation`) の一経路のみ。直接 JSON 編集禁止。
- 確定 (`confirmed: true`) の条件は、U1-U9 の全項目が値または明示 N/A+理由 (`{"status":"not_applicable","reason":"..."}`) を持ち、かつ U1 `essential_purpose` / U2 `background` / U3 `goals` は値必須 (N/A 不可)、さらに U1-U9 要約をユーザーへ提示して得た承認の `approval_ref` を伴うこと。writer がこれを機械強制する。
- 確定はユーザー承認を要する: U1-U9 の要約を提示し、ユーザーの合意 (approval) を得て `approval_log` へ approval_id を記録し、その id を `approval_ref` として付けた場合に限り `confirmed: true` にする。AI の推測だけで確定しない。
- 未確定の上位概念は再質問して埋める。放置して完了扱いしない (C3 往復ヒアリングと同じ resume 規律)。

### 1.2 倫理ガード
- ユーザー発言の原文を改変しない。推測を確定として書かない (不明は空のまま `confirmed: false` で残す)。
- 表層要望 (「何を作るか」) を鵜呑みにせず、その奥の真の動機 (「なぜ」) を掘る。

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (Single Responsibility)
- 担当: 深掘りヒアリングで U1-U9 を抽出し `set-foundation` で `requirements_foundation` を確定。
- 非担当: マトリクス初期化 (R1)、セルのヒアリング (R2)、再質問 (R3)、reopen (R4)。技術選定はしない (上位概念のみ)。

### 2.2 ドメインルール — 上位概念 U1-U9 の抽出
| # | 要素 (キー) | 抽出の問い (深掘り技法) |
|---|---|---|
| U1 | essential_purpose | 「なぜこのシステムを作るのか」を **5 Whys** で表層要望の奥の真の動機まで掘る (最優先)。 |
| U2 | background | 現状のどんな課題・きっかけ・文脈から生まれたか。なぜ「今」必要か。 |
| U3 | goals `[{id,text}]` | 達成したい最終状態 (定性)。「完成したらどうなっていたいか」。 |
| U4 | objectives `[{id,text,measure}]` | ゴールを分解した測定可能な中間目標 (定量・期限)。 |
| U5 | success_criteria | どうなれば「成功」と二値判定できるか (Goodhart 回避)。 |
| U6 | stakeholders | 誰の何の課題を解決するか (**JTBD**: どんな状況で何を成し遂げたいか)。 |
| U7 | scope `{in,out}` | 何を含み何を含まないか。対象外の理由。 |
| U8 | constraints | 予算 / 期限 / 技術 / 組織 / 法規の制約。 |
| U9 | concrete_intents `[{id,text,serves}]` | 上位概念に紐づく具体寄りの「細かくやりたいこと」。各 intent は資するゴール id を `serves` に持つ (マトリクス項目の発生源)。 |

- U1 を最優先で深掘りし、U2-U8 で肉付け、U9 で具体へ降ろす。skill-intake の purpose-excavator (5 Whys / JTBD) の設計流儀を着想として借用する (機構は再利用しない)。
- `goals` の id (G1, G2, ...) は後続マトリクスセルの `serves_goals` トレース先になる。id を安定させる。

### 2.3 入力契約
| field | type | required | 説明 |
|---|---|---|---|
| spec_state | path | yes | 現在の spec-state.json (init 済み・requirements_foundation は空) |
| answers | 対話 | yes | ユーザーへの深掘りヒアリング応答 |

### 2.4 出力契約
- 更新後 `spec-state.json`。`requirements_foundation` の U1-U9 が埋まり、ユーザー承認 `approval_ref` を得られたら `confirmed: true` (U1/U2/U3 は値必須、U4-U9 は値または明示 N/A+理由)。

## Layer 3: インフラ層

### 3.1 参照リソース
| id | path | when_to_read |
|---|---|---|
| framework | $CLAUDE_PLUGIN_ROOT/docs/requirements-foundation-framework.md | 上位概念フレームワーク (U1-U9・anchor 機構) の正本を確認するとき |
| contract | references/spec-state-contract.md | requirements_foundation 形状・set-foundation 契約の確認時 |

### 3.2 外部ツール
- `AskUserQuestion` / `Task`: 深掘りヒアリング + U1-U9 要約提示による承認取得。
- `Bash`: 承認記録 `python3 scripts/apply-spec-transition.py chunk --state spec-state.json --turns <approval-turn.json>` (turn に `approval_id` を持たせ `approval_log` へ承認を記録) → 確定 `python3 scripts/apply-spec-transition.py set-foundation --state spec-state.json --foundation <foundation.json>` (foundation に承認 id を `approval_ref` として付与し `confirmed: true`)。

## Layer 4: 共通ポリシー

### 4.1 失敗時挙動
- U1/U2/U3 が値で埋まらない (N/A 不可) → `confirmed: false` のまま保存し、未確定要素を再質問する (放置しない)。
- ユーザー承認 (`approval_ref`) が未取得 → `confirmed: false` のまま保存し、U1-U9 要約を提示して承認を求める。
- 確定条件 (U1-U9 値または明示 N/A・U1-U3 値必須・approval_ref 付き) を満たさず `confirmed: true` を渡すと writer が `TransitionError`。停止して不足要素を報告 (fail-closed)。

### 4.2 最大反復
- 上位概念が確定 (U1-U3 非空 + ユーザー合意) するまで往復。各周回で未確定要素を最小化する。

### 4.3 観測
- 確定後に `$CLAUDE_PLUGIN_ROOT/scripts/validate-coverage-matrix.py --matrix spec-state.json --require-foundation` で U1-U5 非空・serves_goals トレースを検証 (anti-drift)。

### 4.4 セキュリティ
- 秘匿情報を requirements_foundation に格納しない。

## Layer 5: エージェント層 (l5-contract v2.0.0)

### 5.1 担当 agent
- run-system-spec-elicit の R0 局面 (inline、深掘りは必要時 subagent fork)。

### 5.2 ゴール定義
- 目的: 技術マトリクス収集の手前に、ブレない上位概念 (要件定義書の憲法) を確定する。
- 背景: 現設計は下位概念 (技術マトリクス) から始まるため、上位概念が無いと網羅しても「本当にやりたいこと」から乖離する (spec drift)。
- 達成ゴール: `requirements_foundation` のU1本質的目的/U2背景/U3ゴール/U4目標/U5成功基準/U6ステークホルダー/U7スコープ/U8制約/U9具体的意図が値または理由付きN/Aで確定し、`confirmed: true`かつfoundation検証がexit0の状態になっている。

### 5.3 完了チェックリスト (停止条件)
- [ ] U1-U9の各項目が値または理由付きN/Aを持つ
- [ ] U1/U2/U3が値を持つ (N/A不可)
- [ ] U1の内容が表面的手段ではなく本質的目的を表す
- [ ] U9の各intentの`serves`が実在goal idを指す
- [ ] U1-U9要約をユーザーへ提示し承認を得た`approval_ref`が`approval_log`に実在する
- [ ] `requirements_foundation.confirmed`がtrueである
- [ ] `validate-coverage-matrix.py --require-foundation` が exit0

### 5.4 実行方式
- 固定手順を持たない。状況に応じて必要な質問と確認内容を都度設計し、5.3 の全停止条件が満たされるまで上位概念を改善する。

## Layer 6: オーケストレーション

### 6.1 上位接続
- 呼び出し元: run-system-spec-elicit (開始局面・最初)。後続: R1-init (マトリクス初期化)。上位概念が確定してからマトリクスへ進む。

### 6.2 並列性
- 単発 (上位概念は 1 系統)。

## Layer 7: UI / 提示

### 7.1 提示形式
- `AskUserQuestion` (4 件以内)。U1 (なぜ) から入り、ゴール→目標→スコープの順に降ろす。抽出サマリ (U1-U9 の充足状況) を提示し、確定前に U1-U9 要約をユーザーへ提示して承認 (approval) を得る。

### 7.2 言語
- 日本語 (JSON キー/goal id は英語)。

---

## 出力指示

技術マトリクス収集 (R1-init) の手前で、5 Whys で U1 本質的目的を最優先に掘り、JTBD で U6 を掴み、U2-U9 を深掘りヒアリングで抽出する。U1-U9 の要約をユーザーへ提示して承認を得、その承認を `chunk` (turn の `approval_id`) で `approval_log` へ記録する。埋めた上位概念を `python3 scripts/apply-spec-transition.py set-foundation --state spec-state.json --foundation <foundation.json>` で確定する (U1/U2/U3 は値必須・U4-U9 は値または明示 N/A+理由・foundation に承認 id を `approval_ref` として付け `confirmed: true`)。`validate-coverage-matrix.py --require-foundation` の exit0 を確認する。承認未取得または U1/U2/U3 未確定なら再質問して埋め、放置して完了扱いしない。余計な前置き・思考過程出力は禁止。
