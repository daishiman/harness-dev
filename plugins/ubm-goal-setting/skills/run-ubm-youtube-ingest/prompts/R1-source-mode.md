# プロンプト: R1-source-mode

> このファイルは 7 層プロンプトの Markdown 表現。`run-prompt-creator-7layer` の
> `seven-layer-format.md` を正本とする。Layer 番号と依存方向 (L1 ← L7) は不変。
> `run-ubm-youtube-ingest` が取込モードとソースの優先度を確定する責務プロンプト正本。

## メタ

| 項目 | 値 |
|---|---|
| name | `source-mode` |
| skill | `run-ubm-youtube-ingest` |
| responsibility | R1-source-mode (1 プロンプト = 1 責務) |
| layers_covered | [L1, L2, L3, L4, L5, L6, L7] |
| output_schema | references/registry-ledger-schema.md のソース登録簿の定義 (モード + ソースの優先度) |
| reproducible | true (モード判定と優先度の確定は決定論的) |

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール
- 目的: 引数 (`--url`/`--backfill`/`--sync`) から取込モードを確定し、2 ソースの登録簿の優先度を解決する。
- 背景: モードごとに取得範囲・完全性基準・自動性が異なるため、後続 R2-R4 の前提を最初に固定しなければ全量性も冪等性も根拠を失う。
- `required-primary`(北原孝彦のコンサルティング)は第2ソースが未同定でも独立に取込を進める (改善計画 C2 の全量必須)。

### 1.2 倫理ガード
- 秘匿情報 (API キー/トークン) を登録簿・報告・ログへ書かない。公開チャンネルの URL / 動画 ID / 区間 / グラフのハッシュ値のみを出所情報として保持する。

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (単一責務)
- 担当: モードの確定 + ソースの優先度の解決 + 登録簿のソース節の整合。
- 非担当: 取得/正規化 (R2)、抽出/グラフ (R3)、同期の冪等制御 (R4)。

### 2.2 ドメインルール
- **モード排他**: `--url URL`=単発1本 / `--backfill`=`required-primary` 全量 / `--sync`=無人差分。同時指定は不正として1つに確定させる。
- **ソースの優先度**: 提示済みチャンネルを `required-primary`・全量必須。第2アカウントは URL/handle/channel_id 未提示のため `pending-identification` で保持し、その未同定を `required-primary` 停止の理由にしない。
- **分母の起点**: `--backfill`/`--sync` は正となる動画一覧の全 ID を台帳の分母に入れる。除外による分母縮小は禁止 (完全性判定は C03 が所有)。

### 2.3 入力契約
| フィールド | 型 | 必須 | 説明 |
|---|---|---|---|
| モード引数 | enum: url/backfill/sync | はい | 取込モード |
| --url | string | いいえ | `mode=url` 時の対象動画 URL |
| --source | string | いいえ | 対象ソースのハンドル (既定=`required-primary`) |
| --source-out | path | いいえ | 正規化ソースの親ルート。未指定時は youtube-registry.json の親。YouTube/ は出力時に1回付加する |
| --dry-run | bool | いいえ | 検知/整形のみ・書込禁止 |

### 2.4 出力契約
| フィールド | 型 | 説明 |
|---|---|---|
| resolved_mode | enum | url/backfill/sync |
| target_sources | object[] | `{priority, handle, status}` の並び |
| source_out | path | --source-out または registry の親を絶対パスへ解決した値。R2-R4 へ渡す |
| project_root | path | host が示した呼び出し元プロジェクトの絶対パス。R3 の候補出力へ伝播 |
| plugin_root | path | 親スキルが解決したプラグインの絶対パス |
| dry_run | bool | 書込抑止フラグを R2-R4 へ伝播 |

## Layer 3: インフラ層 (外部依存)

### 3.1 参照リソース
| ID | パス | 読むとき |
|---|---|---|
| `registry-schema` | `${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/skills/run-ubm-youtube-ingest/references/registry-ledger-schema.md` | ソース登録簿の形と初期化手順を確認するとき |

### 3.2 外部ツール / API
- なし (引数解釈と登録簿の読取のみ。取得は R2)。

## Layer 4: 共通ポリシー層

### 4.1 共通ルールへの従属
- 信頼できない文字起こしの規範・全量性規範・出所情報の規範は SKILL.md `## 守ること` が正本。本プロンプトで再定義しない (二重定義によるずれの防止)。

### 4.2 失敗時挙動
- モードが未指定/複数指定のとき: 既定を `--sync` とせず、ユーザーへ1問で確定を促す (無人のスケジューラ経路は `--sync` を明示引数で受ける)。
- 登録簿が未存在のとき: R4 の1回きりの実行による自動初期化契約に委ね、本段階は `required-primary` + 未同定ソースの初期のソース節を宣言する。

## Layer 5: エージェント層 (ゴール駆動の実行主体)

### 5.1 担当
- `run-ubm-youtube-ingest` 本体 (サブエージェントへ分けずインライン)。

### 5.2 ゴール定義
- 目的: 後続が前提にできるモード + ソースの優先度を確定する。
- 達成ゴール: `resolved_mode` と `target_sources` が確定し、`dry_run` が伝播した状態。固定手順は書かない。

### 5.3 完了チェックリスト (停止条件)
- [ ] `resolved_mode` が `url`/`backfill`/`sync` のいずれかに確定している
- [ ] `required-primary` が `active`、第2ソースが `pending-identification` で登録簿に保持されている
- [ ] `dry_run` フラグが後続へ渡っている

### 5.4 実行方式
- 現状評価→手順を都度立案→実行→検証→全項目充足まで反復する。

## Layer 6: オーケストレーション層 (ゴールシーク制御)

### 6.1 上位スキルとの接続
- 呼び出し元: `run-ubm-youtube-ingest` の最初の段階。
- 後続ステップ: R2-fetch-normalize — 受け渡し: `resolved_mode` + `target_sources` + `source_out` + `plugin_root` + `dry_run`。

### 6.2 ハンドオフ / 並列性
- 直列: 完了チェックリスト充足後にのみ R2 へ遷移する。

## Layer 7: UI / 提示層

### 7.1 提示の判断基準
| 状況 | 提示 |
|------|------|
| モード明示 | 確定内容を1行で要約し R2 へ |
| モード未確定 | 3モードの違いを1問で確認 |

### 7.2 言語
- 本文: 日本語 (フィールド名・CLI 引数は英語のまま)。

---

## 出力指示 (LLM 実行時に読む箇所)

LLM はここから下の指示のみを実行し、Layer 1〜7 はコンテキストとして参照する。

引数から `resolved_mode` を確定し、`target_sources` に `required-primary`(`active`)と第2ソース(`pending-identification`)を並べる。`source_out` は --source-out の指定値、未指定なら youtube-registry.json の親を絶対パスへ1回解決する（YouTube/ を含めない）。親が解決した `plugin_root` と host が示す `project_root` と `source_out` と `dry_run` を伝播し、5.3 の完了チェックリストを全て満たしたら R2 へ遷移する。余計な前置きは出力しない。
