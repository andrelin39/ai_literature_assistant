import streamlit as st

from src.config import settings
from src.ui.state import clear_search_state


def render() -> None:
    st.title("⚙️ 設定")

    # ── Claude model ──────────────────────────────────────────────────────────
    st.subheader("Claude 模型")
    model_choice = st.radio(
        "選擇分析模型",
        options=["default", "advanced"],
        format_func=lambda x: (
            f"預設（{settings.claude_model_default}）" if x == "default"
            else f"進階（{settings.claude_model_advanced}）"
        ),
        index=0 if st.session_state.get("claude_model_choice", "default") == "default" else 1,
        key="settings_model_radio",
    )
    if model_choice != st.session_state.get("claude_model_choice"):
        st.session_state.claude_model_choice = model_choice

    st.caption(
        "預設（Sonnet）成本約 $0.018/篇；進階（Opus）約 $0.09/篇，品質更高但費用較貴。"
    )

    st.divider()

    # ── Search defaults ───────────────────────────────────────────────────────
    st.subheader("搜尋預設值")
    st.info("這些設定影響搜尋頁面的初始值，可在搜尋時隨時覆蓋。")

    default_strategy = st.selectbox(
        "預設搜尋策略",
        options=["relevance", "recent", "highly_cited", "review"],
        index=["relevance", "recent", "highly_cited", "review"].index(
            st.session_state.get("default_search_strategy", "relevance")
        ),
        key="settings_strategy",
    )
    st.session_state.default_search_strategy = default_strategy

    default_limit = st.number_input(
        "預設結果數量",
        min_value=3,
        max_value=10,
        value=st.session_state.get("default_search_limit", 5),
        key="settings_limit",
    )
    st.session_state.default_search_limit = int(default_limit)

    st.divider()

    # ── Danger zone ───────────────────────────────────────────────────────────
    with st.expander("🔴 危險區", expanded=False):
        st.warning("以下操作不可還原（僅影響目前 session，不刪除資料庫資料）。")
        if st.button("重置 session state（清空搜尋與分析結果）", type="secondary"):
            clear_search_state()
            st.session_state.comparison_result = None
            st.success("Session state 已重置。")
            st.rerun()
