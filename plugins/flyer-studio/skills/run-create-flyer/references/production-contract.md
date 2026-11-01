# 制作・修正の契約

目的は確定目的と採用要求を実画像で成立させること。診断の文章を整えるだけで改善済みとしない。共通規則は[stage-common](../../../references/stage-common.md)、描画の型は[scene schema](../../../schemas/scene.schema.json)、採否の正本は案件のanalysisとbrief.feedback。

## 必要情報と制約

読者・価値・行動、必須事実、素材公開範囲、使用可能な書体、編集元と描画経路を確認する。brief.analysisMode が source-artifact の案件では、元画像/要求/analysisに対応する独立PASSのanalysis-reviewが必要。初回新規案の生成と、その現物からの改善を区別し、未生成画像を診断済みとしない。既存修正は既存の編集元を保持し、analysisのsource snapshot（診断した時点の元画像）と今回の制作先を区別する。

採用要求の対象を実要素へ結び、なぜ変えたか、何を保ったかを、満たす本質条項（serves）とともにdesignIntent/feedbackへ簡潔に残す。必須要求を消す、意味群のラベルを変えて中心軸を回避する、極小化する、肩書きや成果を創作する方法で収めない。候補が前提上実現できない時は証拠を添えて診断/提案評価へ戻す。

## 都度考える処方

指針はstage-commonの「知識の読み込み」どおり今の未達に要るものだけを読み、構図・Y位置・群幅・余白・トリミング・書体/太さ/大きさを比較する。固定pt比や著名作品の表層を全案件へ当てはめない。素材の公開条件と読者の判断を守り、全案上部を一律構図へ均さない。

背景の実生成/承認済み再利用、写真加工物の保持、自然な境界、白外縁、独立QR/文字/ロゴは[workflow](../../../references/workflow.md#stage-ごとの要点)を参照。ツール未実行を実行済みにしない。

## 実行・鮮度・戻り

編集をまとめた後に入力/素材/実装を凍結し、validate→render→verifyへ進む。開始時と終了時のsnapshotが変わればその成果と下流レビューを失効させ、旧hashで通さない。評価中は編集せず、全担当の結果を待つ。

評価テンプレート（pilot-review-template・review-template）の生成はこのstageが行い、記入は評価担当に任せる。完成評価の必須修正はfixClassで決まる戻り先どおりに受け、serves（どの本質条項の未達か）を確かめてから直す。preferenceNotesは必須修正として扱わず、cycleにも数えない。

finalize（納品物の結合と検査）は、全案の最新独立PASSと必須修正0が揃った後にこのstageが行う。確かめる条件と渡す物は[workflowの改善と納品](../../../references/workflow.md#改善と納品)。
