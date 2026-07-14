# system-dev-planner setup

## 仕組みを一言で

共有されるのは plugin の道具で、caller repository の文書や状態は共有しません。`$CLAUDE_PLUGIN_ROOT` には実行 script、schema、reference、asset があり、実際の system spec、architecture、tasks、state、cache、lock、staging、published generation は caller repository 内に置きます。つまり、同じ工具箱を複数の現場で使っても、各現場の書類箱は混ざりません。

## 前提

- caller repository が Git repository であること。
- `system-spec-harness` と `dev-graph` が利用可能であること。
- system spec の index、requirements、architecture graph が caller repository 内で confirmed になっていること。
- feature context が [`schemas/feature-context.schema.json`](schemas/feature-context.schema.json) に従う repository 相対 JSON であること。

`$CLAUDE_PLUGIN_ROOT` は plugin manager が設定する物理配置です。文書や `.dev-graph` の保存先として使わないでください。caller repository は `--repo-root`、信頼された project environment、Git root、cwd marker の順で解決され、realpath containment と repository id 再導出が一致しない場合は fail-closed で停止します。

## 1. Init

caller repository の root で実行します。

```bash
/system-dev-plan init --repo-root "$PWD"
```

同等の診断用 command は次です。

```bash
python3 "$CLAUDE_PLUGIN_ROOT/scripts/init-project-layout.py" --repo-root "$PWD"
python3 "$CLAUDE_PLUGIN_ROOT/scripts/resolve-project-context.py" --repo-root "$PWD" --json
```

`init` は `.dev-graph/config.json` と不足 directory/key だけを作成します。既存の config 値、docs、specs、architecture、tasks、issues は上書きしません。receipt の `repository_id` と `root_source` を確認してください。

## 2. Plan

caller repository 相対の feature context を用意します。例は [`examples/feature-context.example.json`](examples/feature-context.example.json) にあります。

```bash
/system-dev-plan plan \
  --feature-id feature-auth \
  --feature-context features/feature-auth.json \
  --repo-root "$PWD"
```

planner は1 feature だけを扱い、P01..P13 に1件ずつ対応する exact 13 task specs、13-entry inventory、13-node DAG、handoff を caller repository の staging に生成します。feature id と context 内の `graph_node_id` が違う場合や、absolute path、`..`、repository 外 symlink は拒否されます。

`plan` は内部で C13 lock manager を呼び、run/session/feature digest を束縛して acquire→反復ごとの renew→終了時 release を行います。診断時は同じ identity を各操作に渡してください。lock JSON を手で作成・編集・削除してはいけません。

```bash
python3 "$CLAUDE_PLUGIN_ROOT/scripts/manage-system-plan-lock.py" \
  --lock-action acquire --repo-root "$PWD" --run-id <run-id> \
  --session-owner <session-owner> --feature-id <feature-id> \
  --feature-digest sha256:<64hex>
```

## 3. Validate and evaluate

通常は `plan` がこの段階を駆動します。調査時は各決定論 gate を個別実行できます。以下の相対 path は実際の run に合わせて置き換えてください。

```bash
python3 "$CLAUDE_PLUGIN_ROOT/scripts/check-implementation-readiness.py" \
  --repo-root "$PWD"

python3 "$CLAUDE_PLUGIN_ROOT/scripts/build-system-handoff.py" \
  --repo-root "$PWD" \
  --staging .dev-graph/staging/<run-id>

python3 "$CLAUDE_PLUGIN_ROOT/scripts/validate-system-plan.py" \
  --repo-root "$PWD" \
  --staging .dev-graph/staging/<run-id>
```

C08 readiness の後、C14 が exact-13 source SHAとregistration ownershipを持つ versioned handoff を生成し、handoff bytes を含む最終 manifestをcommit pointとして書きます。その後 C12 validation と `assign-system-dev-plan-evaluator` を実行します。validator の `validated_digest`、evaluator の `evaluated_digest`、staging canonical digest は完全一致が必要です。FAIL の場合、評価対象を evaluator が直すことはなく、findings を planner へ返します。

## 4. Promote

通常は `plan` が全 gate PASS 後に C11 を呼びます。復旧・診断で個別実行する場合は、readiness、validation、independent findings の repo 相対 path を明示します。

```bash
python3 "$CLAUDE_PLUGIN_ROOT/scripts/promote-system-plan.py" \
  --repo-root "$PWD" \
  --feature-id <feature-id> \
  --feature-context features/<feature-id>.json \
  --run-id <run-id> \
  --session-owner <session-owner> \
  --staging .dev-graph/staging/<run-id> \
  --readiness .dev-graph/state/<readiness-report>.json \
  --validation .dev-graph/state/<validation-report>.json \
  --findings .dev-graph/state/<plan-findings>.json
```

C11 は全条件 PASS、same digest、C14 handoff の owner 宣言に加え、C13 active lock の repository/run/session/feature/digest/TTL を書込み前に再検証し、同じ filesystem 内でのみ atomic rename します。lock 不在・owner 不一致・期限切れでは promotion/recovery とも exit 2 で停止します。成功すると published generation に C11 所有の immutable promotion receipt と dev-graph registration request を置き、repo-local `current.json` を atomic replace します。all-or-none registration receipt のdev-graph C02が所有し、C14/C11はそれを自己発行しません。通常の `plan` 実行では C01 が finally 相当の終了処理を所有し、成否にかかわらず C13 `release` を呼びます。個別診断で C11 を直接呼び出した場合は、呼出元が同じ owner 引数で `release` を必ず実行します。

## Resume and rollback

- gate 未達、digest mismatch、rename 前の失敗: staging と findings を残し、同じ feature id/source digest で最大5周まで再実行します。published/current は旧世代のままです。
- rename 後、pointer 更新前の中断: 同じ promote command と同じ引数を再実行します。C11 が promotion intent、published receipt、digest を照合し、`current.json` 更新を冪等に完了します。
- 成功後の業務 rollback: published generation や receipt を削除・書換えず、dev-graph の receipt/pointer recovery 手順で直前の検証済み generation を選びます。system-dev-planner 自身は履歴を破壊しません。
- digest が変わった場合: 古い evaluator findings、validation report、receipt は再利用せず、新しい run として検証し直します。

### Lock 復旧 runbook (C13 stale / malformed lock)

canonical lock は `<repo-root>/.dev-graph/locks/system-dev-plan-lock.json` の1本のみ。lock JSON を手で作成・編集しないこと。復旧はケースで分岐する:

- **期限切れ lock (`expires_at` < 現在時刻)**: 手動操作は不要。次の `plan` の C13 `acquire` と guard hook が audit receipt 付きで自動 cleanup する。そのまま同じ feature id/digest で再実行する。TTL 既定は 900s、`--ttl-seconds` 上限 24h。異常終了に備え長時間 run では小さめ TTL + heartbeat renew を使い、大 TTL 放置による最大 TTL 分の誤 block を避ける。
- **破損 lock (field-set 不一致で `expires_at` を読めない)**: fail-closed で全 Bash/Task を block するが、`expired` と分類できず自己修復経路が無い。**アクティブな run が無いことを確認したうえで**、破損した `system-dev-plan-lock.json` を手で削除する (これが唯一の許容される手動介入)。削除後に `plan` を再実行すれば C13 が正常 lock を再取得する。編集ではなく削除である点、他 run 実行中に消さない点を厳守する。

## 確認ポイント

- 保存 path はすべて caller repository 相対である。
- `$CLAUDE_PLUGIN_ROOT` が現れるのは plugin の code/assets 参照だけである。
- readiness、validation、evaluation、published の digest が一致している。
- task は P01..P13 の exact set で、feature 外 dependency がない。
- receipt が生成されるまで dev-graph へ handoff しない。
- `staging-manifest.json` が `system-build-handoff.json` の SHA-256 を含み、handoff自身は自分の digest/最終 manifest digest を埋め込まない。
- lock の acquire/renew/release は同一 repository/run/session/feature digest で C13 経由に限定される。
