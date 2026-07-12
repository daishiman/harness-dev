# Phase1 俯瞰: skill-intake standalone 自己完結性

対象: 非技術者向け intake→Markdown/JSON/Notion publish plugin。共有ローダ notion_config.py を vendoring 同梱し単独 install のコアフロー自己完結を狙う。

## 第一印象の懸念（単独自己完結性）
- references/notion-per-repo-setup.md の表(L113-114)が notion_config.py を「Loader symlink」「YES(symlink)」と記載し、vendoring実体化方針(plugin.json/lint/sync.sh)と直接矛盾。doc が dangling 回帰を誘発。
- drift防止機構 sync-intake-vendored.sh / lint-intake-vendored-ssot.py が両方 repo-root scripts/ にあり plugin 外。単独 install で同梱されず byte一致強制が効かない。
- aggregator SKILL.md(L32) lint_scripts が ../../scripts/lint_subagent_seven_layer.py を越境参照（実体は plugin 内 scripts/ にあるが path 不整合）。
- lint_subagent_seven_layer.py が REPO=parents[3] を repo-root 前提で算出。plugin 単独配置だと path 破綻の懸念。
- setup-doc が build-notion-config.py / sync-notion-schema.py を repo-root scripts/ 前提で案内し plugin 単独に未同梱。

## 関連ファイル一覧（Phase2 fresh read 推奨）
- plugins/skill-intake/.claude-plugin/plugin.json
- plugins/skill-intake/README.md
- plugins/skill-intake/references/notion-per-repo-setup.md
- plugins/skill-intake/scripts/notion_config.py
- plugins/skill-intake/scripts/notion_http.py
- plugins/skill-intake/scripts/lint_subagent_seven_layer.py
- plugins/skill-intake/skills/run-skill-intake-aggregator/SKILL.md
- plugins/skill-intake/skills/run-notion-intake-publish/references/resource-map.yaml
- scripts/lint-intake-vendored-ssot.py
- scripts/sync-intake-vendored.sh
