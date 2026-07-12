# Republish Contract — run-notion-intake-publish

## 入力前提 (precondition)

呼び出し元 (人間 or 上位 skill) は次を満たした状態で本 skill を起動する。

| 前提 | 検査方法 | 不成立時 |
|---|---|---|
| `output/<hint>/intake.json` 存在 | `test -f` | exit 2 (hard-fail) |
| `output/<hint>/notion-manifest.json` 存在 | `test -f` | exit 2 |
| Keychain にトークン登録済み | `validate-notion-ready.py --check-api` | exit 44 (Keychain セットアップ案内。Secret-Out-of-Repo 違反防止) |
| Notion DB スキーマ整合 | `verify_notion_schema.py --on-conflict skip-warn` | exit 1 (skip) or 2 (fail) |
| アセット (PNG/SVG) 全数揃い | `verify_notion_assets.py` (All-or-Nothing) | exit 2 |

## exit code 規約

| code | 意味 | 呼び出し元の期待挙動 |
|---|---|---|
| 0 | publish 成功 | `notion-url.txt` を読み次工程へ |
| 1 | safe-skip (schema 差分など軽微) | warn ログ残し、人間に判断委譲 |
| 2 | hard-fail | 即停止。retry せず原因解析 |
| 51 | target 解決不能 / page_id mismatch | 即停止。再公開なら `--page-id`/`--page-url` を付すか orphan を解消、初回なら `intake.json` の `notion_target` を整えてから再実行 |

> exit 51 は初回 / 再公開の両経路で発火する。再公開 (`--revise` = update 専用) では
> update 先 `page_id` を `--page-id` / `--page-url` / 既存 `notion-publish-result.json` の
> いずれからも解決できない、または既存 result の `page_id` が要求値と食い違う (orphan 化)
> 場合に発火する。初回経路でも `intake.json` の `notion_target` が不備
> (`mode=create-explicit` かつ `allow_create=true` でない) なら stage=`target_resolution`
> の exit 51 で fail-closed する。いずれも新規ページ量産・別ページ上書きを publish 前に
> 構造的に封鎖するための契約。

## 不変条件 (invariants)

1. 本 skill 内で `intake.json` を **書き換えない**。読み取り専用。
2. publish 順序は必ず `render → quality_gate → publish`。pipeline 内で固定済み。
3. トークンを環境変数や CLI 引数に **載せない**。Keychain helper 経由のみ。
4. 失敗時も `notion-log.json` は書き出す (silent-fail 禁止)。`notion-url.txt` は
   成功 URL 確定時のみ書く (失敗時の空ファイル残置は初回翻訳ゲートを恒久 False 化し
   retry デッドエンドになるため。再実行での自動回復性を優先)。

## 再公開拒否ルール

Notion API は冪等な page update を提供する一方、誤った状態での再公開は外部リンク
破壊・差分逆流・rate-limit 違反を引き起こす。本 skill は以下 3 条件のいずれかに
該当した場合、publish に進まず即停止する (再公開は update 専用: `page_id` 不変前提)。

- `fidelity-guard verdict != pass` → exit 2 (canonical-page-snapshot 更新後に
  構造粒度ガードが未通過なら view を上書きすると canonical との差分が逆流するため、
  hard-fail で再ヒアリングを促す)
- `intake.json.updated_at < notion-manifest.json.updated_at` → exit 2
  (manifest が intake より新しい状態は手動編集または前回 publish 中断の痕跡で、
  そのまま update すると古い canonical を Notion へ再書込みするため hard-fail)
  **[未発効・manual]** 本条件は pipeline に未実装で、現状は実行者による手動検査。
  機械化するまで exit 2 の自動発火は保証されない。
- `now - notion-publish-result.json.published_at < 60s` → exit 1
  (前回 publish から 60 秒未満の連続起動は Notion API rate-limit / 二重発火事故の
  典型パターン。safe-skip で warn ログのみ残し、人間判断に委ねる)
  **[未発効・manual]** 本条件も pipeline に未実装 (同上)。実装時に exit 規約へ昇格する。

## 不変条件の補足: 冪等性と page_id

1. 本 skill は初回 / 再公開の両方を扱う (初回 publish も workflow-manifest P10 が
   本 skill へ委譲)。初回 (成功痕跡なし) は `intake.json` の `notion_target`
   (`mode=create-explicit` かつ `allow_create=true`) を pipeline が `--allow-create` へ
   翻訳したときだけ create を許可する。再公開は `--revise` の update 専用で、
   `page_id` 源は `--page-id` / `--page-url` / 既存 `notion-publish-result.json` の
   優先順に解決する (いずれも無ければ exit 51)。
2. `page_id` は canonical key であり、再公開で変えてはならない。変えた場合は
   外部参照リンクが全て無効化されるため exit 2。
3. 同一 intake/manifest での再起動は **冪等** であること (Notion 側 page の内容が
   等価収束する)。pipeline 内 render 出力がバイト一致しない場合でも、ブロック構造の
   論理等価性が保たれていれば合格とする。
