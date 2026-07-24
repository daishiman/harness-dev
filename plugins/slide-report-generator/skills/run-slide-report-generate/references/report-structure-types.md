# レポート構成設計 ドメイン定義（report-structure-designer 手続き知識 SSOT）

> **正本**: このファイルは report-structure-designer から抽出した手続き知識/規範の SSOT。run-slide-report-generate の SKILL.md と agent 本体（agents/report-structure-designer.md）の双方がこれを参照する。規則の上位正本 (SR-ID) は spec-registry.md を辿る。

**責務**: report モードの構成設計ドメイン定義（用語集・reportType 4種の骨格判定基準・入力検証基準・ビジュアル要否ルブリック・制約カタログ RCONST_001-007）の逐語正本。report-structure-designer（薄化アダプタ）は役割・起動条件・I/O契約に専念し、詳細規範は本 reference を SSOT とする。reportType 各型の節構成テンプレの深掘りは `${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/references/report-types.md` を辿る。

## 用語集
| 用語 | 定義 | 関連概念 |
|------|------|----------|
| reportType | レポートの目的別骨格の型。4種（internal-analysis / client-proposal / tech-doc / learning） | `meta.reportType` / `${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/references/report-types.md` |
| 骨格（skeleton） | reportType ごとに定義された節の並び。例: 要約→背景→現状分析→所見→次アクション | `sections[].role` |
| section | 見出し＋読み物段落＋最大1ビジュアルからなる読み単位。slide の 1 枚に対応する report の主単位 | `sections[]` |
| role | セクションが骨格のどの節かを示すラベル（summary/background/analysis…） | `sections[].role` |
| read-through 粒度 | 投影ではなく通読を前提とした本文密度。文章多め・複数段落を許容 | `${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/references/report-writing-rules.md` |
| 1項目1ビジュアル | 1セクションに図解は最大1つ。過剰装飾を避け読解を助ける1点に絞る | `sections[].visual` |
| visual kind | ビジュアル種別の三択（svg / mermaid / codex-image）＋none | visual-strategist / `${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/references/report-visual-strategy.md` |
| readingOrder / focalPoint | 視線誘導の向きと主ビジュアルの重心。デッキ内一貫性の配置ヒント | `${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/references/full-image-deck-method.md` §1.11 |
| report-structure.json | 構造化データ正本。生成前にユーザー承認を得る | `${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/schemas/report-structure.schema.json` |
| 読者価値ブリーフ | 対象範囲・共有課題/願望・読後の変化・専門の橋・深さの証拠・正式タイトル制約を、schema 外の設計入力としてまとめたもの | RCONST_007 / `${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/references/report-narrative-logic.md` §7.2 |
| 入口ホリゾンタル・中身バーティカル | 想定読者の範囲内で共有課題・得たい変化から広く開き（入口）、本論は専門の深さで応える（中身）設計原則 | RCONST_007 / `${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/references/report-narrative-logic.md` §7 |

## 評価基準（ドメイン固有の判定基準）

### reportType 骨格判定基準
**詳細**: `${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/references/report-types.md`

| reportType | 用途 | 骨格（role の標準並び） |
|------------|------|------------------------|
| `internal-analysis`（社内報告分析） | 社内向けの現状把握・意思決定材料 | 要約(summary)→背景(background)→現状分析(analysis)→所見(finding)→次アクション(next-action) |
| `client-proposal`（顧客提案WP） | 顧客向けの提案・ホワイトペーパー | 課題(problem)→解決策(solution)→効果実績(impact)→導入ステップ(step)→CTA(cta) |
| `tech-doc`（技術ドキュメント） | 手順・仕様の技術文書 | 概要(overview)→前提(prerequisite)→手順構造(procedure)→注意点(caution)→参照(reference) |
| `learning`（学習解説） | 概念を段階的に理解させる教材 | 問い(question)→核心概念(concept)→図解理解(diagram-understanding)→例応用(example-application)→まとめ(conclusion) |

- 骨格は**最小の必須並び**であり、内容に応じて同 role の節を複数回（例: 現状分析を 2 セクションに分割）使ってよい。ただし骨格の**論理順序は崩さない**（背景の前に結論だけを置かない、前提の前に手順を置かない）。
- reportType が確定していない場合は hearing-facilitator へ差し戻す（推測で確定しない）。

### 入力検証基準
| 基準 | 条件 |
|------|------|
| 必須入力の充足 | 受理=reportType＋title＋目的＋素材＋読者を含む / 拒否=いずれか欠落（hearing-facilitator に再要求） |
| 読者価値ブリーフ | 対象範囲・共有課題/願望・読後の変化・専門の橋・深さの証拠・正式タイトル制約が、入力素材に基づいて確定または未確認として明示されている。schema 外フィールドは report-structure.json に追加しない |
| 骨格網羅 | 確定 reportType の必須 role が sections[] に 1 つ以上ずつ写像されている / 欠落があれば補うか、省略理由を notes に残す |
| 読み物成立 | 各 section の paragraphs[] が空でなく、要点が言い切られている（見出しだけの空節ゼロ） |
| 1項目1ビジュアル | 各 section の visual は 0 または 1。1 節に複数図解を積まない |
| schema 適合 | 出力が report-structure.schema.json に valid（additionalProperties 違反・required 欠落ゼロ） |

### ビジュアル要否の指定ルブリック（三択は visual-strategist へ委譲）
本エージェントは「その節にビジュアルが要るか、要るなら何を伝える図か」までを決め、`visual.kind` に**第一候補**を、`visual.rationale` に意図を記す。SVG図解 / Mermaid / Codex 画像の**最終確定と配置（grid/zones/readingOrder/focalPoint）は visual-strategist が最適化する**（本エージェントの第一候補は上書きされうる）。

| 節の内容 | ビジュアル要否 | 第一候補 kind の目安 |
|----------|--------------|---------------------|
| 順序・依存・分岐・階層が意味を持つ構造 | 要 | `svg`（インライン図解・意匠トークン共有）または `mermaid`（フロー/シーケンス/状態が定型なら） |
| 定量比較・時系列推移・割合 | 要 | `svg`（chart 系 variant）または `mermaid`（pie/gantt） |
| 概念の情感・世界観・章扉的な導入 | 要 | `codex-image`（Codex Image2 コンセプト画像） |
| プロセス・関係が Mermaid の定型記法で素直に書ける | 要 | `mermaid` |
| 純粋な論述・要約・注意点の列挙 | 不要 | `none`（本文と callouts で十分） |

- **read-through では図解過多を避ける**。文章で足りる節は `none` を選び、図解は「読解を明確に助ける1点」に絞る（slide の CONST_002「全スライドにアイコン/図解必須」を report では緩和する）。
- 数値・逐語が頻繁に変わる表・コード・精密数値は画像へ焼き込まず、本文（markdown 表・インラインコード）で持つ（退化耐性優先。slide の CONST_007 と同趣旨）。

## ビジネスルール
- **RCONST_001（骨格順序保持）**: reportType の骨格の論理順序を崩さない。
  - 目的: 読者が文脈（背景・前提）を得た上で結論・手順へ到達できるようにする。
  - 背景: 読み物は通読される。順序が乱れると理解が断絶する。slide の CONST_006（背景→質問の順）と同じ思想を文書全体へ拡張したもの。
- **RCONST_002（読み物成立）**: 各セクションは見出しだけで終わらせず、要点を言い切る段落を持つ。
  - 目的: 「見出しの羅列」ではなく「読める文書」にする。
  - 背景: report モードは slide の長文禁止（BP11-13）を**緩和**する。文章多めが正であり、空節・箇条書きだけの節は退化。
- **RCONST_003（1項目1ビジュアル）**: 1セクションにビジュアルは最大1つ。
  - 目的: 読解を助ける1点に絞り、装飾過多で本文が痩せるのを防ぐ。
  - 背景: 1メッセージ1図の可読性原則を read-through 粒度へ適用。
- **RCONST_004（三択の非確定）**: 本エージェントはビジュアル種別の第一候補と意図を書くにとどめ、三択の最終最適化と配置は visual-strategist に委ねる。
  - 目的: 責務分離（構成設計 ↔ ビジュアル戦略）を保ち、SRP を守る。
  - 背景: 固定比率を持たない三択最適化は独立の意思決定層（visual-strategist）が担う設計。
- **RCONST_005（承認必須）**: ユーザー承認なしで仕様確定ゲート（structure-validator）へ進まない。
  - 目的: 構造段階での手戻り防止と過不足の早期検出。
  - 背景: 構造化データ先行。HTML/prose 後の修正は構造修正より高コスト。
- **RCONST_006（意匠コア共有）**: theme は `kanagawa-lotus` 固定。配色・フォント・最小サイズは slide と同一 SSOT を参照し report 独自に発明しない。
  - 目的: slide/report で意匠を単一 SSOT に保つ（build-contract §D 共有層）。
  - 背景: 分岐するのはコンテンツ意図層のみ。意匠/技術層は共有。
- **RCONST_007（読者中心の入口設計）**: ヒアリングの読者価値ブリーフを設計入力とし、title・`meta.throughLine`・summary/導入節は、想定読者の範囲内で共有される課題と「読者が得る変化（Before→After・根拠があれば数字）」を先に渡す（入口ホリゾンタル）。専門手段だけを主語にしない・内容理解に不要な属性スタックを置かない・書き手の資格紹介から始めない。本論の節では専門の深さ（確認済みの数字・手順・失敗・再現条件・限界）を保ち、各主要 part / 節に「自分に当てはまる兆候・判断の問い・選択肢・次の行動」のいずれかを置く（中身バーティカル＋自分ごと化）。
  - 目的: 専門性を保ったまま、読者が「自分ごと」として入ってこられる文書にする。読者が知りたいのは書き手の知識ではなく自分の変化。
  - 背景: 入口まで専門特化した文書は想定読者の注意を失う。「ターゲットを絞る」ことと「入口まで狭くする」ことは別。ただし tech-doc・社内定型報告・監査/契約/仕様文書では正式名称・検索語・適用範囲を主タイトルに残し、subtitle/keyMessage/summary で読者価値を補う。素材にない数字・実績は作らない。正本は `${SRG_ROOT:-$CLAUDE_PLUGIN_ROOT}/references/report-narrative-logic.md` §7。違反は report-quality-reviewer の RQ31〜RQ34 が検出し本エージェントへ差し戻す。
