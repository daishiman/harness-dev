---
name: run-ubm-challenge
description: 挑戦宣言と企画を作りたいとき、目的・目標・挑戦・リスク回避5理由・行うこと5つ・定期報告を北原さんのナレッジを使った引き出し型の対話で言語化し提出用テキストに仕上げたいときに使う。
disable-model-invocation: false
user-invocable: true
argument-hint: "[挑戦の仮タイトル]"
arguments: [title]
allowed-tools:
  - Read
  - Write
  - Bash
  - Glob
  - Grep
  - Task
  - AskUserQuestion
kind: run
prefix: run
effect: external-mutation
external_mutation_guard: {runtime_ref: "plugin:skill-governance-adapters/scripts/build-external-mutation-guard.py", flow: "preview-confirm-authorize-execute-v1"}
owner: harness-maintainers
since: 2026-10-08
version: 0.1.0
trigger_conditions:
  - 挑戦宣言
  - 挑戦宣言と企画
  - ubm-challenge
responsibility_refs:
  - references/question-map.md
  - references/handoff-format.md
  - ../../references/goal-seek-anchor-contract.md
  - ../../references/agent-root-contract.md
  - ../../agents/challenge-advisor.md
  - scripts/validate-challenge-output.py
subagent_refs:
  - challenge-advisor
schema_refs:
  - references/challenge-format.md
knowledge_loop:
  pattern: router-registry
  index: ../../knowledge/router.json
  consult_at: [runtime]
script_refs:
  - ../../scripts/evaluate-design-rubric.py
  - ../../scripts/search-knowledge.py
  - ../../scripts/record-knowledge-usage.py
  - ../../scripts/publish-staged-files.py
  - scripts/validate-challenge-output.py
  - ../../scripts/validate-inline-goal-seek-anchor.py
domain: ubm-goal-setting
rubric_refs:
  - ../run-ubm-knowledge-sync/references/rubric.json
reference_refs:
  - ../../references/content-review-rubric.md
  - ../../references/knowledge-retrieval-contract.md
  - ../../references/guarded-publication-contract.md
  - ../../references/action-language-policy.json
  - references/challenge-format.md
  - references/question-map.md
  - ../../agents/phase3-coordinator.md
combinators:
  - with-goal-seek
  - with-feedback-contract
goal_seek:
  activation_state: semantic_evaluator_started
  engine: inline
  fork: inline
  progress: eval-log/ubm-goal-setting/run-ubm-challenge/goal-seek-progress.json
  intermediate: eval-log/ubm-goal-setting/run-ubm-challenge/run-ubm-challenge-intermediate.jsonl
  handoff: eval-log/ubm-goal-setting/run-ubm-challenge/handoff-run-ubm-challenge.json
  max_loops: 3
source: 北原さんへ提出する「挑戦宣言と企画」フォーマット (2026-10-08 利用者提示) の仕組み化
source-tier: internal
last-audited: 2026-10-08
audit-trigger: quarterly
completeness_exempt:
  - "manifest: C0〜C7 の段階の遷移は SKILL.md の「全体の流れ」表、戻り先は question-map.md の戻りゲート表が正本。workflow-manifest.json を置くと段階の表と戻りゲートが二重定義になる。実行体の対応は responsibility_refs が持つ。書き込み許可の正本は hooks/ubm-write-path-guard.py の ALLOWED_PREFIXES / ALLOWED_EXACT。スキル固有の境界は本文 C6-C7 が持つ。"
feedback_contract:
  activation_state: semantic_evaluator_started
  max_iterations: 3
  criteria:
    - id: IN1
      loop_scope: inner
      text: validate-challenge-output.py が保存前の下書きと保存後のファイルの両方で、見出し6欄の順序・リスク回避5理由・挑戦の日付と規模・行うこと5項目と締め文・定期報告の頻度かタイミング・お金の理由・未置換プレースホルダを検査し違反0件であることを確認する。
      verify_by: script
    - id: IN2
      loop_scope: inner
      text: tests/test_validate_challenge_output.py が golden-sample の合格（PASS）、各違反コードの不合格（FAIL）、challenge-format.md と検査スクリプトの定数の文言一致を固定する。
      verify_by: test
    - id: OUT1
      loop_scope: outer
      text: run-skill-live-trial で実際の対話を C0 から C7 まで自走完遂し、各欄の確定文がユーザーの発話か要約確認への了承に由来し (AI が足した数字・日付・固有名詞がゼロ)、北原ナレッジの引用が ID 付きで、選んだ深さの上限（標準 1件・詳細 2件／field キーごと）以内に収まり、検査スクリプトが終了コード 0 を返すファイルが 05_Project/UBM/挑戦宣言/ に実生成されることを実行証拠で確認する。
      verify_by: live-trial
    - id: OUT2
      loop_scope: outer
      text: 提出前に利用者が提出用テキストを読み、自分の言葉ではない文・決めていない数字が無いことを確認する。
      verify_by: human
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

# run-ubm-challenge

北原さんへ提出する「挑戦宣言と企画」を、ユーザーの言葉だけで組み立てる。AI は聞き手（本スキルの親コンテキスト）と助言役（`challenge-advisor`。読み取り専用）の2役。
聞き手が欄の問いを聞き、ユーザーの答えを助言役に渡す。助言役は答えに紐づく北原ナレッジを探し、深掘りの問いか方向の助言を1つ返す。
聞き手はそれをユーザーに聞き、足りたら要約確認し、了承で欄を確定する。欄の値はユーザーが決め、AI は方向だけを示す。

## 目的と出力契約

**禁則**: 下書きの失敗を残したまま挑戦宣言を正式保存しない。総試行上限と承認済み保存範囲を守る。

- **ゴール**: `references/challenge-format.md` の骨格どおりの挑戦宣言1件が、全欄ユーザーの言葉で埋まり、
  `validate-challenge-output.py` が合格（PASS）し、ユーザーが提出用テキストを了承した状態。
- **出力契約**: `$UBM_VAULT_ROOT/05_Project/UBM/挑戦宣言/UBM - 挑戦宣言 - {declared_on}.md` 1ファイル
  （フロントマター＋提出用本文。正本: `challenge-format.md`）と、会話内に表示する提出用テキスト（フロントマターを除いた本文）。
- **境界**: 入力=対話回答 / 既存の期報・月報（読むだけ）/ ナレッジ（読むだけ）。出力=挑戦宣言1件のみ。
  週報・月報・期報の更新は `run-ubm-goal-setting`、ナレッジの更新は `run-ubm-knowledge-sync` へ委譲する。
- **選ぶ前の最小の実成果物**: 全欄が空の骨格の下書き（引数の仮タイトルは提示のときに添えるだけで、欄には入れない）を一時パスに作り提示する。
  現状で試す＝下書きだけで終わり vault に書かない / 軽微＝聞き手だけで進む（助言役・北原レンズなし）/
  標準＝C1 以降を聞き手と助言役の2役で進め、北原レンズは `field` キーごとに1件まで / 詳細＝標準と同じ流れで、北原レンズは `field` キーごとに2件まで。

<!-- runtime-root-contract:v1 -->
## 実行時のルートの決め方

- `runtime_root_policy: host-skill-path` を適用する。
- Claude Code では、プラグインのルートとして `CLAUDE_PLUGIN_ROOT` を使う。
- Codex では、ホストが示したこの `SKILL.md` の絶対パスから上の階層へたどり、プラグインの定義ファイル（`.codex-plugin/plugin.json` か `.claude-plugin/plugin.json`）を持つ最も近い祖先を、論理上の `PLUGIN_ROOT` とする。
- 作業ディレクトリ（`cwd`）からプラグインのルートを推測しない。置き換える前のプレースホルダをそのままシェルへ渡さない。シェルを呼ぶたびに、その中で解決済みの絶対パスを `PLUGIN_ROOT` に入れる。
<!-- /runtime-root-contract:v1 -->

## 選ぶ前の実成果物の作成

「目的と出力契約」の最小の実成果物を親コンテキストで作る。effect に応じた最低限の検査（読み込めて開けるか・秘密情報・取り消せない操作・壊れたファイル）だけを行い、現物のパス・ハッシュ値・開き方を見せたうえで、現状で試す／軽微／標準／詳細のどれにするかを記録する（記録する値は順に `accept-as-is`・`light`・`standard`・`detailed`）。現状で試すなら vault への書き込みを行わずに引き継ぎを完了とし、後続の節を実行しない。

## 選んだ深さでの改善の実行

以下の節「全体の流れ」「C0: 文脈解決」「C1-C5: 対話（聞き手と助言役）」「C6-C7: 組み立て・検証・保存」「ゴールシーク実行」と外部変更の安全手順は、軽微・標準・詳細のどれかが記録されて `semantic_evaluator_started` へ遷移したときだけ実行する。実際の外部変更は正規の `preview`→`hook-confirm`→`authorize`→`execute` の手順だけを通し、リリースと完全監査は別イベントとして明示されたときだけ行う。

<!-- external-mutation-guard-cli-ja:v1 -->
### 外部変更の受領書の手順（必須）

外部変更のコマンドを直接実行しない。山括弧のプレースホルダは、すべてこの実行で確かめた値に置き換える。
値が欠けていたり正しくなかったりすれば、中央の CLI が止める（fail-closed）。

`preview` の前に、ガードを持つプラグインのルートを1回だけ解決する。インストールされたプラグインからは、
隣のプラグインに `<プラグインのルート>/..` では届かないので、このパスを推測しない:

```bash
python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/extract-plugin-root.py" skill-governance-adapters
```

表示された絶対パスを、`preview`・`authorize`・`execute` の `<GUARD_PLUGIN_ROOT>` に使う
（確認を待つあいだはほかの Bash が止められるので、解決し直さない）。
解決のスクリプトが 0 以外で終わったら、外部変更をせずに止まり、`skill-governance-adapters` プラグインを入れるようユーザーに伝える。

```bash
python3 "<GUARD_PLUGIN_ROOT>/scripts/build-external-mutation-guard.py" preview --project-root "$PWD" --entrypoint-ref "plugin:<PLUGIN_NAME>/skills/<SKILL_NAME>/SKILL.md" --target-scope "<TARGET_SCOPE>" --diff-summary "<DIFF_SUMMARY>" --side-effect-summary "<SIDE_EFFECT_SUMMARY>" --command-json '<MUTATION_ARGV_JSON>'
```

この正規の `preview` の出力をユーザーに見せる。登録済みの `hook-confirm` を動かせるのは、`preview` が表示したとおりのユーザーの返答だけ。
そのあと、返ってきた2つの受領書のパスを使う:

```bash
python3 "<GUARD_PLUGIN_ROOT>/scripts/build-external-mutation-guard.py" authorize --project-root "$PWD" --preview-receipt "<PREVIEW_RECEIPT_PATH>" --confirmation-receipt "<CONFIRMATION_RECEIPT_PATH>"
python3 "<GUARD_PLUGIN_ROOT>/scripts/build-external-mutation-guard.py" execute --project-root "$PWD" --authorization-receipt "<AUTHORIZATION_RECEIPT_PATH>" --command-json '<MUTATION_ARGV_JSON>'
```

自動承認のフラグを使わない。この受領書の手順の外で外部変更のコマンドを実行しない。
<!-- /external-mutation-guard-cli-ja:v1 -->


### 正式保存の実行境界

`../../references/guarded-publication-contract.md` をReadして適用する。書き手のWriteは一時下書きだけとし、正式保存・archive移動・Daily更新・ナレッジ/台帳/グラフの更新は親がユーザー承認とcommand-bound受領書を揃えた中央guard `execute`だけで実行する。保存可否booleanだけで直接Write/Editしない。

`../../references/knowledge-retrieval-contract.md` をReadし、同契約の入力表に従って決定論の重み付き検索→候補の意味選択→親による実利用IDと取得済みユーザー反応の記録を実行する。検索結果を `knowledge_candidates` として担当役へ渡し、返された実使用を実際の出力と照合する。

## 全体の流れ

この表が段階の正本。戻り先は `references/question-map.md` の「戻りゲート」表、対話の原則と返し方は同じファイルの「原則」「返し方（phase3 との差分）」が正本。

| 段階 | 責務 | 実行体 |
|---|---|---|
| C0-resolve | 宣言日・保存先・同日ファイルの有無を確かめ、期報・月報の目的と目標を呼び水として読む | 本スキル |
| C1-purpose | 目的を引き出す | 本スキル + `challenge-advisor` |
| C2-goal | 数値目標を引き出す | 本スキル + `challenge-advisor` |
| C3-challenge | 挑戦の中身・規模（定員）・日付を引き出す | 本スキル + `challenge-advisor` |
| C4-risk | リスク回避5理由を引き出す（お金を最初に聞く。成立しなければ C3 へ戻る） | 本スキル + `challenge-advisor` |
| C5-actions-report | 行うこと5つと定期報告を引き出す | 本スキル + `challenge-advisor` |
| C6-compose-validate | 確定文を骨格へ組み、一時パスの下書きを検証し、提出用テキストを見せて了承を取る | 本スキル + 検査スクリプト |
| C7-save | vault へ保存し、保存後のファイルを再検証する | 本スキル + 検査スクリプト |

## C0: 文脈解決

- 最初に `UBM_VAULT_ROOT` が空でないかを `Bash` で確かめる。未設定なら先へ進まず、「つまずきやすい点」のとおりユーザーに vault のパスを確かめて設定してから再実行してもらう。
- 宣言日 `declared_on` は今日。保存先は `challenge-format.md`。
- `original_goal` は `挑戦宣言を作成する / 宣言日:{declared_on} / 仮タイトル:{引数の値、無ければ未指定}` という非空文字列としてC0で固定する。後のタイトル変更は `current_goal_snapshot` に記録し、固定値とハッシュを書き換えない。
- 同日のファイルが既にあれば、上書きか中止をユーザーに聞く（既存SHA256を固定し、上書きは正式保存の契約の中央guard executeで行う）。
- `05_Project/UBM/目標設定/` 直下を `UBM - 3-*.md`（期報）と `UBM - 2-*.md`（月報）で `Glob` し、命名の正本 `../run-ubm-goal-setting/references/output-formats.md` の旧名も受理する。`archive/` と `（提出）` の別ファイルは候補にしない。見出しの期間を確かめ、期報・月報ごとに期間の開始日が最新の1件を選び、目的・売上目標・成果目標だけを呼び水として読む。見つからなければ呼び水なしで進む。

## C1-C5: 対話（聞き手と助言役）

1. 聞き手は `question-map.md` の「原則」「返し方（phase3 との差分）」（返し方が指す `agents/phase3-coordinator.md` の2節を含む）を読み、
   その欄の「欄ごとの問い」の開く問いを聞く。
2. ユーザーが答えるたびに `challenge-advisor` を `Task` で呼ぶ（最大3回）。渡すものは助言役の「入力」節
   （`field`／`answers`／`confirmed`／`depth`／`lens_limit`／`plugin_root`／共通検索契約で親が先に取得した `knowledge_candidates`）。答えの履歴・確定文・`depth`・使ったレンズの数・方向を示したかはこのコンテキストが持ち、入力に当たるものを毎回渡し直す（回数とレンズの件数は `field` キーごと）。
   助言役が `{"error": "plugin_root が未指定"}` を返したら、解決済みの絶対パスを `plugin_root` に入れて1回だけ呼び直す（3回に数えない）。
   それでも `error` が返れば、以後は助言役を呼ばず、聞き手が 4 の合格条件で判定して進める。
3. `gate` が `null` でなければ 5 へ。`next.kind` が `deepen` か `direction` なら、その問いか助言を会話の流れに合わせて1つ聞く（方向は欄ごとに1回。示し済みの欄で `direction` が来たら `question-map.md` の「返し方（phase3 との差分）」の保留へ）。`lens` があれば原文1文と ID を添える（原文は変えず、言い換えるのは `bridge` と問いだけ）。
4. `next.kind` が `confirm` なら欄の要約確認を返し、了承で確定する。助言役を呼ばないとき（軽微／その欄で3回呼んだ後／
   要約確認の往復／ユーザーが完成した文を出したとき／2 の呼び直しでも `error` が返ったとき）は、聞き手が `challenge-format.md` の「各欄の合格条件」と `question-map.md` の「戻りゲート」表で判定する。
   足りていれば要約確認、足りなければその欄の「確かめる」から欠けている要素を1つ聞く（深掘りは2回まで）。
   使い切っても足りなければ、その欄でまだ方向を示していなければ切り口か判断軸2つを1回示し、それでも足りなければ `question-map.md` の「返し方（phase3 との差分）」の保留へ。
5. 戻りゲートに当たったら、影響する欄を確定前に戻したことをユーザーに伝えてから、戻り先の欄の問いへ移る。

## C6-C7: 組み立て・検証・保存

- 保留した欄があれば、`question-map.md` の「返し方（phase3 との差分）」のとおり組み立ての前に聞き直す。
- C6を初めて実行するとき、以下を `Bash` で一度だけ実行して実行専用の一時ディレクトリを作り、表示された絶対パスを `draft_path` として保持する。初回提示前の空の骨格にも同じ解決手順を使い、その実行ではパスを再利用する。

```bash
python3 -c 'import pathlib, sys, tempfile; print((pathlib.Path(tempfile.mkdtemp(prefix="ubm-challenge-")) / ("UBM - 挑戦宣言 - " + sys.argv[1] + ".md")).resolve())' "{declared_on}"
```

- 確定文を `challenge-format.md` の骨格へ並べ、観測した `draft_path` へ `Write` し、検証する。シェル変数を含む文字列を `Write` へ渡さず、同じ絶対パスを `--file` に渡す:

```bash
python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/skills/run-ubm-challenge/scripts/validate-challenge-output.py" \
  --file "{draft_path}"
```

- 終了コード1なら違反コードの欄へ戻って**ユーザーに聞き直す**（AI が文を補って合格させない）。2なら読込不能・引数不正なので内容を修正せず、その絶対パスと標準エラーを報告して停止する。
- 合格したら提出用テキスト（フロントマターを除く本文）をコードブロックで表示し、
  「この内容で保存して提出しますか」と聞く。この本文了承だけで保存せず、親が正式保存の契約でmanifestを作り、中央previewのユーザー確認・authorize・executeを経てvaultへ保存する。
- 保存後に同じ検査スクリプトを vault のパスで再実行し、終了コード0を完了条件とする。1または2なら保存先と結果を報告し、完了にせず自動再編集もしない。
- 書き込み保護: `ubm-write-path-guard` フックは、`UBM_VAULT_ROOT` 配下の許可範囲外への Write|Edit|MultiEdit を止め、検査するパスを判定できない呼び出しも、不明なら止める（fail-closed）の決まりに従って止める。
  許可範囲の正本はプラグイン直下 `hooks/ubm-write-path-guard.py` の `ALLOWED_PREFIXES` / `ALLOWED_EXACT`。
  本スキルが vault に書くのは `05_Project/UBM/挑戦宣言/` だけで、その境界はフックではなく本スキルの規則が守る（一時パスの下書きは vault の外なのでフックの検査対象外）。

## ゴールシーク実行

`goal_seek.engine: inline` / `fork: inline`。対話と保存可否は親コンテキストが持ち、助言役は読み取り専用の助言だけを返す。
1 周回の実体は「C6 の提出用テキストを見たユーザーが直したい欄を挙げたとき、その欄の対話へ戻って
確定し直し、C6 を再実行すること」。初回提示を含む総試行は最大3回（見直しは最大2回）。未達なら `references/handoff-format.md` に従って残件を記録し、完了扱いにしない。
検査スクリプトの不合格を欄へ戻して聞き直すのは周回に数えない（機械違反の修復であり、ゴールの見直しではない）。

### ゴールシーク配線

C0で固定した `original_goal` を進捗ファイル（`goal_seek.progress`）に記録し、C6の初回提示と各見直しを中間ファイル（`goal_seek.intermediate`）へ追記する。途中で保留・中止しても `references/handoff-format.md` の契約で引き継ぐ。
各行は `iteration/original_goal/current_goal_snapshot/delta_from_original/merged_directive_for_next/drift_signal` を持つ。

### ゴールシーク検証

アンカーの固定・必須キー・検査範囲・終了コードは `../../references/goal-seek-anchor-contract.md` が正本。

- C6初回提示を `iteration: 1` として追記し、再提示ごとに1増やす（最大3）。最初の提示で了承されても中間ファイルを空にしない。
- C7の保存後検査が0になった後、呼出元のプロジェクトルートから解決した進捗・中間ファイルへ以下を実行し、0を完了条件とする。

```bash
python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/validate-inline-goal-seek-anchor.py" \
  "{resolved_progress_path}" "{resolved_intermediate_path}"
```

## 守ること

- 出力の規則は `references/challenge-format.md`、対話の規則は `references/question-map.md` が正本。ここでは繰り返さない。

## つまずきやすい点

- **`UBM_VAULT_ROOT` 未設定**: 保存先が決まらず、フックも検査しない。C0 で確かめ、未設定ならユーザーに vault のパスを確かめて `UBM_VAULT_ROOT` を設定してから再実行してもらう。
- **リスク5理由の順序**: 対話ではお金を先に聞くが、出力はフォーマットの順（健康→信頼→家族→社内拠点→お金）。

## 関連資料

- `references/challenge-format.md`: 出力の正本（骨格・保存先・各欄の合格条件・違反コード）。
- `references/question-map.md`: 対話の正本（原則・返し方・欄ごとの問い・北原レンズ・戻りゲート・ナレッジ未収録）。
- `agents/phase3-coordinator.md`（プラグイン直下）: 回答パターン別の返し方と3ステップの正本（`question-map.md` の「返し方（phase3 との差分）」は差分だけを持つ）。
- `scripts/validate-challenge-output.py`: 保存前後の決定論検査（終了コード 0=合格 / 1=不合格 / 2=読込不能）。
- `examples/golden-sample.md`: 検査スクリプトに合格する見本（対話では使わない）。
- `agents/challenge-advisor.md`（プラグイン直下）: 答えに紐づく北原ナレッジから深掘りの問いか方向の助言を返す読み取り専用の助言役。
