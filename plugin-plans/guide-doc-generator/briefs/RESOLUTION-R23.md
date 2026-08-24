# RESOLUTION-R23 — セクション別挿絵の画風と焼き込み規律の裁定

leaf: `P04-x-07` / 対象正本: `briefs/script-brief-C21.json` / `briefs/agent-brief-C05.json` / 日付: 2026-08-17

一次入力: 利用者提示の参考画像群 (`/Users/dm/dev/dev/ObsidianMemo/05_Project/スライド/slide-2026-06-13-skill-mass-production/assets/generated/` のアイソメ図解 22 枚と、フラット正面図 2 枚「LP制作の前後」「指示の3要素」)。
外部 read-only 参照: `plugins/slide-report-generator/vendor/assets/style-genome-kanagawa-comic-diagram.json` (schemaVersion 1.3.0)。本 graph に producer を持たない既存資産のため `consumes` へは載せない (`P04-x-07.md` の明記に従う)。
先行裁定: `RESOLUTION-P04-x-05.md`。本書はその 3 原則 — **契約に書くのは不変条件であって導出値ではない** / **同じ概念の被覆を 2 つの独立した列挙へ分けない** / **委譲は「同じ規則を書く」ではなく「同じ実装を呼ぶ」** — をそのまま適用する。

| 裁定 | 欠陥の性質 | 結論 | 反映先 |
| --- | --- | --- | --- |
| (a) | 安全弁を「焼かないこと」で実装したため、読み手が得るべき性質まで落ちていた | 既定を `baked-with-overlay` へ。安全弁は `overlayText` 必須で確保する | C21 `algorithm[7]` / `[8]` |
| (b) | 上限が範囲 (6-8) のままで機械検査にならない | ブロック数 **6**・1 ブロック **12 字** の単一整数。形を 3 種の閉じた allowlist に限定 | C21 `baked_text_discipline` (数値の唯一の正本) |
| (c) | 画風が 1 系統しかなく、面積・格子・二項対比が読めない | `isometric-diorama` / `flat-infographic-jp` の 2 系統。図解型 6 語からの全域写像で決定論選択 | C21 `image_style_families` |
| (d) | 退化禁止が画素判定を要求していて実行不能 | 判定を計画側へ移す。`motifs` を 3 役の構造体にして平坦図を**表現不可能**にする | C21 `degradation_proxy_checks` |
| (e) | 内容適応が genome の散文にしかなく、執筆側の必須手順になっていない | C05 の 4 段手順を required 化。全セクション同一構図を C21 が落とす | C05 `procedure` / C21 `algorithm[8]` |

---

## (a) textPolicy 既定を `baked-with-overlay` にする

### (1) 欠陥の性質

`script-brief-C21.json` の `algorithm[7]` は `textPolicy="overlay-only"` を**固定**し、理由を「焼き文字は崩れると印刷 (R15) で修正できない」と書いていた。この理由付け自体は正しい観測である — 実際に参考画像 `slide-11-flow-comparison` の下段ラベル (「情報を集める → 手で整える → 転記する → チェック → 共有」) は生成時に歪んでおり、印刷物ではそのまま出荷できない。

しかし対処が過剰だった。genome の `textPolicies["baked-with-overlay"]` は同じ懸念に別の解を既に与えている — 「**overlayText が常に正本**。崩れたら overlay を表示し画像内文字を装飾扱いにする」。つまり安全弁の実体は「焼かないこと」ではなく「**正本が画像の外にあること**」である。C21 は安全弁の**実装のひとつ**を安全弁そのものと取り違え、その結果「パッと見て直感的に分かる」という参考画像の主要因を丸ごと捨てていた。

参考画像 22 枚は全て `textPolicy: "baked-with-overlay"` で作られており、焼き込みラベルを外すと `slide-09-five-axes` は「鳥居と 5 つの台座」の絵になって何の図か分からなくなる。図解の意味は焼き込みラベルが担っている。

### (2) 裁定

**既定は `baked-with-overlay`。`overlay-only` は構成データの明示指定でのみ選ばれる。どちらでも `overlayText` は必須。**

- 既定 `baked-with-overlay` / `backgroundSource="none"` / `pattern="image-only"`。
- `overlay-only` への切替は、構成データのセクションが `text_policy: "overlay-only"` と `text_policy_reason` (非空) を**対で**持つときだけ。理由を書かずに切り替えられない形にすることで、「迷ったら焼かない」への無言の退避を封じる。片方だけの指定は exit2。
- `overlayText` は両 policy で必須・非空。欠落は exit2。これを C21 の事前検査 (`algorithm[8]`) へ加える。焼き込みを許すのと引き換えに、正本の外部化を検査で強制する。
- 精密な数値表・料金表を含むセクションは、genome の `nonApplicableTypes.precise-table-or-number` に従い**画像を持たない** (HTML 本文で表現する)。`overlay-only` の画像にして逃がさない。画像化しない判断は C05 が行い、そのセクションは `--image-plan` に載らない。

### (3) 根拠

- **安全弁は二重に効く。** overlayText が正本である以上、焼き文字が崩れた画像は「装飾が崩れた」だけであり、内容は overlay 側で読める。R15 (印刷) が要求するのは「読めること」であって「画像が完璧であること」ではない。
- **`overlay-only` を残す理由は残っている。** 正確な表・料金・頻繁に変わる文言は焼くと差し替えコストが跳ねる。ただしその判定は「不安だから」ではなく「値が変わるから」であり、理由の明記を必須にすれば区別が事後に検証できる。
- **既定の向きが利用者の要件と一致する。** 利用者が示したのは全て焼き込み画像であり、既定を焼かない側に置くと、利用者が毎回上書きしないと望む成果物が出ない。既定は「何も言わなかったときに正しい方」へ置く。

---

## (b) 焼き込みテキストの量的規律 — ブロック数 6 / 1 ブロック 12 字

### (1) 欠陥の性質

genome の `patterns["image-only"].rules` は `max 6-8 text blocks per slide` / `each block short and independently readable` を持つ。前者は**範囲**であり、後者は**形容詞**である。どちらも機械検査にならない。範囲を契約へ写すと、実装者は上限 8 を採り、検査は 8 で書かれ、しかしその 8 が正しいかは誰も判断していない状態になる。

### (2) 裁定 — 確定値

`script-brief-C21.json` に `baked_text_discipline` を新設し、**そこを数値の唯一の正本**とする。

| 項目 | 確定値 | 単位 |
| --- | --- | --- |
| `blocks_per_image_max` | **6** | ブロック / 1 画像 |
| `chars_per_block_max` | **12** | 文字 (書記素単位) / 1 ブロック |

**ブロック数 6 の根拠。** genome の範囲 `6-8` の**下限**を採る。上限ではなく下限を採るのは、handout の画像がスライドより小さく描画されるためである — 参考画像はいずれも 1920x1080 のスライド 1 枚を占有するが、handout の挿絵は印刷単一 HTML のセクション内に収まる (R15)。線寸が半分になれば同じ字数でも可読性は落ちる。かつ下限を採ることで、本契約は genome の規則の**部分集合**であり続け、genome 側と矛盾しない (genome を満たさない値を handout が要求する状況が起きない)。参考画像の実測もこれを支持する: ブロック数が 8 を超えた 2 枚 (`slide-10` = 15 / `slide-11` = 13) がまさに文字の歪みを起こした 2 枚であり、範囲上限側は既に破綻の側にある。

**1 ブロック 12 字の根拠。** 参考のフラット正面図の実測 —「作れない」4 字 /「連携要件を言語化できない」12 字 /「ではどう量産するか？」10 字 /「AIが自動生成し人は微調整」12 字 — の最大値がそのまま 12 である。アイソメ群の見出しブロックは 25-33 字あるが、これは**スライドの見出し**であって handout では該当しない — handout の見出し・リード文は HTML 側 (C11) が持つ。したがって「見出しを焼き込めない字数」であることは欠陥ではなく、**HTML と画像の責務境界がそのまま字数上限として現れたもの**である。

**完全文を焼き込まないことの判定規則 (allowlist)。** 焼き込みブロックを裸の文字列で持たず、`{form, text}` のタグ付きオブジェクトにする。`form` は閉じた 3 語 `keyword` / `question` / `metric` のいずれか。各 form の許容形は次のとおりで、これ以外は書けない。

| form | 許容形 | 機械検査 |
| --- | --- | --- |
| `keyword` | 要点語・体言止め | `text` が文末記号 `。．.？?！!` と読点 `、` を 1 文字も含まない。12 字以下 |
| `question` | 短い問い | `text` の末尾が `か` または `？` のちょうど 1 つ。文末記号は末尾のもの以外に現れない。12 字以下 |
| `metric` | 数値強調 | `text` が数字 (半角/全角/漢数字) を 1 文字以上含み、文末記号を含まない。12 字以下 |

12 字以下かつ文末記号を持てない文字列で日本語の完全文を成立させることは実用上できない。**規則で禁じるのではなく、形で書けなくしている**点が要点である (P04-x-05 の「違反を表現不可能にする」)。

**数値強調は条件付き必須にする。** 「推奨か必須か」の二択ではなく、条件付きの不変条件に落とす。

- セクションの構成データが数値 (効果値・所要時間・件数・比率) を持つとき、その画像は `form: "metric"` のブロックを**ちょうど 1 件**持ち、その 1 件に `emphasis: "max"` (画像内で最大級の字面) を与える。0 件も 2 件以上も exit2。
- セクションが数値を持たないとき、`metric` ブロックは **0 件**でなければならない。
- `metric` ブロックの数字部分は、そのセクションの構成データに**逐語で存在する**こと。存在しない数字は exit2。

最後の 1 行が本質である。数値強調を無条件の推奨として置くと、生成側は「効果的に見える数字」を捏造する誘因を持つ。数字の出所を構成データに固定すれば、強調は「持っている数字を大きく描く」だけの操作になり、捏造が契約違反として落ちる。

### (3) 正本の位置と C11 との分離

- 数値の正本は `script-brief-C21.json` の `baked_text_discipline` **1 箇所**。C21 の事前検査が唯一の実行点である。
- `agent-brief-C05.json` は上限値の**数値リテラルを持たない**。C05 の規律は「要点語のみを焼く」「超過で差し戻されたら削るのではなく要点語へ言い換える」という質的規律に限り、閾値は C21 が持つ。受入検査 `AC9` で agent 本文に数値リテラルが 0 件であることを見る (P04-x-05 の `AC-C23-R22-61d` と同型)。
- **C11 の `text_limits` (C63 の 180 / 400 / 900) とは別系統**である。あちらは HTML 本文の折り畳み閾値であり、単位は「セクション本文の字数」。こちらは「画像内に焼く文字の量」で、単位も、writer も、失敗時の症状 (折り畳まれる / 文字が潰れる) も違う。同じキー名へ寄せない。この分離を `baked_text_discipline.not_c11_text_limits` に明記した。

---

## (c) style family 2 系統と決定論選択規則

### (1) 確定した 2 系統

| family | genome | 画風 |
| --- | --- | --- |
| `isometric-diorama` | `<SRG_ROOT>/vendor/assets/style-genome-kanagawa-comic-diagram.json` (既存・read-only) | アイソメ 30 度・ドットグリッド床・角丸プラットフォームタイル・紺 #0B2A55 アウトライン・kanagawa 系低彩度 |
| `flat-infographic-jp` | `plugins/guide-doc-generator/genomes/style-genome-flat-infographic-jp.json` (**新規・producer は `P05-x-04`**) | フラット正面図・クリーム地・濃緑支配色 + 橙アクセント・大きな数値強調・カード枠の前後対比・チェックリストと簡易バー |

### (2) 決定論選択規則 — 図解型からの全域写像

一次キーは**図解型**とし、閉じた列挙に対する全域写像を置く。C11 / C14 が持つ図解パターン語彙がそのまま定義域である。**表の左列に書くのは C14 `PATTERNS` の id そのもの**であり、日本語ラベルの英訳を id にしない。

| 図解型 | family | 理由 |
| --- | --- | --- |
| フロー (`flow`) | `isometric-diorama` | 工程の受け渡しは奥行きと連結で読む |
| サイクル (`cycle`) | `isometric-diorama` | 循環は場面タイルの連結で表す |
| 階層 (`hierarchy`) | `isometric-diorama` | 積層は 30 度の奥行きが最も読みやすい |
| 比較 (`compare`) | `flat-infographic-jp` | 量の比較はアイソメで面積が歪む |
| マトリクス (`matrix`) | `flat-infographic-jp` | 格子はアイソメで軸が斜行して読めない |
| 対比2択 (`versus`) | `flat-infographic-jp` | 導入前 / 導入後のカード対比が参考フラット図そのもの |
| 前後変化 (`before_after`) | `flat-infographic-jp` | genome の look が「カード枠で対比 (導入前/導入後)」を既に宣言している |
| たとえ (`analogy`) | `flat-infographic-jp` | 既知と未知の 1 対 1 対応は二項対比の一種であり、面で並べたときに読める |
| 数値の言い切り (`bignumber`) | `flat-infographic-jp` | genome の look が「大きな数値強調」を既に宣言している |

境界は「**奥行き・順序・連結を読む図はアイソメ、面積・格子・二項対比・数値の言い切りを読む図はフラット**」である。

> **訂正 (2026-08-23)** — 初版の表は左列に `comparison` / `binary-contrast` と書いていたが、これは日本語ラベルの英訳であって C14 の id (`compare` / `versus`) ではなかった。本文が「C11 / C14 が持つ図解パターン語彙がそのまま定義域」と述べているとおりへ id を揃え、後から C14 へ追加された 3 語も全域写像へ含めた。裁定の内容は変えていない。この線は genome 自身も引いている — `tableAndMatrixRules` と `nonApplicableTypes.precise-table-or-number` は、格子と精密な数値をアイソメから退避させよと述べている。本裁定はその退避先に「画風を変える」という第 3 の選択肢を与えたものであって、新しい原則を持ち込んでいない。

上書きと欠落の扱い:

- 構成データのセクションが `style_family` を明示したときはそれが勝つ (値は 2 語の閉じた allowlist)。
- 図解型を持たないセクションの画像は、`style_family` の**明示が必須**。既定へ落とさない。欠落は exit2。fallback を置かないのは `RESOLUTION-P04-x-05` 裁定 C と同じ理由で、無言の既定は「誰も適切さを判断していない画風」を出荷させるためである。

### (3) 用途種別 (C23 の語彙) を選択キーに入れなかった理由 — worker 裁量

`P04-x-07.md` は「用途種別と図解型から既定を引き」と書いていたが、**用途種別を選択キーから外した**。理由は先行裁定と正面から衝突するためである。

- 用途種別を C21 の選択表へ書くと、C23 の 8 語の語彙が C21 にも並ぶ。これは `RESOLUTION-P04-x-05` 裁定 C が根本原因と名指した形 —「同じ概念の被覆が 2 つの独立した列挙に分かれている」— そのものである。語彙が 9 語目を得たとき C21 の表は 8 行のままで、しかも catalog 検査は通る。
- 用途種別を入れるなら格納先は `preset_definitions[].image_style_family` (裁定 A / C と同じ、preset の内側へ入れて漏れを表現不可能にする形) でなければならないが、`script-brief-C23.json` は本 leaf の `produces` に無く、`acceptance_criterion` も C21 / C05 の 2 ファイルしか挙げていない。宣言外のファイルを書き換えるより、選択キーを 1 本に絞る方が安全かつ設計として正しい。
- 実質的な損失も無い。画風は「何を描くか (構造)」に従うべきで「資料の用途」には従わない。同じ比較図はレクチャーでも提案でも同じ画風が読みやすく、用途差はセクション構成 (preset) が既に吸収している。

用途種別を選択に関与させたくなった場合の拡張経路は `preset_definitions[].image_style_family` を必須キーとして足すことであり、そのときは C23 側の裁定 leaf を別に立てる。この経路を `image_style_families.future_extension` に記録した。

### (4) genome 供給が「再実装しない」に抵触しない根拠

`flat-infographic-jp` の genome ファイルを handout 側へ置くことは、`build-image-prompts.js --genome <path>` に**渡す設定値を供給すること**であって、プロンプト組み立ての再実装ではない。判定基準は AC-C21-1 が既に定義している — 禁じられているのは「プロンプト本文の組み立て・style genome の複製・画像生成 API 呼び出し」の 3 つである。

- **プロンプト本文の組み立てではない。** `slide-09-five-axes.prompt.md` の STYLE BIBLE preamble を見ると、`artStyle` / `palette` / `compositionRules` / `densityPreservation` / `notACopyTemplate` の文面は全て vendor script が genome から組み立てている。C21 はプロンプト文字列を 1 文字も書かない。
- **複製ではない。** `flat-infographic-jp` は kanagawa genome の写しではなく、SRG 同梱 genome に該当形が存在しない別の画風である。裁定 A/B/C が禁じたのは「同じ内容を 2 箇所に持つこと」であり、内容が異なる資産の追加はこれに当たらない。`isometric-diorama` 側は SRG 同梱ファイルを**参照するだけ**で複製しない (C21 の既存契約どおり `--genome` に SRG の絶対パスを渡す)。
- **API 呼び出しではない。** 委譲経路 (`build-image-prompts.js` → `generate-images-codex.js`) は 1 段も変わらない。

したがって `script-brief-C21.json` の `open_questions` にあった「genome を SRG 同梱固定にするか handout 側へ vendoring するか」は、**両方**で閉じる — アイソメは SRG 同梱を参照、フラットは handout 側に新規供給。この項目を解決済みへ書き換えた。

---

## (d) 平坦化退化の検査可能な代理指標

### (1) 画素判定を持ち込まない理由

genome の `degradationBan` は「平坦化・単純化 (小物の脱落・占有率の低下・ベタ塗りボックス化) が起きたら不合格」と述べる。これを生成画像の画素から判定する経路は採らない。

- 判定器が非決定論の出力を非決定論に判定する構図になり、閾値が Goodhart 化する (占有率 X% を満たすためだけの飾りが増える)。
- C21 は `stdlib_only: true` である。画素解析は画像ライブラリを要求し、C27 (標準ライブラリのみ) と正面から衝突する。
- 失敗したときの差し戻し先が「モデルの出力」になり、修正できる主体が存在しない。C21 の設計思想は「差し戻し先が handout の計画側だと分かる位置で落とす」(`algorithm[8]` の既存記述) であり、画素判定はこれに反する。

**判定は計画とプロンプトの側へ移す。** 退化は「計画が薄いときに起きる」という因果を前提に、計画の薄さを落とす。

### (2) 採用する代理指標

`script-brief-C21.json` に `degradation_proxy_checks` を新設し、`algorithm[8]` の事前検査へ 3 件、回収後検査へ 1 件を加えた。

1. **`densityLevel` 必須。** 各セクションが `low` / `medium` / `high` のいずれかを明示する。値域の正本は genome の `densityPreservation.densityLevels` のキー集合であり、C21 は 3 語を自前で列挙せず genome から読んで照合する (規則を書かず実装を読む — P04-x-05 の委譲原則)。欠落・値域外は exit2。
2. **`motifs` を 3 役の構造体にする。** 平坦な配列 `motifs: [...]` をやめ、`motifs: {platform, primary, props[]}` にする。`platform` と `primary` は必須の単一名、`props` は 1 件以上。genome の `richnessFloor` (「各シーンタイルは『プラットフォーム + 主モチーフ + 小物 1 点以上 + 影』を最低限持つ」) をそのままデータ形にしたものである。**これにより「空の角丸枠 + テキストだけ」の計画が書けなくなる** — 非空検査を足す (task-spec の選択肢) のではなく、空を表現できない形にした。影 (shadow) は `artStyle` が常時与えるため役に入れない。3 名は全て genome の `motifs[].name` の要素でなければならない (既存の部分集合検査を役ごとに適用)。C21 は SRG plan へ変換する際にこの 3 役を `platform` → `primary` → `props` の順に連結して従来どおりの `motifs[]` 配列を作る — **委譲先の入力契約は 1 バイトも変えない**。
3. **`adaptationTrace` 必須。** genome の `contentAdaptationRules.biasPrevention.traceRequirement` と `noveltyRule.biasGuard.trace` が要求する「主題語 → 選択 motif」の対応を、計画の必須フィールドにする。非空で、各エントリの motif 名が当該セクションの 3 役のいずれかと一致すること。根拠なき motif 選定がここで落ちる。
4. **回収後: meta の照合。** `<slug>.meta.json` の `densityLevel` と `motifs` が計画値と一致することを確認する。委譲先が値を落としていれば、プロンプトに密度指示が乗っていない証拠になる。

`richnessFloor` の文言をプロンプトへ毎回明記する件 (task-spec の選択肢) は **C21 の責務にしない**。`slide-09-five-axes.prompt.md` を実測したところ、`densityPreservation` の本文と `notACopyTemplate` は既に vendor script が genome から STYLE BIBLE preamble へ組み込んでいる。C21 がプロンプトへ文言を足すことは、まさに AC-C21-1 が禁じる「プロンプト本文の組み立て」に当たる。C21 がすべきなのは、vendor script が消費するフィールド (`densityLevel` / `motifs` / `layoutTemplate`) を計画に正しく載せることだけである。

生成後 meta の `diagramPrimitives` 非空検査 (task-spec の選択肢) は**採らない**。実測した 22 枚の meta.json にこのフィールドは 1 件も無い。genome の `noveltyRule` step 4 を読むと、`diagramPrimitives` は `semanticMapping` に無い概念を新規に描いたときだけ記録されるフィールドである。非空を必須にすると「毎回どこかで新規モチーフを発明しろ」という要求になり、genome が `biasPrevention.deterministicSelection` で確立した「候補リスト先頭から決定論的に選ぶ」と正面から矛盾する。**存在しないフィールドの非空を要求する検査は、常に赤いか、赤くしないための無駄な発明を誘発するかのどちらかにしかならない。**

---

## (e) セクション別内容適応の必須化

### (1) 裁定 — C05 の 4 段手順を required にする

genome の `contentAdaptationRules.notACopyTemplate` (「参照デッキの構図を丸写しせず、同じ画風で内容に合う構図・被写体を新規に組む。固定 = スタイル仕様、可変 = 図解の中身」) を、`agent-brief-C05.json` の `procedure` へ執筆規律として下ろした。C05 が `subject` / `diagram_structure` / `overlay_text` / `motifs` を書く手順は次の 4 段に固定される。

1. セクションの `goal` と `lead_line` から**主要概念と動詞**を抽出する (流れ / 蓄積 / 検証 / 比較 / 成長 / 問題 / 役割 / 自動化 / 判断 / 配布 / 循環 / 階層 / 時系列)。抽出語は `adaptation_trace` の左辺として記録する。
2. genome の `semanticMapping` で概念 → 具体物 motif を引く。該当が無ければ `noveltyRule.industryObjectTable` を引く。選び方は genome の `deterministicSelection` に従い「**候補リスト先頭から、この資料でまだ未使用のものを 1 つ**」。動詞の語彙も候補リストも C05 は自前で列挙せず、genome ファイルを読んで引く。
3. 内容の構造から図解型を選ぶ (`layoutSelectionByStructure`)。図解型が (c) の写像を通じて style family を決める。
4. 焼き込みは**要点語のみ**。`{form, text}` の 3 形式で書き、セクション本文の言い換えを焼かない。上限値は C21 の事前検査が正本であり、C05 は数値を持たない。

### (2) 全セクション同一構図の禁止を機械化する — 採用する

C21 の事前検査へ加える (task-spec の裁定点)。ただし多様性の割合や閾値は置かない。単一の閉じた条件にする。

> セクションが 2 件以上ある資料で、`(図解型, motifs.primary)` の組が**全セクションで同一**であってはならない。違反は exit2。

閾値を置かない理由は、閾値が Goodhart 化するからである (「7 割以上が異なること」は 3 割を機械的に散らせば通る)。一方「全部同じ」は退化の完全な証拠であり、正当な例外を持たない — 同じ構図で全セクションを描くなら、そもそもセクションごとに画像を持つ意味が無い。genome の `biasGuard.usageBudgetHint` (同一 motif が 6 回超で warn) は 20 枚のデッキを前提とした目安であり、セクション数が 4-8 件の handout へそのまま持ち込むと機能しない。件数に依存しない条件を選んだ。

`props` の重複は許す。小物は一貫性のために再利用されるべきもので、`platform` と `primary` と図解型が全て同一であることだけを退化とみなす。

---

## 派生した知見

**安全弁の実装を安全弁そのものと取り違えない。** (a) の欠陥は、R15 (印刷可用性) という正しい要件に対して「焼かない」という 1 つの実装を選び、それを契約へ固定したことにあった。要件の本体は「読めること」であり、`overlayText` が正本であればそれは満たされる。契約に書くべきは要件 (`overlayText` 必須) であって、要件を満たす手段の 1 つ (`overlay-only` 固定) ではない。これは P04-x-05 の「不変条件を書き、導出値を書かない」の変種で、今回は**導出値ではなく「手段」が契約に居座っていた**。

**検査を足す前に、違反を書けない形があるか探す。** (d) の task-spec は「`motifs[]` の非空検査を足すか」を問うていたが、答えは「足す」ではなく「役ごとの必須キーにする」だった。非空検査は `motifs: ["speech-label"]` (ラベルだけの平坦図) を通してしまう。3 役の構造体は同じことを検査 0 件で達成する。P04-x-05 が `granularity_defaults` を preset の内側へ移して被覆漏れを消したのと同じ操作を、配列 → 構造体の方向で行った。

**存在しないものを検査に使わない。** (d) で `diagramPrimitives` の非空を退けた根拠は、実測 22 枚に 1 件も無かったことである。仕様書の記述だけを読んで検査を設計すると、常に赤いゲートか、ゲートを緑にするためだけの歪んだ生成物を作る。代理指標は、実在の出力に現れるフィールドから選ぶ。

---

## 反映先ブリーフと変更したキー

### `briefs/script-brief-C21.json`

| キー | 変更 |
| --- | --- |
| `purpose` | 画風 2 系統と焼き込み規律の検査点であることを追記 |
| `argv[--image-plan].description` | 計画が持つフィールドを裁定後の形へ (`baked_text[]` / `motifs{3役}` / `density_level` / `adaptation_trace` / `style_family` / `text_policy`) |
| `dependencies.reads` | handout 側 genome ディレクトリ (`plugins/guide-doc-generator/genomes/`) を追加 |
| `algorithm[2]` | 必須キー検査を裁定後のフィールド集合へ |
| `algorithm[7]` | `textPolicy="overlay-only"` 固定を撤回し `baked-with-overlay` 既定へ。`densityLevel` / `layoutTemplate` / `motifs` の 3 役連結 / `bakedText` の写像 / style family → genome パス解決を追記 |
| `algorithm[8]` | 事前検査へ (a)(b)(d)(e) の各項を追加 |
| `algorithm[9]` | `--genome` に渡すパスを family から解決する形へ |
| `algorithm[14]` | 回収後の meta 照合 (`densityLevel` / `motifs`) を追加 |
| `baked_text_discipline` | **新規**。数値の唯一の正本 (6 / 12)、3 form の allowlist、`metric` の条件付き必須、C11 `text_limits` との分離 |
| `image_style_families` | **新規**。2 系統の定義、図解型 6 語からの全域写像、上書き規則、再実装非該当の根拠、将来拡張経路 |
| `degradation_proxy_checks` | **新規**。4 指標と、画素判定・`diagramPrimitives` 非空を退けた理由 |
| `exit_codes.2` | 新しい契約違反 (overlayText 欠落 / 焼き込み規律違反 / 3 役欠落 / densityLevel 欠落 / 全セクション同一構図 / style_family 欠落) を追加 |
| `acceptance_checks` | `AC-C21-12`..`AC-C21-17` を追加 |
| `open_questions` | genome 固定 vs vendoring の項目 (旧 line 188) を解決済みの記述へ置換。C05 との突き合わせ項目に本裁定のフィールドを反映 |
| `requirements_covered` | R15 を追加 (印刷可用性を overlayText 必須で担保する側になったため) |

### `briefs/agent-brief-C05.json`

| キー | 変更 |
| --- | --- |
| `question_solved` | 画像計画の執筆が責務に含まれることを追記 |
| `input_contract.reads_files` | SRG 同梱 genome と handout 側 genome ディレクトリを追加 |
| `input_contract.must_not_assume` | (6) 参考デッキの構図の丸写し禁止、(7) genome 語彙の記憶復元禁止 を追加 |
| `output_contract.returns` | `image_plan[]` の要約を戻り値へ追加 |
| `boundary` | 画像計画を書く範囲と、書かない範囲 (プロンプト本文・genome 本体・画像生成) を明示 |
| `procedure[13]` | **新規**。セクション別内容適応の 4 段手順 (required) |
| `procedure[14]` | **新規**。焼き込み規律 (質的規律のみ。数値は C21 が正本) |
| `procedure[15]` | **新規**。style family の決定と、図解型が無いときの明示必須 |
| `requirements_covered` | R12 / R23 を追加 |
| `checklist_covered` | C17 を追加 (プロンプト再実装をしない側の遵守者) |
| `acceptance_checks` | `AC8` (4 段手順の明記) / `AC9` (数値リテラル 0 件) / `AC10` (全セクション同一構図でない) を追加 |
| `failure_modes` | 参考デッキ構図の丸写し / 本文の言い換えを焼く / 数値の捏造 / motif の根拠なき選定 を追加 |

### 本裁定が要求するが本 leaf の write_scope 外の追従

| 対象 | 内容 | 担当 |
| --- | --- | --- |
| `plugins/guide-doc-generator/genomes/style-genome-flat-infographic-jp.json` | `flat-infographic-jp` genome の実体化 (schemaVersion 1.3.0 互換) | `P05-x-04` |
| `briefs/script-brief-C11.json` | 画像が崩れたときに `overlayText` を表示できる markup を出すこと ((a) の安全弁の受け側) | **未割当** — C11 の owner leaf での追従が要る |
| `briefs/script-brief-C12.json` / handout-config schema | セクションの `style_family` / `text_policy` / `text_policy_reason` / 画像計画フィールドの schema 表現 | `P02-C12-01` 系の schema 確定 |
