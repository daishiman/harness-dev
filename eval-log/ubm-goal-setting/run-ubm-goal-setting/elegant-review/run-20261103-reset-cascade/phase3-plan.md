# Phase 3 改善計画（iteration 1）— 並列 executor 共通契約

正本の指摘一覧: 同じディレクトリの `findings.json`（30思考法・47 issue）。各 executor は自分の担当 issue を
paradigm_id で引き、`recommended_intervention` を基に直す。ただし下の「確定事項」と矛盾する推奨は確定事項を優先する。

## 書き方の原則（全員共通）

1. **追記ではなく置換**（ユーザー要件 R4）。既存の該当文を探し、置き換えるか削除する。新しい注記を足して古い文を残さない。
2. **重複は参照に置換**（R7）。規則の本文は output-formats.md の共通部品にだけ置き、他ファイルは次の形の1行参照にする（tests/test_heading_references.py が実在を検査する）:
   `` `output-formats.md` の「共通部品A 行動行」 ``
3. 担当ファイル以外は編集しない。他レーンの担当ファイルに直しが必要なら、報告に「他レーンへの依頼」として書く。
4. 意味の変更は下の確定事項の範囲に限る。それ以外で意味の変更が必要なら直さずに報告する。
5. git commit / push / stash / reset はしない。

## 共通部品の見出し名（固定。output-formats.md 冒頭に新設する）

`## 共通部品（全層共通の正本）` の下に次の `###` 見出しを置く（名前は一字一句この通り）:

| 見出し | 中身（正本） |
|---|---|
| `### 共通部品A 行動行` | 行動目標1行の書式・合格基準・期日トークン・注記・優先順位 |
| `### 共通部品B 成果目標と売上貢献の根拠` | 成果の2行記法、売上貢献の式／括弧根拠、貢献0の括弧 |
| `### 共通部品C 設計順序と4層` | 売上→成果→行動の逆算、1年→3ヶ月→1ヶ月→1週間、--yearly |
| `### 共通部品D 前回ブロック` | 前回正本→実績→差分→挽回（週・月・3ヶ月・年で共通） |
| `### 共通部品E 軌道修正記録` | 月・週の軌道修正と記録書式・記録先 |
| `### 共通部品F 層別差分表` | 層ごとに違う値だけを1表に（月報1本2セクション、projects要否、やらないことの出力先、S1/S3、上限回数の区別、所要時間） |

## 確定事項（ユーザー承認済み・ユーザー要件から導出）

### A 行動行（R2）
- 管理用の書式: `- [ ] 項目名：何をする（判定に必要な対象・数量だけ）　期日{期日トークン}`
- 提出用: 同じ行からチェックボックス・グループ見出し・個人名を外したもの。**期日は管理用と同じ値を必ず書く**。
- 期日トークン: `M/D`・`YYYY-MM-DD`・`毎日`・`毎朝`・`毎週`・`今週`・`〜までに`（validate-goal-output.py の既存正規表現と同じ集合）。
- 合格基準は「何をする＋期日」。**誰に・トリガー・数値・人名は必須にしない**（判定に必要なときだけ残す）。年間・3ヶ月・月間・週間で共通。
- 【考え】【思い】などの注記は依頼されたときだけ。テンプレート・例・手本から削除する。
- 精神論 NG の正本は `references/action-language-policy.json`（goal_exact_phrases）。他ファイルの NG 語リストは削除して参照に置換。policy への語の追加はしない。
- 優先順位: 売上貢献額の大きい成果グループを上、グループ内は依存の順。「売上直結度×すぐできるか」の2軸は廃止。
- 前期間への自動転記は「今期の行動行からチェックボックスだけ外して転記」（項目名の「：」を保つ）。

### B 成果と貢献根拠（R1・R7）
- 正本は現 output-formats.md の中間成果規則（旧 L147）。
- 中間成果の貢献0: `0（{支える直接成果の項目名}を支える）`。翌期に計上する直接成果だけ: `0（{M}月計上・{根拠}）`。
- 「`0（8月に 200000 の見込み）`」型の例・検査メッセージ・手本・テスト fixture は上の形へ置換。

### C 設計順序と4層（R1・R5）
- 売上目標→成果目標→行動目標の順で逆算する（行動から積み上げない）。例文も売上側から書く。
- 1年→3ヶ月→1ヶ月→1週間を上から降ろす。3層だけの列挙は4層に置換。
- **--yearly の機械強制**: validate-cross-level.py は `--yearly PATH` か `--no-yearly REASON`（理由は空不可）のどちらか一方を必須にし、どちらも無ければ rc=2（使い方エラー）。workflow-manifest の phase5 コマンドと文書の「必ず渡す」の再掲は、この1つの仕組みへの参照に置換する。

### D 前回ブロック（R3）
- 前回正本（前回の目標をそのまま転記）→実績→差分→挽回。**週報・月報・期報・1年で共通**。
- 項目名・順序が前回と1対1。**差分は項目ごとに必須**。挽回は未達があるときだけ。
- validate-goal-output.py の check_report_alignment は週報（前週）も対象にする。
- データ契約: `prev_action_diff` を `string[]`（1項目1行）に変更。新フィールド `prev_other_diff`（#36, `string[]`, 売上以外の成果の前期間差分, Step 2 で算出, 初回 null）を追加して全36フィールドにする。テンプレート変数 `{{other_diff}}` ← `prev_other_diff`、`{{action_diff}}` ← `prev_action_diff`。

### E 軌道修正記録（R6）
- 月・週は実行後に軌道修正してよい。上位（1年・3ヶ月）は自動で変えない。前回の目標・実績・差分は遡って書き換えない。
- 記録書式は2種類で共通の尾部「｜理由：…｜上位への影響：…」を持つ:
  - 上位配分の見直し（月報のみ・内訳継承4項目・機械検査あり。既存書式のまま）: `- 上位配分の見直し：{対象}｜上位計画：{値}｜実行目標：{値}｜理由：…｜上位への影響：…`
  - 行動の見直し（週報・月報）: `- 行動の見直し：{項目名}｜変更前：…｜変更後：…｜理由：…｜上位への影響：…`
- 記録先: 月報＝管理用【確認された情報】。週報＝**新設見出し `## 【今週の見直し記録】`**（見直しが無い週は `- なし`）。週報の必須見出しに加える。

### F その他（R7）
- #6 事業パートナー数・#7 グリッドパートナー数・#8 次回の壁打ち予定日は**時点値（スナップショット）**。層間で照合せず INFO で並べて表示するだけ。validate-cross-level.py の ANCHORS から外し、data-contract の「未決」段落は削除。
- 「最大改善回数」の同名3種は名前を分ける: 次問案の作り直し上限（2回）／決定論ゲートの修復上限（3回、正本 validation-gates.md）／OUT1 の周回上限（5周）。
- 外部の存在しない正本 `.claude/rules/ubm-kitahara-mindset.md` への依存は削除し、必要な規則（人数を第1優先）は output-formats.md 内で完結させる。
- 統合済みスタブ `references/thinking-methods-toolkit.md`・`references/thinking-process.md` は参照を消して削除する。
- 手本の本人名「中村健一」は架空表記（Xさん）へ。
- data-contract.md 末尾の版履歴表は CHANGELOG.md へ移し（無い版だけ）、1行参照に置換。

## レーン分担（書き込み範囲は重ならない）

| レーン | 書き込み範囲 |
|---|---|
| X1 正本 | `skills/run-ubm-goal-setting/references/output-formats.md` |
| X2 検査 | `skills/run-ubm-goal-setting/scripts/*.py`、`skills/run-ubm-goal-setting/workflow-manifest.json`、`references/action-language-policy.json`、`tests/*.py` |
| X3 手順 | `skills/run-ubm-goal-setting/SKILL.md`、`prompts/R1〜R5`、`agents/{phase3-coordinator,output-formatter,goal-reviewer,info-collector}.md`、`references/agent-*.md`（プラグイン直下）、`skills/run-ubm-goal-setting/references/{thinking-guide.md,resource-map.yaml,validation-gates.md,selection-focus-goal-frame.md}`、スタブ2本の削除、`README.md`、`RUNBOOK.md` |
| X4 契約・資産 | `skills/run-ubm-goal-setting/references/data-contract.md`、`skills/run-ubm-goal-setting/assets/*.md`、`CHANGELOG.md`（版履歴の移設だけ。版上げはしない） |

パスはすべて `plugins/ubm-goal-setting/` 起点。
