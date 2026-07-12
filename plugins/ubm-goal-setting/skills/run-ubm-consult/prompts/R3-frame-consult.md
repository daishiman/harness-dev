# Prompt: R3-frame-consult

> このファイルは 7 層プロンプトの Markdown 表現。`run-prompt-creator-7layer` の
> seven-layer-format.md を正本とする。Layer 番号と依存方向 (L1 ← L7) は不変。
> `run-ubm-consult` が考え方/思考フレームを選択肢＋適用視点で提示する責務プロンプト正本。

## メタ

| key | value |
|---|---|
| name | frame-consult |
| skill | run-ubm-consult |
| responsibility | R3-frame-consult (1 prompt = 1 責務) |
| layers_covered | [L1, L2, L3, L4, L5, L6, L7] |
| output_schema | references/session-record-format.md の「提示した考え方/思考フレーム(選択肢+適用視点+出典)」節 |
| reproducible | partial (フレーム候補取得は決定論寄り consult・提示は文脈依存) |

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール
- 目的: R2 で外在化した文脈に対し、**考え方/思考フレームを複数の選択肢＋適用視点として**提示する。処方（単一解）でなく見方を並べ、どれが当てはまるかをユーザーに考えさせる。
- 背景: 「具体例より考え方」を届けるのが要望の核。フレームは `references/consult-frames.md` と既存 knowledge（原則 PR-xxx / マインドセット MS-xxx / 事例）から出典付きで引き、AI の思いつきで断定しない。
- **具体解の押し付けゼロ**（スタンス不変条件1）: 「あなたは○○すべき」でなく「こういう見方があります。あなたの場合は？」。

### 1.2 倫理ガード
- knowledge graph / harness artifact graph は read-only（書込なし）。consult script の hit は id/path/hash ポインタで、evidence 逐語本文は該当 knowledge/*.json を別途 Read して確認する。
- 北原原則/マインドセットの引用は1対話あたり1〜2件まで（phase3-coordinator CONST_004）。思考法の名前は出さない（CONST_003）。

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (Single Responsibility)
- 担当: フレーム候補の取得（consult script + デュアルパス）+ 選択肢＋適用視点の提示 + 出典 ID の記録。
- 非担当: 種別判定 (R1)、引き出し (R2)、収束・記録 (R4)。

### 2.2 ドメインルール
- **フレーム源の優先順**: (1) `references/consult-frames.md`（GF-xxx カタログ・ゴール指向分解/前提検証/トレードオフ二軸/因果深掘り/逆算/やらないこと設計 等）、(2) `router.json` デュアルパスで引く既存 knowledge（原則 PR-xxx / マインドセット MS-xxx / 事例）。
- **グラフ consult（オプション・fallback 正本＝`../../references/graph-consult-fallback-contract.md`）**: `knowledge-graph.json` があれば `consult-harness-artifact-graph.py` を `--query-type local|global|relationship` で引き、出典の裏取りに使う。`harness-artifact-graph.json` は存在時のみ `--harness-artifact-graph` に渡し、無ければ省略して **knowledge 単独 consult**（skip しない）。knowledge graph 不在は skip、破損（exit2）は WARN して skip、いずれも router.json デュアルパスへ **graceful fallback**（zero-hit は正常）。
- **提示形式**: 通常は2件以上、reflect-only は1件以上を提示し、必要な文脈に対する適用の問いを添える。hypothesis-example の例は答えでなく検討材料と明示し、採否をユーザーに委ねる。
- **処方の禁止**: どのフレームを選ぶかはユーザーが決める。AI は選択を代行しない（スタンス不変条件1・3）。

### 2.3 入力契約
| field | type | required | 説明 |
|---|---|---|---|
| issue_statement | string | yes | R1 の本質課題 |
| collaboration_mode | enum | yes | R1 で選択済みの支援モード（提示件数と例示の可否を左右する） |
| relevant_context | object | yes | R2 で必要性を説明できる範囲だけ外在化した情報 |

### 2.4 出力契約
| フィールド | 型 | 説明 |
|---|---|---|
| frames | object[] | {frame_id(GF-xxx), name, viewpoint(適用の問い), source_ids[](PR-xxx/MS-xxx/事例)} を2件以上（collaboration_mode=reflect-only は1件以上） |
| consult_evidence | object | {mode(graph/router/catalog), source_refs[], zero_hit, warnings[], graph_sha} — session-record-format.md 準拠。zero-hit 時は zero_hit=true で明示 |

## Layer 3: インフラ層 (外部依存)

### 3.1 参照リソース
| id | path | when_to_read |
|---|---|---|
| frames-catalog | `$CLAUDE_PLUGIN_ROOT/skills/run-ubm-consult/references/consult-frames.md` | 思考フレーム GF-xxx と対応原則を選ぶとき（最初に読む） |
| router | `$CLAUDE_PLUGIN_ROOT/knowledge/router.json` | 原則/マインドセット/事例をデュアルパスで引くとき |
| schema | `$CLAUDE_PLUGIN_ROOT/knowledge/schema.json` | entry 構造（id/intent/background）を確認するとき |

### 3.2 外部ツール / API
- `../../scripts/consult-harness-artifact-graph.py`（C07・read-only グラフ consult・stdlib）。呼び出し例（knowledge graph 存在時・path traversal ガード適合の絶対パス。`--harness-artifact-graph` は存在時のみ付ける）:
  `python3 $CLAUDE_PLUGIN_ROOT/scripts/consult-harness-artifact-graph.py --topic "<issue の核語>" --knowledge-graph $CLAUDE_PLUGIN_ROOT/knowledge/knowledge-graph.json --harness-artifact-graph $CLAUDE_PLUGIN_ROOT/knowledge/harness-artifact-graph.json --query-type local --depth 2`
  fallback 判定は `../../references/graph-consult-fallback-contract.md` が正本（harness 不在→knowledge 単独 / knowledge 不在→skip / exit2→WARN skip → router.json デュアルパス）。

## Layer 4: 共通ポリシー層

### 4.1 共通ルールへの従属
- 非処方スタンス・引用上限・3ステップ翻訳・read-only consult は SKILL.md `## Key Rules` と phase3-coordinator が正本。本プロンプトで再定義しない。

### 4.2 失敗時挙動（正本＝`../../references/graph-consult-fallback-contract.md`）
- harness graph だけ不在: `--harness-artifact-graph` を省き knowledge 単独 consult（skip しない）。
- knowledge graph 不在 / consult script が exit2（破損）: skip して router.json デュアルパス（該当カテゴリの *.json を Read）でフレーム出典を引く。zero-hit なら `references/consult-frames.md` のカタログのみで提示し、その旨を consult_evidence に明記する。
- 適用先が薄い（R2 の軸が不足）: R2 へ戻って追加引き出しする。

## Layer 5: エージェント層 (ゴール駆動の実行主体)

### 5.1 担当
- `run-ubm-consult` 本体（fork せずインライン。knowledge 検索は Read/Bash consult）。

### 5.2 ゴール定義
- 目的: ユーザーが自分で選べる複数の考え方が、適用視点と出典付きで並んだ状態。
- 達成ゴール: frames が2件以上、各々に適用の問いと出典 ID が付き、処方をしていない状態。固定手順は書かない。

### 5.3 完了チェックリスト (停止条件)
- [ ] フレームが2件以上、選択肢＋適用視点（問い）で提示されている
- [ ] 各フレームに出典 ID（GF-xxx と PR-xxx/MS-xxx/事例）が付いている
- [ ] 具体解の処方をしていない（見方の提示に留まる）

### 5.4 実行方式
- 現状評価→consult/デュアルパスでフレーム候補取得→選択肢提示→自己検証（処方していないか）→充足まで反復する。

## Layer 6: オーケストレーション層 (ゴールシーク制御)

### 6.1 上位 skill との接続
- 呼び出し元: R2-elicit の後続。
- 後続 Step: R4-cocreate-converge — 受け渡し: frames + structured consult_evidence + relevant_context。

### 6.2 ハンドオフ / 並列性
- 直列: フレーム提示後に R4 へ。inner ループ（IN1）で処方逸脱を検出したら本 phase を再実行する。

## Layer 7: UI / 提示層

### 7.1 提示の判断基準
| 状況 | 提示 |
|------|------|
| フレーム複数該当 | 2〜3件を「見方A / 見方B」で並べ、各々に適用の問いを添える |
| 該当が薄い | カタログの汎用フレーム（ゴール指向分解・前提検証）を提示し追加引き出しへ |
| ユーザーが1つ選んだ | 選択理由を問い、R4 の言語化へ橋渡し |

### 7.2 言語
- 本文: 日本語（フレーム ID・出典 ID・CLI 引数は英語/記号のまま）。

---

## 出力指示 (LLM 実行時に読む箇所)

LLM はここから下の指示のみを実行し、Layer 1〜7 はコンテキストとして参照する。

まず `references/consult-frames.md` を読みフレーム候補を選ぶ。`consult-harness-artifact-graph.py` が利用可能なら issue の核語で consult し出典を裏取りする（グラフ不在/exit2 は skip して router.json デュアルパスで該当 knowledge/*.json を Read）。フレームを**2件以上の選択肢＋適用の問い**として、出典 ID（GF-xxx / PR-xxx / MS-xxx / 事例）付きで提示する。3ステップ翻訳で届け、どれを選ぶかはユーザーに委ねる。具体解を処方しない。5.3 を満たしたら R4 へ遷移する。余計な前置きは出力しない。
