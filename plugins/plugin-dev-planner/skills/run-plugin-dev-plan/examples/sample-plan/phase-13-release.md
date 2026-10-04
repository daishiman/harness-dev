---
id: P13
phase_number: 13
phase_name: release
category: 完了
prev_phase: 12
next_phase: 14
status: 未実施
gate_type: none
entities_covered: []
applicability:
  applicable: true
  reason: ""
---

# P13 — release (完了/PR・リリース)

## 目的
プラグイン開発ドメインへの写像として、UBM 固有の IPC/Cloudflare 等は全 DROP し、PR は本 planner の責務外として soft note に留める (評価ゲート化しない) 一方、`plugin_meta.install` が宣言した Claude/Codex 両 platform への install 検証を build 側の完了条件として確かめる完了フェーズ。

## 背景
PR は本 planner の責務外 (責務は計画の生成のみ)。UBM 固有の IPC/Cloudflare/D1/Workers 等ドメイン外項目は DROP し、PR は soft note に留めてゲート化しない。ただし「作ったが install されない」状態を完了扱いにしないため、Claude/Codex 両 platform への install は `plugin_meta.install` の契約として build 側が満たす。Claude の marketplace autoUpdate は導入済み plugin の版しか上げず新規 plugin を入れないので、実環境への導入は明示の install で行う。

## 前提条件
- P01-P12 が完了している。
- ドメイン外項目 (IPC/Cloudflare/D1/Workers) の DROP 判断が済んでいる。
- PR/配布はユーザー承認後に別途実行する前提を共有している。

## ドメイン知識
- 本フェーズ固有の追加ドメイン知識は無い (plan 全体の用語集=index `## ドメイン知識` で足りる)。境界語彙のみ: soft note = 評価ゲート化しない参考注記 (満たさなくても plan は完了扱い)。

## 成果物
- リリース準備完了の記録 (PR は soft note・評価ゲート化しない)。
- install receipt (`install-local-plugins.py` の stdout JSON。隔離 install と実環境 install の両方)。

## スコープ外
- PR 作成 (ユーザー承認後の別作業・planner の責務外)。
- build 済み実体の修正 (不備は該当 phase へ差し戻し)。

## 完了チェックリスト
- [ ] P01-P12 の完了チェックリストが全て満たされている。
- [ ] リリースに向けた残タスクが soft note として整理されている (PR 自体はゲート化しない)。
- [ ] ドメイン外項目 (IPC/Cloudflare 等) が写像対象外として DROP 記録されている。
- [ ] CHANGELOG を先に書き、`build-plugin-release.py --only notion-task-sync` で版を上げ、`build-plugin-release.py --check` と `build-local-marketplace.py --check` と `sync-plugin-platforms.py --all --check` が drift 0 で通っている (`plugin_meta.install.release` / `registries`)。
- [ ] `claude plugin validate --strict plugins/notion-task-sync` が通っている (hook command の plugin root は `"${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/..."` とクォートする・`plugin_meta.install.strict_validate`)。
- [ ] `install-local-plugins.py --plugin notion-task-sync --claude-config-dir <tmp> --codex-home <tmp>` の receipt が Claude/Codex とも verified=true (`plugin_meta.install.verify.isolated`)。
- [ ] `install-local-plugins.py --plugin notion-task-sync` で手元の Claude Code と Codex へ導入し、receipt が verified=true (`plugin_meta.install.verify.live`)。

## 参照情報
- `references/phase-lifecycle.md` §7 (DROP 読替表)。
- P01-P12 の完了。
- PR は soft note (本 planner の責務外)。
- `references/plugin-creator-contract.md` の install 契約 (Claude/Codex)。
