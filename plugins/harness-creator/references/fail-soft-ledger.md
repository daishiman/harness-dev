# fail-soft 棚卸し台帳

fail-soft 構文 (`|| true`)・completeness 免除 (`completeness_exempt`)・縮小要件プレースホルダー (REDUCED_REQUIREMENT_PHASES) の全数棚卸し。目的は「意図的 fail-soft (正当) と理由不明の警告抑止 (ノイズ源) の分離」。一律排除はしない。

- 棚卸し日: 2026-08-23
- 対象: リポジトリ全体。ただし以下を除外 (理由は各節に記載)
- 本台帳は記録と勧告のみ。コードの実編集は別途判断。

## サマリ

| 種別 | 生の grep 件数 | 除外 | 対象 (判定済み) |
|---|---|---|---|
| `\|\| true` (advisory) | 86 行 | 74 行 (eval-log 実行ログ/rollback 台本 68・doc/参考Skill 第三者由来ドキュメント 5・yaml-spec-cache.md 外部仕様キャッシュ本文 1) | 12 行 (コード実行箇所 11 + コメント内言及 1) |
| `completeness_exempt` (exempt) | 231 行 | 162 行 (eval-log/doc/参考Skill) | 69 行 (frontmatter 宣言 47 エントリ/43 ファイル + 機構自体 (lint/validator/テスト/文書) 26 行) |
| REDUCED_REQUIREMENT (placeholder) | 12 行 | 0 行 | 12 行 (機構 4 + plugin-plans プレースホルダー 8) |

判定内訳 (対象のみ。機構定義・コメント言及は判定対象外):

| 判定 | `\|\| true` | exempt | placeholder |
|---|---|---|---|
| 正当な fail-soft と読める | 9 | 47 | 8 |
| 理由不明・要判断 | 1 | 0 | 0 |
| ゲート昇格候補 | 1 | 0 | 0 |
| 削除候補 | 0 | 0 | 0 |

**主要な発見**: 当初仮説「理由が記録されていない」は completeness_exempt には当てはまらない。`lint-skill-completeness.py` が `<category>: <reason>` 形式を強制しており (LS-211 ほか)、宣言 47 エントリすべてに実質的な理由文が付いている。理由不明の fail-soft はほぼ `|| true` 側に限られ、それも大半はコメントで意図が併記されている。

**ゲート昇格候補 (上位)**:

1. `.github/workflows/harness-creator-kit-ci.yml:202` — skill-fixture-runner が warn-only。コメント自身が「ベースライン整備後に blocking 化」と昇格を予告しており、予告のまま放置されている唯一の明示的昇格待ち。
2. (次点) `plugins/plugin-dev-planner/skills/run-plugin-dev-plan/SKILL.md:310` — lint-sibling-coupling が record-only。couples_with 宣言の運用が安定した時点で warn→gate 昇格を検討する価値がある (現状は安全網として正当)。
3. (次点) `installers/install.sh:217` — rubric-registry 整合チェックが WARN のみ。インストーラを赤にしない判断は妥当だが、CI 側に同等の blocking チェックがなければ片翼。

**次のアクション提案**:

- ci.yml:202 の blocking 化条件 (ベースライン整備) を bead 化し、昇格期限か判断者を決める。
- deploy-plugin.sh:126 の evidence snapshot 無音失敗 (下表・要判断) の意図を deploy script 所有者が 1 行コメントで確定させる。
- run-skill-feedback の prompts 免除 20 件は同一文面のテンプレート複製。免除自体は正当だが、文面変更時に 20 ファイル同期が必要になる点は SSOT 化の検討余地 (別 issue)。
- 次回棚卸しは末尾の再集計手順で差分を取る。

## 台帳: `|| true` (advisory)

| パス:行 | 種別 | 周辺コードから読み取れる意図 | 判定 |
|---|---|---|---|
| `Makefile:214` | (コメント) | 直下 2 件の許容理由を説明するコメント内の言及。コードではない | 判定対象外 |
| `Makefile:216` | advisory | `coverage erase` の初回実行 (データ無し) 許容。合否は `make test` が正と直上コメントに明記 | 正当な fail-soft と読める |
| `Makefile:218` | advisory | coverage 計測モードで一部 IO テストが赤化する既知事象の許容。合否判定は coverage 無し `make test` が正、と直上コメントに明記。閾値割れは後続行が WARN (ratchet) を出す | 正当な fail-soft と読める |
| `plugins/plugin-dev-planner/skills/run-plugin-dev-plan/SKILL.md:310` | advisory | lint-sibling-coupling を record-only (couples_with 宣言忘れの安全網・exit0) と同一行コメントで宣言 | 正当な fail-soft と読める (運用安定後の昇格検討余地) |
| `plugins/skill-intake/hooks/post-keychain-add.sh:26` | advisory | Keychain 取得失敗を変数空で受け、直後の `if [[ -z "$TOKEN" ]]` が FAIL 終了する。fail-soft ではなくエラーハンドリングの捕捉手段 | 正当な fail-soft と読める |
| `plugins/skill-intake/skills/run-notion-intake-publish/SKILL.md:204` | advisory | 任意ファイル (notion-url.txt) の不在許容。不在時は後段が初回公開経路に分岐する設計が直上コメントに明記 | 正当な fail-soft と読める |
| `.github/workflows/harness-creator-kit-ci.yml:202` | advisory | skill-fixture-runner の回帰 smoke。コメント (G-D1) に「現状 warn-only、ベースライン整備後に blocking 化」と昇格予告あり | ゲート昇格候補 |
| `.github/workflows/harness-creator-kit-ci.yml:263` | advisory | rubric bump 再評価。コメント (P1-4) に「notification 用途、exit 0 固定」と明記。直後 echo も non-blocking を宣言 | 正当な fail-soft と読める |
| `scripts/install-git-hooks.sh:7` | advisory | chmod 対象が clone 状態により不在でも hooks 切替を続行する初期化スクリプトの寛容化 | 正当な fail-soft と読める |
| `scripts/phase2/deploy-plugin.sh:126` | advisory | pre-state evidence (symlink 一覧) の snapshot。`.claude` 不在の初回 deploy 許容と読めるが、権限エラー等の収集失敗も無音で空 snapshot になり before/after 差分が誤る余地。意図コメントなし | 理由不明・要判断 |
| `.github/workflows/update-yaml-spec.yml:32` | advisory | 前回キャッシュの退避。初回実行 (キャッシュ不在) 許容。直上コメントに diff 計算目的が明記 | 正当な fail-soft と読める |
| `installers/install.sh:217` | advisory | rubric-registry の L1 整合チェック。欠落は WARN 出力のみでインストールは続行 (インストーラを整合性で赤にしない判断) | 正当な fail-soft と読める (CI 側に blocking 相当が無ければ昇格検討) |

除外 (74 行): `eval-log/**` (live-trial の transcript/pane 実行ログ、phase2 rollback 台本、elegant-review の patch スナップショット — いずれも過去実行の記録であり現行コードではない)、`doc/参考Skill/**` (参考用の第三者由来スキル文書)、`plugins/harness-creator/skills/ref-yaml-spec-fetcher/references/yaml-spec-cache.md:1528` (外部公式ドキュメントのキャッシュ本文中の記述)。

## 台帳: `completeness_exempt` (exempt)

frontmatter 宣言は全 47 エントリ (43 ファイル)。lint (`lint-skill-completeness.py`) が理由なし宣言を exit 1 にするため、全件に理由文がある。判定は理由文と実体の突合による。

### グループ A: run-skill-feedback の prompts 免除 (20 ファイル・同一テンプレート文面)

対象 (すべて `:46`、カテゴリ prompts): plugins/{contract-generator, dev-graph, extract-system-blueprint, guide-doc-generator, harness-creator, plugin-dev-planner, prompt-creator, skill-governance-adapters, skill-governance-automation, skill-governance-config, skill-governance-hooks, skill-governance-lint, skill-governance-migration, skill-governance-secrets, skill-intake, slide-report-generator, spec-drift-guardian, system-dev-planner, system-spec-harness, ubm-goal-setting}/skills/run-skill-feedback/SKILL.md

- 意図: 対話手順は Notion schema 正本から本文へ展開済みで、R-id 単位 prompts を置くと二重定義になる。整合は lint-feedback-protocol.py が検証、と理由文に明記。
- 判定: 正当な fail-soft と読める (20 件とも)。ただしテンプレート複製 20 件の文面同期コストは SSOT 化検討余地 (サマリ参照)。

### グループ B: manifest 免除 (21 エントリ) — goal-seek/inline engine・ref/assign 系

| パス:行 | 意図 (理由文の要約) | 判定 |
|---|---|---|
| `plugins/plugin-dev-planner/skills/run-plugin-dev-plan/SKILL.md:98` | goal-seek が手順を都度生成、固定 manifest 適用外。phase 定義は phase-lifecycle.md 参照 | 正当な fail-soft と読める |
| `plugins/dev-graph/skills/run-dev-graph-{node:52, sync:69, decompose:61, requirements:47, init:53, status:41, system-spec:46, schedule:41, render:41}/SKILL.md` (9 件) | goal_seek.engine=inline のため固定 phase manifest 適用外。停止条件は本文 ## ゴールシーク実行が正本 | 正当な fail-soft と読める (9 件とも) |
| `plugins/system-spec-harness/skills/run-system-spec-{compile:51, elicit:73, doc-fetch:45}/SKILL.md` (3 件) | 同上 (inline engine) | 正当な fail-soft と読める |
| `plugins/system-spec-harness/skills/ref-system-design-knowledge/SKILL.md:23` | ref/effect:none は不変参照資料で実行 workflow を持たない | 正当な fail-soft と読める |
| `plugins/system-spec-harness/skills/assign-system-spec-completeness-evaluator/SKILL.md:34` | assign evaluator は単発 fork 採点ゲートで rubric/schema/script が runtime SSOT | 正当な fail-soft と読める |
| `plugins/harness-creator/skills/{run-skill-live-trial:44, run-goal-seek:30, run-goal-elicit:25, run-skill-iter-improve:38}/SKILL.md` (4 件) | ゴールシークループで手順都度生成のため固定 manifest 適用外 | 正当な fail-soft と読める |
| `plugins/guide-doc-generator/skills/run-handout-{build:142, extract:24}/SKILL.md` (2 件) | 同上 (inline engine)。build は本文 ## ゴールシーク実行が正本と明記 | 正当な fail-soft と読める |

### グループ C: prompts 免除 (グループ A 以外・6 エントリ)

| パス:行 | 意図 (理由文の要約) | 判定 |
|---|---|---|
| `plugins/slide-report-generator/skills/ref-diagram-system/SKILL.md:20` | 正本への索引 skill。責務プロンプトを置くと二重管理 (lint-ssot-duplication 検出対象) | 正当な fail-soft と読める |
| `plugins/ubm-goal-setting/skills/run-ubm-knowledge-sync/SKILL.md:57` | LLM 責務は SubAgent knowledge-extractor.md が単独所有。skill ローカル prompts は二重定義。宣言と実体の一致まで理由文に明記 | 正当な fail-soft と読める |
| `plugins/harness-creator/skills/{run-skill-live-trial:44, run-goal-seek:30, run-goal-elicit:25, run-skill-iter-improve:38}/SKILL.md` (4 件・manifest と重複宣言) | ゴールシーク系で R-id 単位 7 層プロンプト適用外。正本 (task-template.md / goal-seek-paradigm.md 等) を明示 | 正当な fail-soft と読める |

### 判定対象外 (機構・記録): 26 行

免除「機構」自体の定義・検証・テスト・記録であり、免除の使用ではない:
`plugins/skill-governance-lint/scripts/lint-skill-completeness.py` (8 行)、`plugins/skill-governance-lint/tests/test_lint_regressions.py` (2 行)、`plugins/harness-creator/skills/assign-plugin-package-evaluator/scripts/validate-plugin-package.py` (4 行)、`tests/scripts-plugins/test_harness_creator__validate_plugin_package.py` (2 行)、`tests/scripts-plugins/test_skill_governance_lint__lint_skill_completeness.py` (4 行)、`plugins/harness-creator/skills/run-build-skill/SKILL.md` (2 行: チェックリストと lint 起動行)、`plugins/harness-creator/skills/run-build-skill/references/prompt-placement-convention.md:130` (規約文書)、`plugins/ubm-goal-setting/CHANGELOG.md:35` (変更記録)、`plugin-plans/guide-doc-generator/evidence/P05.json` (2 行: planner 所有の worker 裁量記録)。

除外 (162 行): `eval-log/**`・`doc/参考Skill/**` (実行ログと第三者由来文書)。

## 台帳: REDUCED_REQUIREMENT プレースホルダー (placeholder)

機構: `plugins/plugin-dev-planner/skills/run-plugin-dev-plan/scripts/check-downstream-harness.py` が `REDUCED_REQUIREMENT_PHASES = ("P03","P07","P09","P10")` を定義し、gate 系 phase は「判定記録そのものが受入例的性質を持つ」ため見出し存在のみを検査する (docstring に理由明記)。同 4 phase の空節は設計どおりの縮小要件であり、欠落の握りつぶしではない。

| パス:行 | 種別 | 意図 | 判定 |
|---|---|---|---|
| `plugins/plugin-dev-planner/skills/run-plugin-dev-plan/scripts/check-downstream-harness.py:27,41,93` | (機構) | 縮小要件の定義と適用。docstring に根拠 | 判定対象外 (機構) |
| `plugins/plugin-dev-planner/skills/run-plugin-dev-plan/tests/test_check_downstream_harness.py:42` | (機構) | 定数の回帰テスト | 判定対象外 (機構) |
| `plugin-plans/plugin-dev-planner/phase-{03:41, 07:40, 09:43, 10:40}-*.md` (4 件) | placeholder | 「縮小要件対象のため簡略形で足りる」と自己宣言する空節。planner 所有 | 正当な fail-soft と読める |
| `plugin-plans/harness-creator/phase-{07:40, 09:43, 10:41}-*.md` (3 件) | placeholder | 同上。planner 所有 | 正当な fail-soft と読める |
| `plugin-plans/finish/plugin-dev-planner/phase-05-implementation.md:34` | placeholder (設計記述) | 縮小要件機構そのものの実装設計の記録 | 正当な fail-soft と読める |

注: `plugin-plans/` 配下は planner 所有のため、本台帳から編集提案は出さない (記録のみ)。

## 再集計手順 (次回棚卸し用)

repo root で以下を実行し、本台帳の生件数と突合する。除外フィルタも同一にすること。

```bash
# advisory (生件数)
grep -rn '|| true' . --exclude-dir=.git | wc -l
# advisory (対象)
grep -rn '|| true' . --exclude-dir=.git --exclude-dir=eval-log | grep -v 'doc/参考Skill' | grep -v vendor

# exempt (生件数)
grep -rn 'completeness_exempt' . --exclude-dir=.git | wc -l
# exempt (対象・行レベル)
grep -rn 'completeness_exempt' . --exclude-dir=.git --exclude-dir=eval-log | grep -v 'doc/参考Skill' | grep -v vendor
# exempt (frontmatter 宣言ファイルとカテゴリ)
grep -rln 'completeness_exempt' plugins --include='SKILL.md'

# placeholder
grep -rn 'REDUCED_REQUIREMENT' . --exclude-dir=.git --exclude-dir=eval-log | grep -v 'doc/参考Skill' | grep -v vendor
```

前回実測 (2026-08-23): `|| true` 生 86 / 対象 12、`completeness_exempt` 生 231 / 対象 69 (宣言 47 エントリ)、REDUCED 生 12 / 対象 12。
