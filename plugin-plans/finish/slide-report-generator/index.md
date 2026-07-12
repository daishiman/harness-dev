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
> 注記: 本 index は当初の L3 計画正本を保持するためフェーズ一覧に「未実施」表記を残す。ユーザー指示により後続で実プラグイン build まで進めた完了記録は `outputs/phase-05..13/` と `plugins/slide-report-generator/` が正本であり、実体反映の判定はそちらを優先する。

## 基本定義
- **プラグイン slug**: `slide-report-generator` (plan_dir=`plugin-plans/slide-report-generator/`・同一構想は常に同一出力先=再現性アンカー)。既存 `presentation-slide-generator` との併存・区別のため暫定命名 (確定後 rename 可)。
- **最上位目的 (purpose)**: presentation-slide-generator の全機能を抜け漏れなく移植しつつ、共通の意匠・技術コアを単一 SSOT で共有する output_mode=slide/report の 2 モード・ビジュアル生成ハーネスを作る。
- **仕様駆動 (大前提)**: 本計画は harness-creator 仕様を基に作成される (規律の焼き先=`harness-creator-spec-reflection.md` マトリクスの引用・独自流儀の発明禁止)。要件の正本は `goal-spec.json` の checklist (C1-C8) と `source-inventory.md` §5 被覆、仕様書 (本 index + 13 phase) はその被覆であり、乖離が出たら**仕様を先に更新**してから build へ戻す (spec-first)。
- **スコープ (含む)**: index + 13 フェーズ計画 + `component-inventory.json` + `handoff` + `envelope-draft` の生成 (計画=L3 契約)。
- **スコープ (含まない)**: 実プラグイン/実コードの build (L4・後段 run-skill-create / run-build-skill へ委譲)、PR/配布登録。

## ドメイン知識
- **2 軸直交**: ライフサイクル軸 (13 phase・人間可読) と成果物実体軸 (N=23 component・機械 SSOT) を二重に持たない。
- **component_kind (5 種)**: skill / sub-agent / slash-command / hook / script。同一 kind の複数実体はそれぞれ独立 component。
- **phase ≠ component**: 13 はフェーズ数の固定値、N=23 は buildable 実体数で独立に決まる。phase は `entities_covered: [C01, ...]` の id 参照のみで component に紐づく。
- **output_mode 分岐**: slide=1スライド1メッセージ/chip強制/長文禁止(BP11-13)/16:9/97 slideType、report=読み物(文章多め可)/セクション+段落/1項目1ビジュアル最適化/HTMLレポート/4 reportType。意匠/技術層は単一 SSOT 共有・コンテンツ意図層のみ mode 別 rubric で分岐。
- **vendored Node engine**: Node/CJS 製レンダリング/画像/印刷/検証エンジンは vendor surface として byte 維持で携行し stdlib script へ書き換えない。skill/agent は Bash(node *) で起動する (既存資産の毀損回避)。携行単位は個別ファイル allowlist ではなく `scripts/`/`assets/`/`schemas/`/`package.json` の **whole-tree byte copy**(inventory `plugin_level_surfaces.vendor.copy_mode=whole-tree`)とし、共有ランタイム `utils.js` を含む scripts/ 直下 30 Node script 全数(+ hooks/deck-postgen-hook.js 移植元 + 118 templates + test-fixtures/)を取りこぼしなく携行する。
- **upstream 凍結**: upstream (presentation-slide-generator) は v8.4.2 で凍結。byte 正本 = `vendor-digest-manifest.json` (plan 同梱)。追従は明示的な再 vendor 手続き (manifest 再生成) のみ。
- **elegant-review C1-C4**: 矛盾なし/漏れなし/整合性/依存整合 の設計審査 4 条件 (design-gate/final-gate 共通)。
- **共通コア**: 意匠/技術 (Kanagawa/16:9/最小1.4rem/GSAP/インラインSVG2/印刷CSS/letterbox/Codex Image2/style genome/決定論レンダラ) は vendor + references + schemas (structure⇄report-structure の nodes/edges/groups/theme/aiVisual) で単一 SSOT 共有。

## インフラ
- **実行環境**: harness glue script は Python 標準ライブラリのみ (validate-output-mode.py)。レンダリング/画像/印刷/検証は vendor Node engine を `Bash(node *)` で起動する (byte 携行・Python 化しない)。画像生成は `codex exec` (Bash) 経由。lint/スクリプト起動は repo-root cwd 前提、skill 資産は self-relative / `$CLAUDE_PLUGIN_ROOT` 参照。
- **同梱決定論ゲート (2 層命名・機械正本=`specfm.GATE_SCRIPTS`)**: core 5 scripts / 6 invocations = verify-index-topsort / detect-unassigned / check-spec-frontmatter / check-spec-gates / check-spec-matrix-coverage (--self-test + PLAN の 2 起動)。拡張ゲート = check-plugin-goal-spec / check-requirements-coverage / check-surface-inventory / check-build-handoff / check-runtime-portability / check-plugin-surface-audit (総数の人間可読正本=io-contract §11 表)。区分注記: plan 段階で実行可能なゲート起動 = 10 (self-test 別掲)。check-plugin-surface-audit は build 後 (plugins/ 実体前提) のみ実行可能。roster の機械正本 = `specfm.GATE_SCRIPTS`・人間可読正本 = io-contract §11 表。
- **build の始め方 (consumer 手順・宣言のみ)**: 後段 builder は `handoff-run-plugin-dev-plan.json` の routes を top-sort 順に消費する。skill route は routes[].build_args の `brief_path` (render-skill-brief.py) で inventory から skill-brief JSON を決定論射影して `run-skill-create` へ渡す。初見 builder quickstart: 読む順 = 本 index → `handoff-run-plugin-dev-plan.json` → `component-inventory.json`。最初の 1 コマンド = render-skill-brief.py による brief 生成。`plan-findings.json` は digest pin 付き評価 snapshot であり、鮮度は evaluated_inputs の sha 照合で判定する。
- **コンポーネント目録の所在**: buildable な実体 (skill×3 / sub-agent×16 / slash-command×2 / hook×1 / script×1 = 計 23) は `component-inventory.json` が唯一の SSOT。build_target・依存 DAG・quality_gates・harness_coverage・feedback_contract を目録側が保持する。
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
- **品質基準**: 全 23 buildable component が quality_gates (p0_lint(kind別)/build_trace/elegant_review C1-C4/content_review verdict/evaluator≥80,high0) + harness_coverage(min≥80/kind_pass) を携帯する。
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
- [ ] 全 23 component が >=1 phase の `entities_covered` に出現する (orphan 0 件)。
- [ ] 同梱決定論ゲート (core + 拡張・機械正本=`specfm.GATE_SCRIPTS`) が全 exit0。
- [ ] `handoff-run-plugin-dev-plan.json` の routes が inventory 由来で builder/build_kind/build_args/build_target を持ち、各 component を後段 builder へルーティングする。

## 受入確認

> 計画 (上記) が満たすのは「各 component が評価基準を携帯し決定論ゲートを通る」こと。**組み上がった実プラグインが当初 purpose を満たすか**は build 後に下記で確認する。plan は受入基準を**契約として焼く**だけで、実行は後段 build (run-skill-create の harness criteria-test)。purpose の正本 = `goal-spec.purpose`「presentation-slide-generator の全機能を抜け漏れなく移植した output_mode=slide/report の 2 モード・ビジュアル生成ハーネス」。要件 C1-C8 の被覆は本章と上記完了チェックリストで宣言する。

| 受入観点 (purpose 由来) | 確認の見方 (build 後) | 焼き先 |
|---|---|---|
| 既存全機能が抜け漏れなく移植されている (C1/C4/C5) | 13 agents→C04-C16、Codex Image2→C14+vendor、30種思考法→C13+C20+vendor、決定論レンダラ→C10+vendor、A4印刷/GAS→vendor+references が実体で機能 | source-inventory §5 被覆 + 各 component の受入テスト |
| slide/report が 1 経路で mode 別に生成できる (C2) | 同一 skill で --mode slide/report を切替え、意匠/技術は共通・コンテンツ意図のみ mode 別で出力 | generate skill (C01) の inner/outer criterion + hearing (C04) |
| report 新規機能が動く (C3) | 4 reportType 骨格で構成 (C17)、SVG/Mermaid/Codex 三択最適化 (C18)、report HTML 生成 (C19+vendor render-report/mermaid-render) | C17/C18/C19 + schemas(report-structure) + vendor |
| 生成後評価が両モードで機能する (C4) | 30種思考法で slide=視覚崩れ/1メッセージ・report=可読性/図解適合を区分評価し、hook が書込を検知して fail-soft に評価起動を促す | deck-evaluator (C13) + hook-postgen-eval (C20) |
| Node engine が byte 携行で動く (C5) | node 再 install 後、skill/agent が Bash(node *) で render-slide.cjs 等を起動し HTML を出力 (Python 化していない)。byte 携行の検証は `vendor-digest-manifest.json` を比較基準に lint-vendor-parity.py で行う (移植元 live tree 非依存・additive_new_files は除外集合) | vendor surface + C10/C14/C18/C19 |
| 修正/横断検証が独立起動できる | 既存成果物の局所修正 (C02)、シリーズ横断整合検出 (C03) が単独 skill で動く | modify skill (C02) / cross-deck-review skill (C03) の OUT criterion |

build 後、各 skill component の `feedback_contract.criteria` が criteria-test として実行され、上表の受入が PASS して初めて「purpose を満たすプラグインが出来た」と確定する。`EVALS.json` の `llm_eval` はこの受入 (slide/report 両モード) が評価系に配線されていることを宣言する。
