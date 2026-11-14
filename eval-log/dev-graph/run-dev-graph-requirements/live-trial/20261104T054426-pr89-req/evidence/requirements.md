# 要件定義書: UTF-8 text line-count CLI (FEATURE-1)

- graph snapshot digest: `sha256:5c3e88eb932e718f4c89b71c6122df4b09f4cae40e8a06ffb23927aab31f2f45` (revision 2)
- feature package: `feature-package/feat` / `.dev-graph/plans/generations/feature-package-feat/155c3673635e04c33e09350391c06f532d079deda45052dfd6d5351b3cd6bda6`
- validated_digest (validate-system-plan.py): `sha256:155c3673635e04c33e09350391c06f532d079deda45052dfd6d5351b3cd6bda6`
- readiness_digest c11 = c02: `sha256:237d61bc757937c4fbae77ed1acbdc95452c6ac5ea0fca09ef6b0dfbdfe9ae35`
- handoff target: capability-build (task-graph mode)

## 目的

UTF-8のテキストファイルの行数を、Linux/macOSの利用者がPython標準ライブラリだけで安全に取得できるようにする。

## ゴール

python3 src/utf8_line_count.py PATH がAC01..AC09を満たし、CLI利用説明と検証記録を伴うローカル配布ZIPとして引き渡せる状態。

## スコープ (含む)

- 1ファイルpathのCLI入力
- UTF-8 strictとuniversal newlineの逐次カウント
- 整数と改行だけの成功出力
- 入力/復号/usage失敗時exit 2
- stdlib unittestとローカルZIP・手動利用説明

## スコープ (含まない)

- stdin・複数ファイル・再帰探索
- GUI・HTTP API・DB・認証
- Windowsでの動作保証
- pip公開・クラウドdeploy・実GitHub/Beads mutation

## 受入条件 (source: features/FEATURE-1.md, system-spec/requirements.md)

- AC01: 空UTF-8ファイルはstdoutが0と改行、exit 0。
- AC02: a\nb\nは2行、a\nbも末尾改行なしで2行。
- AC03: 日本語の2行は文字数によらず2。UTF-8 strictで読む。
- AC04: LF・CRLF・単独CRをPython universal newlineの1境界として扱う。
- AC05: 存在しないpath・directory・権限拒否はstdout空、stderrに説明、exit 2、traceback無し。
- AC06: 不正UTF-8はstdout空、stderrに説明、exit 2、traceback無し。
- AC07: 引数が0件または2件以上ならusageをstderrへ出しexit 2、stdout空。
- AC08: 入力ファイルのbytesを変更せず、外部network・DB・認証・サービスを使わない。
- AC09: ファイルを行iteratorで読み、ファイル全体readで保持しない。カウンタ以外の追加メモリは1行分。

## 参照 architecture

- `architecture-system`

## 要件 → source → system task trace

| node | phase | title | depends_on | source task spec | resource_scope |
|---|---|---|---|---|---|
| SYS-P01 | P01 | 要件を固定 (UTF-8 line-count) | - | `phase-01-requirements.md` | `docs/requirements-utf8-lines.md`, `evidence/utf8-lines/P01.json`, `evidence/utf8-lines/P01/` |
| SYS-P02 | P02 | CLI構造を設計 (UTF-8 line-count) | SYS-P01 | `phase-02-architecture.md` | `docs/architecture-utf8-lines.md`, `evidence/utf8-lines/P02.json`, `evidence/utf8-lines/P02/` |
| SYS-P03 | P03 | 設計を独立レビュー (UTF-8 line-count) | SYS-P02 | `phase-03-design-review.md` | `docs/design-review-utf8-lines.json`, `evidence/utf8-lines/P03.json`, `evidence/utf8-lines/P03/` |
| SYS-P04 | P04 | 境界テストを設計 (UTF-8 line-count) | SYS-P03 | `phase-04-test-design.md` | `docs/test-matrix-utf8-lines.json`, `evidence/utf8-lines/P04.json`, `evidence/utf8-lines/P04/`, `tests/fixtures/`, `tests/test_utf8_line_count.py` |
| SYS-P05 | P05 | 逐次CLIを実装 (UTF-8 line-count) | SYS-P04 | `phase-05-implementation.md` | `evidence/utf8-lines/P05.json`, `evidence/utf8-lines/P05/`, `src/utf8_line_count.py` |
| SYS-P06 | P06 | 全境界テストを実行 (UTF-8 line-count) | SYS-P05 | `phase-06-test-run.md` | `evidence/utf8-lines/P06.json`, `evidence/utf8-lines/P06/` |
| SYS-P07 | P07 | 利用者経路で受入確認 (UTF-8 line-count) | SYS-P06 | `phase-07-acceptance.md` | `evidence/utf8-lines/P07.json`, `evidence/utf8-lines/P07/` |
| SYS-P08 | P08 | 外部挙動を保ち整理 (UTF-8 line-count) | SYS-P07 | `phase-08-refactoring-migration.md` | `docs/refactoring-utf8-lines.md`, `evidence/utf8-lines/P08.json`, `evidence/utf8-lines/P08/`, `src/utf8_line_count.py`, `tests/` |
| SYS-P09 | P09 | 品質と非変更を確認 (UTF-8 line-count) | SYS-P08 | `phase-09-quality-assurance.md` | `docs/quality-utf8-lines.json`, `evidence/utf8-lines/P09.json`, `evidence/utf8-lines/P09/` |
| SYS-P10 | P10 | 最終独立レビュー (UTF-8 line-count) | SYS-P09 | `phase-10-final-review.md` | `docs/final-review-utf8-lines.json`, `evidence/utf8-lines/P10.json`, `evidence/utf8-lines/P10/` |
| SYS-P11 | P11 | 証跡manifestを固定 (UTF-8 line-count) | SYS-P10 | `phase-11-evidence.md` | `evidence/utf8-lines/P11.json`, `evidence/utf8-lines/P11/`, `evidence/utf8-lines/manifest.json` |
| SYS-P12 | P12 | 利用と保守を説明 (UTF-8 line-count) | SYS-P11 | `phase-12-documentation-operations.md` | `docs/README-utf8-lines.md`, `evidence/utf8-lines/P12.json`, `evidence/utf8-lines/P12/`, `examples/input.txt` |
| SYS-P13 | P13 | ローカル配布と仕様反映 (UTF-8 line-count) | SYS-P12 | `phase-13-release-deploy.md` | `architecture/system.md`, `dist/utf8-line-count.zip`, `evidence/utf8-lines/P13.json`, `evidence/utf8-lines/P13/`, `system-spec/index.md` |

## 実装境界

本書は要件定義のみであり、実装コードは含まない。実装は capability-build/task-graph build が task spec と本書を入力に行う。
