"""Shared UI components for all pages."""
from __future__ import annotations

import streamlit as st

from src.analysis.schemas import (
    ComparisonAnalysis,
    GroundedField,
    InferredField,
    PaperAnalysis,
)
from src.storage.schemas import PaperCreate


# ── Pure helpers (unit-testable) ──────────────────────────────────────────────

def estimate_analysis_cost(n_papers: int) -> float:
    """Estimate USD cost for analyzing n papers + one comparison call."""
    return round(n_papers * 0.018 + 0.06, 4)


def fmt_authors(authors: list, max_shown: int = 3) -> str:
    names = [a.get("name", "") if isinstance(a, dict) else getattr(a, "name", "") for a in authors]
    names = [n for n in names if n]
    if not names:
        return "Unknown"
    shown = names[:max_shown]
    result = ", ".join(shown)
    if len(names) > max_shown:
        result += " et al."
    return result


# ── Badge renderers ───────────────────────────────────────────────────────────

def grounded_badge(label: str, field: GroundedField) -> None:
    if field.confidence == "not_found" or field.value is None:
        not_found_badge(label)
        return
    icon = "🟢" if field.confidence == "grounded" else "🟡"
    value_str = str(field.value) if not isinstance(field.value, dict) else _study_design_str(field.value)
    with st.container():
        header = f"{icon} **{label}**：{value_str}"
        if field.evidence:
            with st.expander(header):
                st.caption(f"> {field.evidence.text}")
        else:
            st.markdown(header)


def inferred_badge(label: str, field: InferredField) -> None:
    icon_map = {"high": "🟠", "medium": "🟡", "low": "⚪"}
    icon = icon_map.get(field.confidence, "🟡")
    value_str = str(field.value)
    with st.expander(f"{icon} **{label}**：{value_str}"):
        st.caption(f"*推論依據：{field.reasoning}*")


def not_found_badge(field_name: str) -> None:
    st.caption(f"⚫ *abstract 未提及 {field_name}*")


def _study_design_str(sd) -> str:
    if isinstance(sd, dict):
        parts = []
        if sd.get("type"):
            parts.append(sd["type"])
        if sd.get("sample_size"):
            parts.append(f"n={sd['sample_size']}")
        if sd.get("population"):
            parts.append(sd["population"])
        return "；".join(parts) if parts else "（未提及）"
    return str(sd)


# ── Confirm dialog ────────────────────────────────────────────────────────────

@st.dialog("確認操作", width="small")
def _confirm_dialog_modal() -> None:
    cfg = st.session_state.get("_confirm_cfg", {})
    st.write(cfg.get("message", "確定要執行此操作嗎？"))
    c1, c2 = st.columns(2)
    if c1.button("確認", type="primary", key="_cyes"):
        st.session_state["_confirm_result"] = cfg.get("key")
        st.rerun()
    if c2.button("取消", key="_cno"):
        st.session_state["_confirm_result"] = None
        st.rerun()


def open_confirm_dialog(message: str, key: str) -> None:
    """Call this when a delete/dangerous button is clicked."""
    st.session_state["_confirm_cfg"] = {"message": message, "key": key}
    st.session_state["_confirm_open"] = True


def consume_confirm_result(key: str) -> bool:
    """Returns True once if the dialog was confirmed for this key."""
    if st.session_state.get("_confirm_open", False):
        _confirm_dialog_modal()
        st.session_state["_confirm_open"] = False

    result = st.session_state.get("_confirm_result")
    if result == key:
        st.session_state["_confirm_result"] = None
        return True
    return False


# ── Guard helper ──────────────────────────────────────────────────────────────

def require_project() -> int:
    """Stop rendering if no project is selected. Returns project_id."""
    pid = st.session_state.get("current_project_id")
    if not pid:
        st.warning("⚠️ 請先在左側選擇或建立一個專案")
        st.stop()
    return pid


# ── Paper cards ───────────────────────────────────────────────────────────────

def paper_card_metadata(paper: PaperCreate, idx: int, show_checkbox: bool = True) -> None:
    has_abstract = bool(paper.abstract and len(paper.abstract.strip()) >= 50)

    with st.container(border=True):
        header_cols = st.columns([0.05, 0.95]) if show_checkbox else [None]

        if show_checkbox:
            with header_cols[0]:
                is_checked = st.checkbox(
                    "選取",
                    value=idx in st.session_state.selected_paper_indices,
                    key=f"paper_chk_{idx}",
                    disabled=not has_abstract,
                    label_visibility="collapsed",
                )
                if has_abstract:
                    if is_checked:
                        st.session_state.selected_paper_indices.add(idx)
                    else:
                        st.session_state.selected_paper_indices.discard(idx)
            title_col = header_cols[1]
        else:
            title_col = st.container()

        with title_col:
            title = paper.title or "(無標題)"
            if paper.url:
                st.markdown(f"**[{title}]({paper.url})**")
            else:
                st.markdown(f"**{title}**")

        meta_parts: list[str] = []
        if paper.authors:
            meta_parts.append(fmt_authors(paper.authors))
        if paper.year:
            meta_parts.append(str(paper.year))
        if paper.venue:
            meta_parts.append(paper.venue)
        st.caption(" | ".join(meta_parts))

        if paper.doi:
            st.caption(f"DOI: [{paper.doi}](https://doi.org/{paper.doi})")

        if paper.abstract:
            with st.expander("摘要", expanded=False):
                st.write(paper.abstract)
        elif not has_abstract:
            st.warning("⚠️ 無 abstract，無法深度分析", icon="⚠️")

        stat_cols = st.columns(3)
        if paper.citation_count is not None:
            stat_cols[0].metric("被引用", paper.citation_count)


def paper_card_analysis(paper: PaperCreate, analysis: PaperAnalysis, idx: int) -> None:
    from src.storage import crud, get_session
    from src.storage.schemas import ProjectPaperCreate

    already_saved = idx in st.session_state.saved_project_paper_ids

    with st.container(border=True):
        title = paper.title or "(無標題)"
        if paper.url:
            st.markdown(f"### [{title}]({paper.url})")
        else:
            st.markdown(f"### {title}")

        meta_parts = []
        if paper.authors:
            meta_parts.append(fmt_authors(paper.authors))
        if paper.year:
            meta_parts.append(str(paper.year))
        if paper.venue:
            meta_parts.append(paper.venue)
        st.caption(" | ".join(meta_parts))

        st.divider()
        col_left, col_right = st.columns(2)

        with col_left:
            st.markdown("**Grounded 事實**")
            grounded_badge("研究問題", analysis.research_question)

            if analysis.study_design.value:
                sd = analysis.study_design.value
                sd_dict = sd.model_dump() if hasattr(sd, "model_dump") else sd
                from src.analysis.schemas import GroundedField as GF
                dummy = GF(
                    value=sd_dict,
                    evidence=analysis.study_design.evidence,
                    confidence=analysis.study_design.confidence,
                )
                grounded_badge("研究設計", dummy)
            else:
                not_found_badge("研究設計")

            if analysis.key_findings:
                st.markdown("**主要發現**")
                for kf in analysis.key_findings:
                    with st.expander(f"• {kf.statement}"):
                        st.caption(f"> {kf.evidence.text}")

        with col_right:
            st.markdown("**Inferred 推論**")
            inferred_badge("為何相關", analysis.why_relevant)
            if analysis.limitations_or_gaps:
                inferred_badge("研究限制", analysis.limitations_or_gaps)

            if analysis.citation_contexts:
                st.markdown("**引用情境**")
                ctx_type_labels = {
                    "background": "背景",
                    "method": "方法",
                    "comparison": "比較",
                    "support": "支持",
                    "contrast": "對比",
                    "gap": "研究缺口",
                }
                for ctx in analysis.citation_contexts:
                    label = ctx_type_labels.get(ctx.context_type, ctx.context_type)
                    with st.expander(f"[{label}] {ctx.description}"):
                        st.info(f'"{ctx.example_sentence}"')

        st.divider()
        btn_cols = st.columns([2, 2, 3])

        if already_saved:
            btn_cols[0].success("✅ 已加入專案")
        else:
            if btn_cols[0].button("✅ 確認加入專案", key=f"add_{idx}", type="primary"):
                project_id = st.session_state.get("current_project_id")
                if not project_id:
                    st.error("請先選擇專案")
                    return
                with get_session() as session:
                    db_paper = crud.upsert_paper(session, paper)
                    session.flush()
                    db_id = db_paper.id
                    pp_data = ProjectPaperCreate(
                        status="confirmed",
                        key_points=[kf.statement for kf in analysis.key_findings],
                        why_cite=analysis.why_relevant.value if analysis.why_relevant else None,
                        how_to_cite=(
                            "; ".join(ctx.example_sentence for ctx in analysis.citation_contexts)
                            if analysis.citation_contexts else None
                        ),
                        relevance_to_project=(
                            analysis.why_relevant.reasoning if analysis.why_relevant else None
                        ),
                    )
                    crud.add_paper_to_project(session, project_id, db_id, pp_data)
                    crud.confirm_paper(session, project_id, db_id)
                    session.commit()
                st.session_state.saved_project_paper_ids[idx] = db_id
                st.rerun()

        if btn_cols[1].button("❌ 不採用", key=f"rej_{idx}", disabled=already_saved):
            st.session_state.analysis_results.pop(idx, None)
            st.session_state.selected_paper_indices.discard(idx)
            st.session_state[f"paper_chk_{idx}"] = False
            st.rerun()

        with btn_cols[2]:
            with st.expander("📝 我的註記"):
                st.text_area("", key=f"note_{idx}", label_visibility="collapsed", height=80)


# ── Comparison panel ──────────────────────────────────────────────────────────

def comparison_panel(comparison: ComparisonAnalysis, papers: list[PaperCreate]) -> None:
    st.subheader("📊 跨文獻比較分析")

    cols = st.columns(3)
    with cols[0]:
        st.markdown("**共通主題**")
        for theme in comparison.common_themes:
            st.markdown(f"• {theme}")

    with cols[1]:
        st.markdown("**對立觀點**")
        if comparison.contrasts:
            for c in comparison.contrasts:
                st.markdown(f"• {c}")
        else:
            st.caption("無明顯對立")

    with cols[2]:
        st.markdown("**研究缺口**")
        for gap in comparison.research_gaps:
            st.markdown(f"• {gap}")

    st.markdown("**綜述建議**")
    st.info(comparison.suggested_synthesis)

    if comparison.cross_relations:
        st.markdown("**文獻關聯**")
        rel_type_labels = {
            "similar_topic": "相似主題",
            "opposing_view": "觀點對立",
            "methodological_parallel": "方法相似",
            "extends": "延伸研究",
            "contradicted_by": "被反駁",
        }
        for rel in comparison.cross_relations:
            target_idx = rel.target_paper_index
            target_title = papers[target_idx].title if target_idx < len(papers) else f"文獻 #{target_idx}"
            label = rel_type_labels.get(rel.relation_type, rel.relation_type)
            st.caption(f"[{label}] → 《{target_title}》：{rel.description}")
