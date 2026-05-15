import streamlit as st

from src.storage import crud, get_session
from src.storage.schemas import ProjectCreate, ProjectUpdate
from src.ui.components import consume_confirm_result, open_confirm_dialog


def render() -> None:
    st.title("📋 專案管理")

    # ── Handle delete confirmation result ─────────────────────────────────────
    target_id = st.session_state.get("_del_project_id")
    if target_id and consume_confirm_result(f"del_proj_{target_id}"):
        with get_session() as session:
            crud.delete_project(session, target_id)
            session.commit()
        if st.session_state.get("current_project_id") == target_id:
            st.session_state.current_project_id = None
        st.session_state.pop("_del_project_id", None)
        st.success("專案已刪除")
        st.rerun()

    # ── Project list ──────────────────────────────────────────────────────────
    with get_session() as session:
        projects = crud.list_projects(session)
        counts = {p.id: crud.count_project_papers(session, p.id) for p in projects}

    if projects:
        st.subheader(f"所有專案（共 {len(projects)} 個）")
        for proj in projects:
            _project_row(proj, counts.get(proj.id, 0))
    else:
        st.info("尚未建立任何專案。請使用下方表單建立第一個專案。")

    st.divider()

    # ── Create form ───────────────────────────────────────────────────────────
    st.subheader("建立新專案")
    with st.form("create_project_form", clear_on_submit=True):
        name = st.text_input("專案名稱 *", placeholder="例：護理職場壓力文獻回顧 2025")
        description = st.text_area("描述（選填）", height=80)
        rq = st.text_area("研究問題（選填）", placeholder="例：COVID-19 對護理師職業倦怠的影響為何？", height=80)
        submitted = st.form_submit_button("➕ 建立專案", type="primary")

    if submitted:
        if not name.strip():
            st.error("專案名稱為必填欄位。")
        else:
            with get_session() as session:
                existing = crud.get_project_by_name(session, name.strip())
                if existing:
                    st.error(f"已存在同名專案「{name}」，請使用不同名稱。")
                else:
                    proj = crud.create_project(
                        session,
                        ProjectCreate(
                            name=name.strip(),
                            description=description.strip() or None,
                            research_question=rq.strip() or None,
                        ),
                    )
                    session.commit()
                    st.session_state.current_project_id = proj.id
            st.success(f"專案「{name}」已建立！")
            st.rerun()


def _project_row(proj, papers_count: int) -> None:
    edit_key = f"_edit_proj_{proj.id}"
    is_editing = st.session_state.get(edit_key, False)
    is_current = st.session_state.get("current_project_id") == proj.id

    border_color = "blue" if is_current else None
    with st.container(border=True):
        header_cols = st.columns([4, 1, 1, 1])
        with header_cols[0]:
            label = f"{'🔵 ' if is_current else ''}**{proj.name}**"
            st.markdown(label)
            if proj.research_question:
                st.caption(proj.research_question[:100])
            st.caption(f"文獻數：{papers_count}　｜　更新：{proj.updated_at.strftime('%Y-%m-%d') if proj.updated_at else 'N/A'}")

        with header_cols[1]:
            if not is_current:
                if st.button("選取", key=f"sel_{proj.id}", use_container_width=True):
                    st.session_state.current_project_id = proj.id
                    st.session_state.current_page = "🔍 搜尋文獻"
                    st.rerun()
            else:
                st.caption("（當前）")

        with header_cols[2]:
            if st.button("✏️ 編輯", key=f"edit_{proj.id}", use_container_width=True):
                st.session_state[edit_key] = not is_editing
                st.rerun()

        with header_cols[3]:
            if st.button("🗑️ 刪除", key=f"del_{proj.id}", use_container_width=True, type="secondary"):
                st.session_state["_del_project_id"] = proj.id
                open_confirm_dialog(
                    f"確定要刪除專案「{proj.name}」嗎？所有關聯文獻記錄將一同刪除，此操作無法還原。",
                    key=f"del_proj_{proj.id}",
                )
                st.rerun()

        if is_editing:
            with st.form(f"edit_form_{proj.id}"):
                new_name = st.text_input("名稱", value=proj.name)
                new_desc = st.text_area("描述", value=proj.description or "", height=70)
                new_rq = st.text_area("研究問題", value=proj.research_question or "", height=70)
                save = st.form_submit_button("💾 儲存", type="primary")
            if save:
                with get_session() as session:
                    crud.update_project(
                        session,
                        proj.id,
                        ProjectUpdate(
                            name=new_name.strip() or proj.name,
                            description=new_desc.strip() or None,
                            research_question=new_rq.strip() or None,
                        ),
                    )
                    session.commit()
                st.session_state[edit_key] = False
                st.rerun()
