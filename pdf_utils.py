import os
import base64
import fitz  # PyMuPDF
import requests

PDF_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pdfs")
os.makedirs(PDF_DIR, exist_ok=True)


def _github_headers(token: str) -> dict:
    return {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }


def _github_upload(token: str, repo: str, filename: str, pdf_bytes: bytes):
    url = f"https://api.github.com/repos/{repo}/contents/pdfs/{filename}"
    headers = _github_headers(token)
    resp = requests.get(url, headers=headers, timeout=15)
    sha = resp.json().get("sha") if resp.status_code == 200 else None
    payload = {
        "message": f"上傳保母車文件: {filename}",
        "content": base64.b64encode(pdf_bytes).decode("utf-8"),
        "branch": "main",
    }
    if sha:
        payload["sha"] = sha
    resp = requests.put(url, headers=headers, json=payload, timeout=30)
    resp.raise_for_status()


def _github_delete(token: str, repo: str, filename: str):
    url = f"https://api.github.com/repos/{repo}/contents/pdfs/{filename}"
    headers = _github_headers(token)
    resp = requests.get(url, headers=headers, timeout=15)
    if resp.status_code != 200:
        return
    sha = resp.json()["sha"]
    payload = {
        "message": f"刪除保母車文件: {filename}",
        "sha": sha,
        "branch": "main",
    }
    resp = requests.delete(url, headers=headers, json=payload, timeout=30)
    resp.raise_for_status()


def upload_pdf(pdf_bytes: bytes, filename: str, github_token: str = "", github_repo: str = ""):
    filepath = os.path.join(PDF_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(pdf_bytes)
    if github_token and github_repo:
        _github_upload(github_token, github_repo, filename, pdf_bytes)


def delete_pdf(filename: str, github_token: str = "", github_repo: str = ""):
    filepath = os.path.join(PDF_DIR, filename)
    if os.path.exists(filepath):
        os.remove(filepath)
    if github_token and github_repo:
        _github_delete(github_token, github_repo, filename)


def list_pdfs() -> list[dict]:
    files = []
    for name in sorted(os.listdir(PDF_DIR)):
        if name.lower().endswith(".pdf"):
            filepath = os.path.join(PDF_DIR, name)
            modified = os.path.getmtime(filepath)
            files.append({"name": name, "path": filepath, "modified": str(modified)})
    return files


def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    text_parts = [page.get_text() for page in doc]
    doc.close()
    return "\n".join(text_parts)


def load_all_docs() -> list[dict]:
    docs = []
    for f in list_pdfs():
        try:
            with open(f["path"], "rb") as fh:
                text = extract_text_from_pdf(fh.read())
            docs.append({"name": f["name"], "modified": f["modified"], "text": text if text.strip() else "（無文字內容）"})
        except Exception as e:
            docs.append({"name": f["name"], "modified": f["modified"], "text": f"（無法讀取：{e}）"})
    return docs
