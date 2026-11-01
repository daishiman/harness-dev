---
id: P13
phase_number: 13
phase_name: release
category: 完了
prev_phase: 12
next_phase: 14
status: 未実施
gate_type: none
entities_covered: []
applicability:
  applicable: true
  reason: チラシ制作の再現性と導入品質のため適用
---

# P13 — release

## 目的
検証済みローカルキットを納品する。

## 背景
個人写真を含むため、可搬キット納品と実環境導入を分離する。未依頼の共有registry更新を完成のために勝手に行わない。

## 前提条件
P10の独立判定・P11の証拠・P12の操作説明がそろい、CHANGELOGの変更内容が確定する。agentの配置変更・専門役のlens化・入口の一本化・評価担当の権限縮小・本質アンカーとessence-checkの追加は利用者から見える変更なので、各変更に本質成果IDを添えてminor版(1.3.0想定)としてCHANGELOGへ書く。

## ドメイン知識
local kitの自己完結検査とcanonical HarnessHub release receiptは別契約。下のcanonical条項は将来再実行用であり、未実行のままチェックしない。

## 成果物
versionが一致するprivate zip・kit-manifest.json・digest・未実施一覧。実環境導入はdeferred。

## スコープ外
外部公開、実機印刷、来場率の効果保証、グローバル設定の変更。次段階への未完は不足として渡す。

## 完了チェックリスト
- [ ] python3 scripts/package.py --checkが成功し、--out <新規kit dir>で旧成果物を上書きせずprivate zipを作り、kit-manifest.jsonのSHAが現物に一致する。版を上げる前に、package.pyがessence-checkの通過を確かめてから新版のreferences/essence-baseline.jsonを書き出し、その後にbuild-plugin-release.pyで版を上げる(導入版ではこれが最初の基準となり初期化を終える)。
- [ ] C10/C12の納品範囲と未実施経路をverification/README.mdに記し、公開registry/利用者設定を変更しない。
- [ ] CHANGELOG を先に書き、`python3 scripts/build-plugin-release.py --only flyer-studio` で版を上げ、`python3 scripts/build-plugin-release.py --check` が drift 0 で通っている。
- [ ] 両製品の package を維持し、`python3 scripts/build-local-marketplace.py --check` と `python3 plugins/harness-creator/scripts/sync-plugin-platforms.py --repo-root . --all --check` が drift 0 で通っている。
- [ ] `claude plugin validate --strict plugins/flyer-studio` が通っている。
- [ ] `python3 plugins/harness-creator/scripts/install-local-plugins.py --plugin flyer-studio --platform both --claude-config-dir <tmp-claude> --codex-home <tmp-codex>` の receipt が指定 platform のすべてで verified=true。
- [ ] 実環境 install は `plugin_meta.install.verify.live_skip_reason` の明示理由により省略する。

### 受入例
- 満たす例: 最新版kitを新パスへ作り、両manifest、素材、検証記録、実行制約が同梱される。
- 満たさない例: private kit検査を実環境install receiptとして記録、個人素材を公開catalogへ登録する。

### 事前解決済み判断
実環境installはユーザー未依頼につきdeferred。下のcanonical release/registry/isolated工程が未実施ならprospective未チェックのままとし、今回の私有キット納品と混同しない。

## 参照情報
[index](index.md)、[要件](goal-spec.json)、[実体目録](component-inventory.json)、[実行証拠](../verification/README.md)。
