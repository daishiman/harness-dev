---
name: run-notion-gmail-sendlog-setup
description: Gmail個別送信の送信ログDBを仕様書schemaと照合したいとき、不足プロパティや選択肢を冪等に追加したいときに使う。
disable-model-invocation: true
user-invocable: true
argument-hint: "[--db-id <id>] [--apply] [--write-config] [--config <path>]"
arguments: [db_id]
allowed-tools:
  - Read
  - Write
  - Bash(python3 *)
kind: run
prefix: run
effect: external-mutation
owner: team-platform
since: 2026-06-24
version: 0.1.0
source: doc/run-notion-gmail-send-仕様と検証メモ.md
source-tier: internal
last-audited: 2026-06-24
audit-trigger: source-update
feedback_contract: # per-skill 評価基準(SSOT=scripts/feedback_contract_ssot.py)
  max_iterations: 3
  criteria:
    - id: IN1
      loop_scope: inner
      text: 送信ログDBの構築が §9 schema に対し冪等(additive-only)で、不足プロパティと select 選択肢のみを追加し既存プロパティ・既存データを破壊的に変更しないことを test_contract_sync で機械検証できる。
      verify_by: test
    - id: OUT1
      loop_scope: outer
      text: 「送信ログDBを仕様 schema と照合し不足分だけ安全に補う」というユーザー目的を満たし、--apply 適用前に追加差分を提示し send 系スキルが依存する冪等キー基盤を過不足なく用意する責務設計を run-elegant-review の4条件で確認する。
      verify_by: elegant-review
---

# run-notion-gmail-sendlog-setup

## Purpose & Output Contract

`run-notion-gmail-send` が**事前予約つき冪等ログ**を書き込む Notion 送信ログDBを、仕様書 §9 の schema 通りに整える。ユーザーが構築済みのDB (db_id は `--db-id` か config `databases.gmail-send-log.db_id` で解決) を入力に、現状プロパティを期待 schema と照合し、**不足プロパティと select 選択肢だけを冪等に追加**する。既存プロパティ・データは変更しない。これは送信フローの preflight **G2 (依存実体)** が解決可能になる前提づくりであり、ここが整わない限り live-send は中断する (§10/§13)。

- **入力**: `--db-id <id>` (省略時は `.notion-config.json` の `databases.gmail-send-log.db_id` から解決)。Notion API キーは Keychain `notion-api-key.<keychain-prefix>`。
- **出力**: 送信ログDBが §9 schema と整合し、dry-run 再実行で差分0になる。`--write-config` で db_id を config に焼き込む案内を提示。
- **完了条件**: 下記「完了チェックリスト」が全て YES。dry-run 差分が0かつ title 名が「冪等キー」。

## End-to-End Flow

決定論的本体は `scripts/setup-send-log-db.py` が担い、本スキルは差分の解釈・適用可否判断・config 反映の案内を担う (二層分離)。

1. **差分確認 (dry-run・既定)** — `--apply` 無しで現状と §9 期待 schema を照合し、不足プロパティ・型不一致・title rename 提案を表示する (副作用なし)。差分があれば exit 1。

   ```bash
   python3 "$CLAUDE_PLUGIN_ROOT/skills/run-notion-gmail-sendlog-setup/scripts/setup-send-log-db.py" \
     --db-id <送信ログDBのid>   # 省略時は config databases.gmail-send-log.db_id から解決
   ```

2. **適用 (apply)** — 差分を確認のうえ `--apply` を付け、`PATCH /databases` で不足プロパティ追加と title rename を実行する。型不一致は自動修正せず手動確認に差し戻す。

   ```bash
   python3 "$CLAUDE_PLUGIN_ROOT/skills/run-notion-gmail-sendlog-setup/scripts/setup-send-log-db.py" \
     --db-id <送信ログDBのid> --apply   # 省略時は config databases.gmail-send-log.db_id から解決
   ```

3. **config 焼き込み案内** — `--write-config` で `databases.gmail-send-log.db_id` の設定スニペットを提示する。`.notion-config.json` は作業フォルダ（`$CLAUDE_PROJECT_DIR` 直下・clone は repo-root）・gitignore 対象のため手動で追記する。

4. **再 dry-run** — 適用後に手順1を再実行し、差分0 (`✅ schema は期待と整合済み`) を確認する。

## ゴールシーク実行

### ゴール (Goal)
送信ログDB (`databases.gmail-send-log.db_id` で解決可能) が仕様書 §9 schema と完全整合し、dry-run 差分が0で、`run-notion-gmail-send` の冪等ログ書き込みが構造的に成立する状態。

### 目的・背景 (Why)
不可逆なメール送信を**二重送信させない**ためには、冪等キーで検索→reserved→sent/unknown を記録する送信ログDBが必須 (§2 三本柱の一つ)。送信ログDBの schema が欠けると preflight G2 が解決できず live-send は fail-closed で止まる (§10/§13)。本スキルはその依存実体を **db-setup として先行確定**し、送信フェーズが「DB ID 不在で詰む」ことなく「整わなければ送らない」を両立させる土台を作る。schema は `setup-send-log-db.py` 内 `EXPECTED` 定数が正本で、本スキルはそれとの差分を解消する。

### 完了チェックリスト (二値)
- [ ] 送信ログDB id が `--db-id` または config `databases.gmail-send-log.db_id` で解決できる
- [ ] 現状プロパティと §9 期待 schema を dry-run で照合し差分を表示した
- [ ] 不足プロパティ (campaign_id/plan_hash/content_hash/status/reason_code/本文page_id/宛先page_id/From/To/CC/件名/messageId/reserved_at/sending_at/sent_at/error) を `--apply` で追加した
- [ ] status の select 選択肢8値 (planned/reserved/sending/sent/skipped_idempotent/skipped_validation/error/unknown_needs_reconcile) が設定された
- [ ] reason_code の select 選択肢 (empty_body 等の機械可読理由) が設定された
- [ ] title プロパティ名が「冪等キー」になっている (rename 提案を適用済み)
- [ ] db_id を `.notion-config.json` に焼き込んだ、または `--write-config` の案内を提示した
- [ ] dry-run 再実行で差分0 (`✅ schema は期待と整合済み`) になった

### ゴールシークループ
1. db_id を `--db-id` か config から解決し、dry-run でDBの現状プロパティと期待 schema の差分を評価する。
2. 差分 (不足プロパティ / select 選択肢欠落 / title rename) があれば `--apply` で冪等に解消する。
3. 型不一致が出た場合は自動修正せず内訳を提示し、ユーザーの手動是正へ差し戻す (破壊的変更を避ける)。
4. db_id が未焼き込みなら `--write-config` の案内で `.notion-config.json` 追記を促す。
5. dry-run を再実行し差分0を確認する。チェックリストが全て YES なら完了。FAIL があれば 1 へ戻る。

### ゴールシーク配線
本スキルは初回1回の単発適用が主だが、型不一致是正 → 再適用 → 再 dry-run で多周回しうる。周回末に `eval-log/run-notion-gmail-sendlog-setup-intermediate.jsonl` へ `{iteration, original_goal, current_goal_snapshot, delta_from_original, merged_directive_for_next, drift_signal}` を1行追記する。`original_goal` は全周回で不変 (SHA-256 を `eval-log/run-notion-gmail-sendlog-setup-progress.json` の `original_goal_hash` に固定し毎周回照合)。次周回の手順生成は直前の `merged_directive_for_next` と `original_goal` を必須入力として読む (AI 単独再導出禁止)。1周で差分0なら本配線は no-op。

```bash
# 中間成果物アンカーの機械検査 (run-goal-seek/SKILL.md と同型 SSOT)
python3 - "$PWD/eval-log/run-notion-gmail-sendlog-setup-progress.json" "$PWD/eval-log/run-notion-gmail-sendlog-setup-intermediate.jsonl" <<'PY'
import json, os, sys, hashlib
prog_path, inter_path = sys.argv[1], sys.argv[2]
required_keys = {"iteration","original_goal","current_goal_snapshot","delta_from_original","merged_directive_for_next","drift_signal"}
if not os.path.exists(inter_path):
    print("intermediate.jsonl 未生成 (ループ未実行)"); sys.exit(0)
prog = json.load(open(prog_path, encoding="utf-8")) if os.path.exists(prog_path) else {}
lines = [l for l in open(inter_path, encoding="utf-8").read().splitlines() if l.strip()]
first = None
for i, line in enumerate(lines):
    e = json.loads(line)
    assert not (required_keys - e.keys()), f"intermediate[{i}] 必須キー不足"
    if i == 0:
        first = e["original_goal"]
        h = hashlib.sha256(first.encode()).hexdigest()
        assert prog.get("original_goal_hash") in (None, h), "original_goal_hash drift"
    assert e["original_goal"] == first, f"intermediate[{i}] anchor 不変性違反"
print(f"anchor OK: {len(lines)} 行 / 不変 / hash 一致")
PY
```

## Key Rules

1. **追加のみ・既存非破壊**: 不足プロパティと select 選択肢の追加だけを行い、既存プロパティ・データ・記入値は変更しない。再実行しても冪等。
2. **title は「冪等キー」**: 検索キー title が `冪等キー` でなければ rename を提案・適用する。冪等キーは `{本文page_id}:{宛先page_id}:{content_hash}` を格納する (§9)。`campaign_id` は含めず、意図的再送時だけ `--allow-resend` が suffix を付ける。
3. **型不一致は自動修正しない**: 期待型と現状型が食い違うプロパティは `--apply` でも変更せず、内訳を提示して手動是正へ差し戻す。
4. **schema 正本は1か所**: 期待プロパティ定義は `setup-send-log-db.py` 内 `EXPECTED` 定数のみ。status/reason_code の選択肢は `lib/idempotent_log.py` の enum 定数を参照する (二重定義を作らない)。
5. **db_id 解決順**: `--db-id` 明示 > config `databases.gmail-send-log.db_id`。両方無ければ exit 2 で停止し、db_id の指定を促す。

## Gotchas

1. **Notion integration 未接続**: 対象DBに integration が共有されていないと `404 object_not_found`。Notion MCP は未共有のため REST 直叩き (`notion-api-key.<keychain-prefix>`) を使う。
2. **`.notion-config.json` は gitignore 対象**: `--write-config` はスニペット提示のみで自動書き込みしない。作業フォルダ（`$CLAUDE_PROJECT_DIR` 直下・clone は repo-root）に手動追記する (秘匿値を git に乗せない)。
3. **select 選択肢は既存温存**: status/reason_code は既存選択肢に不足分を**マージ**追加する。既存の独自選択肢は消さない。
4. **dry-run の exit code**: 差分ありは exit 1 (整合済みは 0)。CI で「差分0」をゲートにする場合はこの戻り値を使う。
5. **このDBは送信フローの前提**: ここが整わないと `run-notion-gmail-send` の preflight G2 が fail-closed で送信を止める。送信前に本スキルで差分0にしておく。

## Additional Resources

- `scripts/setup-send-log-db.py` — schema 照合・不足追加・title rename・config 案内 (期待 schema の正本 `EXPECTED`)
- `../../lib/idempotent_log.py` — status/reason_code enum 定数と reserved→sent/unknown の冪等ログ本体
- `../../lib/notion_config.py` — `databases.gmail-send-log.db_id` 解決 (`.notion-config.json` ローダー)
- `../../lib/notion_client.py` — `update_database` (PATCH /databases) ほか Notion REST ラッパ
- `doc/run-notion-gmail-send-仕様と検証メモ.md` §9/§10/§13 — 送信ログDB schema・preflight gate・依存実体トレーサビリティ (実装 SSOT)
- `../ref-notion-gmail-send-spec/` — 送信フロー全体の参照仕様
