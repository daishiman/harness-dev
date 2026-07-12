---
name: run-ubm-knowledge-sync
description: 北原さん式ナレッジソースの差分を検知したいとき、6カテゴリへ分類・格納してナレッジを同期したいときに使う。
disable-model-invocation: true
user-invocable: true
argument-hint: "[--all] [--since YYYY-MM-DD] [--dry-run]"
arguments: [all, since, dry-run]
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Glob
  - Grep
  - Task
kind: run
prefix: run
effect: external-mutation
owner: harness-maintainers
since: 2026-07-04
version: 0.1.0
manifest: workflow-manifest.json
goal_seek:
  engine: inline
  fork: subagent
  progress: eval-log/ubm-goal-setting/run-ubm-knowledge-sync/goal-seek-progress.json
  intermediate: eval-log/ubm-goal-setting/run-ubm-knowledge-sync/run-ubm-knowledge-sync-intermediate.jsonl
  handoff: eval-log/ubm-goal-setting/run-ubm-knowledge-sync/handoff-run-ubm-knowledge-sync.json
  max_loops: 5
responsibility_refs:
  - scripts/detect-knowledge-updates.py
  - ../../agents/knowledge-extractor.md
  - scripts/check-knowledge-split.py
subagent_refs:
  - knowledge-extractor
  - knowledge-relation-extractor
schema_refs:
  - ../../knowledge/schema.json
knowledge_loop:
  pattern: router-registry
  index: ../../knowledge/router.json
  consult_at: [runtime]
script_refs:
  - scripts/detect-knowledge-updates.py
  - scripts/check-knowledge-split.py
  - ../../scripts/validate-knowledge-graph.py
reference_refs:
  - references/knowledge-sources.md
  - references/knowledge-design-principles.md
source: ObsidianMemo vault (.claude/commands/ai/ubm-knowledge-sync) の移植
source-tier: internal
last-audited: 2026-07-04
audit-trigger: quarterly
completeness_exempt:
  - "prompts: 抽出・6カテゴリ分類という唯一の LLM 責務は plugin 直下 SubAgent knowledge-extractor.md (7層プロンプトを本文に内包・43KB) が単独所有し、他 Phase は決定論スクリプト (detect-knowledge-updates.py / check-knowledge-split.py) が担う。skill ローカルの R-id 単位 prompts は SubAgent 本文との二重定義になるため置かない (二重定義禁止 [[project_ssot_dedup_mechanism]])。責務→実行体の対応は本文 End-to-End Flow 表が正本。(prompts/ ディレクトリは配置しない=本 exempt の宣言と実体が一致)"
feedback_contract:
  max_iterations: 5
  criteria:
    - id: IN1
      loop_scope: inner
      text: detect-knowledge-updates.py が registry.json との MD5 照合で NEW/MODIFIED ソースを漏れなく検知することをスクリプトで確認する。
      verify_by: script
    - id: OUT1
      loop_scope: outer
      text: 既知の更新済みソースを投入し knowledge-extractor が6カテゴリへ正しく分類し router.json/registry.json が同期完了することを受入テストが確認する。
      verify_by: test
---

# run-ubm-knowledge-sync

UBM ナレッジソース（YouTube 議事録・合宿記録・月報 FB・セミナー等）の新規追加・更新差分を検知し、**内容別 JSON ファイル**（6カテゴリ）へ反映する。北原さんの最新の教えを継続的に取り込み、`run-ubm-goal-setting` の品質を底上げする。

## Purpose & Output Contract

- **ゴール**: ナレッジソースの追加・変更差分が registry.json との照合で検知され、knowledge-extractor による6カテゴリ分類と router.json 更新までナレッジ同期が完了した状態。
- **出力契約**: 検知/抽出/分割チェックの結果レポート（NEW/MODIFIED 件数・格納先・分割要否）+ `knowledge/*.json` 更新 + `router.json`/`registry.json`/`sync-log.jsonl` 追記。
- **境界**: 入力=ナレッジソース（vault 内）/ `knowledge/registry.json`。目標設定対話そのものは `run-ubm-goal-setting` へ委譲する。
- **6カテゴリ**: principles（原則）/ consultation（相談）/ phase-advice（フェーズ）/ action-guides（行動）/ mindset（転換）/ case-studies（事例）。

## End-to-End Flow

| Phase | 責務 | 実行体 |
|---|---|---|
| Phase1-detect | `detect-knowledge-updates.py` が registry.json との MD5 照合で NEW/MODIFIED ソースを漏れなく検知。出力から `05_Project/UBM/目標設定/` を含む行を除外したものが Phase2 入力 | script |
| Phase2-extract | 本 skill が NEW/MODIFIED を最大20ファイルずつのバッチへ分割し、各バッチで `knowledge-extractor` が6カテゴリへ分類して Rule A-F に従い `knowledge/*.json` + `router.json`/`registry.json` を更新 | 本 skill（batch制御）+ `knowledge-extractor`（Task） |
| Phase3-split-check | `check-knowledge-split.py` がナレッジ JSON の500行閾値超過を機械検査し、knowledge-extractor が25エントリ超過時の意味単位分割を検討する | script / `knowledge-extractor` |
| Phase4-report | 検知/抽出/分割チェックの結果（NEW/MODIFIED 件数・格納先・分割要否）をレポート | 本 skill |
| Phase5-graph-sync（Phase2 後に分岐・split-check/report と並行） | `knowledge-relation-extractor` が全 knowledge entry から根拠付き有方向辺の**候補 JSON** を read-only で返し（knowledge へ書込しない=幻覚防止）、呼び出し側が候補を eval-log へ materialize、`validate-knowledge-graph.py --merge-relations` が canonical key (source_id,target_id,relation_type) で `knowledge/knowledge-relations.json` へ冪等 merge（既存辺は保持=first-write-wins）し、検証 PASS 時のみ relations と `knowledge-graph.json` を atomic 再生成。dry-run 時は write 禁止 | `knowledge-relation-extractor`（Task）/ `validate-knowledge-graph.py --merge-relations`（script） |

Phase5 は差分 entry 起点で発火するため、**差分ゼロの周回では不発**になる。既存 corpus へ辺が一度も付いていない（`knowledge-relations.json` 不在＝edges=0 の退化グラフ）場合の初回適用は、RUNBOOK（plugin 直下 `RUNBOOK.md`）の「初回 edge backfill」手順を使う。

## ゴールシーク実行

固定手順でなく、上記ゴールと `feedback_contract` を満たすまで反復する（engine=inline / fork=subagent / max_loops=5）。

### ゴールシーク配線

- `goal_seek.progress`: `eval-log/ubm-goal-setting/run-ubm-knowledge-sync/goal-seek-progress.json` に checklist 状態、iteration、`open_issues`、`status` を記録する。 `goal_seek.intermediate`: 各周回末の Anchor Step で `run-ubm-knowledge-sync-intermediate.jsonl` に `original_goal` / `current_goal_snapshot` / `delta_from_original` / `merged_directive_for_next` / `drift_signal` を append-only で残す。 `goal_seek.handoff`: 完了時に検知件数、更新先、split-check 結果、dry-run 有無、未解決課題を `handoff-run-ubm-knowledge-sync.json` へ書く。
- ループ本体は SubAgent context で実行し、親へ返すのは同期レポート、handoff 要約、未解決 `open_issues` のみにする。
- `--dry-run` 指定時は Phase1 の検知と Phase4 のレポートだけを実行し、Phase2 extraction と Phase3 split repair の write を禁止する。
- `max_loops` 到達時は PASS 扱いせず、残チェック項目を `open_issues` に残して human review へ差し戻す。

### ゴールシーク検証

Anchor Step の検証は `required_keys = {"iteration","original_goal","current_goal_snapshot","delta_from_original","merged_directive_for_next","drift_signal"}` を満たす全 JSONL 行を対象にする。初回に `hashlib.sha256(original_goal)` を `original_goal_hash` として progress へ固定し、以後の周回で `original_goal` が変化していないことを照合する。

- **inner ループ (IN1)**: Phase1 で `detect-knowledge-updates.py --registry knowledge/registry.json --sources $UBM_VAULT_ROOT/05_Project/UBM [--all|--since]` を実行し、NEW/MODIFIED を registry との MD5 照合で漏れなく検知する。
- **outer ループ (OUT1)**: 既知の更新済みソースを投入し、knowledge-extractor が6カテゴリへ正しく分類し router.json/registry.json が同期完了することを受入テストで確認する。

## Key Rules

- **検知対象**: `$UBM_VAULT_ROOT/05_Project/UBM/` 配下の全 `.md`（YouTube/合宿/月報フィードバック/動画教材/ルート直下）。`05_Project/UBM/目標設定/`（ユーザー自身の目標記録＝北原ナレッジ非該当）は **consumer 側で除外**する。
- **抽出モード**: 引数なし=未処理のみ / `--all`=全件強制 NEW（mode:full 全再構築・knowledge-extractor Rule F）/ `--since YYYY-MM-DD`=指定日以降 / `--dry-run`=検知のみで書込なし。
- **必須フィールド**: 各エントリに `content`/`background`/`intent`/`root_cause`/`expected_outcome` 等（`schema.json` 準拠）。引用は北原さんの原文を正確に抜き出す（要約でなく引用）。分類はソース種別でなく**内容の種類**で行う。
- **命名規則（厳守）**: `{category}-{subtopic}.json`。subtopic は内容を英語で表現（relationship/organization/0to1 等）。**連番 `-1`/`-2`/`-a`/`-b` は絶対禁止**（ファイル名だけで対象読者が分かること）。
- **分割基準の二層化**: 25エントリ超過は意味単位の分割検討トリガー、500行超過は `check-knowledge-split.py` の機械的な肥大ガード。両者が衝突する場合は 25エントリ基準でサブテーマを設計し、500行ガードを必ず解消する。
- **registry の file_hash**: Bash の md5 由来 32文字ハッシュを記録。日付文字列・偽値の使用は禁止。`extracted_entry_ids` は null 禁止（次回 MODIFIED 検知時の削除に使用）。
- **MODIFIED 処理**: registry の `extracted_entry_ids` を辿って既存エントリを削除 → 全件再抽出 → registry を上書き（Case A/B は knowledge-extractor の Step U-1〜U-4 を正本とする）。
- **legacy null の移行**: シード registry の `extracted_entry_ids: null` 7件（`_note: legacy`）は、初回 MODIFIED 検知時に該当ソース由来のエントリを全削除 → 再抽出で `extracted_entry_ids` を backfill し、以後は null 禁止を適用する。
- **バッチ途中失敗の再開**: registry 更新 + sync-log 追記 + router 数値更新はバッチ（最大20ファイル）単位の1トランザクション扱い。途中失敗時は `sync-log.jsonl` の最後のエントリを完了点とみなし、そこから resume する（部分更新のまま次バッチへ進まない）。

## Gotchas

- **schema は plugin-root 共有 surface**: 本 skill の knowledge-extractor は `knowledge/schema.json` 準拠でエントリを書き、`run-ubm-goal-setting` の info-collector は `router.json` 経由でその `knowledge/*.json` を読む。consumer が schema ファイル自体を直接読む契約ではなく、共有データを schema 準拠に保つことで skill 間を整合させる。
- **初期シードの非対称**: `registry.json` は実台帳（処理済み67ファイル・移植元の dead path 6件は build 時に除去）を初期値として vendor 済み（初回 sync 全件 NEW 誤検知を回避）。`sync-log.jsonl` は空（0エントリ）で開始し append-only で追記する。
- **L2 vault 未接続時**: sources が空でも検知0件レポートを正常終了として返す（個人利用で vault 未接続でも FAIL 扱いしない）。L1 curated knowledge は vendor 同梱のため疎通不要。
- **書き込み保護**: plugin 同梱 `knowledge/*.json` への knowledge-extractor 書込は vault 外ゆえ `ubm-write-path-guard` 対象外。vault 側 asset 書込のみ guard が検査する。

## Additional Resources

- **agents**: `knowledge-extractor`（plugin 直下 `agents/`。6カテゴリ分類・Rule A-F・router/registry 更新）。
- **scripts**: `scripts/detect-knowledge-updates.py`（差分検知・決定論ゲート）/ `scripts/check-knowledge-split.py`（500行閾値検査）。
- **references**: `references/knowledge-sources.md`（取得方法・優先順位）/ `references/knowledge-design-principles.md`（記録対象・必須フィールド・命名規則）。
- **assets**: `assets/kitahara-principles-db.md`（北原さん原則 DB・新原則発見時に追記する L3 mutable asset）。
- **knowledge**: plugin 直下 `knowledge/`（`schema.json`/`router.json`/`registry.json`/`sync-log.jsonl` + 6カテゴリ `*.json`）。
