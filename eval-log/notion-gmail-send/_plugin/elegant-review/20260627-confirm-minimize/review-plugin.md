# elegant-review: notion-gmail-send 確認事項の最小化 (run-id 20260627-confirm-minimize)

## ゴール
自動化のため確認事項を最大限省略化し、承認を端末 APPROVE 文字列から Notion `送信対象=✅` へ移す再設計が、エレガント(最小複雑性で目的達成)かつ正しい(誤送信・二重送信を防ぐ)かを 30 思考法で検証・改善する。安全保証は機械層で担保したまま人手確認のみ削減。

## プロセス
- **Phase 1 思考リセット俯瞰** (`elegant-reset-observer`): 確認0実装が未コミットで存在することを確認、7件の seed 懸念を提示。
- **Phase 2 並列多角分析** (3 SubAgent・30思考法全使用): 論理構造(A2)/メタ発想(A3)/システム戦略(A4) が独立収束。seed1(auto Class A 同語反復)・seed2(high全停止非対称)を実証、seed7(C-1毎回全件query)を反証。
- **ユーザー意思決定** (AskUserQuestion): Q1=「件数に関わらず常に1回確認」/ Q2=「canary は opt-in 据置」。
- **Phase 3 改善実行** (proposer): コード+全ドキュメント改修。**独立承認** (approver≠proposer) で 4 条件全 PASS・APPROVE。

## 核心的発見と設計判断
1. 3アナリストが独立に同一核心へ収束: 「確認0」の弱点は端末確認の有無でなく、**承認(authorization=Notion✅)と確認(verification=目視)を混同し、auto で"確認"次元だけが黙って脱落**している点。
2. ユーザーは「真の0」でなく**最小非ゼロ確認(常に1回)**を選択 = A3 ダブルループ思考が指摘した最適点を自ら選んだ。
3. エレガンスの本質(A4 トレードオン): 「確認の手間」と「誤送信リスク」は両立可能 = 人手確認を増やさず機械層で安全を足す。

## 改善内容
- **既定を「確認0」→「最小確認1回」へ転回**: 引数なし=preview(要約[件数/先頭To/本文先頭/抑制·skip/⚠️警告]+CONFIRM_TOKEN を出し exit 10・送信しない) → 人間の単一確認 → `--confirm-token <plan_hash>` で plan_hash 一致時のみ送信(不一致 exit 11)。重い APPROVE+nonce 読解強制を軽量な単一確認へ圧縮。確認は R1 散文でなく**コードのゲートで機械強制**。
- **無人確認0(cron)** = `--auto-approve`/`--yes` を温存(「最悪0でも問題ない」を満たす)。
- **正直化(F1/F2)**: README §195 の「literal誤記を source-audit が緩和」矛盾を訂正。「Class A は確認回数と独立に常時オン(plan改竄検出含む)」過大表現を是正 — 非対話では plan_hash/content_hash 照合は self-derive ゆえ恒真(defense-in-depth)、実効独立検証は source-audit/fresh rebuild/C-1/From/dedup。
- **gate階層化(F5)**: 既定 preview は high を ⚠️ 警告化し全停止しない(該当 unit は送信時 skip)/無人 cron は fail-closed。
- **C-1 fail-closed(F8)**: recipient_db 未解決時は非対話で送信中断。
- **素人警告(F7)/秘書CC不達(F9)** を README に明示。
- **canary opt-in 据置(F3)**・**二段フラグ見送り(F6)** はユーザー判断。

## 検証4条件 (post-fix)
| 条件 | 判定 |
|---|---|
| 矛盾なし | PASS |
| 漏れなし | PASS |
| 整合性あり | PASS |
| 依存関係整合 | PASS |

- 30 思考法全使用 (used=30 / skipped=0)。proposer≠approver で独立 APPROVE。
- pytest 198 passed / feedback-contract lint OK / SKILL.md 162行。

## next-step (コミット時)
- SKILL.md を大きく変更したため、コミット/PR 時に content-review verdict を**現 SHA で独立 SubAgent 再生成**する(SHA 書換は偽装・genuine 再生成必須)。
- deferred: F10(db2 3重query 効率改善)・preview 時の PII plan.json 書出し要否再評価。
