import streamlit as st
import os
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(
    page_title="SPPD PTMB",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─── SIMPLE AUTH ───────────────────────────────────────
def check_password():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if st.session_state.authenticated:
        return True

    st.title("🏢 SPPD PTMB")
    st.subheader("Login")
    
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submit = st.form_submit_button("Login")
        
        if submit:
            if username == os.getenv("APP_USERNAME") and password == os.getenv("APP_PASSWORD"):
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Username atau password salah!")
    
    return False

if not check_password():
    st.stop()

# ─── MAIN (setelah login) ──────────────────────────────
st.switch_page("pages/1_dashboard.py")