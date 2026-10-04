# system-spec-harness リリースノート (P13)

## バージョン 0.1.16 (1 つの出典を複数の章へ載せる宣言)

target の `category` は 1 つしか持てず、同じ公式文書を根拠にした別の章の判断を、章から出典へ辿れなかった
(例: D1 の文書が database 章にだけ載り、一括書込の上限を決めた backend 章と infrastructure 章の出典表に出ない)。
また writer は target の未知キーを黙って捨てていたため、複数の章を宣言しても章割当に届かなかった。

- **targets の任意キー `also_categories`**: `set-targets` が受理して保存する。`category` (主たる章) を持つ target に
  だけ指定でき、非空文字列の非空配列で、要素の重複と `category` との一致は TransitionError で拒否する。
- **compile**: `_target_category_map` は target_id → 章の列 (先頭が主たる category) を返し、
  `references_by_category` は宣言した各章へ同じ出典を載せる。章内の並びは fetched-references の記録順のまま。
  宣言の無い章へは載せない。
- **変えないもの**: C02 の取得と C13 の全件突合は target_id 単位のままで、record は 1 件に束ねる。

### 既存の spec-state への影響
- `also_categories` を持たない targets の挙動は変わらない。複数の章に載せたい target は `set-targets` で宣言し直す。

## バージョン 0.1.15 (ヒアリング監査と推奨の食い違いの解消・逐語の漏れの片付け)

0.1.14 では、R5 に従って推奨を示した問が R6/C06 で誘導と判定され、qa_log の凍結のために
その検出が問い直しても毎周再発し、low 1 件でも完成度評価が総合 FAIL になっていた。
また compile が answer の行頭 `###` を章の見出しとして漏らし、次回の compile がそれを人の節として
引き継ぎ続けていた。判定は緩めず、基準と対応を 1 か所に置き直して解消する。

- **中立な問の基準を 1 か所に置いた**: `skills/run-system-spec-elicit/references/neutral-question-criteria.md`
  (N1 推奨の印なし / N2 利点と不利な点の対称 / N3 前提を埋め込まず決めない道を残す / N4 1 問 1 論点)。
  R5 は推奨を比較の後の別の段に「AI推奨 (参考)」として示し、問は最後に中立に聞く。R6 と C06 は同じ基準で判定し、
  推奨を提示したこと自体は検出しない。
- **置き換え (supersession)**: writer に `supersede-qa` op を追加した。旧 entry に `superseded_by` /
  `superseded_at` / `superseded_note` を 1 度だけ追記する (本文は凍結のまま)。writer は (c) 利用者の回答が
  記録されていることを決定論で検査し、(a) 中立 (b) 同じ論点 は C06 が判定する。旧 entry が確定セルの主たる
  接地根拠のままの置き換えと、置き換え済みの entry を qa_ref にする confirm は拒否する。
- **C06 は R6 の監査 5 軸を参照する**: 「検出 3 軸 + トレース 1 軸」の記述を撤去し、各検出に重大度
  (high / medium / low / info) を付けて R6 Layer 6 の JSON 形で返す。置き換え済みの問は判定の対象から外し、
  閉じた検出として報告に残す。
- **重大度と判定の対応を aspect-criteria.md の 1a に置いた**: high と、確定セルの主たる接地根拠の問への
  medium と、軸 2 以外の medium は従来どおり FAIL。主たる接地根拠でない問への medium と low / info は、
  PASS に残す注記として findings に残す。決定論実装は `aggregate-completeness.py --hearing <C06 出力> --state <spec-state.json>`
  (`derive_hearing_verdict`)。C06 自身の verdict は判定に使わない。
- **compile**: 構造 (見出し・フェンス・setext の下線) を含む逐語はフェンスに閉じ込めて描く。置き換え済みの qa は
  「旧版（置き換え先: <qa_id>）」の印付きで描き、R4-reopen の履歴から一律に旧版と描かない。
- **既存章の片付け (移行)**: 逐語に行として現れる見出しを人の節の引き継ぎと消失判定から外し、管轄節と同じ見出しの
  `####` 質疑ブロックは引き継がず再描画する。人が書いた見出しが消えるときは従来どおり CompileError で止める。

### 既存の spec-state への影響
- 既存の qa entry には `superseded_*` が無い。誘導の検出がある問は、N1-N4 に沿って問い直し
  (必要なら R4-reopen → 新しい qa で再確定) → `supersede-qa` で閉じる。自動では閉じない。
- 章は次回の compile で片付く (漏れた見出しと重複した質疑ブロックが消える)。人が書いた節は残る。

## バージョン 0.1.0 (初回 build)

14 component (skill×5 / sub-agent×3 / slash-command×2 / hook×1 / script×3) + envelope surface (manifest / EVALS / RUNBOOK / plugin-composition / CI additive wiring) を build。全 component が p0_lint (kind別) exit0・pytest 375 passed・route-build-report×14 valid。知識グラフ追加サイクルでは `validate-knowledge-graph.py` の knowledge / required-info / doctrine / cross 4 profile が exit0。

## リリース準備 soft note (PR/配布はゲート化しない)
- PR: feature branch から main への PR は soft note に留める (本 plugin の完了条件に PR merge を含めない)。
- marketplace 登録と `harness-full` bundle 配線は distributable 承認済みの現行 manifest に反映済み。
- `.claude/` symlink 反映 (`build-claude-symlinks.py` + `make sync`) を配布前に実施。

## ドメイン外 DROP 記録 (写像対象外)
本 plugin の purpose は「システム構築仕様のヒアリング収集と仕様書化」であり、以下は component 写像対象外として意図的に DROP:
- **IPC (プロセス間通信) の実装**: 仕様として章に記録する対象ではあるが、IPC 実装そのものは本 plugin の生成物でない (仕様書に書く内容であって plugin が作る機能ではない)。
- **Cloudflare 等 特定ベンダー連携**: インフラカテゴリのヒアリング項目として扱うが、特定 CDN/WAF ベンダー固有の実装は component 化しない (最新情報は C02 doc-fetch が公式ドキュメントとして取得)。
- **MCP / app connector 経由のドキュメント取得**: WebSearch/WebFetch で完結する方針のため今回は新設せず (`GAP-MCP-DOCFETCH` として保留)。

## 配布状態
- **GAP-DISTRIBUTION-DECISION は解消済み**: 現行 manifest は `distributable: true` で、marketplace と `harness-full` bundle に登録済み。
- package 契約は `validate-plugin-packages.py` で blocking finding なしを確認する。

## 残タスク (次サイクル候補)
- 実運用での往復ヒアリング実走フィードバックに基づく質問バンク (C01 references) の拡充。
- task-graph の checklist ownership 射影を component owner 単位へ再設計し、covered task を再生成する。
- C16 required-info の `missing_effect=block` を単一 writer で決定論施行し、coverage certificate を spec-state に保存する。
