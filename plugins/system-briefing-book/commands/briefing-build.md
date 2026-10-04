---
description: 素材フォルダと要望から業務システムの打ち合わせ資料一式を新しく作りたいとき、ヒアリングから確認点を経てまとめ HTML まで同じ工程で進めたいときに使う。
argument-hint: "<素材フォルダ> [要望をひとこと]"
allowed-tools: Read, Bash(node *), Skill
entrypoint: run-briefing
name: briefing-build
kind: command
version: 0.1.0
owner: harness maintainers
---

# /briefing-build

`$ARGUMENTS` の先頭を素材フォルダ、残りを要望として受け取り、Skill `run-briefing` に `new <素材フォルダ> [要望]` として渡す。

- 素材フォルダが無い、またはフォルダでないときは、使い方 (`/briefing-build <素材フォルダ> [要望]`) を見せて止まる。
- 要望が空でもよい。run-briefing のヒアリングで聞く。
- 出力は `<素材フォルダ>/打ち合わせ資料/`。既にあるファイルは上書きされない。打ち合わせのあとの直しは `/briefing-revise` を使う。
- Codex では `$run-briefing` に `new <素材フォルダ> [要望]` を添えて呼ぶ。

スキルの使い心地の不満や改善の案は run-skill-feedback で記録する。
