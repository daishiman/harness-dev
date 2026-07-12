# 23. メタSkillアーキテクチャ

## 読むべき関連章

本章はメタSkillアーキテクチャの中核設計を扱うが、運用詳細・実行モデル・多重継承・パラダイム対応は以下の章に委譲する。

| 章 | 主題 | 本章との関係 |
|---|---|---|
| 24-meta-skill-templates.md | メタSkill正本テンプレ | 本章のアーキテクチャ案A/Bを実装する雛形 |
| 25-meta-skill-runbook.md | 実行 runbook | generator/evaluator の実行手順 |
| 26-meta-skill-dogfooding.md | ドッグフーディング | 自己進化ループの運用 |
| 27-rubric-governance-runbook.md | rubric governance 詳細手順 | 本章 governance 節の詳細委譲先 |
| 28-script-execution-model.md | script の実行モデル | 本章で言及する `scripts/lint-*` の実行詳細 |
| 29-multi-project-rubric-composition.md | rubric 多重継承パターン | 本章で言及する `ref-*` 階層化の詳細 |
| 30-paradigm-analogy-map.md | パラダイム対応マップ | アーキテクチャ案A〜Eの位置付け |
| 34-plugin-governance-roadmap.md | plugin 移行ガバナンスロードマップ | 本章 案D/案D’ の移行条件・Phase 0-4・公式制約照合 |

## 問題提起: 設計書を読まないとSkillが作れない

00〜26 の設計書は「Skill の書き方の知識」を網羅している。だが現状、新しい Skill を作るたびに人間または Claude が:

1. 多数の設計書を都度読み返す
2. frontmatter 規約 (03) / 命名 (06) / Progressive Disclosure（段階的開示） (07) / Gotchas（落とし穴） (08) を手作業で組み立てる
3. forked evaluator (09) を毎回スクラッチで書く

これは「設計書がある」だけで、アウトカム (動く `.claude/skills/<name>/SKILL.md` 群) には到達していない状態。設計書群そのものが Progressive Disclosure（段階的開示） 原則に反した「全部読め」になっている。

## 代替アーキテクチャ比較

メタSkillの構造には複数の選択肢があり、フェーズ・規模・governance要求に応じて使い分ける。以下6案を比較する。

### 案A: 現状（generator + evaluator + rubric埋込）

`run-build-skill` + `assign-skill-design-evaluator` + `assign.../references/rubric.json`。rubric（評価基準）は evaluator 配下に埋め込み。MVP の標準形。

- 長所: Skill数最小（2）、依存単純、立ち上げが速い
- 短所: rubric が evaluator にロックインされ、共有・独立 versioning が難しい

### 案B: 昇格版（generator + evaluator + ref-skill-design-rubric 独立）

案A の rubric を独立 Skill `ref-skill-design-rubric` に昇格。複数 evaluator が同一 rubric を参照可能。

- 長所: rubric の共有正本化、独立 versioning、Goodhart（評価基準を都合よく歪める罠） 対策がしやすい
- 短所: Skill数 +1、参照経路の更新が複数箇所に発生

### 案C: 設定埋込（claude-code settings に rubric/templates を埋め込み、Skill廃止）

メタSkill そのものをやめ、`.claude/settings.json` や hook に rubric / templates を埋め込み、生成は通常の Claude セッションで行う。

- 長所: Skill 管理コストゼロ、公式機能のみで完結
- 短所: Progressive Disclosure（段階的開示） 不能、rubric の独立性なし、評価が hook 任せで Goodhart（評価基準を都合よく歪める罠） 検知が弱い

### 案D: Plugin型（evaluator を plugin distribution: npm/pkg）

evaluator を npm パッケージや plugin として配布し、`assign-*` Skill は薄い wrapper にする。

- 長所: バージョン管理が成熟したエコシステムに乗る、CI 親和性高い
- 短所: 公式 Skill 仕様から外れ、Claude Code のネイティブ機構（forked context, references）の利得を失う

### 案D': 公式 .claude-plugin/ 型（Claude Code 公式 plugin 機構を活用）

Claude Code が将来正式サポートする `.claude-plugin/` ディレクトリ形式（またはそれに準ずる公式仕組み）を使い、Skill 群を plugin 単位でパッケージ化する案。案D（npm/pkg 配布）とは異なり、Claude Code のネイティブ機構の上に乗る点が本質的な差異。

**案D vs 案D' の区別（PF-A4 アブダクション検証）:**

| 軸 | 案D（npm/pkg Plugin） | 案D'（公式 .claude-plugin/ 型） |
|---|---|---|
| 配布媒体 | npm / pip / パッケージマネージャ | Claude Code 公式 marketplace または `.claude-plugin/` |
| Claude Code 機構との関係 | 外れる（native forked context 喪失） | 乗る（公式機構上で plugin スコープを得る） |
| permissions 宣言 | plugin スコープ外で宣言不可 | 公式仕様内で宣言（ただし現時点で未確定部分あり） |
| 外部参照制約 (公式制約 e) | scripts/adapters/ 等への隠れ依存リスク | plugin 境界内に閉じる必要あり（棚卸し必須） |
| 採用前提条件 | Phase 0 完了 + 配布計画確定後 | Phase 0 完了 + **全 SKILL.md 外部参照棚卸し** 完了後 |

- 長所: 公式 Skill 機構の利点を維持しながら namespace 独立性・再利用性を得られる（実現すれば）
- 短所: 2026-05-18 時点で公式仕様が未確定。`classify_change` stub 未実装の状態では移行禁止（33章・34章参照）
- **警告**: plugin 移行前に全 SKILL.md の外部参照棚卸しが必須（3アナリスト独立検出：PF-A7/PF-C05/PF-G04）

### 案E: 契約JSON（.claude/contract（契約）s/*.json で intent/boundary を機械可読化）

rubric を yaml ではなく JSON Schema ベースの「契約」として `.claude/contract（契約）s/` に置き、generator と evaluator がそれを共通入力とする。

- 長所: 機械可読性最大、IDE / lint との統合容易、契約の差分が diff レビューしやすい
- 短所: 自然言語的な評価軸（説明品質など）が表現しづらい、契約スキーマ設計コストが高い

### 比較表

| 軸 | 案A 現状 | 案B 昇格版 | 案C 設定埋込 | 案D Plugin型 | 案D' 公式plugin型 | 案E 契約JSON |
|---|---|---|---|---|---|---|
| Skill 数 | 2 | 3 | 0 | 1〜2 | 2〜4 | 2 |
| governance 難度 | 中（rubric 改正は evaluator と同梱） | 低（rubric 独立で履歴管理しやすい） | 高（settings 散在） | 中（pkg version + Skill 同期） | 中〜高（plugin 境界 + 棚卸しコスト） | 低（schema diff で機械的） |
| 多重継承耐性 | 弱（rubric が evaluator 配下） | 強（`ref-*` を階層化可能、29 章参照） | 弱（settings は階層化困難） | 中（pkg の peer dep に依存） | 中（plugin スコープ内に限定） | 強（schema extends で表現） |
| 公式追従性 | 高（公式 Skill 機構をそのまま使う） | 高 | 中（公式 Skill を捨てる） | 低（公式機構から外れる） | 高（公式機構上だが仕様未確定） | 中（公式仕様外の慣習） |
| 採用推奨フェーズ | MVP（最初の1〜2 Skill） | evaluator が複数化した後 | 非推奨（Skill を捨てる積極理由がない場合） | 大規模・社外配布 | Phase 0 完了 + 外部参照棚卸し完了後 | 機械検証可能な契約が中心の領域 |

### 結論: 案A → 案B 段階昇格を推奨

- MVP では **案A** を採用する。Skill 数を抑え、立ち上げ速度を優先する。
- evaluator が複数化（例: skill 設計 evaluator とは別に security evaluator が必要になる）したら **案B** に昇格し、`ref-skill-design-rubric` を独立させる。
- 案C/D/E は本リポジトリの現フェーズでは非採用。ただし将来、社外配布・機械契約中心領域に拡張する場合は再検討する。
- 案D' は plugin 移行への自然な経路だが、**Phase 0 (classify_change 実装 + 全 SKILL.md 外部参照棚卸し) 完了を移行開始の最低条件**とする。Phase 0 未完了での案D' 移行は禁止（34章参照）。
- **2026-05-18 暫定**: 本リポジトリの**暫定最終形は案D'**（公式 `.claude-plugin/` marketplace 型）。**公式 `.claude-plugin/` 仕様確定をゲート条件**とし、仕様確定前の不可逆判断は禁止（PF-F03 Real Options 適用）。物理レイアウト・symlink 戦略・settings.json マージ方針の詳細は **34章 § plugin 物理レイアウトと symlink 戦略** を正本とする。実物理移行は Phase 0 ゲート完了後の **P0_breaking 変更**として実施する。
- 昇格判断・rubric 多重継承の詳細は 27 / 29 章を参照。

## 解決: 2 Skill MVP から 3点セットへ昇格

初期構築の標準形は **2 Skill + rubric 補助ファイル** とする。これは高品質な Skill を継続生成するための推奨 MVP であり、すべての軽量ケースに forked evaluator を必須化する意味ではない。

| 構成 | 内容 | 採用条件 |
|---|---|---|
| MVP | `run-build-skill` + `assign-skill-design-evaluator` + `assign.../references/rubric.json` | 最初の2スキル構築。依存を最小化する |
| 昇格版 | MVP + `ref-skill-design-rubric` | 複数 evaluator が同じ rubric を共有する、または rubric を独立管理したい |
| 簡易版 | `run-build-skill` + CI/lint | forked evaluator が不要な軽量運用 |

Skill を構築する Skill (= メタSkill) は、標準運用では Generator（生成役）/Evaluator（評価役） を分離する。軽量例外として `run-build-skill + CI/lint` を使う場合は、対象が低リスクで、P0 lint と人間レビューで十分なことを明示する。rubric（評価基準）は最初は evaluator の補助ファイルとして置く。`ref-skill-design-rubric` は将来の共有正本であり、MVP の必須 Skill ではない。

| Skill 名 | 種別 | 役割 |
|---|---|---|
| `run-build-skill` | run (workflow) | ユーザー要求 → `SKILL.md` + 補助ファイルを生成 |
| `assign-skill-design-evaluator` | assign (forked evaluator) | 生成された Skill の設計書品質を rubric で採点 |
| `ref-skill-design-rubric` | ref (dictionary) | 昇格版のみ。評価基準・公式仕様準拠チェックリスト・命名規則の共有正本 |

### rubric 正本の昇格条件

rubric の正本は段階で変わる。

| 段階 | rubric 正本 | 採用条件 |
|---|---|---|
| MVP | `assign-skill-design-evaluator/references/rubric.json` | evaluator が 1 つだけ |
| 昇格版 | `ref-skill-design-rubric` | 複数 evaluator が同じ rubric を参照する、または rubric を独立 versioning したい |
| 軽量例外 | CI/lint の設定 + 人間レビュー記録 | forked evaluator 不要な低リスク Skill |

昇格時は `README`、`13`、`24`、`25` の参照先を同時に更新し、旧 rubric には deprecation を記録する。正本が二重化した状態で運用しない。複数プロジェクトで rubric を継承・合成する場合の多重継承パターンは [29-multi-project-rubric-composition.md](./29-multi-project-rubric-composition.md) を参照。

## creator-kit への配布形態

`creator-kit/` は、本章で定義するメタSkill群を別repoで再利用するための配布単位である。新しいアーキテクチャ案ではなく、案A/案Bの実装物を portable kit として束ねたものとして扱う。

`creator-kit/manifest.json` を kit 構成の正本とし、含めるものは「複数プロジェクトで同じものを使う」メタSkill、rubric/reference、lint/hook scripts、出力routing/adapter、設定雛形に限定する。業務workflow skill、プロジェクト固有設計書、分析ログ、具体的な routing 設定値は kit 外に置く。

現行 kit は `run-skill-create` を E2E オーケストレーターとして持ち、`run-skill-elicit` → `run-build-skill` → creator-kit登録判定 → P0 lint → `assign-skill-design-evaluator` → `run-elegant-review` → governance の順にゲート付きで連鎖する。独立した出力先や秘密管理は 31 章の `ref-output-routing` と adapter scripts に委譲し、Bash/Python 規約は 28 章に委譲する。

### creator-kit登録判定

自然言語で「Harness Creator を改善して」「この補助Skillも横展開して」と依頼された場合、Claude Code は次の順で扱う。

1. 追加物が複数プロジェクトで再利用される共通基盤か判定する。
2. 共通基盤なら `creator-kit/skills/`、`creator-kit/scripts/`、`creator-kit/config/` のいずれかへ配置する。
3. `scripts/build-manifest-registration-plan.py` で `manifest.json` 登録案を生成する。
4. 登録案をユーザーに提示し、承認後だけ `--apply` で `manifest.json` を更新する。
5. `lint-manifest-contents.py`、`lint-forbidden-deps.py`、`audit_secret_leak.py` を通す。

プロジェクト固有Skillは `creator-kit` に入れない。プロジェクト固有Skillから共通化できる基準・hook・lint・adapter が見つかった場合は、`ref-*`、`assign-*`、`scripts/lint-*` などへ抽出してから登録候補にする。

3 点セットの依存関係:

```text
            ┌──────────────────────────────────┐
            │     User request (要件)           │
            └────────────────┬─────────────────┘
                             │
                             ▼
              ┌──────────────────────────┐
              │     run-build-skill      │  (generator / workflow)
              │  - 設計書 01-21 を必要分参照│
              │  - templates/ から雛形展開 │
              │  - scripts/ で frontmatter整形│
              └──────┬──────────────────┘
                     │ artifact: SKILL.md + assets
                     ▼
        ┌────────────────────────────────────┐
        │  assign-skill-design-evaluator      │  (forked, context: fork)
        │  - Read references/rubric.json      │
        │  - or ref-skill-design-rubric       │
        │  - score / findings / required_fixes│
        └──────┬──────────────────────────────┘
               │ JSON {score, passed, ...}
               ▼
        ┌──────────────────┐  fail  ┌─────────────────┐
        │ score >= threshold├──────►│ retry generator │
        └────────┬─────────┘        └─────────────────┘
                 │ pass
                 ▼
            installed Skill
                 │
                 ▼
        ┌──────────────────────────┐
        │  ref-skill-design-rubric │ (read-only, Goodhart（評価基準を都合よく歪める罠）対策)
        └──────────────────────────┘
```

## 最小 Skill 数で拡張する依存設計

Skill を増やしすぎないため、役割を「実行エンジン」と「基準リソース」に分ける。

| 役割 | 推奨数 | 例 | 増やす条件 |
|---|---:|---|---|
| workflow engine | 少数 | `run-build-skill`, `run-execute-task` | 手順や副作用の種類が根本的に違う |
| evaluator engine | 少数 | `assign-generic-artifact-evaluator`, `assign-skill-design-evaluator` | 評価対象の artifact 種別が違う |
| reference / rubric | domain ごと | `ref-skill-design-rubric`, `ref-security-rules`, `ref-marketing-quality-rubric` | 基準・用語・禁止事項が違う |
| deterministic script | check ごと | `lint-skill-name.py`, `validate-frontmatter.ps1` | 機械判定できる規則が増えた |

原則: **Skill は orchestration、基準は references、判定可能な検査は scripts** に置く。新しい案件やプロジェクトが増えた時は、まず `ref-*` / `references/` / config を追加し、`run-*` や `assign-*` を増やすのは最後にする。

> scripts の実行モデル（trigger、I/O 契約、失敗時挙動、クロスプラットフォーム互換）の詳細は [28-script-execution-model.md](./28-script-execution-model.md) を参照。
>
> `ref-*` を複数プロジェクトで継承・合成するパターン（共通 rubric + project 上書き + task 固有差分）の詳細は [29-multi-project-rubric-composition.md](./29-multi-project-rubric-composition.md) を参照。

依存方向:

```text
run-build-skill
  -> assign-skill-design-evaluator
  -> ref-skill-design-rubric
  -> scripts/lint-skill-*.*

run-execute-task
  -> assign-generic-artifact-evaluator
  -> ref-<project>-rules / references/<task>-criteria.yaml
  -> scripts/validate-*.*
```

この一方向依存により、会社内で複数プロジェクトが走っても、共通 evaluator を使い回しながら project / 案件 / task ごとの基準だけを差し替えられる。

### 追加判断ルール

| 追加したいもの | 置き場所 |
|---|---|
| 会社全体の命名・セキュリティ・品質基準 | `ref-company-*-rules` |
| プロジェクト固有のAPI契約・用語・禁止事項 | `references/project-*.json` または `ref-<project>-rules` |
| タスク固有の done 条件 | artifact 近くの `criteria.json` |
| 正規表現や schema で判定できる規則 | `scripts/lint-*` / `scripts/validate-*` |
| 評価結果の要約・優先順位付け | `assign-*-evaluator` |
| 実際にファイルや外部状態を変える手順 | `run-*` |

循環を避けるため、`ref-*` から `run-*` / `assign-*` を呼ばない。rubric（評価基準）は evaluator の入力であり、evaluator が rubric を生成・改変しない。

## 自己進化ループ

メタSkill自身も Skill であるため、同じ評価器で採点できる。

```text
run-build-skill ──生成──► <新Skill>
                            │
                            ▼
                  assign-skill-design-evaluator
                            │
                rubric違反検出 │
                            ▼
                  rubric.json / ref-skill-design-rubric 更新候補
                            │
                            ▼
                  run-build-skill 自身を再生成 (dogfood)
```

新Skill 生成で繰り返し検出される rubric 違反は、`run-build-skill` のテンプレ欠陥を示すシグナル。fix は templates/ または rubric の追補で行い、過去 Skill に再適用する。

## ドッグフーディング原則

設計書 01-21 と本 23-26 自体を「artifact」とみなし、`assign-skill-design-evaluator` の forked 実行で採点する。

- 設計書が rubric を満たさなければ、メタSkill が生成する Skill も満たさない (推移律)
- rubric を Read-only にすることで、書き手が rubric を緩める Goodhart（評価基準を都合よく歪める罠）を防ぐ (09 参照)
- 評価ログは `xl-skills/eval-log/` に蓄積し、過去 score との回帰を検知

## rubric governance（改正の手続き）

> 本節は概要のみを示す。**詳細手順・テンプレ・チェックリストは [27-rubric-governance-runbook.md](./27-rubric-governance-runbook.md) を参照。**

rubric（評価基準）は read-only でも「永久不変」ではない。Goodhart（評価基準を都合よく歪める罠） 対策（書き手が rubric を緩める）と、現実の知見蓄積（命名規約 第15条の改正手続きと同期）を両立するためのガバナンスを定義する。

### 改正トリガー

| トリガー | 条件 | 起点 |
|---|---|---|
| **違反率閾値** | 同一 rubric 項目で違反率が連続 3 release で 20% を超える | テンプレ欠陥のシグナル → templates/ 修正で対応 |
| **新公式仕様** | Claude Code 公式 docs / SDK の変更が検出された | 16/17 と差分照合 → rubric 追補 |
| **命名規約改正** | 06 の第1〜16条のうち rubric 連動項目が改正された | 第15条手続きと同期 |
| **人手提案** | PR で改正案 + 影響評価が提示された | 影響を受ける Skill 数を lint で計測 |

### 改正の段階

1. **提案 (Proposal)**: PR で rubric の `diff` と「影響を受ける既存 Skill のリスト」を提示。
2. **影響評価 (Impact Assessment)**: 全 Skill に対し**新 rubric** で採点をシミュレーションし、score 低下 Skill 数を記録。
3. **猶予期間 (Grace Period)**: 影響 Skill 数が 0 でない場合、`rubric_version` を bump し、最低 1 release（または 30 日）の deprecation 期間を設ける。
4. **発効 (Enactment)**: 猶予期間後、新 rubric が evaluator のデフォルトになる。

### ガバナンス・ボード

人手判断が必要な改正（人間判定）は以下の3役で行う:

| 役 | 責務 |
|---|---|
| **提案者** | rubric 改正の動機・影響評価を作成 |
| **第三者レビュアー** | 影響評価の妥当性と Goodhart（評価基準を都合よく歪める罠） リスクを評価 |
| **承認者** | merge 権限を持ち、deprecation 期間を確定する |

小規模運用では1人が複数役を兼ねてよいが、提案者と承認者の兼任は禁止する（自己承認の Goodhart（評価基準を都合よく歪める罠） 防止）。

## 自己進化ループの終了条件

23 章前半のループ図には終了条件がなかった。以下を明示する。

### 安定版凍結ルール

連続する `N` 回の `run-build-skill` 実行で rubric 違反率が `M%` 以下に収束した場合、その時点のテンプレ + rubric を**安定版（stable）として凍結**する。デフォルト推奨値:

| 指標 | デフォルト | 説明 |
|---|---|---|
| `N` | 10 | 連続実行回数 |
| `M%` | 5% | 違反率の上限 |
| 凍結対象 | `templates/` + `references/rubric.json` | 同時凍結（個別凍結禁止） |

凍結後は **次の改正トリガー**（前節）まで自動更新を停止する。これにより自己参照ループの無限後退を防ぐ。

### 退避ルール

凍結後に新たに違反率が `M%` を上回った場合は、直近 stable に**自動 rollback** する。lint script が違反率を継続計測し、threshold 超過を hook で検知する。

### 観測ログ

| ファイル | 内容 | 更新タイミング |
|---|---|---|
| `xl-skills/eval-log/<date>-score.jsonl` | 各 Skill の score 履歴 | evaluator 実行ごと |
| `xl-skills/eval-log/violation-rate.csv` | rubric 項目別 違反率の時系列 | release ごと |
| `xl-skills/eval-log/rubric-versions.md` | rubric 改正履歴 | 改正発効時 |

## 命名規約との連動

06 章で定義した命名規約条文（第1〜16条）と本 23 章のメタSkillは以下のように連動する。`run-build-skill` が新 Skill を生成する際、第1〜16条すべてに従う必要がある。

| 条 | run-build-skill での扱い |
|---|---|
| 第1〜5条（命名形式） | テンプレ展開時に prefix / domain / role-suffix を入力として要求 |
| 第6条（改名） | 改名ユースケースは別 Skill（`run-skill-rename`）として分離（未実装） |
| 第7条（重複禁止） | 既存 Skill 一覧を Read し、命名衝突を生成前に検出 |
| 第8〜13条（配下構造） | テンプレ展開時に標準ディレクトリ構成を生成 |
| 第14条（_drafts/） | `--draft` フラグで `_drafts/` 配下に生成可能 |
| 第15条（改正手続き） | rubric governance と同期（前節） |
| 第16条（例外宣言） | テンプレに `name-policy-exception` 欄を持たせる |

`run-skill-rename` は未実装である。したがって改名は当面、手動 runbook + CHANGELOG + alias/deprecation の人間レビューで扱う。命名を契約として扱う以上、改名自動化が入るまでは第6条を P2 governance として管理する。

## 他設計書との関係マップ

| 層 | 参照先 | `run-build-skill` での用途 |
|---|---|
| 入口 | 00 / 00a / 01a | 全体像、最小作成、作成フロー |
| 公式正本 | 16 / 17 | Claude Code 仕様、Subagent / Agent Teams / hooks の事実 |
| 設計判断 | 01 / 03 / 04 / 05 / 06 / 07 / 08 / 09 / 10 / 13 / 14 | 4条件、frontmatter 運用、命名、評価、権限、動的注入 |
| テンプレ | 11 / 18 / 24 | 汎用雛形、完成例、メタSkill正本テンプレ |
| 運用 | 19 / 20 / 22 / 25 / 26 | troubleshooting、移行、クロスプラットフォーム、Runbook、dogfooding |
| メタ詳細 | 27 / 28 / 29 / 30 / 34 | rubric governance 手順、script 実行モデル、rubric 多重継承、パラダイム対応、plugin ロードマップ |
| 追跡 | 12 / 15 / 21 | 画像、公式取得日、元情報差分 |

24 はテンプレ本体、25 は実行 runbook、26 はドッグフーディング手順を担う。27 は本章 governance 節の詳細手順、28 は scripts の実行モデル、29 は rubric の多重継承パターン、30 はアーキテクチャ案A〜Eの位置付けマップを担う。34 は plugin 移行ロードマップ（Phase 0-4）・公式制約照合表・3アナリスト収束的証拠のサマリを担う。

---

## メタスキルと既存スキルの責務マトリクス（B1/C2 パッチ）

既存スキルとの責務重複を防ぐため、各スキルの責務境界を以下のマトリクスで管理する。

| スキル | 主責務 | 入力 | 出力 | 呼ぶもの | 呼ばれるもの |
|---|---|---|---|---|---|
| `run-build-skill` | Skill新規作成・更新ワークフロー | skill_name, kind, mode | SKILL.md + assets | assign-skill-design-evaluator, build-subagent.py | ユーザー, run-skill-elicit |
| `run-skill-elicit` | 要求ヒアリング・brief生成 | topic (任意) | skill-brief.md | (なし) | ユーザー, run-build-skill |
| `run-skill-rename` | スキル安全改名 | old_name, new_name | 改名済みディレクトリ + CHANGELOG | lint scripts | ユーザー |
| `assign-skill-design-evaluator` | スキル設計品質採点 | SKILL.md パス | JSON {score, findings, passed} | rubric.json | run-build-skill (fork) |
| `ref-skill-design-rubric` | 評価基準正本 (昇格版) | (Read-only) | rubric.json の内容 | (なし) | assign-skill-design-evaluator |
| `run-skill-rubric-governance` | rubric改正 Runbook | proposal.json + governance-params.json | rubric.json PR + governance log | lint-rubric-violation.py, diff-rubric-impact.py | ユーザー |
| `run-elegant-review` | 30パラダイム×4条件 レビュー | target path | findings.json + review-*.md | 3 analyst subagents, elegant-improvement-executor | ユーザー |
| `ref-yaml-spec-fetcher` | 公式YAML仕様キャッシュ参照 | (Read-only) | yaml-spec-cache.md の内容 | (なし) | run-build-skill, validate-frontmatter.py |
| `elegant-reset-observer` | 30パラダイム評価の思考リセット・俯瞰 | target path | 俯瞰レポート（全体像・第一印象） | (なし) | run-elegant-review |
| `elegant-logical-structural-analyst` | 論理分析系+構造分解系9思考法による検証 | target + reset レポート | 論理・構造検証結果 | (なし) | run-elegant-review |
| `elegant-meta-divergent-analyst` | メタ・抽象系+発想・拡張系9思考法による検証 | target + reset レポート | メタ・発想分析結果 + 代替案 | (なし) | run-elegant-review |
| `elegant-system-strategic-analyst` | システム系+戦略系+問題解決系12思考法による検証 | target + reset レポート | システム・戦略・問題解決分析結果 | (なし) | run-elegant-review |
| `elegant-improvement-executor` | 3アナリスト結果を統合し4条件PASSまで改善実行・検証 | 3アナリスト結果 | 改善後artifact + 4条件判定 | lint scripts, write-eval-log.py | run-elegant-review |

### 責務分割の原則

- `run-build-skill` は**新規作成・更新**のみ。改名は `run-skill-rename` に委譲する。
- `run-skill-elicit` は**ヒアリングのみ**。SKILL.md を書かない。
- `assign-*` は評価のみ。生成・改名・改正を行わない（Goodhart対策）。
- `ref-*` は Read-only。Write/Edit を実行しない。
- governance は `run-skill-rubric-governance` 経由のみ。直接 rubric.json を編集しない。

### 重複・兼任の禁止ルール

1. ヒアリング (`run-skill-elicit`) と生成 (`run-build-skill`) の同一コンテキスト実行は可（sequential）。
2. 生成 (`run-build-skill`) と評価 (`assign-skill-design-evaluator`) は必ず分離コンテキスト（context: fork）。
3. 改名 (`run-skill-rename`) と評価は独立。改名後に評価が必要な場合は別途 `assign-skill-design-evaluator` を呼ぶ。

## § X-1 prefix 別内部構造規約 (23a 参照)

各 Skill の内部構造は prefix が宣言する実行モードに応じて非対称に決まる。本章は meta-skill 群の責務分割と連携の正本であり、内部構造の正本は分離する。
詳細は [23a-prefix-driven-internal-structure.md](23a-prefix-driven-internal-structure.md) § 3 を参照。

## § X-2 manifest + schemas + prompts 三層 contract モデル (23a § 4 参照)

Step / Gate / handoff の正本は `workflow-manifest.json` + `schemas/` + `prompts/<R-id>.yaml` の三層に置く。SKILL.md は参照役に徹し、散文に同じ内容を写経しない。詳細は [23a-prefix-driven-internal-structure.md](23a-prefix-driven-internal-structure.md) § 4 を参照。

---

## Capability 抽象への拡張 (2026-05-22)

本章は当初「Skill を Skill で作るためのアーキテクチャ」として書かれたが、2026-05 の harness-creator プラグイン整備の過程で、Claude Code 拡張資産は Skill だけではなく **Agent / Hook / Command / Plugin-Composition / Prompt / Workflow** を含む 7 種に分岐していることが明らかになった。本節はその知見を取り込み、これら全種を **Capability** という統一抽象で扱う設計判断を明文化する。

### 動機 (なぜ Skill 中心の枠組みでは破綻するか)

| 観測された破綻 | 原因 |
|---|---|
| Agent / Hook / Command の品質基準が場当たり的 | rubric / templates が Skill 専用に設計され、他 kind では空欄か流用 |
| plugin 単位の改訂が `plugins/<name>/.claude-plugin/plugin.json` の手書きに依存 | bundle 全体の依存関係 (DAG) を機械検証する正本が無い |
| EVALS / lessons-learned / changelog が plugin 直下で揃わない | plugin = bundle という概念が定義されていない |
| reflective loop (35章) が Skill 改訂にしか走らない | 観測対象 (failure mode) が Skill 起動ログ前提 |

### 統一抽象の定義

| 抽象 | 役割 | 正本パス |
|---|---|---|
| **Capability** | Claude Code 拡張資産の最小単位。`kind ∈ {skill, agent, hook, command, plugin-composition, prompt, workflow}` のいずれかを宣言する | `plugins/harness-creator/skills/ref-skill-glossary/references/terms.md` |
| **CapabilityManifest** | 各 Capability の宣言ファイル。共通核 (`name / description / kind / version / owner / tags / since`) + kind 固有スキーマ (注入) の二層構造 | `plugins/harness-creator/skills/run-build-skill/references/capability-manifest.schema.json` |
| **CapabilityBundle** | 複数 Capability の集合 ≒ plugin。`plugin-composition.yaml` (別名 `capability-bundle.yaml`) で `capabilities[] / dependencies / eval-sinks / governance.rubric_refs / observability.hooks` を宣言 | plugin 直下 `plugin-composition.yaml` |
| **CapabilityContract** | 三層 contract: **intent**(なぜ存在するか) / **interface**(入出力・呼出規約) / **invariant**(変更してはならない不変条件)。23a章の三層 contract モデルを Capability 全 kind に拡張 | 各 Capability の `workflow-manifest.json` / `schemas/` / `prompts/<R-id>.md` |

### Skill との互換性

Skill は Capability の **特殊形 (`kind: skill`)** として扱う。既存の `run-* / ref-* / assign-* / delegate-* / wrap-*` prefix 規約 (23a § 2) は `kind: skill` 配下のサブ分類として継続有効である。本節の追加は破壊変更ではなく、**包含関係を上位に明示する** 拡張に留まる。

### 三層 contract の Capability 横断適用

23a § 4 で確立した三層 contract モデル (`workflow-manifest.json` + `schemas/` + `prompts/`) は、kind ごとに以下のように写像される。

| kind | intent (なぜ) | interface (入出力) | invariant (不変) |
|---|---|---|---|
| `skill` | description (発動条件) | frontmatter + Output Contract | rubric_refs / Gotchas |
| `agent` | agent の責務宣言 | system_prompt + tools 許可リスト | fork context 必須 / 親 context 不汚染 |
| `hook` | trigger event の意図 | event/matcher/command の三組 | 公式 hook event 名のみ / 副作用境界 |
| `command` | slash command の使途 | argument schema + 出力 | コマンド名の namespace 衝突禁止 |
| `plugin-composition` | bundle の存在理由 | `capabilities[]` / `dependencies` DAG / `eval-sinks` | DAG 循環禁止 / governance.rubric_refs 必須 |
| `prompt` | prompt 単体の責務 | input slots + expected output schema | 7層 markdown 骨格 / 1 ファイル = 1 責務 |
| `workflow` | フェーズ進行の意図 | phases + gates + handoff schemas | dependsOn 循環禁止 / fatal_exit_codes 必須 |

### 設計判断の根拠

1. **rubric / templates / validator が kind ごとに分岐する必然性**: kind 別に invariant が異なるため、単一 rubric では Goodhart 罠が再生産される。Capability 抽象で kind を一級市民に昇格させることで、kind 固有 rubric を `references/rubric-<kind>.json` として独立 versioning できる。
2. **CapabilityBundle = plugin の同一視**: Claude Code 公式 `.claude-plugin/` の単位と本リポジトリの `plugins/<name>/` の単位を一致させることで、案D' (公式 plugin 型) への移行コストを最小化する (34章 Phase 0 ゲート整合)。
3. **composition lint の機械検証性**: `plugin-composition.yaml` を PostToolUse hook で lint することで、依存 DAG・rubric_refs・hooks 配線の整合を**変更時点で検出**する。23a § 5 の「再現性保証メカニズム」を bundle 単位に拡張したもの。

### 移行ステータス

| Phase | 内容 | 状態 |
|---|---|---|
| Phase A | 用語確定 (`ref-skill-glossary/references/terms.md` に追加) | 完了 (2026-05-22) |
| Phase B | CapabilityManifest schema 整備 (`run-build-skill/references/capability-manifest.schema.json`) | 完了 (2026-05-22) |
| Phase C | `plugin-composition.yaml` の各 plugin 配置 + composition lint hook | 進行中 |
| Phase D | rubric / templates の kind 別分岐 | 未着手 |
| Phase E | reflective loop (35章) の Capability 横断化 | 未着手 |

Phase D/E は 33章 P1_structural として個別に proposal する。

### 関連章

- 23a章: 三層 contract の Skill 内部実装 (本節はそれを kind 横断に汎化)
- 33章: CapabilityBundle governance のカテゴリ判定 (§ CapabilityBundle governance)
- 34a章: hook の Capability 化 (kind=hook の CapabilityManifest 宣言)
- 35章: reflective loop の Capability 用語による再記述

