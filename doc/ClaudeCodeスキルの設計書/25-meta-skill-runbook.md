# 25. メタSkill Runbook

`run-build-skill` を使ってユーザー要求から動作する Skill を 1 本仕上げるまでの実行手順。MVP は `run-build-skill` と `assign-skill-design-evaluator` の 2 Skill で開始し、rubric（評価基準）は evaluator 配下の `references/rubric.json` として扱う。

## creator-kit を使うE2E運用

別プロジェクトでメタSkill基盤を使う場合は、個別Skillを手でコピーせず harness-creator-kit（旧 `creator-kit/`。今の置き場所は `installers/` と `plugins/` で、[32章](./32-creator-kit-implementation-ledger.md) 冒頭の注記のとおり）を配布単位にする。配布形態は git submodule、単純コピー、同一マシン内 symlink の3つで、詳細手順は `installers/harness-creator-kit/README.md` に委譲する。

### 配布レイヤーの時系列分離（manifest 二義性の解消）

本 runbook で `manifest` が指す対象は時系列で2層あり、混同しないこと。詳細は [36-plugin-package-harness-contract.md](./36-plugin-package-harness-contract.md) §`package_mode` を正本とする。

| フェーズ | 配布単位 | `manifest` が指す実体 | `name:` 表記 |
|---|---|---|---|
| 現行（creator-kit 配布 = `skill-only` 相当の移行期表現） | harness-creator-kit（旧 `creator-kit/`） | `installers/manifest.json`（kit 内の Skill 収録目録） | kebab-case の Skill 名（plugin 名は不在） |
| Phase 2 以降（36章 `package_mode != skill-only`） | `plugins/<plugin-name>/` plugin package | `plugins/<plugin-name>/.claude-plugin/plugin.json`（Claude Code 公式 plugin manifest） | kebab-case の Skill 名のみ。plugin 名は配置パスで表現（06章第17条） |

Phase 2 以降の標準運用では、配布単位は harness-creator-kit ではなく `plugins/<plugin-name>/` の plugin package になる。ユーザーは `/plugin install <plugin>` だけで必要な Skill / Agent / Hook / script / settings を利用できる状態を完了条件とする。どの component を同梱するか、どの検査を package completeness check とするかは [36-plugin-package-harness-contract.md](./36-plugin-package-harness-contract.md) を正本とする。`skill-only` は legacy / dev-only / migration exception 扱いであり（36章 §`skill-only`）、新規量産では選択しない。

標準のE2E入口は `run-skill-create` である。`run-skill-create` は要望から完成までを、`run-skill-elicit` → `run-build-skill` (生成と、利用者が選んだときだけの初稿診断) → creator-kit登録判定 → create 固有の P0 lint (build と重複する lint は build の lint receipt を再利用) → Gate 2 → package 検査 → 完了レポートの順でゲート付きに連鎖させる。評価は build の初稿診断 1 回に一本化し、`assign-skill-design-evaluator` / `run-elegant-review` / governance は利用者が明示的に呼んだときだけ走らせる。新規作成と更新のどちらもこの入口から開始し、途中でユーザー判断が必要な箇所だけ gate template に従って確認する。

既存プロジェクトを kit 化する場合は、まず `bash installers/migrate-from-project.sh --dry-run` で移動対象を確認し、問題なければ本実行する。ただしこの script は旧 `creator-kit/` の配置（kit 直下の `skills/`・`scripts/`・`config/`）へ移す作りのままで、今の `plugins/` の配置には移さない。`--dry-run` でも `installers/` の下に空の dir を作る。kit 由来 symlink だけを uninstall 対象とし、プロジェクト固有 Skill や業務設計書は移動しない。`xl-skills` 本体の symlink 配置は完了しており、`.claude/skills/` の大半は `plugins/*/skills/*` への symlink である（32章冒頭の注記）。ただし `migrate-from-project.sh` の正式実行ログは未取得であり、C4は暫定PASSとして扱う (32章参照)。

## 自動フロー (全体図)

phase の正本は `plugins/harness-creator/skills/run-skill-create/workflow-manifest.json`。利用者に確認するのは `gate_order` の 3 か所 (Gate 1 → Gate 2.5 → Gate 2) と、build が現物を見せた後の診断深度の選択だけ。

```text
[User] "○○する Skill を作って"
   │
   ▼
[elicit] 要求ヒアリング → eval-log/skill-brief.json
   │     Gate 1: brief を見せて承認 (要件の確認はここで 1 回だけ)
   ▼
[build] run-build-skill がスキルを生成
   │     Step 4 lint (lint-matrix の build-preflight) → 現物を提示
   │     Step 12.5 診断深度の選択 (accept-as-is / light / standard / detailed)
   │       └ accept-as-is 以外を選んだときだけ、初稿診断 1 回と選んだ finding だけの改善
   ▼
[manifest-register] Gate 2.5: plugin / marketplace 登録判定 (承認後だけ apply)
   │     3.5 bundle 登録 / 3.55-3.56 Codex 同期 (plugin.json がある場合)
   │     3.6 local marketplace 再生成 / 3.7 fingerprint 記録・version 採番
   ▼
[p0-lint] create 固有の P0 lint
   │     build の lint receipt が PASS で SKILL.md の sha256 も一致すれば、重なる lint は再実行しない
   │     Gate 2: diff と build-trace を見せて承認
   ▼
[pkg-check] plugin-composition か新規 plugin のときだけ PKG completeness check
   │
   ▼
[report] 完了レポート
         C1-C4 は build の診断 receipt を転記する (評価し直さない。未診断ならそう書く)
         build_stage と deferred_to_release (draft で後回しにした release 検証) も書く
```

## ステップ別: 参照ドキュメント・テンプレ

| phase | 参照する設計書 | 使うテンプレ/asset |
|---|---|---|
| elicit | 06-classification-and-naming | `run-skill-elicit` / `schemas/skill-brief.schema.json` |
| build: frontmatter | 03-yaml-frontmatter-reference | `run-build-skill/templates/<kind>.md` |
| build: 本文 | 07 / 08 / 11 | `examples/*.md` |
| build: scripts | 22-cross-platform-runtime | `scripts/render-frontmatter.py`（ps1 版は計画） |
| build: lint | 13-checklists | `references/lint-matrix.json` |
| build: 診断 (選んだときだけ) | 09-evaluation-orchestration | `elegant-initial-draft-evaluator` |
| manifest-register | 23 / 28 / 32 / 36 | `scripts/build-manifest-registration-plan.py` |
| p0-lint | 13 | `workflow-manifest.json` の `phases[id=p0-lint]` |
| pkg-check | 36-plugin-package-harness-contract | `run-plugin-package-check` |
| 失敗時 | 19-troubleshooting | 失敗した lint の出力 |

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

ここで `manifest.json` が指すのは `installers/manifest.json`（kit 収録目録）であり、Claude Code 公式 plugin manifest（`plugins/<plugin-name>/.claude-plugin/plugin.json`）とは別物である。Phase 2 以降の plugin package mode では、本ゲートは PKG completeness check（36章フロー[5]、PKG-001〜010）に置き換わる。本 runbook で「manifest」と書かれた箇所は、文脈が creator-kit 配布なら前者、plugin package 配布なら後者を指す。

## 失敗時の扱い

自動の作り直し (retry) はしない。止まったときは原因を見せ、続け方は利用者が選ぶ。

| 条件 | 動作 |
|---|---|
| lint・Gate が fail | build へ自動で戻さない。失敗した lint と根本原因を見せて止まり、利用者が修正と再実行を選んだときだけ build から 1 回やり直す |
| 初稿診断で finding が出た | 利用者が選んだ finding だけを、指定した round 数の中で改善する (`elegant-improvement-executor`) |
| evaluator 自体が落ちた | 中断し、stderr を `eval-log/` に残す |

`references/rubric.json` の `threshold: 80` は、`build_stage=release` の出荷評価 (score>=80 かつ high=0) で使う。draft の build では出荷評価を走らせず、`deferred_to_release` に記録する。

## 改善時の注意

- generator は会話履歴を保持しているため self-correction で sycophancy が出やすい (09)。診断は fresh context の evaluator 1 回に限る
- 同じ finding が 2 回続けて出たら rubric 側のバグを疑い、改善を止めて報告する

## Mac / Windows 別実行手順

### 共通: OS 確認プロンプト

`run-build-skill` の Step 1 で次を実行:

```text
これから Skill を作ります。実行 OS を選択してください:
  1) macOS / Linux  (python3 を使用)
  2) Windows        (python を使用。無ければ起動コマンドを尋ねる)
```

選択結果を `$SKILL_BUILD_OS` に保持して以後の Bash 呼び出しで分岐。

### macOS / Linux

```bash
python3 .claude/skills/run-build-skill/scripts/render-frontmatter.py \
  --name run-foo --kind run --template .claude/skills/run-build-skill/templates/run.md \
  --out .claude/skills/run-foo/SKILL.md
```

前提:

- Python 3.9+ が PATH にある (macOS 標準 / Homebrew どちらでも可)
- 標準ライブラリのみ使用 (依存インストール不要)

### Windows

```powershell
python .claude\skills\run-build-skill\scripts\render-frontmatter.py `
  --name run-foo --kind run --template .claude\skills\run-build-skill\templates\run.md `
  --out .claude\skills\run-foo\SKILL.md
```

前提:

- Python 3.9+ が `python` で起動できる (Windows では別途 install が要る。22章「許可 CLI ホワイトリスト」)。
- `python` が無ければ、Python の起動コマンド (python3 / python / 未インストール) をユーザーに尋ね、答えのコマンドで上を実行する。未インストールなら止まる (22章「フォールバック動線」)。
- `render-frontmatter.ps1` で代わりに動かすのは計画（今の lint は `.ps1` を Skill 配下の scripts/ に置けない。06章 第10条、28章 §4.1）。

### 共通の後処理

evaluator は既定の流れでは起動しない。`build_stage=release` の出荷評価か、利用者が明示したときだけ次を呼ぶ。

```bash
/skill assign-skill-design-evaluator .claude/skills/run-foo
```

evaluator 出力 JSON は `eval-log/` に保存する。

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

- `gate_order` の全 Gate (Gate 1 / Gate 2.5 / Gate 2) に利用者の明示承認がある
- build の lint receipt が PASS で、create 固有の P0 lint (`lint-dependency-direction` / `lint-skill-dep-step7` / `lint-forbidden-deps` / `lint-manifest-contents` / `audit-capability-parity`) が通過する
- `.claude/skills/<name>/SKILL.md` (plugin なら `plugins/<plugin>/skills/<name>/SKILL.md`) が存在し YAML がパース可能
- `name` ディレクトリ名と frontmatter `name` が一致 (rubric NM-001)
- 完了レポートに C1-C4 の診断 receipt (未診断ならその旨)、`build_stage`、`deferred_to_release` がある
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
| Step 12.6 診断 (選んだときだけ) | 09章のみ |
| Step 7 SubAgent生成 | references/build-steps.md のみ |
