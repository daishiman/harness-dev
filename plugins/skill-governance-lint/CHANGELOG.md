# 変更履歴

## 0.1.26 — 2026-11-15

- build-plugin-release.py の自動採番で作られた版。変更内容の記述は未記入。

## 0.1.25 — 2026-11-14

- lint-skill-description.py に `--skill DIR|SKILL.md` を足した。run-build-skill Step 4 は生成した skill だけを検査し、同じ plugin の既存 skill の違反で新規 build が止まらなくなる。指定した path に SKILL.md が無ければ違反として返す。
- lint-plugin-composition.py の docstring の例示を、削除済みの名前から現存する名前に替えた。
- lint-script-frontmatter.py から、削除済み script への参照を外した。

## 0.1.24 — 2026-11-02

- build-plugin-release.py の自動採番で作られた版。変更内容の記述は未記入。

## 0.1.23 — 2026-11-02

- JSON形式のplugin-composition.yamlも既存の部品・依存・公開面・版の検査へ接続する。JSON破損・型不正は拒否する。
- 元作業ツリーの旧採番メモはdocs/branch-publicationのsource snapshotへ保持する。
