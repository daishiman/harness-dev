# ubm-goal-setting Runbook

## Purpose

この runbook は、`ubm-goal-setting` plugin の個人利用運用で確認すべき入口、環境変数、保護境界、検証コマンドをまとめる。

## Entry Points

- `/ubm-goal-setting [weekly|monthly|bimonthly]`: 目標設定・振り返り対話を生成し、`validate-goal-output.py` で保存前検証する。
- `/ubm-knowledge-sync [--all] [--since YYYY-MM-DD] [--dry-run]`: L2 vault source の差分を検知し、knowledge JSON を同期する。
- `/ubm-youtube-ingest [--url URL | --backfill | --sync] [--source SOURCE] [--dry-run]` (v0.2.0): 北原さん YouTube を 3 モード（URL 単発 / 厳格全量 / scheduler 無人差分）で手動起動・再実行・dry-run する。手動 sync は scheduler one-shot と同一 cursor / idempotency key（`video_id`）を共有する。モード（`--url`/`--backfill`/`--sync`）は相互排他。
- `/ubm-consult "[相談内容]"` (v0.2.0): 具体解を処方せず考え方（思考フレーム）を提示するコーチング型相談。`run-ubm-consult` スキルは `disable-model-invocation: true` のため発話では自動起動せず、本コマンドが唯一の入口。目標設定そのものは `/ubm-goal-setting`（`run-ubm-goal-setting`）へ委譲する。

## Environment

- `UBM_VAULT_ROOT`: L2 raw vault source と Daily.md embed 更新先の root。未設定または未接続でも L1 curated knowledge は plugin 同梱 seed から読める。
- `CLAUDE_PLUGIN_ROOT`: hook と skill scripts の self-relative 解決に使う plugin root。

## Write Protection

`hooks/ubm-write-path-guard.py` は `UBM_VAULT_ROOT` 配下の Write/Edit/MultiEdit だけを検査する。

許可する vault write:

- `05_Project/UBM/目標設定/` 配下の目標設定ファイル保存
- `02_Configs/Templates/Daily.md` の embed 参照更新

保護対象外:

- vault 外の plugin 同梱 `knowledge/*.json`
- `UBM_VAULT_ROOT` 未設定時の任意 path
- Read など非 write tool

## Verification

```bash
python3 -m pytest plugins/ubm-goal-setting/tests -q
python3 plugins/ubm-goal-setting/skills/run-ubm-knowledge-sync/scripts/check-knowledge-split.py --dir plugins/ubm-goal-setting/knowledge
python3 -m json.tool plugins/ubm-goal-setting/.claude-plugin/plugin.json >/dev/null
python3 -m json.tool plugins/ubm-goal-setting/EVALS.json >/dev/null
```

## YouTube Sync（scheduler / 冪等 one-shot）— v0.2.0

無人の定期取込は、手動コマンド（`/ubm-youtube-ingest`）と**同一の one-shot**（`skills/run-ubm-youtube-ingest/scripts/run-youtube-sync-oneshot.py`）を host scheduler が呼ぶことで実現する（daemon 常駐でなく lease 付き one-shot の portable 設計）。手動 sync と scheduler は同じ cursor / idempotency key（`video_id`）を共有し、別系統の状態を作らない。

one-shot の実行（repo root から）:

```bash
python3 plugins/ubm-goal-setting/skills/run-ubm-youtube-ingest/scripts/run-youtube-sync-oneshot.py \
  --registry plugins/ubm-goal-setting/knowledge/youtube-registry.json \
  --channel <handle> \
  --source-out "$UBM_VAULT_ROOT/05_Project/UBM/YouTube" \
  --mode sync --max-retries 3 --lease-ttl 900
```

- **provider**: `--provider` の既定は `fixture`（受入テスト用）。具体 YouTube provider は運用時に late-bind する設計で、fixture 経路（`--provider fixture --fixture <file>`）で冪等性を検証する。
- **正規化ソースの配置**: `--source-out` は `detect-knowledge-updates.py` が `source_type=youtube` として検知できる vault 配下（`05_Project/UBM/` 配下）にする。one-shot は provenance を保った lossless 保存に徹し、意味抽出（C08→C06）は下流 R3 が担う。
- **書込境界**: one-shot の write-scope は `--registry` と `--source-out` 配下のみ。`--dry-run` は registry 初期化も含め書込 0。plugin 同梱 `knowledge/*.json` / registry は vault 外ゆえ `ubm-write-path-guard` の対象外（vault 側 asset 書込のみ hook が検査する）。

cron 設定例（毎時 05 分に差分同期・repo root へ cd）:

```cron
5 * * * * cd /path/to/harness && UBM_VAULT_ROOT="$HOME/dev/dev/ObsidianMemo" python3 plugins/ubm-goal-setting/skills/run-ubm-youtube-ingest/scripts/run-youtube-sync-oneshot.py --registry plugins/ubm-goal-setting/knowledge/youtube-registry.json --channel <handle> --source-out "$UBM_VAULT_ROOT/05_Project/UBM/YouTube" --mode sync >> "$HOME/.ubm-youtube-sync.log" 2>&1
```

### 失敗時の確認（retry / alert / lease）

one-shot は stdout に sync report（JSON・正本形式は `skills/run-ubm-youtube-ingest/references/sync-report-format.md`）を出す。scheduler ログでは以下を確認する:

- **temporary_failure**: `alerts` に `[temporary_failure] <video_id> (attempt N)`。次回 run で自動 retry され、復旧すると `ingested` に計上される（`attempts` が増える）。`--max-retries`（既定 3）超過は `[retry_exhausted]`。
- **quota / auth**: `stopped_reason` が `quota` / `auth`。graceful stop（exit 0）で scheduler は次 cadence で再開する。`alerts` に `[quota]` / `[auth]`。
- **lease**: scheduler 二重発火時、未失効 lease を持つ run が居れば `stopped_reason=lease_held` の no-op（exit 0）。`--lease-ttl`（既定 900 秒）を運用 cadence に合わせる。
- **冪等性**: 同一動画は `already_ingested` に写像され二度 ingest されない（idempotency key=`video_id`）。二回目 run は `ingested=0`。

### 完全性ゲート（--backfill）

`--backfill` の全量性は authoritative snapshot（`--video-list`）を分母に固定して機械判定する:

```bash
python3 plugins/ubm-goal-setting/skills/run-ubm-youtube-ingest/scripts/check-youtube-backfill-completeness.py \
  --channels <handle> \
  --video-list <snapshot.json> \
  --registry plugins/ubm-goal-setting/knowledge/youtube-registry.json
```

`FULL_BACKFILL_PASS` は `ingested==discovered_total` かつ `temporary_failure==0` かつ `unapproved_unavailable==0`（exit 0）。除外による分母縮小・重複 ID・pagination 欠落・waiver 参照欠落は exit 1、usage/入力不正は exit 2。

## Graph Verification（knowledge / harness artifact）— v0.2.0

knowledge 依存グラフの決定論再生成 + 検証:

```bash
python3 plugins/ubm-goal-setting/scripts/validate-knowledge-graph.py \
  --knowledge-dir plugins/ubm-goal-setting/knowledge \
  --graph-out plugins/ubm-goal-setting/knowledge/knowledge-graph.json
```

self-loop 禁止・`depends_on` の DAG 非循環・evidence≥1・confidence 0..1・review_status 必須を検査（exit 0=OK / 1=違反 / 2=usage）。PASS 時のみ `knowledge-graph.json` を書く。dangling（endpoint の entry 不在）だけは違反でなく縮退で、`knowledge-relations-quarantine.json` へ WARN 付きで自動退避し残辺で生成を継続する（Recovery 参照）。辺が 1 本も無い退化グラフ（edges=0）は exit 0 のまま stderr WARN で表面化する。

### 初回 edge backfill（既存 corpus への辺の初回適用）

C08（`knowledge-relation-extractor`）の発火点は ingest R3 / sync Phase5（いずれも差分駆動）のみのため、**既存 corpus には辺が付かず `knowledge-relations.json` 不在（edges=0 の退化グラフ）のまま**になる。初回は次の手順で backfill する:

1. `knowledge-relation-extractor` を Task 起動し、既存の全 knowledge entry から根拠付き辺候補 JSON（read-only 出力）を得る。
2. 候補を一時ファイルへ materialize する（例: `eval-log/ubm-goal-setting/relations-candidate.json`）。
3. 候補の冪等 merge（`knowledge-relations.json` へ永続化）と `knowledge-graph.json` の再生成は同一コマンドで行う:

```bash
python3 plugins/ubm-goal-setting/scripts/validate-knowledge-graph.py \
  --knowledge-dir plugins/ubm-goal-setting/knowledge \
  --merge-relations <候補ファイル> \
  --graph-out plugins/ubm-goal-setting/knowledge/knowledge-graph.json
```

4. stdout の `OK: knowledge-graph validated (... edges=N ...)` で **edges>0** を確認する（stderr に `WARN: ... edges=0` が出る間は backfill 未完了）。

merge は canonical key（source_id, target_id, relation_type）で冪等（first-write-wins）のため、同じ候補での再実行は安全に不変となる。

### 辺レビューの昇格（pending_review → approved）

C08 由来の辺は `review_status: "pending_review"` で merge される。昇格の編集先は **`knowledge/knowledge-relations.json`（辺の永続ストア＝正本）** であり、`knowledge-graph.json`（派生・再生成で上書きされる）は直接編集しない。昇格基準:

- `evidence` の逐語が出典（`source_ref` が指す entry / ソース原文）と一致していること（要約・言い換えは不可）。
- 辺の向きが正しいこと（`depends_on` は依存する側→される側、`derived_from` は派生物→原典）。

昇格後は `validate-knowledge-graph.py` で graph を再生成する。merge は first-write-wins のため、approved 済み status が後続 sync の候補で上書きされることはない。corpus 増加時は全量再抽出でなく、**新規/変更 entry を起点にした増分抽出**（該当 entry のみを extractor へ渡す）を推奨する。

harness artifact graph の index 生成と read-only consult:

```bash
python3 plugins/ubm-goal-setting/scripts/index-harness-artifact-graph.py \
  --plan-glob "plugin-plans/ubm-goal-setting/*" \
  --plugin-root plugins/ubm-goal-setting \
  --out plugins/ubm-goal-setting/knowledge/harness-artifact-graph.json

python3 plugins/ubm-goal-setting/scripts/consult-harness-artifact-graph.py \
  --topic "youtube ingest 全量性" \
  --knowledge-graph plugins/ubm-goal-setting/knowledge/knowledge-graph.json \
  --harness-artifact-graph plugins/ubm-goal-setting/knowledge/harness-artifact-graph.json \
  --query-type local --depth 2
```

consult は zero-hit も正常終了（exit 0）。`--knowledge-graph` は必須、`--harness-artifact-graph` は任意。**harness graph だけ不在なら `--harness-artifact-graph` を省いて knowledge 単独 consult に落ち**、knowledge graph も不在のときだけ `run-ubm-consult` / `info-collector` は `router.json` デュアルパスへ fallback する（fallback 契約の正本＝`references/graph-consult-fallback-contract.md`）。

### harness artifact graph の再生成（定常手順・鮮度 SLA）

`harness-artifact-graph.json`（C05）は「これから作る計画」と「実成果物」を突合した index であり、**plugin を build/レビューして実成果物（task-state / route-report / build-trace / 実在 build_target）が変わるたびに陳腐化する**。次のタイミングで `index-harness-artifact-graph.py` を再実行して再生成する:

- **build / レビュー完了後**（component の追加・state 遷移 planned→built→verified が起きたら必ず）。
- **consult 前に鮮度確認**: 生成から時間が経っている場合は再生成してから consult する。目安の鮮度 SLA は **7 日**（それより古い index は `state`/`stale_reasons` が実態とずれている可能性があるため再生成推奨）。
- 再生成しない間は harness graph を **省略して knowledge 単独 consult** しても良い（誤同定した stale index を引くより安全）。C06 `knowledge-graph.json` は knowledge 実データが変わったとき再生成する。

```bash
# build/レビュー後の再生成（再掲）
python3 plugins/ubm-goal-setting/scripts/index-harness-artifact-graph.py \
  --plan-glob "plugin-plans/ubm-goal-setting/*" \
  --plugin-root plugins/ubm-goal-setting \
  --out plugins/ubm-goal-setting/knowledge/harness-artifact-graph.json
```

## Acceptance Evidence

- C16: 週報/月報/期報を生成し、`validate-goal-output.py --type weekly|monthly|bimonthly` が PASS すること。
- C17: 既知の更新済み source で NEW/MODIFIED を検知し、knowledge-extractor が6カテゴリ分類と `router.json` / `registry.json` 同期を完了すること。
- C04: `UBM_VAULT_ROOT` 配下の許可外 path への Write/Edit/MultiEdit が exit 2 で阻止されること。

## Recovery

- `UBM_VAULT_ROOT` が未接続の場合、knowledge sync は 0件レポートとして正常終了する。vault を接続して再実行する。
- `check-knowledge-split.py` が 500行超過を検知した場合、25エントリ基準でサブテーマを設計し、`{category}-{subtopic}.json` へ分割する。
- 目標設定出力が validate に失敗した場合、未展開 `{{...}}`、全角数字、差分の `+/-`、やらないこと3項目、種別別必須見出しを優先して直す。
- (v0.2.0) `youtube-registry.json` 未存在時、one-shot は required-primary + pending 第2source で自動初期化する（`--dry-run` は初期化も書込まない）。破損 registry は上書きしない（exit 1）ため、破損時はバックアップから復旧して再実行する。
- (v0.2.0) `--backfill` の完全性ゲートが exit 1 の場合、stderr の pending / temporary_failure / unapproved_unavailable / waiver 欠落 / 重複 ID / pagination 欠落 の video ID を確認し、除外で分母を縮めず取得を再試行する。承認済み除外は `waiver_ref` を付ける。
- (v0.2.0) `validate-knowledge-graph.py` が exit 1 の場合、stderr の violation（self-loop / evidence 欠落 / confidence 範囲外 / review_status 欠落 / cycle）を確認し、C08（`knowledge-relation-extractor`）の辺 handover を修正して再生成する。`related` は無方向連想（cycle 対象外）である点に注意する。
- (v0.2.0) dangling 辺（endpoint の entry 不在）は exit 1 にならず、WARN 付きで `knowledge/knowledge-relations-quarantine.json` へ自動退避され `knowledge-relations.json` から除去された上で、残辺により graph 再生成が継続する（entry 削除で graph が恒久ブロックされない縮退）。**確認**: quarantine ファイルの `edges[]` を見る。**復旧**: 対象 entry を復活（または辺の endpoint id を実在 entry へ修正）し、該当辺を quarantine から `knowledge-relations.json` の `edges[]` へ戻して `validate-knowledge-graph.py` で再検証・再生成する。**破棄**: 辺自体が無効なら quarantine から該当辺を削除する（quarantine は graph 生成に影響しない退避先のため放置しても機能劣化はないが、棚卸しで空に保つ）。
