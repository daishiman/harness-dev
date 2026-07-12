# Question Bank Pointer

質問雛形の正本は旧 aggregator references に残置 (Phase C で本 references へ統合判断)。

参照先:
- `references/question-plan.json` — **どの Q-ID を出すかの決定論的正本** (depth×軸→Q-ID)。質問選択はここに従い `scripts/build-questions.py` が機械的に解決する。
- `plugins/skill-intake/references/question-bank.md` — Q-ID → 文面の正本 (索引表)
- `plugins/skill-intake/references/vocabulary-tiers.md` — 専門用語 → 平易語対応表
- `plugins/skill-intake/references/non-tech-vocabulary.md` — 非エンジニア向け言い換え

**再現性ルール**: 質問は「都度立案」しない。`build-questions.py` が返す Q-ID/文面を verbatim で使う。tier 対応は vocabulary-tiers.md の固定対応表による語置換のみ (質問そのものの改変・追加・削除は禁止)。これにより実行者が変わっても同じ入力なら同じ質問列になる。
