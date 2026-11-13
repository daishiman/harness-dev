# Gate Templates

各ゲートで使う AskUserQuestion テンプレート。

## Gate 1: brief確認

```
question: "skill-brief を確認しました。これでビルドを開始してよろしいですか？"
options:
  - "承認 (Step2へ)": briefの通りbuildを起動
  - "skill_name変更": 命名を再検討
  - "kind変更": kind判定を再実行
  - "中断": フロー終了
```

## Gate 2: diff確認

**前提**: Step 4a の P0 lint 全て exit 0 で通過済みであること。

### Gate 2 前 必須手動チェックリスト (01a Step8 検証1-3)

P0 lint が pass しても以下3項目は**手動確認**が必要 (自動化不能):

- [ ] **検証1 (直接呼び出し)**: `/skill-name` で直接 invoke して動くか確認
- [ ] **検証2 (description自動発動)**: trigger phrase に合致する自然文を投げて発動するか確認
  - 例: trigger に「PRレビュー観点」があれば「PRレビュー観点を確認したい」で発動するか
- [ ] **検証3 (誤発動なし)**: 関係ない自然文 (例: 天気・雑談) で**発動しない**ことを確認
- [ ] **検証4 (output contract)**: 出力ファイル名・形式が SKILL.md の Purpose & Output Contract と一致
- [ ] **検証5 (dangerous action)**: 危険操作 (削除・force-push等) が permission / hook で止まるか確認
- [ ] **05 Layering Review**: 決定論的検査は script/hook/CI へ分離され、Skill本文に高級リンターとして残っていない
- [ ] **05 Layering Review**: Subagent は独立contextが必要な場合だけ、Hook は lifecycle強制が必要な場合だけ使っている
- [ ] **05 Layering Review**: MCP/CLI/API/script は選定理由・fallback・依存方向・macOS stdlib適合が `skill-build-trace.json` に残っている
- [ ] **05 Layering Review**: 採用しない layer にも skip 理由がある

3項目以上 NG、または 05 Layering Review に NG があるなら Gate 2 を拒否し Step 2 (run-build-skill --mode update) へ戻す。

```
question: "生成されたスキルのdiffを確認しました。上記5検証 (検証1-5) は全てOKですか? 完了レポートへ進みますか？"
options:
  - "承認 (Step4a.5→7へ)": 条件該当時の PKG check を経て完了レポートを作成 (C1-C4 は run-build-skill の初稿診断 receipt を転記し、評価し直さない)
  - "修正が必要": run-build-skill --mode update で再生成
  - "中断": フロー終了
```

> Gate 3 (評価結果確認) と Gate 4 (governance 最終承認) は既定の流れから外した。C1-C4 は run-build-skill の初稿診断が正本で、rubric governance は rubric を変更するときだけ利用者が `run-skill-rubric-governance` を明示的に呼ぶ。
