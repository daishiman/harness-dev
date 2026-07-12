# Skill Design Glossary

各エントリは `## <term>` → 定義 / 文脈 / 関連 の3行構成を原則とする。

## Goodhart
測定指標を最適化対象にすると指標自体が壊れる法則。Skill設計では「採点者と被採点物の context 分離」で構造的に防ぐ。関連: 09章, fork context, assign-evaluator。

## Generator/Evaluator
生成本体 (run-*) と評価器 (assign-*) を別 Skill / 別 context に分離する設計パターン。`pair:` frontmatter で双方向リンクする。

## fork context
Sub-agent 起動時に親 context を継承しない実行モード。assign-* は必ず fork で動かし、生成本体の作業メモリを汚さない。

## rubric_refs
Skill が依拠する rubric.json の参照リスト。L0 (upstream) → L1/L2 (local override) の順で deep-merge される。

## merge_strategy
rubric_refs の合成方式。`deep-merge` は同id ルールをフィールド単位でマージ、`replace` は丸ごと差し替え。

## conflict_policy
同一 rule_id が複数 layer で定義された際の解決方針。`most-specific-wins` = 後段 (L2) 優先、`upstream-wins` = L0 優先。

## deep-merge
辞書はキー再帰、配列は id 一致でフィールドマージ、スカラーは後勝ち（policy 依存）の合成アルゴリズム。

## Progressive Disclosure
SKILL.md 本文は100〜300行に圧縮、詳細は `references/` に分離する読込戦略。token 効率と認知負荷の最適化（07章）。

## dogfooding
自Skill群の lint / rubric を自Skill自身に適用すること。例: run-build-skill の SKILL.md を assign-skill-design-evaluator で採点。

## evaluator contract
assign-* が STDOUT に出す JSON スキーマ: `{rubric_id, rubric_version, rubric_hash, target, score, threshold, passed, findings[], pending_human[]}`。

## Output Contract
Skill 本文冒頭の `## Purpose & Output Contract` 節で宣言する I/O 仕様。テスト可能性とスクリプト実行モデル（28章）の前提。

## semver bump rules
rubric.json の version 更新規約。rule 削除/破壊的変更=major、rule 追加=minor、文言修正=patch。

## Gotchas
反パターン集。SKILL.md 必須節 `## Gotchas` に箇条書きで列挙、読者の事故を防ぐ（08章）。

## Less is More
description は発動条件のみ、本文は300行以下、references で深堀り、という設計哲学（24章）。

## Why-driven
rubric の各 rule に `rationale` を必須化し、ルールの理由を文書化する原則。

## Ubiquitous Language
DDDの「すべての関係者が同じ語で同じ概念を指す」原則。本 glossary が xlocal Skill群のユビキタス言語正本。

## Bounded Context
意味境界。assign-evaluator は採点 context、run-build-skill は生成 context として分離される。

## 4条件
タスク仕様書の品質ゲート: (1) 矛盾なし (2) 漏れなし (3) 整合性 (4) 依存関係整合。task-specification-creator スキル由来。

## composition_hash
複数 rubric_refs を deep-merge した結果の確定性ハッシュ (sha256)。再現性検証用、evaluator JSON 出力に含める。

## TODO(human)
rubric.json 内の人間判断保留マーカー。検出時は finding にせず `pending_human` 配列へ。
