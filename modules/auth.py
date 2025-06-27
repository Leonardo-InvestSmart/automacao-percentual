import random
import pandas as pd
import streamlit as st
import requests
import msal
import time

from modules.gsheet import carregar_dataframe
from modules.email_service import (
    limpar_cpf,
    gerar_senha_personalizada,
    enviar_codigo_email
)
from config import TENANT_ID, CLIENT_ID, CLIENT_SECRET, EMAIL_USER

def do_login_stage1():
    st.subheader("Faça login")
    with st.form("login_form"):
        usuario_input = st.text_input("Usuário", placeholder="Nome e sobrenome")
        senha_input  = st.text_input("Senha", type="password", placeholder="Sua senha")
        btn = st.form_submit_button("Entrar")
    if not btn:
        return

    user = (usuario_input or "").strip()
    pwd  = (senha_input  or "").strip()
    if not user or not pwd:
        st.error("Informe usuário e senha para prosseguir.")
        return

    # 1) Primeiro, tenta autenticar como Diretor com OTP
    directors = st.secrets["directors"]  # { "NOME": "senha", ... }
    # busca key ignorando case
    found_dir = next(
        (k for k in directors if k.strip().upper() == user.upper()),
        None
    )
    if found_dir:
        # senha está correta?
        if pwd != directors[found_dir]:
            st.error("Senha de Diretor inválida.")
            return
        # gera e envia OTP ao e-mail do Diretor
        code = f"{random.randint(0, 999999):06d}"
        diretor_email = st.secrets["director_emails"][found_dir]
        if enviar_codigo_email(diretor_email, code):
            st.session_state.confirmation_code = code
            st.session_state.temp_dados = {
                "LIDER":       found_dir.strip(),
                "EMAIL_LIDER": diretor_email
            }
            st.session_state.role        = "director"
            st.session_state.login_stage = 2
            st.info("Código de verificação enviado para seu e-mail de Diretor.")
            
        else:
            st.error("Não foi possível enviar o código de verificação ao Diretor.")
        return

    # 2) Se não for Diretor, tenta como Líder (OTP por e-mail)
    df_filial_all = carregar_dataframe("Filial")
    df_filial_all["CPF_LIDER_CLEAN"] = (
        df_filial_all["CPF"].astype(str).apply(limpar_cpf)
    )
    nome_upper = user.upper()
    df_cand = df_filial_all[
        df_filial_all["LIDER"].str.strip().str.upper() == nome_upper
    ]
    if df_cand.empty:
        st.error("Usuário não encontrado.")
        return

    valid = False
    for _, row in df_cand.iterrows():
        senha_esp = gerar_senha_personalizada(
            row["FILIAL"], row["LIDER"], row["CPF"]
        )
        if pwd == senha_esp:
            valid = True
            st.session_state.temp_dados = {
                "LIDER":      row["LIDER"],
                "CPF_LIDER":  row["CPF"],
                "EMAIL_LIDER": row["EMAIL"]
            }
            break

    if not valid:
        st.error("Senha incorreta para este usuário.")
        return

    # envia OTP ao Líder
    code = f"{random.randint(0, 999999):06d}"
    if enviar_codigo_email(row["EMAIL"], code):
        st.session_state.confirmation_code = code
        st.session_state.role              = "leader"
        st.session_state.login_stage       = 2
        st.info("Código de confirmação enviado para seu e-mail.")
        time.sleep(3)       # pausa 3s
        return              # sai e recarrega na tela de confirmação
    else:
        st.error("Não foi possível enviar o código de confirmação ao Líder.")

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
            time.sleep(3)   # pausa 3s
            return          # sai e recarrega já logado, liberando o app
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
