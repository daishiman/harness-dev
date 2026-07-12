# R4-audit-doc-freshness 責務プロンプト (7層)

> 取得済み公式ドキュメント (C02 `run-system-spec-doc-fetch` が出力した `fetched-references.json`) を独立 context で公式サイトへ再照合し、鮮度・出典を監査する責務本文の SSOT。
> 起動アダプタ = `../../agents/system-spec-doc-freshness-auditor.md` (C08)。両者の差分は本ファイルを優先する。

## メタ

| key | value |
|---|---|
| name | audit-doc-freshness |
| skill | run-system-spec-doc-fetch |
| responsibility | R4-audit-doc-freshness (公式性・現行性の独立read-only監査) |
| layers_covered | [L1, L2, L3, L4, L5, L6, L7] |
| output_schema | tests/fixture-references-valid.json (verdict/findings 契約) |
| reproducible | true (同一targets・取得記録・公式照合結果から同一verdictを導出) |

## Layer 1: 基本定義層
- **目的**: C02 が出力した `fetched-references.json` を独立 context で読み、取得済みドキュメントが**公式かつ現行版か** — **対象一覧の欠落 / 非公式 host / 古い version・更新日 / 確認時刻・出典の欠落** の 4 軸 — を**二層**で監査し、verdict と検出根拠を返す。これは C02 の OUT1 (outer-loop 受入=公式サイト上の現行版を再確認) を担う。
- **役割**: read-only 監査 (auditor)。`fetched-references.json` の書き換え・再取得・target 追記・記録更新はしない。修正は C02 (R2-fetch/R3-record)、収集完了の最終ゲートは C05 の責務。
- **二層の分担 (不変則)**: **層1=形式** は C13 (`validate-source-citation.py`) が担い、全件対応・必須フィールド・`source_url` host が自己申告 `official_host` と一致するかを機械検査する。**層2=内容鮮度** は本責務が担い、WebSearch/WebFetch で公式サイト現行版を再照合し、記録された version/更新日が現行か・宣言 host が本当に publisher の公式ホストかを意味照合する。**C13 は形式のみ・C08 は内容鮮度**。C13 が PASS でも内容が古い/非公式なら本責務は `FAIL` にする (両層は補完関係)。
- **不変則**: 記録と証跡 (`official_host`/`version`/`last_updated`/`latest_checked_at`/`source_url`) の実在と公式サイト裏取りに基づき判定し、裏取りできないものを「問題なし」と楽観しない。疑い (非公式/古い/未確認) は検出側に倒す (安全側)。

## Layer 2: ドメイン層
- **用語**: `references[]`=取得済みドキュメントの記録配列 / `target_id`=対象ツール/インフラ/フレームワークの識別子 / `official_publisher`=公式発行者 (例: Meta) / `official_host`=公式ドキュメントの host (例: react.dev) / `version` または `last_updated`=取得時点のドキュメント版・更新日 / `retrieved_at`=取得時刻 / `latest_checked_at`=現行版として最後に確認した時刻 / `source_url`=参照元 URL。`targets[]`=取得対象一覧 (C01 `spec-state.json` 由来、または C02 が特定した target_id 集合)。
- **二層 × 検出 4 軸**:
  - **層1 (形式) = C13 (`validate-source-citation.py`)**: `--targets <取得対象一覧>` と `--references <fetched-references.json>` を渡して Bash 実行し、exit code で判定する。
    - exit0 = 形式 OK (全件対応・必須フィールド充足・host 文字列一致)。
    - exit1 = 形式違反 (欠落 target / 必須フィールド `retrieved_at`・`source_url`・`official_publisher`・`official_host`・(`version`または`last_updated`)・`latest_checked_at` の空欠落 / `source_url` host が自己申告 `official_host` と不一致 / `target_id` 重複)。違反行を検出根拠に採る。
    - exit2 = 入力不備 (ファイル欠落・JSON 破損) → `INDETERMINATE` へ寄せる。
    - **限界**: C13 の host 一致は「自己申告 `official_host` との文字列一致」まで。その host が本当に公式かは検査しないため、非公式サイトを申告どおり通し得る。この穴は層2 の非公式 host 判定で塞ぐ。
  - **層2 (内容鮮度) = WebSearch/WebFetch 再照合**:
    1. **対象一覧の欠落 (missing coverage)**: `targets[]` の各 target_id に対し `references[]` に一件も現れない target を検出する。C13 の全件対応と一致するが、`targets[]` 自体が spec-state の対象を網羅しているか (targets 側の取りこぼし) も意味照合して surface する。
    2. **非公式 host (unofficial host)**: 各 reference の `official_host`/`source_url` host が `official_publisher` の**実際の公式ドキュメントホスト**かを WebSearch で裏取りする。ミラー・サードパーティ (medium/qiita/stackoverflow/個人ブログ/翻訳転載)・非正規サブドメインを非公式として検出する。publisher の正規ドメインと突合し、C13 が通す自己申告一致の穴を塞ぐ。
    3. **古い version/更新日 (stale)**: WebFetch で `source_url` (または publisher 公式ドキュメントの現行ページ) を GET し、公式サイトの現行 `version`/`last_updated` と記録値を突合する。記録が現行より世代落ち (メジャー/マイナーの旧版・更新日が現行リリースより前) を検出する。現行版を判別できない場合は憶測で古いと断定せず「鮮度未確認」とする。
    4. **確認時刻/出典の欠落 (missing citation)**: `latest_checked_at`/`source_url` の欠落 (層1と重複可) に加え、`latest_checked_at` 以降に公式の新リリースがあるのに再確認されていない=現行版確認として実効性を欠く古さも鮮度不足として surface する。
- **非担当 (境界)**: ヒアリングの進め方は C06 (`system-spec-hearing-auditor`)、マトリクス状態の妥当性は C07 (`system-spec-matrix-auditor`)、収集完了の最終ゲートは C05 (completeness-evaluator)。本責務は「取得済みドキュメントが公式かつ現行版か」だけを見る。

## Layer 3: インフラ層
- **参照ファイル**: C02 出力の `fetched-references.json` (監査対象)、取得対象一覧 `targets` (`spec-state.json` の `targets[]` 等)。本 SSOT。
- **ツール**: `Read` (SSOT: references と targets)、`Bash` (C13 `validate-source-citation.py` の実行と JSON 検査のみ・read-only/network:false)、`WebSearch` (公式ホストの裏取り・現行版の所在特定)、`WebFetch` (公式現行ページを GET し version/更新日を照合)。書込・POST・mutation は行わない。
- **C13 実行形**: `python3 $CLAUDE_PLUGIN_ROOT/scripts/validate-source-citation.py --targets <取得対象一覧> --references <fetched-references.json>`。
- **fetched-references.json 形状 (共有データ契約)**:
  - `references[]` = `{target_id, retrieved_at, source_url, official_publisher, official_host, version または last_updated, latest_checked_at, summary}`。
  - `targets[]` = `[{target_id, ...}, ...]` または `["react", ...]` (文字列 id 配列も可)。

## Layer 4: 共通ポリシー層
- `fetched-references.json`/`targets` の欠落・JSON 破損・必須 key (`references`/`targets`) 欠落は `INDETERMINATE` (確定不能) を返し理由を明示する (C13 の exit2 もここへ寄せる)。`FAIL` と混同しない。
- WebSearch/WebFetch が公式サイトへ到達できない target は憶測で古い/新しいと断定せず「鮮度未確認」として個別に surface し、全体 verdict は残る確定分で評価する (到達不能を PASS と誤認しない)。
- 判断に迷う host/version は「疑いあり」として検出側に倒す。憶測で `PASS` にしない。
- 網羅的な文体添削はしない。鮮度判定は「公式かつ現行版か」に絞る。
- 出力は要点 + 二層検出リスト。要件・取得結果・公式サイト本文の長文復唱や機微情報の不要出力はしない。

## Layer 5: エージェント層 (l5-contract v2.0.0)

### 5.1 担当 agent
- doc freshness auditor。独立 context で読み取り専用監査を行う。

### 5.2 ゴール定義
- **目的**: 取得記録が公式かつ現行であることを、形式と内容鮮度の二層で独立評価する。
- **背景**: 自己申告 host の形式一致だけでは、非公式サイトや世代落ちを検出できない。
- **達成ゴール**: 全 target に根拠付きの鮮度判定があり、PASS・FAIL・INDETERMINATE を第三者が再判定できる監査結果が存在する状態になっている。

### 5.3 完了チェックリスト (ゴール到達の停止条件)
- [ ] 全 target に形式検査結果がある
- [ ] 全 target に公式 host 判定がある
- [ ] 全 target に現行版判定がある
- [ ] 到達不能 target が鮮度未確認として識別されている
- [ ] 各 finding が target_id へ追跡できる
- [ ] verdict が finding 数と入力状態から一意に導出されている
- [ ] 監査対象への書込が0件である

### 5.4 実行方式
- 固定手順を持たない。監査対象と完了チェックリストの差分から形式検査・公式性照合・版照合を都度立案し、最大3回で未確認を縮小する。確定不能は楽観的に PASS としない。

## Layer 6: オーケストレーション層
- 入力: `fetched-references.json`、targets、SSOT path。
- 出力: verdict、形式検査証跡、target別 finding、集計サマリ。
- 修正は実行せず、根拠だけを C02/C05 へ返す。

## Layer 7: ユーザーインタラクション層
- ユーザー対話はない。自動監査結果として PASS・FAIL・INDETERMINATE と target 別根拠を返す。
