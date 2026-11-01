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
- `requirements_foundation` の書込は writer (`scripts/apply-spec-transition.py set-foundation`) の一経路のみ。直接 JSON 編集禁止。各 source-index の question は binding 対象の `U<N>` を明記し、確定済み U の値変更では新しい `qa_ref` / `approval_ref` とトップレベル `approval_ref` を同時更新する。旧証拠を残した値だけの変更は writer が拒否する。
- 確定 (`confirmed: true`) の条件は、U1-U9 の全項目が値または明示 N/A+理由 (`{"status":"not_applicable","reason":"..."}`) を持ち、かつ U1 `essential_purpose` / U2 `background` / U3 `goals` は値必須 (N/A 不可)、U1-U9 ごとの一論点の現行根拠を `effective_source_refs.U<N>.{qa_ref,approval_ref}` で指し、さらに U1-U9 要約をユーザーへ提示して得た承認の `approval_ref` を伴うこと。writer が参照先の実在・一意性・利用者一次入力の `source.kind`・承認との整合を機械強制する。既定の schema 1.0 で `effective_source_refs` を省いた state だけは canonical `qa-foundation-u1`〜`u9` を根拠として読む (fallback)。`--schema-version 1.1` で opt-in した confirmed state は全9件の `effective_source_refs` が必須である。
- **根拠を記録してから確定する**: `set-foundation` に `confirmed: true` を渡す前に、U1-U9 の根拠 QA (初回は canonical `qa-foundation-u1`〜`u9`) を `chunk` の turn (`qa_id` 指定・`source` 付き) で `qa_log` へ、U1-U9 要約への承認を turn の `approval_id` で `approval_log` へ記録しておく。根拠 QA または承認が欠けていれば writer は確定を拒否する。
- 確定はユーザー承認を要する: U1-U9 の要約を提示し、ユーザーの合意 (approval) を得て `approval_log` へ approval_id を記録し、その id を `approval_ref` として付けた場合に限り `confirmed: true` にする。AI の推測だけで確定しない。
- 書面に同等の承認が明記されていればその逐語証跡を使えるが、AI が書面を要約したこと自体を承認に代用しない。新しい利用者入力が無いときは AI 自身を承認者とする新規 approval を作らない。
- `requirements-brief.md` など利用者が渡した**書面要件**は、対話回答と同じ一次入力である。ただしファイルを読んで foundation へ直接代入してはならない。U1-U9 ごとに 1論点の `qa_log` source-index を `chunk` の `{"qa_id":"qa-foundation-uN","question":"書面入力 <relative-path> §<section> の U<N> は何か","answer":"<指定 section に実在する逐語原文>","source":{"kind":"written-requirements","path":"<relative-path>","section":"§<section>","sha256":"<sha256(answer UTF-8 bytes)>"},"ops":[]}` として追記する。質問に入力 path/section、回答に指定 section の逐語原文、`source.sha256` にその answer の UTF-8 SHA-256 を残す。AI 要約・判断・entry 自身の digest を一次根拠にしない。対話入力でも `source:{"kind":"user-dialogue"}` を付けた同 id の entry を残す。
- 未確定の上位概念は再質問して埋める。放置して完了扱いしない (C3 往復ヒアリングと同じ resume 規律)。

### 1.2 倫理ガード
- ユーザー発言の原文を改変しない。推測を確定として書かない (不明は空のまま `confirmed: false` で残す)。
- 表層要望 (「何を作るか」) を鵜呑みにせず、その奥の真の動機 (「なぜ」) を掘る。
- 深掘りの問も `references/neutral-question-criteria.md` の N1-N4 に従う。AI が推測した動機や背景を前提として問に書き込まない (N3)。U1-U9 は R6 の軸 5 で「ユーザー発言へ遡れるか」を監査される。

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
- **承認を求める問の逐語保全**: 問の中立性は `references/neutral-question-criteria.md` の N1-N4 が正本である。上位概念の承認では、それに加えて生の質問文・全選択肢・提示順序を `approval_log` に逐語で残す。上位概念は下位の全決定のトレース先になるため、ここでの偏りは仕様全体へ波及する。
- **上位概念の逐語保全**: `requirements_foundation` の値を後から書き換えるときは、承認済みの canonical entry (`qa-foundation-u1`〜`u9`) を初回確定の履歴として改変せず、変更を新しい 1論点 entry + approval として追記する。そのうえで変更対象 U の `effective_source_refs` だけを新しい `qa_ref` / `approval_ref` へ `set-foundation` で更新する。canonical は履歴の SSOT、effective は現行値の SSOT であり、両者を同一視しない。AI が概念文書や設計都合へ寄せて goals / objectives を書き換えることは、利用者の承認を経ない限り認めない。書き換えの承認を得る際は、旧値と新値を対称に併記し、どちらの選択肢も先頭に固定しない。
- **共有 QA の境界**: 原則は U ごとの 1論点索引である。ただし 1 回の中立再確認で複数 U を同時に扱い、answer に U ごとに分離可能な利用者決定が逐語で残る場合は、同じ `qa_ref` を指す **明示的な共有 binding** を許可する。機械ゲートは `qa_ref` ごとの binding U 集合を作り、(1) question の **共有対象の全 U marker** がその集合と exact match、(2) 各 binding が consumer 別の `evidence_quote` と `evidence_sha256` を持ち、quote が共有 QA answer 内に完全一致し、hash が quote の UTF-8 bytes と一致、(3) consumer 間の quote が同一または包含関係でない、(4) 各 binding の `approval_ref` が同一、を決定論的に強制する。answer 全体の他 U 言及は binding 範囲を広げず、qa_ref の一致だけを重複違反にしない。対象 marker 欠落、question の対象外 marker、quote 欠落/改変/hash 不一致/流用は機械層で拒否する。一方、quote が対象 U の現行値を意味的に裏付けるか、AI 要約でなく利用者の逐語決定かは機械層だけでは判別できないため、C06 が question / answer / approval / consumer 別 quote の生証跡を意味監査する。

### 2.3 入力契約
| field | type | required | 説明 |
|---|---|---|---|
| spec_state | path | yes | 現在の spec-state.json (`bootstrap` 済み・matrix 未初期化・requirements_foundation は空) |
| answers | 対話または利用者の書面要件 | yes | 深掘りヒアリング応答。書面入力なら U1-U9 の 1論点 source-index を先に残す。 |

### 2.4 出力契約
- 更新後 `spec-state.json`。`requirements_foundation` の U1-U9 が埋まり、各 U が `effective_source_refs.U<N>` が指す 1論点 `qa_log` entry と `approval_log` entry (schema 1.0 で `effective_source_refs` を省いた場合は canonical `qa-foundation-uN`) へ遡及できたら `confirmed: true` (U1/U2/U3 は値必須、U4-U9 は値または明示 N/A+理由)。canonical `qa-foundation-u1`〜`u9` は初回履歴として保持する。

## Layer 3: インフラ層

### 3.1 参照リソース
| id | path | when_to_read |
|---|---|---|
| framework | ${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/docs/requirements-foundation-framework.md | 上位概念フレームワーク (U1-U9・anchor 機構) の正本を確認するとき |
| contract | references/spec-state-contract.md | requirements_foundation 形状・set-foundation 契約の確認時 |
| neutral | references/neutral-question-criteria.md | 利用者への問を作るとき (N1-N4: 推奨の印なし・利点と不利な点の対称・前提を埋め込まず決めない道を残す・1 問 1 論点) |

### 3.2 外部ツール
- `AskUserQuestion` / `Task`: 深掘りヒアリング + U1-U9 要約提示による承認取得。
- `Bash`: source-index または承認記録 `python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/skills/run-system-spec-elicit/scripts/apply-spec-transition.py" chunk --state spec-state.json --turns <turns.json>` (`ops: []` でも qa_log 追記は有効。turn の `source` も保持され、`approval_id` を持たせれば `approval_log` も記録) → 確定 `python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/skills/run-system-spec-elicit/scripts/apply-spec-transition.py" set-foundation --state spec-state.json --foundation <foundation.json>` (foundation に承認 id を `approval_ref` として付与し `confirmed: true`)。

## Layer 4: 共通ポリシー

### 4.1 失敗時挙動
- U1/U2/U3 が値で埋まらない (N/A 不可) → `confirmed: false` のまま保存し、未確定要素を再質問する (放置しない)。
- ユーザー承認 (`approval_ref`) が未取得 → `confirmed: false` のまま保存し、U1-U9 要約を提示して承認を求める。
- 確定条件 (U1-U9 値または明示 N/A・U1-U3 値必須・U1-U9 source-index・approval_ref 付き) を満たさず `confirmed: true` を渡すと writer が `TransitionError`。停止して不足要素を報告 (fail-closed)。

### 4.2 最大反復
- 上位概念が確定 (U1-U3 非空 + ユーザー合意) するまで往復。各周回で未確定要素を最小化する。

### 4.3 観測
- 確定後に `python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/validate-coverage-matrix.py" --matrix spec-state.json --require-foundation` で U1-U5 非空・serves_goals トレースを検証 (anti-drift)。

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
- [ ] U1-U9 の各現行値が `effective_source_refs.U<N>.qa_ref` の 1論点 qa_log entry と `.approval_ref` の承認へ遡及できる。書面要件は入力 path/section・原文 SHA-256、対話は `source.kind=user-dialogue` を持つ。
- [ ] `requirements_foundation.confirmed`がtrueである
- [ ] `validate-coverage-matrix.py --require-foundation` が exit0
- [ ] 選択式の質問が N1-N4 を満たし、質問文・全選択肢・提示順序が approval_log に逐語で残っている
- [ ] 既存 foundation を書き換える場合、canonical entry の逐語が履歴として未改変で、変更が分離索引 entry + 新しい approval + 対象 U の `effective_source_refs` 更新として記録されている

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
- 選択式の問は `references/neutral-question-criteria.md` の N1-N4 に従い、選択肢の並び順は AI の選好から独立した決定論的規則で決める。

### 7.2 言語
- 日本語 (JSON キー/goal id は英語)。

---

## 出力指示

技術マトリクス収集 (R1-init) の手前で、5 Whys で U1 本質的目的を最優先に掘り、JTBD で U6 を掴み、U2-U9 を 1論点ずつ深掘りヒアリングで抽出する。初回は canonical `qa-foundation-u1`〜`qa-foundation-u9` を履歴として記録し、各 U の `effective_source_refs` をその QA/approval へ結ぶ。更新時は canonical 履歴を改変せず、新しい QA/approval を追記し対象 U の effective binding だけを更新する。書面は path/section・逐語 `answer`・`source.kind=written-requirements`・`source.sha256`、対話は `source.kind=user-dialogue` を使い、AI 要約を一次根拠にしない。U1-U9 の要約をユーザーへ提示して承認を得、その承認を `chunk` (turn の `approval_id`) で `approval_log` へ記録する。新しい利用者入力なしに新規 approval を作らない。埋めた上位概念を `python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/skills/run-system-spec-elicit/scripts/apply-spec-transition.py" set-foundation --state spec-state.json --foundation <foundation.json>` で確定する (U1/U2/U3 は値必須・U4-U9 は値または明示 N/A+理由・全 U の `effective_source_refs`・現行 `approval_ref`・`confirmed: true`)。`validate-coverage-matrix.py --require-foundation` の exit0 を確認する。承認未取得または U1/U2/U3 未確定なら再質問して埋め、放置して完了扱いしない。再確認では旧値と新値を対称提示し、質問文・全選択肢・提示順序を逐語で残す。余計な前置き・思考過程出力は禁止。
