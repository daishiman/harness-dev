# goal-verdict: dev-graph:run-dev-graph-node (20261005T1600-p83o)

VERDICT: PASS

## 根拠

対象の約束 (SKILL.md description): 「dev-graph artifact を正規 path へ atomic 追加・差分更新」する。
fixture: `/Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/live-trial-fixtures/p83o-node`。
out/status.json は判定に使っていない。下の確認は全て read-only で行った (sha256 採取、validate-graph-schema.py、`resolve-repo-context.py --mode read`、`build-graph-node.py --dry-run`)。

### 準備: init と 5 kind の add

- `.dev-graph/state/receipts/` には `init-20261005T032634450053Z.json`、`node-r000001-add.json`、`node-r000002-update.json` の 3 件がある。
- r1 は `operation=add`、`applied_count=5`、graph_revision 0→1。
- graph.json を python で読んだ結果は次のとおり。
  - `rev 2 nodes 5 feature 0`
  - 5 node は issue、task、specification、architecture、document が 1 件ずつ。
  - 5 node とも `tracker_binding=none`。
  - 5 node とも file_path は正規 root (issues/、tasks/、specs/、architecture/、docs/) の下にある。

### 本題 1: issue への section 追記 (apply まで到達したか)

**apply が発生したこと**
- receipt r2 の値:
  - `status=applied`
  - `operation=update`
  - `applied_count=1`
  - `graph_revision_before=1`、`graph_revision_after=2`
  - `node_ids=["issue-login-timeout"]`
- graph.json の `graph_revision` は 2。
- r2 の `graph_digest_after` は `sha256:362090de…4d139`。graph.json の canonical digest (sort_keys、compact) を自分で計算すると同じ `sha256:362090deadf46d0b21e83de6cfef6993538f98f37567fa63681945c84064d139` になった。

**graph_node_id と file_path が不変であること**
- graph 上の値は `issue-login-timeout` / `issues/login-timeout.md`。
- frontmatter の `graph_node_id` と `file_path` も同じ値。
- r1、r2 の値とも一致した。

**全置換ではなく追記だけであること**
- `shasum -a 256 issues/login-timeout.md` は `851b3027…81987` で、r2 の `sha256_after` と一致した。
- r2 の `sha256_before` (`73b22578…34f51`) は r1 の issue の `sha256_after` と一致する。
- r2 は `sections_appended=["調査メモ"]`、`sections_replaced=[]`、`unmanaged_body_preserved=true`。
- 本文を Read すると、`# 概要` から `## 検証証跡` までの既存 10 section がそのまま残り、末尾に `## 調査メモ` だけが増えている。
- transcript の diff 出力でも、変化は frontmatter の `updated_at` と `implementation_readiness.checked_at`、末尾 4 行の追加だけだった。
- build-graph-node.py の `_plan_update` を読んで実装も確認した。append_sections は `(len(lines), len(lines), …)` という末尾挿入の edit だけを積む。

**他 4 kind の node が無変更であること**
- `shasum -a 256` の結果は r1 の各 `sha256_after` と完全に一致した。
  - tasks/fix-session-lock.md: `ff14e4f6…`
  - specs/session-policy.md: `e7c50fb1…`
  - architecture/auth-backend.md: `54ed77bb…`
  - docs/auth-runbook.md: `222ad717…`
- graph 上の 4 node の `updated_at` は add 時刻の `2026-10-05T03:27:18.840208Z` のまま。

### 本題 2: feature の直接 add が fail-closed すること

**被験の実投入 (transcript)**
- 被験は `build-graph-node.py add --input .dev-graph/cache/inputs/add-feature-direct.json` を dry-run なしで実投入した (transcript row 160)。
- 出力: `{"applied_count": 0, "code": "feature_requires_c14_macro_contract", "status": "rejected", "valid": false, "write_count": 0}`、`exit=1`。
- 直後の確認結果: `graph-bytes-unchanged`、`rev 2 feature nodes 0`、`features/` は 0 件。

**独立の再現**
- 同じ入力を `--dry-run` で再投入した。
- 結果は同じ `feature_requires_c14_macro_contract` の rejected で、exit=1。
- 前後で graph.json の sha256 は `6033fd3c…68d0` のまま変わらなかった。
- `features/` は 0 件、receipt は 3 件のままで増えていない。
- 実装では `_plan_add` が `kind == "feature" and "macro" not in entry` を planning 段階で拒否する。拒否は lock、staging、書込みのどれよりも前に起きる。

### 本題 3: 最終 graph の validate

- `python3 plugins/dev-graph/scripts/validate-graph-schema.py --graph <fixture>/.dev-graph/state/graph.json --repo-root <fixture>` を実行した。
- 結果は `validate_exit=0`、`valid=True`、`graph_validation={status: pass, violation_count: 0}`、violations 0 件。
- 参考: task、spec、arch、doc の 4 node は readiness が incomplete (draft のため)。ただし graph_validation は pass で、task の検証条件には含まれない。

### C24 の repository 境界

- `resolve-repo-context.py --repo-root <fixture> --mode read` の repository_id は `local:sha256:7e2532ac…51a6b`。
- この値は config.json、init receipt、r2 receipt の repository_id と一致した。
- repo_root は fixture 自身を指している。

## 経路制約

**Skill の起動**
- transcript を python で抽出した。tool の内訳は Bash 17、Skill 2、Write 4、Edit 2。
- Skill tool で `dev-graph:run-dev-graph-init` (row 37) と `dev-graph:run-dev-graph-node` (row 67) を正規に起動している。

**責務 prompt を出力の前に読んだか**
- init の prompts は row 45 で読んでいる。
- node は row 78 の `cat prompts/*.md` で R0 から R4 までを一括で読んでいる。時刻は 03:26:39Z で、最初の add (03:27:18Z) より前。

**直接書込みの有無**
- Write と Edit の対象は 2 種類だけで、graph、config、content への直接書込みは 0 件。
  - `.dev-graph/cache/inputs/*.json` (writer への入力 JSON 3 種)
  - `out/status.json`

**writer の経路**
- graph と content への書込みは全て C02 単一 writer `build-graph-node.py` を経由している。init は `build-init-scaffold.py` を経由している。
- add と update は、まず `--dry-run` の preview を取り、`expected_graph_revision` を付けた CAS apply で適用している。
- feature だけは task の指示どおり実投入した (拒否)。

**代行と外部操作**
- 被験 skill の責務を代行する自作 script は無い。python one-liner は読取と比較だけ。
- Agent の起動は 0 件。pre-choice では subagent が禁止なので、これと整合する。
- AskUserQuestion は 0 件。
- external mutation guard の preview 発行は無い。gh と bd の実行も無い。
- 自分の評価中に Bash が pending guard context で一時ブロックされた。原因は並行中の別 trial (sync) の preview f52178fa で、この被験の transcript に guard の痕跡は無い。ブロックは迂回せず、解除を待ってから検証した。

## blocker

なし

gate_response_count: 0
