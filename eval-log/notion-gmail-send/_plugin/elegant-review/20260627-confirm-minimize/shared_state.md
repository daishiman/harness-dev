# shared_state (Phase1→2 handoff, ≤200字)

対象=Notion2DB→Gmail一斉個別送信plugin。承認を端末`APPROVE`文字列からNotion『送信対象=✅』(データ層)へ移し確認0 auto-sendを既定化。送信直前にsource-audit高severityゲート→最新Notionからfresh rebuild→承認tupleをself-derive→per-unit send_guard(Class A)+content冪等dedup。検証主眼=確認0での誤送信/二重送信の穴、自己生成planへのguard照合の同語反復性、README/SKILL主張とsend-campaign.py実装の一致。

---

## Phase1 観測者の seed 懸念（後続は検証/反証する。鵜呑み禁止）

1. **auto で Class A の plan_hash/件数/content_hash 照合が同語反復**: 同一プロセス内で compose→直後に同じ units から再計算して比較するため改竄介在窓が無く常に一致。auto で実効する guard は reserved 行存在/未置換token/from検証/C-1 suppress/dedup に縮退。README/SKILL の「Class A は確認回数と独立に常時オン」が plan 改竄検出の保護価値を auto で過大表現していないか。
2. **source-audit high ゲートの全停止がモード非対称**: auto は high 1件で全体0送信。`empty_substitution` も high。1宛先の空フィールドが全停止。dry-run/対話は当該unitだけskip。手間最小化の狙いと衝突しないか(過剰結合)。安全側だが整合性論点。
3. **秘書CC不正で unit 全体 skip→プロ人材本人にも届かない**: docとは一致するが到達性(deliverability)の境界が利用者に伝わるか。
4. **proposer==approver の独立検証が auto で不在**: context:fork二段確認は対話限定。auto の独立検証=決定論セルフチェックだが懸念1で自己生成データ再計算。正しさの最終拠り所が source-audit+Notion運用+canary検品に集約。
5. **hook は best-effort・射程狭い**: `gmail.googleapis.com`文字列含むBashのみ対象。script内urllibは射程外。`send-campaign.py`部分文字列含めば無条件許可(擬装余地)。正本がsend_guardゆえ影響限定。
6. **doc/impl一致は概ね良好**: fresh rebuild/content dedup/C-1 subtract-only/canary安定順/exit code/冪等キーcampaign非依存/--allow-resend/quota exit3 reserved戻し は三者整合。乖離リスクは「断言の強さ」側(懸念1・4)。
7. **C-1 suppress再検証が毎送信前にDB2全件query**: large規模で追加負荷。`st is None`(ページ削除)もsend_suppressed扱いの整合性。

重点: 懸念1(auto Class A 同語反復)と懸念2(high全停止非対称)を「確認0設計のエレガンス×正しさ」で検証。
