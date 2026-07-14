---
id: P01
phase_number: 1
phase_name: requirements
category: 要件
prev_phase: 0
next_phase: 2
status: 完了
gate_type: none
entities_covered: []
applicability:
  applicable: true
  reason: ""
---

# P01 — requirements (要件定義)

## 目的

ユーザー価値を「Claude/Codex の人工的な対称化」ではなく「有効・信頼済み capability を各製品の公式 native surface へ手作業・推測投影なしに一貫公開し、片側だけ未反映・stale になる drift を build 完了ゲートと CI で機械検出・修復する」と定義し、`goal-spec.json` の C1-C10 に固定する。

## 背景

Claude reflector は配線不足に加えて現行 target event で exit 3 になる。Codex 旧案は `.agents/{agents,commands,skills,hooks}` 全反映と推測 TOML merge を前提にしたが、2026-07-12 時点の公式仕様と repo 実測では `.agents/skills`、`.codex/{config.toml,hooks.json}`、`.codex-plugin/plugin.json`、`.agents/plugins/marketplace.json`、plugin hooks が native surface である。

## 前提条件

- 今回は plan review のみで、build/apply/install/trust/PR は実行しない。
- Codex CLI 実測 version は 0.144.0。
- 公式参照は `https://developers.openai.com/codex/concepts/customization`、`/codex/config-advanced`、`/codex/plugins/build`。

## ドメイン知識

- confirmed: skills、project hooks、plugin manifest、repo marketplace、plugin hooks。
- unsupported/deferred: Claude-style agents/commands の Codex plugin mapping。
- plugin hooks は install/enable だけでなく user trust が必要。
- target unknown event は preserve、managed source unknown event は block する。

## 成果物

- 最適化済み `goal-spec.json`。
- native surface matrix、state ownership matrix、failure taxonomy。
- 実行禁止境界と user-gated runtime boundary。

## スコープ外

- 実コード、manifest、marketplace、settings の変更。
- plugin trust の自動承認。
- public marketplace publish。

## 完了チェックリスト

- [x] purpose/background/goal が問題・確認済み事実・観測可能 outcome・非ゴールに分離されている。
- [x] checklist C1-C10 と max loop=3 が定義されている。
- [x] Codex 旧推測 surface が撤回され native-first に置換されている。
- [x] Claude reflector blocker と activation/trust boundary が明示されている。

### 受入例 (満たす例 / 満たさない例)

- 満たす例: 初見者が Claude/Codex の surface 差、今回作るもの、今回実行しないものを4項目以内で説明できる。
- 満たさない例: 「`.agents` へ全部 symlink する」「config.toml 相当」のような未確認案が要件として残る。

### 事前解決済み判断

- Codex は native plugin/marketplace/hooks を優先する。
- agents/commands は v1 unsupported/deferred とし silent projection しない。

## 参照情報

- `goal-spec.json`
- `.codex/config.toml` / `.codex/hooks.json`
- OpenAI Codex official customization/config/plugin docs (checked 2026-07-12)
