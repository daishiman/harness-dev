# 25. メタSkill Runbook

`run-build-skill` を使ってユーザー要求から動作する Skill を 1 本仕上げるまでの実行手順。MVP は `run-build-skill` と `assign-skill-design-evaluator` の 2 Skill で開始し、rubric（評価基準）は evaluator 配下の `references/rubric.json` として扱う。

## creator-kit を使うE2E運用

別プロジェクトでメタSkill基盤を使う場合は、個別Skillを手でコピーせず `creator-kit/` を配布単位にする。配布形態は git submodule、単純コピー、同一マシン内 symlink の3つで、詳細手順は `creator-kit/README.md` に委譲する。

### 配布レイヤーの時系列分離（manifest 二義性の解消）

本 runbook で `manifest` が指す対象は時系列で2層あり、混同しないこと。詳細は [36-plugin-package-harness-contract.md](./36-plugin-package-harness-contract.md) §`package_mode` を正本とする。

| フェーズ | 配布単位 | `manifest` が指す実体 | `name:` 表記 |
|---|---|---|---|
| 現行（creator-kit 配布 = `skill-only` 相当の移行期表現） | `creator-kit/` | `creator-kit/manifest.json`（kit 内の Skill 収録目録） | kebab-case の Skill 名（plugin 名は不在） |
| Phase 2 以降（36章 `package_mode != skill-only`） | `plugins/<plugin-name>/` plugin package | `plugins/<plugin-name>/.claude-plugin/plugin.json`（Claude Code 公式 plugin manifest） | kebab-case の Skill 名のみ。plugin 名は配置パスで表現（06章第17条） |

Phase 2 以降の標準運用では、配布単位は `creator-kit/` ではなく `plugins/<plugin-name>/` の plugin package になる。ユーザーは `/plugin install <plugin>` だけで必要な Skill / Agent / Hook / script / settings を利用できる状態を完了条件とする。どの component を同梱するか、どの検査を package completeness check とするかは [36-plugin-package-harness-contract.md](./36-plugin-package-harness-contract.md) を正本とする。`skill-only` は legacy / dev-only / migration exception 扱いであり（36章 §`skill-only`）、新規量産では選択しない。

標準のE2E入口は `run-skill-create` である。`run-skill-create` は要望から完成までを、`run-skill-elicit` → `run-build-skill` → creator-kit登録判定 → P0 lint → `assign-skill-design-evaluator` → `run-elegant-review` → governance の順でゲート付きに連鎖させる。新規作成と更新のどちらもこの入口から開始し、途中でユーザー判断が必要な箇所だけ gate template に従って確認する。

既存プロジェクトを kit 化する場合は、まず `bash creator-kit/migrate-from-project.sh --dry-run` で移動対象を確認し、問題なければ本実行する。kit 由来 symlink だけを uninstall 対象とし、プロジェクト固有 Skill や業務設計書は移動しない。`xl-skills` 本体の symlink 配置は完了しており、`.claude/skills/` は `creator-kit/skills/*` への symlink 参照として確認済みである。ただし `migrate-from-project.sh` の正式実行ログは未取得であり、C4は暫定PASSとして扱う (32章参照)。

## 自動フロー (全体図)

```text
[User] "○○する Skill を作って"
   │
   ▼
[Step 1] OS確認 (Mac / Windows) ──► scripts ランタイム選択
   │
   ▼
[Step 2] 要件ヒアリング (name / kind / trigger / output)
   │
   ▼
[Step 3] 設計書参照 (Progressive Disclosure（段階的開示）)
   │     06 → kind 決定
   │     09 → evaluator 必要性
   │     03/11 → frontmatter & 雛形
   │
   ▼
[Step 4] 雛形展開 + scripts 生成 (Python3 + ps1)
   │
   ▼
[Step 5] creator-kit登録判定（現行: creator-kit/manifest.json）
   │     scripts/build-manifest-registration-plan.py
   │     ├── 共通基盤なら登録案を提示 → 承認後 apply
   │     └── project固有なら登録せず理由を記録
   │     ※ Phase 2 以降は plugin package（.claude-plugin/plugin.json）を対象に
   │       PKG completeness check（36章フロー[5]）を実施。skill-only 時のみ creator-kit 経路。
   ▼
[Step 6] forked evaluator 起動 (assign-skill-design-evaluator)
   │     Read references/rubric.json
   │
   ▼
[Step 7] score >= threshold?
   │       ├── No  → findings 反映 → Step 4 へ (max 3 retry)
   │       └── Yes → install + ユーザーに path を返す
```

## ステップ別: 参照ドキュメント・テンプレ

| Step | 参照する設計書 | 使うテンプレ/asset |
|---|---|---|
| 1 OS確認 | 22-cross-platform-runtime | - |
| 2 要件 | 06-classification-and-naming | - |
| 3 分類 | 06 / 09 / 10 | - |
| 4 frontmatter | 03-yaml-frontmatter-reference | `templates/<kind>.md` |
| 4 本文 | 07 / 08 / 11 | `examples/*.md` |
| 4 scripts | 22 | `scripts/render-frontmatter.{py,ps1}` |
| 4 self-check | 13-checklists | チェックリスト雛形 |
| 5 creator-kit登録判定 | 23 / 28 / 32 | `scripts/build-manifest-registration-plan.py` |
| 6 evaluator | 09-evaluation-orchestration | `assign-skill-design-evaluator/references/rubric.json` |
| 7 retry | 09 / 19-troubleshooting | findings JSON |

## creator-kit登録ゲート

`run-skill-create` は自然言語の依頼から、追加物が横展開対象かを判定する。判定基準:

| 追加物 | creator-kit登録 |
|---|---|
| Harness Creator の生成・更新・評価・governance に関係する Skill | 登録する |
| 複数プロジェクトで使う `ref-*` / rubric / reference | 登録する |
| hook / lint / adapter / secret helper / config雛形 | 登録する |
| 特定プロジェクトだけの業務Skill | 登録しない |
| 業務Skillから抽出した共通ルール | `ref-*` / `assign-*` / `scripts/lint-*` として登録候補 |

登録候補がある場合:

```bash
python3 scripts/build-manifest-registration-plan.py
```

この出力をユーザーに提示し、承認後のみ次を実行する。

```bash
python3 scripts/build-manifest-registration-plan.py --apply
python3 scripts/lint-manifest-contents.py
```

承認なしに `manifest.json` を更新しない。登録しない場合も、完了レポートに `creator_kit_registration: skipped` と理由を残す。

ここで `manifest.json` が指すのは `creator-kit/manifest.json`（kit 収録目録）であり、Claude Code 公式 plugin manifest（`plugins/<plugin-name>/.claude-plugin/plugin.json`）とは別物である。Phase 2 以降の plugin package mode では、本ゲートは PKG completeness check（36章フロー[5]、PKG-001〜010）に置き換わる。本 runbook で「manifest」と書かれた箇所は、文脈が creator-kit 配布なら前者、plugin package 配布なら後者を指す。

## 失敗時 retry ルール

evaluator から返る JSON に基づく:

| 条件 | 動作 |
|---|---|
| `passed: true` | 完了、ユーザーに artifact path を返す |
| `passed: false` かつ retry < 3 | `required_fixes` を入力に generator 再実行 |
| retry == 3 で fail | 中断、findings 全件をユーザーに提示し手動介入要請 |
| evaluator 自体が落ちた | runbook 中断、`xl-skills/eval-log/` に stderr を残す |

threshold は `references/rubric.json` の `threshold: 80` をデフォルトとし、`run-build-skill` の引数で override 可能 (例: deploy-critical Skill は 90)。

## retry時の注意

- generator は会話履歴を保持しているため self-correction で sycophancy が出やすい (09)
- 同じ findings が 2 回連続で出たら rubric 側にバグの可能性 → 自動 retry を止めて報告

## Mac / Windows 別実行手順

### 共通: OS 確認プロンプト

`run-build-skill` の Step 1 で次を実行:

```text
これから Skill を作ります。実行 OS を選択してください:
  1) macOS / Linux  (python3 を使用)
  2) Windows        (powershell 5.1+ を使用 / Windows 10 標準同梱)
```

選択結果を `$SKILL_BUILD_OS` に保持して以後の Bash 呼び出しで分岐。

### macOS / Linux

```bash
python3 .claude/skills/run-build-skill/scripts/render-frontmatter.py \
  --name run-foo --kind run --out .claude/skills/run-foo/SKILL.md
```

前提:

- Python 3.9+ が PATH にある (macOS 標準 / Homebrew どちらでも可)
- 標準ライブラリのみ使用 (依存インストール不要)

### Windows

```powershell
powershell -ExecutionPolicy Bypass -File .claude/skills/run-build-skill/scripts/render-frontmatter.ps1 `
  -Name run-foo -Kind run -Out .claude/skills/run-foo/SKILL.md
```

前提:

- PowerShell 5.1+ (`powershell`) が利用可能 (Windows 10 以降に標準同梱、追加インストール不要)
- ps1 は原則として PowerShell 標準機能だけで完結させる。`.py` を呼ぶ実装にする場合は、Python 不在時の純 PowerShell fallback を同梱する (22 参照)。

### 共通の後処理

```bash
# evaluator 起動 (Claude Code 内から Skill 呼び出し)
/skill assign-skill-design-evaluator .claude/skills/run-foo
```

evaluator 出力 JSON を `xl-skills/eval-log/<timestamp>-run-foo.json` に保存。

evaluator 出力には `rubric_hash` を含める。rubric を変更する場合は生成物修正とは別 PR / 別承認者で扱い、評価基準を緩めて合格させる Goodhart（評価基準を都合よく歪める罠）を防ぐ。

## 案件・プロジェクト追加時の運用

新しい会社プロジェクト、案件、タスク種別が増えた場合、最初に増やすのは Skill ではなく rubric / reference である。

1. 共通 evaluator は変更しない。
2. `references/<project>-rubric.json` または `ref-<domain>-rules` を追加する。
3. `reference_refs` に API 契約、用語集、acceptance criteria を追加する。
4. `rubric_refs` に L0 共通、L1 domain、L2 project/task の順で列挙する。
5. `script_refs` に P0 script を追加し、存在、循環、schema、hash、依存方向を検証する。
6. evaluator は合成済み rubric、reference、script 結果、artifact だけを評価する。

Skill を増やす条件は、artifact 種別、実行副作用、または作業手順が根本的に違う場合に限定する。評価基準が違うだけなら rubric を増やす。

## 完了判定

- evaluator が `passed: true` を返す
- evaluator 出力 JSON に `rubric_hash` が記録されている
- P0 lint (`lint-skill-name` / `lint-skill-tree` / `validate-frontmatter` / `lint-dependency-direction` / `lint-forbidden-deps` / `lint-manifest-contents`) が通過する。P0 未実装、または hook / CI へ未接続なら「暫定PASS」と明記する
- `.claude/skills/<name>/SKILL.md` が存在し YAML がパース可能
- `name` ディレクトリ名と frontmatter `name` が一致 (rubric NM-001)
- README 等の設計書側変更は不要 (`run-build-skill` は設計書を読むのみで編集しない)

---

## context予算制約（CD-005 パッチ）

### 全章一括ロード禁止

Opus モデル + 全30章 + SubAgent 生成を同一コンテキストで実行するとトークン超過が発生する。以下のルールを設計書の運用制約とする。

| 制約 | 内容 |
|---|---|
| 章ロード上限 | 同一 Step で参照する設計書章は最大3章まで |
| 全章一括禁止 | `references/design-docs-index.md` から必要章のみ選択して Read する |
| SubAgent 生成 | 親 context が重い場合は Step7 の SubAgent 生成を別セッションに分離する |

### frontmatter による context 予算宣言

各 SKILL.md の frontmatter に context-budget を宣言できる:

```yaml
# context-budget: 各Stepで読む設計書章の上限
# max-reference-chapters: 3
```

この値は run-build-skill が各 Step で参照章数を制御する際の上限として使う。`build-subagent.py` のデフォルトモデルは opus（PF-F3-001）。

### 段階ロード指針

| Step | 読む章 |
|---|---|
| Step 1 要求ヒアリング | 06章のみ |
| Step 2 テンプレ展開 | 11章のみ |
| Step 3 補助ファイル | 07/08章（どちらか一方） |
| Step 4 Lint | 13章のみ |
| Step 5 creator-kit登録判定 | 23章または32章のみ |
| Step 6 評価 | 09章のみ |
| Step 7 SubAgent生成 | references/build-steps.md のみ |
