# Report 品質チェックリスト（report-quality-reviewer 検証基準 SSOT）

> **正本**: このファイルは report-quality-reviewer から抽出した手続き知識/規範の SSOT。run-slide-report-generate の SKILL.md と agent 本体（agents/report-quality-reviewer.md）の双方がこれを参照する。規則の上位素材は `${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/references/report-types.md` / `report-writing-rules.md` / `report-visual-strategy.md`、構成契約は `schemas/report-structure.schema.json` を辿る。

**責務**: report モードの品質検証ドメイン定義（用語集・評価基準・制約カタログ RQCONST_001-007）と検証基準（read-through 多面検証 MUST/SHOULD/MAY チェックリスト・必須検証基準 RQ1〜RQ34・補正指針・よくある問題と対処法）の逐語正本。report-quality-reviewer（薄化アダプタ）は役割・起動条件・I/O契約に専念し、詳細規範は本 reference を SSOT とする。本チェックリストは slide 側 `ui-quality-checklist.md`（S1〜S26 の視覚品質）＋ `layout-optimization-rules.md`（レイアウト補正）に**対応する report 版**であり、slide が「投影 HTML の視覚崩れ」を扱うのに対し report は「読み物としての成立性」を扱う。機械検出可能な項目は決定論ゲート `${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/scripts/validate-report-visual.py` に先行させ、意味検証と分離する（RQCONST_001）。

## 用語集
| 用語 | 定義 | 関連概念 |
|------|------|----------|
| 必須検証基準 RQ1〜RQ34 | report.html を read-through 成立性・構造的魅力・読者との接続の観点で確認する 34 項目の客観チェック。9 群（読み物文体・段落密度 / 1項目1ビジュアル・図解適合 / reportType 骨格・section 構造 / 見出し階層 / 印刷・letterbox / 可読性・意匠維持 / 節内構造 / 節間構造 / 読者中心の入口設計） | RQCONST_001-007 |
| 決定論ゲート | `validate-report-visual.py <report.html> [--structure …]`。同スクリプトが実検出する崩れ（1項目1ビジュアル超過 / 段落過密 / プレースホルダ・空セクション / letterbox 兆候 / 構造同期ずれ / 1.1.0-1.2.0 構造化＝羅列・強調過多・through-line・reportType横断role・render忠実度・色覚非依存）を LLM 検証に先行して確定するスクリプト（見出し階層スキップ/最小フォント/印刷px は対象外＝grep 手動 or C24 意味判定） | RQCONST_001 |
| read-through 粒度 | 投影ではなく通読を前提とした本文密度。文章多め・複数段落を許容 | `${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/references/report-writing-rules.md` |
| reportType 骨格 | 目的別に定義された節（role）の必須並び。4 型（internal-analysis/client-proposal/tech-doc/learning） | `${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/references/report-types.md` |
| 1項目1ビジュアル | 1 section の非 none visual は最大 1。図解過多を避け読解を助ける 1 点に絞る | `${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/references/report-visual-strategy.md` |
| 補正指針 | 検出した崩れに対し「問題・箇所・補正指針」を対応づけた是正案。本エージェントは read_only で指針を返し、実補正は report-composer / slide-report-modifier が行う | I/O 契約 |
| 構造同期 | report.html の内容が report-structure.json の忠実な射影であること（過不足ゼロ） | RQCONST_007 |
| 退化耐性 | コード・数値・料金・精密表など逐語が変わる要素を画像に焼かず本文（表/コード）で持つこと | slide CONST_007 相当 |

## 評価基準（ドメイン固有の判定基準）
| 基準 | 条件 |
|------|------|
| RQ1〜RQ20 合否 | 全 20 項目が客観条件を満たす=合格 / 違反=補正指針を確定（上流起因は差し戻し） |
| 機械/LLM 分離 | 機械検出可能な項目は決定論ゲートで先行確定 / 意味検証（読み物成立・段落密度品質・種別適合・骨格論理順序）は LLM が担う（RQCONST_001） |
| 段落密度 | brief=各節1-2 段落 / standard=2-4 段落 / deep=3 段落以上。1段落1論点・トピックセンテンス先行（過密/過疎は補正） |
| 1項目1ビジュアル | 各 section の非 none visual が最大 1（超過は補正 or 節分割） |
| 最小フォントサイズ | 本文最小 1.4rem 以上（read-through でも割らない） |
| コントラスト比 | WCAG 2.1 AA（4.5:1）以上で合格 / 未満は不合格 |
| 骨格順守 | 確定 reportType の必須 role が sections[] に順序通り網羅（欠落は差し戻し・省略は理由明示） |
| 補正指針ループ収束 | 補正指針の反映→再検証が 3 周以内で全基準充足=収束 / 3周で未収束=エスカレーション |

## ビジネスルール（制約カタログ RQCONST_001-007）

- **RQCONST_001 (機械検証先行ゲート)**: 決定論ゲート `validate-report-visual.py <report.html> [--structure …]` を LLM 意味検証に**先行**して実行し、**同スクリプトが実際に検出する崩れ**（1項目1ビジュアル超過 / 段落過密・オーバーフロー / 未解決プレースホルダ・空セクション / 印刷 letterbox 兆候 / 構造同期ずれ / 1.1.0-1.2.0 構造化ゲート＝羅列退化・強調過多・through-line 欠落・reportType 横断 role・render 忠実度・色覚非依存強調）を確定してから意味検証に入る。**見出し階層スキップ・最小フォント違反・印刷 px 依存は validate-report-visual.py の検査対象外**であり、RQ17 等の `grep` 手動確認または C24 の意味判定が担う（機械ゲートが担保しない項目を担保済みと誤認しない＝宣言と実装を一致させる）。
  - 目的: 機械で確定できる崩れを LLM の主観・記憶に委ねず、機械検証と意味検証を分離する。
  - 背景: The Checklist Manifesto の知見。機械層で捕れる項目を先に潰すことで、LLM は読み物成立・段落密度品質・種別適合・骨格論理順序という意味判断に集中できる。
- **RQCONST_002 (read-through 成立)**: 各 section は見出しだけで終わらせず、要点を言い切る段落を持つ。空節・箇条書きだけの節は退化。chip 強制・長文禁止を緩和した read-through 粒度を守る。
  - 目的: 「見出しと chip の羅列」ではなく「読める文書」にする。
  - 背景: report は slide の長文禁止（BP11-13）・chip 強制を緩和する。文章多めが正（`${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/references/report-writing-rules.md`）。
- **RQCONST_003 (段落密度)**: length（brief/standard/deep）に応じた段落密度を守り、1段落1論点・トピックセンテンス先行にする。過密（1 段落に論点が混在）・過疎（節が痩せる）を補正する。
  - 目的: 通読の負荷を length 相応に保ち、論点を追える文書にする。
  - 背景: report-writing-rules §2.1 段落・§2.3 length 方針。
- **RQCONST_004 (1項目1ビジュアル・図解過多回避)**: 1 section の非 none visual は最大 1。全節に図解を付ける図解過多を避け、要る節に 1 点、文章で足りる節は none にする。
  - 目的: 読解を助ける 1 点に絞り、装飾過多で本文が痩せるのを防ぐ。
  - 背景: report-visual-strategy §2。複数図が欲しくなったら情報過密のサインとして節分割を検討する。
- **RQCONST_005 (reportType 骨格順守)**: 確定 reportType の必須 role を sections[] に網羅し、論理順序（背景→結論 / 前提→手順 / 問い→まとめ）を崩さない。骨格節を省く場合は省略理由を明示する（無言の省略はしない）。
  - 目的: 読者が文脈（背景・前提）を得た上で結論・手順へ到達できるようにする。
  - 背景: report-types §5「順序保持は絶対」。骨格欠落は上流起因として report-structure-designer へ差し戻す。
- **RQCONST_006 (意匠維持ライン)**: 本文最小 1.4rem・Kanagawa 配色（純黒/純白回避）・印刷 CSS・退化耐性（逐語を画像に焼かない）を維持する。配色・フォント・印刷 CSS は共有 SSOT から適用し report 独自に発明しない。
  - 目的: slide/report の意匠を単一 SSOT に保ち、可読性下限と退化耐性を両モードで共通化する。
  - 背景: report-writing-rules §3 維持ライン。緩和するのはコンテンツ意図層のみ、意匠/技術層は共有（build-contract §D）。
- **RQCONST_007 (構造同期)**: report.html は report-structure.json の忠実な射影で過不足ゼロにする。勝手に節を増減しない。
  - 目的: 承認済み構造からの逸脱を防ぐ。
  - 背景: 構造化データ先行。生成は構造の忠実な射影であり、同期崩れは report-composer へ差し戻す。

## read-through 多面検証チェックリスト（MUST / SHOULD / MAY）

出力の「品質基準（出力に必ず含む必須フィールド）」を満たすため、以下の多面検証チェックリストを全件消化する。

必須（MUST）読み物成立・骨格:

- [ ] 各 section に空でない段落があり、見出しだけの空節が 0 件（RQCONST_002）
- [ ] length（brief/standard/deep）相応の段落密度で、1段落1論点・トピックセンテンス先行（RQCONST_003）
- [ ] 各 section の非 none visual が最大 1 で、図解過多になっていない（RQCONST_004）
- [ ] 確定 reportType の必須 role が sections[] に順序通り網羅されている（RQCONST_005）
- [ ] 骨格節を省く場合は省略理由が本文冒頭の断り等で明示されている（RQCONST_005）
- [ ] report.html が report-structure.json の忠実な射影で過不足ゼロ（RQCONST_007）

必須（MUST）意匠・可読性:

- [ ] 本文最小 1.4rem 以上（read-through でも割らない・RQCONST_006）
- [ ] WCAG AA（コントラスト比 4.5:1 以上）を満たす
- [ ] Kanagawa 配色で純黒（#000000）・純白（#FFFFFF）を本文に使っていない
- [ ] 配色・フォント・印刷 CSS を共有 SSOT から適用し report 独自発明がない（RQCONST_006）
- [ ] コード・数値・料金・精密表を画像に焼かず本文（markdown 表/コードブロック）で持つ（退化耐性）

必須（MUST）構造・レイアウト:

- [ ] h1（タイトル）→ h2（section 見出し）→ h3（下位）の見出し階層がスキップなしで整合
- [ ] 各読み単位が「見出し＋段落＋最大1ビジュアル＋callouts」の構造を保つ
- [ ] A4/レター読み物レイアウト（縦スクロール）で report を 16:9 letterbox に強制していない
- [ ] 印刷 CSS が共有 SSOT トークン（mm/rem・px 依存なし）で適用され印刷時に本文・図が欠落しない

推奨（SHOULD）:

- [ ] 各 visual.kind が内容適合（一次判定/tie-break で説明可能・rationale 記載）
- [ ] readingOrder が 1 方向に統一・focalPoint が同じ高さ帯に揃っている（配置一貫性）
- [ ] 注意点/警告が callouts（note/warning/tip/caution）で目立たせられている
- [ ] 強調（`**…**`）が要点に限られ乱用されていない
- [ ] 見出しが内容を表す自然な長さで、折り返し前提で成立している

任意（MAY）:

- [ ] 参照リンク（外部仕様・出典）が付されている
- [ ] 目次・アンカーで長文の可読性が補助されている
- [ ] 印刷用の改ページ位置が節境界に整っている

## 検証基準（必須検証基準 RQ1〜RQ34）

各基準は第三者が合否判定できる客観条件で記述し、agent の完了チェックリスト（5.3）はこれらを全件消化することで充足する。決定論ゲートで機械検出可能な項目（検出方法欄に「機械」を付記）は LLM 意味検証に先行して確定する（RQCONST_001）。

### A 群: 読み物文体・段落密度（RQ1〜RQ4）

| # | 検証項目 | 基準（検証可能条件） | 検出方法 |
|---|---------|------|----------|
| RQ1 | 空節ゼロ | 各 section.paragraphs[] が空でなく要点を言い切る。見出しだけの空節が 0 件 | report.html の各 section 内 `<p>` 有無を確認（機械＋意味） |
| RQ2 | 段落密度上限 | length に応じた段落数（brief=各節1-2 / standard=2-4 / deep=3+）を大きく超過/下回らない | 各 section の段落数を length と照合（意味） |
| RQ3 | 1段落1論点 | 各段落の先頭にトピックセンテンス、論点混在なし | 段落先頭文と後続文の論点一致を確認（意味） |
| RQ4 | 長文自然性 | slide の 20 字 `<br>` 強制を適用せず段落として自然に書けている（chip 強制で痩せていない） | 段落中の不自然な `<br>` 連発の不在を確認（機械＋意味） |

### B 群: 1項目1ビジュアル・図解適合（RQ5〜RQ8）

| # | 検証項目 | 基準（検証可能条件） | 検出方法 |
|---|---------|------|----------|
| RQ5 | 1項目1ビジュアル | 各 section の非 none visual（svg/mermaid/codex-image）が最大 1 | section 内のビジュアル要素数をカウント（機械） |
| RQ6 | 図解過多回避 | 全 section に図解を付けていない。文章で足りる節は none | none section の存在と図解偏在を確認（意味） |
| RQ7 | 種別適合 | visual.kind が内容適合（構造=svg/mermaid・情感=codex-image・論述=none の一次判定に整合）で rationale がある | report-structure.json の visual.kind と rationale を照合（意味） |
| RQ8 | 退化耐性 | コード・数値・料金・精密表を画像に焼いていない（本文の表/コードで持つ） | 画像 alt/caption と本文表・コードブロックの所在を確認（機械＋意味） |

### C 群: reportType 骨格・section 構造（RQ9〜RQ12）

| # | 検証項目 | 基準（検証可能条件） | 検出方法 |
|---|---------|------|----------|
| RQ9 | 骨格網羅 | 確定 reportType の必須 role が sections[] に 1 つ以上ずつ写像されている | reportType の必須 role 集合と sections[].role を照合（機械） |
| RQ10 | 骨格順序保持 | role の論理順序（背景→結論 / 前提→手順 / 問い→まとめ）を崩していない | sections[].role の並びを骨格順と照合（意味） |
| RQ11 | 省略明示 | 骨格節を省く場合、省略理由が本文冒頭の断り等で明示されている（無言の省略なし） | 欠落 role に対する断り書きの有無を確認（意味） |
| RQ12 | section 構造 | 各読み単位が「見出し＋段落＋最大1ビジュアル＋callouts」の構造を保ち、注意点/警告が callouts で表現 | section の構成要素と callouts 使用を確認（機械＋意味） |

### D 群: 見出し階層（RQ13〜RQ14）

| # | 検証項目 | 基準（検証可能条件） | 検出方法 |
|---|---------|------|----------|
| RQ13 | 見出し階層整合 | h1（タイトル）→ h2（section 見出し）→ h3（下位）がスキップなしで整合（h2 の直下で h4 に飛ばない） | `grep "<h[1-6]"` で見出しレベルの並びを確認（機械） |
| RQ14 | 見出し自然長 | 見出しが内容を表す自然な長さ（slide の最大文字数・改行位置ルールは非適用） | 見出しテキスト長と内容表現性を確認（意味） |

### E 群: 印刷・letterbox（RQ15〜RQ16）

| # | 検証項目 | 基準（検証可能条件） | 検出方法 |
|---|---------|------|----------|
| RQ15 | read-through レイアウト | A4/レター読み物レイアウト（縦スクロール）で report を 16:9 letterbox に強制していない（letterbox は slide 固有） | `aspect-ratio: 16/9` 等の letterbox 強制の不在を確認（機械） |
| RQ16 | 印刷品質 | 印刷 CSS が共有 SSOT トークン（mm/rem・px 依存なし）で適用され、印刷時に本文・図が欠落しない | `@media print` の単位（px 依存の不在）とレイアウトを確認（機械） |

### F 群: 可読性・意匠維持（RQ17〜RQ20）

| # | 検証項目 | 基準（検証可能条件） | 検出方法 |
|---|---------|------|----------|
| RQ17 | 最小フォント | 本文相当テキストが 1.4rem 以上（read-through でも割らない） | `grep "font-size:[0-9.]*rem"` で 1.4rem 未満を検出（機械） |
| RQ18 | コントラスト | WCAG AA（4.5:1）以上、Kanagawa 配色で純黒/純白を本文に使わない | 前景背景の色差を確認、`#000000`/`#FFFFFF` の本文使用を検出（機械＋意味） |
| RQ19 | 意匠共有 | 配色・フォント・印刷 CSS を共有 SSOT から適用し report 独自発明がない | 意匠トークンが共有 SSOT 由来か確認（意味） |
| RQ20 | 構造同期 | report.html が report-structure.json の忠実な射影で過不足ゼロ（勝手な節の増減なし） | sections 数と各 section 内容を report.html と照合（機械） |

### G 群: 積極評価 — 構造化された読み物としての魅力（RQ21〜RQ26・1.1.0）

> A〜F 群が「破綻していないか」の減点型なのに対し、G 群は「構造化された読み物として魅力的か」を **積極評価** する。『羅列でも破綻ゼロなら PASS』と『構造過剰・強調過多でも多様性ありなら PASS』の**双方向**を塞ぐ。機械層（`validate-report-visual.py` の C6）が下限・上限を検出し、意味の正否は本レビュアが判定する（二層分離）。正本は [report-narrative-logic.md](report-narrative-logic.md)。

| # | 検証項目 | 基準（検証可能条件） | 検出方法 |
|---|---------|------|----------|
| RQ21 | 節内論理展開の成立 | 各節に narrative（本質課題→解決→活用 / logic）があり、heading の言い換えでなく本質を突いている | `section.narrative` の有無（機械）＋ essence が本質課題か（意味） |
| RQ22 | block 構造多様性 | 対照は table・手順は ordered-list・コードは code で表現し、本文へ流し込んでいない（1.1.0 は原則 body[] 使用・全節 paragraph-only は羅列の兆候） | body[] の block 型分布（機械）＋ 内容適合（意味） |
| RQ23 | 要点強調の効き | 要点が `==…==`（1段落1箇所）/ key-point（1節0〜1個）で強調され、読者が結論を掴める | mark/key-point の存在（機械）＋ 強調対象が真の要点か（意味） |
| RQ24 | 強調・構造の非過剰 | 強調過多・block 過剰で読み物が断片化していない（節あたり highlight ≤6・key-point ≤2） | validate-report-visual C6 の上限 warn（機械）＋ 断片化の印象（意味） |
| RQ25 | 図解の意味的配置 | 図が段落末尾全幅固定でなく、該当説明の隣（`visual.layout.grid` 2カラム等）へ意味的に配置され、図表番号・キャプションで相互参照可能 | placement/caption の反映（機械）＋ 配置の妥当性（意味） |
| RQ26 | 横断要素の充足 | reportType 別の本質的横断要素（要約/テイクアウェイ/次アクション/根拠出典/リスク留保、型別=前提/用語/手順/学習目標/演習 等）が揃っている | report-narrative-logic §4 のカタログと照合（意味） |

**RQ9・RQ20 に違反（骨格欠落・構造同期崩れ）がある場合、上流起因として report-structure-designer / report-composer へ差し戻す。RQ21〜RQ26（積極評価）に違反する場合は「構造化が薄い / 強調が過剰」の補正指針を上流（report-structure-designer）へ返す。その他の RQ 違反は補正指針を返し report-composer / slide-report-modifier が適用する。**

### H 群: 積極評価 — through-line・色覚非依存・横断要素・適合性優先（RQ27〜RQ30・1.2.0）

> G 群（1.1.0）が**節内**の構造化（narrative・block・強調）を積極評価するのに対し、H 群（1.2.0）は軸を足す: **節間**の論理接続（through-line）、色に依存しない強調（色覚非依存）、型別横断要素の**意味的**充足、block 多様性の水増しでなく**適合性優先**。機械ゲート C25（`validate-report-visual.py`）は「構造の存在／render 忠実度」だけを決定論検査し、**意味の正否（論理が本質を突くか・要約が本当に要約か）は C24 report-quality-reviewer の意味判定が担う**（二層分離）。正本は [report-narrative-logic.md](report-narrative-logic.md)。

| # | 検証項目 | 基準（検証可能条件） | 検出方法 |
|---|---------|------|----------|
| RQ27 | through-line（節間論理・弧） | `meta.throughLine`（通し筋）→本論→結の弧が成立し、節が飛び石でなく `section.transition` が節間を橋渡ししている（heading 羅列でなく主張線が通る） | throughLine/transition の存在（機械 C25）＋ 通し筋が実際に節を貫き transition が論理接続を果たすか（意味） |
| RQ28 | 色覚非依存の強調 | 要点強調 `==…==` が色単一チャネルでなく font-weight/underline 等の非色第2チャネルを併存し、色覚特性に依存せず要点が判別できる | highlight の非色チャネル併存（機械 C25）＋ 色を抜いても要点として立つか（意味） |
| RQ29 | reportType 横断要素の意味的充足 | 型別の本質的横断要素（共通=要約/テイクアウェイ/次アクション/根拠出典/リスク留保/TL;DR＋文書メタ〈version/updatedDate/readingTime/audience〉、型別=前提/用語/手順/学習目標/演習/argument 等）が、role の存在だけでなく内容が実際にその役割を果たす形で揃っている | role・文書メタの存在（機械 C25）＋ 要約が本当に要約か・次アクションが実行可能かの意味充足（意味・report-narrative-logic §4 照合） |
| RQ30 | 多様性 < 適合性 の優先 | block 種類の水増しを加点せず、内容が要求する構造への適合を評価する。全 paragraph の羅列だけを減点し、無意味な block 多様化は加点しない。narrative 不要な role（reference/procedure/summary）へ弧を強制するのは category error として要求しない（analysis/argument は narrative 必須） | 全 paragraph 羅列の下限検出（機械 C25）＋ 構造が内容要求に適合するか・多様化が意味を持つか・role 別 narrative 要否が正しいか（意味） |

**RQ27〜RQ30（1.2.0 積極評価）に違反する場合は「節間の流れが弱い / 強調が色依存 / 横断要素が意味的に欠落 / 構造が内容に不適合」の補正指針を上流（through-line・横断要素・適合性は report-structure-designer、色覚非依存の第2チャネルは report-composer / render）へ返す。多様性の水増しは加点せず、羅列だけを減点する（適合性 > 多様性）。**

### I 群: 積極評価 — 読者中心の入口設計（RQ31〜RQ34・1.3.0）

> G 群が**節内**、H 群が**節間**の構造化を積極評価するのに対し、I 群（1.3.0）は**読者との接続スケール**を評価する。入口（タイトル・throughLine・冒頭要約）が、想定読者の範囲内で共有される課題と得たい変化から開き（入口ホリゾンタル）、本文が専門の深さを保つ（中身バーティカル）かを見る。対象読者そのものを広げる評価ではなく、正式名称・検索性・適用範囲との両立も含む。本軸は**機械ゲート対象外**（C25 変更なし）で全項目を意味判定が担う（機械が担保しない項目を担保済みと誤認しない＝RQCONST_001 と同じ規律）。正本は `${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/references/report-narrative-logic.md` §7。

| # | 検証項目 | 基準（検証可能条件） | 検出方法 |
|---|---------|------|----------|
| RQ31 | 入口ホリゾンタル | タイトル・throughLine・冒頭要約が、想定読者の範囲内で共有される課題と「読者が得る変化」を先に渡す。専門手段だけを主語にせず、不要な属性スタックを置かない。正式名称・検索語・適用範囲が必要な文書は主タイトルに残し subtitle/keyMessage/summary で読者価値を補う | audience / reportType / タイトル / throughLine / 導入節を照合（意味） |
| RQ32 | 自分ごと化 | 第1段落が読者の状況・判断から開き、書き手の資格・専門自己紹介で始まらない。各主要 part / 節に「当てはまる兆候・判断の問い・選択肢・次の行動」のいずれかがあり、読者が自分へ移せる | 導入段落の視点と主要 part / 節の transfer bridge を確認（意味） |
| RQ33 | 変化の可視化と誠実さ | Before→After が冒頭または summary 節で提示され、数字・実績は入力素材または出典で裏づけられている。根拠がない場合は定性的変化として述べ、架空の数字・過大な約束にしていない | 冒頭・summary・出典・入力素材を照合（意味） |
| RQ34 | 広い入口×深い中身 | 入口のホリゾンタル化の代償に本論の深さ（確認済みの数字・手順・失敗・再現条件・適用限界）が薄まっていない。一般論化も、本文が支えられない大きな約束もない | analysis / solution / procedure / caution 節と出典の具体性を確認（意味） |

**RQ31〜RQ33 に違反する場合は「入口が専門側から開いている / 読者の変化または自分へ移す橋が見えない / 約束の根拠がない」の補正指針を上流（report-structure-designer＝title・throughLine・summary 節の設計）へ返す。RQ34（深さの薄化）は、承認済み構造・入力素材にある詳細の射影漏れなら report-composer へ、構造または素材自体が不足するなら report-structure-designer / hearing-facilitator へ返す。正式名称・検索性・適用範囲を壊すタイトル変更や、素材にない数字の追加は是正案にしない。入口と中身はトレードオンで両立させる。**

## 補正指針（検出問題→補正指針）

検出問題ごとの補正指針。本エージェントは read_only で指針を返し、実補正は下流（report-composer / slide-report-modifier）が適用する。font-size 縮小は最小値（1.4rem）以上の範囲でのみ行う。

| 問題 | 補正指針 |
|------|----------|
| 空節（見出しだけ） | 結論文＋根拠段落を加筆する（report-composer へ） |
| 段落過密（1段落に論点混在） | 論点で段落を分割し、各段落先頭にトピックセンテンスを置く |
| 段落過疎（節が痩せる） | 背景・根拠・含意を加筆、または length を見直す |
| 1項目1ビジュアル超過 | 図解を 1 点に絞る。2 点必要なら情報過密のサインとして節分割を report-structure-designer へ |
| 図解過多（全節に図） | 文章で足りる節を none 化する |
| 種別不適合 | 内容の性質（構造/情感/論述/逐語）に合わせ kind を再選択し rationale を更新 |
| 逐語を画像に焼いている | 数値・料金・コードを本文（markdown 表/コードブロック）へ移す（退化耐性） |
| 骨格 role 欠落 | 必須 role を補うか省略理由を明示（差し戻し: report-structure-designer） |
| 骨格順序崩れ | role の並びを骨格の論理順序へ是正（差し戻し: report-structure-designer） |
| 見出し階層スキップ | 中間見出しを補うか下位見出しレベルを是正 |
| letterbox 強制 | 16:9 の aspect-ratio を外し A4/レター縦スクロールへ戻す |
| 印刷 px 依存 | 印刷 CSS の px を mm/rem へ、共有 SSOT トークンへ整合 |
| 最小フォント違反 | CSS 変数（--fs-body 等）で 1.4rem 以上へ |
| コントラスト不足 | テーマの色変数を使い WCAG AA を満たす。純黒/純白を避ける |
| 意匠独自発明 | 共有 SSOT（vendor primitives / theme）の意匠トークンへ差し替え |
| 構造同期崩れ | report-structure.json を正として過不足を是正（差し戻し: report-composer） |
| 入口が専門手段だけで始まる | audience/reportType を維持し、共有課題と読後の変化を title/throughLine/summary の先頭へ。正式名称が必要なら subtitle/keyMessage で補う（差し戻し: report-structure-designer） |
| 自分へ移す橋がない | 主要 part/節に「当てはまる兆候・判断の問い・選択肢・次の行動」のいずれかを追加（差し戻し: report-structure-designer） |
| 根拠のない数字・実績 | 入力素材/出典で確認できない数値を削除し、確認済みの定性的変化または未確認へ戻す（差し戻し: hearing-facilitator / report-structure-designer） |
| 本論が一般論化 | 素材にある数字・手順・失敗・条件・限界の射影漏れを補う。素材自体が不足する場合は捏造せず再ヒアリング |

## よくある問題と対処法

### 読み物文体・段落密度

| 問題 | 原因 | 対処法 |
|------|------|--------|
| 見出しと chip だけで本文がない | slide 規律を report にそのまま適用 | 各節に結論文＋根拠段落を書く（read-through 緩和） |
| slide をそのまま縦に並べた | 1メッセージ圧縮が通読を阻害 | セクション＋段落へ再構成する |
| 段落が長すぎ論点混在 | 1段落に複数論点 | 論点で分割しトピックセンテンス先行に |
| deep 指定なのに各節1段落 | 密度が length と不整合 | 背景・根拠・含意まで加筆 |

### 1項目1ビジュアル・図解適合

| 問題 | 原因 | 対処法 |
|------|------|--------|
| 1節に図解2点 | 情報過密 | 1点に絞る or 節分割（report-structure-designer へ） |
| 全節に図解 | 図解過多 | 文章で足りる節は none |
| 数値・料金を画像に焼いた | 退化耐性違反 | markdown 表で本文に持つ |
| codex-image を構造図に使用 | 種別不適合 | 構造は svg/mermaid へ寄せる |

### reportType 骨格・section 構造

| 問題 | 原因 | 対処法 |
|------|------|--------|
| 必須 role 欠落 | 骨格未網羅 | role を補う or 省略理由明示（差し戻し） |
| 背景の前に結論だけ | 論理順序崩れ | 骨格順へ並べ替え（差し戻し） |
| callouts を使わず警告が埋没 | 注記手段の未使用 | 落とし穴・補足を callouts（warning/caution）で強調 |

### 見出し階層・印刷/letterbox

| 問題 | 原因 | 対処法 |
|------|------|--------|
| h2 の直下で h4 | 見出しレベルスキップ | h3 を経る or 中間見出しを補う |
| report が 16:9 に固定 | slide の letterbox を誤適用 | aspect-ratio を外し縦スクロールへ |
| 印刷でカードが消える | 印刷 CSS の px 依存/box-shadow 依存 | mm/rem・border で輪郭を明示、共有トークンへ |

### 可読性・意匠維持

| 問題 | 原因 | 対処法 |
|------|------|--------|
| 本文が 1.4rem 未満 | 直書き小サイズ | CSS 変数で 1.4rem 以上へ |
| 純白テキストが眩しい | #FFFFFF 使用 | --fg（Kanagawa 淡色）へ |
| 独自配色を発明 | 意匠 SSOT 非共有 | 共有トークンへ差し替え（RQCONST_006） |
| report.html が構造と不一致 | 勝手な節の増減 | report-structure.json を正に是正（差し戻し） |
