# dev-graph artifact templates

このディレクトリは、導入先リポジトリへ `dev-graph init` が配置するテンプレート正本の L3 draft である。実装時の配置先は `plugins/dev-graph/templates/`、導入先での編集可能コピーは `.dev-graph/templates/` とする。

共有harness codeはsymlink元から読めるが、content/config/stateは常に呼出し元repositoryが正本である。`repo-config.example.json`を導入先`.dev-graph/config.json`へ初回だけ配置し、保存pathは全てrepository相対とする。

repo-local runtime 契約の共通正本は system-dev-planner の `plugin-plans/system-dev-planner/references/repo-local-runtime-contract.md` を参照する (dev-graph C24 と system-dev-planner C09 は同一契約に従う)。

## 選択規則

1. `artifact_kind` から `issue.md` / `task.md` / `document.md` / `specification.md` / `architecture.md` を自動選択する。
2. `architecture` は内容から `frontend` / `backend` / `infrastructure` / `data` / `security` を複数選択できる。該当 subtype のテンプレートを基底テンプレートへ合成する。
3. API を公開・変更する仕様では `api-contract.md` を `specification.md` の API 契約へ合成する。
4. 利用者へ保存先やテンプレート名を質問しない。分類 confidence が閾値未満の場合だけ、分類候補と生成予定 path を確認する。
5. 空見出し、`TBD`、`TODO`、`未定` は充足と数えない。非該当は `N/A: <理由>` を必須とする。
6. システム計画では1 featureにつきP01..P13のexact 13件の実行task仕様書を生成する。別の13 lifecycle文書や可変N taskは生成しない。仕様書・アーキテクチャは`system-spec-harness`の確定成果物を引用する。**この実行task仕様を emit する主体は system-dev-planner (ミクロ層) であり、その正本テンプレートは `plugin-plans/system-dev-planner/references/system-task-spec-template.md`**。dev-graph 配下の `templates/system-task-spec.md` は当該正本への後方互換 pointer であり、dev-graph 自身は runtime task spec を emit せず登録・投影・完了収束のみを担う。
7. project rootは`--repo-root`、trusted project env、`git rev-parse --show-toplevel`、cwd markerの順で候補を解決する。候補のrealpathがhost宣言`$CLAUDE_PROJECT_DIR`と一致する場合だけ採用し、symlinkの物理source pathをcontent rootに使わない。

## 検証規則

- `template-contract.json` が種別ごとの必須セクションと subtype 合成規則の正本である。
- `common-frontmatter.md` が全 Markdown 成果物の共通メタデータ正本である。
- `validate-graph-schema.py` は frontmatter、見出し、placeholder、参照先、`file_path` parity を fail-closed で検証する。
- `implementation_readiness` は必須セクションの `complete / incomplete / not_applicable` と不足一覧から算出する。単なる文字数では判定しない。
- テンプレートの変更は `template_version` を更新し、既存文書は自動全書換せず migration preview を生成する。
- システム開発task planはplugin固有のcomponent_kind/build_targetを流用せず、system workstreamと実装対象pathへ置換する。
- system planは評価前にdraft stagingし、同一digestの決定論検証+独立4条件評価PASS後だけactive/confirmed/passへatomic promotionする。
- realpathがrepository root外へ出る設定、content symlink、`..` traversal、repository_id不一致、shared cache/lock pathはfail-closedにする。
- `repository_id`はcanonical GitHub remoteから`github:<owner>/<repo>`を再導出して比較する。remoteがない場合はgit common-dir realpathをSHA-256化した`local:sha256:<64hex>`を用い、repo移動時は明示的rebind確認を要求する。
- C24は起動後に検査できるcontent symlinkの壊れ/移動を診断する。harness自身のsymlinkが壊れるとC24を起動できないため、host launcher/installerがentrypoint実在性を起動前検査する。
