# harness-creator

Claude Code の**ハーネス** — Capability (Skill / Agent / Hook / Command / Plugin-Composition / Prompt / Workflow) と、その評価・統治機構 (rubric / verdict / lint / feedback loop) を束ねた**構築物の総体** — を構築・評価・統治するメタプラグイン。

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

`harness-creator` は plugin 化済みだが `distributable:false` の clone 専用開発基盤であり、**Claude Code でこの repo 内から使うために public marketplace の `/plugin install harness-creator@skills` は実行しない**。C01 (`scripts/sync-native-surfaces.py`) が `plugin@marketplace` 完全 identity の activation scope から単一 desired-set を導出し、`make native-surfaces` が repo-owned projection を apply → check する。Codex では repo marketplace から install/enable/trust する別経路を使う。

Native hook/settings の共通意味論は `native-surfaces.toml` が正本。Claude
`.claude/settings.json` と Codex `.codex/hooks.json` / `.codex/config.toml`
(`features.hooks=true`) を product-specific adapter が反映する。Codex は同一 layer で
`hooks.json` と inline `[hooks]` を併用せず、plugin-delivered hook を project hook に
重複配線しない。Beads など既存 project hook は保存する。ローカル出荷前は
`make native-surfaces-pr-ready` で apply → check → schema検査 → diff表示まで行う
(この target は PR を作成しない)。

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

標準フローは次の順序で**全ステップ必須**に実行する（この順序と連結が「総体を再現性高く・漏れなく組む」正本）。各ステップの産物が次ステップの入力になる。途中を省いた run は**例外運用**であり、省略理由を review に残す（その run は再現性保証の対象外として扱い、緑判定と混同しない）。

**前提**（満たさないと再実行が非決定に落ちる）: cwd = clone した repo root ／ `make native-surfaces` 済（C01 apply→check が PASS）／ `harness-creator` と `plugin-dev-planner` の両方が有効化・信頼済 ／ python3。全コマンドは project-local（unprefixed）で起動する（`<plugin>:` 形式の namespaced prefix は付けない — Claude 経路では本 plugin は `distributable:false` で public marketplace 経由の呼称は存在しない）。

```text
0. 前提: cwd=repo root / make native-surfaces PASS / harness-creator + plugin-dev-planner 有効化・信頼済

1. /plugin-dev-plan <構想>
     産物: index.md + 13 phase + component-inventory.json
            + handoff-run-plugin-dev-plan.json（routes[] = builder/build_kind/build_args
              に加え task_graph_ref を常時携帯）

2. /capability-build --handoff <handoff>
     1 回の起動で task-graph 全体を build（既定 = task-graph route モード）:
     依存グラフ全体を並列 dispatch + 2 ループ（build-execution / spec-improvement）で駆動する。
     skill route は内部で /run-skill-create へ、build_kind=script は build-script-route.py へ
     自動 dispatch される。kind・name は routes[] から機械抽出され手写し不要。
     単一 route だけ消費する段階 build / デバッグは --route-id <Cxx> を明示する（escape hatch）。
     正本: commands/capability-build.md の「task-graph route モード」節。

2.5 envelope（外殻）を適用（envelope 生成器は未整備＝手動ステップ。省略すると Step4 の PKG-001 が manifest 不在で FAIL）:
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
     （task-graph 全体を並列 build。skill route は内部で /run-skill-create へ、
       agent/hook 等は run-build-skill へ自動 dispatch）
2.5 envelope-draft/plugin.json を plugins/contract-generator/.claude-plugin/ へ適用
3. /plugin-compose contract-generator
4. /run-plugin-package-check contract-generator --phase all
5. /capability-review plugins/contract-generator plugin
6. /skill-improve plugins/contract-generator/skills/run-contract-generate
```

## 構成

- `skills/` — 30 skill 実体 + 共有 symlink 3 本 (contract-generator 系) (生成: run-* / 評価: assign-* / 参照知識: ref-* / 委譲: delegate-* / 安全ラッパ: wrap-*)
- `agents/` — elegant-review 系 5 体 + run-build-skill-subagent
- `commands/` — /capability-build, /capability-review, /skill-improve, /plugin-compose, /install-bundle
- `scripts/` — feedback_contract_ssot.py (dogfooding 境界 SSOT・vendored byte 一致 lint 対象) ほか
- `hooks/` — Codex/Claude 両 manifest から配線される repo-local hook。`auto-sync-on-session-start.py` は install/enable/trust 後の SessionStart で C01 を薄く呼ぶ。既存の capability 所有 hook は引き続き所有 skill の `scripts/` へ co-locate する。
- `plugin-composition.yaml` — CapabilityBundle 宣言 (リファレンス実装)

単独配布非対応 (`distributable: false`, NEVER_DISTRIBUTE denylist 登録済み)。repo を clone した開発環境で、Claude Code は `.claude/` projection、Codex は repo marketplace + native plugin manifest 経由で利用する。

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
