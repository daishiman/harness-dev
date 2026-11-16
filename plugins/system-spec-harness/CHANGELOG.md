# CHANGELOG

## 0.1.29 — 2026-11-16

- build-plugin-release.py の自動採番で作られた版。変更内容の記述は未記入。

## 0.1.28 — 2026-11-16

- build-plugin-release.py の自動採番で作られた版。変更内容の記述は未記入。

## 0.1.27 — 2026-11-14

- ref-system-design-knowledge の Gotchas から、harness-creator で削除された stop hook (`check-review-trigger.py`) への言及を外した。content-review の強制は CI / pre-push の `lint-content-review.py` だけになった。

## 0.1.26 — 2026-11-02

- Codexの実spawn・親子関係・fresh子context・監査定義の全文Read・終了応答を、保護された原ログから再検証する監査帰属を追加。
- runtime選択を評価・集約・resumeへ伝播し、Codexでの旧形式・混在台帳・memory上の偽indexを拒否。
- Claude既定の監査台帳1.xとの互換性を維持。host側の記録を必要とし、未観測の監査や自己申告を合格根拠にしない。
