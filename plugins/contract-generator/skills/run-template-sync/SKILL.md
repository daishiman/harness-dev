---
name: run-template-sync
description: 契約書ひな形の変更・更新を同期管理するとき、影響行を作り直し対象にしたいときに使う。
disable-model-invocation: false
user-invocable: true
allowed-tools: [Read, Edit, Bash(python3 *)]
kind: run
version: 0.3.0
owner: harness maintainers
since: 2026-05-30
role_suffix: generator
hierarchy_level: L1
rubric_refs:
  - "../../../harness-creator/skills/run-elegant-review/references/thought-methods.yaml"
  - "../../lib/scan_template.py"
  - "../../lib/ledger.py"
responsibility_refs: [prompts/R1-diagnose-and-resync.md, ../../agents/template-sync-agent.md, scripts/sync.py]
prompt_ssot: prompts/R1-diagnose-and-resync.md
effect: external-mutation
source: output/contract-generator-v2/(refactor-plan.md) + run-contract-generate/references/template-change-runbook.md
source-tier: internal
last-audited: 2026-05-30
audit-trigger: on-change
feedback_contract: # per-skill 評価基準(SSOT=scripts/feedback_contract_ssot.py)
  max_iterations: 3
  criteria:
    - id: IN1
      loop_scope: inner
      text: scan_template が整合時 exit 0 / drift 検知時 exit 5 を返し、MISSING(差込位置消失)/UNMAPPED(新規プレースホルダ)を機械判定できること。
      verify_by: lint
    - id: IN2
      loop_scope: inner
      text: "--apply 時のみ対象 completed 行へ再生成フラグを立て 未作成 へ差し戻し、--dry-run/未指定では台帳書込を行わない(診断のみ)こと。"
      verify_by: test
    - id: OUT1
      loop_scope: outer
      text: 「ひな形が変わった」等の明示意図でのみ発火し、作成意図(「契約書を作って」)では発火しない誤発火防止設計が description に純化されていること。
      verify_by: elegant-review
---

# run-template-sync

## Purpose & Output Contract
ユーザーが「ひな形が変わった/テンプレートが更新された」と**明示した時のみ**発火する独立スキル。自社のひな形フォルダに置き換えられた `.docx` を `scan_template` で診断し、黄色run/プレースホルダの差分(MISSING=差込位置消失/UNMAPPED=新規プレースホルダ)を検知。`--apply` で `template-mapping.json`・台帳列の更新を促し、`completed` 行に**再生成フラグ**を立てて `未作成` へ差し戻す→次回 `run-contract-generate(--phase draft)` で作り直される。実体は `scripts/sync.py`(共有 `../../lib/scan_template.py` を使用)。

## 境界
ひな形差分検知と再生成フラグ付与(completed→未作成)まで。下書き生成は `run-contract-generate`、PDF確定は `run-contract-finalize`。**作成意図(「契約書を作って」)では発火しない**(誤発火防止のため独立スキル化)。

## 主要ルール
- **明示発火のみ**: 「ひな形が変わった」等の意図でのみ起動。作成フローに scan を混ぜない(常時発火でDrive API浪費・誤って再生成フラグ誤爆を防ぐ)。
- 条文は改変しない。差込アンカー(`template-mapping.json`)のみ更新対象。
- ひな形は名前パターンで最新版を取得(差し替えに追従)。
- `--apply` 前は診断のみ(dry的)。再生成フラグ付与は明示 `--apply` で。

## ゴールシーク実行
> 固定手順は書かない。毎周「ゴール・目的/背景・チェックリスト」を読み最適手順を都度生成。詳細は run-build-skill `references/goal-seek-paradigm.md`。

### ゴール (Goal)
変更されたひな形と `template-mapping.json` の差分が解消(整合)し、影響する `completed` 行が再生成対象(`未作成`+再生成フラグ)に差し戻され、作り直しの準備が整っている状態。

### 目的・背景 (Why)
ひな形は法務課により随時更新される。変更を「黙って壊れる」のでなく「検知して知らせ、作り直す」運用にする。作成意図と異質な発動条件のため独立スキルに分離し、自然言語「ひな形が変わった」で発火させ誤爆を防ぐ。

### 完了チェックリスト (Checklist)
- [ ] `scan_template`(個人/法人)で差分(MISSING/UNMAPPED)を診断できる
- [ ] MISSINGアンカー/UNMAPPEDプレースホルダを `template-mapping.json` に反映できる
- [ ] 新規プレースホルダに対応する台帳列を追加できる(`ledger.HEADERS`/`ensure_schema`)
- [ ] `--apply` で `completed` 行に再生成フラグを立て `未作成` へ差し戻せる
- [ ] 差し戻し後 `scan_template` が exit 0(整合)になる
- [ ] 作成意図の入力では本スキルが発火しない(description純化を確認)

### ゴールシークループ
1. 未達 `[ ]` を特定 → 2. 手順を都度生成 → 3. 実行 → 4. 再評価し `[x]` 更新 → 全 `[x]` まで反復。規定周回で未達なら open_issues へ。

### ゴールシーク配線
ひな形差分解消を多周回す場合の周回状態とドリフト圧縮の配線。周回末に `eval-log/run-template-sync-intermediate.jsonl` へ `{iteration, original_goal, current_goal_snapshot, delta_from_original, merged_directive_for_next, drift_signal}` を1行追記する。`original_goal` は全周回で不変(SHA-256 を `eval-log/run-template-sync-progress.json` の `original_goal_hash` に固定し毎周回照合)。次周回は直前の `merged_directive_for_next` と `original_goal` を必須入力として読む(AI単独再導出禁止)。重い周回は `Skill(run-goal-seek)` に fork 委譲。

```bash
python3 "$CLAUDE_PLUGIN_ROOT/lib/check_intermediate.py" run-template-sync
# → eval-log/run-template-sync-intermediate.jsonl の original_goal_hash 不変・required_keys 充足を検査
# 不整合は exit 2 で次周回を停止
```

## ゴールシーク品質ループ (正負フィードバック)

各周回末に `lib/feedback_loop.py` の `record_positive()` / `record_negative()` を呼び、シグナルを `eval-log/run-template-sync-feedback.jsonl` に追記。次周回開始時に `derive_next_directive("run-template-sync", round)` を参照し、戻り値を `merged_directive_for_next` の先頭に prepend する。

正負シグナル定義表は `prompts/R1-diagnose-and-resync.md` の Layer 4.4 を正本(SSOT)とする(本 SKILL.md には再掲しない)。反映タイミング: 周回末 `record_*` → 次周回開始時 `derive_next_directive` → merged_directive に prepend。

## 検証
- `scan_template --type {individual,corporate}` が exit 0(整合)/5(drift)
- `--apply` 後、対象 `completed` 行が `未作成`+再生成フラグ◯ になっている
- `--dry-run` で台帳書込を抑止可能
- 実装: `scripts/sync.py`(集約診断 + `--apply` 時の台帳差し戻し entrypoint) / `$CLAUDE_PLUGIN_ROOT/lib/scan_template.py`(個別ひな形の drift 判定)

## Gotchas
- `read_file_content`(MCP)ではハイライト属性が取れない。黄色run確認は `scan_template`(標準ライブラリ `docx_lib`)で行う。
- ひな形の構造を大改訂した場合は `template-mapping.json` の `anchor`/`conditionals` の手修正が必要(`run-contract-generate/references/template-change-runbook.md`)。

## 変数化契約
ひな形フォルダID/`spreadsheet_id` は `google-config.json` から注入。差込アンカーは `run-contract-generate/references/template-mapping.json` を正本参照。

## 追加リソース
- `run-contract-generate/references/template-change-runbook.md` — ひな形変更時の手順
- `run-contract-generate/references/template-mapping.json` — 差込アンカー正本
- `prompts/R1-diagnose-and-resync.md` — ひな形差分診断・マッピング/台帳追従・再生成フラグ付与の責務単位7層プロンプト(SSOT正本)。`../../agents/template-sync-agent.md` は本プロンプトを参照する薄い実行アダプタ(本文を持たない)。
- 追加リソースは plugin 直下 `lib/` ディレクトリ全体を参照。各ファイルは PEP723 風メタブロックで purpose を記載。
- 本 skill が強く依存する lib: `scan_template.py`(差分診断) / `ledger.py`(再生成フラグ付与・台帳列追加) / `docx_lib.py`(黄色 run 抽出)
- `scripts/sync.py` — エントリ(`lib/scan_template.py` を集約診断し、`--apply` 時は `ledger` へ completed 行の再生成フラグ書込。scan_template の等価 shim ではなく drift 時も exit 0)

## 使い方
```bash
python3 scripts/sync.py --type all              # 診断のみ(差分検知)
python3 scripts/sync.py --type all --apply      # 差分解消後: 再生成フラグを立て未作成へ差し戻し
```
または自然言語で「契約書のひな形が変わりました」と伝える。

## セキュリティと権限
台帳への書込(`effect=external-mutation`)。SA鍵はKeychainのみ(`hooks/hook-guard-secret.py` が保護)。条文・法務承認済書式は改変しない。
