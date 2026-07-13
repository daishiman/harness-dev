---
id: P04
phase_number: 4
phase_name: test-design
category: テスト
prev_phase: 3
next_phase: 5
status: 未実施
gate_type: tdd-red
entities_covered: [C01, C02, C03, C18, C19, C24, C25]
applicability:
  applicable: true
  reason: ""
---

# P04 — test-design (テスト設計)

## 目的
skill loop 系 component(C01 generate / C02 modify / C03 cross-deck-review)の受入基準を test-first に導出し、`feedback_contract` の inner/outer criteria として固定する。実装前は criteria が未達(Red)であることを確認する tdd-red gate。加えて report 構造化 (C9-C15)/UI・UX (C16-C19) 改善の受入 Red —— C19 render-report.js 単体・C24 積極評価 rubric・C25 機械チェック —— の設計も本 phase が担う (entities_covered に C19/C24/C25 を含む)。

## 背景
TDD の Red を先に立てることで、実装が「何を満たせば完了か」を purpose 由来で先に固定できる。汎用ゲートの言い換え(lint exit0 / 4 条件 PASS)に退化した criteria は purpose を一度も受入検証しないため、各 skill の goal/checklist 語彙由来であることを設計時に担保する(`criteria_purpose_traceability` が機械検出する退化を未然に防ぐ)。とりわけ output_mode 分岐の受入(slide=1メッセージ/report=読み物)を criteria に焼く。

## 前提条件
- P03 の design-gate を通過している。
- skill loop 系 component C01/C02/C03 の goal/checklist が inventory に確定済み。
- `feedback_contract.criteria` の SSOT 制約(inner/outer 各 1 件以上・id/verify_by enum)を参照できる。

## ドメイン知識
- inner/outer criteria: inner=生成時の自己検証観点(validate-output-mode / cross-deck-consistency 等)、outer=build 後の受入観点(mode 別成果物品質)。各 1 件以上が契約。
- Red = 実装前に criteria が未達であること(実装後に緑になることで criteria が実効だったと証明される)。
- purpose-traceability = criteria が各 skill の goal/checklist の語彙(output_mode / 視覚崩れ / 横断整合 等)を参照していること(汎用ゲート言い換え退化を `check-spec-frontmatter.py` が機械検出)。

## 成果物
- C01/C02/C03 の `feedback_contract.criteria`(inner+outer 各 1 件以上)が inventory に確定した状態。
- report 構造化 (C9-C14) の受入テストが Red で設計された状態 (下記)。

### report 構造化のテスト設計 (C10/C11/C12/C13・Red)

改善が「羅列でも破綻ゼロなら PASS」を塞げるよう、実装前に Red の受入観点を固定する。機械層 (C25) と意味層 (C24) を二層で設計する:

- **C25 validate-report-visual.py (機械・決定論)**: (i) markdown 表を含む fixture が `<table>` へ変換され `<br>` で潰れていない、(ii) フェンスドコードブロックが `<pre><code>` へ、番号リストが `<ol>` へ変換される、(iii) `section.narrative`(essence/approach/leverage) が非空、(iv) highlight/key-point 表現が render 出力に現れる、(v) placement.grid 指定時に図が段落末尾全幅でなく該当ゾーンへ配置される —— を検証する回帰を tests/test_validate_report_visual.py に Red で追加する。
- **C25 validate-report-visual.py (機械・第2次 1.2.0 追加の機械チェック (a)-(h)・Red)**: inventory C25.purpose の (a)-(h) と一対一の機械チェックを Red で tests/test_validate_report_visual.py へ追加する。(a) reportType別必須横断要素 (要約/次アクション/根拠/リスク/TL;DR+型別[技術ドキュメント=前提/用語/手順/既知問題、学習解説=目標/要点/演習]) の存在検出、(b) placement.grid/zones が render 結果へ live 反映 (figure が section 末尾全幅固定に退化していない=DOM 位置 vs placement 指定一致)、(c) 長尺 report での meta.throughLine 非空、(d) narrative 非空を section.role∈{analysis,argument} 条件に限定 (reference/procedure/summary は narrative 不要で category error 回避)、(e) block多様性の決定論閾値 (N段落超 report は distinct block type>=2 or narrative+>=1構造 block)、(f) doc-level highlight密度の緩い上限 (per-section cap に加え文書総量予算)、(g) inline highlight の非色属性 (weight/underline) 存在、(h) report読書CSS class 出力の存在 —— を各要素欠落 fixture で FAIL・充足 fixture で PASS になるよう Red で固定する。
- **C24 report-quality-reviewer (意味・RQ21-)**: 節内論理展開 (本質課題→解決→活用) の成立/block 構造多様性/要点強調の効き/図解の意味的配置/見出しごとの整形 を積極評価する rubric 次元を、羅列サンプル (現状出力相当) で FAIL・構造化サンプルで PASS になるよう設計する。
- **render-report.js (C19 tests_min≥80)**: 各 block レンダラの単体テスト (表/コード/番号リスト/小見出し/key-point/stat-tile/highlight/placement) を Red で用意する。

### report UI/UX のテスト設計 (C16-C19・Red)

- **C25 validate-report-visual.py (機械・決定論)**: screen layout/TOC+scrollspy/card minmax/print lifecycleのshapeに加え、essence-visualカバレッジを検査する。論理構造を展開する実質節(role∈{分析/主張/課題/解決/所見/影響}=_ESSENCE_REQUIRED_ROLES)が非none visual(visual.kind!=none)を1枚持たない場合はwarn(--strictでfail昇格)。非論理節(summary/reference/procedure等)はtext-first許容で非該当=vacuous PASS。CSS宣言値検査はshape層として残し、computed値はPlaywrightへ委譲する。
- **周回2 追加 (R4 HIGH是正・C25 print/狭画面 shape 検査 3種)**: 上記 (i)-(iii) は screen 新挙動の「存在」検査のみで print/狭画面を検査しない穴があったため、以下を Red で `tests/test_validate_report_visual.py` へ追加する。(iv) `@media print` ブロックの出力存在 + 最小実質条件 (print 内に `.report` 幅規則 [190mm 相当]>=1 と新 block [table/code] の page-break 制御規則を持つ。`@media print` を持たない fixture に加え空 print ブロックの fixture でも FAIL=空ブロック恒真化の封鎖)、(v) print 時の sidebar TOC 非適用/scrollspy 無効化の出力存在 (`@media print` 内での nav 非表示規則 or JS 側の `window.matchMedia('print')`/`beforeprint` 等の print ガードの実体が現れる。print ガードを欠く fixture では FAIL)、(vi) 狭画面 breakpoint (`@media (max-width: 900px)` 系・周回4 で degrade breakpoint を 720→900 追随) の出力存在 + 最小実質条件 (breakpoint 内にレイアウト変更規則>=1。breakpoint を欠く fixture に加え空 breakpoint の fixture でも FAIL=空ブロック恒真化の封鎖)。意味の適合 (degrade が読みやすいか) は C24 に残す二層分離を維持する。
- **周回3 追加 (C25 fail-open 封鎖・Red)**: report gate 用途で `--structure <report-structure.json>` を欠落させた呼び出しが exit2 (usage error) となる fixture を Red で `tests/test_validate_report_visual.py` へ追加する (--structure 無しで exit0/exit1 を返す=構造検査を素通しする fail-open を塞ぐ)。placement live 検査 (b) は DOM 順序/包含関係の構造 proxy に限る観点も併せて Red 化する。
- **C24 report-quality-reviewer (意味・RQ)**: ナビゲーション成立/密度バランス/図解適合 の 3 rubric 次元を、現行実装相当のサンプル (190mm 流用 screen/静的 TOC/過大タイポ/装飾図表) で FAIL・改善後サンプルで PASS になるよう設計する。**周回2 追加 (R4 HIGH是正)**: 「print/狭画面 degrade の成立」rubric 次元を追加し、print 出力サンプル(sticky TOC/scrollspy が紙面に残存)で FAIL・print 温存サンプルで PASS、狭画面インライン TOC が探索性を損なうサンプルで FAIL・graceful degrade サンプルで PASS になるよう設計する。
- **render-report.js (C19 tests_min≥80)**: screen/print 二層 CSS 出力・sticky TOC マークアップ+scrollspy JS 出力・タイポスケール変数の単体テストを Red で用意する。周回2 追加: `@media print` ブロック内で TOC 非表示/scrollspy 無効化が出力されることの単体テストを Red で追加する。
- **Playwright computed/runtime Red**: 899/900/901/1024/1366/1600px+printでcomputed本文16-18px/line-height比/title-body比、card最小幅と横overflow、初期hash/TOC click/manual scroll/font-ready/historyのtarget-active一致、beforeprint→afterprint復帰をassertする。現行21.84px・hashずれfixtureはFAIL。
- **C18 producer Red**: 同一本文から論理構造→図種の写像(essence-visual)→visual.kind→placementの順を出力し、論理節(分析/主張/課題/解決/所見/影響)へ非none visualを割り当てる。装飾図解と図解すべき論理節でのvisual省略の両方をFAILにするprompt fixtureを追加する。

## スコープ外
- criteria を満たす実装(P05)。
- harness カバレッジの設計・実行(P06・kind 別観点はそちらで扱う)。
- 非 skill component(sub-agent/hook/command/script)の受入(output_contract ベースで P07 が判定)。

## 完了チェックリスト
- [ ] 3 skill の criteria が purpose 由来で inner/outer を各 1 件以上持つ(汎用ゲート言い換えに退化していない)。
- [ ] C01 は「slide=1メッセージ/report=1項目1ビジュアルで視覚崩れ0の生成後評価 PASS」、C02 は「指定箇所のみ修正で非対象不変・再評価崩れ0」、C03 は「既知の不整合を全件検出」を outer criterion に持つ。
- [ ] 実装前は criteria が未達(Red)であることが確認できる。
- [ ] report 構造化の受入テスト (C25 機械チェック / C24 積極評価 RQ21- / render-report.js block 単体) が Red で設計され、羅列サンプルで FAIL・構造化サンプルで PASS になる観点が固定されている。
- [ ] report UI/UX の受入テスト (C25 screen レイアウト/TOC+scrollspy/essence-visual カバレッジ[論理節の visual.kind 非none]検査・C24 ナビゲーション成立/密度バランス/図解適合・render-report.js screen/print/TOC/タイポ単体) が Red で設計され、現行実装相当サンプルで FAIL・改善後サンプルで PASS になる観点が固定されている。
- [ ] (周回2 追加・R4 HIGH是正) report UI/UX の print/狭画面非退行受入テスト (C25 の `@media print` 出力存在/print時TOC・scrollspy無効化出力存在/狭画面breakpoint出力存在の3種・C24 の print/狭画面degrade成立rubric) が Red で設計され、screen 新挙動のみを検査し print/狭画面を見逃す fixture では FAIL、print/狭画面が正しく非退行する fixture では PASS になる観点が固定されている。

## 参照情報
- `prompts/R3-emit-specs.md` §2.2(criteria の purpose-traceability・test-first 導出)。
- report 構造化テストの要件正本 = P01「改善要件」節、設計正本 = P02「report 構造化設計」節。
- 対象 component C01(生成)/ C02(修正)/ C03(横断レビュー) + report 構造化は C19/C24/C25。
- 後続 P05(implementation)。
