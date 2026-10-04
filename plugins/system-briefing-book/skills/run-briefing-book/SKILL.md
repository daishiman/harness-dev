---
name: run-briefing-book
description: 検査を通した文書とボード PNG を目次つきの 1 ファイル HTML にまとめたいとき、版の一致と古い PNG や外部参照の有無を確かめてから渡したいときに使う。
kind: run
effect: local-artifact
prefix: run
hierarchy: L2
version: 0.1.0
goal_seek:
  engine: inline
  fork: inline
owner: harness maintainers
source: plugins/system-briefing-book/plugin-composition.yaml#skills/run-briefing-book
user-invocable: true
disable-model-invocation: false
output_language: ja
argument-hint: "<資料フォルダ> [--allow-stale]"
allowed-tools: [Read, Bash, Glob]
context: inherit
manifest: workflow-manifest.json
schema_refs:
  - ../../schemas/briefing.schema.json
reference_refs:
  - ../../references/design-contract.md
  - ../../references/workflow.md
  - ../../references/execution-contract.md
script_refs:
  - ../../scripts/build-briefing-book.mjs
combinators:
  - with-feedback-contract
feedback_contract: # per-skill 評価基準(SSOT=plugins/harness-creator/scripts/feedback_contract_ssot.py)
  activation_state: semantic_evaluator_started
  max_iterations: 2
  criteria:
    - id: IN1
      loop_scope: inner
      text: "build-briefing-book.mjs が --allow-stale なしで exit0 し、_check/book.json の版が 要件定義.md の「版:」と一致し、古い PNG と外部参照がともに 0 件になっている"
      verify_by: script
    - id: IN2
      loop_scope: inner
      text: "_check/book.json に out・version と summary の pages・stale・external がそろい、out が 資料フォルダの直下の <タイトル>_打ち合わせ資料.html を指している"
      verify_by: script
    - id: OUT1
      loop_scope: outer
      text: "まとめ HTML を JavaScript を切ったブラウザで開いても 表紙→変更点→ボード→要件定義書→仕様書 の順に全ページを読め、目次と前へ次へと拡大が使えることを確かめる"
      verify_by: live-trial
    - id: OUT2
      loop_scope: outer
      text: "まとめ HTML を 1 ファイルだけ受け取った読み手が、ほかのファイルを開かずに できること・しくみ・決めること を読み取れることを、お手本の案件で実際に読ませて確かめる"
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


# まとめ HTML

## Runtime root contract

実行場所は [execution-contract.md](../../references/execution-contract.md) の「1. どちらのホストでも同じ呼び方」を正本とし、要点は次のとおり。

- `runtime_root_policy: host-skill-path` を適用する。
- Claude Codeでは `CLAUDE_PLUGIN_ROOT` をplugin rootとして使用する。
- Codexではホストが提示したこの `SKILL.md` のabsolute pathから、plugin manifestを持つ祖先を上方探索して論理 `PLUGIN_ROOT` を解決する。
- `cwd` からplugin rootを推測せず、literal placeholderをshellへ渡さない。各shell invocation内で解決済みabsolute pathを `PLUGIN_ROOT` に設定する。
- `prompts/` 配下はこのowner Skill契約を継承する。

## Purpose & Output Contract

資料フォルダの文書とボード PNG を、先方に渡す 1 ファイルの HTML にまとめる。配色の受け渡しと欠落時の扱いは [design-contract.md](../../references/design-contract.md) に従う。

- 先方に渡すのはこの 1 ファイルだけ。画像ははめ込み済みなので、素材フォルダやボードの PNG を一緒に送らなくてよい。ファイルや外部への参照が残ると LOCAL-REF・EXTERNAL-REF で止まり、書かない。
- 左の目次で選んだページが出る。前へ/次へ、拡大、印刷 (1 ボード 1 ページ横向き) に対応し、JavaScript が動かなくても全ページを縦に読める。
- 文書のページ (要件定義・仕様書・ヒアリング・変更点) は、カードや区切りを使ったレポートの形で描く。正本は Markdown のままで、変わるのはまとめ HTML の見た目だけ (validate と /build-app は Markdown を読む)。
- 書くファイルと中身の順は [build-briefing-book.mjs](../../scripts/build-briefing-book.mjs) の先頭の説明を読む。このスキルはスクリプトを呼ぶだけで、ほかのファイルを書かない。
- 確認の深さを選ぶのと独立レビューは、呼び出し元の run-briefing が持つ。単独で呼ばれたときは結果を見せて終わる。

## 手順

1. まとめる。

```bash
node "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/build-briefing-book.mjs" --dir "<資料フォルダ>"
```

2. 終了コードで分ける。コードの意味とすることは [execution-contract.md](../../references/execution-contract.md) の「3. 終了コード」を読む。このスキルで違うのは exit 1 だけ。自分では直さず、`_check/book.json` の errors を読み、下の表で直す担当を伝えて止まる。

| book.json の errors | 直す担当 |
| --- | --- |
| BRIEFING-JSON (briefing.json が読めない) | 壊れた鍵を書いた担当。pages は run-briefing-boards、palette と data_policy は run-briefing ([workflow.md](../../references/workflow.md) の「出力フォルダ」にある書いてよいスキルの表) |
| TOKENS-MISSING、TOKENS-INVALID | run-briefing (`palette` を確かめて init を `--refresh-css` で回し直し、`tokens.css` を作り直す。そのあと run-briefing-boards の「3. PNG にして検査する」から通し直す。[design-contract.md](../../references/design-contract.md)) |
| TEMPLATE-PLACEHOLDER (まとめの雛形が壊れている) | 直さずに plugin の入れ直しを伝えて止まる |
| VERSION-MISMATCH (版が 要件定義.md と 仕様書.md でずれている)、VERSION-MISSING (「版:」の行が無い) | run-briefing-docs (version-up) |
| DOC-MISSING (要件定義.md か 仕様書.md が無い) | run-briefing-docs |
| DOC-MISSING (book.include_hearing が true なのに ヒアリング.md が無い) | run-briefing-hearing |
| PAGES-EMPTY、PAGE-FORMAT、BOARD-MISSING | run-briefing-boards (pages とボード HTML をそろえる) |
| STALE-PNG、PNG-MISSING、PNG-READ、PNG-SIZE、PNG-HASH、BOARD-CHECK-NG | run-briefing-boards (`--only` で該当ボードの render を通し直す) |
| EXTERNAL-REF (http や // で始まる参照)、LOCAL-REF (ファイルへの参照) | file が `head` なら `_src/tokens.css` の参照で run-briefing-boards。ページの id (`bNN` など) なら、そのページの元を書いたスキル。どちらも参照を消すか data: にする |

`--allow-stale` は利用者が「古い PNG のままでよい」と言ったときだけ付ける。付けたら報告に必ず書く。

3. 報告する。

- まとめ HTML の場所 (先方に渡すのはこれ 1 つ)
- 版、ページ数 (ボードの枚数)、ファイルの大きさ
- 古い PNG と外部参照の結果 (どちらも 0 件のはず)
- ブラウザで開く方法。書き方は execution-contract.md の「ファイル名とパス」を読む (Windows は PowerShell とコマンドプロンプトで違う)

## Gotchas

- 先方にこの HTML を渡すのはよい。公開リンクを作るサービスや、関係のない外部のサービスへ上げない。素材の名前と数字をそのまま載せているか (briefing.json の `data_policy`) は、表紙の 1 文で分かる。
- まとめ HTML を直接書き換えない。直すのは元の文書かボードで、もう一度まとめる。
- 報告では、スクリプトが返した場所 (stdout の `out`) をそのまま使う。

## Additional Resources

- [workflow.md](../../references/workflow.md): 版の決まりと出力フォルダ
- [execution-contract.md](../../references/execution-contract.md): 終了コード、必要なツールの入れ方、まとめ HTML の開き方
