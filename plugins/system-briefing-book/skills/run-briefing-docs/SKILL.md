---
name: run-briefing-docs
description: ヒアリング結果と素材から要件定義書を決まった章立てで書きたいとき、確認を終えた要件定義から画面ごとの項目と動きやしくみを仕様書へ落としたいときに使う。
kind: run
effect: local-artifact
prefix: run
hierarchy: L2
version: 0.1.0
goal_seek:
  engine: inline
  fork: inline
owner: harness maintainers
source: plugins/system-briefing-book/plugin-composition.yaml#skills/run-briefing-docs
user-invocable: true
disable-model-invocation: false
output_language: ja
argument-hint: "requirements|spec|version-up|answers <資料フォルダ> [新しい版] [変更の一覧] [Q と H の組]"
allowed-tools: [Read, Write, Edit, Bash, Glob, Grep]
context: inherit
manifest: workflow-manifest.json
schema_refs:
  - ../../schemas/briefing.schema.json
reference_refs:
  - references/writing-patterns.md
  - ../../references/document-structure.md
  - ../../references/quality-rules.md
  - ../../references/plain-language.md
  - ../../references/workflow.md
  - ../../references/execution-contract.md
script_refs:
  - ../../scripts/validate-briefing-docs.mjs
combinators:
  - with-feedback-contract
feedback_contract: # per-skill 評価基準(SSOT=plugins/harness-creator/scripts/feedback_contract_ssot.py)
  activation_state: semantic_evaluator_started
  max_iterations: 3
  criteria:
    - id: IN1
      loop_scope: inner
      text: "要件定義.md が 1〜9 章の見出しどおりで、3.1 と6章の最初の版の項目が対応し、できること が F01.. と S01.. の画面番号、決めること が Q01.. で振られ、validate-briefing-docs.mjs --stage requirements が exit0 する。件数の警告は必須の業務・安全・運用を保持して整理する判断材料として報告する"
      verify_by: script
    - id: IN2
      loop_scope: inner
      text: "仕様書.md の版が要件定義.md と一致し、要件定義の画面がすべて 1 章の画面一覧にあり、根拠列が空でなく、6 章 しくみと基盤 に 7 項目がそろって validate-briefing-docs.mjs --stage spec が exit0 し、_check/docs.json の warnings に PLATFORM-ITEM-MISSING と FUTURE-FIELD-MISSING が無い"
      verify_by: script
    - id: IN3
      loop_scope: inner
      text: "version-up のあと 要件定義.md と 仕様書.md の「版:」と「更新日:」が同じ値になり、validate-briefing-docs.mjs --stage spec が exit0 する"
      verify_by: script
    - id: OUT1
      loop_scope: outer
      text: "画面・表に出る名前・数字・列名がすべて素材か聞き取りに根拠を持ち、根拠のない値には「例」が付いていると briefing-reviewer の正確さ観点が素材と突き合わせて確認する"
      verify_by: evaluator
    - id: OUT2
      loop_scope: outer
      text: "実装する人が業務回答から仕様と画面へ1件追跡し、画面とデータを作り始める根拠、および未確定の案・元H・確認先Qを区別できることを実際に読ませて確かめる"
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

## Pre-choice usable artifact execution

[execution-contract.md](../../references/execution-contract.md) の「6. 通常生成と確認の選択所有」に従う。L1 が確認点の選択を所有し、L2 は通常生成と既存検査を選択前から実行する。

## Post-choice selected improvement execution

light / standard / detailed が記録されて `semantic_evaluator_started` へ進んだ確認点だけ、独立レビューとその指摘に基づく改善を行う。release / exhaustive は別の明示 event を要する。


# 要件定義書と仕様書

## Runtime root contract

実行場所は [execution-contract.md](../../references/execution-contract.md) の「1. どちらのホストでも同じ呼び方」を正本とし、要点は次のとおり。

- `runtime_root_policy: host-skill-path` を適用する。
- Claude Codeでは `CLAUDE_PLUGIN_ROOT` をplugin rootとして使用する。
- Codexではホストが提示したこの `SKILL.md` のabsolute pathから、plugin manifestを持つ祖先を上方探索して論理 `PLUGIN_ROOT` を解決する。
- `cwd` からplugin rootを推測せず、literal placeholderをshellへ渡さない。各shell invocation内で解決済みabsolute pathを `PLUGIN_ROOT` に設定する。
- `prompts/` 配下はこのowner Skill契約を継承する。

## Purpose & Output Contract

素材・要望・ヒアリング.md から、何をするか (要件定義.md) と どう動くか (仕様書.md) を決まった章立てで書く。

| モード | 書くもの | 通す検査 |
| --- | --- | --- |
| `requirements` | 要件定義.md | `--stage requirements` |
| `spec` | 仕様書.md (決めること が増えたら 要件定義.md の 9 章に Q を足す) | `--stage spec` |
| `version-up` | 両方の「版:」「更新日:」と、渡された変更 | `--stage spec` |
| `answers` (確認点で出た Q と H の組) | 要件定義.md と、書いてあれば 仕様書.md の該当の行 | 仕様書.md を直したら `--stage spec`、要件定義.md だけなら `--stage requirements` |

- 書いてよいのは 要件定義.md と 仕様書.md だけ。
- 見出しは [document-structure.md](../../references/document-structure.md) と 1 文字も変えない。/build-app などの実装スキルが同じ見出しで読む。
- 欄ごとの文の型・長さ・お手本・悪い例は [writing-patterns.md](references/writing-patterns.md)。番号 (S・F・D・R・Q) の振る順もそこにある。
- 確認の深さを選ぶのと独立レビューは、呼び出し元の run-briefing が持つ。単独で呼ばれたときは結果を見せて終わる。
- validate の exit 2 と exit 3 は、[execution-contract.md](../../references/execution-contract.md) の「3. 終了コード」を読み、そこに書かれたとおりにする。

## 書き方の決まり (両方に共通)

- 根拠のない名前・数字・列名には「例」を付ける。表の「根拠」列の値は document-structure.md の「根拠の書き方」を読む。
- 読めない素材 (手書きのかすれ) は「読めない」と書き、推測で埋めない。決めること に回す。
- 人は役割名 (配車の担当者、運転手) で書くのを基本にする。素材にある人と会社の名前、項目の初期値と例の値を素材のまま書いてよいかは、briefing.json の `data_policy` で決まる ([quality-rules.md](../../references/quality-rules.md) の「名前と値の扱い (data_policy)」)。
- 専門用語は [plain-language.md](../../references/plain-language.md) で言い換える。言い換えずに使う語は 要件定義.md の「## 8. 用語」に意味を書く。決まった見出しに出る語の行は雛形に入っているので消さない (plain-language.md の「決まった見出しに出る語」を読む)。
- 重複は共通の記入先への参照にまとめる。必須の業務・安全・運用の条件を件数だけで外さない。最初の版に要らない話は 決めること か 最初の版に入れないもの へ回す ([quality-rules.md](../../references/quality-rules.md) の シンプルさ)。ただし ヒアリング.md の `要望` の行は黙って外さない。6 章に `(要望:Hxx)` を付けて置き、`あとで` に回すなら 9 章で聞く (document-structure.md の「要件定義.md」の 6 章と 9 章の行)。
- 決めること が答えで閉じたら、document-structure.md の「要件定義.md」の表の 9. 決めること の行のとおりに閉じる。version-up と answers のどちらもこの決まりを使う。

- 業務回答から設計案への変換、網羅領域、元Hと確認先Qの追跡は document-structure.md の「業務回答から仕様へ変換する契約」と「実装へ渡す情報の記入先」を正本とする。質問は assets/data/hearing-catalog.json を参照し複製しない。

## requirements: 要件定義.md

1. ヒアリング.md、素材、要望、briefing.json を読む。
2. 雛形の 要件定義.md を章立てどおりに埋める。章ごとに書くことは document-structure.md の「要件定義.md」、文の型と数は writing-patterns.md の「要件定義.md」を読む。
   画面番号はここで決める。振る順は writing-patterns.md の「番号の振り方」を読む。画面が `docs.screens_warn` (assets/data/quality-thresholds.json) を超えそうなら、まず画面をまとめられないかを考える。外すかは確認点で利用者と決める ([workflow.md](../../references/workflow.md) の「既定のページ構成」)。
3. 検査する。

```bash
node "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/validate-briefing-docs.mjs" --dir "<資料フォルダ>" --stage requirements
```

exit 1 なら `_check/docs.json` の errors を見て直し、exit0 になるまで通し直す。warn は件数と中身を呼び出し元へ渡す。

## spec: 仕様書.md

1. 要件定義.md、ヒアリング.md、素材を読む。
2. 雛形の 仕様書.md を章立てどおりに埋める。「版:」と「更新日:」は要件定義.md と同じにする。章ごとに書くことと画面の書き方は document-structure.md の「仕様書.md」、文の型は writing-patterns.md の「仕様書.md」を読む。
   - 「ボード:」は [workflow.md](../../references/workflow.md) の「既定のページ構成」で番号を見込んで書く。確認点3 で番号が変わったら、呼び出し元から頼まれてこの行だけを書き直す。
   - 2・3章のUI詳細と4〜7章の実装詳細は、document-structure.md の「実装へ渡す情報の記入先」に従う。本文ラベルと既存表を埋め、ボードに出さない詳細も仕様書に残す。空ラベル・コメントでは記入済みとしない。
   - 6 章の行は ヒアリング 3 章の回答で埋める。未確認の方式は「案: <仮の内容> (Qxx)」と書き、元Hと確認先を9章のQへつなぐ。既定案を選んだ業務回答から推論した方式も、別に確認されていなければ案とする。理由は writing-patterns.md の「仕様書.md」の 6 章の型 (使う人の得) で書く。
   - 決めること が増えたら、同じ論点の既存Qを先に探して更新し、無ければ要件定義.md の9章に元Hを明記してQを足す。元Hの未定記録が不足する場合はhearing担当へ返す。ボードを組む途中で要る Q も、呼び出し元から頼まれてその Q だけを足す。
   - 8 章の候補は ヒアリング H06 の回答と、`あとで` に回した `要望` の機能から取る。
   - 4 章の `1 件 =` と型の単位、7.1 の 見える範囲 は、/build-app が読む欄。document-structure.md の「仕様書.md」の表のとおりに書く。
3. 検査する。

```bash
node "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/validate-briefing-docs.mjs" --dir "<資料フォルダ>" --stage spec
```

exit 1 なら `_check/docs.json` の errors を見て直し、exit0 になるまで通し直す。warn は件数と中身を呼び出し元へ渡す。

## answers: 確認点の答えで 決めること を閉じる

呼び出し元 (run-briefing の確認点) から、run-briefing-hearing の followup が返した Q と H の組 (例: `Q04=H17, Q01=H25`) を受け取る。版は上げず、「更新日:」も変えない (どちらも変わるのは version-up だけ)。

1. ヒアリング.md の その H の行と、要件定義.md の その Q の行を読む。
2. 組ごとに答えがQの論点を満たすか確認し、満たす行だけ「書き方の決まり (両方に共通)」のとおりに閉じる。業務条件だけ答えられ、同じQの方式が未決ならQを閉じず、案欄に決まった部分と未決部分を分ける。決定の版は要件定義.mdの今の版にする。
3. そのQを指していた本文を答えに合わせて直し、確認できた内容の根拠だけ `決めること:Qxx` から `聞き取り:Hxx` に書き換える。仕様書6章の方式に「案: 〜 (Qxx)」とあれば、その方式まで確認できた場合だけ答えの方式に書き換える。業務条件のみ決まった場合は未決の方式を案/Qで残す。答えが 案 と違うときは、その答えで変わる章も直す (直した章は 見せるもの に書く)。
4. 仕様書.md を直したら `--stage spec`、要件定義.md だけなら `--stage requirements` を exit0 まで通す。仕様書.md が雛形のまま (new の確認点1) なら、仕様書.md は直さない。file が 変更点.md の error は、version-up の手順 3 と同じく返して止まる。

## version-up: 版を上げる

呼び出し元 (run-briefing の revise) から 新しい版 と 変更の一覧 を受け取る。変更点.md を先に書いておく前提は、[run-briefing の SKILL.md](../run-briefing/SKILL.md) の「工程 (revise)」を読む。

1. 要件定義.md と 仕様書.md の「版:」を新しい版に、「更新日:」を今日に書き換える。版の正は要件定義.md の 2 行目で、仕様書はそれに合わせる。
2. 変更の一覧のうち、文書に関わるものを該当の章へ反映する。決めること が答えで閉じたら、「書き方の決まり (両方に共通)」のとおりに閉じる。決定 の版は新しい版にする。
3. `--stage spec` を通す。変更点.md は呼び出し元が書く。
   - file が 変更点.md の error はすべて、変更点.md を直さずに、そのコードと行を呼び出し元へ返して止まる。
   - それ以外の error は 要件定義.md か 仕様書.md を直し、exit0 まで通し直す。

## 見せるもの

- requirements: 要件定義.md の場所、最初の版でやること、できることの数、決めること の一覧、warn。
- spec: 仕様書.md の場所、画面一覧、しくみと基盤の表、最初の版に入れないもの、案と元H・確認先Q、warn。exit0と内容の網羅性は分けて報告する。
- requirements と spec のどちらも、この工程で増えた 決めること (Q 番号と 1 行) を必ず添える。呼び出し元はこれを run-briefing-hearing の followup に渡す。
- answers: 閉じた Q と、直した本文の場所。
- version-up: 反映した章と、増えた 決めること (Q 番号と 1 行)。

## Gotchas

- 件数の警告は重複と優先順位を見直す合図。認証・権限・保護・復旧や明示の要望を、数に収めるためだけに削らない。
- 言い切れない文は 決めること に回す。文の終え方は [quality-rules.md](../../references/quality-rules.md) の「3. 言葉」を読む。
- 画面名を文書ごとに変えない。ボードの h1 も同じ画面名を使う。

## Additional Resources

- [writing-patterns.md](references/writing-patterns.md): 欄ごとの文の型とお手本、悪い例と直した例、番号の振る順
- [document-structure.md](../../references/document-structure.md): 4 つの文書の章立てと表の列
- [quality-rules.md](../../references/quality-rules.md): 正確さ・言葉・シンプルさ
- [plain-language.md](../../references/plain-language.md): 言い換え表の使い方
- [workflow.md](../../references/workflow.md): 既定のページ構成と版の決まり
- [execution-contract.md](../../references/execution-contract.md): スクリプトの終了コード (exit 2・3)
