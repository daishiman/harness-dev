# system-dev-planner

system-dev-planner は dev-graph が確定した **1 feature** を P01..P13 の exact 13 executable task specs に変換する micro planner です。feature の新設・分割、program 全体の goal、tracker mutation は扱いません。

## 最初に知っておくこと

共有されるのは plugin の道具で、caller repository の文書箱や進行状態は共有されません。symlink 導入された `$CLAUDE_PLUGIN_ROOT` は scripts・schemas・references・assets を探すための場所です。仕様書、architecture、tasks、state、cache、lock、staging、published generation は、実行対象である caller repository の内側にだけ保存されます。2つの repository から同じ plugin を使っても、互いの文書や状態を読み書きしません。

初回は [setup.md](setup.md) の順に `init` し、confirmed な system spec と feature context を用意してから `plan` を実行してください。

## Input and output

`plan` は次を必須とします。

```bash
/system-dev-plan plan \
  --feature-id feature-auth \
  --feature-context features/feature-auth.json
```

feature context は caller repository 相対 JSON で、feature id、purpose、goal、scope in/out、acceptance、architecture refs を持ちます。出力は exact 13 task specs、13-entry inventory、13-node intra-feature DAG、handoff、atomic promotion receipt、dev-graph registration manifest です。

### feature context の書き方

必須は次の9フィールドです。入力側 schema は [`schemas/feature-context.schema.json`](schemas/feature-context.schema.json)、valid な実物ゴールデンは [`examples/feature-context.example.json`](examples/feature-context.example.json) にあります (使い方は [`examples/README.md`](examples/README.md))。

```json
{
  "graph_node_id": "feature-auth",
  "artifact_kind": "feature",
  "purpose": "この feature がなぜ必要か",
  "goal": "達成する状態",
  "scope_in": ["含む範囲"],
  "scope_out": ["含まない範囲"],
  "acceptance": ["受け入れ条件"],
  "architecture_refs": ["system-spec/index.md"],
  "updated_at": "2026-07-13T09:00:00Z"
}
```

`graph_node_id` は `--feature-id` と一致必須で、不一致・絶対 path・`..`・root 外 symlink・別 repository の context は C09 が拒否します。

## Automatic and manual planning

- 自動: dev-graph C14 が ready feature の id/context digest を渡して Skill を起動します。
- 手動: 人間が上記 command を実行します。
- 両経路は同じ feature identity/readiness/digest/validation/evaluation/promotion gate を通ります。

## Lifecycle

1. `init`: caller repository を確定し、`.dev-graph/config.json` と不足 directory だけを作ります。既存の文書や設定値は上書きしません。
2. `plan`: C13 が feature-bound session lock を atomic acquire し、1つの confirmed feature を exact 13 task specs、inventory、DAG として caller repository の staging に生成します。各反復で heartbeat を renew します。
3. `handoff/validate/evaluate`: C14 が versioned `system-build-handoff.json` を生成し manifest digest に含め、C08/C12 の決定論 gate と fork された独立 evaluator が、同じ canonical digest に対して4条件を判定します。
4. `promote/release`: 全 gate PASS と digest 一致のときだけ、同じ filesystem 内で staging generation を atomic rename し、C11 所有の promotion receipt・registration request・`current.json` を更新します。registration receipt は dev-graph の all-or-none apply が所有し、run 終了時は C13 がlockを release します。

通常は `/system-dev-plan plan ...` がこの lifecycle を駆動します。検証や障害復旧で各 gate を個別に確認するコマンドは [setup.md](setup.md) を参照してください。

## Resume

検証・独立評価が未達なら published/current は旧世代を維持し、同じ run の staging と findings を残します。同一 feature id/source digest で最大5周まで再開します。期限切れ lock は audit 付き cleanup 対象です。別 digest の verdict や receipt は再利用しません。

rename 後に `current.json` 更新だけが中断した場合は、同じ C11 promote command を同じ引数で再実行すると promotion intent と immutable receipt を照合して pointer 更新を冪等に完了します。gate 未達や rename 前の失敗では旧 current がそのまま残るため、published directory を手で削除・上書きしないでください。成功後に旧世代へ戻す判断は dev-graph の receipt/pointer recovery 手順で行い、本 plugin は履歴の破壊的削除をしません。

## Rollback

promotion 前の失敗は commit されないため rollback 不要で、旧 `current.json` が維持されます。promotion 成功後に戻す場合は published generation と immutable receipt を残したまま、dev-graph の receipt/pointer recovery 手順で直前の検証済み generation を選びます。具体 command と禁止事項は [setup.md](setup.md#resume-and-rollback) を参照してください。

## Macro/micro boundary

want の feature 分解と feature 間依存は dev-graph、spec 内容は system-spec-harness、本 plugin は単一 feature 内の exact-13 package のみを所有します。追加責務は14件目にせず follow-up feature candidate として dev-graph へ返します。

## フィードバック

本 plugin への改善要望は `/run-skill-feedback system-dev-planner` で投入できます (SSOT: harness-creator/skills/run-skill-feedback、symlink 配備)。
