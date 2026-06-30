# pages/calendar_page.py

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from streamlit_calendar import calendar

from services.google_auth import get_current_credentials, current_user_email
from services.google_calendar import sync_deleted_events
from database.supabase import add_task, get_tasks
from database.supabase import auto_update_task_status
from database.supabase import (
    update_task,
    delete_task
)

from services.google_calendar import (
    update_google_event,
    delete_google_event
)
try:
    from services.google_calendar import create_event
    GOOGLE_CALENDAR_AVAILABLE = True
except Exception:
    GOOGLE_CALENDAR_AVAILABLE = False


PRIORITY_STYLES = {
    "HIGH":   {"color": "#DC2626", "bg": "#FEE2E2", "label": "🔴 High"},
    "MEDIUM": {"color": "#D97706", "bg": "#FEF3C7", "label": "🟠 Medium"},
    "LOW":    {"color": "#16A34A", "bg": "#DCFCE7", "label": "🟢 Low"},
}

STATUS_STYLES = {
    "Completed":   {"color": "#16A34A", "bg": "#DCFCE7"},
    "Pending":     {"color": "#2563EB", "bg": "#DBEAFE"},
    "In Progress": {"color": "#D97706", "bg": "#FEF3C7"},
}


def inject_css():
    st.markdown("""
        <style>
        .block-container {
            padding-top: 2rem;
            padding-bottom: 3rem;
        }

        /* Page header */
        .cal-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 0.25rem;
        }
        .cal-subtitle {
            color: #6B7280;
            font-size: 0.95rem;
            margin-bottom: 1.5rem;
        }

        /* Stat cards */
        .stat-card {
            background: linear-gradient(135deg, #FFFFFF 0%, #F8FAFC 100%);
            border: 1px solid #E5E7EB;
            border-radius: 14px;
            padding: 1rem 1.2rem;
            text-align: left;
            box-shadow: 0 1px 3px rgba(0,0,0,0.04);
        }
        .stat-number {
            font-size: 1.6rem;
            font-weight: 700;
            color: #111827;
            line-height: 1.1;
        }
        .stat-label {
            font-size: 0.8rem;
            color: #6B7280;
            margin-top: 2px;
            text-transform: uppercase;
            letter-spacing: 0.03em;
        }

        /* Section card wrapper */
        .section-card {
            background: #FFFFFF;
            border: 1px solid #E5E7EB;
            border-radius: 16px;
            padding: 1.4rem 1.5rem;
            margin-bottom: 1.2rem;
            box-shadow: 0 1px 2px rgba(0,0,0,0.03);
        }
        .section-title {
            font-size: 1.05rem;
            font-weight: 600;
            color: #111827;
            margin-bottom: 0.8rem;
            display: flex;
            align-items: center;
            gap: 0.4rem;
        }

        /* Pills */
        .pill {
            display: inline-block;
            padding: 3px 10px;
            border-radius: 999px;
            font-size: 0.75rem;
            font-weight: 600;
        }

        /* Event row card */
        .event-row {
            border: 1px solid #EEF0F2;
            border-radius: 12px;
            padding: 0.7rem 1rem;
            margin-bottom: 0.5rem;
            background: #FAFAFA;
        }
        .event-title {
            font-weight: 600;
            color: #111827;
            font-size: 0.95rem;
        }
        .event-meta {
            color: #6B7280;
            font-size: 0.8rem;
            margin-top: 2px;
        }

        /* Buttons */
        div.stButton > button {
            border-radius: 10px;
            font-weight: 500;
        }

        hr {
            margin: 1.5rem 0;
        }
        </style>
    """, unsafe_allow_html=True)


def priority_pill(priority):
    style = PRIORITY_STYLES.get(priority, PRIORITY_STYLES["LOW"])
    return f'<span class="pill" style="color:{style["color"]}; background:{style["bg"]};">{style["label"]}</span>'


def status_pill(status):
    style = STATUS_STYLES.get(status, {"color": "#374151", "bg": "#F3F4F6"})
    return f'<span class="pill" style="color:{style["color"]}; background:{style["bg"]};">{status}</span>'


def calendar_page():
    inject_css()

    user_email = current_user_email()
    creds = get_current_credentials()

    # Initialize session state
    if "show_event_form" not in st.session_state:
        st.session_state["show_event_form"] = False

    auto_update_task_status(user_email=user_email)
    try:
        sync_deleted_events(creds)
    except Exception as e:
        st.warning(f"Google Calendar sync skipped: {e}")

    # ==========================
    # HEADER
    # ==========================
    st.markdown(
        """
        <div class="cal-header">
            <h1>📅 Smart Calendar</h1>
        </div>
        <div class="cal-subtitle">Plan, track, and sync your schedule — all in one place.</div>
        """,
        unsafe_allow_html=True
    )

    # ==========================
    # STATS STRIP
    # ==========================
    result_preview = get_tasks(user_email=user_email)
    preview_df = pd.DataFrame(result_preview.data) if result_preview and result_preview.data else pd.DataFrame()

    total = len(preview_df)
    completed = len(preview_df[preview_df["status"] == "Completed"]) if not preview_df.empty else 0
    pending = len(preview_df[preview_df["status"] == "Pending"]) if not preview_df.empty else 0
    high_priority = len(preview_df[preview_df["priority"] == "HIGH"]) if not preview_df.empty else 0

    s1, s2, s3, s4 = st.columns(4)
    for col, label, value in zip(
        [s1, s2, s3, s4],
        ["Total Events", "Completed", "Pending", "High Priority"],
        [total, completed, pending, high_priority]
    ):
        with col:
            st.markdown(
                f"""<div class="stat-card">
                        <div class="stat-number">{value}</div>
                        <div class="stat-label">{label}</div>
                    </div>""",
                unsafe_allow_html=True
            )

    st.write("")

    # ==========================
    # Add Event
    # ==========================
    top_l, top_r = st.columns([5, 1.3])
    with top_l:
        st.markdown('<div class="section-title">🗓️ Your Calendar</div>', unsafe_allow_html=True)
    with top_r:
        btn_label = "❌ Close Form" if st.session_state["show_event_form"] else "➕ Add Event"
        if st.button(btn_label, use_container_width=True):
            st.session_state["show_event_form"] = not st.session_state["show_event_form"]
            st.rerun()

    event_data = None

    if st.session_state["show_event_form"]:
        with st.container(border=True):
            st.markdown('<div class="section-title">✨ New Event</div>', unsafe_allow_html=True)

            with st.form("calendar_event_form"):
                c1, c2 = st.columns(2)
                with c1:
                    title = st.text_input("Event Title", placeholder="e.g. Client presentation")
                with c2:
                    priority = st.selectbox("Priority", ["HIGH", "MEDIUM", "LOW"], index=1)

                description = st.text_area("Description", placeholder="Add details about this event...")

                c3, c4, c5 = st.columns(3)
                with c3:
                    event_date = st.date_input("Date")
                with c4:
                    start_time = st.time_input("Start Time")
                with c5:
                    duration = st.slider("Duration (hrs)", 1, 8, 1)

                sync_google = st.checkbox(
                    "🔗 Sync with Google Calendar",
                    value=True,
                    help=f"Adds this event to {user_email}'s Google Calendar"
                )

                submitted = st.form_submit_button("💾 Save Event", use_container_width=True)

        if submitted:
            start_datetime = datetime.combine(event_date, start_time)
            end_datetime = start_datetime + timedelta(hours=duration)

            if sync_google and GOOGLE_CALENDAR_AVAILABLE:
                if creds is None:
                    st.warning("You're not signed in to Google — event saved locally only.")
                else:
                    try:
                        with st.spinner("Creating Google Calendar event..."):
                            event_data = create_event(creds, title, description, start_datetime, end_datetime)
                    except Exception as e:
                        st.warning(f"Google Calendar Sync Failed:\n{e}")

            add_task({
                "title": title,
                "description": description,
                "deadline": start_datetime.isoformat(),
                "priority": priority,
                "status": "Pending",
                "google_event_id": event_data["id"] if event_data else None
            }, user_email=user_email)

            st.success("✅ Event Added Successfully!")
            st.session_state["show_event_form"] = False
            st.rerun()

    st.divider()

    # ==========================
    # EVENT MANAGER
    # ==========================
    st.markdown('<div class="section-title">✏️ Event Manager</div>', unsafe_allow_html=True)
    result = get_tasks(user_email=user_email)

    df = pd.DataFrame(result.data) if result and result.data else pd.DataFrame()

    if df.empty:
        st.info("No events scheduled yet. Click **➕ Add Event** to create your first one.")

    event_options = {
        f"{row['title']}  ·  {row['deadline'][:10]}": row
        for _, row in df.iterrows()
    }

    if event_options:
        sel_col, btn_col1, btn_col2 = st.columns([4, 1, 1])
        with sel_col:
            selected = st.selectbox("Select Event", list(event_options.keys()), key="event_select", label_visibility="collapsed")

        event = event_options[selected]

        # Preview card of selected event
        st.markdown(
            f"""
            <div class="event-row">
                <div class="event-title">{event['title']}</div>
                <div class="event-meta">{event['deadline'][:16].replace('T', '  •  ')}</div>
                <div style="margin-top:6px;">
                    {priority_pill(event['priority'])}&nbsp;&nbsp;{status_pill(event['status'])}
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

        with btn_col1:
            if st.button("✏️ Update", key="open_update_form", use_container_width=True):
                st.session_state["selected_event"] = event
                st.session_state["show_update_form"] = True
                st.rerun()

        with btn_col2:
            if st.button("🗑 Delete", key="delete_event_btn", use_container_width=True):
                google_event_id = event.get("google_event_id")
                if google_event_id and creds is not None:
                    try:
                        delete_google_event(creds, google_event_id)
                    except Exception as e:
                        st.warning(f"Google delete failed:\n{e}")

                delete_task(event["id"])
                st.success("Event Deleted")
                st.rerun()

    # ==========================
    # UPDATE FORM
    # ==========================
    if st.session_state.get("show_update_form", False):

        event = st.session_state["selected_event"]
        current_datetime = datetime.fromisoformat(event["deadline"])

        with st.container(border=True):
            st.markdown('<div class="section-title">✏️ Edit Event</div>', unsafe_allow_html=True)

            with st.form("update_event_form"):
                c1, c2 = st.columns(2)
                with c1:
                    new_title = st.text_input("Event Title", value=event["title"])
                with c2:
                    new_priority = st.selectbox(
                        "Priority",
                        ["HIGH", "MEDIUM", "LOW"],
                        index=["HIGH", "MEDIUM", "LOW"].index(event["priority"])
                    )

                new_description = st.text_area("Description", value=event["description"])

                c3, c4, c5 = st.columns(3)
                with c3:
                    new_date = st.date_input("Date", value=current_datetime.date())
                with c4:
                    new_time = st.time_input("Time", value=current_datetime.time())
                with c5:
                    duration = st.slider("Duration (hrs)", 1, 8, 1)

                fc1, fc2 = st.columns(2)
                with fc1:
                    save = st.form_submit_button("💾 Save Changes", use_container_width=True)
                with fc2:
                    cancel = st.form_submit_button("❌ Cancel", use_container_width=True)

        if save:
            start_datetime = datetime.combine(new_date, new_time)
            end_datetime = start_datetime + timedelta(hours=duration)

            update_task(
                event["id"],
                {
                    "title": new_title,
                    "description": new_description,
                    "deadline": start_datetime.isoformat(),
                    "priority": new_priority
                }
            )

            google_event_id = event.get("google_event_id")
            if google_event_id and creds is not None:
                try:
                    update_google_event(
                        creds,
                        google_event_id,
                        new_title,
                        new_description,
                        start_datetime,
                        end_datetime
                    )
                except Exception as e:
                    st.warning(f"Google update failed:\n{e}")

            st.success("✅ Event Updated Successfully")
            st.session_state["show_update_form"] = False
            st.session_state["selected_event"] = None
            st.rerun()

        if cancel:
            st.session_state["show_update_form"] = False
            st.session_state["selected_event"] = None
            st.rerun()

    st.divider()

    # ==========================
    # Calendar View
    # ==========================
    result = get_tasks(user_email=user_email)
    df = pd.DataFrame(result.data) if result and result.data else pd.DataFrame()

    events = []
    for _, row in df.iterrows():
        color = PRIORITY_STYLES.get(row["priority"], {}).get("color", "#2563EB")
        start = datetime.fromisoformat(row["deadline"])
        end = start + timedelta(hours=1)

        events.append({
            "title": row["title"],
            "start": start.isoformat(),
            "end": end.isoformat(),
            "color": color,
            "textColor": "#FFFFFF",
        })

    options = {
        "initialView": "dayGridMonth",
        "editable": True,
        "selectable": True,
        "height": 650,
        "headerToolbar": {
            "left": "prev,next today",
            "center": "title",
            "right": "dayGridMonth,timeGridWeek,timeGridDay"
        },
        "eventDisplay": "block",
        "dayMaxEvents": 3,
    }

    # Calendar always renders, even with zero tasks/events — it just shows
    # an empty grid for the current month instead of disappearing entirely.
    with st.container(border=True):
        calendar(events=events, options=options, key="calendar")

    st.write("")

    st.markdown('<div class="section-title">📋 Scheduled Events</div>', unsafe_allow_html=True)

    if not df.empty:
        view_df = df[["title", "deadline", "priority", "status"]].copy()
        view_df["deadline"] = pd.to_datetime(view_df["deadline"]).dt.strftime("%b %d, %Y · %H:%M")
        view_df = view_df.rename(columns={
            "title": "Title",
            "deadline": "Date & Time",
            "priority": "Priority",
            "status": "Status"
        })

        st.dataframe(
            view_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Priority": st.column_config.TextColumn("Priority"),
                "Status": st.column_config.TextColumn("Status"),
            }
        )

    else:
        st.info("No events scheduled yet.")