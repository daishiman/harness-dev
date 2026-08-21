# dev-graph live-trial verdict の再導出記録 (2026-08-21)

## 何をしたか

`live-trial-verdict.py#behavior_closure_files` が manifest `dependencies` を
digest 対象へ含めるよう修正された結果 (load 集合 == digest 集合の不変条件回復)、
既存 9 verdict の `skill_dir_tree_sha` が定義変更により stale になった。

対象 (run-id は据え置き = 同一 run の verdict 再導出であり新規 trial ではない):

| skill | run-id |
| --- | --- |
| run-dev-graph-decompose | 20260821T040000-tk3 |
| run-dev-graph-init | 20260821T030000-tk2 |
| run-dev-graph-node | 20260821T030000-tk2 |
| run-dev-graph-render | 20260821T030000-tk2 |
| run-dev-graph-requirements | 20260821T030000-tk2 |
| run-dev-graph-schedule | 20260821T030000-tk2 |
| run-dev-graph-status | 20260821T030000-tk2 |
| run-dev-graph-sync | 20260821T050000-tk4 |
| run-dev-graph-system-spec | 20260821T030000-tk2 |

## なぜ再実走でなく再導出が正当か

stale-sha は通常「被験 skill の挙動面が verdict 後に変更された」ことを意味するが、
今回は**成果物のバイト列は不変で、digest 関数の定義が広がった**ケースである。
再導出が実走と等価であることを、以下の事実で機械的に確認した。

1. 新たに closure へ入った依存 (skill-governance-adapters 由来 21 ファイル) の
   最終更新は **2026-08-21T01:49:34** が最大。
2. 各 trial の `transcript.jsonl` 最終更新は **03:15:44〜03:15:46** (tk2/tk3)、
   **08:11:55** (tk4)。
3. よって 9 回の実走はいずれも、現在 digest している**まさにそのバイト列**に対して
   行われている。closure の拡張は「その run で実際に load されていた plugin を
   digest へ追加した」だけで、run の内容とは矛盾しない。

## どう再導出したか

`skill_md_sha256` / `skill_dir_tree_sha` を手で書き換えてはいない (それは緑化)。
保存済み一次証拠を入力に `live-trial-verdict.py` を再実行し、CLI 自身に digest を
再計算させ全 gate を再通過させた。

```
python3 plugins/harness-creator/skills/run-skill-live-trial/scripts/live-trial-verdict.py \
  --workdir eval-log/dev-graph/<skill>/live-trial/<run-id>/ \
  --transcript eval-log/dev-graph/<skill>/live-trial/<run-id>/transcript.jsonl \
  --skill-dir plugins/dev-graph/skills/<skill> \
  ...(launch/completion/goal-result/blockers/nudge/gate/scenario/tier/timeline は
      旧 verdict の値をそのまま引き渡し)
```

9 件すべて exit 0。差分を旧 verdict と全 field 比較した結果、変化したのは
`skill_dir_tree_sha` と (run-dev-graph-sync のみ) 新設の
`gate_contract_evidence` だけで、`actual_model` / `transcript_sha256` /
`overall` / `environment.claude_version` / `args` / `scenario_origin` は
1 件も変化しなかった。

## 2 回目の再導出 (CI 追跡中に判明した 2 件の digest 汚染)

CI の `plugins/dev-graph` 失敗を追う過程で、closure digest が
「ローカルで何を実行したか」に依存する経路が 2 本見つかり、いずれも塞いだ。
そのため上記 9 verdict をもう一度同じ手順で再導出した (全件 exit 0、
変化は `skill_dir_tree_sha` と `timeline` のみ、判定入力に drift 0)。

1. **一時 cache の混入**: `add_tree` が `__pycache__` / `.pyc` しか除外しておらず、
   依存 plugin 配下で pytest を回すと `.pytest_cache/` が digest へ入っていた。
   `run-dev-graph-system-spec` だけ closure が古く見えたのはこれが原因
   (この skill だけが `system-spec-harness` を依存に持つ)。
   出荷もされず load もされないファイルなので deny-list で除外し、
   `tests/test_live_trial_harness.py::test_tree_sha_ignores_ephemeral_tool_caches`
   で回帰を止めた。同型の誤検出が `lint-skill-tree.py` の第13条にもあったため同時に修正。

2. **plugin manifest の version**: closure は manifest を丸ごと digest するので、
   `build-plugin-release.py` の version bump だけで plugin 内の全 verdict が stale になる。
   今回は bump → 再導出の順で解消したが、配布メタデータが挙動 digest に混じる構造自体は
   残っている (既知の摩擦源として PR に記載)。

## criteria-test receipt 9 件の再評価

`artifact-delivery-v1` の追加で被験 SKILL.md が変わったため、
`criteria-test/scenario-verdict.json` 9 件の `target.skill_md_sha256` も stale になった。
これは CLI 導出物ではなく人手の独立評価 receipt なので、**sha だけの書き換えはしていない**。
skill ごとに独立評価者を立て、差分が各 criterion の受入条件を変えるかを判定させ、
`test_refs` の pytest node を実際に再実行させたうえで receipt を書き直した
(`reviewer` は `-r1` → `-r2`)。live-trial criterion の参照は現行 closure と一致する
新しい run へ張り替えている。

副産物として、`run-dev-graph-system-spec` IN1 の旧 `independent:` 参照が
実在しない path (`.../r3-system-spec/.dev-graph/state/graph.json`) を指していたことが判明し、
実際に検証した r7-spec-lineage graph へ差し替えた。

## 副次的に判明したこと

`run-dev-graph-sync` の `gate_kind: contractual` は正当だった。
`plugins/dev-graph/skills/run-dev-graph-sync/SKILL.md` の frontmatter が
`external_mutation_guard` (L10) と `allowed-tools` 内の `AskUserQuestion` (L15) を
共に宣言しており、新設の接地検査が根拠 2 件を抽出して verdict へ焼き込んだ。
接地根拠なき contractual であれば CLI が exit 2 で拒否していた。
