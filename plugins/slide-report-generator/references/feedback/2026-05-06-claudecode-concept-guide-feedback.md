---
title: Claude Code 概念ガイド feedback
date: 2026-05-06
status: applied
skill_version_registered: 7.1.2
---

# Feedback

## 発見した問題

| 問題 | 分類 | 反映先 | 状態 |
|---|---|---|---|
| HTMLに `[object Object]` が混入 | 構造的問題 | `scripts/template-engine.cjs`, `scripts/render-slide.cjs`, `scripts/verify-slides.js` | applied |
| `sync-checker.js` とrender出力タグ/属性が不一致 | 構造的問題 | `scripts/render-slide.cjs`, `agents/slide-renderer.md` | applied |
| `structure.md` が決定論renderから出力されない | 構造的問題 | `scripts/render-slide.cjs`, `agents/slide-renderer.md` | applied |
| `diagram-person-network` が文字列配列を扱えない | テンプレート入力正規化不足 | `scripts/render-slide.cjs` | applied |
| `verify-slides.js` が shell quote で失敗 | 検証スクリプト不具合 | `scripts/verify-slides.js` | applied |
| `build-single-html.js` が `--out` と `defer` 付きscriptに弱い | デプロイスクリプト不具合 | `scripts/build-single-html.js` | applied |
| 非エンジニア向けデプロイガイドの粒度不足 | 出力テンプレート改善候補 | 今回は `deploy-guide.md` へ反映。スキルテンプレート化は次回候補 | recorded |

## 適用内容

- changelog に `7.1.2` を追加。
- 決定論レンダラの出力を `sync-checker.js` と整合させた。
- 可視テキストの型崩れを公式 `verify-slides.js` で検出できるようにした。
- GAS single build のCLI互換性を上げた。

## 大規模変更の扱い

アーキテクチャ全体の再設計は不要と判断した。今回の問題は小中規模のスクリプト修正で吸収できた。
