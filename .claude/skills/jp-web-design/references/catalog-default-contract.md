# Catalog default contract

`assets/reference/catalog.html` の視覚・操作・レスポンシブ規律を、指定なしのWeb UIへ再現可能に適用する唯一のconsumer contract。機械可読な正本は `assets/reference/catalog-default-profile.json`。

## 適用判定

| 対象 | 既定 |
|---|---|
| 新規の可視Web UI | `apply --app-state=new`。利用者への確認は不要 |
| 既存UI | 下記「既存アプリの一本化フロー」。適用資格は `migrate-legacy-colors.mjs` と同じ共有判定で自動算出し、既存ブランド・Pop・判定不能は `REPORT_ONLY` |
| API・batchなど可視UIなし | `NON_VISUAL(理由)` をT2/T4へ記録して対象外 |
| Pop・外部ブランド | `REPORT_ONLY`。自動適用せず選択済みvariantの規則を検収する |

依頼文に「デザイン」があるかでは判定しない。DOM / JSX / HTML、描画component、新画面、layout、style/token、利用者が操作するinteractionのいずれかを作る・変えるなら適用対象。

## 新規アプリの実行順

```sh
node <jp-web-design>/scripts/catalog-default.mjs plan <app-root> --app-state=new
node <jp-web-design>/scripts/catalog-default.mjs apply <app-root> --app-state=new
node <jp-web-design>/scripts/catalog-default.mjs verify <app-root> --stage=v0
# 正式版前。runtime scenarioを実業フローで埋めてから:
node <jp-web-design>/scripts/catalog-default.mjs verify <app-root> --stage=v1
```

## 既存アプリの一本化フロー

既存の可視UIへ平賀既定を入れる手順はここだけに書く。他の文書はこの節を参照し、手順を複製しない。

1. `catalog-default.mjs verify <app-root> --stage=v0` — 既に管理下なら drift を先に確認する(「更新」節)。
2. `migrate-legacy-colors.mjs <app-src-dir> --plan --json` — 適用資格と旧→新の計画を保存する。旧→新の対応はこの出力が正本。
3. 適用資格が `eligible`(`source_theme` が `legacy-mode-a` / `unspecified` / `hiraga`)なら `--apply` で `automation=safe` だけを置換する。review-only は未変更のまま役割を判断する。
4. `catalog-default.mjs plan <app-root> --app-state=existing` — `--eligibility` 未指定時は手順2と同じ共有判定で自動算出する。`--eligibility=eligible|unknown` は証拠を確認したうえでの明示上書き。
5. `catalog-default.mjs apply <app-root> --app-state=existing` — 画面構成・文言・余白は変えず、色と正本CSSの読み込みだけを揃える。
6. `verify --stage=v0`。正式版前は `--stage=v1`。
7. T2へ適用資格・plan JSONの旧→新対応・review-only残件・例外を記録する。

「ライトのみ」「既存は色だけ移行」の不変条件は INV-15 と `hiraga-color-system.md` が正本。

## 生成物と読み込み順

`apply` は正本CSS、版・digestつき `docs/product/design-profile.json`、空の `docs/product/design-runtime-scenarios.json`、v1実測用の待機中証拠だけを生成する。業務DOM、可視文言、サンプルデータ、参照HTMLの説明文はコピーしない。検出できたCSS入口で、正本importをコメントではないactive importの1件に正規化し、Tailwind等のframework importより後ろへ置く。入口が見つからなければ勝手にframework構成を推測せずFAILし、実装者がapp root内の `--entry-css=<relative-path>` を指定する。

- 配置先: `src/styles/aidd/hiraga-color-system.css`(色の値の正本コピー)と `src/styles/aidd/catalog-default.css`(部品CSS。先頭で隣の平賀CSSを import する)。値の書き換え、JS定数への複製、CSSの手動コピーはしない(差分は verify が drift として検出する)。
- 読み込み順: 入口CSSでは `@import "tailwindcss";` などframework importを先に置き、`catalog-default.css` の import を最後の active `@import` にする。Tailwind v4 の `@theme inline` 橋渡しはこの後ろに書く(`hiraga-color-system.md` §3)。

各UI sliceの実装後、`design-profile.json` の `adopted_components` に `screen`、app root内の `source_files`、`components`、画面rootと共通の `runtime_marker` を記録し、描画rootに `data-aidd-screen="<runtime_marker>"` を付ける。`screen` と `runtime_marker` は全宣言で一意にし、同じDOMを別画面として二重計上しない。component idはprofileの `component_markers` だけを使う。v0は宣言sourceの存在、コメント/文字列ではない実markupのclassとmarker、consumer source inventory全体の参照サンプル非混入を照合する。空や引用例だけの適用宣言ではPASSしない。

## 段階ゲート

- v0 minimum baseline: 正本資産のdigest、active CSS importと順序、provenance、宣言component/markerと実装sourceの対応、ライトテーマ、consumer source inventory全体のサンプル文言非コピーを機械検査する。ここは速度のためにも省略しない。
- v1 full conformance: v0に加え、`catalog-default.mjs verify --stage=v1` 自身が `catalog-runtime-audit.mjs` を再実行し、Chromeの4幅・実pointer/keyboard操作で初期DOMと各dynamic path後のDOMを再監査する。検査項目の一覧は `acceptance-checklist.md` の v0/v1 項目が正本。`design-runtime-evidence.json` は `catalog-runtime-audit.mjs` の生成物であり、手書きや自己申告で代用しない。開発中の単独実行は `node <jp-web-design>/scripts/catalog-runtime-audit.mjs <app-root>`、起動済みアプリは `--base-url=<url>` を使う。
- T2はprofile/version/digest・適用資格・採用部品・例外、T3はUI sliceごとのcatalog componentと検査、T4はv0/v1 reportと未解決例外を受け取る。詳細値はこの契約へ戻し、他文書へ複製しない。

## Runtime scenario

`design-runtime-scenarios.json` は生成対象のapp root内URLと、実際の主要操作を宣言する。`screens` は `adopted_components[].screen` と一致させ、1件以上、nameとURLはそれぞれ一意にする。`dynamic_paths` はnameを一意にし、pointerとkeyboardの両方を含める。使える操作は `click` / `focus` / `key` / `wait`、検証は `text` / `attribute` / `value` / `visible`。各pathは click/key前のpreconditionと、同じselector+観測項目で値が異なるpostconditionを必須とし、元から真の静的assertionで操作成功を代用しない。selectorは見た目に依存する順番ではなく、一意のidや安定した業務属性を使う。

可視の `p` / `small` / helper系classは既定で常設補足としてFAILする。業務上必要な場合だけ `data-aidd-copy` にprofileの `visible_copy_allowlist`(例: `value`, `next_action`, `irreversible_warning`)を指定する。`role="status"` / `role="alert"`、エラー、toast、注意、空状態は意味から自動分類する。この属性は画面に文言を追加するものではない。

```json
{
  "schema_version": 1,
  "screens": [{ "name": "home", "url": "index.html" }],
  "dynamic_paths": [
    { "name": "save-pointer", "screen": "home", "steps": [
      { "assert": "visible", "selector": "#status", "equals": false },
      { "action": "click", "selector": "#save" },
      { "assert": "visible", "selector": "#status", "equals": true }
    ]},
    { "name": "choice-keyboard", "screen": "home", "steps": [
      { "assert": "attribute", "selector": "#choice", "name": "aria-pressed", "equals": "false" },
      { "action": "focus", "selector": "#choice" },
      { "action": "key", "key": "Enter" },
      { "assert": "attribute", "selector": "#choice", "name": "aria-pressed", "equals": "true" }
    ]}
  ]
}
```

## 更新

`improve-app` 着手時は `verify` を先に実行する。digest不一致や管理資産の改変がある場合、`plan` は `existing-managed-artifact-drift` と対象・理由・期待digestを出して適用を停止する。差分と上書き対象を実作業で確認した場合だけ `apply --app-state=existing --eligibility=eligible --reviewed-upgrade` を使う。このflagは承認の自動推測ではなく、その実行自体を明示証跡とする。既存ブランドや画面固有構造を正本へ合わせる目的で破壊しない。同じ逸脱が複数画面・複数アプリで反復した場合だけ、参照実装またはprofileの改善候補へ昇格する。
