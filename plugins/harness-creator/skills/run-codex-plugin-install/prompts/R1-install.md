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

- 最上位目的: 明示されたpluginとその`dependency_closure` (previewで承認した対象plugin集合) だけを目的のsourceからinstallし、runtime実体をreceiptで証明する。
- 成功基準: `status=installed`、`verified=true`、runtime path実在、plugin/version/source identity一致。
- 不変条件: hook trustは自動承認せず `user-review-required`を保持する。
- スコープ外: package生成、previewで承認した対象plugin集合 (指定pluginと`dependency_closure`) の外のpluginのinstall/disable。

## Layer 2: ドメイン定義層

- `local source`: repository root。`--ref`との併用は拒否する。
- `Git source`: `owner/repo`等。merge済みbranch/tag/SHAの `ref`を受け付ける。
- `対象plugin集合`: 指定pluginと、各pluginの `references/package-contract.json` の `depends_on` を同じmarketplace/sourceの中でたどった `dependency_closure`。previewとguardの `<TARGET_SCOPE>` に全名を出し、実行の後にreceiptの `install_order` と照合する。
- `plugin_id`: CLI receiptが返す `<plugin>@<marketplace>`。入力名から推測しない。
- `verified`: CLI listとruntime pathの実測が一致した状態。exit 0だけで代用しない。

## Layer 3: インフラストラクチャ定義層

- runtime root: `../../ref-cross-platform-runtime/references/runtime-portability.md#product別-plugin-root-契約`。
- local全件: `${PLUGIN_ROOT}/scripts/install-local-plugins.py --all --repo-root <source>` (1件なら`--all`の代わりに`--plugin <name>`、片方だけなら`--platform claude|codex`)。`--repo-root`を省くとinstall cache内の既定rootを読みexit 3になる。
- 単一local/Git: `${PLUGIN_ROOT}/scripts/install-codex-plugin.py`。`--check`は無い。承認した対象plugin集合を名前ごとの`--approved-plugin`で渡し、helperが`plugin add`の前に照合する。Git sourceはrefをcommit SHAに固定し、marketplace登録だけの1段めとhelperの2段めにguardを分ける。helperはsnapshotの実際のcommitが固定したSHAと違うか、gitが答えられたcheckoutに未commitの変更があれば、`plugin add`を1件も出さずに止まる。gitが答えられないとき (`revision_evidence.git_dirty=null`) は止まらないので、Layer 5.3で見る。
- 検証: local全件はinstallと同じ選択引数に`--repo-root <source> --check`を付けてrepository外cwdで実行する。単一local/Gitは`codex plugin list --json`とinstallerの永続receiptを照合する。
- routeごとのstatus・exit code・receipt field: `../references/install-routes.md`。

## Layer 4: 共通ポリシー層

- 非0、非JSON、identity不一致、runtime path不在はfail-closed。
- 同名複数activation (各pluginの`activation_collisions`に`enabled=true`の候補が2つ以上)、hook digest重複、version/source/runtime不一致はverifiedとしない。helperはhook digestが同じときしか`verified`を落とさないので、同名複数activationはhelperが`verified=true`を返していても止める。
- hook trustはユーザーのみが決める。本promptは信頼状態を書き換えない。
- secret、credential、user-global config全文をreceiptや応答に出力しない。

## Layer 5: エージェント定義層

### 5.1 担当 agent

- `run-codex-plugin-install` の独立SubAgent

### 5.2 ゴール定義

- 目的: 指定pluginとその`dependency_closure`だけを対象sourceからinstallし、実体をreceiptで証明する。
- 背景: CLI exit 0だけではruntime identityとtrust境界が証明できない。
- 達成ゴール: 指定pluginとその`dependency_closure`だけがinstalledかつverifiedと確認され、下流が判定可能なrecieptを得た状態になっている。

### 5.3 完了チェックリスト (ゴール到達の停止条件)

  - [ ] source種別・plugin scopeが明示入力に一致し、Git sourceはreceiptの `resolved_revision` (snapshotの実際のcommit。引数を写した`ref`ではない) が固定したcommit SHAと同じで、receiptの `install_order` がpreviewで承認した対象plugin集合と同じである。
  - [ ] receiptの `status/plugin_id/verified/enabled/runtime_path`が存在する。
  - [ ] `status=installed` かつ `verified=true` をCLI listのinstalled/enabled実測が支持する。
  - [ ] 同名多重activationが無い: receiptの各plugin (単一local/Gitは`artifacts[]`、local全件は`plugins[]`) の`activation_collisions`に、`enabled=true`の候補が2つ以上無い。
  - [ ] Git sourceは`revision_evidence.rechecked_after_plugin_add=true`で、`revision_evidence.git_head`があれば`git_dirty=false`である (`git_dirty=null`は成功にしない)。
  - [ ] plugin名・version・source・runtime identityが一致する。
  - [ ] runtime pathがabsoluteかつ実在し、選択routeの検証が通る。local全件はinstallと同じ選択引数に`--repo-root <source> --check`を付けてrepository外cwdで実行しexit 0・`status=verified`、単一local/Gitは`codex plugin list --json`が対象pluginのinstalled/enabledを示す。
  - [ ] hook trustが `user-review-required`として残り、自動承認されていない。

### 5.4 実行方式

- 固定手順を持たない。現状評価 → 未達項目の手順を都度立案 → 実行 → 検証 → 中間成果物アンカー記録 → 全項目充足まで反復する。
- 最大3周で未達なら `open_issues` に残し、successへ変換しない。

## Layer 6: オーケストレーション層

- `workflow-manifest.json` の `preflight -> register-marketplace -> install -> verify -> handoff` 依存に従う。`register-marketplace` はGit sourceの1段めのguardだけで、local sourceは非該当として通る。preflightはuser-global状態を変えない。
- ループはforkしたSubAgent内に閉じ、親にはreceipt・検証結果・未解決だけを返す。
- packageの生成が必要な場合はinstallで代行せず `run-codex-plugin-package`へ差し戻す。

## Layer 7: ユーザーインタラクション層

- 成功時: plugin_id、source/ref、installed/enabled、runtime path、hook trustの次行動を簡潔に返す。Git sourceで`revision_evidence.git_head`が`null`なら、commitはinstall metadataだけで確かめ、未commitの変更は確かめていないことを添える。
- 失敗時: 失敗phase (receiptの`phase`)、CLI exit、identity差分、入ったまま残るplugin (receiptの`added_plugins`)、入ったか分からないplugin (`failed_plugin`。`codex plugin list --json`で確かめる)、同名多重activationの候補、安全な再実行条件を返す。未検証をsuccessと表現しない。

## Output Contract

`workflow-manifest.json` とLayer 5のチェックを停止条件とし、固定化した手順ではなく未達項目に応じた最小操作を選ぶ。最終応答にreceiptの必須fieldとhook trust境界を含める。
