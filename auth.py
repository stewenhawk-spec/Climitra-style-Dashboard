"""
auth.py — a very simple login gate.

IMPORTANT (read this first): this is a DEMO login, not real security.
The username/password are hardcoded in this file. It's fine for showing
teammates a prototype, but before you put real project data behind this,
swap DEMO_USERS for a proper auth system (see the note at the bottom
of this file).
"""

import streamlit as st

# Hardcoded demo accounts: username -> {password, display name, role}
DEMO_USERS = {
    "nandini": {"password": "demo123", "name": "Nandini", "role": "Super Admin"},
    "pranjal": {"password": "demo123", "name": "Pranjal", "role": "Admin"},
}


def check_login() -> bool:
    """Returns True if the current browser session is logged in."""
    return st.session_state.get("logged_in", False)


def show_login_form():
    """Renders a centered login form. Call this when check_login() is False."""
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

        st.caption("Demo login — try **nandini** / **demo123**")


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
