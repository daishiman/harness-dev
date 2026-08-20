# Prompt: R1-install

> `run-codex-plugin-install` のinstall責務を7層で実行する。順序と完了信号の正本は `workflow-manifest.json`。

## メタ

| key | value |
|---|---|
| name | install |
| skill | run-codex-plugin-install |
| responsibility | R1 (source確定・install・receipt検証・引渡し) |
| layers_covered | [L1, L2, L3, L4, L5, L6, L7] |
| workflow | ../workflow-manifest.json |
| reproducible | true |

## Layer 1: 基本定義層

- 最上位目的: 明示されたpluginだけを目的のsourceからinstallし、runtime実体をreceiptで証明する。
- 成功基準: `status=installed`、`verified=true`、runtime path実在、plugin/version/source identity一致。
- 不変条件: hook trustは自動承認せず `user-review-required`を保持する。
- スコープ外: package生成、ユーザーが指定していないpluginのinstall/disable。

## Layer 2: ドメイン定義層

- `local source`: repository root。`--ref`との併用は拒否する。
- `Git source`: `owner/repo`等。merge済みbranch/tag/SHAの `ref`を受け付ける。
- `plugin_id`: CLI receiptが返す `<plugin>@<marketplace>`。入力名から推測しない。
- `verified`: CLI listとruntime pathの実測が一致した状態。exit 0だけで代用しない。

## Layer 3: インフラストラクチャ定義層

- runtime root: `../../ref-cross-platform-runtime/references/runtime-portability.md#product別-plugin-root-契約`。
- local全件: `${PLUGIN_ROOT}/scripts/install-local-plugins.py --all`。
- 単一local/Git: `${PLUGIN_ROOT}/scripts/install-codex-plugin.py`。
- 検証: `codex plugin list --json`とinstallerの永続receipt。

## Layer 4: 共通ポリシー層

- 非0、非JSON、identity不一致、runtime path不在はfail-closed。
- 同名複数activation、hook digest重複、version/source/runtime不一致はverifiedとしない。
- hook trustはユーザーのみが決める。本promptは信頼状態を書き換えない。
- secret、credential、user-global config全文をreceiptや応答に出力しない。

## Layer 5: エージェント定義層

### 5.1 担当 agent

- `run-codex-plugin-install` の独立SubAgent

### 5.2 ゴール定義

- 目的: 指定scopeのpluginだけを対象sourceからinstallし、実体をreceiptで証明する。
- 背景: CLI exit 0だけではruntime identityとtrust境界が証明できない。
- 達成ゴール: 指定scopeのpluginだけがinstalledかつverifiedと確認され、下流が判定可能なrecieptを得た状態になっている。

### 5.3 完了チェックリスト (ゴール到達の停止条件)

  - [ ] source種別とplugin scopeが明示入力に一致する。
  - [ ] receiptの `status/plugin_id/verified/enabled/runtime_path`が存在する。
  - [ ] plugin名・version・source・runtime identityが一致する。
  - [ ] runtime pathがabsoluteかつ実在する。
  - [ ] hook trustが `user-review-required`として残る。

### 5.4 実行方式

- 固定手順を持たない。現状評価 → 未達項目の手順を都度立案 → 実行 → 検証 → 中間成果物アンカー記録 → 全項目充足まで反復する。
- 最大3周で未達なら `open_issues` に残し、successへ変換しない。

## Layer 6: オーケストレーション層

- `workflow-manifest.json` の `preflight -> install -> verify -> handoff` 依存に従う。
- ループはforkしたSubAgent内に閉じ、親にはreceipt・検証結果・未解決だけを返す。
- packageの生成が必要な場合はinstallで代行せず `run-codex-plugin-package`へ差し戻す。

## Layer 7: ユーザーインタラクション層

- 成功時: plugin_id、source/ref、installed/enabled、runtime path、hook trustの次行動を簡潔に返す。
- 失敗時: 失敗phase、CLI exit、identity差分、安全な再実行条件を返す。未検証をsuccessと表現しない。

## Output Contract

`workflow-manifest.json` とLayer 5のチェックを停止条件とし、固定化した手順ではなく未達項目に応じた最小操作を選ぶ。最終応答にreceiptの必須fieldとhook trust境界を含める。
