# spec-drift-guardian

spec-drift-guardian は、**検知済みの spec-drift issue** に対して「どの rubric/schema/template が影響を受けるか」を判定 (triage) し、影響ありと判定された箇所を**独立監査と明示承認を経てから**同期反映する local-first harness です。

検知そのもの (fetch / diff / issue 起票) は既存 workflow と `ref-yaml-spec-fetcher` の責務で、本 plugin では再実装しません。本 plugin が担うのは **完全 diff 再構成 → 4 軸+semantics triage → 独立 verdict → propose → 独立 audit → 明示承認 → allowlist 限定 apply → post-image 検証 → close ゲート**です。

## 前提

Git repository の root、Python 3.10 以上 (stdlib のみ)、Claude Code。issue metadata の取得に認証済み `gh` を使います。diff 復元はローカル git のみで行い、ネットワークへ出ません。

## 使い方

```bash
# 1. issue の影響を triage する (完全 diff を commit pair から復元して判定)
/spec-drift-triage --issue 17

# 2. 影響ありと判定された rubric/schema/template を同期する
/rubric-sync --issue 17 --mode propose   # read-only。最小 Edit 差分と pre-image hash を提案
/rubric-sync --issue 17 --mode apply     # 監査 PASS + 明示承認が揃った場合のみ適用
```

artifact は `$CLAUDE_PROJECT_DIR/.spec-drift/<issue>/` 配下に出ます (`triage-report.json` / `triage-verdict.json` / `sync-proposal.json` / `sync-audit-verdict.json`)。この dir は transient で、追跡しません。

## 設計の要点

- **完全性を証明できない入力は判定しない (fail-closed)**: `spec-diff-history.md` の 80 行 preview は**イベント日時の索引**にのみ使い、実 diff は必ず commit pair から復元したものを使います。truncated preview / digest 不一致 / commit 欠落は triage せず理由付きで停止します。
- **単一 digest 契約**: 1 つの triage-report は 1 commit pair 分の完全 diff だけを扱います。複数 commit pair に跨る入力は集約せず fail-closed するので、issue を commit pair 単位へ分けて triage します。
- **proposer ≠ approver**: triage の再導出は `spec-impact-verifier` (C03)、sync 差分の監査は `rubric-sync-auditor` (C04) が**独立 context**で行い、対象 artifact を書き換えません (Goodhart 防止)。
- **apply-gate は機械検証する**: apply 直前に G1-G5 (監査 PASS / 明示承認 / allowlist 内 / pre-image hash 一致 / C03 agree + diff_sha256 束縛) を `check-triage-complete.py --mode pre-apply` で判定し、exit 0 を得てから Edit します。1 つでも欠ければ**変更 0 件**で停止します (部分適用禁止)。
- **guardian 自身が drift 源にならない**: diff→フィールドの写像規則は `references/field-impact-map/` の data から読み、code に hardcode しません。書き込み先は `plugins/harness-creator/**` の rubric/templates/schema に限定します (allowlist 外は提案にも含めません)。
- **決定論と意味判断の分離**: aggregate / parse / map / gate は python3 stdlib script が担い、LLM は triage と audit の意味判断のみを担います。

## 構成

| component | 実体 | 役割 |
|---|---|---|
| skills | `run-spec-drift-triage` (C01) / `run-rubric-sync` (C02) | triage と同期。各 7 層 prompt (R1-R3) を正本に持つ |
| agents | `spec-impact-verifier` (C03) / `rubric-sync-auditor` (C04) | 独立 context での再導出・監査 |
| commands | `/spec-drift-triage` / `/rubric-sync` | 起動口 |
| hooks | `guard-spec-drift-close` (C07) | verdict なし close を fail-closed で阻止 |
| scripts | `aggregate-issue-diffs` (C11) / `parse-spec-diff` (C08) / `map-field-impact` (C09) / `check-triage-complete` (C10) | 決定論段 |
| references | `field-impact-map` / `apply-gate-policy` | 写像規則と apply-gate の逐語正本 |

受入基準の実測値と既知の制約は `EVALS.json` を参照してください。

## フィードバック

本 plugin への改善要望は `/run-skill-feedback spec-drift-guardian` で投入できます (SSOT: harness-creator/skills/run-skill-feedback、symlink 配備)。
