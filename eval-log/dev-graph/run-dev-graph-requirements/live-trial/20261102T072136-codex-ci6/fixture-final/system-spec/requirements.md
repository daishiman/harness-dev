# UTF-8行数CLI 要件

UTF-8のテキストファイルの行数を、Linux/macOSの利用者がPython標準ライブラリだけで安全に取得できるようにする。

## 利用契約

`python3 src/utf8_line_count.py PATH`。引数1件、成功はASCII十進整数とLFのみ、exit 0。失敗はstdout空、stderr説明、exit 2。

## 受入条件

- AC01: 空UTF-8ファイルはstdoutが0と改行、exit 0。
- AC02: a\nb\nは2行、a\nbも末尾改行なしで2行。
- AC03: 日本語の2行は文字数によらず2。UTF-8 strictで読む。
- AC04: LF・CRLF・単独CRをPython universal newlineの1境界として扱う。
- AC05: 存在しないpath・directory・権限拒否はstdout空、stderrに説明、exit 2、traceback無し。
- AC06: 不正UTF-8はstdout空、stderrに説明、exit 2、traceback無し。
- AC07: 引数が0件または2件以上ならusageをstderrへ出しexit 2、stdout空。
- AC08: 入力ファイルのbytesを変更せず、外部network・DB・認証・サービスを使わない。
- AC09: ファイルを行iteratorで読み、ファイル全体readで保持しない。カウンタ以外の追加メモリは1行分。

## スコープ

- 1ファイルpathのCLI入力
- UTF-8 strictとuniversal newlineの逐次カウント
- 整数と改行だけの成功出力
- 入力/復号/usage失敗時exit 2
- stdlib unittestとローカルZIP・手動利用説明

## スコープ外

- stdin・複数ファイル・再帰探索
- GUI・HTTP API・DB・認証
- Windowsでの動作保証
- pip公開・クラウドdeploy・実GitHub/Beads mutation
