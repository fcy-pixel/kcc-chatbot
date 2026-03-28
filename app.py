import streamlit as st
from openai import OpenAI
from pdf_utils import upload_pdf, delete_pdf, list_pdfs, load_all_docs

# ---------- 頁面設定 ----------
st.set_page_config(page_title="中華基督教會基慈小學 — 保母車查詢 Empowerd by Qwen AI", page_icon="🚌", layout="wide")

# ---------- 讀取設定 ----------
QWEN_API_KEY = st.secrets.get("QWEN_API_KEY", "") or ""
ADMIN_PASSWORD = st.secrets.get("ADMIN_PASSWORD", "") or ""
GITHUB_TOKEN = st.secrets.get("GITHUB_TOKEN", "") or ""
GITHUB_REPO = st.secrets.get("GITHUB_REPO", "") or ""

QWEN_BASE_URL = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
MODEL_NAME = "qwen-plus"

# ---------- 側邊欄 ----------
with st.sidebar:
    st.header("🚌 中華基督教會基慈小學")
    st.caption("保母車查詢 Empowerd by Qwen AI")

    if not QWEN_API_KEY:
        QWEN_API_KEY = st.text_input("Qwen API Key", type="password")
    if QWEN_API_KEY:
        st.success("✅ Qwen API Key 已設定")

    st.divider()
    mode = st.radio("模式", ["💬 聊天", "🔧 管理員"], horizontal=True)

    if mode == "🔧 管理員":
        pwd = st.text_input("管理員密碼", type="password")
        if pwd and pwd != ADMIN_PASSWORD:
            st.error("密碼錯誤")
            mode = "💬 聊天"
        elif not pwd:
            mode = "💬 聊天"

    st.divider()
    if st.button("🔄 重新載入文件", use_container_width=True):
        st.session_state.pop("docs", None)
        st.rerun()

# ==========================================
# 管理員模式：上傳 / 刪除 PDF
# ==========================================
if mode == "🔧 管理員":
    st.title("🔧 管理員 — 管理保母車文件")

    st.subheader("📤 上傳 PDF")
    uploaded_files = st.file_uploader(
        "選擇 PDF 檔案（路線表、時間表、通告、規則等）", type="pdf", accept_multiple_files=True
    )
    if uploaded_files and st.button("確認上傳", type="primary"):
        for uf in uploaded_files:
            with st.spinner(f"上傳 {uf.name}（同步到 GitHub）..."):
                upload_pdf(uf.getvalue(), uf.name, GITHUB_TOKEN, GITHUB_REPO)
            st.success(f"✅ 已上傳：{uf.name}")
        st.session_state.pop("docs", None)
        st.rerun()

    st.divider()
    st.subheader("📄 已儲存的檔案")
    existing_files = list_pdfs()
    if not existing_files:
        st.info("目前沒有任何 PDF 檔案")
    else:
        for f in existing_files:
            col1, col2 = st.columns([4, 1])
            col1.write(f"📎 {f['name']}")
            if col2.button("🗑️", key=f"del_{f['name']}", help=f"刪除 {f['name']}"):
                delete_pdf(f["name"], GITHUB_TOKEN, GITHUB_REPO)
                st.success(f"已刪除：{f['name']}")
                st.session_state.pop("docs", None)
                st.rerun()
    st.stop()

# ==========================================
# 聊天模式
# ==========================================
st.title("🚌 中華基督教會基慈小學")
st.subheader("保母車查詢 Empowerd by Qwen AI")
st.caption("根據已上傳的保母車文件，使用 AI 回答查詢")

if not QWEN_API_KEY:
    st.info("👈 請在側邊欄輸入 Qwen API Key")
    st.stop()

# ---------- 載入文件 ----------
if "docs" not in st.session_state:
    with st.spinner("正在載入保母車文件..."):
        try:
            docs = load_all_docs()
            st.session_state["docs"] = docs
        except Exception as e:
            st.error(f"載入失敗：{e}")
            st.stop()

docs = st.session_state["docs"]

with st.sidebar:
    st.divider()
    st.subheader(f"📄 已載入 {len(docs)} 份文件")
    for d in docs:
        st.text(f"• {d['name']}")

if not docs:
    st.warning("目前沒有保母車文件，請管理員上傳 PDF。")
    st.stop()

# ---------- 對話介面 ----------
if "messages" not in st.session_state:
    st.session_state["messages"] = []

for msg in st.session_state["messages"]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt := st.chat_input("請輸入您的問題（例如：保母車幾點到校？哪條路線途經我的地區？）"):
    st.session_state["messages"].append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("思考中..."):
            try:
                client = OpenAI(api_key=QWEN_API_KEY, base_url=QWEN_BASE_URL)

                # 合併文件內容（控制 token 限制）
                parts = []
                total = 0
                max_chars = 60000
                for doc in docs:
                    header = f"===== 檔案：{doc['name']} =====\n"
                    content = doc["text"]
                    if total + len(header) + len(content) > max_chars:
                        remaining = max_chars - total - len(header)
                        if remaining > 200:
                            parts.append(header + content[:remaining] + "\n...(截斷)")
                        break
                    parts.append(header + content)
                    total += len(header) + len(content)
                context = "\n\n".join(parts)

                system_prompt = (
                    "你是一個專業的學校保母車助手。你的任務是根據提供的保母車路線表、時間表、通告及相關文件，"
                    "準確回答家長和老師的問題。\n\n"
                    "規則：\n"
                    "1. 只根據提供的文件內容回答，不要編造資訊\n"
                    "2. 如果文件中沒有相關資訊，請明確告知\n"
                    "3. 回答時引用具體的文件名稱、路線編號或時間\n"
                    "4. 使用繁體中文回答\n"
                    "5. 回答要清晰、有條理\n\n"
                    f"以下是保母車相關文件內容：\n\n{context}"
                )

                api_messages = [{"role": "system", "content": system_prompt}]
                api_messages.extend(st.session_state["messages"])

                response = client.chat.completions.create(
                    model=MODEL_NAME,
                    messages=api_messages,
                    temperature=0.3,
                    max_tokens=2000,
                )
                answer = response.choices[0].message.content
                st.markdown(answer)
                st.session_state["messages"].append({"role": "assistant", "content": answer})
            except Exception as e:
                error_msg = f"回覆失敗：{e}"
                st.error(error_msg)
                st.session_state["messages"].append({"role": "assistant", "content": error_msg})
