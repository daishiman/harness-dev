# `session-record-format.md` — 相談セッション記録契約

`run-ubm-consult` の分岐、ユーザー主体性、保存同意、セッション分離を定める正本。逐語の文字起こしは保存せず、同意された最小要約だけを保存する。

## 分岐別の `outcome`

- `redirected_goal_setting`: `issue_statement` / `handoff_to=run-ubm-goal-setting` / `referral_confirmed` で完了。R2-R4 は要求しない。
- `redirected_challenge`: `issue_statement` / `handoff_to=run-ubm-challenge` / `referral_confirmed` で完了。R2-R4 は要求しない。
- `safety_redirect`: `risk_class` / `handoff_to` / `referral_message` で完了。通常コーチングを続行しない。
- `consult_completed`: `collaboration_mode`、ユーザー発話参照、提示フレーム、選択された `closure` を要求する。
- R1 の `outcome=consult_continue` は途中状態であり記録の `outcome` にはならない。R4 完了時に `consult_completed` へ写像する。
- 誘導系の `outcome`（`redirected_goal_setting` / `redirected_challenge` / `safety_redirect`）は既定非永続（会話内で完了）。収束の契約は要求しない。記録を希望された場合だけ保存同意を確認し、既に明示同意があれば聞き直さない。永続する場合は `outcome` に依らず `persistence_consent=true` と検査の通過が必須。安全分岐の支援を同意確認で遅らせない。

## 保存同意と置き場

- 既定は `persistence_consent=false`。保存同意は利用者が記録を希望したときだけ、保存内容・置き場・期限を説明して確認する。希望していない利用者へ保存の質問を足さない。
- 同意の有無に依らず検証用の記録を組み立てる。非永続の場合は `validate-consult-session.py --ephemeral`（保存同意の要求だけ免除）を終了コード0で通して会話内要約を返す。`sessions/` 配下へ書き込まず、検証用の一時ファイルと会話内の検証用記録を破棄する。
- 同意時だけ `eval-log/ubm-goal-setting/run-ubm-consult/sessions/<session_id>/handoff.json` を一時ファイルから原子的なリネームで作る。
- `eval-log` 配下のパスはリポジトリのルート起点で解決する（`cwd` 相対解決禁止）。
- `latest.json` は `{session_id, path}` のポインタだけを持ち、過去の記録を上書きしない。追記専用の `index.jsonl` へ `session_id/path/created_at/status` を追記する。
- `session_id` は衝突しない識別子、`created_at` は ISO 8601、`retention_until` は既定30日以内。期限後は削除対象。
- 保存期限切れの掃除: `validate-consult-session.py --gc <sessions root>` が `retention_until` 超過の記録と孤立セッションを走査する。試し実行が既定・`--apply` でのみ実削除し `index.jsonl` へ `status=deleted` 行を追記する。
- 引き継ぎファイルの無い `sessions/<id>/` は中断で孤立したセッションとして `--gc` の回収対象。R1 は開始時に孤立セッションを検出したら再開/破棄をユーザーへ1問確認してよい。
- `persistence_consent=true` のセッションではユーザー発話のターン ID＋要旨を `intermediate.jsonl` へ周回毎に追記する（コンテキストの圧縮の後で R4 の文字起こしを再構成するため）。
- vault へは書かない。個人名、連絡先、口座・健康・法的事件などの秘匿情報は `[REDACTED]` または抽象化要約にする。

## 検証と保存の順序

親は `tempfile.mkdtemp(prefix="ubm-consult-")` をBashで一度実行し、実行専用の一時ディレクトリの絶対パスを保持する。そこに検証用記録と、一般相談の場合は `role`・`id`・`content` を持つ発話記録をWriteする。シェル変数を含む文字列をWriteへ渡さず、観測した絶対パスを `--record`・`--transcript` に使う。

- 終了コード0なら、同意時は検証済み記録だけを上の置き場へ原子的に保存し、同意なしでは破棄する。誘導分岐は `--transcript` 不要。
- 1なら違反項目を修正・再検証し、反復上限に達したら完了にしない。2なら読込不能・引数不正なので内容を修正せず対象パスと検査出力を報告して停止する。
- 発話の逐語内容は検証だけに使い、保存する `intermediate.jsonl` はターンIDと秘匿情報を除いた要旨のみ。一時ファイルは検証後に削除する。検証未完了なら永続せず、残件は会話内で報告する。

## 収束の契約

`consult_completed` だけに適用する。ユーザーが選んだ締め方を `closure.type` に記録し、その列の項目だけを要求する。

| type | 必須キー | 提示と判断基準 |
|---|---|---|
| action | current / goal / gap / next_step | 現状→ゴール→ギャップ→次の一歩。次の一歩は誰に・何を・いつまで・何件の具体的行動にする |
| reflection | insight / not_deciding_yet / resume_when | 見えてきたこと→まだ決めないこと→再開条件。再開条件はいつ・何が起きたらの形。次の一歩を追加で要求しない |

値はユーザーの発話から構造化し、要約は本人に確認する。精神論や抽象的な次の一歩は具体化の問いへ戻す。停止・要約のみの要求を優先する。

## `consult_completed` のスキーマ

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

`closure` の必須項目は上の「収束の契約」を参照する。`collaboration_mode` は `question-led|framework-led|hypothesis-example|reflect-only`。具体例は `hypothesis-example` でユーザーが望んだ場合だけ、検討材料として提示する。

## 発話者の役割（`role`）と出典の契約

`user_solution.source_turn_ids` は実行時の文字起こしの `role=user` のターン ID だけを参照する。AI 発話内の「ユーザー:」という文字列は出所情報にならない。R4 完了前に、保存同意時は `validate-consult-session.py --record <handoff> --transcript <role付きJSON>`、`persistence_consent=false` 時は同じ入力へ `--ephemeral` を追加し、終了コード 0 で通す。

## 目標設定の利用側

`agents/info-collector.md` は `latest.json` を読み取り専用で解決し、同意済みの `consult_completed` だけを読む。不在、期限切れ、誘導/安全分岐の `outcome` は穏当に飛ばす。複数件を使う場合は `index.jsonl` から明示的に最新N件を選ぶ。
