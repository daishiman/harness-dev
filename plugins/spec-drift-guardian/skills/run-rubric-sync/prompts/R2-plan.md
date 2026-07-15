# Prompt: R2-plan

> このファイルは 7 層プロンプトの Markdown 表現。`run-prompt-creator-7layer` の
> seven-layer-markdown-template.md を提示形式の補助とする。Layer 番号と依存方向 (L1 ← L7) は不変。
> L5 サブ構造は seven-layer-format.md「Layer 5 契約」(l5-contract v2.0.0) に従属する。

## メタ

| key | value |
|---|---|
| name | plan |
| skill | run-rubric-sync |
| responsibility | R2 (propose mode・read-only。最小 Edit 差分 + allowlist + pre-image hash を組立) |
| layers_covered | [L1, L2, L3, L4, L5, L6, L7] |
| output_schema | ../../schemas/sync-proposal.schema.json (status=proposed) |
| reproducible | true (同 impact・同ファイル現状 → 同 proposed_diff/pre_image_sha256/proposal_sha256) |

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール
- **propose mode は read-only**: 実ファイル (rubric/schema/template) を一切 Edit しない。生成するのは `sync-proposal.json` (status=proposed) のみ。
- 出力先は `$CLAUDE_PROJECT_DIR/.spec-drift/<issue>/sync-proposal.json`、`schemas/sync-proposal.schema.json` 準拠。
- `target_path` は `references/apply-gate-policy.md` §1 の allowlist glob 内**のみ**。外は提案に含めない。
- 決定論部分 (target×axis 裏取り・pre-image hash・proposal_sha256) は Bash/script、意味判断 (最小差分の文面) のみ LLM。

### 1.2 倫理ガード
- Edit 差分は**最小**に留める (影響軸に無関係な整形・並べ替えを混ぜない=過剰変更を C04 に FAIL されないため)。
- 対象ファイル現状を必ず Read してから before/pre-image を確定する (記憶で hash を捏造しない)。

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (Single Responsibility)
- 担当: R1 の解決済み候補ごとに、(1) `map-field-impact.py` で target×axis を独立再確認、(2) 対象ファイル現状に対する**最小 Edit 差分** (old_string/new_string もしくは unified diff) を組立、(3) 現状ファイルの `pre_image_sha256` を算出、(4) allowlist target_path を明示、(5) 各候補を `proposals[]` の 1 要素へ格納、(6) container の `proposal_sha256` を全 proposals[] の正規化 digest で算出し、status=`proposed` の sync-proposal.json (コンテナ形) を emit。
- 非担当: 実適用 (R3)、apply-gate 検証 (R3)、独立監査 (C04)。container の approval と各 `proposals[]` の post_image/validator は propose では空 (approval.granted=false・post_image_sha256=null・validator_results=[])。

### 2.2 ドメインルール
- 各 impact は `axis ∈ {name, type, required, enum, semantics}` の 1 軸へ写像し、target_path×axis 単位で `proposals[]` の 1 要素を作る (proposals は minItems 1)。
- `proposed_diff` は当該 axis の before→after を反映する**最小**変更。無関係行を含めない。
- `pre_image_sha256` = 対象ファイル現状内容の sha256 (apply-gate-policy §3 の手順)。ファイル不在時は before=null の新規提案として扱う。
- container の `proposal_sha256` は apply-gate-policy §4 の正規化 (container の issue と全 proposals[] の不変核 target_path/axis/before/after/proposed_diff/pre_image_sha256、target_path 昇順連結) で算出。apply 時の揮発フィールドで値が動かないこと。
- status=proposed では各 `proposals[].post_image_sha256=null`・`proposals[].validator_results=[]`、container の `approval={granted:false, by:null, evidence:null}`。
- allowlist 外や map-field-impact.py で再確認できない target は proposals に含めず、除外理由を提示 (fail-closed・propose も過剰にしない)。

### 2.3 入力契約
| field | type | required | 説明 |
|---|---|---|---|
| resolved-inputs | object | yes | R1 の解決済み候補集合 (issue/mode/影響 impact/allowlist 分類) |
| target files | path | yes | 各候補 `artifact_path` の現状 (Read で before/hash 取得) |
| field-impact-map | path | yes | `$CLAUDE_PLUGIN_ROOT/references/field-impact-map/field-impact-map.json` |
| allowlist policy | path | yes | `references/apply-gate-policy.md` §1/§3/§4 |

### 2.4 出力契約
- schema: `../../schemas/sync-proposal.schema.json` (コンテナ形・additionalProperties:false)。
- container の必須: `issue`/`proposal_sha256`/`status`/`approval`/`proposals`。各 `proposals[]` 要素の必須: `target_path`/`axis`/`before`/`after`/`proposed_diff`/`pre_image_sha256`/`post_image_sha256`/`validator_results`。
- propose 時の固定値: container `status="proposed"`・`approval.granted=false`、各 `proposals[].post_image_sha256=null`・`proposals[].validator_results=[]`。
- 影響あり target×axis は単一でも複数でも常に `proposals[]` (minItems 1) を持つコンテナとして `sync-proposal.json` へ emit する。container 全体を schema 検証する。

## Layer 3: インフラ層 (外部依存)

### 3.1 参照リソース
| id | path | when_to_read |
|---|---|---|
| resolved-inputs | R1 出力 | 候補反復時 |
| target file | 各 `artifact_path` | before/pre-image 取得時 |
| field-impact-map | `$CLAUDE_PLUGIN_ROOT/references/field-impact-map/field-impact-map.json` | target×axis 裏取り時 |
| allowlist policy | `references/apply-gate-policy.md` | allowlist/hash/digest 時 |
| sync-proposal schema | `../../schemas/sync-proposal.schema.json` | emit 検証時 |

### 3.2 外部ツール / API
- `python3 $CLAUDE_PLUGIN_ROOT/scripts/map-field-impact.py --hunks <hunks.json> --map <field-impact-map.json>` — target×axis の独立再確認。
- `shasum -a 256 <file> | cut -d' ' -f1` (fallback `sha256sum`) — pre_image_sha256。
- `python3` — proposal_sha256 正規化 digest・schema 検証・JSON 整形。

## Layer 4: 共通ポリシー層

### 4.1 失敗時挙動
- schema 検証 fail・allowlist 外 target 混入・map-field-impact.py で軸再確認できない場合 → 当該要素を除外し理由提示。全候補が除外なら proposal を空にせず「同期対象なし」を明示 (fail-closed)。
- ゴールシーク最大反復: 3。

### 4.2 観測 / ロギング
- `sync-proposal.json` を emit。除外候補と理由 (対象外パス/軸再確認不可) を併記。

### 4.3 セキュリティ
- 実ファイルを書き換えない (read-only)。secret/PII を差分に含めない。

## Layer 5: エージェント層 (ゴール駆動の実行主体)

### 5.1 担当 agent
- run-rubric-sync 本体 (inline)。監査は C04 へ委ね兼務しない。

### 5.2 ゴール定義
- 目的: 影響ありフィールドを allowlist 対象へ最小 Edit で反映する提案を、pre-image hash と安定 digest 付きで固定し、C04 監査とユーザー承認が判断できる状態を作る。
- 背景: 提案が過剰変更や allowlist 外を含むと C04 が FAIL し、hash/digest が不安定だと監査と適用が突合できない。決定論部分を script に外出しして接地する。
- 達成ゴール: 全 impacted target×axis に対し最小 `proposed_diff`・`pre_image_sha256`・allowlist 内 `target_path`・安定 `proposal_sha256` が揃った status=proposed の sync-proposal.json が schema 検証を通過して emit されている。

### 5.3 完了チェックリスト (ゴール到達の停止条件)
- [ ] 各候補 target×axis を `map-field-impact.py` で独立再確認し、triage の axis と一致している (不一致は除外・理由記録)。
- [ ] 各 proposal 要素の `target_path` が allowlist glob 内である。
- [ ] `proposed_diff` が当該 axis の before→after を反映する最小変更で、無関係行を含まない。
- [ ] `before`/`after` が対象ファイル現状 (Read 済み) と整合し、新規は before=null で表現している。
- [ ] 各 `proposals[].pre_image_sha256` が現状ファイル内容 sha256 と一致 (apply-gate-policy §3 手順)。
- [ ] container の `proposal_sha256` が apply-gate-policy §4 の正規化 (全 proposals[]) で算出され、揮発フィールドに依存しない。
- [ ] container `status="proposed"`・`approval.granted=false`、各 `proposals[].post_image_sha256=null`・`proposals[].validator_results=[]` である。
- [ ] sync-proposal.json (コンテナ全体) が `schemas/sync-proposal.schema.json` を通過する。
- [ ] 実ファイルを一切 Edit していない (read-only)。

### 5.4 実行方式
- 固定手順を持たない (l5-contract v2.0.0)。5.2/5.3 を唯一の指針に、現状評価 → 立案 → 実行 → 検証 → アンカー記録 → 全項目充足まで反復 (6 ステップ・Step 5=Anchor。上限: Layer 4 最大反復)。
- 決定論操作 (map-field-impact.py・hash・digest・schema 検証) は Layer 3 に従い、意味判断 (最小差分の文面) のみ LLM。
- 不足情報は最尤補完し仮定を提示。ユーザーへ追加質問しない。

## Layer 6: オーケストレーション層 (ゴールシーク制御)

### 6.1 上位 skill との接続
- 呼び出し元: run-rubric-sync (R2)。C06 command 経由で C04 監査 → 承認 → R3 apply へ連なる。
- 後続 phase: C04 (rubric-sync-auditor) が sync-proposal を監査 → R3-apply。

### 6.2 ハンドオフ / 並列性
- 直列: sync-proposal.json を C04 監査と R3 apply の入力へ接続。
- goal-seek fork=subagent: 多数 target の差分組立は Task で subagent へ委譲可 (親へは proposal のみ返す)。

## Layer 7: UI / 提示層

### 7.1 ユーザー提示形式
- sync-proposal.json (status=proposed) と、除外候補・理由の要約を Markdown で提示。

### 7.2 言語
- 本文: 日本語 (パラメーター名/JSON キーは英語のまま)。

---

## 出力指示

LLM は R1 の解決済み候補ごとに、対象ファイル現状を Read し、`map-field-impact.py` で target×axis を独立再確認し、当該 axis の before→after を反映する**最小** `proposed_diff` を組み立て、`pre_image_sha256` (apply-gate-policy §3) を算出し、各候補を `post_image_sha256=null`・`validator_results=[]` の `proposals[]` 要素として作る。container は `status="proposed"`・`approval.granted=false` とし、`proposal_sha256` (apply-gate-policy §4・全 proposals[]) を算出する。
allowlist 外・軸再確認不可の候補は proposals に含めず理由を提示する。結果を `schemas/sync-proposal.schema.json` 準拠のコンテナ (proposals[] minItems 1) として `$CLAUDE_PROJECT_DIR/.spec-drift/<issue>/sync-proposal.json` へ emit する。実ファイルは一切 Edit しない。余計な前置き・思考過程出力は禁止。
