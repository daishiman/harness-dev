# RESOLUTION-P04-x-05 — テスト実装が検出した設計正本の欠陥 5 件の裁定

leaf: `P04-x-05` / 対象正本: `briefs/script-brief-C15.json` / `script-brief-C22.json` / `script-brief-C23.json` / 日付: 2026-08-17

一次報告: `plugins/guide-doc-generator/tests/R22-AMENDMENT.md`「設計正本の矛盾・未定義」1-3 件目、および P04-x-02 / P04-C15-01 の gaps。
いずれも「テスト側で回避すると実装が誤った正本に従って固まる」性質のため、P05 の実装 leaf を解禁する前に正本側で決着させた。

| 件 | 欠陥の性質 | 裁定 | 反映先 |
| --- | --- | --- | --- |
| G-03 | 同一概念に矛盾する 2 つの判定が並立 | 絵文字判定の正本は C16 の `CR-EMOJI` のみ。C15 は module import で委譲 | `script-brief-C15.json` |
| G-04 | 同梱資産に producer 不在 | 資産専用の build leaf `P05-x-02` を新設 (反映済み・本書は根拠の記録) | `task-specs/P05-x-02.md` / `task-graph.json` |
| A | 保証対象を「キー数」と書いたための偽の矛盾 | 不変条件は閉じた allowlist であり個数は導出値。`granularity_defaults` を 6 番目の許可キーとする | `script-brief-C23.json` |
| B | 検出件数の写しが独立した契約に見えていた | ブリーフの `detections` 配列が固定順の唯一の正本。現時点で `NAR-01..10` | `script-brief-C22.json` |
| C | 既定表を preset の外へ別置きしたための被覆漏れ | 全語彙へ明示列挙。fallback は置かず、欠落を catalog 検査で落とす | `script-brief-C23.json` |

---

## G-03 — C15 の絵文字判定が C16 の禁じた方法を使っている

### (1) 欠陥の性質

`script-brief-C15.json` の algorithm 手順 4 が `U+1F300-1FAFF` / `U+2600-27BF` / `U+2190-21FF` / `U+FE0F` を直接ハードコードしていた。これは C16 の `CR-EMOJI` が明文で禁じた方法 (「Unicode ブロック丸ごとの denylist (U+2600-U+27BF 等) は用いない」) そのものである。

単なる方式の不一致ではなく、**判定結果が実際に食い違う**。`CR-EMOJI` は `✔ U+2714` を層 2 (直後に `U+FE0F` が続くときのみ違反) に置き、VS16 を伴わない `✔` を**通過させるべき文字**として名指している。C15 の denylist は同じ文字を `U+2600-27BF` の内側として弾く。したがって `title: "✔ 完了"` を持つアイコンセットは、C15 単体では exit 1、C16 の検査では PASS になる。同一 plugin 内で同じ概念に 2 つの矛盾する正本が存在していた。

欠陥の位置は「範囲の書き間違い」ではなく**正本の重複**にある。範囲を C16 と同じ二層集合へ書き直しても、2 箇所に同じ語彙が並ぶ限り片方だけが更新される日が来る。

### (2) 裁定

**絵文字判定の正本は C16 の `CR-EMOJI` (SC-05 の二層規則) 1 箇所とし、C15 は独自の Unicode 範囲を一切持たない。**

委譲の具体形を次のとおり確定した。

- C15 は手順 2 で解決した plugin 実体から `scripts/verify-handout-selfcontained.py` を `importlib.util.spec_from_file_location("hb_selfcontained", ...)` で読み込む (ファイル名にハイフンを含むため通常の import 文を使えない。C23 と同じ作法)。
- 呼ぶのは C16 の `module_api.exports` にある `scan_emoji(text) -> list[Violation]` のみ。C15 が渡すのは `icons[].name` と `icons[].title` の 2 種類の**素の文字列**であり、HTML ではない。`scan_emoji` の入力が文字列と定められているのはまさにこの用途のためで、新しい公開点を C16 へ足す必要は無い。
- 返り値が非空なら C15 は exit 1。stderr へは `detection_id=SC-05` / 該当 index / `Violation.codepoints` を**そのまま転記**し、判定文言を言い換えない。言い換えは規則の複製の第一歩になる。
- C16 が解決できない (不在・import 失敗) 場合は独自判定へ退避せず **exit 2** (fail-closed)。退避経路を持たせると、それが `CR-EMOJI` と乖離した第 2 の正本になる。判定できないときは判定したふりをしない。

C15 が前提にするのは「C16 が同一 plugin 内に存在すること」だけである。両者は既に `single_writer` で producer↔consumer (`couples_with`) として結ばれており、新しい依存の種類は増えない。

### (3) 根拠

- `CR-EMOJI` は `owner: C16 (単一正本)` を明示し `delegated_consumers` に「独自の denylist を持たない」と書いている。C15 がその制約の外にいた理由は無く、C10 が既にこの委譲形を採っている前例がある。
- C60 の SC-10 で確立した **denylist → allowlist の反転**と同じ構造 (`RESOLUTION-C60.md`)。ただし本件は反転そのものは C16 側で済んでおり、残っていたのは「反転前の写しを持った第 2 の実装」の除去である。C60 が「列挙は列挙から漏れたものを黙って通す」と述べたのに対し、本件は逆向きの害 — **ブロック列挙は列挙に紛れ込んだ正当な文字を黙って弾く** — が出た。日本語資料で `✔ ★ ■ ♪ ©` を使えなくする害は、絵文字を 1 つ見逃す害より大きい。
- 差し戻し距離の設計は維持する。生成後の C16 検査だけに頼ると原因箇所の特定が HTML 側になり差し戻しが遠くなるため、C15 が入口で落とす構造は残す。変えたのは「どこで落とすか」ではなく「誰の規則で落とすか」だけである。

### (4) 反映先ブリーフと変更したキー

`briefs/script-brief-C15.json`:

| キー | 変更 |
| --- | --- |
| `algorithm[4]` | Unicode 範囲列挙を削除。`scan_emoji` への委譲手順・転記内容・fail-closed の退避禁止・`✔ U+2714` が旧列挙で誤って弾かれていた事実を明記 |
| `exit_codes.1` | 「アイコン名に絵文字」→「アイコン名または title が C16 CR-EMOJI に違反」 |
| `dependencies.reads` | C16 のスクリプトファイルを追加 (module import のための読み込み) |
| `dependencies.invokes` | `[]` → C16 `scan_emoji(text)` の module import 呼び出し |
| `single_writer` | 絵文字判定だけは C15 が owner でないことを明記 |
| `acceptance_checks` | `AC-C15-3` を `scan_emoji` 経由へ変更。`AC-C15-3b` (`✔` VS16 なしが通ること)・`AC-C15-3c` (U+2699 U+FE0F = 層 2 + VS16 が落ちること)・`AC-C15-11` (script 本文にコードポイント列挙が 0 件) を追加 |
| `failure_modes` | 絵文字混入の behavior を委譲形へ。C16 の import 失敗を exit 2 とする case を追加 |

---

## G-04 — 同梱アセットに producer が存在しない

### (1) 欠陥の性質

`plugins/guide-doc-generator/assets/` 配下の資産 — R10 の jp-web-design 由来トークン、C15 が読むアイコンセット、C63 が数値の正本を置くテーマトークン、参照 v2 のマスコット SVG — が、どの task-spec の `produces` にも現れなかった (`grep -ln "assets/" task-specs/*.md` が 0 件)。

これは「C15 の `produces` に 1 行足し忘れた」という漏れではない。**consumer だけが列挙され producer が誰も名乗っていない資産クラスが丸ごと 1 つ存在した**という、依存グラフの構造的な穴である。C63 の確定値 (overview=180 / standard=400 / detailed=900) は `RESOLUTION-R22.md` に書かれているが、それを実体のファイルへ落とす作業に担当が無く、実装 leaf は「読む側」だけが作られる状態だった。

### (2) 裁定

**C15 の `produces` へ 1 行足すのではなく、同梱アセットを実体化する build leaf を 1 本立てる。** 実体は `task-specs/P05-x-02.md` として新設済みであり (task-spec の追加・`task-graph.json` への配線は本 leaf の実行時点で完了している)、本節はその根拠の記録である。

- `P05-x-02` の `write_scope` は `plugins/guide-doc-generator/assets/` で、`produces` は同ディレクトリ。`depends_on: ["P04-x-05"]` で本裁定の後に直列化し、`consumes` に `RESOLUTION-R22.md` と本書を持つ。
- `P05-C15-01` (`build-icon-sprite.py` の実装) は `consumes` へ `plugins/guide-doc-generator/assets/` を持ち、`produces` は script 1 本のみ。読む側と置く側の分離が task-spec の面でも成立している。

裁定方針の記述にあった leaf 名 `P05-x-01` は既存 id と衝突したため、実際の採番は `P05-x-02` になった。裁定の内容に変更は無い。

### (3) 根拠

- C15 に載せると **C11 が読むテーマトークンの producer 不在が残る**。アイコンセットだけが producer を得ても、C63 の数値の正本とマスコットは宙に浮いたままで、同じ欠陥が 2 回目に発見されるだけである。欠陥は「C15 の宣言漏れ」ではなく「vendoring 資産全体の producer 不在」なので、資産クラス単位で塞ぐのが正しい粒度になる。
- C15 の `write_scope` は単一スクリプトファイルであり、`produces` に `assets/` を書けば **write_scope と produces が乖離する**。宣言と実際の書き込み範囲がずれた leaf は、以後の write_scope 検査を無意味にする。
- 分離そのものに独立した価値がある。資産を置く leaf とそれを読む leaf を分けておくと、**テーマ差し替えがスクリプト変更を伴わないことが構造として保証される**。これは R10 (デザイン言語の vendoring) が求めている性質そのもので、依存グラフの整合のためだけの分割ではない。
- 数値の正本の一意性 (C63) が守られる。`P05-x-02` が `RESOLUTION-R22.md` を `consumes` に持ち、値の再解釈や丸めを禁じているため、`block_body_max_chars_by_detail_level` の値がスクリプト側へ写る経路が生まれない。

### (4) 反映先ブリーフと変更したキー

本件は task-graph 側の欠陥であり、ブリーフの変更を伴わない。反映先は `plugin-plans/guide-doc-generator/task-specs/P05-x-02.md` (新設) と `plugin-plans/guide-doc-generator/task-graph.json` (ノードとエッジ)、および `task-specs/P05-C15-01.md` の `consumes`。いずれも本 leaf の write_scope 外であり、本 leaf 実行前に反映済みである。

---

## A — C23 のプリセット鍵面の矛盾

### (1) 欠陥の性質

`script-brief-C23.json` の `invariant_vs_variant.structural_guarantee` が「preset オブジェクトの許容キーを 5 つに固定」と書き、R22 が `granularity_defaults` を 6 番目として `variant_per_preset` へ足した。既存テスト `test_r20_invariants.PresetKeySurfaceTest.test_preset_keys_are_within_allowed_five` と両立せず、実装は両方を同時に満たせない。

裁定にあたり先に確定すべきだったのは、**「ちょうど 5 個」が何を数えているか**である。結論は次のとおり。

- 数えている対象は **`preset_definitions` の要素 1 件 (= プリセット 1 件が返す構成データ) のトップレベルのキー面**であって、ブリーフ最上位のキー面ではない。ブリーフ最上位には `argv` / `algorithm` / `preset_definitions` など 26 のキーがあり、これを 5 個に固定する読みは元から成立しない。
- そのうえで、**5 という数は保証対象ではない**。`structural_guarantee` の本文自身が「catalog をどう書き換えても不変項を壊す語彙が存在しない」ことを保証の内容として述べており、そのために必要なのは (i) 許可キー集合が閉じていること (ii) 各許可キーの値空間が不変項 (C44) を壊す表現を持たないこと の 2 点である。個数はこの allowlist から**導かれる値**にすぎない。

つまり矛盾は実在の設計矛盾ではなく、**保証の内容ではなく保証の副産物 (個数) を保証文として書いたことによる偽の矛盾**だった。

### (2) 裁定

**`granularity_defaults` を preset オブジェクトの 6 番目の許可キーとして正式に認め、`structural_guarantee` を「閉じた allowlist」の言明へ書き換える。個数は allowlist からの導出値として記述し、契約として固定しない。**

あわせて `granularity_defaults` を**全 preset の必須キー**とし、値のキー集合を厳密に `{detail_level, evidence_depth}` に限定した (裁定 C と同じ手順 4(j) で検査する)。

### (3) 根拠

- **値空間の検査に合格している。** allowlist へキーを足してよい条件は「そのキーの値空間が不変項へ到達しないこと」である。`granularity_defaults` が表現できるのは 2 軸の既定値のみで、値域を狭めることも、利用者の明示指定を拒むことも、セクションの追加・削除も書けない。`CR-GRANULARITY-PRESET-DEFAULT-ONLY` (正本は C12) により、既定は上書き可能であることが型で保証されている。`presentation_order_variants` が順列に閉じ `required_document_fields` が追加専用であるのと同じ意味で、このキーも閉じている。
- **個数を契約にすると、無害な追加が保証違反に見える。** これは裁定 B と同一の欠陥クラスである — 導出値を写して固定した箇所は、写した時点の正本に凍結され、正本が動いても追従しない。B では検出件数、A ではキー数が同じ罠を踏んだ。
- **格納場所を preset の内側にした理由**は裁定 C と共通なのでそちらに記す。要点は、外側の中央表にすると「プリセットを 1 件足す」と「既定表へ 1 行足す」が別作業になり、後者の忘れが検査を通ってしまうことにある。実際 R22 の初版がその形で、`proposal` の被覆漏れ (裁定 C) を生んだ。A と C は同じ根から出ている。
- P04-x-04 が格納形を問わないモジュール API (`granularity_defaults(catalog, purpose)`) 経由の検査に留めた判断は正しく、その API はこの裁定でもそのまま有効である。テスト側は 1 行も書き換える必要がない。

### (4) 反映先ブリーフと変更したキー

`briefs/script-brief-C23.json`:

| キー | 変更 |
| --- | --- |
| `invariant_vs_variant.structural_guarantee` | 数えている対象が preset オブジェクトのキー面であることを明示。「ちょうど 5 個」→「閉じた allowlist (6 キー)」。個数が導出値であることと、`granularity_defaults` が不変項へ到達しない理由を追記 |
| `invariant_vs_variant.structural_guarantee_amendment_note` | 新規。旧文言が偽の矛盾を生んだ経緯と、テスト側の期待値も allowlist から導く形へ改める必要 (物理更新は P04-x-06) |
| `invariant_vs_variant.variant_per_preset` | `granularity_defaults` の行を「必須・2 キーちょうど・不変項へ到達しない」へ具体化 |
| `algorithm[4]` (g) | 許可集合へ `granularity_defaults` を追加。「件数ではなく集合が契約」と明記 |
| `acceptance_checks.AC-C23-R21-50d` | 期待値を allowlist から導く形へ。キー数の数値リテラルで固定しない旨を追記 |

---

## B — C22 の検出件数と CLI 契約の固定順

### (1) 欠陥の性質

`script-brief-C22.json` は R22 で `NAR-09` / `NAR-10` を得て `detections` が 10 件になったが、同じブリーフの `stdout` は固定順を `NAR-01..NAR-08` のままにしており、`AC-C22-01` も「8 行」と書いていた。テスト側では `test_cli_contract.py` と `_support.DETECTION_ORDER` が 8 件を `assertEqual` で固定している。実装は両方を同時に満たせない。

欠陥の所在は「更新漏れ」ではなく**件数を独立した契約として書き写したこと**にある。検出の集合は `detections` 配列が持っており、stdout の行数もテストの期待値も本来そこからの導出物である。写した瞬間に、写した時点の正本に凍結された第 2 の契約が生まれる。

### (2) 裁定

**ブリーフの `detections` 配列が正本であり、検出は 10 件。CLI 契約の固定順は `NAR-01..NAR-10` とする。**

- ブリーフ側で固定順が書かれていた 2 箇所 (`stdout` / `AC-C22-01`) を 10 件へ揃えた。あわせて `algorithm` に `NAR-09` / `NAR-10` の評価手順 (`8d`) が欠けていたのを補った — 出力行だけ 10 件にして評価手順が 8 件のままでは、実装が空行を出す形に落ちる。
- 再発防止として `canonical_rules.detection_order_contract` を新設し、「固定順は `detections` 配列の定義順そのものであり、件数は写さない」を規約として明文化した。
- 既存テストの 8 固定は**正本が 8 件だった時点の写し**であって受入基準の本体ではない。したがって 10 件への更新はテストの**緩和ではなく追従**である。緩和との区別は「検出 1 件あたりの判定内容が 1 つも弱まっていないか」で付き、本件では `NAR-01..08` の rule 本文に変更が無い。
- テスト実体 (`test_cli_contract.py` / `_support.DETECTION_ORDER`) の物理的更新は本 leaf の write_scope 外であり、`P04-x-06` が行う。

### (3) 根拠

- **正本の向きは設計 → テストである。** テストが 8 を固定していることは、正本を 8 に戻す理由にならない。`NAR-09` / `NAR-10` は C66 (宣言↔実態の一致) の唯一の実装点であり、これを落とすと R22 の要件が component のどこにも実装されない。
- **8 のまま実装すると、C66 が「無い」のではなく「あるふりをして無い」状態になる。** `granularity_declared_vs_actual` の `implemented_by_detections` は既に `NAR-09` / `NAR-10` を指しているため、detection を出さない実装はブリーフ内で自己矛盾する。
- **stdout の行数は開示の一部である。** C22 は `NAR-07 SKIP` を PASS と区別して出す設計を採っており、「評価していないことを黙らない」ことを契約にしている。10 件のうち 2 件を出力しないのは、この設計思想に真っ向から反する。
- 件数を導出値へ戻す規約 (`detection_order_contract`) は裁定 A と同一の一般則の適用である。

### (4) 反映先ブリーフと変更したキー

`briefs/script-brief-C22.json`:

| キー | 変更 |
| --- | --- |
| `stdout` | 固定順を `NAR-01..NAR-08` → `NAR-01..NAR-10` の 10 行ちょうど。`detections` 配列の定義順と一致することを明記 |
| `algorithm` | 手順 `8d` を追加 (`NAR-09` / `NAR-10` の評価。境界値は C11 のテーマトークンから read-only で引き数値を持たない。粒度属性の欠落は checked=0 の PASS にせず違反として計上)。手順 9 に行数の契約を追記 |
| `canonical_rules.detection_order_contract` | 新規。固定順は `detections` の定義順であり件数は写さない。裁定 B の経緯と根拠 |
| `acceptance_checks.AC-C22-01` | 「8 行」→「10 行ちょうど」。行数を `detections` の件数と突き合わせる形へ |
| `acceptance_checks.AC-C22-15` | 新規。stdout の detection id 列と `detections` の id 列が順序込みで一致すること。件数の数値リテラルで固定する検査を置かない |

テスト実体は本裁定では触っていない (`P04-x-06` の担当)。

---

## C — C64 の既定値が全語彙を覆っていない

### (1) 欠陥の性質

`granularity_defaults.defaults` が doc_type 7 種 (lecture / agenda / guide / onboarding / study-notes / study-plan / report) のみを持ち、語彙 slug の 8 番目 `proposal` に既定が無かった。C64 は「無回答でも既定を採用して停止しない」を要求するので、`proposal` を選んだ利用者が粒度の質問に無回答だと停止する。

被覆漏れそのものより重要なのは**なぜ漏れたか**である。R22 は既定値を `preset_definitions` の外側にある中央表として置いた。この形では「プリセットを 1 件足す」と「既定表へ 1 行足す」が別の作業になり、後者を忘れても catalog 検査は通る。`proposal` は R20 の時点で `preset_definitions` に存在していたが、R22 が既定表を新しく書き起こす際に 1 件落ちた。**同じ概念の被覆が 2 つの独立した列挙に分かれていること**が欠陥の本体である。

### (2) 裁定

**全語彙への明示列挙を採る。実行時の fallback 既定は置かない。** さらに、既定値を preset の内側 (`preset_definitions[].granularity_defaults`) へ移し、`granularity_defaults` を全 preset の必須キーとする。

- 手順 `4(f)` が既に「presets のキー集合と vocabulary の slug 集合の完全一致」を強制している。ここへ手順 `4(j)` (`granularity_defaults` の必須化) を加えると、**既定値を持たない語彙は catalog 検査を通過できない**。全語彙被覆が列挙の重複ではなく構造から出る。
- `proposal` の既定値は `detail_level: standard` / `evidence_depth: sourced` と定めた。提案資料は決裁者が読むもので、網羅的な詳細さより論点を絞った可読性が要る (detailed ではない)。一方その `section_order` は `options` (選択肢の比較) と `ask` (お願いしたいこと) を必須で持ち、比較の根拠と依頼の裏づけが辿れなければ判断できないため、根拠側は最も強い `sourced` を既定にする。
- モジュール API `granularity_defaults(catalog, purpose)` は全語彙で必ず値を返し、`None` を返す経路も fallback も持たない。未定義語彙のみ `UnknownPurposeError`。

### (3) 根拠

- **fallback は C64 の字面だけを満たす。** 未知の doc_type を `standard` / `none` へ落とせば確かに停止しないが、その既定がその用途に適切かどうかを誰も判断していない。C64 が要求しているのは「利用者を止めないこと」であって「設計者に判断させないこと」ではない。
- **R17 の種別語彙が将来増えたときの挙動が決定的な差になる。** fallback があると、新しく足した用途は無言で `standard` / `none` として生成され、欠陥は誰かが生成物を読むまで表面化しない。しかも `evidence_depth=none` の既定は C22 の `NAR-10` を vacuous に通すため、**品質ゲートも赤くならない**。fallback が無ければ、語彙追加の変更がそのまま `E-PRESET-GRANULARITY-MISSING` で落ち、既定値の決定が語彙追加と同じ作業の中で必ず起きる。停止する先を実行時から catalog 検査時へ移すのが正しい設計であり、これは C64 の「利用者は止めない」と両立する — catalog を編集しているのは利用者ではなく設計者だからである。
- **既定は制約ではないという性質を壊さない。** 必須にしたのは「既定が存在すること」であって「その値に従うこと」ではない。`why_defaults_not_constraints` が述べるとおり lecture で detailed を選ぶことも report で overview を選ぶことも valid であり、その性質に変更は無い。R21 の `presentation_order` で退けた型固定には当たらない。
- **裁定 A と同じ根**である。A が「キー数を写した」、C が「被覆を 2 箇所へ分けた」で、どちらも導出できるものを独立に持ったことによる。preset の内側へ入れる選択は、A で allowlist へ 1 キー足すことと引き換えに、C の再発経路を構造から消す取引になっている。

### (4) 反映先ブリーフと変更したキー

`briefs/script-brief-C23.json`:

| キー | 変更 |
| --- | --- |
| `preset_definitions[]` (8 件全て) | 各要素へ `granularity_defaults {detail_level, evidence_depth}` を追加。`proposal` = standard / sourced、他 7 件は R22 の確定値と同値 |
| `granularity_defaults.defaults.proposal` | 新規。standard / sourced と選定理由 |
| `granularity_defaults.rule` | 必須キーであること、モジュール API 名、`defaults` 表は説明用の写しであって第 2 の格納先ではないことを明記 |
| `granularity_defaults.storage_decision` | 新規。中央表を別置きしない理由と、`proposal` 漏れがその形から生じた経緯 |
| `granularity_defaults.coverage_guarantee` | 新規。fallback を置かない根拠 (R17 の語彙が増えたときの挙動と C64 の意図) |
| `granularity_defaults.defaults_order_note` | 新規。表の記載順は契約ではなく、語彙の順序の正本は `vocabulary_ssot.vocabulary` |
| `algorithm[4j]` | 新規。`granularity_defaults` の必須化・キー集合・値域照合 (enum の正本は C12、自前列挙をしない)・手順 4(f) との合わせ技で全語彙被覆が構造保証されること |
| `stderr` | `E-PRESET-GRANULARITY-MISSING` / `-KEYS` / `-VALUE` の 3 診断コードを追加 |
| `stdout` | `--purpose` の出力へ `granularity_defaults` を追加 |
| `algorithm[7]` | `--purpose` の合成対象へ `granularity_defaults` を追加。常に非空で出るため呼び出し側が有無を分岐しないこと |
| `vocabulary_ssot.consumer_contract.public_module_api` | `granularity_defaults(catalog, purpose)` を追加 (fallback も `None` 返しも持たない旨を含む) |
| `acceptance_checks` | `AC-C23-R22-61a`..`61d` を追加 (全 slug で値が返る / キー削除で exit 1 / 語彙追加だけでは通らない / script に既定値リテラルが 0 件) |

---

## 派生した知見 (一般化)

**契約に書いてよいのは不変条件であって、その導出値ではない。** 本 leaf の 5 件のうち 3 件 (A / B / C) は同一の失敗形をしていた。

| 件 | 本来の不変条件 | 契約に書かれていた導出値 | 起きたこと |
| --- | --- | --- | --- |
| A | preset のキー集合が閉じた allowlist であること | キーが「ちょうど 5 個」 | 無害なキー追加が保証違反に見え、テストと両立しなくなった |
| B | 固定順は `detections` の定義順であること | 出力が「8 行」 | 検出が 10 件になっても写しが 8 のまま凍結された |
| C | 全語彙が既定を持つこと | doc_type 7 種を並べた既定表 | 語彙が 8 件でも表は 7 件のままで、差分が誰にも見えなかった |

導出値は書いた瞬間に正本のスナップショットになり、正本が動いても追従しない。しかも**導出値の側が先に破綻するため、正本の正しい更新が「違反」に見える**。これが最も高くつく — 設計が正しく前進したときに限って赤くなるゲートは、いずれ「テストを緩めた」という誤った診断を招くか、正しい変更を差し戻させる。

対処は 2 つある。(i) 契約文を不変条件の言明として書き直し、個数や件数は「導出値であり現時点では N」と明記する。(ii) 検査側の期待値も正本から導く形にする (件数を `assertEqual` で書かず、正本の配列と突き合わせる)。今回は (i) を 3 件すべてに適用し、(ii) の物理的更新は `P04-x-06` へ渡した。

**同じ概念の被覆を 2 つの独立した列挙へ分けない。** C の根本原因は、語彙の列挙 (`vocabulary`) と既定値の列挙 (`defaults`) が別の場所にあり、片方だけを増やす操作が検査を通ったことだった。どちらか一方を他方の内側へ入れて「増やす操作が 1 つになる」形にすれば、漏れは書けなくなる。テストで被覆を確かめるより、被覆漏れを表現できないデータ形にする方が強い (C23 の `structural_guarantee` が元から述べていた原則であり、`granularity_defaults` だけがその原則の外に置かれていた)。

**判定規則の委譲は「同じ規則を書く」ではなく「同じ実装を呼ぶ」でなければならない。** G-03 では C15 と C16 が同じ概念に別の判定を持ち、しかも一方が他方の明文の禁止事項を踏んでいた。規則本文を複製する運用は、複製時点で正しくても差分が生じる。C16 が `module_api` を「C10 / C11 が再実装しないための単一実装の公開点」として設けていたのは正しく、C15 だけがその公開点を使っていなかった。委譲先が解決できないときに独自判定へ退避する設計は、退避経路を第 2 の正本にするので採らない (fail-closed)。
