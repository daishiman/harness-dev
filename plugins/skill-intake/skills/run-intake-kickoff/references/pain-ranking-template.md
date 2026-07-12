# Pain Ranking Template (kickoff Q3)

ユーザーから 1〜3 件を取り、以下の構造に揃える。

```json
[
  {"task": "顧客アンケート集計", "frequency_per_week": 3, "minutes_per_run": 45},
  {"task": "週次レポート作成",   "frequency_per_week": 1, "minutes_per_run": 120}
]
```

## 確認順序

1. 「最も時間を奪っている作業は何ですか?」 (task 名)
2. 「週に何回くらいやりますか?」 (frequency_per_week)
3. 「1 回あたり何分かかりますか?」 (minutes_per_run)

3 件以上挙げられた場合は上位 3 件に絞る。
