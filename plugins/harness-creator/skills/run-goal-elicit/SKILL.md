---
name: run-goal-elicit
description: タスクの目的・背景・ゴールが曖昧なとき、既存コンテキストからAIが仮想ヒアリング済みとして最適ゴールと完了チェックリストを推定し goal-spec.json に固めたいときに使う。
disable-model-invocation: false
user-invocable: true
argument-hint: "[topic?]"
arguments: [topic]
allowed-tools:
  - Read
  - Write
kind: run
prefix: run
effect: local-artifact
owner: team-platform
since: 2026-05-24
version: 0.1.0
source: doc/ClaudeCodeスキルの設計書/
source-tier: internal
last-audited: 2026-05-24
audit-trigger: quarterly
schema_refs:
  - schemas/goal-spec.schema.json
reference_refs:
  - ../run-build-skill/references/goal-seek-paradigm.md
completeness_exempt:
  - "prompts: ゴール抽出の単一責務 skill。出力契約は schemas/goal-spec.schema.json に集約され、責務分割が不要なため R-id 単位プロンプトを持たない。推定手順はゴールシークループで都度生成する。"
  - "manifest: ゴールシークループで手順を都度生成するため phase/gate 固定の workflow-manifest は適用外。"
feedback_contract: # per-skill 評価基準(SSOT=scripts/feedback_contract_ssot.py)
  max_iterations: 3
  criteria:
    - id: IN1
      loop_scope: inner
      text: 生成した eval-log/goal-spec.json が schemas/goal-spec.schema.json 検証を通過し purpose/background/goal/checklist が全て非空で checklist が1件以上であること(## 検証 の機械チェックで担保)。
      verify_by: lint
    - id: OUT1
      loop_scope: outer
      text: goal が観測可能な完了形の1文で checklist が二値判定可能な受入基準のみで構成され「Edit で X する」等の手順を一切混入させず 達成手順生成は run-goal-seek へ責務分離されている設計であること。
      verify_by: elegant-review
    - id: OUT2
      loop_scope: outer
      text: ユーザーに追加質問せず情報不足でも停止せず 合理的な仮定を constraints か open_questions に明示して実行可能な spec を必ず出すユーザー負担最小化の設計が ゴール抽出という目的を最適に反映していること。
      verify_by: elegant-review
---

# run-goal-elicit

## 目的と出力契約

ユーザーの曖昧な要求と既存コンテキストから **目的・背景・ゴール** をAIが推定し、ゴール達成の **完了チェックリスト** を作って `goal-spec.json` に固める。`run-goal-seek` の入力になる。

- **入力**: `topic` (任意。省略時は会話履歴・変更差分・周辺ファイルから推定)
- **出力**: `eval-log/goal-spec.json` (固定パス、プロジェクトルート基準。`schemas/goal-spec.schema.json` 準拠)
- **完了条件**: `purpose` / `background` / `goal` / `checklist` (1 項目以上) が全て確定し、schema 検証を通過する。

## 境界

手順の実行はしない（それは `run-goal-seek` の責務）。本スキルは「何を達成すれば完了か」を定義するだけ。具体的な達成手順は書かない。

**用途の使い分け（重複回避）**: 本スキルは**汎用タスク**のゴール抽出専用で、出力は `goal-spec.json`（`run-goal-seek` が消費）。**新しい Skill を作る**場合のゴール抽出は `run-goal-elicit` を呼ばず、`run-skill-elicit` の Step 4.4 が `skill-brief.json` 内に `goal`/`purpose_background`/`checklist` を直接埋める（型が異なる: 本スキルの `checklist` は `{id,criterion,done,verify_by}` 構造化オブジェクト、brief の `checklist` は文字列配列）。両者を混用・相互変換しない。

## 主要ルール

1. **ユーザーに追加質問しない**: AI が「既にヒアリング済み」と仮定し、会話履歴・リポジトリ状態・関連ファイルから最尤の目的/背景/ゴールを推定する。
2. **ゴールは観測可能な完了形で 1 文**。「頑張る」「改善する」等の判定不能な表現は不可。
3. **チェックリストは二値判定可能**な受入基準にする。手順（「Edit で X する」）をチェック項目にしない。
4. 情報が不足しても停止しない。合理的な仮定を `constraints` または `open_questions` に明示し、実行可能な `goal-spec.json` を必ず出す。
5. 決定論的に検査できる項目は `verify_by` を `script`/`lint`/`test` にして後段の `## 検証` へ寄せる。
6. 成果物の渡し先が分かっていれば `handoff_targets` に後続 Capability 名を入れる。

## ゴールシーク実行
> 固定手順は書かない。毎周「ゴール・目的/背景・チェックリスト」を読み、その時点で最適な手順を AI が生成・実行する。詳細は `../run-build-skill/references/goal-seek-paradigm.md`。

### ゴール (Goal)
`eval-log/goal-spec.json` が schema 検証を通過し、目的・背景・ゴール・完了チェックリストが全て埋まった状態。

### 目的・背景 (Why)
ゴールシーク実行 (`run-goal-seek`) は「何を満たせば完了か」が無いと回せない。固定手順ではなくゴールとチェックリストを起点にするため、まず到達点を言語化する必要がある。

### 完了チェックリスト (Checklist)
- [ ] **C1**: 目的 (purpose) を 1〜3 文で抽出した
- [ ] **C2**: 背景 (background) を 1〜3 文で抽出した
- [ ] **C3**: ゴール (goal) を観測可能な完了形 1 文で確定した
- [ ] **C4**: 完了チェックリスト (checklist) を二値判定可能な項目で 1 件以上作った
- [ ] **C5**: `eval-log/goal-spec.json` が `schemas/goal-spec.schema.json` 検証を通過した

### ゴールシークループ
正本 `../run-build-skill/references/goal-seek-paradigm.md` の 6 ステップに従う。ただし Anchor Step (Step 5: 中間成果物スナップショット) は適用除外 (出力が `goal-spec.json` 1 点の単発完結で、周回ドリフトの余地が小さいため)。本スキル固有の差分のみ記す:
- Step 1 で会話履歴・`topic`・関連ファイル・直近 diff から「仮想ヒアリング結果」を作る。
- Step 2 で複数の候補ゴールを内部比較し、最も制約充足度が高い 1 件を `goal` に採用する。
- 推定根拠が弱い項目は `constraints` に仮定として残し、未確定だが実行を止めるべきでない事項だけ `open_questions` に記録する。

## 検証

```bash
python3 - "$PWD/eval-log/goal-spec.json" "$PWD/plugins/harness-creator/skills/run-goal-elicit/schemas/goal-spec.schema.json" <<'PY'
import json, sys
spec = json.load(open(sys.argv[1], encoding="utf-8"))
schema = json.load(open(sys.argv[2], encoding="utf-8"))
req = schema["required"]  # schema 正本から required を実読 (ハードコード drift 防止)
missing = [k for k in req if not spec.get(k)]
assert not missing, f"必須欠落: {missing}"
assert len(spec["checklist"]) >= 1, "checklist は1件以上必要"
# checklist 各項目のキー照合: schema items.required + verify_by (主要ルール5: run-goal-seek 決定論検査の前提)
item_req = set(schema["properties"]["checklist"]["items"]["required"]) | {"verify_by"}
for i, item in enumerate(spec["checklist"]):
    lack = item_req - set(item)
    assert not lack, f"checklist[{i}] キー欠落: {sorted(lack)}"
print(f"goal-spec.json OK (required={req} / checklist {len(spec['checklist'])} 項目キー照合済)")
PY
```

## 注意点

- **ユーザー負担の最小化**: 追加質問を前提にしない。曖昧さは AI が最尤仮説として補い、根拠と仮定を spec に残す。
- **ゴールに手順を混ぜない**: ゴールは「状態」、チェックリストは「受入基準」。手順は `run-goal-seek` が都度生成する。
- **抽出できない時は止めない**: 合理的な仮定で spec を出し、後段の検証で仮定が破綻した場合だけ `open_issues` に差し戻す。

## 追加リソース

- `schemas/goal-spec.schema.json` — 出力契約の正本
- `../run-goal-seek/SKILL.md` — このspecを消費する実行スキル
- `../run-build-skill/references/goal-seek-paradigm.md` — ゴールシークの正本定義
