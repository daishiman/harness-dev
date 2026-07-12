#!/usr/bin/env python3
# /// script
# name: postal_api
# purpose: 日本郵便「郵便番号・デジタルアドレスAPI」(addresszip V2) で住所→郵便番号を逆引きし、一意確定したものだけを確度付きで返す(誤値を入れない)。
# inputs:
#   - net: POST https://api.da.pf.japanpost.jp/api/v2/j/token (client_credentials + x-forwarded-for)
#   - net: POST https://api.da.pf.japanpost.jp/api/v2/addresszip (Bearer token)
#   - keychain: japanpost-da-api.<keychain-prefix> (client_id / secret_key / egress_ip) ※notion_config 経由
#   - egress IP 解決順: Keychain `japanpost-da-api.<keychain-prefix>`/`egress_ip` (pin・優先) → env COMPANY_MASTER_EGRESS_IP (低優先フォールバック) → 自動検出 / COMPANY_MASTER_EGRESS_IP_DETECT_URL
#   - net: 送信元IP自動検出の公開エコー (既定 https://api.ipify.org。env 未設定時のみ)
#   - keychain/env: proxy_url / proxy_token (中央プロキシ経由時。設定時は鍵/IP 不要)
# outputs:
#   - api: lookup_postal(normalized_address, company_name="", _search_fn=None) -> {value, certainty, remark_key, source_url, attempts}
#   - exit: 0=OK (CLI 自己検査・実 API 疎通を伴う)
# contexts: [C, E]
# network: true
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""日本郵便 addresszip V2 による住所→郵便番号逆引き (postal_from_address の決定論実体)。

一括 DL データではなく日本郵便公式 API で逆引きする。API は逆引きのため曖昧な住所だと
候補が多数返るが、レスポンスの level(1=都道府県/2=市区町村/3=町域) と候補の zip 収束で
「確定してよいか」を判定し、一意確定したものだけ NNN-NNNN で返す。一意でない/未一致/取得失敗は
空欄 + 未確定 (誤値を入れない非対称コスト原則)。enrich は戻り値 attempts の result/reject_reason
種別で remark を選ぶため、reject_reason は失敗種別語 (auth: / network:) を先頭に含める。

認証 (notion_config が SSOT):
  client_id / secret_key … Keychain `japanpost-da-api.<keychain-prefix>`。
  送信元IP (x-forwarded-for) … Keychain `japanpost-da-api.<keychain-prefix>`/`egress_ip` の pin を優先、無ければ
  env `COMPANY_MASTER_EGRESS_IP` (低優先フォールバック)、どちらも無ければ `detect_egress_ip()` で
  実際の送信元グローバルIPを自動検出する (BYO: ユーザが自分のIPを調べる手間を省く)。日本郵便に
  システム登録した IP と一致している必要がある (IP 認証)。ズレると 401/403 → reject_reason `auth:`。

検索戦略 (3段・M4):
  1. 構造化検索: normalize 済み住所を pref_name / city_name / town_name に分解し、town_name は
     素の町域 → 小字「字○○」/大字を段階剥離した町域 の順で複数回投げる (_town_variants)。
  2. freeword フォールバック: 1 で確定できないときのみ、番地を除いた住所全体を freeword で投げる。
  3. 市区町村前方一致フォールバック: 1-2 が全 miss のとき {pref/city} で町域一覧を取り、入力住所への
     最長前方一致で町域を確定する (pick_best_prefix)。「字」マーカー無しの小字・枝番・カナ末尾や
     町域名に数字を含む住所も拾える。一覧不返/不一致なら空欄に縮退するだけで誤値も回帰も生まない。
     ※ {pref/city} 照会で実 API が町域一覧を返すか (=この段の再現率効果) は精度には無影響だが
       未実証なので、`doctor --probe` 等で字マーカー無し住所を1件流して実機確認することを推奨。
  いずれも pick_best / pick_best_prefix で一意確定のみ採用するため、クエリ品質は再現率にのみ影響し
  精度には影響しない。

中央プロキシモード (不特定多数・多拠点配布向け):
  `notion_config.get_postal_proxy_url()` が設定されていれば、token 発行/直叩きをせず query を
  プロキシへ中継する (`_proxy_search`)。プロキシが固定IP1件で日本郵便鍵を保持し addresszip を代行する
  ため、各ユーザのプラグインは**日本郵便の鍵も送信元IP登録も不要**になる。pick_best 等の確定判定は不変。
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import notion_config  # noqa: E402  (japanpost 認証情報 / egress IP の SSOT)

BASE_URL = "https://api.da.pf.japanpost.jp"
TOKEN_PATH = "/api/v2/j/token"
ADDRESSZIP_PATH = "/api/v2/addresszip"
# 確定郵便番号の固定検証手段 URL (weak provenance)。API 逆引きは per-value の取得元ページが
# 存在しないため、人間が再検証できる日本郵便 (郵便番号検索の入口) トップ URL を返す。
# 本値はプラグイン全体の唯一の正本 (SSOT)。他スクリプトは literal 再定義せず本定数を import する。
JAPANPOST_VERIFY_URL = "https://www.post.japanpost.jp/"

CERTAINTY_PUBLIC_FETCHED = "公的データ取得"
CERTAINTY_UNRESOLVED = "未確定(要確認)"

# 都道府県名 (pref_name 抽出用)。normalize.PREFECTURES と同一だが、postal_api 単独でも
# import 失敗しないよう自前で持つ (正規化は normalize に委譲し、ここは前方一致の剥がしのみ)。
_PREFECTURES = (
    "北海道", "青森県", "岩手県", "宮城県", "秋田県", "山形県", "福島県", "茨城県",
    "栃木県", "群馬県", "埼玉県", "千葉県", "東京都", "神奈川県", "新潟県", "富山県",
    "石川県", "福井県", "山梨県", "長野県", "岐阜県", "静岡県", "愛知県", "三重県",
    "滋賀県", "京都府", "大阪府", "兵庫県", "奈良県", "和歌山県", "鳥取県", "島根県",
    "岡山県", "広島県", "山口県", "徳島県", "香川県", "愛媛県", "高知県", "福岡県",
    "佐賀県", "長崎県", "熊本県", "大分県", "宮崎県", "鹿児島県", "沖縄県",
)
# 政令市(市+区) を 1 単位の city とし、それ以外は最初の 市/区/町/村 までを city とする。
# 郡 は終端でないため `郡○○町` のように city へ取り込まれる (日本郵便の市区町村単位と一致)。
_CITY_RE = re.compile(r"(.+?市.+?区|.+?[市区町村])(.*)")
# 番地 (丁目・番・号を含む数値以降) を落とす: NFKC 後の ASCII 数字で切る。
_BANCHI_RE = re.compile(r"\d")
# 小字「字○○」境界。日本郵便の町域DBは大字粒度までで小字は照合に通らないため town から削る。
# 大字の「字」は (?<!大) で保護する（「大字北京田」の先頭字を誤って切らない）。
_KOAZA_SPLIT_RE = re.compile(r"(?<!大)字")

# token のプロセス内メモ化 (expires_in を尊重。margin 60s 手前で失効扱い)。
_TOKEN_CACHE: dict[str, float | str] = {}
_TOKEN_MARGIN_SEC = 60

# 送信元IP (x-forwarded-for) の自動検出。Keychain `egress_ip` pin (主) があればそれを正とし、
# 次に env COMPANY_MASTER_EGRESS_IP (従・低優先フォールバック)、どちらも無ければ
# 公開エコーサービスで「実際に外へ出ていくグローバルIP」を検出する (解決順は resolve_egress_ip)。
# 日本郵便ゲートウェイが見る送信元IPと同一値が得られるため、検出値をそのまま x-forwarded-for に
# 使え、かつ for Biz に登録すべきIPとしてユーザへ提示できる (BYO の「自分のIPが分からない」摩擦を解消)。
# 検出先は env COMPANY_MASTER_EGRESS_IP_DETECT_URL で差し替え可。プロセス内 1 回キャッシュ。
EGRESS_DETECT_URL_ENV = "COMPANY_MASTER_EGRESS_IP_DETECT_URL"
DEFAULT_EGRESS_DETECT_URL = "https://api.ipify.org"
_EGRESS_CACHE: dict[str, str] = {}


def detect_egress_ip(timeout: int = 5, _opener=None) -> str | None:
    """送信元グローバルIPを公開エコーサービスで検出する。失敗は None (プロセス内キャッシュ)。

    `_opener(url, timeout) -> str` を渡すとネット非依存でテストできる。
    """
    if "ip" in _EGRESS_CACHE:
        return _EGRESS_CACHE["ip"]
    url = (os.environ.get(EGRESS_DETECT_URL_ENV) or DEFAULT_EGRESS_DETECT_URL).strip()
    try:
        if _opener is not None:
            raw = _opener(url, timeout)
        else:
            req = urllib.request.Request(url, headers={"User-Agent": "company-master/0.1"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
                raw = resp.read().decode("utf-8", "replace")
    except Exception:  # noqa: BLE001  検出失敗は致命でない (None で呼び出し側が判断)
        return None
    ip = (raw or "").strip()
    # 簡易検証: IPv4/IPv6 の文字種・長さのみ (厳密検証はしない)。
    if ip and len(ip) <= 45 and all(c in "0123456789abcdefABCDEF.:" for c in ip):
        _EGRESS_CACHE["ip"] = ip
        return ip
    return None


def resolve_egress_ip() -> str | None:
    """x-forwarded-for に使う送信元IP: notion_config の pin (Keychain egress_ip 優先 → env
    COMPANY_MASTER_EGRESS_IP の低優先フォールバック) を採り、無ければ自動検出へフォールバック。"""
    return notion_config.get_japanpost_egress_ip() or detect_egress_ip()


def _base_url() -> str:
    """日本郵便 API 接続先。notion_config の上書き (テスト/stub 環境) があればそれ、無ければ本番既定。"""
    return notion_config.get_japanpost_base_url() or BASE_URL


class JapanPostError(Exception):
    """addresszip API 呼び出しの失敗。kind で remark 種別 (auth / network) を区別する。"""

    def __init__(self, kind: str, detail: str):
        super().__init__(f"{kind}: {detail}")
        # "auth"(401/403/認証情報不在) | "notfound"(404 該当住所なし=miss) | "network"(5xx/timeout/その他)
        self.kind = kind
        self.detail = detail


def _post_json(url: str, payload: dict, headers: dict, timeout: int = 30) -> dict:
    """JSON を絶対 URL へ POST し JSON を受け取る。失敗は JapanPostError(kind) へ分類して送出する。"""
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            return json.load(resp)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:200]
        if e.code in (401, 403):
            raise JapanPostError("auth", f"HTTP {e.code} 認証失敗 (IP未登録/鍵不正の可能性): {body}")
        if e.code == 404:
            # addresszip は「該当する住所なし」を 200+空配列でなく HTTP 404 で返す。これは
            # 通信エラーでなく miss (一意確定不能/未一致) として扱う。
            raise JapanPostError("notfound", f"HTTP 404 該当住所なし: {body}")
        raise JapanPostError("network", f"HTTP {e.code}: {body}")
    except (urllib.error.URLError, TimeoutError) as e:
        raise JapanPostError("network", f"通信失敗 ({type(e).__name__}): {e}")


def get_token(now: float | None = None, _post_fn=None) -> str:
    """client_credentials でトークン(JWT)を取得する。expires_in を尊重してプロセス内メモ化する。

    POST /api/v2/j/token  header: x-forwarded-for(送信元IP) 必須  body: grant_type/client_id/secret_key
    return body: {scope, token_type:"jwt", expires_in, token}
    認証情報 (Keychain) / egress IP (Keychain pin 優先 → env 低優先 → 自動検出) は notion_config が SSOT。
    不在は JapanPostError(auth)。
    """
    t = time.time() if now is None else now
    cached_exp = _TOKEN_CACHE.get("exp")
    if isinstance(cached_exp, (int, float)) and t < cached_exp - _TOKEN_MARGIN_SEC:
        return str(_TOKEN_CACHE["token"])
    creds = notion_config.get_japanpost_credentials()
    egress_ip = resolve_egress_ip()
    if not creds or not creds[0] or not creds[1]:
        raise JapanPostError("auth", "japanpost 認証情報 (Keychain japanpost-da-api.<keychain-prefix>) 不在")
    if not egress_ip:
        raise JapanPostError(
            "network",
            "送信元IP を解決できない (Keychain japanpost-da-api.<keychain-prefix>/egress_ip pin も env COMPANY_MASTER_EGRESS_IP も未設定かつ自動検出失敗=ネット不達の可能性)")
    client_id, secret_key = creds
    post = _post_fn or _post_json
    data = post(
        _base_url() + TOKEN_PATH,
        {"grant_type": "client_credentials", "client_id": client_id, "secret_key": secret_key},
        {"x-forwarded-for": egress_ip},
    )
    token = data.get("token")
    if not token:
        raise JapanPostError("auth", f"token 不在のレスポンス: {str(data)[:120]}")
    expires_in = data.get("expires_in")
    if isinstance(expires_in, (int, float)) and expires_in > 0:
        _TOKEN_CACHE["token"] = token
        _TOKEN_CACHE["exp"] = t + float(expires_in)
    return str(token)


def search_zip(token: str, query: dict, egress_ip: str | None = None, _post_fn=None) -> tuple[list[dict], int | None]:
    """住所の一部 (query) から郵便番号候補を検索する (POST /api/v2/addresszip, Bearer)。

    return: (addresses, level)  level 1=都道府県一致 / 2=市区町村一致 / 3=町域一致。
    """
    headers = {"Authorization": f"Bearer {token}"}
    if egress_ip:
        headers["x-forwarded-for"] = egress_ip
    post = _post_fn or _post_json
    data = post(_base_url() + ADDRESSZIP_PATH, query, headers)
    return data.get("addresses", []) or [], data.get("level")


def _proxy_search(proxy_url: str, proxy_token: str | None, query: dict,
                  _post_fn=None) -> tuple[list[dict], int | None]:
    """中央プロキシ経由で addresszip 検索する (ローカルに日本郵便鍵/IP 不要)。

    プロキシは query (addresszip と同じ body) を受け、日本郵便のレスポンス形 {addresses, level}
    をそのまま返す契約。proxy_token があれば Bearer で通行認証する。失敗は JapanPostError(kind)。
    """
    headers = {}
    if proxy_token:
        headers["Authorization"] = f"Bearer {proxy_token}"
    post = _post_fn or _post_json
    data = post(proxy_url, query, headers)
    return data.get("addresses", []) or [], data.get("level")


def _strip_banchi(s: str) -> str:
    """番地 (最初の数字以降) を落とす。normalize 済み (NFKC) 前提で ASCII 数字で切る。"""
    return _BANCHI_RE.split(s or "", 1)[0]


def _city_rest(normalized: str) -> dict:
    """正規化済み住所を {pref_name, city_name, rest} へ分解する (純関数)。

    rest は市区町村以降の生文字列 (番地も小字も含む。前方一致フォールバック用)。
    都道府県起点でない住所は {}、市区町村が判別できない住所は {pref_name} のみを返す。
    """
    s = (normalized or "").strip()
    pref = next((p for p in _PREFECTURES if s.startswith(p)), None)
    if not pref:
        return {}
    rest = s[len(pref):]
    m = _CITY_RE.match(rest)
    if not m:
        # 市区町村が判別できない (rest が空/番地のみ等) → 都道府県のみ
        return {"pref_name": pref}
    return {"pref_name": pref, "city_name": m.group(1), "rest": m.group(2).strip()}


def _split_address(normalized: str) -> dict:
    """正規化済み住所 (都道府県起点) を {pref_name, city_name, town_name} へ分解する (純関数)。

    都道府県起点でない (= normalize_address が空に潰す) 住所は {} を返す。
    town_name は番地を除いた町域。完全な分解は保証しないが、pick_best が一意確定のみ採用するため
    分解誤りは再現率を下げるだけで誤値は生まない。
    """
    cr = _city_rest(normalized)
    if "city_name" not in cr:
        return cr  # {} または {pref_name} をそのまま返す
    q = {"pref_name": cr["pref_name"], "city_name": cr["city_name"]}
    town = _strip_banchi(cr["rest"]).strip()
    if town:
        q["town_name"] = town
    return q


def _town_variants(town: str) -> list[str]:
    """町域名を「具体→粗」の順で候補化する（番地は _strip_banchi 済み前提・純関数）。

    日本郵便 addresszip の町域DBは大字（おおむね町丁目）粒度までで、小字「字○○」は照合に
    通らず404になる。素の町域 → 小字を削った町域 → 先頭「大字」を削った町域 を具体的な順に
    並べ、lookup_postal が miss のとき順に再照会させる。pick_best が一意確定のみ採用するため、
    削りすぎても再現率が下がるだけで誤値は生まない（非対称コスト原則を不変に保つ）。
    重複・空は除き、字も大字も無い町域は元の1件だけ返す（無駄な再照会を生まない）。
    """
    t = (town or "").strip()
    if not t:
        return []
    bases = [t]
    if t.startswith("大字"):
        bases.append(t[len("大字"):].strip())
    variants: list[str] = []
    for b in bases:
        for v in (b, _KOAZA_SPLIT_RE.split(b, 1)[0].strip()):
            if v and v not in variants:
                variants.append(v)
    return variants


def address_to_query(normalized_address: str) -> dict:
    """構造化検索クエリ (pref_name/city_name/town_name) を返す (純関数・stage1 用)。"""
    return _split_address(normalized_address)


def _zip_of(candidate: dict) -> str:
    """候補 dict から郵便番号フィールドを取り出す (API のフィールド名揺れに対し防御的)。"""
    for key in ("zip_code", "zip", "postal_code"):
        v = candidate.get(key)
        if v:
            return str(v)
    return ""


def _format_postal(value: str) -> str:
    """7 桁 or NNN-NNNN を NNN-NNNN へ整形する。形式不正は空。"""
    s = (value or "").strip().strip('"').replace("-", "")
    return f"{s[:3]}-{s[3:]}" if len(s) == 7 and s.isdigit() else ""


def pick_best(candidates: list[dict], level: int | None, query: dict) -> dict | None:
    """addresszip が返した候補から、クエリ住所に一意確定できる 1 件を選ぶ (純関数)。

    確定条件 (誤値を入れない非対称コスト原則・保守的):
      - level が都道府県一致のみ (1) なら候補が広すぎるため確定しない。
      - town_name 指定時は完全一致で優先的に絞る。
      - 候補の郵便番号が 1 種類に収束していれば確定 (住所が複数行でも zip が同じケース)。
      - 町域(level=3)まで一致し候補が 1 件なら確定。
      - それ以外は曖昧 → None。
    """
    if not candidates:
        return None
    if level is not None and level < 2:
        return None  # 都道府県一致のみ: 候補が広すぎる (誤値回避)
    wanted_town = query.get("town_name")
    if wanted_town:
        exact = [c for c in candidates if c.get("town_name") == wanted_town]
        if len(exact) == 1:
            return exact[0]
        if exact:
            candidates = exact  # 完全一致が複数 → 以降の zip 収束判定に委ねる
    zips = {_zip_of(c) for c in candidates}
    zips.discard("")
    if len(zips) == 1:
        return candidates[0]
    if level == 3 and len(candidates) == 1:
        return candidates[0]
    return None  # 曖昧 → 確定しない


def pick_best_prefix(candidates: list[dict], rest: str) -> dict | None:
    """市区町村レベルの町域一覧から、入力住所 rest に最長前方一致する町域を一意確定で選ぶ (純関数)。

    API が返す正式町域名 (town_name) のうち rest の先頭に一致する最長のものを採り、その zip が
    一意に収束していれば確定する。「字」マーカーの無い小字・イロハ/甲乙の枝番・カナ末尾や、
    町域名に数字を含む住所 (北24条西 等) も、正式町域一覧との前方一致で拾える (区切り文字の無い
    住所文字列だけからは町域境界を判定できないため、権威ある一覧側に境界判定を委ねる)。
    誤値非混入: 「official town_name は rest の prefix」制約 + 最長一致群の zip 収束で担保。
    曖昧 (前方一致なし/最長群の zip 割れ) は None → 呼び出し側で空欄に縮退する。
    """
    if not candidates or not rest:
        return None
    matched = [(c.get("town_name") or "", c) for c in candidates]
    matched = [(t, c) for t, c in matched if t and rest.startswith(t)]
    if not matched:
        return None
    longest = max(len(t) for t, _ in matched)
    best = [c for t, c in matched if len(t) == longest]
    zips = {_zip_of(c) for c in best}
    zips.discard("")
    return best[0] if len(zips) == 1 else None


def lookup_postal(normalized_address: str, company_name: str = "", _search_fn=None) -> dict:
    """住所→郵便番号逆引きのエントリポイント (enrich の postal_from_address が呼ぶ決定論層)。

    戻り値: {value(NNN-NNNN or ""), certainty, remark_key, source_url, attempts}。
    attempts[] = [{source:"japanpost", pattern, result(hit/miss/error), reject_reason}]。
    取得失敗(error)の reject_reason は種別語 (auth: / network:) 先頭付き。
    `_search_fn(query)->(addresses, level)` を渡すとトークン/ネットを介さずテストできる。
    company_name は将来の事業所名絞り込み余地のため受けるが、現状の確定判定では未使用。
    """
    attempts: list[dict] = []
    structured = address_to_query(normalized_address)
    freeword_addr = _strip_banchi((normalized_address or "").strip())
    queries: list[tuple[str, dict]] = []
    if structured.get("city_name"):
        town = structured.get("town_name")
        if town:
            # 町域を「具体→粗（小字/大字を段階剥離）」で複数照会。先頭は従来と同一の素の町域
            # （pattern も従来名を維持＝後方互換）。2件目以降は剥離後バリアントで再現率を補う。
            for i, tv in enumerate(_town_variants(town)):
                q = {"pref_name": structured["pref_name"],
                     "city_name": structured["city_name"], "town_name": tv}
                pattern = "structured_pref_city_town" if i == 0 else "structured_town_trimmed"
                queries.append((pattern, q))
        else:
            queries.append(("structured_pref_city_town", structured))
    if freeword_addr:
        queries.append(("freeword_no_banchi", {"freeword": freeword_addr}))
    if not queries:
        # 都道府県起点でない等で検索クエリを作れない → 未確定 (誤値を入れない)
        attempts.append({"source": "japanpost", "pattern": "none",
                         "result": "miss", "reject_reason": "検索クエリ生成不能 (住所が都道府県起点でない)"})
        return {"value": "", "certainty": CERTAINTY_UNRESOLVED,
                "remark_key": "postal_code", "source_url": "", "attempts": attempts}

    proxy_url = notion_config.get_postal_proxy_url()
    if _search_fn is not None:
        search = _search_fn
    elif proxy_url:
        # プロキシモード: ローカルに日本郵便鍵/IP 不要。query をプロキシへ中継する
        # (鍵と固定IP登録はプロキシ側に集約。不特定多数・多拠点配布向け)。
        proxy_token = notion_config.get_postal_proxy_token()

        def search(q: dict) -> tuple[list[dict], int | None]:
            return _proxy_search(proxy_url, proxy_token, q)
    else:
        egress_ip = resolve_egress_ip()

        def search(q: dict) -> tuple[list[dict], int | None]:
            token = get_token()
            return search_zip(token, q, egress_ip=egress_ip)

    auth_failed = False
    for pattern, q in queries:
        try:
            addresses, level = search(q)
        except JapanPostError as e:
            if e.kind == "notfound":
                # 404=該当住所なし は miss (誤値でなく未一致)。次クエリ/未確定へ。
                attempts.append({"source": "japanpost", "pattern": pattern,
                                 "result": "miss", "reject_reason": "該当する住所なし (HTTP 404)"})
                continue
            attempts.append({"source": "japanpost", "pattern": pattern,
                             "result": "error", "reject_reason": f"{e.kind}: {e.detail}"})
            if e.kind == "auth":
                auth_failed = True
                break  # 認証失敗は後続クエリでも同じく失敗するため打ち切り
            continue
        best = pick_best(addresses, level, q)
        if best:
            attempts.append({"source": "japanpost", "pattern": pattern,
                             "result": "hit", "reject_reason": ""})
            return {"value": _format_postal(_zip_of(best)),
                    "certainty": CERTAINTY_PUBLIC_FETCHED, "remark_key": "",
                    "source_url": JAPANPOST_VERIFY_URL, "attempts": attempts}
        attempts.append({"source": "japanpost", "pattern": pattern,
                         "result": "miss", "reject_reason": "一意確定不能または未一致"})

    # 最終フォールバック (fail-safe): ここまで全 miss でも、{都道府県+市区町村} で町域一覧を取り、
    # 入力住所への最長前方一致で町域を確定する。「字」マーカー無しの小字・枝番・カナ末尾や、
    # 町域名に数字を含む住所も拾える (正式町域一覧に境界判定を委ねる)。一覧が返らない/前方一致が
    # 無ければ現状どおり空欄に縮退するだけで誤値も回帰も生まない (純増の安全な再現率補強)。
    cr = _city_rest(normalized_address)
    if not auth_failed and cr.get("city_name") and cr.get("rest"):
        try:
            addresses, _level = search({"pref_name": cr["pref_name"], "city_name": cr["city_name"]})
        except JapanPostError as e:
            attempts.append({"source": "japanpost", "pattern": "structured_city_prefix_match",
                             "result": "miss" if e.kind == "notfound" else "error",
                             "reject_reason": "該当する住所なし (HTTP 404)" if e.kind == "notfound"
                             else f"{e.kind}: {e.detail}"})
        else:
            best = pick_best_prefix(addresses, cr["rest"])
            if best:
                attempts.append({"source": "japanpost", "pattern": "structured_city_prefix_match",
                                 "result": "hit", "reject_reason": ""})
                return {"value": _format_postal(_zip_of(best)),
                        "certainty": CERTAINTY_PUBLIC_FETCHED, "remark_key": "",
                        "source_url": JAPANPOST_VERIFY_URL, "attempts": attempts}
            attempts.append({"source": "japanpost", "pattern": "structured_city_prefix_match",
                             "result": "miss", "reject_reason": "市区町村一覧に前方一致する町域なし"})

    return {"value": "", "certainty": CERTAINTY_UNRESOLVED,
            "remark_key": "postal_code", "source_url": "", "attempts": attempts}


def main() -> int:
    """CLI 自己検査: 引数住所を逆引きする (実 API 疎通を伴う)。"""
    if len(sys.argv) != 2:
        sys.stderr.write("usage: postal_api.py <正規化済み住所(都道府県起点)>\n")
        return 2
    print(json.dumps(lookup_postal(sys.argv[1]), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
