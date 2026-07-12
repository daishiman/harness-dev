#!/usr/bin/env python3
"""mf_invoice_enrich.py (初回契約月 差分エンリッチ本体) を mock で検証する (network 不要)。

守る契約:
- needs_enrichment: 管理列『初回契約月』が空 + 顧客ID あり → True (差分対象)。
- _title / _rt: Notion properties から title / rich_text を抽出。
- query_all_pages: has_more / next_cursor のページネーション (nis._req mock)。
- main() --plan: 書込なしで対象一覧 (return 0)。
- main() 実取得: 名寄せして PATCH 書込、名寄せ失敗を集計 (return 0)。
"""
import mf_invoice_api as inv
import mf_invoice_enrich as enrich


# --- Notion page ヘルパ (現物 properties 構造に合わせる) ---

def _page(pid, title, auth_month="", cid="C1"):
    props = {
        enrich.TITLE_COL: {"title": [{"plain_text": title}]},
        enrich.CID_COL: {"rich_text": [{"plain_text": cid}]},
    }
    if auth_month is not None:
        props[enrich.AUTH_COL] = {"rich_text": ([{"plain_text": auth_month}] if auth_month else [])}
    return {"id": pid, "properties": props}


# --- _title / _rt ---

def test_title_and_rt_extract_plain_text():
    pg = _page("p1", "株式会社サンプル", auth_month="2026-03", cid="C9")
    assert enrich._title(pg) == "株式会社サンプル"
    assert enrich._rt(pg, enrich.AUTH_COL) == "2026-03"
    assert enrich._rt(pg, enrich.CID_COL) == "C9"
    # 未知列は空文字。
    assert enrich._rt(pg, "存在しない列") == ""


# --- needs_enrichment ---

def test_needs_enrichment_true_when_auth_empty_and_cid_present():
    assert enrich.needs_enrichment(_page("p", "A社", auth_month="", cid="C1")) is True


def test_needs_enrichment_false_when_auth_filled():
    assert enrich.needs_enrichment(_page("p", "A社", auth_month="2026-01", cid="C1")) is False


def test_needs_enrichment_false_when_no_cid():
    assert enrich.needs_enrichment(_page("p", "A社", auth_month="", cid="")) is False


# --- query_all_pages (ページネーション) ---

def test_query_all_pages_follows_cursor(monkeypatch):
    page1 = {"results": [{"id": "a"}, {"id": "b"}], "has_more": True, "next_cursor": "CUR2"}
    page2 = {"results": [{"id": "c"}], "has_more": False}
    seq = iter([page1, page2])
    seen = []

    def fake_req(method, path, token, body=None):
        seen.append(body)
        return next(seq)

    monkeypatch.setattr(enrich.nis, "_req", fake_req)
    out = enrich.query_all_pages("DB", "tok")
    assert [r["id"] for r in out] == ["a", "b", "c"]
    # 2回目の呼び出しに start_cursor が載る。
    assert seen[1].get("start_cursor") == "CUR2"


# --- main() --plan (書込なし) ---

def test_main_plan_reads_only(monkeypatch, capsys):
    pages = [
        _page("p1", "未取得A", auth_month="", cid="C1"),
        _page("p2", "取得済B", auth_month="2026-02", cid="C2"),
    ]
    monkeypatch.setattr(enrich.nis, "_notion_token", lambda: "tok")
    monkeypatch.setattr(enrich, "load_config",
                        lambda *a, **k: {"notion": {"database_id": "DB"}})
    monkeypatch.setattr(enrich, "query_all_pages", lambda db, token: pages)
    # PATCH が呼ばれたら失敗 (plan は書込しない)。
    monkeypatch.setattr(enrich.nis, "_req",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("plan で書込禁止")))
    monkeypatch.setattr(enrich.sys, "argv", ["mf_invoice_enrich.py", "--plan"])
    assert enrich.main() == 0
    out = capsys.readouterr().out
    assert "未取得A" in out                                 # 未取得のみ対象
    assert "取得済B" not in out


def test_main_returns_2_when_no_db_id(monkeypatch):
    monkeypatch.setattr(enrich.nis, "_notion_token", lambda: "tok")
    monkeypatch.setattr(enrich, "load_config", lambda *a, **k: {"notion": {}})
    monkeypatch.setattr(enrich.sys, "argv", ["mf_invoice_enrich.py", "--plan"])
    assert enrich.main() == 2


# --- main() 実取得 (PATCH 書込 + 名寄せ失敗集計) ---

def test_main_real_fetch_writes_and_counts_unmatched(monkeypatch, capsys):
    pages = [
        _page("p1", "株式会社マッチ", auth_month="", cid="C1"),   # 名寄せ成功 → 書込
        _page("p2", "名寄せ失敗社", auth_month="", cid="C2"),     # partners に無 → unmatched
    ]
    monkeypatch.setattr(enrich.nis, "_notion_token", lambda: "tok")
    monkeypatch.setattr(enrich, "load_config",
                        lambda *a, **k: {"notion": {"database_id": "DB"}})
    monkeypatch.setattr(enrich, "query_all_pages", lambda db, token: pages)

    # 実取得 path 内で import される mf_invoice_api を mock。
    monkeypatch.setattr(inv, "all_partners",
                        lambda: [{"id": "PT1", "name": "株式会社マッチ"}])
    monkeypatch.setattr(inv, "oldest_billing_month", lambda pid: ("2026-01", 4))

    patched = []

    def fake_req(method, path, token, body=None):
        patched.append((method, path, body))
        return {}

    monkeypatch.setattr(enrich.nis, "_req", fake_req)
    monkeypatch.setattr(enrich.sys, "argv", ["mf_invoice_enrich.py"])  # 既定=実取得
    assert enrich.main() == 0

    # 名寄せ成功した1社のみ PATCH される。
    patches = [c for c in patched if c[0] == "PATCH"]
    assert len(patches) == 1
    method, path, body = patches[0]
    assert path == "/pages/p1"
    # 初回契約月 = oldest_billing_month の YYYY-MM が書かれる。
    content = body["properties"][enrich.AUTH_COL]["rich_text"][0]["text"]["content"]
    assert content == "2026-01"

    out = capsys.readouterr().out
    assert "書込 1" in out
    assert "名寄せ失敗 1" in out                            # partners に無い1社
