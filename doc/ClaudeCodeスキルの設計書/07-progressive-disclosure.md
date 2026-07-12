# 07. Progressive Disclosure（段階的開示）の設計判断

## このファイルの責務

Progressive Disclosure（段階的開示）の **設計思想・なぜ分けるか・失敗パターン・compaction 対策・context reset 運用** を保持する。lifecycle の token 数値（token budget）や、Skill lifecycle の公式挙動そのものは記載しない。

**更新責務マトリクス**: lifecycle の token 上限値の変更は `16` のみ更新する。本ファイルは「層分けの基準」「何を本文に残して何を逃がすか」「context reset の運用」が変わったときだけ更新する。

→ 公式 lifecycle と token budget tokens の挙動: [16-official-skills-complete-reference.md §14](./16-official-skills-complete-reference.md#14-skill-content-lifecycle)
→ 補助ファイル仕様: [§12](./16-official-skills-complete-reference.md#12-supporting-files)

## 基本思想

Progressive Disclosure（段階的開示）は、**必要な情報を必要になった段階でだけ読ませる設計** である。`SKILL.md` にすべてを書かず、入口情報・本文・補助ファイル・forked context を分ける。

## 3 層モデル（設計の指針）

| 層 | 内容 | ロード時点 | 設計ねらい |
|---|---|---|---|
| 入口情報 | `name`, `description`, `when_to_use` | session start | Claude の **発動判断** に必要な最小情報だけ |
| `SKILL.md` 本文 | 手順、制約、出力契約 | Skill invoked | 発動後の **判断と出力契約** に集中 |
| 補助ファイル | 詳細仕様、例、script | Claude が Read / 実行 | **必要時のみ消費** する深い情報 |
| feedback artifact | evaluator JSON、eval-log、handoff、rubric hash | 評価・再開・監査時 | 会話履歴に依存せず **再検証・再開** できる状態を残す |

公式 token 数値は [16 §14](./16-official-skills-complete-reference.md#14-skill-content-lifecycle) を参照。

## なぜ分けるか（Why（理由））

- context 予算を早く消費しない。
- 重要ルールを長文中央に埋めない（**lost in the middle**）。
- 無関係な情報による **context rot** を避ける。
- compaction 後も重要事項が残るようにする。

## 失敗パターン

| 失敗 | 問題 | 修正 |
|---|---|---|
| 全部 `SKILL.md` に詰め込む | token 消費、lost-in-the-middle | 本文は最小手順と地図にする |
| 補助ファイルの案内がない | Claude が到達できない | `Additional resources` を置く |
| 親会話に全部残す | context rot | `context: fork` に逃がす |
| 補助ファイル名が役割を語らない | Claude が読むか判断できない | `reference.md` ではなく `api-fields-reference.md` のように具体化 |

## `SKILL.md` に残すもの

- 発動後の最初の判断
- output contract（契約）
- 禁止事項
- 最重要 gotchas
- 補助ファイルの地図
- 実行 script の入口

## 補助ファイルに逃がすもの

- 長い表
- API reference
- 大量 examples
- rubric 詳細
- historical background
- domain dictionary
- generated schema

## compaction 対策（設計則）

公式 lifecycle の制約（→ [16 §14](./16-official-skills-complete-reference.md#14-skill-content-lifecycle)）を踏まえた本ファイル独自の運用則:

- 冒頭 30 行に **目的・出力契約・禁則** を置く。
- 後半にしかない重要ルールを作らない。
- 公式 docs の補助ファイル章には 500 行未満の目安があるが、生成対象の `.claude/skills/<skill-name>/SKILL.md` 本文は `08` の **300 行 hard cap** とする。
- 本ディレクトリの設計書 Markdown はこの hard cap の対象外であり、正確性・追跡性・判断根拠の明示を優先して 300 行以上を許容する。
- 長い情報は補助ファイルへ移す。
- 重要 Skill は **再 invocation できる前提** にする（compaction で消えても hook で再呼び出し）。
- 評価結果や handoff は会話要約ではなく artifact として残す。rubric hash / score / required_fixes が残れば、context reset 後も同じ基準で再開できる。

## Context Reset（文脈リセット）の設計応用

元画像では、compaction ではなく **context reset で真っ白なスレートで継続する** 考え方が示されている。

目的:

- 要約ノイズを残さない。
- 引き継ぎファイル経由で goal / progress / next steps だけを渡す。
- 新しい agent の集中力を戻す。

設計への応用:

- 長期 workflow は **handoff file を持つ**。
- Skill は「会話履歴が残る」前提でなく、**artifact から再開できる** ようにする。
- `PreCompact` hook で handoff file を生成し、`PostCompact` で参照する設計が有効（→ [10](./10-subagents-hooks-integration.md)）。

## タスク文脈に応じた自動読込パターン

### 問題

本ディレクトリの設計書群は 28 ファイル規模に達しており、Skill 設計タスクのたびに全章を preload するのは現実的でない。一方、必要な章を Claude の主観判断だけに任せると、関連章の見落とし（lost-in-the-disclosure）が起きる。Progressive Disclosure（段階的開示）を「人間が読む順序」ではなく「**タスク metadata から必要章を決定論的に推論する機構**」として再定義する必要がある。

### 解法: task → refs の決定論的マッピング

入力（user task の description / frontmatter / 分類結果）から「読むべき設計書ファイル集合」を関数的に導出する。Claude の判断ではなく、ルール表または script の出力で確定させることで再現性を保つ。

### パターン例

#### (1) description trigger keyword → 関連章 table

Skill の `description` または task spec の冒頭に含まれる keyword を、章番号にマップする静的表を補助ファイルに置く。

| keyword | 必読章 |
|---|---|
| `Progressive Disclosure（段階的開示）`, `補助ファイル` | 07, 16 §12, §14 |
| `dynamic injection`, `!` 構文 | 14, 22 |
| `subagent`, `hook`, `fork` | 10 |
| `evaluator`, `rubric`, `score` | 評価系章 |

Claude は task 受領時にこの表だけを読み、該当章を Read で取得する。

#### (2) frontmatter `context_refs:` field

Skill 側 frontmatter に `context_refs: ["07", "14"]` を持たせ、起動時に referenced 章だけを Read する。既存 `Additional resources` メカニズムの拡張として扱える。

#### (3) 14 章 `!` 動的注入との合成

`!` で task 分類 script を実行し、stdout の章 ID list を本文に焼き込む。Claude が見る時点で「次に Read すべき章」がすでに確定している（→ [14 章 §タスク分類による条件付き読込](./14-dynamic-context-injection.md#タスク分類による条件付き読込)）。

### `ref-task-context-map` 補助 Skill 構想

06 章の補助ファイル命名規約に従い、`ref-task-context-map.md` を設計書 root に置く案。役割は単一: **task category → 章 ID list の静的辞書**。Skill 本体からも script からも参照できる single source of truth とする。更新責務は本ファイル（07）が持つ。

### アンチパターン

| アンチパターン | 問題 | 対処 |
|---|---|---|
| 全 28 章 preload | token 即枯渇、lost-in-the-middle | 入口は map だけにする |
| 過剰 lazy load（map も読まない） | 関連章の取りこぼし、判断根拠の欠落 | map は必ず最初に Read |
| Claude の主観で章を選ばせる | 再現性なし、評価不能 | 決定論的 mapping に固定 |
| keyword 表を SKILL.md 本文に埋め込む | 表が肥大化し本文を圧迫 | 補助ファイルに逃がす |
