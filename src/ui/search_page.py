import streamlit as st

from src.analysis import ClaudeAnalysisClient, PaperComparator, PaperExtractor
from src.analysis.exceptions import EmptyAbstractError
from src.config import settings
from src.search import SearchFilters, SemanticScholarClient
from src.storage import crud, get_session
from src.storage.schemas import ProjectPaperCreate
from src.ui.components import (
    comparison_panel,
    estimate_analysis_cost,
    paper_card_analysis,
    paper_card_metadata,
    require_project,
)
from src.ui.state import clear_search_state


_PUB_TYPE_OPTIONS = ["journal", "review", "conference", "preprint"]
_STRATEGY_LABELS = {
    "relevance": "相關性優先",
    "recent": "最新發表",
    "highly_cited": "高引用數",
    "review": "僅回顧文章",
}


def _get_extractor() -> PaperExtractor:
    model = (
        settings.claude_model_advanced
        if st.session_state.get("claude_model_choice") == "advanced"
        else settings.claude_model_default
    )
    return PaperExtractor(client=ClaudeAnalysisClient(model=model))


def _get_comparator() -> PaperComparator:
    model = (
        settings.claude_model_advanced
        if st.session_state.get("claude_model_choice") == "advanced"
        else settings.claude_model_default
    )
    return PaperComparator(client=ClaudeAnalysisClient(model=model))


def render() -> None:
    project_id = require_project()

    with get_session() as session:
        proj = crud.get_project(session, project_id)
        proj_name = proj.name if proj else "（未知）"
        proj_rq = proj.research_question if proj else ""

    st.title("🔍 搜尋文獻")
    st.caption(
        f"目前專案：**{proj_name}**" + (f" — {proj_rq}" if proj_rq else "")
    )

    # ── A. Search form ────────────────────────────────────────────────────────
    with st.form("search_form"):
        query = st.text_area(
            "研究主題或關鍵字",
            value=st.session_state.get("search_query", ""),
            height=80,
            placeholder="例：nursing burnout COVID-19 Taiwan",
        )
        col_l, col_r = st.columns(2)
        with col_l:
            strategy = st.selectbox(
                "搜尋策略",
                options=list(_STRATEGY_LABELS.keys()),
                format_func=lambda x: _STRATEGY_LABELS[x],
                index=list(_STRATEGY_LABELS.keys()).index(
                    st.session_state.get("search_strategy", "relevance")
                ),
                help="relevance=語意相關；recent=近 3 年新文獻；highly_cited=高引用；review=僅系統回顧",
            )
        with col_r:
            limit = st.number_input(
                "結果數量",
                min_value=3,
                max_value=10,
                value=st.session_state.get("default_search_limit", 5),
            )

        with st.expander("進階篩選"):
            fc1, fc2 = st.columns(2)
            with fc1:
                year_from = st.number_input("發表年份（從）", min_value=1990, max_value=2026, value=2015, step=1)
                year_to = st.number_input("發表年份（至）", min_value=1990, max_value=2026, value=2026, step=1)
            with fc2:
                pub_types = st.multiselect(
                    "文獻類型",
                    options=_PUB_TYPE_OPTIONS,
                    default=[],
                    format_func=lambda x: {
                        "journal": "期刊文章", "review": "系統回顧",
                        "conference": "研討會", "preprint": "預印本",
                    }.get(x, x),
                )
                min_cit = st.number_input("最低被引次數", min_value=0, value=0, step=5)
                oa_only = st.checkbox("僅 Open Access")

        search_submitted = st.form_submit_button("🔍 搜尋（免費）", type="primary", use_container_width=True)

    if search_submitted and query.strip():
        clear_search_state()
        st.session_state.search_query = query.strip()
        st.session_state.search_strategy = strategy

        with st.spinner("正在搜尋 Semantic Scholar..."):
            try:
                client = SemanticScholarClient()
                results = client.search(
                    query=query.strip(),
                    limit=int(limit),
                    filters=SearchFilters(
                        year_from=int(year_from) if year_from else None,
                        year_to=int(year_to) if year_to else None,
                        publication_types=pub_types or None,
                        min_citation_count=int(min_cit) if min_cit > 0 else None,
                        open_access_only=oa_only,
                    ),
                    strategy=strategy,
                )
                st.session_state.search_results = results
            except Exception as e:
                st.error(f"搜尋失敗：{e}")
                results = []

        if not results:
            st.info("無相符文獻，請調整關鍵字或搜尋策略。")
        else:
            st.rerun()

    elif search_submitted and not query.strip():
        st.warning("請輸入搜尋關鍵字。")

    # ── B. Search results ──────────────────────────────────────────────────────
    results = st.session_state.get("search_results", [])
    if not results:
        return

    has_abstract_count = sum(
        1 for p in results if p.abstract and len(p.abstract.strip()) >= 50
    )
    st.subheader(
        f"找到 {len(results)} 篇文獻（其中 {has_abstract_count} 篇有 abstract 可分析）"
    )

    btn_c1, btn_c2 = st.columns(2)
    if btn_c1.button("全選"):
        for i, p in enumerate(results):
            if p.abstract and len(p.abstract.strip()) >= 50:
                st.session_state.selected_paper_indices.add(i)
                st.session_state[f"paper_chk_{i}"] = True
        st.rerun()
    if btn_c2.button("全不選"):
        st.session_state.selected_paper_indices.clear()
        for i in range(len(results)):
            st.session_state[f"paper_chk_{i}"] = False
        st.rerun()

    for idx, paper in enumerate(results):
        paper_card_metadata(paper, idx)

    # ── C. Analysis trigger ───────────────────────────────────────────────────
    selected = sorted(st.session_state.selected_paper_indices)
    n_selected = len(selected)

    if n_selected >= 2:
        st.divider()
        cost_est = estimate_analysis_cost(n_selected)

        info_c1, info_c2 = st.columns([2, 3])
        info_c1.metric("已選篇數", n_selected)
        info_c2.markdown(
            f"**預估費用**：{n_selected} × $0.018（單篇）+ $0.06（比較）≈ **${cost_est:.3f}**"
        )

        analyze_clicked = st.button(
            f"⚡ 分析選取的 {n_selected} 篇（預估 ${cost_est:.3f}）",
            type="primary",
            use_container_width=True,
        )

        if analyze_clicked:
            _run_analysis(selected, st.session_state.search_query)
    elif 0 < n_selected < 2:
        st.info("請至少選取 2 篇才能執行跨文獻比較分析。")

    # ── D. Analysis results ────────────────────────────────────────────────────
    analysis_results = st.session_state.get("analysis_results", {})
    comparison = st.session_state.get("comparison_result")

    if analysis_results:
        st.divider()
        st.subheader("📊 分析結果")

        analyzed_papers = [results[i] for i in sorted(analysis_results.keys()) if i < len(results)]
        analyzed_list = [analysis_results[i] for i in sorted(analysis_results.keys()) if i < len(results)]

        if comparison and len(analyzed_papers) >= 2:
            comparison_panel(comparison, analyzed_papers)
            st.divider()

        for i in sorted(analysis_results.keys()):
            if i < len(results):
                paper_card_analysis(results[i], analysis_results[i], i)


def _run_analysis(selected_indices: list[int], query: str) -> None:
    results = st.session_state.search_results
    n = len(selected_indices)

    progress = st.progress(0, text="準備分析...")
    status_placeholder = st.empty()

    extractor = _get_extractor()
    analyses = []
    analyzed_papers = []

    for i, idx in enumerate(selected_indices):
        paper = results[idx]
        short_title = (paper.title or "")[:45]
        progress.progress(i / n, text=f"分析第 {i + 1}/{n} 篇：{short_title}...")
        status_placeholder.info(f"🔬 正在分析：《{short_title}》")

        try:
            analysis, usage = extractor.analyze(paper, user_topic=query)
            st.session_state.analysis_results[idx] = analysis
            st.session_state.total_cost_usd += usage.get("estimated_cost_usd", 0)
            analyses.append(analysis)
            analyzed_papers.append(paper)
        except EmptyAbstractError:
            st.warning(f"第 {i + 1} 篇《{short_title}》無 abstract，已跳過。")
        except Exception as e:
            st.error(f"第 {i + 1} 篇《{short_title}》分析失敗：{e}")

    if len(analyses) >= 2:
        progress.progress(0.95, text="進行跨文獻比較分析...")
        status_placeholder.info("🔗 正在比較文獻...")
        try:
            comparator = _get_comparator()
            comparison, comp_usage = comparator.compare(analyzed_papers, analyses, user_topic=query)
            st.session_state.comparison_result = comparison
            st.session_state.total_cost_usd += comp_usage.get("estimated_cost_usd", 0)
        except Exception as e:
            st.error(f"跨文獻比較失敗：{e}")
    elif len(analyses) == 1:
        st.info("只有 1 篇成功分析，跨文獻比較需至少 2 篇。")

    progress.progress(1.0, text="✅ 分析完成！")
    status_placeholder.empty()
    st.rerun()
