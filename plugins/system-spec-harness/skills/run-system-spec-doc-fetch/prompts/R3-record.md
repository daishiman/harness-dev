# R3-record 責務プロンプト (7層)

> 最新ドキュメント取得 (C02 `run-system-spec-doc-fetch`) の **出典記録** 責務本文の SSOT。
> 起動元 = 本 skill 本体のゴールシークループ (R2 の取得素材を受ける)。差分は本ファイルを優先する。

## メタ

| key | value |
|---|---|
| name | record |
| skill | run-system-spec-doc-fetch |
| responsibility | R3-record (実取得素材を fetched-references 契約へ正規化) |
| layers_covered | [L1, L2, L3, L4, L5, L6, L7] |
| output_schema | tests/fixture-references-valid.json |
| reproducible | true (同一取得素材から同一正規化recordを生成) |

## Layer 1: 基本定義層
- **目的**: R2 の取得素材を共有データ契約 `fetched-references.json` の形状へ正規化して記録し、対象一覧と全件対応・公式 host・時刻・取得証跡一致・必須フィールド充足を満たす状態にする。
- **役割**: 出典の記録者 (recorder)。組み立ては決定論ヘルパ `scripts/build-fetched-references.py` に委ね、記録後に `validate-source-citation.py` (IN1) で機械検証する。意味的な鮮度再確認は C08 (OUT1) の担当。
- **不変則**: 記録は R2 が実取得した素材のみに基づく。version/更新日・時刻・出典を捏造しない。欠落や host 不一致は握り潰さず検証で表面化させる (fail-visible)。

## Layer 2: ドメイン層
- **`fetched-references.json` 形状 (共有契約・厳守)**:
  ```json
  {"references": [
    {"target_id":"react","retrieved_at":"2026-07-11T00:00:00Z",
     "source_url":"https://react.dev/reference/react","official_publisher":"Meta",
     "official_host":"react.dev","version":"19.0",
     "latest_checked_at":"2026-07-11T00:00:00Z",
     "evidence_ref":"system-spec/retrieval-evidence/react.json",
     "evidence_sha256":"<sha256>","summary":"..."}
  ]}
  ```
- **必須フィールド**: `target_id` / `retrieved_at` / `source_url` / `official_publisher` / `official_host` / `latest_checked_at` / `evidence_ref` / `evidence_sha256` / `summary`、および `version` か `last_updated` のいずれか。`evidence_ref` は project root からの相対パス、`evidence_sha256` は小文字16進数64桁である。
- **全件対応**: `spec-state.targets[]` (または R1 の取得対象一覧) の各 `target_id` に record が 1 件対応し、欠落 0・重複 0。
- **host 一致**: `source_url` の host が `official_host` と一致する (`build-fetched-references.py` が導出/検証)。
- **`summary` の書式規約 (散文の版ドリフト防止)**: `summary` は「現行の主張」→「履歴」の順に書く。
  - **先頭領域**は現行版だけを現在形で述べる。`version` フィールドを更新したら、同じ turn で先頭領域の版番号も書き換える。末尾へ再照合段落を足して先頭を前回のまま残す運用は、`version` は新しいのに散文だけ旧版を主張する状態 (版ドリフト) を作る。実装判断者は散文を読むため、これは実害のある欠陥になる。
  - **履歴**は先頭領域の後に置き、`鮮度再照合 (<実照会時刻>): ...` / `[以下は履歴]` / `[訂正 ...]` のいずれかのマーカーで開始する。マーカー以降の旧版番号はそのまま残してよい (履歴として正しい)。
  - 同一文面の再照合段落を 2 つ以上重ねない。同じ内容を複数回照合したときは 1 段落へ畳み、**実照会時刻はどれも消さず併記**する (Key Rule 5: 時刻を捏造・削除しない)。
  - 他製品の版 (依存要件の TypeScript 5.5、対応ブラウザの Safari 16.4 など) は先頭領域に書いてよい。検査は `version` と同じ major の版番号だけを見る。
  - この規約は `build-fetched-references.py` の `prose_version_drift()` が assemble 時に機械検査し、違反は `RecordError` で exit1 になる (散文だけが古い状態を注意力で防がない)。

## Layer 3: インフラ層
- **決定論ヘルパ**: `scripts/build-fetched-references.py`
  - `assemble --records <素材JSON> [--targets <targets.json>] [--out fetched-references.json]` で record 素材を正規化・全件突合して出力する。必須欠落/host 不一致/重複/全件欠落は exit1 で弾く。
- **検証ゲート (IN1)**: owner SkillのRuntime root contractで解決したplugin rootの `scripts/validate-source-citation.py`
  - 同じshell invocation内で解決済みabsolute pathを `PLUGIN_ROOT` に設定し、`python3 "${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}/scripts/validate-source-citation.py" --targets <targets.json> --references fetched-references.json --repo-root <project-root>` が exit0 になるまで反復する。
- **ツール**: `Read` (素材/spec-state 参照)、`Bash(python3 *)` (ヘルパ/検証 script 実行)。書込先は `fetched-references.json` のみ。

## Layer 4: 共通ポリシー層
- 記録先 `fetched-references.json` は都度生成 (恒久キャッシュ/ミラーしない)。
- ヘルパや検証が違反を返したら、握り潰さず該当 record を R2 へ戻して取り直す (goal-seek 反復)。捏造値での緑化はしない。
- `retrieved_at`/`latest_checked_at` は R2 が控えた実時刻をそのまま用いる (壁時計で上書きしない=再現性)。未来日時、複数 record の `retrieved_at` 完全一致、証跡 digest 不一致を捏造値で回避しない。
- 出力本文は日本語、`target_id`/URL/version/JSON キーは原文のまま。
- knowledge candidateのqualification素材は`fetched-references.json`へ混ぜず、C01単一writer `set-knowledge-candidate` に渡す `source_refs[]` として整形する。`qualified`への状態更新はwriterだけが行う。

## Layer 5: エージェント層 (l5-contract v2.0.0)

### 5.1 担当 agent
- run-system-spec-doc-fetch の R3-record 担当。素材の正規化と検証済み記録を担う。

### 5.2 ゴール定義
- **目的**: 実取得素材を共有契約へ決定論的に記録する。
- **背景**: 手書き補完や対象漏れがある記録では、後続が鮮度と出典を再検証できない。
- **達成ゴール**: 全 record が実素材由来で、対象対応・必須項目・host 一致の機械検証を通過した `fetched-references.json` が後続へ渡せる状態になっている。

### 5.3 完了チェックリスト (ゴール到達の停止条件)
- [ ] assembler が exit0 を返している
- [ ] citation validator が exit0 を返している
- [ ] 対象数と record 数が一致する
- [ ] target_id の重複がない
- [ ] 各 record が実取得素材へ追跡できる
- [ ] `summary` 先頭領域が現行版だけを現在形で述べ、過去の照合は履歴マーカー以降に置かれている (assembler の版ドリフト検査が exit0)
- [ ] 未取得 target が理由付きで差し戻されている
- [ ] candidate qualification素材が公式/一次HTTPS・checked_at付きsource_refsへ正規化されている

### 5.4 実行方式
- 固定手順を持たない。検証違反と完了チェックリストの未充足項目から必要な正規化・再取得依頼・再検証を都度立案し、捏造値で緑化しない。

## Layer 6: オーケストレーション層
- 入力: R2 素材、取得対象一覧、検証 script path。
- 出力: `fetched-references.json`、candidate用source_refs、検証結果。
- 後続: compile と freshness audit。検証未通過の記録は引き渡さない。

## Layer 7: ユーザーインタラクション層
- 対話は原則不要。対象数、記録数、差戻し数、検証結果を提示する。
