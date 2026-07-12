# 26. メタSkillドッグフーディング

設計書 01-26 自身を Skill artifact とみなし、`assign-skill-design-evaluator` で採点する。これにより「Skill の作り方を書いた文書」と「Skill を作る Skill」と「採点する Skill」が同じ rubric で評価される閉ループを得る。

## なぜ必要か

- 設計書が rubric を満たさなければ、それを参照して作られる Skill も満たさない (推移律)
- 設計書 = 人間向けの README 化が進むと冗長化し、`run-build-skill` が参照しづらくなる
- 09 の sycophancy: 書き手が自分の文書を採点しても甘くなる → forked evaluator が必要

## 09 の Generator（生成役）/Evaluator（評価役） 分離を設計書群に適用

設計書を次のロールに割り当てる:

| ロール | 実体 |
|---|---|
| Generator（生成役） | 設計書の著者 (人間 or Claude) |
| Artifact（成果物） | `xl-skills/doc/スキルの設計書/*.md` |
| Evaluator（評価役） | `assign-skill-design-evaluator` を context: fork で起動 |
| Rubric（評価基準） | MVP では `assign-skill-design-evaluator/references/rubric.json`。昇格版では `ref-skill-design-rubric` (read-only) |

### 手順

1. 各設計書 `NN-*.md` を 1 artifact として扱う。
2. `assign-skill-design-evaluator` に渡すため、`name`/`description` を持つ仮想 frontmatter を「設計書 → Skill candidate」として供給するアダプタを `scripts/doc_to_skill_adapter.py` (Python3 stdlib) で生成。
3. forked evaluator が JSON を返す。
4. 結果を `xl-skills/eval-log/docs/<NN>-<timestamp>.json` に保存。
5. 全 26 本に対し集計し、平均 score / 最低 score / 共通 findings を週次レポート化。

## 再帰的 rubric チェック (設計書版)

rubric の中から、設計書にも適用可能なルールを抜粋:

| ルール | 設計書での意味 |
|---|---|
| DRY (01) | 同じ事を複数設計書で繰り返し書かない、リンクで一意化 |
| Less is More (08) | 正本リファレンスを除き、長文は補助ファイルへ分割 |
| Why（理由）-driven (08) | 各章冒頭に「なぜこの規約が必要か」 |
| 4条件PASS (01) | 矛盾なし / 漏れなし / 整合性あり / 依存関係整合を満たす |
| Gotchas（落とし穴） (08) | 設計書にも known-bad-pattern を含める |
| Progressive Disclosure（段階的開示） (07) | 詳細は `references/` 相当のサブ文書に逃がす |
| `max_skill_md_lines: 300` (24 rubric) | 生成対象 Skill と通常設計書は 300 行以内。`16` / `17` のような公式正本リファレンスは例外として長文を許容し、入口文書からリンクする |
| `trigger_count_min: 2` / `trigger_count_max: 3` (24 rubric) | 設計書内で例示する全 description 雛形が発動条件 2〜3 個を満たす |
| `description_no_action_detail: true` (24 rubric) | 設計書内 description 例から動作詳細（採点する／JSON で返す／段数）を排除 |

### 自己採点の追加観点（Phase3-H 由来）

`assign-skill-design-evaluator` で 01-26 を採点する際、次を機械チェックする:

- 設計書本文行数 ≤ 300 (`BD-003` 相当を設計書自身にも適用)
- 設計書内に登場する `description:` 例示が `trigger_count_min/max` を満たす (`FM-003`)
- 設計書内に登場する `description:` 例示に動作詳細トークンが混入していない (`FM-004`)
- 設計書内 description 例示が動詞 / 手順ベース (`FM-005`)

設計書自身がこれらを満たさない場合、`run-build-skill` が参照したときに「設計書の悪い例をそのまま新 Skill に持ち込む」事故が起きる。設計書 → Skill の推移律で品質が伝播するため、設計書側を rubric で先に守る必要がある。

## 自己進化フィードバック

```text
docs (artifact)
   │
   ▼
assign-skill-design-evaluator (fork)
   │
   ▼
findings: "10 と 17 で SubAgent 説明が重複 (DRY違反)"
   │
   ▼
fix: 重複箇所を 10 に集約、17 からリンク
   │
   ▼
re-eval → score 上昇を確認
```

同じ findings が `run-build-skill` 生成物でも頻出するなら、`templates/` か `rubric.json` を更新し、過去の Skill にも適用 (regression check)。

## dogfooding と `skill-only` モードの関係（恒久例外）

[36-plugin-package-harness-contract.md](./36-plugin-package-harness-contract.md) §`skill-only` では、`package_mode: skill-only` を「legacy / dev-only / migration exception」と定義し、新規量産では選択しない方針を取る。一方で本章の dogfooding ループ（設計書 01-26 自身を artifact とみなして `assign-skill-design-evaluator` に通す運用）は、配布対象ではなく設計書の自己検査であり、`/plugin install` UX を保証する必要がない。したがって dogfooding 用途に限り `skill-only` モードを**恒久例外として許容**する。これは 36章で列挙された3例外（legacy / dev-only / migration）のうち「dev-only（局所検証）」に該当し、設計書側に明示しておくことで「dogfooding が package completeness check に通らない」ことを fail として誤検知するのを防ぐ。dogfooding artifact は plugin package を構成しないため、36章の PKG-001〜010 は適用対象外であり、`completeness check: not applicable (dogfooding)` を完了レポートに残す。逆方向のリンクとして、36章 §`skill-only` 列挙箇所からは本章を「dev-only の恒久例外運用」として参照する。

## 運用ルール

- 設計書を変更したら必ず evaluator を再走させる (CI 化推奨: `TaskCompleted` Hook で gate)
- rubric を更新したら全設計書を再採点し、回帰を検知
- rubric 変更は生成物修正と同じ PR に混ぜない。別承認者と `rubric_hash` 記録で Goodhart（評価基準を都合よく歪める罠）を防ぐ。
- score < threshold の設計書はマージ禁止 (Goodhart（評価基準を都合よく歪める罠） 対策で rubric 改変は別 PR)

## 期待効果

- 設計書品質と Skill 品質が同一基準で担保される
- 「書いただけで動かない」設計書を rubric が機械的に排除
- メタSkill 自身も同じループで改善され続ける (自己進化)
