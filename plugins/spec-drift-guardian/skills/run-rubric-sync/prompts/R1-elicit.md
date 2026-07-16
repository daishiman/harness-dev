# Prompt: R1-elicit

> このファイルは 7 層プロンプトの Markdown 表現。`run-prompt-creator-7layer` の
> seven-layer-markdown-template.md を提示形式の補助とする。Layer 番号と依存方向 (L1 ← L7) は不変。
> L5 サブ構造は seven-layer-format.md「Layer 5 契約」(l5-contract v2.0.0) に従属する。

## メタ

| key | value |
|---|---|
| name | elicit |
| skill | run-rubric-sync |
| responsibility | R1 (トリアージ入力の確定 → read-only 参照先の解決) |
| layers_covered | [L1, L2, L3, L4, L5, L6, L7] |
| output_schema | (中間) resolved-inputs (R2 への受け渡し。最終 emit は R2/R3) |
| reproducible | true (同 issue・同 artifact → 同 read-only 参照集合。未確定は最尤補完し open_questions に記録) |

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール
- **read-only**: 本責務は一切ファイルを書き換えない (Edit/Write を実行しない)。参照先の解決までが担当。
- artifact 起点は `$CLAUDE_PROJECT_DIR/.spec-drift/<issue>/`、plugin 資産は `$CLAUDE_PLUGIN_ROOT/` 起点 (repo-root 直書き禁止)。
- 入力の完全性を証明できないとき (triage-report が `complete≠true`) は proposal を作らず fail-closed。
- output_language=ja、パラメーター名/JSON キー/CLI 引数は英語のまま。

### 1.2 倫理ガード
- 秘匿情報・個人特定情報を artifact に格納しない。
- 対象パスを LLM の記憶から創作せず、triage-report と実ファイルの実在確認から解決する。

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (Single Responsibility)
- 担当: 対象 issue の確定、C01 `triage-report.json` と C03 `triage-verdict.json` の読取、影響あり (`impacted=true`) フィールドの抽出、対象 rubric/schema/template の**read-only 参照先パスの実在確認**、mode(propose/apply) の判定。
- 非担当: Edit 差分の組立 (R2)、apply-gate 検証と実適用 (R3)、独立監査 (C04)、独立再導出 (C03)。

### 2.2 ドメインルール
- triage-report は `complete==true` かつ `diff_sha256` を持つこと。false/欠落は fail-closed。
- triage-verdict は同 issue・同 `diff_sha256` を持ち、`agree` と `findings` を確認する。agree=false かつ未解消 findings があれば「上流未確定」として R2 へ進めない。
- `impacted=true` かつ `artifact_kind ∈ {rubric, schema, template}` の impact のみ同期候補。`other` と `impacted=false` は候補から除外し理由を記録。
- 候補 `artifact_path` は `references/apply-gate-policy.md` §1 の allowlist glob で分類し、**allowlist 外は「対象外パス」**として候補から外す (guardian が自 drift 源化するのを防ぐ)。
- mode 未指定時は既定 `propose`。`apply` 指定時も、後段 R3 が apply-gate 条件 (G1-G5) を検証するまで実ファイルは触らない。

### 2.3 入力契約
| field | type | required | 説明 |
|---|---|---|---|
| issue | integer | yes | 対象 GitHub issue 番号 |
| mode | string | no | propose(既定) / apply |
| triage-report | path | yes | `$CLAUDE_PROJECT_DIR/.spec-drift/<issue>/triage-report.json` |
| triage-verdict | path | yes | `$CLAUDE_PROJECT_DIR/.spec-drift/<issue>/triage-verdict.json` |
| allowlist policy | path | yes | `references/apply-gate-policy.md` §1 |

### 2.4 出力契約
- 中間成果 (R2 への受け渡し) として、解決済み入力集合を提示する: `issue` / `mode` / 影響あり impact のリスト (`artifact_kind`/`artifact_path`/`axis`/`before`/`after`/`evidence`) / allowlist 分類 (内/外) / 各 `artifact_path` の実在フラグ / 未確定を補完した `open_questions`。
- schema へ直接 emit しない (emit は R2 で sync-proposal.json)。R1 は「何を同期対象にするか」を確定するだけ。

## Layer 3: インフラ層 (外部依存)

### 3.1 参照リソース
| id | path | when_to_read |
|---|---|---|
| triage-report | `$CLAUDE_PROJECT_DIR/.spec-drift/<issue>/triage-report.json` | 影響抽出時 |
| triage-verdict | `$CLAUDE_PROJECT_DIR/.spec-drift/<issue>/triage-verdict.json` | agree/findings 確認時 |
| allowlist policy | `references/apply-gate-policy.md` | allowlist 分類時 |
| field-impact-map | `$CLAUDE_PLUGIN_ROOT/references/field-impact-map/field-impact-map.json` | target×axis 裏取り (R2 と共有) |
| target files | 各 impact の `artifact_path` | 実在確認 (Glob/Read) |

### 3.2 外部ツール / API
- Read / Glob / Grep (read-only)。
- `python3 $CLAUDE_PLUGIN_ROOT/scripts/map-field-impact.py` (任意: target×axis の独立再確認。R2 で必須)。

## Layer 4: 共通ポリシー層

### 4.1 失敗時挙動
- triage-report 欠落/`complete≠true`、triage-verdict 欠落/`diff_sha256` 不一致 → proposal を作らず停止 (exit 1 相当)、理由提示。
- ゴールシーク/差し戻し最大反復: 3 (SKILL.md feedback_contract max_iterations と同値)。

### 4.2 観測 / ロギング
- 解決結果と除外理由 (対象外パス/impacted=false/other) を提示。artifact への書込は R2 以降。

### 4.3 セキュリティ
- secret/PII を出力に含めない。read-only を厳守。

## Layer 5: エージェント層 (ゴール駆動の実行主体)

### 5.1 担当 agent
- run-rubric-sync 本体 (inline)。独立監査/再導出は C04/C03 へ委ね兼務しない。

### 5.2 ゴール定義
- 目的: 「何を同期対象にするか」を triage の事実に接地して確定し、R2 が再ヒアリングなしに最小 Edit 差分を組める状態を作る。
- 背景: 同期候補を LLM 記憶から創作すると allowlist 外や幻の影響を提案し fail-closed の意味が壊れる。triage-report/verdict を唯一の入力に固定して接地する。
- 達成ゴール: 影響あり impact が allowlist 内/外に分類され、内側候補の `artifact_path` 実在が確認され、mode が確定し、R2 へ渡す解決済み入力集合が提示されている。

### 5.3 完了チェックリスト (ゴール到達の停止条件)
- [ ] `issue` が確定し、triage-report/triage-verdict を読取済みである。
- [ ] triage-report が `complete==true` かつ `diff_sha256` を持つ (でなければ fail-closed 停止)。
- [ ] triage-verdict が同 issue・同 `diff_sha256` で、`agree` と未解消 `findings` の有無を確認済みである。
- [ ] `impacted=true` かつ `artifact_kind ∈ {rubric, schema, template}` の impact のみ候補に残している。
- [ ] 各候補 `artifact_path` を allowlist glob で内/外に分類し、外側を「対象外パス」として除外・理由記録している。
- [ ] allowlist 内候補の `artifact_path` が実在する (Glob/Read で確認)。
- [ ] mode(propose/apply) が確定している (未指定は propose)。
- [ ] 未確定事項を最尤補完し `open_questions` に記録している (人間差し戻しマーカーを残さない)。

### 5.4 実行方式
- 固定手順を持たない (l5-contract v2.0.0)。5.2/5.3 を唯一の指針に、現状評価 → 手順を都度立案 → 実行 → 検証 → 中間成果物アンカー記録 (original_goal 不変+delta+merged_directive+drift_signal) → 全項目充足まで反復 (6 ステップ・Step 5=Anchor。上限: Layer 4 最大反復)。
- 決定論操作 (Read/Glob・allowlist 照合・実在確認) は Layer 3 のツールに従う。意味判断 (どの impact を候補にするか) のみ LLM が担う。
- 不足情報はユーザーへ追加質問せず最尤補完し `open_questions` へ記録する。

## Layer 6: オーケストレーション層 (ゴールシーク制御)

### 6.1 上位 skill との接続
- 呼び出し元: run-rubric-sync (R1)。上位オーケストレーションは C06 slash-command `rubric-sync`。
- 後続 phase: R2-plan (解決済み入力集合を受領)。

### 6.2 ハンドオフ / 並列性
- 直列: R1 の解決済み入力を R2 の入力へ接続。
- goal-seek fork=subagent: 大規模 diff の影響再確認は Task で subagent へ委譲可 (親へは解決結果のみ返す)。

## Layer 7: UI / 提示層

### 7.1 ユーザー提示形式
- 解決済み入力集合 (候補一覧 + 除外理由 + open_questions) を Markdown で提示。

### 7.2 言語
- 本文: 日本語 (パラメーター名/JSON キーは英語のまま)。

---

## 出力指示

LLM は `$CLAUDE_PROJECT_DIR/.spec-drift/<issue>/triage-report.json` と `triage-verdict.json` を読み、影響あり (`impacted=true`) かつ `artifact_kind ∈ {rubric, schema, template}` の impact を抽出し、`references/apply-gate-policy.md` §1 の allowlist glob で内/外に分類し、内側候補の `artifact_path` 実在を確認し、mode を確定して R2 へ渡す解決済み入力集合を提示する。
`complete≠true` / triage-verdict 不一致 / agree=false かつ未解消 findings のときは proposal を作らず理由を提示して停止する。実ファイルは一切書き換えない。余計な前置き・思考過程出力は禁止。
