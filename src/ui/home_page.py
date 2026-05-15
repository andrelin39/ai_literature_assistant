import streamlit as st

from src.storage import crud, get_session


def render() -> None:
    st.title("📚 AI 文獻助理")
    st.markdown("協助系統性文獻回顧的端到端工具：搜尋 → 分析 → 管理。")

    with get_session() as session:
        n_projects = crud.count_all_projects(session)
        n_papers = crud.count_all_papers(session)
        n_this_month = crud.count_papers_this_month(session)
        recent = crud.get_recent_projects(session, limit=5)
        recent_data = [
            {
                "名稱": p.name,
                "研究問題": (p.research_question or "")[:60],
                "更新時間": p.updated_at.strftime("%Y-%m-%d") if p.updated_at else "",
                "_id": p.id,
            }
            for p in recent
        ]

    m1, m2, m3 = st.columns(3)
    m1.metric("總專案數", n_projects)
    m2.metric("總文獻數", n_papers)
    m3.metric("本月新增文獻", n_this_month)

    st.divider()

    col_left, col_right = st.columns([3, 2])

    with col_left:
        st.subheader("最近專案")
        if recent_data:
            display = [{k: v for k, v in d.items() if k != "_id"} for d in recent_data]
            st.dataframe(display, use_container_width=True, hide_index=True)
        else:
            st.info("尚未建立任何專案。")

    with col_right:
        st.subheader("快速開始")
        st.markdown(
            """
            1. 在左側建立或選擇專案
            2. 前往「搜尋文獻」輸入關鍵字
            3. 勾選文獻後點「分析」
            4. 確認加入文獻庫
            """
        )
        if st.button("🔍 開始搜尋", type="primary", use_container_width=True):
            st.session_state.current_page = "🔍 搜尋文獻"
            st.rerun()
        if st.button("📋 管理專案", use_container_width=True):
            st.session_state.current_page = "📋 專案管理"
            st.rerun()

    if st.session_state.get("total_cost_usd", 0) > 0:
        st.caption(
            f"本次 session 估算 Claude API 成本：${st.session_state.total_cost_usd:.4f} USD"
        )
