# Prompt: R1-source-mode

> このファイルは 7 層プロンプトの Markdown 表現。`run-prompt-creator-7layer` の
> seven-layer-format.md を正本とする。Layer 番号と依存方向 (L1 ← L7) は不変。
> `run-ubm-youtube-ingest` が取込モードと source priority を確定する責務プロンプト正本。

## メタ

| key | value |
|---|---|
| name | source-mode |
| skill | run-ubm-youtube-ingest |
| responsibility | R1-source-mode (1 prompt = 1 責務) |
| layers_covered | [L1, L2, L3, L4, L5, L6, L7] |
| output_schema | references/registry-ledger-schema.md の source registry 定義 (mode + source priority) |
| reproducible | true (モード判定と priority 確定は決定論的) |

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール
- 目的: 引数 (`--url`/`--backfill`/`--sync`) から取込モードを確定し、2-source registry の priority を解決する。
- 背景: モードごとに取得範囲・完全性基準・自動性が異なるため、後続 R2-R4 の前提を最初に固定しなければ全量性も冪等性も根拠を失う。
- required-primary(北原孝彦のコンサルティング)は第2source が pending でも独立に取込を進める (改善計画 C2 の全量必須)。

### 1.2 倫理ガード
- 秘匿情報 (API キー/トークン) を registry・report・ログへ書かない。公開 channel URL / video ID / span / graph hash のみ provenance として保持する。

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (Single Responsibility)
- 担当: mode 確定 + source priority 解決 + registry の source 節整合。
- 非担当: 取得/正規化 (R2)、抽出/graph (R3)、sync 冪等制御 (R4)。

### 2.2 ドメインルール
- **モード排他**: `--url URL`=単発1本 / `--backfill`=required-primary 全量 / `--sync`=無人差分。同時指定は不正として1つに確定させる。
- **source priority**: 提示済み channel を `required-primary`・全量必須。第2アカウントは URL/handle/channel_id 未提示のため `pending-identification` で保持し、その未同定を required-primary 停止の理由にしない。
- **分母の起点**: `--backfill`/`--sync` は authoritative inventory 全 ID を ledger 分母に入れる。除外による分母縮小は禁止 (完全性判定は C03 が所有)。

### 2.3 入力契約
| field | type | required | 説明 |
|---|---|---|---|
| mode 引数 | enum: url/backfill/sync | yes | 取込モード |
| --url | string | no | mode=url 時の対象動画 URL |
| --source | string | no | 対象 source handle (既定=required-primary) |
| --dry-run | bool | no | 検知/整形のみ・書込禁止 |

### 2.4 出力契約
| フィールド | 型 | 説明 |
|---|---|---|
| resolved_mode | enum | url/backfill/sync |
| target_sources | object[] | {priority, handle, status} の並び |
| dry_run | bool | 書込抑止フラグを R2-R4 へ伝播 |

## Layer 3: インフラ層 (外部依存)

### 3.1 参照リソース
| id | path | when_to_read |
|---|---|---|
| registry-schema | `$CLAUDE_PLUGIN_ROOT/skills/run-ubm-youtube-ingest/references/registry-ledger-schema.md` | source registry の形と初期化手順を確認するとき |

### 3.2 外部ツール / API
- なし (引数解釈と registry 読取のみ。取得は R2)。

## Layer 4: 共通ポリシー層

### 4.1 共通ルールへの従属
- untrusted transcript 規範・全量性規範・provenance 規範は SKILL.md `## Key Rules` が正本。本プロンプトで再定義しない (二重定義 drift 防止)。

### 4.2 失敗時挙動
- モードが未指定/複数指定のとき: 既定を `--sync` とせず、ユーザーへ1問で確定を促す (無人 scheduler 経路は `--sync` を明示引数で受ける)。
- registry が未存在のとき: R4 one-shot の自動初期化契約に委ね、本 phase は required-primary + pending の初期 source 節を宣言する。

## Layer 5: エージェント層 (ゴール駆動の実行主体)

### 5.1 担当
- `run-ubm-youtube-ingest` 本体 (fork せずインライン)。

### 5.2 ゴール定義
- 目的: 後続が前提にできる mode + source priority を確定する。
- 達成ゴール: resolved_mode と target_sources が確定し、dry_run が伝播した状態。固定手順は書かない。

### 5.3 完了チェックリスト (停止条件)
- [ ] resolved_mode が url/backfill/sync のいずれかに確定している
- [ ] required-primary が active、第2source が pending-identification で registry に保持されている
- [ ] dry_run フラグが後続へ渡っている

### 5.4 実行方式
- 現状評価→手順を都度立案→実行→検証→全項目充足まで反復する。

## Layer 6: オーケストレーション層 (ゴールシーク制御)

### 6.1 上位 skill との接続
- 呼び出し元: `run-ubm-youtube-ingest` の最初の phase。
- 後続 Step: R2-fetch-normalize — 受け渡し: resolved_mode + target_sources + dry_run。

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

引数から resolved_mode を確定し、target_sources に required-primary(active)と第2source(pending-identification)を並べる。dry_run を伝播し、5.3 の完了チェックリストを全て満たしたら R2 へ遷移する。余計な前置きは出力しない。
