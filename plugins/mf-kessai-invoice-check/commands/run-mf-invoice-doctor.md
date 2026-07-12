---
name: run-mf-invoice-doctor
description: MF掛け払い請求書チェックのセットアップ状態(APIキー/API疎通/Notionトークン/DB到達)を1コマンドで自己診断したいとき、疎通確認をしたいとき、さらに『最新を漏れなく取れているか』(pagination完全性/件数突合/当月issue_date範囲/stale)を fetch fidelity 監査したいときに使う。
argument-hint: "[--json] | [--fetch-trace <path> --target <YYMM>]"
allowed-tools: Read, Bash
---

# /run-mf-invoice-doctor

MF掛け払い請求書チェックのセットアップを横断自己診断する。(1) MF掛け払い APIキーの Keychain 取得可否、(2) MF API 疎通 (GET `/customers`・読み取りのみ)、(3) Notion トークン取得可否、(4) 既定 Notion DB への到達を、それぞれ **OK / WARN / SKIP** で一覧表示する。**鍵・トークン本体は表示しません**(マスクのみ)。
加えて、R1/reconcile が『最新を漏れなく取れているか』を、C06 fetch fidelity 監査器 (`scripts/mfk_fetch_audit.py`・**network=false**) で単独検証できる (下記「fetch fidelity 診断」)。
Marketplace から install した場合の呼び出し名は通常 `/mf-kessai-invoice-check:run-mf-invoice-doctor`。

> **疎通確認はこのコマンド(または「MF掛け払いのセットアップを確認して」と自然文で依頼)で行ってください。** 生ターミナルで `python3 "$CLAUDE_PLUGIN_ROOT/lib/..."` を手打ちすると、`$CLAUDE_PLUGIN_ROOT` が未定義で空展開し `can't open file '/lib/...'` になります(→ README「トラブルシュート」)。このコマンドは**セットアップ確認専用**で、MF/Notion とも**読み取りのみ**・請求データやトークンには一切書き込みません。

## 振る舞い

1. 下記スクリプトを実行し、各チェックの OK / WARN / SKIP を一覧表示する。
2. WARN があっても処理は止めない (WARN-not-FAIL の診断ツール)。表示された「次アクション」を実施して再実行する。
3. install 位置は `__file__` 相対で自己解決するため、リポジトリ / マーケットプレースのどちらでも動く (`$CLAUDE_PLUGIN_ROOT` 未定義でも lib は自己解決)。
4. `--fetch-trace <path> --target <YYMM>` を渡すと、セットアップ診断とは別枠で **fetch fidelity 診断** (C06) を実行する (下記セクション)。セットアップ診断は常に WARN-not-FAIL (exit 0) だが、fetch fidelity 診断は最新性の担保をゲートするため **fail-closed** (当月/先月違反=exit 1) である点が異なる。

## 実行コード

```bash
python3 "${CLAUDE_PLUGIN_ROOT:-plugins/mf-kessai-invoice-check}/lib/mfk_doctor.py"
```

## fetch fidelity 診断 (最新を漏れなく取れているか)

上のセットアップ診断とは別枠で、**「MF から最新を漏れなく取れているか」を単独検証**できる。判定は C06 監査器 `scripts/mfk_fetch_audit.py` が担い、次の 4 観点で機械検証する。

- **pagination 完全性** — `has_next=true` のページは次カーソル (`end`) が非空で、最終記録ページが `has_next=false` で終端している (途中打切り=NG)。
- **total 件数突合** — `pagination.total` を提供する site は Σ`items_count` == `total` (取りこぼし/二重取得=NG)。
- **当月 issue_date 範囲** — billings の `issue_date_from` が対象月の当月初 (`YYYY-MM-01`) と一致する (別月取得=stale/範囲ずれ=NG)。
- **stale / 欠落** — 当月/先月/12ヶ月ルックバックの各グループについて trace の有無と完全性を点検する。

**取得と監査の分離**: C06 は **network=false** で自力では API を叩かない。R1/reconcile の read-only fetch 経路 (`lib/mfk_api.iter_all` の `trace_sink` / `get_with_trace`・GET 専用) が記録した pagination trace JSON を後追いで検証するだけである (取得層は GET のみ、監査層はネットワーク非依存)。したがって本診断は先に R1/reconcile を回して得た fetch trace を入力に取る。

### exit コード契約 (fail-closed)

| exit | 意味 | 扱い |
|---|---|---|
| 0 | 全 OK (当月・先月・ルックバックとも完全) | そのまま漏れ確認処理を続行してよい |
| 1 | **当月 or 先月の fidelity 違反、または trace 完全不在** | **fail-closed** = 漏れ確認処理を実行しない (前月↔今月比較の前提が崩れる最新性欠如)。C03 レポートも emit を止める |
| 3 | 12ヶ月ルックバックの一部月が欠落/不完全 (当月・先月は OK) | 全停止せず、該当取引先の判定を『要確認』へ降格する部分欠損の中間状態 |
| 2 | 入力不正 (fetch trace の読込失敗) | fail-closed。trace path を見直して再実行 |

当月/先月の完全性は正しい前月↔今月比較の前提そのものなので、ここが崩れたら (exit 1) **その回の漏れ確認は実行しない**のが安全側。fidelity report JSON (`{target_month, curr:{ok,violations}, prev:{...}, lookback:{complete,partial,ng_months,...}, overall, exit_code}`) は C03 (`mfk_period_report.py --fidelity-report`) が必須入力として消費する。

### 実行コード

```bash
# R1/reconcile が記録した pagination trace を対象月 (YYMM) の観点で fidelity 監査する。
# --out を省くと fidelity report JSON を stdout に出す。exit 0/1/3/2 は上表の契約どおり。
python3 "${CLAUDE_PLUGIN_ROOT:-plugins/mf-kessai-invoice-check}/scripts/mfk_fetch_audit.py" \
  --fetch-trace fetch-trace.json --target 2606        # stdout に fidelity report・exit で合否
python3 "${CLAUDE_PLUGIN_ROOT:-plugins/mf-kessai-invoice-check}/scripts/mfk_fetch_audit.py" \
  --fetch-trace fetch-trace.json --target 2606 --out fidelity.json   # report をファイルへ (C03 の --fidelity-report 入力)
```
