# orchestrate-gate-pattern

> harness-creator 横断パターン。Step 5 / 5.5 / 6 の三段ゲート設計を抽象化 (ABS-001)。
>
> **read_when** (G9, plugin-level resource-map):
> - Step 5 / 5.5 / 6 の三段ゲート設計を新規 plugin に展開する時
> - Gate 間で同一 finding が重複検出された時 (優先順位 A>B>C>D を適用)
> - 1 ゲートで複数次元採点する設計提案を検出した時 (アンチパターン)
>
> 正本: `plugins/harness-creator/references/resource-map.yaml#orchestrate-gate-pattern`

## パターン概要

複数の品質ゲートを直列に配置し、各ゲートが独立した検証次元 (契約 / elegance / 規範 / 実行 acceptance) を担うことで、Goodhart 罠と単一ゲート過負荷を回避する。

## 抽象モデル

```
input ──▶ [Gate A: 機械契約] ──▶ [Gate B: elegance lint] ──▶ [Gate C: 規範採点] ──▶ output
              │                       │                          │
              ▼                       ▼                          ▼
         PKG-* fail              C1-C4 fail                rubric score < threshold
         (eval-log)              (verdict.json)            (assignment report)
```

## 責務直交ルール

| 次元 | 担当ゲート | 一次判定 |
|---|---|---|
| 契約適合 (binary, 機械検査) | Gate A | exit code |
| 設計 elegance (30 思考法) | Gate B | findings + verdict |
| rubric 適合度 (採点) | Gate C | score 集計 |
| 実行 acceptance (実走行動ログによる受け入れ: 起動 / 完走 (自走含む) / goal 適合の 3 軸判定) | Gate D | live-trial verdict + transcript |

衝突時の優先順位: A > B > C > D (契約 > elegance > 規範 > acceptance)。

### Gate D (実行 acceptance) の帰属

Gate D は `run-skill-live-trial` が担い、対象は **behavioral trait (自走 hook / 入れ子 Skill / 対話 gate) を持つ loop 実行系 skill のみ** (全 kind 常設ではない)。証拠は主張型で直交する: Gate A-C は design claim (設計 adequacy) を静的成果物で判定し、Gate D は behavioral claim (実行挙動) を実走証拠のみで判定する。Gate D の収束根拠に静的 verdict を混ぜず、Gate A-C の収束根拠に実走を要求しない。

### 構造粒度検証 (structure fidelity) の Gate 帰属

出力成果物の構造粒度検証 — 生成物が canonical な章 / section 構造・`required_fields` を満たすかの機械検証 — は **Gate A (機械契約) の一種**に属する。構造 fidelity は「契約が binary に充足されているか」を write なしで機械判定する検証であり、elegance (Gate B) や採点 (Gate C) とは検出粒度が異なるため、Gate A の read-only 契約検査として扱う。この採点は `assign-*` prefix の skill が担う (例: skill-intake の notion fidelity 検証)。構造充足は契約層の判定なので、fail 時は A > B > C > D の優先順位で最優先に解消する。

## 適用先

- `run-plugin-package-check` (Gate A)
- `run-elegant-review` (Gate B)
- `assign-skill-design-evaluator` (Gate C)
- `run-skill-live-trial` (Gate D, loop 実行系のみ)

## アンチパターン

- 1 ゲートで複数次元を採点する (検出粒度と修正粒度が一致しない)
- ゲート間で findings を握りつぶす (proposer ≠ approver 違反)
- Gate B / C で write を許す (read-only 強制で Sycophancy 予防)。write は別 step に分離

## 関連

- 25 章 §runbook Step 5 / 5.5 / 6
- 35 章 § 3 層メタモデル (Layer 2 = Review-level)
- ANAL-001 di-quartet (ref / lookup / assign / run の役割四重奏)
