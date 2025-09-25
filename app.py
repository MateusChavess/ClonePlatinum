# app.py
import streamlit as st
st.set_page_config(page_title="Login • Clone Edição Platinum", layout="wide")

VALID_USER = "Pipo"
VALID_PASS = "P1po!2025"

# já logado? manda pra Main
if st.session_state.get("logged_in"):
    st.switch_page("pages/Main.py")

st.title("🔐 Acesso Clone Platinum")

with st.form("login_form"):
    user = st.text_input("Usuário")
    pwd  = st.text_input("Senha", type="password")
    ok   = st.form_submit_button("Entrar", use_container_width=True)

    if ok:
        if user == VALID_USER and pwd == VALID_PASS:
            st.session_state.logged_in = True          # <-- único lugar que vira True
            st.session_state.user_name = user
            st.switch_page("pages/main.py")
        else:
            st.error("Usuário ou senha inválidos.")
