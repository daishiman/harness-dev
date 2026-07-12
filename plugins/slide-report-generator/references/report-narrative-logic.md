# report 節内論理展開 & 構造化要素カタログ（1.2.0 正本）

> 責務: output_mode=report を「情報の羅列」でなく「構造化された読み物」にするための **(A) 節内論理展開（narrative）** と **(B) 構造化本文ブロック（body[]）** と **(C) 本質的に含むべき横断要素カタログ** の正本。`report-structure.schema.json` 1.1.0 の `section.narrative` / `section.body[]` / inline `==highlight==` / `placement` を、どの内容にどう使うかの意思決定規準を定める。
> 関連: 骨格は [report-types.md](report-types.md)、書式規律は [report-writing-rules.md](report-writing-rules.md)、ビジュアル三択は [report-visual-strategy.md](report-visual-strategy.md)、schema は `schemas/report-structure.schema.json`。

---

## 0. 中心原則 — 「羅列」を生む3欠落を塞ぐ

現状 report が羅列に見える根因は、schema/renderer に (1) **節内論理の器**、(2) **構造化ブロックの器**、(3) **要点強調の器** が無かったこと。1.1.0 でこの3つを additive に足した。書き手（report-structure-designer / report-composer）は本書に従い、各 section を次の3層で組む:

1. **narrative（論理）** — この節が何の本質課題を、どう解決し、どう活かすかを宣言する（heading 直下のリード帯）。
2. **body[]（構造）** — 段落だけでなく、表・コード・番号リスト・小見出し・キーポイント・統計・callout・引用を内容適合で選ぶ。
3. **highlight（強調）** — 要点だけを `==…==` で色付け、または key-point ボックスで囲う（**乱用禁止**）。

> **二層分離（Goodhart 回避）**: schema/renderer/validator が凍結するのは *形（shape）* のみ。「論理が本質を突くか」「強調が本当に要点か」の *意味* は report-quality-reviewer（RQ21-）の意味判定に委ねる。

---

## 1. (A) 節内論理展開 — `section.narrative`

各節は「順序に並んだ情報」でなく「本質課題→解決→活用」の論理を持つ。`narrative` は heading 直下に短いリード帯として描画され、読者に「この節で何が分かるか」を先に渡す。

### 1.1 既定形（推奨）: essence / approach / leverage

| フィールド | 意味 | 書き方 |
|---|---|---|
| `essence` | **本質課題／核心** | 「何が本当の問題か」を1文。表面の症状でなく根っこ |
| `approach` | **解決策／どうやるか** | essence に対する打ち手を1文 |
| `leverage` | **活用／含意** | 「この内容をどう活かすか／次に何が言えるか」1文 |

> 3つ揃わなくてよい（`minProperties:1`）。要約節は essence + leverage、手順節は approach 中心、など節役割に合わせる。

### 1.2 汎用形: `logic[]`（主張→根拠→含意→行動）

論説・分析で essence/approach/leverage が馴染まない時は `logic: [{role, text}]` を使う。role ∈ `claim`(主張) / `evidence`(根拠) / `implication`(含意) / `action`(行動)。

### 1.3 反退化ルール
- narrative を「見出しの言い換え」にしない（heading と同義な essence は退化）。
- 抽象語だけで終えない。approach は具体（手段・条件）を1つ含む。

---

## 2. (B) 構造化本文ブロック — `section.body[]`

`body[]` が存在する節では `paragraphs[]` は **無視**される（排他移行・後方互換）。内容の性質でブロック型を選ぶ:

| type | いつ使うか | 主フィールド |
|---|---|---|
| `paragraph` | 論述・つなぎ | `text`（markdown inline 可） |
| `subheading` | 節内の話題転換 | `text` / `level`(3\|4) |
| `bullet-list` | 並列（順序なし） | `items[]` |
| `ordered-list` | **手順・順序のある列** | `items[]` |
| `table` | **対照・一覧・精密な値** | `headers[]` / `rows[][]` / `caption` |
| `code` | **コマンド・コード・設定** | `code` / `language` / `caption` |
| `key-point` | **節の要点を囲って強調** | `title` / `text` / `tone`(accent\|positive\|caution\|neutral) |
| `stat-tile` | **数値の要約（KPI 的）** | `stats[]`（label/value/trend/note） |
| `callout` | **注意・補足・ヒント** | `variant`(note\|warning\|tip\|caution) / `title` / `text` |
| `blockquote` | **引用・キーメッセージの反復** | `text` |

### 2.1 選択規準（羅列を避ける勘所）
- 3項目以上の対照が出たら **table**（本文に `A は… B は…` と書き流さない）。
- 手順は必ず **ordered-list**（箇条書きでなく番号で順序を見せる）。
- コマンド/コードは **code**（本文にインラインで長く書かない・退化耐性）。
- 節の結論は **key-point** で1つだけ囲う（各節 0〜1 個。多用は逆効果）。
- 数値の要約は **stat-tile**（3〜4枚まで）。

### 2.2 図表番号
`table`/`code` に `caption` を付けると render-report.js が「表N.」「コードN.」を、visual に caption を付けると「図N.」を決定論採番する。相互参照する図表には caption を付ける。

---

## 3. (C) 要点の色付き強調 — inline `==…==` と key-point

| 手段 | 用途 | 密度上限 |
|---|---|---|
| `==要点==`（inline highlight） | 文中の**キーフレーズ1つ**を黄色マーカーで強調 | **1段落に1箇所まで** |
| `key-point` ブロック | **節の結論・最重要メッセージ**を色付きボックスで囲う | **1節に0〜1個** |
| `**太字**` | 用語・ラベルの軽い強調 | 節内で数語 |
| `callout` | 注意/警告/ヒント（本文と別レーン） | 内容に応じ |

> **過剰強調は減点**（report-quality-reviewer RQ・validate-report-visual の上限チェック）。「全部強調＝どこも強調されていない」。強調は要点にだけ効かせる。配色は意匠 SSOT（Kanagawa accent / callout 色）を流用し新規配色を足さない。

---

## 4. (C) 本質的に含むべき横断要素カタログ（reportType 別）

「本質課題→解決→活用」を読者が追えるレポートには、節の中身に加えて横断的な要素が要る。**全 reportType 共通**の骨と、**型別**の必須要素を分けて設計する。

### 4.1 全 reportType 共通
- **エグゼクティブ要約 / TL;DR**（先頭・narrative + key-point で「結論を先に」）
- **キーテイクアウェイ**（読者が持ち帰る3点・stat-tile or key-point）
- **意思決定・次アクション**（読者が次に何をするか・ordered-list）
- **根拠・出典 attribution**（主張の裏づけ・リンク/表）
- **リスク・留保**（限界・前提・注意・callout warning）
- **図表番号・キャプション**（相互参照可読性）
- **長尺時は目次(TOC) + 節間相互参照**（`meta.toc:true`）

### 4.2 reportType 別の必須追加

| reportType | 骨格（[report-types.md](report-types.md)） | 本カタログで足す型別要素 |
|---|---|---|
| `internal-analysis` | 要約→背景→現状分析→所見→次アクション | 現状記述で止めず「本質課題→示唆→次アクション」の論理を通す。所見は key-point、次アクションは ordered-list |
| `client-proposal` | 課題→解決策→効果実績→導入ステップ→CTA | 効果は stat-tile（measurable）、導入は ordered-list、CTA は key-point |
| `tech-doc` | 概要→前提→手順構造→注意点→参照 | **前提条件**（callout）、**用語定義**（table）、**手順番号**（ordered-list + code）、**既知の問題/トラブルシューティング**（table or callout caution） |
| `learning` | 問い→核心概念→図解理解→例応用→まとめ | **学習目標**（先頭 key-point）、**要点まとめ**（末尾 key-point/stat）、**演習・チェック問題**（ordered-list） |

---

## 5. 組み立てチェック（書き手の自己確認）
- [ ] 各節に narrative（essence/approach/leverage or logic）があり heading の言い換えでない。
- [ ] 対照は table、手順は ordered-list、コードは code で表現し本文に流し込んでいない。
- [ ] 要点は `==…==`（1段落1箇所）か key-point（1節0〜1個）で強調し、過剰でない。
- [ ] reportType 別の必須横断要素（§4.2）を満たす。
- [ ] 図表に caption（図表番号採番）、長尺なら `meta.toc:true`。
- [ ] `body[]` を使う節では `paragraphs[]` を併載しない（二重充填禁止）。

---

## 6. 1.2.0 追補 — 文書スケールの通し筋と執筆規律（本 update の正本）

1.1.0 が「節内」の論理器を足したのに対し、1.2.0 は **文書スケール**の論理器（`meta.throughLine` ＋ `section.transition`）、`section.role` による narrative 要否の条件付け、そして羅列/色覚の**評価規律**を足す。機械ゲート **C25**（`validate-report-visual.py`）が through-line/transition/横断 role/多様性<適合性/render 忠実/色覚非依存/doc-level highlight 予算 を決定論検査する（意味の当否は C17 論理 owner に委ね、schema は additive-safe のため hard require しない）。

### 6.1 `section.role` → narrative 適用表

narrative は全節に一律では要らない。role が「本質課題→解決の論理展開を要する節」かで決まる。**弧を持たない列挙・手順・要約節に narrative を強制するのは category error**（意味のない essence を捏造させ退化を招く）。

| 群 | role | narrative | 理由 |
|---|---|---|---|
| **期待**（論理展開が要る） | `analysis` `argument` `problem` `solution` `finding` `background` `impact` `body` | **強く期待**（analysis/argument は実質必須・C25 検査） | 本質課題→解決→含意を通さないと「現状の羅列」に退化する |
| **不要**（弧の強制は誤り） | `reference` `procedure` `summary` `overview` `prerequisite` `step` `cta` `next-action` | 任意（無くてよい） | 列挙/手順/要約/行動喚起が主で、無理な essence は category error |
| **文脈依存**（learning 系） | `question` `concept` `diagram-understanding` `example-application` `conclusion` `caution` | 節が主張を持てば期待、単なる提示なら任意 | 核心概念・まとめは論理を持つが、図の提示・注意喚起は持たなくてよい |

> C25(validate-report-visual.py) は「期待」群 role の narrative 欠落を warn（受入は `--strict` 実行ゆえ fail 相当に昇格）、「不要」群・「文脈依存」群では narrative 強制を課さない（機械は安全側に倒し、主張を持つ文脈依存節の narrative 欠落は C24 の意味判定が担う＝二層分離）。
>
> **機械可読 SSOT**: 本表の role 分類は `validate-report-visual.py` の `_NARRATIVE_REQUIRED_ROLES`（＝「期待」群）と `_NARRATIVE_OPTIONAL_ROLES`（＝「不要」＋「文脈依存」群）を正本とし、本表はその人間可読ミラーである。両者の一致は `lint-contract-drift.py`（check E）が機械検証し、schema `section.role` enum 全値の網羅（MECE）は `test_120_role_classification_covers_all_schema_roles` が担保する（3系統手更新の drift を封鎖）。role を追加する際は validator の2集合と本表を同時更新すること。

### 6.2 横断要素カタログに「文書メタ」を追加（§4.1 への追補）

§4.1 の全 reportType 共通要素に、1.2.0 の**文書メタ**を加える。read-through の鮮度・所要・信頼を冒頭で読者へ渡す。

| 要素 | schema | render | 役割 |
|---|---|---|---|
| 通し筋 | `meta.throughLine` | `.report-throughline`（導入部アーク帯） | 冒頭=本質課題→本論=解決→結=活用の文書アークを1宣言 |
| 版 | `meta.version` | `.report-meta__doc` | 文書の版数（鮮度） |
| 更新日 | `meta.updatedDate`(date) | `.report-meta__doc` | 最終更新（鮮度） |
| 読了目安 | `meta.readingTime` | `.report-meta__doc` | 精読コスト（例「約8分」） |
| 読者 | `meta.audience` | ヘッダ/導入 | 誰向けか（既存必須・語り口の前提） |

### 6.3 report 長さ別 要素適用マトリクス（`meta.length`）

横断要素は length で opt-out 可否が変わる。短報に TOC/相互参照を課すと過剰、精読物で throughLine を欠くと飛び石になる。

| 要素 | `brief`（短報） | `standard` | `deep`（精読） |
|---|---|---|---|
| `meta.throughLine` | 任意 | 推奨 | **必須**（C25 warn） |
| TOC（`meta.toc`） | opt-out 許容 | 推奨 | **必須** |
| 文書メタ（version/updatedDate/readingTime） | opt-out 許容 | 推奨 | **必須** |
| `section.transition`（節間橋渡し） | 軽め（要所のみ） | 推奨 | **必須**（各節） |
| 節間相互参照・図表番号 | 任意 | 推奨 | **必須** |
| 出典 `footnote` | 任意 | 推奨 | **必須**（主張に attribution） |
| `meta.throughLineParts`（部単位 sub-arc） | 不要 | 不要 | **大規模時 推奨**（12節以上で C25 warn） |

> **大規模文書の階層アーク**: 単一 `throughLine`（400字）に文書全体の弧が収まらない精読物（〜50節級）は、`meta.throughLineParts[]`（`{title?,arc}` の配列）で『部(part)』ごとの中間アークを宣言する。render-report.js が throughLine 主帯の下に部構成リストを描画し、読者が章スケールの道標を得る。`deep` かつ 12 節以上で未宣言だと C25 が warn する。50節を超える場合は part 分割で複数レポート化も検討する。

### 6.4 多様性 < 適合性 規律

block 型を「増やすこと」自体は価値ではない。**内容が要求する範囲で** block を適合させる（3項対照→table、手順→ordered-list、用語→definition-list）。

- **叩くのは羅列の床のみ**＝全ブロックが `paragraph` だけの節（構造化の器を一つも使っていない）。C25 はこれを検出する。
- **block 種類数の水増しは加点しない**。要らない table や stat-tile を「多様性のため」に足すのは逆に減点（適合しない構造化＝ノイズ）。
- 判定軸は「この内容にこの器が最適か」。多様性それ自体を目的化しない。

### 6.5 inline highlight 2チャネル規律

`==要点==`（`mark.report-hl`）は**色 + 非色第2チャネル（font-weight:700 + underline）を必須併存**させる＝色覚非依存。色だけの強調は色覚特性で消えるため不可。

- render-report.js の `mark.report-hl` は既に weight+underline を持つ。C25 は CSS block が非色属性を欠く場合を warn する。
- 密度規律は §3（1段落1箇所）に加え、**文書総量の上限**を持つ（[report-writing-rules.md](report-writing-rules.md) §6.3・C25 `doc_highlight_budget=24`）。

### 6.6 reportType → narrative 形式の binding 正本

「本質課題→解決→活用」の弧を、第1語彙（essence/approach/leverage）または第2語彙（`logic[]` の claim/evidence/implication/action）で保存する。**文書冒頭 essence↔throughLine 起点、結節 leverage↔throughLine 終点**を一致させ、文書アークと節論理を同期させる。

| reportType | 弧の起点（本質課題） | 本論（解決） | 終端 role（活用/含意） | 主な narrative 形式 |
|---|---|---|---|---|
| `internal-analysis` | essence（真の課題）/ claim | approach（示唆）/ evidence | `next-action`：leverage / action | essence-approach-leverage 主体 |
| `client-proposal` | essence（顧客課題）/ claim | approach（解決策）/ evidence+implication | `cta`：leverage / action | 効果節は `logic[]`（evidence 厚め） |
| `tech-doc` | 概要節 essence（何を解くか） | 手順節は approach 中心 | `reference`/`procedure`：narrative 任意 | 概要/注意点のみ narrative、手順は不要 |
| `learning` | `question` essence（問い） | `concept`/`diagram-understanding` approach | `conclusion`：leverage（応用・まとめ） | essence-approach-leverage 主体 |

> 終端 role が narrative 不要群（reference/procedure/cta/next-action）でも、**文書全体の leverage は throughLine の結で回収**する。節が持てない弧を throughLine が引き受ける。
