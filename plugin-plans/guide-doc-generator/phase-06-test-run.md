---
id: P06
phase_number: 6
phase_name: test-run
category: テスト
prev_phase: 5
next_phase: 7
status: 未実施
gate_type: none
entities_covered: [C01, C02, C03, C04, C05, C06, C07, C08, C09, C10, C11, C12, C13, C14, C15, C16, C17, C18, C19, C20, C21, C22, C23]
applicability:
  applicable: true
  reason: guide-doc-generator の全 component に対して適用する
---

# P06 — test-run (テスト)

## 目的

全テストを実行し、結果を記録して green を実測で確認する。個別に通ることと一式で通ることは別なので、パイプライン全体を通した実行結果を残す。

## 背景

script 単体では通っても、構成データを跨いだ実行では契約の食い違いが顕在化することがある。実行結果を証跡として残さないと後段の evidence フェーズで再収集が必要になる。

## 前提条件

- P05 で実装が揃っている

## ドメイン知識

- **実行の再現性**: テスト実行は環境非依存であること。専用 env 未設定でも自己解決フォールバックで動くことを実行で確認する
- **exit code の意味論**: 0=合格 / 1=違反検出 / 2=実行エラー。1 と 2 を混同すると差し戻し先を誤る

## 成果物

- 全テストの実行結果 (成否と失敗内訳)
- パイプライン一気通貫の実行ログ
- 環境変数未設定時の実行結果

## スコープ外

- 失敗テストの根本原因修正 (P05 へ差し戻し)
- 受入基準の判定 (P07)

## 完了チェックリスト

- [ ] 全テストが green で実行された記録がある
- [ ] パイプライン一気通貫の実行が成功している
- [ ] 専用 env 未設定でも自己解決で動作することを確認済み

### 受入例 (満たす例 / 満たさない例)

- 満たす例: 全テストの実行記録が残り、専用 env 未設定の環境でも `__file__` 相対フォールバックで一気通貫が成功する。
- 満たさない例: 開発者環境でしか通らず、env 未設定時に実体解決へ失敗して停止する。

### 事前解決済み判断

- 専用 env 未設定の環境でも自己解決フォールバックで動くことを実行で確認する。開発者環境の env 設定を前提にしない。

## 参照情報

- 要件正本: `goal-spec.json` (checklist C1-C45)
- component 正本: `component-inventory.json`
- 参照解析: `{{PROJECT_ROOT}}/analysis/guide-doc-generator/reference-analysis.md`
- plan 全体像と用語集: `index.md`

