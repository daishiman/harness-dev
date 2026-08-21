# harness-creator

Codex / Claude Code の**ハーネス** — Capability (Skill / Agent / Hook / Command / Plugin-Composition / Prompt / Workflow) と、その評価・統治機構 (rubric / verdict / lint / feedback loop) を束ねた**構築物の総体** — を構築・評価・統治するメタプラグイン。

Codex package / marketplace / hook契約はOpenAI公式の
[Package your plugin](https://developers.openai.com/plugins/build/plugins)、Claude Code側は
[Plugins reference](https://code.claude.com/docs/en/plugins-reference)と
[Hooks reference](https://code.claude.com/docs/en/hooks)を正本とし、2026-08-20時点の
Codex / Claude Code CLIで実機確認している。

## Claude Code / Codex への user-global install

local cloneの全pluginを両製品へ入れる標準入口は`install-local-plugins.py`である。
scriptの配置からrepo rootを導出し、cwd相対pathを使わないため、別repositoryや`/tmp`からも
同じpluginを呼び出せる。

```bash
python3 /absolute/path/to/harness/plugins/harness-creator/scripts/install-local-plugins.py --all
```

| 差分 | Claude Code | Codex |
|---|---|---|
| marketplace root | `<repo>/marketplaces/local` | `<repo>` |
| marketplace name | `harness-local` | `harness-dev` |
| install範囲 | `--scope user` | user-global |
| runtime artifact | cacheへの`copy` | local=`live-source` / Git=`git-snapshot` |
| plugin hook root | `${CLAUDE_PLUGIN_ROOT}` | `${PLUGIN_ROOT}`（hookでは`${CLAUDE_PLUGIN_ROOT}`互換も提供） |

helperは2つのmarketplaceに掲載されたplugin集合が一致すること、sourceが各marketplace root
基準の`./plugins/<name>`でrepo内に閉じること、全pluginがenabledであることをfail-closedで
検証する。receiptには実行CLIの絶対path/version、`source_path`、実在する絶対`runtime_path`、
version、source/runtime digest、取得可能なGit commit、依存closure/SCCを記録する。さらに
installed / enabled / trust / new-session / runtimeを別statusにし、同名pluginのscope・marketplace・
runtime・hook digestを列挙する。`claude plugin list --json`の`errors`が非空、または同一hookの
多重activationがある場合は自動disableせず`pending_user_gate`（非verified、exit 1）にする。
対象は暗黙選択せず、全件は`--all`、1件は`--plugin <name>`を必ず明示する。read-only検証は
`--check`、片方だけは`--platform claude|codex`を使う。

### Codex単独のlocal / Git install

Codex は repository root の `.agents/plugins/marketplace.json` と、各
`plugins/<plugin-name>/.codex-plugin/plugin.json` を読む。marketplace 名は
`harness-dev`。残る20 pluginすべてを `<plugin-name>@harness-dev`（例:
`harness-creator@harness-dev`）としてinstallできる。

#### ローカル clone から

```bash
HARNESS_REPO_ROOT="/absolute/path/to/harness"
python3 "$HARNESS_REPO_ROOT/plugins/harness-creator/scripts/install-codex-plugin.py" \
  --source "$HARNESS_REPO_ROOT" \
  --plugin harness-creator
```

この明示コマンドがmarketplace登録、install、installed/enabled receipt確認まで行う。
作業中の差分を確認するときはsource更新後にmanifest versionを更新し、同じコマンドを
再実行して新規threadで読み直す。

#### GitHub の merge 済み ref から

```bash
HARNESS_REPO_ROOT="/absolute/path/to/harness"
python3 "$HARNESS_REPO_ROOT/plugins/harness-creator/scripts/install-codex-plugin.py" \
  --source daishiman/harness-dev \
  --ref main \
  --plugin harness-creator
```

PR が `main` へmergeされた後も同じコマンドを再実行する。既登録のGit marketplaceは
snapshotをupgradeしてからinstallする。

Codex CLIに`codex plugin add`が無い場合は、`codex plugin marketplace add ...`で
sourceだけ登録し、ChatGPT desktopのPlugins Directoryからinstallする。

hookはinstallとは別のtrust gateを持つ。`/hooks`またはPlugins画面で現在のcommand /
event / plugin rootを確認し、ユーザー自身がtrustした後に新規threadで確認する。

### pathの書き分け

marketplace JSON内の`source`は機械間で共有するため相対pathのまま保つ。ただしCLIへ
marketplaceを登録する瞬間は、Claude Codeでは`<repo>/marketplaces/local`、Codexでは
`<repo>`という異なるrootをそれぞれ絶対pathで渡す。plugin hookはsession cwdで走るため
`python3 scripts/x.py`のようなcwd相対実行は禁止し、共通hook commandは
`"${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/x.py"`を使う。Codex用hook生成時は既存の
`$CLAUDE_PLUGIN_ROOT`表記をこのdual-root形へ決定論的に正規化する。

通常Skillのshell実行はhookと異なりroot環境変数の注入を前提にしない。ホストが提示した
absolute `SKILL.md` pathからplugin manifestを持つ祖先を探索し、manifest nameを確認したrootを
各shell invocationへ渡す。これによりinstall先とcwdの双方から独立する。

### 生成した plugin も Codex 対応する

`run-codex-plugin-package` は新規作成と既存改善を同じ冪等upsertで扱う。

```bash
HARNESS_REPO_ROOT="/absolute/path/to/harness"
python3 "$HARNESS_REPO_ROOT/plugins/harness-creator/scripts/sync-plugin-platforms.py" \
  --repo-root "$HARNESS_REPO_ROOT" \
  --plugin "$HARNESS_REPO_ROOT/plugins/<plugin-name>" --apply
python3 "$HARNESS_REPO_ROOT/plugins/harness-creator/scripts/sync-plugin-platforms.py" \
  --repo-root "$HARNESS_REPO_ROOT" \
  --plugin "$HARNESS_REPO_ROOT/plugins/<plugin-name>" --check
```

新規ならmanifest/entryを追加し、既存なら同じ位置で置換する。Codex固有のinterfaceや
hook subsetは`.codex-plugin-overrides.json`へ宣言し、生成済みmanifestを入力へ戻さない。
量産後は`--all --apply` でClaude manifestを持つ全pluginを調停し、
`--all --check`がexit 0であることを出荷条件にする。削除済みpluginの
repo-local marketplace entryはこの一括調停で自動削除される。

全pluginの機能対称性は、単なるmanifest存在ではなく、Skill / Agent / Command / Hook / Script /
Prompt / Workflow / MCP / Appを利用者到達可能性で監査する。実体、package contract、
`plugin-composition.yaml`の公開面は双方向完全一致を必須とする。Claude Code固有surfaceには、
単なる同名Skillではなく、責務・引数・作用・発見経路を保つCodex代替契約を必須化する。
意図的省略には理由と代替経路を必須化する。この静的契約PASSはinstall / enable / trust /
new-session runtimeの実証とは別の状態である。

```bash
HARNESS_REPO_ROOT="/absolute/path/to/harness"
python3 "$HARNESS_REPO_ROOT/plugins/harness-creator/scripts/audit-capability-parity.py" \
  --repo-root "$HARNESS_REPO_ROOT" --all --json
```

package依存は選択pluginだけでなく推移閉包を導入する。実在する`dev-graph`と
`system-dev-planner`の相互依存は同一SCCとして共同導入し、receiptにも記録する。

## ハーネスとは / なぜ skill-creator から改名したか

本 plugin は 2026-07-02 に `skill-creator` から `harness-creator` へ改名した。理由: このプラグインが構築しているのは単体のスキルではなく、スキル・エージェント・フック・コマンド・評価・統治を束ねた**ハーネス全体**だから。

用語は次の意味論境界に従う (正本: `skills/ref-skill-glossary/references/terms.md` の「ハーネス」エントリ、規約: リポジトリ root の `CONVENTIONS.md`):

| 概念 | 表現 | 例 |
|---|---|---|
| 単体スキルを作る (部品単位) | スキル / skill | `run-skill-create`, `run-build-skill`, `run-skill-rename` |
| 総体を構築する (メタ能力) | ハーネス / harness | plugin 名 `harness-creator`, `harness-creator-kit` |

内部 skill 名 (`run-skill-*` 等) が skill 語を保つのは中途半端な改名ではなく**意図的設計**: それらの操作対象は単体 skill であり、`SKILL.md` / `skills/` / Skill tool は Claude Code プラットフォームの予約語彙でもある。既存の harness 語 (`doc/harness-coverage-spec.md` = 構築物総体の品質装具) は同系譜の概念で、本 plugin 名はその系譜に連なる。

## 改名の移行手順 (ローカル環境)

plugin 名には aliases 機構が無いため、改名前から使っている開発環境では enabledPlugins キーの切替が必要:

1. `.claude/settings.json` の `"skill-creator@skills": true` を削除 (旧キーは無害だが plugin が未ロードになり hooks が黙って発火しなくなる)
2. repo 正本 `.claude-plugin/marketplace.json` の marketplace name `skills` と一致する `"harness-creator@skills": true` を追加
3. `make native-surfaces` で C01 の同一 desired-set を apply → check

この設定は clone した worktree 内のローカル有効化であり、marketplace からの `/plugin install` ではない。

過去の評価履歴は `eval-log/skill-creator/` に凍結保存されている (遡及書換なし)。改名後の新規 run は `eval-log/harness-creator/` に記録される。

## 入口の使い分け (何を作るかで入口が変わる)

`harness-creator` は製品別の配布契約を持つ。**Claude Code では従来どおり
`distributable:false` のためpublic marketplace `skills`へは載せない**が、clone内の
local marketplace `harness-local`からuser scopeへinstallできる。**Codex では
`.agents/plugins/marketplace.json` からローカルまたは GitHub 経由で単独 install できる。**
C01 (`scripts/sync-native-surfaces.py`) は source checkout 内の repo-owned projection を
apply → check するもので、Codex marketplace install とは責務を分ける。

Native hook/settings の共通意味論は `native-surfaces.toml` が正本。plugin-delivered
hook の実体は共通してplugin root `hooks/hooks.json`に置く。Claude Codeは標準pathを
自動検出するためClaude manifestでは再宣言せず、Codex manifestだけが明示参照する。
project の`.claude/settings.json` / `.codex/hooks.json`には重複配線しない。Codex は同一
project layer で `hooks.json` と inline `[hooks]` も併用しない。Beads など既存の
project-owned hook は保存する。ローカル出荷前は
`make native-surfaces-pr-ready` で apply → check → schema検査 → diff表示まで行う
(この target は PR を作成しない)。

## Codex / Claude 共通の外部知能

PostToolUse の再現可能な失敗は、両製品とも `skills/run-build-skill/scripts/auto-record-lesson.py` から同じ `build-external-intelligence.py` へ渡される。runtime state は installed plugin 内ではなく、既定で Git common dir（非Gitは project `.harness/`）に保存されるため、plugin 更新や worktree 切替でも継続できる。

検索は薄い index の上位5件まで、詳細は必要時だけ `show` する。同一・高類似観測は統合し、曖昧な自動観測は解決待ちのまま隔離保存する。1回の観測をルールへ昇格せず、独立 evidence source・別文脈での helpful reuse・承認者と承認証跡を必須とする。状態遷移・user scope・promotion 条件・cache/quota との因果境界は [`ref-knowledge-loop/references/external-intelligence.md`](skills/ref-knowledge-loop/references/external-intelligence.md) を正本とする。

plugin 名が `harness-creator` (総体) でも、**単体スキルを作る入口とハーネス総体を組む入口は別**である。混同しやすいので下表を正本導線とする (用語規約: リポジトリ root `CONVENTIONS.md` §用語規約 第6条、定義正本: `skills/ref-skill-glossary/references/terms.md`)。

| 作りたいもの | 入口 | 産物 |
|---|---|---|
| 構想から plugin 全体の計画を作る | `/plugin-dev-plan <構想>` (plugin-dev-planner) | `index.md` + 13 phase + `component-inventory.json` |
| 単体スキルを端から端まで | `/run-skill-create` (Skill) | `skills/<name>/` 一式 = **スキル 1 個** |
| skill 以外の単一 Capability (agent/hook/command/prompt/workflow) | `/capability-build <kind> <name> --plugin=<plugin>` → `run-build-skill` に委譲 | Capability 1 個 |
| ハーネス総体 (複数 Capability の束 = plugin-composition) | `/plugin-compose <plugin-name>` / `/capability-build plugin-composition <name>` | `plugin-composition.yaml` (CapabilityBundle) |
| plugin 総体の出荷前検査 | `/run-plugin-package-check <plugin-name> --phase all` | PKG-001〜015 verdict |
| 既存 Capability / plugin のレビュー | `/capability-review <target-path> [skill|plugin|repo]` | 4 条件 verdict |
| 既存 Capability の改善 | `/skill-improve <capability-path>` | 最小パッチ + 再レビュー |

**注意**: `run-skill-create` は名前どおり**単体スキル 1 個**を作る (内部で評価・統治をオーケストレーションするが産物は単体)。「ハーネス (総体)」を組むのは `plugin-compose` / `capability-build plugin-composition <name>` であり、`run-skill-create` ではない。`plugin-compose` は既存 Capability を束ねるための `plugin-composition.yaml` を編集する入口で、個別 Capability 本体は作らない。

標準フローは **第1稿の現物 → class別最小guard(parse/open・secret・不可逆・破損) → path/試し方を提示 → 利用者が診断深度を選択 → 選択時だけsemantic評価・有界改善**。`現状で試す`はevaluator 0 / improver 0。今回のように30思考法監査が明示済みな場合は、現物提示後に現在turn限定choiceとして実行できるが、将来の毎draft自動診断へ流用しない。release / exhaustiveは明示選択なしに自動昇格しない。

**前提**（満たさないと再実行が非決定に落ちる）: cwd = clone した repo root ／ `make native-surfaces` 済（C01 apply→check が PASS）／ `harness-creator` と `plugin-dev-planner` の両方が有効化・信頼済 ／ python3。全コマンドは project-local（unprefixed）で起動する（`<plugin>:` 形式の namespaced prefix は付けない — Claude 経路では本 plugin は `distributable:false` で public marketplace 経由の呼称は存在しない）。

```text
0. 前提: cwd=repo root / make native-surfaces PASS / harness-creator + plugin-dev-planner 有効化・信頼済

1. /plugin-dev-plan <構想>
     産物: index.md + 13 phase + component-inventory.json
            + handoff-run-plugin-dev-plan.json（routes[] = builder/build_kind/build_args
              に加え task_graph_ref を常時携帯）

2. /capability-build --handoff <handoff>
     既定=draft。1回の起動で task-graph から実体生成に必要な経路だけを build:
     generation/check を依存順に dispatch し、usable-draft proof を作る。
     skill route は内部で /run-skill-create へ、build_kind=script は build-script-route.py へ
     自動 dispatch される。kind・name は routes[] から機械抽出され手写し不要。
     単一 route だけ消費する段階 build / デバッグは --route-id <Cxx> を明示する（escape hatch）。
     正本: commands/capability-build.md の「task-graph route モード」節。

2D. 現物提示と診断深度選択（Step2 が自動的に導くのは提示まで）:
     全7 Capabilityを共通gateへ渡し、build-review-launch.pyがclaimをatomic consumeして共通payloadを1件生成。
     実artifactのpath・hash・開き方を提示し、その後に診断深度を質問。
     診断選択時のみ Claude Code Task / Codex subagentへのfresh-context、read-only、1 context launchを最大1回認可。
     「現状で試す」は無編集で停止、軽微=critical/high・1周、標準=+目的影響medium・2周、
     詳細=全所見・3周、リリース=全所見改善+繰越し検証。exhaustiveは別確認。

2V. 選択対象がある場合だけelegant-bounded-improvement-executorを1 worker起動し、
     validate-improvement-result.pyで選択閉集合・diff・round上限・C1〜C4を再検証。

     ここで出力された現物と提示操作を試す。ユーザーが「リリース」を選んだときだけ次を実行:

2R. /capability-build --handoff <handoff> --stage release
     draft のreceiptを再利用し、受入テスト設計・設計レビュー・意味検証・実走・文書・出荷義務を回収。

2.5 release の envelope（外殻）を適用（envelope 生成器は未整備＝手動ステップ。省略すると Step4 の PKG-001 が manifest 不在で FAIL）:
     plan の envelope-draft/plugin.json を plugins/<plugin>/.claude-plugin/ へ貼る。
     配布する総体なら .claude-plugin/marketplace.json と .claude-plugin/bundles.json にも登録する。

3. /plugin-compose <plugin-name>
     束ねる: 実体を走査して plugin-composition.yaml を再計算。
     併せて capabilities[] を Step1 の component-inventory.json と照合し、
     計画にあって未 build の component が無いか確認する（← 「漏れなく」を測る唯一の gate）。
     照合は scripts/validate-plan-coverage.py が決定論実行する（build_target のディスク実在と
     required surface を突合し、漏れを exit 1 で fail-closed 報告。目視・AI 判断に依存しない）。

4. /run-plugin-package-check <plugin-name> --phase all
     契約適合: PKG-001〜015 を全件検査。
     --phase を省くと既定 phase0（PKG-001〜009 のみ）で 010〜015 が黙って未検査になり
     subset のまま緑に見える（false green）。出荷検査では必ず --phase all。

5. /capability-review plugins/<plugin-name> plugin    # 4 条件レビュー（analyse only）

6. /skill-improve <capability-path>                   # 必要な Capability だけ改善（最小パッチ）
   改善で Capability 集合（追加/削除/改名）が変わったら Step3〜4 を再実行する。
```

Step4 だけ入口の命名が他と異なる: command ラッパを持たない skill 直起動で `/run-plugin-package-check`（run- prefix）。残りは unprefixed command 名（Step2 の `/run-skill-create` は task-graph route モードが内部 dispatch するもので、単体スキルを単発で作るときだけ直接打つ）。

**具体例**（契約書生成プラグインを 1 本組む）:

```text
1. /plugin-dev-plan 契約書を台帳から生成し Slack 承認後に PDF 化するプラグイン
     → plugins/contract-generator/ の計画一式 + routes[]（例: skill×2 / agent×1 / hook×1）
2. /capability-build --handoff plugin-plans/contract-generator/handoff-run-plugin-dev-plan.json
     （既定draft。試用できる生成物+最小guardを先に提示）
   → 現物を確認し診断深度を選ぶ。診断と改善は選択範囲だけ実行
2R. /capability-build --handoff plugin-plans/contract-generator/handoff-run-plugin-dev-plan.json --stage release
     （draft証拠を再利用し、繰越した出荷義務だけを回収）
2.5 envelope-draft/plugin.json を plugins/contract-generator/.claude-plugin/ へ適用
3. /plugin-compose contract-generator
4. /run-plugin-package-check contract-generator --phase all
5. /capability-review plugins/contract-generator plugin
6. /skill-improve plugins/contract-generator/skills/run-contract-generate
```

## 構成

- `skills/` — 32 skill 実体。Codex 単独 install で壊れる plugin 境界外 symlink は持たない (生成: run-* / 評価: assign-* / 参照知識: ref-* / 委譲: delegate-* / 安全ラッパ: wrap-*)
- `agents/` — elegant-review系、初回draft評価、有界改善、build実行を責務別に配置（実数はディレクトリと`plugin-composition.yaml`を正本とし、READMEへ固定しない）
- `commands/` — /capability-build, /capability-review, /skill-improve, /plugin-compose, /install-bundle, /marketplace-register
- `scripts/` — feedback_contract_ssot.py (dogfooding 境界 SSOT・vendored byte 一致 lint 対象) ほか
- `hooks/` — Claude Codeの標準path自動検出とCodex manifestの明示参照から配信されるrepo-local hook。`auto-sync-on-session-start.py` は install/enable/trust 後の SessionStart で C01 を薄く呼ぶ。既存の capability 所有 hook は引き続き所有 skill の `scripts/` へ co-locate する。
- `plugin-composition.yaml` — CapabilityBundle 宣言 (リファレンス実装)

Claude 公開 marketplace では非配布 (`distribution.distributable:false`)。Codex では
本pluginを含む残存20 pluginが、ローカル clone / GitHub ref から repo marketplace +
native plugin manifest 経由で個別に install できる。

## Claude Code / Codex native surface 運用

初めての人向け説明と operator 向けの install / enable / trust / re-trust / uninstall、
dry-run、managed-only projection rollback、source/activation release rollback、CI check-only、
`pending_user_gate`、unsupported
agents/commands の再評価 trigger は
[`references/native-surface-operations.md`](references/native-surface-operations.md) を正本とする。

要点は次の4つ。

1. C01 が唯一の desired-set owner。旧 all-plugin sync と混ぜない。
2. ローカル修復は `make native-surfaces-dry-run` → clean-scope evidence →
   `make native-surfaces` (apply→check)。rollback は C01 が作った patch/created-path のみを戻す。
   CI は `make native-surfaces-check` だけ。
3. user global config / trust store は自動で書かない。製品側の lifecycle 操作は
   `pending_user_gate` として build completion から分離する。
4. current local state は Claude source present/project enabled と Codex hook trust pending を別々に記録する。
   manifest 実在から Codex install/enable/trust を推定しない。
