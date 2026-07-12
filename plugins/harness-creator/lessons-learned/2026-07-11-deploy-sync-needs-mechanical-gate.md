---
date: 2026-07-11
---

# deploy-sync (.claude symlink 展開) は宣言契約だけでは task-graph モードで skip される

## 背景

extract-system-blueprint build (2026-07-11) が全ゲート緑で completed 宣言されたのに `.claude/{skills,agents,commands}/` へ symlink 未展開のまま終わり、Claude Code が新規 plugin を認識しなかった (ユーザー指摘で発覚)。sync 契約は run-build-skill SKILL.md に「build/更新後は必ず実行」と宣言済みだったが、task-graph route モードでは build が route 単位で SubAgent に分散し、repo-root 横断の仕上げ手順を担う owner がどのノードにも割当てられていなかった (2026-07-11-surfaces-must-be-builder-assigned と同型の owner 不在 skip)。

## 知見

「build/更新後に必ず X せよ」型の repo-root 横断契約は、分散 build では担当 owner が構造的に消えるため、完了ゲートへ機械検査として組込まない限り履行されない (保証要件は機械層で担保)。repo root 依存の検査は cwd でなく成果物 (task-state) パスから上方解決すると、実 run で必ず enforce・隔離テスト/配布先で fail-soft の両立ができる。

## 適用先

- TG-C08 `record-task-graph-knowledge.py` 完了ゲート第3段: 生成器 `build-claude-symlinks.py --check` で drift=blocked+fix_command 単体提示。実装済。
- `commands/capability-build.md`: dispatcher は全 route build 完了後・TG-C08 前に `bash scripts/sync-skills-to-claude.sh --apply` を先回り実行。実装済。
- 他の「完了後に必ず」系契約 (例: make sync 系・投影再生成系) も同パターンで完了ゲートへ組込めるか点検する。
