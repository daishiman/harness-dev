# Makefile — harness ローカル開発補助
# 二重正本 drift 防止: creator-kit/skills/ 変更後に sync ターゲットを実行すること。
# CI では --check gate (harness-creator-kit-ci.yml) が走るため二重防護となる。

.PHONY: sync sync-check native-surfaces native-surfaces-dry-run native-surfaces-apply native-surfaces-check native-surfaces-pr-ready lint plugin-package-check contract-intake vendored-ssot tenant-isolation runtime-portability readme-portability prompt-contract-drift company-master-vendored config-version-lock feedback-contract content-review pytest coverage llm-coverage coverage-gate harness-coverage harness-ratchet test help

# LLM_COV_SINCE: 新規スキルの coverage gate 境界日。これ以降に since された loop-kind スキルは
# coverage-gate で <80% なら fail-closed。既存スキルは ratchet で段階的に底上げ。
LLM_COV_SINCE ?= 2026-06-24
COV_THRESHOLD ?= 80

## sync: creator-kit/skills/ を .claude/skills/ に同期する（--apply）
sync:
	bash scripts/sync-skills-to-claude.sh --apply

## sync-check: 同期差分がないことを確認する（CI gate 相当、--check）
sync-check:
	bash scripts/sync-skills-to-claude.sh --check

## native-surfaces: repo-owned native projections を apply してから read-only parity check する
native-surfaces:
	$(MAKE) native-surfaces-apply
	$(MAKE) native-surfaces-check

## native-surfaces-dry-run: C01 の単一 desired-set で変更計画だけを表示する（無書込）
native-surfaces-dry-run:
	python3 plugins/harness-creator/scripts/sync-native-surfaces.py --repo-root . --dry-run

## native-surfaces-apply: repo-present + project-enabled scope の差分だけを原子的に反映する（trust は別 user gate）
native-surfaces-apply:
	python3 plugins/harness-creator/scripts/sync-native-surfaces.py --repo-root . --apply

## native-surfaces-check: native surface / dual manifest / marketplace parity を書込なしで検査する
native-surfaces-check:
	python3 plugins/harness-creator/scripts/sync-native-surfaces.py --repo-root . --check

## native-surfaces-pr-ready: local-only preflight (apply→check→schema validate→diff visibility; PR は作成しない)
native-surfaces-pr-ready:
	$(MAKE) native-surfaces-apply
	$(MAKE) native-surfaces-check
	python3 -c 'import json,tomllib; json.load(open(".claude/settings.json")); json.load(open(".codex/hooks.json")); json.load(open(".agents/plugins/marketplace.json")); tomllib.load(open(".codex/config.toml","rb")); tomllib.load(open("plugins/harness-creator/native-surfaces.toml","rb"))'
	git status --short -- .claude/skills .claude/agents .claude/commands .claude/settings.json .codex/hooks.json .codex/config.toml .agents/plugins/marketplace.json plugins/harness-creator/.claude-plugin/plugin.json plugins/harness-creator/.codex-plugin/plugin.json plugins/harness-creator/native-surfaces.toml
	git diff -- .claude/skills .claude/agents .claude/commands .claude/settings.json .codex/hooks.json .codex/config.toml .agents/plugins/marketplace.json plugins/harness-creator/.claude-plugin/plugin.json plugins/harness-creator/.codex-plugin/plugin.json plugins/harness-creator/native-surfaces.toml

## lint: スキル lint 一式 + skill-intake contract test + vendored SSOT + runtime/README ポータビリティ + company-master vendored 検証を実行する
lint: contract-intake vendored-ssot legacy-plugin-name tenant-isolation runtime-portability readme-portability prompt-contract-drift company-master-vendored
	python3 scripts/lint-skill-name.py --skills-dir plugins/harness-creator/skills
	python3 scripts/lint-skill-description.py --skills-dir plugins/harness-creator/skills
	python3 scripts/validate-frontmatter.py --skills-dir plugins/harness-creator/skills
	python3 scripts/lint-skill-name.py --skills-dir plugins/company-master/skills
	python3 scripts/lint-skill-description.py --skills-dir plugins/company-master/skills
	python3 scripts/validate-frontmatter.py --skills-dir plugins/company-master/skills
	python3 scripts/lint-skill-name.py --skills-dir plugins/contract-generator/skills
	python3 scripts/lint-skill-description.py --skills-dir plugins/contract-generator/skills
	python3 scripts/validate-frontmatter.py --skills-dir plugins/contract-generator/skills
	python3 scripts/lint-skill-name.py --skills-dir plugins/skill-intake/skills
	python3 scripts/lint-skill-description.py --skills-dir plugins/skill-intake/skills
	# skill-intake の validate-frontmatter は effect enum 違反で FAIL するため
	# lint-plugin-lint-coverage.py の ALLOWLIST に理由付きで宣言済み (後日是正)
	python3 scripts/lint-skill-name.py --skills-dir plugins/mf-kessai-invoice-check/skills
	python3 scripts/lint-skill-description.py --skills-dir plugins/mf-kessai-invoice-check/skills
	python3 scripts/validate-frontmatter.py --skills-dir plugins/mf-kessai-invoice-check/skills
	python3 scripts/lint-skill-name.py --skills-dir plugins/notion-gmail-send/skills
	python3 scripts/lint-skill-description.py --skills-dir plugins/notion-gmail-send/skills
	python3 scripts/validate-frontmatter.py --skills-dir plugins/notion-gmail-send/skills
	python3 scripts/lint-skill-name.py --skills-dir plugins/system-spec-harness/skills
	python3 scripts/lint-skill-description.py --skills-dir plugins/system-spec-harness/skills
	python3 scripts/validate-frontmatter.py --skills-dir plugins/system-spec-harness/skills
	python3 scripts/lint-plugin-lint-coverage.py
	# repo 全域の全 test が CI のテスト実行で到達することを fail-closed 検査 (elegant-review 2026-06-30)
	python3 scripts/lint-test-discovery-coverage.py
	# marketplace ↔ plugins / bundles 双方向整合 (MK-001..003 / BD-001) を fail-closed 検査
	python3 scripts/validate-plugin-completeness.py
	# 焼き込みconfig (*.default.json / *.fixed.json) の内容変更が version bump を伴うか fail-closed 検査
	#   (version 据え置き→配布キャッシュ未更新→毎回 fail-closed の再発を封じる。elegant-review 2026-07-01)
	python3 scripts/lint-config-version-sync.py
	# 片方向 writer: harness の task-graph consumer が producer 所有 plan (task-graph/inventory/phase/
	#   plugin-plans) へ AST 上で直書きしないことを fail-closed 検査 (per-script test を補完・S1)
	python3 scripts/lint-harness-plan-writeguard.py
	# knowledge/ (JSON ストア) ↔ lessons-learned/ (散文ログ) の役割分担を fail-closed 検査
	#   (散文 .md の knowledge/ 直下混入・lessons-index の dangling source.file・lesson 形式。2026-07-11)
	python3 scripts/lint-knowledge-layout.py

## vendored-ssot: plugin 同梱 SSOT (notion_config.py / feedback_contract_ssot.py) が正本と byte 一致か検証
vendored-ssot:
	python3 scripts/lint-vendored-ssot.py

## legacy-plugin-name: 改名済み旧 plugin 固有名の能動層再流入を遮断 (2026-07-02 改名)
legacy-plugin-name:
	python3 scripts/lint-legacy-plugin-name.py

## tenant-isolation: distributable core に企業固有値が再流入しないことを検査
tenant-isolation:
	python3 scripts/lint-tenant-isolation.py

## runtime-portability: runtime hook script が import-time に自 plugin 外を fail-closed 依存しないか静的検査
##   単独 install (plugin のみ install) で全フックが exit 0 を維持する不変条件を機械担保する。
runtime-portability:
	python3 scripts/lint-runtime-portability.py

## readme-portability: marketplace 配布 plugin の README bash/sh フェンスが install 位置に依存しないか静的検査
##   裸 $CLAUDE_PLUGIN_ROOT 一次手順 / repo 相対 python3 plugins/<name>/... / os.environ 添字を fail-closed 検出し、
##   生ターミナル空展開事故の恒久再発を防ぐ (company-master deferred の文書層 lint 回収)。
readme-portability:
	python3 scripts/lint-readme-plugin-root-portability.py

## prompt-contract-drift: 7 層プロンプトの契約記述 (参照 schema/reference/script パス・allowed-tools) が
##   実装と乖離する再ドリフトを機械検出。Tier1 (参照パス実在) は fail-closed、
##   Tier2 (allowed-tools) は forked 責務の binding 曖昧性ゆえ WARN (report-only)。
##   content-review の LLM 監査に頼らず、schema 移動/削除時に即赤化して再発を封じる。
prompt-contract-drift:
	python3 scripts/lint-prompt-contract-drift.py --all

## company-master-vendored: company-master の scripts が外部依存ゼロ(空 vendor が正常)か機械検証
company-master-vendored:
	python3 scripts/lint-company-master-vendored-deps.py

## config-version-lock: 焼き込みconfig (*.default.json / *.fixed.json) を変更した後に lockfile を再生成する
##   version bump 漏れ / marketplace 不一致は書込みを拒否する (真因の papering over を防ぐ fail-closed)。
config-version-lock:
	python3 scripts/lint-config-version-sync.py --write

## contract-intake: skill-intake の enum SSOT / 軸分離 / 二重定義検出 contract test
contract-intake:
	python3 scripts/contract-intake-enum-ssot.py

## plugin-package-check: 全 plugin の package completeness (PKG-002〜008) を検査する
##   実検査器 (assign-plugin-package-evaluator/scripts/validate-plugin-package.py) は単一
##   plugin 用のため、全 plugin を回す advisory ラッパー経由で呼ぶ。PKG-002/004 は未採用の
##   将来標準のため現状は非ブロッキング (詳細は scripts/validate-plugin-packages.py)。
plugin-package-check:
	python3 scripts/validate-plugin-packages.py

## feedback-contract: 量産先 loop-kind スキルが frontmatter に評価基準を携帯するか repo 全体検査
feedback-contract:
	python3 scripts/lint-feedback-contract.py --all

## content-review: 全スキルの content-review verdict 存在・PASS・sha一致・criteria突合を repo 全体検査
content-review:
	python3 scripts/lint-content-review.py --all
	python3 scripts/lint-live-trial-verdict.py --all

## pytest: tests/ 配下の振る舞いテストを実行する (hook-guard-skillgen 等の機械保証を回帰検証)
pytest:
	python3 -m pytest tests/ -q

## coverage: コード側の行カバレッジを pytest-cov で計測する (計測専用。テスト合否は `make pytest`/`make test` が担保)
##   COVERAGE_FILE を絶対パス固定し subprocess 計測データを cwd 変更に依らず repo root へ集約する。
##   この計測モードでは coverage .pth が subprocess 出力に混入し一部 IO テストが赤化するが、
##   合否判定は coverage 無しの `make test` を正とするため許容 (|| true)。行カバレッジ数値のみ採取する。
coverage:
	python3 -m coverage erase || true
	COVERAGE_FILE="$(PWD)/.coverage" COVERAGE_PROCESS_START="$(PWD)/.coveragerc" PYTHONPATH="$(PWD)" \
	  python3 -m pytest tests/ -q --cov --cov-report=json:eval-log/code-coverage.json -p no:cacheprovider || true
	@python3 -c "import json;d=json.load(open('eval-log/code-coverage.json'));p=round(d['totals']['percent_covered'],1);print(f'[coverage] code line coverage {p}% / 閾値 $(COV_THRESHOLD)%');print('[OK] code coverage >=閾値' if p>=$(COV_THRESHOLD) else '[WARN] code coverage <閾値 (ratchet)')"
	@python3 -c "import json;d=json.load(open('eval-log/code-coverage.json'));p=round(d['totals']['percent_covered'],1);print(f'[coverage] code line coverage {p}% / 閾値 $(COV_THRESHOLD)%');print('[WARN] code coverage <閾値 (ratchet)' if p < $(COV_THRESHOLD) else '[OK] code coverage >=閾値')"

## llm-coverage: LLM 駆動部分(criteria+checklist 被覆)のカバレッジを計測する (WARN, ratchet baseline)
llm-coverage:
	python3 scripts/validate-llm-coverage.py --all --threshold $(COV_THRESHOLD)

## coverage-gate: 新規 loop-kind スキル(since>=LLM_COV_SINCE)が <80% なら fail-closed (CI gate)
coverage-gate:
	python3 scripts/validate-llm-coverage.py --all --threshold $(COV_THRESHOLD) \
	  --gate-new --since $(LLM_COV_SINCE)

## harness-coverage: ハーネス仕様(全種別×二軸 >=80%)の整備状況を横断集計する (doc/harness-coverage-spec.md)
##   先に make coverage / llm-coverage を走らせ eval-log の *-coverage.json を生成しておくこと。
harness-coverage:
	python3 scripts/validate-harness-coverage.py --threshold $(COV_THRESHOLD)

## harness-ratchet: ハーネス仕様カバレッジが floor(現状値=eval-log/harness-coverage-floor.json) を下回ったら fail-closed (回帰ガード)
##   80% 絶対 gate (harness-coverage) は WARN のまま漸進を許すが、現状より悪化 (verdict/test 未添付の新規 artifact 追加) は blocking で止める。改善時は --update-floor で floor を引き上げる。
harness-ratchet:
	python3 scripts/validate-harness-coverage.py --ratchet

## test: sync-check + lint + plugin-package-check + feedback-contract + content-review + pytest + gate-phase0 を順に実行する
##   (coverage / llm-coverage は WARN のため test には含めず、coverage-gate を CI で別途実行する)
test: sync-check lint plugin-package-check feedback-contract content-review pytest llm-coverage
	python3 scripts/gate-phase0.py

## help: このメッセージを表示する
help:
	@grep -E '^## ' Makefile | sed 's/## /  /'
