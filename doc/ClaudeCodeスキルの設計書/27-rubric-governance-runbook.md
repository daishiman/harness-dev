# 27. rubric ガバナンス Runbook

## 目的・出力・禁則・関連章（compaction対策）

### 目的

rubric 改正手続きを「**自動検出 → 招集 → 評価 → 猶予 → 発効**」の 5 ステップ Runbook に落とし、23 章 governance 節を矛盾なく詳細化する。Goodhart（評価基準を都合よく歪める罠） 対策と知見蓄積を両立し、人/script/Hook/CI の責務境界を明示する。

### 出力

- score ログ（`eval-log/**/*-score.jsonl`）を集計する自動検出 script（`plugins/skill-governance-lint/scripts/lint-rubric-violation.py`）
- 改正提案テンプレ（実装は `run-skill-rubric-governance` の `templates/proposal.json`。§5 の YAML は素案）
- 影響評価 script（過去の score ログに提案を当てて合否の変動を見積もる。§6）
- deprecation warning パターン（evaluator 側は未実装（計画）。§7）
- `eval-log/rubric-versions.md` 発効記録（まだ無い。最初の発効で作る。§8.3）

### 禁則

- rubric を evaluator/generator が編集（09 章 Goodhart（評価基準を都合よく歪める罠） 対策）
- 提案者と承認者の兼任（自己承認）
- `would_flip>0` で猶予ゼロ発効
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

23 章既定値（`連続3×20%`、凍結 `N=10, M%=5%`）を継承し、調整可能パラメータとして repo root の `references/governance-params.json` に外出しする（まだ無い。§11）。06 章との接続は §3.3。

---
## 2. governance 自動化アーキテクチャ

```text
  eval-log/**/*-score.jsonl (09)
              │ (人が回す。release tag の CI は未実装)
              ▼
        lint-rubric-violation.py  (§3.2, 決定論)
              │ eval-log/trigger.json / exit 2
              ▼
        notify-if-governance-trigger.py  (§3.4)  ── governance ボード招集通知
              │ (人が手で呼ぶ。Stop Hook への登録は未実装)
              │ (人手: 提案者起票)
              ▼
        PR: 改正提案  (§5。proposals/<date>-<slug>.md + proposal.json)
              │ (人が回す。PR 時の CI は未実装)
              ▼
        diff-rubric-impact.py  (§6)  → stdout の JSON (would_flip / required_bump)
              │
              ▼
        第三者レビュアー → 承認者  (§4, §7)
              │ approve
              ▼
        猶予期間: 旧ルールを warning (severity→low) に下げて残す  (§7。旧/新の併走採点は未実装)
              │ 期間満了
              ▼
        発効: version bump + compute-rubric-hash.py + eval-log/rubric-versions.md / CHANGELOG  (§8)
```

縦軸が時間。人手 / 自動の境界は §9 で表化する。script の置き場は、`lint-rubric-violation.py` が `plugins/skill-governance-lint/scripts/`、`notify-if-governance-trigger.py` と `compute-rubric-hash.py` が `plugins/skill-governance-automation/scripts/`、`diff-rubric-impact.py` が `plugins/harness-creator/skills/run-skill-rubric-governance/scripts/`。

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

`lint-rubric-violation.py` の素案（Python 3 標準ライブラリのみ。22 章準拠。実装は下の注記）:

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

判定は決定論。LLM は使わない。上は設計時の素案で、実装は `plugins/skill-governance-lint/scripts/lint-rubric-violation.py`。`--log-dir` の下の `*-score.jsonl` を再帰で読み、`--out` に trigger.json（置き場は `eval-log/trigger.json`）を書く。exit は 0=招集不要、2=招集必要、3=score ログが `--bootstrap-threshold`（既定 20）件に満たず判定を保留、1=trigger.json を書けない。rule ごとの件数は `run-skill-rubric-governance/scripts/lint-rubric-violation.py` が別に数える。この script を CI で回す job と、exit 2 を受けて招集の Hook を起こす配線は未実装（計画）で、今は `run-skill-rubric-governance` の手順で人が回す。

### 3.3 しきい値判定と 06 章第15条との関係

| パラメータ | 既定 | 出典 | 調整 |
|---|---|---|---|
| `N`（連続 release） | 3 | 23 章 | `governance-params.json` |
| `M%`（違反率） | 20% | 23 章 | 同上 |
| 凍結 `N` | 10 | 23 章 安定版凍結 | 同上 |
| 凍結 `M%` | 5% | 同上 | 同上 |

06 章 第15条は命名規約改正だが、命名規約条文も `naming-*` prefix の rubric 項目として eval-log に記録するため、本章の検出ロジックがそのまま適用できる。第15条が要求する「影響を受ける Skill リスト」は、§6 の `diff-rubric-impact.py` が件数（`would_flip`）しか出さないので、今は人が score ログから拾う（Skill の一覧を出す機能は未実装（計画））。

### 3.4 検出時の通知（Hook で発火）

`lint-rubric-violation.py` の exit 2 を受け、`Stop` Hook で招集メッセージを表示する設計である。script の実体は `plugins/skill-governance-automation/scripts/notify-if-governance-trigger.py`（`--trigger` の既定は `eval-log/trigger.json`）。Hook への登録は未実装（計画）で、どの hooks.json にも `.claude/settings.json` にも入っておらず、今は人が手で呼ぶ。登録するときの `.claude/settings.json`（抜粋）:

```json
{ "hooks": { "Stop": [ { "matcher": ".*", "hooks": [
  { "type": "command",
    "command": "python3 ${CLAUDE_PROJECT_DIR}/plugins/skill-governance-automation/scripts/notify-if-governance-trigger.py --trigger ${CLAUDE_PROJECT_DIR}/eval-log/trigger.json" }
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
| **tooling 役（新規）** | script/Hook/CI 維持、`diff-rubric-impact.py` が出す JSON の品質保証 | 人（`assign-governance-tooling-contributor` は未実装（計画）） |

tooling 役は人手判断をしない。「人手判断に必要な数値が揃っているか」だけを保証する。提案者と承認者の兼任は禁止（23 章踏襲）。tooling 役は他役と兼任可。

### 4.1 PKG ID 改廃の governance（36章連動、2026-05-20 追加）

36章 Plugin Package Harness Contract の **PKG ID（PKG-001〜017、PKG-013 の 013a/013b/013c/013d への分割等を含む）の新設・分割・削除・意味変更** は、本章 rubric governance のレビュー対象に含める。理由は、PKG gate は rubric 違反率と同じく eval-log 集計に直結し（§3.1 PKG gate 用 eval-log パス）、ID 使い回しが時系列比較性を破壊するため（§10 アンチパターン #7 と同型）。

| 操作 | 承認要件 |
|---|---|
| PKG ID 新設 | 36章正本への追加 PR + 本章 §5 の改正提案（`trigger.type: "manual"` で起票、提案者≠承認者） |
| PKG ID 分割（例: 013 → 013a〜d） | 上記に加え、旧 ID を deprecated として 1 release 以上猶予（§7） |
| PKG ID 削除 | 上記に加え、`diff-rubric-impact.py` 相当の影響評価（既存 plugin の PKG fail 履歴に対する影響）を添付 |
| PKG ID 意味変更 | 36章 + 本章で **major bump 扱い**。新 ID（例: `PKG-001-v2`）を発行し旧 ID を deprecated（§10 #7 準用） |

PKG ID の改廃を 36章単独で行うことは禁止。本章承認を経ない PKG ID 変更は CI block 対象とする（それを検査する CI の job は未実装（計画））。

---
## 5. 改正提案テンプレ（YAML）

PR 起票時、人が読む提案書（front matter つきの md）を `plugins/harness-creator/skills/run-skill-rubric-governance/proposals/<YYYY-MM-DD>-<slug>.md` に置き（実例は `2026-10-09-ja-heading-alias.md`）、`diff-rubric-impact.py --proposal` に渡す機械可読の提案を同じ Skill の `templates/proposal.json` の形で作る。下の YAML は設計時の素案で、YAML の提案ファイルは実装していない（項目の対応は下の注記）。

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
  detected_by: "plugins/skill-governance-lint/scripts/lint-rubric-violation.py"
  trigger_artifact: "eval-log/trigger.json"
rubric_diff:
  rubric_id: "skill-design"
  from_version: "1.2.0"
  to_version:   "2.0.0"    # tighten は厳格化なので major（§8.1）
  changes:
    - rubric_item_id: "fm-description-length"
      kind: "tighten"      # tighten | loosen | add | remove | clarify
      before: "description は適切な長さ"
      after:  "description は 200 文字以内、かつ trigger 条件を含む"
expected_effect:
  - "違反率が次 release で 10% 以下に低下する見込み"
  - "templates/ の description 欄を同時更新"
impact_assessment_required: true  # §6 で自動生成
grace_period: {min_days: 14}   # major>=14d / minor>=7d / patch 0d（Key Rule 3。§8.1）
approvers: {reviewer: "@TBD", approver: "@TBD"}
```

素案と `templates/proposal.json` の対応: `rubric_diff.changes[].kind` は `change.type`（add / remove / modify）と、modify のときの `change.direction`（tighten / relax）に当たる。tighten と add は厳格化で major（猶予 14 日以上）、loosen（relax）と remove は緩和で最低 minor（猶予 7 日。§8.1 の条件を満たせば 0 日）、clarify は判定を変えない文言の修正だけなら patch で、判定が変わるなら厳格化か緩和として扱う（§6 の注記と同じ規則）。`from_version` は `current_version`、`to_version` は `current_version` に `bump` を当てた版（提案書の front matter では `proposed_version`）、`grace_period.min_days` は `sunset_days`、`approvers` は `reviewers` に当たる。

`trigger.type == "naming_amendment"` の場合は 06 章 第15条を優先し、本テンプレの `rubric_diff` は naming 連動項目の追従に限定する。

---
## 6. 影響評価（破壊度測定 script）

`diff-rubric-impact.py` の素案（Python 3 標準ライブラリのみ。実装は下の注記）:

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

LLM 採点は別 process、本 script は JSON Lines の差分だけを決定論で計算する。

上は設計時の素案である。実装（`plugins/harness-creator/skills/run-skill-rubric-governance/scripts/diff-rubric-impact.py` 0.5.1）は `--proposal <proposal.json> --logs eval-log [--threshold 80]` を取り、過去の score ログに提案を当てて `would_flip`・`flip_rate`・`required_bump` を出す。見積もりの模型は提案の向きで選ぶ。厳格化（`change.type: add`、または `modify` で `change.direction: tighten`）は最悪の場合で数え、緩和（`remove`、または `modify` で `relax`）は定義上 `would_flip` が 0 になる。direction の無い `modify` は厳格化とみなす（`direction_source: assumed`）。`required_bump` は、厳格化なら合否変動率に関わらず major（`run-skill-rubric-governance` の SKILL.md Key Rule 2）、緩和なら提案の bump と minor の大きい方（閾値や severity を変えるなら最低 minor。下回ってよいのは文言だけの patch と緊急パッチだけ）。bump（最上位か `change.bump`）が無いか major・minor・patch 以外なら exit 2 で止まる。両方に書いてあり、どちらかが不正か値が違うときも exit 2 で止まる（片方を黙って選ばない）。厳格化で `change.severity` が無いか high・medium・low 以外のときは、一番重い重み（high の -20）で見積もり、stderr に warning を出す。使った重みは出力の `severity_weight` に、その出どころは `severity_source`（`change.severity` どおりなら `declared`、推し量ったなら `assumed`。緩和はどちらも null）に残す。合否変動率が 30% を超えたか（`exceeds_flip_rate_limit`）は bump を決めず、猶予期間と board 招集の根拠として別に出す。`would_flip > 0` なら必ず猶予期間を設定する（§7）。`would_flip` が 0 の緩和の minor の猶予期間は §8.1 のとおり。

---
## 7. 猶予期間運用（Skill 側 deprecation warning）

猶予期間中、evaluator は **旧/新 rubric_version の両方で採点**し、新で fail / 旧で pass の Skill に warning を出す設計である。この二重採点は未実装（計画）で、`assign-skill-design-evaluator` に `grace_period` を読む処理は無い。evaluator の採点で落ちる CI の job も無い（rubric に関わる CI は §9 の表）。今の猶予は、`run-skill-rubric-governance` の手順どおり、厳格化した旧ルールの severity を low に下げて warning として残し、その記録を governance log に書く形で行う。

実装するときの `assign-skill-design-evaluator/SKILL.md` の抜粋パターン（計画）:

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

これにより作者は猶予期間中に修正でき、発効日に一斉に fail が出る事態を避けられる。

---
## 8. 発効と版管理（semver / hash / changelog）

### 8.1 version 規約

| 変更種別 | bump | 猶予期間 | 例 |
|---|---|---|---|
| ルール追加・weight↑（厳格化） | major | 14 日以上 | 1.2.0 → 2.0.0 |
| ルール削除・しきい値↓（緩和） | minor | 7 日（下の条件を満たせば 0 日） | 1.2.0 → 1.3.0 |
| 文言修正・誤字 | patch | 即時 | 1.2.0 → 1.2.1 |

向きと猶予日数の正本は `run-skill-rubric-governance` の SKILL.md（Key Rule 2 と Key Rule 3。細目は同じ Skill の `references/version-rules.md`）で、この表はそれに合わせる。緩和とは、今まで合格したものがすべて合格のままである変更をいい、そうでない変更は厳格化として扱う（§6 の注記）。

緩和の minor で、`diff-rubric-impact.py` の `would_flip` が 0 であり、承認者が緩和の根拠を確かめたものは、猶予期間を 0 日にできる。その理由は governance log に残す。23章「改正の段階」3 の、影響を受ける Skill が 0 なら猶予期間を置かないのと同じ考えである。

### 8.2 hash 算出

evaluator は `rubric_hash` を出力に含める（09 章踏襲）。その値は rubric.json のファイルの sha256 である（`assign-skill-design-evaluator/scripts/render-findings-score.py`）。

発効時に記録する hash は、これとは別に `plugins/skill-governance-automation/scripts/compute-rubric-hash.py --rubric <rubric.json>` が出す。この script は `rubric_hash` を除いた rubric.json を正規化 JSON（キーを並べ替え、区切りの空白なし）にして `hashlib.sha256` を取り、rubric.json の `rubric_hash` に書き戻し、同じディレクトリに `rubric.normalized.json` を書く（22 章準拠で yaml は import しない）。`rubric.normalized.json` は commit しておらず repo に無い。この変換を CI で回す job も無く（未実装）、発効の手順で人が回す。正規化 JSON の hash を `eval-log/rubric-versions.md` に記録する（§8.3）。

### 8.3 rubric-versions.md 追記

`eval-log/rubric-versions.md`。まだ無く、最初の発効で版の節を追記したときに作る。複数の rubric の版を1つのファイルに並べ、各節の `rubric_id` 行で区別する（`run-skill-rubric-governance` の発効手順と `rollback-to-stable.py --versions-md` がこのパスを使う）。ひな形（§5 の素案の厳格化を発効した例なので major）:

```markdown
## 2.0.0 (2026-06-01)
- rubric_id: skill-design / hash: sha256:abcd...
- proposal: plugins/harness-creator/skills/run-skill-rubric-governance/proposals/2026-05-17-tighten-fm-description.md
- changes: tighten fm-description-length (200文字 / trigger 条件含む。厳格化なので major)
- grace_period: from 1.2.0, 2026-05-17 → 2026-06-01
- impact: affected=12, newly_failing_at_announce=4, at_enactment=0
```

CHANGELOG.md にも同 release エントリを追加する。

実例（2026-10-09、日本語の正規見出し）:

- **1.4.0**（minor・緩和）: BD-001・BD-002・PD-002 の見出し候補に `## 目的と出力契約`・`## つまずきやすい点` を別名として追加した。日本語は行全体の一致だけを認め、英語側の判定は変えていない。過去の合格はすべて合格のまま（flip_rate 0.0）。proposal は `plugins/harness-creator/skills/run-skill-rubric-governance/proposals/2026-10-09-ja-heading-alias.md`。
- **1.5.0**（minor）: PD-002 の禁則の条件に `## 守ること` の行一致を追加し、BD-001 と PD-002 の関係の説明を訂正した（BD-001 は契約節の有無、PD-002 は冒頭30行への集約を独立に見る）。本文中の単語「守ること」だけでは合格しない。記録は `PROP-2026-10-09-ELEGANT-PD002`。

どちらも `run-skill-rubric-governance/log/governance-log.jsonl` と `.claude/changelog/governance-log.jsonl` に記録し、L2 の `upstream_version_pin` と `rubric_hash` を同期した。

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

この節はすべて未実装（計画）である。再生成の script、`eval-log/<plugin>/rubric-governance-log.jsonl`、手編集を検出する CI lint はどれも無く、`quality-rubric.md` は今は手で直している。

### 8.5 elegant-review v2 governance-log: 範囲外 finding のスキップ記録 (2026-05-23 セッション)

`run-elegant-review` v2 改善実行で **規模・新規実装リスク** から本セッションで未着手とした finding を記録する。再評価条件と次セッション開始時の必須確認項目を明示し、永久 deferral を防止する。

| ID | 概要 | スキップ理由 | trade-off | 再評価条件 | 次セッション必須確認 | deadline |
|---|---|---|---|---|---|---|
| LAT-001 | prompt-as-template-engine adapter pilot | 新規 adapter 実装 (規模大、跨複数 plugin) | 即時着手なら elegant-review が遅延、6 章命名規約抵触リスク | adapter 設計 ADR が起票され proposer≠approver で承認後 | adapter scope/契約/test 計画/migration 影響を 5 行以内で要約 | 2026-06-20 |
| IF-001 | scripts/lint-prompt-naming.sh 新規 + CI 配線 | 新規 lint script + CI workflow 改修 (規模中、CI 全体回帰リスク) | 即時着手なら CI 安定性に影響 | prompt 命名規約 (responsibility_refs パス規則) が確定後 | 命名規約 v1 仕様文書 + 既存 prompt の違反件数 baseline | 2026-06-13 |
| G6 | rate-limit (7 日/1 PR) 計測 script | `plugins/skill-governance-automation/scripts/check-emit-rate-limit.py` 新規。observable jsonl 集計 + PR メタ照合実装が必要 | 即時実装で elegant-review 範囲超 | observable jsonl の record 数が rate-limit 想定の最小 sample (>=10) を満たすか確認後 | jsonl 母数 + PR メタソース仕様 (gh api or PR title prefix) | 2026-06-06 |
| G7 | classify/accumulate 中間層実装 (`classify-meta-harness.py` / `accumulate-observables.py`) | 35 章 3 層モデルの新規 script 2 件、データフロー設計が未確定 | 即時実装で 35 章設計と二重実装の risk | 35 章 §3 層メタモデルが Layer 2/3 入出力 schema を確定 | classify 出力 schema + accumulate 集計鍵 | 2026-06-13 |

**自動 escalation**: deadline 超過 release で本 §8.5 表に残存している ID は、`lint-rubric-violation.py` の検出対象に **強制 inject** する (CI で表を parse し deadline < today なら exit 2)。これにより人手で deferral を継続できない。この escalation は未実装（計画）で、`lint-rubric-violation.py` はこの表を読まず、表を parse する CI の job も無い。

**proposer ≠ approver**: 本表への ID 追加は提案者起票だが、削除 (= 完了マーク) は別 SubAgent または別人間が governance log（`plugins/harness-creator/skills/run-skill-rubric-governance/log/governance-log.jsonl`）への完了 event 追記と引換に行う (§4 governance 役割表に準拠)。

---
## 9. 自動化責務分担表

| ステップ | 人 | script | Hook | CI |
|---|---|---|---|---|
| eval-log への append | – | evaluator 出力を `write-eval-log.py` で追記 | – | 未実装 |
| 違反率集計 | 回す | `lint-rubric-violation.py` | – | 未実装（release tag の job は無い） |
| 招集通知 | 回す | `notify-if-governance-trigger.py` | 未実装（`Stop` への登録は計画） | 未実装 |
| 改正提案作成 | ○ 提案者 | –（`templates/proposal.json` を埋める） | – | – |
| rubric diff | ○ 提案者 | – | – | – |
| 影響評価 | 回す | `diff-rubric-impact.py` | – | 未実装（PR 時の job は無い） |
| Goodhart（評価基準を都合よく歪める罠） リスク評価 | ○ 第三者レビュアー | – | – | – |
| 猶予期間長確定 | ○ 承認者 | – | – | – |
| 猶予中 warning | 旧ルールの severity を low に下げる | 未実装（evaluator の二重採点は計画。§7） | – | 未実装 |
| 発効（version bump） | ○ 承認者（merge） | `compute-rubric-hash.py` | `PostToolUse`（`.claude/settings.json` の `re-evaluate-on-rubric-bump.py --post-tool-use`） | `harness-creator-kit-ci.yml` の job `governance`: `check-rubric-sync.py`（L0/L2 の版ずれで fail）と `re-evaluate-on-rubric-bump.py`（major bump の再評価対象は通知だけで、対象があっても exit 0。入力を読めないときだけ fail） |
| `rubric-versions.md` 追記 | ○ 提案者 | –（§8.3 のひな形を手で書く） | – | 未実装（lint は無い） |
| 安定版凍結判定 | 数える | 未実装（`lint-rubric-violation.py` に凍結の判定は無い。数え方は `run-skill-rubric-governance/references/governance-board.md`） | – | 未実装 |
| 自動 rollback（計画） | 回す | `rollback-to-stable.py`（巻き戻しの計画を出すだけで、書き込まない） | `PostToolUse`（計画。未実装で、hook にはつないでいない） | 未実装 |

**人手判断は 5 箇所のみ**（提案 / リスク評価 / 期間確定 / merge / versions 追記）。残りは決定論または LLM 採点の集計。ただし「未実装」の欄を自動化するまでは、人の欄に「回す」「数える」と書いたステップも、`run-skill-rubric-governance` の手順で人が script を回すか数える。script の置き場は §2 の図の下に書いた（`write-eval-log.py` と `rollback-to-stable.py` は `plugins/skill-governance-automation/scripts/`）。

---
## 10. アンチパターン集（Goodhart（評価基準を都合よく歪める罠） / 濫用防止）

| # | アンチパターン | 症状 | 対策 |
|---|---|---|---|
| 1 | 緩和ばかりの連発 | minor bump 連続で違反率が機械的に下がる | tooling 役が直近 3 release の tighten/loosen 比率を影響評価の結果に添え（`diff-rubric-impact.py` は比率を出さないので、governance log から数える）、loosen 連続を第三者レビュアーが拒否 |
| 2 | 提案者=承認者 | 自己承認で Goodhart（評価基準を都合よく歪める罠） | CI で PR author と approver の重複を lint、重複時 merge block |
| 3 | 猶予ゼロ強行 | `would_flip>0` なのに即発効 | `diff-rubric-impact.py` の `would_flip`・`required_bump` を承認レビューで確かめ、猶予期間の無い発効を拒否する（道具は exit 0 で数字を出すだけで、CI を止めない） |
| 4 | rubric を generator/evaluator が改変 | 評価対象が基準を書換 | permissions で `references/rubric.json` への Write/Edit を deny |
| 5 | trigger なし「気分」改正 | `manual` 連発 | 四半期 1 件まで（governance-params） |
| 6 | eval-log の選択削除 | 不利な release log 削除で違反率を下げる | append-only、削除 PR を CI block |
| 7 | rubric 項目 ID 使い回し | 同 ID の意味が改正で変わると時系列違反率が破綻 | major bump 時は ID を `*-v2` に rename、旧 ID を deprecated |
| 8 | 「全項目総取り替え」 | 影響評価が実質不可能 | major bump は 1 PR あたり最大 3 項目 |
| 9 | 安定版の個別解除 | templates だけ更新、rubric 据え置き | templates + rubric（評価基準）は同時凍結・同時解除のみ（23 章踏襲）、個別操作 CI block |
| 10 | 猶予中 warning の無視蓄積 | 発効日に大量 fail | warning 件数を `eval-log/grace-warnings.csv` に記録、発効 2 週間前に Hook で再通知 |

この表の対策のうち、CI で止めるもの（#2・#6・#9）、四半期の件数制限（#5）、`eval-log/grace-warnings.csv` と発効前の Hook 再通知（#10）は未実装（計画）で、今は承認レビューで確かめる。#4 は permissions ではなく、`.claude/settings.json` の PreToolUse に登録した `scripts/hook-guard-rubric.py`（`ALLOW_RUBRIC_EDIT=1` が無ければ canonical rubric の編集を止める）で実装している。

---
## 11. パラメータ正本（governance-params.json）

repo root の `references/governance-params.json`（`rollback-to-stable.py --params` の既定。作業ディレクトリ基準）。このファイルはまだ無い。ひな形は同じディレクトリの `references/governance-params.json.example` で、作るときはこれを写す。無いあいだ `rollback-to-stable.py` は警告を出して既定の ceiling 0.05 を使う。形（`solo_operator_mode` の条件文と `note` は example を参照）:

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
    "min_days": 14
  },
  "limits": {
    "manual_proposals_per_quarter": 1,
    "major_bump_items_per_pr": 3
  },
  "solo_operator_mode": {
    "enabled": true,
    "self_approval_conditions": ["..."]
  }
}
```

数値正本はここに集約し、23 章のデフォルト値とこのファイルを一致させて二重管理を避ける。ただし猶予日数の正本は `run-skill-rubric-governance` の Key Rule 3（`references/version-rules.md`）で、`grace_period.min_days` はそこから major の最低日数を写した値である（major>=14d / minor>=7d / patch 0d。緩和の minor で would_flip が 0 であり、承認者が緩和の根拠を確かめたものは、理由を記録して 0d にできる）。Key Rule 3 が決めるのは日数だけで、release の回数の下限は決めていない。そのため `grace_period` には `min_days` だけを置き、release の回数のキーは置かない（2本の `governance-params.json.example` も同じ形）。

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

1人運用環境では提案者と承認者の兼任が構造上不可避になる。repo root の `references/governance-params.json`（まだ無い。§11）で `solo_operator_mode.enabled` を `true` にし、下記3条件をすべて満たす場合に限り自己承認を許可する。

### 自己承認条件

| # | 条件 | 確認方法 |
|---|---|---|
| 1 | 安定版凍結済み | freeze 条件（連続10 run × 5%以下）を人が score ログから数えて evidence に書く（`lint-rubric-violation.py` に freeze の判定は無い。数え方は `run-skill-rubric-governance/references/governance-board.md`） |
| 2 | would_flip=0 | `diff-rubric-impact.py` 出力の `would_flip == 0` |
| 3 | LLM-reviewer pass | `run-skill-rubric-governance` Step2 影響評価で problem=none |

### solo_operator_mode 有効中の制約

- major bump 禁止（minor/patch のみ）
- governance log に `solo_operator: true` と3条件の evidence を必ず記録
- `proposal.json` に evidence artifact（スクリプト出力 JSON）を添付

### 解除条件

- 組織メンバー追加時は `solo_operator_mode.enabled` を `false` に戻し、通常の4ロールに移行する
- TODO(human): メンバー追加時の解除手順を PR checklist に追加すること

---
## 14. 段階昇格ロードマップ（CD-001 パッチ）

第2階（案A: MVP）が安定するまで第3階（案B: rubric独立）へ昇格しない。

### 昇格ゲート

| フェーズ | 前提条件 | 確認方法 |
|---|---|---|
| MVP (案A) → 昇格版 (案B) | evaluator が2つ以上存在 OR rubric の独立 versioning が必要 | スキルディレクトリ数 + 運用判断 |
| 昇格版 (案B) 安定 | 連続3 release で violation_rate <= 5% | 人が score ログから数える（`lint-rubric-violation.py` の freeze モードは未実装（計画）） |
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
