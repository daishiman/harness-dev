# rubric.json CHANGELOG

各版の承認と影響の記録の正本は `run-skill-rubric-governance/log/governance-log.jsonl`。この文書は人が読むための要約で、食い違ったときは governance-log と `rubric.json` を正とする。

## 1.6.0 — 2026-10-11（PROP-2026-10-11-HK001-POSTTOOLUSEFAILURE、minor）
- HK-001: hook の event の候補に `PostToolUseFailure` を追加（10値）。harness-creator の hooks.json はこの event を配線済みで、`capability-manifest.schema.json` の kindHook の enum も同じ10値。`test_hook_event_vocabulary_parity.py` が「配線 ⊆ schema」「配線 ⊆ HK-001」「schema = HK-001」を検査する。
- それまで check の文字列だけが本体の作業ツリーで書き換わり、版・L2 の同期・記録が無かった（check-rubric-sync が RUBRIC_DRIFT）。今回その変更を正規の手順に乗せ直した。
- L2 の rubric_version・upstream_version_pin を 1.6.0、rubric_hash を L0 のファイル sha256（22667118…）へ同期（check-rubric-sync は exit 0）。
- 影響: repo 内の hook の event 宣言 28件を旧新の集合で判定し、would_regress 0・would_improve 1（harness-creator の PostToolUseFailure 配線）。猶予0日（superset の緩和）。0 日は `run-skill-rubric-governance/references/version-rules.md` の minor 節の 3 つの条件によるもので、3 つ目の承認者の確認は承認レビューで行う。

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
- 注（2026-10-11 追記）: governance log の記録では、この 0 日の理由は `would_flip` 0（total 1）と、緩和の superset であること。猶予期間を 0 日にできる 3 つの条件（緩和の宣言・`would_flip` 0・承認者による緩和の根拠の確認）は、2026-10-11 に `run-skill-rubric-governance/references/version-rules.md` の minor 節に定めた。この版には遡って当てはめない。

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
