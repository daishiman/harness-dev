# 実走fixtureの共通実行契約

これは公開system-spec-harness 0.1.24とC19の既存契約を各独立contextへ届けるプロジェクト指示であり、判定基準・権限・予算・資料を変更しない。過去の評価結果は今回の判断に使わない。出力は日本語とする。

各Skill/Agentは担当の出力を作る前に、このCLAUDE.local.mdをReadし、自分のSKILL.md・起動adapter・責務prompt・必読SSOTをfrontmatterも含め全文取得する。親のReadや親の会話を、自分が読んだ証拠と数えない。内容がツール上限で欠けたら残りを取得し、見出し/先頭/grep/存在確認で意味評価を代用しない。sourceが許すtool/CLIと読取専用境界を守り、sourceやguard/この指示を編集しない。

C05 completeness evaluatorでは、R1-scoreとR2-delegate、scoring-rubric.json、aspect-criteria.md、resource-map.yamlと指定schemaを全文取得し、spec_dir内の全Markdownとstate/refsを意味評価する。設計知識はC04 mapと各章の確定要件への具体適用を照合する。3監査の実completion/台帳が揃うまで合格にしない。

C05のprompt_qualityは、plugins/system-spec-harness/skills/*/prompts/*.mdの全18件が対象。全件のC1-C4（Layer役割、L7からL1への整合、再現性、Self-Evaluation）を、この独立contextで内容を読んで意味評価し、既存schemaが認めるsummary/findings等にprompt別の実根拠を残す。R1/R2だけの標本評価・機械validatorの形状PASS・既存レビューの存在確認で残りをPASSにしない。外部prompt-creator未導入時のstandalone例外は機械gateだけで、意味評価の免除ではない。未実施/根拠不足なら通常どおりINDETERMINATE/FAILを返す。期待する判定や点数は指定しない。

C05の保存境界はR1-score 4.3/R2-delegate 2.4どおり。書けるのは許可されたhearing-audit.jsonの無改変保存と引数outputの評価レポートだけ。Write/Edit、catリダイレクト、heredocでのPython script生成、scratch/tmpへの自作report builder保存・実行はしない。レポートはpython3 -cでliteralのpathlib.Pathへsys.stdin.read()を無改変保存し、引用JSON heredocに妥当なJSONだけを渡す。正規検証CLIを使い、レポートやreceiptの自己緑化をしない。既存sourceの正常なliteral保存先修正は可能。

C06/C07/C08は起動adapterだけで責務が完結したとみなさず、adapterが指す責務SSOTと必読資料を全文取得する。C08は出力前にskills/run-system-spec-doc-fetch/prompts/R4-audit-doc-freshness.mdを必ず読み、R4 Layer3が指定する公式source catalog等を読み、公式サイトの実再照合を行う。未読SSOTがある状態で監査PASSにしない。sourceにない新しい許可・検査免除は設けない。

C19親は固定C24 root、各周回3CLI実測後のIN1、6キー/hash、親が所有する集約ログ、責務Verifierの実完了を守る。C02は評価済み内容のみを正規single writerで登録し、pre-choiceの実成果提示と選択/baseline、source lineage/evaluated_digest/readiness、独立整合性監査を守る。途中で人に追加判断を求めず、実際の失敗は失敗として完了markerに記す。

## C05 の明示ツール境界と索引
C05自身はfilesystem本文・索引・promptをReadで取得する。C05がBashを使えるのはpython3で正規の検査CLIを実行する場合と、R1-score4.3のliteral保存だけである。C05でcat/ls/find/grep/sed/head/tail/wc/awk等のshell調査を行わず、python3 -cの自作探索/reader/報告builderにも置換しない。CLIと入力/出力は絶対パスで渡し、Readで必要な本文を揃える。検査のstdoutやsnapshotをtmpへredirect保存せず、artifact_snapshot/gate_resultsには正規CLI応答をそのまま使い、保存先は許可2JSONだけとする。standaloneで外部PCが無ければsourceの機械gate例外だけを正確に記し、root全体/別repoの探索をしない。
C05が必ず全文ReadするC04索引は plugins/system-spec-harness/skills/ref-system-design-knowledge/references/resource-map.yaml である。C05自身の references/resource-map.yaml とは別物であり、両方を読む。各章の原則採否とC04 mapの対応・新要件への具体適用を自前で検証する。
次はsourceから列挙した18promptの入力inventoryだけであり、評価済み/合格を意味しない。各fileは自分で全文ReadしC1-C4を意味評価する。
- plugins/system-spec-harness/skills/assign-system-spec-completeness-evaluator/prompts/R1-score.md sha256=ef674d2766f992048676482ad8d671440966a21df20898014c4e19ad8e488c43
- plugins/system-spec-harness/skills/assign-system-spec-completeness-evaluator/prompts/R2-delegate.md sha256=030f8c2da816b0fd46a835e1f8d05c7d9e1d09c4624cd97f02c37a9b94b90309
- plugins/system-spec-harness/skills/ref-system-design-knowledge/prompts/R1-system-design-knowledge.md sha256=a2953c59442019e0174a6bdbbe4b1efd7ea14fe3286c4b3e4c4565f76470f538
- plugins/system-spec-harness/skills/run-system-spec-compile/prompts/R1-assemble.md sha256=e826d94dafcbddb9296a22c08132f8cb44d5a02bce06e022673222ee51eb1eb6
- plugins/system-spec-harness/skills/run-system-spec-compile/prompts/R2-render.md sha256=f111f404b3df1f684571efa90b9ca3406c943be1fa5aa49326ab4f9444f038b5
- plugins/system-spec-harness/skills/run-system-spec-compile/prompts/R3-crosslink.md sha256=894783fe8485bf5d382230fc6817661507b2ddc5cc29315117d8b99453c6b664
- plugins/system-spec-harness/skills/run-system-spec-doc-fetch/prompts/R1-identify.md sha256=f5b6ef403f0ffca13adaf78a80a6d990cb6529d408eb1a5cb436502712d8404d
- plugins/system-spec-harness/skills/run-system-spec-doc-fetch/prompts/R2-fetch.md sha256=c74acafdc2abed1141cdc26f7f4a42b7d0062556e5168588f72e46da4b7587d5
- plugins/system-spec-harness/skills/run-system-spec-doc-fetch/prompts/R3-record.md sha256=df225877a020e1fada8e98b0566373267bdb58614de96bca72cd7339e5e09e28
- plugins/system-spec-harness/skills/run-system-spec-doc-fetch/prompts/R4-audit-doc-freshness.md sha256=3fb7ee09926bff77cba880f07bd929242012fea0d08af2a6a0a1b94ebb742501
- plugins/system-spec-harness/skills/run-system-spec-elicit/prompts/R0-foundation.md sha256=6504ed986790f356c898a296e1c819631305d7e663f44168c4aa9b428597cd83
- plugins/system-spec-harness/skills/run-system-spec-elicit/prompts/R1-init.md sha256=0c680368e000645b74dab2c62852adbdb78458bf68e348597ada3875ee83bf6f
- plugins/system-spec-harness/skills/run-system-spec-elicit/prompts/R2-interview.md sha256=6dbe8048720b950e17daac8425a44a295c9c2255e0293ec315e04323facac084
- plugins/system-spec-harness/skills/run-system-spec-elicit/prompts/R3-reask.md sha256=16ad7f236badf040ffbc9ac790871b17dc7b7cc4c69523c1f606b2a6e2bed9b8
- plugins/system-spec-harness/skills/run-system-spec-elicit/prompts/R4-reopen.md sha256=113078305c2284c6b7e61867534b78da3a30272f5c8800b5a5760872b0cb4fca
- plugins/system-spec-harness/skills/run-system-spec-elicit/prompts/R5-decision-guide.md sha256=e53d1dff697e2a5cb034e6487f32f4b10121867032fd47c3d20746f143db37d9
- plugins/system-spec-harness/skills/run-system-spec-elicit/prompts/R6-audit-hearing.md sha256=9521a9048ef144a307ee50508dc16895b86c105a1891a6d805669b3fa82f2e83
- plugins/system-spec-harness/skills/run-system-spec-elicit/prompts/R7-audit-matrix.md sha256=ab3562ed3d238504886b95c17942cda95c92d8e4900755994860ad47cff8cdac

## C19 main の固定root前置き（診断を含む全Bash）
C19本体のmain contextが呼ぶBashは、observer自己診断、readonly Python、JSON確認、進捗記録を含め全件、次の文字列をcommandの先頭へ毎回書く。shell状態を前呼出しから継承したと仮定しない。開始C24 receiptがこのrootと一致しなければ停止し、再探索でrootを付け替えない。
`export CLAUDE_PROJECT_DIR="/private/tmp/claude-501/pr86-ci-live/lt/runs/sysspec118/fx" && cd -- "$CLAUDE_PROJECT_DIR" && [ "$(pwd -P)" = "$CLAUDE_PROJECT_DIR" ] && `
source進行に不要なobserver自己診断は親が新しいBashで行わずReadを使い、担当Verifierへ実検証を任せる。この前置きはmain streamの親に適用する。C05 child自身は既定のRead/正規python3 CLIと絶対パスを使い、C05のBash制約に反するshell setupを追加しない。
## native foreground mode
起動前からCLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1である。Agent/Bashのrun_in_background parameterは存在せず、context:fork SkillとAgentは同期完了する。明示background/name指定をせず、利用できるforeground APIだけを使う。C05監査は1message1Agent、実final responseと台帳のresolvedを確認してから次の監査を呼ぶ。source通りAUDIT_DISPATCH: <unique-token>をpromptへ逐語で渡し、auditorのechoとmarkerを束縛する。起動受付/名前/自己申告を完了や判定に置換しない。これは既存foreground契約を保つ実行設定であり、監査省略やPASS免除ではない。

## 全run Skillの選択前提示（source既存契約）
最小の実成果物を作成しparse/open等のminimal guardが通ったら、choiceを記録する前の別呼出しで、現物の絶対path・実SHA256・『開き方: less <絶対path>』をstdoutまたは応答へ提示する。choice記録JSON内のopen_withだけを、選択前の実提示へ代用しない。C19 preflight report、elicit、compile、C02全て同じ既存契約である。
## C02登録の正式な実行分岐（source既存契約）
C02の選択前の最小成果物は実際にcanonical writerでatomic登録したtyped node/packageであり、dry-run/write_count0のpreviewではない。C05完了後にだけC02を呼び、C02のR1/R2/R3と本文を全文取得する。main contextでpre-choiceの実成果物を正規writerで作る段階と、standard後の未達responsibilityをAgentへforkする段階を混同しない。pre-choiceのcanonical addで依頼された2nodeを登録済みなら、その実node/receiptのpath・digest・開き方を別callで提示してから事前回答standardを記録し、直後の現物graphをbaselineとして一度だけ固定する。この場合post-choice未達writerは無いため、writer_receiptsへpre-choice receiptを足さず、未達を捏造しない。まだ未達writerがある場合は担当R-id/固定C24 receipt/入力を渡してAgentの分離contextで実行し、mainが直接add/updateする代用は禁止。どちらの分岐でもstandard後の独立dev-graph-integrity-auditorは実際のAgentで起動し、現在graphとreceiptのdigestを照合してからC02完了とする。dry-run previewだけでstandardを記録し、mainがpost-choice addする経路は禁止。これはC02本文のpre-choice commit/baseline/未達fork規則を再掲したものであり、source/検査/criterionの変更や免除ではない。
## native監査adapterのfrontmatter入力
次はboot時にpinした実sourceのfrontmatterそのもの。nativeは対応adapter本文をsystemへ投入するため、各監査AgentはこのCLAUDE.local.mdの全文Readで下記metadataと自分のnative system本文を併せて全文取得できる。資料不足を推測で補わず、native本文投入が無ければ自分のadapter全fileをReadする。監査SSOT/必読資料の個別全文Readは引き続き必須。

### system-spec-hearing-auditor
```yaml
---
name: system-spec-hearing-auditor
description: 往復ヒアリングの質問設計と回答反映を独立 context で監査し、聞き漏れ/誘導質問/早期停止/根拠切れ/foundation の利用者根拠欠落を検出したいときに使う。
kind: agent
tools: Read, Bash
model: sonnet
isolation: fork
phase: audit
version: 0.1.0
owner: team-platform
prompt_ssot: ../skills/run-system-spec-elicit/prompts/R6-audit-hearing.md
responsibility_id: R6-audit-hearing
---
```

### system-spec-matrix-auditor
```yaml
---
name: system-spec-matrix-auditor
description: カテゴリ×プラットフォームの収集マトリクス状態を独立 context で監査し、未収集セルの放置や対象外理由の妥当性を検証したいときに使う。
kind: agent
tools: Read, Bash
model: sonnet
isolation: fork
phase: verify
version: 0.1.0
owner: team-platform
prompt_ssot: ../skills/run-system-spec-elicit/prompts/R7-audit-matrix.md
responsibility_id: R7-audit-matrix
---
```

### system-spec-doc-freshness-auditor
```yaml
---
name: system-spec-doc-freshness-auditor
description: 取得済み公式ドキュメントを独立 context で公式サイトへ再照合し、対象一覧の欠落・非公式host・古いversion/更新日・確認時刻や出典の欠落を検出したいときに使う。
kind: agent
tools: Read, Bash, WebSearch, WebFetch
model: sonnet
isolation: fork
phase: verify
version: 0.1.0
owner: team-platform
prompt_ssot: ../skills/run-system-spec-doc-fetch/prompts/R4-audit-doc-freshness.md
responsibility_id: R4-audit-doc-freshness
---
```

runnerは既存C02契約の誤記録を防ぐ補助read-only guardを使う。Write toolでgraph.nodes空のままC02 standardを記録すると拒否するだけで、成果物/監査/判定を生成しない。拒否を別toolへ置換して回避せず、sourceのpre-choice実成果物作成・検査・提示を履行する。guardが受理したことをsource全遵守やPASSの証拠としない。

### C02 native Skill frontmatter input
C02もSkill本文にはfrontmatterが無いので、boot pinした次の原文とnative本文を併せて取得する。C02の責務promptは各出力前に個別に全文Readする。
```yaml
---
name: run-dev-graph-node
description: dev-graph artifact を正規 path へ atomic 追加・差分更新したいとき、system-dev-planner の exact 13 phase task package を all-or-none 登録したいときに使う。
version: 0.2.0
owner: harness maintainers
source: plugin-plans/dev-graph/component-inventory.json#C02
kind: run
effect: local-artifact
prefix: run
hierarchy: L1
user-invocable: true
argument-hint: "<add|update|bind-github|link-github|register-package> [--repo-root PATH] [--input PATH] [--dry-run]"
allowed-tools: [Read, Write, Edit, Bash, Glob, Grep, AskUserQuestion, Skill, Agent]
script_refs: [../../scripts/_common.py, ../../scripts/resolve-repo-context.py, ../../scripts/validate-graph-schema.py, ../../scripts/build-graph-node.py, ../../scripts/register-package.py, ../../scripts/validate-source-lineage.py]
schema_refs: [../../schemas/graph-node.schema.json, ../../schemas/package-registration-receipt.schema.json]
reference_refs: [../../schemas/graph-node.schema.json, ../../templates/template-contract.json, ../../references/feature-execution-package-contract.md, ../../references/prompt-common-layers.md, ../../agents/dev-graph-integrity-auditor.md]
responsibility_refs:
  - prompts/R0-context.md
  - prompts/R1-classify.md
  - prompts/R2-preview.md
  - prompts/R3-write.md
  - prompts/R4-apply-template.md
responsibilities:
  - id: R0-context
    name: context
    prompt_required: true
    summary: "C24でcaller repo/config/content rootsを解決し、全read/write realpathがroot内であることをpreflightする"
  - id: R1-classify
    name: classify
    prompt_required: true
    summary: "成果物内容からartifact_kind/domain/project_id候補、confidence、reason、候補pathを推定する。保存先を質問しない"
  - id: R2-preview
    name: preview
    prompt_required: true
    summary: "分類previewを提示し、閾値未達時だけ確認して正規pathを確定する"
  - id: R3-write
    name: write
    prompt_required: true
    summary: "artifact_kindからtemplateを選び単一transactionで差分書込みする。feature package登録はexact 13 nodeのP01..P13、共通parent/package、機能内dependency/bindingを検証しpartial 0件のreceiptを生成する"
  - id: R4-apply-template
    name: apply-template
    prompt_required: true
    summary: "確定したartifact_kind (architectureはsubtype複数選択、specificationはAPI変更有無) からtemplates/template-contract.jsonが示す本文骨格を適用し、template_id/template_version/artifact_subtypesをfrontmatterへ書き込む。既存文書は全書換せず不足セクションのみ差分追記する (要件C18/C19)"
combinators:
  - with-goal-seek
  - with-feedback-contract
goal_seek:
  activation_state: semantic_evaluator_started
  engine: inline
  fork: subagent
  max_loops: 5
completeness_exempt:
  - "manifest: goal_seek.engine=inline が未達 checklist から実行局面を都度選ぶため、固定 phase の workflow-manifest.json は適用外。停止条件と配線は本文 ## ゴールシーク実行を正本とする。"
feedback_contract:
  activation_state: semantic_evaluator_started
  max_iterations: 3
  criteria:
    - id: IN1
      loop_scope: inner
      text: "validate-graph-schema.py でノード書込み前検証しスキーマの必須キー欠落が 0 件"
      verify_by: script
    - id: OUT1
      loop_scope: outer
      text: "通常5 artifact混在入力は自動routingされ、featureはC14 macro contractだけからfeatures/へ入り、連続更新後もfrontmatter/path整合性が維持される"
      verify_by: live-trial
    - id: OUT2
      loop_scope: outer
      text: "新規ノード作成時にartifact_kind (architectureは選択したsubtype全て、specificationはAPI変更有無に応じたapi-contract合成) に対応する本文必須セクション見出しが欠落0件で適用されることを受入テストが確認する (要件C18/C19)"
      verify_by: test
    - id: OUT3
      loop_scope: outer
      text: "12/14 task、phase欠落/重複、mixed parent/package、cross-feature edgeを注入するとapplied_count=0。正常時はexpected_count=applied_count=13、P01..P13/node exact-set、graph_revision付きreceiptとなる"
      verify_by: test
artifact_delivery:
  contract: artifact-delivery-v1
  state_machine:
    initial: artifact_created
    states: [artifact_created, minimal_guard_passed, artifact_presented, user_choice_recorded, semantic_evaluator_started, handoff_complete]
    transitions:
      - {from: artifact_created, event: minimum_guard_pass, to: minimal_guard_passed}
      - {from: minimal_guard_passed, event: present_actual_artifact, to: artifact_presented}
      - {from: artifact_presented, event: record_user_choice, to: user_choice_recorded}
      - {from: user_choice_recorded, event: accept-as-is, to: handoff_complete}
      - {from: user_choice_recorded, event: "light|standard|detailed", to: semantic_evaluator_started}
      - {from: semantic_evaluator_started, event: improvement_complete, to: handoff_complete}
    pre_choice_forbidden: [semantic-evaluator, task-fork, subagent, multi-worker, revise-loop]
    accept_contexts: {evaluator: 0, improver: 0}
  release: explicit-only
  exhaustive: explicit-only
---
```
