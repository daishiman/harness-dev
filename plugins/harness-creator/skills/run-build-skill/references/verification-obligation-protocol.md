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
2. build後は graph全体の build unit を `derive-verification-contract.py --unit-manifest ...` で1契約へまとめる。routeごとにreview sessionを作らない。
3. `plan-verification-obligations.py` を実行する。このscriptはLLMを起動せず `reuse/generate/check/adjudicate/observe/audit/defer/blocked/remediate/escalate` を出力する。
4. `generate/check` を先に実行し、成果物・stdout・report等を `record-verification-evidence.py` でfingerprintへ束縛する。plannerを再実行して上流proof済みのclaimをready化する。
5. `llm_batches[]` ごとに1 contextだけ起動し、`obligation_ids` と `context_paths` だけを渡す。全repository、全route report、30思考法本文を無条件ロードしない。
6. `observe` は `observation_tier` の最小環境だけで実走する。PASS receiptが現在なら再実走しない。
7. `INCONCLUSIVE`、低confidence、同fingerprintの矛盾証拠は `escalate` とする。Agentを自動増殖させず、人間または明示 `exhaustive` へ渡す。

証拠receipt自体も `evidence[].sha256` で保護する。verdict/transcript/check reportが変わったreceiptは再利用しない。

receiptは実行器が取得できる場合に `usage.input_tokens` / `output_tokens` / `elapsed_ms` / `estimated_cost_usd` を記録する。同一command invocationは固定 `run_id` を全plan/receiptへ渡し、1 contextが複数receiptを生成する場合は同じ `model_action_id` を付ける。plannerはこのjoin keyで生成・semantic batch・live観測の累積actionを重複なく数える。`cost_summary` はproof reuse率、回避した実行数、今回のgeneration/check/semantic/observation件数、semantic context bytesを返す。品質指標はAgent数や思考法数でなく、`新規finding / model action`、proof reuse率、反復finding率で観測する。

`budget_gate.status=blocked` のplanからmodel workを起動してはならない。既定incrementalはsemantic batch 1個、同一runの累積model action 4個までで、1 batchがcontext byte上限を超える場合も停止する。対象sliceを狭めるか、利用者が明示的に予算を上書きして再planする。これは静かな品質低下ではなく、費用・時間・contextの拡大を承認境界へ変換するfail-closed契約である。

## 学習ラチェット

同じ `finding_code` が同一 obligation で2回以上 `FAIL/INCONCLUSIVE` になった場合、plannerは `automation_candidates[]` に `promote-to-deterministic-checker` を出す。繰り返し発見される規則はpromptへ追記せずschema/lint/testへ昇格させる。これにより運用を重ねるほど意味判定が機械判定へ移り、LLMコストが下がる。反復の検知は `scripts/detect-recurring-findings.py` が eval-log と plan-findings を横断して機械集計し (`status: unreviewed` の台帳を出力)、昇格の判断と実施は人間/AI が行う。

## 30思考法の位置づけ

30思考法は二つの実行形態に分け、proofを混ぜない。

| 形態 | 実行者 | 発火 | 効果 |
|---|---|---|---|
| 初回usable-draft診断 | `elegant-initial-draft-evaluator` 1context | usable draft完成後にartifact+contract fingerprintあたり起動認可は最大1回（別runは完了receiptを再利用） | 30レンズの簡潔な所見を先に提示し、改善深度をユーザーに聞く。release/audit proofは閉じない |
| adversarial audit | reset + 3独立analyst | 利用者が `release + exhaustive` を別途明示 | 完全監査obligationを閉じる |

初回診断は `initial-draft-review.schema.json` と `build-improvement-gate.py` で制御する。canonical method IDは `run-elegant-review/references/thought-methods.yaml` を再利用し、別の30件リストを持たない。所見提示後に `references/improvement-levels.json` の `accept-draft/light/standard/detailed/release` を質問し、回答前は `improvement.authorized=false`。`exhaustive` は既定表示せず、二重確認と `confirm_exhaustive=true` でのみ許可する。

## 安全弁との違い

`--max-live-trials`、worker上限、context byte上限は暴走時の安全弁であり、削減原理ではない。削減原理は obligation fingerprint、依存DAG、証拠再利用、machine-first、semantic slicing、学習ラチェットである。
