---
name: run-notion-intake-publish
description: intake 成果物を Notion へ初回公開したいとき、ヒアリングをやり直さず Notion 側だけ更新して再公開したいときに使う。
allowed-tools:
  - Read
  - Write
  - Bash
kind: run
disable-model-invocation: true
user-invocable: true
effect: external-mutation
source: plugins/skill-intake
source-tier: internal
last-audited: 2026-05-22
audit-trigger: monthly
hierarchy_level: L1
rubric_refs:
  - ../../references/quality-rubric.md
  - references/republish-contract.md
responsibility_refs:
  - references/republish-contract.md
  - references/abstraction-contract.md
schema_refs: []
manifest: references/resource-map.yaml
role_suffix: null
owner: team-platform
since: 2026-05-20
version: 0.1.0
feedback_contract: # per-skill 評価基準(SSOT=scripts/feedback_contract_ssot.py)
  max_iterations: 3
  criteria:
    - id: IN1
      loop_scope: inner
      text: 単一発火点が機構として守られ、本 skill の Steps が publish パイプとして intake_publish_pipeline.py のみを起動し render_notion_page.py / publish_notion_page.py を直接呼ばないこと(render/quality_gate/publish の重複実装も無いこと)を lint で機械検証できる。
      verify_by: lint
    - id: IN2
      loop_scope: inner
      text: 再公開が update 専用の冪等動作になり、--revise + page_id_consistency(notion-url.txt 期待値との一致検査)+ page_id 解決不能時の exit 51 により、同一 intake/manifest を複数回起動しても新規ページを量産せず既存 page_id を保ったまま更新されることを pipeline の exit code/quality_gate で機械検証できる。
      verify_by: script
    - id: OUT1
      loop_scope: outer
      text: スキル全体がユーザ目的(ヒアリングをやり直さず Notion 側だけを安全に再公開し、canonical=output/<hint> 修正→派生 view 更新のループを page_id 破壊なく回す)を最適に反映し、wrapper としての責務(precheck 4 種→単一発火点起動→exit code 伝搬、aggregator/fidelity-guard との境界、All-or-Nothing/Keychain/読み取り専用の各契約)が目的に対し過不足ないこと。
      verify_by: elegant-review
---

# run-notion-intake-publish

## Purpose & Output Contract

`run-skill-intake` が生成済みの `output/<hint>/` 一式を、ヒアリングを
やり直さず **Notion 側だけ** 公開 / 再公開するための薄い wrapper skill
(初回 publish も workflow-manifest P10 が本 skill へ委譲する)。
実体は `plugins/skill-intake/scripts/intake_publish_pipeline.py` (単一発火点) を
1 回呼ぶだけで、render / quality_gate / publish の重複実装は禁止する。

**起動形態 (disable-model-invocation wrapper 特性)**: 本 skill は
`disable-model-invocation: true` のため LLM 自律起動は不可。呼び出し元 (人間 or
上位 skill) が **Bash script 経由** で直接 dispatch する。LLM 判断面は持たないため
`prompts/` および `schemas/` は意図的に保持しない (R1 は pure script orchestration)。

- 入力: `<skill-name-hint> [--page-url <url>|--page-id <id>] [--database-id <db_id>]` (前提: `output/<hint>/intake.json` と
  `output/<hint>/notion-manifest.json` が既に存在)
- 出力: pipeline が `output/<hint>/` 配下に書き出す
  `notion-blocks.json` / `notion-publish-result.json` / `notion-url.txt` /
  `notion-log.json`
- 完了条件: pipeline exit 0 かつ `notion-url.txt` に有効 URL が書かれていること
  (exit 1=safe-skip / 2=hard-fail は `references/republish-contract.md` 参照)

## 既存スキルとの責務境界

| Skill / Script | 責務 | 本スキルとの境界 |
|---|---|---|
| `run-skill-intake` | ヒアリング・5 軸抽出・図解 | publish は初回含め workflow-manifest P10 が本 skill へ委譲。初回=intake.json `notion_target` 翻訳 / 再公開=`--revise` (Step 3 分岐) |
| `assign-notion-fidelity-evaluator` | 公開直前の構造粒度検証 | 本 skill は呼び出し元として fidelity-guard `verdict=pass` を前提 |
| `intake_publish_pipeline.py` | render → quality_gate → publish の単一発火点 | 本 skill は引数を整え 1 回呼ぶだけ |

## Key Rules

1. **単一発火点**: publish パイプは `intake_publish_pipeline.py` のみ。本 skill から
   `render_notion_page.py` / `publish_notion_page.py` を直接呼ばない。単一発火点の SSOT 定義は `../run-skill-intake/SKILL.md` 「単一発火点」項 (ゴールシークループ内) を参照。
2. **publish 専用**: ヒアリング・図解生成・JSON 整形はやらない (aggregator の責務)。
   初回 / 再公開の別は Step 3 の分岐 (成果物実在チェック) に従う。
3. **All-or-Nothing**: `verify_notion_assets.py` 通過必須。PNG 1 枚でも欠ければ停止。
4. **Secret-Out-of-Repo**: トークンは Keychain からのみ取得。環境変数・CLI 引数禁止。
5. **読み取り専用 (入力側)**: `intake.json` / `notion-manifest.json` を書き換えない。
6. **Progressive Disclosure**: 詳細ルールは `references/` に分割し、SKILL.md 本体は
   起動契約 (入出力 / Steps / ゴールシーク) に絞る。

## Responsibilities (1 layer / wrapper)

| ID | 名前 | スコープ | LLM responsibility |
|---|---|---|---|
| R1 | republish-dispatch | precheck 4 種 → `intake_publish_pipeline.py` 起動 → exit code を呼び出し元へ伝搬 | なし (pure script orchestration) |

wrapper skill のため `prompts/` は持たない。判断は全て script の exit code に従う。

## Steps

### Step 0: 引数正規化

```bash
HINT=""
PAGE_ID=""
PAGE_URL=""
DATABASE_ID=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --page-id) shift; PAGE_ID="${1:-}" ;;
    --page-url) shift; PAGE_URL="${1:-}" ;;
    --database-id) shift; DATABASE_ID="${1:-}" ;;
    --*) echo "unknown option: $1" >&2; exit 2 ;;
    *) if [ -z "$HINT" ]; then HINT="$1"; else echo "unexpected arg: $1" >&2; exit 2; fi ;;
  esac
  shift
done
test -n "$HINT" || { echo "skill-name-hint is required"; exit 2; }
```

### Step 1: precondition 検査

```bash
test -f "output/$HINT/intake.json"          || { echo "intake.json not found";          exit 2; }
test -f "output/$HINT/notion-manifest.json" || { echo "notion-manifest.json not found"; exit 2; }
```

### Step 2: 副作用前検査 (Keychain / Schema / Assets)

```bash
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-plugins/skill-intake}"
python3 "$PLUGIN_ROOT/scripts/validate-notion-ready.py" --check-api
python3 "$PLUGIN_ROOT/scripts/verify_notion_schema.py" --on-conflict skip-warn ${DATABASE_ID:+--database-id "$DATABASE_ID"}
python3 "$PLUGIN_ROOT/scripts/verify_notion_assets.py" "output/$HINT/notion-manifest.json"
```

いずれか exit !=0 ならその時点で停止。詳細な exit 規約は
`references/republish-contract.md`。
`validate-notion-ready.py --check-api` が PASS した場合、API キー / Notion トークンは確認済みとして扱い、ユーザーへ再入力を求めない。exit 44 のときだけ Keychain セットアップを案内する。

### Step 3: pipeline 起動 (唯一の publish 発火点)

```bash
# 再公開 (notion-url.txt / notion-publish-result.json 等が実在) は update 専用 --revise で
# create を禁止する (page_id 解決不能なら pipeline が exit 51。新規ページ量産を構造的に封鎖)。
# 初回 (上記いずれも不在) は --revise を付けず、pipeline が intake.json の notion_target
# (mode=create-explicit かつ allow_create=true) を読み --allow-create 相当へ翻訳する (P10 委譲)。
if [ -z "$PAGE_URL" ]; then
  PAGE_URL="$(cat "output/$HINT/notion-url.txt" 2>/dev/null || true)"
fi
MODE_ARGS=()
if [ -n "$PAGE_ID" ] || [ -n "$PAGE_URL" ] || [ -f "output/$HINT/notion-publish-result.json" ]; then
  MODE_ARGS+=(--revise)
fi
EXTRA_ARGS=()
[ -n "$DATABASE_ID" ] && EXTRA_ARGS+=(--database-id "$DATABASE_ID")
[ -n "$PAGE_ID" ] && EXTRA_ARGS+=(--page-id "$PAGE_ID")
[ -n "$PAGE_URL" ] && EXTRA_ARGS+=(--page-url "$PAGE_URL")
python3 "$PLUGIN_ROOT/scripts/intake_publish_pipeline.py" \
  --intake   "output/$HINT/intake.json" \
  --manifest "output/$HINT/notion-manifest.json" \
  "${MODE_ARGS[@]}" \
  "${EXTRA_ARGS[@]}"
```

pipeline 内部で render → quality_gate → publish を順 exec し、いずれか
exit !=0 で停止。トークンは `notion_http.py` が Keychain から都度取得 (環境変数渡し禁止)。
publish 前に `assign-notion-fidelity-evaluator/scripts/validate-notion-fidelity.py` を必ず実行し、`verdict=pass` 以外は Notion API mutation へ進まない。
再公開時は `--revise` により既存 `notion-publish-result.json` の page_id が期待値 (notion-url.txt) と
一致するか quality_gate で検査され (page_id_consistency)、別ページへの化け (orphan) を publish 前に FAIL させる。
初回は pipeline が intake.json の `notion_target` を読み取り、`mode=create-explicit` かつ
`allow_create=true` のときだけ create を許可する (それ以外は exit 51 で fail-closed)。

## Abstraction Variables (量産時の差し替え点)

| 変数 | 既定値 | 用途 |
|---|---|---|
| `sink_pipeline_script` | `plugins/skill-intake/scripts/intake_publish_pipeline.py` | 単一発火点 |
| `secret_keychain_label` | `notion-intake-token` | Keychain ラベル |
| `manifest_filename` | `notion-manifest.json` | sink 別アセット manifest |
| `on_schema_conflict` | `skip-warn` | スキーマ差分時挙動 ∈ {skip-warn,fail,auto-migrate} |

仕様は `references/abstraction-contract.md`。

## ゴールシーク実行

呼び出し元 (人間 or 上位 skill) が「再公開を完遂できたか」を自己判定するための
3 層プロトコル。本 skill は wrapper のため LLM の自由裁量は持たず、各層は
script exit code と成果物ファイル存在で機械判定する。

### Goal (達成すべきゴール)

`output/<hint>/notion-url.txt` に有効な Notion URL が書かれ、`notion-log.json` の
`status` が `published` で、対応する Notion ページが update mode で同一 `page_id`
を保ったまま最新 intake/manifest を反映していること。再公開は **冪等** であり、
同一 intake/manifest で複数回起動しても新規ページを増やさず既存ページを更新する。

### Why (なぜそのゴールか)

intake 成果物は canonical source として `output/<hint>/` 配下で管理され、Notion は
読み手向けの **派生 view**。view を作り直すたびに `page_id` を変えると外部参照
リンクが破壊されるため、再公開は常に「同一 page を update する」契約を採る。
これにより canonical 修正 → 再公開のループが安全に回り、ヒアリング工程を再消費
しない (aggregator 責務との重複排除)。

### Checklist (機械判定可能な完了条件)

| # | 検査 | 合格基準 |
|---|---|---|
| 1 | pipeline exit code | `intake_publish_pipeline.py` が exit 0 |
| 2 | URL ファイル | `output/<hint>/notion-url.txt` が非空かつ `https://www.notion.so/` で始まる |
| 3 | ログ status | `output/<hint>/notion-log.json` の `status == "published"` |
| 4 | page_id 不変 | `notion-publish-result.json.page_id` が前回値と一致 (初回除く) |
| 5 | precheck 全 pass | Keychain / schema / assets の 3 検査が全て exit 0 |
| 6 | 再公開拒否ルール非該当 | `references/republish-contract.md` の拒否条件全て非該当 |

いずれか不合格なら exit code (1=skip / 2=hard-fail) を呼び出し元へ伝搬し停止。

## Gotchas

1. **初回 publish も成果物確定後に**: 図解生成・JSON 整形は run-skill-intake (P1-P9) の
   責務で、publish は初回含め workflow-manifest P10 が本 skill へ委譲する。初回
   (notion-url.txt 等不在) は pipeline が intake.json の `notion_target` 翻訳で create を許可する。
2. **fidelity-guard を skip しない**: pipeline 内で fidelity-guard を必ず実行し、
   `verdict=pass` 以外は Notion API mutation へ進まない。
3. **トークンは Keychain のみ**: `.env` / CLI 引数 / shell history へ載せない。
   うっかり `NOTION_TOKEN=xxx python3 ...` と打つと監査で落ちる。
4. **silent-fail 禁止**: pipeline は失敗時も `notion-log.json` を書く。読まずに retry しない。
5. **初回 publish 失敗時の回復**: 失敗時は `notion-url.txt` を書かない (成功 URL 確定時のみ) ため、
   `notion-log.json` で原因を解消したのち同じコマンドを再実行すれば初回翻訳経路が自動回復する。

## Additional Resources (Progressive Disclosure)

| 用途 | パス | when_to_read |
|---|---|---|
| 入力前提と exit 規約 | `references/republish-contract.md` | 起動前の前提条件 / exit code を確認するとき |
| 量産差し替え点 | `references/abstraction-contract.md` | 別 sink (Confluence 等) に流用するとき |
| Notion API 正本 | `../../references/notion-integration.md` | Notion property 名 / 認可フローを確認するとき |
| Keychain セットアップ | `../../references/keychain-setup.md` | トークン登録手順を確認するとき |
| 読み順マップ | `references/resource-map.yaml` | references 全体の Progressive Disclosure 地図 |

## 関連スキル

- `run-skill-intake` — 上流工程 (workflow-manifest P10 で初回含む publish を本 skill へ委譲)
- `assign-notion-fidelity-evaluator` — 公開直前の構造粒度ガード (本 skill 起動前に pass 必須)
