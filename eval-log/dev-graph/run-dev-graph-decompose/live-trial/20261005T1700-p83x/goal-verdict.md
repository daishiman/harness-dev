# goal-verdict: dev-graph:run-dev-graph-decompose (20261005T1700-p83x)

VERDICT: PASS

## 根拠

判定は fixture の実体と plugin script を自分で実行して確かめた。被験 session の自己申告 (`out/status.json` の PASS) は根拠に使っていない。fixture は書き換えていない。検証の前後で次の 3 つの値を取り、すべて一致した。

- path・mtime・size の一覧 digest `e08c5980…`
- 全ファイル内容の digest `2f2c391c…`
- `git status` の digest `b624f99a…`

対象 fixture: `/Users/dm/dev/dev/個人開発/harness/eval-log/dev-graph/live-trial-fixtures/p83x-decompose`

### 前提: 初期化と repository context
- `resolve-repo-context.py --mode read --repo-root <fixture>` は exit 0 だった。`repo_root` は fixture の realpath と一致し、`repository_id=local:sha256:039a54dd…` は `config.json` の値と同じだった。`root_trust_evidence` の 3 項目はすべて true だった。
- `validate-graph-schema.py --graph .dev-graph/state/graph.json --repo-root <fixture>` は `valid=true`、`violation_count=0` だった。
- init receipt (`.dev-graph/state/receipts/init-20261005T050912288879Z.json`) は `status=applied`、`planned_changes=33`、`schema_result.valid=true` だった。被験 session による 2 回目の init は `noop 0 0` だった (transcript [54])。

### 検証項目 1: feature+architecture DAG が循環なし
- 被験 session が C02 に渡した入力 `.dev-graph/cache/decompose-macro-input.json` (sha256 `45e9a9fa…`) を使い、`build-graph-node.py add --dry-run` を自分で再実行した。その際 planner が返す node をメモリ上で取り出して調べた。
- 結果は `status=preview`、`valid=true`、`pre_write_validation.findings=0`、`planned_count=3`、`node_ids=[arch-todo-api, feature-auth, feature-todo]` だった。`input_sha256` は被験 session と auditor の値と一致した。
- `depends_on` の edge は `feature-todo → feature-auth` の 1 本だけで、Kahn 法で `acyclic: True` を確認した。両 feature の `architecture_refs` はどちらも `arch-todo-api` を指す。writer の `_macro_edges` は、`depends_on` の先が feature であることと `architecture_refs` の先が architecture であることを強制しており、これも通過した。
- want の指定 (architecture 1 件、feature 2 件、TODO は認証に依存) と一致する。

### 検証項目 2: task 粒度の混入なし
- 計画 node の kind は `architecture`、`feature`、`feature` の 3 件だけだった。task や issue の kind は 0 件だった。
- 3 node とも `parent_feature`、`feature_package_id`、`phase_ref` が null だった。P01..P13 に相当する node はない。
- `run-system-dev-plan` と `register-package` の呼出しは、transcript でも subagent transcript でも 0 件だった。

### 検証項目 3: 全 node が draft の preview である
- 計画 node 3 件は、どれも `status=draft`、`confirmation_status=draft`、`evaluation_status=pending` だった。
- `github_publication.mode=local_only`、`issue_linkage=null`、`beads_linkage=null` で、`tracker_binding=none` は 3 件とも同じだった。
- dry-run の結果は `status=preview`、`dry_run=true`、`applied_count=0`、`write_count=0` だった。`features/`、`architecture/`、`tasks/`、`issues/` は空のままで、`.dev-graph/state/receipts` には init receipt しかない。
- feature 2 件は macro 必須項目をすべて非空で持っていた。feature-auth は purpose と goal に加えて scope_in 3 件、scope_out 3 件、acceptance 3 件、architecture_refs 1 件。feature-todo は scope_in が 4 件で、ほかは feature-auth と同じだった。

### 検証項目 4: 外部 write 0
- fixture に `.beads/` はない。`.git/dev-graph/` (coordination store) も作られていない。
- `config.json` は `github.enabled=false` だった。
- 被験 session の transcript と auditor subagent の transcript (`~/.claude/projects/-Users-dm-dev-dev------harness/4c621a61-…/subagents/agent-a59cbd9ed47d276d6.jsonl`) にあるすべての Bash を走査した。`bd`、`gh`、`bd-bridge`、`gh-bridge`、`build-github-projection` の呼出しは 0 件だった。

### 検証項目 5: 元の graph の digest が変わっていない
- 現在の `graph.json` の sha256 は `27ef0078ae9bf6e61be1b9a6da5a5c94d30fbcd84db5f71d7c370e4e88e66177` だった。init が生成する空 graph `{graph_revision:0, nodes:[], schema_version:"1.0.0"}` を正規に直列化した値と同じである。mtime は init 時刻 (14:09:12) のままだった。
- 被験 session が dry-run の前後で記録した digest も、どちらも `27ef0078…` だった (transcript [136])。私自身の dry-run 再実行の前後でも変化はなかった。

### 検証項目 6: feature を通常の C02 add として直接登録していない
- 入力の feature 2 件は `macro{purpose, goal, scope_in, scope_out, acceptance, architecture_refs}` を持ち、`classification` を持たない。architecture は `classification={reason, decision:"c14_macro_contract"}` の形で、同じバッチの feature から引用されている。
- dry-run receipt の `classification.decision` は 3 件とも `c14_macro_contract` (confidence 1.0、margin 1.0) だった。feature の `classification_reason` は `declared by the C14 macro contract (run-dev-graph-decompose)` だった。
- 否定側も確かめた。`classification` を付け `macro` を付けない通常形式の feature add をメモリ上で `_plan_add` に通すと、`feature_requires_c14_macro_contract` で拒否された。通常経路で feature を直接登録できないことを writer 自身が強制している。

## 経路制約
- Skill の起動: `dev-graph:run-dev-graph-init` ([37])、`dev-graph:run-dev-graph-decompose` ([57])、`dev-graph:run-dev-graph-node` (`add … --input .dev-graph/cache/decompose-macro-input.json --dry-run`、[130]) の 3 つを、どれも Skill tool で実際に起動していた。init と C02 の実体は、各 SKILL.md が委譲先と定めた正規 script (`build-init-scaffold.py`、`build-graph-node.py`) だった。
- 責務 prompt を先に読んだか: `prompts/R1-elicit.md` から `R6-dryrun.md` まで 6 本の全文を `cat` で読んでいた ([63]。結果に 6 本の見出しと `## 出力指示` が 6 個ある)。読んだのは C02 入力を作る [113] より前だった。`references/prompt-common-layers.md` と C02 の SKILL.md も読んでいた。
- 独立 auditor: `Agent(subagent_type="dev-graph:dev-graph-integrity-auditor")` を実際に起動していた ([115])。meta.json の agentType も一致する。auditor は read-only で、Bash は cat、grep、sed と C02 の dry-run だけを使った。6 項目に判定を付け、総合 verdict は PASS、findings は 0 件だった。被験 session は、この結果が返ってから C02 preview へ進んでいた。
- 代行や直接書込みの有無: Write は 2 回だけだった。1 回目は C02 の入力 JSON `.dev-graph/cache/decompose-macro-input.json` である。C02 SKILL.md は「skill は分類結果と section 本文を入力 JSON に整形するだけ」で `--input <repo 内 JSON>` を使うと定めており、writer は repo の外に置いた入力を拒否する。置き場所も config の `local_state.cache` の配下なので、正規の入力経路である。2 回目は `out/status.json` だった。graph、config、content、receipt を Write、Edit、heredoc で直接書いた形跡はない。成果物を作る自作 script もない (自作の python one-liner は preview JSON の読取りだけだった)。
- 人間への質問と gate での待機: AskUserQuestion の呼出しは 0 回だった。user 発話は最初の指示と auditor の完了通知 (task-notification) だけだった。poll-state の `gate_ticks` は 0 である。Pre-choice の選択は、task.md の「途中で人間に質問しない」に従って accept-as-is を自分で選んでいた。

### 参考 (blocker ではない所見)
1. fixture に C02 の入力ファイル `.dev-graph/cache/decompose-macro-input.json` が untracked のまま残っている。graph でも content でも外部 write でもないため、検証項目には当たらない。ただ、dry-run のあとに cache が 1 件増える点は、運用上の残り物として記録しておく。
2. C02 の dry-run preview の JSON には、node ごとの `status`、`confirmation_status`、`evaluation_status` が出ない。そのため被験 session は「全 node が draft」を writer の source (770 行目と 778 行目) から推論していた。結論は私の独立検証と一致する。ただし R6-dryrun の受入条件「全 target/operation/digest 表示」から見ると、preview の表示が足りない。
3. SKILL.md は ready feature を「機能間 depends_on 充足」と定義している。この定義なら、依存のない feature-auth は ready に当たりうる。被験 session は「draft なので ready ではない」と判断して R2b (planner 起動) を行わなかった。`--dry-run` で planner を起動すると write が生じるので、この判断には妥当性がある。ただ、ready の定義が SKILL の中で一意に決まっていない。
4. `artifact_delivery.pre_choice_forbidden` は subagent を禁じている。一方で Macro flow の手順 2 は、C02 preview の前に独立 auditor を求めている。SKILL の契約に緊張関係がある。今回は task.md の明示要求に従って auditor を起動しており、違反とは扱わない。
5. 被験 session は終了後に `build-external-intelligence-runtime.py finish` を呼び、`invalid_request` で失敗していた。被験 skill の範囲外の呼出しで、fixture への影響はない。

## blocker
なし

gate_response_count: 0
