# Phase2 システム・戦略・問題解決分析 findings（system-strategic-analyst・read-only）

## 1. 真の論点
根本原因=承認の停止点が「対話イベント(送信時APPROVE文字列)」に束縛され、人間の真の熟慮が宿る「データ状態(Notionチェック)」に束縛されていない。摩擦=承認行為の二モダリティ重複。
真の論点 = 「確認を消す」でなく「承認の所在を対話イベント→データ状態(Notionチェック)へ移設し、対話0でも安全網が誤送信を吸収する運用へ再設計」。
副次論点(cron完全無人)=明示defer。根拠: ユーザーは*確認*0は承認したが*不在送信*は未承認 / [[feedback_contract_pdf_pull_model]]と整合 / auto経路を純Python安全コアで作れば将来cron土台(プラスサム)。

## 2. send_guard 8フィールドの Class A/B 分離
**Class A 改竄検出/完全性(人間非依存・auto-approveで完全温存):** recomputed_ph==plan_hash / len(units)==count・per-unit content_hash再計算(不一致は content_hash_mismatch で当該unit非送信) / from_verified / unresolved空(skip) / reserved_log_id+content dedup / **C-1 suppress再検証(t2でNotion再取得・subtract-only)**。
**Class B 人間内容承認/独立停止点(auto-approveでトートロジー化):** approved_*束縛(self-deriveで自作物照合に退化) / approved_nonce==actual_nonce(rendered本文を読ませる強制)。
判定: auto-approveで Class A は1つも失わない。Class B はトートロジー化するが意図通り(内容承認は送信対象=✅へ再配置)。ただし nonce の「rendered最終本文を読ませる」役割のみ箱チェックに再配置不能 → **nonce は auto-approveで撤去し content-assurance を canary既定+source-audit gate へ移す**のが唯一整合。

## 3. S-1 安全網再配置（因果ループ）
機械層が t1-t2 間の構文誤りを人無しで fail-closed 吸収(空{{}}→unit skip / 不正addr→skip / content_hash改変→検出 / C-1→✅外し subtract)。機械が捕捉しないのは「構文validだが意味的に誤った本文」=nonce/目視のみが捕捉。対話0での代替=**canary既定**(数通送り実inboxで検品→✅広げる。実メール検品>端末プレビュー)。
強化ループR(安全網増→信頼↑→熟慮↓→意味誤り流出)を均衡ループB(canary既定→実メール検品→意味誤り捕捉→修正)で打ち消す。ループを切る不変点=canary-first既定(skipは明示flag)。

**収束したトレードオン解(1案):** `run-notion-gmail-send --auto-approve`: (1)build-plan自動実行 (2)source-audit自動・high severity残存なら0送信fail-closed (3)新鮮planから承認tuple self-derive・**per-unit guard loop必須通過**(Class A全有効) (4)**canary既定**: plan の content-dedupキーが送信ログDB未出現の新規campaignなら先頭N件(既定3)のみ送信し停止・再実行で残り (5)nonce撤去・content-assuranceを canary+audit へ再配置。対話APPROVEモードは無改変併存。

## 4. 完成運用像
1.(Notion既存業務)送信対象=✅・本文DBにメッセージ対象=✅で本文記入 2.`/run-notion-gmail-send --auto-approve`→build-plan→audit gate→(初回)canary 3通→停止 3.届いた3通を実inbox検品 4.同コマンド再実行→残り送信(dedupでcanary skip)。
人間アクション = コマンド2回+検品1回。端末APPROVE/nonce 0。真の0望むなら `--auto-approve --full --skip-canary`。canary既定・skipは明示flag=fail-safe既定。
compose正しさ: canary後Notion編集→plan_hash変化→新規campaign扱いで再canary(変更後再検品)。content-dedupはcampaign非依存で未変更unitは二重送信不可。

## 5. S-2 feedback_contract 改訂
- lint-content-review L131: 変更されたSKILL.mdは elegance/rubric verdict が PASS かつ reviewed_sha==現sha 必須 → **任意byte変更でverdict再生成必須**(独立SubAgent genuine・proposer≠approver)。
- 最小blast → 変更SKILL.mdを run-notion-gmail-send 1枚に絞る(dry-run/source-audit無改変)。
- **IN1改訂**(test): --auto-approveが新鮮build結果から承認tuple self-deriveしてもper-unit guard loop通過・plan改竄(content_hash再計算)・C-1 suppress再検証・未置換skip・From検証・送信件数が新鮮plan件数を超えない・nonce強制は対話モード限定を test_send_campaign で検証。
- **IN3新規**(inner/test): --auto-approveが (a)内部build-plan→source-audit実行しhigh severityで0送信fail-closed (b)content-dedupキー未出現の新規campaignでcanary既定先頭Nのみ送信し残り停止 (c)2回目実行でdedupでcanary skipし残り送信 を検証。
- **OUT1改訂**(elegant-review): 対話0 auto-approveでも承認所在をNotionデータ状態へ移設しClass A+audit gate+canary既定+C-1で対話0誤送信リスクを吸収する設計が目的最適反映・nonce撤去とcanary再配置が過不足ないことを4条件で確認。
- 新規test 9検証点(§5)。**実装gotcha**: canary-first検出は plan_hash一致で判定してはいけない(canary plan_hash≠full plan_hash)。「full planのcontent-dedupキーが送信ログDBにsentで存在するか」で判定(content dedupはcampaign非依存)。

## 6. 実装タスク依存順
A 契約(直列): A1 トレードオン確定 → A2 feedback_contract改訂(skill-improve)。
B 実装(send-campaign.py内直列/層跨ぎ並列): B1 --auto-approve経路(内部build-plan+self-derive+nonce無効化) → B2 source-audit gate → B3 canary-first検出(full plan dedupキー未sent判定)。B4 R1-orchestrate(auto時 fork-LLM→決定論verify-plan.py) ∥ B1-3。
C テスト(並列): C1 test_send_campaign 9検証点をSubAgent分割並列。
D 検証(直列): D1 SKILL.md更新 → D2 content-review verdict再生成(新SHA独立genuine) → D3 elegant-review 4条件 → D4 pytest全+lint緑(pytest直接[[feedback_run_ci_checks_excludes_pytest]])。

## 7. 改善優先順位
CRITICAL: C-1]auto-approveを必ずper-unit guard loopに通す(Class A全温存・self-derive退化で無音誤送信穴防止) / C-2]canary-first既定(skipは明示flag)。
HIGH: H-1]source-audit auto-gate(high severity→0送信) / H-2]content-review verdict新SHA genuine再生成 / H-3]feedback_contract criteria改訂。
MEDIUM: M-1]auto時 fork-LLM→決定論verify-plan.py / M-2]README三本柱に対話0 mode行追記(トレードオフ正直明示) / M-3]無人cronは明示defer。

C1矛盾なし/C2漏れなし/C3整合(dry-run無改変)/C4依存整合(canary検出はdedupキー基準・plan_hash基準でない点が唯一の依存罠)。
