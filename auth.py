"""
auth.py — a very simple login gate.

IMPORTANT (read this first): this is a DEMO login, not real security.
Credentials now come from st.secrets instead of being hardcoded in this
file — so a public Streamlit Cloud deploy doesn't ship guessable
passwords inside the repo itself. This is NOT the same as real auth
(no password hashing, no lockout, no per-user audit identity) — swap
DEMO_USERS for a proper auth system (see the note at the bottom of this
file) before this app handles anything a client would consider sensitive.

HOW TO SET CREDENTIALS:
  Local dev:  create .streamlit/secrets.toml (already git-ignored) with:

    [demo_users]
    nandini = { password = "choose-a-real-password", name = "Nandini", role = "Super Admin" }
    pranjal = { password = "choose-a-real-password", name = "Pranjal", role = "Admin" }

  Streamlit Community Cloud: paste the same TOML into the app's Secrets
  panel (Settings -> Secrets) instead of a local file.

  If no secrets are configured at all (e.g. first local run before you've
  set up secrets.toml), this falls back to randomly-generated one-time
  passwords printed to your terminal on startup -- NOT to a fixed
  guessable default -- so an accidental public deploy is never silently
  wide open.
"""

import secrets as _secrets

import streamlit as st


def _load_users() -> dict:
    if "demo_users" in st.secrets:
        return {k: dict(v) for k, v in st.secrets["demo_users"].items()}

    # No secrets configured -- generate throwaway random passwords instead
    # of falling back to a hardcoded default. Printed once to the terminal
    # (server logs), never shown in the UI, never stored in the repo.
    generated = {
        "nandini": {"password": _secrets.token_urlsafe(9), "name": "Nandini", "role": "Super Admin"},
        "pranjal": {"password": _secrets.token_urlsafe(9), "name": "Pranjal", "role": "Admin"},
    }
    if not st.session_state.get("_printed_generated_creds"):
        print("=" * 60)
        print("No st.secrets['demo_users'] configured. Temporary login credentials:")
        for uname, u in generated.items():
            print(f"  {uname} / {u['password']}")
        print("Set these permanently in .streamlit/secrets.toml -- see auth.py docstring.")
        print("=" * 60)
        st.session_state["_printed_generated_creds"] = True
    return generated


DEMO_USERS = None  # populated lazily inside show_login_form() / check_login()


def check_login() -> bool:
    """Returns True if the current browser session is logged in."""
    return st.session_state.get("logged_in", False)


def show_login_form():
    """Renders a centered login form. Call this when check_login() is False."""
    global DEMO_USERS
    if DEMO_USERS is None:
        DEMO_USERS = _load_users()

    left, center, right = st.columns([1, 1.2, 1])
    with center:
        st.markdown("<div style='padding-top:80px;'></div>", unsafe_allow_html=True)
        st.markdown("### 🌱 Chanakya dMRV")
        st.caption("Sign in to continue")

        username = st.text_input("Username")
        password = st.text_input("Password", type="password")

        if st.button("Log in", type="primary", use_container_width=True):
            user = DEMO_USERS.get(username.strip().lower())
            if user and user["password"] == password:
                st.session_state["logged_in"] = True
                st.session_state["user_name"] = user["name"]
                st.session_state["user_role"] = user["role"]
                st.rerun()
            else:
                st.error("Incorrect username or password.")

        if "demo_users" not in st.secrets:
            st.caption("No secrets.toml configured — check the server terminal for a generated login.")


def show_user_badge():
    """Small top-right 'logged in as ...' badge with a log-out button."""
    _, badge_col = st.columns([5, 1.3])
    with badge_col:
        name = st.session_state.get("user_name", "User")
        role = st.session_state.get("user_role", "")
        st.markdown(
            f"<div style='text-align:right; font-size:13px;'>"
            f"<b>{name}</b><br><span style='color:#5C6B73;'>{role}</span></div>",
            unsafe_allow_html=True,
        )
        if st.button("Log out", key="logout_btn", use_container_width=True):
            st.session_state.clear()
            st.rerun()


# -----------------------------------------------------------------------
# WHEN YOU'RE READY FOR REAL LOGIN / SIGN-UP:
# This file is intentionally simple so you can see how the "gate" pattern
# works. To make it production-ready, replace check_login()/show_login_form()
# with one of:
#   - streamlit-authenticator (pip package) — adds hashed passwords,
#     cookies, and a sign-up form with only a little more code than this.
#   - Supabase Auth or Firebase Auth — if you want email/Google sign-in,
#     password reset emails, etc. handled for you.
# The rest of this app (Home/Projects/Audit Log/Settings) doesn't need to
# change at all when you make that swap — it only reads st.session_state.
# -----------------------------------------------------------------------
