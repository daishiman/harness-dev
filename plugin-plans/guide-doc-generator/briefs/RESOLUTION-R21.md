# R21 (goal-spec C46〜C59) の設計反映記録

本ファイルは 2026-08-17 に研修フィードバックとして `goal-spec.json` へ追加された要件群 **R21 (checklist C46〜C59 の 14 項目)** を、23 component の設計正本 (`briefs/` + `component-inventory.json` + `index.md`) のどこへ焼いたかを 1 箇所に記録するものである。

読み方: 表の 1 行が要件 1 件に対応し、**責務を持つ component は必ず 1 つ**である。複数 component が関与する要件でも「その要件が満たされたか否かを決める側」を owner とし、他は副検査または描画側として本文に併記した。

対象ディレクトリ: `plugin-plans/guide-doc-generator/`
書き換えていないもの: `task-graph.json` / `task-specs/` / `evidence/` / `goal-spec.json` / `handoff-run-plugin-dev-plan.json`

**前提として守った 3 つの不変条件**

1. **component は 23 のまま**。R21 は全て既存 component への責務追加で解決し、24 個目を作っていない (`unresolved` は 0 件)。
2. **新機構を足していない**。用途別の差分は R20 のプリセット機構 (C23) に相乗りし、長文の折り畳みは既存部品 B10 アコーディオンを器に使い、所要時間は R20 のアジェンダ用途が既に要求する `section.duration` をそのまま単一の時間フィールドとして使う。
3. **RESOLUTION-P03.md が固定した SSOT を動かしていない**。部品 id は `config/handout-parts.json` (owner C11)、`section_kind` は `config/handout-sections.json` (writer C12)、用途語彙とプリセットは `script-brief-C23.json` の `vocabulary_ssot` / `preset_definitions` (owner C23)。R21 で足した部品 (B17) と種別 (6 件) はいずれもそのデータファイル側へ追加しており、ブリーフ散文へ id を列挙していない。

---

## 要件別の割り当て表

| 要件 id | 要件の要旨 | 責務を持つ component (1 つ) | スキーマ上の表現 (新設フィールド名など) | 検証手段 (script/test と、どの component のどの判定項目か) | 変更したファイル |
|---|---|---|---|---|---|
| C46 | 冒頭の流れは大きな流れだけ・項目数上限 (既定 5)・手順詳細を書かない | **C12** validate-handout-config.py | `section_kind="flow-overview"` と、その種別属性 `max_items: 5` / `forbid_row_detail: true` (数値は script でなくデータファイル側に持つ) | **script** — C12 の algorithm A9 (section_kind 追加検査)。エラーコード `E-SECTIONKIND-MAXITEMS` / `E-SECTIONKIND-ROWDETAIL`。受入検査 `AC-C12-R21-46` (閾値がハードコードでないことも検査する) | `briefs/config/handout-sections.json` / `briefs/script-brief-C12.json` |
| C47 | 冒頭の主題枠を 1〜2 件に絞り空にできない | **C12** | document 直下 `focus_theme: array<string>` (1..2、必須)。描画は C11 の `data-hb-field="focus_theme"` | **script** — C12 の `E-FOCUS-THEME` (0 件・3 件以上で FAIL)。受入検査 `AC-C12-R21-47` | `briefs/script-brief-C12.json` / `briefs/script-brief-C11.json` / `briefs/skill-brief-C01.json` |
| C48 | 本編セクションは goal か主題へ必ず紐づけ、運営連絡は付録へ隔離 | **C12** | `section.ties_to` (`goal` / `focus_theme:<idx>` / `target_task:<id>`)、`section.role` (`main`\|`appendix`)、`section_kind="logistics"` の `required_role: "appendix"` | **script** — C12 の `E-TIES-DANGLING` / `E-SECTION-UNTIED-GOAL` / `E-SECTION-ROLE-CONFLICT` / `E-APPENDIX-ORDER`。描画順の副検査は C22 `NAR-08` (`AC-C22-R21-48`) | `briefs/script-brief-C12.json` / `briefs/config/handout-sections.json` / `briefs/script-brief-C22.json` / `briefs/script-brief-C11.json` |
| C49 | `presentation_order` を必須化し `prior_knowledge` から決定論導出、明示上書き可 | **C12** | document 直下 `presentation_order: enum(demo_first\|explain_first)` (必須) + `provenance.presentation_order_source` (`explicit` \| `derived-from-prior-knowledge`)。導出規則は C12 の `r21_type_constraints.presentation_order_derivation` = **CR-PRESENTATION-ORDER** に 1 箇所だけ書く | **script** — C12 `--normalize` の N4b (plugin 全体で唯一の導出実行点)。受入検査 `AC-C12-R21-49` (`none`/`basic` → demo_first、`intermediate` → explain_first、明示指定は上書きされない) | `briefs/script-brief-C12.json` / `briefs/script-brief-C11.json` / `briefs/skill-brief-C01.json` / `briefs/agent-brief-C05.json` |
| C50 | 両モードで並びだけが変わり C44 の共有の型が保たれる | **C23** resolve-handout-preset.py | preset の許可キーへ `presentation_order_variants` を追加 (値は **自身の `section_order` の順列に限る**)。CLI は `--presentation-order`。C23 は導出せず確定値を受け取るだけ | **test** — C23 の `AC-C23-R21-50a`〜`50d`。50a が両モードの section 集合一致と `recommended_parts` / `required_document_fields` 同値を実測し、50b が順列違反を `E-PRESET-ORDER-NOT-PERMUTATION` で落とす | `briefs/script-brief-C23.json` |
| C51 | 機能名から始めず「成果 → 分解 → 用いる機能」の順 | **C12** | `section_kind="capability-explainer"` と `parts[].slot: outcome\|breakdown\|feature\|null` | **script** — C12 の `E-CAPABILITY-SLOT-MISSING` / `E-CAPABILITY-SLOT-ORDER` (`AC-C12-R21-51`)。描画テキスト面の副検査は C18 `LANG-07` (`AC-C18-R21-51a/b`) | `briefs/config/handout-sections.json` / `briefs/script-brief-C12.json` / `briefs/script-brief-C18.json` |
| C52 | 説明ブロックの文字数上限と超過分の既定折り畳み、上限はテーマで変更可 | **C12** | 上限は **テーマトークン** `assets/tokens/<theme>.json` の `text_limits.block_body_max_chars` (既定 400。スキーマ owner は C11)。折り畳み規則は C12 の **CR-TEXT-FOLD**。生成先は既存部品 **B10** (`open=false`、id は元 TEXT + `-cont`) | **script** — C12 `--normalize` の N10b と、非 normalize 実行の `E-TEXT-OVERFLOW`。受入検査 `AC-C12-R21-52` (テーマ値変更で挙動が変わること・2 回実行のバイト一致) | `briefs/script-brief-C12.json` / `briefs/script-brief-C11.json` |
| C53 | ハンズオン部品と先回り Q&A 枠、レクチャーでは両方必須 | **C23** | 部品カタログへ **B17 ハンズオン手順** (`steps[].{operation, expected, stuck_hint}` / `asset_id` / `live_demo`)、`section_kind` へ `handson` と `anticipated-qa` (器は既存の B10)。lecture プリセットの `section_order` に両セクションを固定 | **test** — C23 の `AC-C23-R21-53` (lecture が両種別を必ず含み、handson の推奨部品に B17 が入る)。構成データ側の必須検査は C12 `E-SECTIONKIND-HANDSON` / `anticipated-qa` の items 2 件以上 | `briefs/config/handout-parts.json` / `briefs/config/handout-sections.json` / `briefs/script-brief-C23.json` / `briefs/script-brief-C12.json` / `briefs/script-brief-C11.json` |
| C54 | 到達レベルの段階宣言 (Skill 化まで) と内容範囲の整合検査 | **C12** | document 直下 `attainment_level: enum(overview\|operable\|reproducible\|skill-authoring)` (順序つき) と `section.attainment_step` (同 enum) | **script** — C12 の `E-ATTAINMENT-OVERRUN` (宣言を超える step を持つ section) / `E-ATTAINMENT-UNREACHED` (宣言に届く section が 1 つも無い)。受入検査 `AC-C12-R21-54` | `briefs/script-brief-C12.json` / `briefs/script-brief-C11.json` / `briefs/skill-brief-C01.json` |
| C55 | 図表・グラフの欠落 (空 SVG / 空 data URI / 未解決 placeholder) の検出 | **C16** verify-handout-selfcontained.py | スキーマ追加なし (生成 HTML に対する検査項目の追加)。判定対象は `data-hb-part` が IMG / DIAGRAM の要素と `<figure>` | **test** — C16 の新設 detection **SC-09**。受入検査 `AC-C16-R21-55a`〜`55c`。55a は同一 HTML が SC-01..SC-04 を PASS することも併せて確認する | `briefs/script-brief-C16.json` |
| C56 | demo_first の最初の提示物は実画面。概念図・抽象説明の先行を禁止 | **C22** verify-handout-narrative.py | `assets[].role: screenshot\|figure\|photo` (必須・既定値なし) → C11 が `data-hb-asset-role` を出力。B17 の `live_demo: boolean` | **test** — C22 の新設 detection **NAR-07** (規則正本 **CR-DEMO1**)。受入検査 `AC-C22-R21-56a`〜`56c`。explain_first では PASS ではなく `SKIP` を出す | `briefs/script-brief-C22.json` / `briefs/script-brief-C12.json` / `briefs/script-brief-C11.json` |
| C57 | 「覚えていただきたいこと」と「覚えなくてよいこと」を対で必須 | **C12** | document 直下 `must_remember: array` (既定上限 2)・`must_remember_max: integer` (既定 2)・`no_need_to_remember: array`。lecture プリセットの `required_document_fields` に両方を宣言 | **script** — C12 の `E-REMEMBER-PAIR` (片方だけなら FAIL) / `E-REMEMBER-MAX`。受入検査 `AC-C12-R21-57`。描画で片方だけ出す経路が無いことは C11 `AC-C11-R21-b` | `briefs/script-brief-C12.json` / `briefs/script-brief-C23.json` / `briefs/script-brief-C11.json` / `briefs/skill-brief-C01.json` |
| C58 | 達成したい具体業務をヒアリング必須項目化し、各本編セクションの紐づけを検査 | **C01** run-handout-build (R1-elicit) | ヒアリング項目 `target_tasks: array<{id, label}>` (1 件以上必須)。項目定義の正本は `skill-brief-C01.json` の `hearing_required_items_r21`。構成データ表現は C12 の同名フィールドと `section.ties_to = target_task:<id>` | **script** — C12 の `E-TARGET-TASKS-EMPTY` / `E-SECTION-UNTIED-TASK`。受入検査 `AC-C12-R21-58` (全セクションが goal にだけ紐づく資料は不合格になることを確認する) | `briefs/skill-brief-C01.json` / `briefs/agent-brief-C05.json` / `briefs/script-brief-C12.json` / `briefs/script-brief-C11.json` |
| C59 | 各セクションの想定所要時間と、対話枠の必須化・下限割合の検査 | **C12** | `section.duration` (`^\d{1,3}分$` へ正規化。**時間の正本はこの 1 フィールドのみ**)、`section_kind="dialogue"` の `min_duration_share: 0.15` | **script** — C12 の `E-SECTIONKIND-DURATION-SHARE` / `E-DURATION-INCOMPLETE` / `E-TIMEBOX-SUM`。受入検査 `AC-C12-R21-59`。対話枠を lecture の必須セクションにするのは C23 (`AC-C23-R21-53` と同じ preset 定義) | `briefs/config/handout-sections.json` / `briefs/script-brief-C12.json` / `briefs/script-brief-C23.json` |

---

## 判断の根拠 (自明でないもの)

### presentation_order をヒアリング項目にせず導出にした理由と、導出規則を 1 箇所に置いた場所

デモ先行と説明先行はどちらが優れているかではなく聴き手の習熟度に依存する。したがって片方を型として固定できない。一方で、判断のためにヒアリング項目を 1 つ増やすと、質問を減らすという R21 の別の原則 (冒頭の情報過多を避ける・段取りを軽くする) と衝突する。そこで **R19 が既に取得している `prior_knowledge_level` から決定論導出**する形にした。

- 導出表: `none` → `demo_first` / `basic` → `demo_first` / `intermediate` → `explain_first`。
- `basic` を demo_first に倒したのは、「少し触ったことがある」層でも、実際に何ができるかの像が無いまま説明を聞くと離脱するという観測 (研修フィードバック) に従ったため。境界を 1 段引き上げると、explain_first が既定になる層が広がりすぎる。
- **導出の実行点は `script-brief-C12.json` の `r21_type_constraints.presentation_order_derivation` (規則 id: `CR-PRESENTATION-ORDER`) だけ**にした。C12 は構成データスキーマの正本所有者であり、既定値の充填を行う唯一の場所 (`--normalize`) を既に持っているので、既定値の規則をここに置くのが既存の分界と一致する。
- 他の component は導出しない。C23 は確定値を `--presentation-order` で受け取って並べ替えるだけ、C01 は利用者が自発的に述べたときだけ明示値を渡すだけ、C11 は `data-hb-presentation-order` として焼くだけ、C22 は読んで NAR-07 の適用可否を決めるだけである。この「読む側は複数・書く側は 1 つ」の形は、日付の既定充填 (C33〜C35) で既に採った形をそのまま延長したものである。
- 明示上書きは受け付ける。上書きされたかどうかは `provenance.presentation_order_source` に残るので、生成物だけを見て「既定で走ったのか指定されたのか」が判別できる。

### C57 を「対」で必須にした理由 (片方だけでは要件を満たさない)

覚える対象を 2 件に絞るだけでは認知負荷は下がらない。**明示しない限り、読み手は残り全部も覚える対象だと見なす**からである。「覚えなくてよいこと (その場で調べればよい / この資料を見返せば足りる)」を並べて初めて、絞り込みが読み手の側で成立する。したがって `must_remember` と `no_need_to_remember` は片方だけでは不備とし、`E-REMEMBER-PAIR` で落とす。

この「対」はヒアリング (C01)・構成データ (C12)・描画 (C11) の 3 層すべてで対のまま扱う。とくに C11 側で片方だけを描画する経路を設けないことをテスト (`AC-C11-R21-b`) で固定した。片側だけ描画できる経路が 1 つでもあると、スキーマが対を要求していても生成物では対が消えうるためである。

### C59 を「数値の下限割合」で表現した理由と、時間フィールドを二重に持たなかった方法

対話枠 (受講者の悩み・やりたいことを聞き出す時間) は、時間配分に載っていない限り「時間があれば聞く」枠に退化し、実際には必ず削られる。存在の必須化 (セクションがあること) だけでは、所要時間 0 分の名目上の枠で通ってしまう。だから **全体所要時間に占める下限割合という数値**で書いた。値 0.15 は script のコードではなく `config/handout-sections.json` の `dialogue.min_duration_share` に置いてあるので、運用しながら調整できる。

時間フィールドの二重化は次のように避けた。

- R20 のアジェンダ用途は既に「時間配分」を要求しており、その表現は B03 ステップ行の `rows[].time` だった。R21 でセクション所要時間が要るからといって、これとは別の時間フィールドを増やすと、2 つの値が食い違ったときにどちらが正かが決まらない。
- そこで **`section.duration` を時間の唯一の正本**とし、B03 の `rows[].time` は「そのセクション内部の内訳」に格下げした。内訳の総和はセクションの `duration` と一致しなければならない (`E-TIMEBOX-SUM`)。整合は一方向 (行 → セクション) にしか検査せず、`--normalize` も行時間からセクション時間を組み立てる方向にしか働かない (N7c)。
- 割合の分母は `document.duration` ではなく **`sections[].duration` の総和**とした。`document.duration` は表紙に出す表示用の値であり、セクションの積み上げと一致しない書き方 (「約 90 分」) を許しているためである。

### C56 を禁止として書いた理由

「実画面を先に出すことが望ましい」という推奨形にすると、資料のどこかに実画面が 1 枚あるだけで満たされてしまい、冒頭に概念図が居座る状態を落とせない。**「実画面より前に概念図解・フロー・特徴カード・120 字を超える説明段落を置いてはならない」という位置関係の禁止**にすると、機械が文書順だけで判定できる。規則本文は `script-brief-C22.json` の `canonical_rules.demo_first_rule` (`CR-DEMO1`) に 1 箇所だけ置き、C11 は判定せず属性を出すだけにした。

なお `explain_first` のときは NAR-07 を PASS にせず `SKIP` と出す。評価していないものを「通った」と表示すると、ゲートの意味が実態より強く見えてしまうためである (C16 の OUT-OF-SCOPE 節と同じ思想)。

### C55 を C16 に置いた理由 (R01 の検査を通過する欠陥クラス)

「生成したはずのグラフが表示されない」は、外部参照を 1 件も持たない。つまり R01 のゼロ外部参照検査 (SC-01〜SC-04) を **全て PASS したまま**発生する。「参照が外を向いていない」と「中身がある」は別の述語なので、独立した検出項目が要る。新規 component を作らず、生成 HTML の静的自己完結性を見る既存ゲート C16 の 9 番目の検出項目 (`SC-09`) として足した。C11 (図を作る側) には判定を置いていない — 作った本人に空判定を任せると欠落は検出されないためである。

### C52 を C11 ではなく C12 `--normalize` に置いた理由

折り畳みは「長い本文を分割して B10 を 1 件増やす」という**構成データの変換**である。これを C11 のレンダリング時に行うと、C20 (逆抽出) が生成 HTML から取り出した構成データと入力の構成データが一致しなくなり、round-trip 等価 (C20) が壊れる。C12 `--normalize` で行えば、正規化済み構成データの側に B10 が現れるので、round-trip の比較対象は変換後どうしとなり等価が保たれる。上限値をテーマトークンへ置いたのは、妥当な文字数が版面設計 (字送り・欄幅) に依存する値であり、テーマを足すたびにコードを触りたくないためである。

### C51 を 2 段構えにした理由

`parts[].slot` の順序検査 (C12) だけでは、並びが正しくても lead_line の書き出しが機能名のままという状態を落とせない。逆に、文言だけを見る検査では部品の並びを保証できない。構造は C12、文言は C18 という既存の分界 (C12 = スキーマ、C18 = 言語規約) をそのまま延長し、**判定の正本は C12、描画テキストの副検査が C18 `LANG-07`** とした。

### C50 で C44 を壊さずに済んだ仕組み

`presentation_order_variants` の値を **自身の `section_order` の順列に限定**した。順列であることを C23 の手順 4i が検査するので (`E-PRESET-ORDER-NOT-PERMUTATION`)、モードを切り替えてもセクションが増えたり消えたりすることが**データの形として不可能**になる。あわせて preset の許可キーを 5 つ (`section_order` / `recommended_parts` / `notes` / `presentation_order_variants` / `required_document_fields`) に固定し、それ以外のキーは `E-PRESET-FORBIDDEN-KEY` で落とす。`required_document_fields` は必須項目の追加しかできない (削除の表現を持たない) ので、こちらも共有の型を弱める方向へは働かない。

### C58 を C01 の責務とした理由

R19 が既に持つ読者像・前提知識・利用シーンは受講者の**属性**であって**達成目標**ではない。属性から目標は導けないので、`presentation_order` のような導出では解決できず、新しいヒアリング項目が要る。ヒアリングの責務所有者は C01 の `R1-elicit` なので、項目定義の正本をそこに置いた (`hearing_required_items_r21`)。C05 は受け取って構成データへ書く側であり、独自に項目を増やさない。機械検査は構成データ段の C12 が行う — skill そのものは script で検査できないが、「ヒアリングされなかった」状態は `target_tasks` の欠落として C12 が確実に落とすので、要件としては script で検証可能である。

---

## 未解決 (unresolved)

なし。C46〜C59 の 14 件すべてが既存 23 component のいずれかへ、検証手段つきで割り当たっている。
