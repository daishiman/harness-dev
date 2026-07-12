# タスク: {{TARGET_SKILL}} の実走

<!-- task-template.md — 準備局面で cp して {{...}} placeholder を全て Edit で埋める。
     task.md 契約 5 項目 (SKILL.md の表) をこの構造が満たす。項目の削除は契約違反。 -->

以下を実行してください:

Skill({skill: "{{TARGET_SKILL}}", args: "{{ARGS — target skill に渡すリテラル。言い換え・要約禁止}}"})

処理が終了 (成功 / 失敗 / 中断いずれでも) したら:

1. {{WORK_DIR — 絶対パス}}/out/status.json に完了マーカーを 1 ファイルだけ Write する。内容:
   {"status": "{{PASS|FAIL|ERROR など終端語彙}}", {{検証目的に応じた最小フィールド (例: "final_score": <数値 or null>)}}}
2. 「DONE: <status>」と 1 行だけ報告する。

制約:
- 途中で人間に質問せず最後まで自走すること。
- skill の手順に忠実に従い、人手の追加判断・省略をしないこと。
- out/ には status.json 以外を書かないこと (中間生成物は skill 側の出力先 (WORK_DIR 外) へ — out/ に中間 Write させると poll が DONE 偽陽性を起こす)。
