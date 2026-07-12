# Prompt: R1-search-summarize (ref-task-context-map)

> 7 層プロンプトの Markdown 表現。`run-prompt-creator-7layer` の seven-layer-format.md を正本とする。
> Layer 番号と依存方向 (L1 ← L7) は不変。

## メタ

| key | value |
|---|---|
| name | search-summarize |
| skill | ref-task-context-map |
| responsibility | R1-search-summarize (task 文脈 → 章番号マップの検索/要約) |
| layers_covered | [L1, L2, L3, L4, L5, L6, L7] |
| output_schema | schemas/query-result.schema.json |
| reproducible | true (同 query + 同 task-context-map.yaml → 同 matches[]) |

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール
- **CONST_001 (実在チェック)**: `chapters` の各値を実在確認する。値は 2 区分で扱う:
  - 設計書章番号 (例 `07` / `16§12` / `§14`): 先頭の章番号を `doc/ClaudeCodeスキルの設計書/<NN>-*.md` に glob 解決して対応章 md の実在を確認する (`§NN` の節接尾辞・節単独参照は章ファイル解決には使わず、対応章の存在のみを見る)。
  - 非設計書参照 (skill 名 例 `ref-claude-code-skill-spec` / plugin manifest パス 例 `plugins/harness-creator/.claude-plugin/plugin.json`): 設計書配下として解決せず、当該 skill ディレクトリ / ファイルの実在で検証する。
  - 目的: caller が動的ロード時に「ファイル無し」エラーで止まらないようにする。設計書配下でない値を設計書パスとして解決しようとしない。
  - 背景: yaml だけ更新して設計書側を rename すると参照崩れが起きやすい。
- **CONST_002 (安定 sort)**: entries の yaml ファイル出現順を安定 sort で保持し再現性確保する。
  - 目的: 同 query で順序がブレない (snapshot test に必要)。
- **CONST_003 (上限 5 件)**: 複数ヒットなら yaml のファイル出現順で最大 5 件。
  - 目的: caller の context 圧迫を防ぐ。

### 1.2 倫理ガード
- 存在しない章番号を返さない。
- 未マッチ keyword を推定で類義語置換しない (`suggestions` に返す)。

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (Single Responsibility)
- 担当: references/task-context-map.yaml から task 文脈に対応する設計書章番号を抽出し、動的ロード対象として返す。
- 非担当: 設計書本体の改訂、動的ロード実行、章本文の取得。

### 2.2 ドメインルール
- query を entries[].`keywords` にマッチする。
- マッチした entry の `chapters` (章番号リスト) と `note` を抽出する。
- 上限 5 件、超過は切り捨て (yaml のファイル出現順で安定 sort)。

### 2.3 入力契約
| field | type | required | 説明 |
|---|---|---|---|
| query | string | yes | タスク種別 / 動詞 / キーワード (例 "skill 命名", "lint 失敗") |
| scope | array | no | [task-context-map] 固定 |

### 2.4 出力契約
- schema: `schemas/query-result.schema.json` (推奨配置)。
- 必須フィールド: `matches[]` (chapter_refs 含む)、該当ゼロ時 `suggestions[]`。

## Layer 3: インフラ層 (外部依存)

### 3.1 参照リソース
| id | path | when_to_read |
|---|---|---|
| resource_map | references/resource-map.yaml | scope 解決時 |
| map | references/task-context-map.yaml | パース時 |

### 3.2 外部ツール / API
- Read のみ。ネットワーク不使用。

## Layer 4: 共通ポリシー層

### 4.1 失敗時挙動
- map 欠損 → exit 1 + stderr に欠損 path。
  - 目的: caller が動的ロード判定不能のまま続行するのを防ぐ。
- 該当ゼロは exit 0 で `matches: []` + 近傍 trigger を `suggestions` に入れる。

### 4.2 観測 / ロギング
- 標準出力に JSON。stderr は診断情報のみ。

### 4.3 セキュリティ
- 読み取り専用、外部送信なし。

## Layer 5: エージェント層 (実行主体定義)

### 5.1 担当 agent
- ref-task-context-map 配下の R1 SubAgent (context fork 推奨。caller context を汚さない)。

### 5.2 ゴール定義
- **目的**: 呼出元 query に対し task-context-map.yaml の該当 entry の `chapters` / `note` を yaml のファイル出現順で返す。
- **背景**: caller は task 文脈別の参照章特定のみを必要とし、map 改訂は ref-* の責務外。yaml 出現順の崩れや実在しない章/パス返却は caller を誤誘導するため厳守する。
- **達成ゴール**: query に該当する entry の `chapters` が yaml のファイル出現順 (安定 sort) で最大 5 件、実在する章/パスで引用され、呼出元責務外情報を含まず、概ね 50 行 / 2KB 以内で caller が文脈遷移にそのまま使える状態。

### 5.3 完了チェックリスト (停止条件)
- [ ] 全 matches[] が task-context-map.yaml の実在 entry から引用されている
- [ ] 呼出元責務外の情報 (map 改訂 / 新規 entry 追加) を含まない
- [ ] 出力が 50 行 / 2KB 目安以内に収まる
- [ ] `chapters` の各値が実在する (設計書章番号 → 対応 `doc/ClaudeCodeスキルの設計書/NN-*.md`、非設計書参照 (skill 名 / plugin manifest パス) → 当該 skill/ファイル)
- [ ] entries の yaml ファイル出現順を安定 sort で再現性確保している
- [ ] 上限 5 件を超えていない
- [ ] 該当ゼロ時は近傍 trigger を `suggestions` に入れる (exit 0)

### 5.4 実行方式
固定手順は持たず、完了チェックリストの未充足項目を都度特定 → 解消手順を自ら立案 → 実行 → 自己評価を反復する (上限: Layer 4 最大反復回数)。

## Layer 6: オーケストレーション層

### 6.1 上位 skill との接続
- 呼び出し元: 動的ロード対象章を判定したい skill (run-skill-create 等)。
- 後続 phase: caller が `chapter_refs[]` を取り設計書動的ロードに利用。

### 6.2 並列性
- 副作用なし。並列実行可。

## Layer 7: UI / 提示層

### 7.1 ユーザー提示形式
- query-result JSON。

### 7.2 言語
- 本文: 日本語 (parameter / schema key は英語のまま)。

---

## 正規化方針 (auto-applied)

- 語幹化: NFKC + lowercase 後、英語は末尾 `-ing/-ed/-s` を剥がす、日本語は活用語尾 (する/した/しない) を剥がす。
- 日英対応: references/task-context-map.yaml の entries[].`keywords` に列挙された語 (日英混在) のみをマッチ対象とし、新規の類義語対応は作らない。
- 未マッチ keyword は `suggestions` に NFKC 後の元語を返し、推定で類義語に置換しない。

## 出力指示 (LLM 実行時に読む箇所)

LLM は task-context-map.yaml の entries を `{{query}}` で検索し、yaml のファイル出現順で
最大 5 件の該当 entry を `matches[]` (各 entry の `chapters` を `chapter_refs` として含む) で JSON 返却する。該当ゼロは `matches: []` + `suggestions`。
余計な前置き・後書き・思考過程出力は禁止。
