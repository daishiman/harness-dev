---
name: run-extract-blueprint
description: 参考システムのURL1件から、フロント表層の事実とバックエンド/設計意図の根拠つき推測を明示区別した章別ブループリントを外部公開せずローカルに生成したいとき、生成物の忠実性を独立verdictで品質評価したいときに使う。
disable-model-invocation: true
user-invocable: true
argument-hint: "<url> [--crawl-mode single|full_site] [--resume]"
arguments: [url, crawl_mode, resume]
allowed-tools:
  - Read
  - Write
  - WebFetch
  - Bash(python3 *)
  - Task
kind: run
prefix: run
effect: external-mutation
owner: harness maintainers
since: 2026-07-11
version: 0.2.0
output_language: ja
mcp_tools: []
external_systems: [対象システムの公開URL]
deterministic_checks: [authz-classify.py, fetch-snapshot.py, mermaid-validate.py, doc-emit.py]
responsibility_refs:
  - prompts/R1-fetch.md
  - prompts/R2-analyze.md
  - prompts/R3-document.md
schema_refs:
  - ../../schemas/fact-inference-confidence.schema.json
  - ../../schemas/system-blueprint.schema.json
manifest: workflow-manifest.json
goal_seek:
  engine: inline
  fork: subagent
  spec: eval-log/goal-spec.json
  progress: eval-log/run-extract-blueprint-progress.json
  max_loops: 5
feedback_contract: # per-skill 評価基準。content-review verdict の criteria_evaluated と突合
  max_iterations: 3
  criteria:
    - id: IN1
      loop_scope: inner
      text: authz/fetch/mermaid/doc の決定論チェックが exit0 になり、重要 fact 欠落 0、未観測の無断 inference 化 0、request budget 超過 0、対象 origin 並列数 1 を確認する
      verify_by: script
      derived_from: [CL-1, CL-2, CL-3, CL-6, CL-9]
    - id: OUT1
      loop_scope: outer
      text: 生成物でバックエンド機構・設計意図が根拠+確度つき推測として事実と明示区別され、AI へ渡した際に追加のヒアリングなしで自社版スカフォールドの雛形生成に着手できる粒度であることを受入テストが確認する (EVALS reconstruction-rehearsal)
      verify_by: test
      derived_from: [CL-3, CL-4, CL-5]
source: doc/ClaudeCodeスキルの設計書/
source-tier: internal
last-audited: 2026-07-11
audit-trigger: quarterly
---

# run-extract-blueprint

> extract-system-blueprint plugin の抽出本体 (L1 skill)。plugin-root 共有 script (`scripts/authz-classify.py`=C12 / `fetch-snapshot.py`=C09 / `browser-render.py`=C15 / `doc-emit.py`=C11 / `mermaid-validate.py`=C10)・analyzer sub-agent 5 体 (C03/C04/C05/C13/C06)・fail-closed hook (`hooks/pre-fetch-authz-guard.py`=C08) を配線する。パス解決は `$CLAUDE_PLUGIN_ROOT` 起点、成果物は `$CLAUDE_PROJECT_DIR`/cwd 配下。

## Purpose & Output Contract

対象システムの公開 URL 1 件から、フロント表層の**事実 (fact)** とバックエンド/UIUX/コンテンツ伝達意図の**根拠+確度つき推測 (inference)** を明示区別した章別ブループリント (md + json + Mermaid5種) を**ローカルへ生成して完結**する (外部公開はしない)。

**入力**: `url` (対象 URL 1 件), `--crawl-mode single|full_site` (既定 single), `--resume` (前 run の site coverage manifest から継続)
**出力**:
- ローカル章別 blueprint (`system-blueprint.schema.json` 準拠の md + json)・5 種 Mermaid 図・画面別 layout.json / layout-overlay.svg・合成 design-tokens.json・site coverage manifest・request ledger
- 完了レポート (日本語本文、パラメーター名・JSON キー・enum は原文)

**完了条件**: 決定論チェック (authz/fetch/mermaid/doc) 全 exit0 + fact/inference/observation_gap 相互排他 + 5 種 Mermaid 網羅。生成物はローカル draft として完結し、C02 (独立 context) がローカル品質評価の verdict (PASS/FAIL) を発行する。

**禁則**: 認証必須領域への無断到達・実侵入・認可外スクレイピングをしない。全 origin 並列 1・最小間隔・request budget・Retry-After・停止条件を緩めない (引上げはユーザー承認対象)。

## データ契約と責務分割

- **fact / inference / observation_gap 三値分離** (`$CLAUDE_PLUGIN_ROOT/schemas/fact-inference-confidence.schema.json`): fact は provenance (source_url/locator/captured_at/method/snapshot_id) 必須・レンズ解釈を含めない。inference は claim + evidence_refs(≥1) + confidence{level,rationale} 必須。observation_gap は not_observed|blocked + reason + budget_state で inference に昇格させない。top-level blueprint shape は `system-blueprint.schema.json` (screens[]/design_tokens/tech_stack/essence 等) を正本とする。
- **責務 (詳細は `prompts/R1-R3`)**:
  - **R1-fetch** (`prompts/R1-fetch.md`): C12 で AuthzEvidence/request budget/crawl_profile を確定し、C09 の URL discovery → C12 の scope 分類 (in_scope/excluded+reason) で system 関連 URL 台帳を作り、C08 の fail-closed 境界内で C09 静的 HTTP snapshot を全 in-scope 画面へ取得し、加えて C15 (`browser-render.py`・MCP 非依存 headless Chrome via Bash) で rendered DOM/screenshot の取得を試みる (ブラウザ不在=exit 3 時のみ gap)。`--resume` は前 run の site coverage manifest を C12 `--coverage-manifest-in` へ再投入する。
  - **R2-analyze** (`prompts/R2-analyze.md`): C03 (視覚/content/tech_signals/機能/CWV/security/compliance/site_inventory fact) → C04 (バックエンド/named 同定/security_design(OWASP)/delivery_topology) / C05 (UIUX/user_journeys) / C13 (content-intent) → C06 (essence + feature_map + user_journeys + security/topology 統合) の順に **Task で独立 context へ委譲**し、fact と inference を明示区別して収集する。C03 の観測は **静的 HTTP (WebFetch + C09 snapshot) と C15 browser-render (MCP 非依存 headless Chrome via Bash) の rendered DOM/screenshot** を根拠とし、JS 実行後 DOM・screenshot・computed style は browser-render で取得を試み、ブラウザ不在 (exit 3=browser-unavailable) 時のみ `observation_gap` (blocked) として記録する。
  - **R3-document** (`prompts/R3-document.md`): C11 (`doc-emit.py`) で章別ローカル draft (md/json) と 5 種 Mermaid・画面別 layout.json/overlay を確定し、`doc-emit.py --check-screens` で layout completeness を、`mermaid-validate.py` (C10) で図種網羅を自己検証する。`python3 "$CLAUDE_PLUGIN_ROOT/scripts/doc-emit.py" --extraction <json> --out-dir <dir> --request-ledger <f> [--check-screens]` で起動する。screenshot / annotated は browser-render (C15) 取得時に extraction の screens[] へ populate され、ブラウザ不在時のみ `observation_gap` として記録する。

## ゴールシーク実行

> 本 skill は固定手順ではなく、下記ゴールへ向けて完了チェックリストの未達項目を埋める手順を都度生成して反復する。正本: `../../../harness-creator/skills/run-build-skill/references/goal-seek-paradigm.md`。

### ゴール (Goal)

対象 URL 1 件について、フロント表層の事実とバックエンド/設計意図の根拠つき推測を明示区別した章別ドキュメント群 (md + json + 事実推測区別図を含む 5 種 Mermaid + 主要画面の layout.json / 注釈 overlay / verbatim content fact / essence 章) が**ローカルへ生成されて完結**し、C02 (独立 context) がローカル品質評価の verdict (PASS/FAIL) を発行できる状態。

### 目的・背景 (Why)

URL をブラウザ目視 + F12 確認する手作業 3 ステップ (週 2.5 回 × 平均 90 分) を排し、URL 解析結果から自社実装の雛形・設計ドキュメントを即生成して自社構築の着手を速くするため。事実と推測を構造分離することで、AI へ渡した際に追加ヒアリングなしで自社版スカフォールドへ着手できる粒度を担保する。

### 完了チェックリスト (Checklist)

- [ ] C12 が AuthzEvidence/request budget/crawl_profile を発行し (`allow`)、C08 の fail-closed 境界内で C09 静的 HTTP snapshot を全 in-scope 画面へ取得し、C15 browser-render で rendered DOM/screenshot の取得を試みた (MCP 非依存・対象 origin 並列 1・budget 超過 0・ブラウザ不在=exit 3 時のみ gap) <!-- CL-1 -->
- [ ] フロント表層の fact (UI 要素/観測通信/verbatim content/tech_signals/機能/CWV/security/compliance/site_inventory・および browser-render 取得時は JS 後 DOM/screenshot/computed style) が provenance 付きで採取され、browser-render がブラウザ不在 (exit 3=browser-unavailable) の場合のみ JS 後 DOM/screenshot/computed style が `observation_gap`+reason=browser-unavailable として記録され、未取得 field が無言欠落でなく `not_observed`+reason である <!-- CL-2 -->
- [ ] バックエンド機構・設計意図・named 同定・UIUX 根拠・content-intent が evidence_refs+confidence 付き inference として fact と明示区別され、essence 章 (本質的問題(JTBD)/読者/価値提案/キーメッセージ/トーン/positioning) が統合された <!-- CL-3 -->
- [ ] 各 analyzer の実プロンプトに著名エンジニア名付き原則レンズ見出し・cross-lens conflicts・neutral synthesis があり、レンズ由来主張も evidence_refs+confidence 必須で fact へ混入していない <!-- CL-4 -->
- [ ] 5 種 Mermaid 図 (全体構成/事実↔推測レイヤ/画面遷移/データフロー sequence/データモデル) が生成され `mermaid-validate.py` が exit0 <!-- CL-5 -->
- [ ] `doc-emit.py --check-screens` が exit0 (layout 参照整合・観測色の palette 孤児 0・site coverage manifest の pending 無言欠落なし・未取得 screenshot は observation_gap として記録) で、draft_hash が固定された <!-- CL-6 -->
- [ ] 対象 origin への load-policy (並列 1・最小間隔・request budget・Retry-After・停止条件) を全周で満たし、full_site でも瞬間負荷レバーを緩めていない <!-- CL-9 -->

### ゴールシークループ

正本 goal-seek-paradigm.md の 6 ステップ (現状評価/手順生成/実行/検証/Anchor Step/反復) に従う。本 skill 固有の差分:

- **現状評価**の単位は上記チェックリスト。未達項目を `## 局面カタログ (順序は都度判断)` から選んで埋める (順序固定禁止)。
- **検証**は決定論チェック (authz/fetch/mermaid/doc の exit0) を優先し、LLM 判断より機械層を先に通す。
- **差し戻し**: 決定論チェック fail または C02 FAIL なら R1-R3 の該当局面へ戻す (最大 5 周)。超過・drift 停滞は `open_issues` へ残し上位 orchestrator へ差し戻す。
- **重い周回は分離 context**: analyzer への fan-out は Task で独立 context に fork し、親へは最終成果物パスと要約のみ返す。

### ゴールシーク配線

- goal_seek.spec は plugin 単一の `eval-log/goal-spec.json` を本 skill と `run-blueprint-apply` (C14) が共有する (progress は skill 別ファイル。ゴール正本は 1 つ、周回状態は skill 別という設計意図)。
- 周回状態と中間成果物は **repo-root (非 repo 環境では plugin-root) 直下**の `eval-log/run-extract-blueprint-intermediate.jsonl` へ追記する (cwd 相対禁止)。各周回末に不変アンカー `original_goal` (上記ゴール文の原文) と `delta_from_original`、次周回の必須入力 `merged_directive_for_next` を記録し、次周回 Step2 の必須入力とする (集約化ドリフト圧縮)。周回サマリは `schemas/goal-seek-loop.schema.json` 準拠の `eval-log/run-extract-blueprint-progress.json` に残す。
- SubAgent dispatch は責務単位で固定する: fact 抽出は `frontend-surface-analyzer`、バックエンド推測は `backend-inference-analyzer`、UIUX 推測は `uiux-rationale-analyzer`、content 意図は `content-intent-analyzer`、統合は `architecture-essence-synthesizer` を Task で fork する。
- 重い候補観測・統合は該当 SubAgent へ fork し、親へは最終成果物と要約のみ返す。

### ゴールシーク検証

各周回末に中間成果物 JSONL の整合を機械検証する。`required_keys` (= `original_goal`, `merged_directive_for_next`, `delta_from_original`) が全て存在し、`original_goal_hash` が初回の `hashlib.sha256(original_goal)` と一致することを確認する (ゴール改竄検出)。不一致なら周回を停止し差し戻す。

```bash
python3 "$CLAUDE_PLUGIN_ROOT/scripts/validate-goal-seek-anchor.py" \
  --intermediate eval-log/run-extract-blueprint-intermediate.jsonl
```

検証ロジックの正本は共有 validator `../../scripts/validate-goal-seek-anchor.py` とし、各 skill は対象 JSONL のパスだけを渡す (対象 JSONL 不在は fail-closed で exit 1=配線バグ扱い。必ず追記後に起動する)。

## 局面カタログ (順序は都度判断)

下記は固定順序ではなく、ゴールシークループが未達チェックリスト項目に応じて選ぶ局面群。各局面の詳細手順・入出力契約は `prompts/R1-R3` を正本とする。

### 局面: 認可 preflight と取得 (R1-fetch)

run 開始時の bootstrap は**単一 Bash 呼び**が正本: `mkdir -p "${CLAUDE_PROJECT_DIR:-$PWD}/.esb-authz" && python3 "$CLAUDE_PLUGIN_ROOT/scripts/authz-classify.py" --url <url> --evidence-out <dir>/authz.json --budget-out <dir>/budget.json [--crawl-mode full_site --discovered-urls ... --coverage-manifest-in ...]` で状態置場作成と C12 authz 発行を同一呼び内で完結させ、allow/deny/unknown と budget/crawl_profile を確定する (unknown は deny)。C08 hook は tool call 時点で dir 不在なら非アクティブで素通すため、この呼び完了時には dir+evidence が揃い、以後の全 tool call が enforce される (evidence 不在窓なし)。**分割禁止**: `mkdir` 単独を先行させると hook が即アクティブ化し、evidence の唯一の producer である C12 呼び自身が evidence 不在=fail-closed deny (exit2) で遮断され bootstrap deadlock になる。`ESB_RUN=1` は hook が別プロセスで spawn されるため Bash セッション内 export では継承されず、セッション起動時 env としてのみ有効な補助上書き。allow のとき `python3 "$CLAUDE_PLUGIN_ROOT/scripts/fetch-snapshot.py" --url <url> --out-dir <dir> --authz-evidence <dir>/authz.json --request-budget <dir>/budget.json [--discover-urls --discovered-urls-out ...]` で snapshot + discovery。evidence/budget は C08 が参照する `ESB_AUTHZ_DIR` (既定 `.esb-authz`) へ配置する。全 fetch は C08 hook の fail-closed 境界内で走る。

### 局面: 分析への fan-out (R2-analyze)

Task で `frontend-surface-analyzer` を先行起動し fact records を得てから、`backend-inference-analyzer` / `uiux-rationale-analyzer` / `content-intent-analyzer` を C03 出力起点の直交レーンとして起動し、最後に `architecture-essence-synthesizer` へ fan-in する。各 analyzer は fact/inference を分離 JSON として成果物ディレクトリへ直接書き出す (応答長起因の無言欠落を排除)。

### 局面: 文書化と自己検証 (R3-document)

`python3 "$CLAUDE_PLUGIN_ROOT/scripts/doc-emit.py" --extraction <json> --out-dir <dir> --request-ledger <f> [--check-screens]` で章別 draft + Mermaid + layout を生成し、`doc-emit.py --check-screens` と `python3 "$CLAUDE_PLUGIN_ROOT/scripts/mermaid-validate.py" --docs-dir <dir>` で自己検証。draft_hash を固定する。

## Key Rules

1. **fact ≠ inference ≠ gap**: 観測は provenance 付き fact、推測は evidence_refs+confidence 付き inference、未観測は observation_gap。gap を無言欠落や inference へ昇格させない。
2. **proposer ≠ approver**: 自己 draft は C02 (独立 context) の**ローカル品質ゲート** verdict (PASS/FAIL) を経て品質適格を判定する。C01 は自己評価だけで適格判定しない (proposer と approver を分離する)。
3. **低負荷不変**: 対象 origin 並列 1・最小間隔・request/byte budget・Retry-After・stop 条件は single/full_site 両モードで不変。full_site は per-run 有界 + multi-run resume で全 URL へ到達する。
4. **認可外へ egress しない**: C12 が allow した AuthzEvidence 範囲外・認証必須領域へフェッチしない (C08 が fail-closed 遮断)。
5. **共有決定論ゲートの SSOT**: `mermaid-validate.py` (C10) / `doc-emit.py --check-screens` (C11) は C01 の自己検証と C02 の独立評価で同一ロジックを共有する。
6. **参考/学習目的注記**: 各正本へ参考/学習目的限定注記を焼く (C11 が担保)。

## ハンドオフ

- **次工程 (評価)**: `assign-blueprint-fidelity-evaluator` (C02) が draft_hash に束縛したローカル品質評価の verdict (PASS/FAIL) を発行する。C01 は draft と draft_hash を成果物ディレクトリへ出す。
- **下流適用**: C02 PASS (ローカル品質評価) 済 blueprint は `run-blueprint-apply` (C14) が自社適用 recommendations の入力に使う。

## Gotchas

- **`export ESB_RUN=1` は hook に届かない**: PreToolUse hook はハーネスが別プロセスで spawn するため Bash セッション内 export を継承しない。C08 run-scoping のアクティブ化は `.esb-authz` / `.esb-verdict` ディレクトリ検出が正 (R1 冒頭の combined call で作成)。`ESB_RUN=1` はセッション起動時 env としてのみ有効。
- **`mkdir -p .esb-authz` 単独先行は bootstrap deadlock**: dir 発見で hook が即アクティブ化し、evidence の唯一の producer である C12 (`authz-classify.py`) の Bash 呼び自身が evidence 不在=fail-closed deny (exit2) で遮断される。bootstrap は `mkdir -p ... && authz-classify` の**単一 Bash 呼び** (R1 冒頭) で行う (呼び時点は dir 不在=非アクティブで素通り、完了時に dir+evidence が揃う)。
- **MCP を使わない (browser 観測は progressive enhancement)**: 本 skill は外部 MCP 接続を持たず、WebFetch + C09 静的 HTTP snapshot を baseline 観測とする。JS 実行後 DOM・画面遷移・screenshot・computed style は C15 `browser-render.py` (MCP 非依存のローカル headless Chrome via Bash) で取得を試み、ブラウザ不在 (exit 3=browser-unavailable) 時のみこれらを `observation_gap` (blocked) として記録する (無言欠落禁止・inference へ昇格させない)。
- **per-run 予算は out-dir 単位**: 別 out-dir で再実行すると request budget は新規に始まる。ただし瞬間負荷レバー (並列 1・最小間隔・Retry-After・停止条件) は out-dir 非依存で常に不変。
- **verdict receipt は cwd 相対既定**: `${ESB_VERDICT_DIR:-.esb-verdict}` は cwd 起点なので、C02 の品質評価 verdict 発行と C01 の品質判定参照は同一 cwd で回す (cwd が変わると receipt 不在=fail-closed で品質判定が読めない)。

## Additional Resources

- `$CLAUDE_PLUGIN_ROOT/scripts/` — `authz-classify.py` (C12) / `fetch-snapshot.py` (C09) / `doc-emit.py` (C11) / `mermaid-validate.py` (C10)
- `$CLAUDE_PLUGIN_ROOT/agents/` — `frontend-surface-analyzer` (C03) / `backend-inference-analyzer` (C04) / `uiux-rationale-analyzer` (C05) / `content-intent-analyzer` (C13) / `architecture-essence-synthesizer` (C06)
- `$CLAUDE_PLUGIN_ROOT/hooks/pre-fetch-authz-guard.py` (C08) — fetch-authz 単一述語の fail-closed hook (matcher=`Bash|WebFetch`)
- `$CLAUDE_PLUGIN_ROOT/schemas/` — `fact-inference-confidence.schema.json` / `system-blueprint.schema.json` (横断データ契約)
- `prompts/R1-fetch.md`〜`R3-document.md` — 責務プロンプト (7 層)
