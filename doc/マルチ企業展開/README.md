# マルチ企業展開 — harness 正本化 + テナント派生

このディレクトリは、`~/dev/dev/xlocal/xl-skills` の有用な内容をこの harness に移し、以後は **harness を plugin/skill の正本**として扱うための設計と手順をまとめる。

目標は 2 つある。

1. `xl-skills` のレビュー済み commit SHA を `source_snapshot_sha` として固定し、その Git 管理成果物を企業非依存の master として harness に反映する。
2. 企業固有値は `tenants/<company>/` に閉じ込め、2 社目以降を config 差し替えだけ(= **plugin コード変更ゼロ**)で導入できるようにする。なお外部リソースの準備(Notion DB スキーマ作成・SA 発行・Workspace 委任・Slack App)は config 差し替えに含まれず別途必要([企業別リポジトリ運用.md](企業別リポジトリ運用.md) §6 Step R2)。

2026-07-12 に本計画の Phase 0-6 のローカル実装・検証を完了した。実行結果と未完了ゲートは [`実行記録.md`](実行記録.md) を正とする。秘密情報はGitへ格納せず、既存Keychain項目を残したtenant-scoped複製まで完了している。XLOCAL実運用のsymlink cutoverと公開releaseはまだ実行しない。

### 現在の成熟度（2026-07-12 実測）

| 能力 | 状態 | 解放ゲート |
|---|---|---|
| harness を正本にする設計 | **Phase 0-6 ローカル実装・検証済み** | clean commit / release |
| 指定 plugin の正本移管 | **snapshot取込・genericize・XLOCAL標準doctor・機械回帰・content-review・2社目実Notion E2E済み（ローカル未commit）** | clean commit上のbundle再生成 / クリーン環境E2E |
| 同一マシンの symlink 共有 | tooling 実装済み・cutover 未実行 | clean commit + freeze + Step 6.5差分0 + `link_master_plugins.py --apply` |
| macOS 企業向け bundle | ローカル build/install 往復実証済み | clean commit release、クリーン環境 E2E |
| Linux 企業内運用 | 条件付きBLOCKED | 平文XDG backendを企業基準で承認、またはSecret Service等へ置換 + E2E |
| Windows 企業内運用 | **BLOCKED** | Credential Manager または同等の暗号化 backend 実装 + E2E |

したがって、本書の「サポート」は**目標契約**を表す。上表のゲートを通るまでは「対応済み」「納品可能」と表現しない。

| ドキュメント | 内容 |
|---|---|
| `README.md`(本書) | 全体像・現状分析・目標アーキテクチャ・core/tenant 分離線・既存機構マップ |
| [`移管計画.md`](移管計画.md) | `xl-skills` から harness へ取り込むための実行前 Runbook。反映方式の判断記録(§2.5: 手動コピー廃止・fork 棄却・snapshot 採用)、Git 管理外情報の扱い、棚卸し、反映順、検証ゲート |
| [`クリーンアップ計画.md`](クリーンアップ計画.md) | 不要物の削除準備 Runbook(移管計画 §5 disposition の実行子文書)。削除対象の3分類(即削除可 / 旧構造 commit 確定待ち / 削除禁止)・参照整合 8点の検証ゲート・ロールバック |
| [`構築手順.md`](構築手順.md) | Phase 0-7 のフェーズ別構築手順。master 化、genericize、tenant 化、将来の symlink 運用 |
| [`テナント仕様.md`](テナント仕様.md) | `tenant.json` スキーマ・overlay ファイル契約・config 解決の注入点マップ |
| [`企業別リポジトリ運用.md`](企業別リポジトリ運用.md) | **移管完了後の将来運用**: 企業ハーネス(方式B = sanitized export + fresh history)の構築・接続・企業固有 plugin・納品フロー(Step R0-R7) |
| [`30思考法レビュー.md`](30思考法レビュー.md) | 思考リセット後の30思考法適用記録・訂正根拠・4条件の検証結果 |
| [`実行記録.md`](実行記録.md) | 2026-07-12 の snapshot、実装済み範囲、検証結果、未完了ゲート |

読者別の導線:

| 読者 | 読む順 |
|---|---|
| 移管作業者(xl-skills → harness) | [`クリーンアップ計画.md`](クリーンアップ計画.md)(削除準備)→ [`移管計画.md`](移管計画.md) → [`構築手順.md`](構築手順.md) |
| 2 社目導入エンジニア | [`企業別リポジトリ運用.md`](企業別リポジトリ運用.md) §6 Step R0-R7(前提: [`テナント仕様.md`](テナント仕様.md)) |
| 納品先エンジニア(形態(ii)) | 企業 repo の README(正本。[`企業別リポジトリ運用.md`](企業別リポジトリ運用.md) §5 が規定) |

番号体系が 4 種(構築手順 Phase 0-7 / 移管計画 Step 1-7 / PR-1..6 / 納品トラック Step R0-R7)あるため、相互参照は次の対応表を正とする。

| 構築手順 Phase | 移管計画 Step | PR([移管計画 §8](移管計画.md)) |
|---|---|---|
| Phase 0 原則確定・棚卸し設計 | §1-5 の合意と棚卸し手順の固定(Step 番号なし) | PR-1 |
| Phase 1 汎用 core の集約 | Step 1-4(作業保護 → archive export → dry-run → core 反映) | PR-2 |
| Phase 2 genericize | Step 6 | PR-3 |
| Phase 3 テナント層の新設 | Step 5 | PR-3 |
| Phase 4 オンボーディング・オーケストレータ | 対応 Step なし(§7 検証ゲートの tenant-* コマンドを実装) | PR-4 |
| Phase 5 配布(企業別) | 対応 Step なし | PR-5 |
| Phase 6 検証・XLOCAL リグレッション | §7 検証ゲートの実施 | PR-4 の完了条件(XLOCAL doctor / demo fail-closed) |
| Phase 7 symlink 共有 | Step 6.5(切替直前の差分再同期)→ Step 7 | PR-6 |

第 4 の体系 = 納品トラック **Step R0-R7**([企業別リポジトリ運用.md](企業別リポジトリ運用.md))は、移管完了後(Phase 6 全緑 + Phase 7 完了)に開始する独立トラックであり、上表の Phase / Step / PR に対応行を持たない。

---

## 1. 今回の決定

| 項目 | 決定 |
|---|---|
| 正本リポジトリ | この harness を大元 master にする |
| 供給元 | `~/dev/dev/xlocal/xl-skills` |
| 取り込み単位 | 原則として Git 管理ファイルのみ。cache / worktree / pycache / run artifact / local secrets は持ち込まない |
| 企業固有値 | `tenants/xlocal/` に退避し、core から除去する |
| 前提条件 | 本 repo(remote `daishiman/meta-skill-creator`)が **private** であること。`tenants/` に実企業名・企業別基準を Git 管理するため。public 化する場合は `tenants/` を別 private repo へ分離する |
| OS 前提(層別) | **マスター保守者マシン = macOS**(Keychain を実値の正とする現行運用)。企業側マシンの**目標契約**は macOS / Windows / Linux(WSL は Linux 扱い)。Windows は Credential Manager 等の暗号化 backend 実装・E2E 完了まで納品不可 |
| plugin 正本 | 将来は harness 側 `plugins/` を正にし、`xl-skills` 側へ symlink 共有する |
| 現在も実行しないこと | clean commit前のXLOCAL symlink cutover、秘密情報のGit格納、ユーザーが対象外としたGoogle Workspace DWD / 日本郵便IP許可の変更、公開 release |

> **private前提とGitHub導線の両立**: 企業側にprivate harness本体へのread権限は与えない。配布可能coreは版固定bundleとmanifest/checksumを**private企業repoのGitHub Release asset**として添付し、企業側はそこからinstallする。企業固有pluginは企業repo自身の独立marketplaceで配る。これによりharnessの非公開性と「GitHubで共有してinstall」を両立する。
>
> **public 化チェックリスト**: 本 repo を public 化する場合は `tenants/` の別 private repo 分離に加え、次を先に完了する。(a) `doc/`(実ドメイン・実 Keychain 名等)と `eval-log/` に残る実企業値の掃除または private 分離、(b) `lint-tenant-isolation.py` の allowlist(`doc/` `eval-log/` 除外)を検査対象へ拡張するかの判断(構築手順 Phase 2-4)。
>
> **OS前提の層別化**: マスター保守者マシンはmacOS現行運用、企業側の目標はmacOS / Windows / Linux(WSLはLinux扱い)。Python標準ライブラリを実行基盤とするが、secret backendはOS別成熟度ゲートを通す。共通env fallbackはtenant scoped化前に多企業運用へ使わない。unknown OSはfail-closed。

「Git 以外の情報を削除してから反映する」は、次の意味で扱う。

- `xl-skills` からは `git ls-files` または `git archive` で Git 管理ファイルだけを取り込む。
- harness 側では、対象 import path の Git 管理外ファイルを事前に棚卸しし、必要な退避後に削除する。
- `.git/`、秘密情報、作業中のユーザ変更は削除対象にしない。
- 実削除は必ず `git clean -n` 相当の dry-run とレビューを挟む。

### 要望と設計解釈の対照

ユーザー要望をどう設計へ解釈したかの対照。字義から意図的に置換した箇所はその理由を明記する。

| 要望 | 設計解釈 |
|---|---|
| plugins 11本を symlink で共有し、改善を全反映先へ波及 | 保守者マシン内は字義どおり symlink(即時反映)。企業側マシンへは版固定 bundle 配布に**意図的置換**(理由: private repo の非公開性、`NEVER_DISTRIBUTE` 分離、版固定の再現性、Windows の symlink 権限) |
| API キー等は反映先リポジトリで企業ごとに設定 | `keychain_prefix` 名前空間 + credentials 契約(repo に秘密を置かない)で字義どおり充足 |
| Windows 企業でも使える | Step R0 の暗号化 backend 実装ゲート付きの**目標契約**(実装完了まで Windows 企業内運用は BLOCKED) |

---

## 2. なぜやるか(背景)

現状 `xl-skills` は **XLOCAL 一社専用**として稼働している。企業固有値が plugin コード・焼き込み config に直接埋め込まれている:

- Keychain サービス名 `notion-api-key.xl-skills` 等の `.xl-skills` 定数(**36 箇所以上** — 概数。`git -C ~/dev/dev/xlocal/xl-skills grep '\.xl-skills' -- plugins scripts` では 70 ファイル/265 ヒット。正確な母数は Phase 2 の `scripts/lint-tenant-isolation.py` 新設時に再計測する。再計測は `lint-tenant-isolation.py` と同一走査系(対象 path・tracked 判定)で行い、その値を genericize 完了判定の母数とする)、`account="xl-skills"` 定数
- 実 Notion DB ID(`company-master`/`skill-intake`/`mf-kessai-invoice-check` の `*.fixed.json` / `*.default.json`)
- 会社プロフィール実データ(`contract-generator/references/party_a.default.json` = 株式会社XLOCAL 一式)
- ドメイン固有値(`impersonate=…@shonai.inc`, `google-sa.xl-skills`)

この状態では **2 社目を導入できない**:同一マシンで Keychain エントリが衝突し、別社の DB が混入し、テナントを分離する第一級の概念が存在しない。

**目標**:企業非依存の大元を 1 つ持ち、`tenants/<company>/` に config 差分を置くだけ(plugin コード変更ゼロ。外部リソース準備は [企業別リポジトリ運用.md](企業別リポジトリ運用.md) §6 Step R2)で企業を追加できる状態にする。

なお 2 社目の具体的な導入予定は現時点で未確定であり、見込みの有無に関わらず「一社専用構造の解消(Keychain/DB 分離の構造化)」自体を本計画の投資根拠とする。

---

## 3. 確定した方針

1. **大元 = この harness リポジトリ**(`個人開発/harness`, remote `daishiman/meta-skill-creator`)を企業非依存の汎用 master にする。`xl-skills` は **XLOCAL テナント #1** として残す。
   - **なぜ harness か(棄却した代替案)**: (a) 中立な新規 repo を master に新設する案は、統治基盤(lint 群・CI・installers・CONVENTIONS)の再構築コストと履歴の断絶に見合う利点がなく棄却。(b) `xl-skills` を直接 genericize して master 化する案は、XLOCAL の実運用 repo 上で破壊的変更を行うことになり、テナント #1 の安定稼働と正本の分離に反するため棄却。harness は統治基盤の開発起点であり企業非依存の正本に最も近い。
2. **トポロジ = モノレポ + `tenants/<company>/` オーバーレイ**。企業追加は `tenants/<company>/` を 1 つ足すだけ。
3. **カスタマイズ深度 = config のみで多社対応**。同一 plugin コードのまま、DB ID・会社プロフィール・鍵・ひな形パスを overlay 注入。企業ごとの品質/セキュリティ差は `ref-company-*-rules` の注入で吸収し、**plugin の fork はしない**。
   - **仮説の境界**: config で吸収できない企業差(業務フロー・契約書構造の差など)が見つかった場合も fork はせず、plugin 側への **opt-in 機能フラグ**追加で対応する。その際は判断記録を本ディレクトリに残す。
4. **plugin 実体の正本 = harness**。移管完了後に symlink 共有へ進む場合も、編集・レビュー・リリース判断は harness 側を起点にする。

---

## 4. 目標アーキテクチャ

```
harness (大元 master, 企業非依存)
├─ plugins/                     # 層0: 汎用 core (企業固有の焼き込み値なし = placeholder のみ)
│  ├─ harness-creator/ prompt-creator/ plugin-dev-planner/
│  │  skill-governance-*(7本)/                       # 現行実装では配布可能
│  ├─ skill-intake/                                  # 配布可能な共有 plugin
│  └─ company-master/ contract-generator/ mf-kessai-invoice-check/
│     notion-gmail-send/ ubm-goal-setting/ slide-report-generator/  # 業務テンプレ(配布可能)
├─ tenants/
│  ├─ _template/                # scaffold 雛形
│  │  ├─ tenant.json            # slug / keychain_prefix / enabled_bundles / 各 overlay パス
│  │  ├─ notion-config.example.json
│  │  ├─ party_a.example.json
│  │  ├─ google-config.example.json   # contract-generator の台帳/出力フォルダ/slack_channel
│  │  └─ ref-company-rules/     # L0 company 品質/セキュリティ基準
│  ├─ xlocal/                   # テナント #1 = xl-skills から抽出移設
│  │  └─ (_template と同構成。notion-config / party_a / google-config の実値 .json は gitignore)
│  └─ <newcompany>/             # 企業追加はここを1つ足すだけ
├─ scripts/tenant-{init,build,doctor}.py   # オンボーディング・オーケストレータ
└─ .notion-config.json → tenants/<active>/notion-config.json  # 有効テナント (symlink or HARNESS_TENANT env)
```

### plugin 集合の正本

| 集合 | 内容 | 用途 |
|---|---|---|
| `MASTER_LINK_SET`（11本） | `harness-creator` / `plugin-dev-planner` / `prompt-creator` / `skill-governance-*` 7本 / `skill-intake` | ユーザー指定の symlink 必須集合 |
| `NEVER_DISTRIBUTE`（3本） | `harness-creator` / `prompt-creator` / `plugin-dev-planner` | 企業側 bundle へ含めない。正本は `scripts/validate-plugin-completeness.py`(供給元 xl-skills 版。Phase 1 取込後は harness 版) |
| `BUSINESS_TEMPLATE_SET`（6本） | `company-master` / `contract-generator` / `mf-kessai-invoice-check` / `notion-gmail-send` / `ubm-goal-setting` / `slide-report-generator` | tenant の `enabled_bundles` で選択する業務 plugin |
| `XLOCAL_CUTOVER_SET`（17本） | `MASTER_LINK_SET` + `BUSINESS_TEMPLATE_SET` | XLOCAL 日次業務の切替時だけ全数を検証する在庫集合 |

> **訂正記録(2026-07-11)**: 旧文書の `NEVER_DISTRIBUTE=10本` は、現行実装（3本）と marketplace / bundle（governance 7本を配布）に反する未承認の方針追加だったため撤回した。将来この集合を変える場合は、実装・manifest・marketplace・bundle と本表を同一変更で更新する。
>
> **機械可読正本**: 集合の機械可読正本は `.claude-plugin/link-profiles.json`。本表と `scripts/link_master_plugins.py` は同一変更で同期する。

将来の symlink 共有は次の向き(参照元 → harness 正本)に限定する。

```
<参照元>/plugins/<plugin>   ->  harness/plugins/<plugin>            # 参照元の例: xl-skills、企業 repo ローカルクローン
<参照元>/.claude/skills/*   ->  harness generated output or plugin install output
```

逆向き、つまり harness が参照元内の実体へ依存する構成は採用しない。

> **symlink 参照元の一般化**: 参照元は `xl-skills` に限定しない。同一マシン上の任意ディレクトリから引用できる。条件: (a) 編集起点は harness だけ（技術的read-onlyではなく運用規約）、(b) symlinkはcommitせず `link_master_plugins.py` で再生成、(c) doctorが11本の存在・向き・dirtyを検査する。

### 改善の伝播範囲(正本マトリクス)

core plugin の改善が「どこへ・どの機構で・いつ・どのゲートを経て」届くかの正本。**他文書はこの表を参照し、同じ表を重複掲載しない**(構築手順 Phase 7 / 企業別リポジトリ運用 §6 Step R7 から参照される)。

| 参照先 | 機構 | 即時性 | ゲート |
|---|---|---|---|
| 同一マシンの symlink 参照元(xl-skills / 他作業ディレクトリ / 企業 repo ローカルクローン) | 作業ツリー直結 symlink(setup スクリプト再生成・commit しない) | **即時**(未コミット編集・ブランチ切替も見えるため開発参照専用) | `link_master_plugins.py --check`。業務実行時は正本 worktree の dirty を FAIL し、harness 正本 worktree の HEAD が main（または明示許容した branch/tag）であることを検査。実験は worktree 隔離 |
| 企業側マシン(形態(ii)) | private企業repoのGitHub Release asset（版固定bundle）+ repo pull | release作成・導入時 | release manifest / checksum / install receipt / `core_compat` / `tenant-doctor --mode customer_bundle` |

`NEVER_DISTRIBUTE` 3本は下段(企業側マシン)へは決して届かない。上段の symlink 引用は「配布」に当たらない。

### 分離線(何が core で何が tenant か)

| 軸 | core(master, 企業非依存) | tenant(`tenants/<company>/`) |
|---|---|---|
| plugin コード | ○(全企業で同一) | ✗(fork しない) |
| Keychain サービス名 | 接頭辞の**導出規則**のみ | 具体値(`keychain_prefix`) |
| Notion DB ID / parent_page | placeholder のみ | 実値(`notion-config.json`) |
| 会社プロフィール(甲) | placeholder のみ | 実値(`party_a.json`) |
| 有効 plugin 集合 | 全 plugin を保持 | 使う bundle を選択(`enabled_bundles`) |
| 品質/セキュリティ基準 | 汎用 evaluator | `ref-company-*-rules` を注入 |
| 秘密情報(トークン等) | 置かない | **置かない**(企業基準で承認したsecret backendのみ・git管理外 — テナント仕様 §3) |

> **原則**: 企業固有値は core に一切置かない。core に企業名/実 DB ID/実ドメイン/`.xl-skills` が残っていないことを lint で fail-closed 検査する(構築手順 Phase 2)。

---

## 5. 「新規発明しない」— 既存機構の再利用マップ

この設計は新しい仕組みをほぼ作らない。以下の素地を**第一級に昇格させるだけ**で成立する。ただし「所在」列のとおり、一部は現 harness に無く **xl-skills から Phase 1 で取り込む**(所在は 2026-07 の実測。[移管計画 §4.5](移管計画.md) の診断と整合)。

| 目的 | 再利用する既存資産 | 所在 | 本計画での扱い |
|---|---|---|---|
| base+overlay の config 解決 | 4層解決 `plugins/*/scripts/notion_config.py`(env → repo-root `.notion-config.json` → plugin-root → 焼き込み `*.fixed.json`) | harness に現存(`skill-creator` / `skill-intake` の 2 箇所。Phase 1 で `skill-creator` は `harness-creator` へ改名(置換)され、`company-master` 分が到来して計 **3 箇所**) | tenant 注入点として流用。`.xl-skills` 定数を tenant 由来に集約 |
| Keychain 名前空間化 | `scripts/build-notion-config.py`(git slug → `notion-api-key.<slug>`) | harness に現存 | 全業務 plugin DB・全 Keychain へ拡張 |
| 「有効 plugin 集合」= 配布目録 | `.claude-plugin/bundles.json` + `.claude-plugin/marketplace.json` + `scripts/validate-plugin-completeness.py`(MK/BD, `NEVER_DISTRIBUTE`) | harness に旧版が現存(MK 系のみ・`NEVER_DISTRIBUTE` 未実装の stale)。現行実装は xl-skills にあり Phase 1 で取り込む | 企業別 bundle を tenant から生成 |
| 焼き込み config の版束縛 | `config-version-lock.json` + `scripts/lint-config-version-sync.py` | **xl-skills にあり Phase 1 で取り込む**(現 harness に不在) | placeholder 化に伴う version bump に使用(Phase 1 取込が前提) |
| vendored 配布の同期規約 | `scripts/lint-intake-vendored-ssot.py`(SSOT 1 実装 + 各 plugin への vendored 配置 + drift 検出 lint) | harness に現存 | Phase 2-1 の resolver 一元化はこの方式を踏襲(単一ファイルへの物理集約はしない) |
| overlay 配備エンジンの型 | `installers/install.sh` + `installers/manifest.json`(symlink/copy, OS 分岐, 衝突ポリシ) | harness に現存 | tenant 有効化機構の参考 |
| 企業別カスタマイズの思想 | [`29-multi-project-rubric-composition.md`](../ClaudeCodeスキルの設計書/29-multi-project-rubric-composition.md) / [`03-yaml-frontmatter-reference.md`](../ClaudeCodeスキルの設計書/03-yaml-frontmatter-reference.md) / [`23-meta-skill-architecture.md`](../ClaudeCodeスキルの設計書/23-meta-skill-architecture.md) の `L0 company → L1 project → L2 task` 注入(`ref-company-*-rules`) | harness に現存 | tenant の品質/セキュリティ差の吸収層 |
| setup 検証 | 各 plugin の doctor(`company_master.py doctor` / `mfk_doctor.py` / `setup_doctor.py`) | `contract-generator/lib/setup_doctor.py` のみ現存。他は xl-skills にあり Phase 1 で取り込む | `tenant-doctor` で統合実行 |
| 三層モデル(層A/B/C, 層A-internal) | `CONVENTIONS.md` | harness に現存 | 「企業A固有 vs 企業B固有」テナント軸を**新設追記** |

> **重要な誤解注意**: plugin `company-master` は「大元 master」ではなく、**会社名/住所/法人番号を補完して Notion 企業マスタ DB へ upsert する業務ドメイン plugin**。名称が紛らわしいが master/upstream の概念とは無関係。

---

## 6. 移管時の安全原則

| 原則 | 内容 |
|---|---|
| レビュー済み snapshot のみ取り込む | `rsync` で丸ごとコピーしない。fetch 後の採用 SHA を `source_snapshot_sha` に固定し、供給元が behind / dirty の間は停止する。その SHA の `git archive` / `git ls-tree` を入力にする |
| 秘密情報を移さない | token / service account json / `.env` / local keychain dump は移管対象外 |
| 非 Git 情報は dry-run 後に削除 | cache / generated output / pycache / `.worktrees` / local run artifact は削除候補。ただし手動レビュー前に削除しない |
| core は企業非依存 | `plugins/`, `scripts/`, `.claude-plugin/` に XLOCAL 固有値を残さない |
| tenant は実値を持つ | `tenants/xlocal/` は XLOCAL 実値の置き場。ただし秘密情報はファイルに置かない |
| fail-closed | 未設定時に XLOCAL へフォールバックしない |

**削除判断**: 現時点で「`doc/マルチ企業展開/` 以外をすべて削除」は不可。少なくとも本書が参照する `doc/ClaudeCodeスキルの設計書/` と、移管後の plugins / scripts / tests / installers / manifests / CI の依存閉包を保持する必要がある。削除できるのは、[移管計画.md](移管計画.md) の disposition 表で `DELETE_AFTER_REVIEW` と判定され、参照・実行依存が0であることを確認した項目だけである。

詳細な実行前手順は [`移管計画.md`](移管計画.md) を参照。

---

## 7. 用語

| 語 | 意味 |
|---|---|
| 大元 / master | 企業非依存の core。この harness リポジトリ。 |
| harness | 本 repo(`個人開発/harness`)。企業非依存の大元 master。 |
| 企業ハーネス | 方式B の企業別 private repo。harness の fork・コピーではなく sanitized export + fresh history で構築する([企業別リポジトリ運用.md](企業別リポジトリ運用.md))。 |
| `harness-creator` | plugin 名。repo としての harness とは無関係。 |
| テナント / tenant | 1 企業 = `tenants/<company>/` の overlay 一式。 |
| overlay | core を上書きする企業固有 config の差分。plugin コードは含まない。 |
| `keychain_prefix` | テナントごとの資格情報ストア名前空間(例: `xlocal` → `notion-api-key.xlocal`)。二社の秘密情報の物理衝突を防ぐ。フィールド名は互換のため維持するが、意味は「**OS 資格情報ストア上の名前空間 prefix**」であり macOS Keychain 専用ではない(2026-07-11 ユーザー要望・テナント仕様 §2/§3)。 |
| 資格情報ストア(credential store) | 秘密(トークン・SA 鍵)を置く保管先。macOS は Keychain。現行 Linux 実装は `$XDG_CONFIG_HOME/xl-skills/secrets.json`(chmod 600)であり OS credential store ではない。Windows 現行実装は base64 の非暗号化ファイル。両者は企業納品前にセキュリティ基準を再判定し、Windows は暗号化 backend 実装まで BLOCKED。解決チェーンの正本は設計書 [22-cross-platform-runtime.md](../ClaudeCodeスキルの設計書/22-cross-platform-runtime.md) と `cross_platform_secret.py`。 |
| WSL | Windows Subsystem for Linux。OS 判定(mac / linux / windows / unknown)では **Linux 扱い**(設計書 22 章)。unknown は fail-closed 停止。 |
| 有効化(activate) | あるマシンで「今どの企業か」を選ぶこと(`HARNESS_TENANT` env or `.notion-config.json` symlink)。 |
| 正本 | 編集・レビュー・配布判断の基準になる唯一の実体。移管完了後は harness 側。 |
| 供給元 | 今回取り込む元リポジトリ。現状は `xl-skills`(`plugins/` に 17 本実在)。 |
| genericize | core から企業固有の焼き込み値を除去し、placeholder + fail-closed にする作業(構築手順 Phase 2)。 |
| fail-closed | 未設定・不整合のとき黙って既定値へ落ちず、エラー停止する設計原則。 |
| doctor | 設定・接続・契約の充足を検査する診断スクリプト群。`tenant-doctor` が統合実行する。 |
| bundle | `.claude-plugin/bundles.json` に定義する配布用 plugin 集合。企業側マシンへは版固定アーカイブで提供する。 |
| marketplace | Claude Code の plugin 配布目録(`.claude-plugin/marketplace.json`)。企業 repo は企業固有 plugin 用の独立 marketplace を持てる。 |
| vendored | SSOT 1 実装を各 plugin 内へ複製配置し、同期 lint(`lint-intake-vendored-ssot.py` 方式)で drift を検出する配置方式。 |
| SSOT | Single Source of Truth。唯一の正本実装・正本定義。 |
| MK/BD | `validate-plugin-completeness.py` の検査系列 ID。MK = marketplace 登録整合(MK-001..004)、BD = bundle 登録整合(BD-001)。 |
| `MASTER_LINK_SET` | 同一マシンで harness 正本を symlink 引用するユーザー指定11 plugin。業務テンプレ6本は含まない。 |
| NEVER_DISTRIBUTE | 企業側マシンへ配布しない plugin の固有名 denylist。現行正本は §4 の3本。 |

読者別の読み順は冒頭の導線表を参照(移管作業者は [`移管計画.md`](移管計画.md) → [`構築手順.md`](構築手順.md))。
