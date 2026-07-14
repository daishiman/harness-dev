# Repo-local runtime contract

## Authority boundary

- `plugin source root`: symlink の物理解決先。Python/Markdown/assets を読むためだけに使い、管理 content/config/state の正本にはしない。
- `caller repository root`: 実行対象 repository の content authority。`.dev-graph/config.json`、system-spec、architecture、tasks、issues、docs、state/cache/lock/staging/published はすべてこの root 内に置く。
- root 解決順は `--repo-root` > allowlist 済み `SYSTEM_DEV_PROJECT_ROOT` / `CLAUDE_PROJECT_DIR` > `git rev-parse --show-toplevel` > cwd から上方探索した `.dev-graph/config.json`。選択候補のrealpathがhost宣言`$CLAUDE_PROJECT_DIR`のrealpathと一致する場合だけ採用し、複数候補の不一致やhost境界外候補は黙って選ばず exit 2。

## Repo-local config

正本は `<CALLER_REPO>/.dev-graph/config.json`。保存値は repository 相対 path のみとする。基底形は dev-graph 形 (`repository_id`/`content_roots`/`local_state`/`path_policy`、正本形=`plugin-plans/dev-graph/templates/repo-config.example.json`) であり、sdp は追加 section `plan_roots` (staging/published/state) を非破壊で追記する共存形を読む (`schemas-draft/project-config.schema.json` 準拠)。

```json
{
  "schema_version": "1.0.0",
  "repository_id": "github:example/example-repository",
  "content_roots": {
    "issues": "issues",
    "tasks": "tasks",
    "specifications": "specs",
    "architecture": "architecture",
    "documents": "docs",
    "system_spec": "system-spec"
  },
  "local_state": {
    "cache": ".dev-graph/cache",
    "locks": ".dev-graph/locks"
  },
  "path_policy": {
    "authority": "caller-repository",
    "stored_paths": "repository-relative",
    "allow_outside_repository": false,
    "follow_content_symlinks_outside_repository": false
  },
  "plan_roots": {
    "staging": ".dev-graph/staging",
    "published": ".dev-graph/plans",
    "state": ".dev-graph/state"
  }
}
```

## Path guard

1. config 値の absolute path、空 path、`..` segment、NUL を拒否する。
2. `candidate = repo_root / relative` と `repo_real = repo_root.resolve()` を作り、既存対象は `candidate.resolve(strict=true)`、作成予定対象は実在する最長親を realpath 化する。
3. `os.path.commonpath([repo_real, candidate_real]) == repo_real` を満たさないものを拒否する。symlink が root 外へ逃げる場合も拒否する。
4. repo identity (`st_dev`, `st_ino`, git common dir) を実行中に pin し、promotion 前に再照合する。root 移動は再解決を要求する。
5. `repository_id` の正本値は C10 init が canonical GitHub remote (`github:<owner>/<repo>`、remote がない場合は git common-dir realpath を SHA-256 化した `local:sha256:<64hex>`) から導出して書込む。asset の example/sentinel 値 (`__DERIVED_AT_INIT__` 等) をそのまま配置することは禁止する。C09 は同じ規則で再導出して config 値と照合し、不一致 (sentinel 残存を含む) は exit 2 で拒否する。local repo 移動時は明示的 rebind 確認を要求する。
6. C09起動後に検査可能なcontent symlinkがbroken/movedなら診断付きexit 2とする。harness自身のsymlinkがbrokenならC09を起動できないため、host launcher/installerがentrypoint実在性を起動前preflightし、修復導線を返す。

## Isolation and init

- state/cache/lock/staging/published key は `sha256(repo_real + git_common_dir)` を repo-local ledger に記録し、global/shared temp を正本にしない。
- 2 repo の並列実行は同じ plugin source を共有してよいが、content path と lock namespace を共有してはならない。
- init は missing file/dir のみ作成する。既存ファイルは byte comparison し、同一なら `skipped_same`、異なるなら `preserved_conflict` として receipt に記録し、上書きしない。
- 既存 `.dev-graph/config.json` がある場合、init は missing-key 追記 merge のみ行う: 不足 section/キー (`plan_roots` 等) を追記し、既存キーの値は一切上書きしない。
- init の再実行は同じ receipt 意味結果を返す。既存 docs/specs/architecture/tasks/issues の rename/delete は行わない。

## Acceptance fixtures

- repo-A / repo-B が同じ plugin source symlink を使い、同名 `system-spec/index.md` に異なる marker を持つ fixture。
- repo-A 実行が repo-B marker を一度も読まないこと、逆も同様であること。
- root 外を指す config path、`../other-repo`、root 外 symlink を全拒否すること。
- broken/moved content symlinkが診断付きexit 2になり、broken harness symlinkはhost launcher/installer fixtureが起動前に検出すること。
- root候補が`$CLAUDE_PROJECT_DIR`と不一致、またはrepository_id再導出値がconfigと不一致ならexit 2になること。
- init 2 回目が既存 docs を byte-for-byte 保持すること。
