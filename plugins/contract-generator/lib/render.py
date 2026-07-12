#!/usr/bin/env python3
# /// script
# name: render
# purpose: Drive REST(urllib)でひな形DL・Docs化保存・PDF export保存を行う(標準ライブラリのみ・pip不要)。
# inputs:
#   - access_token / docx パス / フォルダID
# outputs:
#   - Google Docs(黄色) + PDF(クリーン) を Drive フォルダへ
# contexts: [C, E]
# network: true
# write-scope: google-drive
# dependencies: []
# requires-python: ">=3.11"
# ///
"""責務: render-and-store(標準ライブラリ urllib・pip不要)。

Drive v3 REST を urllib で直叩きする。SA 認証トークンは config_auth.get_access_token で取得。
ひな形最新版取得 / 黄色維持 .docx を Google Docs 化保存 / 黄色除去 .docx を PDF export 保存。
各関数は access_token(str) を第1引数に受け取る。
"""

import json
import os
import shutil
import tempfile

import config_auth

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
GDOC_MIME = "application/vnd.google-apps.document"
PDF_MIME = "application/pdf"
DRIVE = "https://www.googleapis.com/drive/v3/files"
UPLOAD = "https://www.googleapis.com/upload/drive/v3/files"
_BOUNDARY = "===============contract-generator-boundary=="


def fetch_template(token, templates_folder_id, name_pattern):
    """フォルダ内で name_pattern を含む .docx の最新(modifiedTime降順)を temp に DL。"""
    q = (f"'{templates_folder_id}' in parents and trashed=false "
         f"and name contains '{name_pattern}'")
    res = config_auth.gapi_get(DRIVE, token, params={
        "q": q, "orderBy": "modifiedTime desc",
        "fields": "files(id,name,modifiedTime)",
        "supportsAllDrives": "true", "includeItemsFromAllDrives": "true",
    })
    files = res.get("files", [])
    if not files:
        raise FileNotFoundError(f"ひな形が見つかりません: pattern='{name_pattern}'")
    fid = files[0]["id"]
    data = config_auth.gapi_get(f"{DRIVE}/{fid}", token,
                                params={"alt": "media", "supportsAllDrives": "true"}, raw=True)
    # O27: ひな形 .docx は機微情報を含み得るため隔離 tempdir に配置。呼出元 (engine.py)
    # が docx_fill 完了後に親ディレクトリごと削除する責務を持つ (永続パス不要なため移動不要)。
    tmpdir = tempfile.mkdtemp(prefix="cg_tpl_")
    path = os.path.join(tmpdir, f"tpl_{fid}.docx")
    try:
        with open(path, "wb") as f:
            f.write(data)
    except Exception:
        shutil.rmtree(tmpdir, ignore_errors=True)
        raise
    return path


def _multipart(metadata, media_bytes, media_mime):
    """metadata(JSON) + media の multipart/related ボディを組み立てる。"""
    head = (f"--{_BOUNDARY}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n"
            ).encode("utf-8") + json.dumps(metadata).encode("utf-8")
    mid = (f"\r\n--{_BOUNDARY}\r\nContent-Type: {media_mime}\r\n\r\n").encode("utf-8")
    tail = (f"\r\n--{_BOUNDARY}--\r\n").encode("utf-8")
    return head + mid + media_bytes + tail, f"multipart/related; boundary={_BOUNDARY}"


def _upload(token, metadata, media_bytes, media_mime):
    body, ct = _multipart(metadata, media_bytes, media_mime)
    url = f"{UPLOAD}?uploadType=multipart&supportsAllDrives=true&fields=id,webViewLink"
    return config_auth.gapi_send(url, token, method="POST", raw_body=body, content_type=ct)


def upload_as_gdoc(token, docx_path, name, folder_id):
    """.docx を Google Docs に変換アップロード(黄色維持)。returns (id, webViewLink)。"""
    with open(docx_path, "rb") as f:
        media = f.read()
    meta = {"name": name, "parents": [folder_id], "mimeType": GDOC_MIME}
    res = _upload(token, meta, media, DOCX_MIME)
    return res["id"], res.get("webViewLink", f"https://docs.google.com/document/d/{res['id']}/edit")


def store_pdf(token, clean_docx_path, name, folder_id, persist_dir=None):
    """黄色除去 .docx → 一時 Google Docs → PDF export → フォルダ保存。returns (pdf_id, link)。

    O27: PDF 中間ファイルは TemporaryDirectory 内に閉じ込め関数終了時に確実削除。
    呼出元が最終 PDF ローカルパスを必要とする場合のみ persist_dir または環境変数
    HARNESS_OUTPUT_DIR を指定 → shutil.copy2 で永続化してから tempdir 破棄。
    """
    with open(clean_docx_path, "rb") as f:
        media = f.read()
    tmp = _upload(token, {"name": f"_tmp_{name}", "mimeType": GDOC_MIME}, media, DOCX_MIME)
    tmp_id = tmp["id"]
    try:
        pdf = config_auth.gapi_get(f"{DRIVE}/{tmp_id}/export", token,
                                   params={"mimeType": PDF_MIME}, raw=True)
        with tempfile.TemporaryDirectory(prefix="cg_pdf_") as tmpdir:
            pdf_path = os.path.join(tmpdir, f"{name}.pdf")
            try:
                with open(pdf_path, "wb") as fh:
                    fh.write(pdf)
                pf = _upload(token, {"name": f"{name}.pdf", "parents": [folder_id]},
                             pdf, PDF_MIME)
                dest = persist_dir or os.environ.get("HARNESS_OUTPUT_DIR")
                if dest:
                    os.makedirs(dest, exist_ok=True)
                    shutil.copy2(pdf_path, os.path.join(dest, f"{name}.pdf"))
                return pf["id"], pf.get("webViewLink",
                                        f"https://drive.google.com/file/d/{pf['id']}/view")
            finally:
                # TemporaryDirectory が __exit__ で削除するが、例外時の二重保険として明示
                shutil.rmtree(tmpdir, ignore_errors=True)
    finally:
        config_auth.gapi_send(f"{DRIVE}/{tmp_id}?supportsAllDrives=true", token, method="DELETE")
