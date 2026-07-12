# Phase2→3 統合設計（synthesis）— 確認0自動化

## 3分析の収束（observer / meta / system + 親のコード精読）
承認の所在を「対話イベント(端末APPROVE文字列)」から「データ状態(Notionチェック)」へ移設する。三不変分離:
- **意図(I)** = Notion `送信対象=✅`/`メッセージ対象=✅`（既存の熟慮的操作・永続/帰属/時刻付き＝監査強）。追加対話確認0。
- **完全性(II)** = build+send 単一アトミック実行で APPROVE tuple を plan から self-derive。`send_guard` の Class A 機械層を全温存。
- **鮮度(III)** = C-1 を送信直前に実行。**確認0では C-1 強化が load-bearing**。

## send_guard Class A/B 分離（logic 次元の結論・system が精密化）
- **Class A（改竄検出・人間非依存・auto で全温存）**: plan_hash再計算照合 / count・per-unit content_hash再計算 / from_verified / unresolved空skip / reserved+content dedup / C-1 suppress再検証。
- **Class B（人間内容承認・auto でトートロジー化＝意図通り）**: approved_* 束縛 / approved_nonce 照合。
- ⇒ auto-approve で**失う機械安全は0**。Class B は Notion チェックへ再配置。nonce の「rendered本文を読ませる」役割のみ箱チェックに移せない → 撤去し canary/source-audit へ content-assurance を再配置。

## 確定した実装方針（フォーク以外は全確定）
1. `run-notion-gmail-send` に **auto モード**追加（既定 auto / `--interactive` で従来の複雑APPROVE＋nonce＋fork verifier を後方互換温存）。
2. auto: 内部で build-plan 自動実行 → source-audit 自動 preflight（high severity 残存なら**0送信 fail-closed**）→ 新鮮 plan から tuple self-derive → **per-unit guard loop 必須通過**（Class A 全有効）→ 送信 → 冪等ログ → 日本語レポート。
3. **stale plan.json 再利用禁止・常に再生成**（t1≈t2 で C2 改竄窓を閉じる）。
4. **C-1 を subtract-only から「鮮度照合」へ強化**（`送信対象=✅` 維持のままアドレス/会社名編集→旧アドレス送信を封鎖。確認0の主要残存リスク）。
5. nonce 撤去（auto 既定経路）。fork-LLM verifier は決定論 verify-plan.py の self-check へ統合し `--interactive` 限定に降格（C4 解消）。
6. feedback_contract 改訂（IN1改/IN3新/OUT1改・run-notion-gmail-send 1枚のみ＝verdict再生成1回）。
7. README 三本柱に「対話0 mode」行追記（nonce撤去とcanary/audit再配置のトレードオフを正直明示）。Key Rule#1『自動本送信禁止』を『intent-gate=Notionデータ層チェック』へ改稿。
8. test_send_campaign に auto モード検証点 ~9件追加。
9. content-review verdict 新SHA genuine 再生成（独立SubAgent・proposer≠approver）。
10. 無人 cron（通知チャネル/no-LLM起動）は明示 defer。

## 唯一の未確定フォーク（ユーザー確認対象）
**auto モードの既定 send 挙動:**
- 案A canary 既定（推奨/system）: 初回は安定順先頭N通だけ送信→実inbox検品→同コマンド再実行で残り（dedupでcanary skip）。端末入力0、誤本文の全員流出を機械外で防ぐ最後の砦。「最悪1回」に相当。検出は content-dedupキー未sentで判定（plan_hash基準は不可）。
- 案B 全件即送信（meta収束）: 真の0。1コマンドで全員へ。source-audit は通すが意味的誤記は止まらない。canary は使いたいとき `--canary N`。

両案とも canary も全件も実装はする。違いは「既定どちら／skip と full のどちらが明示flag」だけ。
