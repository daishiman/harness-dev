#!/usr/bin/env python3
# /// script
# name: validate-goal-output
# version: 0.2.3
# purpose: 目標設定・振り返り対話の出力 Markdown を保存前に検証する決定論ゲート。
#          未展開プレースホルダ/ファイル名日付パターン/全角数字/差分+-表記/種別別必須見出し/
#          見出し重複/NG表現/やらないこと3項目以上/プロジェクト別タスク種別方針 等を検査。
#          旧 validate-goal-output.sh 474 行の契約移植 (逐語移植ではない)。
#          --peer 指定時のみ、他層ファイルとの期アンカー3値の層間整合を WARN で報告する。
# inputs:
#   - argv: --file PATH --type weekly|monthly|quarterly (bimonthly は後方互換の別名)
#           [--peer PATH ...] (任意・複数可。層間整合の比較相手)
# outputs:
#   - stdout: PASS 詳細 / 結果サマリ
#   - stderr: (未使用・失敗理由も stdout の FAIL 行に出す)
#   - exit: 0=PASS / 1=FAIL / 2=usage
# contexts: [E, C]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.9"
# ///
"""目標設定出力 Markdown の保存前バリデーション。

旧 validate-goal-output.sh の契約移植。種別 (週報/月報/期報) 別の必須見出し・NG表現・
やらないこと3項目以上・売上系フォーマット等を保存前に検査し違反を FAIL させる。
種別はファイル名推論でなく明示引数 --type (weekly/monthly/quarterly) を正本とする。
`bimonthly` は quarterly の後方互換の別名として受理し続ける (期報=3ヶ月へ改定済み)。
ただし --type と本文のタイトル見出しラベルの不一致は error とする (種別の取り違え検出)。

`--peer PATH` を渡したときだけ他層のファイルを開き、期アンカー (今期の売上目標 /
今期の累計売上実績 / 最重要数字) を突き合わせる。不一致は WARN で、rc は変えない。
最重要数字はどちらか一方でも週報レベルなら比較対象外 (週報は上位の内訳を書く)。
--peer 未指定時のコードパスは従来と同一。
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# --type -> kind (分岐キー)。期報=quarterly=3-月報（３ヶ月）。
# "bimonthly" は期報が2ヶ月だった頃の旧キー。新規は quarterly を正とし、旧キーも受理し続ける。
TYPE_MAP = {
    "weekly": "week",
    "monthly": "month",
    "quarterly": "period",
    "bimonthly": "period",  # 後方互換の別名（旧2ヶ月期報の呼び出し・過去スクリプト用）
}

# --type -> 本文のタイトル見出しラベル。
# quarterly と bimonthly は kind がどちらも period なので、kind だけを見ると
# 「3ヶ月期報を --type bimonthly で検証」しても通ってしまう。種別の取り違えを
# 検出するために、元の --type の値とラベルの対応をここで正本として持つ。
TYPE_TITLE_LABEL = {
    "weekly": "1週間の目標",
    "monthly": "1ヶ月の目標",
    "quarterly": "3ヶ月の目標",
    "bimonthly": "2ヶ月の目標",
}

# 旧種別。取り違え時に「引数が古い」のか「ファイルが古い」のかを言い分けるために使う。
LEGACY_TYPES = {"bimonthly"}


def judge_sales_coverage(total: int, target: int) -> tuple[str, str]:
    """成果目標の売上貢献合計 total と、今期間の売上目標 target を突き合わせる。

    「この成果を達成したら、売上がここまで動く」という線が引けているかの判定。
    戻り値は (verdict, message)。verdict は次のいずれか:
      "ok"   … 線がつながっている（PASS を出す）
      "warn" … 疑わしいが保存は通す（WARN を出す。rc は変わらない）
      "fail" … 保存を止める（FAIL を出す。rc=1）
      "info" … 判定しない（情報行のみ出す）

    採用しているポリシー:
      1. 完全一致は求めない。`total >= target` を満たせば線はつながっている
        （超過は「成果の出しすぎ」ではなく、取りこぼし前提の積み増しでありうる）
      2. 未達は target の 5% 以内なら warn（端数・単価の丸めで生じる程度のズレ）
      3. それを超える未達は fail。線が引けないまま保存させない
      4. target が 0（売上目標を置かない期間）は判定せず info

    message には必ず total と target の実数を含める。差分だけだと、
    どちらが動いたのかが読めなくなる。
    """
    if target <= 0:
        return ("info", f"突合: 貢献合計 {total} / 売上目標 {target}（売上目標が無いため判定しない）")

    shortfall = target - total
    if shortfall <= 0:
        return ("ok", f"突合: 貢献合計 {total} / 売上目標 {target}（線がつながっている）")

    if shortfall <= target * 0.05:
        return (
            "warn",
            f"突合: 貢献合計 {total} / 売上目標 {target}（不足 {shortfall}）。"
            "端数程度のズレ。成果の単価・件数を見直すか、売上目標を置き直してください",
        )

    return (
        "fail",
        f"突合: 貢献合計 {total} / 売上目標 {target}（不足 {shortfall}）。"
        "成果目標が足りていません。この成果が全部出ても売上目標に届きません。"
        "相手を足すか、売上目標を置き直してください（行動を足してごまかさない）",
    )

# --- 層間整合（--peer）用の期アンカー定義 ---
# references/data-contract.md が「期アンカー・全レベル同値」と定めている値。
# 週報/月報/期報のどの層でも同じ値でなければならないが、継承は inherited_context の
# 作成時 pull（一方向）しかなく、上位確定後に下位へ push する経路が無い。しかも実際の
# 作成順は下位が先になることがあるので、正しく運用しても最低1回はズレる。
# そのため不一致は FAIL でなく WARN とし、気づかせるだけにする。
#
# (アンカー名, 見出しの正規表現, 値の型) 値の型: "number" | "text"
PEER_ANCHORS = [
    ("今期の売上目標", r"^## 【今期の売上目標】", "number"),
    ("今期の累計売上実績", r"^## 【今期の累計売上実績】", "number"),
    ("最重要数字", r"^## 【今(週|月|期)の最重要数字】", "text"),
]

# 週報レベルが絡むときは一致検査から外すアンカー。
# 週報の【今週の最重要数字】は、期・月の最重要数字を今週分へ割った内訳であって、
# 上位と同じ値になるべき数字ではない（例: 期「困りごとを解決した件数：6件」に対して
# 週「平賀運送さんの困りごとを書き出した件数：3件」）。ここを比較すると、正しい書き方が
# 毎週 WARN になる。金額2値（今期の売上目標・今期の累計売上実績）は週報でも全レベル同値
# が正しい契約なので、除外しない。
WEEKLY_EXEMPT_ANCHORS = {"最重要数字"}

# 本文のタイトル見出しから読む階層。--file 側は --type を正本とし、peer 側は本文から判定する。
_WEEK_TITLE_RX = re.compile(r"^## 【[0-9]*週間の目標】")
_WEEK_KEYNUM_RX = re.compile(r"^## 【今週の最重要数字】")


def detect_level(text: str) -> str:
    """本文から階層を判定する。'week' か 'other'（月報・期報・判定不能）。

    タイトル見出し「## 【1週間の目標】」を第一の根拠にし、見つからないときだけ
    「## 【今週の最重要数字】」の有無で補う（タイトル行が編集途中で欠けていても
    週報を月報・期報と取り違えないため）。
    """
    for line in text.split("\n"):
        if _WEEK_TITLE_RX.search(line):
            return "week"
    for line in text.split("\n"):
        if _WEEK_KEYNUM_RX.search(line):
            return "week"
    return "other"

# 値ではなく注釈である行。継承元の記載や補足は値として拾わない。
_NOTE_PREFIXES = ("（", "(", "※")


def _section_body(lines: list[str], head_rx: str) -> list[str] | None:
    """`head_rx` に一致する最初の見出しの本文（次の ^## まで）を返す。無ければ None。"""
    rx = re.compile(head_rx)
    n = len(lines)
    for i, line in enumerate(lines):
        if rx.search(line):
            j = i + 1
            body = []
            while j < n and not lines[j].startswith("## "):
                body.append(lines[j])
                j += 1
            return body
    return None


def _content_lines(body: list[str]) -> list[str]:
    """空行・区切り線・注釈行を除いた本文行。"""
    out = []
    for l in body:
        s = l.strip()
        if not s or re.match(r"^-{3,}$", s):
            continue
        if s.startswith(_NOTE_PREFIXES):
            continue
        out.append(s)
    return out


def extract_peer_anchors(text: str) -> dict[str, str | None]:
    """期アンカー3値を正規化して取り出す。見つからない項目は None（＝比較対象外）。"""
    lines = text.split("\n")
    result: dict[str, str | None] = {}
    for name, head_rx, kind in PEER_ANCHORS:
        body = _section_body(lines, head_rx)
        result[name] = None if body is None else _normalize_anchor(_content_lines(body), kind)
    return result


def _normalize_anchor(content: list[str], kind: str) -> str | None:
    if not content:
        return None
    if kind == "number":
        for l in content:
            m = re.search(r"[0-9][0-9,]*", l)
            if m:
                return m.group(0).replace(",", "")
        return None
    # text: 先頭の箇条書き記号・チェックボックスを落として比較する
    first = re.sub(r"^(?:[*-]\s*(?:\[[ xX]\]\s*)?|・)", "", content[0]).strip()
    return first or None


class Validator:
    def __init__(self, text: str, basename: str, kind: str, type_name: str = "",
                 peers: list[tuple[str, str]] | None = None):
        self.lines = text.split("\n")
        self.text = text
        self.basename = basename
        self.kind = kind  # week | month | period
        # 元の --type の値。kind へ潰す前の値で、ラベル照合の正本。
        self.type_name = type_name or next(
            (t for t, k in TYPE_MAP.items() if k == kind), ""
        )
        # (表示名, 本文) の並び。空（既定）なら層間整合チェックは一切走らない。
        self.peers = peers or []
        self.errors = 0
        self.warnings = 0

    def fail(self, msg: str) -> None:
        print(f"FAIL: {msg}")
        self.errors += 1

    def warn(self, msg: str) -> None:
        print(f"WARN: {msg}")
        self.warnings += 1

    def ok(self, msg: str) -> None:
        print(f"PASS: {msg}")

    # --- セクション抽出ヘルパ ---
    def sections_by_regex(self, pattern: str):
        """`^## .*{pattern}.*` に一致する見出しの本文 (次の ^## まで) を列挙。"""
        rx = re.compile(r"^## .*" + pattern + r".*")
        out = []
        n = len(self.lines)
        for i, line in enumerate(self.lines):
            if rx.search(line):
                j = i + 1
                while j < n and not self.lines[j].startswith("## "):
                    j += 1
                out.append((i, self.lines[i + 1:j]))
        return out

    def capture_awk(self, pred) -> list[str]:
        """awk '/^## /{if(pred)f=1;next; else f=0} f' 相当。複数節を累積。"""
        f = False
        out: list[str] = []
        for line in self.lines:
            if line.startswith("## "):
                if pred(line):
                    f = True
                    continue
                f = False
            if f:
                out.append(line)
        return out

    def capture_from_start(self, start_rx: str) -> list[str]:
        """awk '/{start}/{f=1;next} /^## /{f=0} f' 相当 (任意の ^## で停止)。"""
        rx = re.compile(start_rx)
        f = False
        out: list[str] = []
        for line in self.lines:
            if rx.match(line):
                f = True
                continue
            if line.startswith("## "):
                f = False
            if f:
                out.append(line)
        return out

    def sed_range(self, start_sub: str, end_rx: str) -> list[str]:
        """sed -n '/start_sub/,/end_rx/p' 相当 (start は部分一致, end は正規表現, 両端含む)。"""
        rx_end = re.compile(end_rx)
        out: list[str] = []
        active = False
        for line in self.lines:
            if not active:
                if start_sub in line:
                    active = True
                    out.append(line)
                continue
            out.append(line)
            if rx_end.search(line):
                break
        return out

    # --- 各チェック ---
    def check_require_exact(self, label: str) -> None:
        rx = re.compile(r"^## 【" + re.escape(label) + r"】[ \t]*$")
        if any(rx.search(l) for l in self.lines):
            self.ok(f"必須見出し「## 【{label}】」")
        else:
            self.fail(f"必須見出し「## 【{label}】」がありません（完全一致）")

    # 旧 check_require_prefix は check_title_matches_type に統合した。
    # prefix_any は「3ヶ月」「2ヶ月」の両方を無条件に受理するため、--type の取り違えを
    # 検出できなかった（同じ3ヶ月期報が quarterly でも bimonthly でも PASS していた）。

    def has_title(self, label: str) -> bool:
        return any(l.startswith(f"## 【{label}】") for l in self.lines)

    def check_title_matches_type(self) -> None:
        """--type と本文のタイトル見出しラベルが一致することを要求する。

        不一致は error。読みの後方互換（旧2ヶ月期報を --type bimonthly で再検証）は
        ラベル側も旧表記なので通る。
        """
        expected = TYPE_TITLE_LABEL.get(self.type_name)
        if expected is None:
            return
        if self.has_title(expected):
            self.ok(f"必須タイトル見出し「## 【{expected}】…」")
            return

        other = next(
            (t for t, lbl in TYPE_TITLE_LABEL.items()
             if t != self.type_name and self.has_title(lbl)),
            None,
        )
        if other is None:
            self.fail(f"必須タイトル見出し「## 【{expected}】」がありません")
            return

        if self.type_name in LEGACY_TYPES:
            hint = f"引数側が旧種別です。現行のファイルは --type {other} で検証してください"
        elif other in LEGACY_TYPES:
            hint = f"ファイル側が旧種別です。旧ファイルを再検証するなら --type {other} を指定してください"
        else:
            hint = f"--type {other} を指定してください"
        self.fail(
            f"--type {self.type_name}（【{expected}】）で検証していますが、"
            f"本文のタイトル見出しは「## 【{TYPE_TITLE_LABEL[other]}】…」です（{hint}）"
        )

    def check_section_optional(self, section: str) -> None:
        if section in self.text:
            self.ok(f"セクション「{section}」")
        else:
            self.warn(f"セクション「{section}」がありません（任意）")

    def check_goal_section(self, pattern: str, label: str, mode: str) -> None:
        for start, body in self.sections_by_regex(pattern):
            if mode == "numeric":
                table_hit = [l for l in body if re.match(r"^\|", l)]
                subhead_hit = [l for l in body if re.match(r"^### ", l)]
                if table_hit or subhead_hit:
                    self.fail(
                        f"売上系セクション「{label}」に表またはサブ見出しが含まれています（数値1つのみ許可）"
                    )
                # 区切り線 `---` は次セクションとの境界であって本文ではない。
                # 数えると「1,000,000 + ---」で常に2行になり、正しい形が警告になる。
                non_empty = [
                    l for l in body
                    if not re.match(r"^\s*$", l)
                    and not l.startswith("（")
                    and not re.match(r"^\{\{.*\}\}$", l)
                    and not re.match(r"^\s*-{3,}\s*$", l)
                ]
                if len(non_empty) > 1:
                    self.warn(f"売上系セクション「{label}」が複数行になっています（数値1つのみ推奨）")
            elif mode == "bullet":
                table_hit = [l for l in body if re.match(r"^\|", l)]
                if table_hit:
                    self.fail(f"「{label}」セクションに Markdown 表が含まれています（箇条書きのみ許可）")

    # --- 逆算チェーン（売上 → 成果 → 行動）ヘルパ ---

    # --- シンプルさの上限 ---
    # 目標は複雑にした瞬間に自分で回せなくなる。長さと件数を上限で止めておかないと、
    # 「気をつける」では必ず膨らむ。数字は運用可能な範囲の実測から置いた上限であり、
    # 足りないと感じたら項目を削るのが正しい（上限を上げるのではない）。
    MAX_OUTCOME_ITEMS = 5      # 成果目標の件数
    MAX_OUTCOME_CHARS = 50     # 成果目標1項目の本体（`→ 売上貢献` の前まで）
    MAX_ACTION_ITEMS = 8       # 行動目標の件数
    MAX_ACTION_CHARS = 60      # 行動目標1項目の本体（1行目・期日込み）

    # 成果目標セクションに置いてはいけない「実行完了型」の語尾。
    # 実行した時点で達成になってしまうものは成果ではなく行動なので、行動目標側へ移す。
    OUTCOME_NG_VERBS = (
        "実施する", "開催する", "参加する", "送付する", "作成する",
        "提出する", "共有する", "告知する", "打診する", "連絡する",
    )

    @staticmethod
    def _is_bullet(line: str) -> bool:
        return bool(re.match(r"^([*-] |・)", line))

    @staticmethod
    def _outcome_key(item: str) -> str:
        """成果目標の1項目から参照キー（`：` の前の対象名）を取り出す。"""
        body = re.sub(r"^([*-] |・)\s*", "", item)
        body = re.split(r"→", body)[0]
        body = re.split(r"[：:]", body)[0]
        return body.strip().strip("*").strip()

    @staticmethod
    def _ref_matches_key(ref: str, key: str) -> bool:
        """行動目標の参照 `ref` が、成果目標のキー `key` を指しているか判定する。

        C5（実在しない成果目標を参照していないか）と C6（どの行動からも支えられて
        いない成果目標が無いか）は、同じ「参照が成果を指す」関係を逆向きに見ている
        だけである。両者が別々の判定式を持つと、`ref="田所"` / `key="田所さん"` の
        ような入力で「C5 は実在すると言い、C6 は支えられていないと言う」相反した
        2行が同時に出る。そのため一致判定はこの1つの述語に集約する。

        Args:
            ref: 行動目標の `→ 支える成果目標：` に書かれた1つの参照名
                 （`・` 区切りは呼び出し側で分解済み。`（土台）` 等の免除も処理済み）
            key: 成果目標1項目から取り出した対象名（`_outcome_key` の戻り値）

        Returns:
            ref が key を指しているとみなせるなら True

        採用しているポリシー: 空白を落としたうえでの完全一致。
        部分一致を許すと `→ 支える成果目標：さん` があらゆるキーに一致してしまい、
        「実在する成果目標を指すこと」という契約が空洞化する。略記を許したくなったら、
        略記側ではなく成果目標のキーそのものを短くするのが正しい直し方。
        """
        def norm(s: str) -> str:
            return re.sub(r"[\s　]+", "", s).strip("*")

        return bool(norm(ref)) and norm(ref) == norm(key)

    @staticmethod
    def _outcome_head(item: str) -> str:
        """成果目標の1項目から本文（`→` より前）だけを取り出す。

        `→ 売上貢献：0（翌月の提案書を作成するための材料）` のような理由欄は
        自由記述であり、実行完了型の判定対象にしてはいけない。C1 が理由を書けと
        要求しているのに C2 がその理由で FAIL させる、という自家撞着を避ける。
        """
        head = re.sub(r"^([*-] |・)\s*", "", item)
        return re.split(r"→", head)[0].strip()

    # kind -> 今期間を指す語。週報では【今期の売上目標】は期アンカー（3ヶ月分）であって
    # 今週の売上目標ではない。ここを `今(週|月|期)` で緩く拾うと、週報で期アンカーの側を
    # 掴んで突合が壊れるので、種別ごとに1語へ固定する。
    KIND_PERIOD_WORD = {"week": "今週", "month": "今月", "period": "今期"}

    def _period_word(self) -> str:
        return self.KIND_PERIOD_WORD.get(self.kind, "今週")

    def _current_outcome_items(self) -> list[str]:
        """今期間の成果目標を「箇条書き行 + 続く注記行」を1項目へ束ねて返す。

        成果目標は1項目=2行で書く（1行目に成果、2行目に `→ 売上貢献：` の式）。
        1行に詰めると横に長くなって金額が読み飛ばされるため、正本のフォーマットで
        改行を必須にした。ここで束ねずに箇条書き行だけを見ると、貢献額の行が丸ごと
        視界から外れ、C1 が全項目を「貢献額なし」と誤判定する。

        空行が項目の区切り。セクション末尾の `合計 … ＝ 今週の売上目標 …` の行が
        最後の項目にぶら下がらないようにするためでもある。
        """
        groups: list[list[str]] = []
        pat = r"【" + self._period_word() + r"の売上以外の成果目標】"
        for _, body in self.sections_by_regex(pat):
            cur: list[str] | None = None
            for line in body:
                if self._is_bullet(line):
                    cur = [line]
                    groups.append(cur)
                elif not line.strip():
                    cur = None
                elif cur is not None:
                    cur.append(line)
        return ["\n".join(g) for g in groups]

    # `→ 売上貢献：` に続く記述（改行までの1行分）。式も理由も、まずここへ丸ごと取る。
    CONTRIB_RX = re.compile(r"→\s*売上貢献\s*[：:]\s*([^\n]*)")

    # `50000 × 3件 = 150000` の形。件数に付く単位語は捨てずに取っておく（C1e で見る）。
    CONTRIB_EXPR_RX = re.compile(
        r"([0-9][0-9,]*)\s*[×xX*]\s*([0-9][0-9,]*)\s*((?:[ヶヵカか]?月|年|件|名|回|本))?\s*"
        r"[=＝]\s*([0-9][0-9,]*)"
    )

    # 裸の数字に随伴する「括弧の根拠」。数字の直後に括弧書きが続く形だけを根拠と認める。
    # 文末に付いた括弧まで拾うと `→ 売上貢献：150000（Aさん）` のような、金額の
    # 出どころを説明していない注記でも通ってしまう。
    CONTRIB_BASIS_RX = re.compile(r"^[0-9][0-9,]*\s*[（(]\s*[^）)]")

    # 件数に付いてはいけない期間単位。`50000 × 3ヶ月 = 150000` を今期間の売上として
    # 計上すると、今期間に入らない金銭で目標が埋まる（月額顧問なら初月の 50000 だけが
    # 今期間の売上に立つ）。`件`/`名`/`回`/`本` は今期間に確定する数え方なので許す。
    PERIOD_COUNT_UNIT_RX = re.compile(r"^(?:[ヶヵカか]?月|年)$")

    @classmethod
    def _parse_contribution(
        cls, item: str
    ) -> tuple[int | None, tuple[int, int, int] | None, str, str]:
        """成果目標1項目から売上貢献額を読み取る。

        貢献額には、式（`単価 × 件数 = 貢献額`）か括弧の根拠のどちらかが必ず随伴して
        いなければならない。裸の数字1つだけでは、その数字が正しいかを後から誰も
        検算できない。式で残っていれば単価が下がったとき・本数が変わったときに何が
        崩れるかがその場で分かる。ただし値引き後の一括見積のように単価×件数へ分解
        できない成果は実在するので、式そのものは必須にしない（要求するのは「検算
        可能な根拠が随伴すること」であって「式の形」ではない）。判定は C1（R-a）で行う。

        Returns:
            (貢献額, 式, 記述全体, 件数の単位) の4つ組。
            貢献額は式があれば `=` の右辺、無ければ先頭の数値。読めなければ None。
            式は `(単価, 件数, 右辺)`。式で書かれていないときは None。
            件数の単位は式の件数に付いていた単位語（無ければ空文字）。
        """
        m = cls.CONTRIB_RX.search(item)
        if not m:
            return None, None, "", ""
        raw = m.group(1).strip()

        expr = cls.CONTRIB_EXPR_RX.search(raw)
        if expr:
            unit, count, stated = (
                int(g.replace(",", "")) for g in (expr.group(1), expr.group(2), expr.group(4))
            )
            return stated, (unit, count, stated), raw, expr.group(3) or ""

        num = re.match(r"([0-9][0-9,]*)", raw)
        if num:
            return int(num.group(1).replace(",", "")), None, raw, ""
        return None, None, raw, ""

    def _current_sales_target(self) -> int | None:
        pat = r"【" + self._period_word() + r"の売上目標】"
        for _, body in self.sections_by_regex(pat):
            for l in body:
                m = re.match(r"^\s*([0-9][0-9,]*)\s*円?\s*$", l)
                if m:
                    return int(m.group(1).replace(",", ""))
        return None

    # `### → Aさん：月額顧問の成約（150000円）` のグループ見出し。
    ACTION_GROUP_RX = re.compile(r"^#{3,6}\s*→\s*(.+?)\s*$")

    # 見出しの括弧内に書かれた金額。`（0円・8月の仕込み）` のように補足が続く形も拾う。
    GROUP_AMOUNT_RX = re.compile(r"[（(]\s*([0-9][0-9,]*)\s*円")

    @classmethod
    def _group_ref(cls, heading: str) -> str:
        """行動目標のグループ見出しから、支える成果目標の参照名を取り出す。"""
        m = cls.ACTION_GROUP_RX.match(heading)
        if not m:
            return ""
        return re.split(r"[：:]", m.group(1))[0].strip().strip("*")

    @classmethod
    def _group_amount(cls, heading: str) -> int | None:
        """グループ見出しの括弧内の金額を取り出す。金額が書かれていなければ None。

        None は「検査対象外」を意味する。`### → （土台）` のように成果に紐づかない
        免除グループには金額が無く、そこへ金額を書かせる意味も無い。
        """
        m = cls.GROUP_AMOUNT_RX.search(heading)
        return int(m.group(1).replace(",", "")) if m else None

    def _current_action_groups(self) -> list[tuple[str, int | None, list[list[str]]]]:
        """今期間の行動目標を、支える成果目標ごとのグループへ束ねる。

        行動目標は `### → {成果目標名}：{要約}（{金額}円）` の見出しで区切り、その
        配下に `- [ ]` を並べる。売上 → 成果 → 行動の一直線を、そのまま文書の目次に
        するための構造である。行ごとに `→ 支える成果目標：` を繰り返す旧記法だと、
        同じ成果名が何度も現れるだけで「どの成果に何件ぶら下がっているか」は読み手が
        頭の中で集計するしかなかった。

        Returns:
            `(参照名, 見出しの金額, ブロック群)` の並び。参照名はグループ見出しから
            取れなければ空文字（呼び出し側が行内の `→ 支える成果目標：` へ
            フォールバックする。旧記法で書かれた既存ファイルを読めるようにするため）。
            見出しの金額は書かれていなければ None（C4b の検査対象外）。
        """
        # 期間語は種別ごとに1語へ固定する（成果・売上側と同じ理由）。`今(週|月|期)` の
        # 緩いマッチだと、週報ファイル内の期アンカー見出しを行動目標として掴みうる。
        def pred(line: str) -> bool:
            return ("行動目標" in line and self._period_word() in line
                    and not re.search(r"差分|実績", line))

        groups: list[tuple[str, int | None, list[list[str]]]] = [("", None, [])]
        cur: list[str] | None = None
        for line in self.capture_awk(pred):
            if self.ACTION_GROUP_RX.match(line):
                groups.append((self._group_ref(line), self._group_amount(line), []))
                cur = None
            elif self._is_bullet(line):
                cur = [line]
                groups[-1][2].append(cur)
            elif cur is not None and line.strip():
                cur.append(line)
        return [g for g in groups if g[2]]

    def _current_action_blocks(self) -> list[list[str]]:
        """グループを畳んだ、今期間の全行動ブロック（件数・長さの検査用）。"""
        return [b for _, _, blocks in self._current_action_groups() for b in blocks]

    def check_goal_chain(self) -> None:
        """売上 → 成果 → 行動の逆算が最後までつながっているかを検査する。

        文章での指示だけでは「行動ありき」に戻ってしまうため、連鎖そのものを機械で止める。
        """
        print("")
        print("--- 逆算チェーン（売上 → 成果 → 行動）---")

        outcome_items = self._current_outcome_items()
        if not outcome_items:
            self.fail("今期間の成果目標セクションに箇条書き項目がありません")
            return

        # C1: 各成果目標に売上貢献額があるか（売上と成果を数値で結ぶ線）
        #
        # 合計は欠落の有無に関わらず、読み取れた分だけ積む（C3 の暫定突合で使う）。
        total = 0
        missing: list[str] = []
        amounts: list[int] = []
        key_amounts: dict[str, int] = {}
        for i in outcome_items:
            amount, factors, raw, count_unit = self._parse_contribution(i)
            head = self._outcome_head(i)
            if amount is None:
                missing.append(i)
                continue
            total += amount
            amounts.append(amount)
            key_amounts[self._outcome_key(i)] = amount

            # C1a（R-a）: 貢献額には式か括弧の根拠のどちらかが必ず随伴する。
            # 裸の数字を通すと、式で書いた人だけが C1c の検算 FAIL を負い、根拠を
            # 出さなかった人は免除される。情報量の多い正しい記法のほうが罰せられる
            # 非対称をここで塞ぐ。貢献 0 の理由要求も、この一般規則の特殊ケースとして
            # 吸収した（0 のときだけ厳しくする独立の検査は廃止）。
            if factors is None and not self.CONTRIB_BASIS_RX.match(raw):
                self.fail(
                    "売上貢献に式または括弧の根拠がありません"
                    "（例: `→ 売上貢献：50000 × 3 = 150000` / "
                    "`→ 売上貢献：150000（値引き後の一括見積）` / "
                    "`→ 売上貢献：0（8月に 300000 の見込み）`）: " + head
                )

            # C1c: 式の検算。`50000 × 3 = 200000` のような計算違いを見逃すと、
            # 「式で書けば根拠が残る」という記法の意味そのものが失われる。
            if factors is not None:
                unit, count, stated = factors
                if unit * count != stated:
                    self.fail(
                        f"売上貢献の式が合っていません（{unit} × {count} = {unit * count}）: "
                        f"{head} → 売上貢献：{raw}"
                    )

            # C1e（R-b）: 期間をまたぐ計上の禁止。件数に期間単位が付いた式は、
            # 今期間に入らない金銭を今期間の売上目標へ充ててしまう。
            if count_unit and self.PERIOD_COUNT_UNIT_RX.match(count_unit):
                self.fail(
                    f"売上貢献の件数に期間単位「{count_unit}」が付いています"
                    f"（{self._period_word()}に実際に売上として立つ分だけを計上してください。"
                    "月額顧問なら初月分だけを計上し、残りは次の期間の成果目標にする）: "
                    f"{head} → 売上貢献：{raw}"
                )

        if missing:
            for i in missing:
                self.fail(
                    "成果目標に「→ 売上貢献：<単価> × <件数> = <貢献額>」がありません: "
                    + self._outcome_head(i)
                )
        else:
            self.ok(f"全 {len(outcome_items)} 件の成果目標に売上貢献額あり（合計 {total}）")

        # C1d: 貢献 0 の偏りを見る。0 の項目は「今期間の売上には乗らないが、先に繋がる」
        # 仕込みであり、一定数はあってよい。ただし大半が 0 なら、その期間は売上から
        # 逆算した目標になっていない（＝今週やることが今週の数字に効かない）。
        # amounts には、貢献額が読み取れた項目だけが入っている。
        # 1件しかない期間は母数が小さすぎて偏りを論じられないので判定しない。
        zeros = [a for a in amounts if a == 0]
        if len(amounts) >= 2 and len(zeros) * 2 > len(amounts):
            self.warn(
                f"売上貢献 0 の成果目標が {len(zeros)}/{len(amounts)} 件です。"
                f"{self._period_word()}の売上に効く成果を1件足すか、"
                "仕込みの成果を次の期間へ送ってください"
            )

        # S1/S2: シンプルさ（成果目標の件数・長さ・1項目1成果）
        if len(outcome_items) > self.MAX_OUTCOME_ITEMS:
            self.fail(
                f"成果目標が{len(outcome_items)}件です（上限{self.MAX_OUTCOME_ITEMS}件）。"
                "絞り込んでください（増やすほど、どれも動かなくなる）"
            )
        else:
            self.ok(f"成果目標 {len(outcome_items)} 件（上限{self.MAX_OUTCOME_ITEMS}件）")
        for i in outcome_items:
            head = re.sub(r"^([*-] |・)\s*", "", i)
            head = re.split(r"→", head)[0].strip()
            if len(head) > self.MAX_OUTCOME_CHARS:
                self.fail(
                    f"成果目標が長すぎます（{len(head)}字・上限{self.MAX_OUTCOME_CHARS}字）: {head}"
                )
            if "・" in head:
                self.fail(f"成果目標に複数の成果が入っています（1項目1成果に分ける）: {head}")

        # C2: 実行完了型を成果目標に置いていないか
        bad_verb = [i for i in outcome_items
                    if any(v in self._outcome_head(i) for v in self.OUTCOME_NG_VERBS)]
        if bad_verb:
            for i in bad_verb:
                self.fail(
                    "成果目標が実行完了型です（実行した時点で達成になる項目は行動目標へ）: "
                    + i.strip()
                )
        else:
            self.ok("成果目標に実行完了型なし")

        # C3: 売上貢献の合計と売上目標の突合
        #
        # 突合できなかったときは黙って消えてはいけない。黙って消えると STATUS: PASS が
        # 「突合した結果つながっていた」と読めてしまう。判定できない理由を必ず印字する。
        target = self._current_sales_target()
        if target is None:
            print(
                f"INFO: 突合: 【{self._period_word()}の売上目標】から数値を1つ読み取れず、"
                "突合を実施していません（このセクションには数値1行だけを書いてください。"
                "PASS は突合済みを意味しません）"
            )
        elif missing:
            # 貢献額を欠く項目があっても、既知分だけで暫定の突合結果を出す。1回の実行で
            # 直すべき違反を出し切らないと、改善リトライ（最大3回）を検査の段数で使い切る。
            print(
                f"INFO: 突合（暫定）: 判明分の貢献合計 {total} / 売上目標 {target}"
                f"（未記入 {len(missing)} 件を除く）。上の売上貢献の欠落を直すと確定します"
            )
        else:
            verdict, message = judge_sales_coverage(total, target)
            if verdict == "fail":
                self.fail(message)
            elif verdict == "warn":
                self.warn(message)
            elif verdict == "ok":
                self.ok(message)
            else:
                print(f"INFO: {message}")

        # C4/C5: 各行動目標が実在する成果目標を支えているか
        action_groups = self._current_action_groups()
        blocks = [b for _, _, bs in action_groups for b in bs]
        if not blocks:
            print(
                f"INFO: 紐づけ検査: 【{self._period_word()}の行動目標】に箇条書き項目が無く、"
                "C4/C5/C6 を実施していません"
            )
            return
        # S3: シンプルさ（行動目標の件数・長さ）
        if len(blocks) > self.MAX_ACTION_ITEMS:
            self.fail(
                f"行動目標が{len(blocks)}件です（上限{self.MAX_ACTION_ITEMS}件）。"
                "やることを増やすのではなく、やらないことを増やしてください"
            )
        else:
            self.ok(f"行動目標 {len(blocks)} 件（上限{self.MAX_ACTION_ITEMS}件）")
        for block in blocks:
            head = re.sub(r"^([*-] |・)\s*(\[[ xX]\]\s*)?", "", block[0]).strip()
            if len(head) > self.MAX_ACTION_CHARS:
                self.fail(
                    f"行動目標が長すぎます（{len(head)}字・上限{self.MAX_ACTION_CHARS}字）: {head}"
                )

        keys = [self._outcome_key(i) for i in outcome_items]
        keys = [k for k in keys if k]
        unlinked = 0
        dangling = 0
        linked_keys: set[str] = set()
        # C4b（R-c）: グループ見出しの金額と、その成果目標の貢献額の一致。
        # 見出しの金額は「この行動群は何円のために動いているか」を読み手へ渡す唯一の
        # 数字なので、成果目標側と食い違ったまま通すと、目次だけが別の計画を語る。
        # 金額の無い見出し（`### → （土台）` 等の免除グループ）は対象外。
        #
        # R-d: グループの並び順（貢献額の降順）は機械検査しない。同額のときに順序が
        # 一意に決まらず、正しく書いても直しようのない FAIL が出るため、意図的に
        # 非検査としている（実装し忘れではない）。
        for group_ref, group_amount, _blocks in action_groups:
            if not group_ref or group_amount is None:
                continue
            matched = [k for k in keys if self._ref_matches_key(group_ref, k)]
            for k in matched:
                if k in key_amounts and key_amounts[k] != group_amount:
                    self.fail(
                        f"行動目標グループの金額が成果目標の貢献額と違います"
                        f"（見出し {group_amount} / 成果目標「{k}」{key_amounts[k]}）: "
                        f"### → {group_ref}"
                    )

        for group_ref, _group_amount, group_blocks in action_groups:
            for block in group_blocks:
                head = block[0].strip()
                # グループ見出し（`### → 成果目標名：…`）が正。見出しが無いときだけ、
                # 旧記法の行内注記へフォールバックする（既存ファイルを読めるように）。
                inline = next(
                    (l for l in block if re.search(r"→\s*支える成果目標\s*[：:]", l)), None
                )
                if group_ref:
                    value = group_ref
                elif inline is not None:
                    value = re.split(
                        r"→\s*支える成果目標\s*[：:]", inline, maxsplit=1
                    )[1].strip()
                else:
                    self.fail(
                        "行動目標がどの成果目標に属するか分かりません"
                        "（`### → 成果目標名：要約（金額円）` の見出しでグループ化してください）: "
                        + head
                    )
                    unlinked += 1
                    continue
                for ref in [r.strip() for r in value.split("・") if r.strip()]:
                    if ref.startswith("（") or ref.startswith("("):
                        continue  # （土台）／（関係維持）は成果への紐づけを免除
                    matched = [k for k in keys if self._ref_matches_key(ref, k)]
                    if not matched:
                        self.fail(
                            f"行動目標が実在しない成果目標を参照しています: 「{ref}」← {head}"
                        )
                        dangling += 1
                    else:
                        linked_keys.update(matched)
        if unlinked == 0 and dangling == 0:
            self.ok(f"全 {len(blocks)} 件の行動目標が実在する成果目標に紐づいています")

        # C6: 支える行動が1件もない成果目標（成果側から見た抜け）
        # C5 と同じ述語の結果（linked_keys）だけを見るので、両検査は必ず整合する。
        orphan = [k for k in keys if k not in linked_keys]
        if orphan:
            for k in orphan:
                self.warn(f"成果目標「{k}」を支える行動目標がありません")
        else:
            self.ok("全ての成果目標に、それを支える行動目標があります")

    def check_peer_consistency(self) -> None:
        """他層ファイルとの期アンカー3値の突き合わせ。不一致は WARN（FAIL にしない）。

        「不一致0件」は「比較して0件だった」と「比較対象が0件だった」を区別しないので、
        必ず比較した項目数（分母）を印字する。
        """
        print("")
        print("--- 層間整合チェック（--peer） ---")
        mine = extract_peer_anchors(self.text)
        # --file 側の階層は --type を正本にする（本文から読み直さない）。
        my_level = "week" if self.kind == "week" else "other"
        for peer_name, peer_text in self.peers:
            theirs = extract_peer_anchors(peer_text)
            peer_level = detect_level(peer_text)
            print(f"PEER: {peer_name}")
            compared = 0
            mismatched = 0
            for name, _rx, _kind in PEER_ANCHORS:
                a, b = mine.get(name), theirs.get(name)
                if name in WEEKLY_EXEMPT_ANCHORS and "week" in (my_level, peer_level):
                    print(
                        f"  SKIP: {name}（週報の最重要数字は上位の内訳のため一致検査の対象外）"
                    )
                    continue
                if a is None or b is None:
                    missing = []
                    if a is None:
                        missing.append("対象")
                    if b is None:
                        missing.append("peer")
                    print(f"  SKIP: {name}（{'・'.join(missing)}に値なし・比較対象外）")
                    continue
                compared += 1
                if a == b:
                    print(f"  MATCH: {name} = {a}")
                else:
                    mismatched += 1
                    self.warn(
                        f"層間の値ズレ: {name} 対象={a} / peer({peer_name})={b}"
                        "（期アンカーは全レベル同値。継承は作成時 pull のみなので運用上ズレ得る）"
                    )
            print(f"  層間比較: 比較{compared}項目中 不一致{mismatched}件")
            if compared == 0:
                print("  （比較できる項目が1件もありませんでした。不一致0件は検査結果ではありません）")

    def run(self) -> int:
        print("=== UBM目標設定 バリデーション ===")
        print(f"対象: {self.basename}")
        print("")

        # 0. 未展開テンプレート変数
        unexpanded = [l for l in self.lines if re.search(r"\{\{[^}]*\}\}", l)]
        if not unexpanded:
            self.ok("未展開テンプレート変数なし")
        else:
            self.fail("未展開テンプレート変数 {{...}} が残っています")

        # 1. ファイル名チェック
        if re.search(r"^UBM - [1-3]-", self.basename):
            self.ok("ファイル名プレフィックス")
        else:
            self.fail("ファイル名が 'UBM - {1,2,3}-' で始まっていません")
        if re.search(r"[0-9]{4}-[0-9]{2}-[0-9]{2}[〜~][0-9]{4}-[0-9]{2}-[0-9]{2}", self.basename):
            self.ok("日付パターン")
        else:
            self.fail("ファイル名に日付パターン (YYYY-MM-DD〜YYYY-MM-DD) がありません")

        # 2. 全角数字 (見出し行・１ヶ月・３ヶ月 除外。２ヶ月は旧期報の後方互換で除外を継続)
        zenkaku = [
            l for l in self.lines
            if re.search(r"[０-９]", l)
            and not l.startswith("##")
            and "１ヶ月" not in l
            and "２ヶ月" not in l
            and "３ヶ月" not in l
        ]
        if not zenkaku:
            self.ok("全角数字なし")
        else:
            self.fail("全角数字が含まれています")

        # 3. 差分の +/- 表記
        diff_lines = [l for l in self.lines if "差分" in l]
        if diff_lines:
            diff_values = [l for l in diff_lines if "##" not in l]
            if diff_values:
                no_sign = [
                    l for l in diff_values
                    if re.search(r"[0-9]", l) and not re.search(r"[+-]", l) and "差分】" not in l
                ]
                if not no_sign:
                    self.ok("差分の +/- 表記")
                else:
                    self.warn("差分値に +/- が付いていない可能性があります")

        # 4. 種別別 必須セクション
        # タイトル見出しは --type と一致していること（種別の取り違えを error にする）
        self.check_title_matches_type()

        if self.kind == "week":
            for lbl in ["今週の最重要数字", "今週の売上目標", "今週の売上以外の成果目標",
                        "今週の行動目標（行動管理・優先順位付き）", "習慣目標（仕組みで動く土台）",
                        "今週の判断基準", "現在のグリッドパートナー数"]:
                self.check_require_exact(lbl)
            for opt in ["到達ライン", "今期の売上目標", "前回のアカデミーへの参加日",
                        "次回のアカデミーへの参加日", "次回の壁打ち予定日", "現在事業パートナー数"]:
                self.check_section_optional(opt)
        elif self.kind == "month":
            for lbl in ["確認された情報", "今期の売上目標", "今期の累計売上実績", "前月の売上目標",
                        "前月の売上実績", "前月の売上目標と実績の差分", "前月の売上に対して未達を挽回するための行動",
                        "前月の売上以外の成果目標", "前月の売上以外の成果実績",
                        "前月の売上以外の成果に対して未達を挽回するための行動", "前月の売上以外の成果目標と実績の差分",
                        "前月の行動目標（行動管理）", "前月の行動実績（行動管理）", "前月の行動目標と実績の差分",
                        "前月の行動に対して未達を挽回するための行動", "今月の売上目標", "今月の売上以外の成果目標",
                        "今月の行動目標（行動管理・優先順位付き）", "現在事業パートナー数", "現在のグリッドパートナー数",
                        "プロジェクト別タスク", "今月やらないこと（明確に排除するもの）", "今月末の振り返りチェックリスト"]:
                self.check_require_exact(lbl)
        elif self.kind == "period":
            for lbl in ["確認された情報", "今期の累計売上実績", "前期の売上目標", "前期の売上実績",
                        "前期の売上目標と実績の差分", "前期の売上に対して未達を挽回するための行動",
                        "前期の売上以外の成果目標", "前期の売上以外の成果実績",
                        "前期の売上以外の成果に対して未達を挽回するための行動", "前期の売上以外の成果目標と実績の差分",
                        "前期の行動目標（行動管理）", "前期の行動実績（行動管理）", "前期の行動目標と実績の差分",
                        "前期の行動に対して未達を挽回するための行動", "今期の売上目標", "今期の売上以外の成果目標",
                        "今期の行動目標（行動管理・優先順位付き）", "現在事業パートナー数", "現在のグリッドパートナー数",
                        "今期やらないこと（明確に排除するもの）", "今期末の振り返りチェックリスト", "事業の柱"]:
                self.check_require_exact(lbl)

        # 5. 空セクション
        # 見出しの直後に空行を1行置くのは通常の Markdown。直後の1行だけを見ると
        # 正しく書かれた節が全部「空」になるので、次の見出しまでに本文があるかで判定する。
        empty_sections = []
        for i, line in enumerate(self.lines):
            if not line.startswith("## 【"):
                continue
            j = i + 1
            has_body = False
            while j < len(self.lines) and not self.lines[j].startswith("## "):
                if self.lines[j].strip() and not re.match(r"^\s*-{3,}\s*$", self.lines[j]):
                    has_body = True
                    break
                j += 1
            if not has_body:
                empty_sections.append(line)
        if empty_sections:
            self.warn("空のセクションがあります: " + " / ".join(empty_sections))

        # 5b. 重複見出し
        counts: dict[str, int] = {}
        for l in self.lines:
            if l.startswith("## 【"):
                key = re.sub(r"[ \t]+$", "", l)
                counts[key] = counts.get(key, 0) + 1
        dups = {k: c for k, c in counts.items() if c > 1}
        if not dups:
            self.ok("重複見出しなし")
        else:
            self.fail("完全一致する見出し「## 【…】」が2回以上出現しています（重複禁止）")

        # --- 目標・実績・差分フォーマット ---
        print("")
        print("--- 目標・実績・差分フォーマットチェック ---")
        self.check_goal_section(r"【前.*の売上目標】", "前期間の売上目標", "numeric")
        self.check_goal_section(r"【前.*の売上実績】", "前期間の売上実績", "numeric")
        self.check_goal_section(r"【前.*の売上目標と実績の差分】", "前期間の売上差分", "numeric")
        self.check_goal_section(r"【今(週|月|期)の売上目標】", "今期間の売上目標", "numeric")
        self.check_goal_section(r"【前.*の売上以外の成果目標】", "前期間の売上以外の成果目標", "bullet")
        self.check_goal_section(r"【前.*の売上以外の成果実績】", "前期間の売上以外の成果実績", "bullet")
        self.check_goal_section(r"【前.*の売上以外の成果目標と実績の差分】", "前期間の売上以外の成果差分", "bullet")
        self.check_goal_section(r"【前.*の行動目標", "前期間の行動目標", "bullet")
        self.check_goal_section(r"【前.*の行動実績", "前期間の行動実績", "bullet")
        self.check_goal_section(r"【前.*の行動目標と実績の差分】", "前期間の行動差分", "bullet")

        self.check_goal_chain()

        # --- 品質チェック ---
        print("")
        print("--- 品質チェック ---")

        def action_pred(line: str) -> bool:
            return ("行動目標" in line and self._period_word() in line
                    and not re.search(r"差分|実績", line))

        action_section = self.capture_awk(action_pred)
        action_items = [l for l in action_section if re.match(r"^([*-] |・)", l)]
        if action_section:
            ng = [l for l in action_section if re.search(r"頑張る|意識する|気をつける|心がける|努力する", l)]
            if not ng:
                self.ok("NG表現なし（行動目標セクション）")
            else:
                self.fail("行動目標に精神論が含まれています")
            if action_items:
                no_number = [l for l in action_items if not re.search(r"[0-9]", l)]
                if not no_number:
                    self.ok("行動目標に数値あり")
                else:
                    self.warn("数値のない行動目標があります")
                no_date = [
                    l for l in action_items
                    if not re.search(r"[0-9]{4}-[0-9]{2}-[0-9]{2}|[0-9]{1,2}/[0-9]{1,2}|月曜|火曜|水曜|木曜|金曜|毎日|毎朝|毎週|今週|までに", l)
                ]
                if not no_date:
                    self.ok("行動目標に期日あり")
                else:
                    self.warn("期日のない行動目標があります")

        # 9. やらないこと 3項目以上
        def notdoing_pred(line: str) -> bool:
            return ("やらないこと" in line and re.search(r"今(週|月|期)", line)
                    and "守れたか" not in line)

        not_doing = self.capture_awk(notdoing_pred)
        if not_doing:
            bullet_count = sum(1 for l in not_doing if re.match(r"^([*-] |・)", l))
            table_count = sum(1 for l in not_doing if re.match(r"^\|", l))
            heading_count = sum(1 for l in not_doing if re.match(r"^### ", l))
            table_count = table_count - 2 if table_count > 2 else 0
            total = bullet_count + table_count + heading_count
            if total >= 3:
                self.ok(f"「やらないこと」{total}項目")
            else:
                self.fail(f"「やらないこと」が{total}項目です（必須: 3項目以上）")

        # 10. 固有名詞
        if action_section:
            if any(re.search(r"さん|様", l) for l in action_section):
                self.ok("行動目標に固有名詞あり")
            else:
                self.warn("行動目標に人の名前が入っていません（推奨: 具体的な人名を含める）")

        # 11. プロジェクト別タスク
        project_section = self.sed_range("【プロジェクト別タスク】", r"^## ")
        has_project = any("【プロジェクト別タスク】" in l for l in self.lines)
        if self.kind == "period" and has_project:
            self.fail("期報にプロジェクト別タスクが含まれています（期報では出力禁止）")
        if self.kind == "month" and not has_project:
            self.fail("月報にプロジェクト別タスクがありません（月報では必須）")
        if has_project and self.kind != "period":
            checkbox_count = sum(1 for l in project_section if re.match(r"^(- |・)\[[ x]\] ", l))
            if checkbox_count >= 1:
                self.ok(f"プロジェクト別タスクにチェックボックスが {checkbox_count} 件あり")
            else:
                self.fail("プロジェクト別タスクにチェックボックス（- [ ] / - [x]）が1件もありません")
            recipient_count = sum(1 for l in project_section if re.match(r"^(- |・)\[[ x]\] \[[^\]]+\] \[[^\]]+\] .+", l))
            if recipient_count >= checkbox_count:
                self.ok("プロジェクト別タスクが [期日] [提出先・宛先] 形式")
            else:
                self.fail("プロジェクト別タスクは '- [ ] [期日] [提出先・宛先] 対象物・行動' 形式で記載してください")
            client_owner = sum(1 for l in project_section if re.match(r"^(- |・)先方担当者: .+", l))
            project_heading = sum(1 for l in project_section if re.match(r"^### ", l))
            if client_owner >= project_heading:
                self.ok("各プロジェクトに先方担当者あり")
            else:
                self.fail("各プロジェクトに '- 先方担当者: ...' を記載してください")
            if any(re.match(r"^##### ", l) for l in project_section):
                self.fail("プロジェクト別タスクが3階層以上になっています（2階層まで）")

        # 12. 行動目標チェックボックス (週報のみ)
        if self.kind == "week":
            action_full = self.capture_from_start(r"^## 【今週.*行動目標")
            action_checkboxes = sum(1 for l in action_full if re.match(r"^(- |・)\[[ x]\] ", l))
            if action_checkboxes >= 3:
                self.ok(f"行動目標がチェックボックス形式（{action_checkboxes}項目）")
            else:
                self.fail("行動目標は '- [ ] ...' チェックボックス形式で3項目以上にしてください（済/未済の二値性）")

        # 13. 習慣目標 (週報のみ)
        if self.kind == "week":
            habit_section = self.sed_range("【習慣目標", r"^## ")
            if any("【習慣目標" in l for l in self.lines):
                habit_checkboxes = sum(1 for l in habit_section if re.match(r"^(- |・)\[[ x]\] ", l))
                if habit_checkboxes >= 6:
                    self.ok("習慣目標に3原則 × 2項目以上のチェックボックスあり")
                else:
                    self.warn("習慣目標のチェックボックスが少ないです（推奨: 各原則2項目以上）")

        # 14. 層間整合（--peer 指定時のみ。未指定なら既存の挙動と完全に同一）
        if self.peers:
            self.check_peer_consistency()

        print("")
        print("=== 結果 ===")
        print(f"エラー: {self.errors} 件")
        print(f"警告: {self.warnings} 件")
        if self.errors == 0:
            print("STATUS: PASS")
            return 0
        print("STATUS: FAIL")
        return 1


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="UBM目標設定 出力バリデーション", add_help=True)
    ap.add_argument("--file", required=True, help="検証対象の Markdown ファイル")
    ap.add_argument("--type", required=True, choices=list(TYPE_MAP.keys()),
                    help="目標種別 weekly|monthly|quarterly（bimonthly は quarterly の後方互換の別名）")
    ap.add_argument("--peer", action="append", default=None, metavar="PATH",
                    help="層間整合を突き合わせる他層のファイル（任意・複数指定可）。"
                         "期アンカー3値の不一致を WARN で報告する（FAIL にはしない）")
    try:
        args = ap.parse_args(argv)
    except SystemExit as e:
        # --help / --version は argparse が SystemExit(0) を投げる。これを 2 に潰すと
        # 「usage は正常に出たのに異常終了」になり、rc で成否を見る側が誤判定する。
        return 0 if e.code == 0 else 2

    path = Path(args.file)
    if not path.is_file():
        print(f"ERROR: ファイルが見つかりません: {path}", file=sys.stderr)
        return 1

    peers: list[tuple[str, str]] = []
    for peer in args.peer or []:
        ppath = Path(peer)
        if not ppath.is_file():
            print(f"ERROR: --peer のファイルが見つかりません: {ppath}", file=sys.stderr)
            return 1
        peers.append((ppath.name, ppath.read_text(encoding="utf-8")))

    kind = TYPE_MAP[args.type]
    text = path.read_text(encoding="utf-8")
    return Validator(text, path.name, kind, args.type, peers).run()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
