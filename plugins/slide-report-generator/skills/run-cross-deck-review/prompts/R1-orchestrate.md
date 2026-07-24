# Prompt: R1-orchestrate

> このファイルは 7 層プロンプトの Markdown 表現。`run-prompt-creator-7layer` の
> seven-layer-format.md を正本とする。Layer 番号と依存方向 (L1 ← L7) は不変。
> R1→R2→R3 の横断整合検証ワークフローを完全駆動する実行 SSOT。SKILL.md は router、本ファイルは実行契約。

## メタ

| key | value |
|---|---|
| name | orchestrate |
| skill | run-cross-deck-review |
| responsibility | R1-orchestrate (1 prompt = 1 責務 = R1→R2→R3 シリーズ横断整合検証の駆動) |
| layers_covered | [L1, L2, L3, L4, L5, L6, L7] |
| output_schema | schemas/cross-deck-review-report.schema.json (横断整合レポートの構造契約。conversation-output としてレンダし機械 emit はしない) |
| reproducible | true (機械チェック `cross-deck-consistency.js` + C1-C15/4条件マトリクスの判定は決定論的) |

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール
- **シリーズ横断** (複数 slide deck) の用語 ／ 意匠 ／ 構成整合を **Agent A/B/C の 3 レンズ分析 × 4 条件**で網羅検出する。単一成果物では見えない**シリーズ全体の整合崩れ** (用語ゆれ・意匠差・構成不整合) を対象とする。用語 ／ 意匠 ／ 構成の 3 観点と Agent A/B/C レンズ・C1-C15 の対応は `references/cross-deck-consistency-rules.md` の対応表で橋渡しする。
- **read-only 分析**。生成済み成果物 (index.html / styles.css / scripts.js / structure.md / ソース md) を本 skill から書き換えない (`allowed-tools` に Write/Edit を持たない)。検出のみで、修正は `run-slide-report-modify` へ委譲。
- **配置非依存**: 全実行パスは `${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}` 起点。repo-root ハードコード禁止。
- **機械チェック先行** (CONST_001): 構造的整合性 (C1-C2 / C11-C13 / C15) は `cross-deck-consistency.js` の実行結果を一次根拠とし、LLM 目視のみで判定しない。C3 は Agent A が structure.md を横断比較する。

### 1.2 倫理ガード・品質規約
- **絵文字ゼロ** (CONST_005): レポート・提案に絵文字を使わない。アイコンが要る場合は Font Awesome の `fa-*` 名で表現する。
- **3 レンズを単一観点に縮退させない** (CONST_002): 用語 ／ 意匠 ／ 構成の 3 観点を Agent A/B/C の 3 レンズ (単一 fork context 内・再 fork＝SubAgent 起動しない) に構造的に分担する。

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (Single Responsibility)
- 担当: 横断対象の収集 → 機械チェック → cross-deck-reviewer による 3 レンズ分析 (Agent A/B/C・単一 fork context 内多角分析) × 4 条件 → 不整合の網羅検出結果を横断レポート化。
- 非担当: 個別成果物の修正・再生成 (`run-slide-report-modify`)、新規生成 (`run-slide-report-generate`)、単体 UI 品質検証 (`ui-quality-reviewer` / P3.5)。

### 2.2 ドメインルール
- **4 条件** = 矛盾なし ／ 漏れなし ／ 整合性あり ／ 依存関係整合。各条件に **PASS/WARN/FAIL と根拠 C 番号 (C1-C15)** を付与する。逐語基準は `references/cross-deck-consistency-rules.md` (§評価軸: 判定マトリクス) を正本とする。
- **検証項目 C1-C15 の分担**: 機械チェック = C1-C2 / C11-C13 / C15、Agent A = C3-C5 (論理・構造)、Agent B = C6-C10 (メタ・発想)、Agent C = C11-C15 (システム・戦略)。観点定義・合否条件・検出方法の逐語は reference (§評価軸: 検証項目) を正本とする。
- **修正の優先度分類**: P0 (即時修正) ／ P1 (要判断) ／ P2 (将来改善)。分類基準は reference (§修正の優先度分類)。本 skill は read-only ゆえ **分類まで**を行い、P0 を含む適用は `run-slide-report-modify` へ委譲する (本 skill から書き込まない)。
- **シリーズ成立条件**: P3.5 通過済みデッキが 2 つ以上 (CONST 記載のシリーズ成立条件)。デッキ 2 未満なら横断検証 (P5) 全体をスキップし「横断検証不要 (単一デッキ)」を返す。

### 2.3 入力契約

| field | type | required | 説明 |
|---|---|---|---|
| series_dir | path (argument) | yes | シリーズディレクトリ。配下の `slide-*` deck 群を Glob 列挙 |
| structure.md × N | resource://<series-dir>/*/structure.md | yes | 各デッキの共通仕様セクションを含む (機械チェック・C1-C5 の対象) |
| index.html / styles.css / scripts.js × N | resource://<series-dir>/*/ | yes | P3.5 通過済み各デッキ (C11-C15 の対象) |
| ソース md × N | resource://<series-dir>/*/source.md | no | 比喩・コンセプト追跡 (C6-C8)。無ければ追跡精度を下げて続行 |
| consistency-rules | resource://run-cross-deck-review/references/cross-deck-consistency-rules.md | yes | 用語集 / CONST_001-005 / C1-C15 / 判定マトリクス / Agent A/B/C 3レンズ分析テンプレ / headline 軸対応表 / 優先度分類の逐語正本 |

### 2.4 出力契約
- schema: schemas/cross-deck-review-report.schema.json — 横断整合レポートの構造契約 (conversation-output としてレンダし機械 emit はしない)。
- 成果物: **横断整合レポート** = 用語ゆれ一覧 ＋ 意匠差一覧 ＋ 構成不整合一覧 ＋ 4 条件判定 (PASS/WARN/FAIL ＋ 根拠 C 番号) ＋ 網羅率、および **修正提案リスト** (P0/P1/P2 分類・対象デッキ・対象ファイル・修正内容)。

## Layer 3: インフラ層 (外部依存)

### 3.1 参照リソース

| id | path | when_to_read |
|---|---|---|
| consistency-rules | ./references/cross-deck-consistency-rules.md | 用語集・CONST_001-005・C1-C15・判定マトリクス・Agent A/B/C 3レンズ分析テンプレート・headline 軸対応表・優先度分類の逐語解決時 |

### 3.2 統率する agent (Task で name 起動)

| agent | 起動方式 | 役割 |
|---|---|---|
| `cross-deck-reviewer` | `Task` (name 参照・`isolation: fork`) | 独立 context で機械チェック結果を一次根拠に Agent A/B/C の 3 レンズ分析 (単一 fork context 内・再 fork しない) × 4 条件を実行する read-only 自動 worker。実体は `../../agents/cross-deck-reviewer.md` だが起動はファイルパス依存でなく Task の name 参照。ドメイン規範は reference を SSOT とする薄化アダプタ |

### 3.3 外部ツール / vendor scripts (`${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/vendor/scripts/`)
- `node "${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/vendor/scripts/cross-deck-consistency.js" <series-dir> --check all` — 必須入力欠落・shared-spec 差分 (A4印刷/コードブロック/GSAP/フォント)・CSS 変数・GSAP・印刷・外部 URL 混入・rem 残存の機械検出 (C1-C2 / C11-C13 / C15 の一次根拠。SVG設計/スライドタイプ定義の異同は Agent A 目視)。`--check` の個別カテゴリは `inputs` / `shared-spec` / `urls` / `css-vars` / `gsap` / `print` / `rem-units`。
- `node "${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/vendor/scripts/check-consistency.js" <deck-dir>` — 個別成果物の統一感検証 (テーマ・スタイル整合)。
- `Read` / `Grep` — structure.md ／ ソース md ／ styles.css ／ scripts.js の横断読取と用語横断検索 (C3-C15 の目視検証)。
- `Task` — `cross-deck-reviewer` を独立 context で fork 起動。

## Layer 4: 共通ポリシー層

### 4.1 失敗時挙動
- `cross-deck-consistency.js` 実行失敗 (exit≠0 ／ node 不在 ／ series-dir 不正) → series-dir・引数を修正して**最大 1 回**再実行。解消しなければ機械検出分を **WARN で明記して続行**し、機械チェック不能を隠さない。引数不正 ／ 環境エラー (exit 2) は fatal。
- Agent A/B/C いずれかのレンズ分析が不完全 → 当該観点を**縮退 (degradation) で記録**し、残るレンズ結果で 4 条件判定を続行 (最大 1 回)。
- 必須入力 (structure.md / index.html / styles.css / scripts.js) が 1 件でも不足 → `inputs` error として fail-closed で停止し、不足デッキとファイルを明示して生成完了を求める。欠落デッキを除外して続行しない。

### 4.2 観測 / ロギング
- 各周回末に中間成果物アンカー (`original_goal` 不変 / `current_goal_snapshot` / `delta_from_original` / `merged_directive_for_next` / `drift_signal`) を記録し次周回の入力とする。`drift_signal` が stagnant / widening / oscillating で 2 周連続なら上位オーケストレータへ差し戻す。

### 4.3 read-only ・修正委譲
- 本 skill も cross-deck-reviewer agent も `Write`/`Edit` を持たない read-only 検出・分類専任。P0 を含む**全修正 (P0/P1/P2) は分類済みの修正提案リストとして `run-slide-report-modify` へ委譲**し、成果物を書き換えない。reference の CONST_004 は cross-deck-reviewer も read-only とし修正の適用を `run-slide-report-modify` へ一本化する規範であり、本 skill・agent とも**適用まで行わず分類・提案に留める**。

### 4.4 品質規約
- 絵文字ゼロ (CONST_005)。アイコンは `fa-*`。P1 (要判断) はユーザー承認前に適用しない (CONST_003・本 skill では委譲提示に留まる)。

### 4.5 最大反復回数
- `with-goal-seek` **max_loops 5** ／ `with-feedback-contract` inner **max_iterations 3**。網羅率が閾値未満なら分析観点を追加して再走する。上限到達で未達なら未検出の観点を明示して停止する (一部検出で PASS 扱いにしない)。

## Layer 5: エージェント層 (ゴール駆動の実行主体)

### 5.1 担当 agent
- `cross-deck-reviewer` (`Task` で name 起動・`isolation: fork`・model sonnet)。

### 5.2 ゴール定義
- 目的: 全デッキを「一つのシリーズ (学習体験)」として整合させ、矛盾なし ／ 漏れなし ／ 整合性あり ／ 依存関係整合の 4 条件を満たす**網羅検出状態**に到達させる。
- 背景: 各デッキ単体では正しくてもシリーズ全体では共通仕様の食い違い・用語ゆれ・難易度の断絶・外部参照混入が発生する。単体検証 (ui-quality-reviewer / P3.5) の後段で横断的に検出する。機械チェックを一次根拠に、単一 fork context 内の 3 レンズ分析の人的観点を重ね、C1-C15 を 4 条件へ集約する二層構成。
- 達成ゴール: 機械チェック結果と Agent A/B/C 結果が 4 条件へ集約され、各条件に PASS/WARN/FAIL と根拠 C 番号が付与され、全 FAIL/WARN が P0/P1/P2 に分類され、用語ゆれ一覧 ＋ 意匠差一覧 ＋ 構成不整合一覧 ＋ 網羅率を含む横断レポートが `run-slide-report-modify` へ引き渡せる状態。

### 5.3 完了チェックリスト (停止条件)
- [ ] 横断対象の slide deck を Glob で列挙し、比較基準 (共通用語・共通意匠 SSOT・章立て構成) を確定した
- [ ] `cross-deck-consistency.js --check all` を実行し C1-C2 / C11-C13 / C15 の機械検出結果を取得した (CONST_001)
- [ ] `cross-deck-reviewer` を `Task` fork で起動し、Agent A/B/C の 3 レンズ分析 (単一 fork context 内・再 fork しない) が全完了、C1-C15 を全件判定した (CONST_002)
- [ ] 4 条件 (矛盾 / 漏れ / 整合性 / 依存) すべてに PASS/WARN/FAIL と根拠 C 番号を付与した (判定マトリクス)
- [ ] 全 FAIL/WARN を P0/P1/P2 に分類した
- [ ] 用語ゆれ一覧 ＋ 意匠差一覧 ＋ 構成不整合一覧 ＋ 網羅率を横断レポートに統合した
- [ ] IN1: `cross-deck-consistency.js` が横断対象 slide deck を走査し必須入力欠落・shared-spec 差分・外部 URL 混入・CSS 変数・GSAP・印刷 CSS・rem 逸脱を突合し、機械チェック入力 (各デッキの structure.md / index.html / styles.css / scripts.js) の欠落が 0 件
- [ ] OUT1: 既知の機械検出可能な不整合 (shared-spec差分 ／ rem単位 ／ 外部URL ／ 必須入力欠落) を注入したシリーズで全件検出し、クリーンseriesをPASSとすることを受入テストが確認した
- [ ] read-only を維持し成果物を書き換えていない (修正は `run-slide-report-modify` へ委譲)
- [ ] レポート・提案に絵文字を使っていない (CONST_005・`fa-*` で表現)
- [ ] デッキ 1 つのみの場合は横断検証 (P5) 全体をスキップし「横断検証不要 (単一デッキ)」を返した

### 5.4 実行方式 (決定論)
- **機械チェック先行**: 3 レンズ分析の前に `cross-deck-consistency.js --check all` を走らせ、C1-C2 / C11-C13 / C15 を機械結果で確定する。C3 は Agent A が目視判定する (CONST_001)。
- **3 レンズは立案せず reference の 3レンズ分析テンプレートを正本に適用**: `references/cross-deck-consistency-rules.md` (§Agent A/B/C 3レンズ分析テンプレート) の Agent A (論理・構造 / C3-C5) ・Agent B (メタ・発想 / C6-C10) ・Agent C (システム・戦略 / C11-C15) を `cross-deck-reviewer` が単一 fork context 内で適用する (再 fork＝SubAgent 起動しない)。観点を 1 レンズへ集約しない (CONST_002)。
- **判定はマトリクスに従う**: 4 条件の PASS/WARN/FAIL は reference (§評価軸: 判定マトリクス) の基準に従い、gut 判定を禁止。各判定に根拠 C 番号を明示する。
- **反復は分離 context で完結**: ループ本体は `Task` で fork し、親へは横断レポートのみ返却する。run-slide-report-modify へは横断レポート ＋ 修正提案リストを渡す。

## Layer 6: オーケストレーション層

### 6.1 上位 skill との接続・起動
- 独立起動 skill (`user-invocable: true`)。移植元 P5 = cross-deck-reviewer 相当。
- 上流: `html-generator` / `slide-renderer` / `ui-quality-reviewer` (各デッキ P3.5 通過済み)。下流: `run-slide-report-modify` (P1 適用)。

### 6.2 R1 → R2 → R3 の agent dispatch 詳細
- **R1 (横断対象の収集と観点確定)**: `series_dir` 配下の `slide-*` deck を `Glob` で列挙し、比較の基準 (共通用語・共通意匠 SSOT・章立て構成) を明示する。P3.5 通過済みデッキが 2 未満なら横断検証をスキップして終了する。
- **R2 (3 レンズ分析)**: まず `node "${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/vendor/scripts/cross-deck-consistency.js" <series-dir> --check all` で機械チェックし、FAIL ／ WARN 項目について `Task` で `cross-deck-reviewer` を `isolation: fork` 起動する。cross-deck-reviewer は**単一 fork context 内で Agent A/B/C の 3 レンズ** (再 fork＝SubAgent 起動しない) で用語 ／ 意匠 ／ 構成の観点を多角分析し、4 条件で判定する。個別成果物は `check-consistency.js <deck-dir>` で統一感を検証する。
- **R3 (網羅検出結果の報告)**: 機械結果と 3 Agent 結果を統合し、不整合の網羅検出結果を横断レポート (用語ゆれ一覧 ＋ 意匠差一覧 ＋ 構成不整合一覧 ＋ 網羅率) として返す。修正が必要な項目は P0/P1/P2 分類付きで `run-slide-report-modify` への委譲として提示する (本 skill は検証のみ)。

### 6.3 ハンドオフ / 実行性
- 直列: 横断レポート ＋ 修正提案リスト (提供元 = 本 skill、受領先 = `run-slide-report-modify`) を後続の修正入力に接続する。
- レンズ分析: Agent A/B/C は `cross-deck-reviewer` の単一 fork context 内で適用する 3 レンズ多角分析 (再 fork＝SubAgent 起動しない)。機械チェックは 3 レンズ分析の**前**に単一直列で実行する (先行根拠)。

## Layer 7: UI / 提示層

### 7.1 ユーザー提示形式
- 横断品質レポート = 4 条件判定 (PASS/WARN/FAIL ＋ 根拠 C 番号) ＋ 修正提案リスト (P0 ／ P1 ／ P2) ＋ 網羅率。提示テンプレートは `cross-deck-reviewer.md` Layer 7 の提示テンプレート例に準拠する。

### 7.2 言語
- 本文: 日本語 (`output_language: ja`)。絵文字ゼロ・アイコンは `fa-*`。

---

## Self-Evaluation

横断レポート生成後に以下を自己確認する。未達があれば該当観点へ戻り再走する。

| 観点 | 確認内容 | 判定 |
|---|---|---|
| 網羅性 | 機械層はOUT1 fixtureの注入不整合を全件検出し、意味層は3レンズでC1-C15を全件判定。一部観点でPASS扱いにしていない | PASS/FAIL |
| 機械先行 | C1-C2 / C11-C13 / C15 を `cross-deck-consistency.js` の結果で判定し、C3 は Agent A が判定 (CONST_001) | PASS/FAIL |
| 3 レンズ | Agent A/B/C を単一観点に縮退させず単一 fork context 内で C1-C15 を 4 条件へ集約 (CONST_002・再 fork しない) | PASS/FAIL |
| read-only | 成果物を書き換えず、修正は `run-slide-report-modify` へ委譲 | PASS/FAIL |
| 根拠明示 | 4 条件各判定に根拠 C 番号を付与し、絵文字ゼロで提示 | PASS/FAIL |

---

## 出力指示 (LLM 実行時に読む箇所)

LLM はここから下の指示のみを実行し、Layer 1〜7 はコンテキストとして参照する。

`{{series_dir}}` 配下の `slide-*` deck を `Glob` で列挙し、P3.5 通過済みデッキが 2 未満なら「横断検証不要 (単一デッキ)」を返して終了せよ (R1)。2 つ以上なら、まず `node "${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/vendor/scripts/cross-deck-consistency.js" {{series_dir}} --check all` を実行する。各デッキの structure.md / index.html / styles.css / scripts.js のいずれかが欠落する場合は fail-closed で停止し、不足デッキとファイルを明示せよ。欠落がなければ C1-C2 / C11-C13 / C15 の機械検出結果を一次根拠として取得する (CONST_001)。次に `Task` で `cross-deck-reviewer` を `isolation: fork` 起動し、cross-deck-reviewer が `references/cross-deck-consistency-rules.md` (§Agent A/B/C 3レンズ分析テンプレート) の Agent A (C3-C5) ／ Agent B (C6-C10) ／ Agent C (C11-C15) を**単一 fork context 内の 3 レンズ**として分析し (再 fork＝SubAgent 起動しない)、観点を 1 レンズへ集約しない (CONST_002)。個別成果物は `node "${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/vendor/scripts/check-consistency.js" <deck-dir>` で統一感を検証する (R2)。機械結果と 3 Agent 結果を突き合わせ、4 条件 (矛盾 / 漏れ / 整合性 / 依存) に reference (§評価軸: 判定マトリクス) の基準で PASS/WARN/FAIL と根拠 C 番号を付与し、全 FAIL/WARN を P0/P1/P2 (§修正の優先度分類) に分類する。用語ゆれ一覧 ＋ 意匠差一覧 ＋ 構成不整合一覧 ＋ 網羅率を横断レポートに統合して返し、修正は `run-slide-report-modify` への委譲として提示する (本 skill は read-only・書き換えない、R3)。IN1 (分析入力の欠落 0 件) と OUT1 (既知不整合の全件検出) を満たすまで with-goal-seek (max_loops 5) / with-feedback-contract (inner max_iterations 3) で反復し、未達なら未検出観点を明示する。絵文字を使わず `fa-*` で表現し、前置き禁止。
