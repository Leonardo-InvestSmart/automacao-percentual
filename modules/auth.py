import random
import pandas as pd
import streamlit as st
import requests
import msal
from modules.gsheet import carregar_dataframe
from modules.email_service import (
    limpar_cpf,
    gerar_senha_personalizada,
    enviar_codigo_email
)
from config import TENANT_ID, CLIENT_ID, CLIENT_SECRET, EMAIL_USER

def do_login_stage1():
    st.subheader("Faça login como Líder de Filial")
    with st.form("login_form"):
        usuario_input = st.text_input(
            "Usuario", placeholder="Nome e sobrenome do líder"
        )
        senha_input = st.text_input(
            "Senha", type="password",
            placeholder="Senha única recebida por e-mail"
        )
        btn = st.form_submit_button("Entrar")
    if btn:
        if not usuario_input or not senha_input:
            st.warning("Informe usuário e senha para prosseguir.")
        else:
            df_filial_all = carregar_dataframe("Filial")
            df_filial_all["CPF_LIDER_CLEAN"] = (
                df_filial_all["CPF"].astype(str)
                .apply(limpar_cpf)
            )
            nome_upper = usuario_input.strip().upper()
            df_cand = df_filial_all[
                df_filial_all["LIDER"].astype(str)
                .str.strip().str.upper() == nome_upper
            ]
            if df_cand.empty:
                st.error("Usuário não encontrado.")
            else:
                validou = False
                for _, row in df_cand.iterrows():
                    senha_esp = gerar_senha_personalizada(
                        row["FILIAL"], row["LIDER"], row["CPF"]
                    )
                    if senha_input.strip() == senha_esp:
                        validou = True
                        st.session_state.temp_dados = {
                            "LIDER":     row["LIDER"],
                            "CPF_LIDER": row["CPF"],
                            "EMAIL_LIDER": row["EMAIL"]
                        }
                        break
                if validou:
                    code = f"{random.randint(0, 999999):06d}"
                    if enviar_codigo_email(row["EMAIL"], code):
                        st.session_state.confirmation_code = code
                        st.info("Código de confirmação enviado para seu e-mail.")
                        st.session_state.login_stage = 2
                else:
                    st.error("Senha incorreta para este usuário.")

def do_login_stage2():
    st.subheader("Confirme o código de acesso")
    with st.form("confirm_form"):
        code_input = st.text_input(
            "Código de 6 dígitos", max_chars=6
        )
        btn2 = st.form_submit_button("Confirmar")
    if btn2:
        if code_input == st.session_state.confirmation_code:
            st.session_state.autenticado = True
            st.session_state.dados_lider = st.session_state.temp_dados
            st.success("Login completo! Bem-vindo.")
        else:
            st.error("Código incorreto. Tente novamente.")

def enviar_resumo_email(destinatarios: list[str], assunto: str, corpo: str) -> bool:
    """
    Envia um e-mail com assunto e corpo para uma lista de destinatários via Microsoft Graph.
    """
    # 1) Obter token via Client Credentials Flow
    app = msal.ConfidentialClientApplication(
        CLIENT_ID,
        authority=f"https://login.microsoftonline.com/{TENANT_ID}",
        client_credential=CLIENT_SECRET
    )
    token_resp = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
    if "access_token" not in token_resp:
        st.error(f"Erro ao obter token para envio de e-mail: {token_resp.get('error_description')}")
        return False
    token = token_resp["access_token"]

    # 2) Montar payload
    mail = {
        "message": {
            "subject": assunto,
            "body": {
                "contentType": "Text",
                "content": corpo
            },
            "toRecipients": [
                {"emailAddress": {"address": email}} for email in destinatarios
            ],
            "from": {"emailAddress": {"address": EMAIL_USER}}
        },
        "saveToSentItems": "true"
    }

    # 3) Enviar via Graph API
    endpoint = f"https://graph.microsoft.com/v1.0/users/{EMAIL_USER}/sendMail"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    resp = requests.post(endpoint, headers=headers, json=mail)
    if resp.status_code == 202:
        return True
    else:
        st.error(f"Falha ao enviar e-mail: {resp.status_code} – {resp.text}")
        return False
