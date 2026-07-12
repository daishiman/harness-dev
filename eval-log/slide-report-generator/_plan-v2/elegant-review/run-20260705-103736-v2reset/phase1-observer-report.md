# Phase 1 俯瞰レポート (elegant-reset-observer)

## 地上真実 (親が実測)
- 決定論ゲート11本すべて exit0
- plan-findings.json evaluated_inputs sha256 現ファイルと完全一致 (drift 0)
- 前回 plan-findings.json: verdict PASS / finding は info×7 のみ
→ 機械層は全緑。残余リスクは機械ゲートが原理的に見ない**意味論層**に存在。

## 第一印象の懸念点 14件 (種出し・分析官が検証する対象)

**C-1【構造矛盾・高】v1「温存・改変しない」constraint と全 build_target の in-place 上書きが正面衝突**
goal-spec constraints[0]「既存 plugins/slide-report-generator/ は温存し削除・改変しない」に対し、handoff 24 routes の build_target は全て `plugins/slide-report-generator/agents/*.md` 等 v1 実パス。consumer_steps.note は「in-place 再配置…既存ファイルへの差分適用」と明言。build すれば v1 を破壊。check-runtime-portability は接頭辞しか見ず温存 constraint と突合しない。

**C-2【核心設計・高】responsibility_anchor: prompts/*.md が v1 実体に無く、移設先(skill references/)と二重 SSOT**
inventory は 16 agent 全件に responsibility_anchor: prompts/xxx.md を宣言(例 C05)。だが v1 に prompts/ は不在で agent .md 自体がフルボディ7層。extracted_reference は skill 配下 references/。知識の正本が prompts/ か skill references/ か二重定義。

**C-3【核心設計・高】抽出方向がオーナーシップ逆転 — 既存は plugin-root 共有、新設は skill 私有**
v1 agent は既に plugin-root references/(共有46件)へ委譲済。plan は残り agent 固有知識を skill 私有 references/(共有度が低い階層)へ移す。なぜ既存46件と同じ plugin-root でなく skill-scoped か(二層 reference 体系)の根拠が薄い。

**C-4【実行時機能・高】知識を移設した薄化 agent の「非回帰」保証機構が未定義**
薄化後 agent は「役割・起動条件・I/O契約のみ」(P05)。規範が C01 の references/ に移ると fork agent がどう参照・適用して等価出力を出すか(prompt 注入か skill ref 読取か)の実行時経路が無記述。OUT1「v1 と同等入出力」は golden-output 差分検証が未設計。

**C-5【Goodhart・中高】no-split 判定が実質「行数閾値」**
no_split_threshold は ≤342=maintain / ≥410=thin-adapter(gap 68)。「maintain は抽出可能な汎用塊を持たない」は各 rationale で断定のみ。visual-strategist(328・maintain)の三択最適化や report-composer(330)の HTML 生成は再利用可能に見え、行数≠抽出可能性。

**C-6【再集中・中高】C01 が 11 抽出物中 9件(html-generation-rules 990 含む)を単一 skill に吸収**
過重 5,964行の大半が C01 references/ 一箇所へ再集中。11 agent への分散を 1 skill へ移すのは「均衡」か「山の移動」か。

**C-7【フェーズ論理・中】P05「移動のみ」と P08「重複除去」が両立しない**
P05「情報消失禁止・移動のみ」。P08 は「残留重複記述の除去」。移動なら残留重複は原理的に生じず P08 の dedup は空役務。plan-findings の post_improvement が P08 を no-op 化した疑い。

**C-8【検証の要が最未整備・中】帰属機械検証の linchpin C24 が contract-only gap**
rebalance の「機械検証可能」主張は C24(lint-reference-attribution.py)+resource-map.yaml に全依存。だが C24 は builder_status=contract-only / gap_ref=GAP-SCRIPT-BUILDER(severity high 未解決)。妥当性を保証するゲート自体が未 buildable の循環。

**C-9【計数整合・中】resource-map.md は 51件の一部 — 「51件不変」と「resource-map.md 除去」が矛盾**
handoff S-REFERENCES は「既存 51 references が変更されず維持」と「resource-map.md→yaml 完全置換(removed_files)」を同時主張。resource-map.md は直下46の1件。除去すれば「51不変」が崩れ、yaml が52件目か51内置換か未定義で off-by-one の芽。

**C-10【vendor 記述矛盾・中】render-report.js/mermaid-render.js が「新規実装」かつ「v1温存・byte維持」**
inventory C19 build_contract が同一ファイルを「新規実装」と「v1温存・byte維持」と同時記述。地上実測では両ファイルは v1 に実在。excluded_additive(parity manifest 外)なのに「byte維持」。

**C-11【scope 語彙過負荷・中】plugin-root 実体の agent が placement_scope="skill"**
16 agent+hook+command は placement_scope="skill" だが build_target は plugin-root で物理的に skill 配下でない。一方 C23/C24 script(同じ plugin-root)は "plugin-root"。同一物理階層で scope 語彙が割れる。

**C-12【テスト被覆の穴・中】最もリスクの高い agent 本体手術に専用テスト設計が無い**
P04 は 3 skill のみ criteria 設計。11 薄化 agent の非回帰は P06「既存の機能テスト」依存で per-agent golden/挙動テストは未設計。

**C-13【manifest 発信矛盾・低中】非配布なのに marketplace installation=AVAILABLE**
distribution.marketplace=false/distributable=false/bundles=[] の一方、marketplace.policy.installation=AVAILABLE/authentication=ON_INSTALL/default_personal=true。

**C-14【同一性リスク・中】v2 は slug も build_target も v1 と同一で、区別は plan_dir の -v2 のみ**
open_questions は「-v2 統合か別か未確定」を残すが build_target/slug/entry_points は完全同一。build すれば v2 は静かに v1 を上書き。「v2」は plan_dir 上の名目で独立成果物が存在しない(C-1 と連鎖)。

## メタ観察
plan-findings.json の PASS は (a) 決定論ゲート exit0 と (b) 数値2件(references 件数・agent 行数)の実測一致のみが根拠。runtime アクセス経路・抽出方向・prompts anchor 整合・move/copy・C01 集中といった設計健全性の意味論は前回 findings が一度も検分していない。

## 3分析官への割り振り示唆
- **論理構造系**: C-1, C-7, C-9, C-10, C-11, C-13, C-2(二重SSOTの依存整合)
- **メタ発想系**: C-5, C-6, C-12, C-14, C-3(前提), 前回PASS測定範囲への懐疑
- **システム戦略系**: C-4, C-8, C-3(runtime経路), C-14/C-1(build適用方式の破壊性), build_readiness/surface_tasks/open_issues waiver の実効性
