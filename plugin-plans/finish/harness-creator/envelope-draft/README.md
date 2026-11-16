# envelope-draft (履歴の写し)

`plugin.json` は harness-creator 1.1.0 の計画時に作った manifest の下書きで、今の正本ではない。実行時にこの file を読む箇所は無い。今の manifest は `plugins/harness-creator/.claude-plugin/plugin.json`、hook の配線は `plugins/harness-creator/hooks/hooks.json` が正本。

下書きの hook 行のうち、次の 4 本の script は 1.4.65 (PR #90、commit 740f63f0) で削除した。計画時の記録として行は残してある。

| 下書きの行 | 指している script |
|---|---|
| L36 | `skills/run-skill-update-notifier/scripts/hook-cache-refresh.py` |
| L37 | `skills/ref-task-context-map/scripts/preload-context-map.py` |
| L53 | `skills/run-skill-update-notifier/scripts/hook-notify-skill-end.py` |
| L55 | `skills/run-elegant-review/scripts/check-review-trigger.py` |
