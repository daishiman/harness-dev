#!/bin/bash
# shellcheck shell=bash
# =====================================================
#  キットの自己修復 (install-mac.command / setup-env-mac.command 共通)
#
#  このファイルは単体で実行しない。両 .command が
#    . "$KIT_DIR/scripts/lib/self-heal.sh"
#  で読み込み、self_heal_kit を呼ぶ。呼び出し側で KIT_DIR
#  (キットのフォルダの絶対パス) が解決済みであることを前提にする。
#
#  以前は同じ関数を両 .command に複製し、package-kit.sh が byte 一致を
#  検査していた。複製を減らす変更が検査で必ず落ちる構造だったため、
#  正本をここ 1 か所にし、検査は「両 .command がこのファイルを source
#  している」ことへ置き換えた。
# =====================================================

# ブラウザ・メール・AirDrop 経由で受け取ったZIPを展開すると、中の全ファイルに
# 隔離属性(com.apple.quarantine)が伝播する。macOS 15 以降はこの属性が付いた
# .command をダブルクリックすると「Appleは…検証できませんでした」のダイアログ
# (既定ボタンが「ゴミ箱に入れる」)が出る。
# ターミナル経由の起動には隔離属性が適用されないため、この関数が動いている
# 時点で利用者は明示的に実行を選んでいる。ここでキット自身の状態を整えれば、
# 2回目以降はダブルクリックでも起動できるようになる。
#
# 方針:
#   - 対象範囲はキットのフォルダ全体。隔離属性は展開時に全ファイルへ伝播するため、
#     .command だけ外しても、後から開く .html マニュアルなどが残ってしまう。
#   - 告知は「実際に直したときだけ」。何も直していないのに毎回メッセージを出すと、
#     利用者は正常な出力と異常な出力を区別できなくなる。
#   - 失敗しても中断しない。自己修復はあくまで次回以降のための補助であり、
#     今回の導入自体は既に実行できている。中断させる理由がない。
self_heal_kit() {
  _chmodded=0

  # 隔離属性: 1つでも付いていれば、フォルダ全体からまとめて外す。
  #
  # 検出に find -xattrname を使ってはいけない。この述語は比較的新しい macOS に
  # しか無く、古い機では find が usage エラーで即座に終わる。2>/dev/null が
  # それを捨てるので「隔離属性は付いていない」と誤判定し、解除を黙って飛ばす。
  # つまり、いちばん古い機で、いちばん必要な処理だけが消える。
  # xattr はどのバージョンにも在るため、そちらで見る。
  if xattr -r "$KIT_DIR" 2>/dev/null | grep -q com.apple.quarantine; then
    if xattr -dr com.apple.quarantine "$KIT_DIR" 2>/dev/null; then
      echo "  ダブルクリックで開けるように、キットの隔離設定を解除しました。"
    else
      echo "  [注意] キットの隔離設定を解除できませんでした。"
      echo "  次回もダブルクリックで開けない場合は、ターミナルで次を実行してください:"
      echo "    xattr -dr com.apple.quarantine \"$KIT_DIR\""
    fi
  fi

  # 実行権限: ZIPの作り方や転送経路によっては失われる。
  for _f in "$KIT_DIR"/*.command "$KIT_DIR"/*.sh; do
    [ -f "$_f" ] || continue
    [ -x "$_f" ] && continue
    if chmod +x "$_f" 2>/dev/null; then
      _chmodded=1
    fi
  done
  if [ "$_chmodded" = "1" ]; then
    echo "  キットの実行権限を整えました。"
  fi

  unset _chmodded _f
  return 0
}
