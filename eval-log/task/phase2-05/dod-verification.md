# phase2-05 DoD verification

Verified at: 2026-05-20

| DoD | Result | Evidence |
|---|---|---|
| DoD-1 | PASS | `grep -E "^## .*Phase 2.*発効待ち" CONVENTIONS.md` matched `## Phase 2 本番 (発効待ち: 層C 退役)` |
| DoD-2 | PASS | `grep -E "層C.*(退役\|retire)" CONVENTIONS.md` matched the Phase 2 heading,正本 row, and retire checklist heading |
| DoD-3 | PASS | `grep -cE "^\| 層[AB] " CONVENTIONS.md` returned `3` (>= 2) |
| DoD-4 | PASS | `eval-log/task/phase2-05/CONVENTIONS.before.md` exists |
| DoD-5 | PASS | `eval-log/task/phase2-05/CONVENTIONS.diff` is non-empty |
| DoD-6 | PASS | `eval-log/task/phase2-05/review-approval.json` contains `"decision": "approved"` |
| README status | PASS | `doc/migration/phase2/README.md` marks task 05 as `完了 (2026-05-20)` |

