import streamlit as st

st.set_page_config(
    page_title="AI 文獻助理",
    page_icon="📚",
    layout="wide",
)

PAGES = {
    "🏠 首頁": "home",
    "🔍 搜尋文獻": "search",
    "📖 文獻庫": "library",
    "⭐ 評估引用": "evaluate",
    "⚙️ 設定": "settings",
}

with st.sidebar:
    st.title("📚 AI 文獻助理")
    st.divider()
    selected = st.radio("導覽", list(PAGES.keys()), label_visibility="collapsed")

page = PAGES[selected]

if page == "home":
    st.title("AI 學術文獻助理")
    st.markdown(
        """
        歡迎使用 AI 文獻助理，協助您完成系統性文獻回顧流程。

        **主要功能：**
        - **搜尋文獻**：整合 Semantic Scholar、PubMed、Crossref 等資料庫
        - **文獻庫**：管理已收集的文獻，支援篩選與標記
        - **評估引用**：透過 Claude AI 協助評估文獻相關性與品質
        - **匯出報告**：產生 PRISMA 流程圖與參考文獻清單

        從左側選單開始使用。
        """
    )

elif page == "search":
    st.title("搜尋文獻")
    st.info("搜尋模組開發中。")

elif page == "library":
    st.title("文獻庫")
    st.info("文獻庫模組開發中。")

elif page == "evaluate":
    st.title("評估引用")
    st.info("評估模組開發中。")

elif page == "settings":
    st.title("設定")
    st.info("設定模組開發中。")
