# session-record-format.md — 相談セッション記録契約

`run-ubm-consult` の分岐、ユーザー主体性、保存同意、セッション分離を定める正本。逐語 transcript は保存せず、同意された最小要約だけを保存する。

## 分岐別 outcome

- `redirected_goal_setting`: `issue_statement` / `handoff_to=run-ubm-goal-setting` / `referral_confirmed` で完了。R2-R4 は要求しない。
- `safety_redirect`: `risk_class` / `handoff_to` / `referral_message` で完了。通常コーチングを続行しない。
- `consult_completed`: `collaboration_mode`、ユーザー発話参照、提示フレーム、選択された closure を要求する。
- R1 の `outcome=consult_continue` は途中状態であり record の outcome にはならない。R4 完了時に `consult_completed` へ写像する。
- redirect 系 outcome（`redirected_goal_setting` / `safety_redirect`）は既定非永続（会話内で完了）。record を永続する場合は outcome に依らず `persistence_consent=true` と validator 通過が必須。

## 保存同意と置き場

- 既定は `persistence_consent=false`。この場合はファイルを書かず会話内要約だけ返す。ただし record は組み立て、`validate-consult-session.py --ephemeral`（非永続前提の検証モード・consent 要求のみ免除で他検査は同一）を exit 0 で通し、通過後に破棄する（sessions/ 配下へ書き込まない）。
- 同意時だけ `eval-log/ubm-goal-setting/run-ubm-consult/sessions/<session_id>/handoff.json` を一時ファイルから atomic rename で作る。
- eval-log 配下のパスは repo root 起点で解決する（cwd 相対解決禁止）。
- `latest.json` は `{session_id, path}` のポインタだけを持ち、過去 record を上書きしない。append-only `index.jsonl` へ `session_id/path/created_at/status` を追記する。
- `session_id` は衝突しない識別子、`created_at` は ISO 8601、`retention_until` は既定30日以内。期限後は削除対象。
- retention 掃除: `validate-consult-session.py --gc <sessions root>` が `retention_until` 超過 record と orphan を走査する。dry-run 既定・`--apply` でのみ実削除し `index.jsonl` へ `status=deleted` 行を append する。
- handoff 無しの `sessions/<id>/` は中断 orphan として `--gc` の回収対象。R1 は開始時に orphan を検出したら再開/破棄をユーザーへ1問確認してよい。
- `persistence_consent=true` のセッションでは user 発話の turn id＋要旨を `intermediate.jsonl` へ周回毎 append する（compaction 後の R4 transcript 再構成用）。
- vault へは書かない。個人名、連絡先、口座・健康・法的事件などの秘匿情報は `[REDACTED]` または抽象化要約にする。

## consult_completed schema

```json
{
  "schema_version": "1.0",
  "outcome": "consult_completed",
  "session_id": "20260711T120000Z-a1b2c3",
  "created_at": "2026-07-11T12:00:00Z",
  "retention_until": "2026-08-10T12:00:00Z",
  "persistence_consent": true,
  "collaboration_mode": "framework-led",
  "issue_statement": "ユーザー確認済みの本質課題",
  "elicited": {"context": "必要な範囲", "constraints": [], "values": [], "prior_attempts": []},
  "frames_presented": [
    {"frame_id": "GF-01", "viewpoint": "適用の問い", "source_ids": ["PR-001"]}
  ],
  "user_solution": {
    "text": "ユーザー自身が選んだ考え方",
    "source_turn_ids": ["u-04"]
  },
  "closure": {
    "type": "action",
    "current": "現状",
    "goal": "望む状態",
    "gap": "差",
    "next_step": "ユーザーが選んだ次の一歩"
  },
  "consult_evidence": {
    "mode": "graph",
    "source_refs": ["knowledge-graph.json#nodes[id=PR-001]"],
    "zero_hit": false,
    "warnings": [],
    "graph_sha": "sha256:..."
  },
  "user_feedback": {"mode_fit": "yes", "ownership_confirmed": true, "next_time": ""},
  "stance_self_check": {"no_prescription": true, "user_verbalized": true},
  "open_issues": []
}
```

`closure.type=reflection` の場合は `insight` / `not_deciding_yet` / `resume_when` を必須とし、action fields は要求しない。`collaboration_mode` は `question-led|framework-led|hypothesis-example|reflect-only`。具体例は `hypothesis-example` でユーザーが望んだ場合だけ、検討材料として提示する。

## role/source 契約

`user_solution.source_turn_ids` は runtime transcript の `role=user` の turn id だけを参照する。AI 発話内の「ユーザー:」という文字列は provenance にならない。R4 完了前に、保存同意時は `validate-consult-session.py --record <handoff> --transcript <role付きJSON>`、`persistence_consent=false` 時は同じ入力へ `--ephemeral` を追加し、exit 0 で通す。

## 目標設定 consumer

`agents/info-collector.md` は `latest.json` を read-only で解決し、同意済み `consult_completed` だけを読む。不在、期限切れ、redirect/safety outcome は graceful skip。複数件を使う場合は `index.jsonl` から明示的に最新N件を選ぶ。
