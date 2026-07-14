# 36. Plugin Package Harness Contract

最終更新: 2026-05-23

## 目的

Harness Creator が量産する成果物は単独 Skill ではなく **plugin package**（`plugins/<plugin-name>/` 一式）である。本章は、その plugin package を「`/plugin install <plugin>` 一発で、必要な Skill / Agent / Hook / script / settings / config が齟齬なく揃って動く」状態に到達させるための **同梱契約（harness contract）** を正本として定義する。

具体的には次の 3 つを正本として固定する。

1. **`package_mode`**: 配布形態の閉じた列挙（`bundle` / `skill-only`）と、それぞれの正本パス・適用ゲートの差分
2. **PKG-001〜017**: package completeness check の閉じた ID 列挙（P0 静的検査 / Phase 1 smoke / Phase 2 出荷前 gate / 予約）
3. **Install UX Contract**: ユーザー視点で plugin install から最初の Skill 起動までに発生すべき / 発生してはならない事象の列挙

本章は 23 章案 D' で確立した plugin アーキテクチャ、34 章 Phase 0/1/2 ロードマップ、27 章 rubric governance、35 章 meta-harness observables の上に乗る派生章であり、これら 4 章との片道リンクを必ず双方向に閉じる（§関連章 参照）。

---

## 正本の分担

| 領域 | 正本 | 本章で扱うこと |
|---|---|---|
| plugin 物理レイアウト | `34-plugin-governance-roadmap.md` | Phase 0/1/2 ゲートが参照する PKG ID の提供 |
| settings 派生マージ | `34a-settings-merge-spec.md` | package 同梱判定（PKG-003 と §4 名前空間共有） |
| eval-log パス | `27-rubric-governance-runbook.md` §3.1 | PKG gate の eval-log 保存規約に従う |
| PKG fail の観測軸 | `35-meta-harness-feedback-loop.md` `pkg_check_failed` | failure_mode を発火させる側として定義 |
| PKG ID 改廃 governance | `27-rubric-governance-runbook.md` §4.1 | 本章は改廃の **対象**、決裁は 27 章 |
| 命名規約 | `06-classification-and-naming.md` 第17条 | plugin 名は配置パス、Skill 名は kebab-case |
| 配布レイヤー時系列 | `25-meta-skill-runbook.md` 配布レイヤー表 | 現行（creator-kit）⇔ Phase 2 以降（plugin package）の対応 |

**自己制約**: 本章は PKG ID の **意味と検査内容** を正本として持つが、ID 改廃（新設 / 分割 / 削除 / 意味変更）の **決裁経路** は 27 章 §4.1 に従う。本章単独で ID を増減することはできない。

---

## §`package_mode`

`package_mode` は plugin package の配布形態を表す閉じた列挙であり、`plugins/<plugin-name>/.claude-plugin/plugin.json` の最上位キーとして宣言する。

| `package_mode` | 配布意図 | 正本パス（Skill 本文） | 適用 PKG ID | 用途 |
|---|---|---|---|---|
| `bundle` | 公開配布。install UX を満たす plugin package | `plugins/<plugin-name>/skills/<skill-name>/SKILL.md`（一次） | PKG-001〜010 必須、PKG-011〜015 出荷前必須 | 新規量産の既定値。**新規 plugin はこちらを選ぶ** |
| `skill-only` | legacy / dev-only / migration exception | `.claude/skills/<skill-name>/SKILL.md`（一次。`plugins/...` 側があれば派生） | PKG-001〜009 のみ任意適用、PKG-010 以降は適用対象外 | 下記 3 例外に限定 |

### `skill-only` 適用範囲（恒久例外 3 種）

| 例外 | 説明 | 参照 |
|---|---|---|
| legacy | creator-kit 時代に作られた既存資産で plugin 化未着手のもの。Phase 2 移行前の暫定状態 | 25 章 配布レイヤー表 |
| dev-only | 設計書 dogfooding など、配布物ではなく自己検査用 artifact | 26 章 §dogfooding と `skill-only` モードの関係 |
| migration | Phase 2 移行作業中の一時的な並走状態。期限付きで `bundle` へ収束させる | 34 章 Phase 2 ゲート |

新規 plugin で `package_mode: skill-only` を選ぶことは禁止（CI block 対象）。例外 3 種のいずれかに該当することを `plugin.json` の `package_mode_exception` フィールドに記録すること（`legacy` / `dev-only` / `migration` の閉列挙）。

### `bundle` での正本パスとの関係

`bundle` mode では、開発作業の書き換え先は常に `plugins/<plugin-name>/skills/<skill-name>/SKILL.md`。`.claude/skills/<skill-name>/` は `build-claude-symlinks.py`（34 章 Phase 0）が生成する **symlink 派生表現** にすぎず、人間も AI もここを直接編集してはならない（24 章 §正本パスのレイヤー優先順位）。

---

## §Install UX Contract

`bundle` mode plugin が満たすべき install UX を以下に固定する。`skill-only` mode には適用しない。

### 必須事象（install 後 60 秒以内に観測可能であること）

1. `/plugin install <plugin>` 実行後、追加の手動コピー・symlink 操作なしで以下が完了する
   - `plugins/<plugin-name>/skills/*` 配下の全 Skill が `/skill list` に列挙される
   - `plugins/<plugin-name>/agents/*` 配下の全 Agent が `Agent` tool の `subagent_type` で参照可能になる
   - `plugins/<plugin-name>/hooks/*` 配下の hook が settings に反映される（hook 名・event の一覧が `claude hook list` 相当で確認できる）
   - `plugins/<plugin-name>/scripts/*` が実行可能ビットつきで配置される
2. plugin が宣言する `permissions` は plugin スコープ内でのみ有効化される（34 章 公式制約 b）
3. plugin が参照する全パスが plugin root 配下に閉じている（34 章 公式制約 e）

### 禁止事象（install 直後〜初回 Skill 起動までに発生してはならない）

1. plugin 外（`scripts/` `adapters/` `.claude/config/` 等）への参照解決失敗
2. 他 plugin と名前空間が衝突した状態でのサイレント上書き（PKG-003 で fail させる）
3. ユーザーに手動で `chmod +x` / `ln -s` / `cp` を要求するエラー
4. `.claude/settings.json` への直接書き込み（必ず Layer2 settings 断片からの派生生成経路を通る、34a 章 §2）

### 計測点

Install UX Contract の達成は PKG-010 install smoke（後述）で機械検証する。Smoke は `eval-log/<plugin>/pkg-010/<YYYY-MM-DD>-<run>.{json,log}` に保存され（27 章 §3.1）、fail は 35 章 `pkg_check_failed` failure_mode として観測カウントされる。

---

## §PKG-001〜017 一覧

PKG ID は閉じた列挙であり、本表に存在しない ID は **存在しないものとして扱う**。新設・分割・削除・意味変更は 27 章 §4.1 governance を経由する。

### Phase 0 P0 静的検査（PKG-001〜009、必須）

| ID | 名称 | 検査内容 | 実装 | 適用 `package_mode` |
|---|---|---|---|---|
| PKG-001 | `claude plugin validate --strict` 通過 | 公式 CLI の strict validate が exit 0 | `scripts/run-plugin-validate-strict.sh`（公式 CLI ラッパー） | `bundle` |
| PKG-002 | `plugin.json` frontmatter 完備 | `name` / `version` / `package_mode` / `description` / `entry_points` の必須キー充足 | `scripts/validate-plugin-package.py` `--check pkg-002` | `bundle` `skill-only` |
| PKG-003 | package 単位の名前空間衝突検査 | 同一 marketplace 内で `skill-name` / `agent-name` / `hook-name` / `permission-name` の衝突なし。34a §4 と名前空間定義を共有 | `scripts/validate-plugin-package.py` `--check pkg-003` | `bundle` |
| PKG-004 | SKILL.md frontmatter 完備 | 03 章 frontmatter 必須キー、`responsibility_refs` / `schema_refs` / `manifest` を含む | `scripts/validate-frontmatter.py --skills-dir plugins/<plugin>/skills` | `bundle` `skill-only` |
| PKG-005 | Agent definition 整合 | `plugins/<plugin>/agents/*.md` の name と SKILL.md `subagent_refs` が一致 | `scripts/validate-plugin-package.py` `--check pkg-005` | `bundle` |
| PKG-006 | Hook registration 整合 | `plugins/<plugin>/hooks/*.{json,sh}` が settings 断片の `hooks` 配列で全て参照されている。逆方向に未登録 hook ファイルがない | `scripts/validate-plugin-package.py` `--check pkg-006` | `bundle` |
| PKG-007 | script 存在 + 実行可能 | SKILL.md / agent / hook から参照される `scripts/*` が plugin root 配下に存在し、shebang を持ち、`+x` ビットが立っている | `scripts/validate-plugin-package.py` `--check pkg-007` | `bundle` |
| PKG-008 | settings 断片 lint | `plugins/<plugin>/settings/*.json` が 34a 章 INV-1〜12 を満たし、Layer3 派生で衝突を発生させない | `scripts/validate-plugin-package.py` `--check pkg-008` | `bundle` |
| PKG-009 | 外部参照ゼロ | plugin 内の全ファイルが plugin root 外を参照しない（34 章 公式制約 e） | `scripts/lint-external-refs.py --plugin <name>` | `bundle` |

### Phase 1 install smoke（PKG-010、必須）

| ID | 名称 | 検査内容 | 実装 |
|---|---|---|---|
| PKG-010 | install smoke | local marketplace から `/plugin install` を擬似実行し、§Install UX Contract「必須事象」3 項目と「禁止事象」4 項目を観測する。実行ログは `eval-log/<plugin>/pkg-010/` に保存 | `scripts/smoke-plugin-install.sh` |

### Phase 2 出荷前 gate（PKG-011〜015、必須）

| ID | 名称 | 検査内容 | 実装 |
|---|---|---|---|
| PKG-011 | uninstall 完全性 | `/plugin uninstall <plugin>` 後に plugin 由来の symlink / settings 断片 / hook 登録が残存しない | `scripts/smoke-plugin-uninstall.sh` |
| PKG-012 | upgrade 冪等性 | 同一 version の re-install が no-op であり、異なる version の install が破壊的変更を起こさない | `scripts/smoke-plugin-upgrade.sh` |
| PKG-013 | permission scope 検証（4 sub-check） | `package_mode: bundle` plugin が宣言する permission が plugin スコープ内で閉じていることを 4 観点で検査（§PKG-013 分割表 参照） | `scripts/validate-plugin-permissions.py` |
| PKG-014 | runtime contract 検証 | SKILL.md 宣言の `kind` / `combinator` と実 runtime 挙動が一致（28 章 script execution model） | `scripts/validate-plugin-package.py` `--check pkg-014` |
| PKG-015 | rubric 違反率しきい値 | 当該 plugin の直近 release で 27 章 rubric 違反率が governance 設定値を下回る。履歴 bootstrap 中は明示 `not_applicable` | `run-plugin-package-check/scripts/run-pkg-015.py --plugin <name> --log-dir <log-dir> --out <pkg-log>` |

#### PKG-013 分割表（permission scope 4 sub-check）

| sub-ID | 検査対象 |
|---|---|
| PKG-013a | tool permissions（Bash 等の許可コマンド範囲が plugin スコープ宣言を超えない） |
| PKG-013b | file system permissions（読み書き対象が plugin root 配下に閉じる） |
| PKG-013c | network permissions（外部通信先の allowlist が plugin manifest 宣言と一致） |
| PKG-013d | MCP / external integration permissions（Notion / Drive / Gmail 等の scope が manifest と一致） |

### 予約 ID（PKG-016〜017）

| ID | 状態 |
|---|---|
| PKG-016 | **予約**。意味は未確定。34 章 Phase 2 ゲートを clear する前に本章で確定すること |
| PKG-017 | **予約**。意味は未確定。34 章 Phase 2 ゲートを clear する前に本章で確定すること |

予約 ID を実装する際は、ID 新設として 27 章 §4.1 governance を通すこと。「予約済み」状態のままで Phase 3 へは進めない。

---

## §`references/package-contract.json` schema

PKG ID 群を機械可読化した正本 schema。`plugins/<plugin>/references/package-contract.json` として各 plugin に配置し、validator が読み取る。

### schema（JSON Schema draft 2020-12）

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://xl-skills/schemas/package-contract.json",
  "type": "object",
  "required": ["package_mode", "pkg_checks"],
  "properties": {
    "package_mode": {
      "enum": ["bundle", "skill-only"]
    },
    "package_mode_exception": {
      "enum": ["legacy", "dev-only", "migration"],
      "description": "package_mode が skill-only の場合のみ必須"
    },
    "pkg_checks": {
      "type": "object",
      "patternProperties": {
        "^PKG-(00[1-9]|01[0-5]|01[3][a-d])$": {
          "type": "object",
          "required": ["status", "last_run_at"],
          "properties": {
            "status": { "enum": ["pass", "fail", "skip", "not_applicable"] },
            "last_run_at": { "type": "string", "format": "date-time" },
            "eval_log_path": { "type": "string" },
            "skip_reason": { "type": "string" }
          }
        }
      },
      "additionalProperties": false
    }
  },
  "allOf": [
    {
      "if": { "properties": { "package_mode": { "const": "skill-only" } } },
      "then": { "required": ["package_mode_exception"] }
    }
  ]
}
```

### validator

`scripts/validate-package-contract.py`（Python stdlib + `jsonschema` のみ。CI 接続点は 34 章 §更新ルール）。CI からの呼出しは Phase 0 lint パイプライン（`make plugin-package-check` 経由、Makefile 既存ターゲット）に統合する。

### `status: not_applicable`

dogfooding artifact（26 章）など `skill-only` 例外時に PKG-010 以降を適用しないケースは、各 PKG ID に `status: "not_applicable"` と `skip_reason` を明示する。`skip` は「実行予定だが今回省略」、`not_applicable` は「契約上対象外」と意味を分けること。

---

## §現状との差分

2026-05-23 時点での実装ギャップを以下に列挙する。本表は実装進捗に応じて更新する。

| 項目 | 現状 | 必要対応 | 起票先 |
|---|---|---|---|
| `scripts/validate-plugin-package.py` | PKG-002〜008 / PKG-014 の `--check` 対応済み | PKG ID 別 sub-command と findings JSON を維持 | 34 章 Phase 0 タスク |
| `scripts/run-plugin-validate-strict.sh` | 未実装 | 公式 CLI ラッパーを Python stdlib + bash で作成 | 34 章 Phase 0 タスク |
| `scripts/smoke-plugin-install.sh` | 未実装 | local marketplace install smoke 自動化 | 34 章 Phase 1 ゲート |
| `scripts/smoke-plugin-uninstall.sh` | 未実装 | Phase 2 出荷前 gate | 34 章 Phase 2 ゲート |
| `scripts/smoke-plugin-upgrade.sh` | 未実装 | Phase 2 出荷前 gate | 34 章 Phase 2 ゲート |
| `scripts/validate-plugin-permissions.py` | 未実装 | PKG-013 4 sub-check | 34 章 Phase 2 ゲート |
| 全 plugin の `references/package-contract.json` | 8 plugin で未配置 | 各 plugin に schema 準拠の contract を配置 | Phase 0 lint 化 |
| PKG-016 / PKG-017 意味確定 | 未確定 | Phase 2 clear 前に本章で確定 | 27 章 §4.1 governance |
| 35 章 `pkg_check_failed` observable 配線 | 35 章側で定義済み、本章からの fail injection が未配線 | PKG gate fail 時に `eval-log/<plugin>/pkg-<id>/` を 35 章 collector が拾う配線 | 35 章 collect → classify ステップ |

---

## §関連章（双方向リンク）

| 章 | 本章との関係 | 逆方向リンク |
|---|---|---|
| 24 メタスキルテンプレ | 正本パスの `bundle` / `skill-only` 切替を依存 | 24 章 §正本パスのレイヤー優先順位 |
| 25 メタスキルランブック | 配布レイヤー時系列で `manifest` 二義性を解消 | 25 章 §配布レイヤーの時系列分離 |
| 26 dogfooding | `skill-only` の dev-only 恒久例外を受ける | 26 章 §dogfooding と `skill-only` モードの関係 |
| 27 rubric governance | PKG ID 改廃の決裁経路、eval-log パス規約 | 27 章 §3.1 PKG gate 用 eval-log パス、§4.1 PKG ID 改廃 governance |
| 28 script execution model | PKG-014 runtime contract 検証の根拠 | 28 章 |
| 33 change governance | PKG ID 変更は P0_breaking として扱う境界 | 33 章 MECE 表 |
| 34 plugin governance roadmap | Phase 0/1/2 ゲートが本章の PKG ID を参照 | 34 章 Phase 0/1/2 タスク |
| 34a settings merge spec | PKG-003 と §4 名前空間共有 | 34a 章 §4 |
| 35 meta-harness FB ループ | PKG fail → `pkg_check_failed` failure_mode の閉ループ | 35 章 §observables、§PKG gate 連動の閉ループ |

---

## §更新ルール

1. PKG ID の新設・分割・削除・意味変更は本章を正本として行うが、**決裁は 27 章 §4.1 governance を経由**する（自己制約）
2. `package_mode` の列挙値変更は P0_breaking として 33 章 proposal を作成する
3. `references/package-contract.json` schema の破壊的変更（required 追加、enum 削除、`pkg_checks` パターン変更）は P0_breaking として 33 章 proposal を作成する
4. Install UX Contract の必須事象 / 禁止事象の追加・削除は P0_breaking として 33 章 proposal を作成する。**ユーザー観測仕様であり、サイレント変更を禁止**
5. 予約 ID（PKG-016 / 017）を実装する際は ID 新設として §更新ルール 1 に従う。予約状態のまま Phase 3 へ進まない
6. 本章で `eval-log` パスを再定義しない。27 章 §3.1 を一意の正本とする
7. 本章で 35 章 failure_mode 列挙を再定義しない。35 章 observables.json を一意の正本とする
