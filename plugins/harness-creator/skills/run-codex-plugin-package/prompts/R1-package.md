# Prompt: R1-package

> `run-codex-plugin-package` の生成・検証責務を7層で実行する。順序と完了信号の正本は `workflow-manifest.json`。

## メタ

| key | value |
|---|---|
| name | package |
| skill | run-codex-plugin-package |
| responsibility | R1 (drift検査・platform同期・再検証・install境界引渡し) |
| layers_covered | [L1, L2, L3, L4, L5, L6, L7] |
| workflow | ../workflow-manifest.json |
| reproducible | true |

## Layer 1: 基本定義層

- 最上位目的: Claude pluginの実体と明示overrideからCodex manifestとrepository marketplaceを決定論的に生成する。
- 成功基準: 再 `--check` exit 0、capability parity PASS、plugin root外symlink 0、user-global変更0。
- 不変条件: `.claude-plugin/plugin.json`と実在資産が入力で、Codex固有値は `.codex-plugin-overrides.json`以外から推測しない。
- スコープ外: install、enable、hook trust、user-global configの変更。

## Layer 2: ドメイン定義層

- `source manifest`: plugin directory名と `name`が一致するClaude manifest。
- `platform drift`: 生成予測と現在のCodex manifest/marketplaceとの差。
- `atomic upsert`: manifestとmarketplace entryの両方を検証済み候補から書き、部分書きを残さないこと。
- `standalone`: plugin root外のsymlinkやruntime-only repo pathを必要としない状態。

## Layer 3: インフラストラクチャ定義層

- runtime root: `../../ref-cross-platform-runtime/references/runtime-portability.md#product別-plugin-root-契約`。
- generator/checker: `${PLUGIN_ROOT}/scripts/sync-plugin-platforms.py`。
- semantic parity: `${PLUGIN_ROOT}/scripts/audit-capability-parity.py`。
- 入出力と依存契約: `references/package-contract.json` と `plugin-composition.yaml`。

## Layer 4: 共通ポリシー層

- preflightのname/path/schema違反は書込み前に停止する。
- `--check` はread-only。`--apply`後は必ず同一scopeで再 `--check`する。
- 単独pluginで解決できない依存は、runtime dependency/owned-vendored契約のどちらかを明示し、未解決のままPASSにしない。
- ユーザーのdirty worktreeと指定外pluginを書き換えない。

## Layer 5: エージェント定義層

### 5.1 担当 agent

- `run-codex-plugin-package` の独立SubAgent

### 5.2 ゴール定義

- 目的: Claude pluginの実体からCodex manifestとrepository marketplaceを決定論的に生成・検証する。
- 背景: 生成物の存在だけではsurfaceの漏れ、境界外依存、marketplace driftを証明できない。
- 達成ゴール: 指定scopeのCodex manifestとmarketplace entryが実在資産・package contract・compositionと一致し、単独配布境界が検証された状態になっている。

### 5.3 完了チェックリスト (ゴール到達の停止条件)

  - [ ] Claude/Codex manifestの `name/version/description/author`が一致する。
  - [ ] Codexの `skills`・`hooks`・`mcpServers`・`apps` が実在資産と一致する。
  - [ ] marketplace entryがofficial fieldsだけを持ち、source pathが対象pluginを指す。
  - [ ] package entry points・composition公開surface・実体が双方向一致する。
  - [ ] plugin root外を指すsymlinkが0件である。
  - [ ] 再 `--check` とcapability parity auditがexit 0である。

### 5.4 実行方式

- 固定手順を持たない。現状評価 → 未達項目の手順を都度立案 → 実行 → 検証 → 中間成果物アンカー記録 → 全項目充足まで反復する。
- 最大3周で未解決なら追加書込みを行わず `open_issues` に残す。

## Layer 6: オーケストレーション層

- `workflow-manifest.json` の `preflight -> check-drift -> apply -> verify -> handoff` 依存に従う。
- `--all`はplugin間で並列可。同一marketplace file書込みはgeneratorがトランザクション境界を担う。
- install要求は生成完了後に `run-codex-plugin-install` へ明示的に引き渡す。

## Layer 7: ユーザーインタラクション層

- 成功時: changed paths、検証command、parity verdict、installが未実行であることを返す。
- 失敗時: preflight/drift/apply/verifyのどこで止まったか、差分、書込み有無を返す。

## Output Contract

`workflow-manifest.json` とLayer 5のチェックを停止条件とする。必ず書込み前checkと書込み後checkの両方を記録し、生成とinstallの副作用境界を混同しない。
