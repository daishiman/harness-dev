# Verification-as-program protocol

## 解決する本質的課題

旧方式は品質を `route数 × review Agent数 × 思考法数 × 反復数` のプロセス完遂で近似していた。同じ入力と同じ主張を別contextで繰り返し読み、変更していない対象にも再推論が伝播するため、品質ではなくworkflow規模がtoken・時間・計算資源・費用を決めていた。

本方式は検証単位を **verification obligation（証明すべき主張）** に変更する。通常コストの支配変数は次の2つだけである。

1. 入力または依存claimが変わり、現在の証拠が無効化された obligation
2. 決定論的validatorでは証明できず、意味判断または実環境観測が残った obligation

route、Agent、思考法の個数はコストモデルに含めない。

## build stage (draft / release)

profile が「作った物にどれだけ証明を要求するか」であるのに対し、stage は「そもそもどこまで作るか」を決める**直交した別の軸**である。両者を 1 本へ潰さないのは、`build-only` を選んでも生成 obligation の集合が変わらないためである — 検証の深さを下げても、component 数と同じだけの受入テスト設計 (P04) は最後まで走る。利用者が最初の 1 本を手にするまでの時間を決めているのは検証の深さではなく生成の集合であり、profile ではそこへ手が届かない。

| stage | 実行する obligation | 繰り越すもの |
|---|---|---|
| `draft` (既定) | `stage=draft` かつ kind が `generative` / `deterministic` のもの。実体 (route build) と、それを立ち上げるのに要る phase (P01 goal-spec / P02 設計ブリーフ / P05 実装) | 受入テスト設計 (P04)、設計レビュー (P03)、P06 以降の検証・文書・リリース、および全ての `semantic` / `observational` / `audit` |
| `release` (明示) | 利用者が第1稿を試した後、全 obligation を回収 | なし |

stage は `derive-route-build-obligations.py` が `phase_ref` から決定論導出する (`DRAFT_PHASES`)。title の自然文や entity_ref の有無で判断しない。**stage 未宣言の obligation は `draft` 扱い**とする — 未分類を release へ倒すと、stage を知らない旧 contract を draft で回した瞬間に全件 defer され「何も作られていないのに何も落ちていない」計画が成立するためである。分類漏れは遅くなる側へ倒す。

**畳み込みの単位は component ではなく「component × stage」である。** task-graph の `P02-Cxx-01` / `P04-Cxx-01` はどちらも `entity_ref` に component を持つため、component 単位で route obligation へ畳むと、第1稿の route build 指示に「受入テストを赤で固定する」が同梱され、stage を分けても待ち時間が縮まらない状態が黙って成立する。`_folds_into_route()` は `component-build` (route build 本体・`phase_ref` を持たない node がある) と draft 段の node だけを畳み、release 段の node は独立した `task:<node-id>` obligation として第1稿の外へ出す。

draft は**release 完了ではないが、利用者が試せる正常な引き渡し点**である。生成/checkが残る間は `stage_gate.status=draft-building`、`handoff_ready=false`。現物のproofが揃った後だけ `status=usable-draft`、`handoff_ready=true` とする。繰越しは `deferred_to_release[]` に名前つきで残し、`auto_promote=false`、`max_repair_rounds=1` は両状態で不変。usable draft proof後は `next_gate=build-improvement-gate.py` へ渡し、初回診断と改善深度選択を経由する。完全化用のTask/Agentは追加せず、選択前の編集やrelease/exhaustive自動昇格をしない。release completed とは宣言しないが、失敗/stallとして自動修復ループへ戻してもならない。draft 側の obligation がその繰越し先に依存する場合 (実グラフの `P05-x-01 → P04-x-01` がこれにあたる)、`blocked` ではなく `defer` + `dependency-deferred` として理由を残す。両者を混ぜると「証拠が足りない」と「意図的に後ろへ回した」の区別が計画から引けなくなり、昇格時に何を回収すべきか読めない。

**stage は fingerprint に含めない。** draft で得た PASS receipt は release でそのまま再利用され、昇格は繰り越し分の追加実行だけで済む。含めてしまうと昇格のたびに全 route を作り直すことになり、二段階にした意味 (待ち時間の短縮) がそっくり失われる。

第1稿の「smoke」水準の検証は新設しない。route build ごとに dispatcher が既に回している決定論ゲート (`validate-build-trace.py` / `validate-route-build-reports.py` / `check-route-component-parity.py`) がそれであり、draft が外すのは受入テストの**設計工程**であって、成果物が壊れていないことの機械確認ではない。

## 証拠DAG

`verification-contract.json` は obligation を5種類に分類する。

| kind | owner | 通常動作 |
|---|---|---|
| `generative` | builder | route固有仕様または上流proofが変わった成果物だけ生成 |
| `deterministic` | script/schema/lint | `checker.argv` を実行しreceiptを記録 |
| `semantic` | 独立LLM裁定 | machine proof後に残る意味差分だけを1つのbatchで判定 |
| `observational` | fork/live harness | 静的に証明不能な挙動だけを観測 |
| `audit` | 30思考法catalog | `exhaustive` 明示時のみ。通常runtime fan-outに使わない |

各 fingerprint は claim、入力pathの内容digest、checker契約、上流 obligation の fingerprint から決定論導出する。このため上流や入力の変更は下流だけを無効化し、無関係な兄弟claimのPASS証拠は維持される。

## 実行契約

1. build前は `derive-route-build-obligations.py --handoff ...` でrouteとtask-graphの `direct-task` を `generative` obligationへcompileする。route全JSONでなくroute-local inventory/task node/spec sliceをfingerprint化するため、無関係なroute変更を全buildへ伝播させない。`phase-gate` は依存proofのstate projectionでありAgent workにしない。`reuse` route/taskはSubAgentを起動せずdone証拠を投影し、`generation_queue` だけをbuildする。
2. build後は graph全体の build unit を `derive-verification-contract.py --unit-manifest ... --evidence-dir <plannerと同じdir>` で1契約へまとめる。routeごとにreview sessionを作らない。`--evidence-dir` を付けると、trace (skill_name が build plan と一致するもの) の `reproducibility_gates.lint=PASS`・`build_mode`・`lint_target_sha256` (今の skill dir の digest)・`lint_brief_sha256` (今の brief の sha256) がすべて今と一致する unit を候補にし、derive が contract の checker argv (`validate-build-plan --check`) をその場で走らせ、exit 0 のときだけ `record-verification-evidence.py` 経由で build-conformance の receipt にする。trace は agent が書く自己申告で、digest は skill dir と brief しか覆わない。validate-build-plan が読む pair skill・plugin の agents・templates・checker 自身が Step 4 の後に変わっても、走らせ直した結果が receipt になる。1つでも欠けるか、checker が通らないか、planner がその obligation を `check` 以外 (今の PASS・FAIL・矛盾) と判定していれば何も書かず、従来どおり `check` が残る。contract と fingerprint はこの指定で変わらない。
3. `plan-verification-obligations.py` を実行する。このscriptはLLMを起動せず `reuse/generate/check/adjudicate/observe/audit/defer/blocked/remediate/escalate` を出力する。
4. `generate/check` を先に実行し、成果物・stdout・report等を `record-verification-evidence.py` でfingerprintへ束縛する。plannerを再実行して上流proof済みのclaimをready化する。
5. `llm_batches[]` ごとに1 contextだけ起動し、`obligation_ids` と `context_paths` だけを渡す。全repository、全route report、30思考法本文を無条件ロードしない。1 context が複数の次元を読んでも、合否は次元ごとの証拠に分けて出す。content-review では elegance を LLM が判定し、rubric の合否は `render-findings-score.py --write-rubric-verdict` が機械採点から書く。LLM が rubric に渡すのは、機械で採点できない rule の判定だけである (`content-review-protocol.md`)。
5a. 選んだ指摘を直したあとの再判定は、次の 3 点に絞る。(1) 選んだ指摘が解消したか。(2) 変わった hunk に新しい C1-C4 違反や rubric の high 違反が無いか。(3) criteria の被覆。すでに PASS した節は読み直さない。結び直しは LLM を使わない経路から先に試す。順番は `--finding-ids` → `--replay` → 変わった節だけを読む `--scoped-review` → 全体の再レビュー。差分が小さいというだけで、LLM の読み直しなしに結び直すことはしない。
6. `observe` は `observation_tier` の最小環境だけで実走する。PASS receiptが現在なら再実走しない。
7. `INCONCLUSIVE`、低confidence、同fingerprintの矛盾証拠は `escalate` とする。Agentを自動増殖させず、人間または明示 `exhaustive` へ渡す。`--evidence-dir` に中身を読めない receipt (一覧を取れないサブディレクトリ、開けない・非 UTF-8・JSON でない `*.json`) が1件でもあると、どの obligation の今の FAIL かを否定できないので、PASS を持つ obligation も再利用せず `escalate` (`reason=unreadable-receipt-blocks-reuse`) とし、該当ファイルを plan の `unreadable_receipts[]` に `{path, error}` で列挙する。直すか片付けるのは人間である。

証拠receipt自体も `evidence[].sha256` で保護する。verdict/transcript/check reportが変わったreceiptは再利用しない。

receiptは実行器が取得できる場合に `usage.input_tokens` / `output_tokens` / `elapsed_ms` / `estimated_cost_usd` を記録する。同一command invocationは固定 `run_id` を全plan/receiptへ渡し、1 contextが複数receiptを生成する場合は同じ `model_action_id` を付ける。plannerはこのjoin keyで生成・semantic batch・live観測の累積actionを重複なく数える。`cost_summary` はproof reuse率、回避した実行数、今回のgeneration/check/semantic/observation件数、semantic context bytesを返す。品質指標はAgent数や思考法数でなく、`新規finding / model action`、proof reuse率、反復finding率で観測する。

`budget_gate.status=blocked` のplanからmodel workを起動してはならない。既定incrementalはsemantic batch 1個、同一runの累積model action 4個までで、1 batchがcontext byte上限を超える場合も停止する。対象sliceを狭めるか、利用者が明示的に予算を上書きして再planする。これは静かな品質低下ではなく、費用・時間・contextの拡大を承認境界へ変換するfail-closed契約である。run全体 (初回診断・改善・検証) の上限は `run-elegant-review/references/convergence-policy.json#/run_model_action_budget` の1か所が正本で、各ループ上限から計算した最悪ケースと一致することを `validate-run-model-budget.py` が検査する。`--state-dir <gateのstate dir>` (実在するdir) を渡すと、plannerは本planの検証actionをその台帳へ予約し、残りを `budget_gate.run_budget` に出す。足りなければ何も書かず `run-model-action-budget-exceeded` でblockする。gateとlauncherも起動前に同じ台帳へ予約し、足りなければ `status=run-budget-exhausted` で何も起動しない。

台帳の約束は次の 5 つである。
- **式の検査**: `load_budget` は毎回、components/total が `compute_worst_case(bounds)` と一致するかを確かめる。合計だけを揃えた水増しの policy では、gate・launcher・planner のどれも動かない。宣言との照合は CI の CLI が受け持つ。
- **total の束縛**: 台帳は最初に予約したときの total を `budget_total` に記録する。別の policy を読んだ呼び出しは `opened with total` で拒否する。
- **やり直しで二重に引かない**: 初回診断の claim id は、claim が束縛する入力 (run・subject・baseline・binding・target・提示と選択) の hash で決まる。state の書き込みが落ちて再試行しても、同じ予約に着地する。
- **深さの選び直しで止めない**: 改善の予約は「少なくとも max_rounds」で取る。予約の後に decision の書き込みが落ちて深さを選び直したとき、足りていればそのまま使い、足りなければ差分だけを `#topup-<n>` で足す。多めに引いた分は返さない (fail-closed)。
- **検証の予約**: 検証用 model action は component `verification`、action_id `verification:<subject>` で「少なくとも required[subject]」を予約する。required は、同じ `run_id` で `verifier.kind` が `llm`/`live` の receipt を subject ごとに数えた消費 (`cost_summary.consumed_model_actions_by_subject`) に、今の subject の planned を足したものである。planner と gate は同じ plan から同じ required を出すので、後から呼んだ側は何も足さない。全 subject の差分を 1 つの lock の中で足すので、並行する検証が同じ残りを読んでも合計は total を超えない。planner の `--state-dir` を誤っても、gate が正しい台帳へ同じ量を予約し直す。検証が台帳に入ったので、gate が台帳の外の消費として足す `verification_model_actions` は 0 である (launcher は古い claim を予約し直すときだけこの値を読む)。

## trace と build plan の検査の台帳

brief のある create/update の build で、`validate-build-plan.py` と `validate-build-trace.py` が走る場所はこの表だけである。足すときは、ここに行と理由を足す。

| # | どこで | 引数 | 何を確かめるか | 残す理由 |
|---|---|---|---|---|
| P1 | Step 1 | `--brief --out` | (検査ではない) brief から `build-plan.json` を作る | 後の step が読む flags の出どころはここだけ |
| P2 | Step 4 | `--brief --check --skill-dir` | plan が求める成果物が disk にあるか | lint を PASS と書く前の、唯一の突合。落ちたら Step 2 / 3.5 へ戻る |
| P3 | Step 12 の derive の中 | 同上 (contract の checker argv) | P2 と同じ | trace の lint PASS・build_mode・2 つの digest が今と一致する unit だけ走る。digest は skill dir と brief しか覆わないが、`--check` は pair skill・plugin の agents・templates・checker 自身も読むので、P2 の結果を digest だけで使い回すとその外の変化を見逃す。agent が走らせて記録する往復は無くした (process は 1 本のまま)。一致しない unit は従来どおり `check` が残り、Step 12 で 1 回走る |
| — | create の p0-lint | 走らせない | — | `build_lint_reuse` が P2 の receipt を使い回す。digest が違うときだけ `covered_scripts` として走らせ直す |
| T1 | Step 4 | `<trace.json>` | Step 3.5 の初回記入 (lint は N/A) | lint を PASS と書く条件の一部。ここの findings で Step 3.5 を直す。Step 3.5 の中で同じ trace を検査していた 1 回は、これと重なるので外した |
| T2 | R4 の最終記入の後 | `<trace.json>` | Step 4 が lint を PASS に、`lint_target_sha256`・`lint_brief_sha256` を書き、R4 の最終記入が残りを埋めた trace (最終記入はこの 3 つを書き換えない) | どちらの書き換えも手で JSON を直す作業。後の T3・T4 は生成物の manifest を見るだけで trace JSON を読まないので、ここで落とさないと壊れた trace が P3 と p0-lint の使い回しの判定に流れる |
| T3 | Step 12.4 `build-usable-draft-proof.py` の中 | `--manifest <artifact>` (plugin-composition は `--bundle`) | 生成物の manifest (trace ではない) | proof に validator の path・sha256・exit・stdout digest を結び付ける。receipt の PASS の自己申告を信じない |
| T4 | `build-improvement-gate.py` の判定ごと | T3 と同じ | T3 と同じ | proof を作った後に生成物が変わっていないか (TOCTOU) を、判定のたびに確かめる |
| T5 | rubric の機械採点 (REG-001、`render-findings-score.py`) | `<per-skill trace>` | `eval-log/<plugin>/<skill>/skill-build-trace.json` があるときだけ | 採点が trace の正本検査を通った build だけを数える |

実行の回数は、transcript の Bash に script 名が現れた回数とは違う。`extract-harness-run-metrics.py` の `checkers` は名前の出現を数えるので、validator の本文を `sed`・`grep` で読んだ回も入り、T3〜T5 のように script の中から走る回は入らない。

## 学習ラチェット

同じ `finding_code` が同一 obligation で2回以上 `FAIL/INCONCLUSIVE` になった場合、plannerは `automation_candidates[]` に `promote-to-deterministic-checker` を出す。繰り返し発見される規則はpromptへ追記せずschema/lint/testへ昇格させる。これにより運用を重ねるほど意味判定が機械判定へ移り、LLMコストが下がる。昇格の判断と実施は人間/AI が行う。

完了時、今回だけで閉じる事実は保存しない。別案件でも判断を変えうる新規構造が証拠付きで得られた場合だけ `build-external-intelligence.py capture` を最大1件実行し、`--evidence-source` に issue/テスト系/調査元など意味的な出典を指定する。同じ失敗の自動観測は `auto-record-lesson.py` が PostToolUse から捕捉するため重ねて登録しない。対話操作の `possible_duplicate` (exit 3) は、`--merge-with` または根拠付き `--force-new --distinct-reason` で解決する。`promote` は verified 前に実行せず、`--approved-by` と `--approval-evidence-ref` を必須とする。

## 30思考法の位置づけ

30思考法は二つの実行形態に分け、proofを混ぜない。

| 形態 | 実行者 | 発火 | 効果 |
|---|---|---|---|
| 初回usable-draft診断 | `elegant-initial-draft-evaluator` 1context | usable draft完成後にartifact+contract fingerprintあたり起動認可は最大1回（別runは完了receiptを再利用） | 30レンズの簡潔な所見を先に提示し、改善深度をユーザーに聞く。release/audit proofは閉じない |
| adversarial audit | reset + 3独立analyst | 利用者が `release + exhaustive` を別途明示 | 完全監査obligationを閉じる |

初回診断は `initial-draft-review.schema.json` と `build-improvement-gate.py` で制御する。canonical method IDは `run-elegant-review/references/thought-methods.yaml` を再利用し、別の30件リストを持たない。所見提示後に `references/improvement-levels.json` の `accept-draft/light/standard/detailed/release` を質問し、回答前は `improvement.authorized=false`。`exhaustive` は既定表示せず、二重確認と `confirm_exhaustive=true` でのみ許可する。

### 初回診断の起動契約

SKILL.md Step 12.6 の起動で `build-review-launch.py` と評価Agentが守る規則。親contextのAIが手順中に判断するものではない。

- **配送lease**: launcherは `state_ref` と同じlockで `<state_ref>.launch.json` の単一active delivery leaseをatomicに取得し、gateのdurable claimを消費して `authorized=true / launch_count=1` のschema準拠requestを返す。active lease中の重複配送と再生は `authorized=false / launch_count=0` で拒否し、leaseがstaleになった場合は同一 `request_id / idempotency_key` で再配送する。同artifact+contractの完了receiptは別runでも再利用する。このleaseはexactly-once resultを保証せず、古いruntime実行が生存したまま再配送される可能性を受け入れる。unsupported runtime、durable state/identity不一致はfail-closedにする。
- **起動順序**: 評価Agentはread-onlyで思考リセットを先に行い、target manifestをfresh readする。30 method observationは固有rationaleと実在evidenceを持ち、`launch_request_id` / durable claim / runtimeに束縛して返す。launcherは `artifact_created_at < artifact_presented_at < semantic_evaluator_started_at` を検査し、choice前の起動を拒否する。

承認receiptの扱い (捏造・代理選択の禁止) は AI 自身が守る行動規則なので、ここではなく SKILL.md Step 12.6 に置く。

## 安全弁との違い

`--max-live-trials`、worker上限、context byte上限は暴走時の安全弁であり、削減原理ではない。削減原理は obligation fingerprint、依存DAG、証拠再利用、machine-first、semantic slicing、学習ラチェットである。
