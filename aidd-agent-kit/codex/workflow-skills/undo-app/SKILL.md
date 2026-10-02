---
name: undo-app
description: 公開済みWebアプリの直前の変更を、履歴を消さずに安全に取り消して再公開する。Codexで「前の状態に戻して」「変更を取り消して」「$undo-app」と依頼されたときに使用する。
---

# Undo app change

1. 最初に `$solo-git-flow` を使用し、同スキルの§7にある取り消し手順を確認する。
2. `git log --oneline` とリリースタグから戻す対象を特定する。曖昧でも質問一覧を返さず、依頼文・リリース時刻・影響範囲から最有力の対象を1つ選び、非破壊の差分プレビューと復元方法を先に示す。
3. 必ず `git revert` を使う。`git reset --hard` と `push --force` は使用しない。
4. データベース変更を含む場合はバックアップ、影響行、コードだけ戻した場合の挙動を調査し、推奨する復旧計画を1つ作る。不可逆なデータ復元を実行する直前だけ、その計画への一点承認を得る。
5. 対象コミットをrevertした後、`pnpm run preview` で戻った状態を確認する。
6. `.github/workflows/deploy.yml`がある場合は main へ反映し(`git tag --list v1` で到達済みならPR経由、未達なら main へ直接コミットして push)、mainのCI成功後に起動したDeployを監視する。手元から`wrangler deploy`して自動経路を迂回しない。CI/CD未導入の初回公開または記録を残す緊急対応だけ、`cloudflare-secure-deploy`と`wrangler`に従いcleanな確定コミットから公開する。
7. 本番URLを時間を空けて2回確認し、「1つ前の状態に戻しました」、確認用URL、戻した内容の順で、git用語を使わず報告する。
