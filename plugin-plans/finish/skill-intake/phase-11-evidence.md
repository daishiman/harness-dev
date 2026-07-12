---
id: P11
phase_number: 11
phase_name: evidence
category: 検証
prev_phase: 10
next_phase: 12
status: 未実施
gate_type: evidence
entities_covered: [C01, C02, C03, C04]
applicability:
  applicable: true
  reason: ""
---

# P11 — evidence (手動 trial 検証)

## 目的
build 後、実際の会話 (live-trial) で「手順を言語化できるユーザー」「手順化困難なユーザー」「一般論で答えがちなユーザー」「自発的に改善提案を述べるユーザー」の 4 パターンを再現し、C1 (詳細抽出)・C2 (概略フォールバック)・C6 (決定論分岐)・C7 (as-is/to-be 分離)・C8 (相手固有の具体性) が機械テストだけでなく実会話でも意図通り機能する証跡を収集する手順を宣言する。

## 背景
自動テスト (P06) は入力データを直接与えるが、実際のヒアリングは自然文の会話として進む。決定論分岐 (C6) が「同一パターンなら常に同じ経路」であることは機械テストで担保できるが、会話としての自然さ・停止しないこと (C2) は live-trial による手動検証が必要である (goal-spec C2「停止せず」の実質確認)。

## 前提条件
- P10 の final-gate が PASS している。
- build 側で C01-C04 の実装が完了し `run-skill-intake` が動作する状態にある (本 plan のスコープ外・build 側の前提)。

## ドメイン知識
- 用語集は index `## ドメイン知識` を参照。差分なし。
- **live-trial**: 実際の会話フローを通した手動検証。C01 の OUT3 criterion (loop_scope=outer, verify_by=test, 「決定論フォールバック発火時に停止せず継続する」goal-spec C2) の受入証跡を実会話で収集する検証様式 (シナリオ 2/3 が対応)。

## 成果物
- **trial シナリオ 1 (詳細抽出)**: 手順を具体的に言語化できるペルソナで `run-skill-intake` の Phase4 procedure ヒアリングを実施し、`interview.json.procedure.mode=detailed` で `steps[]` が生成され validate PASS することを確認する手順。
- **trial シナリオ 2 (概略フォールバック)**: 「わからない」「特に決まった手順はない」等の抽象回答/未回答を意図的に 2 回連続入力し、ヒアリングが停止せず `overview_fallback` へ切り替わり工程数目安等の最小情報のみで完了することを確認する手順。
- **trial シナリオ 3 (決定論分岐の再現性)**: シナリオ 2 と同一の回答パターンを別セッションで再入力し、常に `overview_fallback` が選ばれることを確認する手順 (C6)。
- **trial シナリオ 4 (相手固有の具体性・平均回帰防止)**: 「普通のやり方です」「一般的な感じです」等の抽象的・一般論的な回答を意図的に入力し、ヒアリング担当が正規化・要約せず「具体的にはどのツール/頻度/関与者か」等の追加質問で固有名詞・実例を引き出すまで深掘りすることを確認する手順 (goal-spec C8)。
- **trial シナリオ 5 (as-is/to-be 混入防止)**: ユーザーが自発的に改善提案・理想手順 (例:「本当はもっと効率的な方法があると思う」) を述べた場合に、当該発言が as-is フィールドへ記録されず (別フィールドへの退避もされず)、`validate-procedure-completeness.py` の contamination check が混入なしと判定することを確認する手順 (goal-spec C7)。加えて denylist 語をユーザー自身の業務語彙として含む as-is ペルソナ (例: 「広告運用の最適化」業務で action に「入札単価を最適化する」が事実描写として現れる) を必ず 1 件含め、false-positive escape (warn 記録+detected=false の文脈規則, P05 C02 仕様) が働き忠実記録と contamination check が恒久差し戻しループに陥らないことを確認する。
- 各シナリオの実施結果 (成功/失敗、逸脱があればその内容) を証跡として記録する形式。
- **手戻り指標ベースライン**: build 後の初回 dogfooding (intake→build 1 サイクル) で builder が手順を推測/追加質問した回数を証跡へ記録し、purpose (手戻り解消) の実現度を測る手戻り指標のベースラインとする (既存 `plugins/skill-intake/scripts/measure_value_realized.py` の計測経路へ接続する)。
- **P11 後の実証レビュー sign-off**: trial シナリオ 1-5 の証跡をもとに、P10 とは別に「実会話で C1/C2/C6/C7/C8 が意図通り機能したか」を確認する軽量 sign-off を記録する。ここで FAIL した場合は該当 phase (P04/P05/P06) へ差し戻し、P13 release へ進めない。

## スコープ外
- 自動テスト (P06) で既に確認可能な項目の再実施 (evidence は自動化困難な会話的側面に限定)。
- Notion 公開・実際の Notion ページ確認 (goal-spec constraints によりスコープ外)。

## 完了チェックリスト
- [ ] trial シナリオ 1-5 それぞれの実施手順が入力例・期待結果とともに宣言されている。
- [ ] gate_type=evidence の証跡記録形式 (成功/失敗・逸脱内容) が明記されている。
- [ ] P11 後の実証レビュー sign-off が P13 release の前提条件として明記されている。

## 参照情報
- goal-spec C2/C6/C7/C8 (「停止せず」「決定論的」「as-is/to-be 分離」「相手固有の具体性」の受入観点)。
- `plugin-plans/skill-intake/component-inventory.json` (C01 の feedback_contract.criteria OUT1/IN2/OUT2)。
- 後続 P12 (evidence 結果を踏まえたドキュメント更新)。
