# shared_state (Phase1 anchor / run-20260625T055146)

対象: notion-gmail-send plugin。Notion 2DB→Gmail一斉個別送信。承認plan+人間承認ゲート+冪等ログの三本柱。pytest baseline=97 passed。
焦点(前回deferred smell): ①doctor/preflight の他plugin作法統一 ②大量送信canary ③README素人向け補強。**未対応かは各自fresh readで検証**(前回報告に虚偽前科)。
主要file: README.md / lib/{setup_doctor,preflight,send_campaign系}.py / skills/run-notion-gmail-dry-run/scripts/build_plan.py / skills/run-notion-gmail-send/scripts/send_campaign.py / 各SKILL.md。
注意: 本pluginレビューはハーネス出力破損が既知。判定はpytest/hashlib/SubAgent最終messageに還元。
