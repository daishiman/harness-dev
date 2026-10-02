"""system-briefing-book のスクリプト (Node 22 の .mjs) のテストで共通に使う道具。

- run_script: `node scripts/<name>.mjs` を別プロセスで動かし (終了コード, stdout の JSON, stderr) を返す
- node_eval: scripts/ のモジュールを import する短い JS を動かし、最後に出した JSON を返す (定数や関数を直接確かめる)
- BROWSER / needs_browser: Chrome か Edge の場所 (無ければ None) と、ブラウザが要るテストの印
- write_png: Pillow なしで 1 色の PNG を書く
- make_case: 契約 (章立て・表・番号) どおりの最小の打ち合わせ資料フォルダを作る
"""
from __future__ import annotations

import json
import os
import shutil
import struct
import subprocess
import sys
import zlib
from pathlib import Path

import pytest

sys.dont_write_bytecode = True

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = PLUGIN_ROOT / "scripts"
NODE = shutil.which("node")
TITLE = "写真で記録"

HEARING_MD = """# ヒアリング記録: {title}
更新日: 2026-10-01

## 1. 目的と範囲
| 番号 | 質問 | 回答 | 出どころ |
| --- | --- | --- | --- |
| H01 | 何を楽にしたいか | 打ち直しをなくしたい | 聞き取り |

## 2. 画面の共通ルール
| 番号 | 質問 | 回答 | 出どころ |
| --- | --- | --- | --- |
| H02 | 読めない欄はどうするか | 空のまま残す | 既定案 |

## 3. しくみと基盤
| 番号 | 質問 | 回答 | 出どころ |
| --- | --- | --- | --- |
| H03 | どこで動かすか |  | 未定 |

## 4. 運用
| 番号 | 質問 | 回答 | 出どころ |
| --- | --- | --- | --- |
| H04 | 困ったときの連絡先 | 事務の担当者 | 聞き取り |

## 5. あとで相談すること
- 月ごとのまとめ
"""

REQ_MD = """# 要件定義書: {title}
版: {version}
更新日: 2026-10-01

## 1. 目的
紙の記録を写真で送るだけで、一覧に入るようにする。

## 2. 今の困りごと
- 紙の記録を事務所で打ち直している。

## 3. 範囲
### 3.1 最初の版でやること
- 写真を送る
- 一覧で直す

### 3.2 やらないこと
- 請求の計算

## 4. 使う人と端末
| 使う人 | 人数 | 端末 | 主にすること |
| --- | --- | --- | --- |
| 現場の担当者 | 3 | スマホ | 写真を送る |
| 事務の担当者 | 1 | PC | 一覧で直す |

## 5. 業務の流れ
### 5.1 今
1. 紙に書く
2. 事務所で打ち直す

### 5.2 これから
1. 紙を撮って送る
2. 一覧で直す

## 6. できること
| 番号 | できること | 画面 | 最初の版 |
| --- | --- | --- | --- |
| F01 | 写真を送る | S01 | ○ |
| F02 | 一覧で直す | S02 | ○ |
| F03 | 月ごとにまとめる | なし | あとで |

## 7. 守ること
- 送ってから 1 分以内に一覧に出る。
- 記録のコピーを毎晩取る。

## 8. 用語
| 用語 | 意味 |
| --- | --- |
| ヘッダー | 画面のいちばん上の帯 |
| フッター | 画面のいちばん下の帯 |
| メニュー | 画面を切り替えるボタンの並び |
| モーダル | 画面の上に重ねて出す小さな窓 |
| ログイン | 使う人を確かめる入り口 |
| バックアップ | 記録のコピーを別の場所に取っておくこと |
| 権限 | 役割ごとの、できることとできないことの決まり |

## 9. 決めること
| 番号 | 決めること | 案 | 誰に聞くか |
| --- | --- | --- | --- |
| Q01 | 入れる項目はこの 4 つでよいか | 日付・相手先・数・メモ | 現場の担当者 |
| Q02 | 記録を何日分残すか | 30 日分 | 発注側の責任者 |
"""

SPEC_MD = """# 仕様書: {title}
版: {version}
更新日: 2026-10-01

## 1. 画面一覧
| 画面番号 | 画面名 | 使う人 | 端末 | ひとことで |
| --- | --- | --- | --- | --- |
| S01 | 写真を送る | 現場の担当者 | スマホ | 撮って送る |
| S02 | 一覧で直す | 事務の担当者 | PC | 読み取った記録を直す |

## 2. 画面の共通ルール
### 2.1 骨組み
- 上に帯、まん中に中身。
### 2.2 ヘッダー
- 画面名と戻るボタン。
### 2.3 メニュー
- PC は左に 2 つだけ並べる。
### 2.4 フッター
- 置かない。
### 2.5 色の役割
- 青は押せるもの、赤は消すもの。
### 2.6 モーダル
- 消す前の確かめだけに使う。
### 2.7 メッセージ
- 送れたら上に 3 秒出す。
### 2.8 空のときと読み込み中
- 空のときは「まだありません」と出す。

## 3. 画面ごとの項目と動き
### S01 写真を送る
- 目的: 紙の記録を撮って送る
- 使う人: 現場の担当者
- 端末: スマホ
- 開き方: ホーム画面のアイコン
- ボード: 02

| 項目 | 種類 | 必須 | 初期値 | 説明 | 根拠 |
| --- | --- | --- | --- | --- | --- |
| 写真 | 画像 | ○ | なし | 紙 1 枚を撮る | 素材:記録票.pdf |
| 日付 | 日付 | ○ | 今日 | 記録の日 | 例 |

| 操作 | 動き | 次の画面 |
| --- | --- | --- |
| 送る | 写真を送って一覧に入れる | S02 |
| やめる | 何もしない | 同じ画面 |

### S02 一覧で直す
- 目的: 読み取った記録を直す
- 使う人: 事務の担当者
- 端末: PC
- 開き方: いつも使うブラウザのお気に入り
- ボード: 03

| 項目 | 種類 | 必須 | 初期値 | 説明 | 根拠 |
| --- | --- | --- | --- | --- | --- |
| 相手先 | 文字 | ○ | 読み取った値 | 記録の相手 | 聞き取り:H01 |

| 操作 | 動き | 次の画面 |
| --- | --- | --- |
| 保存 | 直した値を残す | なし |

## 4. データの形
### D01 記録
1 件 = 記録票 1 枚

| 項目 | 型 | 必須 | 例 | 根拠 |
| --- | --- | --- | --- | --- |
| 日付 | 日付 | ○ | 2026-10-01 | 例 |
| 相手先 | 文字 | ○ | サンプル商店 | 決めること:Q01 |

## 5. 処理のルール
| 番号 | ルール | いつ | 根拠 |
| --- | --- | --- | --- |
| R01 | 読み取れない欄は空のまま残す | 送ったとき | 聞き取り:H02 |

## 6. しくみと基盤
| 項目 | 方式 | 理由 |
| --- | --- | --- |
| 動かす場所 | インターネット上のサービス | 事務所に機械を置かなくてよい |
| データの置き場所 | 1 か所にまとめる | 探しやすい |
| ログイン | 会社のアカウント | 新しい ID を増やさない |
| 外部とのつなぎ | なし | 最初の版は単独で動く |
| 自動で動く処理 | 毎晩コピーを取る | なくさない |
| バックアップ | 毎晩 1 回 | 30 日分残す |
| 通知 | なし | 最初の版は入れない |

## 7. 権限と運用
### 7.1 権限
| 役割 | できること | できないこと | 見える範囲 |
| --- | --- | --- | --- |
| 現場の担当者 | 写真を送る | 一覧を直す | 自分が送った記録だけ |
| 事務の担当者 | 一覧を直す | なし | すべての記録 |

### 7.2 運用
- 困ったら事務の担当者に連絡する。

## 8. 最初の版に入れないもの
- 月ごとのまとめ
  - 備え: 記録の日を、行ごとに残す (D01)。
  - 時期: 次の版
"""

CHANGES_MD = """# 変更点: {title}
"""

BOARD_HTML = """<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<title>{no} {title}</title>
<link rel="stylesheet" href="tokens.css">
<link rel="stylesheet" href="common.css">
</head>
<body>
<div class="board" data-board="{no}" data-type="{type}" data-screens="{screens}">
  <header class="board-head">
    <div>
      <div class="kicker">{kicker}</div>
      <h1>{title}</h1>
      <div class="lead">{message}</div>
    </div>
    <div class="meta">{project}</div>
  </header>
  <main class="board-body">
    <div class="stage">
      <div class="anchor"><i class="mk" style="left:40px;top:40px">1</i><i class="mk" style="left:40px;top:120px">2</i></div>
    </div>
    <aside class="notes">{reqs}
      <ol class="marks">
        <li data-mark="1" data-kind="can"><b>{title}ことができる</b><span class="sub">ボタンを押すだけ。</span></li>
        <li data-mark="2" data-kind="ask"><b>入れる項目</b><span class="q">Q01</span><span class="sub">案: 日付・相手先・数・メモ</span></li>
      </ol>
    </aside>
  </main>
</div>
</body>
</html>
"""

PAGES = [
    {"no": "00", "file": "00_overview.html", "type": "overview", "title": "全体図", "reader": "発注側の責任者",
     "screens": [], "message": "写真を送るだけで一覧に入る"},
    {"no": "02", "file": "02_phone-send.html", "type": "phone", "title": "写真を送る", "reader": "現場の担当者",
     "screens": ["S01"], "message": "撮って送るだけ"},
    {"no": "03", "file": "03_pc-list.html", "type": "pc", "title": "一覧で直す", "reader": "現場の担当者",
     "screens": ["S02"], "message": "読み取った記録を一覧で直す"},
]
# phone / pc のボードに置く要件の札 (要件定義 6 章で最初の版 ○ の行)
REQ_TAGS = {"S01": ("F01", "写真を送る"), "S02": ("F02", "一覧で直す")}
KICKERS = {"overview": "はじめに", "phone": "画面 1 / 2 ・ スマホ", "pc": "画面 2 / 2 ・ PC"}
TOKENS_CSS = ":root { --text: #1F2937; --text-brand: #1747B5; --bg-page: #F4F6F9; }\n"


def _require_node() -> str:
    if NODE is None:
        pytest.skip("node (Node.js 22 以上) が見つかりません")
    return NODE


def run_script(name: str, *args: str, env: dict | None = None, timeout: float = 600) -> tuple[int, object, str]:
    """scripts/<name>.mjs を node で動かす (shell は使わない)。stdout が JSON なら dict にして返す。"""
    full_env = dict(os.environ)
    if env:
        full_env.update(env)
    proc = subprocess.run(
        [_require_node(), str(SCRIPTS / f"{name}.mjs"), *args],
        capture_output=True, text=True, encoding="utf-8", env=full_env, timeout=timeout,
    )
    try:
        out = json.loads(proc.stdout)
    except ValueError:
        out = proc.stdout
    return proc.returncode, out, proc.stderr


def node_eval(code: str, timeout: float = 60) -> object:
    """ES モジュールとして JS を動かし、stdout の最後の行を JSON として返す。

    import は `./lib/x.mjs` や `./validate-briefing-docs.mjs` のように scripts/ から見た形で書く。
    """
    script = code.replace('from "./', f'from "{SCRIPTS.as_uri()}/')
    proc = subprocess.run(
        [_require_node(), "--input-type=module", "-e", script],
        capture_output=True, text=True, encoding="utf-8", timeout=timeout,
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout.strip().splitlines()[-1])


def _find_browser() -> str | None:
    """lib/browser-session.mjs の findBrowser で Chrome / Edge を探す。見つからなければ None。"""
    if NODE is None:
        return None
    script = (
        f'import {{ findBrowser }} from "{(SCRIPTS / "lib" / "browser-session.mjs").as_uri()}";\n'
        "try { console.log(JSON.stringify(findBrowser())); } catch { console.log(\"null\"); }"
    )
    try:
        proc = subprocess.run([NODE, "--input-type=module", "-e", script],
                              capture_output=True, text=True, encoding="utf-8", timeout=60)
        return json.loads(proc.stdout.strip().splitlines()[-1]) if proc.returncode == 0 else None
    except (OSError, ValueError, IndexError, subprocess.SubprocessError):
        return None


BROWSER: str | None = _find_browser()
needs_browser = pytest.mark.skipif(BROWSER is None, reason="Chrome/Edge が無い")


def codes(items: list[dict]) -> set[str]:
    return {item["code"] for item in items}


def write_png(path: Path, size: tuple[int, int] = (3360, 2100), color=(240, 244, 249)) -> Path:
    """1 色の RGB の PNG を Pillow なしで書く (zlib と struct で組み立てる)。"""
    width, height = size

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    row = b"\x00" + bytes(color[:3]) * width
    raw = zlib.compress(row * height, 6)
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", raw) + chunk(b"IEND", b""))
    return path


def make_case(root: Path, *, title: str = TITLE, version: str = "v0.1", hearing: bool = True,
              boards: bool = True, pngs: bool = False, pages: list[dict] | None = None) -> Path:
    """契約どおりの最小の案件を root/素材/打ち合わせ資料 に作り、そのフォルダを返す。"""
    materials = root / "素材"
    base = materials / "打ち合わせ資料"
    (base / "_src" / "assets").mkdir(parents=True, exist_ok=True)
    (base / "_check").mkdir(exist_ok=True)
    (materials / "記録票.pdf").write_bytes(b"%PDF-1.4\n%%EOF\n")
    pages = PAGES if pages is None else pages
    briefing = {
        "schema": "briefing-v1", "title": title,
        "readers": ["現場の担当者", "発注側の責任者", "開発する人"],
        "palette": "hiraga", "materials": "..", "data_policy": "source", "book": {"include_hearing": False},
        "pages": pages,
    }
    (base / "briefing.json").write_text(json.dumps(briefing, ensure_ascii=False, indent=2), encoding="utf-8")
    values = {"title": title, "version": version}
    if hearing:
        (base / "ヒアリング.md").write_text(HEARING_MD.format(**values), encoding="utf-8")
    (base / "要件定義.md").write_text(REQ_MD.format(**values), encoding="utf-8")
    (base / "仕様書.md").write_text(SPEC_MD.format(**values), encoding="utf-8")
    (base / "変更点.md").write_text(CHANGES_MD.format(**values), encoding="utf-8")
    (base / "_src" / "tokens.css").write_text(TOKENS_CSS, encoding="utf-8")
    (base / "_src" / "common.css").write_text(".board { width: 1680px; height: 1050px; }\n", encoding="utf-8")
    if boards:
        for page in pages:
            tags = [REQ_TAGS[s] for s in page["screens"] if page["type"] in ("phone", "pc") and s in REQ_TAGS]
            reqs = "".join(f'<span class="req" data-req="{fid}">{fid} {text}</span>' for fid, text in tags)
            html = BOARD_HTML.format(
                no=page["no"], title=page["title"], type=page["type"], screens=" ".join(page["screens"]),
                kicker=KICKERS.get(page["type"], "はじめに"), message=page["message"], project=title,
                reqs=f'\n      <div class="reqs">{reqs}</div>' if reqs else "",
            )
            (base / "_src" / page["file"]).write_text(html, encoding="utf-8")
    if pngs:
        for page in pages:
            write_png(base / (page["file"][:-5] + ".png"))
    return base


@pytest.fixture
def case(tmp_path: Path) -> Path:
    return make_case(tmp_path)


@pytest.fixture
def case_with_png(tmp_path: Path) -> Path:
    return make_case(tmp_path, pngs=True)
