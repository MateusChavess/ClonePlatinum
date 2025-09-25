import streamlit as st

st.set_page_config(page_title="Login • Clone Edição Platinum", layout="wide")

VALID_USER = "Pipo"
VALID_PASS = "Pipo123TS"   # troquei por uma senha forte para evitar o alerta do navegador

# 🔕 Esconde o hint "Press Enter to submit form"
st.markdown(
    """
    <style>
      [data-testid="InputInstructions"] { display: none !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

# Se já estiver logado, vai direto para a página principal
if st.session_state.get("logged_in"):
    st.switch_page("pages/Main.py")  # <- mantém a navegação, com 'M' maiúsculo

# ------- Login simples -------
st.title("🔐 Acesso Clone Platinum")

# centraliza o formulário
c1, c2, c3 = st.columns([1, 1.2, 1])
with c2:
    with st.form("login_form", clear_on_submit=False):
        user = st.text_input("Usuário", value="", placeholder="Digite seu usuário")
        pwd  = st.text_input("Senha", value="", placeholder="Digite sua senha", type="password")
        ok   = st.form_submit_button("Entrar", use_container_width=True)

        if ok:
            if user == VALID_USER and pwd == VALID_PASS:
                st.session_state.logged_in = True
                st.session_state.user_name = user
                st.switch_page("pages/main.py")  # <- navega para a Main protegida
            else:
                st.error("Usuário ou senha inválidos.")
