# RESOLUTION-R22 — 記述粒度の可変を型として持つ (detail_level / evidence_depth)

leaf: `P04-x-03` / 対象正本: `briefs/script-brief-C12.json` ほか 4 本 / 日付: 2026-08-17

## 要件

利用者要件 (2026-08-17):

> あとは、詳しく詳細に伝えるパターンと、勉強会のように大まかに伝えるパターン、レポートのように詳細に伝えるパターンがあります。
>
> 根拠だったりとか、作成する成果物によって、どこまで具体的に、詳細に書くのかという粒度が変わってくるので、その辺もヒアリングしながら整えられるようにしておいてほしいです。

goal-spec へ **C61-C66** として登録済み (checklist 61..66 件目)。

## 設計判断 1 — 粒度は 1 軸ではなく直交する 2 軸である

挙げられた 3 パターンを素直に enum 化すると `detailed / overview / report` の 1 軸になる。これは 2 箇所で破綻する。

1. **「詳しく詳細に伝える」と「レポートのように詳細に伝える」はどちらも詳細だが同じではない。** 両者を分けている実質は**根拠・出典をどこまで書くか**であり、説明の詳しさとは独立に動く。1 軸に畳むと「詳しいが根拠は不要」(社内向けの操作説明) と「粗いが根拠は示す」(経営向けの要約) が表現できない。
2. **`report` は用途 (doc_type) であって粒度ではない。** 1 軸の enum に入れると doc_type と意味が重なる第 2 の入口ができ、片方が必ず腐る。

したがって 2 軸に分ける。

| 軸 | 値域 | 意味 |
| --- | --- | --- |
| `detail_level` | overview / standard / detailed | 説明の詳しさ |
| `evidence_depth` | none / cited / sourced | 根拠の明示度 |

3x3=9 通りは全て valid で、禁止の対を 1 つも設けない (`CR-GRANULARITY-ORTHOGONAL`)。利用者の 3 パターンはこの空間の点として表現される — 詳しく = `detailed`/`none`、勉強会 = `overview`/`cited`、レポート = `detailed`/`sourced`。軸を分けたことで、この 3 点以外も表現できるようになった。

## 設計判断 2 — 粒度を用途プリセットへ埋め込まない

「勉強会のように大まかに」は勉強会という用途の**傾向**であって定義ではない。粒度を R20 のプリセットへ焼き込むと「勉強会だから必ず粗い」が型として固定され、同じ勉強会で詳細版を作る要求に応えられなくなる。

これは R21 の `presentation_order` で確定した「時と場合の問題を片方に固定してはならない」(`CR-PRESENTATION-ORDER`) と**同一構造**なので、新機構を足さず同じ扱いにする — プリセットは既定値を与えるだけ (`CR-GRANULARITY-PRESET-DEFAULT-ONLY`)。

ただし `presentation_order` と 1 点だけ違う。あちらは `prior_knowledge_level` から決定論導出できたので新規ヒアリング項目を足さずに済んだが、粒度は既存のどのヒアリング項目からも導出できない。同じ読者・同じ用途でも「今日は要点だけ」「今回は詳しく」が変わるのは利用者側の事情であり、資料の属性からは決まらない。利用者が明示的に「ヒアリングしながら整えられるように」と要求したのもこの性質による。したがって粒度だけはヒアリング項目にする — ただし**必須回答にはしない** (既定が常に存在するため)。

## 責務の割り当て (新 component を作らない)

| checklist | 責務 component | 機構 |
| --- | --- | --- |
| C61 (detail_level 必須・プリセット既定・provenance) | C12 / C23 | `document_level_fields` へ追加 + `CR-GRANULARITY-PRESET-DEFAULT-ONLY` + C23 `granularity_defaults` |
| C62 (evidence_depth の独立軸) | C12 | `CR-GRANULARITY-ORTHOGONAL` |
| C63 (文字数上限の modulate) | C11 (数値の正本) / C12 (適用) | テーマトークン `text_limits.block_body_max_chars_by_detail_level` + `CR-DETAIL-TEXT-BUDGET` |
| C64 (ヒアリング) | C01 | `responsibilities[R1-elicit].hearing_required_items_r22` (required:false) |
| C65 (水準間の共有の型の不変) | C11 | 既存の C44 不変条件をテストで水準横断に固定 (P04-x-04) |
| C66 (宣言↔実態の一致) | C22 | 検出 `NAR-09` / `NAR-10` + `granularity_declared_vs_actual` |

**C09 は変更しない。** C66 は「4 面集約への反映」を求めるが、`NAR-09`/`NAR-10` は C22 の内部検出として追加されており、C09 は既に C16/C17/C18/C22 の 4 面を集約している。集約側に手を入れると 4 面の境界 (P03 Y-07 で確定) が崩れる。

## 数値の正本を 1 箇所に保つ (C63 の要点)

R21 C52 が既に `text_limits.block_body_max_chars` (既定 400) をテーマトークンへ置いている。detail_level ごとの値を script 側へ書くと、同じ概念の数値が 2 箇所へ分かれ、テーマを差し替えたときに standard の上限だけが追従して detailed が追従しない不整合が起きる。

したがって水準別の値も同じトークンファイルが持ち、C12 は `detail_level` をキーに引くだけにする。キーを持たないテーマでは `block_body_max_chars` を全水準へ適用する fail-soft とし、既存テーマを壊さない。

## 宣言と実態の突合が要る理由 (C66 の要点)

宣言値は生成物の**自己申告**である。`detailed` を宣言しながら記述量が overview 相当しかない資料、`evidence_depth=sourced` を宣言しながら出典が 1 つも無い資料は、外部参照ゼロ検査も a11y 検査も絵文字検査も通過する。宣言と実態の乖離は既存のどのゲートでも捕まらない**独立した欠陥クラス**なので、専用の判定が要る。

判定は 2 つの規約で成り立つ。

- **宣言は下限の約束として扱う。** `none` は「根拠を書いてはならない」ではなく「根拠を示さない方針」の意味なので、下回った場合のみ違反とする。
- **主張単位・セクション平均で見る。** 文書全体に出典が 1 つあれば通る判定にすると 10 個の主張のうち 1 つだけ根拠がある資料が `sourced` を名乗れる。総量で判定するとセクション数の多い資料が自動的に `detailed` 判定になる。

## 正本への反映内容

| ブリーフ | 変更 |
| --- | --- |
| `script-brief-C12.json` | `document_level_fields` へ `detail_level` / `evidence_depth` を追加 (29 件)。新キー `r22_granularity_constraints` に 4 規則 (`CR-GRANULARITY-ORTHOGONAL` / `CR-GRANULARITY-PRESET-DEFAULT-ONLY` / `CR-DETAIL-TEXT-BUDGET` / `CR-GRANULARITY-DECLARED-VS-ACTUAL`)。`requirements_covered` / `checklist_covered` (C61-C63) |
| `script-brief-C11.json` | `theme_token_schema_ownership` へ `added_block_r22` (`block_body_max_chars_by_detail_level`) と設置理由。`html_attribute_contract` へ `data-hb-detail-level` / `data-hb-evidence-depth`。`checklist_covered` (C63/C65) |
| `script-brief-C23.json` | 新キー `granularity_defaults` (7 doc_type 分の既定値と各々の理由)。`invariant_vs_variant.variant_per_preset` へ 1 行。`checklist_covered` (C61) |
| `script-brief-C22.json` | 検出 `NAR-09` / `NAR-10` を追加 (8 → 10 件)。`canonical_rules.granularity_declared_vs_actual`。`checklist_covered` (C66) |
| `skill-brief-C01.json` | `responsibilities[R1-elicit].hearing_required_items_r22` (2 項目・required:false・1 問へまとめる)。`checklist` へ 1 行 |

## 確定した数値 (C63) — **2026-08-18 に R25 (REQ-7・goal-spec C73・最優先) が superseded にした。現在の正本は `improvement/text-length-gate-decision.json` (+ `briefs/RESOLUTION-R25-improvement-2026-08-18.md` D8)。下表は R22 時点の当初値として経緯のみ残す**

`assets/tokens/<theme>.json` の `text_limits.block_body_max_chars_by_detail_level`:

| 水準 | 上限 | 根拠 |
| --- | --- | --- |
| overview | 180 | 日本語で 3〜4 文。lead_line と要点 2 つが収まる量。これ以上下げると折り畳みが多発し、畳まれた中身の総量は変わらないので粗さが実現しない (折り畳みは要約ではない) |
| standard | 400 | R21 C52 の既定値と一致。既存テーマの `block_body_max_chars` をそのまま standard として読めるようにするため動かせない |
| detailed | 900 | standard の 2.25 倍。overview との比を 5 倍に開いたのは NAR-09 のためで、差が小さいと「detailed 宣言だが実態は overview 相当」を検出できない |

**detailed における折り畳み挙動**: 折り畳み自体は全水準で行い、detailed のみ生成する B10 を `open=true` で出力する。

折り畳みを止めなかった理由は構造の同一性にある。止めると `--normalize` に水準依存の分岐が生まれ、構成データと HTML の構造対応が水準ごとに変わる。`open` 属性を変えるだけなら**構造は全水準で同一**のまま読み味だけが変わり、C20 の round-trip 等価 (C31) も C65 の共有の型の保持も無傷で、既存のアコーディオン部品に相乗りできる。「詳しく書いたのに畳まれている」と「版面が長大化して離脱する」の両方を同時に避ける唯一の選択肢だった。

## 到着時期についての逸脱

R21 は P04 のテストが 1 本も書かれる前に到着したため設計 leaf 1 本で完結したが、R22 は C11 / C12 / C22 / C23 のテスト leaf が `done` へ遷移した後に到着した。`sync-task-state.py` の `ALLOWED_TRANSITIONS` で `done` は終端であり、閉じた leaf を再オープンすると `reconcile_done_dependency_closure()` が下流の done も巻き戻す。したがってテスト側の反映は本 leaf ではなく追補 leaf `P04-x-04` として置き、`P04-x-01` の phase gate が両者に依存するようにした。

## 派生した知見 (一般化)

利用者が「A のパターンと B のパターンと C のパターンがある」と列挙したとき、**その列挙をそのまま enum にしてはならない**。列挙は利用者が経験した事例の標本であって次元ではない。今回も 3 パターンをそのまま enum 化すると、標本に無い組み合わせ (詳しいが根拠不要) が表現不能になり、かつ標本の 1 つ (report) が別次元 (用途) の値だったために既存フィールドと衝突した。列挙を受け取ったら**何がその 3 つを分けているのか**を先に問い、次元を同定してから値域を決める。
