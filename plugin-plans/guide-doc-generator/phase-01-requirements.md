---
id: P01
phase_number: 1
phase_name: requirements
category: 要件
prev_phase: 0
next_phase: 2
status: 未実施
gate_type: none
entities_covered: []
applicability:
  applicable: true
  reason: guide-doc-generator の全 component に対して適用する
---

# P01 — requirements (要件)

## 目的

goal-spec の checklist C1-C45 を guide-doc-generator の要件正本として確定し、LLM 判断が要る領域と決定論に閉じる領域の分界線を要件レベルで言い切った状態にする。この分界が後段の機械ゲートを成立させる前提であり、ここで曖昧なまま進むと検証不能な要件が実装まで流れる。

## 背景

初心者・非エンジニア向けの資料は毎回ゼロから手書きされ、部品もデザイン言語も資産にならない。参照解析で既存 2 資料の骨格・部品カタログ・デザイントークン・文章設計の型が抽出されており、これを構成データ駆動の生成系へ移す要件が立っている。同時に「外部依存ゼロ」「絵文字ゼロ」「同一入力からの再現性」といった二値判定可能な要件が多く、要件段階でそれらを検証手段つきで固定できる。

## 前提条件

- `goal-spec.json` が確定し `artifact_class: plugin-plan` / `target_plugin_slug: guide-doc-generator` が固定されている
- 参照解析 (`analysis/guide-doc-generator/reference-analysis.md`) が既存資料の実測と設計原則を提供している
- 委譲先候補である slide-report-generator の画像生成パイプラインが repo 内に実在することを確認済み

## ドメイン知識

- **構成データ**: 資料の内容と部品選択を表現する JSON。本 plugin における単一の入力正本
- **単一 HTML**: CSS/JS/画像/フォントを全て内包し、外部 URL を一切参照しない 1 ファイル
- **分界線**: 「ヒアリング→構成データ」「読みやすさ判定」は LLM、「構成データ→HTML」「検証」「出力先解決」は決定論 script。この線を越える設計は要件違反として扱う
- 参照資料の実測値 (文字数・data URI 比率など) は現状把握であり目標値ではない。数値を目標化すると Goodhart 化するため要件へ焼かない

## 成果物

- 要件正本の確定 (`goal-spec.json` checklist C1-C45 を凍結)
- 要件と検証手段の対応表 (各 checklist 項目の `verify_by` が script / test / reasoning のいずれかであること)
- 分界線の宣言 (LLM 領域と決定論領域の境界)
- open_questions への回答方針 (既定出力先・サイズ上限・round-trip 粒度・テーマ入力・レビュアー要否・用語検出・日付意味論・補助日付表記)
- 用途種別の語彙と、用途別に何を必ず載せるかの確定 (6 用途分)
- 追加の未決事項への回答方針 (非対話経路の要否・目次上のゴール表示形式・プリセットの利用者拡張・混成用途の可否・追加語彙の具体名)

## スコープ外

- component への分解と build_target の割当 (P02 と `component-inventory.json`)
- 資料の中身そのもの (題材はユーザー固有であり plugin 資産ではない)
- 実コードの記述 (本 plan は L3 計画層で完結する)

## 完了チェックリスト

- [ ] checklist C1-C45 が全て検証手段つきで確定している
- [ ] LLM 領域と決定論領域の分界線が要件文として言い切られている
- [ ] 参照資料の実測値が目標値として要件へ混入していない
- [ ] open_questions が回答済みで、設計を拘束する決着は 13 phase 本文へ転記されている (記録の写しは `plan-design-notes.json`。`plan-findings.json` は独立評価者の出力枠として空けておく)

### 受入例 (満たす例 / 満たさない例)

- 満たす例: checklist C1-C45 のそれぞれに `verify_by` (script / test / reasoning) が付き、参照解析の実測値がどの要件文にも数値として現れていない。
- 満たさない例: 「読みやすい資料にする」のように合否を分ける観測点が無い要件が残っている、または「data URI 比率 99% 以上」のように参照資料の実測値が目標値として焼かれている。

### 事前解決済み判断

- 要件正本は goal-spec.json の checklist C1-C45 に固定し、参照解析の実測値は現状把握として扱い目標値へ転写しない。
- open_questions の決着は本 plan の 13 phase 本文へ転記する。plan-design-notes.json はその写しであり、単一ファイル消失で決着が失われない形にする。

## 参照情報

- 要件正本: `goal-spec.json` (checklist C1-C45)
- component 正本: `component-inventory.json`
- 参照解析: `{{PROJECT_ROOT}}/analysis/guide-doc-generator/reference-analysis.md`
- plan 全体像と用語集: `index.md`

