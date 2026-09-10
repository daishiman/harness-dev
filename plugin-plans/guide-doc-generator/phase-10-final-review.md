---
id: P10
phase_number: 10
phase_name: final-review
category: レビュー
prev_phase: 9
next_phase: 11
status: 未実施
gate_type: final-gate
entities_covered: [C01, C02, C03, C04, C05, C06, C07, C08, C09, C10, C11, C12, C13, C14, C15, C16, C17, C18, C19, C20, C21, C22, C23]
applicability:
  applicable: true
  reason: guide-doc-generator の全 component に対して適用する
---

# P10 — final-review (レビュー)

## 目的

plugin 全体を通した最終レビューを行い final-gate を成立させる。個々の component が合格していても、組み上がった plugin として目的を果たすかは別に判定する。

## 背景

component 単位の合格の総和は plugin の合格ではない。install した状態で command から skill が呼べるか、hook が意図した場面で発火するか、といった結合面は最後にしか確認できない。

## 前提条件

- P09 の qa gate が PASS している

## ドメイン知識

- **final-gate**: plugin 全体に対する最終二値判定。FAIL 時は該当フェーズへ差し戻す
- **結合面**: manifest の宣言と実体の一致、command から skill への到達、hook の発火条件、委譲先不在時の縮退動作
- **単独 install**: 本 repo 外へ install しても script が dangling しないこと

## 成果物

- 最終レビューの判定記録
- 結合面の確認結果
- 未解決事項の `plan-design-notes.json` への転記

## スコープ外

- 証跡の収集と保全 (P11)
- 利用者向け文書 (P12)

## 完了チェックリスト

- [ ] manifest の宣言と実体が一致している
- [ ] command から skill へ到達できる
- [ ] hook が意図した場面で発火し、意図しない場面で発火しない
- [ ] 委譲先不在時に縮退動作で完走する
- [ ] final-gate が PASS である

### 受入例 (満たす例 / 満たさない例)

- 満たす例: manifest の宣言と実体が 1:1 で一致し、hook が資料出力ディレクトリ配下の `*.html` でだけ発火し、無関係な Markdown 書込では発火しないことを確認できている。
- 満たさない例: hook が全 Write/Edit を検査対象にしており、handout と無関係な文書の外部 URL で書込を止めている。

### 事前解決済み判断

- hook の発火は「意図した場面で発火する」と「意図しない場面で発火しない」の両方を確認する。片側だけでは適用範囲の逸脱を検出できない。
- 委譲先不在時は失敗ではなく縮退動作 (skip) で完走することを最終確認の対象にする。

## 参照情報

- 要件正本: `goal-spec.json` (checklist C1-C45)
- component 正本: `component-inventory.json`
- 参照解析: `{{PROJECT_ROOT}}/analysis/guide-doc-generator/reference-analysis.md`
- plan 全体像と用語集: `index.md`

