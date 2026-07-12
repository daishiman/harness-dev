---
id: IDX0
title: slide-report-generator 開発計画 index (main)
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
      installation: AVAILABLE
      authentication: ON_INSTALL
      category: Productivity
    cachebuster_for_update: true
  distribution:
    distributable: false
    bundles: []
    marketplace: false
  pkg_contract:
    pkg: 002-008
  governance:
    runbook: required
  ci:
    workflow: governance-check
  ssot_dedup:
    lint: ssot-duplication
    references_config_assets: tracked
    vendor: byte-parity
  feedback_deploy:
    enabled: false
    reason: 本 plugin はローカル HTML 出力のみで Notion 連携を持たず (notion_config surface=false)、改善要望の Notion 受け皿を設けない (D6 opt-out)。フィードバックは repo 同梱の feedback/ references と lessons-learned で扱う
  harness_eval:
    evals_json: EVALS.json
    mechanical: required
    llm_eval: required
---

# slide-report-generator 開発計画 index (main)

> プラグイン構想「presentation-slide-generator の全機能を xl-skills plugin へ抜け漏れなく移植しつつ、共通コア + output_mode=slide/report の 2 モードへ再編し report 出力を新規追加する」を、人間可読な 13 フェーズのライフサイクル (本 index + phase-01..13.md) と、機械可読な buildable component 目録 (`component-inventory.json`) の 2 軸直交で計画したもの。
> ライフサイクル軸 (フェーズ) は宣言型のタスク仕様 (`specfm.PHASE_BODY_SECTIONS` の 8 節) で primary deliverable。成果物実体軸 (component) は build routing・依存 DAG・品質機構を保持する唯一の SSOT。フェーズは component id を `entities_covered` で参照するだけで build_target を再記述しない (正規化)。
> 注記: 本 index は当初の L3 計画正本を保持するためフェーズ一覧に「未実施」表記を残す。旧buildの完了記録は`outputs/phase-05..13/`、今回UI updateのcurrent evidenceは新しいPhase11 freshness manifestが正本。再buildはC01/C02/C17/C18/C19/C24/C25 + S-SCHEMAS/S-REFERENCES/S-EVALS。残りはunchanged、component数25は維持する。

## 基本定義
- **プラグイン slug**: `slide-report-generator` (plan_dir=`plugin-plans/slide-report-generator/`・同一構想は常に同一出力先=再現性アンカー)。既存 `presentation-slide-generator` との併存・区別のため暫定命名 (確定後 rename 可)。
- **最上位目的 (purpose)**: presentation-slide-generator の全機能を抜け漏れなく移植しつつ、共通の意匠・技術コアを単一 SSOT で共有する output_mode=slide/report の 2 モード・ビジュアル生成ハーネスを作る。
- **仕様駆動 (大前提)**: 本計画は harness-creator 仕様を基に作成される (規律の焼き先=`harness-creator-spec-reflection.md` マトリクスの引用・独自流儀の発明禁止)。要件の正本は `goal-spec.json` の checklist (移植 C1-C8 + report 構造化改善 C9-C15) と `source-inventory.md` §5 被覆、仕様書 (本 index + 13 phase) はその被覆であり、乖離が出たら**仕様を先に更新**してから build へ戻す (spec-first)。
- **要件 id と component id の識別 (誤読防止)**: 要件 id は非ゼロ埋め `C1`..`C19` (goal-spec.checklist)、component id はゼロ埋め `C01`..`C25` (component-inventory)。両者は別名前空間で、2桁域 (要件 C10-C19 ↔ component C10-C19) は要件 id と component id が文字列一致するため (例: 要件 C11 ↔ component C11 layout-optimizer、要件 C15 ↔ component C15 slide-report-modifier、要件 C19[本質図解(essence-visual)第一級化] ↔ component C19 report-composer) が指す対象は異なる (要件 C19 の設計 owner は component C18 visual-strategist であり component C19 ではない)。字面一致域では要件参照か component 参照かを文脈で明示する。本 index の「要件 Cn」表記は常に要件 checklist を指す。今後の update で追加する要件 id は component id (C01-C25) と字面衝突しない系列 (例: U1..) を採番する (恒久緩和規約)。
- **スコープ (含む)**: index + 13 フェーズ計画 + `component-inventory.json` + `handoff` + `envelope-draft` の生成 (計画=L3 契約)。
- **スコープ (含まない)**: 実プラグイン/実コードの build (L4・後段 run-skill-create / run-build-skill へ委譲)、PR/配布登録。

## ドメイン知識
- **2 軸直交**: ライフサイクル軸 (13 phase・人間可読) と成果物実体軸 (N=25 component・機械 SSOT) を二重に持たない。
- **component_kind (5 種)**: skill / sub-agent / slash-command / hook / script。同一 kind の複数実体はそれぞれ独立 component。
- **phase ≠ component**: 13 はフェーズ数の固定値、N=25 は buildable 実体数で独立に決まる。phase は `entities_covered: [C01, ...]` の id 参照のみで component に紐づく。
- **output_mode 分岐**: slide=1スライド1メッセージ/chip強制/長文禁止(BP11-13)/16:9/97 slideType、report=読み物(文章多め可)/セクション+段落/1項目1ビジュアル最適化/HTMLレポート/4 reportType。意匠/技術層は単一 SSOT 共有・コンテンツ意図層のみ mode 別 rubric で分岐。
- **report 構造化語彙 (C9-C15 の第一級用語)**: `narrative`=節内論理展開 (本質課題→解決策→活用/含意・section.narrative)、`body block`=構造化本文ブロック (段落/markdown表/コードブロック/番号リスト/小見出し/key-point 強調ボックス/stat-tile/callout/blockquote + 1.2.0 additive の `definition-list`[用語定義 term↔def]/`footnote+citation`[脚注引用]/`task-list`[次アクション])、`highlight`=要点の色付き強調 (意匠 accent・過剰抑制つき・色覚非依存の第2チャネル weight/underline 併存)、`placement`=図解の意味的配置 (正規化 field {grid/zones/`emphasisZone`/readingOrder/focalPoint}・render-report.js が live 反映。emphasisZone は旧 emphasis を inline highlight との字面衝突回避で改名)、`reportType`=4 骨格 (社内報告分析/顧客提案WP/技術ドキュメント/学習解説)、`throughLine`=文書全体の通し筋 (冒頭=本質課題→本論=解決→結=活用のアーク・meta.throughLine)、`transition`=節間接続 (次節への橋渡し1文・section.transition)、`section.role`=節の役割 enum {analysis/argument/reference/procedure/summary}(narrative 要否を決める)、`文書メタ`=meta の version/updatedDate/readingTime/audience。羅列でなく読者が論理を追え文書全体の弧を辿れる読み物にする改善軸。
- **report 構造化 owner 表 (要件→焼き先の担当)**: 要件 C9(節内論理 narrative)→C17 設計 / C10(block構造+読書CSS render)→C19 render-report.js / C11(色付き強調・色覚非依存)→C19 render + 意匠SSOT / C12(図解の意味的配置)→C18 幾何配置 owner + C19 render / C13(積極評価ゲート)→C24 RQ + C25 機械 / C14(横断要素カタログ)→references(report-narrative-logic.md)+ 4 reportType 骨格 / C15(節間フロー throughLine/transition)→C17 throughLine 設計。**C17↔C18 責務境界**: C17=論理構造(narrative/throughLine/transition/section.role)+意味的スロット割当、C18=幾何配置(grid/zones/emphasisZone/readingOrder/focalPoint)の唯一 owner。
- **report UI/UX 語彙 (C16-C19 の第一級用語)**: `screen/print 二層 CSS`、`sticky sidebar TOC`、`scrollspy lifecycle`、`computed typography`、`card minimum readable width`、`essence-visual`(論理節=role∈{分析/主張/課題/解決/所見/影響}が非none visual を持つ・論理構造→図種写像 §0.5.1)を第一級とする。C25は`--structure`必須、C24はstructure+render+metrics+navigation bundle必須。狭画面は900px、899/900/901境界を検査する。
- **report UI/UX owner 表 (要件→焼き先の担当)**: 要件 C16(screen/print幅二層化)→C19 render-report.js(周回2 是正・R4 MEDIUM: report 読書 CSS の正本責務は buildReportCss() inline <style> 出力・独立ファイル report.css への分離は将来オプション・screen/print 分岐はこの CSS 出力内で行う) / C17(sticky sidebar TOC+scrollspy)→C19 render(self-contained JS 出力) / C18(タイポ/密度再調整)→C19 render(スケール/spacing 変数調整・意匠 SSOT 無改変) / C19(本質図解 essence-visual 第一級化)→C18 visual-strategist(essence-visual/図種写像 設計 owner・形式三択に先行。component C19 は essence-visual を render 側で素通しするのみで設計 owner ではない)。C16-C19 いずれも積極評価=C24・決定論検査=C25 が共通で担う (schema は 1.2.0 のまま=essence-visual は既存 role/visual.kind を使い schema bump 不要・第3次UIは render CSS のみで schema 非依存)。print/狭画面 degrade の非退行は C24(意味適合)+ C25(shape: @media print/print無効化/breakpoint 存在)の二層で検査する (周回2 追加)。
- **vendored Node engine**: Node/CJS 製レンダリング/画像/印刷/検証エンジンは vendor surface として byte 維持で携行し stdlib script へ書き換えない。skill/agent は Bash(node *) で起動する (既存資産の毀損回避)。携行単位は個別ファイル allowlist ではなく `scripts/`/`assets/`/`schemas/`/`package.json` の **whole-tree byte copy**(inventory `plugin_level_surfaces.vendor.copy_mode=whole-tree`)とし、共有ランタイム `utils.js` を含む scripts/ 直下 30 Node script 全数(+ hooks/deck-postgen-hook.js 移植元 + 118 templates + test-fixtures/)を取りこぼしなく携行する。
- **upstream 凍結**: upstream (presentation-slide-generator) は v8.4.2 で凍結。byte 正本 = `vendor-digest-manifest.json` (plan 同梱)。追従は明示的な再 vendor 手続き (manifest 再生成) のみ。
- **elegant-review C1-C4**: 矛盾なし/漏れなし/整合性/依存整合 の設計審査 4 条件 (design-gate/final-gate 共通)。
- **共通コア**: 意匠/技術 (Kanagawa/16:9/最小1.4rem/GSAP/インラインSVG2/印刷CSS/letterbox/Codex Image2/style genome/決定論レンダラ) は vendor + references + schemas (structure⇄report-structure の nodes/edges/groups/theme/aiVisual) で単一 SSOT 共有。

## インフラ
- **実行環境**: harness glue script は Python 標準ライブラリのみ (validate-output-mode.py)。レンダリング/画像/印刷/検証は vendor Node engine を `Bash(node *)` で起動する (byte 携行・Python 化しない)。画像生成は `codex exec` (Bash) 経由。lint/スクリプト起動は repo-root cwd 前提、skill 資産は self-relative / `$CLAUDE_PLUGIN_ROOT` 参照。
- **同梱決定論ゲート (2 層命名・機械正本=`specfm.GATE_SCRIPTS`)**: core 5 scripts / 6 invocations = verify-index-topsort / detect-unassigned / check-spec-frontmatter / check-spec-gates / check-spec-matrix-coverage (--self-test + PLAN の 2 起動)。拡張ゲート = check-plugin-goal-spec / check-requirements-coverage / check-surface-inventory / check-build-handoff / check-runtime-portability / check-plugin-surface-audit (総数の人間可読正本=io-contract §11 表)。区分注記: plan 段階で実行可能なゲート起動 = 10 (self-test 別掲)。check-plugin-surface-audit は build 後 (plugins/ 実体前提) のみ実行可能。roster の機械正本 = `specfm.GATE_SCRIPTS`・人間可読正本 = io-contract §11 表。
- **build の始め方 (consumer 手順・宣言のみ)**: 後段 builder は `handoff-run-plugin-dev-plan.json` の routes を top-sort 順に消費する。skill route は routes[].build_args の `brief_path` (render-skill-brief.py) で inventory から skill-brief JSON を決定論射影して `run-skill-create` へ渡す。初見 builder quickstart: 読む順 = 本 index → `handoff-run-plugin-dev-plan.json` → `component-inventory.json`。最初の 1 コマンド = render-skill-brief.py による brief 生成。`plan-findings.json` は digest pin 付き評価 snapshot であり、鮮度は evaluated_inputs の sha 照合で判定する。
- **コンポーネント目録の所在**: buildable な実体 (skill×3 / sub-agent×17 / slash-command×2 / hook×1 / script×2 = 計 25。sub-agent×17 は既存13+report新規3(C17/C18/C19)+report品質1(C24)、script×2 は C23 validate-output-mode/C25 validate-report-visual) は `component-inventory.json` が唯一の SSOT。build_target・依存 DAG・quality_gates・harness_coverage・feedback_contract を目録側が保持する。
- **Plugin-level surfaces**:

  | surface | 判定 | 記録先 |
  |---|---|---|
  | manifest | required | `plugin_meta.manifest` + `envelope-draft/plugin.json` |
  | composition | required | `plugin-composition.yaml` |
  | harness/eval | required | `EVALS.json` + `plugin_meta.harness_eval` (slide/report 両モード配線) |
  | schemas | required | inventory `plugin_level_surfaces.schemas` (structure 移植 + report-structure 新設) |
  | references/config/assets | required | `plugin_meta.ssot_dedup` (42 references + report 新規。118 templates/style-genome/d3-components/pagination/print-styles/gas-deploy-guide の byte 実体は vendor 側に一本化し本 surface からはポインタ参照のみ=二重 SSOT 回避) |
  | vendor | required | inventory `plugin_level_surfaces.vendor` (Node engine を含む `scripts/`/`assets/`/`schemas/`/`package.json` の whole-tree byte 携行・Python 化しない) + `plugin_meta.ssot_dedup.vendor=byte-parity` + source_digest_manifest=`vendor-digest-manifest.json` (byte 比較基準) |
  | MCP/app connector | omitted | inventory の omitted_reason (画像生成は codex exec Bash 経由) |
  | notion_config | omitted | inventory の omitted_reason (ローカル HTML 出力のみ・Notion 不使用) |

## 環境ポリシー
- **品質基準**: 全 25 buildable component が quality_gates (p0_lint(kind別)/build_trace/elegant_review C1-C4/content_review verdict/evaluator≥80,high0) + harness_coverage(min≥80/kind_pass) を携帯する。
- **抜け漏れ厳禁**: 既存全資産 (13 agents / 42 references / 30 Node scripts / 118 templates / schemas 7本(真 schema 4 + example fixture 3・移植先は report-structure 新設で真 schema 計5) / Codex Image2 / 30種思考法 / A4印刷 / GAS) を機能削減・平均回帰・オミットせず component or surface へ移植する (`source-inventory.md` §5 被覆)。
- **proposer≠approver**: 設計/最終レビューは提案者と別 context の approver が承認する (design-gate/final-gate)。
- **現状値非焼込**: 「≥80% を満たす設計」を要件化し、harness 現状未達数値は component エントリへ焼かない (Goodhart 回避)。
- **エスカレーション**: ゲート未達は最大 5 周 (goal-spec.max_loops) で findings を反映し再実行、超過時は `open_issues` に残し差し戻す。

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
- [ ] ドメイン知識 (2 軸直交 / component_kind 5 種 / output_mode 分岐 / vendor 携行 / 用語集) が宣言されている。
- [ ] インフラ (実行環境 / core scripts / 目録所在 / surface 採否) が宣言されている。
- [ ] 環境ポリシー (品質基準 / 抜け漏れ厳禁 / proposer≠approver / 現状値非焼込) が宣言されている。
- [ ] 13 フェーズ (P01..P13) が phase_number 昇順で全存在し、各 phase 本文が §5 section 床 (`specfm.PHASE_BODY_SECTIONS` の宣言型 8 節) を満たす。
- [ ] 要件 C1: 既存 13 sub-agent が新 plugin の component (C04-C16) へ漏れなく写像されている。
- [ ] 要件 C2: output_mode=slide/report 分岐が主オーケストレータ skill (C01) と hearing-facilitator (C04) に焼かれ、意匠/技術層は単一 SSOT 共有・コンテンツ意図層のみ mode 別になっている。
- [ ] 要件 C3: report モードが 4 reportType 骨格 (report-structure schema・C17)・visual-strategist (C18・三択最適化)・Mermaid 統合・report HTML レンダラ (C19+vendor) を component として持つ。
- [ ] 要件 C4: Codex Image2 全面画像チェーン (C14+vendor) と 30種思考法の生成後評価ゲート (deck-evaluator C13 + hook C20) が両モードで機能する形で移植されている。
- [ ] 要件 C5: Node 製レンダリング/画像/印刷エンジンが vendored asset surface として携行され、Python-stdlib 書換なしで install 携帯性を満たす (skill から Bash(node *) 起動)。
- [ ] 要件 C6: `component-inventory.json` が 5 component_kind の検討証跡と plugin-level surfaces の採否・不要理由を記録している。
- [ ] 要件 C7: 各 buildable component が core 規律 quality_gates + harness_coverage(min≥80/kind_pass) を携帯している。
- [ ] 要件 C8: index が P01..P13 を phase_number 昇順で全列挙し plugin_meta (manifest/marketplace/ci/feedback_deploy) と受入確認章を携帯している。
- [ ] 要件 C9 (report構造化): report が節内論理展開 (本質課題→解決策→活用/含意) を section.narrative として持ち、reportType 骨格の節順序だけでなく節内部の論理構造を強制する (C17 設計 + report-narrative-logic.md 正本)。
- [ ] 要件 C10 (report構造化): report 本文が block 構造 (段落/markdownテーブル/フェンスドコードブロック/番号リスト/箇条書き/小見出し/キーポイント強調ボックス/統計タイル + 1.2.0 additive の定義リスト/脚注引用/タスクリスト) を第一級で表現し、決定論レンダラ render-report.js が各 block を正しく HTML 化する (表が `<br>` で潰れない・C19 実装 + schema 1.1.0→1.2.0 additive)。読み物可読性の report 読書 CSS は render-report.js の buildReportCss() が inline 出力する(正本=inventory C19.build_contract: buildReportCss() inline 出力・CCONST_006 自己完結 HTML・分離は将来オプション)。C25 pre-render gate が block 型多様性・新 block 型・読書 CSS class 出力の存在を被覆検査する。
- [ ] 要件 C11 (report構造化): report が要点の色付き強調 (インライン highlight トークン + キーポイント/統計タイル) を schema トークン + render-report.js + 意匠SSOT配色 (Kanagawa accent) で表現し、見出しごとに整形される (bold→accent 1種のみを超える)。強調は色単一チャネルに依存せず font-weight/underline 等の第2チャネルを必須併存し色覚非依存 (C24 積極評価 + C25 非色属性の機械検査)。
- [ ] 要件 C12 (report構造化): 図解の意味的配置 (placement.grid/zones/emphasis/focalPoint) を C18 の決定を render-report.js が反映し、図が段落末尾全幅固定でなく本文の該当箇所へ意味的に配置される (schema の placement デッドフィールドを live 化)。
- [ ] 要件 C13 (report構造化): C24 report-quality-reviewer の RQ 積極評価次元 (論理展開成立/節間の論理接続 through-line/block 適合[多様性 < 適合性]/強調の効きと色覚非依存/意味的配置/reportType 横断要素の充足/見出し整形) と C25 validate-report-visual.py の機械チェック (block型多様性の決定論閾値/narrative 非空[role条件]/highlight 表現と非色属性/表・コード・番号リストの正 HTML 化/reportType別必須横断要素/placement live 反映/throughLine 非空) が『羅列でも破綻ゼロなら PASS』も『構造過剰でも多様性ありなら PASS』も塞ぐ (機械強制の境界は shape/存在/閾値まで・意味の適合は C24 evaluator へ委譲=二層分離)。
- [ ] 要件 C14 (report構造化): 『本質的に含むべき要素』の開いた読書体験カタログ (再問い由来) が report-narrative-logic.md 正本と 4 reportType 骨格へ reportType 別に additive 反映される。共通=エグゼクティブ要約/キーテイクアウェイ/意思決定・次アクション/根拠・出典/リスク・留保/TL;DR + 図表番号・キャプション + 長尺時の目次(TOC)・相互参照 + callout(note/warning/tip) + 文書メタ(version/updatedDate/readingTime/audience) + per-section recap + 表現機構(定義リスト/脚注引用/タスクリスト)、型別=技術ドキュメント(前提/用語定義/手順/既知の問題)・学習解説(学習目標/要点/演習)。C25 が reportType別必須横断要素の存在を機械検査し C01 受入へ結線する。読者が本質課題→解決→活用を追える。
- [ ] 要件 C15 (report構造化): report が文書全体の通し筋 (meta.throughLine: 冒頭=本質課題→本論=解決→結=活用のアーク) と節間の論理接続 (section.transition) を持ち、節が羅列でなく弧で連結される。C17 が throughLine/transition/section.role の設計 owner、C24 が through-line を積極評価、C25 が長尺 report での throughLine 非空を機械検査する (節順序・節内論理に加え文書全体の弧を強制)。
- [ ] 要件 C16 (report UI/UX): screen 表示が print 用 190mm 単層幅を流用せず、screen=可読幅本文カラム+sidebar レイアウト・print=190mm/A4 を `@media print` で温存する二層 CSS になっている (C19 render-report.js の buildReportCss() inline <style> 出力を正本責務として拡張。独立ファイル report.css への分離は将来オプション)。広画面で『空白 > 本文』の逆転が解消される。print 出力側は `@media print` ブロックの出力存在(C25 shape 検査)と従来 190mm/A4 読了体験の非退行(C24 積極評価)の二層で非退行を担保する (周回2 追加)。
- [ ] 要件 C17 (report UI/UX): `.report-toc` が冒頭静的2カラムに留まらず、スクロール追従する sticky sidebar TOC + scrollspy (self-contained JS・print 無効) を持ち、狭画面はインライン TOC へ graceful degrade する (C19 実装)。print 時の TOC/scrollspy 無効化出力の存在と狭画面 breakpoint 出力の存在は C25 が shape 検査し、degrade の読みやすさ・探索性は C24 が積極評価する (周回2 追加)。
- [ ] 要件 C18 (report UI/UX): 見出し/本文のタイポ・密度スケール (`--fs-title` 等) が狭カラム相対の過大から是正され、意匠 SSOT (Kanagawa 配色/フォント) は無改変のままスケール/spacing 変数のみ調整される (C19 実装)。
- [ ] 要件 C19 (report UI/UX): C18が形式三択より先に節の論理構造→図種の写像(essence-visual)を行い、論理構造を展開する実質節(role∈{分析/主張/課題/解決/所見/影響}=_ESSENCE_REQUIRED_ROLES)に非none visual(visual.kind!=none)を必ず1枚割り当てる。写像規律はreference report-visual-strategy.md §0.5.1とvisual-strategist VCONST_000が正本。C24は装飾図表と図解すべき論理節でのvisual省略を負値評価し、C25はessence-visualカバレッジ(論理節のvisual.kind非none)を検査する。schemaは1.2.0のまま(essence-visualは既存role/visual.kindを使いschema bump不要)。
- [ ] 全 25 component が >=1 phase の `entities_covered` に出現する (orphan 0 件)。
- [ ] 同梱決定論ゲート (core + 拡張・機械正本=`specfm.GATE_SCRIPTS`) が全 exit0。
- [ ] `handoff-run-plugin-dev-plan.json` の routes が inventory 由来で builder/build_kind/build_args/build_target を持ち、各 component を後段 builder へルーティングする。

## 受入確認

> 計画 (上記) が満たすのは「各 component が評価基準を携帯し決定論ゲートを通る」こと。**組み上がった実プラグインが当初 purpose を満たすか**は build 後に下記で確認する。plan は受入基準を**契約として焼く**だけで、実行は後段 build (run-skill-create の harness criteria-test)。purpose の正本 = `goal-spec.purpose`「presentation-slide-generator の全機能を抜け漏れなく移植した output_mode=slide/report の 2 モード・ビジュアル生成ハーネス」。要件 C1-C8 (移植/2モード) + C9-C15 (report 構造化改善) + C16-C19 (report UI/UX改善) の被覆は本章と上記完了チェックリストで宣言する。

| 受入観点 (purpose 由来) | 確認の見方 (build 後) | 焼き先 |
|---|---|---|
| 既存全機能が抜け漏れなく移植されている (C1/C4/C5) | 13 agents→C04-C16、Codex Image2→C14+vendor、30種思考法→C13+C20+vendor、決定論レンダラ→C10+vendor、A4印刷/GAS→vendor+references が実体で機能 | source-inventory §5 被覆 + 各 component の受入テスト |
| slide/report が 1 経路で mode 別に生成できる (C2) | 同一 skill で --mode slide/report を切替え、意匠/技術は共通・コンテンツ意図のみ mode 別で出力 | generate skill (C01) の inner/outer criterion + hearing (C04) |
| report 新規機能が動く (C3) | 4 reportType 骨格で構成 (C17)、SVG/Mermaid/Codex 三択最適化 (C18)、report HTML 生成 (C19+vendor render-report/mermaid-render) | C17/C18/C19 + schemas(report-structure) + vendor |
| report が『構造化された読み物』になっている (C9-C15) | 生成 report に節内論理展開(本質課題→解決策→活用)・文書アーク(throughLine)と節間接続(transition)による節間フロー・block構造(段落/markdown表/コードブロック/番号リスト/小見出し/キーポイント強調 + 定義リスト/脚注引用/タスクリスト)・要点の色付き強調(色覚非依存の第2チャネル)・図解の意味的配置・reportType 横断要素(要約/次アクション/根拠/リスク)・文書メタが現れ、情報の羅列でなく読者が論理と文書全体の弧を追える。RQ21- 積極評価(through-line/色覚非依存/reportType横断/多様性<適合性)と validate-report-visual の追加機械チェック(reportType別横断要素/placement live反映/throughLine非空/非色属性/読書CSS)が PASS し『羅列でも破綻ゼロなら PASS』も『構造過剰でも多様性ありなら PASS』も塞がれている | C17(narrative+throughLine+transition+section.role+block設計)/C18(live placement emphasisZone/readingOrder)/C19(render-report.js block/highlight第2チャネル/placement/読書CSS inline)/C24(積極評価RQ)/C25(機械チェック) + schemas(report-structure 1.1.0→1.2.0 additive) + references(report-narrative-logic 新設) |
| report の画面表示 UI/UX が是正されている (C16-C19) | screen 表示が print 用 190mm 単層幅の流用をやめ可読幅本文カラム+sidebar の二層 CSS になり広画面の『空白 > 本文』逆転が解消、`.report-toc` が sticky sidebar TOC + scrollspy(self-contained JS)へ拡張されスクロール追従、`--fs-title` 等のタイポ/密度スケールが狭カラム相対の過大から是正 (意匠 SSOT 無改変)、visual-strategist が形式三択に先立ち節の論理構造→図種の写像(essence-visual・§0.5.1)を行い論理節(分析/主張/課題/解決/所見/影響)に非none visual を必須設計し装飾目的の図解と図解不足の両方を防ぐ。print(190mm/A4)契約は `@media print` で温存され退行しない。**print/狭画面確認 (周回2 追加)**: print 出力で従来 190mm/A4 読了体験が退行せず sticky TOC/scrollspy が紙面に現れず、狭画面ではインライン TOC への graceful degrade が探索性を損なわない (`@media print`/print 無効化/狭画面 breakpoint の出力存在は C25 shape 検査、degrade の読みやすさは C24 積極評価)。C24 の評価入力は vendor playwright による wide(≥1600px)/narrow(≤900px・iPad 縦 820px 等の degrade 発火域を含む)/print emulation の 3 状態実レンダリングで得る (HTML ソース Read のみで視覚品質を判定しない)。RQ 積極評価(ナビゲーション成立/密度バランス/図解適合/print・狭画面 degrade の成立)と validate-report-visual の追加機械チェック(screenレイアウトCSS出力/TOC+scrollspy出力/essence-visualカバレッジ[論理節のvisual.kind非none]/`@media print`出力/print時TOC・scrollspy無効化出力/狭画面breakpoint出力)が PASS する | C19(screen/print二層CSS/sticky TOC+scrollspy/タイポ密度スケール)/C18(essence-visual/図種写像 設計 owner)/C24(積極評価RQ)/C25(機械チェック) + schemas(report-structure 1.2.0 据置・essence-visual は既存 role/visual.kind) |
| 生成後評価が両モードで機能する (C4) | 30種思考法で slide=視覚崩れ/1メッセージ・report=可読性/図解適合を区分評価し、hook が書込を検知して fail-soft に評価起動を促す | deck-evaluator (C13) + hook-postgen-eval (C20) |
| Node engine が byte 携行で動く (C5) | node 再 install 後、skill/agent が Bash(node *) で render-slide.cjs 等を起動し HTML を出力 (Python 化していない)。byte 携行の検証は `vendor-digest-manifest.json` を比較基準に lint-vendor-parity.py で行う (移植元 live tree 非依存・additive_new_files は除外集合) | vendor surface + C10/C14/C18/C19 |
| 修正/横断検証が独立起動できる | 既存成果物の局所修正 (C02)、シリーズ横断整合検出 (C03) が単独 skill で動く | modify skill (C02) / cross-deck-review skill (C03) の OUT criterion |

> C16-C19受入の追加精密化: 上表のwide/narrow/printは代表状態であり、必須matrixは899/900/901/1024/1366/1600px+print。宣言CSSだけでなくcomputed本文16-18px、card最小幅、hash-active+`aria-current`、font-ready/history/afterprint、essence-visual(論理節のvisual.kind非none・図が節の要旨を一目化するか)を判定する。本注記が旧来の「5分類+3状態」略記を上書きする。

build 後、各 skill component の `feedback_contract.criteria` が criteria-test として実行され、上表の受入が PASS して初めて「purpose を満たすプラグインが出来た」と確定する。`EVALS.json` の `llm_eval` はこの受入 (slide/report 両モード) が評価系に配線されていることを宣言する。
