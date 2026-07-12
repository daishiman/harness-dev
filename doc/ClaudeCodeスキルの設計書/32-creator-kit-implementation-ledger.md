# 32. Creator Kit Implementation Ledger

最終更新: 2026-05-18

## 目的

本章は、`creator-kit/` と関連メタSkill基盤の実装状態を、設計書側から追跡するための台帳である。

23〜31章は「どう設計するか」を定義する。本章は「その設計が現在どこまで実装・評価・運用化されたか」を記録する。重複した仕様を増やさないため、詳細仕様は各章と実ファイルを正本とし、本章は時系列、判断、検証結果、残課題だけを扱う。

## 正本の分担

| 領域 | 正本 | 本章で扱うこと |
|---|---|---|
| メタSkill構造 | `23-meta-skill-architecture.md` | 実装済みSkill群とkit境界の状態 |
| 運用Runbook | `25-meta-skill-runbook.md` | E2E入口と移行状態 |
| script規約 | `28-script-execution-model.md` / `creator-kit/CONVENTIONS.md` | Bash/Python 2層規約の採用状態 |
| 出力routing / secret | `31-output-routing-adapter-architecture.md` | adapter / Keychain / audit の実装状態 |
| kit構成 | `creator-kit/manifest.json` | 配布対象、禁止依存、version |
| 実装現物 | `.claude/skills/`, `scripts/`, `creator-kit/` | ファイル実在と未移行項目 |

## 全体テーマ

「Claude Code Skill を量産・評価・運用するためのメタスキル基盤」を、設計書31章ぶんの知見を反映しつつ、安全、可搬、規律的に整える。

| 軸 | 意味 | 機械強制 |
|---|---|---|
| 安全 | APIキーを LLM context に渡さない | Keychain + `scripts/secrets/audit_secret_leak.py` |
| 可搬 | 別repoでメタSkill群を再利用できる | `creator-kit/manifest.json` + install/migrate/uninstall |
| 規律 | Bash/Pythonと依存関係を統一ルールで管理する | `creator-kit/CONVENTIONS.md` + `creator-kit/scripts/lint-forbidden-deps.py` |
| 横展開 | 新しい共通Skill/script/configを manifest に反映する | `scripts/build-manifest-registration-plan.py` + `lint-manifest-contents.py` |

通底する設計原則は「文書から仕組みへ」である。ルールをMarkdownだけに閉じず、可能な限り script、manifest、gate、lint、audit に落とす。

## 実装履歴

| Phase | 内容 | 主な成果物 | 設計書への対応 |
|---|---|---|---|
| A | 31章全体を `run-elegant-review` 相当の 30思考法 x 4条件で再検証 | 責務分離、Subagent自動構築、hook統合、model選択、YAML configurable、create/update両対応の採用判断 | `23` / `24` / `25` / `30` |
| B | E2Eオーケストレーターを構築 | `.claude/skills/run-skill-create/`, `gate-templates.md`, `handoff-schema.json` | `23` / `25` |
| C | 出力先routing基盤を Port/Adapter で設計 | `ref-output-routing`, `scripts/adapters/sink_*.py`, `resolve_route.py`, `dispatch.py` | `31` |
| D | APIキー保護機構を実装 | `keychain_helper.py`, `audit_secret_leak.py`, `scripts/secrets/README.md`, `sanitize_error()` 方針 | `31` / `28` |
| E | 出力routing/adapter章を追加 | `31-output-routing-adapter-architecture.md` | `README` / `31` |
| F | 別repo再利用用 kit を新設・本移行 | `creator-kit/manifest.json`, `install.sh`, `uninstall.sh`, `migrate-from-project.sh`, `README.md`, kit実体 + symlink | `23` / `25` |
| G | Bash/Python統一ルールを正典化 | `creator-kit/CONVENTIONS.md` | `28` |
| H | 機械処理設定を JSON に統一し YAML依存を除去 | `manifest.json`, `adapter-registry.json`, `output-routing.json.example`, stdlib `json` 実装 | `28` / `31` |
| I | creator-kit と規約を再度 elegant-review | YAML残骸、現状違反リスト、`sys.exit(main())` 欠落を是正。`lint-forbidden-deps.py` 追加 | `28` / `25` / 本章 |
| J | 旧YAML実ファイルを削除 | `creator-kit/manifest.yaml`、governance params、rubric/proposal/4条件の内部YAMLをJSON化。GitHub Actions `.yml` と Claude frontmatter YAML は仕様例外 | `28` / `31` |

## 現在の成果物マップ

```text
xl-skills/
├── creator-kit/
│   ├── CONVENTIONS.md
│   ├── manifest.json
│   ├── README.md
│   ├── install.sh
│   ├── uninstall.sh
│   ├── migrate-from-project.sh
│   ├── config/
│   │   ├── adapter-registry.json
│   │   └── output-routing.json.example
│   └── scripts/
│       └── lint-forbidden-deps.py
├── .claude/skills/                       ← creator-kit/skills/* への symlink
│   ├── run-skill-create -> ../../creator-kit/skills/run-skill-create
│   ├── ref-output-routing -> ../../creator-kit/skills/ref-output-routing
│   └── other meta-skills -> ../../creator-kit/skills/*
├── scripts/
│   ├── adapters/
│   │   ├── resolve_route.py
│   │   ├── dispatch.py
│   │   └── sink_{local,http,notion,sheets,slack}.py
│   └── secrets/
│       ├── keychain_helper.py
│       ├── audit_secret_leak.py
│       └── README.md
└── doc/ClaudeCodeスキルの設計書/
    ├── 31-output-routing-adapter-architecture.md
    └── 32-creator-kit-implementation-ledger.md
```

`creator-kit/manifest.json` が kit 構成の正本である。上記マップは人間向けの俯瞰であり、実際の install/migrate 対象は manifest を優先する。

## 重要な設計判断

| 場面 | 採用 | 理由 | 正本 |
|---|---|---|---|
| Governance | 厳格運用ではなく solo_operator を含むハイブリッド | 1人運用でも止まらず、承認ログは残すため | `27` / `25` |
| E2E入口 | `run-skill-create` 新設 | 要望から完成までのゲート付き自動連鎖が不足していたため | `25` |
| 出力先拡張 | Port/Adapter | Skill数の M x N 爆発を避けるため | `31` |
| APIキー保護 | macOS Keychain | LLM context、repo、履歴に平文secretを載せないため | `31` |
| 別repo再利用 | `creator-kit/` | 文書ではなく仕組みとして配布するため | `23` / `25` |
| 言語規約 | Bash lifecycle + Python stdlib logic の2層 | 既存scriptを全面再実装せず、責務で混在を制御するため | `28` |
| 機械処理設定 | JSON正本 | PyYAML / yq 依存を避け、stdlib only を守るため | `28` / `31` |
| 禁止依存 | `manifest.json` に宣言し lint で検査 | 禁止リストを文書だけでなくデータにするため | `creator-kit/manifest.json` |
| manifest登録 | 登録案生成 + ユーザー承認 + apply | 自然言語依頼でも横展開対象を漏らさず、勝手な広域反映を防ぐため | `23` / `25` |

## レビュー履歴

| 周回 | 対象 | 初回判定 | 改善後 | 主な修正 |
|---|---|---|---|---|
| 1 | harness-creator 31章反映設計 | C1〜C4 一部FAIL | PASS | E2E、routing、Keychain、creator-kit を追加 |
| 2 | creator-kit + CONVENTIONS | C1〜C4 FAIL | PASS | YAML残骸除去、現状違反記述更新、`sys.exit(main())` 統一、forbidden-deps lint 追加 |

4条件の定義:

| 条件 | 本章での判定基準 |
|---|---|
| C1 矛盾なし | README、23、25、28、31、manifest の記述が相反しない |
| C2 漏れなし | Phase A-J の実施内容、成果物、残課題が追跡できる |
| C3 整合性あり | JSON正本、Keychain参照、Bash/Python 2層規約の用語が揃っている |
| C4 依存関係整合 | run/assign/ref/scripts/config の依存方向と kit 境界が崩れていない |

## 現在の判定

| 条件 | 判定 | 根拠 |
|---|---|---|
| C1 矛盾なし | PASS | YAML機械処理設定は JSON に統一。APIキー保護は Keychain 参照に統一 |
| C2 漏れなし | PASS | Phase A-J、3軸、レビュー2周、残課題を本章に集約 |
| C3 整合性あり | PASS | Bash/Python 2層、Sink Contract、manifest正本の用語を README と接続 |
| C4 依存関係整合 | 暫定PASS | manifest一致lint、禁止依存lint、secret audit は `.github/workflows/harness-creator-kit-ci.yml` でCI接続済み。ただし `migrate-from-project.sh` の本実行ログ未取得、`audit_secret_leak.py` docstring 未更新のため 25章L174「暫定PASS」制度を継承する |

GitHub Actions の workflow ファイル (`.yml`) と Claude Code の `SKILL.md` frontmatter YAML は外部仕様に従う例外である。kit内部の機械処理設定、rubric、proposal、4条件定義は JSON を正本とする。

## 残課題

| 優先 | 課題 | 完了条件 | 関連 | 検証方法 |
|---|---|---|---|---|
| P0 | `migrate-from-project.sh` 本実行 | dry-run ではなく本実行し、実行ログを `creator-kit/migrate-log/` に保存する | `25` / `creator-kit/migrate-from-project.sh` | ログファイルの存在確認 |
| P0 | `lint-forbidden-deps.py` / `audit_secret_leak.py` の CI接続確認と正式実行 | `harness-creator-kit-ci.yml` で exit 0 を確認し、CIグリーンのスクリーンショットまたはActionsログURLを記録 | `.github/workflows/harness-creator-kit-ci.yml` | `gh run list` で直近CI成功を確認 |
| P1 | `audit_secret_leak.py` docstring 微更新 | docstring の purpose・inputs・outputs を最新挙動に合わせて更新する | `creator-kit/scripts/secrets/audit_secret_leak.py` | `python3 -m py_compile` 後 docstring の内容目視確認 |
| P2 | `output-routing.json` のプロジェクト固有実設定作成 | `.claude/config/output-routing.json.example` を元に、secret本体を含まない実設定を作る | `31` | ファイル存在 + JSON parse 確認 |
| P2 | `update-yaml-spec.yml` の取得実装 | 公式frontmatter仕様の取得スクリプトを実装し、cacheを自動更新する | `ref-yaml-spec-fetcher` | スクリプト実行 + cache ファイル更新確認 |
| P2 | manifest登録案のrole自動補完改善 | `build-manifest-registration-plan.py` が新規Skillの role を TODO ではなく要約できる | `creator-kit/scripts/build-manifest-registration-plan.py` | `build-manifest-registration-plan.py` 出力の role フィールド確認 |
| P1 | script命名規約違反の段階リネーム (13件 VIOLATION + 10件 PENDING_RENAME) | `python3 scripts/lint-script-naming.py --report` の VIOLATION リスト全件を 28章 §4.1 動詞に統一。33章 P1 ワークフローに従う | `28` / `33` / `scripts/lint-script-naming.py` | lint exit 0 |
| P1 | governance-policy.json の pre-commit / CI接続 | `guard-change-category.py` 実装、`.github/workflows/governance-check.yml` 新設、blast radius lint 自動実行 | `33` / `creator-kit/config/governance-policy.json` | CIで lint-script-naming + lint-forbidden-deps が green |

## 更新ルール

1. `creator-kit/manifest.json` の skill/script/config が変わったら、本章の成果物マップと設計判断を確認する。
2. `31` の Sink Contract、Keychain方式、adapter registry が変わったら、本章の3軸と残課題を確認する。
3. `28` または `creator-kit/CONVENTIONS.md` の禁止依存が変わったら、`manifest.json` と `lint-forbidden-deps.py` を同時に更新する。
4. 新しい Skill / hook / lint / adapter / config を `creator-kit` に追加したら、`build-manifest-registration-plan.py` で登録案を出し、ユーザー承認後に `--apply` する。
5. elegant-review を再実行したら、レビュー履歴と現在の判定を更新する。
6. 本章に詳細仕様を重複記述しない。詳細が必要なら該当章または実ファイルへ委譲する。
7. 本章の C1-C4 判定は CI接続未完の項目があれば自動的に「暫定PASS」に降格する。実装者が単独で「PASS」を書き換えてはならない (自己採点回避)。
