# 34. plugin 移行ガバナンスロードマップ

最終更新: 2026-10-10（現状とゲートの充足状況を 2026-07-12 の物理移行後の実物に更新）

> **現状（2026-10-10 時点）**: 物理移行は実施済みである。2026-07-12 のコミット `4cd8faf8`（件名「skills/ 単一構成から plugins/ マルチプラグイン構成へ全面再編」、4224 ファイル）で、今の `plugins/<plugin>/`（正本）と `installers/` の構成になり、19 plugin が一度に入った。旧 `creator-kit/` から移したかどうかは git では確かめられない（`git log --all -- creator-kit` は 0 件で、親 `4f566b46` にも `creator-kit/` は無い）。`.claude/{skills,agents,commands}` の大部分は `scripts/build-claude-symlinks.py` が作る plugins への symlink だが（例: `.claude/skills/run-build-skill` → `../../plugins/harness-creator/skills/run-build-skill`）、aidd-agent-kit 由来の通常エントリ（skills 21・agents 1・commands 4、`.claude/aidd-agent-kit.manifest` が管理）は git が通常のファイルとして追跡している。`.claude-plugin/marketplace.json` と `plugins/harness-creator/hooks/hooks.json` も実在する。この移行は下記のゲートがすべてそろう前に行われ、ゲート通過の判定記録は残っていない。そのため以下のゲートとチェックリストは、移行の可否ではなく「移行後に満たすべき条件」の追跡表として読む。[x] は実物と CI 配線で確かめたもの、[ ] は未達または証跡が未記録のものを表す。

## 目的

本章は、3アナリスト（論理構造9 / メタ発想9 / システム戦略12 = 30 paradigm）の収束的証拠に基づき、plugin 移行を「Phase 0-4 のゲート付きロードマップ」として明文化する。**ユーザー意向（plugin 化進行）と3アナリスト推奨（Phase 0 即時改善優先）を両立させるための設計書章**。

## 正本の分担

| 領域 | 正本 | 本章で扱うこと |
|---|---|---|
| plugin アーキテクチャ比較 | `23-meta-skill-architecture.md` 案D/案D' | 案D' 移行の前提条件と Phase 0-4 接続 |
| plugin 命名規約 | `06-classification-and-naming.md` 第17条 | 命名ゲート (Phase 0 完了後適用) |
| plugin 境界 governance | `33-change-governance.md` MECE 表 | 境界違反の分類と強制ルール |
| classify_change | `scripts/guard-change-category.py` | 実装済み・CI 配線済み（`.github/workflows/governance-check.yml` が `--base origin/main` で実行）。本章は plugin 境界の運用証跡だけを扱う |
| eval-log plugin 対応 | `27-rubric-governance-runbook.md` §3.1 | eval-log パスの plugin 拡張（PKG gate 用 `eval-log/<plugin>/pkg-<id>/` も §3.1 に準拠） |
| plugin package harness | `36-plugin-package-harness-contract.md` | plugin install だけで Skill / Agent / Hook / script / settings を使える同梱契約（PKG-001〜017 の正本） |

**正本分担の追記（2026-05-20）**: Plugin Package Harness Contract（PKG-001〜017、`references/package-contract.json` schema、Install UX Contract）の正本は **36章**。本章は Phase 0/1/2 ゲートで参照するのみで、ID 改廃・schema 変更は 36章 + 27章 rubric governance の承認を要する（27章 §4 参照）。

---

## 公式制約 5 点照合表

plugin 移行前に確認が必要な公式制約を明示する。全て PASS でなければ Phase 2 以降に進んではならない。

| # | 制約 | 内容 | 現状 | Phase 0 での対応 |
|---|---|---|---|---|
| a | Skill スコープ制限 | plugin スコープ宣言外の Skill・ファイルへのアクセス禁止 | 未確認 | 全 SKILL.md 外部参照棚卸し |
| b | permissions 宣言 | plugin 内 permissions は plugin スコープ内でのみ宣言可能 | 設計中 | plugin 境界設計後に反映 |
| c | CI 強制 | `classify_change` は実装済み・CI 配線済み。`lint-external-refs.py` の CI 検査は harness-creator の skills だけで、全 plugin の境界棚卸しとその CI gate は未完 | **暫定FAIL** | `lint-external-refs.py` による棚卸し + CI強制 |
| d | marketplace 非可逆 | marketplace 公開は実質不可逆。配布計画なし時点での公開禁止 | 未公開 | 現フェーズでは公開しない方針で OK |
| e | plugin 外参照禁止 | plugin 内 Skill が plugin 外の scripts/adapters/.claude/config/ を参照することを禁ずる | **一部棚卸し**（harness-creator のみ） | 外部参照棚卸し完了が Phase 0 の必要条件 |

**制約 c・e は未解決のまま、物理移行は 2026-07-12 に実施済み（冒頭の現状を参照）**。残る作業は移行の可否判断ではなく、c・e の解消である。c は「分類器未実装」ではなく「plugin境界の証跡とCI強制が未完」という意味で暫定FAILとする。

---

## Phase 0-4 ロードマップ

### Phase 0 (即時: classify_change 実装 + 外部参照棚卸し)

**Phase 0 完了を Phase 2 以降の移行開始の最低条件とする。**

| タスク | 担当 | 完了条件 | 対応 constraint | TODO(human) 解除トリガー |
|---|---|---|---|---|
| `classify_change` CI強制確認 | TODO(human) | `guard-change-category.py` が P0/P1/P2/P3 を分類し、plugin境界変更を保守的に P0 としてCIで止められる | 制約 c | Phase 1 設計完了 + P1 変更の手動分類実績 3 件以上 + solo_operator レビュー承認 |
| OB-09 `target_path` 配列化 | TODO(human) | `target_path` が配列型を受け付けるようになる | changelog 整合性 | N/A（solo_operator 判断で即着手可） |
| OB-10 `migrate dry-run` ログ取得 | TODO(human) | `migrate-from-project.sh --dry-run` のログが取得できる | 移行前後の状態把握 | N/A（migrate スクリプト実装後に着手） |
| 全 SKILL.md 外部参照棚卸し | TODO(human) | 全 SKILL.md の外部参照先が `scripts/lint-external-refs.py` で洗い出されている | 制約 e | N/A（solo_operator 判断で即着手可） |
| メタガバナンス集約レイヤー設計 | TODO(human) | plugin 間の共通基準 (rubric/lint/config) の共有方式が決定している | 制約 b | N/A（solo_operator 判断で即着手可） |

> **注意**: `classify_change` 自体は実装済み。TODO(human) は plugin境界の運用証跡、外部参照棚卸し、CI強制確認に限定する。

### Phase 1 (1-2週: 設計 + 評価)

| タスク | 担当 | 完了条件 |
|---|---|---|
| SKILL.md 外部参照棚卸し完了 | 人間 | 全外部参照が一覧化され、plugin 境界内に収める計画が立っている |
| メタガバナンス集約レイヤー設計完了 | 人間 | 設計書に反映済み |
| plugin 試験移行の対象 Skill 選定 | 人間 | **廃止**: harness-creator 1件に絞る試験移行は行わず、`4cd8faf8` で 19 plugin を一度に移したため、前提が無くなった |
| 公式制約 a/b/d/e の PASS 確認 | 人間 + lint | 照合表の a/b/d/e が全て PASS |

### Phase 2 (1ヶ月: 試験 plugin 移行)

**実行条件: Phase 0 全タスク完了 + Phase 1 完了 + 公式制約 5点が全て PASS**

| タスク | 担当 | 完了条件 |
|---|---|---|
| harness-creator 1件のみ試験 plugin 移行 | 人間 + AI | **読み替え**: 1件の試験移行は行わず、全 plugin を一度に移した（`4cd8faf8`）。以後は `plugins/harness-creator/` を含む全 plugin が正常に動くことを、下の行と Phase 2 ゲートで追う |
| plugin 境界内での動作確認 | 人間 | 外部参照ゼロを確認 |
| eval-log plugin 対応パスへの移行 | 人間 | `eval-log/harness-creator/` にログが記録される |
| 3ヶ月評価開始 | 人間 | 評価基準と観測項目が決定している |

### Phase 3 (条件達成後: marketplace + 手動 merge 運用確立)

**実行条件: Phase 2 の3ヶ月評価で機能/コスト比 >= 1 と判定**

| タスク | 担当 | 完了条件 |
|---|---|---|
| marketplace.json 作成 | 人間 | **作成は達成**: `.claude-plugin/marketplace.json` は 2026-01-15（`677321e5`）から実在し、2026-10-10 時点で 17 plugin を載せる。ローカル用の `marketplaces/local/.claude-plugin/marketplace.json` は 22 plugin を載せる。完了条件の「公開前のレビュー」の記録は無い |
| 手動 merge 運用フロー確立 | 人間 | CONTRIBUTING.md に記載 |
| plugin 間依存 governance 整備 | 人間 + 33章 MECE 表 | P0_breaking 判定が機械強制されている |

### Phase 4 (条件達成後: 全面移行 + plugin 量産開始)

**実行条件: Phase 3 完了 + `classify_change` 実装完了**

| タスク | 担当 | 完了条件 |
|---|---|---|
| 全 Skill の plugin 移行 | 人間 + AI | 全 Skill が plugin 境界内で動作 |
| plugin 量産開始 | 人間 + AI | `run-build-skill` が plugin 対応テンプレートを使用 |
| 旧 `.claude/skills/` アーキテクチャの deprecation | 人間 | CHANGELOG.md に deprecation 記録 |

---

## 3アナリスト収束的証拠サマリ

8 paradigm が独立検出した主要収束点を記録する。詳細は Phase 2 分析を参照。

### 収束1: classify_change stub が真のボトルネック (8 paradigm 独立指摘)

| Paradigm | 検出内容 | severity |
|---|---|---|
| PF-A1 批判 (論理) | governance-policy.json の機械強制宣言と stub の矛盾 | critical C1 |
| PF-A2 演繹 (論理) | P1 確定 plugin 移行が stub で自動 P2 化 → anti_patterns[0] 直接抵触 | critical C1 |
| PF-E02 フィードバックループ (システム) | 正ループ切断、CI 存在するが機能しない | critical C1/C3 |
| PF-E03 TOC (システム) | 唯一の真のボトルネック | critical C2 |
| PF-G01 OODA (システム) | Orient フェーズ stub で遮断 | high C1 |
| PF-G05 R04 (システム) | 現在進行中リスク | critical C1 |

**結論**: Phase 3 最優先は classify_change の実装（ただし TODO(human) として温存）。

### 収束2: 公式制約 (e) plugin 外参照禁止が本リポジトリ最致命 (3名独立)

| Paradigm | 検出内容 |
|---|---|
| PF-A7 ロジックツリー (論理) | rubric 共有 (案B昇格版) が plugin 外参照禁止に抵触 |
| PF-C05 逆転 (メタ, score 92 最高) | permissions plugin スコープ宣言不可 × 独立ガバナンス境界の根本衝突 |
| PF-G04 制約思考 (システム) | 5制約中最致命、scripts/adapters/, .claude/config/ への隠れ依存 |

**結論**: plugin 移行前に全 SKILL.md の外部参照棚卸しが必須。

### 収束3: plugin 化は唯一解ではない (5 paradigm 独立指摘)

| Paradigm | 検出内容 |
|---|---|
| PF-C04 水平思考 (メタ) | Skills + git submodule で 80% 達成可能 |
| PF-C08 5why (メタ) | 根本動機は (1)リスク隔離 (2)再利用 (3)namespace 独立性 — 商用配布ではない |
| PF-F02 ゼロベース (システム) | 配布計画ない時点での移行はコスト過剰 |
| PF-F04 価値工学 (システム) | 機能/コスト比 < 1 |
| PF-F03 リアルオプション (システム) | marketplace 公開は不可逆判断、延期価値高い |

**結論**: Phase 3 以降の移行判定で機能/コスト比を再評価する。

---

## ゲート判定チェックリスト

Phase 移行の前にこのチェックリストを確認する。

### Phase 0 → Phase 1 移行ゲート

- [ ] `classify_change` が実装済みで、plugin境界変更を P0 として分類することを確認（実装と CI 配線は済み。plugin 境界変更を P0 に分類することの確認記録は未作成）
- [ ] OB-09 `target_path` 配列化の要否が判断されている
- [ ] OB-10 dry-run ログが取得できる
- [ ] 全 SKILL.md の外部参照棚卸しが開始されている

### Phase 1 → Phase 2 移行ゲート

- [ ] 全 SKILL.md 外部参照棚卸し完了（一覧化 + plugin 境界計画）
- [ ] 公式制約 a/b/d/e が全て PASS
- [ ] **制約 c (classify_change CI強制) の状態確認**: CI未接続の場合は手動 P0_breaking 運用で補完
- **廃止**: 試験移行対象 Skill を harness-creator 1件に絞る条件（`4cd8faf8` で 19 plugin を一度に移したため、前提が無い）
- [ ] メタガバナンス集約レイヤー設計完了

### Phase 2 → Phase 3 移行ゲート

- [ ] harness-creator の試験 plugin が3ヶ月正常動作
- [ ] 機能/コスト比 >= 1 の評価結果
- [ ] eval-log plugin 対応パス動作確認
- [ ] plugin 境界外参照ゼロ確認

### Phase 3 → Phase 4 移行ゲート

- [x] **classify_change CI強制完了**（Phase 4 はCI強制完了を必須条件とする。達成: `governance-check.yml` が pull_request と push で `guard-change-category.py --base origin/main` を流し、承認か cooldown が足りない変更があれば exit 1 で job を落とす。ブランチ保護の必須チェックになっているかは repo の中からは確かめられない）
- [ ] marketplace.json レビュー完了
- [ ] 手動 merge 運用確立
- [ ] plugin 間依存 governance 機械強制

---

## plugin 物理レイアウトと symlink 戦略（2026-05-18 確定）

### 最終形ディレクトリ構造

```
<repo root>/                        # marketplace リポジトリ
├── .claude-plugin/
│   └── marketplace.json            # marketplace 宣言（plugins 配列）
├── plugins/                        # ★ 正本（source of truth）
│   ├── harness-creator/              # 2026-07-12（4cd8faf8）からこの構成
│   │   ├── .claude-plugin/
│   │   │   └── plugin.json         # name, version, description 等（hooks は持たない）
│   │   ├── agents/                 # subagent
│   │   ├── skills/                 # SKILL.md 群
│   │   ├── commands/               # slash command
│   │   ├── hooks/                  # hooks.json = plugin の hook 配布の正本
│   │   ├── scripts/                # plugin 内 script（plugin 外参照禁止）
│   │   └── references/             # plugin 内 ref-* 関連
│   ├── presentation-builder/       # 将来追加 plugin
│   └── code-review/                # 将来追加 plugin
├── .claude/                        # ★ 派生（symlink）と project 所有の設定
│   ├── agents/                     # → plugins/*/agents/ への symlink 群（aidd-agent-kit 由来の通常ファイル 1 を含む）
│   ├── skills/                     # → plugins/*/skills/ への symlink 群（同 通常ディレクトリ 21 を含む）
│   ├── commands/                   # → plugins/*/commands/ への symlink 群（同 通常ファイル 4 を含む）
│   ├── settings.json               # project 所有の hooks・permissions。plugin の hook は入らない
│   ├── logs/                       # session log（35章、.gitignore 対象）
│   └── changelog/                  # governance changelog（git 追跡）
├── scripts/                        # marketplace 全体の共通 script
└── doc/                            # 設計書
```

### 正本と派生の原則

| 区分 | 場所 | 性質 |
|---|---|---|
| **正本** | `plugins/<name>/` | 全変更はここに対して行う。git で履歴管理 |
| **派生（symlink）** | `.claude/agents/`, `.claude/skills/`, `.claude/commands/` | `plugins/*/` 配下を参照する symlink（git では skills 94・agents 63・commands 24） |
| **plugin の外の通常エントリ** | 同上の一部 | aidd-agent-kit 由来（skills 21・agents 1・commands 4）。`.claude/aidd-agent-kit.manifest` が管理し、symlink ではない |
| **project 所有の設定** | `.claude/settings.json` | project の hooks・permissions と `enabledPlugins`。`build-claude-settings.py` は plugin の permissions だけを合わせる（下記） |
| **ローカル蓄積** | `.claude/logs/*.jsonl` | session log 実体。git 追跡外（35章） |

**不変条件**:
- `.claude/agents/` 等の symlink 先は **常に `plugins/<name>/` 配下**でなければならない
- `.claude/settings.json` の `_build_claude_settings`（build CLI の管理台帳）を手編集しない。台帳に載っていない値は project 所有として保存される（[34a](./34a-settings-merge-spec.md) INV-1）
- 逆向き（`.claude/` 正本 / `plugins/` symlink）は禁止：公式 `/plugin install` 配布時に symlink 先が壊れる

### symlink 構築フロー

```
[plugins/<name>/agents/foo.md]
         │
         ▼ scripts/build-claude-symlinks.py（実装済・規約正本 / CI --check で fail-closed 強制）
         │
[.claude/agents/foo.md] = symlink → ../../plugins/<name>/agents/foo.md
```

- スクリプト名: `build-claude-symlinks.py`（28章動詞 `build` 準拠）
- 冪等性: 既存 symlink は再構築、broken symlink は除去、手書きファイルは保護
- name collision: 同名 file を複数 plugin が持つ場合は **失敗終了**（06章第17条 namespace 衝突禁止）

### settings.json マージ仕様（hook 二重発動の予防）

管理メタデータの構文と不変条件の正本は [34a-settings-merge-spec.md](./34a-settings-merge-spec.md)。本節は 2026-10-10 時点の配線と、`scripts/build-claude-settings.py` が実際にすることだけを書く。

#### hook と設定の置き場所

| 置き場所 | 役割 |
|---|---|
| `plugins/<name>/hooks/hooks.json`（13 plugin が持つ） | plugin の hook 配布の正本。Claude Code / Codex の plugin loader が plugin root から1回だけ読む |
| `plugins/<name>/.claude-plugin/plugin.json` | `hooks` フィールドは持たない（22 件すべて。`git grep '"hooks"'` は 0 件） |
| `plugins/<name>/settings/permissions.json`（任意） | plugin 由来の permissions。2026-10-10 時点で持つ plugin は無い |
| `.claude/settings.json` | project 所有の hooks・permissions と `enabledPlugins`。plugin の hook は入れない |

#### `build-claude-settings.py` が実際にすること

- 28章動詞 `build` 準拠。test は `tests/test_build_claude_settings.py`、CI は `make native-surfaces-check`（`sync-native-surfaces.py --check` 経由）で `--check`。
- plugin の hook は読んで正規化し検証するだけで、`.claude/settings.json` へは投影しない（script L396-398・L764-768。`test_inv4_plugin_hooks_are_not_project_managed` が `managed_hooks == []` を固定）。前に投影した hook は台帳 `_build_claude_settings.managed_hooks` で見分けて取り除き、台帳に無い project の hook は残す。
- plugin の permissions（deny / ask）だけを `permissions` に合わせ、`_build_claude_settings.managed_permissions` に記録する。
- 管理情報は top-level の `_build_claude_settings` にだけ置く。`hooks` の下に `_generated_section_start` などの番兵キーは置かない（34a §6）。
- 2026-10-10 の `--check --json` は exit 0 で、`settings.hooks=[]`・`settings.permissions=[]`。

> 34a は 2026-10-10 に、上の実装に合わせて全体を書き直した。hook を settings へ投影しないこと、当初の投影案と、それをやめた理由は 34a §1 にある。§13 の hook の Capability 化は未実装の案である。

#### 二重発動の罠の予防ルール

1. plugin 配下 hook を `.claude/settings.json` に**手書きしない**（plugin loader の配布と二重発動する）
2. `_build_claude_settings` は build CLI の台帳なので手編集しない（34a §6）
3. 既存の `.claude/settings.creator-kit-hooks.json.example` は `plugins/harness-creator/hooks/` に移植（Phase 0 完了後の Phase 1 で実施。現在は `.claude/` 直下を維持）
4. 35章の `.claude/settings.meta-harness-hooks.json.example` も同様に対応 plugin の `hooks/` へ移植（Phase 0 完了後の Phase 1 で実施。現在は `.claude/` 直下を維持）

### Phase 0 ゲート（実物理移行の前提、再掲）

実物理移行（`plugins/<plugin>/` 構成への P0_breaking 変更）の前提として定めたゲート。移行は 2026-07-12 の `4cd8faf8` で行われ、以下は 2026-10-10 時点の充足状況:

- [x] `classify_change()` 実装完了（`scripts/guard-change-category.py`、`governance-check.yml` で CI 実行）
- [ ] 全 SKILL.md の外部参照棚卸し完了（`lint-external-refs.py` の CI 検査は harness-creator の skills のみ）
- [x] `build-claude-symlinks.py` 実装と test（実装済: `scripts/build-claude-symlinks.py` + `tests/test_build_claude_symlinks.py`、CI は `make native-surfaces-check` 経由で `--check`）
- [x] `build-claude-settings.py` 実装と test（`scripts/build-claude-settings.py` + `tests/test_build_claude_settings.py`。実装は plugin の hook を settings へ投影しない形で、当初の「plugin.json の hooks から生成区間を作る」案ではない。上の § settings.json マージ仕様）
- [ ] migrate スクリプトの `--dry-run` ログ取得（`installers/harness-creator-kit/migrate-log/` は `.gitkeep` のみ）
- [x] **36章 PKG-001〜009 lint 実装**（package completeness check の P0 セット、Python stdlib 限定。当初予定の `scripts/validate-plugin-package.py` ではなく、PKG-002〜008 は `plugins/harness-creator/skills/assign-plugin-package-evaluator/scripts/validate-plugin-package.py`、PKG-009 は `plugins/harness-creator/skills/run-plugin-package-check/scripts/lint-pkg-009.py`、PKG-001 は下記ラッパーに置いた。repo 全体は `scripts/validate-plugin-packages.py` を `harness-creator-kit-ci.yml` が実行）
- [ ] **`references/package-contract.json` の schema 整備と validator script の所在明示**（schema 正本: 36章。validator として予定した `scripts/validate-package-contract.py` は未実装で、repo に存在しない）
- [ ] **`claude plugin validate --strict` の harness 内ラッパー**（ラッパーは `plugins/harness-creator/skills/run-plugin-package-check/scripts/run-plugin-validate-strict.sh` に実装済み。exit code の CI gate への接続は未。PKG-001 と同期）

### Phase 1 ゲート（PKG smoke 自動化、新設）

Phase 1 完了の追加条件として、以下を満たすこと:

- [ ] **PKG-010 install smoke の自動化**: local marketplace install smoke が `plugins/harness-creator/skills/run-plugin-package-check/scripts/smoke-plugin-install.sh`（実装済み）等で再現可能になり、entrypoint / hook registration / script existence の3確認を機械実行できる。実行ログは `eval-log/<plugin>/pkg-010/` に保存（27章 §3.1 に準拠。2026-10-10 時点でログは未保存）

### Phase 2 ゲート（出荷前 PKG gate、新設）

Phase 2 完了の追加条件として、以下を満たすこと:

- [ ] **PKG-011〜015 出荷前 gate 配備**（PKG-013 が `013a/013b/013c/013d` に分割された場合は分割後の全 ID を含む）。各 gate の fail は `pkg_check_failed` failure_mode として 35章 observables に登録される（35章 §observables 参照）
- [ ] PKG-016 / PKG-017（将来追加される ID を含む）の取り扱いを 36章で確定してから本ゲートを clear する

### Skill 作成側への反映

- `run-build-skill` および 24章テンプレの配置先記述: **正本は `plugins/<plugin-name>/skills/<skill>/`**。`.claude/skills/<skill>/` はそこへの symlink で、`scripts/build-claude-symlinks.py` が作る（aidd-agent-kit 由来の 21 件だけは plugins の外の通常ディレクトリ）
- 24章テンプレ `frontmatter` の `name:` 命名規約は不変（kebab-case）。所属 plugin 名は `name:` には含めず、配置パスで表現（06章第17条）

---

## 関連章

| 章 | 本章との関係 |
|---|---|
| 23 案D/D' | plugin アーキテクチャ前提 |
| 27 §3.1 / §4 | eval-log パス規約（`eval-log/<plugin>/pkg-<id>/` 含む）、PKG ID 改廃の governance |
| 33 MECE 表 | plugin 境界違反の分類 |
| 35 observables | PKG gate fail → `pkg_check_failed` failure_mode の閉ループ |
| 36 PKG-001〜017 | Plugin Package Harness Contract 正本。Phase 0/1/2 ゲートはここを参照する |

## 更新ルール

1. Phase 移行ゲートが変わったら、本章のチェックリストと公式制約照合表を同時に更新する
2. 3アナリスト証拠に新しい収束点が追加されたら本章に追記する
3. 本章の変更は P1_structural（33章ワークフロー準拠）
4. **classify_change の TODO(human) を本章で勝手に実装しない**（自己適用ルール）
5. Phase 0 の「温存」判断を変える場合は P0_breaking として proposal を作成する
6. plugin 物理レイアウト・symlink 戦略・settings.json マージ仕様を変更する場合は P0_breaking として proposal を作成する
7. **PKG-001〜017 の ID 新設・分割・削除は本章で行わず、36章正本 + 27章 §4 rubric governance の承認を経る**（PKG ID 改廃の governance）。本章は PKG ID の参照のみ更新する
