---
id: P02
phase_number: 2
phase_name: design
category: 設計
prev_phase: 1
next_phase: 3
status: 未実施
gate_type: none
entities_covered: [C01, C02, C03, C04, C05, C06, C07, C08, C09, C10, C11, C12, C13, C14, C15, C16, C17, C18, C19, C20, C21, C22, C23]
applicability:
  applicable: true
  reason: guide-doc-generator の全 component に対して適用する
---

# P02 — design (設計)

## 目的

要件を buildable な component 23 個へ写像し、各々の責務境界・依存 DAG・build_target・品質ゲートを `component-inventory.json` に確定させる。単一 skill へ退化させず、5 種の component_kind すべてについて採否と根拠を残した状態にする。

## 背景

資料生成は一見「1 つの skill が HTML を書く」で済みそうに見えるが、それでは同一入力からの再現性も、外部参照ゼロの機械検証も成立しない。決定論 script 群を独立実体として切り出し、LLM が触る面を構成データ設計と読みやすさ判定に限定する構造が要る。加えて `.claude/` 平置き projection では `CLAUDE_PLUGIN_ROOT` を 1 値しか持てないため、実体解決方式もこの段階で設計する。

## 前提条件

- P01 で要件正本と分界線が確定している
- 参照解析の部品カタログ B01-B15 とデザイントークンが利用可能である
- slide-report-generator の画像生成 I/F (画像計画 JSON を入力とする 2 段パイプライン) を実測済みである

## ドメイン知識

- **component_kind は 5 種のみ**: skill / sub-agent / slash-command / hook / script。同一 kind の複数実体は可で、1 実体 = 1 component = 1 build_target
- **script の hoist**: 全 script は `placement_scope: plugin-root` とし plugin 直下 `scripts/` へ置く。2 つ以上の consumer から共有され、単独 install 時の dangling を避けるため
- **環境変数の排他**: `.claude/` 平置き projection の `CLAUDE_PLUGIN_ROOT` は別 plugin が保持している。本 plugin は専用 env `HB_ROOT` を一次とし `${HB_ROOT:-$CLAUDE_PLUGIN_ROOT}` で解決したうえで、manifest の name 照合による二重防御と `__file__` 相対の自己解決フォールバックを重ねる (slide-report-generator / harness-creator と同方式)
- **委譲は再実装しない**: 画像生成は既存 plugin へ subprocess 委譲し、不在時は当該ステップのみ skip する fail-soft とする
- **語彙の単一正本**: 用途種別の語彙は 1 箇所で定義し、出力先の命名とプリセット選択の双方がそれを参照する。両側に列挙を書くと語彙追加のたびに片側が取り残される
- **検証面の独立**: 導入一文と判断軸の検査 (読み手を迷わせない書き出し) と、目的・背景・ゴールの検査 (資料全体のゴールから各セクションのゴールへの連なり) は別の検証面であり、一方が他方を代替しない。検証器を分けて独立に判定する
- **日付の単一ソース**: 資料は必須の日付フィールドを 1 つだけ持つ。未指定時に生成実行日を既定として充填するのは構成データ正規化 (`validate-handout-config.py --normalize`) の 1 箇所だけで、レンダラも出力先ルーティングも自前で現在日を取得しない。本文の `yyyy/mm/dd` と出力先ディレクトリ名の `<YYYY-MM-DD>` はこの 1 値から導かれ、言語検査器は両者の一致を照合する側であってソースではない
- **非対話経路は必須**: 対話ヒアリングは既定の入口であって唯一の入口ではない。検証済み構成データを直接渡す非対話経路を必ず用意し、両経路が同じ正規化済み構成データへ合流する
- **用途語彙の具体名**: `lecture` / `agenda` / `guide` / `onboarding` / `report` / `proposal` / `study-notes` / `study-plan` の 8 語を 1 正本に置く。出力先命名とプリセット選択の双方がこの正本だけを参照する
- **混成用途は不可**: プリセットの合成は許さない。主用途を 1 つ選び、足りない要素はセクション追加で補う。合成を許すと共有の型が崩れ、用途ごとの受入判定が定義できなくなる
- **プリセットは外部宣言データ**: プリセット定義は宣言的データファイルとして plugin 外へ開き、利用者が拡張できるようにする。ただし用途語彙の正本と同一ファイルに置き、語彙とプリセットが別ファイルへ分かれて片方だけ更新される事態を防ぐ
- **テーマの入力経路**: テーマは構成データのテーマ欄を正とする。CLI の `--theme` は構成データにテーマ欄が無い場合に限り有効で、採用値は出力先へ同梱する構成データへ書き戻す。したがってバイト一致再現性の単位は「同梱構成データ 1 点」であり「構成データ + 起動引数」ではない
- **round-trip の判定粒度**: 逆抽出の等価判定は正規化後の構成データ等価で行う。バイト一致は同一構成データからの再生成にのみ課す (HTML は空白と属性順で差が出るため)
- **hook の適用範囲**: 外部参照と絵文字の混入を止める hook は、資料出力ディレクトリ配下の `*.html` 生成物だけを対象とし、それ以外の Write/Edit は判定せず exit0 で素通しする。fail-closed は適用対象内でのみ働かせる

## 成果物

- `component-inventory.json` (23 component + 責務候補の採否根拠 + plugin-level surface の採否)
- `envelope-draft/plugin.json` (manifest 草案)
- 依存 DAG の確定 (循環なし)
- 実体解決方式の確定 (専用 env + 二重防御 + 自己解決フォールバック)

## スコープ外

- 設計の妥当性判定 (P03 の design-gate)
- テスト設計 (P04)
- 実コードの記述 (L4 build 層)

## 完了チェックリスト

- [ ] buildable 実体が全て component として登録され build_target を持つ
- [ ] 5 種の component_kind すべてについて採否と根拠が記録されている
- [ ] 責務候補 (ヒアリング/スキーマ/レンダラ/埋め込み/図解/アイコン/画像委譲/品質検証/筋道検証/用途プリセット/出力ルーティング/逆抽出/読みやすさレビュー) が漏れなく採否判定されている
- [ ] 依存 DAG に循環がない
- [ ] 実体解決方式が専用 env + 二重防御 + 自己解決で宣言されている

### 受入例 (満たす例 / 満たさない例)

- 満たす例: buildable 実体 23 個が全て `component-inventory.json` に登録され build_target を持ち、5 種の component_kind すべてに採否と根拠があり、依存 DAG に循環が無い。
- 満たさない例: 決定論 script 群を 1 skill の内部関数として畳んでおり、実体として独立に検証できる単位になっていない。

### 事前解決済み判断

- 日付の単一ソース: 未指定時の既定 (生成実行日) 充填は構成データ正規化の 1 箇所だけ。表示日付と出力先ディレクトリ名はその 1 値から導く。
- 非対話経路の必須性: 対話ヒアリングは既定の入口であって唯一の入口ではない。検証済み構成データの直渡し経路を必ず用意する。
- 混成用途は不可: プリセットの合成は許さない。主用途を 1 つ選び、不足はセクション追加で補う。
- 用途語彙の具体名: lecture / agenda / guide / onboarding / report / proposal / study-notes / study-plan の 8 語を 1 正本に置く。
- テーマの入力経路: 構成データのテーマ欄が正。CLI の --theme は構成データに欄が無い場合のみ有効で、採用値は同梱構成データへ書き戻す。
- round-trip の判定粒度: 逆抽出の等価は正規化後の構成データ等価で判定し、バイト一致は同一構成データからの再生成にのみ課す。
- プリセットは宣言データファイルとして外部へ開くが、用途語彙の正本と同一ファイルに置く。
- 実体解決は HB_ROOT → ${HB_ROOT:-$CLAUDE_PLUGIN_ROOT} → manifest name 照合 → __file__ 相対の 4 段で行う。CLAUDE_PLUGIN_ROOT 単独依存にはしない。

## 参照情報

- 要件正本: `goal-spec.json` (checklist C1-C45)
- component 正本: `component-inventory.json`
- 参照解析: `{{PROJECT_ROOT}}/analysis/guide-doc-generator/reference-analysis.md`
- plan 全体像と用語集: `index.md`
- 実体解決の先例: `{{PROJECT_ROOT}}/plugins/slide-report-generator/` / `{{PROJECT_ROOT}}/plugins/harness-creator/`

