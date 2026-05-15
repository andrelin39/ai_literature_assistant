import streamlit as st


def init_session_state() -> None:
    defaults: dict = {
        "current_project_id": None,
        "search_results": [],
        "search_query": "",
        "search_strategy": "relevance",
        "selected_paper_indices": set(),
        "analysis_results": {},
        "comparison_result": None,
        "saved_paper_ids": {},
        "saved_project_paper_ids": {},
        "current_page": "🏠 首頁",
        "claude_model_choice": "default",
        "total_cost_usd": 0.0,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def clear_search_state() -> None:
    """Clear search results, analysis data, and related widget keys."""
    for k in list(st.session_state.keys()):
        if k.startswith("paper_chk_"):
            del st.session_state[k]
    st.session_state.search_results = []
    st.session_state.selected_paper_indices = set()
    st.session_state.analysis_results = {}
    st.session_state.comparison_result = None
    st.session_state.saved_paper_ids = {}
    st.session_state.saved_project_paper_ids = {}
