# C06 responsibility — graph integrity audit

`dev-graph-integrity-auditor` は独立 context で graph schema、DAG 非循環、orphan、参照実在、C14 が生成する macro feature 粒度を read-only 監査する。

- 入力: graph、schema、component inventory、関連 route report。
- 出力: `PASS|FAIL`、重大度付き finding、対象 node/path、再現 command。
- 禁止: graph・state・tracker の mutation、C02 single-writer の代行。
- 完了: schema/DAG/orphan/reference の各判定を明示し、未観測項目を PASS にしない。
