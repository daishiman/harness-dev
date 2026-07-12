# Prompt: R2-decompose-components

> このファイルは 7 層プロンプトの Markdown 表現。`run-prompt-creator-7layer` の
> seven-layer-format.md を正本とする。Layer 番号と依存方向 (L1 ← L7) は不変。

## メタ

| key | value |
|---|---|
| name | decompose-components |
| skill | run-plugin-dev-plan |
| responsibility | R2 (5 種写像で N 実体を component-inventory.json へ分解 + envelope 設計・Phase02 owner) |
| layers_covered | [L2, L4, L5, L6] |
| output_schema | references/io-contract.md (component-inventory 形式) |
| reproducible | true |

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール
- 1 コンポーネント = 1 単一責務 (SRP)。過剰分割しない (no-split threshold)
  - 目的: 分離≠善。第二消費者/機械検証/280 行超のいずれも無い分割は避ける
  - 背景: 不要な分割は保守コストと依存複雑性を増やす
- 各 capability 実体を §4 の 5 種 (skill / sub-agent / slash-command / hook / script) のいずれかへ写像する。**同一 kind に複数実体があれば各実体を独立 component にする**
  - 目的: placement_candidates enum と整合させ buildable 実体数 N (= inventory `components[]` 件数) の根拠を機械追跡可能にする
  - 背景: 「5 種を 1 本ずつ=5 本」ではなく、実プラグインは skill 複数・agent 複数… を含み N は自然に 10 実体超になる (5=kind の分類軸と N=実体数は直交する別軸・13=フェーズ数とも独立)

### 1.2 倫理ガード
- 分析材料 (UBM-Hyogo 配下) は read-only 抽出のみ。fork/複製しない

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (Single Responsibility)
- 担当: goal-spec を入力に capability を列挙し、各実体を 5 種の component_kind へ単一責務分解して `component-inventory.json` の `components[]` に載せる (buildable 実体数 N は inventory 件数の射影)。各々の kind/prefix/hierarchy/pattern を確定し依存 DAG を作る。加えて Phase02 owner として envelope(plugin.json)設計を確定する
- 非担当: 目的抽出 (R1)、13 phase ファイル + index 生成 (R3)、検証 (R4)

### 2.2 ドメインルール
- 各コンポーネントに `id` (例 C01・`^C[0-9]{2,}$`) / `component_kind` ∈ {skill, sub-agent, slash-command, hook, script} / `depends_on` を必ず確定する
- `component_kind == skill` の場合のみ `skill_kind` ∈ {run, ref, wrap, assign, delegate} を **top-level sub-field** として持つ (`component_kind` との衝突回避・fallback `kind`。非 skill 4 種は skill 形状を強制しない)。後段ルーティングは component_kind で分岐 (skill→run-skill-create / 非 skill→親 skill build)
- **component 粒度 (P02)**: 独立 builder を持つ kind (skill / sub-agent / slash-command / hook) は各実体を独立 component にする。builder を持たない script は複数 skill 共有 / 独立検証 / 280 行超のいずれか (no-split threshold) を満たす時のみ独立 component に昇格し、単一 skill 専用 script は親 skill の build へ畳む (専用 script を 1 実体ずつ component に割る水増しを防ぐ)
- buildable 実体数 N は 5 (kind 数) でも 13 (フェーズ数) でもなく、対象プラグインが持つ実体の数に依存して変動する (input でなく output)。各 component は唯一の実 `build_target` を持つこと (build_target 無し=水増しは `detect-unassigned.py` が弾く)
- 依存は DAG (循環禁止)。top-sort 可能な順序を保証する (inventory の component DAG は `verify-index-topsort.py` が非循環検査)
- **接合が密な兄弟ペアは `couples_with` を宣言する (盲目並列の代償を防ぐ)**: `depends_on` (成果物ハード依存=to が先に done でないと動けない) とは別に、`couples_with: [<相手 id>]` (optional・対称) は「同一 phase の兄弟で成果物依存は無いが接合が密なペア」を宣言する。判定の目安は「片方の出力形状が他方の入力形状になる (共有 contract/schema を挟む producer↔consumer)」「同じ統合面 (join) を両側から触る」。これらを盲目に並列 build すると統合 finding が両方 build 後まで先送りされ、実 pipe で出力キー↔読取キー不一致が露見する代償が起きる (実観測済み)。`couples_with` 宣言により derive-task-graph が同一 phase 直列化 depends_on を焼き (id 昇順で先発/後発を decisive に決定)、先発の done=統合面が観測済みになってから後発を build させる。**過剰宣言しない**: 真に接合が密なペアのみ (無関係な兄弟の並列性は保つ=幅広 DAG の利点を殺さない)。宣言忘れは advisory `lint-sibling-coupling.py` がデータ流シグナルから候補提示する

### 2.3 入力契約

| field | type | required | 説明 |
|---|---|---|---|
| goal_spec | path | yes | <PLAN_DIR>/goal-spec.json |
| component_hints | text | no | ユーザー希望コンポーネント |

### 2.4 出力契約
- 形式: コンポーネント目録 `component-inventory.json` (`{"considered_component_kinds":[...5種...],"components":[{"id","component_kind","skill_kind"(skill のみ),"name","depends_on","couples_with"(optional・接合密な同一phase兄弟),"build_target","builder","build_kind",...品質機構}],"plugin_level_surfaces":{...}}`) + 依存 DAG + envelope 設計 (Phase02 が `<PLAN_DIR>/envelope-draft/plugin.json` の下地を確定)
- 必須: `considered_component_kinds` は 5 種を全列挙する (検討証跡)。`components[]` は**実際に必要な buildable component のみ**を列挙する (不要な hook/script/command を水増し生成しない)。各コンポーネントの `id` / `component_kind` / `name` / `depends_on` / `build_target` / `builder` / `build_kind` (skill は `skill_kind` sub-field も)。**`build_target` は L4 実体化先パス** (skill→`plugins/<plugin-slug>/skills/<skill>/`、sub-agent→`plugins/<plugin-slug>/agents/<name>.md`、hook→`plugins/<plugin-slug>/hooks/<name>.py`、slash-command→`plugins/<plugin-slug>/commands/<name>.md`、script→親 skill の `scripts/<name>.py`)。`detect-unassigned.py` は各 component の `build_target` 非空 (欠落で exit1) と **各 component が ≥1 phase の `entities_covered` に出現** (orphan 防止) を機械強制する (io-contract.md §9 L3→L4 追跡)。`check-surface-inventory.py` が 5 種検討証跡と plugin-level surface 採否を検査する。キー名は `name` (≠`summary`)・ゴールデン例 `examples/sample-plan/component-inventory.json` と一致させる

## Layer 3: インフラ層 (外部依存)

### 3.1 参照リソース

| id | path | when_to_read |
|---|---|---|
| domain | references/component-domain.md | 5 種写像 / script 畳み込み / 2 軸直交判定時 |
| lifecycle | references/phase-lifecycle.md | Phase02(設計)・Phase05(実装) の写像確認時 |

### 3.2 外部ツール / API
- Read / Write / Glob / Grep (UBM-Hyogo 配下の read-only 抽出)

## Layer 4: 共通ポリシー層

### 4.1 失敗時挙動
- 依存に循環が生じたら分割をやり直す。`detect-unassigned.py` が後段で未配置を捕捉する前提で目録を完全にする

### 4.2 観測 / ロギング
- 出力先: `<PLAN_DIR>/component-inventory.json`

### 4.3 セキュリティ
- 抽出元の固有名・トークンを本文転記しない (anti-bloat)

## Layer 5: エージェント層 (ゴール駆動の実行主体)

### 5.1 担当 agent
- run-plugin-dev-plan 配下の architect SubAgent (R2/R3、`isolation: fork`)

### 5.2 ゴール定義
- **目的**: 構想を単一責務コンポーネント目録 (`components[]` = buildable 実体軸の機械 SSOT) + 依存 DAG + envelope 設計に変換する
- **背景**: inventory が確定しないと R3 が各 component を phase の `entities_covered` へ紐づけ後段 build へ 1 件ずつ委譲できない。plugin 階層横断規律は index の章であり component に加算しない
- **達成ゴール**: 5 種へ写像された目録と循環なし依存 DAG + envelope(plugin.json)設計が確定した状態

### 5.3 完了チェックリスト (ゴール到達の停止条件)
- [ ] capability を列挙し SRP 分割線を引いた (過剰分割なし)
- [ ] 5 種の component_kind すべてを検討軸として `considered_component_kinds` に記録した
- [ ] 必要な各実体を 5 種のいずれかへ写像し component_kind を確定した (同一 kind 複数実体はそれぞれ独立 component)
- [ ] skill コンポーネントのみ `skill_kind` (run/ref/wrap/assign/delegate) を sub-field で確定した
- [ ] 各コンポーネントの hierarchy / pattern を確定し依存 DAG を作り循環が無い (top-sort 可能) ことを確認した
- [ ] 接合が密な同一 phase 兄弟ペア (共有 contract を挟む producer↔consumer・同一 join を両側から触る) を `couples_with` で宣言した (過剰宣言せず・無関係兄弟の並列性は保つ)。宣言は derive が直列化し `validate-task-graph` (j) が実現を強制する
- [ ] 各コンポーネントの `name` と L4 実体化先 `build_target` + `builder` / `build_kind` を確定し目録へ記録した (R3 後の `detect-unassigned.py` が build_target 非空と phase への出現を強制するため R2 段で前倒し確定し fail-late を避ける)
- [ ] Phase02 owner として envelope(plugin.json)設計を確定し `<PLAN_DIR>/envelope-draft/plugin.json` の下地にした
- [ ] 不要な plugin-level surface は `plugin_level_surfaces.<surface>.omitted_reason` (正本キー一本) に根拠付きで記録した

### 5.4 実行方式
- 固定手順を持たない。未充足項目を特定→手順を都度立案→実行→チェックリストで自己評価→全項目充足まで反復 (上限: Layer 4 最大反復回数)。

## Layer 6: オーケストレーション層 (ゴールシーク制御)

### 6.1 上位 skill との接続
- 呼び出し元: run-plugin-dev-plan (Phase02 設計 owner)
- 後続 phase: R3-emit-specs

### 6.2 ハンドオフ / 並列性
- 直列: 目録 + DAG + envelope 設計を R3 へ接続。R3 は 13 phase ファイルと inventory component を並列展開し得る

## Layer 7: 提示層

この Layer 7 は prompt-creator 7層形式の出力提示レイヤーであり、Web UI/UX やスクリーンショット要求ではない。

### 7.1 ユーザー提示形式
- component-inventory.json + 依存 DAG (Markdown 箇条)

### 7.2 言語
- 本文: 日本語 (パラメーター名 / schema key は英語のまま)

---

## 出力指示 (LLM 実行時に読む箇所)

LLM はここから下の指示のみを実行し、Layer 1〜7 はコンテキストとして参照する。

Layer 5.2 のゴール + 5.3 完了チェックリストを唯一の停止条件とし、5.4 ループで
動的に手順を生成・実行・自己評価する。入力 `{{goal_spec}}` (と任意 `{{component_hints}}`)
を Read し、各実体を 5 種の component_kind へ単一責務分解する (同一 kind 複数実体可)。出力は次の 1 つのみとする:

1. component-inventory.json (`components[]` = id/component_kind/skill_kind(skill のみ)/name/depends_on/build_target/builder/build_kind + 依存 DAG + envelope 設計の下地。キー名・形状は `examples/sample-plan/component-inventory.json` に一致させる)

余計な前置き・後書き・思考過程出力は禁止。
