---
name: run-briefing-boards
description: 仕様書からページ構成を決めて画面ボードを型どおりに組みたいとき、組んだボードを PNG にしてはみ出しや注記の数を検査し目で確かめたいときに使う。
kind: run
effect: local-artifact
prefix: run
hierarchy: L2
version: 0.1.0
goal_seek:
  engine: inline
  fork: inline
owner: harness maintainers
source: plugins/system-briefing-book/plugin-composition.yaml#skills/run-briefing-boards
user-invocable: true
disable-model-invocation: false
output_language: ja
argument-hint: "pages|boards <資料フォルダ> [--only NN ...]"
allowed-tools: [Read, Write, Edit, Bash, Glob, Grep]
context: inherit
manifest: workflow-manifest.json
schema_refs:
  - ../../schemas/briefing.schema.json
reference_refs:
  - ../../references/design-contract.md
  - references/board-copy.md
  - ../../references/workflow.md
  - ../../references/page-patterns.md
  - ../../references/quality-rules.md
  - ../../references/plain-language.md
  - ../../references/execution-contract.md
script_refs:
  - ../../scripts/build-briefing-scaffold.mjs
  - ../../scripts/extract-source-crop.mjs
  - ../../scripts/render-board-png.mjs
  - ../../scripts/validate-briefing-docs.mjs
  - ../../scripts/count-csv-columns.mjs
combinators:
  - with-feedback-contract
feedback_contract: # per-skill 評価基準(SSOT=plugins/harness-creator/scripts/feedback_contract_ssot.py)
  activation_state: semantic_evaluator_started
  max_iterations: 3
  criteria:
    - id: IN1
      loop_scope: inner
      text: "briefing.json の pages が 7 種類の型だけで組まれ、no が 2 桁で重複せず、phone/pc に screens があり、validate-briefing-docs.mjs --stage pages が exit0 する"
      verify_by: script
    - id: IN2
      loop_scope: inner
      text: "pages の全ページに _src/NN_<slug>.html があり、注記の data-kind が can/how/ask のどれかになり、.mk の番号と注記の番号がそろっている (注記の数は quality-thresholds.json の board.notes_note を超えると報告 NOTES-MANY が出るだけで、止めない)"
      verify_by: script
    - id: IN3
      loop_scope: inner
      text: "render-board-png.mjs が error 0 で exit0 し、全ページの NN_<slug>.png が quality-thresholds.json の board.width x board.height の board.scale 倍でボード HTML より新しい"
      verify_by: script
    - id: OUT1
      loop_scope: outer
      text: "どのボードも伝えることが 1 つに絞られ、文字の詰まり・読みにくい配置がないと briefing-reviewer の見た目とシンプルさ観点が PNG を見て確認する (light は見た目だけなので、判定は standard 以上の結果で行う)"
      verify_by: evaluator
    - id: OUT2
      loop_scope: outer
      text: "お手本 examples/sample-haisha のボードを Mac と Windows の両方で PNG にし、どちらでも error 0 で同じ構成に見えることを実機で確かめる"
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


# ページ構成と画面ボード

## Runtime root contract

実行場所は [execution-contract.md](../../references/execution-contract.md) の「1. どちらのホストでも同じ呼び方」を正本とし、要点は次のとおり。

- `runtime_root_policy: host-skill-path` を適用する。
- Claude Codeでは `CLAUDE_PLUGIN_ROOT` をplugin rootとして使用する。
- Codexではホストが提示したこの `SKILL.md` のabsolute pathから、plugin manifestを持つ祖先を上方探索して論理 `PLUGIN_ROOT` を解決する。
- `cwd` からplugin rootを推測せず、literal placeholderをshellへ渡さない。各shell invocation内で解決済みabsolute pathを `PLUGIN_ROOT` に設定する。
- `prompts/` 配下はこのowner Skill契約を継承する。

## Purpose & Output Contract

仕様書から、どのページをどの順で見せるかを決め、ページの型からボードを組んで PNG にする。

| モード | 書くもの | 通す検査 |
| --- | --- | --- |
| `pages` | briefing.json の `pages` | `validate-briefing-docs.mjs --stage pages` |
| `boards` | `_src/NN_<slug>.html`、`_src/assets/`、`NN_<slug>.png` | `render-board-png.mjs` が error と warn 0、PNG の目視 |

- 書いてよいのは上の表のものだけ。文書は書かない。どのスキルが何を書くかは [workflow.md](../../references/workflow.md) の「出力フォルダ」を読む。
- ボードは画面構成・操作・状態を中心にする。仕様書2・3章のUIと合わせ、4〜7章のバックエンド・安全対策・基盤の詳細は転記しない。仕様書に足りない章や画面があれば、その章と画面番号を呼び出し元へ返す (書き足すのは run-briefing-docs)。
- ページの型と部品の正本は [page-patterns.md](../../references/page-patterns.md)、雛形は plugin の `assets/templates/board-<型>.html`。
- どのページを置き、何と書くか (画面のボードの置き方、ファイル名、message、注記の言葉) は [board-copy.md](references/board-copy.md)。
- 確認の深さを選ぶのと独立レビューは、呼び出し元の run-briefing が持つ。単独で呼ばれたときは結果を見せて終わる。
- このスキルが呼ぶスクリプトの exit 2 と exit 3 は、[execution-contract.md](../../references/execution-contract.md) の「3. 終了コード」を読み、そこに書かれたとおりにする。

## pages: ページ構成を決める

1. ヒアリング.md の H06、仕様書.md の 1・3・8 章、要件定義.md の 3.1・4・5.2・6・9 章を読む。
2. [workflow.md](../../references/workflow.md) の「既定のページ構成」を読み、既定の並びから始める。仕様書 1 章の画面はすべてボードにする。要らないページは足さない。数の目安 (`docs.screens_warn`、`docs.pages_warn`) と、超えたときの相談も同じ節にある。
3. briefing.json の `pages` を書く。各ページの鍵と形は [briefing.schema.json](../../schemas/briefing.schema.json) の `page` を読む。画面のボードの置き方、slug、title、message の決め方は board-copy.md を読む。
4. 検査する。

```bash
node "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/validate-briefing-docs.mjs" --dir "<資料フォルダ>" --stage pages
```

   exit 1 なら `_check/docs.json` の errors を見る。BOARD-REF-* (仕様書の「ボード:」行のずれ) は仕様書.md を書けないので、ずれた画面番号を呼び出し元へ返す (書き直すのは run-briefing-docs)。それ以外は pages を直して通し直す。
5. 番号・型・タイトル・主な読み手・伝えること を並べた表を見せる。

## boards: ボードを組んで PNG にする

### 1. 雛形を作る

[design-contract.md](../../references/design-contract.md) の標準デザインと共通部品を使う。CSSの更新や案件の配色変更も同じ契約に従う。

```bash
node "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/build-briefing-scaffold.mjs" boards --dir "<資料フォルダ>"
```

既にある HTML は上書きされない。雛形から作り直したいボードは、今のファイルを別の名前に変えてから呼ぶ (消さない)。

### 2. 中身を組む

[page-patterns.md](../../references/page-patterns.md) の「1 枚のボードの決まり」「注記 (notes)」「端末の画像を他のボードで使う (data-export)」と型ごとの中身に沿って、雛形の印の所を埋める。言葉は board-copy.md の型で書く。

- 要件定義 9 章で 決定 になった Q の ask は外し、決まった中身を画面に描く (既にあるボードも同じ)。
- 9 章に無い 決めること がボードに要るときは、書かずにその話を呼び出し元へ返す (9 章に足すのは run-briefing-docs)。

素材の紙や画面を載せるときは切り出して `_src/assets/` に置き、載せた所に `data-source` を付ける ([page-patterns.md](../../references/page-patterns.md) の「判断材料の部品」)。実名が写る素材をそのまま載せてよいかは briefing.json の `data_policy` で決まる ([quality-rules.md](../../references/quality-rules.md) の「名前と値の扱い (data_policy)」)。

```bash
node "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/extract-source-crop.mjs" --src "<素材>/配車表.pdf" --page 1 --rel 0.05,0.1,0.6,0.4 --out "<資料フォルダ>/_src/assets/haisha-top.png"
```

大きさが分からないときは `--src <ファイル> --info` で先に調べる。

data-map の列の区分の棒は、素材の列の見本の列を先に数えてから描く。道具は列ごとに `blank` (全部が空)・`fixed` (いつも同じ値)・`value` (それ以外) だけを返す。紙から読む・しくみが入れる・決めること の区分は、仕様書 4 章と素材を読んで決める。

```bash
node "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/count-csv-columns.mjs" --src "<素材>/取り込み列_例.csv"
```

### 3. PNG にして検査する

```bash
node "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/render-board-png.mjs" --dir "<資料フォルダ>"
```

- exit 1 なら `_check/boards.json` の `errors` と `warnings` を見て直し、同じボードだけ `--only NN` で通し直す。render は warn だけでも exit 1 になる。
- 文字の量の報告 (`notices` の TEXT-LONG・NOTES-MANY) は exit に効かない。直さずに進めてよい。減らすときは quality-rules.md の「量を減らすとき」に従う。
- 直し方に判断が要る検査コードは [quality-rules.md](../../references/quality-rules.md) の「4. 見た目」を読む。ほかのコードはメッセージに従う。
- 3 回直しても error か warn が残るときは、ボード番号と検査コードを呼び出し元へ返して止まる。

### 4. 目で確かめる

全ページの PNG を Read で開き、quality-rules.md の「4. 見た目」にある「目で確かめること」を見る。直したら 3 に戻る。最後に `--stage all` を通す (ボードの h1 と画面名の一致、ボード HTML の有無、ボードの文字の言い換えを見る)。

## 見せるもの

- pages: ページ構成の表と warn。
- boards: PNG の場所と枚数、boards.json の error と warn と notices の数、目で見て直した点。

## Gotchas

- mechanism を置くのは、workflow.md の「既定のページ構成」の条件に当たるときだけ。それ以外で型に収まらない図を描きたくなったら、まず型のどれかで言えないか考える。
- Windows で作るときや、別の PC で作り直すときは、execution-contract.md の「4. Mac と Windows」を読む。
- 色を変えたくなっても `_src/tokens.css` と common.css を書き換えない。案件の色が要るときは、そのことを呼び出し元へ返す (briefing.json の `palette` に配色の CSS の場所を書いて init を回し直すのは run-briefing)。手順は [standard-attribution.md](../../assets/css/standard-attribution.md) の「案件の配色に合わせるとき」、init の引数は execution-contract.md の表にある。

## Additional Resources

- [board-copy.md](references/board-copy.md): 画面のボードの置き方、ファイル名と見出し、message と注記と画面の中の言葉のお手本
- [workflow.md](../../references/workflow.md): 既定のページ構成、どのスキルが何を書くか
- [page-patterns.md](../../references/page-patterns.md): 7 種類の型、ボードの部品、注記の書き方
- [quality-rules.md](../../references/quality-rules.md): 見た目とシンプルさの基準、判断が要る検査コードの直し方、目で確かめること
- [plain-language.md](../../references/plain-language.md): ボードの言葉
- [execution-contract.md](../../references/execution-contract.md): 終了コード、ブラウザの探し方、Mac と Windows の違い
