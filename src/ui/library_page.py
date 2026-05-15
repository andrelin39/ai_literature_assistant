import streamlit as st

from src.storage import crud, get_session
from src.storage.schemas import ProjectPaperUpdate
from src.ui.components import consume_confirm_result, open_confirm_dialog, require_project


_STATUS_LABELS = {"confirmed": "✅ 已確認", "suggested": "🔵 待決定", "rejected": "❌ 已拒絕"}
_SORT_OPTIONS = {
    "加入時間（最新）": ("added_at", True),
    "加入時間（最舊）": ("added_at", False),
    "發表年份（新→舊）": ("year", True),
    "被引用數（高→低）": ("citation_count", True),
    "標題（A-Z）": ("title", False),
}


def render() -> None:
    project_id = require_project()

    with get_session() as session:
        proj = crud.get_project(session, project_id)
        proj_name = proj.name if proj else "（未知專案）"
        proj_rq = proj.research_question if proj else ""

    st.title("📚 文獻庫管理")
    st.caption(f"當前專案：**{proj_name}**" + (f" — {proj_rq}" if proj_rq else ""))

    # ── Handle remove confirmation ─────────────────────────────────────────────
    del_key = st.session_state.get("_del_pp_key")
    if del_key and consume_confirm_result(del_key):
        pid, ppid = st.session_state.pop("_del_pp_ids", (None, None))
        if pid and ppid:
            with get_session() as session:
                crud.remove_paper_from_project(session, pid, ppid)
                session.commit()
        st.session_state.pop("_del_pp_key", None)
        st.success("已從專案移除")
        st.rerun()

    # ── Stats ─────────────────────────────────────────────────────────────────
    with get_session() as session:
        total = crud.count_project_papers(session, project_id)
        confirmed = crud.count_project_papers(session, project_id, status="confirmed")
        suggested = crud.count_project_papers(session, project_id, status="suggested")
        rejected = crud.count_project_papers(session, project_id, status="rejected")
        all_tags = crud.get_distinct_tags(session, project_id)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("總文獻數", total)
    m2.metric("✅ 已確認", confirmed)
    m3.metric("🔵 待決定", suggested)
    m4.metric("❌ 已拒絕", rejected)

    if total == 0:
        st.info("尚未加入任何文獻。請前往「搜尋文獻」頁面開始。")
        if st.button("🔍 前往搜尋"):
            st.session_state.current_page = "🔍 搜尋文獻"
            st.rerun()
        return

    st.divider()

    # ── Filters ───────────────────────────────────────────────────────────────
    f1, f2, f3 = st.columns([2, 3, 2])
    with f1:
        status_filter = st.selectbox(
            "狀態篩選",
            options=["全部", "已確認", "待決定", "已拒絕"],
            index=0,
        )
    with f2:
        tag_filter = st.multiselect("標籤篩選", options=all_tags) if all_tags else []
    with f3:
        sort_key_label = st.selectbox("排序", options=list(_SORT_OPTIONS.keys()))

    status_map = {"全部": None, "已確認": "confirmed", "待決定": "suggested", "已拒絕": "rejected"}
    sort_by, sort_desc = _SORT_OPTIONS[sort_key_label]

    # ── Load data ─────────────────────────────────────────────────────────────
    with get_session() as session:
        pps = crud.list_project_papers_with_filters(
            session,
            project_id,
            status=status_map[status_filter],
            tags=tag_filter or None,
            sort_by=sort_by,
            sort_desc=sort_desc,
        )
        pp_data = [_pp_to_dict(pp) for pp in pps]

    if not pp_data:
        st.info("沒有符合條件的文獻。")
        return

    st.caption(f"顯示 {len(pp_data)} 筆")

    # ── List ──────────────────────────────────────────────────────────────────
    for item in pp_data:
        _paper_row(item, project_id, all_tags)


def _pp_to_dict(pp) -> dict:
    return {
        "id": pp.id,
        "paper_id": pp.paper_id,
        "status": pp.status,
        "key_points": pp.key_points or [],
        "why_cite": pp.why_cite,
        "how_to_cite": pp.how_to_cite,
        "relevance_to_project": pp.relevance_to_project,
        "tags": pp.tags or [],
        "user_notes": pp.user_notes or "",
        "added_at": pp.added_at,
        "updated_at": pp.updated_at,
        "paper_title": pp.paper.title if pp.paper else "",
        "paper_authors": pp.paper.authors if pp.paper else [],
        "paper_year": pp.paper.year if pp.paper else None,
        "paper_venue": pp.paper.venue if pp.paper else "",
        "paper_doi": pp.paper.doi if pp.paper else None,
        "paper_citation_count": pp.paper.citation_count if pp.paper else None,
        "paper_abstract": pp.paper.abstract if pp.paper else None,
        "paper_url": pp.paper.url if pp.paper else None,
    }


def _paper_row(item: dict, project_id: int, all_tags: list[str]) -> None:
    pp_id = item["id"]
    edit_key = f"_lib_edit_{pp_id}"
    is_editing = st.session_state.get(edit_key, False)

    status_label = _STATUS_LABELS.get(item["status"], item["status"])

    with st.container(border=True):
        h1, h2, h3 = st.columns([5, 1, 1])
        with h1:
            title = item["paper_title"] or "(無標題)"
            if item["paper_url"]:
                st.markdown(f"**[{title}]({item['paper_url']})**")
            else:
                st.markdown(f"**{title}**")
            meta_parts = []
            if item["paper_authors"]:
                from src.ui.components import fmt_authors
                meta_parts.append(fmt_authors(item["paper_authors"]))
            if item["paper_year"]:
                meta_parts.append(str(item["paper_year"]))
            if item["paper_venue"]:
                meta_parts.append(item["paper_venue"])
            st.caption(" | ".join(meta_parts) + f"   {status_label}")
            if item["paper_doi"]:
                st.caption(f"DOI: [{item['paper_doi']}](https://doi.org/{item['paper_doi']})")

        with h2:
            if st.button("✏️ 編輯", key=f"lib_edit_btn_{pp_id}", use_container_width=True):
                st.session_state[edit_key] = not is_editing
                st.rerun()

        with h3:
            if st.button("🗑️ 移除", key=f"lib_del_btn_{pp_id}", use_container_width=True):
                del_key = f"rm_pp_{pp_id}"
                st.session_state["_del_pp_key"] = del_key
                st.session_state["_del_pp_ids"] = (project_id, item["paper_id"])
                open_confirm_dialog(
                    f"確定要從專案移除《{item['paper_title'][:40]}》嗎？",
                    key=del_key,
                )
                st.rerun()

        if not is_editing:
            # Read-only summary
            if item["key_points"]:
                with st.expander("重點摘要", expanded=False):
                    for kp in item["key_points"]:
                        st.markdown(f"• {kp}")
            if item["why_cite"]:
                st.caption(f"**為何引用**：{item['why_cite']}")
            if item["tags"]:
                st.caption("標籤：" + "　".join(f"`{t}`" for t in item["tags"]))
            if item["user_notes"]:
                st.caption(f"📝 {item['user_notes']}")
        else:
            # Inline edit form
            with st.form(f"lib_edit_form_{pp_id}"):
                new_status = st.selectbox(
                    "狀態",
                    options=["confirmed", "suggested", "rejected"],
                    index=["confirmed", "suggested", "rejected"].index(item["status"]),
                    format_func=lambda x: _STATUS_LABELS.get(x, x),
                )
                existing_tags = item["tags"]
                tag_options = sorted(set(all_tags) | set(existing_tags))
                new_tags = st.multiselect("標籤", options=tag_options, default=existing_tags)
                new_notes = st.text_area("我的註記", value=item["user_notes"], height=100)
                save = st.form_submit_button("💾 儲存變更", type="primary")
                cancel = st.form_submit_button("取消")

            if save:
                with get_session() as session:
                    crud.update_project_paper(
                        session,
                        pp_id,
                        ProjectPaperUpdate(
                            status=new_status,
                            tags=new_tags or None,
                            user_notes=new_notes.strip() or None,
                        ),
                    )
                    session.commit()
                st.session_state[edit_key] = False
                st.rerun()
            elif cancel:
                st.session_state[edit_key] = False
                st.rerun()
