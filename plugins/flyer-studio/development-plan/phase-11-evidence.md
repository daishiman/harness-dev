---
id: P11
phase_number: 11
phase_name: evidence
category: 検証
prev_phase: 10
next_phase: 12
status: 未実施
gate_type: evidence
entities_covered: []
applicability:
  applicable: true
  reason: チラシ制作の再現性と導入品質のため適用
---

# P11 — evidence

## 目的
両ホストの導入面と実出力を確認する。

## 背景
manifestの静的整合と本物ホストsessionでの制作は別の証拠である。配布コピーで実行できる範囲を再現する。

## 前提条件
両manifest・plugin.json・scripts/package.py・INSTALL.mdと実描画証拠を読む。

## ドメイン知識
private local catalogと公開marketplace登録は異なる。隔離copy検証はglobal設定を変更しない。

## 成果物
verification/results.json・README.md・render-checks.json・smoke-delivery.json、kit-manifest.json。

## スコープ外
外部公開、実機印刷、来場率の効果保証、グローバル設定の変更。次段階への未完は不足として渡す。

## 完了チェックリスト
- [ ] python3 scripts/package.py --checkとclaude plugin validateのログを保存し、Codex manifest/catalogは構造確認と本物session実走を分けて記録する。
- [ ] キットを別場所へコピーしてnpm ci --ignore-scripts、doctor、package --checkを実行し、元の素材パス無しで成功する。
- [ ] results.jsonに実際の環境・依存version・出力SHA・試験skip/未実施経路を記録し、P06/P09の証拠へ到達できる。
- [ ] verification/README.mdの1.2.0未検証経路(新しい背景の実生成・漫画/手書き表現・両ホストの新規会話での完走・実機印刷・告知効果)を、新版で実施/未実施/対象外の3値に分けて理由付きで記録し、1.2.0のPASSを新版の証拠に転用しない。
- [ ] 4段階の実走記録が、analysis.json→analysis-review.json PASS→新しい描画と検査→visual-review.json PASS→納品の順で同一案件dirにそろい、各段階の担当名とSHAが追える。

### 受入例
- 満たす例: Claude native validate成功、Codex JSON/kit整合成功、Codex実session未実施と別項目になる。
- 満たさない例: JSON parse成功を両ホストの制作完走と書く。

### 事前解決済み判断
既存ユーザー設定やHOME/CODEX_HOMEを差し替えず検証する。認証や画像生成機能が無ければその経路を未検証に残す。

## 参照情報
[index](index.md)、[要件](goal-spec.json)、[実体目録](component-inventory.json)、[実行証拠](../verification/README.md)。
