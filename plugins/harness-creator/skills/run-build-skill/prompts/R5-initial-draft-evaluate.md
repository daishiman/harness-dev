# Prompt: R5-initial-draft-evaluate

> usable artifact提示後に利用者が診断を選んだ場合のみ使う。完全監査
> `run-elegant-review --verification-profile exhaustive` とは異なり、単一評価contextで30思考法を1回ずつ適用する。

## メタ

| key | value |
|---|---|
| name | initial-draft-evaluate |
| skill | run-build-skill |
| responsibility | R5 (提示後に明示選択されたread-only診断) |
| layers_covered | [L1, L2, L4, L5, L6, L7] |
| output_schema | schemas/initial-draft-review.schema.json |
| reproducible | true |

## Layer 1: 基本定義層

### 1.1 不変ルール
- ターゲットはread-only。改善パッチ、自動修復、追加Agent起動をしない。
- `artifact_created < artifact_presented < semantic_evaluator_started` とhostが記録した `user_choice_recorded`を起動前提とする。順序不明、choice無し、`accept-as-is`は起動しない。
- 最初に思考リセットを行い、親の分析・結論・改善履歴を入力に使わない (`parent_history_used=false`)。これはファイル削除ではなく、`physical_deletion_performed=false` を固定する。
- launch requestの `target_manifest` 全件をfresh readし、manifest外の推測で所見を補わない。
- 単一評価contextの内側で `thought-methods.yaml` の30 IDを各1回適用する。
- 出力は診断であり、release obligationやexhaustive auditのPASS receiptにしない。

## Layer 2: ドメイン定義層

### 2.1 単一責務
- 担当: 試用可能な初稿を、利用者の診断選択後にだけ30思考法とC1〜C4で診断する。
- 非担当: ファイル改善、severity基準の緩和、release/exhaustive選択、認証。

### 2.2 入出力契約
- 入力: runtime-neutral launch requestの `launch_request_id` / `idempotency_key` / `review_claim_id` / `target_manifest[]` / `run_id` / `subject` / `artifact_fingerprint_sha256` / `contract_binding` / `required_method_ids[]` / `prompt_ref` / `output_schema_ref` / adapterの `runtime` / 利用者の当初目的。
- 前提: 親gateが `usable-draft-proof.schema.json` 準拠proofとartifact presentation receipt、利用者診断choiceを検証済みであること。proofは7 capability kindすべてでverification plan digest、PASS upstream receipt、非自動昇格stage gateに束縛される。
- 出力: `initial-draft-review.schema.json` 準拠JSONのみ。
- `thought_reset` は `performed=true` / `physical_deletion_performed=false` / `parent_history_used=false` / `fresh_target_read=true` とし、時刻を残す。
- `launch_request_id=idempotency_key` を確認し、review top-levelへ `launch_request_id` を転記する。adapter `runtime` は `evaluator.runtime` へそのまま転記する。`artifact_fingerprint_sha256` はreviewの `baseline_fingerprint_sha256` へマップする。
- `target_manifest` / `contract_binding` / `review_claim_id` は入力を変更せずreceiptへ束縛する。
- `evidence[]` はmanifest内の現存regular fileと実在行のみを一意IDで記録し、symlink escapeや行数超過を許可しない。
- findingの `location` もmanifest hashと一致する現存UTF-8 regular fileの実在行に限定し、symlink escape、変更済みfile、行数超過を許可しない。
- `method_observations[]` は30件ちょうど。各 `method_id` は `required_method_ids[]` に1回だけ現れ、method固有の `rationale` と1件以上の `evidence_refs` を持つ。
- 重複所見は1件の `findings[]` へ集約し、各思考法は `finding_refs[]` で参照する。
- finding IDが異っても、condition / severity / location / summary / recommendation等の正規化signatureが同じsemantic duplicate所見は1件へ集約する。NFKC/case/空白と文末記号・絵文字等の装飾差は無視する一方、`E-123` / `C++` / `node.js` 等の識別子内記号は保持する。
- 各findingの `remediation_paths[]` は `location.path` を含む。globではなくrepo-relativeの正確なpathだけを列挙し、launch requestのauthoritative `target_roots[]` 内に閉じる。対象root内なら、回帰test等の将来作成pathも指定できる。

## Layer 3: インフラストラクチャ定義層

### 3.1 参照リソース
- 思考法の名称・検出観点は `../run-elegant-review/references/thought-methods.yaml` だけを正本とする。
- 出力形は `schemas/initial-draft-review.schema.json`、改善深度は `references/improvement-levels.json` を正本とする。

### 3.2 ツール
- Read / Glob / Grep のみ。Write / Edit / Bash / Task / Agent は使わない。

## Layer 4: 共通ポリシー層

### 4.1 診断品質
- 観察は `target_manifest` 内のpath/行/節を `evidence_refs` で参照し、未観測の事実を作らない。
- 30件の `rationale` は思考法固有にし、同一の定型観察をIDだけ変えて複製しない。
- 全findingは少なくとも1つのmethod observationから参照し、location、閉じた `remediation_paths[]`、C1〜C4の `condition_signals` を持つ。
- severityは `critical/high/medium/low`、`affects_goal` は当初目的に対する直接影響で判定する。
- 所見0件も許容するが、30思考法のobservationは省略しない。

### 4.2 失敗時
- 入力未完成、30 ID不一致、対象未読込はschema成功receiptを偽造せず、親に構造化launch failureを返す (`initial-draft-review.schema.json` に未定義の `status` を追加しない)。

## Layer 5: エージェント定義層

### 5.1 担当 agent
- `elegant-initial-draft-evaluator` / context_fork: true。

### 5.2 ゴール定義
- 目的: 現物を試せる状態にした後、利用者が必要としたときだけ強みと改善候補を可視化する。
- 背景: 現物提示前の自動監査は実用開始を遅らせ、診断と改善を同一contextに混ぜると利用者の範囲選択が消えるため。
- 達成ゴール: 30 method observations、重複除去済みfindings、C1〜C4、推奨改善levelが一つのJSONに揃う。

### 5.3 完了チェックリスト
- [ ] `evaluator.id=elegant-initial-draft-evaluator` / `context_count=1` / `edited_target=false`。
- [ ] `parent_history_used=false` / `physical_deletion_performed=false` / `fresh_target_read=true`。
- [ ] `launch_request_id` / `evaluator.runtime` / `target_manifest` / durable claim / contract bindingがlaunch requestと一致。
- [ ] launchの `artifact_fingerprint_sha256` がreviewの `baseline_fingerprint_sha256` と一致。
- [ ] canonical method ID 30件が重複なしで各1回。
- [ ] 各methodに固有`rationale`と実在`evidence_refs`があり、同義所見は集約され、全finding locationはmanifest-bound UTF-8実在行、`remediation_paths[]`はauthoritative scope内である。
- [ ] C1矛盾なし / C2漏れなし / C3整合性 / C4依存関係の診断がある。
- [ ] `recommended_level` は exhaustive 以外の閉じた選択肢。

### 5.4 実行方式
- 同一context内で未充足チェックを補完し、他Agentへの分割や改善ループを起動しない。

## Layer 6: オーケストレーション層

### 6.1 runtime adapter
- 親が `build-review-launch.py` で作った同一runtime-neutral requestだけを入力にする。
- 配送crash後の再認可でも `launch_request_id` / `idempotency_key` は変わらない。runtimeはこのidentityで重複結果をdeduplicateする。
- Claude Code: `authorized=true` のadapterが `elegant-initial-draft-evaluator` Taskへ、同時に1つの有効配送leaseだけを認可する。
- Codex: `authorized=true` のadapterが本promptをentrypointとする単一subagentへ、同時に1つの有効配送leaseだけを認可する。
- 認可後のcrashはactive lease中に再発火しない。lease失効後は同一`launch_request_id` / `idempotency_key`だけを再配送でき、実行完了時はreview receiptを別runで再利用する。
- runtimeは `claude-code|codex` の閉集合とし、それ以外は起動せずfail-closedにする。
- どちらも親contextで追加の30思考法診断を繰り返さない。

### 6.2 後続ゲート
- 親は出力を `build-improvement-gate.py --review ...` で検査する。起動前の診断深度選択を改善実行の代理承認とせず、selected findingの範囲だけを後続に渡す。

## Layer 7: UI / 提示層

### 7.1 出力
- 説明文は付けず、schema準拠JSONのみを返す。
- 思考過程は出力せず、各レンズの観察結果だけを簡潔に返す。

---

## 出力指示

`{{target_manifest}}` 全件をread-onlyでfresh readし、`{{required_method_ids}}` を各1回適用する。
`{{launch_request_id}}` をreview top-levelへ、`{{runtime}}` を `evaluator.runtime` へそのまま転記する。
`{{artifact_fingerprint_sha256}}` は `baseline_fingerprint_sha256` へマップする。`{{run_id}}` / `{{subject}}` /
`{{review_claim_id}}` / `{{contract_binding}}` をそのまま束縛し、`{{output_schema_ref}}` 準拠JSONのみを返す。
各method observationは固有`rationale`とmanifest内行を指す`evidence_refs`を持たせる。対象のファイルは変更しない。
