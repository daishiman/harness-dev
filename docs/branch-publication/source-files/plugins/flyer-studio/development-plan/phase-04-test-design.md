---
id: P04
phase_number: 4
phase_name: test-design
category: テスト
prev_phase: 3
next_phase: 5
status: 未実施
gate_type: tdd-red
entities_covered: []
applicability:
  applicable: true
  reason: チラシ制作の再現性と導入品質のため適用
---

# P04 — test-design

## 目的
壊れたら困る中央軸と未確認素材・古い目視結果のケースを定義する。

## 背景
中央軸・公開範囲・更新鮮度の破綻は最終画像だけで発見すると修正費用が大きい。境界値を先に定義する。

## 前提条件
schemas/brief.schema.json・scene.schema.json・concepts.schema.jsonとreferences/design-rules.mdを読む。

## ドメイン知識
C2の構図差は6軸の署名チェックに加え個別目視が要る。C4はA4縦105mmの軸、QRの幅は中心計算に使わない。

## 成果物
tests/contract.test.cjs・acceptance.test.cjs・fixture.cjsの正常/異常受入ケース。4段階境界と周回上限はtests/analysis.test.cjs・runtime-gates.test.cjs・feedback.test.cjs、配置と入口はtests/package-contract.test.cjsのケース。essence-checkはPython標準ライブラリのunittest(tests/test_essence_check.py)で、案件側とプラグイン側の正常/異常ケースを持つ。

## スコープ外
外部公開、実機印刷、来場率の効果保証、グローバル設定の変更。次段階への未完は不足として渡す。

## 完了チェックリスト
- [ ] tests/contract.test.cjsが中央ずれ、白黒欠落、未確認素材、U01crop逸脱、生成履歴欠落をそれぞれ失敗として検査する。
- [ ] tests/acceptance.test.cjsがreview無し/古いfingerprint/PNG改変/古いreview SHAでfinalize失敗、現行証拠のみ成功を確認する。
- [ ] analysis-review.jsonのPASS無し・analysisSha不一致・seal後の分析書換えで制作開始が失敗し、評価担当のtoolsにWrite/Edit/Bashがあれば検査が失敗する(C13)。
- [ ] 周回4回目の開始、提案再評価による周回数の初期化、同一画像SHAと同一所見の再提出を失敗とし、上限到達時はINCOMPLETEと未解決項目を返すことを確認する(C14)。
- [ ] agentsディレクトリにcomposition未登録のagentがある、またはSKILL.mdがnode scripts/cli.cjsを直接起動していると、package-contractの検査が失敗する。
- [ ] 原依頼hashの書換え、本質成果IDの無いFIX、失敗したE*基準の観測が無い本質区分のFIX、好みだけの所見による周回開始、決定論の失敗を分析へ・目的のずれを制作へ戻す誤振分を、essence-check --projectが失敗とする(C15)。
- [ ] 3 digestが全て同じ案の案単位の判定は再利用され、どれか1つ(規範digestならlens 1項目)でも変わった案と、案の集合に掛かる判定は再評価になる。決定論検査で判定済みの項目がvisual-review.jsonの必須修正に重複して現れる、呼出記録から数えたLLM担当の起動数が予算を超える、または呼出記録に無い入力束IDの判定が混ざると、essence-check --projectが失敗する(C16)。
- [ ] serves/evidenceの無いcapabilityや規則の追加、実在しないE*や同梱されていない事例を指すserves/evidence、承認記録の無いE*の追加や担当数・LLM評価予算の基準超過、基準ファイルがplugin.jsonの現在版以下で最新のリリース版と異なる状態(作業中の新版の項目だけがCHANGELOGに先に入った状態は通す)・導入版より後の基準欠落・承認記録の無い初期化、golden事例(中心軸・白黒欠落・旧SHA)の削除を、essence-check(プラグイン)が失敗とする。対象digestの一致する承認記録がある超過だけが通る(C17)。

### 受入例
- 満たす例: 105mm中心は成功、QR除外領域の中心への変更は失敗。
- 満たさない例: 件数だけ増やし、失敗理由を確認しない試験。

### 事前解決済み判断
13案全部を生成する試験と2案の機能試験を区別する。単体が通っても新規13案制作済みとは扱わない。周回上限の試験は件数の境界(3は成功・4は失敗)で固定し、時間や回数の目標値へ置き換えない。予算の試験は基準ファイルとの比較(超えたら失敗、一致する承認記録がある時だけ通る)で固定し、上限の具体値を試験へ直書きしない。

## 参照情報
[index](index.md)、[要件](goal-spec.json)、[実体目録](component-inventory.json)、[実行証拠](../verification/README.md)。
