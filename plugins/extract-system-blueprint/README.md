# extract-system-blueprint

参考システムの公開 URL を**認可・低負荷 budget 内**で調査し、フロント表層の**事実 (fact)** とバックエンド/設計意図の**根拠+確度つき推測 (inference)**、そして**欠測 (observation_gap)** を明示区別した設計ブループリント (md + json + Mermaid5種 + (browser-render 取得時) rendered DOM/screenshot + 画面別 layout/overlay + 合成 design-tokens + サイト被覆 manifest + request ledger) を**ローカルへ**生成する plugin。成果物はローカル完結で、外部サービスへは公開しない。

> **参考/学習目的限定**。本 plugin は参考システムの**公開情報の低負荷観測**に限る。認証必須領域への無断到達・実侵入・認可外スクレイピング・脆弱性スキャンは行わない (認可 preflight `authz-classify.py`=C12 が allow した範囲外は fail-closed hook `pre-fetch-authz-guard.py`=C08 が機械層で遮断する)。生成物 (各正本) には参考/学習目的限定の注記を焼く。

---

## Part1 — この plugin は何を解決するか (概念)

気になる Web サービスを「どう作られているか」参考にしたいとき、これまではブラウザで目視し、F12 開発者ツールで通信や DOM を1つずつ確認する手作業が必要でした。この plugin は、**URL を1つ渡すだけ**でその作業を代行し、後から人にも AI にも読める「設計ブループリント」を作ります。

ブループリントで一番大事なのは、書かれている内容を **3 種類にきっちり分けている**ことです。

- **事実 (fact)** — 実際に見えたもの。ボタンの色、画面の並び、宣言されている遷移先や form の送信先など。「どこで・いつ・どう観測したか」の出所 (provenance) が必ず付きます。
- **根拠つき推測 (inference)** — 見えたものから「たぶんこうだろう」と考えた設計意図。バックエンドの仕組みなど。**必ず根拠 (evidence) と確度 (confidence) が付き**、断定はしません。
- **欠測 (observation_gap)** — 見られなかったもの。「ログインが必要で見えなかった」など理由付きで正直に記録し、勝手に推測で埋めません。

この 3 分けにより、生成物を AI へ渡すと**追加のヒアリングなしで「自社版のたたき台 (scaffold)」の生成に着手できる**粒度になります。「事実だから真似できる/推測だから検証が要る/欠測だから調べ直す」を読み手が判断できる、というのが核心の価値です。

さらに、出来上がったブループリントは `run-blueprint-apply` (C14) に渡すと、自社の技術スタックや制約に照らして「採用 (adopt) / 回避 (avoid) / 差別化機会 (differentiate)」の 3 分類の適用提案へ変換できます (ローカル生成に限ります)。

---

## 使い方 (install / setup)

### install

marketplace 配布 plugin (`distributable: true`)。導入経路は 3 つ。

| 経路 | 手順 |
|---|---|
| marketplace | プラグインマーケットプレイスから `extract-system-blueprint` を追加する |
| CLI | `claude plugin` で marketplace 追加後に本 plugin を install する |
| Desktop | Desktop アプリのプラグイン設定から `extract-system-blueprint` を有効化する |

> **現行ステータス**: 配布登録は manual-user-gated で、現在 marketplace/bundles **未登録** (登録は [`ROADMAP.md`](ROADMAP.md) 短期のユーザー承認後作業)。登録完了まで上記 3 経路は使えず、**ローカル導入 (リポジトリ clone + `.claude` symlink)** が現行経路。

install 後の起動名は通常 `/extract-system-blueprint:extract-blueprint` (ローカル開発時は `/extract-blueprint`)。

### setup (初回設定)

外部サービス連携・MCP server・API トークンは**不要**。観測は stdlib Python (`html.parser` + `urllib`、外部ライブラリ導入なし) による保存済み HTML と linked CSS の**静的 DOM/HTML/CSS 解析を常時 baseline** とし、これに**任意のローカル headless Chrome (下記「setup (任意)」) の rendered fact を上乗せする両方併用**で行う (どちらもローカル完結・外部公開なし)。成果物は**ローカルのみ**へ生成する。詳細な運用手順は [`references/runbook.md`](references/runbook.md) を正本とする (ここでは要点のみ)。

- **静的観測 (stdlib)** — `fetch-snapshot.py` (C09) が低負荷取得した HTML と linked CSS から `static-observation.json` (要素ツリー / 見出し階層 / nav・link / form / meta・OGP・JSON-LD / 宣言色 / font トークン / a11y semantic 等) を emit し、C03 (`frontend-surface-analyzer`) がそれを provenance 付き fact 化する。
- **レンダリング必須観測は捏造しない** — 実ピクセル描画・CWV (LCP/CLS/INP/TTFB)・JS 実行後 DOM・computed 幾何 (`bounding_box_px`)・hover/focus state は stdlib (静的経路) では取得できないため、`observation_gap` (`observation_status: blocked`, reason=`static-analysis-only`) として正直に記録する (fact/inference へ昇格させない)。ただし**任意の headless Chrome 経路** (下記「setup (任意): ブラウザ情報取得」) が使える場合は JS 実行後 DOM・screenshot 等をこの経路で fact 化できる。

### setup (任意): ブラウザ情報取得 (headless Chrome — MCP ではない)

JS 実行後 DOM・viewport screenshot など**ブラウザがレンダリングした情報**は、**ローカルにインストールされた headless Chrome/Chromium を Bash 経由 subprocess で起動**する `scripts/browser-render.py` (CLI) で取得する。本 plugin は **MCP サーバー接続を一切持たない** — ブラウザ取得は「Bash 経由 headless Chrome CLI」であって MCP ではない。これは上記の静的観測 (stdlib/WebFetch) の上に載る **progressive enhancement** で、あれば rendered fact が増え、無ければ静的観測のみで続行する。

- **用意 (任意依存)** — OS の一般的な入手経路で Chrome/Chromium バイナリを導入する (macOS の Homebrew `chromium`、Linux の `chromium` / `google-chrome` パッケージ、公式ビルド等)。バイナリは `--browser-bin <path>` または env `ESB_BROWSER_BIN` で明示でき、未指定時は PATH 上の `chromium` / `google-chrome` 等を探索する。
- **無い場合の graceful 縮退** — バイナリを解決できない環境 (CI・最小コンテナ等) では browser-render は **exit 3 (browser-unavailable)** を返し、該当観測は `observation_gap` (`observation_status: blocked`, reason=`browser-unavailable`) として記録され、plugin は静的 HTTP 観測 (WebFetch + `urllib` snapshot) のみで続行する。
- **認可・低負荷は不変** — browser-render の URL を含む Bash 呼びも C08 fetch-authz hook の認可境界で捕捉され、browser-render 自身も C12 (`authz-classify.py`) の `decide()` を import 共有して二重に fail-closed。低負荷レバー (対象 origin 並列 1・最小間隔 2000ms・timeout・`Retry-After` 尊重) は静的観測と共通で不変。remote font 由来の headless ハングは `--disable-remote-fonts --virtual-time-budget` で回避する。出力は `rendered/<host>.rendered.html` (JS 実行後 DOM) と `rendered/<host>.screenshot.png` (viewport screenshot)。起動例・exit コードは [`references/runbook.md`](references/runbook.md) を正本とする。

---

## 代表タスク 6 雛形

いずれも入口は薄いラッパ command [`commands/extract-blueprint.md`](commands/extract-blueprint.md)。成果物は**ローカル完結**で外部公開はしない。draft の完成可否 (PASS/FAIL) は独立評価器 C02 の品質 verdict が決める。

| # | やりたいこと | コマンド雛形 |
|---|---|---|
| 1 | 入口 URL 1 件の表層抽出 (ローカル draft) | `/extract-blueprint https://example.com` |
| 2 | サイト全域を被覆して抽出 | `/extract-blueprint https://example.com --crawl-mode full_site` |
| 3 | 中断した full_site 抽出を再開 (multi-run resume) | `/extract-blueprint https://example.com --crawl-mode full_site --resume` |
| 4 | draft の独立品質 verdict を得る (公開はしない) | `/extract-blueprint https://example.com` を実行すると Step2 で C02 が独立品質 verdict を自動発行する |
| 5 | 抽出結果を自社開発へ適用 (採用/回避/差別化) | `/run-blueprint-apply <blueprint-dir> <自社コンテキストのパスまたは自然文>` (install 後は `/extract-system-blueprint:run-blueprint-apply` 相当。[`skills/run-blueprint-apply/SKILL.md`](skills/run-blueprint-apply/SKILL.md)) |
| 6 | 分析レンズ (著名エンジニア原則) を差し替える | [`references/expert-lens-roster.md`](references/expert-lens-roster.md) を編集し analyzer sub-agent のレンズ見出しを更新する |

> タスク 4 の補足: この command は公開フラグを持たない。Step1 でローカル draft を生成 → Step2 で独立品質 verdict → 報告、の順序で完結する (外部公開の Step は無い)。verdict=PASS は draft 完成扱い、FAIL は runtime の request budget をリセットしないまま有界に差し戻す (bounded handback)。詳細は [`commands/extract-blueprint.md`](commands/extract-blueprint.md) の「順序保証」節。

---

## Part2 — 生成物の読み方 (技術)

運用者・レビュアー向け。フィールドの詳細一覧・被覆の追い方は [`references/runbook.md`](references/runbook.md) を正本とし、ここでは**確度スキーマの読み方**を中心に要約する。

### fact / inference / observation_gap 三値スキーマ

正本 schema: [`schemas/fact-inference-confidence.schema.json`](schemas/fact-inference-confidence.schema.json)。この 3 値は**相互排他**で、混同されていたら C02 が FAIL にする。

| 種別 | 読み方 (何を確認するか) | 必須フィールド |
|---|---|---|
| `fact` | 実際に観測されたもの。レンズ解釈を含めない | `provenance` (source_url / locator / captured_at / method / snapshot_id) |
| `inference` | 根拠から導いた推測。断定でなく確度で読む | `claim` + `evidence_refs` (≥1) + `confidence{level ∈ high/medium/low, rationale}` |
| `observation_gap` | 見られなかったもの。埋めずに理由を読む | `not_observed`\|`blocked` + `reason` + `budget_state` |

読み手の指針: **fact は出所を辿れば再現でき、inference は evidence_refs と confidence.level で確からしさを測り、gap は「まだ調べていない箇所」として扱う**。inference の confidence が `high` の主張には複数の直接根拠が求められる (anti-overfit)。実在個人/組織を代弁する主張 (「〜氏はこう設計する」) が fact レーンに混入していると FAIL — 必ず根拠つき inference へ落ちる。

top-level のブループリント形状 (`screens[]` / `design_tokens` / `tech_stack` / `essence` 等) は [`schemas/system-blueprint.schema.json`](schemas/system-blueprint.schema.json) が正本。

### 静的観測と visual formation

主要画面ごとに、保存済み HTML と linked CSS から得た**静的観測** (`static-observation.json`) をもとに `layout.json` / 番号付き注釈 overlay を生成し、宣言色・タイポグラフィ・宣言レイアウト構造・a11y semantic など **visual formation カテゴリ** (identity / geometry / layout / paint / typography / media / effects / pseudo_elements / state / motion / responsive / a11y / tokens) のうち**宣言由来で取れる field** を provenance 付き fact として記録する。ただし**レンダリング必須の field** (computed 幾何 `bounding_box_px` / hover・focus 等の動的 state / 実ピクセル描画) は stdlib 静的経路では取得できないが、**任意の headless Chrome 経路 (browser-render) が使える環境では rendered fact 化され**、ブラウザ不在時のみ無言欠落させず `observation_gap` (`observation_status: blocked`, reason=`browser-unavailable`。純静的 baseline のみの gap は reason=`static-analysis-only`) として記録する (fact/inference へ昇格させない)。CWV は field/RUM 計測必須でいずれの経路でも取得できず gap のまま残す。合成 design-tokens は観測した宣言色を漏れなく被覆する (孤児 0)。full_site の scope 分類 (in_scope / excluded+reason)・feature_map / user_journeys 章・security_design 章 (**受動観測のみ・侵入テスト非実施**の限界明記)・delivery_topology の読み方は [`references/runbook.md`](references/runbook.md) に一覧がある。

### ローカル draft 品質ゲート (C02)

品質判定は **proposer ≠ approver** で二重に守られる (外部公開ゲートではなく draft 品質のゲート)。

1. 生成器 C01 (`run-extract-blueprint`) は自己評価で完成宣言しない。ローカル draft を固めて `draft_hash` を確定する。
2. 独立 context の評価器 C02 ([`skills/assign-blueprint-fidelity-evaluator/SKILL.md`](skills/assign-blueprint-fidelity-evaluator/SKILL.md)) が `draft_hash` に束縛した品質 verdict (PASS/FAIL) を発行する。
3. **verdict=PASS かつ draft_hash 一致のとき** draft は完成扱いとなり、下流 C14 (`run-blueprint-apply`) の apply 入力ゲートを通過する。FAIL / hash 不一致は下流適用へ進めず、request budget を非リセットで有界に差し戻す。

生成本体の詳細は [`skills/run-extract-blueprint/SKILL.md`](skills/run-extract-blueprint/SKILL.md) を参照。

---

## 構成 (14 component)

| 種別 | 数 | 実体 |
|---|---|---|
| skill | 3 | `run-extract-blueprint` (C01・抽出本体) / `assign-blueprint-fidelity-evaluator` (C02・独立評価器) / `run-blueprint-apply` (C14・自社適用) |
| agent | 5 | `frontend-surface-analyzer` (C03) / `backend-inference-analyzer` (C04) / `uiux-rationale-analyzer` (C05) / `content-intent-analyzer` (C13) / `architecture-essence-synthesizer` (C06) |
| command | 1 | `extract-blueprint` (順序保証つき薄いラッパ) |
| hook | 1 | `pre-fetch-authz-guard.py` (C08・fetch-authz 単一述語の fail-closed hook。matcher=`Bash`\|`WebFetch`) |
| script | 4 | `authz-classify.py` (C12) / `fetch-snapshot.py` (C09) / `mermaid-validate.py` (C10) / `doc-emit.py` (C11) |

共有スキーマ: [`schemas/fact-inference-confidence.schema.json`](schemas/fact-inference-confidence.schema.json) / [`schemas/system-blueprint.schema.json`](schemas/system-blueprint.schema.json) / [`schemas/goal-seek-loop.schema.json`](schemas/goal-seek-loop.schema.json)。

決定論ゲート `mermaid-validate.py` (C10) と `doc-emit.py --check-screens` (C11) は C01 の自己検証と C02 の独立評価で**同一ロジックを共有** (基準統一) しつつ、C02 は非共有の再計数経路 (`recount-palette-orphans.py`) を 1 本通して common-mode 誤りを排除する。

---

## 関連ドキュメント

- 運用手順 (install/setup/run/被覆/観測フィールド一覧): [`references/runbook.md`](references/runbook.md)
- 分析レンズ (著名エンジニア原則ロスター): [`references/expert-lens-roster.md`](references/expert-lens-roster.md)
- 起動 command: [`commands/extract-blueprint.md`](commands/extract-blueprint.md)

## 改善要望 (feedback)

本 plugin への改善要望は `/run-skill-feedback extract-system-blueprint` で投入できる (`skills/run-skill-feedback/` に配備・初回は Notion sink 設定が必要)。評価基準 (feedback_contract) は量産元の harness-creator から焼き込まれる。
