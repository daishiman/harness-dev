# notion-submit-improvement.py 実行契約 (実装照合版)

本文 (SKILL.md) の要約に対する詳細。**`scripts/notion-submit-improvement.py` と
`plugins/harness-creator/scripts/notion_config.py` の実装を正とし、乖離を見つけたら
本ファイルを先に直してから SKILL.md 本文を同期する。**

## 1. 解決順 (実装準拠)

| 対象 | 実際の解決順 | 実装 |
|---|---|---|
| token | **Keychain が既定**。`security find-generic-password -s <keychain_service> [-a <keychain_account>] -w`。env `NOTION_TOKEN` は **`INTAKE_ALLOW_ENV_TOKEN=1` を明示した時だけ**先行採用される | `notion_config.get_token()` |
| DB ID | env (`skill-list`→`NOTION_DB_SKILL_LIST` / `improvement-request`→`NOTION_DB_IMPROVEMENT_REQUEST`) → `.notion-config.json` の `databases.<key>.db_id` | `notion_config.get_db_id()` |
| config path | env `NOTION_CONFIG_PATH` → repo-root → plugin-root (`.notion-config.json` / 焼き込み `notion-config.fixed.json`) | `notion_config.find_config_path()` |

**CLI 引数で token / DB ID を渡す経路は存在しない** (`argparse` に該当オプションが無い)。
「CLI > env > config > Keychain」と書くと実装に無い経路を案内することになるので禁止。

上表の解決順は散文の宣言ではなく `lint-feedback-protocol.py` R8 (5) が `get_token` / `get_db_id` を
**実際に呼んで返り値で** pin している。順序を入れ替えたら lint が落ちるので、実装を変えるならここも同時に直す。

### token の受け渡し (curl への transport)

`curl()` は token を **argv にも一時ファイルにも置かず**、`--config -` で stdin から渡す
(`header = "Authorization: Bearer <token>"` を書き込む。curl config 構文に合わせ `"` と `\` を escape)。

argv に置いてはいけない理由は ps 可視性だけではない — **`CalledProcessError.__str__()` は cmd 全体を含む**ため、
`except ... as e: print(f"...{e}")` が一箇所あるだけで token が stdout へ出る。stdout は Claude が
`[CREATED]` 判定のために読む経路そのもので、IN2 が名指しで禁じている露出先に一致する。
実際にこの経路を踏んだため、print 側ではなく **argv に載せない側**を根治とした
(出力側を塞ぐ方針は列挙漏れが避けられない)。R8 (3) がこの再発を機械で止める。

## 2. fail-closed / fail-open の実際

- `require_or_skip(key, allow_skip=False)` の既定は **fail-closed**: config 不在 /
  token 取得不可 / `databases.<key>.db_id` 不在のいずれかで stderr に FATAL を出して
  `sys.exit(2)`。**skip はしない。**
- `notion-submit-improvement.py` は `allow_skip` を渡さない (`require_or_skip("improvement-request")`)
  ので、その直後の `if not cfg: return 0` は到達しない防御コード。
- ただし **`skill-list` の db_id だけは `require_or_skip` の検査対象外**で、
  欠けていると `[SKIP] skill-list / improvement-request db_id missing` を出して
  **exit 0 で終わる** (投入も存在確認もされないまま成功扱い)。要望が Notion に
  入っていないのに緑を見る唯一の経路なので、完了通知は必ず標準出力の
  `[CREATED]` 行の有無で判定する。

## 3. `--dry-run` の実際の意味

```python
if args.dry_run:
    print(json.dumps(vars(args), ensure_ascii=False, indent=2)); return
```

**引数を JSON で印字して即 return するだけで、Notion へは一切アクセスしない。**
`find_plugin_page()` は非 dry-run 経路 (`require_or_skip` の後) からしか呼ばれない。
したがって `--dry-run` は「スキル一覧 DB への登録確認」には**使えない** (未登録でも必ず成功する)。

存在確認の実体は本投入の途中にある:

1. `find_plugin_page(skill_list_db, plugin, token)` で `プラグイン名` title 完全一致を query
2. 見つからなければ `[ERR] スキル一覧に '<plugin>' が存在しません` を出して `sys.exit(2)`
3. **改善要望ページの作成 (`POST /v1/pages`) はこの後**なので、未登録時にレコードは作られない

**「未登録」と「API に届いていない」を混ぜない**: query が HTTP 300 以上 (401/403/5xx) を返した場合や
curl 自体が失敗した場合は `NotionApiError` として **exit 3** で止まる。以前はこれを `None` に潰していたため
token 失効でも「未登録」と表示され、解決策にならない `--notion-register` へ誘導していた。
exit 3 を見たら確認するのは token の有効期限・integration の DB 共有・ネットワークであって、登録操作ではない。

孤児レコードが生成されないのは「事前 dry-run で止めるから」ではなく
「本投入が relation 解決に失敗した時点で、ページ作成前に fail-closed するから」。
`--dry-run` は投入前に引数の型・必須項目を目視確認する用途に留める。

## 4. 終了コードと出力

| 状況 | 出力 | exit |
|---|---|---|
| 成功 | `[CREATED] 改善要望: '<title>' -> <page_id>` + `対象プラグイン: ...` | 0 |
| config/token/improvement-request db 不在 | stderr `[notion_config] FATAL: ...` | 2 |
| skill-list db_id 不在 | `[SKIP] skill-list / improvement-request db_id missing ...` | **0 (fail-open)** |
| プラグイン未登録 | `[ERR] スキル一覧に '<plugin>' が存在しません` | 2 |
| skill-list query が HTTP 300+ (401/403/5xx) | `[ERR] スキル一覧 DB へ問い合わせできません: skill-list query が HTTP <code>: ...` | **3** |
| curl 自体の失敗 (ネットワーク/実行環境) | `[ERR] スキル一覧 DB へ問い合わせできません: curl 失敗 ...` | **3** |
| 改善要望ページ作成が HTTP 300+ | `[ERR] 改善要望ページを作成できません: create が HTTP <code>: ...` | **3** |
| 改善要望ページ作成の curl 失敗 | `[ERR] 改善要望ページを作成できません: curl 失敗 ...` | **3** |

exit 2 と exit 3 の切り分けは **query か create か**ではなく**原因が誰の手元にあるか**で引く —
exit 2 = 入力が Notion 側の実体と噛み合っていない (未登録・config 不在) ので**利用者が直せる**、
exit 3 = API へ到達できない/認可されない (token 失効・共有漏れ・5xx・ネットワーク) ので**登録操作では直らない**。
create の失敗を exit 2 に残すと、後者を前者と読み違えて `--notion-register` へ誘導する退行が復活する。

script は **URL ではなく page id を印字する**。利用者へ提示する URL は
`https://www.notion.so/<page_id からハイフンを除いた32桁>` で組み立てる。
