# skill-brief テンプレート

run-skill-elicit の出力。run-build-skill に渡す要件定義。

```markdown
# Skill Brief

skill_name: <kebab-case — 06章命名規約に従う>
kind: run | ref | assign | wrap | delegate
created_at: <YYYY-MM-DD>
created_by: run-skill-elicit

## trigger_conditions (2〜3個、動詞ベース)

- <動詞 + 状況 1>
- <動詞 + 状況 2>
- <動詞 + 状況 3> (任意)

## output_contract

- artifact: <ファイル名・形式>
- completion_condition: <完了条件 (機械判定可能な形で)>
- threshold: <スコア閾値など>

## key_constraints

- <制約 1>
- <制約 2>

## open_questions (TODO(human))

- [ ] <設計判断が分かれる事項 1>
- [ ] <設計判断が分かれる事項 2>

## context_budget

max_reference_chapters: 3  # run-build-skill が参照する設計書章の上限 (CD-005)
```

## 使い方

1. `run-skill-elicit` を呼ぶ (topic 任意)
2. ウィザード完了後に `skill-brief.md` が生成される
3. `run-build-skill` に渡す:
   ```
   Skill(run-build-skill) skill_name=<name> kind=<kind>
   ```
   または brief ファイルを参照させる:
   ```
   references/skill-brief.md を読んで run-build-skill を実行してください
   ```
