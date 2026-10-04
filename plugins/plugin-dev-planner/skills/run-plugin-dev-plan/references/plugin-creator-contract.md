---
name: plugin-creator-contract
description: Claude Code / Codex 両 platform 向けプラグインの scaffold / manifest / marketplace / install / update validation 物理契約を確認したいとき、plugin_meta や plugin 階層の受け入れ条件を生成する際に読む。
kind: reference
owner: team-platform
since: 2026-06-30
source-tier: internal
source: plugins/harness-creator/skills/run-skill-create/SKILL.md
---

# plugin-creator 物理契約 (Claude Code / Codex)

`run-plugin-dev-plan` は計画成果物のみを作るが、各計画は最終 build と `run-skill-create` /
`validate-plugin-completeness.py` が満たすべき **Claude Code プラグインの物理契約** を携帯する必要がある。

> 注: manifest の正本は **Claude Code** 規約 (`.claude-plugin/plugin.json`)。Codex 側の
> `.codex-plugin/plugin.json` と `.agents/plugins/marketplace.json` は手書きせず、
> `plugins/harness-creator/scripts/sync-plugin-platforms.py` が正本から投影する。計画は両 platform への
> install を既定とし、install できるかを「作った後で誰かが気付く」問題にしない (下記 install 契約)。

## 必須プラグインアーティファクト

| 契約 | 要件 |
|---|---|
| plugin root | フォルダ名は正規化した小文字ハイフン区切りの plugin 名 |
| manifest | `.claude-plugin/plugin.json` が必須 |
| manifest name | `plugin.json.name` が外側フォルダ名と完全一致 |
| placeholder 禁止 | manifest 値に `[TODO: ...]` 等の未展開プレースホルダを含めない |
| 任意の同梱物 | `skills/` `agents/` `commands/` `hooks/` `scripts/` `assets/` は実際に作る場合のみ出現 |
| 予約フィールド | `plugin.json` の予約フィールド(skills/agents/commands 等)に独自オブジェクトを格納しない(型不一致で install 拒否)。独自データは `entry_points` 等へ退避 |
| 検証 | 最終 build は `python3 scripts/validate-plugin-completeness.py` (検出モードで exit0) と `validate-plugin-packages.py` を通す |

## marketplace / 配布契約

| 契約 | 要件 |
|---|---|
| marketplace 正本 | repo ルートの `.claude-plugin/marketplace.json` (`plugins[]`)。個人/チーム共有はこの 1 経路 |
| bundles | `.claude-plugin/bundles.json` (`harness-full` 等)。cross-plugin 一括 install は `install-bundle` が担う |
| source path | marketplace エントリは `./plugins/<plugin-name>` を指す |
| 必須 policy | 各エントリは `policy.installation` / `policy.authentication` / `category` を持つ |
| 既定 policy | `installation: AVAILABLE`、`authentication: ON_INSTALL` |
| 並び順 | 明示要求が無ければ追記(append-only)。並べ替えない |
| update flow | 既存 plugin の更新は cachebuster flow を使い、marketplace 手編集をしない |
| 非配布 | `distributable:false` は marketplace/bundles 非登録で実体保持。harness-creator/prompt-creator は `NEVER_DISTRIBUTE` denylist で二重ロック |

## install 契約 (Claude Code / Codex)

plugin を作っても install されなければ使えない。harness の install 経路は 3 つあり、どれも新規 plugin を
自動では入れない: Claude の `harness-local` marketplace は `autoUpdate` で**導入済み** plugin の版しか上げず、
定期同期ジョブは main かつ clean な clone でしか全件 install を回さない。よって計画は install を build 側の
完了条件として携帯する。実装は既存スクリプトの名前参照のみで、planner で再実装しない。

| 契約 | 要件 | 実体 |
|---|---|---|
| platforms | 既定は `[claude, codex]`。claude は manifest 正本ゆえ除外不可。codex を外すときだけ `excluded_platforms.codex` に理由 | — |
| Codex manifest | `.codex-plugin/plugin.json` を正本から投影する (手書きしない・Codex 固有値は `.codex-plugin-overrides.json`) | `sync-plugin-platforms.py --plugin plugins/<slug> --apply` / `--all --check` |
| 登録先 | claude → `harness-local` (`marketplaces/local/.claude-plugin/marketplace.json`。非配布 plugin を含む全 plugin の install 経路)、codex → `codex-repo` (`.agents/plugins/marketplace.json`)。公開 marketplace は `distribution.marketplace` が担う | `build-local-marketplace.py --check` / `sync-plugin-platforms.py --all --check` |
| strict 検証 | `claude plugin validate --strict` を通す。hook command の plugin root は `python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/hooks/x.py"` とクォートする (未クォートの `${CLAUDE_PLUGIN_ROOT}` は strict で落ち、installer は最初の失敗で全件を止める) | `run-plugin-validate-strict.sh` (PKG-001) |
| release 順序 | CHANGELOG を先に書き、`build-plugin-release.py --only <slug>` で bump、`--check` が drift 0 (CHANGELOG は fingerprint に入るので後から書くと二重 bump になる) | `scripts/build-plugin-release.py` |
| 隔離 install | `install-local-plugins.py --plugin <slug> --claude-config-dir <tmp> --codex-home <tmp>` の receipt が両 platform で `verified=true`。手元の設定を汚さないので opt-out 不可 | `plugins/harness-creator/scripts/install-local-plugins.py` |
| 実環境 install | `install-local-plugins.py --plugin <slug>` で手元の Claude Code (user scope) と Codex へ入れ、receipt が `verified=true`。省くときだけ `verify.live:false` + `live_skip_reason` | 同上 |

## 計画への含意 (index.plugin_meta)

- `index.md` は `plugin_meta.manifest` と `plugin_meta.marketplace` を持つ。
- `plugin_meta.manifest.path` は常に `.claude-plugin/plugin.json`。
- `plugin_meta.manifest.validate_plugin` は `true` (= `validate-plugin-completeness.py` を通す意図)。
- `plugin_meta.marketplace.policy.installation` は `NOT_AVAILABLE` / `AVAILABLE` / `INSTALLED_BY_DEFAULT` のいずれか。
- `plugin_meta.marketplace.policy.authentication` は `ON_INSTALL` / `ON_USE` のいずれか。
- `plugin_meta.marketplace.cachebuster_for_update` は update-mode 計画で `true`。
- `distribution.distributable:false` は bundles 空かつ marketplace false/不在 (非配布整合)。
- `distribution.distributable:true` は bundle 最低 1 件または明示的な marketplace 登録判断を要する。
- `plugin_meta.install` は core。`platforms` / `codex_manifest` / `registries` / `strict_validate:true` /
  `release: changelog-then-bump` / `verify.{isolated,live}` を持ち、`check-spec-gates.py` が値域検証する
  (値域の正本は `specfm.INSTALL_*`)。

## 停止条件 (inventory component へ展開しない)

- 単一 skill 要求で plugin packaging / marketplace 境界が無い。
- 既存 plugin の更新で足り、新規 inventory component が不要。
- plugin 名 / 配置先 / 配布意図が矛盾している。
- 必須 manifest / marketplace policy がユーザー承認なしに一意決定できない。
- codex を外す理由も実環境 install を省く理由も示せないのに、片方だけの install を前提にしている。
