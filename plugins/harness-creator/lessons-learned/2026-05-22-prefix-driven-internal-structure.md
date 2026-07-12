---
date: 2026-05-22
---

# prefix-driven internal structure

## 背景

Skill 名 prefix (run-/assign-/ref-/wrap-/delegate-) は外部識別子としては機能していたが、内部ディレクトリ構造は Skill ごとにバラつきがあった。とくに ref-* で `rubric.json` を直下に置く流派と `references/rubric.json` に置く流派が混在していた。

## 知見

prefix は内部構造規約の鍵としても使う。ref-* は「機械可読リソースの正本」であり、SKILL.md の隣に複数リソースが並ぶ可能性が常にある。よって rubric.json 等の data ファイルは最初から `references/` 配下に置くのが拡張性・lint 一貫性の両面で勝つ。直下配置は単発の data 1 ファイルだけ存在する瞬間にしか正当化できない。

## 適用先

- ref-* Skill: 機械可読リソースは必ず `references/` 配下。lint で強制。
- assign-* Skill: 評価対象 rubric も `references/rubric.json` に置く (既に準拠)。
- run-* Skill: templates/ scripts/ examples/ を prefix とは独立に使用可。
