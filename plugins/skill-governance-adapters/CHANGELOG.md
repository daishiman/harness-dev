# 変更履歴

0.1.17 までの版には、この履歴の記録が無い。

## 0.1.21 — 2026-11-16

- build-plugin-release.py の自動採番で作られた版。変更内容の記述は未記入。

## 0.1.18 — 2026-11-16

### 変わったこと

- 外部変更の guard の署名の鍵を、`.artifact-delivery/external-mutation/.guard-key` から `.guard-key-local` へ移した。旧名の鍵は commit `cf93ab33` で公開 repo に載ったので、guard は旧名を一切読まない。新しい鍵は `.gitignore` により repo にも配布物にも載らない。
- 鍵を初めて作る直前に、その時点の未完了の preview を key-rotation の記録で退役させる。schema の `kind` に `key-rotation` を足した。
- run-governance-adapters と run-skill-feedback の `artifact_delivery` を、`artifact-delivery-v1` を指す 1 行に替えた。利用者が選ぶのは accept-as-is と diagnose の 2 つになった。

詳しい決まりは `references/external-mutation-guard-contract.md` の「署名の鍵」と「移行」にある。

### インストール済みの写しを 0.1.18 へ更新する手順

前提: この版が main に入り、marketplace `harness-local` が指す checkout を `git pull` で最新にしてあること。

1. 開いている Claude Code と Codex のセッションを、すべて閉じる。新しいセッションの起動時に plugin が更新される。自動更新を切っている場合や確実にしたい場合は、利用者の端末で次を実行する。

   ```sh
   claude plugin marketplace update harness-local
   claude plugin update skill-governance-adapters@harness-local
   ```

2. 版と installPath を確かめる。

   ```sh
   claude plugin list | grep skill-governance-adapters
   python3 -c 'import json,os; d=json.load(open(os.path.expanduser("~/.claude/plugins/installed_plugins.json"))); print([(e["version"], e["installPath"]) for e in d["plugins"]["skill-governance-adapters@harness-local"]])'
   ```

   期待: version が `0.1.18`、installPath が `~/.claude/plugins/cache/harness-local/skill-governance-adapters/0.1.18`。`0.1.17` のままなら cache が更新されていないので、1 のコマンドを実行し直す。

3. 新しいセッションで、新しい guard が動くことを確かめる。
   - bd の書き込みを 1 件だけ、公式の流れ (preview → `CONFIRM EXTERNAL MUTATION <challenge>` → authorize → execute) で通す。
   - `.artifact-delivery/external-mutation/.guard-key-local` ができていて、権限が 0600 であること。

4. 3 が通った後で、利用者の端末から旧名の `.guard-key` の実ファイルを消す。消した後も Bash が止まらないことを確かめる。2 で 0.1.18 を確かめる前には消さない (0.1.17 はこのファイルを読んで動いている)。

### うまくいかなかったときの戻し方

- **古いセッションで Bash がすべて止まった場合。** 0.1.17 は、状態 directory があるのに `.guard-key` を読めないと、すべての Bash を止める。main を pull すると、git が他の checkout の `.guard-key` を作業ツリーから消すので、この状態になる。利用者の端末で次を実行して旧鍵を一時的に戻し、1 からやり直す。新しい guard は旧鍵を読まないので、戻しても信用は広がらない。

  ```sh
  git show <pull 前の commit>:.artifact-delivery/external-mutation/.guard-key > .artifact-delivery/external-mutation/.guard-key
  ```

- **更新前に作った preview が確認できない場合。** 更新前の未完了の preview は、新しい鍵では確かめられない。最初の preview で退役し、Bash を止めなくなる。必要な操作は preview から作り直す。
- **0.1.18 で preview の公式の呼び出しが止められた場合。** hook の stderr の全文と、呼び出しに使った path (`extract-plugin-root.py skill-governance-adapters` が出す絶対 path) を記録して、bd に起票する。0.1.17 へは戻さない。0.1.17 は公開済みの旧鍵で封を確かめるので、戻すと誰でも作れる封を信用する状態に戻る。
