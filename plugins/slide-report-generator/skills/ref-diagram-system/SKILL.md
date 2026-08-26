---
name: ref-diagram-system
description: 図解1枚で何をどの順に決めるか引きたいとき、図種選定・コネクタ入射・日本語ラベル・素材レイヤ検査の根拠を参照したいときに使う。
kind: ref
prefix: ref
version: 0.1.1
user-invocable: false
disable-model-invocation: false
effect: none
owner: harness maintainers
since: 2026-08-09
source: plugins/slide-report-generator/vendor/scripts/
source-tier: internal
last-audited: 2026-08-17
output_language: ja
allowed-tools:
  - Read
  - Grep
responsibility_refs:
  - references/resource-map.yaml
schema_refs:
  - ../../schemas/visual-derivation-table.json
completeness_exempt:
  - "prompts: 本スキルは正本への到達経路だけを持つ索引で、自身は判断を実行しない。責務プロンプトを置くと『索引が正本を語る』二重管理になり lint-ssot-duplication.py の検出対象になるため持たない。"
  - "manifest: 参照専用の索引で phase 遷移や副作用を持たず、resource-map.yaml が読込分岐の正本のため workflow manifest は作らない。"
---

# ref-diagram-system

> **役割**: 図解 1 枚を描くときの**手続き知識の索引**。値・閾値・列挙の正本は一切持たない。
> **パスの読み方**: 裸の `references/...` は**本スキル私有**（`skills/ref-diagram-system/references/`、
> 全 4 ファイル）を指す。`（plugin root）` 注記のあるものと `vendor/` `schemas/` `scripts/` `assets/`
> `tests/` は `${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}` 起点。

## Purpose & Output Contract

- **入力**: 「いま図解のどこで詰まっているか」（型が決まらない / 線が引けない / 文字が入らない / 検査に落ちた）。
- **出力**: 読むべき正本ファイルと、その正本を読む前に知っておく不変条件。
- **完了条件**: 参照のみ。図種の決定・SVG の生成・検査の実行は本スキルの責務ではなく、
  `run-slide-report-generate` の agent 群（`visual-strategist` ほか）と
  `vendor/scripts/render-report.js` / `render-slide.cjs`、および `scripts/validate-svg-diagram.py` が担う。

境界: 本スキルは**索引であって正本ではない**。値がここと正本で食い違ったら常に正本が勝つ。
値をここへ写すと `scripts/lint-contract-drift.py` と
`plugins/harness-creator/skills/run-build-skill/scripts/lint-ssot-duplication.py` が
二重管理として検出する対象になるため、本スキルの本文には数値・色・型の全列挙を置かない。

---

## 1. 1 枚描くときの不変条件

順序も含めてこの 8 条が先に立つ。どれかを崩す設計は、崩した箇所で必ず読者が図を誤読する。

1. **語彙は 3 つの表から取る。** 線幅は `kit.STROKE`、色は `kit.TOKENS` / `kit.SERIES`、
   配置は `kit.LAYOUTS`（いずれも `vendor/scripts/svg-kit.cjs`）。
   数値・色をその場で決めた図は、他の図と並べた瞬間に「別の人が描いた図」になる。
   → 根拠: `references/diagram-layout-contract.md` §1

2. **図種は決定表を上から引く。** 正本は `schemas/visual-derivation-table.json` の `rows[]`
   （`order` 昇順・first-match-wins）で、これを実行するのが
   `vendor/scripts/render-report.js` の `deriveVisualFromBody` / `evalSvgRow`。
   LLM が介入してよい口は `section.visual.kind` の明示指定 1 箇所だけで、
   そのとき `visual.rationale` に**上書きした行 ID** を書くことが表の `override.requires` で必須。

3. **容量を超える素材は載せない。** 上限の正本は `vendor/scripts/svg-builder.cjs` の `CAPACITY`
   （複数の配列引数を取る型は `CAPACITY_ARGS`、入れ子を持つ構造図は
   `vendor/scripts/svg-structures.cjs` の `NESTED_CAPACITY`）。
   上流の導出は `fitsCapacity` で超過行を**不成立**にし、決定論ビルダー側は `guard()` が
   隠れた件数を「ほか N 件」として図の隅に明記する。詰めて載せる経路は存在しない。

4. **ラベルは切り詰めない。** 判定は `render-report.js` の `conciseLabel()`（第 1 文だけを候補にし、
   逆接・留保を含むもの、および上限字数を超えるものは不採用）。
   1 件でも不採用なら `labelsOf()` が `null` を返し、その行の導出ごと中止する。
   日本語は述部が末尾に来るので、途中で切ると否定・条件・留保が落ちて図が本文と逆の主張になる。
   → 詳細: [`references/label-japanese.md`](references/label-japanese.md)

5. **コネクタは宛先辺の外向き法線と逆向きに入射させない。** 許容は
   「左辺へ右向き」「右辺へ左向き」「上辺へ下向き」「下辺へ上向き」の 4 通りのみで、
   正本は `svg-kit.cjs` の `INCIDENCE_RULE`。`safeElbow()` は満たせない配置で
   `incidence: 'degraded'` を申告するので、呼出し側は**その線を引かない**判断ができる。
   → 詳細: [`references/connector-incidence.md`](references/connector-incidence.md)

6. **viewBox は標準寸法から選ぶ。** 幅と高さ 3 段の正本は `svg-builder.cjs` の `CANVAS`
   （`CANVAS.height(needed)` が必要高から段を決定論的に選ぶ）。
   `svg-structures.cjs` も `base.CANVAS` を通じて同じ表を使う。
   図ごとに viewBox 幅が違うと実効縮小率が図ごとに変わり、線幅の階層（第 1 条）が意味を失う。
   **既知の例外**: `render-report.js` の `buildNeutralComparison` だけは `CANVAS` を経由せず
   自前の幅・高さで描く（`svg-builder.buildVs` が Before/After の善悪を固定描画するうえ
   Before/Afterの意味を固定するため、report側の中立比較は別rendererを使う）。

7. **焦点は 1 図あたり 1-2 件。** `kit.resolvePalette()` は明示 focal を先頭 2 件だけ採り、
   成果物側では `scripts/validate-svg-diagram.py` の D7 が強調色の面塗り件数を見る。
   3 件以上あると視線の着地点が定まらず、「どこから読むか」が読者任せになる。

8. **未登録は「無制限」ではなく「不採用 / 失格」。** 登録面は 3 つある。
   (a) **容量** — `fitsCapacity` は上限がどこにも宣言されていなければ不採用にする。
   (b) **重大度** — `validate-svg-diagram.py` の `_sev()` は `SEVERITY` 未登録の検査コードを
   error として扱う。
   (c) **テンプレート** — `slideType` に対応する `.html.tpl` が無い面。
   登録漏れが静かに通る設計にすると、契約は書いた日から緩み続ける。

   (c) は `vendor/scripts/render-slide.cjs` の `loadTemplate()` がfail-closedで担う。
   `slideType`とaliasのどちらにもtemplateが無ければexit 3で停止し、`slide-message`へ
   暗黙fallbackしない。`tests/test_render_slide_fail_closed.py` がこの契約を固定する。

---

## 2. どこで詰まったかで読む先を分ける

| いま詰まっているところ | 読む | そこにあるもの |
|---|---|---|
| どの型で描くか決まらない | [`references/diagram-type-catalog.md`](references/diagram-type-catalog.md) | 実在ビルダー全件の「選ぶ条件 / 選ばない条件」と決定表の行 ID |
| 型は分かったが決定論 / tpl / 手書きのどれで作るか決まらない | `references/diagram-type-crosswalk.md`（plugin root） | 4 名前空間（ビルダー <!-- count: svgBuilder -->38 / CSS 型 <!-- count: cssDiagramType -->44 / tpl <!-- count: slideTemplate -->128 / 参考型 27）の対応表と経路選択の判断順序 |
| 色をどのロール名で引くか分からない | `references/diagram-style-tokens.md`（plugin root） | セマンティックロール表・系列色の使用制限・ノード種別→塗り/枠/破線 |
| 決定論ビルダーが無い型を手書きする | `assets/diagram-templates/README.md`（plugin root） | 埋め込み用の骨格 HTML と、単体ページ用テンプレートを持ち込んではいけない理由 |
| 線がノードに埋もれる・分岐が束に見えない | [`references/connector-incidence.md`](references/connector-incidence.md) | 入射規則・トランク分岐・段を跨ぐ昇格弧 |
| ラベルが入らない・変な位置で折り返す | [`references/label-japanese.md`](references/label-japanese.md) | 幅を伸ばす / 縮める / 載せない の 3 つの吸収先 |
| D10-D13（色・複雑度・外部参照・書体）で落ちた | [`references/material-lint.md`](references/material-lint.md) | 素材レイヤ検査の設計意図と、検査値を検査器へ書かない理由 |
| D0-D9（幾何・可読性）で落ちた | `references/diagram-layout-contract.md`（plugin root） | 契約の全文と D1 の意図的な検出漏れ |
| 図種選定そのものの正本を確認したい | `schemas/visual-derivation-table.json` | R01-R14 の predicate / result / override |
| 描画プリミティブの使い方を知りたい | `references/svg-diagram-primitives.md`（plugin root） | 描き方のカタログ |
| 収まり計算の手順を知りたい | `references/spec-registry.md` §5-a（plugin root） | 折返し・寸法計算 |
| SVG 図解 / Mermaid / 生成画像 のどれにするか | `references/report-visual-strategy.md`（plugin root） | 三択の意思決定と本質図解の原則 |

共有 reference 層全体の読込条件は plugin root の `references/resource-map.md` が持つ。
本スキルの 4 ファイルの読込条件は
[`references/resource-map.yaml`](references/resource-map.yaml) に機械可読で置いてある。

## 3. 本スキルが持たないもの

- **色・書体・パレットの値** — `svg-kit.cjs` の `TOKENS` / `SERIES` と `textBlock` の既定スタックが正本。
- **容量・複雑度の数値** — `svg-builder.cjs` の `CAPACITY` / `CAPACITY_ARGS`、
  `svg-structures.cjs` の `NESTED_CAPACITY`、`validate-svg-diagram.py` の `COMPLEXITY_FACTOR` が正本。
- **検査 ID の重大度表** — `validate-svg-diagram.py` の `SEVERITY` が正本。
- **図種選定の条件式** — `schemas/visual-derivation-table.json` が正本。

本スキルはそれらへ**どういう問いで到達するか**だけを持つ。

## Gotchas

- **`references/` は 2 箇所ある**。裸の `references/...` は本スキル私有（4 ファイル）、
  `（plugin root）` 注記付きは `${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/references/`（56 ファイル）。
  前者を plugin root 側で探すと 1 件も見つからない。
- **`resource-map` も 2 つある**。plugin root の `resource-map.md` は共有 reference 層全体の索引、
  本スキル私有の `resource-map.yaml` は本スキル 4 ファイルの読込条件。stem が同じで拡張子だけ違う。
- **§2 の routing 表は D0-D13 しか受けていない**。実在する検査コードは `validate-svg-diagram.py` の
  `ALL_CODES` が示すとおり D0-D23。特に「線が読めない」で落ちたときは D19-D21（線がノードを貫く／
  重なる）が原因のことがあり、`connector-incidence.md` の入射規則だけでは解けない。
  CSS 図解経路（`cssDiagramType`）では強調色の件数は D7 ではなく D16 が見る。
- **`CANVAS` を経由しない描画が 1 つだけある**。`render-report.js` の `buildNeutralComparison` は
  自前の幅・高さで描く（不変条件 6 の既知の例外）。viewBox が揃わないのはバグではない。
- **値をここへ写さない**。`lint-contract-drift.py` と `lint-ssot-duplication.py` が二重管理として
  検出する。数を書くときは `<!-- count: <key> -->` を付ける（`lint-count-parity.py` の追随対象になる）。
