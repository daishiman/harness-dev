# Phase 3 設計決定書 (3 analyst ファンイン、41 issues → 14 決定)

3視点独立分析が同一解へ収束した決定。Phase 3 executor はこれを正とする。

## 決定一覧

- **D1 (INV8スコープ限定・critical 3件収束: A2-001/A3-002/A4-014)**: 証拠を主張型で直交化。design claim(設計adequacy)=静的 content-review/elegant-review/rubric が正本のまま。behavioral claim(自走完遂/入れ子Skill/対話gate越え/goal達成)=実走証拠(live-trial verdict+transcript)のみが収束根拠。INVARIANT 8 は behavior スコープ限定輸入。orchestrate-gate-pattern.md に **Gate D(実行acceptance)** を追加、優先 A>B>C>D、「D は loop 実行系のみ」。
- **D2 (forbidden-clis解決: A2-003/A3-011/A4-002/A4-012)**: .sh 4本+jq+bats → Python stdlib 移植(subprocess/json/re/glob/time)。tmux のみ代替不能な輸送層として `.claude-plugin/plugin.json` に `requirements.external_clis: ["tmux"]` を新設登録(dangling解消)。tmux 不在検出時は verdict=BLOCKED で fail-closed。tmux 呼出は backend module 単一境界に閉じ込め。
- **D3 (goalアンカー一本化: A2-010/A3-007/A4-016)**: goal-spec.json.goal / original_goal(SHA-256) が唯一のアンカー正本。iter-improve の --goal は正規化書込/読取エイリアス。GOAL VERIFICATION(PASS|FAIL+blocker列挙・点数出力禁止)は drift_signal(軌道監視)と別軸の「達成判定」として goal-seek-paradigm.md へ追記。緩め禁止リスト(forbidden_loosening)は goal-spec 拡張 field+convergence-policy anti_patterns へ一本化。二重宣言禁止 1 行を両文書へ。
- **D4 (loop_bounds拡張+命名: A2-011/A3-008/A3-013/A4-001)**: convergence-policy.json loop_bounds へ `trial_acceptance`(nudge_max=2, stall_limit_s=600, hard_cap_s=7200) / `iter_improve`(max_iter=5, batch_per_iter=2, parallel_agents=3, threshold=90) を consumed_by 付き追加。「3つ」→「5つ」同時更新。**位相語(inner/outer)輸入禁止**、機能語(acceptance/improve)で命名。
- **D5 (INV5境界宣言: A2-014/A4-007)**: eval帰属反復ループ=1-2件/iter(INVARIANT 5)、レビュー一括改善=DAG全件消化(eval非帰属)。編集エンジン非共有。両文書相互参照。
- **D6 (INV7エンジン/被験体: A2-002/A3-001/A4-017)**: feedback_contract_ssot.py へ ENGINE_SKILLS(エンジン閉包)+第4述語 `requires_subject_copy(plugin, loop_kind)` 追加。iter-improve×閉包交差時のみ被験体コピー強制、通常skillは直接編集維持。feedback-loop-deployment.md 境界表へ行追加。
- **D7 (verify_by語彙: A2-015/A4-005)**: CRITERIA_VERIFY_BY += "live-trial"(SSOT 1点変更で3 lint自動伝播)。schema側ミラー注記同期。loop実行系のouter criteria要求はP2 ratchet(新規のみ)としてdeferred記録。
- **D8 (acceptance_tier決定論導出: A2-012/A3-003/A4-006)**: `acceptance_tier: static|fork|live` を契約化。frontmatter静的信号(hooks配線/allowed-toolsのSkill・Agent/AskUserQuestion)から純関数導出、宣言<導出でFAIL。
- **D9 (常設=常時発火可能+条件必須: A2-013/A3-004/A3-010/A4-006)**: workflow-manifest 新 phase `live-acceptance`(default_on: false, execution=local-only)。発火三積=(behavioral trait該当)×(挙動面SHA差分)×(予算内)。非発火は queue へ deferred 記録。proof trial のみ無条件。起動経路=main 直下(Skill→Agent制約)。強制=CI/pre-push の lint(lint-content-review 同型の最終強制層)、hook は queue 記録のみ。
- **D10 (runtime-evidence契約: A2-005/A2-007/A3-011/A4-003/A4-008/A4-012)**: 実装順=契約が先・輸送層(tmux)は後。live-trial-verdict schema 必須キー: requested_model/actual_model/nudge_count/gate_response_count/goal判定(PASS|FAIL+blockers[])/総合判定/skill_dir_tree_sha(SKILL.md+scripts複合)/transcript_sha256/scenario_origin(synthetic|replay)/environment{claude_version,tmux,transcript_layer,permissions_mode}/tier+downgrade_reason(A3-012)/score_delta+independent_check(A4-004a)。sink=eval-log/<plugin>/<skill>/live-trial/<run-id>/。.mso・$HOME fallback 全廃(A2-006)。
- **D11 (審問ログartifact: A4-004c)**: PASS詐欺自己審問(毎iter Yes/No+根拠)+緩め禁止リスト宣言を iter-improve の必須成果物(eval-log保存)に昇格。score急変(+10pt超)は別個体fresh agentの独立判定必須、判定者はGOAL VERIFICATION agentと別個体。
- **D12 (配置: A3-005/A4-009)**: skill-creator 核=契約(schema/SHA/lint/manifest step)のみ常設。runner=新skill 2本(run-skill-live-trial / run-skill-iter-improve)を交換可能な葉として skills/ へ。[新設]=harness/N並列eval/審問ログ/急変独立判定/proof gate。[参照統合]=INV2→goal-seek分離節、INV6→elegant-review B7、判定者独立→C4(1行相互参照のみ、再実装禁止)。
- **D13 (パイロットゲート: A4-013)**: P1完了条件=パイロット2-3件の判定表を eval-log へ記録。P3常設化(default_on昇格)の go/no-go は乖離率で判定。ROADMAP へ deferred 明記。
- **D14 (過剰設計却下: A4-014/A4-011/A3-006)**: 却下=全kind常設live-trial / CIでのlive-trial実行 / AG workflow-checklist別機構移植(validate-paradigm-coverage --phase-order同型で吸収) / selection混入 / 量産先へのlive-trial配備(composition invariantに開発環境限定を明記)。シナリオコーパスhook拡張(A3-009)はverdictのscenario_originフィールドのみ実装しhook拡張はdeferred。

## 移植忠実性チェックリスト (A2-009)
1. fork内長時間実行のSTALL誤報→subagents/*.jsonl bytes合算
2. idle時grep空マッチ→非例外(Python re では自然解消だが明示テスト)
3. busy判定はtranscript JSONL一次+TUI fallback、分岐(DONE/STALL/GATE/HARD_CAP)を合成fixture pytestで固定
4. 再帰遮断: 被験skill denylist(live-trial/iter-improve自身) (A2-008)
5. trial cwd=隔離workdir、全終了経路でtmux kill-session reaper

## 実装Wave (島DAG: A4-015)
- Wave1(並列): E1=SSOT機械層(convergence-policy.json/feedback_contract_ssot.py/build-flags.schema.json/plugin.json/validate-build-plan.py)、E2=文書ゲート層(orchestrate-gate-pattern.md/content-review-protocol.md/run-build-skill SKILL.md文言/goal-seek-paradigm.md/elegant-improvement-executor.md/feedback-loop-deployment.md)
- Wave2(並列): E3=run-skill-live-trial skill新設(Python harness+schema+references)、E4=run-skill-iter-improve skill新設
- Wave3: E5=強制層配線(lint-live-trial-verdict.py/lint登録/workflow-manifest phase/plugin-composition.yaml/pytest)
- Wave4: 4条件再検証+proposer≠approver独立承認
