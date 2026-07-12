# 運用 runbook

extract-system-blueprint の **導入 (install / setup) と実行 (run)** の運用手順。

> 本 plugin は**参考/学習目的限定**。認証必須領域への無断到達・実侵入・認可外スクレイピングは行わない
> (C12 が allow した AuthzEvidence 範囲外は C08 hook が fail-closed 遮断する)。

## 1. install

marketplace 配布 plugin (`distributable: true`)。導入経路は 3 つ。

| 経路 | 手順 |
|---|---|
| marketplace | プラグインマーケットプレイスから `extract-system-blueprint` を追加する |
| CLI | `claude plugin` で marketplace 追加後に本 plugin を install する |
| Desktop | Desktop アプリのプラグイン設定から `extract-system-blueprint` を有効化する |

install 後の起動名は通常 `/extract-system-blueprint:extract-blueprint` (ローカル開発時は `/extract-blueprint`)。

## 2. setup

外部サービス連携・MCP server・API トークンは**不要**。観測は **stdlib Python (`html.parser` + `urllib`、
外部ライブラリ導入なし)** による**静的 DOM/HTML/CSS 解析を常時 baseline** とし、任意の headless Chrome 経路
(2.3) の rendered fact を上乗せする**両方併用**で行う (どちらもローカル完結・外部公開なし)。成果物はローカル
のみへ生成する。

### 2.1 静的観測 (stdlib)

C09 (`fetch-snapshot.py`) が低負荷取得した保存済み HTML と linked CSS から `static-observation.json` を
emit する。新規 connector ファイルや外部 runtime は使わない。含む内容:

- 要素ツリー / 見出し階層 (h1-h6) / nav・link 構造 / form (action・method・field)
- meta・OGP・JSON-LD / 宣言色 (CSS 由来) / font トークン (font-family・src・weight) / a11y semantic
  (role・aria・alt・label)

C03 (`frontend-surface-analyzer`) はこの `static-observation.json` を provenance 付き fact 化する。

- network 統制の**実効層は C08 hook (PreToolUse exit2)** であり、`.claude-plugin/plugin.json` の
  `permissions.network` は宣言層 (意図の表明) — 実行時遮断は hook が担う。
- 全取得は C08 の fail-closed 境界 (認可 + 残予算検査) 内で走る。

### 2.2 レンダリング必須観測の欠測扱い (unconfigured_consequence・正本)

以下は stdlib の静的解析では取得できないため、**捏造せず** `observation_gap` として記録する
(fact/inference へ昇格させない):

- 実ピクセル描画 / JS 実行後 DOM / interaction 後の状態
- computed 幾何 (`bounding_box_px`) / hover・focus・active 等の動的 state
- CWV (LCP/CLS/INP/TTFB) 実測値

記録形式は `observation_gap` (`observation_status: blocked`, reason=`static-analysis-only`)。JS 実行を要する
観測が当該対象の重要 fact (受入 C1/C9 必須 fact) に該当する場合でも、静的解析限界による gap は正直に記録する
(無言欠落は不可)。gap として記録せず無言で欠落させた場合は C9/C02 が FAIL にし、gap として正直に記録されて
いれば静的解析限界は減点対象とせず C02 が draft の品質を判定する。

> **任意の headless Chrome 経路がある場合** (下記 2.3): JS 実行後 DOM・screenshot 等の一部はブラウザ経路で
> fact 化できる。ブラウザバイナリを解決できない環境ではこれらは gap のまま残り、ブラウザ経路の起動で失敗した
> 観測は reason=`browser-unavailable` として記録される (静的経路の gap は従来どおり reason=`static-analysis-only`)。

### 2.3 ブラウザ情報取得 (任意・headless Chrome CLI — MCP ではない)

JS 実行後 DOM・viewport screenshot・rendered/computed な視覚情報は、**ローカルにインストールされた
headless Chrome/Chromium を Bash 経由 subprocess で起動**する `scripts/browser-render.py` (C03 が呼ぶ CLI)
で取得する。本 plugin は **MCP サーバー接続を一切持たない** — ブラウザ取得は「Bash 経由 headless Chrome CLI」
であって MCP ではない。静的観測 (2.1) の上に載る **progressive enhancement** で、あれば rendered fact が
増え、無ければ静的観測のみで続行する。

- **前提 (任意依存)**: ローカルに Chrome/Chromium バイナリ (`chromium` / `google-chrome` 等)。バイナリは
  `--browser-bin <path>` または env `ESB_BROWSER_BIN` で明示でき (優先度は `--browser-bin` > env > PATH 探索)、
  未指定時は PATH 上の `chromium` / `google-chrome` 等を探索する。
- **認可・二重 fail-closed**: URL を含む Bash 呼びは C08 fetch-authz hook が捕捉し、browser-render 自身も
  C12 (`authz-classify.py`) の `decide()` を import 共有して二重に fail-closed する (判定ロジックは重複実装
  しない)。低負荷レバー (対象 origin 並列 **1**・最小間隔 **2000ms**・`timeout`・`Retry-After` 尊重) は
  静的観測と共通で不変。remote font 由来の headless ハングは `--disable-remote-fonts --virtual-time-budget`
  で回避する。budget 消費は request ledger へ記録する。
- **出力**: `rendered/<host>.rendered.html` (JS 実行後 DOM) と `rendered/<host>.screenshot.png`
  (viewport screenshot、`--screenshot` 指定時)。

起動例:

```
python3 "$CLAUDE_PLUGIN_ROOT/scripts/browser-render.py" \
  --url <url> \
  --out-dir <dir> \
  --authz-evidence <dir>/authz.json \
  --request-budget <dir>/budget.json \
  --screenshot \
  --request-ledger <ledger>
```

exit コード:

| exit | 意味 | 後段 (C03) の扱い |
|---|---|---|
| `0` | 取得成功 (rendered DOM、`--screenshot` 指定時は screenshot も) | rendered fact として記録 |
| `1` | 認可外 (C12 が allow 以外) / ブラウザ起動失敗 | fail-closed。gap として記録し静的観測で続行 |
| `2` | usage エラー (必須引数不足) | 呼び出し側を修正 |
| `3` | `browser-unavailable` (バイナリ解決不能) | **graceful 縮退**。`observation_gap` (blocked, reason=`browser-unavailable`) を記録し、静的 HTTP (WebFetch + `urllib` snapshot) 観測のみで続行 |

## 3. run

```
/extract-blueprint <url> [--crawl-mode single|full_site] [--resume]
```

- 起動は薄いラッパ (command)。順序保証は **C01 draft 生成 → C02 独立品質 verdict → 報告**。
  draft の完成可否 (PASS/FAIL) は C02 の品質 verdict が決める (外部公開の Step は無い)。
- C08 hook の bootstrap は**単一 Bash 呼び** (`mkdir -p "${CLAUDE_PROJECT_DIR:-$PWD}/.esb-authz" && python3 .../authz-classify.py --url <url> ...`) が正本。hook は呼び時点で dir 不在なら非アクティブで素通し、呼び完了時には dir+evidence が揃って以後の全 tool call が enforce される (evidence 不在窓なし)。**`mkdir` 単独先行は禁止**: dir 発見で hook が即アクティブ化し、C12 呼び自身が evidence 不在=fail-closed deny で遮断される (bootstrap deadlock)。`ESB_RUN=1` は hook が別プロセスで spawn されるため Bash セッション内 export では継承されず、セッション起動時 env としてのみ有効な補助上書き。

### 3.1 crawl mode と全域被覆

| mode | 挙動 |
|---|---|
| `single` (既定) | 入口周辺のみ観測する |
| `full_site` | 全 in-scope URL を被覆する (per-run 有界 + multi-run resume で全 URL へ到達) |

- **scope 分類 (C12 が SSOT)**: C09 が discovery した URL 群を、system 関連 (same-origin + 明示承認 related
  origin) = `in_scope`、アフィリエイト/広告/外部 SNS/トラッカー/utm 付き外部リンク = `excluded` (reason 付き) に
  **fail-closed 分類**する (判定不能は `excluded`)。
- **multi-run resume**: full_site は 1 run で全部取り切らず、per-run 有界予算内で観測し、未到達 URL を site
  coverage manifest の `pending` に残す。再開 run は `--resume` で前 run の manifest を C12 `--coverage-manifest-in`
  へ渡し、`pending` と未分類 discovered を分類対象へ再投入する (writer=C11 / reader=C12)。
- **瞬間負荷レバーは両モード不変**: 対象 origin 並列 **1**・最小間隔 **2000ms**・`Retry-After` 尊重・有界
  backoff・停止条件 (429/403/robots-deny/budget-exhausted/unstable-response) を single/full_site で緩めない。
  per-run 既定予算の**引き上げはユーザー承認対象**。

## 4. 観測カバレッジ (visual formation field 一覧)

C03 は主要画面ごとに、以下の **visual formation カテゴリ**を provenance 付き fact として採取する
(未取得 field は欠落させず `not_observed` + reason)。

| カテゴリ | 主な内容 |
|---|---|
| `identity` | element_id / parent_id / locator / tag / role / accessible_name |
| `geometry` | bounding_box (px / normalized) / intrinsic_size / box model (margin/border/padding) |
| `layout` | display / position / z_index / stacking_context / flex / grid / gap / overflow / sticky-fixed |
| `paint` | 前景/背景色 / gradient / border / radius / shadow / opacity / filter / caret/accent/selection/scrollbar 色 / 色値の正準表現 (hex8 + gamut) |
| `typography` | font_family / fallbacks / font_source (provider/src) / size / weight / line_height / letter_spacing |
| `media` | asset_type / src(hash) / srcset / object_fit / svg_viewbox / icon_label |
| `effects` | transform / clip_path / mask |
| `pseudo_elements` | before / after / marker / placeholder / selection |
| `state` | default / hover / focus / active / disabled / checked / validation / cursor |
| `motion` | transition / animation / keyframe_summary / prefers_reduced_motion |
| `responsive` | viewport_profile / breakpoint or container change / profile 差分 |
| `a11y` | semantic_role / focus_order / hit_target_size / contrast_ratio |
| `tokens` | css_custom_properties / resolved_design_tokens |

> **静的 baseline の限界と browser-render 補完**: 上表のうちレンダリング/JS 実行/computed style を要する
> field (`geometry` の `bounding_box (px)`・`state` の hover/focus/active・`motion` の実 animation・実ピクセル
> 描画) は stdlib 静的経路では取得できないが、**任意の headless Chrome 経路 (2.3) が使える環境では
> browser-render が rendered fact 化する**。ブラウザ不在時のみ `observation_gap` (`observation_status: blocked`,
> reason=`browser-unavailable`。純静的 baseline のみの gap は reason=`static-analysis-only`) として記録する。
> CWV は field/RUM 計測必須でいずれの経路でも取得できず gap のまま残す。宣言由来で取れる field
> (tag/role/accessible_name・宣言色・font トークン・宣言 layout プロパティ・a11y semantic 等) は静的
> baseline で fact として採取する。

- **coverage manifest**: 画面 → region → 主要 element の階層で **対象数 / 抽出数 / not_observed 数**を示し網羅率を追跡する。
- **gap の扱い**: budget 枯渇・429/403・robots-deny・レンダリング必須 field の静的解析限界・canvas/WebGL/closed
  shadow DOM は **無言欠落させず** `not_observed` / `observation_gap` / `site_inventory.pending` に理由付きで
  記録する。観測済み鍵画面の無言欠落は C9 FAIL。

## 5. 参考/学習目的限定

- 本 plugin は参考システムの**公開情報の低負荷観測**に限る。認証必須領域・認可外 origin へアクセスしない。
- 生成物 (各正本) には**参考/学習目的限定**の注記を焼く。
- security 推測は**受動観測のみ** (侵入テスト/脆弱性スキャン/認証突破は行わない。C04 / OWASP レンズの guard)。

## 関連

- 原則レンズ: [`expert-lens-roster.md`](expert-lens-roster.md)
- 認可 preflight / scope 分類: `$CLAUDE_PLUGIN_ROOT/scripts/authz-classify.py`
- 取得 / URL discovery / 静的観測 emit: `$CLAUDE_PLUGIN_ROOT/scripts/fetch-snapshot.py`
- ブラウザ情報取得 (任意・headless Chrome CLI): `$CLAUDE_PLUGIN_ROOT/scripts/browser-render.py`
- fail-closed 境界 (fetch-authz): `$CLAUDE_PLUGIN_ROOT/hooks/pre-fetch-authz-guard.py`
