---
name: goal-seek-paradigm
description: harness-creator が生成する実行系 Capability の「固定手順を書かず、ゴール+チェックリストへ向かって都度手順を生成・反復する」中核パラダイムの正本定義。
kind: reference
owner: team-platform
since: 2026-05-24
source-tier: internal
---

# ゴールシーク・パラダイム（正本）

> harness-creator が生成する**ループ実行系 Capability**（run / wrap / delegate / orchestrator / agent / agent-team / hook-integrated）は、達成手順を固定で列挙しない。ユーザーへ追加ヒアリングするのではなく、AI が既存コンテキストを仮想ヒアリング結果として扱い、**最適ゴール + 目的・背景 + 完了チェックリスト** を推定する。そのうえで、チェックリストが全充足するまで「手順を都度生成して実行する」ループを回す。`assign-*` は評価系のため Goal/Checklist 形は使うが、runtime loop は配線せず一度の採点で完結する。

## なぜ固定手順を書かないか

- 固定手順は実行時の文脈（入力・環境・中間結果）を無視するため、ゴールに対して脆い。前提が崩れると手順全体が破綻する。
- ゴールとチェックリストは**到達点**を定義するので文脈に強い。手順は「いまの未達項目を埋める最短経路」としてその都度導出するのが頑健。
- これにより、生成された各 Skill / Agent / Plugin は固有タスクに対して**自律的にステップを踏んでゴールを達成**できる。
- ヒアリング前提にするとユーザー負担が増える。曖昧さは AI が最尤仮説で補い、仮定・未確定事項を成果物に残して検証ループで潰す。

## ゴール推定（ユーザー質問なし）

`goal-spec` や `{{goal}}` が未確定でも、原則としてユーザーへ質問しない。AI は次の順に情報を読み、仮想ヒアリング済みとして最適ゴールを選ぶ:

1. ユーザーの直近依頼、明示制約、禁止事項
2. 会話履歴に含まれる目的・背景・成功条件
3. 対象ファイル、関連 manifest/schema/reference、直近 diff
4. 既存の `goal-spec.json` / handoff / eval-log があればその未達項目

候補ゴールが複数ある場合は、(a) ユーザー負担最小、(b) 観測可能性、(c) 既存制約との整合、(d) 完了チェックリスト化しやすさ、の順で 1 件に絞る。根拠が弱い判断は `constraints` に仮定として残し、実行を止めるほどの不明点だけ `open_questions` または `open_issues` に記録する。

## 4 ブロック構造（実行系の `## ゴールシーク実行` 配下）

| ブロック | 役割 | 書き方 |
|---|---|---|
| **ゴール (Goal)** | 達成すべき最終状態を 1 文 | 「〜が〜の状態になっている」完了形・観測可能 |
| **目的・背景 (Why)** | なぜそのゴールか（判断のよりどころ） | 1〜3 文。手順生成時の優先順位の根拠になる |
| **完了チェックリスト (Checklist)** | ゴール達成の受入基準 | `- [ ]` 形式の**検証可能**な項目。各項目は YES/NO で判定できること |
| **ゴールシークループ (Loop)** | 反復の規約 | 下記 6 ステップ固定 (現状評価/手順生成/実行/検証/Anchor Step/反復)。これは手順ではなく**メタ手順**＝反復の枠組み |

## 適用マトリクス

| Capability | Goal/Checklist 構造 | runtime loop wiring | 扱い |
|---|---:|---:|---|
| `run` / `wrap` / `delegate` | 必須 | 必須 (default-ON) | `with-goal-seek` が `goal_seek:` と progress/intermediate 記録を注入 |
| `orchestrator` / `agent` / `agent-team` / `hook-integrated` | 必須 | 必須相当 | 専用テンプレート側で Gate / hook / SubAgent 境界として配線 |
| `assign-*` evaluator | 必須 | 対象外 | 採点網羅性を checklist で担保し、一度の read-only 採点で終了 |
| `ref-*` | 対象外 | 対象外 | 参照用。手順なし |

## ゴールシークループ（メタ手順・固定）

1. **現状評価**: チェックリストの未達 `[ ]` 項目を列挙する。全て `[x]` なら完了。
2. **手順生成**: 未達項目を満たすための手順を、その時点の文脈から**その場で立てる**（事前固定しない）。不足情報はユーザーへ聞かず、仮定を明示して進める。
3. **実行**: 立てた手順を実行する。
4. **検証**: チェックリストを再評価し、満たした項目を `[x]` に更新する。決定論的に検査できる項目は `## 検証` の script/lint へ寄せる。
5. **中間成果物スナップショット (必須・Anchor Step)**: 周回末に「中間成果物」を `eval-log/<skill>-intermediate.jsonl` へ追記する (詳細は下節「中間成果物」)。`original_goal`/`current_goal_snapshot`/`delta_from_original`/`merged_directive_for_next`/`drift_signal` を含める。Step 2 はこの直前周回の `merged_directive_for_next` と `original_goal` を**必須入力**として読む。
6. **反復 / 差し戻し**: 全 `[x]` まで 1→5 を繰り返す。規定周回（既定 5 周）を超えても未達、または `drift_signal` が `stagnant`/`widening`/`oscillating` で 2 周連続停滞した場合は、残項目と差分を `open_issues` として記録し人間 or 上位 orchestrator に差し戻す。

> ループ自体は固定で良い（これは「どう反復するか」の枠であり、「何をするか」の手順ではない）。固定してはいけないのは Step 2 の**中身**。

## コンテキスト分離（必須）

ゴールシークループの**実行は親セッションから切り離す**。ループは「手順生成→実行→検証」を複数周回するため、中間生成物・試行錯誤・周回ログが親セッションのコンテキストを肥大化・汚染する。これを防ぐため、起動側は次のいずれかで**fork されたコンテキスト**にループを閉じ込める:

- **SubAgent**（既定）: `Agent` ツールで goal-seek 実行を専用 SubAgent に委譲する。親には**最終成果物パスとハンドオフ要約だけ**を返す（周回の途中経過は SubAgent 内に留める）。
- **Agent Team**: 並列度が要る／複数の独立ゴールを同時に回す場合は Team に分離する。各 teammate が 1 ゴールを担当し、親は集約結果のみ受け取る。

| 守ること | 理由 |
|---|---|
| ループ本体を親セッションで直接回さない | 周回ごとの中間情報が親 context を汚染する |
| 親へ返すのは最終成果物 + `handoff-*.json` 要約のみ | context 肥大を防ぎ、親は結論だけ保持 |
| 周回ログ (`*-progress.json`) は fork 内で完結させ eval-log にだけ残す | 観察可能性は保ちつつ context は汚さない |

> `run-goal-seek` はこの分離を内蔵する（ループを SubAgent に fork して起動）。生成される実行系スキルがゴールシークを内部で回す場合も、同様に SubAgent / Agent Team へ切り離して起動すること。

## 実行可能機構としての配線（with-goal-seek combinator）

ゴールシークは「散文で書く」だけでなく、生成スキルに**実行可能な機構として配線**される。これにより、配布先のどの環境でも「ユーザーの悩み（要望）をゴールに変換し、達成まで自律ループを回す」挙動が同じ仕組みで再現される。

- **default-ON の対象**: loop 実行系 kind（`run` / `wrap` / `delegate`）は `render-combinators.py` が `with-goal-seek.patch` を**既定で自動適用**する（`--no-goal-seek` で opt-out）。`assign-*`（一発採点でループしない評価系）と `ref-*`（read-only）は対象外。
- **frontmatter `goal_seek:`**: 2 つの独立軸を宣言する。**(1) 外部依存軸 `engine`**（既定 `inline`＝本 Skill 内の AI 推論で自己完結・外部スキル不要／`run-goal-seek` は同梱時のみ任意で使う重量オーケストレータで必須ではない）。**(2) context 衛生軸 `fork`**（既定 `subagent`＝反復を分離 context で実行し親へ最終差分のみ返す。Claude Code 組込みの Agent/Task であり外部スキル依存ではない／`agent-team`／`inline` は軽量単発の opt-down）。加えて `spec: eval-log/goal-spec.json`（あればロード、無ければ AI が推定）/ `progress: eval-log/<skill>-progress.json` / `max_loops`（既定5）。**engine の自己完結性は with-knowledge の「外部依存ゼロ・同梱完結」原則と対称**であり、fork の分離既定は [[feedback-goalseek-session-separation]]（反復は分離 context で実行し親へ最終差分のみ）に従う。
- **`### ゴールシーク配線` サブセクション**: goal-spec のロード、周回 progress JSON 記録、コンテキスト分離、打ち切り規約を本文に明記する。
- **周回状態の契約**: 各周回の状態は `schemas/goal-seek-loop.schema.json` 準拠の `eval-log/<skill>-progress.json`（`iteration` / 各 checklist 項目 `{id,text,status}` / `open_issues` / `status`）に記録する。観測可能性をこの JSON で担保する。
- **lint 強制**: `lint-goal-seek.py` が loop 実行系に対し、(1) 二値チェックリスト項目（`- [ ]`/`- [x]`）の存在、(2) 曖昧語（「丁寧」「品質を高める」等）の不在を **violation (exit 1)** で検査し、(3) `### ゴールシーク配線` の不在を **warning** で助言する（既存スキルは次回更新時に combinator で注入）。CI は `governance-check.yml` が全生成スキルへ実行する。

> この二層（散文で意図を示し、combinator + schema + lint で機構を強制する）により、再現性は仕組みで担保しつつ、ループ Step 2 の「何をするか」は AI の自由度に委ねる。

## 中間成果物（ドリフト圧縮アンカー）

固定手順を持たないループは、放置すると AI が確率的に最尤＝**一般的に集約化された解**へ流れ、初期ユーザーゴール（具体寄りの要望）からドリフトする。これを防ぐため、**各周回の末で「中間成果物」を必ずスナップショットし、次周回の入力に必ず混ぜる**。これがアンカーとなり、初期ゴールから離れた瞬間に踏み直せる。

### 中間成果物の役割
- **アンカー**: 「最初にユーザーが求めたゴール」を不変保持し、毎周回そこへ視線を戻す。
- **差分検知**: 今周回の手順生成が向かっている「現在ゴール」と「初期ゴール」の差分を観測可能にする。
- **掛け合わせ入力**: 次周回の Step 2（手順生成）には *初期ゴール × 現在ゴール × 差分要約* を必ず入力として与える。AI が単独で再導出させない。

### 周回ごとに残す 5 要素 (+ drift_signal)
| キー | 内容 | Writer | Timing | Source |
|---|---|---|---|---|
| `original_goal` | 初期に確定した（or 推定した）ユーザーゴール。**全周回で不変**。SHA-256 を `progress.original_goal_hash` に固定し毎周回照合する。 | iteration=0 で確定 | 初回 Anchor Step | `goal-spec.json.goal` or AI推定 |
| `current_goal_snapshot` | 今周回で AI が向かっている到達点を 1 文で明示。 | ループ実行 SubAgent | Anchor Step (Step 4 検証後) | Step 2 で立てた手順の意図 |
| `delta_from_original` | `original_goal` と `current_goal_snapshot` の差分（抽象化しすぎ／論点ズレ／粒度ズレを言語化）。差分なしなら空文字。 | ループ実行 SubAgent | Anchor Step | 両ゴールの自然言語比較 |
| `merged_directive_for_next` | 差分を埋めるため次周回 Step 2 に渡す指示。「`original_goal` の具体性を保ったまま `delta` を圧縮せよ」型。 | ループ実行 SubAgent | Anchor Step | delta + original_goal |
| `drift_signal` | `initial`/`aligned`/`compressing`/`stagnant`/`widening`/`oscillating` の 6 enum。schema 必須。 | ループ実行 SubAgent (自己評価) | Anchor Step (Step 5 反復判定前) | 前周回 delta との比較 |

### 最小サンプル (intermediate.jsonl の 2 行)

```jsonl
{"iteration":0,"original_goal":"ユーザーAが特定ファイルXのバグYを修正したコミットを得る","current_goal_snapshot":"file Xの当該関数の null チェック追加","delta_from_original":"","merged_directive_for_next":"original_goal の具体性 (ユーザーA・X・Y) を全て保ったまま手順を立てよ","drift_signal":"initial"}
{"iteration":1,"original_goal":"ユーザーAが特定ファイルXのバグYを修正したコミットを得る","current_goal_snapshot":"汎用的な null 安全パターンの導入","delta_from_original":"X→汎用化 / Y→null安全パターン全般。具体性が薄れ集約化ドリフトが発生","merged_directive_for_next":"file X 限定・バグ Y のみを対象に絞り、汎用化提案は別 issue へ分離せよ","drift_signal":"widening"}
```

### iteration=0 (初期化規定)

1 周目は前周回が存在しないため特例:
- `original_goal`: `goal-spec.json.goal` をそのまま転記。無ければ AI 推定値を採用し `goal-spec.constraints` に「inferred」と記録。
- `current_goal_snapshot`: Step 2 で立てた初回手順の意図を 1 文化。
- `delta_from_original`: 空文字 (比較対象が無いため)。
- `merged_directive_for_next`: 「`original_goal` の具体性を全て保ったまま手順を立てよ」固定文。
- `drift_signal`: `initial` 固定 (前周回比較不能を明示)。
- `original_goal_hash`: SHA-256(`original_goal`) を `progress.json` トップに 1 度だけ書き、以降全周回で照合。改竄検知時は `open_issues` に `anchor_mutation` を記録して停止。

### 配線契約
- 各周回末に `eval-log/<skill>-intermediate.jsonl` へ 1 行追記（append-only ログ）。schema は `schemas/goal-seek-loop.schema.json` の `intermediate_artifacts[]`。
- 次周回 Step 2 の手順生成プロンプトは、直前の `merged_directive_for_next` と `original_goal` を**必須入力**として読み込む。読まずに新手順を立てるのは違反。
- `delta_from_original` が 2 周連続で縮まらない、または `original_goal` から逸れる方向に拡大した場合、Step 5（反復/差し戻し）でアプローチを切り替える。

### 集約化ドリフトの典型
- 「具体名 X を扱う」が「汎用パターン Y を扱う」へ抽象化されて初期意図が消える。
- ユーザー固有の制約・例外がループ内で「一般化されて」削ぎ落とされる。
- チェックリスト項目が無意識に緩和される（達成しやすい言葉に書き換わる）。

中間成果物がアンカーになる限り、上記の集約化は周回ごとに `delta_from_original` として可視化され、`merged_directive_for_next` で押し戻される。

## 達成判定 (GOAL VERIFICATION)

`drift_signal` (軌道監視) とは別軸の**達成判定**。収束停止 (全 `[x]` 宣言・ループ終了) の前に、fresh agent 1 体 — 改善履歴・score を共有しない別個体 (score 急変の独立判定 agent とも別個体) — が `original_goal` (正本 `goal-spec.json.goal`) に対し **PASS | FAIL + blocker 列挙のみ**を返す。点数出力は禁止 (score が proxy 化し Goodhart 罠へ戻るため)。

- blocker が 1 件でも残存すれば FAIL。score gate 通過でも FAIL なら **PASS 詐欺疑い**として blocker を次周回の対象に積む。
- goal アンカーの正本は `goal-spec.json.goal` / `original_goal` の単一系であり、別系の goal 宣言 (`--goal` 等) は本正本への読取 / 初期化エイリアスに限る (二重宣言禁止)。

## チェックリストの良し悪し

- **良い**: 「`eval-log/result.json` が schema 検証を通過する」「テストが全て green」「成果物が後続 skill の入力契約を満たす」— 観測可能・二値判定。
- **悪い**: 「丁寧に実装する」「品質を高める」— 判定不能。手順を埋め込んだだけの項目（「Edit で X を書く」）も不可（それは Step 2 で都度生成する手順）。

## ハンドオフ（成果物の受け渡し）

ゴール達成後、成果物を後続 Capability へ渡す。

- **汎用ハンドオフ**: `eval-log/handoff-<skill>.json`（`schemas/handoff.schema.json` 準拠）へ成果物パスと達成チェックリストを出力。後続 skill が拾う疎結合方式。
- **主要連携の明示**: 受け渡し先が確定している場合は `## ハンドオフ` 節に `次工程: <skill 名>` と入力契約を明記する。

## ref-* は対象外

`ref-*`（知識参照・read-only）は実行しないため、ゴールシーク対象外。`## 手順` は「参照用。手順なし。」のままとする。

## 評価系 (assign-*-evaluator) の扱い

evaluator は一度の採点で完結する read-only 工程。ループは回さないが、**採点の網羅性をチェックリスト**で担保する（全 rubric 項目を評価したか / findings にエビデンスがあるか / score が算出済みか）。

> **P8 整合**: 評価器（`assign-*`）は read-only 単発で**ループしない**。評価→改善の**ループ**は `feedback_contract` / content-review が回す（評価器自身ではない）。内/外ループの正本説明は `content-review-protocol.md` の「ループ分類」表を参照。

有界反復の数値正本（SSOT）は `run-elegant-review/references/convergence-policy.json` の `loop_bounds`。本ファイルの goal-seek `max_loops` 既定 5 は `loop_bounds.goal_seek_inner`（手順反復＝AI が文脈から手順を都度導出する内ループの上限）であり、content-review の inner 評価→改善 **再評価** 上限 3（`inner_loop.max_iterations`）とは**別ループ**（同名 'inner' の 3 と 5 を混同しない）。ここでは参照のみ（重複宣言しない）。

内ループ × 正フィードバック（従来の空白セル）= 小機能単位で見つけた良手順パターンは、生成スキルの `knowledge/`（Loop A, [[ref-knowledge-loop]]）へ蓄積・横展開する。

## engine 変種 (task-graph): 依存順駆動 + self-reflect

`goal_seek.engine` の値 `task-graph`（**loop kind の既定**: brief が engine を明示しない場合に defaulting される。opt-out は `engine: inline`/`run-goal-seek` の明示。独立 combinator flag は新設しない＝H5）。checklist の `depends_on`（additive・`goal-seek-loop.schema.json`）を依存充足順に消費し、実行中に発見した新規タスクを self-reflect で checklist 末尾へ追記する engine 変種。

### 単一truth設計（別状態ファイルを新設しない・H3）
task-graph 変種は **別状態ファイル（task-graph.json 相当）を一切新設せず**、既存の `eval-log/<skill>-progress.json` の checklist と `intermediate.jsonl` のみを唯一の真実源とする。

- **ready 集合の算出**: 各周回冒頭で `scripts/ready-set-from-checklist.py <progress.json>` が `depends_on` 全充足かつ `status==pending` の item を id 昇順（`^C[0-9]+$` は数値昇順）で `{"ready":[...]}` として返す。base ループ Step1「未達 `[ ]` を任意特定」を **task-graph 変種に限り**「ready 集合の**最小 id item のみ**を拘束的に選択・実行」へ上書き置換する（`inline` は従来どおり任意選択）。これにより依存順序保証が「助言」でなく「拘束」になる。
- **self-reflect 追記**: 発見した新規タスクは `scripts/self-reflect-append.py <progress.json> --id <新id> --text <達成条件> --depends-on <...>` で checklist 末尾へ追記する。追記 item は done-judge が毎回スキャンする**同じ checklist 配列**の一部になるため「発見したが完了判定に反映されない」非統合が構造的に発生しない。追記は既存 item を一切書き換えず（新規シンク）、id 重複・未知 depends_on・追記後サイクルを fail-closed 検査する。
- **consumption verifier**: 各周回末に `intermediate.jsonl` へ `ready_set`（算出時点の ready）と `selected_item`（実際に選択した id）を additive 追記し、ループ完了時に「毎周回 `selected_item` が `ready_set` の最小 id と一致＝依存順消費」と「self-reflect 追記 item が `status==done` まで全体 done 判定を gate」を機械検査する（`references/goal-seek-paradigm.md` 中間成果物アンカー検査と同型）。
- **done 記述＝発火条件**: item 完了は progress.json の該当 item への `status: done` 記述で確定し、その記述自体が次周回 ready 再計算の入力＝次 item の発火条件になる（完了記述→ready 再計算→次 item 発火の連鎖）。
- **max_loops の bound 連動**: 1 周回 1 item 消費×消費完全性の拘束下では done 化 item 数 ≤ max_loops。よって `goal_seek.max_loops` は checklist item 数＋self-reflect 追記余裕以上（目安: item 数×1.5）に設定する。不足は completed を構造的に不能にするため、consumption verifier が bound 不足を早期診断し、max_loops 到達時は handed_off で上位が bound を引き上げて再入する。

### write_scope 並列衝突機構は不要（H1）
本 engine 変種は生成ハーネス内の**単一 self-writer プロセスが逐次一つずつ** checklist を処理するため、同時に複数 writer が同一資源を奪い合う状況が構造的に発生しない。ゆえに `ready-set-from-checklist.py` は write_scope フィールド・tie-break・conflicts 機構を**持たない**。

### 既存 compute-ready-set.py の正しい再framing（H2・バグではない）
`plugins/plugin-dev-planner/skills/run-plugin-dev-plan/scripts/compute-ready-set.py` の write_scope tie-break（同一 write_scope の ready 候補を id 昇順で 1 件のみ許可し残りを deferred/conflicts へ回す・docstring L16-27、実装 L90-109）は「全除外バグ」ではなく、**複数 candidate が同時に ready になり得る並列/多ノード dispatch モデルを前提とした意図的な fail-closed 回避設計**である。build-pipeline task-graph（producer/consumer 分離・並列 dispatch）ではこの tie-break が正しく機能する。本 engine:task-graph 変種は逐次単一 self-writer ゆえこの前提が構造的に成立せず、同型 tie-break を**複製しない**（H1 と同根）。両者は別概念であり本変種は build-pipeline task-graph を一切改変しない。

### cross-surface dependency graph knowledge（H6）
実行順序の状態源（checklist）とは別レイヤの派生 knowledge として、`scripts/extract-capability-dependency-graph.py` が生成 harness の skill/command/agent/hook/script surface 間依存を抽出（nodes/edges/gaps・未知参照/循環/空 graph は fail-closed）し、`scripts/record-capability-graph-knowledge.py` が Loop A（生成 harness）/Loop B（harness-creator）へ `source_ref` 付き entry を append/merge 記録する。各 surface は着手前にこの knowledge を consult し、依存先が未完成/dangling の surface を先に着手しない。この graph は「どの surface がどの前提知識・成果物に依存するか」の派生情報であり、別 `task-graph.json` 状態を新設しないため単一truth原則と矛盾しない。
