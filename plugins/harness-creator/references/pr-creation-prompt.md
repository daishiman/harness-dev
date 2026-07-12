# PR作成 完全自律プロンプト（feature → main）

> このリポジトリの実態（ブランチ運用 / 検証コマンド / CI / 落とし穴）に対応させた、PR作成を完全自律実行するための運用プロンプト。7層構造（`plugins/prompt-creator/skills/run-prompt-creator-7layer/references/seven-layer-format.md` 準拠・Layer 5 はゴールシーク型 l5-contract v2.0.0：固定手順ではなく目的・背景・達成ゴール・完了チェックリストで宣言）で記述する。

---

## ① 使い方（エントリ）

このリポジトリには PR 作成専用のスラッシュコマンド（例: `diff-to-pr` のようなもの）は存在しない。下記「② 構造化プロンプト」をそのまま Claude Code（本セッションまたは新規セッション）に貼り付けて実行させること。コミットの安全化（機密ファイル混入・`--no-verify`/`--no-gpg-sign`・force-push の検出）には `wrap-git-commit-safe` skill（`plugins/harness-creator/skills/wrap-git-commit-safe`）を併用可能で、明示指定しなくても Claude Code が commit 前に自律判断で呼び出してよい。

---

## ② 構造化プロンプト（説明）

### メタ

| key | value |
|---|---|
| プロジェクトID | `pr-creation-skills` |
| 実行モード | 完全自律（承認確認なし） |
| 対象repo | このリポジトリ |
| ブランチフロー | feature → main（dev ブランチ無し） |
| layers_covered | [L1, L2, L3, L4, L5, L6, L7] |
| reproducible | 同一の差分・同一のCI状態からは同一手順に収束する（LLM自由度は手順選択のみ） |

## Layer 1: 基本定義層（不変原則）

### 1.1 プロジェクト概要
- 想定利用者: 変更を行った開発者（本人 or Claude Code 自律実行）。
- 最上位目的: 現在のブランチの全変更を漏れなく `main` へ安全にPR化する。
- 背景コンテキスト: リモートは `origin/main` のみでdevブランチが存在しない feature→main 直結運用。CIはgovernance-check.yml / harness-creator-kit-ci.yml の2本立てで、pre-push相当の `scripts/run-ci-checks.sh` はpytestを含まないため単独では不十分。
- 期待される成果: `gh pr create --base main` で作成されたPRが、全変更を100%含み、`make test` 相当のゲートがローカルで確認済みの状態。
- 成功基準: (a) `make test` 全ゲートPASS、(b) `git diff origin/main...HEAD --name-only` と実際にPRへ含まれる変更が完全一致、(c) `gh pr create` が成功しPR URLが得られる。
- スコープ:
  - 含む: main同期・コンフリクト解消・品質検証・自動修復・PR作成・最終報告。
  - 含まない: 内容面のレビュー（PRの是非判断）・強制push・main直push・破壊的操作の無承認実行。

### 1.2 不変ルール
- ユーザーに確認・承認・選択を求めない（CONST_009）。
- 本ブランチの変更を一切除外しない（CONST_006）。
- `main` への直push・force-pushを行わない。

## Layer 2: ドメイン定義層（本質ロジック）

### 2.1 用語集

| 用語 | 定義 |
|---|---|
| feature→main運用（dev無し） | リモートは `origin/main` のみ。参考プロンプトの「feature→dev」「dev同期」は全て「main同期」に読み替える。 |
| `make test` | 検証の正本コマンド。`sync-check lint plugin-package-check feedback-contract content-review pytest llm-coverage` + `scripts/gate-phase0.py` を集約実行する（Makefile `test` ターゲット）。 |
| clean-checkout検証（`git archive HEAD`） | push前に `git archive HEAD \| tar -t` でtrackedツリーのみを列挙し、広い `.gitignore` が正規ソースを巻き込んでいない（＝ローカル緑/CI赤の再発）ことを確認する手段。 |
| eval-log evidence | `eval-log/` 配下のelegant-review verdict・pytest件数・ゲートPASSログ等の検証証跡。PR本文の裏付けとして参照する。 |
| `wrap-git-commit-safe` | commit前後を安全側でwrapするskill（`plugins/harness-creator/skills/wrap-git-commit-safe`）。機密ファイル・`--no-verify`/`--no-gpg-sign`・force-pushを決定論的にBLOCKする。 |

### 2.2 ビジネスルール（CONST）

| ID | 内容 |
|---|---|
| CONST_001 | テスト実行は不要ではなく必須。このrepoはpytestが検証ゲートの正本でCIも走らせる（`run-ci-checks.sh`はpytest非包含）。`make test` またはpytest直接実行で緑を確認する。 |
| CONST_002 | 実行コマンドは `make`(test/lint/pytest/sync 等) + `python3` 各lintスクリプト + `pip install -r requirements-dev.txt` + `git` + `gh` のみ。pnpm/npm/yarn/tsc等TypeScript系ツールは使わない。 |
| CONST_003 | PR本文は自前テンプレ（概要 / 変更点(plugin・component別) / 検証結果(各ゲートPASS) / eval-log evidence / 関連）。 |
| CONST_004 | PR本文に全変更をplugin/component別で100%反映（源泉=実diff + eval-log evidence）。 |
| CONST_005 | スクリーンショット該当なし（UI無しrepo）。項目自体を設けない。 |
| CONST_006 | 本ブランチの全変更を一切除外せずPRに含める（絶対原則）。ステージ済み/未ステージ/未追跡/コミット済み差分すべて。`git status --porcelain` と `git diff origin/main...HEAD --name-only` の2段照合で欠落ゼロを保証する。ただし `.claude/` symlink経由でなく実 `plugins/` パスでaddする。 |
| CONST_007 | push前に `git archive HEAD` でclean-tree CIパリティを確認しgitignore巻込漏れを検出する。 |
| CONST_008 | `guard-change-category`(`--base origin/main`)をPR前に緑化する。 |
| CONST_009 | AIはユーザーに確認・承認・選択を求めない。全分岐は自律判断ルール（A/B/C/D）で即時決定する。 |
| CONST_010 | エラー・コンフリクト・失敗時もユーザーに問わず自動修復を試行する。解決不能な場合のみ最後に1回まとめて報告する。 |

## Layer 3: インフラストラクチャ定義層（外部依存）

### 3.1 ツール

| ツール | 用途 |
|---|---|
| `git` | fetch/merge/add/commit/branch/diff/status/archive |
| `gh` | `gh pr create --base main`（PRテンプレートファイルは無いので本文は自前構成） |
| `make` | `test` / `lint` / `pytest` / `sync` / `sync-check` / `plugin-package-check` / `content-review` / `feedback-contract` / `llm-coverage` / `coverage-gate` / `harness-coverage` / `harness-ratchet` |
| `python3` | 各lint/validateスクリプト直接実行、`pip install -r requirements-dev.txt` |
| `scripts/run-ci-checks.sh` | pre-push SSOT。ただしpytestを含まないため単独では不十分（必ずpytestを別途直接実行）。 |
| `git archive HEAD` | clean-checkout CIパリティ検証（gitignore巻込漏れ検出） |
| `wrap-git-commit-safe` skill | commit安全化（機密ファイル/`--no-verify`/force-push検出） |
| SubAgent並列実行 | Agent2の各ゲート・Agent3の事前検証項目を独立に並列化してよい |

### 3.2 参照リソース

| id | path | when_to_read |
|---|---|---|
| Makefile | `Makefile` | 検証コマンドの正確な集約内容を確認する時 |
| pre-push SSOT | `scripts/run-ci-checks.sh` | ローカルCI相当チェックを走らせる時（pytestは別途必須） |
| governance CI | `.github/workflows/governance-check.yml` | `guard-change-category`含む先頭ゲート内容を確認する時 |
| kit CI | `.github/workflows/harness-creator-kit-ci.yml` | per-plugin pytestのcwd規約・py_compile対象を確認する時 |
| dev依存 | `requirements-dev.txt` | pytest実行前提（PyYAML/jsonschema必須）を確認する時 |
| commit安全化 | `plugins/harness-creator/skills/wrap-git-commit-safe/SKILL.md` | commit前の安全チェック内容を確認する時 |

## Layer 4: 共通ポリシー層

### 4.1 許可コマンド
- `make`（test/lint/pytest/sync/sync-check/plugin-package-check/feedback-contract/content-review/llm-coverage/coverage-gate/harness-coverage/harness-ratchet）
- `python3` 各lint/validateスクリプト直接実行
- `pip install -r requirements-dev.txt`（`--user` or venv 推奨。macOS system pythonはPEP668で素の`pip install`が失敗しうる）
- `git`（status/diff/fetch/merge/add/commit/branch/archive/push。force-push禁止・main直push禁止）
- `gh`（`pr create`/`pr view` 等）
- 禁止: pnpm/npm/yarn/tsc等TypeScript系ツール全般（CONST_002。このrepoはPython/Bash製）

### 4.2 自律判断ルール（分岐は即時決定・確認不要）

**ルールA（ブランチ命名）**: 現在のブランチが `main` または detached HEAD の場合、`feat|fix|refactor|docs/<主題-kebab>` 形式の新規ブランチを切ってから作業する。主題特定が困難な場合は `feat/update-YYYYMMDD` を既定名にする。

**ルールB（コンフリクト解消）**: `git merge origin/main` でコンフリクトが出た場合、種別ごとに以下の方針で自律解消する。
- 設定ファイル: main優先で採用し、自分の変更差分を再適用する。
- 生成物（lockfile・`*-coverage.json`等の派生ファイル）: 手動マージせず対応する生成スクリプトで再生成する。
- ソースコード: 両者の変更意図を保持する形で手動マージする（片方を機械的に捨てない）。
- ドキュメント: 内容を結合し重複記述をdedupする。

**ルールC（検証失敗の自動修復。repo固有・最大3イテレーション）**:

| # | 症状（赤化ゲート） | 自動修復 |
|---|---|---|
| 1 | pytest実行前提不足（PyYAML/jsonschema等ImportError） | `python3 -m pip install --user -r requirements-dev.txt` |
| 2 | `build-claude-symlinks --check` 赤 | `make sync`（`bash scripts/sync-skills-to-claude.sh --apply`）で再生成 |
| 3 | `criteria-roster-parity` 赤 | `python3 tests/criteria/build_criteria_roster.py` で再生成 |
| 4 | `llm-coverage-parity` 赤 | `python3 scripts/validate-llm-coverage.py --all`（`--check`を外して書込実行）で再生成 |
| 5 | `sync-notion-schema --check` 赤 | **自動修復しない**（`--apply` は Notion への書込＝ネットワーク副作用のため PR フローで自動実行禁止）。`doc/notion-schema/` の意図した変更が原因かを調べ、意図的なら差分を PR 本文へ記録、想定外なら最終レポートに残す |
| 6 | `check-scripts-drift` 赤（`scripts/check-scripts-drift.sh`） | drift元（壊れたsymlink/参照先欠落）を実体に同期・復元する |
| 7 | 全 `.py` の `py_compile` 赤 | 構文エラーを特定し修正する |
| 8 | `content-review`/`live-trial-verdict` verdict赤（stale verdict） | 独立SubAgentでgenuine再評価してから緑化する |
| 9 | pytest赤 | CIのcwd規約（`cd <plugin> && pytest`。repo-rootからのpassは無保証）で緑判定し最小修正する |

上限到達（3イテレーション）しても赤が残る場合はルールDに進まずLayer4「エスカレーション」に落とす。

**ルールD（PR本文自動判定）**: スクリーンショット項目は固定で設けない（CONST_005）。PR本文の源泉は実diff（plugin/component別グルーピング）＋ `eval-log/` evidence（あれば参照。無ければ「該当証跡なし」と明記し省略しない）。PRタイトルはブランチ名の主題部分（`feat/xxx` → 「xxx」相当）から簡潔に生成する。

### 4.3 失敗時挙動・エスカレーション
- ルールC上限（3イテレーション）到達で解消不能な検証失敗、またはルールBで解消不能な意味的コンフリクト（両者の意図が両立不能）が生じた場合のみ、最後に1回まとめてユーザーへ報告する（CONST_010）。それ以外は自律修復を継続する。
- 報告内容: 未解消ゲート/コンフリクト箇所・試行した修復内容・推奨される人手判断ポイント。

## Layer 5: エージェント定義層（ゴール駆動の実行主体）

### Agent1 — main同期・コンフリクト解消

- 5.1 担当: 現ブランチをmainと同期し、コンフリクトを自律解消する。
- 5.2 ゴール定義
  - 目的: リモートmainとの乖離・コンフリクトを人手を介さず解消し、後続の検証・PR作成を阻害しない状態を作る。
  - 背景: feature→main直結運用（dev無し）のため、同期漏れ・コンフリクト放置は`guard-change-category`はじめgovernance-check.yml全体を無意味に赤化させる。
  - 達成ゴール: **ローカル `main` が `origin/main` に一致（リモート main → ローカル main を反映済み）**し、その最新 `main` を**作業ブランチ（ワークツリー / 本ブランチ）へマージ済み**で、コンフリクトマーカーが1つも残っていない状態。作業ブランチはルールA準拠の命名。
- 5.2.1 main同期の二段手順（必須順序・**コンフリクトはPR前に完全解消する**）
  1. `git fetch origin main` — リモート main の最新を取得。
  2. **リモート main → ローカル main**（ローカル `main` を `origin/main` に一致させる）:
     - 通常: `git checkout main && git merge --ff-only origin/main`。
     - **worktree 運用で `main` が別 worktree に checkout 済みで切替不可の場合**: `main` を持つ worktree 側で上記 FF を行うか、`git fetch origin main:main` でローカル main ref を FF 更新する。どちらも不可なら次段のマージ元を `origin/main` に読み替える（ローカル main == origin/main ゆえ結果は同一）。
  3. **ローカル main → 作業ブランチ**（ワークツリー / 本ブランチ）: 作業ブランチに戻り `git merge main` で最新 main を取り込む。
  4. 発生したコンフリクトをルールBで**完全解消**（`git add` → `git commit`。`<<<<<<<` マーカーと unmerged path が 0）。
  - **ゲート: コンフリクトが1件でも残る間は Phase2 / Phase3 へ進まない。PR は必ずコンフリクト完全解消後に作成する。**
- 5.3 完了チェックリスト
  - [ ] `git branch --show-current` が `main`／detached HEADではなく、ルールA準拠の命名である
  - [ ] **リモート main → ローカル main 反映済み**（`git log main..origin/main` が空＝ローカル `main` が `origin/main` に一致）
  - [ ] その最新 `main` を**作業ブランチへマージ済み**（`git merge main`）で、コンフリクトマーカー（`<<<<<<<`等）がツリーに残っていない
  - [ ] 発生したコンフリクトがルールB（設定=main優先再適用／生成物=再生成／ソース=両意図保持／文書=結合dedup）に従って解消済みである
  - [ ] `git status --porcelain` がunmerged pathを含まない（**コンフリクト完全解消をPR前に確認**）
- 5.4 実行方式: 固定手順を持たない。現状評価（ブランチ名・fetch差分・コンフリクト種別）→ルールA/Bを適用した解消方針を都度立案→実行→`git status`で検証→全項目充足まで反復する。
- インターフェース: 出力(受領先=Agent2) = 同期済み・コンフリクト解消済みの作業ブランチ + 解消ログ（どのファイルを何の方針で解消したか）。

### Agent2 — 品質検証

- 5.1 担当: `make test` 相当の全ゲートを緑化し、赤の場合はルールCで自動修復する。
- 5.2 ゴール定義
  - 目的: PR作成前に、このrepoの検証正本（`make test`）と`guard-change-category`をローカルで緑化しておき、push後のCI赤を未然に防ぐ。
  - 背景: `scripts/run-ci-checks.sh`はpytestを含まないため単独PASSは十分条件でない（CONST_001）。CIは`cd <plugin> && pytest`のcwdで走るため、repo-rootのpassだけでは不十分。
  - 達成ゴール: `make test`（`sync-check lint plugin-package-check feedback-contract content-review pytest llm-coverage` + `gate-phase0.py`）が exit 0、かつ `python3 scripts/guard-change-category.py --base origin/main` がPASSしている状態。
- 5.3 完了チェックリスト
  - [ ] `python3 -m pip install --user -r requirements-dev.txt` 実行済み（pytest/PyYAML/jsonschema等が解決済み）
  - [ ] `make test` が exit 0
  - [ ] `bash scripts/run-ci-checks.sh` がPASS（ただしこれ単独は十分条件でないと認識した上で実行）
  - [ ] repo-root `pytest tests/` に加え、変更が及ぶ各pluginで `cd plugins/<plugin> && pytest` が緑（CIのcwd規約に合わせて確認済み）
  - [ ] `python3 scripts/guard-change-category.py --base origin/main` がPASS
  - [ ] 赤化ゲートが1件でもあれば、ルールC該当行を適用し再検証済み（最大3イテレーション）
  - [ ] 自動修復を行った場合、その変更は `chore: auto-fix <対象>` 相当のコミットとして分離記録されている
- 5.4 実行方式: 固定手順を持たない。現状評価（どのゲートが赤か）→ルールC該当行を適用した修復手順を都度立案→実行→再検証→全項目充足まで反復（上限3イテレーション。超過時はLayer4エスカレーションへ）。
- インターフェース: 入力(提供元=Agent1) = 同期済みブランチ。出力(受領先=Agent3) = 全ゲートPASS状態 + 実施した自動修復の一覧（コミット済み）。

### Agent3 — PR作成

- 5.1 担当: 全変更を漏れなくコミット・push し、`gh pr create --base main` でPRを作成する。
- 5.2 ゴール定義
  - 目的: 本ブランチの全変更（ステージ済み/未ステージ/未追跡/コミット済み差分すべて）を一切除外せず、検証済みの状態でPR化する。
  - 背景: `.claude/`はsymlink経由のため、そこ経由で`git add`するとCIで beyond-symbolic-link 失敗する。広い`.gitignore`が正規ソースを巻き込むと「ローカル緑/CI赤」が再発する。
  - 達成ゴール: `gh pr create`で作成されたPRの差分が`git diff origin/main...HEAD --name-only`と完全一致し、PR本文が全変更をplugin/component別で反映し、`git archive HEAD`によるclean-tree検証済みの状態。
- 5.3 完了チェックリスト
  - [ ] 未追跡・未ステージの変更を実 `plugins/…` パス（`.claude/`symlink経由でない）で `git add` 済み
  - [ ] `git status --porcelain` と `git diff origin/main...HEAD --name-only` を突合し、addされるべき変更に欠落がない（CONST_006の2段照合）
  - [ ] commitはCo-Authored-By行（`Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`）を含み、commit時は`wrap-git-commit-safe`skillの安全チェック（機密ファイル/`--no-verify`/force-push検出）を経ている
  - [ ] push前に `git archive HEAD | tar -t` でtracked treeを検証し、必要ファイルが漏れなくtrackedである（CONST_007）
  - [ ] PR本文がCONST_003テンプレ（概要/変更点(plugin・component別)/検証結果(各ゲートPASS)/eval-log evidence/関連）に従い、スクリーンショット項目を含まない（CONST_005/ルールD）
  - [ ] PR本文の変更点がplugin/component別で100%反映されている（CONST_004。実diff起点で機械的に列挙し漏れをゼロ照合）
  - [ ] PR本文末尾に `🤖 Generated with [Claude Code](https://claude.com/claude-code)` フッターがある
  - [ ] `gh pr create --base main` が成功しPR URLを得ている
- 5.4 実行方式: 固定手順を持たない。現状評価（未反映の変更・PR本文源泉の充足状況）→充足のための手順を都度立案→実行→上記チェックリストで検証→全項目充足まで反復。
- インターフェース: 入力(提供元=Agent2) = 全ゲートPASS済みブランチ。出力(受領先=最終レポート/ユーザー) = PR URL・含まれる変更件数・実施した自動修復概要・自律解消したコンフリクト・残課題。

## Layer 6: オーケストレーション層（ゴールシーク制御）

### 6.1 フェーズ制御
- Phase1（Agent1: main同期＝**リモート main → ローカル main → 作業ブランチ の二段マージ＋コンフリクト完全解消**）→ Phase2（Agent2: 品質検証）→ Phase3（Agent3: PR作成）の直列実行。省略禁止（Phase2を飛ばしてPhase3に進まない）。**Phase1 でコンフリクトが1件でも残る間は Phase2/Phase3 に進まず、PR は必ずコンフリクト解消後に作成する。**
- 完全自律: 各Phase内・Phase間の分岐判断はLayer4の自律判断ルールA/B/C/Dで即時決定し、ユーザーに確認を求めない。

### 6.2 ハンドオフ
- 直列: 前Agentの出力(受領先)を後続Agentの入力(提供元)にそのまま接続する（5.x インターフェース節参照）。
- 並列（任意）: Agent2内の各ゲート、Agent3内の事前検証項目はSubAgentで並列化してよい。統合はAND条件（全項目PASSで次Phaseへ）。

### 6.3 全変更網羅の2段検証（CONST_006の機械照合）
1. `git status --porcelain` で working tree の全変更（追跡・未追跡）を列挙する。
2. `git diff origin/main...HEAD --name-only` でmainからの差分ファイル一覧を取得する。
3. 両者を突合し、addされるべきなのに漏れているファイルが無いことを確認する（0件でPASS）。

### 6.4 完了判定・最終レポート
- 完了判定: Agent1〜3の完了チェックリストが全て充足し、`gh pr create`が成功した時点で完了。
- 最終レポートは1回のみ、以下を含めて報告する: PR URL / ブランチ名 / 自動修復概要（ルールC適用箇所） / 自律解消したコンフリクト（ルールB適用箇所） / 残課題（あれば）。

## Layer 7: ユーザーインタラクション層

### 7.1 UserInput（このプロンプトの起動テキスト）

> 本ブランチの全変更を漏れなく main 同期・コンフリクト解消・`make test` 検証・`gh pr create` で PR 化してください。**main 同期はリモート main → ローカル main → 作業ブランチ（ワークツリー / 本ブランチ）の順にマージし、コンフリクトを完全解消してから PR を出してください。** SubAgent分割・並列可。完全自律（確認なし）でお願いします。feature→main運用（devブランチ無し）です。push前に `git archive HEAD` で clean-tree 検証してください。`.claude/` symlink経由でなく実 `plugins/` パスで `git add` してください。

### 7.2 出力形式
- 本文: 日本語。
- 最終レポートはMarkdown（Layer6.4の5項目を見出し無しの箇条書きで簡潔に）。
- 途中経過（各Phaseの実行ログ）は逐次出力してよいが、確認・承認を求める文言は出力しない（CONST_009）。

---

## 出力指示（LLM実行時に読む箇所）

上記Layer 1〜7をコンテキストとして、以下を実行せよ。

1. Phase1（Agent1）: 現在のブランチ・fetch差分・コンフリクトの有無を確認し、**二段手順（`git fetch origin main` → リモート main をローカル `main` に反映 → 作業ブランチへ `git merge main` → コンフリクトをルールBで完全解消）**でmain同期を完了する。**コンフリクトが残る間はPhase2へ進まない。**
2. Phase2（Agent2）: `pip install -r requirements-dev.txt` 前提を満たした上で `make test` と `guard-change-category.py --base origin/main` を実行し、赤があればルールC該当行で最大3イテレーション自動修復する。
3. Phase3（Agent3）: 実 `plugins/` パスで全変更を `git add`、CONST_006の2段照合で欠落ゼロを確認、`wrap-git-commit-safe` 経由で安全にcommit（末尾に `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`）、push前に `git archive HEAD` でclean-tree検証、CONST_003テンプレでPR本文を構成（フッター `🤖 Generated with [Claude Code](https://claude.com/claude-code)` を含む）、`gh pr create --base main` を実行する。
4. 完了後、Layer6.4の最終レポートを1回だけ出力する。確認・承認は一切求めない。解消不能な失敗が残った場合のみ、その内容をレポートに含めて報告する。
