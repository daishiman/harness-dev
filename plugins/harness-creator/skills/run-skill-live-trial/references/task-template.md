# タスク: {{TARGET_SKILL}} の実走 {{— scenario がある場合は (scenario <SCENARIO_ID>) を付す}}

<!-- task-template.md — 準備局面で cp して {{...}} placeholder を全て Edit で埋める。
     task.md 契約 8 項目 (SKILL.md の表) をこの構造が満たす。項目の削除は契約違反。 -->

{{SCENARIO_BLOCK — scenario がある run では次の 2 つをそのまま置く。無い run では節ごと削除する。
  (a) 「この run は scenario <SCENARIO_ID> の充足を確認するものです」の 1 行
  (b) scenario の required_observations を逐語で番号付き列挙 (要約・言い換え・取捨選択は禁止)}}

{{TASK_CONTRACT_BLOCK — scenario に task_contract がある場合、required_fragments が
  task.md に全て現れ、forbidden_fragments が一つも現れない具体的手順を書く。
  結果だけを合わせる別 operation への読み替えは禁止する。}}

以下を実行してください:

Skill({skill: "{{TARGET_SKILL}}", args: "{{ARGS — target skill に渡すリテラル。言い換え・要約禁止。
  scenario がある run では task_args_template の placeholder だけを実値へ置換して起こす。
  契約と違う args で走らせたくなったら、ここを書き換えず scenario を改訂して scenario_id を bump する}}"})

処理が終了 (成功 / 失敗 / 中断いずれでも) したら:

1. {{WORK_DIR — 絶対パス}}/out/status.json に完了マーカーを 1 ファイルだけ Write する。内容:
   {"status": "{{PASS|FAIL|ERROR など終端語彙}}", {{検証目的に応じた最小フィールド (例: "final_score": <数値 or null>)}}}
2. 「DONE: <status>」と 1 行だけ報告する。

制約:
- 途中で人間に質問せず最後まで自走すること。
- skill の手順に忠実に従い、人手の追加判断・省略をしないこと。
- out/ には status.json 以外を書かないこと (中間生成物は skill 側の出力先 (WORK_DIR 外) へ — out/ に中間 Write させると poll が DONE 偽陽性を起こす)。
