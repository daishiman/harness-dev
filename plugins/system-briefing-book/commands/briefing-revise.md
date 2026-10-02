---
description: 打ち合わせのあとにメモから変更点をまとめて資料の版を上げたいとき、影響する工程だけをやり直してまとめ HTML を作り直したいときに使う。
argument-hint: "<資料フォルダ> <打ち合わせメモのファイルか文章>"
allowed-tools: Read, Bash(node *), Skill
entrypoint: run-briefing
name: briefing-revise
kind: command
version: 0.1.0
owner: harness maintainers
---

# /briefing-revise

`$ARGUMENTS` の先頭を資料フォルダ (`<素材フォルダ>/打ち合わせ資料`)、残りを打ち合わせメモとして受け取り、Skill `run-briefing` に `revise <資料フォルダ> <打ち合わせメモ>` として渡す。

- 資料フォルダに 要件定義.md と briefing.json が無いときは、先に `/briefing-build` を使うよう伝えて止まる。
- メモがファイルの場所なら、そのファイルを読んで渡す。文章ならそのまま渡す。メモが空なら何が変わったかを聞く。
- 版は 1 つ上がり (例: v0.1 → v0.2)、変更点.md に新しい版の節が足される。
- Codex では `$run-briefing` に `revise <資料フォルダ> <打ち合わせメモ>` を添えて呼ぶ。

スキルの使い心地の不満や改善の案は run-skill-feedback で記録する。
