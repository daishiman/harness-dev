---
name: run-ubm-consult
description: 月間目標・目標設定以外も含む相談を構造化するとき、具体解の処方でなく考え方・思考フレームを引き出し型の共創で提示しユーザー主導で解決策を言語化したいときに使う。
disable-model-invocation: false
user-invocable: true
argument-hint: "[相談内容]"
arguments: [topic]
allowed-tools:
  - Read
  - Write
  - Edit
  - AskUserQuestion
  - Bash
  - Glob
  - Grep
  - Task
kind: run
prefix: run
effect: local-artifact
owner: harness-maintainers
since: 2026-07-11
version: 0.1.0
manifest: workflow-manifest.json
trigger_conditions:
  - 相談したい
  - 壁打ち
  - 考え方を教えて
  - ubm-consult
combinators:
  - with-goal-seek
  - with-feedback-contract
goal_seek:
  activation_state: semantic_evaluator_started
  engine: inline
  fork: inline
  progress: eval-log/ubm-goal-setting/run-ubm-consult/sessions/{{session_id}}/progress.json
  intermediate: eval-log/ubm-goal-setting/run-ubm-consult/sessions/{{session_id}}/intermediate.jsonl
  handoff: eval-log/ubm-goal-setting/run-ubm-consult/sessions/{{session_id}}/handoff.json
  max_loops: 5
responsibility_refs:
  - prompts/R1-intake-issue.md
  - prompts/R2-elicit.md
  - prompts/R3-frame-consult.md
  - prompts/R4-cocreate-converge.md
subagent_refs:
  - phase3-coordinator
schema_refs:
  - ../../knowledge/schema.json
knowledge_loop:
  pattern: router-registry
  index: ../../knowledge/router.json
  consult_at: [runtime]
script_refs:
  - ../../scripts/evaluate-design-rubric.py
  - ../../scripts/search-knowledge.py
  - ../../scripts/record-knowledge-usage.py
  - ../../scripts/consult-harness-artifact-graph.py
  - ../../scripts/validate-consult-session.py
  - ../../scripts/validate-inline-goal-seek-anchor.py
domain: ubm-goal-setting
rubric_refs:
  - ../run-ubm-knowledge-sync/references/rubric.json
reference_refs:
  - ../../references/content-review-rubric.md
  - ../../references/knowledge-retrieval-contract.md
  - references/consult-frames.md
  - references/session-record-format.md
  - references/resource-map.yaml
  - ../../references/goal-seek-anchor-contract.md
source: plugin-plans/ubm-goal-setting (改善計画 C09・user-request-consult-20260711) の設計
source-tier: internal
last-audited: 2026-07-11
audit-trigger: quarterly
feedback_contract:
  activation_state: semantic_evaluator_started
  max_iterations: 5
  criteria:
    - id: IN1
      loop_scope: inner
      text: テスト用の相談例で具体解を処方せず考え方/思考フレームを 1 件以上提示し、非処方スタンス不変条件(具体解押し付けゼロ)を自己検証する。
      verify_by: test
    - id: OUT1
      loop_scope: outer
      text: 相談セッションの対話の文字起こし（transcript）で考え方提示・引き出し質問・ユーザー自身の言葉での解決策言語化・ゴール指向の次の一歩（reflection の締め方では再開条件）の 4 要素を検出する。
      verify_by: test
    - id: OUT2
      loop_scope: outer
      text: 実際の相談を使った実地試行（live-trial）で、非処方スタンス不変条件(具体解押し付けゼロ・共同判断ターンで引き出し質問≥1・解決策の主語=ユーザー)を守ったまま R1→R4 を完走し、セッション記録を validate-consult-session.py (persistence_consent=false 時は --ephemeral) が終了コード 0 で機械検証する。
      verify_by: live-trial
artifact_delivery:
  contract: artifact-delivery-v1
  state_machine:
    initial: artifact_created
    states: [artifact_created, minimal_guard_passed, artifact_presented, user_choice_recorded, semantic_evaluator_started, handoff_complete]
    transitions:
      - {from: artifact_created, event: minimum_guard_pass, to: minimal_guard_passed}
      - {from: minimal_guard_passed, event: present_actual_artifact, to: artifact_presented}
      - {from: artifact_presented, event: record_user_choice, to: user_choice_recorded}
      - {from: user_choice_recorded, event: accept-as-is, to: handoff_complete}
      - {from: user_choice_recorded, event: "light|standard|detailed", to: semantic_evaluator_started}
      - {from: semantic_evaluator_started, event: improvement_complete, to: handoff_complete}
    pre_choice_forbidden: [semantic-evaluator, task-fork, subagent, multi-worker, revise-loop]
    accept_contexts: {evaluator: 0, improver: 0}
  release: explicit-only
  exhaustive: explicit-only
runtime_root_policy: host-skill-path
---

# run-ubm-consult

月間目標・目標設定以外も含む相談に、**具体解を処方せず「考え方（思考フレーム）」を提示するコーチング型の進行役**。引き出し質問でユーザーの文脈・制約・価値観を外在化し、解決策の言語化はユーザー主導とし、AI は構造化と検証を担う。目標設定以外の相談にもゴール指向の締めを適用し、締め方（行動化の `action` か、整理・内省の `reflection` か。記録では `closure.type` に残す）はユーザーが選ぶ。既存の機能 A（`run-ubm-goal-setting` Phase3 の対話原則「愛情ある厳しさ」・引き出し型）とナレッジ基盤（原則/マインドセット/事例）、C06/C07 の読み取り専用のグラフ参照を、非後退（既存に足すだけ）で再利用する。

## 目的と出力契約

**禁則**: 具体解を処方しない。安全分岐では論点確認を待たず支援を案内し、同意のない相談記録を永続保存しない。

- **ゴール**: 相談に対し考え方/思考フレームを選択肢として提示し、ユーザー自身の言葉で言語化された解決策と、ユーザーが選んだ収束の締め方（`references/session-record-format.md` の「収束の契約」）へ帰結した状態。`feedback_contract` の IN1（非処方スタンス）と OUT1 を満たす。OUT1 の4要素は、対話の文字起こし（話し手（`role`）付きの発話を並べた JSON で、`validate-consult-session.py --transcript` に渡す。下の相談セッション記録とは別物で、逐語のままは保存しない）から検出する。
- **出力契約**: 相談セッション記録（`outcome` の分岐・引き出したユーザー文脈/制約/価値観/既試行・提示した考え方/思考フレーム（選択肢＋適用視点・出典 ID 付き）・ユーザー自身の言葉で言語化した解決策・ユーザーが選んだ収束の締め方での締め（`references/session-record-format.md` の「収束の契約」））。**処方的な単一解は出力しない**。記録の形式と置き場は `references/session-record-format.md` が正本。
- **境界**: ナレッジグラフと harness の成果物グラフは、読み取り専用で参照する（C06/C07 経由・書き込みなし）。相談記録は `eval-log/` 配下の引き継ぎファイル（vault の外で、`ubm-write-path-guard` の対象外）へ書く。既存の機能 A（公式21ブロック）/ B（6カテゴリ）の契約を壊さない（非後退・既存に足すだけ）。**目標設定の生成は `run-ubm-goal-setting`、挑戦宣言の生成は `run-ubm-challenge` へ誘導する**。
- **正本**: 思考フレーム カタログ=`references/consult-frames.md`、セッション記録形式と置き場=`references/session-record-format.md`。

<!-- runtime-root-contract:v1 -->
## 実行時のルートの決め方

- `runtime_root_policy: host-skill-path` を適用する。
- Claude Code では、プラグインのルートとして `CLAUDE_PLUGIN_ROOT` を使う。
- Codex では、ホストが示したこの `SKILL.md` の絶対パスから上の階層へたどり、プラグインの定義ファイル（`.codex-plugin/plugin.json` か `.claude-plugin/plugin.json`）を持つ最も近い祖先を、論理上の `PLUGIN_ROOT` とする。
- 作業ディレクトリ（`cwd`）からプラグインのルートを推測しない。置き換える前のプレースホルダをそのままシェルへ渡さない。シェルを呼ぶたびに、その中で解決済みの絶対パスを `PLUGIN_ROOT` に入れる。
- `prompts/` の下のファイルも、このスキルの決まりに従う。
<!-- /runtime-root-contract:v1 -->

## 選ぶ前の実成果物の作成

「目的と出力契約」の最小の実成果物を親コンテキストで作る。effect に応じた最低限の検査（読み込めて開けるか・秘密情報・取り消せない操作・壊れたファイル）だけを行い、現物のパス・ハッシュ値・開き方を見せたうえで、現状で試す／軽微／標準／詳細のどれにするかを記録する（記録する値は順に `accept-as-is`・`light`・`standard`・`detailed`）。現状で試すならその場で引き継ぎを完了とし、後続の節を実行しない。

## 選んだ深さでの改善の実行

以下の既存の節（全体の流れ・ゴールシーク・評価・修正）は、軽微・標準・詳細のどれかが記録されて `semantic_evaluator_started` へ遷移したときだけ実行する。リリースと完全監査は別イベントとして明示されたときだけ行う。

`../../references/knowledge-retrieval-contract.md` をReadし、同契約の入力表に従って決定論の重み付き検索→候補の意味選択→親による実利用IDと取得済みユーザー反応の記録を実行する。検索結果を `knowledge_candidates` として担当役へ渡し、返された実使用を実際の出力と照合する。

## 全体の流れ

`workflow-manifest.json` が段階の機械可読な正本。責務は以下の 4 つのプロンプト（`prompts/R*.md`）が所有する。

| 段階 | 責務 | 実行体 |
|---|---|---|
| R1-intake-issue | 相談を受理し相談種別を判定・本質課題の言語化を支援する（具体解を出さない）。目標設定相談なら `run-ubm-goal-setting` へ誘導 | 本スキル（`prompts/R1-intake-issue.md`） |
| R2-elicit | 引き出し質問でユーザーの文脈・制約・価値観・既試行を外在化する | 本スキル（`prompts/R2-elicit.md`） |
| R3-frame-consult | 考え方/思考フレームを選定・提示する（`consult-harness-artifact-graph.py` + `router.json` デュアルパス + 既存ナレッジの原則/マインドセット/事例）。処方でなく選択肢＋適用視点 | 本スキル（`prompts/R3-frame-consult.md`）＋スクリプト |
| R4-cocreate-converge | 共創・収束。ユーザー自身の言葉で解決策を言語化させ、ユーザーが選んだ収束の締め方（`action` / `reflection`）で締め、保存同意に従って記録する | 本スキル（`prompts/R4-cocreate-converge.md`） |

## スタンス不変条件

本スキルの全ターンで不変。逸脱は `open_issues` に残し差し戻す。

1. **具体解の押し付けゼロ** — 提案は「考え方・視点・フレーム」＋適用のための問いに留める。「あなたは○○すべき」という単一の処方解を出さない。
2. **共同判断が残るターンで引き出し質問 ≥1** — 情報不足や選択が残るときは問いを最低1つ添える。ユーザーが停止・要約のみ・安全分岐・最終確認を求めたターンでは質問を強制しない。
3. **解決策の言語化はユーザーの発話から** — 解決策の主語は常にユーザー。AI は構造化・要約・検証のみを担い、ユーザーの言葉を先取りして代弁しない。
4. **収束方法はユーザーが選ぶ** — 項目と判断基準の正本は `references/session-record-format.md` の「収束の契約」。誘導・安全分岐へ一般相談の収束を要求しない。
5. **責務境界** — 目標設定は `run-ubm-goal-setting へ誘導`、挑戦宣言は `run-ubm-challenge へ誘導`。分岐別の完了条件は `references/session-record-format.md` の「分岐別の `outcome`」を参照する。

## ゴールシーク実行

固定手順を消化するのでなく、上記ゴールと `feedback_contract` を満たすまでユーザー向けの親コンテキストで反復する（`engine=inline` / `fork=inline` / `max_loops=5`）。サブエージェントは読み取り専用の検索や自己検証にだけ使い、ユーザーとの対話を隔離しない。

### ゴール

相談種別が特定され、ユーザー文脈が引き出しで外在化され、考え方/思考フレームが**選択肢＋適用視点**（出典付き）で提示され、ユーザー自身の言葉で解決策が言語化され、ユーザーが選んだ収束の締め方（`references/session-record-format.md` の「収束の契約」）へ帰結し、保存同意（`persistence_consent`）が `true` なら記録され、`false` なら非永続の検証の後に破棄された状態。

### 目的・背景

要望の本質は「具体例より考え方」を届け、解決策はユーザー側で作り上げる共創（コーチング型・非処方型）にある。決まった一問一答では相談種別の取り違え・引き出し不足・処方への逸脱が起きやすいため、非処方スタンス不変条件を都度自己検証しながら未達を埋める。ナレッジとグラフは読み取り専用で参照し、AI が答えを断定しない。

### 完了チェックリスト

- [ ] R1で相談種別と分岐が判定され、誘導分岐は `references/session-record-format.md` の分岐別契約を満たした。誘導・安全分岐ではR2-R4を要求しない。以下のR2-R4の項目は一般相談だけに適用する。
- [ ] `collaboration_mode` に必要な文脈だけが外在化され、停止・要約要求が尊重されている（R2）。
- [ ] 考え方/思考フレームがR3の数量契約（通常2件以上・`reflect-only`は1件以上）に従い、**選択肢＋適用視点**として出典 ID（`PR-xxx` / `MS-xxx` / 事例）付きで提示され、具体解の処方をしていない（R3・IN1）。
- [ ] ユーザー自身の言葉で解決策が言語化され、ユーザーが選んだ収束の締め方（`references/session-record-format.md` の「収束の契約」）へ帰結した。保存同意が `true` なら記録し、`false` なら非永続の検証の後に破棄した（R4・OUT1）。
- [ ] `persistence_consent=false` でも非永続の記録を組み立て、`validate-consult-session.py --ephemeral`（保存同意の要求だけを免除し、他の検査は同じ）を終了コード 0 で通し、通過後に破棄した（`sessions/` 配下へ書き込まない。一時検証ファイルは作業用の一時フォルダに置く）。

### ゴールシーク配線

正本 `../run-ubm-goal-setting` と同じく `goal_seek` 配線に従う。本スキル固有の差分:

- 保存に同意したときだけ、セッション ID（`session_id`）のディレクトリの下に進捗ファイル（`progress`）・中間ファイル（`intermediate`）・引き継ぎファイル（`handoff`）を書く。同意がないときは会話内の状態だけで進め、ファイルを作らない。完了時の記録は `references/session-record-format.md` に従い C11 で検証する。
- ループ本体はユーザーと対話する親コンテキストで実行する。サブエージェントを使う場合もナレッジ検索と非処方チェックだけを委譲し、質問と回答の往復は親が所有する。
- **内側ループ（IN1）**: 各周回で「具体解を処方していないか（スタンス不変条件1）」「考え方/フレームを1件以上提示したか」を自己検証し、逸脱を検出したら R3 を再実行する。
- **外側ループ（OUT1）**: 対話の文字起こしに考え方提示・引き出し質問・ユーザー自身の言葉での解決策言語化・ゴール指向の次の一歩（`reflection` の締め方では再開条件）の4要素が揃うまで反復し、受入テストで確認する。
- `max_loops` に達したときは合格（PASS）扱いにせず、残ったチェック項目を `open_issues` に残して人のレビューへ差し戻す。

### ゴールシーク検証

共通のアンカー契約は `../../references/goal-seek-anchor-contract.md` が正本。保存同意がtrueのときだけ、呼出元のプロジェクトルートと確定済みsession_idから進捗・中間ファイルの絶対パスを解決する。R4の記録検証の後に以下を実行し、終了コード0を完了条件とする。同意なしでは進捗も中間ファイルも永続せず、同じアンカー項目を会話内で保持・照合する。誘導分岐はR1で終わるため、R1の分岐別記録検証だけを行う。

```bash
python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/validate-inline-goal-seek-anchor.py" \
  "{resolved_progress_path}" "{resolved_intermediate_path}"
```

## 守ること

- **処方でなく考え方**: R3 は「あなたは○○すべき」でなく「こういう見方（フレーム）があります。あなたの場合はどう当てはまりますか？」の形で複数フレームを並べる。北原原則/マインドセットの引用は1対話あたり1〜2件までとし、必ず①原則を引き出す→②ユーザー状況に翻訳→③行動に落とす3ステップで届ける（`reflect-only` を選んだ相談や `reflection` の締め方で締める相談では、③で行動を迫らず再開条件を考えさせる問いにする。phase3-coordinator の CONST_004/CONST_006 に準拠）。
- **協働契約を最初に選ぶ**: R1 で `question-led`（問い中心）/ `framework-led`（考え方の説明中心）/ `hypothesis-example`（例を答えでなく検討材料として少量提示）/ `reflect-only`（整理だけ）の希望を確認する。AI がモードを一方的に決めない。
- **安全分岐を先に行う**: 自傷・他害・緊急危機は通常コーチングを止め、地域の緊急窓口や信頼できる人への即時連絡を優先する。医療・法律・金融など利害の大きい相談は一般的な考え方の整理に限定し、個別判断は有資格者へ委ねる。
- **保存は同意制**: 記録の希望があるときだけ保存内容・置き場・期限を説明して同意を確認する。既定falseで質問を追加しない。手順は `references/session-record-format.md` の「保存同意と置き場」「検証と保存の順序」に従う。
- **引き出しファースト**: 情報提供の前後どちらでも、共同判断が残るターンには引き出し質問を最低1つ置く（停止・要約のみ・安全分岐・最終確認のターンでは強制しない。スタンス不変条件 2）。深掘りは1項目につき2回まで（追い詰めない）。
- **解決策はユーザーの言葉で**: 収束時、解決策は必ずユーザーの発話を引用・構造化して確定する。AI が代わりに解を書き下さない。長文回答は「つまり○○ということですね？」と1文へ要約確認する。
- **ゴール指向の締め**: 一般相談はユーザーが選ぶ「収束の契約」に従う（正本は `references/session-record-format.md`）。誘導・安全分岐は同資料の分岐別契約で完了する。
- **読み取り専用の参照**: `consult-harness-artifact-graph.py`（C07）と `knowledge/*.json` は参照だけにする。起動条件と、使えないときの代わりの経路は `../../references/graph-consult-fallback-contract.md` が正本。

## つまずきやすい点

- **相談記録は vault へ書かない**: 相談記録の正本は `eval-log/` 配下の引き継ぎファイル（vault の外）に置き、vault へは一切書かない。この制約は本スキルの規則（`references/session-record-format.md`）が守るもので、`ubm-write-path-guard` には頼らない — このフックの許可範囲（正本はプラグイン直下の `hooks/ubm-write-path-guard.py` の `ALLOWED_PREFIXES` / `ALLOWED_EXACT`）は `05_Project/` 全体などを含み、vault への相談メモの混入を止めないためである。vault へ相談メモを残したいときはユーザー自身の操作に委ねる。
- **固定ファイルを直接上書きしない**: 保存同意時は `sessions/<session_id>/handoff.json` を原子的に作成し、`latest.json` は最新セッションへのポインタとして更新する。並行する相談を同じ進捗ファイル・中間ファイル・引き継ぎファイルへ混在させない。
- **グラフは運用時に生成する**: `knowledge/knowledge-graph.json`（C06）と `knowledge/harness-artifact-graph.json`（C05）は本ビルドでは作らない。そのため R3 はグラフがそろっている前提にしない（無いときの扱いは `../../references/graph-consult-fallback-contract.md` が正本）。
- **生成機能との棲み分け**: R1の分類で目標設定・挑戦宣言へ誘導する。outcomeと記録は分岐別契約に従う。
- **思考法の名前は出さない**: フレームは質問の形で自然に適用する（phase3-coordinator CONST_003）。カタログ ID（`GF-xxx`）は記録・出典管理用で、対話中に技法名を振りかざさない。
- **`goal_seek` のパスの `{{session_id}}` を文字どおりに書き込むのは禁止**: `session_id` が確定した後に、`inline` エンジンが展開する。テンプレートのまま `{{session_id}}` という名前のディレクトリを作らない。

## 関連資料

- **プロンプト**: `prompts/R{1..4}-*.md` — 責務単位の 7 層プロンプトの正本（`prompt-creator` プラグインの `skills/run-prompt-creator-7layer/scripts/verify-completeness.py` で 7 層と l5-contract を検証する。本プラグインには同梱しない）。
- **エージェント**: `phase3-coordinator`（対話原則「愛情ある厳しさ」引き出し型の前例。R3/R4 の翻訳3ステップと「品質基準（回答パターン別対応ルール）」の節を参照）。プラグイン直下の `agents/`。
- **スクリプト**: `../../scripts/consult-harness-artifact-graph.py`（C07・読み取り専用のグラフ参照）/ `../../scripts/validate-consult-session.py`（話し手（`role`）・出所（`source`）・同意・分岐を検証する R4 の完了ゲート）。C06 は C07 の入力を作る上流であり、本スキルから直接呼ばない。
- **参照資料**: `references/consult-frames.md`（思考フレーム カタログの正本）/ `references/session-record-format.md`（セッション記録の形式と置き場の契約）/ `references/resource-map.yaml`（必要な分だけ段階的に読むための索引）。
- **ナレッジ**: プラグイン直下の `knowledge/`（`router.json` → `*.json` をデュアルパスで検索。原則 `PR-xxx` / マインドセット `MS-xxx` / 事例を出典として引く）。
