# マルチ企業展開 — harness 正本化 + テナント派生

このディレクトリは、`~/dev/dev/xlocal/xl-skills` の有用な内容をこの harness に移し、以後は **harness を plugin/skill の正本**として扱うための設計と手順をまとめる。

目標は 2 つある。

1. `xl-skills` の Git 管理された最新成果物を、企業非依存の master として harness に反映する。
2. 企業固有値は `tenants/<company>/` に閉じ込め、2 社目以降を config 差し替えだけで導入できるようにする。

現時点では **手順整理のみ**を対象にする。実ファイル移管、削除、symlink 化、秘密情報の移動はまだ実行しない。

| ドキュメント | 内容 |
|---|---|
| `README.md`(本書) | 全体像・現状分析・目標アーキテクチャ・core/tenant 分離線・既存機構マップ |
| [`移管計画.md`](移管計画.md) | `xl-skills` から harness へ取り込むための実行前 Runbook。Git 管理外情報の扱い、棚卸し、反映順、検証ゲート |
| [`構築手順.md`](構築手順.md) | Phase 0-7 のフェーズ別構築手順。master 化、genericize、tenant 化、将来の symlink 運用 |
| [`テナント仕様.md`](テナント仕様.md) | `tenant.json` スキーマ・overlay ファイル契約・config 解決の注入点マップ |

---

## 1. 今回の決定

| 項目 | 決定 |
|---|---|
| 正本リポジトリ | この harness を大元 master にする |
| 供給元 | `~/dev/dev/xlocal/xl-skills` |
| 取り込み単位 | 原則として Git 管理ファイルのみ。cache / worktree / pycache / run artifact / local secrets は持ち込まない |
| 企業固有値 | `tenants/xlocal/` に退避し、core から除去する |
| plugin 正本 | 将来は harness 側 `plugins/` を正にし、`xl-skills` 側へ symlink 共有する |
| 今回やらないこと | 実移管、削除、symlink 作成、秘密情報のコピー、企業別 token 登録 |

「Git 以外の情報を削除してから反映する」は、次の意味で扱う。

- `xl-skills` からは `git ls-files` または `git archive` で Git 管理ファイルだけを取り込む。
- harness 側では、対象 import path の Git 管理外ファイルを事前に棚卸しし、必要な退避後に削除する。
- `.git/`、秘密情報、作業中のユーザ変更は削除対象にしない。
- 実削除は必ず `git clean -n` 相当の dry-run とレビューを挟む。

---

## 2. なぜやるか(背景)

現状 `xl-skills` は **XLOCAL 一社専用**として稼働している。企業固有値が plugin コード・焼き込み config に直接埋め込まれている:

- Keychain サービス名 `notion-api-key.xl-skills` 等の `.xl-skills` 定数(**36 箇所以上**)、`account="xl-skills"` 定数
- 実 Notion DB ID(`company-master`/`skill-intake`/`mf-kessai-invoice-check` の `*.fixed.json` / `*.default.json`)
- 会社プロフィール実データ(`contract-generator/references/party_a.default.json` = 株式会社XLOCAL 一式)
- ドメイン固有値(`impersonate=…@shonai.inc`, `google-sa.xl-skills`)

この状態では **2 社目を導入できない**:同一マシンで Keychain エントリが衝突し、別社の DB が混入し、テナントを分離する第一級の概念が存在しない。

**目標**:企業非依存の大元を 1 つ持ち、`tenants/<company>/` に config 差分を置くだけで企業を追加できる状態にする。

---

## 3. 確定した方針

1. **大元 = この harness リポジトリ**(`個人開発/harness`, remote `daishiman/meta-skill-creator`)を企業非依存の汎用 master にする。`xl-skills` は **XLOCAL テナント #1** として残す。
2. **トポロジ = モノレポ + `tenants/<company>/` オーバーレイ**。企業追加は `tenants/<company>/` を 1 つ足すだけ。
3. **カスタマイズ深度 = config のみで多社対応**。同一 plugin コードのまま、DB ID・会社プロフィール・鍵・ひな形パスを overlay 注入。企業ごとの品質/セキュリティ差は `ref-company-*-rules` の注入で吸収し、**plugin の fork はしない**。
4. **plugin 実体の正本 = harness**。移管完了後に symlink 共有へ進む場合も、編集・レビュー・リリース判断は harness 側を起点にする。

---

## 4. 目標アーキテクチャ

```
harness (大元 master, 企業非依存)
├─ plugins/                     # 層0: 汎用 core (企業固有の焼き込み値なし = placeholder のみ)
│  ├─ harness-creator/ prompt-creator/ skill-intake/
│  ├─ skill-governance-*/ plugin-dev-planner/        # 統治基盤 (NEVER_DISTRIBUTE)
│  └─ company-master/ contract-generator/ mf-kessai-invoice-check/
│     notion-gmail-send/ ubm-goal-setting/ slide-report-generator/  # 業務テンプレ
├─ tenants/
│  ├─ _template/                # scaffold 雛形
│  │  ├─ tenant.json            # slug / keychain_prefix / enabled_bundles / 各 overlay パス
│  │  ├─ notion-config.example.json
│  │  ├─ party_a.example.json
│  │  └─ ref-company-rules/     # L0 company 品質/セキュリティ基準
│  ├─ xlocal/                   # テナント #1 = xl-skills から抽出移設
│  └─ <newcompany>/             # 企業追加はここを1つ足すだけ
├─ scripts/tenant-{init,build,doctor}.py   # オンボーディング・オーケストレータ
└─ .notion-config.json → tenants/<active>/notion-config.json  # 有効テナント (symlink or HARNESS_TENANT env)
```

将来の symlink 共有は次の向きに限定する。

```
xl-skills/plugins/<plugin>  ->  harness/plugins/<plugin>
xl-skills/.claude/skills/*  ->  harness generated output or plugin install output
```

逆向き、つまり harness が `xl-skills` 内の実体へ依存する構成は採用しない。

### 分離線(何が core で何が tenant か)

| 軸 | core(master, 企業非依存) | tenant(`tenants/<company>/`) |
|---|---|---|
| plugin コード | ○(全企業で同一) | ✗(fork しない) |
| Keychain サービス名 | 接頭辞の**導出規則**のみ | 具体値(`keychain_prefix`) |
| Notion DB ID / parent_page | placeholder のみ | 実値(`notion-config.json`) |
| 会社プロフィール(甲) | placeholder のみ | 実値(`party_a.json`) |
| 有効 plugin 集合 | 全 plugin を保持 | 使う bundle を選択(`enabled_bundles`) |
| 品質/セキュリティ基準 | 汎用 evaluator | `ref-company-*-rules` を注入 |
| 秘密情報(トークン等) | 置かない | **置かない**(Keychain のみ・git 管理外) |

> **原則**: 企業固有値は core に一切置かない。core に企業名/実 DB ID/実ドメイン/`.xl-skills` が残っていないことを lint で fail-closed 検査する(構築手順 Phase 2)。

---

## 5. 「新規発明しない」— 既存機構の再利用マップ

この設計は新しい仕組みをほぼ作らない。既に repo に存在する 7 つの素地を**第一級に昇格させるだけ**で成立する。

| 目的 | 再利用する既存資産 | 本計画での扱い |
|---|---|---|
| base+overlay の config 解決 | 4層解決 `plugins/*/scripts/notion_config.py`(env → repo-root `.notion-config.json` → plugin-root → 焼き込み `*.fixed.json`) | tenant 注入点として流用。`.xl-skills` 定数を tenant 由来に集約 |
| Keychain 名前空間化 | `scripts/build-notion-config.py`(git slug → `notion-api-key.<slug>`) | 全業務 plugin DB・全 Keychain へ拡張 |
| 「有効 plugin 集合」= 配布目録 | `bundles.json` + `.claude-plugin/marketplace.json` + `scripts/validate-plugin-completeness.py`(MK/BD, `NEVER_DISTRIBUTE`) | 企業別 bundle を tenant から生成 |
| 焼き込み config の版束縛 | `config-version-lock.json` + `scripts/lint-config-version-sync.py` | placeholder 化に伴う version bump に使用 |
| overlay 配備エンジンの型 | `installers/install.sh` + `installers/manifest.json`(symlink/copy, OS 分岐, 衝突ポリシ) | tenant 有効化機構の参考 |
| 企業別カスタマイズの思想 | doc 29/03/23 の `L0 company → L1 project → L2 task` 注入(`ref-company-*-rules`) | tenant の品質/セキュリティ差の吸収層 |
| setup 検証 | 各 plugin の doctor(`company_master.py doctor` / `mfk_doctor.py` / `setup_doctor.py`) | `tenant-doctor` で統合実行 |
| 三層モデル(層A/B/C, 層A-internal) | `CONVENTIONS.md` | 「企業A固有 vs 企業B固有」テナント軸を**新設追記** |

> **重要な誤解注意**: plugin `company-master` は「大元 master」ではなく、**会社名/住所/法人番号を補完して Notion 企業マスタ DB へ upsert する業務ドメイン plugin**。名称が紛らわしいが master/upstream の概念とは無関係。

---

## 6. 移管時の安全原則

| 原則 | 内容 |
|---|---|
| Git 管理物のみ取り込む | `rsync` でディレクトリ丸ごとコピーしない。`git archive` / `git ls-files` / `git diff --name-status` を入力にする |
| 秘密情報を移さない | token / service account json / `.env` / local keychain dump は移管対象外 |
| 非 Git 情報は dry-run 後に削除 | cache / generated output / pycache / `.worktrees` / local run artifact は削除候補。ただし手動レビュー前に削除しない |
| core は企業非依存 | `plugins/`, `scripts/`, `.claude-plugin/` に XLOCAL 固有値を残さない |
| tenant は実値を持つ | `tenants/xlocal/` は XLOCAL 実値の置き場。ただし秘密情報はファイルに置かない |
| fail-closed | 未設定時に XLOCAL へフォールバックしない |

詳細な実行前手順は [`移管計画.md`](移管計画.md) を参照。

---

## 7. 用語

| 語 | 意味 |
|---|---|
| 大元 / master | 企業非依存の core。この harness リポジトリ。 |
| テナント / tenant | 1 企業 = `tenants/<company>/` の overlay 一式。 |
| overlay | core を上書きする企業固有 config の差分。plugin コードは含まない。 |
| `keychain_prefix` | テナントごとの Keychain 名前空間(例: `xlocal` → `notion-api-key.xlocal`)。二社の秘密情報の物理衝突を防ぐ。 |
| 有効化(activate) | あるマシンで「今どの企業か」を選ぶこと(`HARNESS_TENANT` env or `.notion-config.json` symlink)。 |
| 正本 | 編集・レビュー・配布判断の基準になる唯一の実体。移管完了後は harness 側。 |
| 供給元 | 今回取り込む元リポジトリ。現状は `xl-skills`。 |

まず [`移管計画.md`](移管計画.md)、次に [`構築手順.md`](構築手順.md) を参照。
