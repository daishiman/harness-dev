# マネーフォワード掛け払い 請求書発行チェック

請求データをマネーフォワード掛け払い (MF KESSAI) API で確認し、**前月取引分**と**今月取引分**を月次でチェックして Notion で管理するためのプラグイン。

このドキュメントは「**プラグインをインストールし、API キー・Notion トークンを macOS Keychain に登録して月次チェックを回せる状態にする**」までのセットアップ手順です（インストール → 必要な鍵の一覧 → Step 1〜4 の順）。判定ロジック・Notion 出力・参照専用ガード・二段確認 subagent は実装済みです (下記「構成」参照)。

> **「6月分の請求書」の定義**: 請求確認シート基準の照合 (`/run-mf-invoice-reconcile`) では、月帰属は発行日ではなく **取引日** です。6月分は取引日 `2026-06-30` の請求で、発行日が翌月月初 (例: `2026-07-01`) でも 6月分として拾います。API 取得は `issue_date` を対象月初〜翌月末へ広げ、最後に `/transactions` の `date` で対象月だけに絞ります。

> **チームメンバーがやることは「インストール → 自分の API キー/Notion トークンを Keychain に登録 → 疎通確認」の3点だけ**です。それ以外（差集合判定・Notion 投入・年払い抑制）は自動で動きます。`初回契約月` の一括エンリッチ（別製品の OAuth 連携）は**取得担当 1 名だけ**の任意作業で、一般メンバーには不要です（→「初回契約月の埋め方」「付録」参照）。

---

## できること

- API キーを Keychain から安全に取得 (`lib/mfk_keychain.py`)
- MF 掛け払い API v2 への読み取り (GET) 呼び出し (`lib/mfk_api.py`)
- 疎通確認 (`--smoke`) と任意エンドポイントの取得
- 前月取引−今月取引の差集合で**発行漏れ候補**を検出 (`lib/mfk_invoice_diff.py`)
- 結果を Notion DB『請求書チェック_DB』へ**顧客ID単独キーで冪等 upsert** (1 顧客=1 ページ・既存顧客は同じページを更新し、未登録顧客だけ新規ページを作成。月ごとの重複ページは作らない)(`lib/notion_invoice_sink.py`)
- 月次履歴は各顧客ページ**本文の table block** (対象年月/今月の発行状況/前月金額/今月金額/確認済み日時) に 1 行=1 対象年月で蓄積。同月再実行は行更新で冪等
- 過去月の履歴 backfill を `--backfill --from YYYY-MM --to YYYY-MM` でサポート (両端含む・月昇順、既定では未検証の発行漏れ候補を投入しない)

秘匿情報 (API キー本体) は **Keychain にのみ保存**し、git にもチャット履歴にも残しません。
**Notion DB は配布既定に焼き込み済み**で、導入者は ID 設定不要です (下記 Step 2)。

---

## インストール

このプラグインは **Claude Code のプラグイン**です。チームメンバーは以下のいずれかで導入します。

> **前提**: macOS（API キーを Keychain に保存するため）/ Python 3.11+。Windows/Linux のみの環境は未対応です。

### A. Claude Code（CLI / ターミナル）でインストール

Claude Code の**チャット欄**に、以下を**一行ずつ**入力・実行します（ターミナルではなくチャットです）。

```
/plugin marketplace add https://github.com/OWNER/harness
```

Claude Code を再起動してから:

```
/plugin install mf-kessai-invoice-check@harness
```

**✅ 完了確認**: チャットで `/plugin` と入力したとき、一覧に `mf-kessai-invoice-check` が `enabled` で表示されれば成功です。

> ⚠️ URL の後ろに余分な文字や日本語が入るとエラーになります。上の URL だけをそのままコピーしてください。
> 更新は `/plugin update mf-kessai-invoice-check@harness`、無効化は `/plugin disable mf-kessai-invoice-check@harness`。

### B. Claude Desktop アプリでインストール

Claude Desktop でも**同じスラッシュコマンド**が使えます。アプリのチャット欄に、上の A と同じ 2 行（`/plugin marketplace add …` → 再起動 → `/plugin install mf-kessai-invoice-check@harness`）を入力します。インストール後は `/run-mf-invoice-check` などのコマンドが Desktop のチャットでもそのまま使えます。

> マーケットプレースを一度追加すれば、以後は `/plugin install …@harness` だけで他の harness プラグインも入れられます。

### C. ローカル開発（このリポジトリを直接使う）

リポジトリを clone し、`plugins/mf-kessai-invoice-check/` をプラグインとして読み込みます。スクリプトのパスは `$CLAUDE_PLUGIN_ROOT` で解決されるため install 位置に依存しません。

> インストール後にやることは **この後の「必要な API キー・トークン」→ Step 1〜4** だけです。

---

## 必要な API キー・トークン（一覧）

インストール後、各自で以下を **macOS Keychain** に登録します。**生値は Keychain にのみ保存**し、git・チャットには残しません。設定方法の詳細は後続の Step 1（MF 掛け払い）と「Notion セットアップ」を参照してください。

| 用途 | Keychain service / account | 必須/任意 | 設定する人 | 詳細 |
|---|---|---|---|---|
| **MF 掛け払い API キー** | `mfkessai-api-key.<keychain-prefix>` / `harness` | **必須** | 各メンバー（MF 掛け払い管理画面で発行した本番キー） | Step 1 |
| **Notion トークン** | `notion-api-key.<keychain-prefix>` / `harness` | **必須** | 各メンバー（出力先 DB に接続した integration トークン。共有可） | Notion セットアップ |
| **MF クラウド請求書 OAuth** | `mf-invoice-oauth.<keychain-prefix>` / `harness` | **任意** | **取得担当 1 名のみ**（`初回契約月` の一括エンリッチに使用） | 付録 |

> **重要**: 月次の発行漏れチェック本体に必要なのは上 2 つ（MF 掛け払い + Notion）だけです。3 つ目の OAuth は別製品（MF クラウド請求書）用で、**一般メンバーは登録不要**。年払い顧客の `初回契約月` を機械で一括投入したい取得担当だけが、付録の手順で設定します。空でも本体は動きます（→「初回契約月の埋め方」）。

---

## Claude Code への頼み方（かんたん実行）

コマンドや引数を覚える必要はありません。**推奨フロー `/run-mf-invoice-reconcile`（請求確認シート基準の照合）は、ふだんの言葉で頼むだけ**で自動起動します（例「請求確認シートの内容がMFに反映されているか確認して」）。その他の補助フロー（簡易差集合チェック・DB準備・初回契約月エンリッチ）は自然文では自動起動しないので、**表の右列のスラッシュコマンドをそのまま打ってください**（一番確実です）。

> **動かない・AIが自前で実装し始めたら**: 推奨フロー `/run-mf-invoice-reconcile` は自然文 (例「請求確認シートの内容がMFに反映されてるか確認して」) でも自動起動します。もし起動しない言い回しだった場合は、表の右列の**スラッシュコマンドをそのまま打てば確実**です。**照合・判定ロジックは実装済み**なので、AI が新しいスクリプトを書き始めたり、判定を `TODO(human)` で人に書かせようとしたら、それは正規フローの迂回です — `/run-mf-invoice-reconcile --target YYMM` を明示してください (正本は `scripts/reconcile_invoices.py` + `lib/mfk_reconcile.py`、機械的にも `hooks/guard-mfk-no-reinvent.py` が再実装を遮断します)。

| やりたいこと | Claude Code への一言（例・コピペ可） | 内部で動くもの |
|---|---|---|
| **初回: 請求確認シート照合用 DB を準備** | `請求確認シート照合用のDBを準備して` | `scripts/build_reconcile_dbs.py` |
| **初回: 簡易差集合チェック用 DB を準備** | `請求書チェック用の Notion DB を準備して` | `/run-mf-invoice-db-setup` |
| **請求確認シートを基準にMF発行内容を照合（推奨）** | `請求確認シートの内容がMoneyForwardに反映されているか確認して` | `/run-mf-invoice-reconcile --target YYMM` |
| **前月取引−今月取引の簡易差集合チェック** | `先月と今月の請求書発行漏れをチェックして` | `/run-mf-invoice-check` |
| **月を指定して簡易チェック** | `2026-05 の請求書発行漏れをチェックして` | `/run-mf-invoice-check --month 2026-05` |
| **過去月の履歴をまとめて投入 (backfill)** | `2026-03 から 2026-06 までの発行履歴を Notion に入れて` | `/run-mf-invoice-check --backfill --from 2026-03 --to 2026-06` |
| **過去月の確認状況を Notion で見たい** | `過去にチェックした月の状況を Notion でどう見ればいい？` | 下記「過去月の状態を確認する」を案内 |

- **スラッシュコマンドを直接打ってもOK**: 通常運用は `/run-mf-invoice-reconcile --target YYMM` で dry-run を確認し、二段確認後に `/run-mf-invoice-reconcile --target YYMM --apply --verified` を実行します。簡易差集合だけ見たい場合は `/run-mf-invoice-check` を使います。
- **対象月は明示推奨**: 請求確認シート基準の照合は `--target YYMM` (例: `2606`) を明示します。簡易差集合チェックだけは、月指定が無ければ実行日の年月を「今月」として扱います。
- **安全**: チェックは同梱クライアントでは MF 掛け払い API を**読み取り専用**で叩くだけで、請求データを書き換えることはありません（Bash 経路の参照専用ガード + 同梱クライアントの GET 専用設計で強く抑止）。請求確認シートへの書き戻しは `判定`・`AI確認`・`確認ポイント` と、空欄の `契約開始日` 補完だけです。`チェック済み`・`確認内容`・`取引先`・`商品`・`契約終了月` は触れません。

> **tenant 運用者**は、照合に使う 3 DB id (請求確認シート/契約マスタ DB1/月次チェック DB2) が**配布既定に焼き込み済みのため設定不要**です。**① `/run-mf-invoice-reconcile --target YYMM` で dry-run → ②二段確認後 `/run-mf-invoice-reconcile --target YYMM --apply --verified`** の順で動きます。
> **別ワークスペースで使う第三者**は、`.mf-kessai-config.json` に自分の `notion.sheet_db_id` を書き、▶ Claude Code のチャットで `請求確認シート照合用のDBを準備して`(開発者が clone を直叩きするなら `python3 "${CLAUDE_PLUGIN_ROOT:-plugins/mf-kessai-invoice-check}/scripts/build_reconcile_dbs.py" --parent-page-id <page_id>`)で DB1/DB2 を作成 (id は自動で `.mf-kessai-config.json` に記録され既定を上書き) してから dry-run してください。

### 請求確認シート基準の照合

`/run-mf-invoice-reconcile --target YYMM` は、請求確認シートの `年月/取引先/商品/確認内容/契約開始日/契約終了月` を基準に、MF掛け払いの対象月取引へ金額・商品・取引先/エンドクライアントが反映されているかを照合します。対象月の定義は **取引日 (`transaction.date`) 基準**です。例: `--target 2606` なら、取引日 `2026-06-30`・発行日 `2026-07-01` の請求を 6月分として採用し、取引日 `2026-05-31`・発行日 `2026-06-01` の請求は 6月分から除外します。担当者が入力するのは請求確認シートだけで、契約マスタ DB1 と月次チェック DB2 はスキルが生成・移管します。

> **シートの『年月』も取引日 (月末締め) の月で記入してください** (例: 取引日 `2026/06/30` 締め → 年月 `2606`、`--target 2606` と一致)。順方向の発行漏れ検知は当月『年月』の行を期待集合とするため、**発行月 (翌月月初) で記入すると当月の期待集合から外れ、真の発行漏れを見逃します**。MF 側 (`transaction.date`) と同じ取引日(締め)月軸に揃えるのが原則です。

MF 側の証跡は `/billings/qualified` の**発行済み status** を採用します — `invoice_issued` に加え、発行後に進む `account_transfer_notified` (口座振替通知済み=発行後の後続段階) も発行済みとして扱います (共有 `collect_mf` が `mfk_collect_status.is_issued_billing` で判定・実測で `account_transfer_notified` の実在発行が `status=invoice_issued` 限定取得により偽の発行漏れになっていた事象の是正)。`scheduled` (発行予定) と `stopped` (停止) は非発行として証跡には使いません。

確認内容に `期間：A〜B` がある場合、その期間は「作業開始から1年間」の根拠として扱い、初年度は年間払い、2年目以降は月払いとして判定します。期間も契約開始日も未記入の契約は原則月払いとして扱い、当月請求が MF に反映されている前提で照合します。MF側で同じ会社の複数シート行が1つの請求情報・1明細にまとまる場合も、契約ID境界内で期待額合計とMF明細額が一致すれば発行確認OKとして扱います。

**シート『判定』が空欄（未照合）の行の意味**: 当月（対象年月）に登録された行は保留契約も含め**必ず判定が付きます**（保留＝『要確認』として可視化し、なぜ判定保留かは『確認ポイント』に理由を記述）。したがってシート『判定』が空欄（未照合）に残るのは、**その行が当月照合の対象でない場合**（年月が対象月と違う行、または当月シートに登録の無い行）だけです。経理は**当月の年月でフィルタ**して確認してください（空欄＝当月対象外であり、判定漏れではありません）。

**判定語彙（経理向け）**: シート『判定』は 5 値（`AIの確認OK`／`対象外`／`要確認`／`発行漏れ`／未照合）の投影で、**詳しい理由は必ず『確認ポイント』列に出ます**。

- **`対象外`**: 当月は請求が無いのが正常な行。なぜ対象外かを確認ポイントに明記します ──「年間前払い期間中」「契約終了済み」「単発で開始月に計上済み」「分割完了済み／隔月の非請求月」。**理由が空欄のままにはなりません**（以前は対象外の理由が見えませんでしたが、現在は必ず表示します）。**`対象外` でも当月の MF 掛け払いに取消（キャンセル）取引があれば、確認ポイントに取消理由（取消前金額・取消日）を併記します**（例：契約終了済みの会社で当月に「一度発行→取消」が起きていた場合、対象外のまま取消の事実が分かるようにします。判定の色は据え置き＝WARN-not-FAIL）。MF 掛け払いは紐づく取引が取消されると請求合計が 0 円になり商品名だけ残るため、「商品名はあるのに金額0」が取消由来であることを確認ポイントで示します。
- **`要確認(取消)`**: MF 掛け払いで当月の請求が**取消（キャンセル）**されており、同月内に再発行されていない行。取消前金額は MF 上 0 円集計になりますが、取引自体は残っているため「発行確認OK」に化けないよう **要確認（黄）** で可視化します。金額0円でも商品名が残る `status=canceled` 取引は、対象外ではなく `要確認(取消)` です。確認ポイントに**取消日時・取消前金額**を出すので、再発行が必要か（請求不要か）を確認してください。
- **`要確認(取引未確定)`**: MF 取引が**有効な発行（審査通過）になっていない**行（審査中・否決・取引停止など、`status` が `passed`／`canceled` 以外の状態）。取消と同様に「発行済み」へ化けないよう **要確認（黄）** で可視化し、確認ポイントに取引状態を出します。現状の取得データには出現しませんが、将来この状態が起きても発行漏れ（赤）へ誤分類せず拾うための前向きな分類です。
- その他の `要確認(...)`（金額差／数量差／過剰請求／従量 等）・`発行漏れ` も、何を確認・対応すべきかを確認ポイントに出します。`AIの確認OK`（緑）だけは確認不要のため確認ポイントは空です。

> **凍結×取消の限界**: 過去に人が確認して**凍結された行**（DB2 で「人間対応済み」または過去月）は再計算しないため、後から MF 側で取消が発生しても DB2 へは反映されません。一方シート『判定』は毎回の再実行で再計算されるため、凍結後に取消された当月行は次回実行で `要確認(取消)` に変わりうります（DB2 とシートで一時的に表示が食い違う場合があります）。

---

## 前提

- macOS (Keychain を利用)
- Python 3.11+
- MF 掛け払いの **本番 API キー** を取得済み (管理画面で発行)

---

## セットアップの進め方 (Step 1 → 3)

以下は「**① 鍵の登録 → ② 設定 (通常は不要) → ③ セットアップ確認 (doctor)**」の順です。各コマンドブロックには **どこで実行するか** を明示します。

- **▶ 自分のローカルターミナルで**: `security …` の鍵登録 (Step 1) **だけ**は、鍵を macOS Keychain に対話入力するため **真にターミナルが必要** です。
- **▶ Claude Code のチャットで**: 取得確認・疎通確認 (Step 3) は Claude Code に頼みます (`/run-mf-invoice-doctor` または自然文)。

> **⚠️ 疎通確認を素のターミナルで手打ちしないこと**: `python3 "$CLAUDE_PLUGIN_ROOT/lib/…"` のように `$CLAUDE_PLUGIN_ROOT` を含むコマンドを **素のターミナル** にそのまま打つと、`$CLAUDE_PLUGIN_ROOT` は **未定義で空文字に展開** され、`can't open file '/lib/mfk_keychain.py'`(先頭が `/lib/…` になる)というエラーになります。`$CLAUDE_PLUGIN_ROOT` は **Claude Code の実行環境でのみ** 解決される変数だからです。だから **疎通確認は Claude Code のチャットに「MF掛け払いのセットアップを確認して」と頼む**か、`/run-mf-invoice-doctor` を使ってください(Claude が install 位置を解決して実行します)。スクリプト内部のモジュール解決・設定ファイル探索は `__file__` 相対なので install 位置には依存しません。

---

## Step 1. API キーを Keychain に登録

> **▶ 自分のローカルターミナルで実行** — このステップだけは鍵の対話入力のため素のターミナルが必要です。
>
> **安全原則**: API キーを `-w 'xxxx'` のように引数で渡すと、シェル履歴や AI アシスタントの会話に残ります。必ず **対話入力モード** (`-w` を値なしで末尾に置く) で、**自分のローカルターミナル**で実行してください。

```bash
# 既存登録の確認 (任意)
security find-generic-password -s mfkessai-api-key.<keychain-prefix> -a <keychain-prefix> 2>/dev/null \
  && echo "既存あり (更新になります)" || echo "未登録"

# 登録 (対話入力モード)。実行後 "password data:" が出たら本番キーを貼り付けて Enter
security add-generic-password \
  -s mfkessai-api-key.<keychain-prefix> \
  -a <keychain-prefix> \
  -U \
  -w
```

| オプション | 意味 |
|---|---|
| `-s` | service 名 = `mfkessai-api-key.<keychain-prefix>` (`MFK_KEYCHAIN_SERVICE` で上書き可) |
| `-a` | account 名 = `harness` (`MFK_KEYCHAIN_ACCOUNT` で上書き可) |
| `-w` | パスワード本体 (**省略すると対話入力**。シェル履歴に残らない) |
| `-U` | 既存があれば更新 |

> 命名は既存の `notion-api-key.<keychain-prefix>` / account `<keychain-prefix>` と同じ規約に揃えています。

---

## Step 2. 設定 (ほぼゼロ設定)

設定は **2 層**です。**通常は何もしなくても動きます**。

| ファイル | git | 役割 |
|---|---|---|
| `mf-kessai-config.default.json` | 追跡 (コミット) | **配布既定**。`environment`/`base_url`/Keychain 名/**Notion の出力先 `database_id` と照合 3 DB id (`sheet_db_id`/`reconcile_db1_id`/`reconcile_db2_id`)** が入っており、導入者はこのまま使える (id は資格情報ではない。アクセスには Keychain の Notion トークン + integration 接続が必要) |
| `.mf-kessai-config.json` | 無視 (gitignore) | **任意の上書き**のみ。書いた**非空値だけ**が既定を上書きする (空欄は既定を温存) |
| `.mf-kessai-config.example.json` | 追跡 | 上書きの書式サンプル |

```bash
# 別環境・別 DB を使う場合のみ (通常は不要)。fallback 形で Claude Code / clone 開発者の
# どちらでも解決する ($CLAUDE_PLUGIN_ROOT 未定義なら repo 直下の相対パスへ落ちる):
P="${CLAUDE_PLUGIN_ROOT:-plugins/mf-kessai-invoice-check}"
cp "$P/.mf-kessai-config.example.json" "$P/.mf-kessai-config.json"
# 例: サンドボックスで試す → environment を "sandbox" に / 別の Notion DB → notion.database_id を上書き
```

> Notion 出力先は既定で DB『請求書チェック_DB』(`database_id` 焼き込み済み) です。利用には Keychain の Notion トークン (`notion-api-key.<keychain-prefix>`) と、**その DB への integration 接続**が必要です (下記「Notion セットアップ」)。

---

## Step 3. セットアップ確認 (doctor / キー本体は表示しない)

> **▶ Claude Code のチャットで実行** — 取得確認・疎通確認は Claude Code に頼みます(素のターミナルで手打ちしない)。

鍵の取得可否と API/Notion の疎通を **1 コマンドでまとめて自己診断** できます。**推奨（install 形態を問わず動く）**:

- Claude Code のチャットに **「MF掛け払いのセットアップを確認して」** と自然文で頼む、または
- **`/run-mf-invoice-doctor`** を打つ。

doctor は次を順に点検し、各項目を **OK / WARN / SKIP** と「次に何をすべきか」付きで表示します(**鍵・トークンの中身は表示しません**):

1. **MF掛け払い APIキー** … Keychain から取得できるか(マスク表示)
2. **MF掛け払い API 疎通** … `GET /customers`(読み取りのみ)で `HTTP 200`・顧客総数
3. **Notion トークン** … Keychain から取得できるか
4. **Notion 既定 DB 到達** … 既定 DB にアクセスできるか(integration 未接続なら WARN)

`HTTP 200` と顧客総数が出れば、本番 URL・キーともに正常です。WARN は診断のみで処理を止めません(表示された次アクションを実施して再実行)。

> **開発者向け補足 (clone を直叩きするデバッグ用)**: このリポジトリを clone した開発者は、`$CLAUDE_PLUGIN_ROOT` を **fallback 形** で解決すれば自分のターミナルでも同じ点検を実行できます(素のターミナルでは `$CLAUDE_PLUGIN_ROOT` が空になるため、必ず下記の `${…:-…}` 付きで打つ)。install 位置は `__file__` 相対で自己解決するので、マーケットプレース install 先でも動きます。
>
> ```bash
> # 開発者向け (clone 直叩き)。$CLAUDE_PLUGIN_ROOT 未定義なら repo 直下の相対パスへ落ちる:
> python3 "${CLAUDE_PLUGIN_ROOT:-plugins/mf-kessai-invoice-check}/lib/mfk_doctor.py"
> # 個別に確認したい場合 (いずれも読み取りのみ・キー本体は非表示):
> python3 "${CLAUDE_PLUGIN_ROOT:-plugins/mf-kessai-invoice-check}/lib/mfk_keychain.py" --check
> python3 "${CLAUDE_PLUGIN_ROOT:-plugins/mf-kessai-invoice-check}/lib/mfk_api.py" --smoke
> ```

---

## 使い方 — 任意エンドポイントの取得

`--path` と `--param key=value` (複数可) で任意の GET を叩けます。`status` のような配列も `--param` を複数並べれば展開されます。これは**開発者向けのアドホック確認**なので、`$CLAUDE_PLUGIN_ROOT` は **fallback 形**で解決します(素のターミナルでも repo 直下相対へ落ちて動く)。

```bash
# 開発者向け (アドホック GET・clone 直叩きでも動く fallback 形)。
API="${CLAUDE_PLUGIN_ROOT:-plugins/mf-kessai-invoice-check}/lib/mfk_api.py"

# 発行済み請求書の一覧取得例。
# 月次照合ではこの一覧を対象月初〜翌月末で広めに取り、
# /transactions の date(取引日)で対象月に絞る。
python3 "$API" \
  --path /billings/qualified \
  --param issue_date_from=2026-06-01 \
  --param issue_date_to=2026-07-31 \
  --param status=invoice_issued \
  --param limit=5

# 取引(取引日 date・商品名 description・金額)
python3 "$API" --path /transactions --param billing_id=<billing_id> --param limit=5
```

### Python から呼ぶ

```python
import os, sys
# CLAUDE_PLUGIN_ROOT 優先、無ければ repo 直下相対へ fallback (KeyError を出さない)。
# 素のターミナル/スクリプト実行でも壊れないよう os.environ.get を使う。
_root = os.environ.get("CLAUDE_PLUGIN_ROOT") or "plugins/mf-kessai-invoice-check"
sys.path.insert(0, os.path.join(_root, "lib"))
from mfk_api import get

# 6月分照合用の候補一覧。issue_date は over-fetch 窓であり、月帰属は後段の transaction.date で確定する。
data = get("/billings/qualified", {
    "issue_date_from": "2026-06-01",
    "issue_date_to": "2026-07-31",
    "status": "invoice_issued",
    "limit": 200,
})
for b in data["items"]:
    print(b["customer_id"], b["amount"], b["issue_date"])
```

---

## エンドポイント早見表 (発行漏れチェックで使うもの)

| 用途 | パス | 主なパラメータ |
|---|---|---|
| 顧客一覧 (企業名 name の名寄せ) | `/customers` | `ids`, `limit`, `after` |
| 発行済み請求一覧 (インボイスモード) | `/billings/qualified` | `issue_date_from/to`, `status`, `limit`, `after` |
| 請求単体 (status・amount・invoice_ids) | `/billings/{id}` | — |
| 取引・明細 (取引日 date・商品名 description・金額) | `/transactions` | `billing_id`, `limit`, `after` |

> 注: この事業者はインボイス制度モードのため、一覧は `/billings`(区分記載用) ではなく **`/billings/qualified`** を使います (`/billings` は空を返す)。

---

## 環境変数による上書き

| 変数 | 用途 |
|---|---|
| `MFK_KEYCHAIN_SERVICE` / `MFK_KEYCHAIN_ACCOUNT` | 別の Keychain entry (staging 等) を使う |
| `MFK_API_KEY` | Keychain が無い CI / 非macOS のフォールバック (キーが環境に載る点に注意) |
| `MFK_BASE_URL` | base_url を一時的に上書き |

---

## Notion セットアップ (出力先)

出力先 DB『請求書チェック_DB』(`database_id` は配布既定に焼き込み済み) を使うための準備:

1. **Notion トークンを Keychain に登録** (未登録なら): service `notion-api-key.<keychain-prefix>` / account `<keychain-prefix>`。
2. **DB に integration を接続**: Notion でその DB を開き `···` → `+ 接続` (Connections) から、上記トークンの integration を接続。**未接続だと `HTTP 404 object_not_found`** になります。
3. **スキーマを適用** (冪等。既存 DB に不足プロパティを追加・タイトル列を `取引先企業名` にリネーム)。**▶ Claude Code のチャットで** `請求書チェック用の Notion DB を準備して` と頼むか **`/run-mf-invoice-db-setup`** を打ちます(スキーマ適用と verify をまとめて実行)。

> **開発者向け補足 (clone を直叩きするデバッグ用)**: スクリプトを直接叩く場合は `$CLAUDE_PLUGIN_ROOT` を **fallback 形** で解決します(素のターミナルでも repo 直下相対へ落ちる)。
>
> ```bash
> # 開発者向け (clone 直叩き)。$CLAUDE_PLUGIN_ROOT 未定義なら repo 直下の相対パスへ落ちる:
> SK="${CLAUDE_PLUGIN_ROOT:-plugins/mf-kessai-invoice-check}/skills"
> python3 "$SK/run-mf-invoice-db-setup/scripts/build_notion_db.py"
> python3 "$SK/run-mf-invoice-db-setup/scripts/verify_db_schema.py"
> # → PASS 全 N プロパティが存在し、旧プロパティの残存もありません。
> #   (N は notion-db-schema.json のプロパティ数を len(expected) で動的算出した値。
> #    スキーマの列増減に追従するため README には固定値を書かない)
> ```

> 別の既存 DB を使いたい場合は `.mf-kessai-config.json` に `{"notion": {"database_id": "<id>"}}` を書けば上書きできます。親ページ配下に**新規 DB を作成**したい場合は `/run-mf-invoice-db-setup --parent-page-id <page_id>`(または開発者は上記 `build_notion_db.py --parent-page-id <page_id>`)を実行します。`--parent-page-id` は配布既定の `database_id` より優先され、作成した `database_id` をローカル `.mf-kessai-config.json` に記録します。

---

## 初回契約月の埋め方（年払い顧客の誤検出を防ぐ）

> **結論を先に**: `初回契約月` を埋める**正本は「人が Notion に YYYY-MM で記入」**です。空でも発行漏れチェック本体は動きます。機械での一括エンリッチ（付録）は**任意の補助**で、取得担当 1 名だけが使います。

### なぜこの列が要るのか

年間払い（年 1 回前払い）の顧客は、その月以外は請求が無いのが正常です。月次の差集合だけ見ると、こうした顧客が**毎月「発行漏れ候補」として誤検出**されます。これを抑えるため、管理列 `初回契約月`（YYYY-MM）と `支払サイクル`（月払い/年間払い）を使い、**機械が「初回契約月から 12 か月」を年間契約期間とみなして発行漏れ候補から自動抑制**します（`suppress_annual_period_gaps`）。

### 誰が・何を・いつ

| 項目 | 内容 |
|---|---|
| **対象顧客** | **年間払いの顧客のみ**（月払いは記入不要） |
| **正本（必須）** | 人が Notion DB の `初回契約月` に `YYYY-MM`（例 `2026-04`）を記入し、`支払サイクル` を「年間払い」に設定する |
| **未入力でも安全** | 空のままでも本体は動く。年払い抑制が効かず**その顧客が発行漏れ候補に残るだけ**（＝真の漏れを隠さない安全側 fail-safe）。月次チェックはこの列を**読むだけで書き換えない** |
| **一括投入（任意）** | 取得担当 1 名が、別製品 MF クラウド請求書から最古発行月を引いて**初期推定値**を一括投入できる（→ 付録）。あくまで初期値の補助で、最終確定は人 |

> **未入力の顧客を探す**: Notion DB を `初回契約月` が空でフィルタすると、記入が必要な顧客（≒年払いの可能性がある顧客）を洗い出せます。

---

## 過去月の状態を確認する (運用者向け)

> **過去月の確認結果は失われません。** upsert キーは `顧客ID` 単独で **1 顧客=1 ページ**。既存顧客は月が変わっても同じページを更新し、未登録顧客だけ新規ページを作成します。月次履歴は各顧客ページ**本文の table block** (列: 対象年月/今月の発行状況/前月金額/今月金額/確認済み日時) に **1 行=1 対象年月**で蓄積されます。同月の再実行は該当行を更新するだけで重複せず、過去月の行は消えません。管理列 (初回契約月/請求要否/支払サイクル/チェック済/備考) は既存ページでは自動実行が一切触れないため、人の運用判断もそのまま保持されます。

経理担当が「いつ・何を確認したか」を Notion 上で振り返るための見方を Q&A 形式でまとめます。**DB は顧客一覧 (最新月スナップショット)**、**月次の推移は各顧客ページ本文の table** という二層構造です。

| 知りたいこと | Notion での見方 |
|---|---|
| **ある顧客の月ごとの推移は?** | DB でその顧客の行 (ページ) を開き、本文の月次履歴 **table block** を見る。各行=1 対象年月で `今月の発行状況 / 前月金額 / 今月金額 / 確認済み日時` が並ぶ。 |
| **ある月に何を確認したか?** | 各顧客ページ本文 table の `対象年月` 行で、その月の `今月の発行状況`・`確認済み日時` を確認。**単月の正規フローと backfill では網羅性が非対称**: 単月フローは全チェック対象顧客のページに当月行が残る (候補0件月も記録)。一方 **backfill 既定では未検証の発行漏れ候補を sink からスキップする**ため、過去月 table では発行漏れ候補が穴 (行欠落) になる。過去月の漏れ候補まで履歴化したい場合は `--force-unverified` を明示する (**ただし二段確認 subagent はバイパスされ、誤検出が未排除のまま投入される**点に注意)。 |
| **今月の要対応は?** | DB を `チェック済 = 未チェック` または `請求要否 = 継続` × `今月の発行状況 = 発行漏れ候補` でフィルタした「要対応」ビュー。DB プロパティ「今月の発行状況」「対象年月」(最新月スナップショット) と管理列「チェック済」「請求要否」を使うだけで列追加は不要。 |
| **今月発行されなかった顧客 (発行漏れ) を一覧したい?** | **正規フィルタは `今月の発行状況 = 発行漏れ候補`** の1系統に統一する（判定結果を直接見るため backfill でも単月でも結果が一致する）。`今月金額` が**空**かどうかは補足的な目安に留める（発行漏れ候補は今月発行が無いため `今月金額` が空になるが、backfill 既定では未検証候補が sink からスキップされ行自体が作られないことがあり、`今月の発行状況` フィルタと結果が乖離しうる）。`今月金額`/`前月金額` は**月ごとに増えない固定の number 列**で毎月最新月スナップショットに上書きされるため、同じフィルタを毎月そのまま使い回せる（その金額がどの月かは `対象年月` 列で判別。既定では実行日の年月）。 |
| **過去にやり残しは?** | `チェック済 = 未チェック` でフィルタ。詳細な月別推移は各顧客ページ本文 table を開いて確認する。 |
| **全体トータル/件数を見たい?** | **サマリ列 (全体トータル・件数) は作らない設計**。Notion DB ビューで `今月の発行状況 = 発行漏れ候補` 等に絞り込んだ**行数 (フィルタ件数)** で代替する。集計列を手動で足すと月次チェックの整合性が崩れる。旧サマリ列や `全体トータル` 列が DB に残っていたら `/run-mf-invoice-db-setup` を再実行して掃除する (月次 `--sink` 後にも残存を検知し stderr で同じ誘導が出る)。**集計は DB の【ビュー機能】(フィルタ→件数表示・グループ集計)で行い、列(プロパティ)や rollup を足さない。ビューはデータを増やさないので安全。** 禁止理由: `今月金額`/`前月金額` は毎月「最新月スナップショット」で上書きされる固定列のため、集計列を足すと過去月分まで巻き込んで値が壊れる。だから集計列でなくビューのフィルタ件数+目視で確認する。(補足) かつて存在した「月次チェックサマリ」等の集計は旧データモデルの産物で、現在は持たない設計。手動で残っていれば削除してよい(現コードが再生成することはない)。 |
| **初回年払いの契約月が未入力の顧客は?** | DB を `初回契約月` が空でフィルタする。企業ごとの `初回契約月` を YYYY-MM (例: `2026-04`) で補完し、`支払サイクル` (月払い/年間払い) を設定する。年間払いなら入力月から 12 か月を初回年払い期間として人が請求要否を判断する。**`初回契約月` は人が YYYY-MM で記入し、機械が年間契約抑制 (年払い顧客の発行漏れ候補の自動抑制) に利用する列**。記入が無いと当該顧客は抑制対象に乗らないため、年払い顧客では必ず記入する。 |

**役割分担** (上記「構成」と整合):

- **DB プロパティ** = 顧客一覧・絞り込み・並び替え用。各行はその顧客の**最新月スナップショット** (事実列 + 管理列)。
- **ページ本文 table block** = 月次履歴表。`対象年月 / 今月の発行状況 / 前月金額 / 今月金額 / 確認済み日時` を 1 行=1 対象年月で蓄積し、同月再実行は行更新で冪等。過去月の行は上書き・削除されない。
- **管理列** (`初回契約月 / 請求要否 / 支払サイクル / チェック済 / 備考`) = 顧客ページ単位の運用メモ。`初回契約月` (YYYY-MM) と `支払サイクル` (月払い/年間払い) は MF API から直接取得できないため、人が設定する（`初回契約月` は任意で取得担当がエンリッチ一括投入も可。→「初回契約月の埋め方」「付録」）。月別の対応有無は本文 table には持たせないため、「6月は不要、7月は要対応」のような月別管理が必要な場合は、備考に月を明記するか履歴専用 DB への設計変更を検討する。

---

## トラブルシュート

| 症状 | 原因 | 対処 |
|---|---|---|
| `can't open file '/lib/mfk_keychain.py'` / `/lib/…` No such file | 生ターミナルで `$CLAUDE_PLUGIN_ROOT` が未定義 (Claude Code 外で実行し、変数が空展開して先頭が `/lib/…` になった) | Claude Code のチャットで `/run-mf-invoice-doctor` を実行、または「MF掛け払いのセットアップを確認して」と Claude に頼む (Claude が install 位置を解決して実行する) |
| `Keychain lookup failed` | 未登録 / service・account 名違い | Step 1 をやり直す |
| `HTTP 401` | キー不正 / 本番・サンドボックス取り違え | Keychain の値・環境を確認 |
| `HTTP 404` / 接続失敗 (MF) | base_url 誤り | `environment` / `base_url` を確認 |
| `/billings` が 0 件 | インボイスモード事業者 | `/billings/qualified` を使う |
| Notion `404 object_not_found` | DB に integration 未接続 | 上記「Notion セットアップ」2 を実施 |
| 企業名が全て空欄 | `/customers?ids=` が解決失敗 | stderr 警告を確認 (形式は doseq `ids=A&ids=B` で検証済み) |
| AIが自前スクリプトを作り始める / 判定を `TODO(human)` で人に書かせようとする | 正規スキルが起動せず即興実装に倒れた / 既存 `lib/mfk_reconcile.py` を未使用 | `/run-mf-invoice-reconcile --target YYMM` を明示。照合・判定は実装済み (`scripts/reconcile_invoices.py` + `lib/mfk_reconcile.py`)。再実装と `TODO(human)` は `hooks/guard-mfk-no-reinvent.py` が PreToolUse で遮断する |

---

## 構成 (実装済み)

1. **主フロー: 請求確認シート基準の双方向照合** (`run-mf-invoice-reconcile`): 請求確認シートの当月行を期待集合、MF掛け払いの発行済み取引 (`invoice_issued` に加え発行後に進む `account_transfer_notified`・共有 `collect_mf` が `mfk_collect_status.is_issued_billing` で判定) を実績集合として照合します。順方向で発行漏れ・金額差・対象外を、逆方向で要マスタ登録 (orphan) を検出します。
2. **DB1/DB2 二層台帳** (`scripts/build_reconcile_dbs.py` / `lib/notion_reconcile_sink.py`): DB1 は契約マスタ、DB2 は月次発行チェック履歴です。月次運用では DB を作り直さず、対象年月キーで当月だけ非破壊 upsert します。
3. **請求確認シートへの片方向ミラー** (`lib/notion_sheet_writeback.py`): DB2 の判定 SoR から、当月シート行へ `判定`・`AI確認`・`確認ポイント` を書き戻します。空欄の `契約開始日` だけ派生補完し、`契約終了月` と人間列は触りません。
4. **二段確認** (`agents/mfk-reconcile-verifier.md`): dry-run の判定内訳を独立 context の subagent で確認してから、`--apply --verified` で反映します。`--verified` なしの sink apply は fail-closed します。
5. **簡易差集合フロー** (`run-mf-invoice-check`): 前月取引−今月取引の顧客差集合だけを Notion『請求書チェック_DB』へ入れる補助フローです。請求確認シート・契約終了・金額差・orphan まで見る通常運用では主フローを使います。
6. **参照専用ガード** (`hooks/guard-mfk-readonly.py`): Bash 経路での MF API 変更系 (POST/PUT/PATCH/DELETE や curl data 送信) を PreToolUse hook で遮断。同梱 MF クライアントも GET 専用にして二層で抑止する。MFクラウド請求書側 (OAuth) の参照専用は API クライアントの GET 専用設計で担保し、guard hook の射程は掛け払い (mfkessai.co.jp) 宛て Bash。

### 使い方 (月次)

**推奨は請求確認シート基準のスラッシュコマンド経由**です。担当者が入力する正本を請求確認シートに一本化し、契約マスタ DB1 / 月次チェック DB2 はスキルが生成・更新します。

```
/run-mf-invoice-reconcile --target YYMM          # dry-run: 判定内訳を確認
/run-mf-invoice-reconcile --target YYMM --apply --verified  # 適用: 二段確認後に DB1/DB2 と請求確認シートへ反映
```

旧来の `/run-mf-invoice-check` は、前月取引−今月取引の顧客差集合だけを Notion『請求書チェック_DB』へ入れる簡易チェックです。請求確認シートの `確認内容`・契約開始/終了・支払サイクル・金額差・orphan（MF実績はあるがシート未登録）まで確認したい通常運用では `/run-mf-invoice-reconcile` を使います。

スクリプトを直接叩く場合 (**開発者向け・clone を直叩きするデバッグ用**)。`$CLAUDE_PLUGIN_ROOT` は Claude Code の実行環境でしか解決されないため、**素のターミナルでも動くよう fallback 形** で書きます(未定義なら repo 直下相対へ落ちる):

```bash
# 開発者向け (clone 直叩き)。$CLAUDE_PLUGIN_ROOT 未定義なら repo 直下の相対パスへ落ちる:
RC="${CLAUDE_PLUGIN_ROOT:-plugins/mf-kessai-invoice-check}/scripts/reconcile_invoices.py"
python3 "$RC" --target 2606
python3 "$RC" --target 2606 --apply --verified
```

旧来の簡易差集合フローを直接叩く場合 (**開発者向け・clone 直叩き**):

```bash
# 開発者向け (clone 直叩き)。$CLAUDE_PLUGIN_ROOT 未定義なら repo 直下の相対パスへ落ちる:
SK="${CLAUDE_PLUGIN_ROOT:-plugins/mf-kessai-invoice-check}/skills"

# 初回のみ: 既定DBにスキーマ適用 (冪等)
python3 "$SK/run-mf-invoice-db-setup/scripts/build_notion_db.py"

# 毎月の正規フロー (collect → verify → finalize → sink)
python3 "$SK/run-mf-invoice-check/scripts/check_invoice_gaps.py" --collect [--month YYYY-MM]
#  → 全チェック対象顧客の月次チェック行を eval-log/mfk-gap-candidates.json に出力
#  → subagent mfk-gap-verifier が誤検出を排除し、確定リストを finalize:
python3 "$SK/run-mf-invoice-check/scripts/check_invoice_gaps.py" --finalize [--exclude-ids <cid,...>]
#  → 確定リスト eval-log/mfk-gap-verified.json を生成 (= sink の入力境界)
python3 "$SK/run-mf-invoice-check/scripts/check_invoice_gaps.py" --sink
#  → 確定リストを顧客IDキーで Notion へ冪等 upsert
#     (1顧客=1ページ、既存顧客は更新、未登録顧客だけ作成、月ごとの重複ページなし)。
#     各顧客ページ本文の月次履歴 table に当月行 (自然キー period_ym) を upsert。
#     確定リスト不在なら fail-closed (exit 2)

# 過去月の履歴をまとめて投入 (backfill): --from〜--to (両端含む) を月昇順で collect→sink
#   ※ 複数月を自動で回すため対話 verify は挟めない (--month の単月フローと排他)
#   ※ 既定では未検証の発行漏れ候補は投入せず、継続発行/今月新規のみ履歴化する
python3 "$SK/run-mf-invoice-check/scripts/check_invoice_gaps.py" --backfill --from 2026-03 --to 2026-06
```

> **出力先 (eval-log) の解決**: 成果物 (候補/確定 JSON) の置き場は install パスに依存させず、
> `MFK_OUTPUT_DIR` (env) > `CLAUDE_PROJECT_DIR` > 実行 CWD の優先順で `<base>/eval-log/` に解決します。
> collect・finalize・sink は同じ CWD (または同じ `MFK_OUTPUT_DIR`) で実行してください。
> **break-glass**: 二段確認をスキップして未検証候補を直接投入する場合だけ
> `--sink --force-unverified` または `--backfill --from YYYY-MM --to YYYY-MM --force-unverified`
> を明示します。通常運用では使いません。既定の backfill は未検証の発行漏れ候補を
> スキップするため、その顧客の当該月行は Notion には作られません。

---

## 付録: 初回契約月の一括エンリッチ（同梱・取得担当のみ実行）

> **一般メンバーは読み飛ばして構いません。** これは年払い顧客の `初回契約月` を機械で一括投入したい**取得担当 1 名**だけの任意スキルです。手で記入する運用（→「初回契約月の埋め方」）だけでもプラグインは完結します。

### これは何か

別製品 **MF クラウド請求書 (MoneyForward Cloud Invoice)** から各取引先の**最古発行月**を引き、`初回契約月` の**初期推定値**として Notion に一括投入する任意スキル **`run-mf-initial-month-enrich`** です。**プラグインに同梱**されており（`/plugin install` で一緒に入る）、コードは全員の手元に届きます。

### コードは全員に配布・実行は取得担当のみ

このスキルは `disable-model-invocation: true` で自動起動されません。そして**実行には OAuth トークン（Keychain `mf-invoice-oauth.<keychain-prefix>`）が必須**で、それを持つ**取得担当だけが実行できます**。トークンが無い人はコードがあっても実行できないため、全員に OAuth アプリ登録を強制しません（＝「コードの配布」と「トークン/実行権限」を分離）。

| 論点 | 設計 |
|---|---|
| **別製品・別認証** | 本体は MF 掛け払い（API キー）。本スキルは MF クラウド請求書（**OAuth2**）。どちらも GET 専用（読み取り）。Notion への書き込みは `初回契約月` 列のみ |
| **権限の宣言** | `plugin.json` に `invoice.moneyforward.com` / `api.biz.moneyforward.com`（network）と `mf-invoice-oauth.<keychain-prefix>`（secrets）を**任意権限として宣言**。本体の MF 掛け払い読み取り専用ガードはそのまま |
| **月次フローと独立** | 「空の `初回契約月` を初期値で埋める」差分補完で、毎月の発行漏れチェックとは独立して動く |

### 取得担当のやり方（2 通り）

詳細はスキル内の **`skills/run-mf-initial-month-enrich/SKILL.md`** と **`references/oauth-setup.md`**（OAuth トークン取得手順）に集約しています。`$CLAUDE_PLUGIN_ROOT` で install 位置に依存せず解決されます。

1. **CSV 名寄せ（推奨・軽量・API 不要）**: MF クラウド請求書 UI で請求書一覧を CSV エクスポートし、▶ Claude Code のチャットで `初回契約月を CSV で名寄せして` と頼む(開発者が clone を直叩きするなら `python3 "${CLAUDE_PLUGIN_ROOT:-plugins/mf-kessai-invoice-check}/skills/run-mf-initial-month-enrich/scripts/mf_invoice_csv_match.py" <CSV>`)で顧客名を名寄せ。OAuth アプリ登録が不要。
2. **OAuth API（無人運用向け）**: `mf_invoice_oauth.py` でトークンを 1 回取得（Keychain `mf-invoice-oauth.<keychain-prefix>`）し、`mf_invoice_enrich.py --plan`（対象表示）→ `--limit N`（書き込み）で未取得顧客だけを差分エンリッチ。手順は `references/oauth-setup.md`。

> いずれも投入されるのは**初期推定値**です。最終的な `初回契約月` の確定は人が行います（最古発行月 ≠ 初回契約月のケースがあるため）。
>
> 名寄せ精度を事前検証する使い捨てプローブ `mf_invoice_match_probe.py` はリポジトリの `.mfk-run/`（配布対象外）に残してあります。
