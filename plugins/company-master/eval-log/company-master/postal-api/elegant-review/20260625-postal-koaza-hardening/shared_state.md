# shared_state (Phase1→2 中継・200字以内)

住所→郵便番号: enrich.postal_from_address→postal_api.lookup_postal の3段(structured+_town_variants小字/大字段階剥離→freeword→pick_best_prefix前方一致)。一意確定のみ採用。validate(g)が非空postalにorigin=japanpost/確度公的データ取得/日本郵便固定URL必須化・FIELD_ALLOWED_ORIGINSからuser_input除去。報告ケース997-0053回帰テストL536有。懸念=手入力postal経路封鎖/pattern名structured_town_trimmed衝突でsub-attempts縮約/prefix段実API未実証/docs小字境界記述欠。
