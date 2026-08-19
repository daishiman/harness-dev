# RESOLUTION R25 — 改善サイクル REQ-1〜REQ-7 (goal-spec C67-C73)

- 起点: `plugin-plans/guide-doc-generator/improvement/improvement-handoff.json` の
  findings 7 件 (`improvement/findings-2026-08-18.json`)
- 影響コンポーネント: C01 / C05 / C11 / C12 / C14 / C19 / C20 / C21 / C22 / C23
- 確定値の正本 (再解釈も丸めもせず焼く):
  - `improvement/diagram-gate-decision.json` → REQ-2(b) (**2026-08-18 追補で superseded。
    下記「2026-08-18 追補」節と `improvement/visual-per-section-decision.json` を参照**)
  - `improvement/output-naming-decision.json` → REQ-6
  - `improvement/text-length-gate-decision.json` → REQ-7
- 更新した plan 側正本: `briefs/config/handout-visual-policy.json`
  (`thresholds.min_diagrams_per_main_section` / `thresholds.min_images_per_main_section` (新設) /
  `draft_first.skipped_in_draft` / `draft_first.granularity_anchor` (上限ではなく下限ガイドライン) /
  `draft_first.wait_time_scales_with_main_sections` (新設) / 新設 `sentence` 節 /
  `opening.hero_fields.lead` と `goal_chips` / `content_selection.enforced_by`)
- 最優先: REQ-7。利用者原文 (2026-08-18)「文章が長ったらしく何行も続くのは絶対に
  防いでほしい。資料として見にくいから」。長文系の検査は全て error とし、exit 0 で
  通る経路を残さない。

## D1. hero へ lead / goal_chips を追加する (REQ-1 / C67・C12・C11)

`render-handout.py:1944-1957` は既に `lead` / `goal_chips` を描画しているが、
`schemas/handout-config.schema.json` が `additionalProperties:false` でこの 2 キーを
拒み `E-KEY-UNKNOWN` になっていた。作り直さず schema 側の欠落を埋める。

- `document_level_fields` (C12 の `config_schema`) へ `lead` (string, 1 行の宣言,
  `properties.lead.maxLength` は警告閾値 `handout-visual-policy.json#opening.hero_fields.max_chars.lead=40`
  と同じ秩序、schema 上の実体上限は既存 `lead_line` 相当の 80 に置く) と `goal_chips`
  (array of string, `handout-visual-policy.json#opening.hero_fields.goal_chips.max_count=4`) を追加する。
- 文字数・件数の上限そのものは script へ焼かず `handout-visual-policy.json` を正本にする
  (`opening.hero_fields.max_chars.lead` と `opening.hero_fields.goal_chips`)。
- `hero_total.counted_fields` は既に `lead` / `goal_chips` を含めて用意済みだった
  (実装が追従していなかっただけ)。

## D2. 図解密度の下限を warning から error へ昇格する (REQ-2(b) / C68・C12) — **2026-08-18 追補で判定単位を訂正 (下記参照)**

正本は当初 `improvement/diagram-gate-decision.json`。`thresholds.min_diagrams_per_main_sections`
を `value=0.4 / level=error / floor=2` へ更新した (`required = max(floor, ceil(main_count*value))`)。
0.6 のまま error 化すると参照資料 (main_count=7, actual=3 → required=5) が不合格になる
ため、value 自体も引き下げる、という総量比の設計だった。**この総量比の設計は
2026-08-18 追補 (下記「2026-08-18 追補」節) で superseded となり、main セクション単位の
下限 (`min_diagrams_per_main_section=1`) へ置き換わった。0 図解の構成データ
(`examples/minimal-config.json` 等) は新旧いずれの設計でも exit0 で通らない点は変わらない。**

## D3. DIAGRAM を全 8 プリセットの主要セクションへ配線する (REQ-2(a) / C68・C23) — **2026-08-18 追補で被覆範囲を訂正 (下記参照)**

正本データは `config/handout-purposes.json` (C23 が唯一の正本)。plan 側の写しは
`briefs/script-brief-C23.json` の `section_order` サンプル。**当初は「8 プリセット全てで
main セクションの `recommended_parts` に DIAGRAM を最低 1 件配線し `grep -c "DIAGRAM"`
がプリセットごとに 1 以上になれば足りる」というプリセット単位の被覆だったが、
2026-08-18 追補により main セクション単位 (全 `section_order` 要素に 1 件以上) へ
訂正された。** DIAGRAM のパターンは `handout-visual-policy.json#diagram_patterns_by_intent`
とセクションの意図から個別に選び、同一プリセット内で単調に同じパターンを使い回さない。
実データの書き換えは P05-x-03 (config/ の唯一の producer) の実装作業であり、本
resolution は要件と検証条件を確定するに留める。検証は D2 の閾値と対で C12 が行う。

## D4. srg_images を第1稿スキップから外す (REQ-3(a)(b) / C69・C21・C23) — **2026-08-18 追補で被覆範囲を訂正 (下記参照)**

`draft_first.skipped_in_draft.srg_images` を削除した (`handout-visual-policy.json`)。
待ち時間増は利用者が受け入れ済みであり、理由は `skipped_in_draft.why_srg_images_no_longer_skipped`
へ明記した。IMG (role=screenshot は実画面のあるセクション、role=illustration は
概念・人物のセクション) を**当初は「lecture 以外の 7 プリセット」へ配線する方針だったが、
2026-08-18 追補により lecture を含む全 8 プリセットの全 main セクションへ配線する方針へ
訂正された** (D3 と同じく実データは `config/handout-purposes.json`、C23 の担当)。screenshot
役の素材が無いセクションは illustration へ fallback し (`improvement/visual-per-section-decision.json#role_split.fallback`)、
この fallback 手続きは C01 の R3-render (判定と切替) と C13 (素材有無の検査のみ、role 意味論には
関与しない) の責務分担として `skill-brief-C01.json` / `script-brief-C13.json` へ明記する。
`assets[].role` enum (C12 の `config_schema`) へ `illustration` を追加する。C21
(srg-image-bridge.py) の第1稿経路起動を `run-handout-build` (C01) の R3-render 手順書と
SKILL.md の完了チェックリストへ反映する。

## D5. 全 doc_type に冒頭の概観セクションを必須化する (REQ-4 / C70・C12・C23)

`section_kind` を 3 型へ集約し `config/handout-sections.json` (owner C12) へ追加する:

| section_kind | 対象 doc_type | 制約 | 器 |
|---|---|---|---|
| `timeline` | lecture / agenda / study-plan | 項目 ≤5・duration 必須・手順詳細禁止 | B03 + DIAGRAM(flow) |
| `map` | guide / onboarding / study-notes | 時系列を持たない章立て地図 | B08 + DIAGRAM(hierarchy) |
| `thesis` | report / proposal | 要点 3 件を先に置く | B07 + DIAGRAM(compare) |

各 doc_type の最初の main セクションがこのいずれかであることを C12 が検査する
(新設 `E-OVERVIEW-SECTION-MISSING` または `E-OVERVIEW-SECTION-ORDER`)。実データの
`config/handout-purposes.json` `section_order[0]` への配線は C23 (P05-x-03 実装時)。

## D6. 1 セクション = 1 カードの構造化検査を上乗せする (REQ-5 / C71・C12・C20)

`render-handout.py:2143-2173` の描画契約 (section-card / section-label / section-num /
section-duration) は作り直さない。不足分のみ追加する。

- 所要時間または件数がラベルへ必ず載ることを C12 が検査する (`section.duration` が
  空のとき、件数 (`section.parts` 件数など) を代替表示することを保証する新設ルール)。
- `content_selection.prose_vs_list` を machine check へ昇格する
  (`handout-visual-policy.json#content_selection.enforced_by` を更新済み)。
  main セクションが list/table 系構造化部品を 1 件以上持つことを検査する
  (新設 `E-SECTION-NO-STRUCTURE`)。REQ-7 の `sentence.sentences_per_body`
  (`E-TEXT-PARAGRAPH`) と対で効かせる (`text-length-gate-decision.json#risk_and_impact.escape_valve`)。
- 往復契約 (C20 extract-handout-config.py の逆抽出) は破らない。C20 の抽出対象
  フィールド集合は変えず、C12 の schema 拡張 (D1/D4) と structural check (本項) が
  抽出可能なフィールドの範囲内で完結することを確認する。

## D7. 出力ディレクトリ命名を利用者指定書式へ揃える (REQ-6 / C72・C19・C12)

正本は `improvement/output-naming-decision.json`。

- **slug 正本を C19 の `derive_slug` (SLUG_FORBIDDEN = パス禁止文字のみ) に一本化する**。
  C12 (`validate-handout-config.py:334`) の ASCII 潰し正規化 (`re.sub(r"[^a-z0-9]+","-",text)`)
  を撤廃する。`subject_slug` の充填責務は C12 の N5 に残すが、規則の実装は C19 と
  同一関数を import するかロジックを移す (二重実装をしない)。
- **ディレクトリ名書式を `{date}_{slug}` にする** (例: `2026-08-18_KPI進捗管理の業務フロー`)。
  正本は `config/handout-output.json` の `dir_name_format` (C19 が唯一の producer/reader)。
  script へ書式文字列を焼かない。
- **`dir_token` (doc_type 分類語) をパスから外す**。索引メタデータ (manifest/index) 側へ
  残す。衝突 (同日同題別 doc_type) の扱いは C19 の既存衝突処理と整合させる。
- **大文字小文字を保つ**。`derive_slug` の小文字化を外す。`check_explicit_slug` は
  変更しない。
- **非日本語タイトルはそのまま許容し警告も出さない**。空になる場合のみ既存の
  `SLUG_FALLBACK_PREFIX + sha256[:8]` に落ちる挙動を維持する。
- 回帰: `title='KPI進捗管理の業務フロー' / doc_type=report` で日本語ディレクトリ名が
  出ることを新規テストで確認する。`tests/route-handout-output.py` を新書式へ追従させる。

## D8. 長文を完全に排除する (REQ-7 / C73・C12・最優先)

正本は `improvement/text-length-gate-decision.json`。全て error、exit 0 で通る経路を
残さない。`handout-visual-policy.json` へ新設した `sentence` 節と `thresholds` 更新を
正本とする。

1. `E-TEXT-OVERFLOW` の本文上限を detail_level 別 `overview=60 / standard=100 / detailed=160`
   へ引き下げる (正本: `assets/tokens/*.json` の `text_limits.block_body_max_chars_by_detail_level`。
   既定 `block_body_max_chars` も 100 へ揃える)。
2. `validate-handout-config.py:1977` の `report_overflow=not args.normalize` を廃し、
   `--normalize` の有無に関わらず `E-TEXT-OVERFLOW` を常に報告する。
3. `fold_section` (`text_length_fold` / CR-TEXT-FOLD) の折り畳み実行回数上限を全経路で
   0 にする。超過は `E-TEXT-FOLDED` (error)。B10 は `micro_copy.exempt_parts` のまま
   変更しない (免除規則自体は妥当。塞ぐのは fold 回数の側)。
4. 1 文の上限を 60 字とし、1 文でも超えたら `W-SENTENCE-LONG` (level=error) で落とす
   (旧: 45 字 × 3 件以上で warning)。
5. 本文 1 個あたりの文数上限を 3 文とし、超過は `E-TEXT-PARAGRAPH` (error)。
6. `validate-handout-config.py:72-73` の `LONG_SENTENCE_CHARS=45` / `LONG_SENTENCE_COUNT=3`
   を `config/handout-visual-policy.json` 新設 `sentence` 節 (`micro_copy` と同階層) へ
   移し、script 側は `FALLBACK_BODY_MAX_CHARS` と同じ扱いの fallback 定数へ降格する。
7. REQ-5(b) (D6) の構造化検査と組で検証する。

### examples/ と tests/ の予算移行 (副作用ではなく改善そのもの)

現行予算 (180/400/900) で書かれた `examples/` と `tests/` の構成データは新予算
(60/100/160) で確実に落ちる。これは new budget が正しく効いていることの証拠であり、
書き直しを phase-05 (実装) のタスクとして明示的に load する
(`task-specs/P05-x-13-examples-tests-rewrite.md` を新設)。特に「750 字 TEXT が
`--normalize` を exit0 で通る」現行の再現手順は、新予算では非 0 終了になることを
回帰テストとして残す。

## 2026-08-18 追補 — 判定単位を総量比から main セクション単位へ訂正する

利用者原文「この分量に絞る必要はないですよ。そのやりたいドキュメントの内容に合わせて、
この数とかっていうところを増やしたらいいですが、毎回やるべきなのは図解と画像、
イメージを作成するっていうところは、毎回セクションごとに追加しておいてほしいです。」

D2〜D4 で確定させた「資料全体の総量比 (`min_diagrams_per_main_sections=0.4・floor=2`)」
「IMG は lecture 以外の 7 プリセット限定」という設計は、この利用者追補指定と食い違う
(件数の絞り込みそのものは求められておらず、逆に「セクションごとに毎回」という粒度が
求められている)。確定値の正本を差し替える。

- 正本: `improvement/visual-per-section-decision.json` (旧 `improvement/diagram-gate-decision.json`
  は `_meta.status: "superseded"` を付けて履歴として残す)。
- `thresholds.min_diagrams_per_main_sections` (総量比) → `thresholds.min_diagrams_per_main_section`
  (main セクション単位。`value=1` / `level=error` / コード `W-DIAGRAM-FEW` 据え置き) へ差し替える。
- 新設 `thresholds.min_images_per_main_section` (`value=1` / `level=error` / コード新設
  `E-IMAGE-ABSENT`)。既存 `W-VISUAL-ABSENT` は視覚部品全般を集計する粗い検査であり
  IMG 単体の不在を検出できないため、この新コードで補う。
- C12 (`validate-handout-config.py`) の検査アルゴリズムは main セクションを 1 件ずつ
  走査し、DIAGRAM を欠くセクション・IMG を欠くセクションをそれぞれ列挙して error にする。
  旧実装の総量算出式 (`required = max(floor, ceil(main_count*value))`) は残さない。
- C23 の 8 プリセット全ての `section_order[]` 全要素 (`required` の真偽に関わらず) が
  DIAGRAM・IMG を最低 1 件ずつ持つよう配線する。「lecture 以外の 7 プリセット」という
  IMG の限定は撤回する。
- `handout-visual-policy.json#draft_first.granularity_anchor` は上限ではなく下限の
  目安である旨を明記し、`diagram_parts` フィールド (`[2,3]` という数量上限を含意していた)
  を削除する。main_sections / parts_per_section の超過を warning にしない。
- `draft_first.why` (または同等の説明フィールド) に、挿絵 (role=illustration) の生成
  待ち時間が main セクション数に比例して伸びること、生成対象が role=illustration の
  セクションに限られることを明記する。
- REQ-7 (D8・`text-length-gate-decision.json`) の文長ゲート値・`micro_copy` の文字数は
  この追補の対象外であり、一切変更しない。「件数 (節数・視覚部品数) の絞り込みは
  不要」という追補は文章の長さには適用されない。

## 却下した案

- **`W-SENTENCE-LONG` のコード名を `E-SENTENCE-LONG` へ改名する案**: 却下。
  `text-length-gate-decision.json#decision.sentence_gate.code` が明示的に旧コード名を
  維持したまま `level` だけを `error` にする方針を確定させているため、コード体系の
  慣例 (`W-` prefix) と実際の重大度 (`level` フィールド) を分離したまま踏襲する。
- **B10 を `micro_copy.exempt_parts` から外す案**: 却下。免除規則自体は妥当という
  決定に従い、逃げ道は fold 回数の上限 (`max_fold_count=0`) だけで塞ぐ。
- **REQ-6 の dir_token を完全廃止する案**: 却下。パスからは外すが索引メタデータには
  残す (分類情報としての価値を維持しつつ利用者指定書式を満たす)。
