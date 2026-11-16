# Gate Templates

各ゲートで使う AskUserQuestion テンプレート。選択肢は「承認」と「差戻し」の 2 つだけにする。差戻しで直す点は同じ回答の自由入力 (その他) から `required_fixes[]` へそのまま写し、聞き直さない。中断も自由入力で受ける。

## Gate 1: brief確認

**前提**: Step 1 (elicit) の `eval-log/skill-brief.json` が `schemas/skill-brief.schema.json` の検証を PASS していること (manifest の transition.gate)。Notion 指定あり (`--page-url` / `--page-id`) なら `validate-intake-publish-ready.py` が exit 0 であること。未公開・page_id 不一致・URL 欠落なら Gate 1 で止め、build へ進まない (SKILL.md の CL-2)。

確認する成果物:
- `eval-log/skill-brief.json` の path・digest・要点 (skill_name・kind・goal・boundary など。SKILL.md の Pre-choice)
- `open_questions[]` に残った OPEN_QUESTION(escalate) の項目 (R1 の 4.1。代理決定せず、ここで利用者に返す)
- `--brief-path` で持ち込んだ brief に `user_request_verbatim` が無いときは、その旨 (build の目的照合が依頼の原文なしで進む。SKILL.md の起動モード)

```
question: "skill-brief を確認しました。これでビルドを開始してよろしいですか？"
options:
  - "承認 (Step2へ)": briefの通りbuildを起動
  - "差戻し": skill_name・kind・目的など直す点を書き添え、briefを直してGate 1を出し直す
```

## Gate 2.5: 登録確認

**前提**: Step 3 (manifest-register) の登録 plan 検証が PASS していること (manifest の transition.gate)。

確認する成果物:
- Step 3 の command (`build-manifest-registration-plan.py --plugin plugins/<plugin>`) が stdout に出した JSON。生成先の plugin を読んだ結果で、新形式 plugin (`.claude-plugin/plugin.json`) は読んだ `plugin_manifest`・`name`・`version` と空の `proposals` が出る。未登録ファイルの追加提案が `proposals` に並ぶのは legacy `manifest.json` を持つ plugin だけ
- 承認したあとに動く書き込み (manifest の phases 順):
  - legacy の `--apply` (対象 plugin の `manifest.json` へ `proposals` を追記)
  - Step 3.5 の `validate-plugin-completeness.py --fix` (`marketplace.json` / `bundles.json` への append-only 登録)
  - Step 3.55 の `sync-plugin-platforms.py --apply` (`plugins/<plugin>/.codex-plugin/plugin.json` と `.agents/plugins/marketplace.json` の upsert)
  - Step 3.6 の `build-local-marketplace.py` (`marketplaces/local/.claude-plugin/marketplace.json` の再生成)
  - Step 3.7 の `build-plugin-release.py --only <plugin>` (内容 hash の記録と version の採番。version を上げるときは `plugin.json` の version 行と、それに追従する公開 `marketplace.json`・`.codex-plugin/plugin.json` の既存行を書き換え、`config-version-lock.json` を作り直す。SKILL.md の Key Rule 6)

```
question: "登録 plan を確認しました。この内容で plugin / marketplace への登録と release 記録へ進めてよろしいですか？"
options:
  - "承認 (Step3.5へ)": legacy なら --apply してから、bundle-register から plugin-release-record までを順に通す
  - "差戻し": 直す点を書き添える。plugin.json / manifest.json 側の誤りならそれを直して Step 3 から登録 plan を作り直し、Gate 2.5 を出し直す。skill 本体の誤りなら run-build-skill --mode update (build) からやり直す
```

## Gate 2: diff確認

**前提**: Step 4a の P0 lint 全て exit 0 で通過済みであること。

### Gate 2 前 必須手動チェックリスト (01a Step8 検証1-5 + 05 Layering Review)

P0 lint が pass しても以下 9 項目 (検証1-5 と 05 Layering Review 4 項目) は**手動確認**が必要 (自動化不能):

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

上記 9 項目のうち 1 つでも NG なら Gate 2 を拒否し Step 2 (run-build-skill --mode update) へ戻す。当てはまらない項目 (例: 危険操作を持たないスキルの検証5) は N/A と理由を書けば NG に数えない。下の質問は 9 項目全部を聞くので、閾値をここと揃えている。

```
question: "生成されたスキルのdiffを確認しました。上記9項目 (検証1-5 と 05 Layering Review) は全てOKまたは理由付きN/Aですか? 完了レポートへ進みますか？"
options:
  - "承認 (Step4a.5→7へ)": 条件該当時の PKG check を経て完了レポートを作成 (C1-C4 節は scripts/render-c1-c4-section.py が run-build-skill の初稿診断 receipt から描いた出力をそのまま貼り、評価し直さない)
  - "差戻し": NGの項目と直す点を書き添え、run-build-skill --mode update で再生成する
```

差戻しの戻り先は各 Gate の節に書いた先 (Gate 1 は elicit で brief の直し、Gate 2.5 は manifest-register で登録 plan の作り直しか build、Gate 2 は build)。`workflow-manifest.json` の各 transition の `on_fail_comment` にも同じ戻り先を書いてある (`on_fail: abort` は run を終えるのではなく、その Gate の先へ進めないという意味)。差戻しは選ばれるたびに 1 回やり直し、同じ Gate で通算 3 周まで (R2 の CONST_004)。超えたら止めて利用者に相談する。差戻しの handoff は `required_fixes[]` を持ち、`next_phase` に戻り先の phase id を書く。

> Gate 3 (評価結果確認) と Gate 4 (governance 最終承認) は既定の流れから外した。C1-C4 は run-build-skill の初稿診断が正本で、rubric governance は rubric を変更するときだけ利用者が `run-skill-rubric-governance` を明示的に呼ぶ。
