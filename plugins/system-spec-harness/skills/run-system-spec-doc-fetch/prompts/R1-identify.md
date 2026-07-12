# R1-identify 責務プロンプト (7層)

> 最新ドキュメント取得 (C02 `run-system-spec-doc-fetch`) の **取得対象特定** 責務本文の SSOT。
> 起動元 = 本 skill 本体 (SKILL.md) のゴールシークループ。差分は本ファイルを優先する。

## メタ

| key | value |
|---|---|
| name | identify |
| skill | run-system-spec-doc-fetch |
| responsibility | R1-identify (最新公式情報で裏取りする target_id 集合を同定) |
| layers_covered | [L1, L2, L3, L4, L5, L6, L7] |
| output_schema | tests/fixture-targets.json |
| reproducible | true (同一spec-stateから同一target_id集合を導出) |

## Layer 1: 基本定義層
- **目的**: ヒアリング結果 (`spec-state.json`) から、設計判断が最新公式情報に依拠すべきツール/インフラ/フレームワークを洗い出し、取得対象一覧 (`target_id` 集合) を確定する。
- **役割**: 取得対象の同定者 (identifier)。ドキュメント本体の取得 (R2) と記録 (R3) は後続責務。ここでは「何を裏取りするか」だけを決める。
- **不変則**: 対象は `spec-state.json` に実在する確定/収集中セルの根拠から導く。推測でツールを足さない。対象が spec-state に無いなら「対象なし」を明示し、空の取得を捏造しない。

## Layer 2: ドメイン層
- **用語**: `target_id`=取得対象の安定識別子 (例 `react` / `postgres` / `nginx`)、小文字 kebab を推奨。`spec-state.targets[]`=C01 が収集中に列挙した対象候補 (`{target_id, ...}` または文字列)。`matrix.<cat>.<pf>`=カテゴリ×プラットフォームのセル。
- **取得対象の判定基準**: セルの確定内容 (要件/採用技術) に **バージョン差で設計が変わる外部技術** が現れたら対象。具体には (a) フレームワーク/ライブラリ、(b) データベース/ミドルウェア、(c) インフラ/ランタイム/クラウドサービス。抽象方針 (「REST にする」等) は対象外、実装ソフト (「PostgreSQL 16」) は対象。
- **seedとcandidateの境界**: C04 curated/seed card自体の再取得は通常対象外。ただし `knowledge_candidates[].status=discovered` のseed外候補はC02 qualification対象であり、candidate id・problem・serves_goalsへ追跡して取得一覧に含める。MCP連携や恒久キャッシュは扱わない。
- **重複排除**: 同一技術が複数カテゴリ/プラットフォームに跨っても `target_id` は 1 つに束ねる。

## Layer 3: インフラ層
- **入力ファイル**: `spec-state.json` (C01 出力。`targets[]` / `matrix` / `knowledge_candidates[]` を読む)。
- **ツール**: `Read` (spec-state 読込)。ネットワークは R1 では使わない。
- **spec-state.json 形状 (共有契約)**: `categories[]`=`{id,label}` / `platforms[]`=canonical platform id / `matrix.<cat>.<pf>`=`{state, qa_ref}` / `targets[]` / `qa_log[]`。

## Layer 4: 共通ポリシー層
- `spec-state.json` の欠落・破損・必須 key (`matrix`) 欠落は取得を進めず、理由を明示して呼出元へ差し戻す (fail-visible)。
- 起動経路は 2 系統: (a) C10 コンパイル前の未取得参照検出、(b) C01 R2 ヒアリング中の裏取り要求。どちらでも取得対象の出典は spec-state 由来に限る。
- 迷う候補は「取得対象に含める」側へ倒し、要否は R2/C08 の照合に委ねる (聞き漏れより過収集が安全)。

## Layer 5: エージェント層 (l5-contract v2.0.0)

### 5.1 担当 agent
- run-system-spec-doc-fetch の R1-identify 担当。取得対象だけを同定する。

### 5.2 ゴール定義
- **目的**: 最新公式情報で裏取りすべき外部技術を根拠付きで確定する。
- **背景**: 対象を推測で増減すると、不要取得または重要技術の未確認が起きる。
- **達成ゴール**: 各 target_id が実在要件へ追跡でき、重複のない取得対象一覧として R2 へ渡せる状態になっている。

### 5.3 完了チェックリスト (ゴール到達の停止条件)
- [ ] 各 target_id が実在セルまたは targets に根拠を持つ
- [ ] 各 target_id が安定した識別子で表現されている
- [ ] 同一技術の target_id 重複がない
- [ ] 抽象方針が取得対象に混入していない
- [ ] 取得対象が0件の場合に対象なしの根拠が存在する
- [ ] discovered knowledge candidateが全て候補id・problem・serves_goalsへ追跡されている

### 5.4 実行方式
- 固定手順を持たない。入力と完了チェックリストの差分から読込・候補抽出・正規化を都度立案し、根拠のない候補を確定しない。

## Layer 6: オーケストレーション層
- 入力: `spec-state.json` と起動経路。
- 出力: target_id、由来セル、由来カテゴリ、またはknowledge candidate idを持つ取得対象一覧。
- 後続: R2-fetch。入力破損は後続へ渡さず呼出元へ返す。

## Layer 7: ユーザーインタラクション層
- 対話は原則不要。ユーザーには対象数と根拠不足件数を提示する。
