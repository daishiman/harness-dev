# Prompt: R2-delegate

## メタ

| key | value |
|---|---|
| name | delegate |
| skill | assign-system-spec-completeness-evaluator |
| responsibility | R2-delegate (監査 sub-agent C07/C08/C06 を独立 context で fork し集約 → R1 へ渡す。C06 は matrix_coverage の sub-input。design_knowledge は R1 自前評価で auditor を立てない) |
| layers_covered | [L1, L2, L3, L4, L5, L6, L7] |
| output_schema | schemas/completeness-findings.schema.json (aspects 部) |
| reproducible | true (同一入力に対し同一の観点別 verdict 集合) |

## Layer 1: 基本定義層

### 1.1 不変ルール
- sub-agent担当観点は **独立 context (`isolation: fork`) で起動**し、foundation/decision/deep-knowledge/prompt品質は必要入力と機械gate結果をR1へ透過する。
- 監査は現行 `Agent` tool で対応 sub-agent (`system-spec-matrix-auditor` / `system-spec-hearing-auditor` / `system-spec-doc-freshness-auditor`) を起動して得る (`Task` は legacy 互換のみ)。R2 自身は監査ロジックを再実装しない (単一情報源 = 各 agent の SSOT prompt)。
- **正式 evaluator は 1 件ずつ foreground で直列実行する**: 現行 PostToolUse は matching tool call ごとに top-level `tool_use_id` と当該 call の response を受け取り、parallel dispatch 時も各 hook が並行発火する (batch 全体は PostToolBatch の責務)。ただし parallel 対応は defensive hardening / canary であり、正式 evaluator の parallel 許可ではない。current runtime の fresh live-trial で schema 1.2 の end-to-end 帰属を実証するまでは、1 回の assistant message に複数の Task/Agent tool call を並べず、1 件の完全な応答と最終行 `AUDIT_VERDICT` が返り PostToolUse 台帳行が確定したことを確認してから次の 1 件を起動する。
- **background launch は最終 response ではない**: background/非同期起動の「起動受理」だけの response は監査 verdict として扱わない。`verdict_state=pending|absent|ambiguous` または `audit_verdict=null` の台帳行を receipt に使うことを禁止する。
- **監査 fork に `name` を付けない**: `name` 付きで起動した Agent は `taskKind=in_process_teammate` になり、最終応答を返した後も session 終端まで生存するため **`SubagentStop` が発火しない**。completion 行 (schema 1.3) が永久に書かれず、dispatch 行が `pending` のまま残って帰属が接地しない。同時に payload の `agent_type` は `name` の値になり (`customAgentType` が本来の auditor 名を持つ) subagent_type 照合も外れる。監査 fork は `subagent_type` だけを指定して起動する。
- **非同期 fork には `AUDIT_DISPATCH: <token>` を発行する**: background/非同期で auditor を起動する場合、起動 prompt の先頭付近へ `AUDIT_DISPATCH: <token>` の 1 行を置く (`token` は `[A-Za-z0-9._-]{8,64}`・当該 session 内で一意・同じ token を 2 回使わない)。auditor 定義は同じ 1 行を応答本文へ 1 回だけ echo する契約を持ち、`hooks/record-audit-fork.py` は PostToolUse で dispatch 行 (schema 1.2)、SubagentStop で completion 行 (schema 1.3) を書き、この token だけを join key として両者を接合する。ハーネスは親の `tool_use_id` と子の `agent_id` を繋ぐ field を提供しないため、token を発行しない並列起動では帰属が一意に決まらず `verdict_state=pending` のまま fail-closed になる (単発の 1 対 1 起動に限り読取側が fallback で昇格する)。token は R2 が発行するだけで、台帳へは書かない (台帳の writer は hook のみ)。
- 監査 verdict (`PASS`/`FAIL`/`INDETERMINATE`) と軸別根拠をそのまま集約し、緑化のために書き換えない。
- **実際に fork した監査だけを receipt にする**: R2 は起動した各 fork を `audit_delegations[]` の receipt (`aspect`/`role`/`auditor`/`component`/`dispatch{tool,subagent_type,session_id,tool_use_id,response_sha256}`/`verdict`/`evidence`) として R1 へ渡す。`dispatch.tool` / `dispatch.session_id` / `dispatch.tool_use_id` は実際に hook が観測した値を、`dispatch.response_sha256` は当該 per-call `tool_response` **全体**の canonical digest をそのまま使う。ただし**非同期 fork の receipt では `dispatch.response_sha256` に completion 行 (schema 1.3) の digest を使う**。非同期起動の per-call `tool_response` は起動受理 payload であって監査結果を何も含まず、これを receipt の束縛先にすると「起動しただけ」が verdict の根拠になる。読取側は dispatch 行を completion 行で `resolved` へ昇格させ、昇格後の digest を照合対象にする。schema 1.2 台帳では ID・digest・`verdict_state=resolved`・生 verdict を全一致で照合し、ID 欠落/不一致を schema 1.1 扱いへ downgrade しない。schema 1.1 台帳は ID を持たない旧 `Task` 専用の legacy 互換であり、現行 `Agent` は必ず schema 1.2 + `tool_use_id` へ接地する。`verdict` は auditor 応答の最終行 `AUDIT_VERDICT: <PASS|FAIL|INDETERMINATE>` と同じ値にし、FAIL を PASS へ書き換えない。fork を省略した監査の receipt を書いてはならない。**台帳を書けるのは hook 層だけであり、PostToolUse が dispatch 行、SubagentStop が completion 行を append-only 追記する。R2 および監査 agent は台帳を作成・追記・補正してはならない。** `prompt_sha256` / `response_sha256` が空・`manual`・64桁16進数以外、schema 1.2 の `verdict_state` が resolved 以外、または `audit_verdict` が無効な台帳行は集約時に不正として除外される。receipt は hook 層が書く fork 台帳と `aggregate-completeness.py --report` で session・subagent・tool・ID・response digest・verdict の全てを突合され、裏取りできない帰属または判定は fail-closed で violation になる (帰属/緑化の Goodhart 防止)。評価 run 直後の検証では `--session <現在の session_id>` を併用する。

### 1.2 倫理ガード
- 監査結果の根拠を省略・要約し過ぎて FAIL 要因を隠さない。到達不能・入力欠落は INDETERMINATE として明示する。

## Layer 2: ドメイン層

### 2.1 責務
- 担当: sub-agent担当監査を独立contextでforkし、R1自前評価用のfoundation/decision/deep-knowledge/prompt evidenceと併せて渡す。
- 非担当: 総合判定 (R1)、監査ロジックそのもの (各 agent)、仕様書修正。

### 2.2 ドメインルール (観点↔評価主体)
- **matrix_coverage (primary C07 `system-spec-matrix-auditor` + sub-input C06 `system-spec-hearing-auditor`)**: C07 に `spec-state.json` を入力し、未収集セル放置 / 対象外理由妥当性 / 確定 qa_ref トレーサビリティ / 集約真理値表整合 / canonical platform 行全存在を監査させ、`validate-coverage-matrix.py` の両モード exit code を根拠に含める。C06 には同じ `spec-state.json` を入力し R6-audit-hearing の監査 5 軸 (聞き漏れ / 誘導質問 / 早期停止 / `state=確定` セルのトレーサビリティ / foundation 利用者根拠 (R6 の上位概念の遡及性)。軸の定義と数は `../../run-system-spec-elicit/prompts/R6-audit-hearing.md` が正本) で監査させ、重大度付きの検出を R6 Layer 6 の JSON 形で受け取る。確定セルと U1-U9 が誘導なく漏れなく引き出され Q&A と利用者一次入力に遡れることを **matrix_coverage の sub-input (網羅性・トレース補助根拠)** として併せる。C06 の JSON は書き換えずに R1 へ渡す (sub-input の判定は R1 が `aspect-criteria.md` 1a と `aggregate-completeness.py --hearing` で導く)。`decisions[]` の採択根拠は C05 `decision_guidance` の専有責務であり、C06 の起動 prompt に decisions の遡及監査を追加してはならない。caller が誤って要求しても C06 は担当外として合否へ含めない。
- **design_knowledge_reflection (独立 auditor なし・C05 R1-score 自前評価)**: 本観点に監査 sub-agent を立てない。C06 は仕様書 Markdown を読まず設計知識を監査できないため、design_knowledge へ束縛しない (虚偽対応の撤去)。R2 は `spec_docs` (`system-spec/` 配下の全 Markdown) を R1 へ渡し、R1-score が各章の設計知識ポインタ存在 (機械層) + 原則の具体適用 (意味層) を自前評価する (存在確認だけで PASS にしない = Goodhart 防止)。
- **doc_freshness (C08 `system-spec-doc-freshness-auditor`)**: `fetched-references.json` + target 一覧を入力に、形式層と内容鮮度層を監査させる。
- **R1 self-evaluated inputs**: `requirements_foundation`/`decisions[]`/deep knowledge validator結果/全prompt validator結果を改変せずR1へ渡し、foundation_trace/decision_guidance/design_knowledge_reflection/prompt_qualityを埋めさせる。
- 各監査は担当軸のみに限定し、他観点へ重複判定を出さない (agent 側 SSOT の非干渉ルールに従う)。C06 の出力は matrix_coverage の sub-input としてのみ使い、独立観点に昇格させない。

### 2.3 入力契約
| field | required | 説明 |
|---|---|---|
| spec_state | yes | `spec-state.json` (C07 の主入力 + C06 の hearing 監査入力) |
| fetched_refs | yes | `fetched-references.json` (C08 の主入力) |
| targets | yes | 取得対象 target 一覧 (C08 の欠落突合用、`spec-state.json` の `targets[]`) |
| spec_docs | yes | `system-spec/` 配下の全 Markdown (`Path.rglob("*.md")`)。R1-score の design_knowledge 自前評価へ透過する (監査 sub-agent へは渡さない。C06 は読めない) |

### 2.4 出力契約
- matrix/doc-freshnessの独立監査とC06 sub-inputを渡す。foundation/decision/design-knowledge/prompt-qualityは機械evidenceと入力をR1へ透過し、R1がrubric全aspectsを組み立てる。
- あわせて実 fork の receipt 3 件 (`matrix_coverage/primary`=C07 / `matrix_coverage/sub_input`=C06 / `doc_freshness/primary`=C08) を `audit_delegations[]` として R1 へ渡す。schema 1.2 台帳由来の receipt は hook 観測の `tool_use_id` を必須とする。C05 自前評価の 4 観点に `primary` receipt を付けてはならない (虚偽の独立性主張として機械層が拒否する)。
- C06 の Agent 結果 JSON は、無改変のまま評価出力先 (R1 の `output` の置き場。省略時 `eval-log/` 配下・仕様書ディレクトリ外) の固定名ファイル `hearing-audit.json` へ保存し (R1 の `output` が canonical の `system-spec/completeness-report.json` のときは、その隣ではなく `eval-log/` 配下に置く)、そのパスを R1 へ渡す (`aggregate-completeness.py --hearing` はファイルパスを取り、C06 は Read のみで自分では書けないため)。この skill の allowed-tools に Write は無く、`aggregate-completeness.py` にも保存のオプションは無いので、`Bash(python3 *)` の範囲で python3 に書かせる。`<評価出力先>` は解決済みの absolute path に置き換える。

  ```bash
  python3 -c 'import pathlib, sys; pathlib.Path("<評価出力先>/hearing-audit.json").parent.mkdir(parents=True, exist_ok=True); pathlib.Path("<評価出力先>/hearing-audit.json").write_text(sys.stdin.read(), encoding="utf-8")' <<'HEARING_JSON'
  <C06 の Agent 結果 JSON をそのまま>
  HEARING_JSON
  ```

  - 保存先は python のコードの中に literal で書く。`sys.argv` や変数で渡すと、plugin の hook (`guard-confirmed-chapter-overwrite.py`) が書込み先を特定できず、JSON の本文に `system-spec/` が出てくるだけで遮断する。
  - heredoc の区切りは引用符付き (`'HEARING_JSON'`) にし、本文の `$` や `` ` `` を shell に展開させない。
  - `cat >` や shell の `>` では書かない。python3 以外のコマンドになり、`Bash(python3 *)` の外に出る。
  - 応答末尾の `AUDIT_VERDICT:` 行と `AUDIT_DISPATCH:` の echo 行は JSON の外にある台帳束縛用の marker なので、保存するのは JSON 部分だけにする (JSON 部分は 1 文字も書き換えない)。receipt の `verdict` は marker 行の値を使う。

## Layer 3: インフラ層

### 3.1 参照リソース
| id | path |
|---|---|
| matrix_auditor | ../../../agents/system-spec-matrix-auditor.md |
| hearing_auditor | ../../../agents/system-spec-hearing-auditor.md |
| doc_freshness_auditor | ../../../agents/system-spec-doc-freshness-auditor.md |
| rubric | references/scoring-rubric.json |

### 3.2 ツール
- Agent (現行の 3 監査 sub-agent 独立 context fork) / Task (legacy 互換のみ) / Read / Bash(python3 *) (決定論ゲート回収と、2.4 の `hearing-audit.json` の保存)。Write はこの skill の allowed-tools に無い。PostToolUse は各 Task/Agent call 単位、PostToolBatch は batch 単位であり、R2 は両者を同一 payload 契約として扱わない。

## Layer 4: 共通ポリシー

### 4.1 失敗時
- 監査 sub-agent が INDETERMINATE を返す (入力欠落 / 破損 / 到達不能) → 当該観点を INDETERMINATE として R1 へ渡し、fail-closed で総合 FAIL に寄せる。

### 4.2 観測
- rubric全観点の入力/evidenceが揃うことを記録する。

### 4.3 セキュリティ
- 仕様書と監査対象は書き換えない (read-only)。書くのは 2.4 の C06 出力の保存だけ。各監査 sub-agent も read-only (書込・状態更新・再取得を行わない)。台帳 (`audit-fork-ledger.jsonl`) は hook 層だけが書く。

## Layer 5: エージェント層

### 5.1 担当 agent
- R2-delegate 自身は集約役。実監査は 3 つの fork sub-agent (C07 matrix / C08 doc-freshness / C06 hearing) が担う。design_knowledge_reflection は auditor を立てず R1-score が自前評価する。

### 5.2 ゴール定義
- **目的**: matrix_coverage (C07 + C06 sub-input) と doc_freshness (C08) を独立 context で監査させ、生成物に依存しない客観根拠を R1 の総合判定に供給する。design_knowledge は R1 の自前評価入力 (spec_docs) を渡す。
- **達成ゴール**: 独立監査と自前評価入力がR1へ渡り、全観点をfail-closed導出できる状態。

### 5.3 完了チェックリスト
- [ ] matrix_coverage にC07の独立verdictと根拠が存在する
- [ ] C06のヒアリング監査結果 (R6の監査5軸・重大度付きの検出・閉じた検出) がmatrix_coverageのsub-inputとして書き換えずに存在し、`hearing-audit.json` に保存され、独立観点には昇格していない
- [ ] doc_freshness にC08の独立verdictと根拠が存在する
- [ ] 実 fork した監査の receipt 3 件が `audit_delegations[]` として R1 へ渡り、fork していない監査の receipt を 1 件も含んでいない
- [ ] schema 1.2 台帳の receipt は `tool_use_id` / whole per-call response digest / `verdict_state=resolved` を同一 call として照合し、schema 1.1 は旧 `Task` の ID 無し legacy 経路だけで受理されている
- [ ] design_knowledge_reflectionの入力が`spec_docs`としてR1-scoreへ渡り、重複auditorが存在しない
- [ ] foundation/decision/deep-knowledge/prompt validator evidenceが欠落なくR1-scoreへ渡っている
- [ ] INDETERMINATE 観点を隠さず明示した

### 5.4 実行方式
- 固定手順を持たない。状況に応じて必要な独立監査を都度設計し、5.3 の全停止条件を満たす集約結果だけをR1へ返す。

## Layer 6: オーケストレーション

### 6.1 上位接続
- 呼び出し元: R1-score。fork 先: C07 (matrix) / C08 (doc-freshness) / C06 (hearing 品質 = matrix_coverage sub-input) の監査 sub-agent。design_knowledge_reflection は fork せず R1-score が自前評価する。

### 6.2 並列性・ハンドオフ
- 3 監査の context はそれぞれ独立だが、正式 evaluator の dispatch は fresh live-trial gate が閉じるまで **1 message = 1 foreground fork** で直列化する。前の fork の完全応答・`AUDIT_VERDICT`・hook 台帳行を回収するまで次を起動しない。parallel 対応コードや fixture PASS は defensive hardening / canary に留まり、この gate を解除しない。集約結果のみを R1 へ渡し、監査対象は書き換えない。

## Layer 7: 提示

### 7.1 提示形式
- 全観点の監査入力 + 根拠 (R1が最終レポートへ統合)。

### 7.2 言語
- 日本語 (JSON キー・状態 enum・path は原文)。

---

## 出力指示

現行 `Agent` tool で `system-spec-matrix-auditor` (C07) / `system-spec-doc-freshness-auditor` (C08) / `system-spec-hearing-auditor` (C06) をそれぞれ独立 context (fork) で起動する (`Task` は legacy 互換のみ)。現行 PostToolUse は per-call だが、fresh live-trial gate が未完了の正式 evaluator では 1 回の message で複数を同時起動せず、**1 件ずつ foreground で完全応答と `AUDIT_VERDICT` を受け取ってから次へ進む**。background/非同期 launch の受理応答は最終 verdict ではなく receipt に使わない。C07 を matrix_coverage の一次根拠、C08 を doc_freshness の一次根拠とし、C06 のヒアリング監査 (R6 の監査 5 軸・重大度付きの検出) は matrix_coverage の sub-input として併せる (独立観点に昇格させない。判定への対応は `aspect-criteria.md` 1a)。C06 のトレーサビリティ対象は `state=確定` セルと U1-U9 で、`decisions[]` は起動 prompt に含めず C05 `decision_guidance` へ渡す。**design_knowledge_reflection には監査 sub-agent を立てず** (C06 は仕様書 Markdown を読めない)、`spec_docs` を R1-score へ渡して自前評価に委ねる。監査ロジックは各 agent の SSOT に委ね、R2 は結果を書き換えず集約するだけにする。INDETERMINATE は隠さず明示し、集約結果を R1-score へ渡す。余計な前置きは禁止。
