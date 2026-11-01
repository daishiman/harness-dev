# PR86 Flyer Studio 独立内容レビュー

最終判定は elegance / rubric とも PASS。対象SKILL.md SHA-256は `6d5d448360211a9d87a83d561f3db3bce82fb402da0d63e2ae774b2c08da6e23`。今回は差分を中心としたfocusedレビューであり、30思考法のフル実走ではない。

## 対象と独立性

`plugins/flyer-studio/skills/run-intake-flyer/SKILL.md`現行全体とgit diff、`references/package-contract.json`の3 Codex agent代替追加を読み、必要な共通規則・stage実装・workflow-manifest・native agentと照合した。既存content-reviewはJSON形状確認のため読んだが、その結論・肯定文・hash更新を根拠にしていない。source/fixture/既存証跡は編集していない。採点器のeval-log append要件は親の/tmp限定指示に従い実行していない。

## 4条件

|条件|最終判定|根拠|
|---|---|---|
|C1 矛盾|PASS|root宣言は解決規則であり、深さ選択前に局面を実行する指示ではない。下書き→選択→案件生成の順序、E3のplugin外保存を変えない。|
|C2 漏れ|PASS|初回はmanifest名照合不足をmediumとして指摘。修正後SKILL:85-86にname=flyer-studio確認、読取不能・不正・不一致時の実行停止が入った。|
|C3 整合性|PASS|runtime-portability.md:43-52のホスト別root規則、stage-common.md:20-24の自己相対rootと実行形式へ一致。3代替の役割と宣言は下記対応表どおり。|
|C4 依存関係|PASS|7 workflow-manifestのresource pathがすべて実在し、各manifest内phase依存は未知参照/循環なし。3 agent代替からの4 skill routeもすべて実在。|

## Agent / Skill / lens / role 対応

|native agent|観点と出力criterion|Codex代替の入口|
|---|---|---|
|flyer-color-reviewer|色、criteria color/integration|assign-flyer-analysis-evaluator / assign-flyer-evaluator / run-analyze-flyer / run-create-flyer|
|flyer-composition-reviewer|構図、criteria balance/spacing|同上4 skill|
|flyer-typography-reviewer|文字、criteria hierarchy|同上4 skill|

各agentについてpackage-contractのdiscovery.entry_pointsとowner_route.entry_pointsの集合は、当該agentをresourcesに載せる実workflow-manifestの集合と完全一致した。intake/learn/feedbackにレンズ参照はないので代替入口にも含めない。共通規則:69-72はレンズを既定で呼ばず他stageが同じ知見を読むことを認める。review-contract:12-13は制作と別の評価担当が自分でレンズを当てるindependent-reviewer-lensesを既定にする。したがってCodex側でstage自身が知見を使う代替は、レンズ3担当の別contextを実施した証明にはならないが、既存の許容された評価体制と一致する。3 agentのdescriptionの別contextをCodexでも実施済みと解釈してはいけない。主担当の制作/完成評価の別context義務はstage-common:64のまま維持される。

stage=analysisでは分析担当へ観察/保持点/候補根拠、analysis-reviewでは評価担当へ提案妥当性/欠落/保持リスク、createでは制作担当へ候補の利点/保持リスクを返す。これらを完成画像PASSに転用しない。reviewではcoordinatorが5観点へ統合し、実見していない別担当の所見を代筆しない。代替のread-only効果は所見と役割に掛かり、stage全体の制作や評価台帳記入をread-only化する宣言ではない。

## Runtime rootの実行可能性

最寄り祖先は `/Users/dm/orca/workspaces/harness/pr86-ci-fix/plugins/flyer-studio`。両manifestのnameがflyer-studioであることをレビュー側でも実際にJSON parseして確認した。SKILL:85の祖先探索は通常配置でstage-commonのskills/<stage>から2階層上と同じになる。Codexではhost注入PLUGIN_ROOTを前提にせず、shell invocationごとに解決済み絶対値を入れ、cwd推測とliteral placeholderを禁じる。Claude CodeはCLAUDE_PLUGIN_ROOTを使用する。build-flyer.py:23のbackend解決は__file__相対であり、実行開始時cwdを入力にしない。

`python3 <absolute-root>/scripts/build-flyer.py help`を/tmp cwdから実行したところexit1、Nodeのcli.cjs→project.cjs→design.cjsまで到達した後、既存環境のajv未導入で停止した。runtime-help.stderrに生出力を保存した。依存を導入せず、成功したとは扱わない。これはhost-skill-path探索の実装を試したhost trialでも、制作の完遂検査でもない。

## Rubric採点

L0はref-skill-design-rubric/references/rubric.json 1.6.0、L2はassign-skill-design-evaluator/references/rubric.json。L1指定なし。render-findings-score.pyを実行して初回と最終の生出力を保存した。最終score=97、threshold=80、passed=True、high0 / medium0 / low1。機械適用24件中23件実行、未実装rule0、別kindの21 ruleは非適用。

|rule群|評価|
|---|---|
|FM-001〜004|機械PASS。name/trigger/2条件/動作詳細の禁止に適合。|
|FM-005|既存low1。description冒頭形式に-3。今回変更なし。|
|BD-001〜003|機械PASS。目的/出力、Gotchasあり、本文300行以下。|
|BD-004|独立意味確認PASS。trigger1のbriefと基準作成→局面2〜6/8〜9、trigger2の回答から2〜3様式提案→局面7。|
|NM-001〜003|機械PASS。名前とdirectoryが一致し命名/木構造に違反なし。|
|PD-001〜002|機械PASS。referencesあり。目的/契約/禁則が冒頭30本文行内。|
|RG-001|機械PASS。rubric_hashとcomposition_hashを出力。|
|KL-001〜005|knowledge/非導入のため存在ゲートでskip/PASS。参照知識DD07/DD11は別方式でありknowledge/と同一視しない。|
|PG-001〜002|機械PASS。required責務の欠損なし（targetにresponsibilities定義はない）。|
|BND-001|機械PASS。distribution.distributable=falseのprivate kitでbundle必須対象外。|
|REG-001|機械PASS。採点器が正本のcompletenessと存在trace検証を実行。|

scorer-raw.jsonは採点器の無加工出力。scorer-reviewed.jsonは公表schemaの列に投影し、機械側pending BD-004を上記意味評価で解消したもの。機械採点器はplugin/skill/coverage等も出すため、古いadditionalProperties=falseのevaluator-output schemaにそのまま入れると既存のschema乖離がある。生出力を隠さず保存し、targetの欠陥として混ぜない。

## Feedback criteria

|ID|設計上の評価|根拠と限界|
|---|---|---|
|IN1|PASS|局面4〜6の一括シート/不足だけの再質問、完了check1/2とassertResolved。scripts/intake.cjsとtests/intake.test.cjsの出典/仮置き/confirm-factsの拒否経路を照合。テストsuiteは今回未実行。|
|IN2|PASS|局面8/9でessence-baseline・essence-check・essence-reviseを使い、直接承認記録追記を禁止。scripts/essence.cjs:63のassertResolvedと対応。|
|IN3|PASS|局面7がbasis→2〜3案→chosen/chosenBy/label反映を規定。styleProposalNeededの既存テストと対応し、様式だけ未定ならbaselineを止めない規則も保持。|
|OUT1|設計上PASS|完了check2と局面6で、項目/値/出典を利用者が認めた回だけconfirm-facts。公開範囲は目的/指針/完了条件に残る。実案件の人間承認は今回取得していない。|

## 対象外・残る限界

既存FM-005 lowと環境のajv不足を今回差分の退行と区別する。他stageのruntime_root_policy未宣言やregistryのmode分岐表現は今回変更されていないため、このレビューで修正済みとは扱わない。親が行ったrelease 1.3.2更新はmanifestのname判定を変えない。plugin固有のbuild-local-package.py:749-768はmanifest/package/EVALS/workflow/Skill/agentの版一致を要求するため、22ファイルのversionだけの同期が必要だった。metadata-onlyの独立比較はmetadata-version-review.jsonとmetadata-version-review.mdに記録する。

Claude Code/Codexのfresh-session host trial、実際の描画、利用者の事実確認は実施していない。4条件PASSは静的設計の判定である。未実施の試験や人間の承認を捏造していない。
