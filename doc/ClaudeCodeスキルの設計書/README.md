# Claude Code スキル設計書

作成日: 2026-05-17
最終更新: 2026-05-18 (creator-kit / 出力routing / Keychain / Bash-Python規約 / 実装台帳を反映)
目的: `Agent Skill大全` の本文・画像から抽出した設計思想と、2026-05-17 時点の Claude Code Skills 公式仕様、および Mac/Windows 両対応のメタSkill構築知見を統合し、責務別 Markdown 群として整理する。

## この設計書群を読むと何ができるようになるか（価値提案）

- **15分で動く最小 Skill を作れる** (00a → 11 → 18)
- **辞書型/ワークフロー型を正しく選び分け、命名規約と段階的開示で破綻しない Skill 群を設計できる** (01 → 06 → 07)
- **Skill / Subagent / Hook / MCP / CLI / API の責務を分離して、評価ループ付きのオーケストレーションを組める** (05 → 09 → 10 → 17)
- **Mac/Windows 両対応の CLI 要件を満たし、他のスキルを自動生成・更新するメタSkill を構築できる** (22 → 23 → 24 → 25 → 26)
- **メタSkill群を creator-kit として別repoへ再利用し、install/migrate/lint を機械強制できる** (23 → 25 → 28 → 31)
- **Notion / Sheets / Slack / HTTP / Local への出力routingを、APIキーをLLMに渡さず運用できる** (31)
- **公式仕様の正本 (16/17) と元記事 (21) に常に追跡可能な状態で設計判断を残せる**

> 公式仕様の正本は **16-official-skills-complete-reference.md** と **17-agent-teams-reference.md**。
> Subagent / hooks の詳細運用は **17** を参照（10 は接続観点、17 は仕様観点）。
> Mac/Win 両対応 CLI 要件は **22-cross-platform-runtime.md**。
> メタSkill（Skillを作るSkill）構築は **23〜26** の4本セット。

## 正本・優先順位

情報が競合した場合は、領域ごとに次を正本として扱う。

| 領域 | 正本 | 裁定ルール |
|---|---|---|
| Claude Code の動作仕様 | `16` / `17` と公式 docs | 公式 docs の事実を優先し、設計判断は各設計書へ分離する |
| Skill 設計思想・命名・評価概念 | 元記事本文・画像、`01` / `06` / `09` | 公式仕様ではなく本設計書の提唱体系として扱う |
| 画像由来の主張 | `12-image-extraction-map.md` | 画像解釈は `12` の行番号で追跡する |
| 実装テンプレート | `24-meta-skill-templates.md` | `11` は汎用例、`24` はメタSkill正本 |
| creator-kit 配布構成 | `creator-kit/manifest.json` と `23` / `25` | kit に含める Skill / script / config は manifest を優先する |
| Bash / Python 実装規約 | `28-script-execution-model.md` と `creator-kit/CONVENTIONS.md` | Bash は lifecycle、Python は stdlib logic。禁止依存は `manifest.json` を優先する |
| 出力routing / adapter / secret | `31-output-routing-adapter-architecture.md` | Sink Contract、Keychain、adapter例外は `31` を優先する |
| creator-kit 実装状態・残課題 | `32-creator-kit-implementation-ledger.md` | Phase A-J の履歴、レビュー結果、未移行項目、C1-C4 判定は `32` に集約する |
| 変更ガバナンス | `33-change-governance.md` と `creator-kit/config/governance-policy.json` | P0-P3カテゴリ、cooldown、blast radius、承認フローは `33` を優先する |
| plugin 移行ロードマップ | `34-plugin-governance-roadmap.md` | Phase 0-4 ゲート、公式制約照合、3アナリスト収束証拠は `34` を優先する |
| settings.json マージ仕様 | `34a-settings-merge-spec.md` | `.claude/settings.json` の管理メタデータ、INV-1〜12、衝突検出、名前空間 preflight は `34a` を優先する |
| Meta-Harness FBループ | `35-meta-harness-feedback-loop.md` + `.claude/config/meta-harness-observables.json` | log-driven ref-* 改善のパイプライン、observables 列挙、Goodhart 予防は `35` を優先する |
| Plugin Package Harness | `36-plugin-package-harness-contract.md` | Harness Creator が量産する plugin package の同梱判定、install UX、package completeness check は `36` を優先する |
| 元情報の存在・数・差分 | `21-source-traceability.md` | 画像数、実在パス、コード現物の有無は `21` を優先する |

「コード共有有」の元記事は記事本文と画像を現物確認済み。ただし、記事中で言及される同梱 `skills.zip` / Notion 内の Skill 実コードは、このリポジトリ内に現物がないため **code-unavailable** として扱う。実コードと記事説明が競合する場合は、実コード取得後に `21` へ追記してから裁定する。

## 英語ラベル早見表

設計書では Skill 名、frontmatter field、公式用語は英語のまま残す。ただし、設計概念として頻出する英語ラベルは次の意味で読む。

| 英語ラベル | 日本語での意味 | 何を見るための言葉か |
|---|---|---|
| Purpose（目的） | 呼ぶと何が返るか | 知識を返すのか、成果物を作るのか、評価するのか |
| Trigger（発動条件） | 誰が・いつ呼ぶか | ユーザー直呼びか、内部呼び出しか |
| Shape（成果物の形） | 内部構造の形 | 単体で完結するか、fork / loop / 複数Skill連携か |
| Role（役割） | 評価ループ内の役割 | generator（生成役）か evaluator（評価役）か |
| Effect（副作用） | 外部状態への影響 | ファイル作成、API更新、デプロイなどがあるか |
| Generator（生成役） | 成果物を作る側 | report / code / SKILL.md を生成する |
| Evaluator（評価役） | 成果物を採点する側 | rubric に従って score / findings を返す |
| Rubric（評価基準） | 合格条件・採点表 | 何を満たせば良いかを定義する |
| Reference（参照資料） | 根拠資料・辞書 | API契約、用語集、業務ルールを読む |
| Artifact（成果物） | 評価対象の出力物 | SKILL.md、レポート、コード差分など |
| Workflow（実行手順） | 作業の流れ | 手順・分岐・再試行を持つ処理 |
| Context（文脈） | Claude が見ている情報範囲 | 親会話、forked subagent、補助ファイルなど |
| Contract（契約） | 入出力と完了条件 | 何を入力し、何を出し、何で完了とするか |
| Boundary（責務境界） | やること・やらないことの線引き | Skill を肥大化させないための境界 |
| Progressive Disclosure（段階的開示） | 必要時だけ読む設計 | 全部を最初に読ませず、必要な資料だけ読む |
| Goodhart（評価基準を都合よく歪める罠） | 点数を上げるために基準を悪用する問題 | evaluator が rubric を編集しない理由 |
| Clean Architecture（依存方向を守る設計） | 内側の基準に外側が依存する構造 | `run/assign -> ref/references -> scripts` の一方向依存 |
| DDD（ドメイン駆動設計） | 業務領域の言葉と境界を大事にする設計 | domain 名、用語集、Bounded Context（境界づけられた文脈）を決める |
| Bounded Context（境界づけられた文脈） | 用語やルールが通用する範囲 | プロジェクト・業務領域ごとの境界 |
| Ubiquitous Language（共通言語） | チームで揃える業務用語 | Skill 名や domain segment の基準 |
| Gotchas（落とし穴） | よく踏む失敗と回避策 | LLM が間違えやすい点を短く書く |

## ファイル構成（全40本）

Markdown は README を含めて 41 本。README を除く設計書は 40 本で、`00a` / `01a` / `34a` は補助導線として採番している。`27〜30` は依存注入型クリーンアーキ実装の追加章、`31` は出力routing/adapterとKeychain保護の追加章、`32` は creator-kit 実装状態の台帳章、`33` は変更ガバナンス章、`34` は plugin 移行ロードマップ章、`34a` は settings.json マージ仕様章、`36` は plugin package harness 契約章。

行数規律の適用範囲: `08` / `13` / `24` の **300 行 hard cap は生成対象の `.claude/skills/<skill-name>/SKILL.md` 本文に適用する**。本ディレクトリの設計書 Markdown は正本性・追跡性・判断根拠を優先し、300 行以上でも許容する。

| ファイル | 責務 |
|---|---|
| [00-overview.md](00-overview.md) | 全体像、対象範囲、読み順（入口） |
| [00a-quickstart-beginner.md](00a-quickstart-beginner.md) | 15分で最小 Skill を作る初回導線（入口の補助） |
| [01-design-philosophy.md](01-design-philosophy.md) | Skill を設計可能な部品として扱う思想 |
| [01a-build-flow.md](01a-build-flow.md) | 問題定義から検証までの作成フロー |
| [02-claude-code-skill-spec.md](02-claude-code-skill-spec.md) | Claude Code Skills の公式仕様、配置、ライフサイクル |
| [03-yaml-frontmatter-reference.md](03-yaml-frontmatter-reference.md) | `SKILL.md` YAML/frontmatter の全項目と設計判断 |
| [04-invocation-permissions-settings.md](04-invocation-permissions-settings.md) | 呼び出し制御、permissions、settings、`skillOverrides` |
| [05-layering-skill-subagent-hook-mcp-cli.md](05-layering-skill-subagent-hook-mcp-cli.md) | Skill / Subagent / Hook / MCP / CLI / API の責務分離 |
| [06-classification-and-naming.md](06-classification-and-naming.md) | 辞書型/ワークフロー型、4 軸分類、5 prefix 命名、3層命名規約 |
| [07-progressive-disclosure.md](07-progressive-disclosure.md) | 段階的開示、補助ファイル、compaction 対策 |
| [08-skill-writing-guidelines.md](08-skill-writing-guidelines.md) | Less is More、Why（理由）-driven、Gotchas（落とし穴） |
| [09-evaluation-orchestration.md](09-evaluation-orchestration.md) | Generator（生成役） / Evaluator（評価役） 分離、評価ループ、JSON 出力 |
| [10-subagents-hooks-integration.md](10-subagents-hooks-integration.md) | Subagent frontmatter、preload skills、hooks 連携 |
| [11-templates.md](11-templates.md) | 実装用テンプレート集 |
| [12-image-extraction-map.md](12-image-extraction-map.md) | 画像ごとの抽出情報対応表 |
| [13-checklists.md](13-checklists.md) | 設計・実装・レビューのチェックリスト |
| [14-dynamic-context-injection.md](14-dynamic-context-injection.md) | `!` 動的コンテキスト注入と外部 LLM 出力の扱い |
| [15-official-source-notes.md](15-official-source-notes.md) | 公式ドキュメント参照元と取得時点メモ |
| [16-official-skills-complete-reference.md](16-official-skills-complete-reference.md) | **公式仕様の正本**: Claude Code Skills 網羅リファレンス |
| [17-agent-teams-reference.md](17-agent-teams-reference.md) | **公式仕様の正本**: Agent Teams / Subagent / hooks 詳細 |
| [18-complete-examples.md](18-complete-examples.md) | 完成ディレクトリ例 |
| [19-troubleshooting.md](19-troubleshooting.md) | 発動しない・誤発動・権限・評価のトラブル対応 |
| [20-migration-path.md](20-migration-path.md) | プロンプト集 / CLAUDE.md から Skill 群への移行手順 |
| [21-source-traceability.md](21-source-traceability.md) | 元記事・画像・公式仕様との追跡表 |
| [22-cross-platform-runtime.md](22-cross-platform-runtime.md) | **Mac/Windows 両対応**の CLI/シェル/パス要件と回避策 |
| [23-meta-skill-architecture.md](23-meta-skill-architecture.md) | メタSkill（Skillを作るSkill）のアーキテクチャ |
| [23a-prefix-driven-internal-structure.md](23a-prefix-driven-internal-structure.md) | prefix 駆動型内部構造規約と manifest 駆動 contract モデル (三層 contract モデルの正本) |
| [24-meta-skill-templates.md](24-meta-skill-templates.md) | メタSkill 用テンプレート集 |
| [25-meta-skill-runbook.md](25-meta-skill-runbook.md) | メタSkill 運用Runbook（生成→検証→配布） |
| [26-meta-skill-dogfooding.md](26-meta-skill-dogfooding.md) | メタSkill を自分自身に適用する dogfooding 手順 |
| [27-rubric-governance-runbook.md](27-rubric-governance-runbook.md) | rubric 改正の自動検出→招集→評価→猶予→発効 Runbook |
| [28-script-execution-model.md](28-script-execution-model.md) | scripts/ の実行責務マトリクス（誰がいつどの権限で実行） |
| [29-multi-project-rubric-composition.md](29-multi-project-rubric-composition.md) | `rubric_refs` による複数 rubric の多重継承・合成アルゴリズム |
| [30-paradigm-analogy-map.md](30-paradigm-analogy-map.md) | ESLint/pytest/LSP 等 既存パラダイムとの対応表（初学者向け） |
| [31-output-routing-adapter-architecture.md](31-output-routing-adapter-architecture.md) | 出力先routing/adapter基盤 (Hexagonal Arch) + Keychain中心のAPIキー管理 |
| [32-creator-kit-implementation-ledger.md](32-creator-kit-implementation-ledger.md) | creator-kit / E2E / routing / Keychain / 規約の実装履歴、レビュー結果、残課題台帳 |
| [33-change-governance.md](33-change-governance.md) | 変更ガバナンス (P0-P3カテゴリ、cooldown、blast radius、承認フロー)。27章の rubric governance を全Skill/script/configに横展開 |
| [34-plugin-governance-roadmap.md](34-plugin-governance-roadmap.md) | plugin 移行ガバナンスロードマップ (Phase 0-4、公式制約5点照合、3アナリスト収束証拠サマリ) |
| [34a-settings-merge-spec.md](34a-settings-merge-spec.md) | settings.json マージ仕様 (INV-1〜12、管理メタデータ構文、衝突検出、名前空間 preflight、CLIへの引き継ぎ) |
| [35-meta-harness-feedback-loop.md](35-meta-harness-feedback-loop.md) | Meta-Harness フィードバックループ (セッションログ→ref-* 改善のパイプライン Phase 0-4、observables 閉列挙、Goodhart 罠予防) |
| [36-plugin-package-harness-contract.md](36-plugin-package-harness-contract.md) | Plugin Package Harness 契約 (Harness Creator が量産する plugin package の同梱判定、install UX、package completeness check) |

## 命名規約・検証エンジン 横断索引

法律的命名規則（命名規約条文 第1〜16条）と、その違反検出・改正手続きは複数ファイルに分散している。以下は「どこに何があるか」のクイック索引。

| トピック | 主参照 | 連動先 | 役割 |
|---|---|---|---|
| **命名規約条文 第1〜7条**（Skill 名形式） | `06-classification-and-naming.md` | `13` (lint タグ) / `23` (連動) | prefix / domain / kebab / role-suffix |
| **命名規約条文 第8〜14条**（Skill 配下構造） | `06-classification-and-naming.md` | `13` (lint タグ) / `11`, `24` (テンプレ) | references / examples / scripts / templates ディレクトリ |
| **第15条 改正手続き** | `06-classification-and-naming.md` | `23` (rubric governance) | 提案→影響評価→猶予期間→発効 |
| **第16条 例外宣言** | `06-classification-and-naming.md` | `03` (frontmatter) | `name-policy-exception` 構文 |
| **5prefix × 4軸 対応マトリクス** | `06-classification-and-naming.md` | `08` (writing) | 一発で軸の整合性確認 |
| **Decision Table（主要ケース表）** | `06-classification-and-naming.md` | `08` (writing) | 主要 8 ケースを裁定 |
| **汎用性応用例**（DDD（ドメイン駆動設計）/Clean Architecture（依存方向を守る設計）/AIDA/JTBD等） | `06-classification-and-naming.md` | `01` (philosophy) | 他分野への適用 |
| **90 項目チェックリスト + lint/Hook/人タグ** | `13-checklists.md` | `06` (条文) / `23` (governance) | 各項目に実装主体タグ |
| **検証エンジン 優先順位 (P0/P1/P2)** | `13-checklists.md` | `23` (governance) / `10` (hooks) | 実装ロードマップ |
| **rubric governance（改正の手続き）** | `23-meta-skill-architecture.md` | `06` (第15条) / `09` (Goodhart（評価基準を都合よく歪める罠）) / `27` (詳細Runbook) | rubric の改正トリガー・段階・ボード |
| **rubric governance 自動化 Runbook** | `27-rubric-governance-runbook.md` | `23` (上位) / `09` (eval-log) | 違反率検出 script / ボード招集 / 猶予期間 / 版管理 |
| **scripts/ 実行モデル** | `28-script-execution-model.md` | `05` (層責務) / `22` (cross-platform) / `04` (Hook権限) | 5実行コンテキスト × script種別マトリクス |
| **rubric_refs 依存注入と多重継承** | `29-multi-project-rubric-composition.md` | `03` (frontmatter) / `09` (evaluator) / `23` (アーキ) | L0/L1/L2 3層、deep-merge / strict / override / layered |
| **既存パラダイム類推（学習導線）** | `30-paradigm-analogy-map.md` | 全章 | ESLint / pytest / LSP / Terraform / Hexagonal Arch との対応 |
| **creator-kit 配布・再利用境界** | `23-meta-skill-architecture.md` / `25-meta-skill-runbook.md` | `creator-kit/manifest.json` / `creator-kit/README.md` | 13 meta-skills、install/migrate、submodule/copy/symlink |
| **Bash/Python 2層規約** | `28-script-execution-model.md` | `22` / `creator-kit/CONVENTIONS.md` / `manifest.json` | Bash lifecycle、Python stdlib logic、forbidden deps lint |
| **出力routing / APIキー保護** | `31-output-routing-adapter-architecture.md` | `28` / `22` / `scripts/secrets` | Sink Contract v1.0、Keychain、adapter例外、JSON設定 |
| **creator-kit 実装台帳** | `32-creator-kit-implementation-ledger.md` | `23` / `25` / `28` / `31` / `creator-kit/manifest.json` | Phase A-J、レビュー2周、残課題、C1-C4現況 |
| **自己進化ループの終了条件** | `23-meta-skill-architecture.md` | `13` (P2 計測) | 安定版凍結ルール / 退避ルール |
| **命名規約との連動マトリクス** | `23-meta-skill-architecture.md` | `06` (全条) | `run-build-skill` 内での適用方法 |
| **汎用 evaluator + domain（ドメイン） rubric（評価基準）** | `09-evaluation-orchestration.md` | `05` (依存方向) / `23` (最小 Skill 数) | 評価 Skill を増やしすぎず基準を差し替える |
| **一方向依存ルール** | `05-layering-skill-subagent-hook-mcp-cli.md` | `09` / `23` | `run/assign -> ref/references -> scripts` |

## 4 条件達成のフローチャート

「矛盾なし／漏れなし／整合性／依存関係整合」をどこで担保するか:

| 条件 | 設計判定 | 機械判定 | 未実装時の扱い |
|---|---|---|---|
| **矛盾なし** | 正本優先順位、公式事実/提唱規則の分離 | 第1〜14条 lint + rubric シミュレーション | 第15〜16条は governance 判定として暫定PASS |
| **漏れなし** | 5prefix × 4軸 + 主要ケース表 + 読み順 | P0 lint と checklist gate | P0 未実装なら機械検証PASSとは呼ばない |
| **整合性** | 横断索引 + config/manifest 正本 | frontmatter / path / naming / forbidden-deps lint | 人間レビューで補完 |
| **依存関係整合** | 23 の連動マトリクス + rubric 昇格条件 | Hook / CI / eval-log | governance 記録を残して暫定PASS |

## 読み順 3 トラック

### A. 初心者向け（はじめて 1 本作る）

1. [00-overview.md](00-overview.md) — 何ができるかの全体像
2. [00a-quickstart-beginner.md](00a-quickstart-beginner.md) — 15分で動かす
3. [01a-build-flow.md](01a-build-flow.md) — 作成フローを掴む
4. [03-yaml-frontmatter-reference.md](03-yaml-frontmatter-reference.md) — YAML の設計判断
5. [11-templates.md](11-templates.md) — テンプレートから始める
6. [18-complete-examples.md](18-complete-examples.md) — 完成例で答え合わせ
7. [13-checklists.md](13-checklists.md) — 出荷前チェック

### B. 設計者向け（責務分離で複数本を設計する）

1. [00-overview.md](00-overview.md)
2. [01-design-philosophy.md](01-design-philosophy.md)
3. [05-layering-skill-subagent-hook-mcp-cli.md](05-layering-skill-subagent-hook-mcp-cli.md)
4. [06-classification-and-naming.md](06-classification-and-naming.md)
5. [07-progressive-disclosure.md](07-progressive-disclosure.md)
6. [09-evaluation-orchestration.md](09-evaluation-orchestration.md)
7. [10-subagents-hooks-integration.md](10-subagents-hooks-integration.md)
8. [16-official-skills-complete-reference.md](16-official-skills-complete-reference.md) — 公式仕様の正本
9. [17-agent-teams-reference.md](17-agent-teams-reference.md) — Subagent/hooks 詳細
10. 必要に応じて 04 / 08 / 14 / 19 / 20 を参照

### C. メタSkill 構築向け（Skill を作る Skill を組む）

1. [22-cross-platform-runtime.md](22-cross-platform-runtime.md) — Mac/Win 両対応の前提
2. [23-meta-skill-architecture.md](23-meta-skill-architecture.md) — アーキテクチャ（代替案A〜E比較含む）
3. [24-meta-skill-templates.md](24-meta-skill-templates.md) — テンプレート
4. [25-meta-skill-runbook.md](25-meta-skill-runbook.md) — 運用Runbook
5. [26-meta-skill-dogfooding.md](26-meta-skill-dogfooding.md) — 自己適用で品質担保
6. [29-multi-project-rubric-composition.md](29-multi-project-rubric-composition.md) — rubric_refs 多重継承で複数案件対応
7. [28-script-execution-model.md](28-script-execution-model.md) — scripts/ 実行責務マトリクス
8. [27-rubric-governance-runbook.md](27-rubric-governance-runbook.md) — 改正ガバナンスの自動化
9. [31-output-routing-adapter-architecture.md](31-output-routing-adapter-architecture.md) — 出力先routing、Sink Contract、Keychain保護
10. [32-creator-kit-implementation-ledger.md](32-creator-kit-implementation-ledger.md) — 実装状態と残課題を確認
11. 横断参照: [09](09-evaluation-orchestration.md) 評価ループ + 評価ピラミッド / [11](11-templates.md) 基本テンプレ / [13](13-checklists.md) チェックリスト
12. plugin 移行を検討する場合: [34-plugin-governance-roadmap.md](34-plugin-governance-roadmap.md) — Phase 0-4 ゲート確認
13. plugin package として量産する場合: [36-plugin-package-harness-contract.md](36-plugin-package-harness-contract.md) — Skill / Agent / Hook / Script / settings の同梱判定

### D. 既存パラダイム経験者向け（ESLint / pytest / LSP / Terraform から入る）

[30-paradigm-analogy-map.md](30-paradigm-analogy-map.md) を最初に読む。そこから自分の経験に合わせた読み順（例: ESLint 開発者なら `03 → 09 → 29 → 24`）が提示される。

最小実装は **2 Skill + rubric 補助ファイル** で開始する。`run-build-skill` と `assign-skill-design-evaluator` を作り、rubric（評価基準）は evaluator 配下の `references/rubric.json` に置く。複数 evaluator から共有する段階で `ref-skill-design-rubric` を独立 Skill に昇格する。

## 情報源

- 正本ディレクトリ: `xl-skills/doc/【コード共有有】Agent Skill大全 数百本のSkillをり続けた実践知から導いたオーケストレーション設計の概念体系Byまさおさん/`
- 元記事 Markdown: `xl-skills/doc/【コード共有有】Agent Skill大全 数百本のSkillをり続けた実践知から導いたオーケストレーション設計の概念体系Byまさおさん/【コード共有有】Agent Skill大全 数百本のSkillをり続けた実践知から導いたオーケストレーション設計の概念体系Byまさおさん.md`
- 注記: 正規タイトルは `Skillを作り続けた`。ユーザー指定文には `Skillり続けた`、実在ディレクトリには `Skillをり続けた` という表記揺れがある。ファイル参照では実在パスを使う。
- 元記事内画像 55 点
- Claude Code Docs: https://code.claude.com/docs/en/skills
- Claude Code Docs: https://code.claude.com/docs/en/sub-agents
- Claude Code Docs: https://code.claude.com/docs/en/hooks
- Claude Code Docs: https://code.claude.com/docs/en/settings
- Claude Code Docs: https://code.claude.com/docs/en/permissions
- Claude Code Docs: https://code.claude.com/docs/en/agent-teams
