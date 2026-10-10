# 正式保存の承認と実行の契約

外部変更5スキルとその書き手が従う正本。中央guardはBashのargvを承認する。Write/Editに承認を付ける機能はない。保存可否boolean、本文の了承、パス保護フックだけでは正式保存を実行できない。

## 書き手と親の境界

- journal-composer / output-formatter は実行専用の一時下書きだけをWriteし、下書きの絶対パス・SHA256・正式保存予定先・検査受領書を親へ返す。vault、archive、Daily.mdをWrite/Editしない。
- knowledge-extractorには親が既存knowledge/をコピーした一時`knowledge_dir`を必須入力として渡す。本文の`knowledge/`・Rule A-Fの更新/削除/router/registry/sync-logはすべてこのコピーだけへ適用する。plugin_rootは参照元であり書き込み先ではない。原則DBへの変更は提案として返すだけ。親は必要なら別の一時下書きを作る。
- youtube normalizerには一時`dest_root`を渡し、正式`source_out`へ書かせない。R2の親は検証済み下書きを正式保存してから`normalized_paths`を正式パスへ写像し、R3のdetectorは正式source_outから読む。YouTube/を付けるのはnormalizerだけである。
- 一時パスはBashのtempfile.mkdtemp後にPath.resolve()で一度実体解決する（macOSの/var・/tmpなどのシステム別名をmanifestへ残さない）。正式rootも実体の絶対パスを使い、正式rootと交差しない。stageと検査はpreview前に完了する。中央CLIのproject-rootはhostが示したproject_rootと同じ絶対パスを使う。各SKILLの標準例で$PWDを使う場合は、そのBashのcwdを同じproject_rootへ固定する。pending receipt中は追加Bash/修正をせず、変更が必要なら親がcancelして作り直す。

## 下書きの正式保存

親は次のmanifestを一時ディレクトリへWriteする。rootは今回許可された正式範囲の絶対パスだけ、pathはその中の相対パス。old_sha256はコピー開始時の正式先のSHA256（未存在ならnull）で、後から再取得して競合を隠さない。sourceとnew_sha256は検証済み下書きの実体とSHA256である。

```json
{"schema_version":1,"stage_root":"/observed/temp","roots":{"goals":"/resolved/vault/05_Project/UBM/目標設定"},"entries":[{"root":"goals","path":"実ファイル名.md","operation":"write","source":"/observed/temp/実下書き.md","new_sha256":"実SHA256","old_sha256":null}]}
```

manifestの実SHA256を取得し、次の**文字列配列argv**を中央guardのpreviewに渡す。placeholderを実値へ置換してJSONとしてシリアライズし、preview/executeで同一配列を使う（shellの手書き連結やevalは禁止）。guardのルート解決・exact reply・authorize・executeは各SKILLの受領書手順に従う。

```json
["python3","/resolved/plugin/scripts/publish-staged-files.py","--manifest","/observed/temp/publication.json","--manifest-sha256","実manifestSHA256"]
```

ユーザーが保存範囲と差分を確認し、guardの確認受領書と承認受領書が揃った場合だけ、親が中央`execute`でこのargvを起動する。helperを直接Bash実行しない。exit0と正式先の保存後検査0が両方必要。2なら停止し、部分保存の可能性を含め対象と結果を報告する。自動で同じ承認を再使用しない。

archiveへの移動は、元の内容を一時コピーしたarchive宛writeと、元宛`operation:delete`/old_sha256を同じmanifestに含める。archive衝突は上書きせず名前を確認する。helperは全項目を先に検査しwrite後にdeleteする。各ファイル置換は原子的だが、バッチ全体の不可分性は保証しない。

## スクリプトが正式先を更新する経路

split-knowledge-files.py、build-capability-graph-knowledge-entry.py、validate-knowledge-graph.py（グラフ生成を伴う呼出し）、YouTubeの台帳更新/oneshotは、実際の正式先・入力・フラグ（YouTubeは隣接 `<registry名>.lock` の作成・保持も保存範囲と副作用へ明記）を含むargv全体を中央preview→ユーザー確認→authorize→executeへ渡す。正式先に対して直接Bash実行しない。これら既存スクリプトの禁止はこの実行契約の規範であり、中央pretoolの現在のパターンが全スクリプト名を機械的に遮断すると主張しない。一時コピーに対する検査/生成はpreview前に実行してよい。検証済みコピーを昇格する場合は上のmanifest方式を使う。dry-runでは正式保存とguard executeを行わない。

無人スケジューラからの直接oneshotはこの承認経路の外にある独立した運用であり、スキルから新規設定・起動しない。スキル経由のR4は親が承認されたargvをexecuteし、registryのleaseの取得/解放を同じ子プロセス内で維持する。無人実行へ流用する承認は作らない。
