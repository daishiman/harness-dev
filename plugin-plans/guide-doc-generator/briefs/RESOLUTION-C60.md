# RESOLUTION-C60 — 単一ファイル自己完結の判定を許可列挙へ反転する (SC-10)

leaf: `P04-x-02` / 対象正本: `briefs/script-brief-C16.json` / 日付: 2026-08-17

## 要件

利用者要件 (2026-08-17):

> 基本的にこのプラグインで生成される成果物に関しては、JavaScript や CSS で画像ファイル等を全て一つの HTML ファイルに入れておいてください。画像に関しては、ファイルのリンク先を記述するのではなく、しっかりとこの HTML 内に画像をはめ込むというような形で進めておいてください。そしたらこの HTML をデプロイするだけで、今回のドキュメントを整えることができるからです。

goal-spec へ **C60** として登録済み (checklist 60 件目 / `verify_by: script`)。R01 の拡張。

## 欠陥の性質 — 個別規則の漏れではなく判定方式の選択

既存の SC-01 / SC-03 / SC-04 はいずれも **検査対象を列挙する (denylist)** 形で書かれていた。

| 規則 | 列挙していたもの |
| --- | --- |
| SC-01 | 外部スキーム (`http://` `https://` `//` `ftp://` `ws://` `wss://`) を持つ URL 属性 |
| SC-03 | `img@src` / `source@srcset` / `video@poster` / `object@data` / `embed@src` / `a@href` |
| SC-04 | `<link rel>` の取得系 6 種、`@import`、`@font-face` の `src: url()` |

列挙は列挙から漏れたものを黙って通す。実測された漏れは 2 つ。

1. **`<script src="./app.js">`** — `script@src` は SC-03 の属性列挙に無い。相対パスなのでスキームを持たず SC-01 にも掛からない。
2. **`<iframe src>` / `<frame>` / `<portal>`** — どの規則の検査対象でもない。

結果、「外部参照ゼロ」を全 PASS しながら、その 1 ファイルを配置しただけでは成立しない生成物が「合格」になる。R01 の文言自体が列挙 (「外部 CDN・外部フォント・外部 img src」) だったため、設計がその列挙をそのまま属性列挙として実装したことが根本原因である。

## 解決 — SC-10 (同梱閉包の包括規則)

判定軸を **「外部スキームか否か」から「`data:` であるか否か」へ反転**させる。取得を発生させ得る参照は、値がどう書かれていようと `data:` でなければ違反。スキームを持たない相対パス・絶対パスも違反。

これにより将来 HTML に新しい取得属性が追加されても、既定で違反側へ倒れる (fail-closed)。SC-01 / SC-03 / SC-04 は SC-10 の部分集合に対する **詳細診断** として残し、列挙漏れは SC-10 が受け止める。

### 適用対象

| 記号 | 対象 | 判定 |
| --- | --- | --- |
| (a) | `<script>` の `src` | 値によらず違反。インライン本文のみの `<script>` は pass |
| (b) | `<iframe>` / `<frame>` / `<portal>` | 要素の存在自体が違反 |
| (c) | `<link>` の `href` | `rel` によらず `data:` 以外なら違反 |
| (d) | CSS の `url()` | `@font-face` に限らず全宣言が対象 |
| (e) | 将来追加される取得属性 | 既定で違反側へ倒す |

### 維持する境界

SC-02 が確定させた「HTML の text node に現れる URL は違反にしない」規約を壊さない。表示されるだけの文字列は取得を発生させず、これを違反にすると資料本文で参考 URL に言及できなくなる。`alt` / `title` の URL、エスケープされたコード例も同様。SC-10 が見るのは **属性値と CSS 値だけ**。要素名は完全一致で判定し、`<frame>` の前方一致で `<frameset>` や `<figure>` を拾わない。

## 裁定した未決 2 件

テスト側 (`tests/verify-handout-selfcontained.py/README.md` の gaps) が意図的に assert せず残した論点を、本 leaf で裁定した。

### 1. `<iframe srcdoc="...">` のみの場合 → **例外なく違反**

`srcdoc` 自体は取得を発生させないが、

1. 配布資料に入れ子閲覧文脈の正当な用途が無い、
2. `srcdoc` の内容は独立した HTML として再帰的に外部参照を持ち得るため、許可すると検査器に入れ子パースを要求することになる、
3. 例外を 1 つ設けた時点で allowlist の「既定で違反側へ倒す」性質が失われる。

したがって (b) は要素の存在のみで判定する。

### 2. SC-01 と SC-10 の二重報告 → **両方報告する**

detection は欠陥の**分類**であって排他的な分割ではない。片方を抑止すると「どの規則クラスの欠陥か」の情報が失われる。加えて SC-10 は取りこぼしを塞ぐ網であり、他規則へ判定を譲る設計にすると再び順序依存が生まれる。

### 付随して決めたこと — CSS `url()` の分担

`@font-face` の `src: url()` は **SC-04**、それ以外の全宣言 (`background` / `background-image` / `mask` / `border-image` / `cursor` / `list-style-image` 等) は **SC-10**。「どちらかが必ず捕える」ことと「同一違反を 2 度数えない」ことを両立させる。

## 正本への反映内容

`briefs/script-brief-C16.json` の変更点:

| キー | 変更 |
| --- | --- |
| `detections` | `SC-10` を追加 (9 → 10 件)。`rule` / `why_independent_from_sc01` / `boundary` / 裁定 3 件 / 例 / 誤検出リスク |
| `algorithm` | 手順 `7c` を追加。手順 3 の収集結果を再利用し追加走査パスを設けない。判定は `data:` で始まるかの単一述語で行い、スキーム正規表現を再利用しない (再利用すると denylist へ退行する) |
| `stdout` | 固定順を `SC-01..SC-09` → `SC-01..SC-10` |
| `canonical_rules.external_reference_rule` | `statement` / `rationale` へ反転の記述を追記。`implemented_by_detections` へ `SC-10` を追加。`delegated_consumers` の C10 行を「SC-10 を含む CR-EXT 全体が対象」へ |
| `acceptance_checks` | `AC-C16-C60-10a` .. `10e` の 5 件を追加 (15 → 20 件) |
| `module_api.exports` | `scan_external_references` の返り値に SC-10 を含めることを明記 |
| `purpose` / `requirements_covered` / `checklist_covered` | C60 を反映 |

## 順序についての逸脱

通常は設計正本 (P02/P03) → テスト (P04) の順だが、本件は逆順になった。C60 は P04-C16-01 の実行中に利用者から提示された要件であり、走行中のテスト leaf へ SC-10 を伝達したため、テストが先に SC-10 を赤で固定しブリーフが後から追いついた。テスト側エージェントは自らこの乖離を README の gaps へ記録しており、本 leaf はその gaps を消し込む形で実施した。逸脱は `eval-log/guide-doc-generator/build/checklist/P04-C16-01.json` の `design-canon-lags-test` として記録済み。

## 派生した知見 (一般化)

生成物の「外部参照ゼロ」検査を**対象列挙で書くと必ず穴が残る**。自己完結性は「禁止されたものが無いこと」ではなく「許可されたものしか無いこと」として定義するのが正しい。この denylist → allowlist の反転は、本 plugin に限らず自己完結性検査一般に効く。
