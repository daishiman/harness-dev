# Verification-as-program protocol

## 解決する本質的課題

旧方式は品質を `route数 × review Agent数 × 思考法数 × 反復数` のプロセス完遂で近似していた。同じ入力と同じ主張を別contextで繰り返し読み、変更していない対象にも再推論が伝播するため、品質ではなくworkflow規模がtoken・時間・計算資源・費用を決めていた。

本方式は検証単位を **verification obligation（証明すべき主張）** に変更する。通常コストの支配変数は次の2つだけである。

1. 入力または依存claimが変わり、現在の証拠が無効化された obligation
2. 決定論的validatorでは証明できず、意味判断または実環境観測が残った obligation

route、Agent、思考法の個数はコストモデルに含めない。

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

同じ `finding_code` が同一 obligation で2回以上 `FAIL/INCONCLUSIVE` になった場合、plannerは `automation_candidates[]` に `promote-to-deterministic-checker` を出す。繰り返し発見される規則はpromptへ追記せずschema/lint/testへ昇格させる。これにより運用を重ねるほど意味判定が機械判定へ移り、LLMコストが下がる。

## 30思考法の位置づけ

30思考法は設計時に obligation の漏れを発見するcatalog、および明示的な adversarial audit として保持する。全methodを毎buildで別々に文章化することは品質要件ではない。通常buildでは4条件を個別Agentへ割り当てず、deterministic proofで未解決の意味claimだけを共同裁定する。

## 安全弁との違い

`--max-live-trials`、worker上限、context byte上限は暴走時の安全弁であり、削減原理ではない。削減原理は obligation fingerprint、依存DAG、証拠再利用、machine-first、semantic slicing、学習ラチェットである。
