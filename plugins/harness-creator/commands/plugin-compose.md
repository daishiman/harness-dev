---
description: plugin-composition.yaml を編集または新規生成する。capabilities[] / dependencies を対話的に組み立て、ref-skill-design-rubric の構成評価に通る最小構成を出力する。
argument-hint: "<plugin-name>  例: harness-creator / skill-intake / prompt-creator"
allowed-tools: Read, Write, Edit, Bash
name: plugin-compose
kind: command
version: 0.1.0
owner: team-platform
since: 2026-05-24
---

# /plugin-compose

`$ARGUMENTS` の `<plugin-name>` 配下の `plugin-composition.yaml` を読み、capabilities と dependencies を編集または新規生成する。

## 振る舞い

1. `plugins/$ARGUMENTS/plugin-composition.yaml` の存在を確認。無ければ template から雛形を生成。
2. 配下の `skills/ agents/ hooks/ commands/ prompts/ workflows/` (存在するもの) を走査し、現状 capabilities[] を実体から再計算。skill 配下に内包される `prompts/` や `workflow-manifest.json` は親 skill の内部資産として扱い、top-level Capability には昇格しない。
2'. **計画に対する完全性照合 (決定論 gate)**: 直近の `component-inventory.json` (`/plugin-dev-plan` の産物) が参照可能なら、`scripts/validate-plan-coverage.py` で計画 `components[]` の各 `build_target` と build 実体を照合する (目視・AI 判断でなく機械照合):

    ```bash
    python3 "${CLAUDE_PLUGIN_ROOT:-plugins/harness-creator}/scripts/validate-plan-coverage.py" \
      <path>/component-inventory.json --repo-root .
    ```

    各 component のディスク実在 (skill は SKILL.md も) と required plugin-level surface (manifest/composition/EVALS 等 `path` を持つもの) を突合し、**計画にあって未 build の component / 未生成の surface を exit 1 (fail-closed) で報告**する。Step2 の実体からの capabilities[] 再計算は「実体に対する整合」しか測れず「計画に対する漏れ」を静かに落とすため、この照合だけが総体の completeness gate になる。inventory パスは `plugin-plans/<plugin-name>/component-inventory.json` を既定探索先とする。inventory が本当に存在しない (未計画 plugin) 場合のみ照合 skip を明示する — ただし **skip は「計画があるのに照合しない」fail-open を意味しない**。計画が commit 済みで plugin が実体化していれば、`validate-plan-coverage.py --all` が CI (`governance-check.yml`) で全 `plugin-plans/*/` を fail-closed に sweep し、build 済み plugin の計画漏れを機械強制する (実体化前の計画は自動 skip)。`path` を持たない surface (Notion config 等) は本 gate の対象外で、宣言妥当性は plugin-dev-planner 側の `check-surface-inventory.py` が担う。
3. yaml の `capabilities[]` と差分を提示し、追加/削除/更新を確定。
4. `dependencies` (他 plugin への参照) は `.claude-plugin/bundles.json` と整合を取る。ただし bundle 登録そのものは行わず、必要な manual 登録箇所を差分として報告する。
5. `dependencies` の DAG を topological sort で確認し、循環があれば保存前に停止する。
6. 保存後に yaml lint と `ref-skill-design-rubric` の最小チェック、次に走らせる `/run-plugin-package-check <plugin-name>` と `/capability-review plugins/<plugin-name> plugin` を案内する。

## 引数

| 引数 | 説明 |
|---|---|
| `plugin-name` | 対象 plugin ディレクトリ名 (必須) |

## 失敗時

- plugin 不在: `plugins/` 配下の一覧を表示
- yaml parse error: 行番号付きで該当箇所を提示し停止
- capabilities 実体不一致: 実体側の rename/move が必要なケースを案内

## 注意

- 本 command は yaml 編集のみ。capability の新規作成は `/capability-build` を併用する。
- bundles.json への登録は別途 manual で行う (依存解決は install-bundle が担う)。
