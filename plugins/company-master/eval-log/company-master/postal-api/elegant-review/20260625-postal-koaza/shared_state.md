# shared_state（Phase1→2 中継・200字以内）

postal_api は住所を`_split_address`でpref/city/town分解(`_strip_banchi`が最初のASCII数字で切る)→構造化+freewordの固定2クエリ→`pick_best`で一意確定のみ採用(誤値を入れない)。小字「字○○」を削る処理が両クエリに無くtown_nameに小字が残存、API404(notfound→miss握りつぶし)で空欄化。テストはtests/test_company_master.pyに集約、小字分解と404後の町域フォールバック検証は不在。
