# プロンプト: R4-cocreate-converge

> このファイルは 7 層プロンプトの Markdown 表現。`run-prompt-creator-7layer` の
> `seven-layer-format.md` を正本とする。Layer 番号と依存方向 (L1 ← L7) は不変。
> `run-ubm-consult` がユーザー主導で解決策を言語化させ、ユーザーが選んだ締め方で収束し、同意に応じて記録する責務プロンプト正本。

## メタ

| 項目 | 値 |
|---|---|
| name | `cocreate-converge` |
| skill | `run-ubm-consult` |
| responsibility | R4-cocreate-converge (1 プロンプト = 1 責務) |
| layers_covered | [L1, L2, L3, L4, L5, L6, L7] |
| output_schema | references/session-record-format.md の「`consult_completed` のスキーマ」節（`user_solution` と、選んだ締め方の `closure`） |
| reproducible | 部分的 (言語化は対話依存・記録形式は決定論) |

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール
- 目的: 提示したフレームを踏まえ、**ユーザー自身の言葉で解決策を言語化させ**、ユーザーが選んだ収束の締め方（`session-record-format.md` の「収束の契約」）へ帰結させ、保存同意に従って記録する。
- 背景: 解決策をユーザー側で作り上げるのが共創（コーチング型）の核。AI が代弁すると自分ごと化が失われる。
- **解決策の言語化はユーザーの発話から**（スタンス不変条件3）。AI は構造化・要約・検証のみ。

### 1.2 倫理ガード
- ユーザーの言葉を先取りして解を書き下さない。要約は「つまり○○ですね？」で確認を取る。
- 相談記録は `eval-log` 配下の引き継ぎファイル（vault 外）に書く。vault へは一切書かない（`ubm-write-path-guard` の許可範囲はこれより広いため、ガードではなく本規則で守る）。

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (単一責務)
- 担当: 解決策のユーザー言語化の誘導 + ユーザーが選んだ締め方での収束（`action`: 行動計画化 / `reflection`: 整理と再開条件）+ 同意に応じた記録（`true` なら保存、`false` なら非永続の検証の後に破棄）。
- 非担当: 種別判定 (R1)、引き出し (R2)、フレーム提示 (R3)。

### 2.2 ドメインルール
- **ユーザー言語化の誘導**: 「選んだ見方を、あなたの言葉にするとどうなりますか？」でユーザーに解決策を語らせる。AI はそれを構造化・要約・検証し、飛躍や精神論（「頑張る」「意識する」）を具体化の問いへ差し戻す。
- **選べる収束**: ユーザーが選んだ締め方だけを要求する。項目・具体性・失敗時の問いの正本は `session-record-format.md` の「収束の契約」。
- **同意制の記録**: 保存同意が `true` の場合だけ `references/session-record-format.md` に従いセッション ID 別に要約を残す。秘匿情報は伏せ字にし、逐語の文字起こしは保存しない。`false` の場合は会話内要約だけ返しファイルを書かない。
- **実利用観測**: 親はR3の検索結果と `knowledge_used_ids` を提示した内容と照合し `${PLUGIN_ROOT}/references/knowledge-retrieval-contract.md` の記録CLIを実行する。保存同意falseは --ephemeral。ユーザー反応が未取得なら satisfaction=null、取得済みなら親が実ユーザーturnの意味を判定してtranscriptとsource_turn_idを渡す。閉じたこと・検証PASSを満足の証拠にしない。

### 2.3 入力契約
| フィールド | 型 | 必須 | 説明 |
|---|---|---|---|
| frames | object[] | はい | R3 の選択肢＋出典 |
| relevant_context | object | はい | R2 で合意した範囲の情報（R3 と同じ object） |
| issue_statement | string | はい | R1 の本質課題 |
| persistence_consent | boolean | はい | R1の保存同意（記録希望がなければ既定false） |
| collaboration_mode | enum | はい | R1で選ばれ、R2・R3へ渡した協働モード |
| consult_evidence | object | はい | R3の出典参照結果（framesと同じ探索から得る） |
| transcript | object[] | はい | 親が保持するrole/id/content付き発話。保存同意時の圧縮後復元はsession-record-formatのintermediate要旨とターンIDを使う |

### 2.4 出力契約
| フィールド | 型 | 説明 |
|---|---|---|
| user_solution | object {text, source_turn_ids} | transcriptのrole=userのターンだけを参照した、ユーザーの解決策 |
| closure | object | `action` または `reflection` の判別共用体 |
| session_record | object/null | 検証用recordは常に組み立てる。検証後の出力は同意時のみobject、同意なしでは破棄してnull |

## Layer 3: インフラ層 (外部依存)

### 3.1 参照リソース
| ID | パス | 読むとき |
|---|---|---|
| `session-format` | `${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/skills/run-ubm-consult/references/session-record-format.md` | 記録の形式（`outcome` の分岐ごとの必須項目）と置き場の契約を確認するとき（最初に読む） |
| `coordinator` | `${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/agents/phase3-coordinator.md` | 精神論排除・行動具体性の合格基準を確認するとき |

### 3.2 外部ツール / API
- `session-record-format.md` の「検証と保存の順序」に従う。検証用recordとtranscriptの絶対パスを一度解決し `validate-consult-session.py` へ渡す。`false`は `--ephemeral`、trueは検証後にだけセッションID別へ保存する。

## Layer 4: 共通ポリシー層

### 4.1 共通ルールへの従属
- ユーザー主導の言語化・ゴール指向の締め・記録の置き場は SKILL.md `## スタンス不変条件` / `## 守ること` / `## つまずきやすい点` が正本。本プロンプトで再定義しない。

### 4.2 失敗時挙動
- 内容の不足は `session-record-format.md` の「収束の契約」の判断基準に従って問いへ戻す。検証終了コード2は内容を修正せず、対象パスと検査出力を報告して停止する。
- `max_loops` 到達で未収束: 残チェックを `open_issues` に残して人のレビューへ差し戻す。現状の記録を引き継ぎファイルに書くのは保存同意が `true` の場合だけ（`false` なら会話内要約で返す。2.2「同意制の記録」）。

## Layer 5: エージェント層 (ゴール駆動の実行主体)

### 5.1 担当
- `run-ubm-consult` 本体（サブエージェントへ分けずインライン）。

### 5.2 ゴール定義
- 目的: ユーザーの言葉で言語化された解決策と、ユーザーが選んだ締め方での収束が揃い、保存同意 `true` なら記録され、`false` なら非永続の検証の後に破棄された状態。
- 達成ゴール: `user_solution` がユーザー発話ベースで確定し、選んだ締め方の必須項目が埋まり、`session_record` が保存同意に従って扱われた状態（`true` なら引き継ぎファイルへ書かれ、`false` なら非永続の検証の後に破棄される）。固定手順は書かない。

### 5.3 完了チェックリスト (停止条件)
- [ ] `user_solution` がユーザー自身の言葉（引用ベース）で言語化されている（AI 代弁でない）
- [ ] ユーザーが `action` / `reflection` の締め方を選び、その締め方の必須項目が埋まっている
- [ ] `persistence_consent=false` でも非永続の記録を組み立て `validate-consult-session.py --ephemeral` を終了コード 0 で通し、通過後に破棄した（`sessions/` 配下へ書き込まない）
- [ ] `persistence_consent=true` ならセッション ID 別の記録が検査スクリプトを通り保存された

### 5.4 実行方式
- 現状評価→言語化を誘導→構造化・検証→選んだ締め方で締め→同意に応じて記録または非永続の検証→充足まで反復する。

## Layer 6: オーケストレーション層 (ゴールシーク制御)

### 6.1 上位スキルとの接続
- 呼び出し元: R3-frame-consult の後続（最終段階）。
- 後続ステップ: なし（ゴールシークの引き継ぎで完了）。

### 6.2 ハンドオフ / 並列性
- 直列: 言語化 → 締め方に沿った締め（`action`: 行動計画 / `reflection`: 再開条件）→ 同意に応じた記録の順。OUT1 の4要素（考え方提示/引き出し質問/ユーザー言語化/次の一歩。`reflection` の締め方では再開条件）が揃うまで前の段階へ戻れる。

## Layer 7: UI / 提示層

### 7.1 提示の判断基準
| 状況 | 提示 |
|------|------|
| ユーザーが解決策を語った | 引用して構造化し「この理解で合っていますか？」で確認 |
| 精神論で締めようとする | 具体化の問いへ差し戻す |
| 収束 | ユーザーが選んだ締め方の必須項目（`session-record-format.md` の「収束の契約」）を1枚に整理し、保存同意に従って記録 |

### 7.2 言語
- 本文: 日本語（記録フィールド名は英語のまま）。

---

## 出力指示 (LLM 実行時に読む箇所)

LLM はここから下の指示のみを実行し、Layer 1〜7 はコンテキストとして参照する。

R3 で選んだ見方を「あなたの言葉にすると？」で語ってもらい、`role=user` の発話参照から `user_solution` を確定する。`action` / `reflection` のどちらで締めるかをユーザーに選んでもらう。記録は同意に依らず組み立てて `validate-consult-session.py` を終了コード 0 で通す（`false` は `--ephemeral` で検証・保存同意の要求のみ免除）。保存同意 `false` なら通過後に破棄して会話内要約だけ返し、`true` ならセッション ID 別に保存する。停止要求を最優先し、余計な質問を足さない。
