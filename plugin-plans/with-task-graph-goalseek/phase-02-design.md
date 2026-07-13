---
id: P02
phase_number: 2
phase_name: design
category: 設計
prev_phase: 1
next_phase: 3
status: 未実施
gate_type: none
entities_covered: [C01, C02, C03, C04, C05, C06, C07, C08]
applicability:
  applicable: true
  reason: 
---

# P02 — design (設計)

## 目的
8 component(C01-C08)への分解を確定し、【単一truth】設計(H3 解消)・逐次単一 self-writer ゆえ write_scope 並列衝突機構が不要であること(H1 解消)・既存 compute-ready-set tie-break の正しい再framing(H2 解消)・consumption verifier の機械検査設計(H4 解消)・default/opt-in 軸を engine 選択として確定すること(H5 解消)・生成 harness の skill/slash-command/sub-agent/script 横断 dependency graph knowledge の抽出/記録/利用検査(H6 追加)を明文化する。

## 背景
既存 build-pipeline(`plugin-plans/harness-creator/`)の task-graph は producer(plugin-dev-planner)/ consumer(capability-build)の片方向 writer 2 プラグイン分離を採る。理由は(1)別プロセス別タイミングでの書込衝突回避(2)監査可能性(3)責務分離(4)並列 dispatch 時の race 回避、の 4 点である。本 plan の with-goal-seek engine:task-graph 変種は「1 ハーネスが自分の checklist を唯一の真実源として逐次読み書きする」自己完結系であり、上記 4 理由のいずれも本質的に発生しない(別プロセスも別プラグインも並列 dispatch も存在しない)。

## 前提条件
Phase01 で確定した要件(goal-spec checklist C1-C12)が本 phase の入力である。

## ドメイン知識
(引用+差分)単一 self-writer = 1 プロセス内で checklist(progress.json)を読み書きする主体が常に 1 つであることの設計保証。ready 集合 = depends_on が全充足(status==done)の pending item 集合を id 昇順で決定論算出したもの。

## 成果物
8 component(C01-C08)への分解を確定する。

### H1 解消: write_scope 並列衝突機構は不要(旧 A1 設計論点(b)の retract)
旧 A1 設計は compute-ready-set 相当の機構へ write_scope tie-break(同一 write_scope を持つ ready 候補が複数あるとき node id 昇順で 1 件のみ許可する直列化)を実装する設計論点(b)を持っていたが、これは**死機構**である。理由: 本機構(C01 ready-set-from-checklist.py)が対象とする checklist は、生成ハーネス内の**単一の self-writer プロセスが逐次一つずつ**処理するのみであり、同時に複数の writer が同一 write_scope を奪い合う状況が構造的に発生しない。tie-break が意味を持つのは「同時に複数の candidate が ready になり得る並列 dispatch」を前提とするケースのみであり、逐次単一 self-writer には該当しない。よって旧 A1 の「設計論点(b) write_scope 直列化によるデッドロック回避」は本設計から**撤回**し、C01 は write_scope フィールド自体を持たない最小スクリプトとして新設する(H1 解消の実装箇所: `component-inventory.json` C01.purpose/derivation、本節)。

### H2 解消: 既存 compute-ready-set.py の正しい再framing(バグ扱いの撤回)
既存 `plugins/plugin-dev-planner/skills/run-plugin-dev-plan/scripts/compute-ready-set.py` は「全除外バグ」ではない。同ファイルを直接確認した結果、現行実装は以下の 3 段ステートレス決定論アルゴリズムである:
1. `state==blocked` の node を除外する。
2. candidate = `state!=done` かつ全 `depends_on` 先が `state==done` かつ全 `consumes` 先の producing node の `write_scope` が `os.path.exists` である node。
3. candidate を `write_scope` でグルーピングし、id 昇順で先頭を `winner_by_scope[ws]` として採用、以降を `deferred` とし `conflicts` へペア記録する。`ready = candidates - deferred`。

この tie-break 実装はモジュール docstring(L16-27)が明言する通り「fail-closed 全除外(ready 0 件デッドロック)を避けるため」に設計された、**複数 candidate が同時に ready になり得る並列/多ノード dispatch モデルを前提とする意図的機構**である(実装本体は L90-109)。これは「バグ」ではなく正しく機能している設計であり、本 plan はこれを「バグだった」と誤って主張しない。ただし本 plan の C01(ready-set-from-checklist.py)は、逐次単一 self-writer が checklist を一つずつ処理する構造上、同時に複数 candidate が ready 集合に並存して write_scope 衝突を起こす状況が原理的に発生しないため、この tie-break 機構自体が**構造的に不要**であり複製しない(H1 と同根)。この対比は `component-inventory.json` C01.derivation に file:line 引用付きで記載し、本節がその一次情報源である(H2 解消の実装箇所: 本節、C01.derivation)。

### H3 解消: 単一truth設計による self-reflect 完了gate の構造的保証
self-reflect(C02 self-reflect-append.py)は、実行中に発見した新規タスクを**別状態ファイル(task-graph.json 相当)を新設せず**、既存 with-goal-seek の checklist(progress.json)の末尾へ新しい item として追記する。この設計により、discovered task は追記された瞬間から done-judge(周回終了判定)が毎回スキャンする**その同じ checklist 配列**の一部になる。よって「発見はしたが completion 判定に反映されない」という非統合(H3 が指摘した問題)は構造的に発生しない — 別グラフを持たない以上、反映漏れという状態そのものが存在し得ない。追記は「新しい item の追加」のみを行い既存 item の depends_on やstatus を書き換えないため、追記ノードは常に DAG 上の新規シンクとなり構造的にサイクルを生まないが、念のため C02 は id 重複・未知 depends_on 参照・追記後サイクルを fail-closed 検査する(H3 解消の実装箇所: `component-inventory.json` C02.purpose/derivation、本節)。

### H4 解消: consumption verifier(depends_on 消費 + self-reflect 完了gate の機械検査)
`plugins/harness-creator/skills/run-build-skill/scripts/render-combinators.py` の `GOAL_SEEK_WIRING_SECTION`(L203-263)は、既存 with-goal-seek の生成 SKILL.md へ intermediate.jsonl アンカー整合性を検査する bash/heredoc ブロックを埋め込んでいる。本設計はこれと**同型**の consumption verifier を task-graph 変種向けに追加する。

**前提(Step1 置換の拘束化)**: 既存 base ループアンカーの Step1 は engine 非依存の「未達 `[ ]` を任意に特定」であり、これは inline engine では自由選択で正しいが、task-graph 変種では**依存順序保証を助言に留めてしまう**。よって engine==task-graph 分岐に限り、この Step1 を「各周回で C01(ready-set-from-checklist.py)を実行し、返った ready 集合の**最小 id item のみ**を次の実行対象として選ぶ」拘束的 Step へ**上書き置換**する(inline は従来どおり任意選択のまま)。この置換により「ready 集合が算出されても消費されない(拘束力のない助言)」空洞が構造的に閉じ、依存順序保証が「助言」でなく「拘束」になる。この Step1 置換の配線 prose は C03 が `GOAL_SEEK_WIRING_SECTION` の task-graph 変種サブセクション『### ゴールシーク配線(task-graph 変種)』に埋め込む(=ループを回す駆動体は生成 SKILL.md の当該 prose Step が担い、別 component の新設は不要)。

**検査トークン**: (a) 各周回で「算出時点の ready 集合」と「実際に選択・実行した item」を **intermediate.jsonl の周回エントリへ `ready_set` / `selected_item` として追記**し(既存 intermediate.jsonl アンカーへの additive フィールドであり別状態ファイル=task-graph.json 相当を新設しないため単一truth原則を保つ)、後段で「毎周回 `selected_item` がその時点の `ready_set` の最小 id と一致する=任意順でなく依存充足順で消費された」ことを**そのトレースから**検査するトークン(旧案の『progress.json の status 遷移履歴』は progress.json がスナップショットで遷移履歴を保持しないため採らない — 検査は intermediate.jsonl 追記トレースを唯一の証跡源とする)、(b) self-reflect(C02)で追記された item が最終的に status==done へ遷移しない限り全体の done 判定が成立しないことを検査するトークン。両トークンは C03(render-combinators.py 拡張)が `GOAL_SEEK_WIRING_SECTION` の task-graph 変種サブセクションへ埋め込み、C04(lint-goal-seek.py 拡張)の self-test がその存在を機械検査する(H4 解消の実装箇所: `component-inventory.json` C03.purpose/C04.purpose、本節)。

### H5 解消: default/opt-in 軸は with-goal-seek の engine 選択として確定
独立 combinator flag(`with_task_graph` 等)は新設しない。with-goal-seek は loop kind(run/wrap/delegate)で既に default-ON であり(`render-combinators.py` の `selected_patches()` が CLI flag なしで無条件適用)、`brief.goal_seek.engine` は brief 由来のテンプレート変数(既定 `inline`、新規 opt-in 値 `task-graph`)として畳む。default/opt-in の軸は「combinator の有無」ではなく「with-goal-seek 内の engine 値」で一貫して表現し、purpose・component-inventory・index の記述間で矛盾を生じさせない(H5 解消の実装箇所: `component-inventory.json` C03.purpose/C05.trigger_conditions、index.md ## ドメイン知識)。

### H6 追加: generated harness dependency graph knowledge
生成 harness 内の skill / slash-command / sub-agent / hook / script surface 間の依存関係は、checklist の状態源とは別レイヤの **knowledge graph** として扱う。C06(`extract-capability-dependency-graph.py`)が生成済み harness の surface 定義・参照・plugin-composition を走査して dependency graph JSON を抽出し、C07(`record-capability-graph-knowledge.py`)がその graph と self-reflect で発見された task を Loop A(生成 harness) / Loop B(harness-creator) の knowledge entry へ `source_ref` 付きで記録する。C03 は brief.goal_seek.engine=task-graph 指定時に C06/C07 を C01/C02 と同じ task-graph-engine 同梱物として生成先へコピーし、生成 SKILL.md の実行前判断へ「dependency graph knowledge を consult する」手順を挿入する。C08(`lint-capability-graph-knowledge.py`)は生成 harness の skill / slash-command / sub-agent / script 各 surface がこの knowledge consult token を持つこと、C06/C07 が同梱されること、Loop A/B knowledge entry が `source_ref` を持つことを機械検査する。

この H6 は task 状態の二重化ではない。実行順序と discovered task の完了 gate は H3 の通り progress.json checklist が唯一の truth であり、C06/C07 が作る graph knowledge は「どの surface がどの前提知識・成果物に依存するか」を実行前判断で参照するための派生情報である。よって別 `task-graph.json` 状態を生成 harness 内に新設せず、単一truth原則と矛盾しない。

## スコープ外
- 既存 build-pipeline task-graph(`plugin-plans/harness-creator/`)の compute-ready-set 実装自体の修正 → 対象外(別 plan・本 plan constraints #2)。
- render-combinators.py と C08 lint 以外の生成系(template-selection.schema.json 等)への波及 → 対象外(C03 derivation で non-target と明記)。

## 完了チェックリスト
- [ ] H1: write_scope 並列衝突機構が不要である理由(逐次単一 self-writer)が明記されている(goal-spec C7)
- [ ] H2: 既存 compute-ready-set.py の tie-break が「バグ」でなく並列 dispatch 前提の意図的機構であることが file:line 引用付きで再framing されている(goal-spec C7)
- [ ] H3: 単一truth設計(checklist 追記=done-judge 同一配列)による完了gate の構造的保証が明記されている(goal-spec C6)
- [ ] H4: consumption verifier の機械検査設計が intermediate.jsonl アンカー検査と同型で明記されている(goal-spec C8)
- [ ] H5: default/opt-in 軸が with-goal-seek の engine 選択として確定し一貫している(goal-spec C10)
- [ ] H6: generated harness の dependency graph knowledge 抽出/記録/各 surface consult 検査が単一truth状態と分離して明記されている(goal-spec C1/C5/C8)
- [ ] 8 component(C01-C08)への分解が確定している

### 受入例 (満たす例 / 満たさない例)
- 満たす例: H1(write_scope 不要理由)/H2(compute-ready-set 再framing)がそれぞれ file:line 引用(`compute-ready-set.py` L16-27・L90-109、`render-combinators.py` L203-263・L310-328)を伴って明記され、C01-C08 の依存 DAG(C01→依存なし、C02→C01、C06→C01/C02、C07→C02/C06、C03→C01/C02/C06/C07、C04→C03、C08→C03/C06/C07、C05→C03/C04/C06/C07/C08)が非循環で確定している。
- 満たさない例: 「write_scope 機構は不要」とだけ結論のみ記述し、逐次単一 self-writer ゆえ並列衝突が構造的に発生しない根拠(file:line 引用)が示されないまま Phase03 design-review へ進む。

### 事前解決済み判断
- 分岐点: C01(ready-set 算出)と C02(self-reflect 追記)を 1 script に統合するか分離するか → 判断: C01 は読み取り専用ステートレス算出、C02 は書き込み+fail-closed 検査という責務が異なるため分離する。C02 の fail-closed 検査ロジック変更が C01 の副作用範囲へ波及しないことを SRP により構造的に保証する。

## 参照情報
- `plugins/plugin-dev-planner/skills/run-plugin-dev-plan/scripts/compute-ready-set.py`(L16-27 docstring、L90-109 tie-break 実装)
- `plugins/harness-creator/skills/run-build-skill/scripts/render-combinators.py`(L185-195 GOAL_SEEK_FM_BLOCK、L203-263 GOAL_SEEK_WIRING_SECTION、L310-328 selected_patches）
- `plugins/harness-creator/skills/run-build-skill/schemas/goal-seek-loop.schema.json`
- `plugins/harness-creator/skills/run-build-skill/scripts/lint-goal-seek.py`(check_default_drift）
- `component-inventory.json` C01-C08
