---
id: P12
phase_number: 12
phase_name: documentation
category: 文書
prev_phase: 11
next_phase: 13
status: 未実施
gate_type: none
entities_covered: []
applicability:
  applicable: true
  reason: ""
---

# P12 — documentation (文書化)

## 目的
P11のL3 evidenceを根拠に、後段buildが作成するREADME/setupの文書契約を確定する。directory/routingに加え、artifact templateの選択/更新、system-spec-harnessを使う仕様・architecture作成、system task planを使うタスク実行準備を説明必須にする。

## 背景
purpose を満たす実装であっても、導入・運用手順が文書化されていなければ管理ハーネスとして機能しない。特に gh CLI 認証前提・plugin-root 共有 script の存在・zero-dependency HTML の開き方は、利用者が最初に迷う箇所であり優先的に文書化する。

## 前提条件
- P11 の evidence が確定している。
- README-portability lint (`$CLAUDE_PLUGIN_ROOT` 空展開封鎖など) の観点を参照できる。
- setup 手順に必要な前提 (gh CLI インストール・認証) が constraints から確認できる。

## ドメイン知識
- portability 記述: 具体値を焼かず `{{PROJECT_ROOT}}` / `$CLAUDE_PLUGIN_ROOT` / self-relative で表現する不変ルールを文書側にも適用する (README-portability lint の対象)。
- 優先文書化対象: gh CLI認証・plugin-root共有script (C11/C12/C13/C16/C24)・zero-dependency HTML・system-spec/system-plan導線 (system-planはexternal system-dev-planner引用)。

## 成果物
- README/setupに必ず含める章・例・検証方法のdocumentation contract。

## スコープ外
- evidence の再収集 (P11 で確定済み)。
- リリース判断・タグ付け (P13)。
- 実装内容の変更 (文書は実装を後追いで記述するのみ)。

## 完了チェックリスト
- [ ] README/setup契約にgh CLI前提条件が含まれる。
- [ ] 6正規root tree、自動routing preview、低信頼時だけの確認、200件境界migration例が含まれる。
- [ ] plugin-root 共有 script (C11/C12/C13/C16/C24) の役割が利用者向けに説明されている。
- [ ] zero-dependency HTML 可視化の開き方が説明されている。
- [ ] 5 kind template、architecture subtype、API contract、readiness不足の直し方が説明されている。
- [ ] 仕様/architectureは`dev-graph spec`からsystem-spec-harnessを利用し、system task specsは`dev-graph plan` (external plugin system-dev-plannerのrun-system-dev-planをSkill呼出しで引用) で生成してからIssue/実装へ進む導線が説明されている。
- [ ] symlink導入手順、caller repo root解決優先順位と`$CLAUDE_PROJECT_DIR`一致、`.dev-graph/config.json`、repository_id再導出、repoごとに異なるdocs/state root、broken content link/containment診断、host launcherのbroken harness-link preflightが説明されている。
- [ ] README-portability lint がハードコード絶対パスを検出しない。

### 受入例
- 満たす例: README に「`gh auth login` が未実行の場合、`dev-graph init` の初期化レポートに認証案内が表示される」という具体手順が記載されている。
- 満たす例: setup 手順に「生成された静的 HTML はブラウザで直接開くだけで SVG 可視化が表示され、追加インストール不要」という記述がある。
- 満たさない例: README にリポジトリ固有の絶対パス (例: `/Users/xxx/repo/plugins/dev-graph/...`) がハードコードされている → README-portability lint が検出し FAIL。

### 事前解決済み判断
- portability 記述は `{{PROJECT_ROOT}}` / `$CLAUDE_PLUGIN_ROOT` / self-relative のいずれかで表現し、具体パスを焼かない不変ルールを文書側にも適用する。
- 優先文書化対象 (gh CLI 認証前提・共有 script の役割・HTML の開き方) は本フェーズで固定し、後から追加観点を発明しない。

## 参照情報
- P11 evidence。
- `templates/README.md` / `templates/system-plan-contract.json` / `plugins/system-spec-harness/README.md`。
- README-portability lint。
- 後続 P13 (release)。
