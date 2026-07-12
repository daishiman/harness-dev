#!/usr/bin/env python3
"""PreToolUse hook: MF掛け払い APIへの変更系リクエストを Bash 経路で遮断する (参照専用の第1層)。

実配線: plugin manifest の matcher は Bash。実装は防御的に tool_input JSON 全体も読めるが、
本番保証は Bash tool の command 文字列に対する遮断である。GET(参照)は許可。

注意 (保証範囲の正直な明示): 本 hook は『Bash 経由の素の HTTP コマンド (curl / python -c 等)』を
捕捉する層であり、Python スクリプト内部の urllib 呼び出しまでは射程外。そのため第2層として
lib/mfk_api.py は GET 専用に設計し POST/PUT/PATCH/DELETE 関数を実装しない (構造的に変更系を持たない)。
2 層で参照専用を担保する。Notion(api.notion.com)への書き込みは対象外 (MFは読むだけ・Notionは書く の一方向)。

MFクラウド請求書ホスト(invoice.moneyforward.com / api.biz.moneyforward.com)の参照専用は、本 hook
(mfkessai.co.jp 宛て Bash を捕捉)ではなく **mf_invoice_api.py が GET 専用・mf_invoice_oauth.py が
token エンドポイントへの認証 POST のみ** という構造で担保する。請求書の作成/更新系関数を実装しないことが第2層。
"""
import json
import re
import sys

_HOST = "mfkessai.co.jp"
_MUTATION_PATTERNS = [
    r"-x\s+(post|put|patch|delete)\b",
    r"--request\s+(post|put|patch|delete)\b",
    r"\s(-d|--data|--data-raw|--data-binary|--form)\b",
    r"\.(post|put|patch|delete)\s*\(",
    # JSON/dict の method キー。json.dumps は `"method": "POST"` と閉じクオート+スペースを
    # 挟むため、キー直後の任意のクオート/空白を許容してから区切り([=:])を取る。
    # これを許さないと WebFetch 等 非Bash tool の {"method":"POST"} を取りこぼす (回帰防止)。
    r"method[\"']?\s*[=:]\s*['\"]?(post|put|patch|delete)",
    # subprocess の list 形式 (例: ["curl","-X","POST"]) を JSON 文字列で検出
    r'"-x",\s*"(post|put|patch|delete)"',
    r'"--request",\s*"(post|put|patch|delete)"',
    r'"(-d|--data|--data-raw|--data-binary|--form)"',
]

# mfkessai を含む URL を抽出するための粗いトークナイザ。
# 「mfkessai を host に持つ http(s) URL」のみを切り出し、その URL を含む
# コマンド断片に対して変更系判定を行うことで、別ホスト(例: Notion)への
# 変更系が同一行に共起したときの誤遮断を減らす。
_URL_RE = re.compile(r"https?://[^\s\"'`)]+", re.IGNORECASE)


def _has_mutation(text):
    """text に変更系(POST/PUT/PATCH/DELETE/データ送信)の痕跡があるか。"""
    lowered = text.lower()
    return any(re.search(p, lowered) for p in _MUTATION_PATTERNS)


def _segment_is_safely_non_mfkessai(seg):
    """断片 seg が『mfkessai 宛てではないと安全に断定できる』か。

    True を返すのは「seg 内に http(s) URL リテラルが 1 つ以上あり、その全てが
    mfkessai でない明示的別ホスト」のときだけ。URL リテラルが無い断片
    (変数間接 `$U` 等でホスト不明) は False を返し、判定対象から除外しない
    = 安全側 (fail-closed)。これにより変数経由で mfkessai 宛てに化ける断片を
    取りこぼさない。
    """
    urls = _URL_RE.findall(seg)
    if not urls:
        return False
    return all(_HOST not in u.lower() for u in urls)


def _is_mutation_for_mfkessai(text):
    """text 内に『mfkessai 宛ての変更系リクエスト』があるかを安全側で判定する。

    精度方針 (CL5-A4-005):
      - 別ホスト宛てだと URL リテラルから断定できる断片の変更系は無視し、
        誤遮断 (例: MF GET と Notion POST の同一行共起) を減らす。
      - 別ホスト宛てだと断定できない断片 (変数間接でホスト不明、URL リテラル
        無し、非Bash tool の JSON dump 等) は **fail-closed** で必ず判定対象に
        残す。遮断を弱める方向には決して倒さない (取りこぼし防止)。
    """
    if _HOST not in text.lower():
        return False

    # コマンドを「&&」「;」「|」「改行」などの区切りで荒く分割。
    segments = re.split(r"(?:&&|\|\||[;\n|])", text)

    # 「別ホスト宛てと安全に断定できる」断片だけを除外し、残り (mfkessai 宛て or
    # ホスト不明) のいずれかに変更系の痕跡があれば遮断する。
    suspect = [s for s in segments if not _segment_is_safely_non_mfkessai(s)]
    return any(_has_mutation(s) for s in suspect)


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    tool = payload.get("tool_name", "")
    ti = payload.get("tool_input", {}) or {}
    text = ti.get("command", "") if tool == "Bash" else json.dumps(ti, ensure_ascii=False)
    if _HOST not in text.lower():
        return 0
    if _is_mutation_for_mfkessai(text):
        sys.stderr.write(
            "[guard-mfk-readonly] MF掛け払いAPIへの変更系(POST/PUT/PATCH/DELETE)は禁止です。"
            "発行漏れチェックは参照専用(GET)です。請求書の発行・更新はMF管理画面で行ってください。\n"
        )
        return 2
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
