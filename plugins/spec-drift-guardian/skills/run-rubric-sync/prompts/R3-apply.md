# Prompt: R3-apply

> このファイルは 7 層プロンプトの Markdown 表現。`run-prompt-creator-7layer` の
> seven-layer-markdown-template.md を提示形式の補助とする。Layer 番号と依存方向 (L1 ← L7) は不変。
> L5 サブ構造は seven-layer-format.md「Layer 5 契約」(l5-contract v2.0.0) に従属する。

## メタ

| key | value |
|---|---|
| name | apply |
| skill | run-rubric-sync |
| responsibility | R3 (apply mode。G1-G5充足時のみ allowlist 対象へ Edit 適用 + post hash/validator 記録) |
| layers_covered | [L1, L2, L3, L4, L5, L6, L7] |
| output_schema | ../../schemas/sync-proposal.schema.json (status=applied_verified) |
| reproducible | true (同 proposal・同承認・同ファイル → 同 post_image_sha256/validator_results。1 条件でも欠けば変更 0 件で決定論的に停止) |

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール
- **apply-gate 条件 (G1-G5) を全充足したときだけ Edit する**: 監査 PASS ∧ 明示承認 ∧ allowlist 内 ∧ pre-image hash 一致 ∧ C03 同意 (対象 diff 束縛つき) (SSOT=`references/apply-gate-policy.md` §2)。
- 1 条件でも欠けたら**変更 0 件で fail-closed** し、理由を提示 (status は proposed のまま)。
- Edit 対象は sync-proposal の allowlist `target_path` **のみ**。他パスを触らない。
- **commit / PR / issue close は行わない** (close ゲートは C10/C07 の責務)。

### 1.2 倫理ガード
- proposer≠approver: 承認 (approval) と監査 (C04) を自作せず、ユーザー承認と C04 verdict を消費する。
- pre-image drift 時は上書きせず再 propose を促す (他者の後続変更を破壊しない)。

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (Single Responsibility)
- 担当: (1) apply-gate 条件 (G1-G5) の検証、(2) 全充足時に `proposals[]` の各 allowlist target へ最小 Edit を適用、(3) 適用後に各要素の `post_image_sha256` 算出、(4) validator 実行と各要素の `validator_results` 記録、(5) container の status を `applied_verified` へ更新して sync-proposal.json を再 emit。
- 非担当: 提案の組立 (R2)、独立監査 (C04)、独立再導出 (C03)、issue close (C10/C07)。

### 2.2 ドメインルール
- **G1 監査 PASS**: C04 `sync-audit-verdict.json` の `verdict=="PASS"` かつ `proposal_sha256==sync-proposal.proposal_sha256` (container の digest)。
- **G2 明示承認**: container の `approval.granted==true` かつ `by`/`evidence` 非 null。未承認なら AskUserQuestion で取得し、拒否/未回答なら適用しない。
- **G3 allowlist 内**: 全 `proposals[].target_path` が apply-gate-policy §1 の glob に決定論照合で一致。
- **G4 pre-image 一致**: 各 proposal の適用直前に実ファイル sha256 を再計算し `proposals[].pre_image_sha256` と一致 (提案後 drift を検出)。`pre_image_sha256=null` は新規作成提案であり、対象ファイルが**不在であること**が一致条件 (実在したら停止)。
- **G1-G5 は目視でなく機械検証する (必須・Edit の前)**: `python3 $CLAUDE_PLUGIN_ROOT/scripts/check-triage-complete.py --mode pre-apply --issue <N> --sync-proposal <p.json> --sync-audit-verdict <a.json> --triage-report <r.json> --triage-verdict <v.json> --target-root .` を実行し **exit 0 を得てから** Edit する。exit 1 は理由付き `reasons[]` を返すので変更 0 件のまま停止する (引数不足は exit 2)。同 script が G5 (C03 `agree==true` かつ `diff_sha256` が triage-report と一致) も機械検証するため、目視確認で代替しない。close ゲート (`--mode close`) は適用後の post-image しか見ないため pre-image drift をここで止めないと検出機会が失われる。
- **G5 独立 verifier の同意 (対象束縛つき)**: C03 `triage-verdict.json` の `agree==true` **かつ** `diff_sha256` が C01 `triage-report.diff_sha256` と一致 (agree は特定 diff への同意なので、C01 再実行後に C03 未再実行の旧 verdict を流用させない)。
- **部分適用禁止**: `proposals[]` のうち 1 つでも G1-G5 を満たさなければ、その issue の apply を実行せず全体停止。
- 適用は各 `proposals[].proposed_diff` を忠実に反映する最小 Edit。差分外の変更を加えない。
- 適用後: 各 `proposals[].post_image_sha256` 非 null、各 `proposals[].validator_results` 1 件以上 (全 passed=true でなければ applied_verified にしない)、container status=`applied_verified`。`proposal_sha256` は不変 (apply-gate-policy §4)。

### 2.3 入力契約
| field | type | required | 説明 |
|---|---|---|---|
| sync-proposal | path | yes | R2 の `sync-proposal.json` (status=proposed) |
| sync-audit-verdict | path | yes | C04 `sync-audit-verdict.json` (verdict=PASS/proposal_sha256 一致) |
| triage-verdict | path | yes | C03 `triage-verdict.json` (agree 確認) |
| approval | object | yes | ユーザー明示承認 (granted/by/evidence) |
| allowlist policy | path | yes | `references/apply-gate-policy.md` §1-§5 |

### 2.4 出力契約
- schema: `../../schemas/sync-proposal.schema.json` (コンテナ形)。status=`applied_verified` では全 `proposals[].post_image_sha256` 非 null、全 `proposals[].validator_results` 1 件以上かつ全 passed。
- fail-closed 時: sync-proposal は status=proposed のまま更新せず、fail 理由 (未承認/監査不一致/hash drift/対象外パス) を提示。
- `sync-proposal.json` を同パスへ再 emit (applied_verified) または proposed のまま据え置き。

## Layer 3: インフラ層 (外部依存)

### 3.1 参照リソース
| id | path | when_to_read |
|---|---|---|
| sync-proposal | `$CLAUDE_PROJECT_DIR/.spec-drift/<issue>/sync-proposal.json` | gate 検証/更新時 |
| sync-audit-verdict | `$CLAUDE_PROJECT_DIR/.spec-drift/<issue>/sync-audit-verdict.json` | G1 検証時 |
| triage-verdict | `$CLAUDE_PROJECT_DIR/.spec-drift/<issue>/triage-verdict.json` | agree 確認時 |
| allowlist policy | `references/apply-gate-policy.md` | G1-G5/hash/validator 時 |
| target files | 各 `target_path` | Edit/post-image/validator 時 |

### 3.2 外部ツール / API
- `shasum -a 256 <file> | cut -d' ' -f1` (fallback `sha256sum`) — G4 pre-image 再計算・post_image_sha256。
- `Edit` — allowlist target への proposed_diff 適用 (G1-G5充足後のみ)。
- validator: `python3 -c 'import json; json.load(...)'` + kind 別検証 (apply-gate-policy §5)。
- `AskUserQuestion` — 未承認時の明示承認取得。
- `python3` — schema 検証・sync-proposal.json 再 emit。

## Layer 4: 共通ポリシー層

### 4.1 失敗時挙動
- G1-G5 のいずれか fail → **変更 0 件**で停止、status=proposed 据え置き、fail 理由提示 (apply-gate-policy §6 マトリクス準拠)。
- validator に passed=false → 適用を revert 候補として提示し applied_verified にしない (post-image 検証未達)。
- ゴールシーク最大反復: 3。hash drift 時は R2 再 propose へ差し戻す。

### 4.2 観測 / ロギング
- 適用時: sync-proposal.json を applied_verified で再 emit (post hash + validator)。fail 時: 理由のみ提示し artifact は proposed のまま。

### 4.3 セキュリティ
- allowlist 外を Edit しない。secret/PII を差分・validator 出力に含めない。commit/push しない。

## Layer 5: エージェント層 (ゴール駆動の実行主体)

### 5.1 担当 agent
- run-rubric-sync 本体 (inline)。承認取得は AskUserQuestion、監査/再導出は C04/C03 の artifact を消費 (兼務しない)。

### 5.2 ゴール定義
- 目的: 監査と明示承認を満たした提案だけを allowlist 対象へ限定適用し、実反映を post-image hash と validator で検証済み状態に固定する。
- 背景: proposal-only で close 可能になる穴を塞ぐには実適用と検証の固定が要る。一方で無条件適用は誤反映・破壊のリスクなので、G1-G5と部分適用禁止で fail-closed を担保する。
- 達成ゴール: apply-gate G1-G5を全充足した case で allowlist 対象だけが Edit 適用され、`post_image_sha256` と全 passed の `validator_results` が記録され、status=applied_verified で sync-proposal.json が再 emit されている。未充足 case は変更 0 件で停止している。

### 5.3 完了チェックリスト (ゴール到達の停止条件)
- [ ] G1: C04 `verdict=="PASS"` かつ `proposal_sha256` が sync-proposal container と一致している。
- [ ] G2: container の `approval.granted==true` で `by`/`evidence` が非 null である (未承認なら適用せず停止)。
- [ ] G3: 全 `proposals[].target_path` が allowlist glob に一致している。
- [ ] G4: 各 proposal の適用直前の実ファイル sha256 が `proposals[].pre_image_sha256` と一致している。
- [ ] G5: C03 `triage-verdict.agree==true` かつ `diff_sha256` が triage-report と一致している。
- [ ] `check-triage-complete.py --mode pre-apply` が exit 0 を返してから、各 `proposals[]` の allowlist target へ `proposed_diff` を最小 Edit 適用している (部分適用していない)。
- [ ] 適用後の各 `proposals[].post_image_sha256` を算出し非 null で記録している。
- [ ] 各 `proposals[].validator_results` を 1 件以上記録し、全 `passed==true` である (でなければ applied_verified にしない)。
- [ ] container status=`applied_verified` で sync-proposal.json を再 emit し schema 検証を通過している。
- [ ] 未充足 case は変更 0 件・status=proposed 据え置きで、fail 理由を提示している (commit/PR/close していない)。

### 5.4 実行方式
- 固定手順を持たない (l5-contract v2.0.0)。5.2/5.3 を唯一の指針に、現状評価 → 立案 → 実行 → 検証 → アンカー記録 → 全項目充足まで反復 (6 ステップ・Step 5=Anchor。上限: Layer 4 最大反復)。
- 決定論操作 (hash 再計算・allowlist 照合・validator・schema 検証) は Layer 3 に従い、意味判断 (承認証跡の妥当性など) のみ LLM。
- 承認が無いときのみ AskUserQuestion で取得する。それ以外の不足はユーザーに問わず fail-closed。

## Layer 6: オーケストレーション層 (ゴールシーク制御)

### 6.1 上位 skill との接続
- 呼び出し元: run-rubric-sync (R3)。上位は C06 command (C01/C03 一致 → R2 propose → C04 audit → 承認 → R3 apply → C10 検証)。
- 後続 phase: C10 (check-triage-complete.py) が applied_verified を close ゲートで消費、C07 hook が close を制御。

### 6.2 ハンドオフ / 並列性
- 直列: applied_verified な sync-proposal.json を C10/C07 の入力へ接続。
- goal-seek fork=subagent: 検証 (post hash/validator) は Task で subagent へ委譲可 (親へは検証結果のみ返す)。

## Layer 7: UI / 提示層

### 7.1 ユーザー提示形式
- 適用時: 適用 target・post hash・validator 結果の要約。fail 時: どの条件で止まったか (apply-gate-policy §6 のどの行か) を明示。

### 7.2 言語
- 本文: 日本語 (パラメーター名/JSON キーは英語のまま)。

---

## 出力指示

LLM は sync-proposal.json (コンテナ形)・C04 sync-audit-verdict.json・C03 triage-verdict.json と承認情報を読み、apply-gate G1-G5 (G1 監査 PASS / G2 明示承認 / G3 allowlist 内 / G4 pre-image hash 一致 / G5 C03 agree + diff_sha256 束縛) を全 `proposals[]` について検証する (判定は `check-triage-complete.py --mode pre-apply` の exit 0)。
**全充足のときだけ** 各 `proposals[]` の allowlist target へ `proposed_diff` を最小 Edit 適用し、各要素の `post_image_sha256` を算出し validator を実行して `validator_results` を記録し、container status=`applied_verified` で sync-proposal.json を再 emit する。
1 条件でも欠けたら**変更 0 件**で停止し、status=proposed 据え置きのまま fail 理由 (apply-gate-policy §6 のどの行か) を提示する。commit/PR/issue close は行わない。余計な前置き・思考過程出力は禁止。
