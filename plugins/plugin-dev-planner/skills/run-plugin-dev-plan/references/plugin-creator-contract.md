---
name: plugin-creator-contract
description: Claude Code プラグインの scaffold / manifest / marketplace / update validation 物理契約を確認したいとき、plugin_meta や plugin 階層の受け入れ条件を生成する際に読む。
kind: reference
owner: team-platform
since: 2026-06-30
source-tier: internal
source: plugins/harness-creator/skills/run-skill-create/SKILL.md
---

# plugin-creator 物理契約 (Claude Code)

`run-plugin-dev-plan` は計画成果物のみを作るが、各計画は最終 build と `run-skill-create` /
`validate-plugin-completeness.py` が満たすべき **Claude Code プラグインの物理契約** を携帯する必要がある。

> 注: 本リポ (harness) は **Claude Code** プラグイン規約 (`.claude-plugin/`)。他 AI ツール
> (Codex 等) の別マニフェスト/別 marketplace ディレクトリ規約は本スキルの対象外
> (対象プラットフォームはチーム決定で `.claude-plugin` に確定)。

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

## 計画への含意 (index.plugin_meta)

- `index.md` は `plugin_meta.manifest` と `plugin_meta.marketplace` を持つ。
- `plugin_meta.manifest.path` は常に `.claude-plugin/plugin.json`。
- `plugin_meta.manifest.validate_plugin` は `true` (= `validate-plugin-completeness.py` を通す意図)。
- `plugin_meta.marketplace.policy.installation` は `NOT_AVAILABLE` / `AVAILABLE` / `INSTALLED_BY_DEFAULT` のいずれか。
- `plugin_meta.marketplace.policy.authentication` は `ON_INSTALL` / `ON_USE` のいずれか。
- `plugin_meta.marketplace.cachebuster_for_update` は update-mode 計画で `true`。
- `distribution.distributable:false` は bundles 空かつ marketplace false/不在 (非配布整合)。
- `distribution.distributable:true` は bundle 最低 1 件または明示的な marketplace 登録判断を要する。

## 停止条件 (inventory component へ展開しない)

- 単一 skill 要求で plugin packaging / marketplace 境界が無い。
- 既存 plugin の更新で足り、新規 inventory component が不要。
- plugin 名 / 配置先 / 配布意図が矛盾している。
- 必須 manifest / marketplace policy がユーザー承認なしに一意決定できない。
