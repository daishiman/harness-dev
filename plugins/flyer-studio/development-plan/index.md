---
id: IDX0
shape_marker: fixed-13-phase
title: flyer-studio 開発計画 index (main)
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
  ci:
    workflow: local-tests-before-package
  pkg_contract:
    pkg: 002-008
  governance:
    runbook: required
  ssot_dedup:
    lint: ssot-duplication
    references_config_assets: tracked
  feedback_deploy:
    enabled: false
    reason: 個人素材を含むため外部DBへ自動送信しない。ローカルlessonsで改善記録
  install:
    platforms: [claude, codex]
    codex_manifest: .codex-plugin/plugin.json
    registries: [harness-local, codex-repo]
    strict_validate: true
    release: changelog-then-bump
    verify:
      isolated: true
      live: false
      live_skip_reason: ユーザーはローカルプラグイン構築と納品を依頼。実環境導入とグローバル設定変更は未依頼のためdeferred。
  harness_eval:
    evals_json: EVALS.json
    mechanical: required
    llm_eval: required
---

# Flyer Studio 開発計画

## 基本定義
多様な用途のチラシを少ない手戻りで制作し、紙面中央・公開範囲・印刷品質の失敗を反復しない。
要件の正本はgoal-spec.json。仕様駆動で変更を先に反映して実装する。planは設計契約、プラグイン実体は別成果物。13phaseのstatusと未チェック欄は将来の再実行契約を表し、実施済み証拠の正本は`../verification/README.md`と`../verification/results.json`である。計画のPASSを全制作経路の実測PASSに読み替えない。本質の正本は`references/essence.json`(本質課題・本質成果E*・非目的・予算・golden事例)で、制作の周回でもプラグインの改善でも、規則・担当・評価はE*のどれかに結び付く時だけ足す。

## ドメイン知識
紙面中央軸は紙幅/2で、QR除外幅/2ではない。表現形式（写真・漫画・手書き等）と配色（白・黒等）は別軸。白系は全白でなく外周の紙白接続。F07/F11は座標テンプレートでなく品質見本。13フェーズは開発工程、13案は生成成果物数で別概念。

## インフラ
計画・パッケージ制御はPython標準ライブラリ。描画backendはNode22・Playwright/Chromium・QR encoder/decoder・PNG読込、PDF rasterizerを必要とする。依存は明示しローカル一時パスは持たない。ホスト画像生成ツールを実際に呼ぶ。

## 環境ポリシー
個人素材を含む非公開ローカルキット。公開配布登録、グローバルinstall、hook trustは変更しない。harness>=80を品質目標、high0・4条件・最新fingerprintの目視検証を要件とし、未検証の実測値を捏造しない。ブラウザとPDFを実見し、全案レビュー前に完成判定しない。

## フェーズ一覧

1. [P01 — requirements](phase-01-requirements.md)
2. [P02 — design](phase-02-design.md)
3. [P03 — design-review](phase-03-design-review.md)
4. [P04 — test-design](phase-04-test-design.md)
5. [P05 — implementation](phase-05-implementation.md)
6. [P06 — test-run](phase-06-test-run.md)
7. [P07 — acceptance-criteria](phase-07-acceptance-criteria.md)
8. [P08 — refactoring](phase-08-refactoring.md)
9. [P09 — quality-assurance](phase-09-quality-assurance.md)
10. [P10 — final-review](phase-10-final-review.md)
11. [P11 — evidence](phase-11-evidence.md)
12. [P12 — documentation](phase-12-documentation.md)
13. [P13 — release](phase-13-release.md)

## 完了チェックリスト
- [ ] C1 用途・読者・主題・必須事実・表現形式を制作ごとに確認し、既回答を重複質問しない
- [ ] C2 13案は固定型でなく毎回新構図。写真・漫画・手書き・イラスト等から希望を確認し、構図差を3要素以上持つ
- [ ] C3 少なくとも白系・黒系各1案を含み、白系は外周8mm純白と外向き白gradient、写真境界は自然になじむ
- [ ] C4 下部の登壇・相談・日時・住所・料金を紙面全体の中心で配置し、QR除外幅の中心を使わない
- [ ] C5 既定の写真・最新ロゴ・参考21・完成13例を同梱し、毎回選択、公開範囲、子供・顔・PC画面・別イベント文字の保護を確認する
- [ ] C6 背景を実際に新生成し、生成手段が無い時は確認。文字/QR/ロゴを独立レイヤーとし、プロンプト・出力SHAを保存する
- [ ] C7 情報は最小限、主題最優先。意味群の近接、役割別フォント・可読サイズ、CTAと補足分離を実装する
- [ ] C8 HTML・PDF・PDF由来PNG・比較一覧を生成し、全案のQR読取、安全域、文字欠け、中心軸、外縁、入力鮮度を検査する
- [ ] C9 全案PNGの個別目視とSHA照合を完了条件とし、未検証・失敗時に完成扱いしない
- [ ] C10 Claude Code/Codex双方のmanifest・ローカル導入パッケージ・更新version・検証結果がそろう
- [ ] C11 13フェーズ・component inventory・task graph・build handoffをplanner仕様に沿って保持する
- [ ] C12 旧成果物と利用者のグローバル設定を変更せず、個人素材を含むキットを公開配布しない
- [ ] C13 現物診断・提案評価・制作・完成画像評価の4段階を別contextの担当が持ち、各担当がlocal agentとstage契約を備え、評価担当は制作物/分析を修正できない。段階横断の専門知見(構図・文字・配色)は参照資料として各担当が読み、専門役をagentとして起動しない
- [ ] C14 改善周回は工程全体で最大3回とし、提案の再評価で数え直さず、同一画像と同一所見の反復と好みだけの所見を進捗・周回に数えない。上限で未達ならINCOMPLETEと未解決項目を返す
- [ ] C15 制作ごとに原依頼と本質成果を不変の基準として固定し、各周回の所見を本質/好みに区分し(本質区分は失敗した本質成果基準の観測を必須とする)、原依頼との差分を記録する。完了は本質成果のPASSで判定し、決定論検査の失敗は制作へ、目的・事実・公開範囲のずれは分析へ戻す
- [ ] C16 評価は費用に比例させる。決定論検査で判定済みの項目をLLM評価へ回さず、LLM評価は実見が要る項目に限り、画像SHA・要求・規範が同じ案の案単位の実見判定は再利用し、標準制作で起動するLLM担当数を呼出記録から数えて本質アンカーの予算内に収める
- [ ] C17 プラグイン自体の改善では、追加・変更する規則と担当が現行の本質成果IDと同梱の実事例に解決する根拠を持ち、担当数・LLM評価の予算・本質成果の数が直前リリースの基準を超えず(超過は利用者の承認記録がある時だけ)、golden事例の決定論検査が後退しないことをessence-checkで機械判定する

## 受入確認
制作入口で形式・白黒・素材を指定→新規project→生成した背景取込→紙面中央の文字→PDF/PNG出力→全案検査→個別目視→納品。一度中央をQR除外中心に変えて失敗、白黒欠落で失敗、旧画像SHAで失敗を確認する。漫画・手書き用のヒアリング/プロンプトも確認する。両ホストmanifest/Claude validate/Codex隔離localcatalog導入を検証し、実セッションの未実施範囲を明記する。
既存紙面の改善では、元画像→run-analyze-flyerの診断→assign-flyer-analysis-reviewのPASS→flyer-producerの再制作→assign-flyer-reviewの新画像評価→納品の順が同一案件dirで追えることを見る。評価担当がWriteを使えないこと、FIXを3回受けた後の4回目が始まらずINCOMPLETEで止まること、agents/にflyer-reviewerと専門役3本が残らず4skillがflyer.py入口だけを使うことも確認する。
本質への適合は、同じ案件dirのbriefに原依頼の原文とhashが固定され、delivery.jsonの各周回に原依頼との差分・所見の本質/好み区分・FIXの振分先が残り、文字欠けのFIXが分析を経ず制作へ戻り、好みだけの所見で周回が増えず、SHAが変わらない案の判定が再利用されていることで見る。プラグインの改善では、本質成果IDの無いcapabilityを1つ足すとpython3 scripts/flyer.py essence-checkが失敗し、外すと通ることを一度確認する。

## 実行境界と責務写像
`task-graph.json`はcanonical fixed-13-phaseの参照射影であり、dispatch-readyではない。`verification-claim`と`task_spec_ref:null`を含むため、そのまま実行envelopeへ渡さない。将来の自動dispatch対応は別依頼で正規task specへ昇格する。上流のderiver/consumerは変更しない。

同一チェックを9実体へ複製しないため、component固有の受入契約は評価担当C03/C07をP01（入力・拒否条件・返却範囲・読取専用・本質/好みの区分）、呼出と共通入口C02/C05/C12をP02（呼出・集約・FIX振分・共通入口とessence-check）、制作と分析の実行系C01/C04/C06/C08をP05に一意に置く。残るphaseはplugin全体の作業で`entities_covered: []`とする。要件IDはgoal-specのC1..C17、実体IDはinventoryのC01..C08とC12であり別名前空間。C09-C11は1.2.0の共有専門役3本を参照資料のlensへ畳んだ欠番で、過去周回の記録と対応させるため番号を振り直さない。前回計画のC03(agents/flyer-reviewer)は、1.2.0の現物に合わせてstage localのvisual-review-coordinatorへ置き換えた。

| 要件 | 実体・正本 | 判定工程 |
|---|---|---|
| C1/C2 | C01: references/interview.md・schemas/concepts.schema.json | P04/P07 |
| C3/C4/C7 | C01: references/design-rules.md・schemas/scene.schema.json | P06/P09 |
| C5 | C01素材取込、C03公開範囲実見: assets/catalog.json | P01/P09 |
| C6 | C01: prompts/background.md・references/workflow.md | P05/P07（生成未実施は未実施と記録） |
| C8/C9 | C01出力、C02集約、C03個別実見: out/checks.json・visual-review.json | P06/P09/P10 |
| C10/C12 | plugin-level: scripts/package.py・INSTALL.md | P11/P13 |
| C11 | development-plan全体 | P03/P10 |
| C13 | C04/C05/C01/C02の4skill、stage local agent C03/C06/C07/C08、知見lens: skills/*/references/*-contract.md・plugin-composition.yaml・references/design-knowledge-index.json | P01/P02/P04/P07 |
| C14 | C01の戻り先とplugin-composition.yamlのrevisionBudget、C12入口の周回記録 | P02/P04/P05/P07 |
| C15 | C01のbrief/delivery.json、C02のFIX振分、C03/C07の本質/好み区分: references/essence.json | P01/P02/P05/P07/P10 |
| C16 | C02の判定再利用と呼出記録、C03/C07の決定論済み項目の除外、essence.jsonの予算 | P01/P02/P04/P07 |
| C17 | C12のessence-check、essence-baseline.jsonと承認記録、plugin-composition.yamlのserves/evidence、golden事例と試験 | P02/P04/P09 |

## 導入・実行証拠の状態
今回の納品受入は私有キットの自己完結、manifest検証、隔離コピーの実描画まで。実環境installは`verify.live:false`の理由によりdeferred。P13に保持するcanonical release/registry/isolated条項はHarnessHub全体の将来再実行契約であり、私有キットの同等検査をそのreceiptとして偽装しない。未実行の工程は未チェックで残す。新規背景生成・新規13案・漫画/手書きの実描画・各ホストの本物セッション実走は、実際の証拠が無い限り未検証と明示する。1.2.0で取得したfresh検査・独立監査のPASSは1.2.0の入力に対する証拠であり、本計画の改善(agent配置・入口・権限・本質アンカー)を反映した版の証拠として転用しない。

将来consumerを使う場合の第一導線は`task-execution-report.html`、差分は`task-progress.md`、機械状態は`task-graph-status.json`。今回それらは生成しておらず、実行証拠は`../verification/README.md`から参照する。

`envelope-draft/plugin.json`の`entry_points`はplannerの網羅性照合用宣言である。ネイティブClaude manifestへはこの独自キーを転記せず、`skills: ./skills/`と標準agents discoveryへ写像する。実際の配布manifestは`.claude-plugin/plugin.json`/`.codex-plugin/plugin.json`をネイティブvalidatorで別途検査する。
