# shared_state (Phase1 → Phase2 中継, 200字以内)

Notion2DB直積×Gmail個別送信を冪等記録するrun-skillのbrief。schema14必須と主要allOf条件は形式上充足。懸念は外部依存(shonai.inc承認/Keychain鍵/送信ログDB ID)が未確定なまま承認済み前提で出力契約を組む点、本文空除外と未記入2件の扱いの揺れ、Hook候補とhook_events欠落。固有値5件は全てbrief1箇所のみ出現。

## Phase1 懸念点(後続3アナリスト共有)
- C2漏れ: 送信ログDBのDB IDが未確定(open_questions[2])のまま冪等記録の出力契約が成立
- C4依存: shonai.incのDWD+gmail.send承認を済み前提とするが裏付けファイル無し(GCP手順書は汎用ドメイン例)
- C4依存: Keychain SA鍵のsvce/acct未確定のままgmail-send responsibilityが鍵参照前提
- 準拠: placement_candidatesにHook含むがhook_eventsキー無し
- C3整合: open_questions[1]「未設定ならGCP先行」vs key_constraints[3]/goal「承認済み前提」の揺れ
- C1矛盾: open_questions[3]「本文未記入2件」vs key_constraints[2]/checklist「本文空を事前除外」の扱い不一致
- 準拠: last_audited_date有りaudit_trigger欠落(required外だが再監査条件不明)
