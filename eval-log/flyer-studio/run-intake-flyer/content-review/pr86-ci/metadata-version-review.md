# version メタデータ限定レビュー

22ファイルの保存済み変更前全文と最終sourceを独立比較した。JSONはroot.versionだけ（package-lockはpackages[""].versionも）、Markdownはfrontmatter.versionだけを正規化すると全データが同値になり、全対象の版は1.3.2だった。両release manifestもgit HEADからversionを除いて同値であり、nameはflyer-studioのまま。

build-local-package.py:749-768のcheck_versionsはmanifest・package・lock・EVALS・workflow・Skill・agentの同版を要求する。同期はこの検査条件を満たす。本文、責務、criteria、入出力、所有、agent tools/isolation、workflowの資源・依存辺は変わっていない。

run-intake-flyerはroot契約の本体変更まで今回独立にレビューしており、最終SHAで採点器も再実行した。他5 Skillはversionだけの差分レビューで、既存content-reviewの旧対象SHAが保存済み変更前全文のSHAと一致することを確認し、従前の意味判断を継承した。今回それらをフル再評価したとは主張しない。各directoryに両verdict案と根拠履歴を保存した。既存low所見も履歴として保持し、修正済みとは扱わない。

この継承は今回の親からの明示要求による限定レビューであり、汎用的な旧SHAの単純書換・レビュー不要方針ではない。旧verdict自体には手を加えていない。新verdictのcriteria_evaluatedの旧IDは継承根拠に属し、今回の新規評価はVERSION-METADATA-ONLY。30思考法、host trial、人間の承認は追加していない。

|Skill|継承する既存の意味判断|今回独立に検証した範囲|
|---|---|---|
|assign-flyer-analysis-evaluator|観察整合・網羅・変更規律・実現性|version差分、本文/責務/manifestの同値|
|assign-flyer-evaluator|完成画像評価契約とcoordinatorの所有/独立性|同上。既存low所見は未再評価で残置|
|run-analyze-flyer|元画像診断と提案・独立評価への受渡し|同上。既存low所見は未再評価で残置|
|run-create-flyer|制作/評価分離と納品条件|同上。既存low所見は未再評価で残置|
|run-learn-flyer|知見の集計/分類と個人情報境界|同上。既存rubric low所見は未再評価で残置|

前後SHA、変更箇所、履歴verdictのSHA/時刻/担当/旧対象SHAはmetadata-version-review.jsonと各*-inherited-review.jsonに残す。
