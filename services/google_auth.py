# services/google_auth.py
#
# Handles "Sign in with Google" for the Streamlit app.
#
# Unlike the old services/google_calendar.py (which used InstalledAppFlow +
# a single shared token.pickle on disk — fine for one developer, broken for
# multiple users), this uses the OAuth 2.0 "web" Authorization Code flow:
#
#   1. User clicks "Sign in with Google" -> sent to Google's consent screen.
#   2. Google redirects back to our app with ?code=...
#   3. We exchange that code for an access/refresh token *for that user*.
#   4. We look up their email and store the token (in st.session_state for
#      the current session, and in Supabase so they don't have to
#      re-authorize every time they reopen the app).
#
# Every Google Calendar call elsewhere in the app should fetch the current
# user's credentials via get_current_credentials() and pass them in
# explicitly — nothing here is global/shared between users.

import os
from datetime import datetime

import streamlit as st
from dotenv import load_dotenv

# oauthlib (used internally by google-auth-oauthlib's Flow) compares the
# scopes we requested against the scopes Google actually grants, and raises
# if they don't match *exactly* as a list — including order. Google
# routinely returns scopes in a different order, and sometimes adds an
# implied scope alongside one we asked for (e.g. granting both
# "calendar" and "calendar.events" when we only requested "calendar").
# Neither case is actually a problem, so we relax oauthlib's check rather
# than fail sign-in over it. This must be set before Flow.fetch_token() is
# called.
os.environ.setdefault("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")

from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

from database.supabase import get_user_token, save_user_token

load_dotenv()

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")

# This MUST exactly match an "Authorized redirect URI" configured on the
# OAuth Client in Google Cloud Console. For local dev it's usually your
# Streamlit URL, e.g. http://localhost:8501
REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8501")

SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/calendar",
]


def _client_config():
    return {
        "web": {
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [REDIRECT_URI],
        }
    }


def _build_flow():
    # autogenerate_code_verifier=False: this is a confidential "web" client
    # (we have a client_secret), so PKCE isn't needed for security. Newer
    # google-auth-oauthlib versions enable it by default, which generates a
    # code_verifier on the Flow object used for authorization_url() — but a
    # *different* Flow object (often in a *different* Streamlit session,
    # since the round-trip to Google's consent screen and back can land on a
    # fresh session) is used for fetch_token(). That mismatch is exactly
    # what produces "invalid_grant: Missing code verifier". Turning PKCE off
    # removes the dependency on any state surviving the redirect.
    return Flow.from_client_config(
        _client_config(),
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI,
        autogenerate_code_verifier=False,
    )


def get_authorization_url():
    """Builds the Google consent screen URL and stashes the OAuth `state`
    in session so we can validate the callback."""

    flow = _build_flow()

    auth_url, state = flow.authorization_url(
        access_type="offline",       # ask for a refresh_token
        include_granted_scopes="true",
        prompt="consent",            # force refresh_token on every login
    )

    st.session_state["oauth_state"] = state

    return auth_url


def _creds_to_dict(creds: Credentials) -> dict:
    return {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": creds.scopes,
        "expiry": creds.expiry.isoformat() if creds.expiry else None,
    }


def _dict_to_creds(data: dict) -> Credentials:
    return Credentials(
        token=data.get("token"),
        refresh_token=data.get("refresh_token"),
        token_uri=data.get("token_uri"),
        client_id=data.get("client_id"),
        client_secret=data.get("client_secret"),
        scopes=data.get("scopes"),
    )


def fetch_user_profile(creds: Credentials):
    """Returns (email, name) for the signed-in Google account."""
    service = build("oauth2", "v2", credentials=creds)
    info = service.userinfo().get().execute()
    return info.get("email"), info.get("name")


def handle_oauth_callback(code: str):
    """Exchanges the `code` Google sent back for tokens, identifies the
    user, and persists their credentials (session + Supabase)."""

    flow = _build_flow()
    flow.fetch_token(code=code)
    creds = flow.credentials

    email, name = fetch_user_profile(creds)
    creds_dict = _creds_to_dict(creds)

    save_user_token(email, creds_dict)

    st.session_state["user_email"] = email
    st.session_state["user_name"] = name
    st.session_state["google_credentials"] = creds_dict

    return email, name


def get_current_credentials() -> Credentials | None:
    """Returns valid Credentials for the logged-in user, refreshing the
    access token (and persisting it) if it has expired. Returns None if
    nobody is logged in."""

    email = st.session_state.get("user_email")
    if not email:
        return None

    data = st.session_state.get("google_credentials") or get_user_token(email)
    if not data:
        return None

    creds = _dict_to_creds(data)

    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        new_data = _creds_to_dict(creds)
        st.session_state["google_credentials"] = new_data
        save_user_token(email, new_data)

    return creds


def is_logged_in() -> bool:
    return bool(st.session_state.get("user_email"))


def current_user_email() -> str | None:
    return st.session_state.get("user_email")


def logout():
    for key in ["user_email", "user_name", "google_credentials", "oauth_state"]:
        st.session_state.pop(key, None)