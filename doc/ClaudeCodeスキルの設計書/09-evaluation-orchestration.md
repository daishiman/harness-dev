# 09. 評価駆動オーケストレーション

## 読むべき関連章

- `03-*` evaluator と rubric_refs による依存注入の基本
- `27-rubric-governance-runbook.md` rubric 改正・例外承認（P3 governance）
- `28-script-execution-model.md` 決定論的スクリプト判定（P0）
- `29-multi-project-rubric-composition.md` domain（ドメイン） rubric（評価基準）の合成（P2）

## 自己申告を信用しない

ワークフロー型 Skill の最大の罠は、Claude の「完了しました」「問題ありません」「高品質です」を完了判定にすること。

これらは output ではない。完了判定は artifact と evaluator によって行う。

## Sycophancy

同じ文脈で生成し、同じ文脈で評価すると、作り手の意図や失敗理由を知っているため評価が甘くなる。画像ではこれを「甘い自己評価ループ」として示している。

対策:

- generator と evaluator を分ける。
- evaluator は `context: fork` で実行する。
- generator の会話履歴を渡さない。
- artifact / file 経由で評価する。
- 評価結果は JSON にする。

## Evaluator（評価役） が必要な場合 / 不要な場合

| 判断 | 例 | 対応 |
|---|---|---|
| 不要 | 単純な reference skill、短い説明、低リスクの会話回答 | output contract（契約） だけで足りる |
| 軽量でよい | Markdown report、簡単な checklist | self-check checklist を本文に置く |
| 必要 | code edit、document生成、PR review、design spec、user-facing artifact | forked evaluator を作る |
| 必須 | deploy 前判定、security review、大規模 migration | evaluator + deterministic checks + Hook / CI |

段階導入:

1. output contract（契約） を書く。
2. checklist を書く。
3. repeated failure を Gotchas（落とし穴）に書く。
4. evaluator を `assign-*-evaluator` として分離する。
5. 必要なら `TaskCompleted` / `SubagentStop` hook で gate する。

## 汎用 Evaluator（評価役）と domain（ドメイン） rubric（評価基準）

評価 Skill は「どんな成果物でも同じ基準で全部評価する万能 Skill」にはしない。最適形は **少数の汎用 evaluator が、対象に応じた rubric / references / CLI 結果を読む** 構造である。

共通 evaluator が見るもの:

- frontmatter / name / directory などの構造品質
- output contract（契約）の有無
- Progressive Disclosure（段階的開示）の設計
- forbidden action / permission / side effect の扱い
- rubric hash / score / findings の出力形式

対象別 rubric が見るもの:

- プロジェクト固有の業務ルール
- API / DB / UI / security / marketing などの domain 基準
- タスクごとの done 条件
- 案件ごとの禁止事項、承認条件、例外

```text
assign-generic-artifact-evaluator
  -> references/evaluator-contract（契約）.yaml       # 共通出力契約
  -> ref-skill-design-rubric                  # Skill設計共通基準
  -> ref-<domain>-quality-rubric              # domain基準
  -> scripts/lint-*.{sh,py,ps1}               # 機械判定
  -> artifact                                 # 評価対象
```

この構造なら、評価 Skill を大量に増やさずに、基準だけを差し替えられる。LLM は「基準を解釈して findings をまとめる」役割に寄せ、機械的に判定できるものは scripts / Hook / CI に寄せる。

## 標準 evaluator 分類

Evaluator（評価役） はむやみに増やさない。増やす基準は「評価対象 artifact の型」と「評価手順の根本差」で判断する。

| 種類 | 役割 | 増やしてよい条件 |
|---|---|---|
| `assign-generic-artifact-evaluator` | Markdown / JSON / code diff など一般 artifact の構造品質を評価 | 出力契約・rubric hash・findings schema だけを共通評価したい |
| `assign-skill-design-evaluator` | `SKILL.md` と Skill ディレクトリ構造を評価 | Skill frontmatter、命名、Progressive Disclosure（段階的開示）、dependency topology が評価対象 |
| `assign-<domain>-evaluator` | security / legal / brand など domain 専門評価 | domain 特有の評価手順、専門用語、危険操作の扱いが generic evaluator では表現できない |

原則:

- 評価基準が違うだけなら evaluator を増やさず `rubric_refs` を追加する。
- 根拠資料が違うだけなら evaluator を増やさず `reference_refs` を追加する。
- 機械判定が増えただけなら evaluator を増やさず `script_refs` を追加する。
- evaluator を増やすのは、artifact の読み方や評価手順そのものが変わる場合だけ。

## 評価ピラミッド

評価は単一の LLM judge ではなく、責務とコストの異なる4層のピラミッドとして組み立てる。下層ほど決定論的・低コスト・高頻度、上層ほど判断的・高コスト・低頻度になる。下層で落とせる違反を上層に持ち込まないことが、評価コストと評価品質の両立に効く。

```text
         [P3 Human governance]        <- rubric改正・例外承認
      [P2 LLM: domain（ドメイン） rubric（評価基準）評価]     <- project/security/perf固有
   [P1 LLM: 構造・責務分離評価]        <- 共通品質 (ref-skill-design-rubric)
 [P0 Script: schema/lint/naming]      <- 決定論的、CI/Hookで自動実行
```

各層の責務:

| 層 | 判定主体 | 実行コンテキスト | 主な対象 | 成果物 | 参照章 |
|---|---|---|---|---|---|
| P0 | Script / CLI (lint, schema, naming) | CI / Hook / pre-commit | frontmatter、命名、禁止語、ファイル存在 | pass/fail + machine findings (JSON) | `28-script-execution-model.md` |
| P1 | LLM evaluator（汎用） | `context: fork` の subagent | 構造、責務分離、出力契約、Progressive Disclosure（段階的開示） | score + findings (`ref-skill-design-rubric` 基準) | 本章 / `03` |
| P2 | LLM evaluator（domain（ドメイン） rubric（評価基準） 注入） | `context: fork` の subagent | project / security / performance / marketing 固有基準 | score + required_fixes (domain（ドメイン） rubric（評価基準） 基準) | `29-multi-project-rubric-composition.md` |
| P3 | 人間レビュー | governance runbook | rubric 改正、例外承認、価値判断、規程の変更 | decision log + rubric version bump | `27-rubric-governance-runbook.md` |

層間の流れ:

- P0 で失敗 → P1/P2 を起動しない（LLM 呼び出しコストを払わない）。
- P1 で構造違反 → P2 (domain) を起動しない（共通品質を満たさない artifact に domain 評価は意味がない）。
- P2 で曖昧 / 例外候補 → P3 にエスカレーション。
- P3 の決定 → P0/P1/P2 の rubric / script に反映され、次回からは下層で機械判定される（governance loop）。

P1 と P2 はどちらも LLM 評価だが、rubric の出所が異なる。P1 は全 Skill 共通の `ref-skill-design-rubric` のみを根拠にし、P2 は domain（ドメイン） rubric（評価基準） を frontmatter の `rubric_refs` で依存注入する。

## 評価の4層

| 層 | 担当 | 例 | 出力 |
|---|---|---|---|
| P0 deterministic | CLI / lint / schema | name、frontmatter、file existence、禁止語 | pass/fail + machine findings |
| P1 common quality | generic evaluator | 構造、責務分離、出力契約、依存方向 | score + findings |
| P2 domain quality | domain（ドメイン） rubric（評価基準） + evaluator | 業務妥当性、API契約、マーケ基準、security観点 | score + required_fixes |
| P3 governance | 人間レビュー | 例外、改正、承認、曖昧な価値判断 | decision log |

P0 で落とせるものを P1/P2 の LLM 評価に持ち込まない。P1 は全 Skill 共通、P2 は対象 domain ごと、P3 は機械化しない裁定として分ける。

## Role（役割）

| 役割 | Skill 名例 | 仕事 |
|---|---|---|
| Generator（生成役） | `assign-pr-review-generator` | 成果物を作る |
| Evaluator（評価役） | `assign-pr-review-evaluator` | 成果物を採点する |

## 評価ループ

```text
Generator（生成役）
  -> Artifact（成果物）
  -> Evaluator（評価役）
  -> score < threshold なら Generator（生成役） へ戻す
  -> passed なら Done
```

## Evaluator（評価役） 契約

Evaluator（評価役） は:

- rubric を編集しない。
- artifact だけを評価する。
- generator の内部意図を根拠にしない。
- 必要な rubric / references / CLI 結果を明示的に読む。
- 読んだ rubric の `rubric_id` / `rubric_version` / `rubric_hash` を出力に含める。
- score / passed / findings / required_fixes を返す。
- security や permissions に関わる危険操作を行わない。

evaluator は `rubric_refs` frontmatter で複数 rubric を依存注入する。共通 rubric (P1) と domain（ドメイン） rubric（評価基準） (P2) を組み合わせて評価する設計が基本で、evaluator 本体は注入された rubric を読むだけのシンプルな構造に保つ。詳細は `03` および `29-multi-project-rubric-composition.md` を参照。

## JSON schema 例

```json
{
  "score": 82,
  "passed": true,
  "threshold": 80,
  "rubric": {
    "rubric_id": "skill-design",
    "rubric_version": "1.0.0",
    "rubric_hash": "sha256:..."
  },
  "machine_checks": [
    {
      "check": "lint-skill-name",
      "passed": true
    }
  ],
  "findings": [
    {
      "severity": "medium",
      "area": "frontmatter",
      "message": "`description` includes output format details that should move to body."
    }
  ],
  "required_fixes": []
}
```

## `pair:` の設計

```yaml
pair: assign-skill-review-generator
```

用途:

- generator / evaluator の対応を機械集計する。
- 孤児 evaluator を検出する。
- orchestrator が generic loop を回せるようにする。

## `rubric_refs:` の設計

Evaluator（評価役） を増やしすぎないため、評価対象側または orchestrator 側に `rubric_refs` を持たせる。単数形 `rubric_ref` は旧記法として読めるが、新規設計では必ず複数形を使う。

```yaml
pair: assign-skill-build-generator
rubric_refs:
  - ref-skill-design-rubric
  - references/project-rules.yaml
  - scripts/lint-skill-tree.py
```

`rubric_refs` は一方向依存である。artifact / generator は evaluator を直接制御せず、evaluator は `rubric_refs` に列挙された read-only 情報と deterministic check の結果だけを根拠にする。

設計判断:

- evaluator は「採点エンジン」であり、採点基準そのものを本文に持たない。
- company / domain / project / task ごとの違いは `rubric_refs` で注入する。
- P0 の script 結果も rubric component と同じく evaluation input として扱い、LLM が機械判定を再解釈して上書きしない。
- `rubric_refs` の選択責任は orchestrator / runner が持つ。evaluator が実行中に都合のよい rubric へ差し替えることは禁止する。

## Goodhart（評価基準を都合よく歪める罠） 対策

評価基準を成果物側が書き換えられると、agent は成果物ではなく rubric を攻略する。

対策:

- rubric（評価基準）は read-only reference に置く。
- evaluator は rubric を編集しない。
- permissions で evaluator の Write/Edit を制限する。
- rubric hash を記録する。
- score だけでなく findings を要求する。
