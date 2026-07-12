# Prompt: R2-recommend

> このファイルは 7 層プロンプトの Markdown 表現。`run-prompt-creator-7layer` の
> seven-layer-format.md を正本とする。Layer 番号と依存方向 (L1 ← L7) は不変。

## メタ

| key | value |
|---|---|
| name | R2-recommend |
| skill | run-blueprint-apply |
| responsibility | R2 採用/回避/差別化の 3 分類推奨導出 (1 prompt = 1 責務) |
| layers_covered | [L1, L2, L3, L4, L5, L6, L7] |
| output_schema | ../../../schemas/system-blueprint.schema.json |
| reproducible | true (同一 blueprint/自社コンテキストで同一 recommendations) |

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール
- 全 recommendation は `kind=inference`。blueprint に無い事実を新規主張しない (kind=fact 新規レコード禁止)。
- 各項目は blueprint 実在 anchor への `evidence_refs` (≥1) と `confidence{level,rationale}` と `own_context_ref` を必須で持つ。接地なき一般論を出さない。
- 分類は `adopt` (採用) / `avoid` (回避) / `differentiate` (差別化機会) の 3 種のみ。他分類を作らない。

### 1.2 倫理ガード
- 参考/学習目的の適用判断であることを前提に、対象を貶める断定や競合排除の煽動を書かない。推奨は自社実装判断の材料に留める。

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (Single Responsibility)
- 担当: blueprint の fact/inference と自社コンテキスト 4 面の突合、採用/回避/差別化機会の 3 分類 recommendations 導出。
- 非担当: 受理検証 (R1)、emit と self-check (R3)。

### 2.2 ドメインルール
- 突合対象は blueprint の fact (観測) と inference (essence 章の JTBD/価値提案/positioning・design tokens・tech_stack・nonfunctional_baseline・security_design・delivery_topology 含む)。
- **adopt**: 自社の技術スタック/既存資産で実現可能かつ対象ユーザーへ価値がある要素。**avoid**: 自社のリソース制約/対象ユーザー差から採らない方がよい要素 (理由を confidence.rationale へ)。**differentiate**: 対象が満たしていない/自社が優位に立てる差別化機会。
- 各 evidence_ref は blueprint の `anchor|id|screen_id|element_id|record_id|ref` 値・top-level `anchors[]`・top-level 章キー (`screens`/`design_tokens`/`tech_stack`/`essence`/`nonfunctional_baseline` 等) のいずれかへ解決する文字列にする。

### 2.3 入力契約
| field | type | required | 説明 |
|---|---|---|---|
| blueprint | json | yes | R1 が受理した blueprint.json (fact/inference/anchor) |
| own_context_4面 | struct | yes | R1 の技術スタック/制約/既存資産/対象ユーザー (own_context_ref 付き) |

### 2.4 出力契約
- `recommendations[]`: 各項目 `{kind:"inference", category ∈ {adopt,avoid,differentiate}, claim, own_context_ref, evidence_refs:[...], confidence:{level ∈ {high,medium,low}, rationale}}`。
- 3 分類が全て空でない (各分類に少なくとも実在根拠のある推奨を導出できたものを載せ、根拠なき捏造で埋めない)。

## Layer 3: インフラ層 (外部依存)

### 3.1 参照リソース
| id | path | when_to_read |
|---|---|---|
| blueprint 正本 | `<blueprint_dir>/blueprint.json` | fact/inference/anchor の突合元 |
| apply 検査契約 | `$CLAUDE_PLUGIN_ROOT/scripts/doc-emit.py` (--check-apply) | recommendations shape の SSOT 確認 |

### 3.2 外部ツール / API
- 重い突合・導出は Task で独立 context へ fork し、recommendations JSON を成果物ディレクトリへ直接書き出す (応答長起因の無言欠落を排除)。親へは最終 JSON パスと要約のみ返す。
- network なし。対象 origin へアクセスしない。

## Layer 4: 共通ポリシー層

### 4.1 失敗時挙動
- evidence_ref が blueprint anchor へ解決できない/kind=fact を作ってしまった項目は R3 の `--check-apply` で exit1 になるため、該当項目を anchor 解決可能な inference へ修正して再導出する。最大反復回数: 3。

### 4.2 観測 / ロギング
- stdout に 3 分類件数と代表推奨。周回状態は `eval-log/run-blueprint-apply-intermediate.jsonl` へ追記する。

### 4.3 セキュリティ
- 自社コンテキストの機微を claim へ生のまま露出しない (own_context_ref で参照する)。blueprint 本体を書き換えない。

## Layer 5: エージェント層 (ゴール駆動の実行主体)

### 5.1 担当 agent
- 重い突合・3 分類導出を独立 Task context へ fork する。fork 先は fact/inference と 4 面自社コンテキストの突合結果を recommendations JSON として書き出す。

### 5.2 ゴール定義
- 目的: blueprint の fact/inference と自社コンテキストの突合から、実行可能で追跡可能な採用/回避/差別化の 3 分類推奨を導出する。
- 背景: blueprint は対象の記述で完結し「自社ならどうするか」を出さない。自社接地の推奨を evidence 追跡可能な inference として与えることで、追加ヒアリングなしに実装判断へ繋げる。
- 達成ゴール: adopt/avoid/differentiate の 3 分類 recommendations が導出され、全項目が kind=inference + blueprint 実在 anchor への evidence_refs + confidence + own_context_ref を持ち、blueprint に無い事実を新規主張していない状態。

### 5.3 完了チェックリスト (ゴール到達の停止条件)
- [ ] blueprint の fact/inference (essence/design tokens/tech_stack/nonfunctional_baseline 含む) と 4 面自社コンテキストを突合した
- [ ] 採用/回避/差別化機会の 3 分類へ recommendations を導出した
- [ ] 全項目が `kind=inference` で blueprint に無い事実を新規主張していない
- [ ] 各項目が blueprint 実在 anchor への evidence_refs (≥1) + confidence{level,rationale} + own_context_ref を持つ
- [ ] 各推奨が自社コンテキストの制約 (技術スタック/リソース/既存資産) へ接地している

### 5.4 実行方式
- 固定手順を持たない。未充足項目を特定→手順を都度立案 (突合 / 分類 / anchor 付与 / confidence 付与)→実行→チェックリストで自己評価→全項目充足まで反復する (上限: Layer 4 最大反復回数)。

## Layer 6: オーケストレーション層 (ゴールシーク制御)

### 6.1 上位 skill との接続
- 呼び出し元: `run-blueprint-apply` SKILL の R2-recommend 局面。
- 後続 phase: R3-emit が recommendations を md/json へ emit し `--check-apply` で自己検証する。

### 6.2 ハンドオフ / 並列性
- 提供元: R1 (受理 blueprint + 4 面自社コンテキスト)。
- 受領先: R3-emit。
- 引き渡し形式: recommendations JSON (成果物ディレクトリ配下)。

## Layer 7: UI / 提示層

### 7.1 ユーザー提示形式
- 画面に 3 分類件数・代表推奨・確度分布サマリ (Markdown)。

### 7.2 言語
- 本文: 日本語 (JSON キー / enum / anchor は原文)。

---

## 出力指示 (LLM 実行時に読む箇所)

LLM はここから下の指示のみを実行し、Layer 1〜7 はコンテキストとして参照する。

R1 が受理した blueprint の fact/inference (essence 章・design tokens・tech_stack・nonfunctional_baseline 含む) と 4 面自社コンテキスト (技術スタック/制約/既存資産/対象ユーザー) を突合し、採用 (adopt)/回避 (avoid)/差別化機会 (differentiate) の 3 分類 recommendations を Task で独立 context へ fork して導出する。各項目は `{kind:"inference", category, claim, own_context_ref, evidence_refs:[blueprint 実在 anchor], confidence:{level,rationale}}` とし、blueprint に無い事実を新規主張しない。evidence_ref は blueprint の anchor/id/screen_id/element_id/record_id/ref 値・top-level 章キーのいずれかへ解決する文字列にする。Layer 5 の完了チェックリストを唯一の停止条件とし、未充足項目を特定→解消手順を都度立案→実行→自己評価→全項目充足まで反復する (固定手順なし、上限: Layer 4 最大反復回数)。出力は 3 分類件数・代表推奨・recommendations JSON パスのみ、前置き禁止。
