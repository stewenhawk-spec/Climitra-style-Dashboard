"""
main.py — the ONE file you run: `streamlit run main.py`

What this file does, in order:
  1. Sets page config (tab title, icon, wide layout)
  2. Injects shared CSS (dark sidebar, blue/green accents)
  3. Checks login — if not logged in, shows the login form and stops
  4. Builds the left sidebar navigation (Home / Projects / Audit Log / Settings)
  5. Shows the "logged in as ..." badge top-right
  6. Runs whichever page the user clicked

You should NOT need to touch this file much once it's working — new pages
go in views/, new content goes in those files, not here.
"""

import streamlit as st

from auth import check_login, show_login_form, show_user_badge

st.set_page_config(page_title="Chanakya dMRV", page_icon="🌱", layout="wide")

# --- Shared theme: dark navy sidebar, blue/green accents -------------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=Inter:wght@400;500;600&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
h1, h2, h3 { font-family: 'Space Grotesk', sans-serif !important; color: #123F5E; }

section[data-testid="stSidebar"] { background-color: #0B1B2B; }
section[data-testid="stSidebar"] * { color: #D7E2EA !important; }

div[data-testid="stMetric"] {
    background: #FFFFFF; border: 1px solid #E1E6EA; border-radius: 6px;
    padding: 14px 16px 10px 16px; border-top: 3px solid #1B5E8C;
}
div[data-testid="stMetricLabel"] { color: #5C6B73; font-size: 12.5px; }
div[data-testid="stMetricValue"] { color: #123F5E; font-family: 'Space Grotesk', sans-serif; }

.stButton > button {
    background-color: #1B5E8C; color: #FFFFFF; border: none;
    font-weight: 600; border-radius: 5px;
}
.stButton > button:hover { background-color: #123F5E; color: #FFFFFF; }
</style>
""", unsafe_allow_html=True)

# --- Step 1: login gate -----------------------------------------------
if not check_login():
    show_login_form()
    st.stop()  # nothing below this line runs until login succeeds

# --- Step 2: define the pages that make up the left sidebar -----------
home = st.Page("views/home.py", title="Home", icon="🏠", default=True)
projects = st.Page("views/projects.py", title="Projects", icon="📁")
audit_log = st.Page("views/audit_log.py", title="Audit Log", icon="📜")
settings = st.Page("views/settings.py", title="Settings", icon="⚙️")

pg = st.navigation([home, projects, audit_log, settings])

# --- Step 3: top-right "logged in as ..." badge ------------------------
show_user_badge()

# --- Step 4: render whichever page is selected --------------------------
pg.run()
