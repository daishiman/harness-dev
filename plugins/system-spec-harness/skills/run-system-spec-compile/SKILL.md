---
name: run-system-spec-compile
description: 収集済み仕様 (spec-state.json) と取得済み最新ドキュメント・設計知識参照を章立ての複数 Markdown ファイル + index の仕様書ドキュメントセットへまとめたいとき、ヒアリング結果を仕様書へコンパイルしたいときに使う。
disable-model-invocation: false
user-invocable: true
kind: run
prefix: run
effect: local-artifact
owner: team-platform
since: 2026-07-11
version: 0.1.0
source: plugins/system-spec-harness/skills/run-system-spec-compile/
source-tier: internal
last-audited: 2026-07-11
audit-trigger: official-update
responsibility_refs:
  - prompts/R1-assemble.md
  - prompts/R2-render.md
  - prompts/R3-crosslink.md
reference_refs:
  - references/resource-map.yaml
# script_refs の validate-knowledge-graph.py は IN1 ゲートではないが R2-render が実行を指示する
# (--profile knowledge --order で C14 位相順、--profile doctrine で C15 anchor 被覆)。宣言を本文より
# 狭くすると依存追跡が精読頼みになる。script_refs の中に置かないのは lint-plugin-composition が
# block list の中のコメント行を受け付けないため。
script_refs:
  - scripts/compile-spec-doc.py
  - ../../scripts/validate-coverage-matrix.py
  - ../../scripts/validate-source-citation.py
  - ../../scripts/validate-design-knowledge-refs.py
  - ../../scripts/validate-knowledge-graph.py
schema_refs:
  - ../../schemas/spec-state.schema.json
  - ../../schemas/fetched-references.schema.json
allowed-tools:
  - Read
  - Write
  - Bash
responsibilities:
  # id は prompt 本文が名乗る責務 id (`| responsibility | R1-assemble ...`) と同じ形に揃える。
  # frontmatter だけ短縮形 (R1) だと、責務宣言と prompt 側 anchor を機械的に突き合わせられない。
  - id: R1-assemble
    name: assemble
    prompt_required: true
  - id: R2-render
    name: render
    prompt_required: true
  - id: R3-crosslink
    name: crosslink
    prompt_required: true
combinators:
  - with-goal-seek
  - with-feedback-contract
goal_seek:
  activation_state: semantic_evaluator_started
  engine: inline
  fork: subagent
  max_loops: 5
completeness_exempt:
  - "manifest: compile retries select the failed deterministic/content gate dynamically; the SKILL body is the runtime SSOT."
feedback_contract:
  activation_state: semantic_evaluator_started
  max_iterations: 5
  criteria:
    - id: IN1
      loop_scope: inner
      verify_by: script
      text: 生成直前の spec-state.json と fetched-references.json に対し validate-coverage-matrix.py、validate-source-citation.py、validate-design-knowledge-refs.py が exit0。
    - id: OUT1
      loop_scope: outer
      verify_by: test
      text: 生成された仕様書ドキュメントセットがカテゴリ×プラットフォームの確定/対象外理由と最新ドキュメント出典を含むことを受入テストが確認。
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
---

## Pre-choice usable artifact execution

Purpose & Output Contractの最小の実成果物をmain contextで作成する。effect別のparse/open・secret・irreversible・corrupt guardだけを実行し、現物path・digest・開き方を提示してからaccept-as-is/light/standard/detailedを記録する。accept-as-isはその場でhandoff完了とし、後続sectionを実行しない。

## Post-choice selected improvement execution

以下の既存workflow・goal-seek・評価・修正sectionはlight/standard/detailedが記録されて`semantic_evaluator_started`へ遷移した場合だけ実行する。release/exhaustiveは別の明示eventを必要とする。


# run-system-spec-compile

> 収集済み仕様 (spec-state.json) と取得済み最新ドキュメント (fetched-references.json)・設計知識参照を、**章立ての複数 Markdown ファイル + index.md** の仕様書ドキュメントセットへまとめる run skill。ヒアリング継続やドキュメント再取得はしない (入力を組み立てるのみ)。

## Purpose & Output Contract

**入力** (境界・厳守):
- `spec-state.json` — カテゴリ×プラットフォーム収集マトリクス (C01 run-system-spec-elicit の単一 writer が所有)。
- `fetched-references.json` — 取得済み最新公式ドキュメントの出典記録 (C02 が取得)。
- 設計知識参照 — `../ref-system-design-knowledge/references/*.md` (C04)。

**出力**: `system-spec/` 配下の、**先頭にU1-U9と意思決定表を持つ要件定義書 (`00-requirements-definition.md`) + 章別 Markdown 複数ファイル (`<category>.md`) + `index.md`**。

**各技術章の構成** (順序厳守・構造の正本 = `references/chapter-template.md`、実装の正本 = `scripts/compile-spec-doc.py` の `render_chapter`):

1. 確定マーカー frontmatter (下記「章 frontmatter の確定マーカー仕様」)
2. `# <label> (<category>)` 見出し + 集約サマリ
3. `## カテゴリ別収集状態` — canonical platform 順の表 (未収集 / 対象外+理由 / 確定+qa_ref)
4. `## 対象外の承認範囲` — 対象外セルが承認 id を引いているときだけ置く条件付き節 (承認 note の逐語)
5. `## 上流指針 (doctrine anchors)` — concern authority が示す上流指針。category_concern_map に無いカテゴリは pending 例外として暫定扱いを明示し、approved で concerns を解決済みの例外だけ authority を描く
6. `## 確定内容 (質疑録)` — 確定セルの qa_id・対応セル・質問・回答本文
7. `## To-Be / Delta` — 規範節 (到達すべき状態・受入条件・本章のやりたいこと・効く意思決定)
8. `## 適用された設計知識` — 非規範の参考資料。`### 本章での適用` (章単位の適用記述) → C04 deep card 本文 (`knowledge-catalog.json` の depends_on が定める位相順・C14) → project candidate → `### 確定判断ごとの原則採否` (`qa_log[].design_applications` を qa_ref・対応セル・serves_goals へ束縛し、未記録は `unrecorded`)
9. `## 最新ドキュメント出典` — 対象 / version / 公式発行元 (host) / source_url / 取得 / 最新確認の表

**完了条件**: 要件定義書 + 全カテゴリ章 + index.md が生成され、IN1 (3 決定論ゲート exit0) と OUT1 (受入テスト) を満たす。

**上位概念 anchor (要件 C9)**: spec-state.json の `requirements_foundation` (U1-U9) を **`00-requirements-definition.md` (要件定義書=憲法) として最初の章**に生成し、各技術章 frontmatter の `serves_goals` (セル serves_goals の集約) で全章を上位概念へトレース (anchor) する。`index.md` は要件定義書を先頭に相互参照する。requirements_foundation 不在の spec-state でも空落ちさせず draft の要件定義書を出す。

**やらないこと** (boundary): ヒアリングの継続 (C01 の責務)、ドキュメントの再取得 (C02 の責務)、spec-state.json の書換え。本 skill は**入力を章へ組み立てるだけ**で、収集状態そのものは変更しない。

## 章 frontmatter の確定マーカー仕様 (C11 hook の判定ソース・厳守)

各章 Markdown の frontmatter は次の確定マーカーを持つ。C11 hook (`guard-confirmed-chapter-overwrite.py`) はこのマーカーと spec-state.json のセル状態を判定ソースとして確定章の誤上書きを fail-closed で遮断する。

```
---
status: confirmed        # 終端カテゴリ (集約=確定/対象外) は confirmed。進行中 (未着手/収集中) は draft
category: database        # 章のカテゴリ id
aggregate: 確定           # 真理値表導出の集約状態 (未着手/収集中/確定/対象外)
spec_cells: [database.web, database.mobile, ...]   # 対応する spec-state マトリクスセル id
serves_goals: [G1, G2]    # 章が資する上位概念ゴール id (セル serves_goals の集約・要件 C9 anchor)
---
```

- **status**: `confirmed`=章凍結 (集約が終端の 確定/対象外)、`draft`=進行中。集約は宣言値ではなくセル状態から**真理値表で再導出**する (決定論)。
- **spec_cells**: 章が対応する `<category>.<platform>` セル id 一覧 (canonical platform 順)。
- **serves_goals**: 章の確定セルが資する上位概念ゴール id の和集合 (要件 C9 の anchor)。要件定義書 (`00-requirements-definition.md`) の goals へトレースし、どのゴールにも資さない収集を drift として `--require-foundation` が検出する。
- 各章本文は**カテゴリ別収集状態表** (未収集 / 対象外+理由 / 確定+qa_ref) と設計知識参照ポインタと最新ドキュメント出典表を持つ (要件 C1)。

## 単一 writer / 確定状態保全 (C01/C03)

`system-spec/` への正本書込経路は **C03 (本 skill) の `scripts/compile-spec-doc.py`** に一本化する。確定済み章の確定状態 (spec-state 確定セル・対象外理由) は保全され、勝手な巻き戻しをしない。これは C01 (spec-state.json の単一 transition writer) と対をなす**二輪の単一 writer**であり、C11 hook はこの正本防御を二重化する fail-closed の補助防御にすぎない (正本防御は writer 側が担う)。spec-state 上でセルが R4-reopen 済み (再オープン) のときだけ、該当章を draft へ戻して再レンダリングできる。

## 手順 (責務プロンプト正本 = prompts/*.md)

0. **IN1 compile 入口ゲート**: 出力を一切書く前に `validate-coverage-matrix.py --matrix $CLAUDE_PROJECT_DIR/system-spec/spec-state.json --require-complete`、`validate-source-citation.py --targets $CLAUDE_PROJECT_DIR/system-spec/spec-state.json --references $CLAUDE_PROJECT_DIR/system-spec/fetched-references.json --repo-root $CLAUDE_PROJECT_DIR`、`validate-design-knowledge-refs.py --matrix $CLAUDE_PROJECT_DIR/system-spec/spec-state.json --repo-root $CLAUDE_PROJECT_DIR` を実行する。いずれかが非0なら compile へ進まず blocker を返す。`compile-spec-doc.py compile` は最後の実在ゲートを内蔵し、`--repo-root $CLAUDE_PROJECT_DIR` で同じ validator を呼ぶ。
1. **R1-assemble** (`prompts/R1-assemble.md`): spec-state.json の `requirements_foundation` (上位概念) を先頭章に、収集済みカテゴリ×プラットフォーム結果を各技術章に組み立てる (カテゴリ順・canonical platform 順・集約状態を真理値表導出)。
2. **R2-render** (`prompts/R2-render.md`): 章立てに沿って章別 Markdown へレンダリングし、設計知識参照 (C04) と最新ドキュメント出典 (fetched-references) を各章へ、各技術章 frontmatter へ `serves_goals` (上位概念トレース) を反映する。
3. **R3-crosslink** (`prompts/R3-crosslink.md`): 全章横断の `index.md` を生成し、要件定義書を先頭に、各章と収集マトリクス集約状態 (未着手/収集中/確定/対象外) を相互参照可能にする。

決定論の組み立て・frontmatter 生成・index 相互参照は `scripts/compile-spec-doc.py` (Python 標準ライブラリのみ) が担い、責務プロンプトは判断・章構成の意味付けを担う (機械=再現性 / AI=自由度の二層分離)。

## Key Rules

1. **確定性優先**: 集約状態・確定マーカーは spec-state のセルから真理値表で**再導出**し、宣言値を鵜呑みにしない。
2. **入力非改変**: spec-state.json / fetched-references.json を書換えない (読むだけ)。
3. **出典必須**: 章に反映する最新ドキュメントは source_url・公式発行元・version|last_updated・取得/最新確認日時を伴う (C13 が形式検証)。出典は target の category (主たる章) に載せ、target が `also_categories` で宣言した章にも同じ出典を載せる。宣言の無い章へは推測で重複させない。
4. **対象外は理由付き**: 対象外セルは必ず理由 (または承認参照) を章へ明示する (C12 が検証)。
5. **日本語成果物**: 章・index の本文は日本語 (カテゴリ id・platform id・JSON キーは英語)。
6. **逐語は章の構造を壊さない**: spec-state の逐語 (qa の問・答・出所、承認 note、章の適用記述、To-Be/Delta のゴール・具体的にやりたいこと・意思決定の問) に見出し・フェンス・setext の下線が行として含まれるときは、その逐語をフェンスに閉じ込めて描く (本文の字面は変えない)。表のセルに入る逐語 (状態表の対象外理由、To-Be/Delta の目標と観測点) は、改行を `<br>` に、`|` を `\|` にして 1 行に収める (表示される字面は変えない)。逐語の行頭 `###` が章の見出しとして漏れると、次回の compile がそれを人の節と見なして引き継ぎ続ける。
7. **置き換え済みの qa は旧版の印付きで描く**: `superseded_by` を持つ qa entry は「旧版（置き換え先: <qa_id>）」の印付きで描き、問・答は逐語のまま残す。印の根拠は `superseded_by` だけで、R4-reopen の履歴から一律に旧版と推し量らない。
8. **既存章の片付け (移行)**: 以前の compile が漏らした見出し (Key Rules 6 でフェンスに閉じ込める逐語に、行として現れる見出し) は、2 つの判定で扱いを分ける。(a) 引き継ぎの境界からは字面だけで外す (逐語と同じ字面の見出しは、人の節としても引き継げない)。(b) 消失判定から外すのは、既存章でその見出しの直下 (次の見出しまで) が漏れの形をしている場合に限る。漏れの形とは、同じ逐語の続きの行がそのまま並び (逐語の中に次の見出しがあればそこまで)、逐語が末尾まで続いたときだけ、その後ろに spec-state から導ける行 (逐語の行と、compile が qa・承認とその参照を描く行) が並ぶ形をいう。見出しの字面が逐語と同じでも、直下が漏れの形でなければ人の節なので、消失として CompileError で止める。エラーは衝突した見出しを示し、人の節なら逐語に無い見出しへ改めるよう、旧 compile の漏れならその見出しと直下の行を既存章から消すよう促す。管轄節と同じ見出しの `####` 質疑ブロックは引き継がず再描画する。人が書いた見出しが消えるときは従来どおり CompileError で止める (人の節の保存則は変えない)。

## Gotchas

1. `system-spec/*.md` を `Write` / `Edit` で直接書かない。正本経路は `scripts/compile-spec-doc.py` だけで、確定章への直接書込は C11 hook (`guard-confirmed-chapter-overwrite.py`) が fail-closed で遮断する。章の内容を変えたいときは spec-state 側を C01 の writer で直し、compile を回し直す。
2. 章を直したくなったとき spec-state.json を書き換えない (入力非改変)。spec-state の変更は C01 `apply-spec-transition.py` の責務で、本 skill は読むだけ。
3. `aggregate` / `status` を frontmatter へ手で書かない。真理値表からの再導出が正本で、手書き値は次の compile で上書きされる (宣言と実状態の乖離を残さない)。
4. 確定章を draft へ戻せるのは spec-state 上でセルが R4-reopen 済みのときだけ。reopen していないセルの章を draft へ落とすのは確定の巻き戻しにあたる。
5. `design_applications` が無い旧 state の章に、compiler が定型の「適用済み」文を補完しない。未記録は未記録と印字し、C05 が `unrecorded` finding として拾う (存在確認だけの自己循環 PASS を作らない)。
6. deep card を `resource-map.yaml` の記述順で並べない。`knowledge-catalog.json` の depends_on が定める位相順 (C14) で、依存先の知識を依存元より先に置く。
7. 出典表に取得できていない参照を埋めない。未取得は C02 へ差し戻す (捏造値で表を埋めて緑化しない)。

## ゴールシーク実行

IN1/OUT1 の未達ゲートを起点に assemble/render/crosslink の該当責務だけを再実行する。各反復で決定論ゲートを先に通し、最大5周で未達なら成果物を確定せず呼出元へ blocker を返す。全ゲートPASS時だけ完了する。

### ゴール (Goal)

収集済み spec-state.json と取得済み fetched-references.json・設計知識参照が、上位概念へトレース可能な要件定義書 + 章別 Markdown + index.md の仕様書ドキュメントセットへ、決定論的に (同じ入力から同じ出力が出る形で) 組み上がっている。

### 完了チェックリスト (停止条件)

- [ ] `00-requirements-definition.md` が `requirements_foundation` (U1-U9) と意思決定表を持ち、先頭章として生成されている (foundation 不在時は空落ちさせず draft で出す)
- [ ] 全カテゴリ章が上記「各技術章の構成」を順序どおり**全て**持ち (4 の承認節だけは条件付き)、該当データが無い節も見出しを残して不在を明示する placeholder を置いている (空節を落とすと未確定が不可視になるため)
- [ ] 各章 frontmatter の `status` / `aggregate` が宣言値ではなくセル状態からの真理値表再導出になっている
- [ ] 各章 frontmatter の `serves_goals` が確定セル serves_goals の和集合で、要件定義書の goals へトレースできる
- [ ] 確定セルの qa entry が「確定内容 (質疑録)」へ原文のまま転記され、要約・言い換えで置き換わっていない
- [ ] 章内の deep card が `knowledge-catalog.json` の depends_on 位相順 (C14) で並び、`design_applications` 未記録は定型文で補完せず未記録と印字されている
- [ ] 出典表が実取得済み参照だけで構成され、未取得を捏造値で埋めていない
- [ ] `index.md` が要件定義書を先頭に全章と集約状態を相互参照している
- [ ] IN1 (`validate-coverage-matrix.py` / `validate-source-citation.py` / `validate-design-knowledge-refs.py` が exit0) を満たしている
- [ ] OUT1 (`tests/test_compile_spec_doc.py`) が PASS している

## Feedback Contract (with-feedback-contract / with-goal-seek)

- **IN1** (inner, script): 生成直前の spec-state.json / fetched-references.json に対し `../../scripts/validate-coverage-matrix.py --matrix <spec>`、`../../scripts/validate-source-citation.py --targets <spec> --references <refs> --repo-root <project-root>`、`../../scripts/validate-design-knowledge-refs.py --matrix <spec> --repo-root <project-root>` が exit0。最後のゲートは coverage が形状しか見ない `design_applications[].knowledge_ref` の path / anchor 実在を保証する。
- **OUT1** (outer, test): 生成ドキュメントセットがカテゴリ×プラットフォームの確定/対象外理由と最新ドキュメント出典を含むことを `tests/test_compile_spec_doc.py` が確認。
- goal-seek (engine=inline, fork=subagent, max_loops=5): IN1/OUT1 を満たすまで章構成・レンダリングを反復改善する。

## Additional Resources

`references/resource-map.yaml` を最初に読む。主要参照:

- `scripts/compile-spec-doc.py` — 要件定義書 (00-requirements-definition.md) + 章別 Markdown + index.md の決定論コンパイラ (frontmatter 確定マーカー / serves_goals / 状態表 / 出典表 / 相互参照)
- `references/chapter-template.md` — 章 Markdown の構造テンプレート
- `prompts/R1-assemble.md` / `prompts/R2-render.md` / `prompts/R3-crosslink.md` — R1/R2/R3 責務別プロンプト
- 入力: `spec-state.json` (C01) / `fetched-references.json` (C02) / `../ref-system-design-knowledge/references/*.md` (C04)
- 決定論ゲート: `../../scripts/validate-coverage-matrix.py` (C12) / `../../scripts/validate-source-citation.py` (C13) / `../../scripts/validate-design-knowledge-refs.py` (`knowledge_ref` path / anchor 実在)
