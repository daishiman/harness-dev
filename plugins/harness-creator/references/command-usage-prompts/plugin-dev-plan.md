/plugin-dev-plan
# /plugin-dev-plan 用途プロンプト（30思考法エレガント検証つき）

> `/plugin-dev-plan` (実態: `run-plugin-dev-plan` skill) が生成した plan 成果物 (index.md / phase-01..13.md / component-inventory.json / **task-graph.json (デフォルト成果物)** / handoff-run-plugin-dev-plan.json) を、思考リセット後に30種の思考法で多角的に検証し、component分解・依存DAG・task-graph・handoff routeの歪みを4条件全PASSまで磨き上げるための用途プロンプト。①を実行してplanを作り、②をそのままagentへ渡して検証・改善を回す。**task-graph はデフォルト成果物**であり、handoff に `task_graph_ref` が常時付与され build は task-graph mode (依存グラフ駆動) で回る。

## ① スラッシュコマンド入力

**まずこれを打つ**。新規構想か改善構想かで引数が変わる。

### 新規プラグイン構想から plan を生成する場合

```bash
/plugin-dev-plan "<プラグイン構想を自然文で>" --intake-json <intake.jsonのパス>
```

### 既存 plan を改善構想で更新する場合

```bash
/plugin-dev-plan "<改善構想を自然文で>" --mode update --out-dir plugin-plans/<plugin-slug> --improvement-handoff <improvement-handoff.jsonのパス>
```

いずれも `run-plugin-dev-plan` を起動し、`plugin-plans/<plugin-slug>/` 配下に `component-inventory.json` / `phase-01-requirements.md`…`phase-13-release.md` / `index.md` / `task-graph.json` (**デフォルト成果物**・`derive-task-graph.py` が 13 phase §5 + inventory `depends_on` を単一 writer 射影) / `handoff-run-plugin-dev-plan.json` (`task_graph_ref` 常時付与) / `plan-findings.json` / `goal-spec.json` を生成・更新する。この生成物一式が ② の 30 思考法検証の対象であり、range外 (実プラグインの実装そのもの) は含まない。

### オプション

`/plugin-dev-plan` の全オプション（正本 = `commands/plugin-dev-plan.md`）。①では新規=`--intake-json`、更新=`--mode update`+`--improvement-handoff` の 2 典型のみ例示:

| オプション | 何を入れるか | 用途 |
|---|---|---|
| `"<構想>"`（必須・位置引数） | プラグイン構想 or 改善構想の自然文 | 何を計画するか。曖昧でも停止せず仮 slug で進む |
| `--mode create\|update` | 既定 `create` | `update` は既存 plan への Edit 差分のみ（全書換禁止） |
| `--out-dir <path>` | 出力先。既定 `plugin-plans/<slug>/` | plan 成果物の置き場を上書き |
| `--intake-json <path>` | intake.json のパス | ヒアリング結果を計画へ流し込む（新規時の入口） |
| `--next-action-json <path>` | next-action.json のパス | 分解候補を初期分解に使う。**`--intake-json` 併用時のみ有効** |
| `--improvement-handoff <path>` | improvement-handoff.json のパス | 改善成果を反映。**`--mode update` 時のみ有効** |

## ② 構造化プロンプト（説明）

> 以下 Layer1〜7 をそのまま agent に貼り付けて使う。生成直後の agent は自身の分解に確証バイアスを持つため、必ず新規 context (思考リセット) から検証を開始すること。

### Layer 1: 基本定義層

| 項目 | 内容 |
|---|---|
| プロジェクトID | PLUGIN-DEV-PLAN-ELEGANT-VERIFY |
| 最上位目的 | `/plugin-dev-plan` が生成した plan (component-inventory.json / phase-01..13.md / index.md / task-graph.json / handoff-run-plugin-dev-plan.json) を、思考リセット後30種の思考法で多角的に検証し、component分解・依存DAG・task-graph・handoff routeの歪みを4条件全PASSまで磨き上げる |
| 背景 | plan生成は目的ドリブンの自動分解であり、過剰分割/責務重複/漏れcomponent/依存断裂/単一skillへの退化を生みやすい。生成直後のagentは自らの生成物への確証バイアスを持つため、context を新規に立て初見の観察からやり直す必要がある |
| 期待成果 | component分解がMECEで依存DAGが閉じ、handoff routeとinventoryが1:1対応し、4条件(矛盾なし/漏れなし/整合性あり/依存関係整合)を全て満たすエレガントなplan状態 |
| 成功基準 | 30種の思考法を全て適用したうえで4条件が全てPASSと判定される。省略・丸めは失格 |
| スコープ | 対象=`plugin-plans/<plugin-slug>/`配下の生成物一式(component-inventory.json / phase-01..13.md / index.md / task-graph.json / handoff-run-plugin-dev-plan.json / plan-findings.json / goal-spec.json)。範囲外=planからbuildされた実プラグイン実体の実装品質(run-build-skill系の別ゲートが担当) |

### Layer 2: ドメイン定義層

#### 2.1 用語集

| 用語 | 定義 |
|---|---|
| 思考リセット | plan生成直後の確証バイアスをクリアし、生成物を初見のように観察すること。component-inventory.json等の生成物削除ではない |
| エレガント(この用途) | component分解が最小の複雑性(不要な分割・重複がない)で構想の要件を最大充足(漏れがない)する状態 |

#### 2.2 30思考法一覧(全30種・検証対象への適用観点)

| 系統 | 思考法 | この用途 (component分解/依存/handoff) での適用観点 |
|---|---|---|
| 論理分析系 | 批判的思考 | 各componentが本当に独立build_targetを持つ価値があるか、親skillへ畳めないか1件ずつ疑う |
| 論理分析系 | 演繹思考 | 5種component_kind(skill/sub-agent/command/hook/script)の定義から出発し、各capability要求がどのkindに該当するか機械的に導出する |
| 論理分析系 | 帰納的思考 | 既往plan事例(sample-plan等)のcomponent命名・粒度パターンと比較し、今回の分割粒度が粗すぎ/細かすぎに逸脱していないか判定する |
| 論理分析系 | アブダクション | depends_onの欠落やgap_refの背後にある「なぜこの依存/builderが未確定なのか」の最も説明力ある仮説を立てて裏取りする |
| 論理分析系 | 垂直思考 | phase-01→13を論理順序で1本ずつ深掘りし、直前phaseの出力が次phaseの入力契約を連続的に満たすか検証する |
| 構造分解系 | 要素分解 | component-inventory.jsonの各componentを最小責務単位まで分解し、1component=複数責務の混在がないか洗う |
| 構造分解系 | MECE | 5種kind横断で構想の必須機能が漏れなく・重複なくcomponent化されているか照合する |
| 構造分解系 | 2軸思考 | component_kind × 依存深さの2軸マトリクスで配置を俯瞰し、1kindへの偏り集中を検出する |
| 構造分解系 | プロセス思考 | 13フェーズのライフサイクル軸とcomponent build軸(inventory)が独立2軸として整合し、どちらかへの混線(phaseにbuild詳細が漏出等)がないか追う |
| メタ・抽象系 | メタ思考 | 5種kind写像ルール自体(分解プロセスそのもの)が今回の構想に妥当適用されたかを一段上から検証する |
| メタ・抽象系 | 抽象化思考 | component具体名を一旦外し必要な機能クラスタを抽象レベルで再導出し、実際のinventoryと突合する |
| メタ・抽象系 | ダブル・ループ思考 | 漏れが発覚した場合、component追加だけで終わらせず「なぜ最初の分解ルールがそれを見落としたか」前提自体を見直す |
| 発想・拡張系 | ブレインストーミング | 制約を外し「他にどんなcomponentがあり得るか」を量的に発散させ、inventoryとの差分から漏れ候補を拾う |
| 発想・拡張系 | 水平思考 | 類似plugin(company-master/notion-gmail-send等)の分解パターンを借用し、今回planの死角を横展開で照らす |
| 発想・拡張系 | 逆説思考 | 「componentを増やすほど品質が上がる」前提を疑い、過剰分割がむしろ依存DAGを複雑化し保守性を落とす逆説ケースを探す |
| 発想・拡張系 | 類推思考 | 既存の類似pluginのcomponent構成と類推し、今回省略されたcomponent種別がないか照合する |
| 発想・拡張系 | if思考 | 各componentを「もし存在しなかったら」で思考実験し、plan成立に本当に必須か裏付ける |
| 発想・拡張系 | 素人思考 | 初見の開発者としてindex.mdだけを読み、component役割分担が説明なしで理解できるか純朴に確認する |
| システム系 | システム思考 | plan全体をcomponent間の入出力ネットワークとして俯瞰し、孤立ノード(誰からも参照されないdepends_on)や単一障害点を検出する |
| システム系 | 因果関係分析 | 「構想要件→機能→component」の因果連鎖を逆算し、途中の因果が飛躍していないか(根拠なきcomponent)を確認する |
| システム系 | 因果ループ | depends_onの循環参照(A→B→C→A)を検出し、循環があればDAG違反として指摘する |
| 戦略・価値系 | トレードオン思考 | 「分割の独立性」と「統合の単純性」を両立させる配置(共有scriptのplugin-root hoist等)を探し、単純なトレードオフで妥協しない |
| 戦略・価値系 | プラスサム思考 | builder(run-skill-create/run-build-skill/plugin-scaffold)間の責務分担が互いの手戻りを減らし合う配置になっているか検証する |
| 戦略・価値系 | 価値提案思考 | 各componentが構想のどのユーザー価値に直結しているかを1行で言えるか確認し、価値に紐付かないcomponentを疑う |
| 戦略・価値系 | 戦略的思考 | gap_refのlate-binding(builder未確定)とplacement_scopeの引用設計が、将来の拡張・再利用を見据えた設計になっているか評価する |
| 問題解決系 | why思考 | 「なぜこのcomponentが単一skillに退化した/しなかったか」を5回掘り下げ根本原因を特定する |
| 問題解決系 | 改善思考 | 検出した歪み(過剰分割/重複/漏れ)を`--mode update`のEdit差分として最小改善に落とし込む |
| 問題解決系 | 仮説思考 | 「この分解は最適である」という仮説を立て、反証(漏れ/重複/依存断裂の実例)を探しにいく |
| 問題解決系 | 論点思考 | 4条件PASSに直結する本質論点と、命名の好み等の非本質論点を切り分ける |
| 問題解決系 | KJ法 | Phase2の3並列agentが出したfindingsをカード化しグルーピングし、同一根本原因由来の重複指摘を統合する |

#### 2.3 検証4条件 (この用途での読み替え)

| 条件 | 読み替え |
|---|---|
| 矛盾なし | component間/仕様書間(phase-*.md/index.md/inventory)で相反しない |
| 漏れなし | 構想を満たす必須componentが揃う(5種kind検討証跡込み) |
| 整合性あり | 命名・schema・フォーマットが統一されている |
| 依存関係整合 | component依存DAGが成立し、handoff routeとinventoryが1:1対応し、**task-graph.json がデフォルト成果物として在り (validate-task-graph 8検査=DAG非循環/orphan 0/producer一意/非正準拒否 が exit0)・handoff に `task_graph_ref` が常時付与**されている |

#### 2.4 ビジネスルール

- CONST_001: リセット=削除でなくクリア。plan成果物(component-inventory.json等)を物理削除しない
- CONST_002: 30種全使用・省略禁止。1つでも欠けたら検証は不完全
- CONST_003: 4条件(矛盾なし/漏れなし/整合性あり/依存関係整合)全充足まで反復する

### Layer 3: インフラ層

- **Agent Team (SubAgent並列)**: Phase2の3 agent(論理・構造/メタ・発想/システム・戦略・問題解決)をSubAgent forkで並列起動し、plan生成物一式をread-onlyで解析する
- **Codex (改善の外部委譲)**: Phase3の改善パッチ適用を、必要に応じてCodex等の外部エージェントへ委譲する選択肢を持つ(`--mode update`のEdit差分として)

| 参照物 | 用途 |
|---|---|
| `plugin-plans/<plugin-slug>/component-inventory.json` | component分解・依存DAG・quality_gates/harness_coverageの検証対象 |
| `plugin-plans/<plugin-slug>/phase-01-requirements.md`…`phase-13-release.md` | ライフサイクル軸の整合検証対象 |
| `plugin-plans/<plugin-slug>/index.md` | 目次+plugin_meta+受入確認の整合検証対象 |
| `plugin-plans/<plugin-slug>/task-graph.json` | **デフォルト成果物**。依存グラフ (nodes/edges) の非循環・orphan 0・producer 一意・inventory `depends_on` 整合の検証対象 (build を task-graph mode で駆動する第一級成果物) |
| `plugin-plans/<plugin-slug>/handoff-run-plugin-dev-plan.json` | routeとinventoryの1:1対応 + `task_graph_ref` 常時付与の検証対象 |
| `plugin-plans/<plugin-slug>/plan-findings.json` | 既存4条件評価との突合対象 |
| `plugin-plans/<plugin-slug>/goal-spec.json` | 構想原文(purpose/background/goal/checklist)との漏れなし照合対象 |

### Layer 4: 共通ポリシー層

- 30思考法を全使用する(省略禁止)
- 改善提案には適用した思考法を根拠として明示する(findingごとに「どの思考法で検出したか」を記録)
- 4条件(矛盾なし/漏れなし/整合性あり/依存関係整合)を全充足するまで反復する
- **エスカレーション**: 改善方向がagent間で分かれた場合はユーザーに確認する。component の大幅な統合/分割の見直し(構造変更)はユーザー承認を得てから適用する

### Layer 5: エージェント定義層

| Agent | 役割 | 担当思考法 |
|---|---|---|
| Agent1 | 思考リセット俯瞰: plan生成物一式をread-onlyで初見のように観察し、purpose/scope/前提/事実と仮定を抽出する(既存rubric語彙を持ち込まない) | なし(観察のみ) |
| Agent2 | 論理・構造: component-inventory.jsonの分解粒度・網羅性を解剖する | 批判的思考/演繹思考/帰納的思考/アブダクション/垂直思考/要素分解/MECE/2軸思考/プロセス思考 (9) |
| Agent3 | メタ・発想: 死角・省略候補を発散的に洗い出す | メタ思考/抽象化思考/ダブル・ループ思考/ブレインストーミング/水平思考/逆説思考/類推思考/if思考/素人思考 (9) |
| Agent4 | システム・戦略・問題解決: depends_on DAG・handoff route・builder配置の全体最適を評価する | システム思考/因果関係分析/因果ループ/トレードオン思考/プラスサム思考/価値提案思考/戦略的思考/why思考/改善思考/仮説思考/論点思考/KJ法 (12) |
| Agent5 | 改善実行: Agent2〜4のfindingsを統合(KJ法で重複解消)→4条件PASSに直結する論点を優先順位付け→独立な修正はSubAgent並列で`--mode update`のEdit差分として適用、依存する修正は直列適用→4条件を再検証する | — (統合・実行担当) |

### Layer 6: オーケストレーション層

1. **Phase1 思考リセット (必須ゲート)**: Agent1がplan生成物一式をread-onlyで俯瞰観察し、purpose/scope/前提の要約を成立させる。この要約が揃わない限りPhase2へ進まない
2. **Phase2 3並列分析 (全完了ゲート)**: Agent2/3/4をPhase1出力のみを共有入力として並列実行する。3 agentは互いのfindingsを参照しない(独立性原則)。全3 agent完了をゲートとしPhase3へ進む
3. **Phase3 改善実行**: Agent5がfindingsを統合・優先順位付けし、独立修正はSubAgent並列/依存修正は直列で適用→4条件を再検証する。未PASSはPhase2へ差し戻す
4. 最大反復3回。3回を超えて4条件未充足の場合はユーザーへエスカレーションする

### Layer 7: UserInput層

まず ① を実行し、`plugin-plans/<plugin-slug>/` に plan を生成する。生成された plan (`component-inventory.json`/`phase-01..13.md`/`index.md`/`task-graph.json`/`handoff-run-plugin-dev-plan.json`) に対して、本プロンプト(②)をそのままagentへ貼り付け、思考リセット(Phase1)→30思考法並列分析(Phase2)→4条件検証→改善実行(Phase3)を回す。task-graph はデフォルト成果物ゆえ、その欠落・非循環違反・`task_graph_ref` 未付与は依存関係整合(4条件)の不合格として扱う。改善は `--mode update` で元planへEdit差分として反映し、component の大幅な統合/分割見直しはユーザー承認を得てから適用する。
次の内容を元に実行してください。@
