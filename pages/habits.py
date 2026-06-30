# pages/habits.py

import streamlit as st
import pandas as pd

from database.supabase import (
    add_habit,
    get_habits,
    update_habit,
    delete_habit
)


def habits_page():

    st.title("🔥 Habit Tracker")

    tab1, tab2 = st.tabs(
        [
            "Create Habit",
            "Manage Habits"
        ]
    )

    # =========================
    # CREATE HABIT
    # =========================

    with tab1:

        st.subheader("Add New Habit")

        habit_name = st.text_input(
            "Habit Name"
        )

        if st.button(
            "Add Habit"
        ):

            if habit_name:

                add_habit(
                    {
                        "habit_name": habit_name,
                        "streak": 0,
                        "completed_today": False
                    }
                )

                st.success(
                    "Habit Added!"
                )

    # =========================
    # MANAGE HABITS
    # =========================

    with tab2:

        result = get_habits()

        if result.data:

            df = pd.DataFrame(result.data)

            st.dataframe(
                df,
                use_container_width=True
            )

            st.divider()

            # =========================
            # COMPLETE HABIT
            # =========================

            st.subheader("Mark Habit Completed")

            habit_options = {
                row["habit_name"]: row["id"]
                for _, row in df.iterrows()
            }

            selected_habit = st.selectbox(
                "Habit",
                list(habit_options.keys())
            )

            if st.button("Complete Today"):
                habit_id = habit_options[selected_habit]

                habit_row = df[
                    df["id"] == habit_id
                    ].iloc[0]

                new_streak = int(
                    habit_row["streak"]
                ) + 1

                update_habit(
                    habit_id,
                    {
                        "streak": new_streak,
                        "completed_today": True
                    }
                )

                st.success(
                    f"🔥 Streak Increased to {new_streak}"
                )

                st.rerun()

            st.divider()

            # =========================
            # DELETE HABIT
            # =========================

            st.subheader("Delete Habit")

            delete_habit_name = st.selectbox(
                "Select Habit",
                list(habit_options.keys()),
                key="habit_delete"
            )

            if st.button("Delete Habit"):
                delete_habit(
                    habit_options[delete_habit_name]
                )

                st.success(
                    "Habit Deleted Successfully!"
                )

                st.rerun()

        else:

            st.info("No habits found.")
