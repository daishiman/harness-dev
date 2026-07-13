# C07 responsibility — synchronization conflict verification

`dev-graph-sync-conflict-verifier` は独立 context で local graph と tracker projection の差分、`id + updated_at` conflict、retry queue、single-writer authority を read-only 検証する。

- 入力: local graph、binding config、dry-run projection、retry/conflict evidence。
- 出力: `PASS|FAIL`、競合分類、authority side、解消手順。
- 禁止: GitHub/Beads への write、token/node ID の正本保存。
- 完了: local正本・外部projection・conflict policy・dry-run冪等性を個別判定する。
