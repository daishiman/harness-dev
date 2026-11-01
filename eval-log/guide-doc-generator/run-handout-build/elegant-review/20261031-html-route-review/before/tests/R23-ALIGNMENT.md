# R23-ALIGNMENT — RESOLUTION-R23 の裁定とテストの対応

leaf: `P04-x-08` / write_scope: `plugins/guide-doc-generator/tests/`
正本: `plugin-plans/guide-doc-generator/briefs/RESOLUTION-R23.md`、
`briefs/script-brief-C21.json` (`baked_text_discipline` / `image_style_families` /
`degradation_proxy_checks` / `algorithm` 3b・8b・9・14b)、`briefs/agent-brief-C05.json` (AC8-AC10)

この leaf は **実装を 1 行も書かない**。裁定を二値判定可能な赤へ落とすだけである。
緑にするのは `P05-C21-01` (再実装) と `P05-C05-01` (agent 定義) と `P05-x-04` (同梱 genome)。

## 1. 裁定 ↔ テストの 1:1 対応

| 裁定 | 固定した性質 | ファイル | 件数 |
|---|---|---|---|
| (a) `textPolicy` 既定 `baked-with-overlay` | 既定値・`bakedText` 非空・`overlayText` は policy に関わらず必須・`overlay-only` は `text_policy_reason` との対でのみ選べる・`overlay-only` 固定がソースに残っていない | `srg-image-bridge.py/test_r23_text_policy.py` | 16 |
| (b) 焼き込み量 (ブロック数 / 1 ブロック字数) と 3 形式 | 境界ちょうどは通り超過は exit2・字数は grapheme 単位・`keyword`/`question`/`metric` の閉じた allowlist・句点を含む完全文は拒否・`metric` は構成データに逐語で在る数値のときだけ 1 件 | `srg-image-bridge.py/test_r23_baked_text.py` | 29 |
| (c) style family 2 系統と図解型からの全域写像 | allowlist は 2 語・6 図解型の写像が全域で fallback 無し・明示上書きが勝つ・図解型も family も無いセクションは exit2・family ごとに `--genome` を分けて 2 回委譲・同梱 genome の欠落は skip でなく exit2 | `srg-image-bridge.py/test_r23_style_family.py` | 20 |
| (d) 平坦化の代理指標 4 件 | `density_level` 必須 (値域は genome)・`motifs` は `{platform, primary, props[]}` の 3 役で `props` は 1 件以上・`adaptation_trace` 必須・回収後 meta の drift は exit code を変えず開示。退けた検査 (画素解析 / `diagramPrimitives` 非空) を足し戻していないことも固定 | `srg-image-bridge.py/test_r23_degradation.py` | 34 (下記 (e) と共有) |
| (e) 同一構図の資料は拒否 | セクション 2 件以上で `(diagram_pattern, motifs.primary)` が全件同一なら exit2。閾値を置かない。1 件だけの資料は対象外。`props` の共有は許す | `srg-image-bridge.py/test_r23_degradation.py` (`UniformCompositionTest`) | 同上 |
| (a)-(e) の執筆側 (C05 AC8-AC10) | 内容適応 4 段が順番付きで required・丸写しと記憶書きの禁止・上限値 / motif 名 / 密度語彙 / layoutTemplate 名の写しが 0 件・画像計画フィールドの宣言 | `handout-content-architect/test_r23_image_planning.py` | 20 |

`AC-C21-12`〜`AC-C21-17` との対応表は `srg-image-bridge.py/README.md` の契約 id 表に追記した。

## 2. 正本を二重化しないための約束

| 値 | 正本 | テスト側の参照経路 |
|---|---|---|
| ブロック数上限 / 1 ブロック字数上限 | `script-brief-C21.json` の `baked_text_discipline` | `_harness.blocks_per_image_max()` / `chars_per_block_max()` の **1 箇所だけ**。テスト本文に数値リテラルは無い |
| 焼き込み 3 形式 | 同 `baked_text_discipline.forms` | `_harness.baked_forms()` |
| family 名と 6 図解型の写像 | 同 `image_style_families` | `_harness.image_style_families()` / `style_family_map()` |
| family → genome パス | 同 `families[].genome` (`<SRG_ROOT>` / `<HB_ROOT>` テンプレート) | `_harness.resolve_family_genome()` / `handout_genome_path()` |
| motif 名・密度語彙・layoutTemplate 名 | genome ファイル (SRG vendor と handout 同梱の 2 本) | `_harness.real_genome_motifs()` / `genome_density_levels()` / `find_key()` |
| 既定 `textPolicy` の文字列 | RESOLUTION-R23 (a) | `_r23_support.DEFAULT_TEXT_POLICY` の 1 箇所 (`test_plan_validation.py` もここを参照する) |

これを機械で守るために `test_r23_degradation.GenomeIsNotCopiedIntoTestsTest` が
「テスト側のファイルに genome の motif 名 / 密度語彙が literal で現れない」ことを検査する。

## 3. 同梱 genome (`P05-x-04`) の扱い

`plugins/guide-doc-generator/genomes/style-genome-flat-infographic-jp.json` は本 leaf の産出物ではない。
**存在しないことを前提に fail-closed の赤**として書いてある (存在チェックで skip しない)。

- `test_r23_style_family.HandoutGenomePresenceTest` — 実在・JSON である・motif 語彙を持つ・
  密度語彙を持つ・`schemaVersion` の系列が SRG genome と揃う (委譲先が食える形)。
- `_harness.install_handout_genome()` — 偽 HB root へ複製するときに実体が無ければ `fail` する。
- `test_r23_style_family.HandoutGenomeIsFailClosedTest` — flat family を使う計画で同梱 genome が
  無ければ exit2 であり、`srg-absent` の skip へ畳まない。使わない family の不在は阻害しない。

## 4. `DelegationOnlyTest` との無矛盾

R23 は「family ごとに genome を解決して `--genome` で渡す」を要求するので、
「genome を複製しない / プロンプト本文を組み立てない」検査と衝突しうる。実測で確認した。

- `test_source_invariants.DelegationOnlyTest` は 9 件、`test_source_invariants.py` 全体で 23 件が
  **全緑のまま**であり、本 leaf は同ファイルを 1 行も変更していない。
- 追加テストが要求するのは **パスの解決と受け渡し**だけで、genome の読み出し内容を
  script が書き出す経路は要求していない (`test_no_genome_copy` と両立する)。
- `test_r23_text_policy.DefaultPolicyTest.test_overlay_only_is_not_pinned_in_the_source` は
  ソースからの文字列固定の除去を求めるもので、`DelegationOnlyTest` の禁止語 (`promptSuffix` /
  `negativePrompt` / `artStyle` / `base64` / `openai`) を 1 語も持ち込まない。
- `RejectedChecksStayRejectedTest` は PIL / numpy / cv2 / imghdr の import 0 件を要求し、
  `StdlibOnlyTest` を弱めるのではなく同じ向きに強める。

## 5. 共有 fixture を R23 後の形へ更新したこと (影響の申告)

既存 assert を弱めない代わりに、`_harness.section()` / `plan_payload()` が生成する計画を
R23 後の形 (3 役 `motifs` / `diagram_pattern` / `density_level` / `adaptation_trace` / `baked_text`) へ更新した。
結果として **既存ファイル側のテストも赤になる**。根本原因は 1 つで、現行実装が 3 役 `motifs` を
知らず `contract-violation: motif 'platform' が style の語彙に無い` で exit2 になることである。
これは「未実装の契約に触れた赤」であり fixture の不具合ではない。P05 の再実装で解ける。

`plan_payload()` は既定 2 セクションの `(diagram_pattern, motifs.primary)` を位置で振り分ける。
そうしないと既定 fixture 自身が裁定 (e) を踏み、他の検査点が全部その 1 件に飲まれる。

なお、現時点では exit2 を期待する赤テストの一部が **この共通原因で偶然通っている**
(判別力を持つのは P05 が (d) を実装した後)。判別力の要である「境界ちょうどは通る」側
(`assertNotExit2`) は全て赤で立っているので、実装が緩い方向へ倒れる余地は無い。

## 6. 撤回された正本の写しを差し替えた 2 件

| 対象 | before | after | 理由 |
|---|---|---|---|
| `srg-image-bridge.py/test_plan_validation.py::DeckPlanShapeTest::test_pattern_and_text_policy_are_fixed` | `self.assertEqual("overlay-only", slide.get("textPolicy"), ...)` | `self.assertEqual(R.DEFAULT_TEXT_POLICY, slide.get("textPolicy"), ...)` | R23 (a) が `overlay-only` 固定を撤回した。古い正本の写しを新しい正本 (`_r23_support` の単一定数) への参照へ差し替えたのであって、検査を消していない |
| `render-handout.py/test_r21_rendering.py::ThemeTokenSchemaTest::test_no_config_file_added_for_text_limits` | `config/*.json` のファイル名一覧を 3 本の literal で固定 | `config/*.json` のどの JSON にも `text_limits` 系のキーが無いこと + `assets/tokens/*.json` 側に `text_limits` が在ること | 下記 7 節 |

## 7. `test_no_config_file_added_for_text_limits` の書き換え (委任分)

C11 brief の `theme_token_schema_ownership.not_a_new_config_file` が守りたいのは
**「`text_limits` の住所はテーマトークンであって `config/` ではない」** という不変条件である。
旧テストはそれを **`config/` のファイル本数 = 3** という導出値で表現していた。
C19 契約に従って `P05-x-03` が `config/handout-output.json` を追加し、
`route-handout-output.py` 側のテストはそのファイルの実在を要求するため、
両者は同時に成立しない。導出値を契約に書いた欠陥なので、不変条件そのものへ置き換えた。

before:

```python
names = sorted(p.name for p in config_dir.glob("*.json"))
self.assertEqual(["handout-parts.json", "handout-purposes.json", "handout-sections.json"], names,
                 "config/ のデータファイルは 3 本 (P03 で固定)")
```

after:

```python
offenders = []
for path in sorted(config_dir.glob("*.json")):
    data = json.loads(path.read_text(encoding="utf-8"))
    for key in _keys_of(data):
        if key in TEXT_LIMIT_KEYS:
            offenders.append("%s:%s" % (path.name, key))
self.assertEqual([], offenders,
                 "text_limits 系の値が config/ 側に住んでいる (正本は assets/tokens/<theme>.json)")
```

対で `test_text_limits_live_in_the_theme_tokens` を追加し、`assets/tokens/*.json` の
少なくとも 1 本が `text_limits` を持つこと (= 住所が空でないこと) を要求する。
**緩めていない**: 旧テストは「4 本目のファイルを作った」ことしか検出できなかったが、
新テストは既存 3 本のどれかに `text_limits` を紛れ込ませても落ちる。
ファイル本数や固定リストは新たに書いていない。

## 8. 実測 (実装未変更の時点)

| コマンド | Ran | failures | errors |
|---|---|---|---|
| `python3 -m unittest discover -s plugins/guide-doc-generator/tests/srg-image-bridge.py -p 'test_*.py'` | 291 | 120 | 0 |
| `python3 -m unittest discover -s plugins/guide-doc-generator/tests/render-handout.py -p 'test_*.py'` | 110 | 142 (subTest 展開込み) | 20 |
| `python3 -m unittest discover -s plugins/guide-doc-generator/tests/handout-content-architect -p 'test_*.py'` | 49 | 44 | 0 |

`render-handout.py` の errors 20 件は全て `setUpClass` での
`build_target が未実装: plugins/guide-doc-generator/scripts/render-handout.py` であり、本 leaf の変更とは無関係
(`ThemeTokenSchemaTest` は 3 件全緑)。

## 9. gaps (ブリーフから確定できず、テストで断定していない点)

| what | why |
|---|---|
| grapheme の数え方 | ブリーフは「書記素」としか書いていない。標準ライブラリに grapheme cluster 分割が無いため、テストは「結合文字列で上限ちょうどが通る」ことだけを要求し、実装の分割アルゴリズムは指定していない |
| `metric` の「逐語で存在する数値」の照合範囲 | 構成データのどのフィールドを走査するかが未定義。テストはセクション本文に在る数値なら通り、無い数値なら exit2 になることだけを見る |
| meta drift の開示先 | `algorithm` 14b は「warn」とだけ書く。テストは exit code を変えないことと、stderr にスライドごとに現れることを要求した。書式は固定していない |
| family 混在時の `delegated_commands` の並び順 | 「2 行」とあるだけ。テストは集合として一致することだけを見る |
| 同梱 genome の `schemaVersion` 一致粒度 | 「委譲先が食えること」が要件。テストは major.minor の一致までに留めた |
| C05 AC10 の実行検査 | agent の実行は機械検査できないため、`handout-content-architect/` 側は宣言的検査に留め、実行側の判定は C21 の事前検査に委ねた |
