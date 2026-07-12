# shared_state (Phase1→2 中継 / 200字以内)

company-master は会社名・住所・法人番号の断片から gBizINFO(正式名称/住所/法人番号)・日本郵便addresszip(郵便番号)・Web(電話)で補完し Notion企業マスタDBへ法人番号キーで upsert する plugin。構成=2 skill(build/backfill)+3 agent(resolve/enrich/upsert)+2 command+secret-guard hook+doctor診断。出力8列+確度4ラベル+備考定型+本文確認用URL。鍵=Keychain(notion/gbizinfo/japanpost BYO直結)。配布=public repo の marketplace。**決定: 配布モデルはリモート主導(clone不要)を主とする。**
