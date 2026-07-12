# Elicit Question Bank

> doc/prompt-creator/references/prompt-sheet-template.md と writing-style-principles.md を起点に整理した質問テンプレ。3-5 問 + 評価優先度に絞る。質ベース判定 (実行可能か / 検証可能か) を基準にする。

## 必須質問 (3-5 問に圧縮)

1. **prompt_name** — このプロンプトの slug (kebab-case) は?
   - 例: `elicit`, `gate-review`, `governance-decide`
2. **target_skill + responsibility_id** — どの skill のどの responsibility (R-id) を充填しますか?
   - 例: `run-skill-create` の `R2 (gate-review)`
   - skill 非紐付け (standalone) なら「なし」+ 出力先パスを確認
3. **goals + checklist** — 何が出来上がれば「完了」ですか? (成果状態で)。その達成を第三者が YES/NO で判定する条件は?
   - Layer 5 ゴール定義 / 完了チェックリストの材料 (手順は聞かない)
4. **layers_required** — どの Layer を生成しますか? (L1-L7 から複数)
   - 既定推奨: 担当責務に応じて L4/L5/L6 中心、または全層
5. **boundary + output_contract** — このプロンプトが**やらない**ことは? (1 文 200 字以内)。出力すべき成果物 (JSON schema / artifact パス) は?
   - 例: 「ヒアリングと Governance 判定は対象外」

## 評価優先度 (Pass 0 動的基準用)

`evaluation_priorities` は **`schemas/hearing-result.schema.json` の enum が正本 (SSOT)**。本テンプレは従属者。次の 5 値から**最大 2** ピック (quality-criteria.md §7.2 の Pass 強化マッピングと相互参照):
- 正確性・精度 / 創造性・柔軟性 / ユーザー親和性 / ドメイン専門性 / 実行速度・効率

enum 外の回答は evaluation_priorities に入れず open_questions へ fail-visible に記録する。

## 任意追加質問 (必要時のみ)

- checklist 深掘り (L5.3 完了チェックリスト = ゴール到達の停止条件。非空で全項目が第三者 YES/NO 判定可能。旧 self_evaluation_checklist 5-8 項目形式は l5-contract v2.0.0 で廃止)
- inject_sections (既定: `Prompt Templates, Self-Evaluation`)
- format (既定: `md`、yaml/json/xml は legacy のみ)
- trigger_conditions (非空・各 80 字以内の原子性 (1 値=1 短文)、kind と整合。数量レンジは撤廃済み、過不足は質ベースで判定)

## 導出確認テンプレ

AI が target_skill の SKILL.md から推定した値は次の形でユーザーに確認:

```
[導出確認] target_skill=<x> の responsibilities[<i>] から以下を推定しました:
- responsibility_id: R<n>
- layers_required: [L<...>]
- boundary: <推定文>
この内容で進めて良いですか? (はい / 修正)
```

## アンチパターン

- 「3 つ以上挙げて」のような数量カウント要求 (質ベースに反する)
- 7 層全部を 1 回で埋めようとする (Layer 単位生成原則違反)
- ユーザーが回答済みの項目を再質問する
- AI 推定値を導出確認なしに confirm 扱いする
