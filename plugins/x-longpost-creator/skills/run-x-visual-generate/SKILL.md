---
name: run-x-visual-generate
description: 確定した長文投稿パターンAから X 5:2 と note 1280x670 の標準サムネイル2種を作りたいとき、明示指定で冒頭図解も追加したいときに使う。
disable-model-invocation: false
user-invocable: true
argument-hint: "[--file <投稿ファイル>] [--only diagram|x-thumb|note-thumb|diagram,x-thumb|diagram,note-thumb|x-thumb,note-thumb|diagram,x-thumb,note-thumb]"
arguments: [file, only]
allowed-tools:
  - Read
  - Write
  - Glob
  - Grep
  - Bash(node *)
kind: run
version: 1.0.0
effect: local-artifact
owner: team-content
contract:
  intent: 確定した長文投稿パターンAを読み、Xサムネイル（5:2）と noteサムネイル（実 PNG 1280x670）を標準成果物として必ず生成・検証・差し込む。図解（16:9）は明示的に指定された場合だけ追加生成する。
  interface:
    inputs: [file, only]
    outputs: ["diagram.png", "x-thumb.png", "note-thumb.png", "Obsidian添付先の投稿固有名画像", "投稿ファイルの図解・サムネイル欄への差し込み"]
  invariant:
    - 本文に無い主張・数値・固有名詞を図解に足さないこと
    - 図解は純白背景・白黒配色を保ち、赤は失敗を示す ✕ 印にのみ使うこと
    - サムネイル2種はオフホワイト背景・墨黒文字・役割を固定したアクセント2色を保ち、人物を描かず情報商材的意匠を使わないこと
    - 標準成功で x-thumb.png と note-thumb.png の2枚が揃うこと。diagram.png は optional であること
    - 絵文字を画像内・プロンプト内・ファイル名のいずれにも入れないこと
    - 「僕」「私」という文字を画像に入れないこと
    - 長文投稿パターンAが確定する前に実行しないこと
since: 2026-08-31
source: 利用者提供の図解プロンプトとサンプル図解4枚 (2026-08-31)
source-tier: internal
last-audited: 2026-08-31
audit-trigger: quarterly
combinators:
  - with-feedback-contract
responsibility_refs:
  - ../../prompts/x-longpost-analyze-visual-structure.md
  - ../../prompts/x-longpost-design-thumbnail-prompt.md
  - ../../prompts/x-longpost-design-diagram-prompt.md
schema_refs:
  - references/visual-spec.json
  - references/thumbnail-specs.md
completeness_exempt:
  - "manifest: 固定手順の正本は本 SKILL.md と plugin-composition.yaml の依存 DAG。workflow-manifest を別に持つと生成順序と図解 optional 条件が二重管理になるため持たない。"
script_refs:
  - ../../scripts/build-visual-prompts.js
  - ../../scripts/generate-images-codex.js
  - ../../scripts/lint-thumbnail-prompt.js
  - ../../scripts/validate-visual-assets.js
  - ../../scripts/record-thumbnail-review.js
  - ../../scripts/embed-visual-paths.js
  - ../../scripts/check-no-emoji.js
  - ../../scripts/log_usage.js
feedback_contract:
  activation_state: semantic_evaluator_started
  max_iterations: 3
  criteria:
    - id: IN1
      loop_scope: inner
      text: "visual-structure.json に対して build-visual-prompts.js が exit 0 を返すこと（ゾーン数・字数・禁止語・絵文字の全制約を満たすこと）"
      verify_by: script
    - id: IN2
      loop_scope: inner
      text: "標準生成したサムネイル2枚に対して validate-visual-assets.js の既定 strict 検証が exit 0 を返すこと（PNG署名・寸法・比率・不透明背景・規定色）"
      verify_by: script
    - id: IN3
      loop_scope: inner
      text: "サムネイル2種の .prompt.txt に対し、visual-structure.json を --structure で渡した lint-thumbnail-prompt.js が exit 0 を返すこと（TL-01〜TL-12）"
      verify_by: script
    - id: OUT1
      loop_scope: outer
      text: "確定した長文投稿1本を与えた実起動で、pre-choice に x-thumb と note-thumb の2枚を生成・検証・現物表示すること。accept-as-is はその2枚を採用し、図解は明示指定時のみ optional で作ること"
      verify_by: live-trial
    - id: OUT2
      loop_scope: outer
      text: "生成された図解が本文の論理構造を表しており diagram-style-canon.md §5 の退化が無いこと、およびサムネイル2種に thumbnail-style-canon.md §5 の退化（人物の混入・情報商材化・図解化・アクセント散乱）が無いと書き手が判断できること"
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

## Pre-choice usable artifact execution

最小の実成果物は **x-thumb 5:2 + note-thumb 実 PNG 1280x670 の2枚**。main context で両方を作成し、strict 機械検証の後、各 `presentation.absolutePath` と同じ絶対パスを Read / view_image で開く。五つの目視項目を全て PASS として review receipt に画像 SHA256 とともに記録し、その2枚を実物提示する。**accept-as-is は2枚をそのまま採用して embed する。**

## Post-choice selected improvement execution

このゲートの対象は**サムネイルの画風の作り直し・構造の組み替え・追加案の生成**の3種である。light / standard / detailed では選択範囲だけ改善し、再検証・再表示・review receipt の再記録後に2枚を embed する。図解はこの選択ゲートと独立した optional 成果物で、明示指定時に `--only diagram` で作る。

# X長文投稿のサムネイル・図解生成

確定した長文投稿パターンAから X・note のサムネイル2枚を作る。冒頭の図解は明示指定時のみ追加する。

**長文投稿そのものを作るのは `run-x-longpost-create`。** 本スキルはその成果物を入力に取る。

## 設計原則

| 原則 | 説明 |
|------|------|
| **構造解釈は1箇所** | 標準2枚と optional 図解は1つの `visual-structure.json` から派生させる。解釈のずれをこの1箇所で防ぐ |
| **Script First** | 文字ルール・PNG署名・寸法・比率・透過の有無・背景色は機械で止める。絵として何が描かれたかの判断だけを人間の目に残す |
| **課金前に止める** | 画像生成は課金される。構造データ（`build-visual-prompts.js`）とプロンプト文（`lint-thumbnail-prompt.js`）の2層を生成**前**に置き、出力を見て直すループの回数そのものを減らす |
| **目的が違えば画風も違う** | 図解は「理解させる絵」、サムネイルは「足を止める絵」である。サムネイルは図解の画風規範を継承せず、`thumbnail-style-canon.md` を独立した正本として持つ |
| **退化を名指しで禁じる** | 拡散モデルは放置するとコード描画や平坦ボックスへ退化する。禁止対象を列挙して初めて防げる |

---

## 実行環境

パス変数・依存ランタイム（Node.js v18 以上）の定義は `run-x-longpost-create` SKILL.md「実行環境」と共通。加えて本スキルは次を使う。

| 変数 | 意味 | 未設定時 |
|------|------|----------|
| `XLP_IMAGE_DIR` | その投稿専用の画像・中間生成物の作業先 | 明示指定する。投稿ごとに分け、固定名 `diagram.png` を他投稿と共有しない |
| `XLP_ATTACHMENT_DIR` | 検証済み画像の Obsidian 添付先 | env → `${XLP_VAULT_ROOT}/02_Configs/Extra` の2段。どちらも未解決なら最終差し込み前に停止する |
| `CODEX_HOME` | codex の状態ディレクトリ。生成画像の回収基点 | `~/.codex` |
| `XLP_CODEX_BIN` | 画像生成に使う codex 実行ファイル。パスまたは PATH 上のコマンド名 | `codex` |
| `XLP_REFERENCE_IMAGE_DIR` | 画風の見本画像の置き場 | plugin 同梱の `assets/reference-images/`。利用者固有の見本へ差し替えるときだけ指定する |

`generate-images-codex.js` は shell alias を解決しない。`XLP_CODEX_BIN`（既定 `codex`）を PATH または明示パスから解決し、実在・実行権限を課金ループ前に検査する。実行不能なら retry せず終了コード2で停止する。起動は executable + argv で行い、stdin は ignore、stdout/stderr は回収用ログ fd へ接続する。

画風は**文章と絵の2経路**で渡す。文章は `{kind}.prompt.txt` と、`generate-images-codex.js` が `visual-spec.json` の palette から kind ごとに組む起動指示文である。絵は `assets/reference-images/` の見本を `codex exec -i` で添付する。線の太さ・塗りの密度・簡略度は数値へ落とすと窮屈になるため、絵で渡すほうが正確に伝わる。

見本は**複製の対象ではない**。構図・文言・個々のアイコンを写されると、どの投稿でも同じ絵になり本文の構造を表す図解にならないため、指示文で複製を名指しで禁じている。宣言だけあって実体が無い見本は毎回 WARN として出力と `meta.json` の `referenceImages` に記録され、`--require-reference-images` を付けると FAIL になる。

`codex exec` が内蔵 imagegen で作った画像は、まず `${CODEX_HOME}/generated_images/<session-id>/` に現れる。`generate-images-codex.js` が PNG 署名を確かめて `${XLP_IMAGE_DIR}/{kind}.png` へ回収し、絶対パスとホスト別の表示指示を JSON で返す。呼び出し経路は **Claude Code / Codex → `codex exec` → Codex imagegen → session 画像回収 → 指定作業フォルダの PNG → 現物表示** である。

---

## 絶対遵守ルール（最優先）

**画像生成は課金される。** 1枚あたり概ね 1〜2 分かかり、標準の2枚で2回、optional 図解も作る場合は追加で1回の課金が発生する。プロンプトを確定する前に `--dry-run` で組み立てたコマンドを目視する。

**絵文字は一切使用しない**。画像内・プロンプト内・ファイル名のすべてで禁止する。検証は `node "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/check-no-emoji.js" --file "[prompt.txt]"`。定義境界の正本は `ref-x-longpost-canon`「絵文字の定義（判定境界）」にある。

**「僕」「私」という文字を画像に入れない**。図解では一人称の主体を人物アイコンの位置だけで表す（VS-07）。**サムネイルには人物そのものを描かない**（TS-03）。

**サムネイルは図解の STYLE を複写しない**。純白背景と赤アクセントを持ち込むと、貼り先の白い UI に溶けるか煽りの記号に読み替えられる。配色の正本は `visual-spec.json` の `palettes.thumbnail` にあり、`lint-thumbnail-prompt.js` が混入を機械検出する。

**パターンAが確定する前に実行しない**。確定前の本文で図解を作ると、本文の修正が図解に反映されないまま残る。

---

## クイックスタート

```bash
# 1. 構造解析（LLM）→ visual-structure.json を書く
# 2. 標準: 構造検証とサムネイル2種の meta 生成
node "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/build-visual-prompts.js" \
  --structure "${XLP_IMAGE_DIR}/visual-structure.json" --out-dir "${XLP_IMAGE_DIR}" --only x-thumb,note-thumb
# 3. 二つの prompt を設計し、課金前に構造と完全一致するか検査
node "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/check-no-emoji.js" --file "${XLP_IMAGE_DIR}/x-thumb.prompt.txt"
node "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/check-no-emoji.js" --file "${XLP_IMAGE_DIR}/note-thumb.prompt.txt"
node "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/lint-thumbnail-prompt.js" --image-dir "${XLP_IMAGE_DIR}" \
  --structure "${XLP_IMAGE_DIR}/visual-structure.json"
node "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/generate-images-codex.js" --image-dir "${XLP_IMAGE_DIR}" --only x-thumb,note-thumb
node "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/validate-visual-assets.js" --image-dir "${XLP_IMAGE_DIR}" --only x-thumb,note-thumb --strict
# 4. 戻り値 results[].presentation の2つの absolutePath を Read / view_image で開き、各画像を記録
node "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/record-thumbnail-review.js" --image-dir "${XLP_IMAGE_DIR}" --kind x-thumb --host "[claude-code|codex]" --no-people PASS --no-info-product PASS --text-readable-correct PASS --gentle-off-white PASS --impact PASS
node "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/record-thumbnail-review.js" --image-dir "${XLP_IMAGE_DIR}" --kind note-thumb --host "[claude-code|codex]" --no-people PASS --no-info-product PASS --text-readable-correct PASS --gentle-off-white PASS --impact PASS
# 5. accept-as-is はこの2枚を採用
node "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/embed-visual-paths.js" --file "[投稿ファイル]" --image-dir "${XLP_IMAGE_DIR}" --attachment-dir "${XLP_ATTACHMENT_DIR}" --only x-thumb,note-thumb
```

---

## 入力要件

| 入力 | 必須 | 内容 |
|------|------|------|
| 投稿ファイル | 必須 | `run-x-longpost-create` が出力した `.md`。パターンAの本文・確定タイトル・キャッチコピーを含むもの |
| `--only` | 任意 | `diagram` / `x-thumb` / `note-thumb` をカンマ区切りで限定。1枚だけ作り直すときに使う |

---

## 出力設定

| 成果物 | パス | 用途 |
|--------|------|------|
| 構造データ | `${XLP_IMAGE_DIR}/visual-structure.json` | 標準2枚と optional 図解に共通する解釈の正本 |
| プロンプト | `${XLP_IMAGE_DIR}/{kind}.prompt.txt` | 画像内テキストの単一正本。`.md` にしない（Obsidian が vault 内の `.md` を同期取り込みして消すため） |
| メタ | `${XLP_IMAGE_DIR}/{kind}.meta.json` | 生成寸法と出自（`source` は生成後に `codex-image2` へ更新される） |
| 画像 | `${XLP_IMAGE_DIR}/{kind}.png` | 検証・目視用の作業成果物 |
| 確認 receipt | `${XLP_IMAGE_DIR}/{kind}.review.json` | 開いたホスト・ツール、5項目の PASS、確認時点の画像 SHA256 |
| 投稿添付画像 | `${XLP_ATTACHMENT_DIR}/[投稿basename]-{kind}.png` | 投稿ごとに一意な納品物。本文は実運用投稿と同じ `![[basename]]` で参照 |

`{kind}` は `diagram` / `x-thumb` / `note-thumb` の3種である。

---

## ワークフロー

Phase 4.1（構造解析）→ Phase 4.2（プロンプト設計）→ Phase 4.3（生成）→ Phase 4.4（検証・差し込み）の順に進む。

各 Phase がどの `prompts/*.md` を Read するかは「実行手順」に書く。図解とサムネイルは同じ構造データを共有するため、**構造解析は1回だけ行い、標準2枚と明示指定された optional 図解を派生させる**。

---

## リソース一覧

| 正本 | 内容 |
|------|------|
| [references/diagram-style-canon.md](references/diagram-style-canon.md) | 図解の絶対ルール VS-01〜VS-10・三分割版面・構造型 T1〜T4・退化パターン |
| [references/icon-vocabulary.md](references/icon-vocabulary.md) | アイコンの粒度の見本 |
| [references/thumbnail-style-canon.md](references/thumbnail-style-canon.md) | サムネイルの絶対ルール TS-01〜TS-12・インパクトの作り方・情報商材的意匠の禁止リスト・退化パターン |
| [references/thumbnail-specs.md](references/thumbnail-specs.md) | サムネイル2種の寸法と版面 |
| [references/visual-spec.json](references/visual-spec.json) | kind・生成/納品寸法・比率・palette・背景規則・横断 text rule の機械可読正本 |
| [references/resource-map.yaml](references/resource-map.yaml) | 「いつ何を開くか」の機械可読索引 |

規定が食い違って見えたときの決着は `ref-x-longpost-canon` が正本索引として担う。

---

## Runtime root contract

- `runtime_root_policy: host-skill-path` を適用する。
- Claude Codeでは `CLAUDE_PLUGIN_ROOT` をplugin rootとして使用する。
- Codexではホストが提示したこの `SKILL.md` のabsolute pathから、plugin manifestを持つ祖先を上方探索して論理 `PLUGIN_ROOT` を解決する。
- `cwd` からplugin rootを推測せず、literal placeholderをshellへ渡さない。各shell invocation内で解決済みabsolute pathを `PLUGIN_ROOT` に設定する。
- `prompts/` 配下はこのowner Skill契約を継承する。

## 実行手順

### Step 1: 構造解析（Phase 4.1・LLM）

`${XLP_PROMPTS_DIR}/x-longpost-analyze-visual-structure.md` を Read し、投稿のパターンAから `${XLP_IMAGE_DIR}/visual-structure.json` を作る。

### Step 2: pre-choice の標準サムネイル2枚（Phase 4.2〜4.4）

`x-longpost-design-thumbnail-prompt.md` を Read し、`x-thumb.prompt.txt` と `note-thumb.prompt.txt` を作る。両者の STYLE / TYPOGRAPHY / NEGATIVE は完全一致させる。

```bash
node "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/build-visual-prompts.js" \
  --structure "${XLP_IMAGE_DIR}/visual-structure.json" --out-dir "${XLP_IMAGE_DIR}" --only x-thumb,note-thumb
node "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/lint-thumbnail-prompt.js" --image-dir "${XLP_IMAGE_DIR}" \
  --structure "${XLP_IMAGE_DIR}/visual-structure.json"
node "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/generate-images-codex.js" --image-dir "${XLP_IMAGE_DIR}" --only x-thumb,note-thumb --dry-run
node "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/generate-images-codex.js" --image-dir "${XLP_IMAGE_DIR}" --only x-thumb,note-thumb
node "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/validate-visual-assets.js" --image-dir "${XLP_IMAGE_DIR}" --only x-thumb,note-thumb --strict
```

生成 JSON の `results[].presentation` にある x-thumb / note-thumb の各 `absolutePath` は、指定した `${XLP_IMAGE_DIR}` に回収された同じ PNG の絶対パスである。2枚のどちらも、実行ホストに応じて必ず開く。

- **Claude Code**: `Read` ツールで二つの `presentation.absolutePath` をそれぞれ開く
- **Codex**: `view_image` に同じ二つの絶対パスをそれぞれ渡す

ファイル名、パス、サイズ、検証の PASS 表示だけでは `present_actual_artifact` とみなさない。各2枚で no people / no info-product / readable and correct text / gentle off-white / impact を目視し、`record-thumbnail-review.js` で全項目 PASS と画像 SHA256 を receipt へ記録した後にだけ `artifact_presented` へ進む。

### Step 3: 選択ゲート

- `accept-as-is`: 提示した2枚を採用し、`--only x-thumb,note-thumb` で embed する
- `light / standard / detailed`: 選ばれた範囲で2枚を改善し、再検証・再表示・receipt 更新後に embed する

### Step 4: review receipt と最終 embed

サムネイル2本は `lint-thumbnail-prompt.js --structure` の TL-01〜TL-12 を満たし、生成後は下記の手順で receipt を作る。

```bash
node "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/build-visual-prompts.js" \
  --structure "${XLP_IMAGE_DIR}/visual-structure.json" --out-dir "${XLP_IMAGE_DIR}" --only x-thumb,note-thumb
node "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/check-no-emoji.js" --file "${XLP_IMAGE_DIR}/x-thumb.prompt.txt"
node "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/check-no-emoji.js" --file "${XLP_IMAGE_DIR}/note-thumb.prompt.txt"
node "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/lint-thumbnail-prompt.js" --image-dir "${XLP_IMAGE_DIR}" --structure "${XLP_IMAGE_DIR}/visual-structure.json"
node "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/generate-images-codex.js" --image-dir "${XLP_IMAGE_DIR}" --only x-thumb,note-thumb --dry-run
node "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/generate-images-codex.js" --image-dir "${XLP_IMAGE_DIR}" --only x-thumb,note-thumb
node "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/validate-visual-assets.js" --image-dir "${XLP_IMAGE_DIR}" --only x-thumb,note-thumb --strict
node "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/record-thumbnail-review.js" --image-dir "${XLP_IMAGE_DIR}" --kind x-thumb --host "[claude-code|codex]" --no-people PASS --no-info-product PASS --text-readable-correct PASS --gentle-off-white PASS --impact PASS
node "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/record-thumbnail-review.js" --image-dir "${XLP_IMAGE_DIR}" --kind note-thumb --host "[claude-code|codex]" --no-people PASS --no-info-product PASS --text-readable-correct PASS --gentle-off-white PASS --impact PASS
node "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/embed-visual-paths.js" \
  --file "[投稿ファイルの絶対パス]" --image-dir "${XLP_IMAGE_DIR}" \
  --attachment-dir "${XLP_ATTACHMENT_DIR}" --only x-thumb,note-thumb
```

`embed-visual-paths.js --only x-thumb,note-thumb` は二つの slot / image / PASS receipt を事前検証し、receipt の SHA256 が現在の PNG と一致するときだけ差し込む。図解を明示的に追加する optional 経路では `x-longpost-design-diagram-prompt.md` を Read し、`diagram.prompt.txt` を作り、build / generate / validate のすべてに `--only diagram` を付ける。この経路は標準2枚を省略する理由にはならない。

---

## ベストプラクティス

| すべきこと | 避けるべきこと |
|-----------|---------------|
| 本文の主張をそのまま図に写す | 図解で新しい主張を足す |
| 標準2枚の線の太さと簡略度をそろえ、optional 図解とは構図を分ける | サムネイルに図解を縮小して流用する / 図解の人物シルエットをサムネイルへ持ち込む |
| インパクトは余白と要素削減で作る（TS 規範 §2） | 縁取り文字・爆発マーク・高彩度で目立たせる |
| 退化したら作り直す | 崩れた日本語を残したまま差し込む |
| `--dry-run` で先に目視する | 制約違反のまま生成して課金を重ねる |

---

## フィードバック（必須）

実行の記録は `log_usage.js` に残す。

```bash
node "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/log_usage.js" --result success --phase "Phase 4" --agent x-longpost-analyze-visual-structure
```

## Anchors（設計の根拠）

- 版面と構造型は利用者提供のサンプル図解4枚から抽出した（2026-08-31）。4枚すべてが三分割の骨格を共有していたため、これを規範として固定した
- 画像生成の事故対策（PNG署名検証・session dir からの回収・imagegen の明示強制・stdin クローズ）は `slide-report-generator` の同名スクリプトで実証済みのものを移植した
- 「僕」を画像に入れない規定は、サンプル画像の実態ではなく利用者提供プロンプトの原文を正とする判断による（2026-08-31 に利用者が確定）
- サムネイルの画風を図解から分離したのは、利用者提供のサムネイル用プロンプト（人物禁止・優しい白っぽい背景・情報商材的でないインパクト）が図解規範の VS-02 / VS-03 と正面から矛盾したためである。どちらかを曲げるのではなく、目的の違う2つの正本に分けた（2026-08-31）
- 配色はオフホワイト #F8F3E6 / 墨黒 #1A1A1A / セージ #C1C2A0（構造）/ テラコッタ #D87C45（帯1枚）に確定した。当初は藍 #2F4858 の1アクセント案だったが、利用者が実際に良いと判断した生成物から実測した値へ寄せ直した（2026-08-31）。アクセントは色数ではなく**役割**で縛る（TS-05）。実体は `visual-spec.json` の `palettes.thumbnail` にあり、差し替えは同ファイルの1箇所で完結する。色を足したときは `lint-thumbnail-prompt.js` の TL-02 が自動で検査対象に含める
