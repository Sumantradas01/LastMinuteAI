# app.py

import streamlit as st
from streamlit_option_menu import option_menu

from services.google_auth import (
    get_authorization_url,
    handle_oauth_callback,
    is_logged_in,
    current_user_email,
    logout,
)

from pages.calendar import calendar_page
from pages.dashboard import dashboard_page
from pages.habits import habits_page
from pages.analytics import analytics_page


# ===================================
# PAGE CONFIG
# ===================================

st.set_page_config(
    page_title="LastMinuteAI",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ===================================
# LOAD CSS
# ===================================

def load_css():

    with open(
        "assets/style.css",
        encoding="utf-8"
    ) as f:

        st.markdown(
            f"<style>{f.read()}</style>",
            unsafe_allow_html=True
        )


load_css()

# ===================================
# GOOGLE OAUTH CALLBACK
# ===================================
# When Google redirects the user back here it appends ?code=... (and
# &state=...) to the URL. Streamlit re-runs the script, so we just need to
# check for that query param once per redirect and exchange it for a token.

query_params = st.query_params

if "code" in query_params and not is_logged_in():
    try:
        code = query_params["code"]
        email, name = handle_oauth_callback(code)
        st.query_params.clear()
        st.rerun()
    except Exception as e:
        st.query_params.clear()
        st.error(f"Google sign-in failed: {e}")

# ===================================
# SIDEBAR
# ===================================
# Sign-in is now optional rather than a hard gate: every page is reachable
# without signing in (browsing tasks/habits/analytics works, but anything
# that needs a specific Google account — like pushing events to a
# calendar — will prompt for sign-in at the point it's actually needed).

with st.sidebar:

    st.image(
        "assets/logo.png",
        width=120
    )

    st.markdown(
        "## 🚀 LastMinuteAI"
    )

    if is_logged_in():
        st.caption(f"Signed in as **{current_user_email()}**")

        if st.button("Log out", use_container_width=True):
            logout()
            st.rerun()
    else:
        st.caption("Not signed in — Google Calendar sync is disabled.")

        auth_url = get_authorization_url()
        st.link_button(
            "🔐 Sign in with Google",
            auth_url,
            use_container_width=True
        )

    st.divider()

    selected = option_menu(
        menu_title=None,
        options=[
            "Dashboard",
            "Habits",
            "Calendar",
            "Analytics"
        ],
        icons=[
            "clipboard-data",
            "fire",
            "calendar",
            "bar-chart"
        ],
        default_index=0
    )

# ===================================
# ROUTING
# ===================================

if selected == "Dashboard":
    dashboard_page()

elif selected == "Habits":
    habits_page()

elif selected == "Analytics":
    analytics_page()
elif selected == "Calendar":
    calendar_page()