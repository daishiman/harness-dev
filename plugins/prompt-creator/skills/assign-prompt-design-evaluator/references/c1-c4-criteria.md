# C1-C4 評価基準 (人間向け詳細)

> `prompt-rubric.json` (v2.0.0) の機械可読版を解説。`../../run-prompt-creator-7layer/references/quality-criteria.md` §7 と整合。
> C3/C4 の判定対象 (L5 サブ構造 5.1-5.4) と合格条件は `run-prompt-creator-7layer/references/seven-layer-format.md`「Layer 5 契約」(l5-contract v2.0.0) に従属する。
> 旧構成前提の基準 (5.2 推論手順 3-7 ステップ / 5.3 self_evaluation_checklist 5-8 項目) は同契約で廃止済み。

## C1: Layer 整合

L1-L7 が `seven-layer-format.md` と整合し、Layer 番号と役割名の対応が崩れていないか。

**Failing シグナル**:
- L3 を「ドメイン定義」と書いている (本来 L3 はインフラ)
- Layer が 8 つ以上ある / 6 つ以下に潰れている
- メタ表に name / skill / responsibility / layers_covered のいずれかが欠落

## C2: 依存方向 (L7→L1 単方向)

外側 Layer (L7) が内側 (L1) を参照するのは OK。逆方向参照は CA 違反。

**Failing シグナル**:
- L1 不変定義の中で L5 エージェント名を直接参照
- L3 (インフラ) が L6 (オーケストレーション) のフェーズ名を hardcode
- ID 参照 (@agent_1) ではなく名前参照で曖昧性を残す

## C3: 再現性

同じ入力で同じ出力を得る根拠が揃っているか。根拠は手順の固定ではなく、output_schema / script_refs / 検証可能な完了チェックリスト (停止条件) の二層 (決定論部分は script、意味判断はチェックリスト拘束) で担保する (l5-contract v2.0.0)。

**Failing シグナル**:
- reproducible: false (本当に確率的でない限り FAIL)
- output_schema 未指定または存在しないパス
- 5.2 ゴール定義が成果状態 (「〜の状態になっている」完了形・観測可能) でなく、動作や手順の列挙で書かれている
- 5.2 に固定手順列挙が混入 (旧「推論手順」構成の残存 = l5-contract v2.0.0 廃止構造)
- 完了チェックリストの**項目・判定基準内**に「適宜判断」「品質が高い」等、第三者が判定できない曖昧語がある (曖昧語検査の対象は完了チェックリスト項目および判定基準内に限定する)
- script_refs が空で全工程 LLM 判断

**正当パターン (allowlist — FAIL にしない)**:
- 5.4 実行方式の動的手順生成宣言: 「状況に応じて必要な手順をその都度自ら設計」等のゴールシーク正準文言 (goal-seek-paradigm.md / l5-contract v2.0.0 必須事項)。実行方式ループの適応性宣言は曖昧語ではない
- 実行方式のゴールシークループ 6 ステップ (Step 5=Anchor) 記述。ループ自体は固定手順列挙に当たらない

## C4: Self-Evaluation 充足

L5.3 完了チェックリスト (ゴール到達の停止条件) が非空で、全項目が第三者に YES/NO 判定可能か。
(旧基準「self_evaluation_checklist が 5-8 項目」は l5-contract v2.0.0 で廃止。数量レンジは質を保証しないため、構造制約=非空の下限のみ + 質基準=原子性・客観判定可能性の二層に置換)

**Failing シグナル**:
- 完了チェックリストが欠落または空 (verify-completeness.py の L5 必須要素検査で機械検出)
- 「品質が高いか?」のような主観項目 (第三者が YES/NO を判定できない)
- 1 項目に複数の判定が混在 (原子性違反)
- 項目に手順が埋め込まれている (「Edit で X を書く」型。手順はループで都度生成する)
- placeholder `{{...}}` / `TODO(human)` / 英語仮文の残存

## 自動承認との関係

`workflow-manifest.json` governance phase の `auto_approve_conditions` (各条件に evidence=判定主体を 1:1 紐付け) を全て満たし、かつ `preconditions` (solo_operator_mode / stable_frozen = 環境前提) が真のとき、Gate 4 で `solo_operator_auto` となる。`prompt-rubric.json` の `global_thresholds` は rubric 判定 (llm_reviewer 条件) の集計閾値。
