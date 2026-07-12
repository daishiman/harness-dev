# 27. rubric ガバナンス Runbook

## 目的・出力・禁則・関連章（compaction対策）

### 目的

rubric 改正手続きを「**自動検出 → 招集 → 評価 → 猶予 → 発効**」の 5 ステップ Runbook に落とし、23 章 governance 節を矛盾なく詳細化する。Goodhart（評価基準を都合よく歪める罠） 対策と知見蓄積を両立し、人/script/Hook/CI の責務境界を明示する。

### 出力

- `eval-log/violation-rate.csv` を観測する自動検出 script
- 改正提案 YAML テンプレ
- 影響評価 script（新 rubric で全 Skill 再採点）
- deprecation warning パターン
- `rubric-versions.md` 発効記録

### 禁則

- rubric を evaluator/generator が編集（09 章 Goodhart（評価基準を都合よく歪める罠） 対策）
- 提案者と承認者の兼任（自己承認）
- `newly_failing>0` で猶予ゼロ発効
- script に標準ライブラリ外を import（22 章準拠）
- templates と rubric の個別凍結（23 章 同時凍結ルール）

### 関連章

| 章 | 役割 | 本章での参照位置 |
|---|---|---|
| 06 第15条 | 命名規約改正手続き | §1, §3.3 |
| 09 | eval-log JSON schema / evaluator 契約 | §3.1, §6 |
| 22 | Python 3 stdlib 限定 | §3, §6, §8 |
| 23 governance 節 / 凍結ルール | 上位設計 | §1, §2, §8, §10 |
| 25 | 通常 Runbook との接合 | §9 |
| 26 | 設計書自体を採点対象に含む | §3.1, §12 |

---
## 1. 目的と位置付け（23章/06章との関係）

23 章は rubric governance の抽象設計（トリガー一覧・3段階・3役）。06 章 第15条は命名規約の改正手続き。本章はこれらを「実行可能 Runbook」に変換する。

| 章 | レイヤ | 粒度 |
|---|---|---|
| 23 governance 節 | 設計原則 | 「違反率連続 3 release で 20% 超なら改正」 |
| 06 第15条 | 命名規約専用手続き | 提案/影響評価/猶予 |
| **27（本章）** | 実装 Runbook | script・JSON設定・Hook・CI の具体形、責務分担表 |

23 章既定値（`連続3×20%`、凍結 `N=10, M%=5%`）を継承し、調整可能パラメータとして `references/governance-params.json` に外出しする。06 章との接続は §3.3。

---
## 2. governance 自動化アーキテクチャ

```text
  eval-log/*-score.jsonl (09)  ──┐
  eval-log/violation-rate.csv ──┤ release tag (CI)
                                 ▼
        scripts/lint-rubric-violation.py  (§3.1, 決定論)
              │ trigger.json / exit 2
              ▼
        Hook: Stop  (§3.4)  ── governance ボード招集通知
              │ (人手: 提案者起票)
              ▼
        PR: 改正提案 YAML  (§5)
              │ (CI 自動)
              ▼
        scripts/diff-rubric-impact.py  (§6)  → impact-report.json
              │
              ▼
        第三者レビュアー → 承認者  (§4, §7)
              │ approve
              ▼
        猶予期間: 旧/新 rubric_version 併走採点 + deprecation warning  (§7)
              │ 期間満了
              ▼
        発効: version bump + hash 記録 + rubric-versions.md / CHANGELOG  (§8)
```

縦軸が時間。人手 / 自動の境界は §9 で表化する。

---
## 3. 改正トリガー自動検出

### 3.1 eval-log の JSON schema

09 章の evaluator 出力を **集計可能形** に固定する。`eval-log/<plugin>/<YYYY-MM-DD>-score.jsonl`（1 行 1 record）。plugin 移行前は従来パス `eval-log/<YYYY-MM-DD>-score.jsonl` を使用する。plugin 対応パスは 34 章 Phase 0 完了後に移行する。:

```json
{ "timestamp": "2026-05-17T09:00:00Z", "release": "2026.05.0",
  "plugin": "core",
  "skill_name": "run-build-skill", "evaluator": "assign-skill-design-evaluator",
  "rubric": {"rubric_id": "skill-design", "rubric_version": "1.2.0", "rubric_hash": "sha256:..."},
  "score": 82, "passed": true, "threshold": 80,
  "findings": [ {"rubric_item_id": "fm-description-length", "severity": "medium",
                 "passed": false, "message": "description が 200 文字を超過"} ] }

注: `plugin` フィールドは plugin 移行後に使用する（34章 Phase 0 完了後）。移行前は `"plugin": "core"` で統一し、移行後は `plugins/<name>/` の kebab-case 名を入れる。パスは `eval-log/<plugin>/<date>-score.jsonl` に対応する。
```

#### PKG gate 用 eval-log パス（36章連動、2026-05-20 追加）

36章 PKG-001〜017 の gate script 実行結果（install smoke / package validate / contract lint 等）は `eval-log/<plugin>/pkg-<id>/<YYYY-MM-DD>-<run>.{json,log}` に保存する。同パスは 35章 `pkg_check_failed` failure_mode の `observable_signal` 入力源として参照され、34章 Phase 0/1/2 ゲートチェックの evidence になる。append-only（§10 アンチパターン #6 を準用）。

集計鍵は `rubric_item_id` と `release`。`findings[].passed: false` を母数で割れば項目別違反率になる。

### 3.2 違反率集計 script

`scripts/lint-rubric-violation.py`（Python 3 標準ライブラリのみ。22 章準拠）:

```python
#!/usr/bin/env python3
# eval-log/*.jsonl を読み、連続 N release × 違反率 M% 超を検出。
# 依存: json, pathlib, collections, argparse, sys のみ（22 章準拠）
import argparse, json, sys
from collections import defaultdict
from pathlib import Path

def load(log_dir):
    for p in sorted(Path(log_dir).glob("*-score.jsonl")):
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.strip(): yield json.loads(line)

def compute(records):
    bucket = defaultdict(lambda: [0, 0])  # (release, item) -> [total, viol]
    for r in records:
        for f in r.get("findings", []):
            k = (r["release"], f["rubric_item_id"])
            bucket[k][0] += 1
            if not f.get("passed", True): bucket[k][1] += 1
    by_item = defaultdict(list)
    for (rel, item), (t, v) in bucket.items():
        by_item[item].append((rel, v / t if t else 0.0))
    for item in by_item: by_item[item].sort()
    return by_item

def detect(by_item, n, th):
    return [{"rubric_item_id": item,
             "recent_releases": [r for r, _ in s[-n:]],
             "recent_rates":    [v for _, v in s[-n:]]}
            for item, s in by_item.items()
            if len(s) >= n and all(rate > th for _, rate in s[-n:])]

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--log-dir", required=True)
    p.add_argument("--n", type=int, default=3)
    p.add_argument("--threshold", type=float, default=0.20)
    p.add_argument("--out", required=True)
    a = p.parse_args()
    breached = detect(compute(list(load(a.log_dir))), a.n, a.threshold)
    Path(a.out).write_text(json.dumps(
        {"breached": breached, "n": a.n, "threshold": a.threshold},
        ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if not breached else 2  # exit 2 = 招集

if __name__ == "__main__":
    sys.exit(main())
```

判定は決定論。LLM は使わない。CI は exit code で招集 Hook を発火する。

### 3.3 しきい値判定と 06 章第15条との関係

| パラメータ | 既定 | 出典 | 調整 |
|---|---|---|---|
| `N`（連続 release） | 3 | 23 章 | `governance-params.json` |
| `M%`（違反率） | 20% | 23 章 | 同上 |
| 凍結 `N` | 10 | 23 章 安定版凍結 | 同上 |
| 凍結 `M%` | 5% | 同上 | 同上 |

06 章 第15条は命名規約改正だが、命名規約条文も `naming-*` prefix の rubric 項目として eval-log に記録するため、本章の検出ロジックがそのまま適用できる。第15条が要求する「影響を受ける Skill リスト」は §6 の `diff-rubric-impact.py` が自動生成する。

### 3.4 検出時の通知（Hook で発火）

CI から `lint-rubric-violation.py` の exit 2 を受け、`Stop` Hook で招集メッセージを表示。`.claude/settings.json`（抜粋）:

```json
{ "hooks": { "Stop": [ { "matcher": ".*", "hooks": [
  { "type": "command",
    "command": "python3 .claude/scripts/notify-if-governance-trigger.py --trigger xl-skills/eval-log/trigger.json" }
] } ] } }
```

`notify-if-governance-trigger.py` は `trigger.json.breached` が空でなければ stdout に招集文を書く。空なら no-op。

---
## 4. governance ボード構成（既存3役 + tooling役）

23 章の 3 役を継承し、自動化を担う **tooling 役** を追加する。

| 役 | 責務 | 委譲先 |
|---|---|---|
| **提案者** | 改正動機・rubric diff・期待効果を作成 | 人 |
| **第三者レビュアー** | Goodhart（評価基準を都合よく歪める罠） リスク評価、影響評価妥当性 | 人（提案者と非兼任） |
| **承認者** | merge 権限、猶予期間長確定 | 人（提案者と非兼任） |
| **tooling 役（新規）** | script/Hook/CI 維持、`impact-report.json` の品質保証 | 人または `assign-governance-tooling-contributor` |

tooling 役は人手判断をしない。「人手判断に必要な数値が揃っているか」だけを保証する。提案者と承認者の兼任は禁止（23 章踏襲）。tooling 役は他役と兼任可。

### 4.1 PKG ID 改廃の governance（36章連動、2026-05-20 追加）

36章 Plugin Package Harness Contract の **PKG ID（PKG-001〜017、PKG-013 の 013a/013b/013c/013d への分割等を含む）の新設・分割・削除・意味変更** は、本章 rubric governance のレビュー対象に含める。理由は、PKG gate は rubric 違反率と同じく eval-log 集計に直結し（§3.1 PKG gate 用 eval-log パス）、ID 使い回しが時系列比較性を破壊するため（§10 アンチパターン #7 と同型）。

| 操作 | 承認要件 |
|---|---|
| PKG ID 新設 | 36章正本への追加 PR + 本章 §5 改正提案 YAML（`trigger.type: "manual"` で起票、提案者≠承認者） |
| PKG ID 分割（例: 013 → 013a〜d） | 上記に加え、旧 ID を deprecated として 1 release 以上猶予（§7） |
| PKG ID 削除 | 上記に加え、`diff-rubric-impact.py` 相当の影響評価（既存 plugin の PKG fail 履歴に対する影響）を添付 |
| PKG ID 意味変更 | 36章 + 本章で **major bump 扱い**。新 ID（例: `PKG-001-v2`）を発行し旧 ID を deprecated（§10 #7 準用） |

PKG ID の改廃を 36章単独で行うことは禁止。本章承認を経ない PKG ID 変更は CI block 対象とする。

---
## 5. 改正提案テンプレ（YAML）

PR 起票時 `docs/rubric-proposals/<YYYY-MM-DD>-<slug>.yaml`:

```yaml
# rubric-proposal schema v1
proposal_id: "2026-05-17-tighten-fm-description"
proposer: "@daishiman"
created_at: "2026-05-17"
motivation: |
  fm-description-length の違反率が直近 3 release で 22%/24%/28%。
  templates/ 修正だけでは収まらず rubric 文言の明確化が必要。
trigger:
  type: "violation_rate"   # violation_rate | new_official_spec | naming_amendment | manual
  detected_by: "scripts/lint-rubric-violation.py"
  trigger_artifact: "xl-skills/eval-log/trigger.json"
rubric_diff:
  rubric_id: "skill-design"
  from_version: "1.2.0"
  to_version:   "1.3.0"
  changes:
    - rubric_item_id: "fm-description-length"
      kind: "tighten"      # tighten | loosen | add | remove | clarify
      before: "description は適切な長さ"
      after:  "description は 200 文字以内、かつ trigger 条件を含む"
expected_effect:
  - "違反率が次 release で 10% 以下に低下する見込み"
  - "templates/ の description 欄を同時更新"
impact_assessment_required: true  # §6 で自動生成
grace_period: {policy: "auto", min_releases: 1, min_days: 30}
approvers: {reviewer: "@TBD", approver: "@TBD"}
```

`trigger.type == "naming_amendment"` の場合は 06 章 第15条を優先し、本テンプレの `rubric_diff` は naming 連動項目の追従に限定する。

---
## 6. 影響評価（破壊度測定 script）

`scripts/diff-rubric-impact.py`（Python 3 標準ライブラリのみ）:

```python
#!/usr/bin/env python3
# 新/現 rubric それぞれの採点 jsonl 差分を計算（採点本体は別 process）。
import argparse, json, sys
from pathlib import Path
from statistics import mean

def load(p):
    return [json.loads(l) for l in Path(p).read_text(encoding="utf-8").splitlines() if l.strip()]

def main():
    a = argparse.ArgumentParser()
    a.add_argument("--baseline", required=True)
    a.add_argument("--candidate", required=True)
    a.add_argument("--out", required=True)
    args = a.parse_args()
    base = {r["skill_name"]: r for r in load(args.baseline)}
    cand = {r["skill_name"]: r for r in load(args.candidate)}
    aff, deg, newly = [], [], []
    for n, c in cand.items():
        b = base.get(n)
        if not b: continue
        d = c["score"] - b["score"]
        if d != 0: aff.append({"skill": n, "delta": d})
        if d < 0:  deg.append({"skill": n, "delta": d})
        if b["passed"] and not c["passed"]: newly.append(n)
    rep = {"total_skills": len(cand), "affected_count": len(aff),
           "degraded_count": len(deg), "newly_failing_count": len(newly),
           "newly_failing": newly,
           "avg_delta": mean([x["delta"] for x in aff]) if aff else 0,
           "details": sorted(aff, key=lambda x: x["delta"])}
    Path(args.out).write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if not newly else 1

if __name__ == "__main__":
    sys.exit(main())
```

LLM 採点は別 process、本 script は JSON Lines の差分だけを決定論で計算する。`newly_failing_count > 0` なら必ず猶予期間を設定する（§7）。

---
## 7. 猶予期間運用（Skill 側 deprecation warning）

猶予期間中、evaluator は **旧/新 rubric_version の両方で採点**し、新で fail / 旧で pass の Skill に warning を出す。

`assign-skill-design-evaluator/SKILL.md`（抜粋パターン）:

```markdown
## 猶予期間運用

references/rubric.json に grace_period: がある場合:
1. 旧 rubric (grace_period.from_version) で採点 → score_old, passed_old
2. 新 rubric (現行 version) で採点 → score_new, passed_new
3. passed_old && !passed_new なら出力 JSON に deprecation_warning を含める:
   { "rubric_item_id": "...", "effective_release": "...", "remediation": "..." }
4. passed_new を最終 passed とするが、猶予中は CI を fail させない（warning のみ）。
5. 発効後（effective_release 到達）は warning を廃止し passed_new で gate。
```

これにより作者は猶予期間中に修正でき、発効日に一斉に CI が赤くなる事態を避けられる。

---
## 8. 発効と版管理（semver / hash / changelog）

### 8.1 version 規約

| 変更種別 | bump | 例 |
|---|---|---|
| 項目追加（緩和） | minor | 1.2.0 → 1.3.0 |
| 項目厳格化/削除 | major | 1.2.0 → 2.0.0 |
| 文言修正・誤字 | patch | 1.2.0 → 1.2.1 |

major bump は必ず猶予期間（最低 1 release / 30 日）を伴う。

### 8.2 hash 算出

evaluator は `rubric_hash` を出力に含める（09 章踏襲）。算出は `hashlib.sha256` + 正規化 JSON。22 章準拠で yaml を import せず、`rubric.json` を CI で正規化 JSON に変換した `references/rubric.normalized.json` を hash 入力とする。発効時に hash を `rubric-versions.md` に記録。

### 8.3 rubric-versions.md 追記

`eval-log/rubric-versions.md`（plugin 移行後は `eval-log/<plugin>/rubric-versions.md`）:

```markdown
## 1.3.0 (2026-06-01)
- rubric_id: skill-design / hash: sha256:abcd...
- proposal: docs/rubric-proposals/2026-05-17-tighten-fm-description.yaml
- changes: tighten fm-description-length (200文字 / trigger 条件含む)
- grace_period: from 1.2.0, 2026-05-17 → 2026-06-01
- impact: affected=12, newly_failing_at_announce=4, at_enactment=0
```

CHANGELOG.md にも同 release エントリを追加する。

### 8.4 quality-rubric.md 自動再生成 governance-log (DLOOP-001)

`plugins/skill-intake/references/quality-rubric.md` のような **rubric の派生 markdown** は、`rubric.json` 改訂時に CI で自動再生成する。再生成イベントは `eval-log/<plugin>/rubric-governance-log.jsonl` に 1 行 append し、以下フィールドを必須化する:

| field | 内容 |
|---|---|
| `event` | `rubric_derived_md_regenerated` |
| `ts` | ISO8601 |
| `source_rubric_id` + `source_rubric_hash` | 派生元 rubric.json の id と sha256 |
| `target_path` | 再生成された .md の相対パス |
| `trigger_session_id` / `trigger_failure_mode` | 再生成の根拠となった 35 章 observable (任意) |

これは double-loop 学習 (前回 review の改善が次回に反映されているか) を機械観測可能にするため。手作業での .md 直接編集は禁止 (CI lint で diff 検出 → exit 1)。

### 8.5 elegant-review v2 governance-log: 範囲外 finding のスキップ記録 (2026-05-23 セッション)

`run-elegant-review` v2 改善実行で **規模・新規実装リスク** から本セッションで未着手とした finding を記録する。再評価条件と次セッション開始時の必須確認項目を明示し、永久 deferral を防止する。

| ID | 概要 | スキップ理由 | trade-off | 再評価条件 | 次セッション必須確認 | deadline |
|---|---|---|---|---|---|---|
| LAT-001 | prompt-as-template-engine adapter pilot | 新規 adapter 実装 (規模大、跨複数 plugin) | 即時着手なら elegant-review が遅延、6 章命名規約抵触リスク | adapter 設計 ADR が起票され proposer≠approver で承認後 | adapter scope/契約/test 計画/migration 影響を 5 行以内で要約 | 2026-06-20 |
| IF-001 | scripts/lint-prompt-naming.sh 新規 + CI 配線 | 新規 lint script + CI workflow 改修 (規模中、CI 全体回帰リスク) | 即時着手なら CI 安定性に影響 | prompt 命名規約 (responsibility_refs パス規則) が確定後 | 命名規約 v1 仕様文書 + 既存 prompt の違反件数 baseline | 2026-06-13 |
| G6 | rate-limit (7 日/1 PR) 計測 script | `plugins/skill-governance-automation/scripts/check-emit-rate-limit.py` 新規。observable jsonl 集計 + PR メタ照合実装が必要 | 即時実装で elegant-review 範囲超 | observable jsonl の record 数が rate-limit 想定の最小 sample (>=10) を満たすか確認後 | jsonl 母数 + PR メタソース仕様 (gh api or PR title prefix) | 2026-06-06 |
| G7 | classify/accumulate 中間層実装 (`classify-meta-harness.py` / `accumulate-observables.py`) | 35 章 3 層モデルの新規 script 2 件、データフロー設計が未確定 | 即時実装で 35 章設計と二重実装の risk | 35 章 §3 層メタモデルが Layer 2/3 入出力 schema を確定 | classify 出力 schema + accumulate 集計鍵 | 2026-06-13 |

**自動 escalation**: deadline 超過 release で本 §8.5 表に残存している ID は、`scripts/lint-rubric-violation.py` の検出対象に **強制 inject** する (CI で表を parse し deadline < today なら exit 2)。これにより人手で deferral を継続できない。

**proposer ≠ approver**: 本表への ID 追加は提案者起票だが、削除 (= 完了マーク) は別 SubAgent または別人間が `eval-log/<plugin>/rubric-governance-log.jsonl` への完了 event 追記と引換に行う (§4 governance 役割表に準拠)。

---
## 9. 自動化責務分担表

| ステップ | 人 | script | Hook | CI |
|---|---|---|---|---|
| eval-log への append | – | evaluator 出力を追記 | – | ○ |
| 違反率集計 | – | `lint-rubric-violation.py` | – | ○（release tag） |
| 招集通知 | – | – | `Stop` | ○（exit 2 受信） |
| 改正提案 YAML 作成 | ○ 提案者 | テンプレ展開のみ | – | – |
| rubric diff | ○ 提案者 | – | – | – |
| 影響評価 | – | `diff-rubric-impact.py` | – | ○（PR 時自動） |
| Goodhart（評価基準を都合よく歪める罠） リスク評価 | ○ 第三者レビュアー | – | – | – |
| 猶予期間長確定 | ○ 承認者 | – | – | – |
| 猶予中 warning | – | evaluator 内ロジック | – | ○（warning 限定） |
| 発効（version bump） | ○ 承認者（merge） | `compute-rubric-hash.py` | – | ○ |
| `rubric-versions.md` 追記 | ○ 提案者 | テンプレ展開 | – | ○（lint） |
| 安定版凍結判定 | – | detect script 凍結モード | – | ○ |
| 自動 rollback | – | `rollback-to-stable.py` | `PostToolUse` | ○ |

**人手判断は 5 箇所のみ**（提案 / リスク評価 / 期間確定 / merge / versions 追記）。残りは決定論または LLM 採点の集計。

---
## 10. アンチパターン集（Goodhart（評価基準を都合よく歪める罠） / 濫用防止）

| # | アンチパターン | 症状 | 対策 |
|---|---|---|---|
| 1 | 緩和ばかりの連発 | minor bump 連続で違反率が機械的に下がる | tooling 役が直近 3 release の tighten/loosen 比率を `impact-report.json` に出し、loosen 連続を第三者レビュアーが拒否 |
| 2 | 提案者=承認者 | 自己承認で Goodhart（評価基準を都合よく歪める罠） | CI で PR author と approver の重複を lint、重複時 merge block |
| 3 | 猶予ゼロ強行 | `newly_failing>0` なのに即発効 | `diff-rubric-impact.py` exit 1 で CI fail |
| 4 | rubric を generator/evaluator が改変 | 評価対象が基準を書換 | permissions で `references/rubric.json` への Write/Edit を deny |
| 5 | trigger なし「気分」改正 | `manual` 連発 | 四半期 1 件まで（governance-params） |
| 6 | eval-log の選択削除 | 不利な release log 削除で違反率を下げる | append-only、削除 PR を CI block |
| 7 | rubric 項目 ID 使い回し | 同 ID の意味が改正で変わると時系列違反率が破綻 | major bump 時は ID を `*-v2` に rename、旧 ID を deprecated |
| 8 | 「全項目総取り替え」 | 影響評価が実質不可能 | major bump は 1 PR あたり最大 3 項目 |
| 9 | 安定版の個別解除 | templates だけ更新、rubric 据え置き | templates + rubric（評価基準）は同時凍結・同時解除のみ（23 章踏襲）、個別操作 CI block |
| 10 | 猶予中 warning の無視蓄積 | 発効日に大量 fail | warning 件数を `eval-log/grace-warnings.csv` に記録、発効 2 週間前に Hook で再通知 |

---
## 11. パラメータ正本（governance-params.json）

`xl-skills/references/governance-params.json`:

```json
{
  "detection": {
    "consecutive_releases": 3,
    "violation_rate_threshold": 0.20
  },
  "freeze": {
    "consecutive_runs": 10,
    "violation_rate_ceiling": 0.05
  },
  "grace_period": {
    "min_releases": 1,
    "min_days": 30
  },
  "limits": {
    "manual_proposals_per_quarter": 1,
    "major_bump_items_per_pr": 3
  },
  "solo_operator_mode": false
}
```

数値正本はここに集約し、23 章のデフォルト値とこのファイルを一致させて二重管理を避ける。

---
## 12. 他章との関係マップ

| 章 | 本章での参照 |
|---|---|
| 06 第15条 | `trigger.type: naming_amendment` で接続 |
| 09 | eval-log JSON schema、evaluator 契約、Goodhart（評価基準を都合よく歪める罠） 対策 |
| 22 | 全 script を Python 3 標準ライブラリに限定 |
| 23 | governance 節・安定版凍結・退避ルールの実装 |
| 25 | 通常 Runbook と本 governance Runbook の切替条件 |
| 26 | 設計書自体を採点対象に含み、本章も rubric 違反検出の対象 |

矛盾が生じた場合は **23 章を正、本章を従**。数値差は `governance-params.json` の更新で吸収する。

---
## 13. solo_operator_mode（A1/C1, CD-009 パッチ）

1人運用環境では提案者と承認者の兼任が構造上不可避になる。`references/governance-params.json` に `"solo_operator_mode": true` を設定し、下記3条件をすべて満たす場合に限り自己承認を許可する。

### 自己承認条件

| # | 条件 | 確認方法 |
|---|---|---|
| 1 | 安定版凍結済み | `lint-rubric-violation.py` が freeze 条件（連続10 release × 5%以下）を報告 |
| 2 | newly_failing=0 | `diff-rubric-impact.py` 出力の `newly_failing_count == 0` |
| 3 | LLM-reviewer pass | `run-skill-rubric-governance` Step2 影響評価で problem=none |

### solo_operator_mode 有効中の制約

- major bump 禁止（minor/patch のみ）
- governance log に `solo_operator: true` と3条件の evidence を必ず記録
- `proposal.json` に evidence artifact（スクリプト出力 JSON）を添付

### 解除条件

- 組織メンバー追加時は `solo_operator_mode: false` に戻し、通常の4ロールに移行する
- TODO(human): メンバー追加時の解除手順を PR checklist に追加すること

---
## 14. 段階昇格ロードマップ（CD-001 パッチ）

第2階（案A: MVP）が安定するまで第3階（案B: rubric独立）へ昇格しない。

### 昇格ゲート

| フェーズ | 前提条件 | 確認方法 |
|---|---|---|
| MVP (案A) → 昇格版 (案B) | evaluator が2つ以上存在 OR rubric の独立 versioning が必要 | スキルディレクトリ数 + 運用判断 |
| 昇格版 (案B) 安定 | 連続3 release で violation_rate <= 5% | `lint-rubric-violation.py` freeze モード |
| 案C/D/E 検討 | 社外配布・機械契約中心化 | TODO(human): 要件が具体化した時点で再検討 |

### 昇格禁止条件

- solo_operator_mode 有効中は major bump 禁止と同様、案A→案B 昇格を保留する
- 第2階の安定版凍結が未達成の場合、第3階の構築を開始しない（CD-001: 第2階未安定で第3階構築を禁止）

### 昇格時の更新対象

昇格時（案A→案B）は以下を同時更新する（部分更新禁止）:
1. `README.md` の rubric 正本参照先
2. `13-checklists.md` の rubric 参照
3. `24-meta-skill-templates.md` の rubric 参照
4. `25-meta-skill-runbook.md` の rubric 参照
5. 旧 rubric (`assign-skill-design-evaluator/references/rubric.json`) に deprecation 記録

TODO(human): 昇格時の更新対象リストを PR checklist として `.github/PULL_REQUEST_TEMPLATE.md` に追加すること。
