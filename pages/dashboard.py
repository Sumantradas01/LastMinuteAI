# pages/dashboard.py

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

from database.supabase import (
    add_task,
    get_tasks,
    update_task,
    delete_task
)
from database.supabase import auto_update_task_status
from agents.priority import predict_priority
from agents.coach import productivity_coach
from agents.replanner import replan_task
from services.google_calendar import create_events_batch
from services.google_auth import get_current_credentials, current_user_email
from agents.scheduler import generate_schedule


# ============================================================
# STYLING
# ============================================================

CUSTOM_CSS = """
<style>
    .main {
        background-color: #0e1117;
    }

    /* Page title */
    .lm-title {
        font-size: 2.4rem;
        font-weight: 800;
        background: linear-gradient(90deg, #7C3AED, #06B6D4);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0rem;
    }
    .lm-subtitle {
        color: #9CA3AF;
        font-size: 1rem;
        margin-top: -0.3rem;
        margin-bottom: 1.5rem;
    }

    /* Card container */
    .lm-card {
        background: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 16px;
        padding: 1.4rem 1.6rem;
        margin-bottom: 1.2rem;
    }

    /* Section headers inside tabs */
    .lm-section-header {
        font-size: 1.2rem;
        font-weight: 700;
        margin-bottom: 0.6rem;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }

    /* Priority badges */
    .lm-badge {
        display: inline-block;
        padding: 0.3rem 0.9rem;
        border-radius: 999px;
        font-weight: 700;
        font-size: 0.85rem;
        letter-spacing: 0.03em;
    }
    .lm-badge-high {
        background: rgba(239, 68, 68, 0.15);
        color: #F87171;
        border: 1px solid rgba(239, 68, 68, 0.4);
    }
    .lm-badge-medium {
        background: rgba(245, 158, 11, 0.15);
        color: #FBBF24;
        border: 1px solid rgba(245, 158, 11, 0.4);
    }
    .lm-badge-low {
        background: rgba(34, 197, 94, 0.15);
        color: #4ADE80;
        border: 1px solid rgba(34, 197, 94, 0.4);
    }

    /* Buttons */
    div.stButton > button {
        border-radius: 10px;
        font-weight: 600;
        border: 1px solid rgba(124, 58, 237, 0.4);
        transition: all 0.15s ease-in-out;
    }
    div.stButton > button:hover {
        border-color: #7C3AED;
        color: #fff;
        background-color: rgba(124, 58, 237, 0.15);
    }

    /* AI plan output box */
    .lm-plan-box {
        background: rgba(124, 58, 237, 0.06);
        border-left: 4px solid #7C3AED;
        border-radius: 8px;
        padding: 1rem 1.2rem;
        margin-top: 0.8rem;
    }

    /* Metric tiles */
    .lm-metric {
        text-align: center;
        background: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 14px;
        padding: 1rem 0.5rem;
    }
    .lm-metric-value {
        font-size: 1.8rem;
        font-weight: 800;
    }
    .lm-metric-label {
        color: #9CA3AF;
        font-size: 0.85rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }

    hr {
        border-color: rgba(255,255,255,0.08) !important;
    }
</style>
"""


def priority_badge(priority: str) -> str:
    p = (priority or "").upper()
    cls = {
        "HIGH": "lm-badge-high",
        "MEDIUM": "lm-badge-medium",
        "LOW": "lm-badge-low"
    }.get(p, "lm-badge-medium")
    return f'<span class="lm-badge {cls}">{p or "MEDIUM"}</span>'


def status_emoji(status: str) -> str:
    return {
        "Pending": "🟡 Pending",
        "In Progress": "🔵 In Progress",
        "Completed": "🟢 Completed"
    }.get(status, status)


# ============================================================
# DASHBOARD PAGE
# ============================================================

def dashboard_page():
    user_email = current_user_email()
    creds = get_current_credentials()

    auto_update_task_status(user_email=user_email)

    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

    st.markdown('<div class="lm-title">🚀 LastMinuteAI Dashboard</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="lm-subtitle">Plan smarter, prioritize faster, never miss a deadline.</div>',
        unsafe_allow_html=True
    )

    if not user_email:
        st.info(
            "You're browsing without signing in. Tasks and the AI tools below "
            "still work, but you'll need to sign in with Google (sidebar) to "
            "push schedules to your own Google Calendar."
        )

    # ---- Quick stats strip ----
    overview = get_tasks(user_email=user_email)
    if overview.data:
        df_overview = pd.DataFrame(overview.data)
        total = len(df_overview)
        completed = (df_overview["status"] == "Completed").sum() if "status" in df_overview else 0
        pending = (df_overview["status"] == "Pending").sum() if "status" in df_overview else 0
        high_priority = (df_overview["priority"] == "HIGH").sum() if "priority" in df_overview else 0

        c1, c2, c3, c4 = st.columns(4)
        for col, value, label in [
            (c1, total, "Total Tasks"),
            (c2, pending, "Pending"),
            (c3, completed, "Completed"),
            (c4, high_priority, "High Priority"),
        ]:
            with col:
                st.markdown(
                    f"""
                    <div class="lm-metric">
                        <div class="lm-metric-value">{value}</div>
                        <div class="lm-metric-label">{label}</div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
        st.write("")

    tab1, tab2, tab3, tab4 = st.tabs(
        ["➕ Add Task", "📋 Tasks", "🧠 AI Coach", "🔁 Replanner"]
    )

    # ==================================
    # ADD TASK
    # ==================================

    with tab1:

        st.markdown('<div class="lm-card">', unsafe_allow_html=True)
        st.markdown('<div class="lm-section-header">📝 Create New Task</div>', unsafe_allow_html=True)

        col_a, col_b = st.columns([2, 1])

        with col_a:
            title = st.text_input(
                "Task Title",
                key="task_title",
                placeholder="e.g. Finish quarterly report"
            )

            description = st.text_area(
                "Task Description",
                key="task_description",
                placeholder="Add any helpful context for the AI planner...",
                height=120
            )

        with col_b:
            deadline = st.date_input(
                "Deadline",
                key="task_deadline"
            )

            st.write("")
            generate_clicked = st.button(
                "✨ Generate AI Plan & Schedule",
                key="generate_ai_plan",
                use_container_width=True
            )

        if generate_clicked:

            if title:

                with st.spinner("Generating AI plan and schedule..."):

                    priority = predict_priority(title, description, deadline)
                    schedule = generate_schedule(title, description, deadline)

                    st.session_state["priority"] = priority
                    st.session_state["generated_schedule"] = schedule
            else:
                st.warning("Please enter a task title first.")

        if "priority" in st.session_state:
            st.markdown(
                f'Priority Level &nbsp; {priority_badge(st.session_state["priority"])}',
                unsafe_allow_html=True
            )

        st.markdown('</div>', unsafe_allow_html=True)  # end card

        if "generated_schedule" in st.session_state and st.session_state["generated_schedule"]:

            schedule = st.session_state["generated_schedule"]
            df_sched = pd.DataFrame(schedule)

            # Reorder/rename for a clean, readable table
            display_cols = [c for c in ["date", "time", "end_time", "title", "duration_minutes"] if c in df_sched.columns]
            df_display = df_sched[display_cols].rename(columns={
                "date": "Date",
                "time": "Start",
                "end_time": "End",
                "title": "Task",
                "duration_minutes": "Duration (min)"
            })

            st.markdown('<div class="lm-card">', unsafe_allow_html=True)
            st.markdown('<div class="lm-section-header">📋 Generated Schedule</div>', unsafe_allow_html=True)

            st.dataframe(
                df_display,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Date": st.column_config.TextColumn("Date", width="small"),
                    "Start": st.column_config.TextColumn("Start", width="small"),
                    "End": st.column_config.TextColumn("End", width="small"),
                    "Task": st.column_config.TextColumn("Task", width="large"),
                    "Duration (min)": st.column_config.NumberColumn("Duration (min)", width="small"),
                }
            )

            col_save, col_push = st.columns(2)

            with col_save:
                save_clicked = st.button(
                    "💾 Save Task",
                    key="save_task",
                    use_container_width=True
                )

            with col_push:
                push_clicked = st.button(
                    "📤 Add Schedule To Google Calendar",
                    key="push_schedule_gcal",
                    use_container_width=True
                )

            if save_clicked:
                priority = st.session_state.get("priority", "MEDIUM")

                add_task({
                    "title": title,
                    "description": description,
                    "deadline": str(deadline),
                    "priority": priority,
                    "status": "Pending",
                    "schedule": schedule
                }, user_email=user_email)

                st.success("✅ Task saved — view it anytime in the **Tasks** tab.")

            if push_clicked:
                if creds is None:
                    st.warning("Please sign in with Google first (top-right) to push events to your calendar.")
                else:
                    with st.spinner("Creating events on Google Calendar..."):
                        results = create_events_batch(creds, schedule, base_date=deadline)

                    success_count = sum(1 for r in results if r["status"] == "success")
                    fail_count = len(results) - success_count

                    if success_count:
                        st.success(f"✅ Added {success_count} event(s) directly to {user_email}'s Google Calendar.")
                    if fail_count:
                        st.warning(f"⚠️ {fail_count} event(s) failed to sync.")
                        for r in results:
                            if r["status"] != "success":
                                st.caption(f"• {r['title']}: {r['status']}")

            st.markdown('</div>', unsafe_allow_html=True)  # end card

    # ==================================
    # TASK LIST
    # ==================================

    with tab2:

        st.markdown('<div class="lm-section-header">📋 Task Manager</div>', unsafe_allow_html=True)

        result = get_tasks(user_email=user_email)

        if result.data:

            df = pd.DataFrame(result.data)

            # "schedule" holds the raw JSON blocks for each task — shown
            # separately below via the schedule viewer, not as a column here.
            table_cols = [c for c in df.columns if c != "schedule"]

            st.dataframe(
                df[table_cols],
                use_container_width=True,
                column_config={
                    "priority": st.column_config.TextColumn("Priority"),
                    "status": st.column_config.TextColumn("Status"),
                    "deadline": st.column_config.DateColumn("Deadline"),
                }
            )

            st.divider()

            # ==================================
            # SCHEDULE VIEWER
            # ==================================

            st.markdown('<div class="lm-card">', unsafe_allow_html=True)
            st.markdown('<div class="lm-section-header">📅 Saved Schedule</div>', unsafe_allow_html=True)

            schedule_task = st.selectbox(
                "Select Task",
                df["title"].tolist(),
                key="schedule_view_select"
            )

            task_row = df[df["title"] == schedule_task].iloc[0]
            saved_schedule = task_row.get("schedule")

            if saved_schedule:
                df_saved = pd.DataFrame(saved_schedule)
                display_cols = [c for c in ["date", "time", "end_time", "title", "duration_minutes"] if c in df_saved.columns]

                st.dataframe(
                    df_saved[display_cols].rename(columns={
                        "date": "Date",
                        "time": "Start",
                        "end_time": "End",
                        "title": "Task",
                        "duration_minutes": "Duration (min)"
                    }),
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.caption("No schedule was saved for this task.")

            st.markdown('</div>', unsafe_allow_html=True)

            col1, col2 = st.columns(2)

            with col1:
                st.markdown('<div class="lm-card">', unsafe_allow_html=True)
                st.markdown('<div class="lm-section-header">🔄 Update Task Status</div>', unsafe_allow_html=True)

                task_ids = df["title"].tolist()

                selected_task = st.selectbox("Select Task", task_ids, key="update_select")

                status = st.selectbox(
                    "Status",
                    ["Pending", "In Progress", "Completed"],
                    key="update_status_select"
                )

                if st.button("Update Status", use_container_width=True):
                    task_id = df[df["title"] == selected_task]["id"].iloc[0]
                    update_task(task_id, {"status": status})
                    st.success("Status Updated")

                st.markdown('</div>', unsafe_allow_html=True)

            with col2:
                st.markdown('<div class="lm-card">', unsafe_allow_html=True)
                st.markdown('<div class="lm-section-header">🗑️ Delete Task</div>', unsafe_allow_html=True)

                delete_id = st.selectbox(
                    "Select Task To Delete",
                    task_ids,
                    key="delete_box"
                )

                if st.button("Delete Task", use_container_width=True):
                    task_id = df[df["title"] == delete_id]["id"].iloc[0]
                    delete_task(task_id)
                    st.success("Task Deleted")

                st.markdown('</div>', unsafe_allow_html=True)

        else:
            st.info("No tasks found yet — add one in the **Add Task** tab to get started.")

    # ==================================
    # AI COACH
    # ==================================

    with tab3:

        st.markdown('<div class="lm-card">', unsafe_allow_html=True)
        st.markdown('<div class="lm-section-header">🧠 AI Productivity Coach</div>', unsafe_allow_html=True)
        st.caption("Get personalized advice based on your current task load and deadlines.")

        if st.button("Generate Advice", use_container_width=True):

            result = get_tasks(user_email=user_email)

            if result.data:
                with st.spinner("Analyzing your tasks..."):
                    advice = productivity_coach(result.data)

                st.markdown('<div class="lm-plan-box">', unsafe_allow_html=True)
                st.markdown(advice)
                st.markdown('</div>', unsafe_allow_html=True)
            else:
                st.warning("Add tasks first")

        st.markdown('</div>', unsafe_allow_html=True)

    # ==================================
    # REPLANNER
    # ==================================

    with tab4:

        st.markdown('<div class="lm-card">', unsafe_allow_html=True)
        st.markdown('<div class="lm-section-header">🔁 AI Replanner</div>', unsafe_allow_html=True)
        st.caption("Fallen behind? Get an AI-generated recovery plan for a specific task.")

        result = get_tasks(user_email=user_email)

        if result.data:

            df = pd.DataFrame(result.data)

            selected = st.selectbox(
                "Select Task",
                df["title"].tolist(),
                key="replanner_select_task"
            )

            if st.button("Generate Recovery Plan", use_container_width=True):

                task = df[df["title"] == selected].iloc[0]

                with st.spinner("Building recovery plan..."):
                    plan = replan_task(task.to_dict())

                st.markdown('<div class="lm-plan-box">', unsafe_allow_html=True)
                st.markdown(plan)
                st.markdown('</div>', unsafe_allow_html=True)

        else:
            st.warning("No tasks available")

        st.markdown('</div>', unsafe_allow_html=True)