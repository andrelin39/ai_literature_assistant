import streamlit as st

st.set_page_config(page_title="AI 文獻助理", page_icon="📚", layout="wide")

from src.storage import crud, get_session, init_db
from src.ui import state
from src.ui import home_page, library_page, projects_page, search_page, settings_page

init_db()
state.init_session_state()

_PAGES = [
    "🏠 首頁",
    "🔍 搜尋文獻",
    "📚 文獻庫管理",
    "📋 專案管理",
    "✍️ 評估引用（Phase 2）",
    "⚙️ 設定",
]

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("📚 AI 文獻助理")

    with get_session() as session:
        projects = crud.list_projects(session)

    if not projects:
        st.warning("尚未建立專案，請先建立")
        if st.session_state.current_page not in ("📋 專案管理", "⚙️ 設定", "🏠 首頁"):
            st.session_state.current_page = "📋 專案管理"
    else:
        project_options = {p.id: p.name for p in projects}
        if st.session_state.current_project_id not in project_options:
            st.session_state.current_project_id = list(project_options.keys())[0]

        selected_id = st.selectbox(
            "當前專案",
            options=list(project_options.keys()),
            format_func=lambda x: project_options[x],
            index=list(project_options.keys()).index(st.session_state.current_project_id),
        )
        if selected_id != st.session_state.current_project_id:
            st.session_state.current_project_id = selected_id
            state.clear_search_state()
            st.rerun()

    st.divider()

    current_idx = _PAGES.index(st.session_state.current_page) if st.session_state.current_page in _PAGES else 0
    page = st.radio("頁面", options=_PAGES, index=current_idx, label_visibility="collapsed")
    st.session_state.current_page = page

    if st.session_state.get("total_cost_usd", 0) > 0:
        st.divider()
        st.caption(f"Session 估算成本：${st.session_state.total_cost_usd:.4f} USD")

# ── Main routing ──────────────────────────────────────────────────────────────
if page == "🏠 首頁":
    home_page.render()
elif page == "🔍 搜尋文獻":
    search_page.render()
elif page == "📚 文獻庫管理":
    library_page.render()
elif page == "📋 專案管理":
    projects_page.render()
elif page == "✍️ 評估引用（Phase 2）":
    st.info("🚧 此功能將於 Phase 2 實作")
elif page == "⚙️ 設定":
    settings_page.render()
