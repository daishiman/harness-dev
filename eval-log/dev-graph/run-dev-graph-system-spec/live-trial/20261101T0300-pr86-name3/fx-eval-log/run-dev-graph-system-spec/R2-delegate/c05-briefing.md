# C05 起動前共有 (親 run-dev-graph-system-spec R2 → assign-system-spec-completeness-evaluator)

- args は helper (build-evaluation-context.py exit0) の skill_args を無変更で渡す:
  --spec-dir /private/tmp/claude-501/pr86-ci-live/lt/runs/sysspec99/fx/system-spec --output /private/tmp/claude-501/pr86-ci-live/lt/runs/sysspec99/fx/eval-log/system-spec-completeness-report.json
- 役割ごとの保護条件:
  - 仕様state・出典記録・章は system-spec-harness 正規writerのみが生成。C05 はそれらを生成/変更しない。
  - C05 自身が意味評価を行い、C07(matrix)/C06(hearing)/C08(doc-freshness) は実 Agent を 1 message 1 件ずつ起動し、実 completion を待ってから次を起動する。並列起動しない。起動受理 payload を判定に使わない。判定は実 completion の receipt/digest に結ぶ。
  - このhostの Agent は run_in_background/name を指定しなくても runtime が "Async agent launched" を返す。C05 は background/name を明示要求しない。完了通知 (実 completion) を待ってから判定・次起動を行う。
  - 監査台帳の全必須行が resolved であること。
  - C08 の公式再照合は WebFetch で www.postgresql.org / react.dev / fastapi.tiangolo.com / www.typescriptlang.org / kubernetes.io への https GET のみ許可。WebSearch・他host・Bashのネットワークは不可。必須取得が不可能なら迂回せず FAIL。
  - C06 には担当 source (elicit の prompts/R6-audit-hearing.md 全文と対象 spec-state) 全体を読ませる。
- 保存契約 (R1-score 4.3 / allowed-tools 尊重): Write/Edit を使わない。評価JSONは read-only Python の stdout で組み立ててよいが、ファイル保存は literal `pathlib.Path("/private/tmp/claude-501/pr86-ci-live/lt/runs/sysspec99/fx/eval-log/system-spec-completeness-report.json").write_text(sys.stdin.read(), encoding="utf-8")` と引用 JSON heredoc で行う。補助 script のファイル保存も行わない。最終出力は指定 report path のみ。report の spec_dir/output は引数どおりの絶対パス。
- 問答履歴の区別 (R6-audit-hearing): active consumer は確定 cell.qa_ref と requirements_foundation.effective_source_refs の qa_ref。apply-spec-transition.py::_supersede_qa は補助 qa_refs に旧問参照を履歴として残すことを明示許可し、compile は旧版の印と現行根拠ではない旨を描く。qa_refs の存在だけを active consumer と数えず、主根拠/binding と置き換え (a)(b)(c) を個別確認する。履歴を削除しない。無効な置き換え・実 active consumer・他欠陥があれば通常どおり FAIL。
