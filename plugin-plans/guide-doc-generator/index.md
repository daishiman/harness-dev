---
id: IDX0
title: guide-doc-generator 開発計画 index (main)
shape_marker: task-graph-derived
plugin_meta:
  manifest:
    required: true
    path: .claude-plugin/plugin.json
    name_matches_folder: true
    no_unresolved_placeholders: true
    validate_plugin: true
  marketplace:
    default_personal: true
    policy:
      # 2026-08-18 に AVAILABLE へ反転 (裁定と根拠は phase-13-release.md の事前解決済み判断)。
      installation: AVAILABLE
      authentication: ON_USE
      category: Productivity
    cachebuster_for_update: true
  distribution:
    distributable: true
    bundles: [skills-full]
    marketplace: true
  pkg_contract:
    pkg: 002-008
  governance:
    runbook: required
  ci:
    workflow: governance-check
  ssot_dedup:
    lint: ssot-duplication
    references_config_assets: tracked
  feedback_deploy:
    deploy: run-skill-feedback
    enabled: true
    notion_sink:
      config_key: improvement-request
      schema_ref: doc/notion-schema/improvement-request.schema.json
      resolution: notion_config
    portability: vendored
  harness_eval:
    evals_json: EVALS.json
    mechanical: required
    llm_eval: required
---

# guide-doc-generator 開発計画 index (main)

> プラグイン構想「初心者・非エンジニア向けのレクチャー/導入ガイド資料を、外部依存ゼロの単一 HTML として決定論生成し、テンプレートとして反復配布する」を、人間可読な 13 フェーズのライフサイクル (本 index + phase-01..13.md) と、機械可読な buildable component 目録 (`component-inventory.json`) の 2 軸直交で計画したもの。
> ライフサイクル軸 (フェーズ) は宣言型のタスク仕様で primary deliverable。成果物実体軸 (component) は build routing・依存 DAG・品質機構を保持する唯一の SSOT。フェーズは component id を `entities_covered` で参照するだけで build_target を再記述しない (正規化)。

## 基本定義
- **プラグイン slug**: `guide-doc-generator` (plan_dir=`plugin-plans/guide-doc-generator/`・同一構想は常に同一出力先=再現性アンカー)。
- **最上位目的 (purpose)**: 初心者・非エンジニア向けレクチャー/導入ガイド資料を外部依存ゼロの単一 HTML として決定論的に生成し、テンプレートとして反復配布できるプラグインを作る。
- **仕様駆動 (大前提)**: 本計画は harness-creator 仕様を基に作成される (規律の焼き先=`harness-creator-spec-reflection.md` マトリクスの引用・独自流儀の発明禁止)。要件の正本は `goal-spec.json` の checklist (C1-C59。C46-C59 は 2026-08-17 に研修フィードバックとして追加された R21)、仕様書 (本 index + 13 phase) はその被覆であり、実装との乖離が出たら**仕様を先に更新**してから build へ戻す (spec-first)。
- **スコープ (含む)**: index + 13 フェーズ計画 + `component-inventory.json` の生成 (計画=L3 契約)。
- **スコープ (含まない)**: 実プラグイン/実コードの build (L4・後段 run-skill-create / run-build-skill へ委譲)、資料の中身そのものの執筆、PR/配布登録。

## ドメイン知識
- **2 軸直交**: ライフサイクル軸 (13 phase・人間可読) と成果物実体軸 (N=23 component・機械 SSOT) を二重に持たない。
- **component_kind (5 種)**: skill / sub-agent / slash-command / hook / script。同一 kind の複数実体はそれぞれ独立 component。
- **phase ≠ component**: 13 はフェーズ数の固定値、N=23 は buildable 実体数で独立に決まる。phase は `entities_covered: [C01, ...]` の id 参照のみで component に紐づく。
- **構成データ**: 資料の内容と部品選択を表現する JSON。本 plugin の単一の入力正本であり、レンダラ・検証器・逆抽出器・構成データ設計 agent が同一スキーマを共有する。
- **分界線 (本計画の中核)**: 「ヒアリング→構成データを書く」「読みやすさをレビューする」は LLM、「構成データ→単一 HTML」「生成物の検証」「出力先の解決」は決定論 script。レンダリング経路に LLM を挟むと同一入力からの再現性が原理的に失われ、機械ゲートが成立しない。
- **単一 HTML**: CSS/JS/画像/フォントを全て内包し外部 URL を参照しない 1 ファイル。素材は data URI で埋め込む。
- **部品カタログ**: 再利用部品の id 語彙は `config/handout-parts.json` (owner: C11 render-handout.py) ただ 1 箇所を正本とし、この index を含むどの文書も部品 id をここへ列挙しない (P03 Y-05)。構成データ側の宣言で部品を選択する。各部品は `section_scope` (in-section / document) を持ち、C18 LANG-06 の『具体部品』判定はこのフィールドで行う。
- **用途種別と語彙正本**: 資料の用途を表す語彙とプリセット定義は `config/handout-purposes.json` (owner: C23 resolve-handout-preset.py) ただ 1 箇所を正本とし、この index も含めて語彙をここへ列挙しない (P03 Y-06。旧記述にあった `一般配布資料=report` / `onboarding`・`guide` の対応づけは正本と食い違っていたため削除した — 正しくは `guide` が一般配布資料、`report` が報告資料である)。出力先の命名 (C19) と用途別プリセットの選択 (C05/C01/C12) の双方が、この 1 ファイルを C23 経由で参照する。語彙とプリセット定義は同一の宣言データファイルに置き、利用者の追加プリセットもそこへ書き足す。
- **主用途は 1 つ**: 用途をまたぐ資料 (勉強会兼アジェンダ 等) はプリセットの合成では表現しない。主用途を 1 つ選び、足りない要素はセクションの追加で補う。合成を許すとプリセットの組合せが増え、共有の型が保たれているかを検証できなくなる。
- **対話は既定経路であって唯一経路ではない**: 用途と内容のヒアリングが既定の入口だが、検証済みの構成データを直接渡す非対話経路も常に開けておく。塞ぐと逆抽出からの再生成と自動実行ができなくなる。
- **ゴールの連なり**: 資料全体のゴールから各セクションのゴールへ筋道が通っていること。目次からも各セクションのゴールが読み取れる状態を指す。導入一文と判断軸 (読み手を迷わせない書き出し) とは別の検証面として扱う。
- **fail-soft と fail-closed**: 資料の生成を止めてはいけない事象 (素材サイズ上限超過・画像生成委譲先の不在) は warning で継続、成果物の正しさに関わる事象 (外部参照混入・絵文字混入) は fail-closed。

## インフラ
- **実行環境**: スクリプトは Python 標準ライブラリのみ (.sh/.js 新規禁止・scripts 内 yaml import 禁止)。lint/スクリプト起動は repo-root cwd 前提、skill 資産は self-relative 参照。
- **同梱決定論ゲート (機械正本=`specfm.GATE_SCRIPTS`)**: core = verify-index-topsort / detect-unassigned / check-spec-frontmatter / check-spec-gates / check-spec-matrix-coverage (--self-test + PLAN の 2 起動)。拡張 = check-plugin-goal-spec / check-requirements-coverage / check-surface-inventory / check-build-handoff / validate-task-graph / check-runtime-portability / check-plugin-surface-audit (総数の人間可読正本=io-contract §11 表)。
- **build の始め方 (consumer 手順・宣言のみ)**: 後段 builder は `handoff-run-plugin-dev-plan.json` の routes を top-sort 順に消費する。skill route は routes[].build_args の `brief_path` で inventory から skill-brief JSON を決定論射影して `run-skill-create` へ渡す。
- **dispatch 契約 (task-graph route モード)**: 本 plan は `shape_marker: task-graph-derived` を採用し、`task-specs/*.md` (82 件) を dispatchable leaf の正本、`task-graph.json` をその決定論射影とする。task-graph は参照用ではなく dispatch 契約であり、各 leaf は `render-task-execution-envelope.py <PLAN_DIR> --task-id <id>` で TaskExecutionEnvelope へ合成できる。leaf の粒度は、component 粒度へ分岐する設計 (P02: `P02-C<nn>-01`)・テスト設計 (P04: `P04-C<nn>-01`、`write_scope: plugins/guide-doc-generator/tests/<component 名>/`)・実装 (P05: `P05-C<nn>-01`、`execution_kind: component-build` + 明示 `route_ref`) の 3 phase に限り、他 phase は component 横断の集約判定 1 本 (`P<nn>-x-01`) とする。P02 leaf が produce する設計ブリーフと P04 leaf が produce するテスト実体を P05 leaf が consume するため、build は「契約確定 → 赤の固定 → 実体化」の順にしか進めない。P05 leaf はテストを追加しないと宣言しているので、赤の作成を 1 leaf に束ねると tdd-red が単一障害点になる。これを避けるため P04 も build と同じ粒度へ割り、`P04-x-01` は 23 件の赤を集約記録する背骨に徹する。ただし brief の materialize 方法は 2 通りに書き分かれる: **skill 4 件 (C01-C04) の `briefs/skill-brief-C0N.json` は手書きせず `render-skill-brief.py` が inventory から決定論射影する実体**であり、当該 P02 leaf の責務は射影が exit0 で通るよう inventory 側の component ブロックを確定させることに限る (手書きすると route preflight の「未 materialize のときだけ射影する」判定を抑止し、skill-brief schema 検証で build が壊れる)。残る 19 件 (script / agent / command / hook 用) は `build_args` から参照されない plan 内部成果物で、P02 leaf が直接書く。
- **コンポーネント目録の所在**: buildable な実体 (skill×4 / sub-agent×2 / slash-command×3 / hook×1 / script×13 = 計 23) は `component-inventory.json` が唯一の SSOT。build_target・依存 DAG・quality_gates・harness_coverage・feedback_contract を目録側が保持する。
- **実プラグインの配置先**: `plugins/guide-doc-generator/` (skills/ agents/ commands/ hooks/ scripts/ schemas/ assets/ config/ references/)。本 plan は L3 計画層で完結し、この配下へは一切書かない。ただし task-graph の dispatch leaf (P04 のテスト実体・P05 の component build) は下流 builder が同配下へ書く。plan 生成物 (13 phase md / component-inventory.json / handoff / task-specs) はこの配下を作らない。
- **委譲先**: 画像生成は `plugins/slide-report-generator/` の既存パイプラインへ subprocess 委譲する (再実装しない)。不在時は画像ステップのみ skip して生成を完走させる。
- **Plugin-level surfaces**:

  | surface | 判定 | 記録先 |
  |---|---|---|
  | manifest | required | `plugin_meta.manifest` |
  | plugin-composition | required | `plugin-composition.yaml` |
  | harness/eval | required | `EVALS.json` + `plugin_meta.harness_eval` |
  | references/config/assets | required | `plugin_meta.ssot_dedup` (assets=トークン/マスコット/アイコンセット、config=既定出力先とサイズ上限、references=部品カタログとアイコン規約) |
  | schemas | required | inventory `plugin_level_surfaces.schemas` (構成データスキーマ=全 component の共有 contract) |
  | vendor | omitted | component inventory の omitted_reason |
  | MCP/app connector | omitted | component inventory の omitted_reason |
  | notion_config | omitted | component inventory の omitted_reason (受け皿キーは `plugin_meta.feedback_deploy.notion_sink` 側) |

## 環境ポリシー
- **品質基準**: 全 buildable component が quality_gates (p0_lint(kind別)/build_trace/elegant_review C1-C4/content_review verdict/evaluator≥80,high0) + harness_coverage(min≥80/kind_pass) を携帯する。
- **proposer≠approver**: 設計/最終レビューは提案者と別 context の approver が承認する (design-gate/final-gate)。生成資料の読みやすさ判定も同原則で、生成した本人が採点しない。
- **実行時可搬性**: 環境固有の絶対パスを焼かない。実体解決は専用 env `HB_ROOT` を一次、`${HB_ROOT:-$CLAUDE_PLUGIN_ROOT}` を二次とし、manifest の name 照合による二重防御と `__file__` 相対の自己解決フォールバックを重ねる。`.claude/` 平置き projection では `CLAUDE_PLUGIN_ROOT` を 1 値しか持てず別 plugin が保持しているため、この方式でしか単独解決できない。
- **現状値非焼込**: 参照資料の実測値 (文字数・data URI 比率など) は現状把握であって目標値ではない。数値を要件へ焼くと Goodhart 化するため component エントリにも焼かない。
- **エスカレーション**: ゲート未達は最大 3 周で findings を反映し再実行、超過時は `open_issues` に残し差し戻す。

## フェーズ一覧

1. P01 — requirements (要件定義) / 未実施
2. P02 — design (設計) / 未実施
3. P03 — design-review (設計レビューゲート) / 未実施
4. P04 — test-design (テスト設計) / 未実施
5. P05 — implementation (実装) / 未実施
6. P06 — test-run (テスト実行) / 未実施
7. P07 — acceptance-criteria (受入基準判定) / 未実施
8. P08 — refactoring (リファクタリング) / 未実施
9. P09 — quality-assurance (品質保証) / 未実施
10. P10 — final-review (最終レビューゲート) / 未実施
11. P11 — evidence (手動テスト検証) / 未実施
12. P12 — documentation (ドキュメント) / 未実施
13. P13 — release (完了/PR・リリース) / 未実施

## 完了チェックリスト
- [ ] 基本定義 (plugin slug / purpose / スコープ) が宣言されている。
- [ ] ドメイン知識 (2 軸直交 / component_kind 5 種 / 構成データ / 分界線 / 用語集) が宣言されている。
- [ ] インフラ (実行環境 / ゲート / 目録所在 / 配置先 / surface 採否) が宣言されている。
- [ ] 環境ポリシー (品質基準 / proposer≠approver / 実行時可搬性 / 現状値非焼込) が宣言されている。
- [ ] 13 フェーズ (P01..P13) が phase_number 昇順で全存在し、各 phase 本文が §5 section 床 (宣言型 8 節) を満たす。
- [ ] 各 component が >=1 phase の `entities_covered` に出現する (orphan 0 件)。
- [ ] 同梱決定論ゲートが全 exit0 (goal-spec 要件の被覆は check-requirements-coverage が機械検査)。

### 要件被覆 (goal-spec checklist → 焼き先)

| 要件 id | 要件の主旨 | 焼き先 (component / phase) |
|---|---|---|
| C1, C2 | 単一 HTML 1 ファイルで完結し外部参照が 0 件 | C11 レンダラ / C16 自己完結検査 / P05・P07 |
| C3, C4 | 目次ナビのアンカー整合と見出しが隠れないオフセット補正 | C11 / C16 / P05 |
| C5 | 画像を data URI で埋め込む | C13 / C11 / P05 |
| C6 | 画像の拡大表示 (ESC・背景クリック・フォーカス退避) | C11 / C17 / P05 |
| C7 | 添付ファイルの取得動線と取得できない場合の代替提示 | C11 / C13 / P05 |
| C8 | セクション別と全体のメモ保持・書き出し・消去 | C11 / P05 |
| C9 | 概念図解 6 パターンを inline SVG で生成 | C14 / P04・P05 |
| C10, C11 | 絵文字 0 件・アイコン様式統一・未使用 symbol 0 件 | C15 / C16 / C10 hook / P05・P09 |
| C12 | 部品カタログ (`config/handout-parts.json`) の宣言的表現と部品別レンダリングテスト | C04 / C11 / P04 |
| C13, C14 | デザイントークンとマスコットの同梱、アクセント色差し替え時の可読性維持 | C04 / C11 / plugin_meta.ssot_dedup / P02・P05 |
| C15 | 各セクションの導入一文と判断軸の一文が必須 | C12 / C05 / C18 / P05 |
| C16 | 初出専門用語の言い換え併記 | C18 / C06 / P05・P07 |
| C17, C18 | 画像生成は既存 plugin へ委譲し再実装 0 件、不在時は skip して完走 | C21 / P05・P10 |
| C19 | 既定テンプレート (最低限の部品構成と並び順) を持つ | C11 / C12 / P05 |
| C20 | 既存 HTML からの逆抽出と round-trip 等価 | C02 / C20 / P04・P07 |
| C21 | A4 印刷で版面が崩れない印刷規則 | C11 / C17 / P05・P09 |
| C22 | a11y 必須属性と操作性の適用 | C11 / C17 / P05・P09 |
| C23, C24 | 出力先の命名規則と同梱物 4 種 | C19 / P05・P07 |
| C25 | 実プラグインの配置先が index に明記されている | 本 index `## インフラ` / P02 |
| C26 | パッケージング契約が plugin_meta に宣言されている | 本 index frontmatter / P13 |
| C27 | script が Python 標準ライブラリのみで動く | 全 script component / P05・P09 |
| C28 | 責務候補の採否根拠が目録に記録されている | `component-inventory.json` responsibility_decisions / P02 |
| C29 | 出力先へ同梱された構成データからの再生成がバイト一致する (再現の単位は同梱構成データ 1 点) | C11 / C01 の受入 criterion / P04・P07 |
| C30 | 素材サイズ上限超過時は警告して生成を継続する | C13 / P05 |
| C31 | harness-creator native の規律が焼かれ他 plugin 固有項目が 0 件 | 全 component の quality_gates / P09 |
| C32 | 計画成果物の決定論ゲートが全 exit0 | 本 index `## 完了チェックリスト` / P03 |
| C33, C34, C35 | 日付フィールドの必須化・冒頭日付の表記規則・出力先命名との同一ソース (既定値の解決は C12 の正規化 1 箇所、C11 が本文表記、C19 が出力先命名、C18 が両者の一致検査) | C12 / C11 / C18 / C19 / P05・P07 |
| C36 | 資料単位の必須フィールド一式 (読者 / 前提知識 / 用途 / 課題 / 背景 / 全体ゴール / 分量感 / セクション構成) | C12 / schemas surface / P05 |
| C37 | 冒頭に目的・背景・ゴールの 3 要素を描画し不在を検出する | C11 / C22 / P05・P07 |
| C38 | 各セクションが非空のゴールを持ち決定論的に描画される | C12 / C11 / C22 / P05 |
| C39 | 目次の各項目から対応セクションのゴールを参照できる (nav 本体は簡潔に保ち補助属性で持たせ、常時表示はセクション冒頭側で担う) | C11 / C22 / P05 |
| C40 | 導入一文と判断軸の検査とゴールの検査が同時に成立する (相互代替しない) | C18 / C22 / P04・P09 |
| C41 | 6 用途それぞれに既定のセクション構成プリセットが存在する | C23 / config surface / P05 |
| C42 | 用途種別の語彙が単一正本で、命名とプリセット選択の双方がそれを参照する | C23 / C19 / P05・P09 |
| C43 | 語彙正本が 6 用途を被覆し、未被覆プリセットが 0 件である | C23 / P05・P09 |
| C44 | プリセットを切り替えても共有の型が保たれ、差分が並びと推奨部品に限定される | C11 / C23 / P04・P07 |
| C45 | 用途別の追加要求について再利用か新規かの判定と根拠が目録に記録されている | `component-inventory.json` preset_addon_decisions / P02 |
| C46 | 冒頭の流れは大きな流れだけを列挙し項目数に上限がある | C12 (E-SECTIONKIND-MAXITEMS / E-SECTIONKIND-ROWDETAIL) / `config/handout-sections.json` flow-overview / P04・P05 |
| C47 | 冒頭で扱う主題を 1-2 件へ絞り、全セクションがそこへ紐づく | C12 (focus_theme / ties_to) / C01 ヒアリング / P04・P05 |
| C48 | ゴールにも主題にも紐づかない伝達事項を本編から排除し付録へ隔離する | C12 (role / ties_to) / C22 NAR-08 / `config/handout-sections.json` logistics / P04・P05 |
| C49 | presentation_order が必須フィールドで prior_knowledge から決定論導出される | C12 CR-PRESENTATION-ORDER (`--normalize` N4b が唯一の実行点) / P04・P05 |
| C50 | demo_first と explain_first のどちらでも共有の型が保たれ差分が並びに限定される | C23 presentation_order_variants (順列限定) / P04・P07 |
| C51 | 機能名から説明を始めず 成果 → 分解 → 機能 の順で書く | C12 (parts[].slot 順序) / C18 LANG-07 / P04・P05 |
| C52 | 説明の長さに上限があり超過分は既定で折り畳まれる | C12 CR-TEXT-FOLD (器は既存部品 B10) / C11 テーマトークン `text_limits` / P04・P05 |
| C53 | その場で手を動かす枠と先回り Q&A 枠を持つ | C23 lecture プリセット / C12 (B17 / E-SECTIONKIND-HANDSON) / `config/handout-parts.json` B17 / P04・P05 |
| C54 | 到達レベルを宣言し、それを超える内容を検出する | C12 (attainment_level / attainment_step) / P04・P05 |
| C55 | 図表・グラフが枠だけで中身を欠く状態を検出する | C16 SC-09 (外部参照ゼロ検査を通過する欠陥クラスの独立検出) / P04・P09 |
| C56 | demo_first では実画面を先に出し、概念図・抽象説明の先行提示を禁じる | C22 NAR-07 / CR-DEMO1 / C11 `data-hb-asset-role` / P04・P07 |
| C57 | 覚えていただきたいこと と 覚えなくてよいこと を対で明示する | C12 (E-REMEMBER-PAIR / E-REMEMBER-MAX) / C01 ヒアリング / C11 両方描画 / P04・P05 |
| C58 | 達成したい具体業務をヒアリング必須項目とし各セクションの紐づけを検査する | C01 R1-elicit (項目正本) / C12 (E-TARGET-TASKS-EMPTY / E-SECTION-UNTIED-TASK) / P04・P05 |
| C59 | 悩み・やりたいことを聞く対話枠を必須化し所要時間の下限割合を確保する | C12 (E-SECTIONKIND-DURATION-SHARE。時間の正本は section.duration 1 点) / `config/handout-sections.json` dialogue / P04・P05 |
| C60 | JS・CSS・画像・フォント・添付ファイルの全参照を許可列挙 (allowlist) 方式で検査し data: 以外を一律違反とする単一 HTML 完結の拡張検査 | C16 自己完結検査 (allowlist 方式へ拡張) / P04・P05・P09 |
| C61 | detail_level (overview/standard/detailed) を必須フィールドとして持ち、用途プリセットは既定値のみを与え provenance を記録する | C12 (`document_level_fields` / `CR-GRANULARITY-PRESET-DEFAULT-ONLY`) / C23 (`granularity_defaults`) / P04・P05 |
| C62 | evidence_depth (none/cited/sourced) を detail_level と直交する独立軸として必須フィールドに持つ | C12 (`CR-GRANULARITY-ORTHOGONAL`) / P04・P05 |
| C63 | detail_level が C52 のブロック本文文字数上限を決定論的に modulate し、正本はテーマトークン 1 箇所に留める | C11 (テーマトークン `text_limits.block_body_max_chars_by_detail_level` が数値の正本) / C12 (`CR-DETAIL-TEXT-BUDGET` で適用) / P04・P05 |
| C64 | ヒアリングで detail_level / evidence_depth を確定し、既定値を提示したうえで上書きの要否のみを聞き無回答でも停止しない | C01 (`responsibilities[R1-elicit].hearing_required_items_r22`、required:false) / P04・P05 |
| C65 | detail_level を変えて生成しても C44 の共有の型が全水準で保持され、差分が記述量と展開/畳み込みに限定される | C11 (既存 C44 不変条件を水準横断で固定) / P04・P07 |
| C66 | 宣言した detail_level / evidence_depth と生成物の実態が一致することを機械検査し、宣言だけで実態が伴わない資料を通さない | C22 (`NAR-09` / `NAR-10` / `granularity_declared_vs_actual`) / P04・P09 |

> R21 (C46-C59) の 14 項目については、担い手 component と検証手段の一覧・判断根拠を `briefs/RESOLUTION-R21.md` に置く。C60 ([R01拡張] 単一 HTML 完結検査の allowlist 化) は C16 の既存責務の拡張として解決した。R22 (C61-C66) の 6 項目については `briefs/RESOLUTION-R22.md` に置く。23 component の数は変えていない (全て既存 component への責務追加として解決した)。

## 受入確認

> 計画 (上記) が満たすのは「各 component が評価基準を携帯し決定論ゲートを通る」こと。**組み上がった実プラグインが当初 purpose を満たすか**は build 後に下記で確認する。plan は受入基準を**契約として焼く**だけで、実行は後段 build (run-skill-create の harness criteria-test)。purpose の正本 = `goal-spec.purpose`。

| 受入観点 (purpose 由来) | 確認の見方 (build 後) | 焼き先 |
|---|---|---|
| 資料が 1 ファイルで完結して渡せる | 生成 HTML をネットワーク遮断状態で開き、崩れず全機能が動く (要件 C1, C2, C5) | 生成 skill (C01) の OUT criterion + 自己完結検査 (C16) |
| 初心者が読み進められる | 導入一文と判断軸が全セクションに揃い、初出専門用語に言い換えがあり、独立 context のレビュアーが PASS を返す (要件 C15, C16) | 読みやすさレビュー (C03/C06) + 言語検査 (C18) |
| 目次から迷わず移動できる | 目次の各項目から対応セクションへ移動でき、見出しが固定ヘッダに隠れない (要件 C3, C4) | レンダラ (C11) + 自己完結検査 (C16) |
| テンプレートとして反復配布できる | 出力先へ同梱された構成データから 2 回生成して出力がバイト一致し、既定テンプレートで新規題材が 1 本作れる (要件 C19, C29) | 生成 skill (C01) の OUT criterion |
| 過去資料を資産化できる | 既存 HTML を逆抽出して得た構成データから再生成し、構成データ等価が確認できる (要件 C20) | 逆抽出 skill (C02) の OUT criterion |
| 配布物として体裁が整っている | 出力先が命名規則に沿い、資料・構成データ・素材・README が揃い、A4 印刷が崩れない (要件 C21, C23, C24) | 出力ルーティング (C19) + a11y と印刷検査 (C17) |
| 見た目の規律が壊れない | 絵文字 0 件・アイコン様式統一・未使用 symbol 0 件が書込時と生成後の両方で担保される (要件 C10, C11) | 混入阻止 hook (C10) + 自己完結検査 (C16) |
| 資料の筋道が通っている | 冒頭に目的・背景・ゴールが揃い、各セクションのゴールが目次から追え、導入一文と判断軸の検査と同時に成立する (要件 C37, C38, C39, C40) | 筋道検査 (C22) + 言語検査 (C18) |
| 用途に合った型で始められる | 6 用途のいずれを選んでも既定のセクション構成が用意され、共有の型は保たれる (要件 C36, C41, C43, C44) | プリセット解決 (C23) + 構成データ検証 (C12) |
| 語彙が 1 箇所で管理される | 用途種別を 1 つ追加したとき、命名と プリセットの双方が正本の変更だけで追従する (要件 C42, C45) | 語彙正本 (C23) + 目録の追加要求判定 |
| 委譲先が無くても止まらない | 画像生成の委譲先が不在の環境で、画像ステップのみ skip して資料が完成する (要件 C17, C18) | 委譲アダプタ (C21) の縮退動作 |
| 冒頭で全体像と達成目標を 1 行で掴める | 資料冒頭に lead (1 行宣言) と goal_chips (達成目標の札) が描画され、E-KEY-UNKNOWN が出ない (要件 C67) | レンダラ (C11) 既描画 + schema 受理 (C12) |
| 図解が実際に配線され散文へ逃げない | 8 プリセット全ての main セクション 1 件ずつに DIAGRAM が最低 1 件配線され、密度不足は error で止まる (要件 C68) | プリセット (C23) + 密度ゲート error 化 (C12・`visual-per-section-decision.json`) |
| 実画面・概念図の挿絵が第1稿から入る | draft_first でも挿絵生成委譲 (C21) が起動し、全 8 プリセットの全 main セクションで role=screenshot/illustration の IMG が配線される (要件 C69) | 委譲アダプタ (C21) + プリセット (C23) + 生成 skill (C01) R3-render |
| どの用途で始めても最初に全体像がある | 全 8 doc_type の最初の main セクションが timeline/map/thesis のいずれかで、抜けは error で止まる (要件 C70) | プリセット (C23) + 構成データ検証 (C12) |
| 1 セクション = 1 カードで構造が崩れない | 各セクションに番号・見出し・所要時間または件数のラベルがあり、list/table 系部品を最低 1 件持つ (要件 C71) | レンダラ (C11) 既描画 + 構造化検査 (C12) + 往復契約維持 (C20) |
| 出力ディレクトリが読める日本語名になる | `{date}_{日本語命名}` 形式でディレクトリが作られ、大文字小文字と非日本語タイトルがそのまま保たれる (要件 C72) | 出力ルーティング (C19) の slug 正本一本化 |
| 文章が長ったらしく何行も続かない | 1 文 60 字・1 本文 3 文・折り畳み逃避 0 件を全て error で検査し、exit 0 で通る経路が無い (要件 C73) | 構成データ検証 (C12) の長文ゲート error 化 (`text-length-gate-decision.json`) |
| 冒頭の資料レベル記述がカードとして構造化され読み取りやすい | 目的/背景/ゴールが hero-card 要素へ変わり、箇条書きに見出しが付き、hero の文字数/文数上限が error で検査され (既存値 60/80/50/40・合計 400、+ 文数上限 1/1/1/2)、列挙値の生表示が E-ENUM-RAW で検出され表示語彙へ変換される (要件 C74) | レンダラ (C11) の hero-card 描画 + 構成データ検証 (C12) の長文ゲート拡張 (`hero-card-decision.json`) + 言語検査 (C18) の E-ENUM-RAW |
| 外部コネクタの利用前提が資料冒頭で分かる | prerequisite_connectors を宣言すると『前提』カードが描かれ、語彙正本 (Google Drive / OneDrive / kintone の 3 種、拡張可能) に無いコネクタ名は E-CONNECTOR-UNKNOWN で検証ゲートが止まる (要件 C75) | レンダラ (C11) の前提カード描画 + 構成データ検証 (C12) の E-CONNECTOR-UNKNOWN |

build 後、各 component の `feedback_contract.criteria` が criteria-test として実行され、上表の受入が PASS して初めて「purpose を満たすプラグインが出来た」と確定する。`EVALS.json` の `llm_eval` はこの受入が評価系に配線されていることを宣言する。

> R25 (改善 2026-08-18・goal-spec C67-C73) の 7 項目については、担い手 component と確定値の正本 (`improvement/diagram-gate-decision.json` / `improvement/output-naming-decision.json` / `improvement/text-length-gate-decision.json`) の一覧・判断根拠を `briefs/RESOLUTION-R25-improvement-2026-08-18.md` に置く。23 component の数は変えていない (全て既存 component への責務追加として解決した)。最優先は C73 (長文の完全排除) であり、長文系検査は全て error 化し exit 0 で通る経路を残さない。REQ-8/REQ-9 (goal-spec C74/C75、2026-08-18 追補) の 2 項目については、確定値の正本 `improvement/hero-card-decision.json` に一覧・判断根拠を置く。
