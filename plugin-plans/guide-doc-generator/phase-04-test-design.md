---
id: P04
phase_number: 4
phase_name: test-design
category: テスト
prev_phase: 3
next_phase: 5
status: 未実施
gate_type: tdd-red
entities_covered: [C01, C02, C03, C04, C05, C06, C07, C08, C09, C10, C11, C12, C13, C14, C15, C16, C17, C18, C19, C20, C21, C22, C23]
applicability:
  applicable: true
  reason: guide-doc-generator の全 component に対して適用する
---

# P04 — test-design (テスト)

## 目的

各 component の受入基準を先に失敗するテストとして書き下し、tdd-red を成立させる。特に決定論 script 群は exit code と出力の二値判定で受入を定義し、実装が要件を満たしたか機械的に判定できる状態にする。

## 背景

本 plugin の要件の大半 (外部参照ゼロ・絵文字ゼロ・アンカー整合・未使用 symbol ゼロ・日付書式・バイト一致再現性) は二値判定可能であり、テストを先に書ける。逆にテストを後回しにすると、検証器自身の正しさを検証する手段が失われる。

## 前提条件

- P03 の design-gate が PASS している
- 各 component の入出力契約と exit code 意味論が確定している

## ドメイン知識

- **tdd-red**: 実装前にテストが失敗する状態を確認して初めて、そのテストが機能していると言える
- **検証器のテスト**: 検証 script は「違反を含む入力を FAIL させる」ケースと「正常入力を PASS させる」ケースの両方を持つ。前者が無いと常時 PASS の空ゲートになる
- **golden 比較**: 図解 SVG とレンダラ出力は golden ファイル比較で再現性を測る

## 成果物

- 各 script component のテスト (正常系 / 違反系 / 境界系)
- レンダラの部品別レンダリングテスト (カタログ部品ごとに 1 件以上)
- 再現性テスト (同一構成データ 2 回生成のバイト一致)
- round-trip テスト (逆抽出 → 再レンダリング の構成データ等価)
- skill 系の受入テスト (feedback_contract の outer criteria に対応)

## スコープ外

- テストを通す実装 (P05)
- テスト実行結果の収集 (P06)

## 完了チェックリスト

- [ ] 全 component にテストが存在し、実装前に失敗している
- [ ] 各検証 script が違反系ケースを持つ
- [ ] カタログ部品ごとのレンダリングテストが存在する
- [ ] 再現性テストと round-trip テストが存在する

### 受入例 (満たす例 / 満たさない例)

- 満たす例: 各検証 script に違反系ケース (外部参照あり / 絵文字あり / 未使用 symbol あり / 日付不一致 / ゴール欠落) があり、実装前に赤で失敗する。
- 満たさない例: 正常系テストだけが存在し、検証器が何も検出しなくても緑になる。

### 事前解決済み判断

- テストは実装前に赤で固定する。検証器の受入例は違反系ケースの検出で定義し、正常系のみのテストは受入とみなさない。
- 再現性テストは同梱構成データからの再生成で定義する (起動引数を再現の一部にしない)。

## 参照情報

- 要件正本: `goal-spec.json` (checklist C1-C45)
- component 正本: `component-inventory.json`
- 参照解析: `{{PROJECT_ROOT}}/analysis/guide-doc-generator/reference-analysis.md`
- plan 全体像と用語集: `index.md`

