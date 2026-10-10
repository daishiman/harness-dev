# rubric.json CHANGELOG

各版の承認と影響の記録の正本は `run-skill-rubric-governance/log/governance-log.jsonl`。この文書は人が読むための要約で、食い違ったときは governance-log と `rubric.json` を正とする。

## 1.5.0 — 2026-10-09（PROP-2026-10-09-ELEGANT-PD002、minor）
- PD-002: 禁則の候補に、行全体が一致する `## 守ること` を追加。冒頭30行に収める要件と、本文の単語「守ること」だけでは合格させない条件は維持。
- BD-001・PD-002 の check と rationale の説明を訂正（1.4.0 の記録にあった「BD-001 ⊂ PD-002」と厳格一致の説明は誤りだった）。
- L2（`assign-skill-design-evaluator/references/rubric.json`）の upstream_version_pin と rubric_hash を同期。
- 影響: 既存の SKILL 127件を新旧の判定で比べ、would_regress 0・would_improve 0。猶予0日（superset の緩和）。
- その後の ELEGANT-2026-10-09-CHECKER-GUARD-REPAIR（P2_content）は checker と guard の修理で、rule の意味は変えていない（semantic_rules_changed: false）ので版は 1.5.0 のまま。

## 1.4.0 — 2026-10-09（PROP-2026-10-09-001、minor。適用 2026-10-08T23:15:32Z）
- BD-001・BD-002・PD-002: 見出しの候補に日本語の正規形（`## 目的と出力契約`・`## つまずきやすい点`）を別名として追加。日本語は行全体の一致だけを認め、英語の判定は変えない。
- L2 の upstream_version_pin を 1.4.0、rubric_hash を再計算値へ同期（check-rubric-sync は exit 0）。
- 影響: diff-rubric-impact の flip_rate 0.0、required_bump minor。sunset_days 0 で即時発効。

## 1.3.0 — 日付の記録なし（2026-07-12 の plugins/ 再編より前）
- KL-001〜005（knowledge-loop）を追加。applies_to_kinds は `*` だが、knowledge/ ディレクトリか frontmatter.knowledge_loop が無いスキルは無条件 PASS。正本仕様は `ref-knowledge-loop/references/`。

## 1.2.0 — 日付の記録なし（2026-07-12 の plugins/ 再編より前）
- kind=skill 以外の6種（agent・hook・command・plugin-composition・prompt・workflow）に最小 rule を追加（AG・HK・CM・PC・PR・WF）。各 rule に applies_to_kinds を付け、`_kind_dispatch_doc` で振り分けを説明。
- BD-004（description と body の整合、LLM judge）を TODO(human) の空欄から実ルールへ正式化。
- 2026-05-24 の PROP-2026-05-24-001 は人向けの文書（本スキルの SKILL.md と rubric-rationale.md）を追従させた doc-sync の patch で、rules は変えていないので版は 1.2.0 のまま。

## 1.1.0 — 2026-05-18
- FM-002: trigger phrase 検査を日本語 (〜とき/〜場合/〜際/〜時) にも対応。
- FM-003: trigger count 計算を日本語句にも拡張。
- FM-005: 動詞冒頭チェックに日本語動詞 (する/行う/実行/生成/採点/評価/構築/参照/読み取り/レビュー/管理) を追加。
- 第14条改正 (description は日本語推奨) との整合。29章 minor (緩和) bump。

## 1.0.0 — 2026-05-17
- 初版。
