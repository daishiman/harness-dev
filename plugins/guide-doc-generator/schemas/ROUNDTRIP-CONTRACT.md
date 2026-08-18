# ROUNDTRIP-CONTRACT — 逆抽出 round-trip の成立条件

R14 (生成済み HTML を逆抽出して別テーマの新規資料の出発点にする) が成立するための条件を
確定する裁定記録。裁定対象は「構成データの各項目を HTML へマーカーとして刻むか、
round-trip の対象外と明示宣言するか」の二択であり、その採否を機械可読に記録する。

正本の関係:

- 構成データの形の正本 = `schemas/handout-config.schema.json` (owner C12)
- マーカー契約の正本 = `plugin-plans/guide-doc-generator/briefs/script-brief-C20.json#renderer_marker_requirements`
  (C11 宛の要求として書かれている)
- round-trip 粒度の正本 = 同 `#roundtrip_granularity`
- 本ファイル = 上記の隙間に落ちていた項目の採否の正本

## 1. R14 が要求する一致の粒度

`plugin-plans/guide-doc-generator/goal-spec.json` の R14 受入基準は
「生成済み HTML を逆抽出スクリプトにかけたとき構成データ (JSON) が復元され、
その構成データを再レンダリングした HTML が元 HTML と**意味的に一致する**
round-trip テストが PASS する」である。バイト一致とは書かれていない。
同ファイルの open_questions に
「R14 の逆抽出における round-trip 一致の粒度 (バイト一致か構成データ等価か) が未確定。
C20 は暫定で意味的一致を採用している」があり、粒度が未決であったことも明示されている。
`skills/run-handout-extract/SKILL.md` の目的記述も
「既存の単一 HTML を構成データへ戻し、別テーマの新規資料の出発点にできる状態を作る」であって、
再レンダリング物の同一性ではなく**構成データの利用可能性**を求めている。

したがって本契約は次を採る。

- **R14 の合格条件は「正規化済み構成データの比較対象射影の上での深い等価」**
  (script-brief-C20.json#roundtrip_granularity.verdict と同じ)。
- `AC-C20-02` のバイト一致は R14 が直接要求するものではなく、
  「構成データ等価が成立していれば C29 (同一構成データからの再生成は決定論) により
  自動的に従う」派生検査である。よってバイト一致は
  **構成データ等価が成立した後にのみ意味を持つ**。等価が成立していない現状で
  バイト一致だけを緑にする改変 (例: 差分の出る項目を比較から外す) は禁止する。
- 「出発点として使える程度で足りる」とは読まない。出発点として使える構成データとは
  `validate-handout-config.py --config` を exit 0 で通る構成データのことであり、
  必須フィールドが欠けたままの復元結果は出発点にならない (AC-C20-09 が
  「未完成の逆抽出結果がレンダリングへ抜けない」ことを要求している)。

## 2. 実測による復元不能項目集合の導出

裁定の前提として、復元不能な項目集合を discovered-task の記述から借りず自分で実測した。

手続き (再現可能):

1. schema の required と x_required_after_normalize を満たす構成データを作り
   `validate-handout-config.py --normalize` を exit 0 で通す。
2. その正規化済み構成データを `render-handout.py` へ与えて HTML を生成する。
3. 生成 HTML を `extract-handout-config.py --html` へ与える。
4. 復元結果を `validate-handout-config.py --config` へ与える。

実測結果と、そこから導かれる**原因の同定**は次のとおり。

### 2.1 discovered-task の前提は現行実装と食い違う (実測を優先する)

discovered-task (`eval-log/guide-doc-generator/build/discovered-tasks/553225a4…json`) は
`focus_theme / target_tasks / attainment_level / must_remember / no_need_to_remember / ties_to`
について「C11 の renderer_marker_requirements に対応マーカーが無く HTML へ刻まれていない
ため復元不能」と記述している。**現行の `scripts/render-handout.py` ではこれは成立しない。**

- `render-handout.py:1357` `field_span("focus_theme", …)` — `data-hb-field="focus_theme"` を出力
- `render-handout.py:1368` `field_span("target_task", …, extra=[("data-hb-key", task["id"])])`
- `render-handout.py:1373` `field_span("attainment_level", …)`
- `render-handout.py:1378` `field_span("must_remember", …)`
- `render-handout.py:1383` `field_span("no_need_to_remember", …)`
- `render-handout.py:1536` `("data-hb-ties-to", section.get("ties_to", ""))`

生成 HTML を実測すると `data-hb-field` の値として
`title / date / purpose / background / goal / duration / focus_theme / target_task /
attainment_level / must_remember / no_need_to_remember` が実在し、
`data-hb-ties-to` も section 要素に実在する。**マーカーは刻まれている。**

同様に `date` についても、discovered-task は「HTML は表示書式を運ぶ」ため
`E-DATE-FORMAT` になると述べているが、実測では
`<span class="date-pill num" data-hb-field="date">2026/08/17</span>` であり
schema の `^\d{4}/\d{2}/\d{2}$` に適合する素値が刻まれている。
`E-DATE-FORMAT` は再現しない。

### 2.2 真の原因 — マーカーの欠落ではなく到達不能

実測した `extract-handout-config.py` の診断は次のとおり (抜粋)。

```
E-EXTRACT-UNRECOVERABLE /title title を運ぶ data-hb-field="title" が無い
E-EXTRACT-UNRECOVERABLE /date date を運ぶ data-hb-field="date" が無い
E-EXTRACT-UNRECOVERABLE /purpose ...
E-EXTRACT-UNRECOVERABLE /background ...
E-EXTRACT-UNRECOVERABLE /goal ...
E-EXTRACT-UNRECOVERABLE /duration ...
E-EXTRACT-UNRECOVERABLE /sections/0/heading heading を運ぶ data-hb-field="heading" が無い
E-EXTRACT-UNRECOVERABLE /sections/1/heading ...
```

`title` すら復元できていない。原因は次の 2 つの契約条項の衝突である。

- C11 は hero 枠を `data-hb-generated="true"` 付きで出す (`render-handout.py:1386-1391`)。
  これは script-brief-C20.json#renderer_marker_requirements が
  「nav / hero 枠 / sprite / footer / メモ UI / lightbox の各ルート要素」へ要求したものである。
- 同 brief は `data-hb-generated="true"` について
  「抽出器はこの属性を持つ部分木を丸ごと読み飛ばす」と定めている。
- ところが hero 枠の内側は生成 chrome ではなく、文書レベルの著者記述そのものを描画している。

結果として **hero の内側にある `data-hb-field` は全て読み飛ばされる**。
2.1 で確認した focus_theme / target_tasks / attainment_level / must_remember /
no_need_to_remember のマーカーも、title / date / purpose / background / goal / duration の
マーカーも、同じ理由で到達不能になっている。
これは「マーカーが無い」問題ではなく「マーカーが chrome 境界の内側にある」問題である。

この実測は独立に再現されている。`tests/render-handout.py/test_cross_component.py`
の `test_round_trip_equivalence` (AC-C11-15) が同一の診断列を出して赤である。

### 2.3 実測で追加的に判明した項目

discovered-task が挙げていない次の項目も round-trip を阻害している。裁定対象に含める。

- `sections[].heading` — `render-handout.py:1511` は `<h2 class="section-label">` を出し
  `data-hb-field="heading"` を持たない。しかも見出し要素の内側に
  `<span class="section-num">` で連番を描画しているため、テキストからの復元は
  `1全体の流れ` のように連番が混入する。script-brief-C20.json の `data-hb-field` 値の
  列挙にも `heading` が無い一方、`extract-handout-config.py` の `SECTION_FIELDS` は
  `heading` を必須として要求しており、brief と script が食い違っている。
- `sections[].ties_to` の直列化 — 実測値は
  `data-hb-ties-to="[&#x27;goal&#x27;, &#x27;target_task:monthly-check&#x27;]"` であり、
  Python の list repr がそのまま属性へ入っている。宣言された直列化形式が無いため
  機械的に読み戻せない。マーカーの有無ではなく**形式未定義**が欠陥である。
- `sections[].role` / `sections[].attainment_step` — マーカー
  (`data-hb-section-role` / `data-hb-attainment-step`) は C11 が出しているが
  script-brief-C20.json#renderer_marker_requirements に列挙が無く、
  `extract-handout-config.py` も読んでいない。
- C11 と C12 の入力契約が乖離している (round-trip 以前の問題)。
  `render-handout.py:387` は `normalized: true` を、`:441` は `nav` を必須にするが、
  どちらも schema の `additionalProperties:false` で `E-KEY-UNKNOWN` になる。
  さらに C11 は `sections[].blocks` を走査する (`render-handout.py:1523`) 一方
  schema は `sections[].parts` を宣言しており、schema 準拠の構成データを
  C11 へ渡すと部品が 1 件も描画されない (実測: `blocks_by_type: {}`)。
  この乖離が解消されない限り、どの項目を刻んでも round-trip は成立しない。

## 3. 裁定

### 3.1 裁定原則

ある項目を round-trip 対象外と宣言してよいのは、次のいずれかに当たるときに限る。

- **P1 再生成可能**: 構成データの他の値から決定論的に生成される派生物である
  (nav / sprite / CSS / JS / footer / メモ UI など)。
- **P2 実行環境由来**: 意味的同一性に属さない来歴である (provenance ブロック)。
- **P3 表現層の揺れ**: HTML の空白・属性順・キー順など、正規化で消える差分である。

これらに当たらない**著者が書いた内容**を round-trip 対象外と宣言することは、
「受入基準を満たすために基準を弱める」行為であり禁止する。
C20 route report (`eval-log/guide-doc-generator/build/route-P05-C20-01.json`) の
「(b) の schema へ round-trip 免除を足す案は非推奨」という推奨は、この意味で妥当である。
根拠を自分で確認したうえで採用する。**本裁定は C20 の推奨と一致し、
著者記述の項目については 1 件も round-trip 免除を採らない。**

なお 2.1 の実測により、裁定の実務的な意味は当初想定と変わっている。
争点は「マーカーを新設するか免除するか」ではなく、
**既に刻まれているマーカーを到達可能にし、抽出器に読ませるか**である。
それでも選択肢としては (a) 側であり、schema を緩める必要は生じない。

### 3.2 機械可読な裁定表

後続タスクはこの fenced block を JSON として読むこと。
`decision` は `marker` (= HTML へマーカーとして刻む) か
`exempt` (= round-trip の対象外と明示宣言する) のいずれか。

```json
{
  "contract_version": "1.0",
  "roundtrip_pass_condition": "normalized-config-comparable-projection-deep-equality",
  "byte_equality_status": "derived-from-C29-only, not a primary R14 bar",
  "measured_against": {
    "renderer": "plugins/guide-doc-generator/scripts/render-handout.py",
    "extractor": "plugins/guide-doc-generator/scripts/extract-handout-config.py",
    "validator": "plugins/guide-doc-generator/scripts/validate-handout-config.py"
  },
  "adjudications": [
    {
      "pointer": "/focus_theme",
      "decision": "marker",
      "marker": "data-hb-field=\"focus_theme\"",
      "marker_status": "emitted-but-unreachable",
      "evidence": "render-handout.py:1357",
      "rationale": "著者が書いた主題枠であり P1/P2/P3 のいずれにも当たらない。schema required かつ R21 C47 の実体。免除すれば逆抽出結果は必ず E-FOCUS-THEME で落ち、出発点として使えない。",
      "residual_work": "hero 内 data-hb-field の到達性確保と抽出器の読み取り"
    },
    {
      "pointer": "/target_tasks",
      "decision": "marker",
      "marker": "data-hb-field=\"target_task\" + data-hb-key (= target_tasks[].id)",
      "marker_status": "emitted-but-unreachable",
      "evidence": "render-handout.py:1368 (data-hb-key に target_tasks[].id)",
      "rationale": "著者記述。かつ sections[].ties_to の参照先実体であるため、失うと ties_to が必ず dangling になる。id は data-hb-key に既に載っており復元路は存在する。",
      "residual_work": "同上"
    },
    {
      "pointer": "/attainment_level",
      "decision": "marker",
      "marker": "data-hb-field=\"attainment_level\"",
      "marker_status": "emitted-but-unreachable",
      "evidence": "render-handout.py:1373",
      "rationale": "著者記述。sections[].attainment_step の上限検査の基準値であり、他の値から導出できない (最大の attainment_step から逆算すると E-ATTAINMENT-UNREACHED を常に自明に満たす別物になる)。",
      "residual_work": "同上"
    },
    {
      "pointer": "/must_remember",
      "decision": "marker",
      "marker": "data-hb-field=\"must_remember\"",
      "marker_status": "emitted-but-unreachable",
      "evidence": "render-handout.py:1378",
      "rationale": "著者記述 (R21 C57)。no_need_to_remember と対で schema 必須であり、片方だけ復元しても E-REMEMBER-PAIR で落ちる。",
      "residual_work": "同上"
    },
    {
      "pointer": "/no_need_to_remember",
      "decision": "marker",
      "marker": "data-hb-field=\"no_need_to_remember\"",
      "marker_status": "emitted-but-unreachable",
      "evidence": "render-handout.py:1383",
      "rationale": "must_remember と同じ。対の一方だけを免除する非対称な契約は作らない。",
      "residual_work": "同上"
    },
    {
      "pointer": "/sections/*/ties_to",
      "decision": "marker",
      "marker": "data-hb-ties-to",
      "marker_status": "emitted-but-serialization-undefined",
      "evidence": "render-handout.py:1536 (実測値は Python list repr がそのまま属性へ入る)",
      "rationale": "著者記述であり、R21 C48/C58 の紐づけの実体。欠けると role=main の全セクションが E-SECTION-UNTIED-GOAL / E-SECTION-UNTIED-TASK で落ちる。マーカーは存在するので必要なのは直列化形式の宣言であって免除ではない。",
      "required_serialization": "半角スペース区切りのトークン列。各トークンは schema $defs.section.properties.ties_to.items.pattern に適合する。空配列は空文字列。",
      "residual_work": "C11 側で list を上記形式へ直列化し、C20 側で分解する"
    },
    {
      "pointer": "/notes_enabled",
      "decision": "marker",
      "marker": "data-hb-notes-enabled (新設)",
      "marker_status": "absent",
      "evidence": "extract-handout-config.py の UNMARKED_DOCUMENT_KEYS が値 null でキーだけ残すため E-TYPE-INVALID /notes_enabled になる",
      "rationale": "免除を採らない理由: 免除すると normalize が既定 true を充填するため、著者が false を選んだ資料が round-trip で true へ化ける。これは P1 (再生成可能) ではなく値の消失である。メモ UI の有無からの推定も採らない (メモ UI は data-hb-generated 部分木であり、抽出器が読み飛ばす対象と定められているため、そこへ意味情報の復元を依存させると chrome 読み飛ばしの規約と矛盾する)。<html> の属性 1 本を足すのが最も安く、かつ無損失である。",
      "residual_work": "C11 が <html> へ true/false を刻み、C20 が読んで boolean へ戻す。抽出器は null を書かない"
    },
    {
      "pointer": "/date",
      "decision": "marker",
      "marker": "data-hb-field=\"date\"",
      "marker_status": "emitted-but-unreachable",
      "evidence": "render-handout.py:1336 / 実測 HTML: <span class=\"date-pill num\" data-hb-field=\"date\">2026/08/17</span>",
      "rationale": "著者記述。discovered-task の『HTML は表示書式を運ぶため E-DATE-FORMAT になる』という前提は現行実装では再現しない。C11 は schema の書式 (YYYY/MM/DD) の素値をそのまま刻んでいる。したがって表示書式のための追加の裁定は不要で、必要なのは到達性だけ。",
      "residual_work": "hero 内 data-hb-field の到達性確保"
    },
    {
      "pointer": "/assets/*/data_uri",
      "decision": "dialect",
      "marker": "data-hb-src (原本相対パス) と <img src> の data URI",
      "marker_status": "emitted",
      "evidence": "render-handout.py:1154 が data-hb-src へ asset.src を出す / embed-assets.py:251 が data_uri を書く / $defs.asset の properties は id,kind,src,alt,caption,role の 6 個で additionalProperties:false",
      "rationale": "**本エントリは P05-x-28 で裁定を反転した。旧裁定 (『抽出器が schema に無い data_uri キーを発明した E-KEY-UNKNOWN であり、data URI は捨てて src へ原本パスを戻す』) は前提が誤っていた。** data_uri を書いているのは C20 ではなく C13 embed-assets.py であり、C13 は同時に embed_status / embed_source_path / embed_skip_reason / encoded_chars / source_bytes の 5 キーと top-level asset_embedding も書く。これらは 1 つも schema に無く、$defs.asset / $defs.attachment は additionalProperties:false である。つまり data_uri だけを E-KEY-UNKNOWN と呼ぶ根拠が無い (呼ぶなら残り 6 つも同罪になる)。争点は『キーの発明』ではなく、schema が記述している文書型が C13 前の著者構成データだけで、C13 後の埋め込み済み構成データに正本が与えられていないことである。C20 は後者を HTML から復元する側なので src (原本パス) と data_uri (ペイロード) の両方を持つのが正しい。加えて旧裁定は実害を生む: R14 の逆抽出では原本 assets/ が手元に無いのが普通で、HTML 中の data URI が唯一の実体コピーである。これを捨てると『再埋め込みは C13 の責務』が実行不能になり、無損失性を守るつもりで逆に値を消失させる (/notes_enabled のエントリが免除を退けたのと同じ基準に自ら抵触する)。同じ裁定が /attachments/*/data_uri にも当てはまる。詳細は schemas/RESOLUTION-P05-x-28.md。",
      "payload_field": "data-hb-src が非空なら /assets/*/data_uri、空なら /assets/*/src (著者が src へ data URI を直書きした経路。_project_asset が src を空にするため data-hb-src も空になる)",
      "original_path_field": "data-hb-src が非空ならその値を src に戻す。data URI は捨てず data_uri へ入れる",
      "residual_work": "無し (C20 / C13 / C11 の実装は既に本裁定どおり。裁定文書の側が誤っていた)"
    },
    {
      "pointer": "/sections/*/heading",
      "decision": "marker",
      "marker": "data-hb-field=\"heading\" (新設)",
      "marker_status": "absent",
      "evidence": "render-handout.py:1511 は <h2 class=\"section-label\"> を出し data-hb-field を持たない。実測診断: E-EXTRACT-UNRECOVERABLE /sections/N/heading",
      "rationale": "実測で追加検出した項目 (discovered-task の列挙に無い)。著者記述であり schema required。見出しテキストからの復元は <span class=\"section-num\"> の連番が混入するため不可 (実測: '1全体の流れ')。script-brief-C20.json の data-hb-field 値の列挙にも heading が無く、brief 側の欠落でもある。",
      "residual_work": "C11 が見出しテキストのみを持つ要素へ data-hb-field=\"heading\" を付ける"
    },
    {
      "pointer": "/sections/*/role",
      "decision": "marker",
      "marker": "data-hb-section-role",
      "marker_status": "emitted-but-not-in-brief-and-not-read",
      "evidence": "render-handout.py:1535",
      "rationale": "実測で追加検出。appendix の並び順検査 (E-APPENDIX-ORDER) と ties_to 必須性の分岐に効くため、既定 main で埋めると appendix セクションが誤って本編扱いになる。マーカーは既に出ているので brief への追記と抽出器の読み取りだけで足りる。",
      "residual_work": "brief の required_markers へ追記し C20 が読む"
    },
    {
      "pointer": "/sections/*/attainment_step",
      "decision": "marker",
      "marker": "data-hb-attainment-step",
      "marker_status": "emitted-but-not-in-brief-and-not-read",
      "evidence": "render-handout.py:1537-1538",
      "rationale": "実測で追加検出。attainment_level との整合検査の被検査側であり、normalize が充填しない (推測しない) と schema が明記しているため、抽出器が埋めることも許されない。マーカーは既に出ている。",
      "residual_work": "同上"
    }
  ],
  "exempt_preexisting": {
    "note": "以下は本裁定で新たに免除したものではなく、script-brief-C20.json#roundtrip_granularity.not_preserved_by_design が既に宣言していた免除である。本裁定はこれを追認するだけで、範囲を広げない。",
    "items": [
      {"pointer": "/provenance", "principle": "P2"},
      {"pointer": "html whitespace / attribute order / DOCTYPE / comments", "principle": "P3"},
      {"pointer": "config key order", "principle": "P3"},
      {"pointer": "generated chrome (B01 nav / B02 hero frame / sprite / css / js / footer / memo ui / lightbox)", "principle": "P1"}
    ]
  },
  "blocking_contract_divergences": [
    {
      "id": "chrome-boundary-swallows-authored-fields",
      "detail": "hero 枠が data-hb-generated=\"true\" を持つため、その内側の data-hb-field が全て読み飛ばされる。B02 hero 枠が P1 の生成 chrome であること自体は正しいが、枠の内側の著者記述まで一括で捨てる現在の読み飛ばし規約が誤っている。",
      "must_resolve_before": "上記 adjudications の marker 側の実効化"
    },
    {
      "id": "c11-c12-input-shape-divergence",
      "detail": "C11 は normalized:true と nav を必須にし sections[].blocks を走査するが、schema は両キーを additionalProperties:false で拒み sections[].parts を宣言する。schema 準拠の構成データを C11 へ渡すと部品が 1 件も描画されない (実測 blocks_by_type: {})。round-trip の可否以前にパイプラインが繋がっていない。",
      "must_resolve_before": "AC-C20-01 / AC-C20-02 / AC-C11-15 のいずれか"
    }
  ]
}
```

## 4. この裁定が schema に与える影響

**schema (`handout-config.schema.json`) の値域・必須・additionalProperties は 1 箇所も緩めない。**
著者記述の項目を 1 件も免除しなかったため、round-trip 免除の宣言を schema へ足す必要が無い。
schema には本ファイルへの参照 (`x_roundtrip_contract`) だけを置き、
裁定表の実体を二重化しない (二名簿を作らないため)。

## 5. 未達の受入要素

本タスクの受入基準のうち
「復元した構成データが `validate-handout-config.py --config` を exit 0 で通過する」は
**達成していない**。理由は、達成に必要な変更が本タスクの write_scope
(`plugins/guide-doc-generator/schemas/`) の外 (`scripts/render-handout.py` /
`scripts/extract-handout-config.py` および C11/C20 の brief) にあるためである。
scope 外へは 1 バイトも書いていない。必要な後続作業は
`blocking_contract_divergences` と各 adjudication の `residual_work` に列挙してある。
