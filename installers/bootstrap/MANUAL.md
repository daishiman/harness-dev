# Bootstrap マニュアル（最後の砦）

`run-build-skill` と `assign-skill-design-evaluator` は相互依存している。一方が壊れた状態からはどちらの Skill 自身も自動再生成できない。本書は **エディタと Python3 stdlib だけ** で最小 Skill を手書きで再構築するための手順書である。

## 適用シーン

- `run-build-skill/SKILL.md` が破損 / 削除された
- `assign-skill-design-evaluator/references/rubric.json` が破損し採点不能
- `manifest.json` が壊れて install.sh が動かない
- 別プロジェクトに creator-kit を持ち込んだ直後で eval-log が空（bootstrap フェーズ）

## 前提（最小ツールセット）

| ツール | 用途 | 入手 |
|---|---|---|
| エディタ（vi / nano など） | SKILL.md 編集 | OS 標準 |
| Python 3.9+ stdlib | スクリプト実行 | `/usr/bin/python3`（macOS / Linux 既定） |
| `git` | バージョン管理 | OS 標準 / brew |
| `/bin/bash` 3.2+ | install.sh 実行 | OS 標準 |

**禁則**: PyYAML / requests / jq / yq には依存しない（28章 §22 no-deps 原則）。

## 最小 Skill の手書き手順

### Step 1: 最小 SKILL.md を書く

`creator-kit/skills/<my-first-skill>/SKILL.md` に次を書く。

```markdown
---
name: my-first-skill
description: <最小300字以内の説明、trigger条件2-3個を含む>
disable-model-invocation: false
user-invocable: true
allowed-tools: [Read]
kind: run
owner: bootstrap
since: <YYYY-MM-DD>
effect: local-artifact
source: bootstrap-manual
source-tier: internal
last-audited: <YYYY-MM-DD>
audit-trigger: quarterly
---

# my-first-skill

## Purpose & Output Contract
<目的を1段落で>

## Steps
1. <最初の手順>
2. <次の手順>

## Gotchas
- <既知の落とし穴>
```

### Step 2: 最小 rubric.json を書く

`creator-kit/skills/ref-skill-design-rubric/rubric.json` が壊れている場合、次の最小骨格で再構築する。

```json
{
  "rubric_id": "skill-design",
  "rubric_version": "0.1.0-bootstrap",
  "threshold": 60,
  "items": [
    { "rubric_item_id": "fm-name-kebab", "weight": 1, "rule": "name は kebab-case" },
    { "rubric_item_id": "fm-description-length", "weight": 1, "rule": "description は 1024 文字以内" },
    { "rubric_item_id": "body-line-budget", "weight": 1, "rule": "本文 300 行以内" }
  ]
}
```

threshold を意図的に低く（60）設定して bootstrap 中の通過を許容する。完全版 rubric に置き換わるまでの暫定値。

### Step 3: 手動で rubric_hash を計算

```bash
python3 creator-kit/scripts/compute-rubric-hash.py \
  --rubric creator-kit/skills/ref-skill-design-rubric/rubric.json
```

このスクリプト自体が壊れている場合は、次の 3 行 Python で代替:

```bash
python3 -c "import hashlib,json,sys; d=json.load(open(sys.argv[1])); d.pop('rubric_hash',None); print('sha256:'+hashlib.sha256(json.dumps(d,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest())" creator-kit/skills/ref-skill-design-rubric/rubric.json
```

### Step 4: eval-log を 1 件手書きで作る

`eval-log/bootstrap-score.jsonl` に次の 1 行を追記する:

```json
{"timestamp":"<ISO8601>","release":"bootstrap","plugin":"core","skill_name":"my-first-skill","evaluator":"manual","rubric":{"rubric_id":"skill-design","rubric_version":"0.1.0-bootstrap","rubric_hash":"<上で計算したhash>"},"score":60,"passed":true,"threshold":60,"findings":[]}
```

これで eval-log のスキーマ正本（27章§3.1）と整合する 1 件目のレコードが入る。

### Step 5: 通常フローへ復帰

最小 Skill と最小 rubric が揃ったら、`/run-skill-create` を起動して通常フローで `run-build-skill` 自身を再生成する。bootstrap 完了の判定は `creator-kit/scripts/lint-rubric-violation.py` の `bootstrap` フィールドが `false` になること（既定 20 件到達）。

## 自己再生成テスト（ドリフト検知）

通常運用に復帰したあと、定期的に `run-build-skill` 自身を再生成して差分が閾値以内であることを確認する。これは creator-kit が自己ホスティング可能であることの継続的な保証になる。

```bash
python3 creator-kit/_bootstrap/test-self-regenerate.py \
  --target creator-kit/skills/run-build-skill \
  --max-diff-lines 50
```

差分が `--max-diff-lines` を超えた場合は kit のドリフトとして調査対象になる。

## 哲学

bootstrap 手順を「いつでも復元できる安全弁」として用意することで、creator-kit の自動化レイヤを攻めた設計に保てる。Self-hosting compiler と同じ思想であり、コンパイラが自分自身をコンパイルできる状態（completeness）を bootstrap マニュアルで担保する。
