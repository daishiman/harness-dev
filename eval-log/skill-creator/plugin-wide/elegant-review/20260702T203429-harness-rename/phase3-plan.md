# Phase 3 実行計画 (fan-in 統合 + 意思決定記録)

run-id: 20260702T203429-harness-rename / 入力: findings.json (30思考法・issues 39件: critical 2, high 17, medium 18, low 2)

## 意思決定 (論点思考 id29 の 2 決定 + 境界 rubric)

- **DEC-1 eval-log 履歴** = 凍結+新パス新規 (トレードオン id22 採用)。過去 run は eval-log/skill-creator/ に凍結し tombstone README で双方向参照。runtime 参照層のみ更新: content-review verdict は eval-log/harness-creator/<skill>/content-review/ へ、SKILL.md 内容が変わる skill は独立 SubAgent genuine 再生成・byte 不変 skill は target 更新+retargeted_from 監査キー (protocol 明文化を先行)。llm-coverage.json の plugin キーは runtime 突合台帳のため更新。
- **DEC-2 改名境界** = plugin 名/dir 名/kit 名 (harness-creator-kit)/workflow ファイル名/underscore 形テストファイル名/spec-reflection.md ファイル名は追従。内部 skill 名 run-skill-* は単体スキル概念 (ルール1+プラットフォーム予約語) で維持。
- **DEC-3 境界例 rubric** (逆説思考 id15 採用): 操作/生成対象が単一 skill なら skill、plugin 総体・Capability 横断なら harness。部品の集合名は harness 側。判定は台帳へ記録。
- **DEC-4 3層分類** (抽象化思考 id11 採用): 動的導出=0作業 / 固有名3種 (skill-creator, skill_creator, スキルクリエイター)+複合形 (skill-creator-kit, 裸 creator-kit)=機械置換+除外集合 / 一般語 skill/スキル=パターン規則+残余の台帳付き判定。
- **DEC-5 除外集合 (凍結層)** = eval-log/** の過去 run 記録 (本 run workspace 含む)・doc/参考Skill/**・CHANGELOG/changelog/lessons-learned の歴史記述・.obsidian/**・git 履歴。ただし runtime 参照層 (DEC-1) は例外。
- **DEC-6 実施場所** = 独立 worktree + branch feat/harness-creator-rename (共有 worktree で別エージェントが skill-intake 編集中のため隔離)。push は行わない (ユーザー未指示)。
- **DEC-7 再発防止** = lint-legacy-plugin-name (固有名3種 denylist + allowlist=凍結層) 新設+CI 配線。if思考 id17 採用。p2-logical why思考 id26 の「一時スクリプト案」との相違は「並行 worktree からの再流入リスク (id17)」を優先し恒久 lint を採用、allowlist は凍結層 path prefix で最小化。

## 工程 (プロセス思考 id9 の順序ゲート準拠)

- W0: 独立 worktree+branch、pre-phase3.patch 取得、eval-log run dir 複製
- W1: git mv 群 — plugins/skill-creator→harness-creator、tests test_skill_creator__*→test_harness_creator__* (37本)、skill-creator-spec-reflection.md→harness-creator-spec-reflection.md、creator-kit-ci.yml→harness-creator-kit-ci.yml、installers/creator-kit→(参照確認後) harness-creator-kit、settings.creator-kit-hooks.json.example
- W2: 固有名機械置換 (python スクリプト・除外集合適用・全変更ファイルリストを台帳へ)
- W3: 機械層定数/連鎖セット — NEVER_DISTRIBUTE/SELF_DOGFOODING×2 (byte一致再同期)/VENDORED_PAIRS/lint-feedback-protocol:26/CI 42+Makefile3/settings.json:114/upstream-pins 6 pin (path+sha 再計算+verified_at+matrix 行再監査)/criteria_roster/test assert 群。**feedback_contract_ssot.py への編集 (定数+ADRコメント意味論) は1回で確定し2度触らない** (因果ループ id21 v2: pin bump 二重発生防止)
- W4: symlink repoint (14 plugin の run-skill-feedback + notion-per-repo-setup 系) + build-claude-symlinks 再生成
- W5: 新規ガード — parity test (dir↔定数)/NEVER_DISTRIBUTE 実在 test/_JUDGMENT_LITERAL_RES を SSOT 導出化/lint-legacy-plugin-name+CI 配線
- W6: 語彙整合 (SubAgent 並列・DEC-3 rubric・台帳記録) — plugin 自己記述 (plugin.json description/README/composition invariant)/installers manifest description/依存 plugin 文書 (marketplace description, skill-intake handoff, prompt-creator)/doc 層 (CONVENTIONS 用語節, harness-coverage-spec 関係段落)
- W7: 定義3点セット+境界ルール恒久化 (terms.md ハーネスエントリ/README 冒頭/description) + content-review-protocol retarget 規約 + lessons-learned plugin-rename 教訓 + CHANGELOG 機械可読対応 + tombstone README
- W8: 固有名 closure 機械確認 (旧名 grep 残数=許容リスト一致) + 台帳未判定行ゼロ確認 → verdict 再生成 (独立 SubAgent 並列 genuine / byte 不変は retarget)
- W9: 検証 battery 10項目 (仮説思考 id28 v2): 機械層8=(1) 残存 grep=allowlist 一致 (2) make lint 全通過 (3) 中央 pytest 直接実行 (4) CI cwd 再現 (5) build-claude-symlinks --check (6) 単独 install import smoke (7) is_stop_block_exempt("harness-creator")==True smoke (8) git archive clean-checkout / 意味論層2=(9) 概念判定インベントリ(台帳)成果物化 (10) proposer≠approver 独立LLMレビューで台帳突合 APPROVE
- W10: 4条件再検証 → findings.json 最終化 + verdict.json + review-repo.md + 独立 approver (proposer≠approver)

## 完了条件 (メタ思考 id10 の三点セット)
1. 固有名層: 凍結層+別実体を除き旧固有名 0 件 (機械検証)
2. 一般語層: 判定台帳に全境界例の判定+根拠記録 (監査可能)
3. 凍結層: tombstone+CHANGELOG 凍結宣言
