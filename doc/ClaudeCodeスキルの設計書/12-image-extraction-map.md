# 12. 画像抽出対応表

このファイルは、元 Markdown に含まれる画像の情報を漏れなく追跡するための証跡対応表である。設計判断の正本ではなく、画像・行番号・抽出内容の traceability を担う。対象画像は 55 ファイル(参照箇所55点)。ただし以下2ペアはバイト/内容が完全一致しているため、ユニーク画像は実質 53 種である。差分の経緯は `21-source-traceability.md` を参照。

- ペアA: `Obsidian 2026-05-17 15.14.31.png` ≡ `Obsidian 2026-05-17 15.14.41.png` (バイト完全一致 1,659,063 bytes / 同一画像)
- ペアB: `Pasted image 20260517153432.png` ≡ `Pasted image 20260517153442.png` (内容完全一致 / 同一画像)

正本元記事は `xl-skills/doc/【コード共有有】Agent Skill大全 数百本のSkillをり続けた実践知から導いたオーケストレーション設計の概念体系Byまさおさん/` 配下。正規タイトルは `Skillを作り続けた` だが、実在パスでは `作` が欠落した `Skillをり続けた` になっている。ユーザー指定文の `Skillり続けた` も入力揺れとして扱う。

| 行 | 画像 | 抽出内容 |
|---:|---|---|
| 95 | `Obsidian 2026-05-17 15.13.53.png` | Context Reset（文脈リセット）。compaction ではなく完全クリアした新 agent に構造化 handoff を渡す |
| 162 | `Obsidian 2026-05-17 15.14.31.png` | 散らかった運用知 → 5 段引出しで整理 BEFORE/AFTER (ペアA 正本) |
| 248 | `Obsidian 2026-05-17 15.14.41.png` | 重複(同一画像 / ペアA): 248行のキャプション「再利用可能 Skill 設計の全体像」は誤り。実体は 162 行と同一画像 |
| 281 | `Pasted image 20260517151648.png` | Skill / Subagent / Hook / MCP の使い分け早見表 |
| 294 | `Pasted image 20260517151701.png` | Skill / Subagent / Hook / MCP 比較表 |
| 297 | `Pasted image 20260517151710.png` | 運用・判断層と実装層のレイヤー図 |
| 320 | `Pasted image 20260517151722.png` | Skill を作る前に通す決定木。決定論で落ちるものは Skill にしない |
| 335 | `Pasted image 20260517151733.png` | Git status は CLI、GitHub issue は CLI/MCP、禁止語は Hook/CI、PR 観点は Skill |
| 343 | `Pasted image 20260517151757.png` | Skill は CLI / MCP / API の上に立つ管制塔 |
| 346 | `Pasted image 20260517151806.png` | CLI / MCP / API/SDK の定義と例 |
| 353 | `Pasted image 20260517151812.png` | Skill が各実装層をいつ・どう使うかを書く |
| 369 | `Brave Browser 2026-05-17 15.19.55.png` | CLI と MCP は対立ではなく、Skill が道具を選ぶ |
| 427 | `Pasted image 20260517152051.png` | 実装層 4 段階昇華ラダー |
| 457 | `Pasted image 20260517152110.png` | Claude は description / when_to_use で Skill を選ぶ |
| 474 | `Pasted image 20260517152123.png` | YAML frontmatter と Markdown 本文の役割 |
| 515 | `Pasted image 20260517152140.png` | description Before/After。人間向け要約から発動条件へ |
| 529 | `Pasted image 20260517152159.png` | SKILL.md frontmatter の主要 field |
| 536 | `Pasted image 20260517152216.png` | frontmatter field の役割と注意 |
| 542 | `Pasted image 20260517152444.png` | 呼び出し制御マトリクス |
| 543 | `Pasted image 20260517152451.png` | default / disable-model-invocation / user-invocable 比較 |
| 564 | `Pasted image 20260517152506.png` | Progressive Disclosure（段階的開示）と compaction token budget |
| 588 | `Pasted image 20260517152518.png` | 入口情報 / SKILL.md 本文 / 補助ファイル |
| 591 | `Pasted image 20260517152529.png` | 3 層のロードタイミング |
| 601 | `Pasted image 20260517152540.png` | attention は有限。全部 SKILL.md に書かない |
| 675 | `Obsidian 2026-05-17 15.25.56.png` | 段階的開示の 3 失敗 |
| 682 | `Pasted image 20260517152614.png` | 失敗パターン、悪さ、直し方 |
| 695 | `Pasted image 20260517152620.png` | どこに置くか × どこで読ませるか |
| 758 | `Pasted image 20260517152658.png` | 副作用で辞書型 / ワークフロー型を分ける |
| 791 | `Pasted image 20260517152707.png` | 辞書型 / ワークフロー型比較 |
| 805 | `Pasted image 20260517152717.png` | やりたいこと別分類例 |
| 806 | `Pasted image 20260517152728.png` | 公式 reference content / task content 例 |
| 817 | `Pasted image 20260517152736.png` | CLAUDE.md / ref-* / docs の memory density |
| 877 | `Pasted image 20260517152915.png` | 4 軸: Purpose（目的） / Trigger（発動条件） / Shape（成果物の形） / Role（役割） |
| 900 | `Pasted image 20260517152941.png` | Purpose（目的） 軸 |
| 904 | `Pasted image 20260517152948.png` | Trigger（発動条件） 軸 |
| 910 | `Pasted image 20260517152958.png` | Shape（成果物の形） 軸 |
| 916 | `Pasted image 20260517153005.png` | Role（役割） 軸 |
| 923 | `Obsidian 2026-05-17 15.30.09.png` | `ref-agent-essence` の 4 軸例 |
| 937 | `Pasted image 20260517153028.png` | `wrap-masao-ch-thumbnails` の 4 軸例 |
| 945 | `Pasted image 20260517153041.png` | 4 軸は設計レビュー用の問い |
| 964 | `Pasted image 20260517153048.png` | 4 軸のズレと扱い |
| 974 | `Pasted image 20260517153106.png` | 5 prefix 一覧 |
| 978 | `Pasted image 20260517153115.png` | prefix 決定木 |
| 979 | `Pasted image 20260517153120.png` | 4 軸から 5 prefix への決定マトリクス |
| 991 | `Pasted image 20260517153137.png` | 名前は契約 |
| 1009 | `Pasted image 20260517153146.png` | 独自 metadata `base`, `pair`, `kind` |
| 1075 | `Pasted image 20260517153203.png` | Skill は教材ではなく行動設計文書 |
| 1082 | `Pasted image 20260517153212.png` | 書くべき / 書かなくてよい |
| 1185 | `Obsidian 2026-05-17 15.32.20.png` | Less is More / Why（理由）-driven |
| 1228 | `Pasted image 20260517153330.png` | Gotchas（落とし穴）から決定論への 4 段階 |
| 1246 | `Pasted image 20260517153351.png` | dynamic injection と外部 LLM output の扱い |
| 1331 | `Pasted image 20260517153442.png` | sycophancy と評価分離 (手描き図 / ペアB 正本) |
| 1332 | `Pasted image 20260517153432.png` | 同上(重複 / ペアB): 1331 行と内容完全一致。別キャプション「評価が壊れる理由」は二重計上だった |
| 1333 | `Pasted image 20260517153449.png` | Generator（生成役） / Evaluator（評価役） 役割 |
| 1338 | `Pasted image 20260517153455.png` | generator -> artifact -> evaluator -> done/retry |
