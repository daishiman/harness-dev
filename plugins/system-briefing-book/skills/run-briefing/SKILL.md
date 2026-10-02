---
name: run-briefing
description: 素材フォルダと要望から業務システムの打ち合わせ資料一式を同じ工程で作りたいとき、打ち合わせメモから変更点をまとめて影響する工程だけ直し版を上げたいときに使う。
kind: run
effect: local-artifact
prefix: run
hierarchy: L1
version: 0.1.0
goal_seek:
  activation_state: semantic_evaluator_started
  engine: inline
  fork: subagent
owner: harness maintainers
source: plugins/system-briefing-book/plugin-composition.yaml#skills/run-briefing
user-invocable: true
disable-model-invocation: false
output_language: ja
argument-hint: "new <素材フォルダ> [要望] | revise <資料フォルダ> <打ち合わせメモ>"
allowed-tools: [Read, Write, Edit, Bash, Glob, Grep, Skill, Task, AskUserQuestion]
context: inherit
manifest: workflow-manifest.json
responsibility_refs:
  - ../run-briefing-hearing/SKILL.md
  - ../run-briefing-docs/SKILL.md
  - ../run-briefing-boards/SKILL.md
  - ../run-briefing-book/SKILL.md
  - ../assign-briefing-evaluator/SKILL.md
schema_refs:
  - ../../schemas/briefing.schema.json
reference_refs:
  - ../../references/design-contract.md
  - ../../references/workflow.md
  - ../../references/quality-rules.md
  - ../../references/execution-contract.md
  - ../../references/document-structure.md
  - ../../references/case-haisha.md
script_refs:
  - ../../scripts/build-briefing-scaffold.mjs
  - ../../scripts/validate-briefing-docs.mjs
  - ../../scripts/compare-briefing-profile.mjs
combinators:
  - with-feedback-contract
feedback_contract: # per-skill 評価基準(SSOT=plugins/harness-creator/scripts/feedback_contract_ssot.py)
  activation_state: semantic_evaluator_started
  max_iterations: 3
  criteria:
    - id: IN1
      loop_scope: inner
      text: "new で工程0〜6 を順に進め、validate-briefing-docs.mjs --stage all が error 0 で exit0 し、まとめ HTML が <素材フォルダ>/打ち合わせ資料/ に 1 つだけできている"
      verify_by: script
    - id: IN2
      loop_scope: inner
      text: "確認点 3 か所 (要件定義書・仕様書・ページ構成) すべてで現物を見せてから accept-as-is/light/standard/detailed を聞き、選んだ値が _check/choices.json に 3 つそろい、light 以上を選んだ確認点だけ _check/review-<stage>.json が残っている"
      verify_by: live-trial
    - id: IN3
      loop_scope: inner
      text: "revise で 変更点.md の最新の版見出しと 要件定義.md の「版:」が一致し、C01 からの番号で変更・場所・きっかけが埋まっている"
      verify_by: script
    - id: OUT1
      loop_scope: outer
      text: "最初の版でやることが 3〜5 個に絞られ、広げる案が 決めること と 次に広げる候補 に分かれていると briefing-reviewer のシンプルさ観点が確認する"
      verify_by: evaluator
    - id: OUT2
      loop_scope: outer
      text: "examples/sample-haisha と同じ素材構成の匿名素材で new を最後まで通し、利用者がまとめ HTML 1 つを開いて できること・しくみ・決めること を説明なしで読み取れ、素材にある判断材料 (今の手間の数字・本物の紙・CSV の列の区分・要件の札・あとで に回した要望のしくみ) がボードにそろって判断できる (_check/profile.json の missing に残るのは素材に無いものだけ)"
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


# 打ち合わせ資料づくりの入口

## Runtime root contract

実行場所は [execution-contract.md](../../references/execution-contract.md) の「1. どちらのホストでも同じ呼び方」を正本とし、要点は次のとおり。

- `runtime_root_policy: host-skill-path` を適用する。
- Claude Codeでは `CLAUDE_PLUGIN_ROOT` をplugin rootとして使用する。
- Codexではホストが提示したこの `SKILL.md` のabsolute pathから、plugin manifestを持つ祖先を上方探索して論理 `PLUGIN_ROOT` を解決する。
- `cwd` からplugin rootを推測せず、literal placeholderをshellへ渡さない。各shell invocation内で解決済みabsolute pathを `PLUGIN_ROOT` に設定する。
- `prompts/` 配下はこのowner Skill契約を継承する。

## Purpose & Output Contract

素材と要望と短いヒアリングから、業務システムの打ち合わせ資料一式を毎回同じ工程・型・品質で作る。
打ち合わせのあとは、メモから変更点を起こし、影響する工程だけをやり直して版を上げる。

| 入口 | 引数 | できあがるもの |
| --- | --- | --- |
| new | `<素材フォルダ> [要望]` | `<素材フォルダ>/打ち合わせ資料/` 一式 (v0.1) |
| revise | `<資料フォルダ> <打ち合わせメモ>` | 同じフォルダで版を上げた一式と 変更点.md |

- 指定のない配色とデザインは [design-contract.md](../../references/design-contract.md) に従う。
- 出力フォルダの中身と各ファイルの役割は [workflow.md](../../references/workflow.md) にある。
- このスキルが自分で書くのは 変更点.md、`_check/choices.json`、`_check/review-<確認点>.json` だけ。ほかのファイルは担当スキルに任せる。
- 最初の版は「こういうことがやれます」が伝わる最小構成にする。広げる案は 決めること と 次に広げる候補 へ回す ([quality-rules.md](../../references/quality-rules.md) の「1. シンプルさ」を読む)。

### 再現の測り方

構造比較と高再現の受入は [workflow.md](../../references/workflow.md) の「再現の測り方」を正本とする。お手本は4画面の型の例で、6画面参考の再現ではない。参考を再現する場合は、その版・全機能の対応・初版範囲・画像比較の結果を既存の確認点と最終報告に残す。`profile.status=same` だけで高再現と判定しない。

## 工程 (new)

| 工程 | 担当 | 止まるか | 通す検査 |
| --- | --- | --- | --- |
| 0 データの方針と雛形 | このスキル | データの方針を聞く 1 回 | scaffold が exit0 |
| 1 ヒアリング | run-briefing-hearing | 質問のたび | `--stage hearing` |
| 2 要件定義書 | run-briefing-docs | 確認点1 | `--stage requirements` |
| 3 仕様書 | run-briefing-docs | 確認点2 | `--stage spec` |
| 4 ページ構成 | run-briefing-boards | 確認点3 | `--stage pages` |
| 5 ボードと PNG | run-briefing-boards | error と warn が 0 なら止まらない | render が exit0、目視 |
| 6 まとめ | run-briefing-book | exit0 なら止まらない | `--stage all` と book が exit0 |

### 工程0 データの方針と雛形

1. タイトルは要望と素材の名前から短く決める (例: 「配車表の読み取り」)。読む人の既定は 現場の担当者・発注側の責任者・開発する人。
2. 素材の名前と値を資料にそのまま載せるかを、AskUserQuestion で 1 回だけ聞く (header: 「データ」)。briefing.json がもうある (続きから再開する) ときは聞かない。

   | 表示 | 記録する値 | 中身 |
   | --- | --- | --- |
   | 素材のまま (おすすめ) | source | 素材をくれた先方と、作る側だけで見る |
   | 伏せる | masked | それ以外の人にも見せる |

   効き目は [quality-rules.md](../../references/quality-rules.md) の「名前と値の扱い (data_policy)」。あとで変えるときは briefing.json の `data_policy` を直し、ボードの札を合わせる。
3. 雛形を作る。

   ```bash
   node "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/build-briefing-scaffold.mjs" init \
     --materials "<素材フォルダ>" --title "<タイトル>" --data-policy <source|masked>
   ```

4. `_check/materials.json` を読み、素材の一覧を種類ごとに 1 行ずつ見せる。
5. `needs_csv: true` の Excel があれば、CSV に書き出してもらうよう頼む。読めない素材は「読めない」と書き、推測で埋めない。
6. 既存ファイルは上書きされない (`skipped` に出る)。続きから再開するときは skipped を見て工程を選ぶ。

### 工程1 ヒアリング

Skill `run-briefing-hearing` に 資料フォルダ と 要望 を渡す。聞き方と回の数は run-briefing-hearing が決める。
ヒアリング.md が `--stage hearing` を通ったら次へ。

### 工程2 要件定義書 → 確認点1

Skill `run-briefing-docs` に `requirements` を渡す。要件定義.md が `--stage requirements` を通ったら 確認点1 へ。

### 工程3 仕様書 → 確認点2

Skill `run-briefing-docs` に `spec` を渡す。仕様書.md が `--stage spec` を通ったら 確認点2 へ。

### 工程4 ページ構成 → 確認点3

Skill `run-briefing-boards` に `pages` を渡す。briefing.json の pages と表が `--stage pages` を通ったら 確認点3 へ。
仕様書の「ボード:」行と番号がずれたと返ってきたら、Skill `run-briefing-docs` にその行だけ直してもらう。

### 工程5 ボードと PNG (自動)

Skill `run-briefing-boards` に `boards` を渡す。render-board-png.mjs が exit0 (error も warn も 0) になり、PNG を目で見て崩れがなければ、止まらずに工程6 へ進む。文字の量の報告 (`notices` の TEXT-LONG・NOTES-MANY) では止まらない。
boards が 3 回直しても error か warn が残って返ってきたら、残った検査コードとボード番号を見せて利用者に相談する。
boards が 9 章に無い 決めること を返したら、Skill `run-briefing-docs` に 9 章へその Q だけ足してもらい (工程4 の「ボード:」行と同じ頼み方)、boards を通し直す。確認点は過ぎているので、その Q は打ち合わせで聞く。
boards が仕様書の足りない章と画面番号を返したら、Skill `run-briefing-docs` にその箇所だけ書き足してもらい、boards を通し直す。
確認点3 で light / standard / detailed が選ばれていたら、ここで同じ深さのまま `boards` を見てもらう (確認点の手順 5 と同じ。保存先は `_check/review-boards.json`)。

### 工程6 まとめ (自動)

`--stage all` を通す。error が出たら、そのファイルを書いてよいスキル ([workflow.md](../../references/workflow.md) の「出力フォルダ」の表) に直してもらう。変更点.md はこのスキルが revise の手順 4 と同じく直す。exit0 になってから Skill `run-briefing-book` を呼ぶ。
book が exit1 なら、book が示した担当スキルへその行を渡して直し、book を通し直す。担当スキルが無い行 (plugin の入れ直し) は、通し直さずに利用者へ伝える。2 回目も exit1 なら利用者に相談する。exit0 なら報告へ。

## 確認点の進め方

確認点1〜3 は同じ手順で進める。
確認点ごとの選択と次の工程への遷移は、共通の [execution-contract.md](../../references/execution-contract.md) 6節に従う。

1. 検査を通した現物を見せる。
   - 確認点1: 要件定義.md の場所、最初の版でやること、まだ決まっていない 決めること の件数と一覧。
   - 確認点2: 仕様書.md の場所、画面一覧の表、しくみと基盤の表、最初の版に入れないもの。
   - 確認点3: ページ構成の表 (番号・型・タイトル・主な読み手・伝えること)。ボードにならない画面 (要件定義 6 章で `あとで` に回した画面) と、`あとで` に回した `要望` の機能 (9 章の Q と、mechanism で描くか) を添える。下のコマンドで差の表を作り、「ページの型の並び」「画面のボードの数」「あとで に回した要望のしくみ」の 3 行を見せる (ほかの行はボードを作ってから埋まるので、報告で見せる)。

     ```bash
     node "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/compare-briefing-profile.mjs" --dir "<資料フォルダ>"
     ```

   - どの確認点でも validate の warn があれば件数と中身を添える。
2. 確認点1・2 では、この工程で 決めること に増えた Q があれば聞き足す。無ければ飛ばす。確認点3 は飛ばす (工程4 は docs を呼ばないので Q が増えない)。
   - Q 番号は、run-briefing-docs が工程の終わりに見せる「この工程で増えた 決めること」から取る。
   - Skill `run-briefing-hearing` を `followup <資料フォルダ> <Q 番号の並び>` で呼ぶ。何をどう聞くかは run-briefing-hearing が決める。
   - 返ってきた Q 番号と H 番号の組を、Skill `run-briefing-docs` に `answers <資料フォルダ> <組>` で渡して反映し、その工程の `--stage` を通し直す。
   - answers が file が 変更点.md の error を返したら、revise の手順 4 と同じくその行を直し、同じ組でもう一度頼む。
   - answers が返した 閉じた Q と直した本文の場所を見せてから手順 3 へ進む。
3. AskUserQuestion で次の 4 つから 1 つを記録する (header: 「確認点1」など)。

   | 表示 | 記録する値 | 中身 |
   | --- | --- | --- |
   | 標準で見る (おすすめ) | standard | 正確さ・言葉・見た目・シンプルさを見る |
   | このまま進める | accept-as-is | 見ないで次の工程へ |
   | 軽く見る | light | 検査結果と、確認点ごとに決めた観点 1 つだけ |
   | 詳しく見る | detailed | 4 観点に加えて素材との突き合わせを全部 |

   確認点ごとに見る観点は [assign-briefing-evaluator の SKILL.md](../assign-briefing-evaluator/SKILL.md) の「深さ」を読む。
   利用者が自由入力で直したい点を書いたら、その点を担当スキルで直し、検査を通し直して同じ確認点をもう一度見せる。
   選んだ値は `_check/choices.json` に確認点ごとに書く (例 `{"requirements": "accept-as-is", "spec": "standard", "pages": "light"}`)。同じ確認点を見直したら上書きする。
4. accept-as-is なら、次の工程へ進む。
5. light / standard / detailed なら、Skill `assign-briefing-evaluator` に 確認点 (`requirements` / `spec` / `pages`)、深さ、資料フォルダ、素材フォルダ を渡す。
   - 返ってきた指摘 JSON を `_check/review-<確認点>.json` に保存する (保存はこのスキルの役目)。
   - 指摘 JSON の代わりに形の誤りの一覧が返ってきたら、保存せずに一覧を見せ、見直すか accept-as-is にするかを利用者に聞く。
   - 重さ high と medium の指摘は担当スキルに渡して直す。low は利用者に見せ、直すか 決めること へ回すかを選んでもらう ([quality-rules.md](../../references/quality-rules.md) の「重さの決め方 (独立レビュー)」を読む)。
   - 直したら validate を通し直し、直した点の一覧を見せて次の工程へ進む。
   - もう一度見るかは利用者に聞く。同じ確認点で見るのは 3 回まで。

## 工程 (revise)

1. 資料フォルダの 要件定義.md・仕様書.md・briefing.json と打ち合わせメモを読む。
2. メモの中身を 1 件 1 行に分け、影響する工程を決める。

   | 変わったもの | やり直す工程 |
   | --- | --- |
   | 目的・範囲・できること・決めることの答え | 2 要件定義書 → 3 → 4 → 5 → 6 |
   | 画面の項目・動き・ルール・しくみ・権限 | 3 仕様書 → 5 (該当ボード) → 6 |
   | ページの並び・増減 | 4 ページ構成 → 5 → 6 |
   | ボードの見た目・言い回しだけ | 5 (該当ボードだけ `--only`) → 6 |

3. 変更点.md の先頭 (タイトルの直後) に新しい版の節を足す。版を上げる前に書く。docs の版上げは 変更点.md の一番上の版と 要件定義.md の版が同じかを検査するので、後に書くと必ず止まる。
   書き方は [document-structure.md](../../references/document-structure.md) の「変更点.md」を、お手本は [examples/sample-haisha/打ち合わせ資料/変更点.md](../../examples/sample-haisha/打ち合わせ資料/変更点.md) を読む。
4. Skill `run-briefing-docs` に「版を 1 つ上げる」と伝え (例: v0.1 → v0.2)、手順 3 で書いた節の行を変更の一覧として渡す。要件定義.md と 仕様書.md の「版:」行はこのスキルでは書かない。
   file が 変更点.md の error が返ってきたら、手順 3 の節をその行だけ直してから、同じ版でもう一度頼む。2 回目も返ってきたら、止めて利用者に相談する。
5. やり直す工程だけを順に進める。やり直した工程の確認点だけで止まる。確認点では、前の版の `_check/choices.json` の値を添えてから聞く。
   工程 2・3 は version-up で直した文書を確認点で見せるだけにし、requirements と spec は呼び直さない。確認点の手順 2 の Q は、version-up の 見せるもの の「増えた 決めること」のうち、まだ聞いていないものから取る。
   確認点の手順 2 で答えが出た Q も、answers が exit0 で返ってから、変更点.md の今の版の節に続きの C 番号で足し (書き方は手順 3 と同じ)、`--stage requirements` を通す。error はその行を直す。
   この版で 決めること の Q が増えたか閉じたら、工程5 ではその Q の話が出てくるボードを直す (雛形からの作り直しではなく、そのボードだけの更新)。
6. 最後に 工程6 を通す (工程6 の決まりのとおり)。版がずれていると book が止まる。

## 報告

最後に次を短く伝える。ファイルの中身は貼らない。

- まとめ HTML の場所 (先方に渡すのはこれ 1 つ) と版、データの方針 (素材のまま / 伏せる)
- ページ数、画面数、最初の版でやることの数
- 基準点との差の表 (compare-briefing-profile.mjs を通し直した `_check/profile.json`。構造の差・無効な材料・未計測。参考再現時は参考版・意味と範囲の対応・視覚照合の受入結果も別に報告。参考がない通常生成では高再現を「対象外」、参考が未提供なら「未検証」と書く)
- まだ決まっていない 決めること の一覧 (Q 番号と 1 行)
- 次に広げる候補 の数
- 検査の結果 (docs / boards / book の error と warn の数)、選んだ確認の深さ
- 次の一手 (打ち合わせのあとに `/briefing-revise <資料フォルダ> <メモ>`)

## Gotchas

- 先方にまとめ HTML を渡すのはよい。公開リンクを作るサービス (Artifact を含む) や、関係のない外部のサービスへ資料を上げない ([execution-contract.md](../../references/execution-contract.md) の「5. 守ること」)。
- Excel は直接読まない。CSV に書き出してもらう。
- 文書の見出しは /build-app などの実装スキルが読む入力でもある。言い回しを変えない ([document-structure.md](../../references/document-structure.md))。
- Mac と Windows の違いは [execution-contract.md](../../references/execution-contract.md) の「4. Mac と Windows」を読む。
- 同じ指示でもう一度 new を呼ぶと、雛形は上書きされず skipped になる。やり直したいファイルだけを担当スキルで書き直す。
- スキルの使い心地の不満は run-skill-feedback で記録する。

## Additional Resources

- [workflow.md](../../references/workflow.md): 出力フォルダ、書いてよいスキル、既定のページ構成、版の決まり
- [quality-rules.md](../../references/quality-rules.md): 正確さ・言葉・見た目・シンプルさの基準
- [execution-contract.md](../../references/execution-contract.md): スクリプトの呼び方、終了コード、Mac と Windows
- [case-haisha.md](../../references/case-haisha.md): お手本の読み方
