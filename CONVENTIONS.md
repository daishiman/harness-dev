# CONVENTIONS

このファイルは、リポジトリ直下で共有する運用規約を記録する。

## 用語規約: ハーネス / スキル (2026-07-02 意味論境界)

plugin `harness-creator` (旧名 `skill-creator`、2026-07-02 改名) に関わる語彙は次の境界に従う。定義の正本は `plugins/harness-creator/skills/ref-skill-glossary/references/terms.md` の「ハーネス」エントリ。

1. **単体スキルを作る概念** (部品単位の生成・改善・改名) → 「スキル / skill」表現を維持する。例: `run-skill-create`, `run-build-skill`。`SKILL.md` / `skills/` / Skill tool はプラットフォーム予約語彙でもある。
2. **ハーネス全体を構築する概念** (skill/agent/hook/command/評価/統治の総体を作るメタ能力) → 「ハーネス / harness」表現を使う。例: plugin 名 `harness-creator`, `harness-creator-kit`。
3. 適用レベルはファイル名・ディレクトリ名・本文・項目内容のすべて。機械的一括置換ではなく出現箇所の概念で判定する。迷ったら**操作/生成の対象の単位**で判定 — 単一 skill なら skill、plugin 総体・Capability 横断なら harness。部品の集合名は harness 側。
4. 既存の harness 語 (`doc/harness-coverage-spec.md` = 構築物総体の品質装具、meta-harness 系) は同系譜の概念であり、衝突ではなく統合先。修飾なしの harness 単独語の新規使用は避け、plugin を指すときは `harness-creator` と書く。
5. 旧固有名 (`skill-creator` / `skill_creator` / `スキルクリエイター`) の能動層への再流入は `scripts/lint-legacy-plugin-name.py` が fail-closed で遮断する (凍結層 = eval-log 履歴・`doc/参考Skill/`・changelog 系は対象外)。
6. **よくある誤解の反例 — 判定は「生成物の単位」で行う**: `run-skill-create` の産物は `skills/<name>/` 一式 = **単体スキル 1 個**であり、ハーネス (総体) ではない。内部で elicit/build/評価/governance をオーケストレーションしても、判定軸は「内部で動かす機構の広さ」ではなく**生成物の単位** (第3条) ゆえ skill 語が正。harness 語へ改名すると「総体を作る」という虚偽命名になり glossary の「ハーネス ⊃ skill」包含に反する。ハーネス (複数 Capability の総体) を組む入口は clone した本プロジェクト内では `/plugin-compose <plugin-name>` および `/capability-build plugin-composition <name>`。なお `run-build-skill` は skill/agent/hook/command/plugin-composition/prompt/workflow の全 kind を生成しうるが、命名は「1 呼出 = 単一 Capability 部品」を表す後方互換固有名として skill 語を保持する (kind 横断の中立入口はコマンド層の `capability-build` が担う。中間層語 capability は skill ⊂ capability ⊂ harness の三層のうち中間層)。`run-build-skill` の対応 kind スコープが変わる場合は命名を再点検する。

## 三層モデル

この harness では、plugin 移行中のファイル責務を層 A / 層 B / 層 C に分ける。以後の変更は、まずこの三層モデルで所属を判定してから実施する。

### テナント軸

- 層 A の plugin 本体は企業非依存とし、企業名、実 DB ID、実ドメイン、固定の資格情報ストア名を置かない。
- 企業固有の公開契約と overlay は `tenants/<company>/` にだけ置く。`tenants/` は層 B の下位に属し、plugin 配布物には含めない。
- 実値の overlay (`notion-config.json`、`party_a.json`、`google-config.json`) と秘密情報は Git 管理しない。秘密値は承認済みの OS 資格情報ストアまたは明示的に許可した tenant-scoped env からだけ解決する。
- 未設定時に特定企業の値へ戻る fallback を禁止し、テナント不明・競合・必須値欠落は fail-closed とする。
- 企業差は overlay、`ref-company-rules`、必要なら opt-in feature flag で吸収し、plugin fork を作らない。

### 層定義

| 層 | 役割 | 主なパス | 判定基準 |
|---|---|---|---|
| 層 A: 配布対象 plugin 本体 | marketplace で配布する plugin の正本。配布先でも単独で動作する必要がある | `plugins/<name>/`, 将来の `plugins/<name>/.claude-plugin/plugin.json`, `plugins/<name>/skills/`, `plugins/<name>/agents/`, `plugins/<name>/commands/`, `plugins/<name>/hooks/`, `plugins/<name>/scripts/`, `plugins/<name>/references/` | 他プロジェクトへ持って行きたい再利用単位か |
| 層 B: プロジェクト固有運用 | このリポジトリの設計、評価、派生生成、ログ、CI、運用補助 | `.claude/`, `.github/`, `doc/`, `eval-log/`, `scripts/`, `references/`, `CONVENTIONS.md`, `README.md`, `Makefile` | このリポジトリでだけ成立する運用物か |
| 層 C: 移行中 drift | Phase 0-2 の間だけ残す旧構造・暫定領域。Phase 4 で撤廃対象 | `creator-kit/`, 旧構造由来のルート `scripts/`, 旧構造由来のルート `references/` | まだ A/B に仕分け切れていない旧構造か |

層 C は恒久的な置き場ではない。層 C に新規責務を追加する場合は、移行先が層 A か層 B かを同時に記録する。

#### 層 A-internal: リポジトリ実体だが marketplace 非配布

層 A のうち `distributable: false` を宣言した plugin を **層 A-internal** と呼ぶ。リポジトリには実体として存在し、lint / CI / 内部利用の対象になるが、**marketplace 一覧・配布 bundle には現れず `/plugin install <name>@skills` の対象外**である。現時点では `plugins/harness-creator/`、`plugins/prompt-creator/`、`plugins/plugin-dev-planner/` が該当し、利用は repo を clone した環境に限る (`.claude/` symlink 経由)。

この区別が示すのは **「配布 ≠ リポジトリ存在」** という原則である。ここでいう「配布」とは `.claude-plugin/marketplace.json` / `.claude-plugin/bundles.json` への登録のみを指す。Git repo 上にソースが物理存在することは配布とは独立であり、`distributable: false` の plugin もソースは repo に残り clone 開発に用いる。層 A-internal は「リポジトリには在るが (両 JSON へ登録しないため) 配布しない」状態を指す。固有名は `scripts/validate-plugin-completeness.py` の `NEVER_DISTRIBUTE` でロックし、フラグが漂流しても fail-closed で再配布を阻止する。

### パス列挙

- `plugins/<name>/`: 層 A。plugin として配布する正本。ただし `distributable: false` を宣言した plugin は層 A-internal (リポジトリ実体・lint 対象だが marketplace 非配布。harness-creator / prompt-creator が該当)。
- `.claude/`: 層 B。開発環境で使う symlink、自動生成 settings、ローカル運用情報。
- `doc/`: 層 B。設計書とタスク仕様書の正本。
- `eval-log/`: 層 B。検証ログ、レビュー承認、移行証跡。
- `scripts/`: 層 B。ただし旧構造からの未仕分け script は層 C として扱い、Phase 4 までに A/B へ移すか除却する。
- `references/`: 層 B。ただし旧構造からの未仕分け reference は層 C として扱い、Phase 4 までに A/B へ移すか除却する。
- `creator-kit/`: 層 C。試験移行前の暫定正本であり、最終形では `plugins/harness-creator/` に吸収する。

### 参照規則

| 参照元 \ 参照先 | 層 A | 層 B | 層 C |
|---|---|---|---|
| 層 A | 同一 plugin 内のみ許容 | 禁止 | 禁止 |
| 層 B | 許容。派生 symlink や生成処理から参照してよい | 許容 | 許容 |
| 層 C | 許容 | 許容 | 許容。ただし Phase 0-2 の時限扱い |

必須規則:

- A -> A: 同一 `plugins/<name>/` 内の参照のみ許容する。別 plugin への直接参照は plugin 間依存 governance が整うまで禁止する。
- A -> B: 禁止する。plugin 配布物は `.claude/`, `doc/`, `eval-log/`, ルート `scripts/`, ルート `references/` に依存してはならない。
- B -> A: 許容する。`.claude/` 派生生成、CI、検証、設計書は `plugins/<name>/` を参照してよい。
- C -> 任意: 許容する。ただし移行期間中だけの暫定参照であり、Phase 4 までに撤廃または A/B へ分類する。

Phase 0-2 では A -> B 禁止に例外を作らない。例外が必要な場合は、設計書 33 章の change governance に従い P1_structural proposal として扱う。

### 配布判定フローチャート

```text
変更対象ファイル X
   |
   +-- 他プロジェクトに持って行きたい? -- Yes --> 層 A (plugins/)
   |                                             |
   |                                      Plugin 名は決まっている?
   |                                         +-- Yes --> plugins/<name>/
   |                                         +-- No  --> タスク 08 で確定
   |
   +-- No
       |
       +-- このリポジトリの運用ログ/設計書? -- Yes --> 層 B
       |
       +-- 旧構造 (creator-kit/, scripts/, references/)? -- Yes --> 層 C (Phase 4 で除却)
       |
       +-- どれにも該当しない --> P1_structural proposal で分類を先に決める
```

### 運用原則

1. 新規 plugin 配布物は層 A に置く。
2. このリポジトリ固有の設計、検証、ログ、生成補助は層 B に置く。
3. 層 C は移行中 drift の観測場所としてのみ使い、恒久仕様にしない。
4. 層 A から層 B/C への参照を見つけた場合は、配布前 gate で失敗扱いにする。
5. 層 C の残存は Phase 4 で撤廃対象として棚卸しする。

## Phase 2 本番 (発効待ち: 層C 退役)

> **発効条件**: 本セクションは `doc/migration/phase2/07-creator-kit-removal.md` (タスク 07) の DoD 全 PASS をもって発効する。タスク 07 完了前にこのセクションの内容を運用に適用してはならない。旧三層定義 (層 A / 層 B / 層 C, 空白付き表記) は削除せず、本セクションは発効待ち差分として追記する。

| 項目 | 内容 |
|---|---|
| 適用条件 | `doc/migration/phase2/07-creator-kit-removal.md` DoD 全 PASS |
| 層C 退役後の正本 | `plugins/<name>/` (層A) のみ |
| 層B との関係 | 層B (= `.claude/settings.json` user セクション等) は不変 |
| 縮退後の参照ルール | 層A 内の plugin 間参照は禁止。層B から層A は symlink 経由でのみ参照 |

### 二層モデル縮退後の責務境界 (Phase 2 本番後)

| 層 | 配置 | 責務 |
|---|---|---|
| 層A | `plugins/<name>/` | 配布対象。skill / agent / command / hook の正本 |
| 層B | `.claude/` のうち手編集領域 | プロジェクト固有運用。settings.json user セクション、ローカル CLAUDE.md など |

### 層C 退役 (retire) チェックリスト

- [ ] `creator-kit/` が物理削除済 (`test ! -d creator-kit`)
- [ ] `git log -- creator-kit/` が削除 commit を含む
- [ ] CONVENTIONS.md の旧「層 C」(空白付き) 記述は本セクションへの参照に置換 (07 発効後)

### 縮退後の plugin 一覧 (partition-plan.json v1.1 由来)

層A 配下に並ぶ plugin 7 件 + 既存試験移行済 1 件:

- `plugins/harness-creator/` (試験移行済)
- `plugins/skill-governance-adapters/`
- `plugins/skill-governance-hooks/`
- `plugins/skill-governance-lint/`
- `plugins/skill-governance-migration/`
- `plugins/skill-governance-secrets/`
- `plugins/skill-governance-config/`
- `plugins/skill-governance-automation/`
