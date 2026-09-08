# goal-verdict: dev-graph:run-dev-graph-node (20260907T0330-gm4)

VERDICT: PASS

## 根拠 (out/status.json に依存せず transcript とファイルシステムで裏取り)

### 準備 (5 kind 登録)

- transcript step 42: staging `txn-001` に対し公式 `validate-graph-schema.py` を実行し `valid:true / violations:[] / EXIT=0`。
- step 43: `mkdir .dev-graph/locks/graph.lock` を取得したうえで staging から content root と
  `.dev-graph/state/graph.json` へ tmp→`mv` の atomic replace。結果 `COMMIT=applied`、`graph_revision=1`、5 node。
- 現物確認: `.dev-graph/state/graph.json` に issue/task/specification/architecture/document の 5 node が実在し、
  各 `file_path` の md が content root に存在する。

### 本題 1: 冪等な連続更新 — 実行され apply に到達

- 実行済み。step 48-55 で staging `txn-002` を作成 → 本文 1 section 追記 → step 54 で
  `validate-graph-schema.py` EXIT=0 → step 55 で lock 取得のうえ apply、`COMMIT=applied`、
  `graph_revision 1 -> 2`。staging 編集で終わっていない。
- graph_revision 増加: 独立確認済み。現 `graph.json` の `graph_revision=2`、
  receipt `node-update-txn-002.json` の `graph_revision_before=1 / after=2` と一致。
  receipt `node-add-txn-001.json` は `before=0 / after=1` で連続している。
- identity 不変: 現 graph 上の `gm4-issue-001` の `graph_node_id` / `file_path`
  (`issues/gm4-issue-001-digest-duplicate-delivery.md`) は txn-001 適用時から不変。
  評価者側で `diff staging/txn-001/issues/... issues/...` を実行した結果、差分は
  `updated_at` 1 行と末尾 `## 追加調査ログ` 4 行のみ。**既存本文の全置換は発生していない (追記のみ)**。
- 他 4 kind 無変更: 評価者側で `diff -q` を実行し tasks/specs/architecture/docs の 4 ファイルが
  txn-001 staging と bit 一致。transcript step 57 の独立 digest 比較
  (`node_digest SAME / file SAME`、issue のみ sections 9→10) とも一致。
- `diff staging/txn-002/issues/... issues/...` は差分 0。commit された現物が検証済み staging と同一。

### 本題 2: feature の直接 add — 実際に投入され fail-closed

- 実行済み。step 60 で `feature-direct-add.json` (`artifact_kind: "feature"`,
  `source_lineage.origin_kind: "manual"`, `source_plugin: null`) を作成し、
  step 61 で C24 `resolve-repo-context.py --mode write` を通し staging `txn-003` を用意、
  step 63 で feature node を実際に staging へ構成、step 64 で validator を実行。
  「自明として省略」ではなく writer 経路へ投入されている。
- 拒否: step 66 で staging `txn-003` を破棄 (rollback)。receipt
  `node-add-txn-003-rejected.json` が `status:"rejected" / expected_count=1 / applied_count=0`、
  拒否 code `feature_requires_c14_macro_contract` として残っている。
- 拒否後の状態 (評価者が現物で確認): `features/` は 0 件、graph の
  artifact_kind は issue/task/specification/architecture/document 各 1 で feature node は 0、
  `graph_revision` は 2 のまま (拒否で revision が進んでいない)。graph は破損していない。
- 留保 (受入は妨げない): fail-closed は skill contract (R1-classify 責務境界) の判断で成立しており、
  `validate-graph-schema.py` は staged feature node を `valid:true / EXIT=0` で通過させた
  (step 64、および step 65 の grep で validator が C14 provenance を検査しないことを確認)。
  機械 gate による重複防御は存在しない。この事実は receipt の `observed_gap` に実行者自身が
  正直に記録しており、隠蔽や偽装は認められない。宣言 goal (feature は C14 由来のみ features/ へ) の
  結果としての達成は現物で確認できるため PASS を妨げないが、skill の防御は prompt 契約単層である。

### 本題 3: 最終 graph の schema 検証

- 評価者が独立に実行:
  `python3 plugins/dev-graph/scripts/validate-graph-schema.py --graph <fixture>/.dev-graph/state/graph.json --repo-root <fixture>`
  → `{"valid": true, "violations": [], "implementation_readiness": "complete"}`、`EXIT=0`。

### 単一 writer / 自作スクリプト代行の有無

- graph・content への書込みは全て step 43 / 55 の lock 取得 + tmp→`mv` の同一経路のみ。
  それ以外に content root や `.dev-graph/state/` を書き換えた操作は transcript 上に存在しない。
- python3 heredoc (step 45 / 46 / 57) は section 数・digest・revision の**検証専用**で、
  graph/content を書いていない (書込み先は `/tmp/gm4-before.json` のみ)。
  schema 検証は全て plugin 同梱の公式 `validate-graph-schema.py` を使用しており、代替実装はない。
- external mutation guard の preview は発行されていない (transcript の該当語は task.md 引用と
  無関係な過去 failure signature のみ)。

### 手続き上の逸脱 (goal 達成は妨げないため記録のみ)

- `run-dev-graph-node` は `Skill` tool 経由で起動されず、SKILL.md と prompts を読み込んで
  main context で実行された (`Skill` 呼出は `run-dev-graph-init` の 1 回のみ)。
  被験 skill の指示文書が実際の統制文書として使われ (receipt の contract_refs が SKILL.md / R1-classify を参照)、
  結果も現物で検証できるため、宣言 goal の達成判定には影響しないと判断した。
- 責務 prompt は step 19 で `sed -n '1,40p'` により 77 行中 40 行までしか読まれていない
  (R1-classify のみ step 59 で全読)。未読部 (Layer 5-7) の要求 (atomic update / immutable receipt /
  新 graph revision / 失敗時 applied_count=0) は結果として全て満たされているため、実害は確認できない。
