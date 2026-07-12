# Prompt: R1-init

> 7 層プロンプト。カテゴリ×canonical platform マトリクスを、必須 platform 行の全存在(対象外は理由付き)を検証して初期化する責務。カテゴリ初期集合の正本は C04 taxonomy。

## メタ

| key | value |
|---|---|
| name | init-matrix |
| skill | run-system-spec-elicit |
| responsibility | R1-init (taxonomy → 初期 spec-state.json) |
| layers_covered | [L1, L2, L3, L4, L5, L6, L7] |
| output_schema | references/spec-state-contract.md (spec-state.json) |
| reproducible | true |

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール
- カテゴリ初期集合は C04 taxonomy を Read して得る。prompt へ直書き禁止。
- 必須 canonical platform 6 種 (`web`/`mobile`/`tablet`/`desktop-windows`/`desktop-linux`/`desktop-macos`) の行を全カテゴリで全存在させる。
- 初期セルは全て `未収集`。状態書込は writer (`scripts/apply-spec-transition.py`) の一経路のみ。

### 1.2 倫理ガード
- taxonomy にない別名 platform を勝手に作らない。
- ユーザー入力を改変しない。

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (Single Responsibility)
- 担当: taxonomy からカテゴリ/platform を取得し初期マトリクスを生成、必須行の全存在を検証。カテゴリ軸の拡張発見もここ。
- 非担当: 個別セルのヒアリング (R2)、再質問 (R3)、reopen (R4)。

### 2.2 ドメインルール
- カテゴリの拡張発見・除外 (理由付き) は可。除外は `excluded_categories` に根拠を残す。
- `category_aggregate` は真理値表から導出 (writer が再計算)。手書きしない。

### 2.3 入力契約
| field | type | required | 説明 |
|---|---|---|---|
| taxonomy_path | path | yes | C04 system-category-taxonomy.json |
| existing_spec_state | path | no | 既存があれば再初期化しない (差分は R2/R3) |

### 2.4 出力契約
- `spec-state.json` (全セル `未収集`、`hearing_progress.complete=false`、`next_question` に最初の未収集セル質問)。

## Layer 3: インフラ層

### 3.1 参照リソース
| id | path | when_to_read |
|---|---|---|
| taxonomy | $CLAUDE_PLUGIN_ROOT/skills/ref-system-design-knowledge/references/system-category-taxonomy.json | カテゴリ/platform 初期集合の取得時 |
| contract | references/spec-state-contract.md | 形状/真理値表の確認時 |

### 3.2 外部ツール
- `Bash`: `python3 scripts/apply-spec-transition.py init --taxonomy <taxonomy_path> --out spec-state.json`

## Layer 4: 共通ポリシー

### 4.1 失敗時挙動
- 必須 platform が taxonomy に欠落 → writer が `TransitionError`。停止して報告 (fail-closed)。

### 4.2 最大反復
- 初期化は 1 回。再実行は既存 spec-state を上書きしない (存在時 skip)。

### 4.3 観測
- 初期化後に `validate-coverage-matrix.py --matrix spec-state.json` (loop) が exit0 を確認。

### 4.4 セキュリティ
- 秘匿情報を matrix / logs に格納しない。

## Layer 5: エージェント層 (l5-contract v2.0.0)

### 5.1 担当 agent
- run-system-spec-elicit の R1 局面 (inline)。

### 5.2 ゴール定義
- 目的: 後続ヒアリングが依拠できる、必須行が全存在した初期マトリクスを再現性高く用意する。
- 背景: カテゴリを prompt へ直書きすると SSOT が二重化する。taxonomy を唯一の正本にする。
- 達成ゴール: 全カテゴリ×6 platform が `未収集` で全存在し、`validate-coverage-matrix.py` (loop) が exit0。

### 5.3 完了チェックリスト (停止条件)
- [ ] stateのカテゴリ/platform集合がtaxonomy正本と一致する
- [ ] 全カテゴリ行に canonical 6 platform が全存在する
- [ ] 全セルが `未収集`、`category_aggregate` が全 `未着手`
- [ ] `validate-coverage-matrix.py --matrix spec-state.json` が exit0

### 5.4 実行方式
- 固定手順を持たない。状況に応じて必要な初期化内容を都度設計し、5.3 の全停止条件が満たされるまで初期stateを改善する。

## Layer 6: オーケストレーション

### 6.1 上位接続
- 呼び出し元: run-system-spec-elicit (開始局面)。後続: R2-interview。

### 6.2 並列性
- 単発。

## Layer 7: UI / 提示

### 7.1 提示形式
- 初期化サマリ (カテゴリ数 × 6 platform、未収集セル数)。

### 7.2 言語
- 日本語 (JSON キー/platform id は英語)。

---

## 出力指示

C04 taxonomy を Read し、`python3 scripts/apply-spec-transition.py init --taxonomy <path> --out spec-state.json` を実行して初期マトリクスを生成する。`validate-coverage-matrix.py` (loop) が exit0 になることを確認する。余計な前置き・思考過程出力は禁止。
