# pages/analytics.py

import streamlit as st
import pandas as pd
import plotly.express as px

from database.supabase import (
    get_tasks,
    get_habits
)
from services.google_auth import current_user_email


def analytics_page():

    st.title("📊 Productivity Analytics")

    user_email = current_user_email()
    task_result = get_tasks(user_email=user_email)
    habit_result = get_habits()

    # =========================
    # TASK ANALYTICS
    # =========================

    if task_result.data:

        tasks_df = pd.DataFrame(
            task_result.data
        )

        st.header(
            "Task Overview"
        )

        total_tasks = len(tasks_df)

        completed_tasks = len(
            tasks_df[
                tasks_df["status"] == "Completed"
            ]
        )

        pending_tasks = len(
            tasks_df[
                tasks_df["status"] == "Pending"
            ]
        )

        in_progress_tasks = len(
            tasks_df[
                tasks_df["status"] == "In Progress"
            ]
        )

        col1, col2, col3, col4 = st.columns(4)

        col1.metric(
            "Total Tasks",
            total_tasks
        )

        col2.metric(
            "Completed",
            completed_tasks
        )

        col3.metric(
            "Pending",
            pending_tasks
        )

        col4.metric(
            "In Progress",
            in_progress_tasks
        )

        # =========================
        # TASK STATUS CHART
        # =========================

        status_counts = (
            tasks_df["status"]
            .value_counts()
            .reset_index()
        )

        status_counts.columns = [
            "Status",
            "Count"
        ]

        fig = px.pie(
            status_counts,
            values="Count",
            names="Status",
            title="Task Status Distribution"
        )

        st.plotly_chart(
            fig,
            use_container_width=True
        )

        # =========================
        # PRIORITY CHART
        # =========================

        if "priority" in tasks_df.columns:

            priority_counts = (
                tasks_df["priority"]
                .value_counts()
                .reset_index()
            )

            priority_counts.columns = [
                "Priority",
                "Count"
            ]

            fig2 = px.bar(
                priority_counts,
                x="Priority",
                y="Count",
                title="Priority Breakdown"
            )

            st.plotly_chart(
                fig2,
                use_container_width=True
            )

    else:

        st.warning(
            "No task data available."
        )

    st.divider()

    # =========================
    # HABIT ANALYTICS
    # =========================

    if habit_result.data:

        habits_df = pd.DataFrame(
            habit_result.data
        )

        st.header(
            "Habit Analytics"
        )

        total_habits = len(
            habits_df
        )

        highest_streak = (
            habits_df["streak"].max()
        )

        col1, col2 = st.columns(2)

        col1.metric(
            "Total Habits",
            total_habits
        )

        col2.metric(
            "Highest Streak",
            highest_streak
        )

        fig3 = px.bar(
            habits_df,
            x="habit_name",
            y="streak",
            title="Habit Streaks"
        )

        st.plotly_chart(
            fig3,
            use_container_width=True
        )

    else:

        st.info(
            "No habit data available."
        )