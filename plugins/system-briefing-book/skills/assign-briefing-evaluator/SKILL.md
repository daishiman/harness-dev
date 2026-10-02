---
name: assign-briefing-evaluator
description: 確認点で利用者が見る深さを選んだあと打ち合わせ資料を作り手とは別の目で確かめたいとき、正確さ・言葉・見た目・シンプルさの指摘を資料の編集なしで受け取りたいときに使う。
version: 0.1.0
owner: harness maintainers
source: plugins/system-briefing-book/plugin-composition.yaml#skills/assign-briefing-evaluator
kind: assign
effect: conversation-output
prefix: assign
# 見る相手は run-briefing の工程が作った資料 (作った本人は採点しない)
pair: run-briefing
hierarchy: L2
user-invocable: false
disable-model-invocation: false
output_language: ja
context: fork
agent: briefing-reviewer
argument-hint: "--stage requirements|spec|pages|boards --depth light|standard|detailed --dir <資料フォルダ> --materials <素材フォルダ>"
allowed-tools: [Read, Glob, Grep, Bash(node *), Task]
agent_refs:
  - ../../agents/briefing-reviewer.md
reference_refs:
  - ../../references/quality-rules.md
  - ../../references/plain-language.md
  - ../../references/execution-contract.md
script_refs:
  - ../../scripts/validate-briefing-docs.mjs
  - ../../scripts/render-board-png.mjs
responsibility_refs:
  - ../../agents/briefing-reviewer.md
responsibilities:
  - id: R1-assign
    prompt_required: false
    summary: "決定論検査の結果と、確認点の対象・素材の場所・深さだけを briefing-reviewer へ渡し、返った指摘 JSON を形だけ確かめて無加工で呼び出し元へ返す"
combinators: []
feedback_contract:
  skip_reason: "assign kind は独立レビューを briefing-reviewer へ渡して指摘を回収するだけで、自身は資料を直す反復を持たない。直す反復は呼び出し元 run-briefing の feedback_contract が持つ"
runtime_root_policy: host-skill-path
---

# assign-briefing-evaluator

## Runtime root contract

実行場所は [execution-contract.md](../../references/execution-contract.md) の「1. どちらのホストでも同じ呼び方」を正本とし、要点は次のとおり。

- `runtime_root_policy: host-skill-path` を適用する。
- Claude Codeでは `CLAUDE_PLUGIN_ROOT` をplugin rootとして使用する。
- Codexではホストが提示したこの `SKILL.md` のabsolute pathから、plugin manifestを持つ祖先を上方探索して論理 `PLUGIN_ROOT` を解決する。
- `cwd` からplugin rootを推測せず、literal placeholderをshellへ渡さない。各shell invocation内で解決済みabsolute pathを `PLUGIN_ROOT` に設定する。
- `prompts/` 配下はこのowner Skill契約を継承する。

## Purpose & Output Contract

確認点で利用者が light / standard / detailed を選んだときだけ、run-briefing から呼ばれる。
資料を作った文脈とは別の文脈 (briefing-reviewer) に、正確さ・言葉・見た目・シンプルさを確かめさせ、指摘を返す。資料は編集しない。

### 受け取るもの

| 引数 | 値 | 見る対象 |
| --- | --- | --- |
| `--stage` | `requirements` | 要件定義.md (と ヒアリング.md) |
| | `spec` | 仕様書.md (と 要件定義.md) |
| | `pages` | briefing.json の pages (と 仕様書.md) |
| | `boards` | `_src/NN_*.html` と `NN_*.png` |
| `--depth` | `light` / `standard` / `detailed` | 下の「深さ」 |
| `--dir` | 資料フォルダ | |
| `--materials` | 素材フォルダ | 正確さの突き合わせ先 |

`boards` は確認点ではない。確認点3 で light 以上が選ばれていたとき、run-briefing が工程5 のあとに同じ深さで呼ぶ。

### 深さ

| 深さ | 見る観点 | 素材との突き合わせ |
| --- | --- | --- |
| light | 決定論検査の結果 + 下の表の観点 1 つ | 見出しと表の先頭だけ |
| standard | 正確さ・言葉・見た目・シンプルさ の 4 つ | 名前・数字・列名を抜き取りで |
| detailed | 4 つ全部 | 表の全行を素材と 1 つずつ |

| stage | light で見る観点 |
| --- | --- |
| requirements | シンプルさ |
| spec | 正確さ |
| pages | シンプルさ |
| boards | 見た目 |

### 返すもの

briefing-reviewer が返す指摘 JSON 1 個。

- 形は [briefing-reviewer.md](../../agents/briefing-reviewer.md) の「Layer 7: UI / 提示層」を読む。
- 重さ (`severity`) の決め方は [quality-rules.md](../../references/quality-rules.md) の「重さの決め方 (独立レビュー)」を読む。
- 保存は呼び出し元がする (`_check/review-<stage>.json`)。このスキルはファイルを書かない。

## 手順

1. 決定論検査を通す。結果の数だけを控える。

```bash
node "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/validate-briefing-docs.mjs" --dir "<資料フォルダ>" --stage <stage>
```

`stage` が `boards` のときは `--stage all` を通す (`--stage all` が足すのはボード HTML の有無と言い換えの検査だけで、まとめ HTML は見ない)。続けて見た目の検査を PNG を作り直さずに通す。

```bash
node "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/render-board-png.mjs" --dir "<資料フォルダ>" --check-only --allow-warn
```

validate の exit 3 は [execution-contract.md](../../references/execution-contract.md) の「3. 終了コード」のとおり呼び出し元へ伝えて止まる。render の exit 3 (validate を通ったあとなのでブラウザが無いとき) だけは正本と違い、`render_exit: 3` として見た目の観点を PNG の目視だけで進める。

2. briefing-reviewer に次だけを渡す: stage、depth、資料フォルダ、素材フォルダ、手順 1 の終了コードと `_check/docs.json` の場所、light のときの観点。
   boards のときは、`--check-only` の stdout の JSON (ボードごとの errors と warnings と notices) も「render の結果:」の行で渡す。`--check-only` は `_check/boards.json` を書かないので、そのファイルは 工程5 の本番の render の結果で、直したあとには古いことがある。
3. 返ってきた JSON の形を確かめる (schema、findings の 4 項目 severity / 場所 / 理由 / 直し方、summary と findings の数の一致、verdict が high か medium があれば `fix` で無ければ `ok`)。形が崩れていたら 1 回だけ形の直しを頼む。中身は変えない。2 回目も崩れていたら JSON を直さずに、形の誤りの一覧を添えて呼び出し元へ返す (run-briefing は利用者に相談する)。
4. JSON をそのまま呼び出し元へ返す。

## Key Rules

- 独立を保つため、作り手の意図、前の指摘、何回目か、利用者とのやりとりは渡さない。
- 資料 (文書、ボード、briefing.json) を編集しない。検査スクリプトが `_check/` に書く結果だけは上書きされる。
- 指摘の数を減らしたり重さを変えたりしない。並べ替えもしない。
- 素材や資料を、公開リンクを作るサービスや、関係のない外部のサービスへ上げない ([execution-contract.md](../../references/execution-contract.md) の「5. 守ること」)。

## Gotchas

- render の exit 3 で止まらずに進めるのは、このスキルだけの例外 (手順 1)。
- 素材に Excel しか無く CSV が無いときは、正確さの突き合わせができなかった範囲を finding (low) として返す。
- detailed は素材が多いと長くかかる。

## Additional Resources

- [briefing-reviewer.md](../../agents/briefing-reviewer.md): 観点ごとの見方と出力の決まり
- [quality-rules.md](../../references/quality-rules.md): 4 観点の基準と重さの決め方
- [plain-language.md](../../references/plain-language.md): 言葉の観点の基準
