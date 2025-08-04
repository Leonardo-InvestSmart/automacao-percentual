import random
import pandas as pd
import streamlit as st
import requests
import msal
import time

from modules.db import carregar_filial
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
    found_dir = next(
        (k for k in directors if k.strip().upper() == user.upper()),
        None
    )
    if found_dir:
        if pwd != directors[found_dir]:
            st.error("Senha de Diretor inválida.")
            return
        code = f"{random.randint(0, 999999):06d}"
        diretor_email = st.secrets["director_emails"][found_dir]
        if enviar_codigo_email(diretor_email, found_dir, code):
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

    # 1.5) Agora tenta autenticar como RM com OTP (mesma lógica de Diretor)
    rms = st.secrets["rms"]  # { "NOME_RM": "senha", ... }
    found_rm = next(
        (k for k in rms if k.strip().upper() == user.upper()),
        None
    )
    if found_rm:
        if pwd != rms[found_rm]:
            st.error("Senha de RM inválida.")
            return
        code = f"{random.randint(0, 999999):06d}"
        rm_email = st.secrets["rm_emails"][found_rm]
        if enviar_codigo_email(rm_email, found_rm, code):
            st.session_state.confirmation_code = code
            st.session_state.temp_dados = {
                "LIDER":       found_rm.strip(),
                "EMAIL_LIDER": rm_email
            }
            st.session_state.role        = "rm"
            st.session_state.login_stage = 2
            st.info("Código de verificação enviado para seu e-mail de RM.")
        else:
            st.error("Não foi possível enviar o código de verificação à RM.")
        return
    
    # 1.75) Agora autentica como Superintendente com OTP
    superintendents = st.secrets["superintendents"]  # { "NOME_SUP": "senha", … }
    found_sup = next(
        (k for k in superintendents if k.strip().upper() == user.upper()),
        None
    )
    if found_sup:
        if pwd != superintendents[found_sup]:
            st.error("Senha de Superintendente inválida.")
            return
        code = f"{random.randint(0,999999):06d}"
        sup_email = st.secrets["superintendent_emails"][found_sup]
        if enviar_codigo_email(sup_email, found_sup, code):
            st.session_state.confirmation_code = code
            st.session_state.temp_dados = {
                "LIDER":       found_sup.strip(),
                "EMAIL_LIDER": sup_email
            }
            st.session_state.role        = "superintendent"
            st.session_state.login_stage = 2
            st.info("Código de verificação enviado para seu e-mail de Superintendente.")
        else:
            st.error("Não foi possível enviar o código de verificação ao Superintendente.")
        return


    # 2) Se não for Diretor, tenta como Líder 1 (OTP por e-mail)
    df_filial_all = carregar_filial()
    df_filial_all["CPF_LIDER_CLEAN"] = (
        df_filial_all["CPF"].astype(str).apply(limpar_cpf)
    )

    nome_upper = user.upper()
    # -> Líder 1
    df_cand1 = df_filial_all[
        df_filial_all["LIDER"].str.strip().str.upper() == nome_upper
    ]
    valid = False
    if not df_cand1.empty:
        for _, row in df_cand1.iterrows():
            senha_esp = gerar_senha_personalizada(
                row["FILIAL"], row["LIDER"], row["CPF"]
            )
            if pwd == senha_esp:
                valid = True
                st.session_state.temp_dados = {
                    "LIDER":       row["LIDER"],
                    "CPF_LIDER":   row["CPF"],
                    "EMAIL_LIDER": row["EMAIL"]
                }
                break

    # -> Líder 2
    if not valid:
        df_cand2 = df_filial_all[
            df_filial_all["LIDER2"].str.strip().str.upper() == nome_upper
        ]
        if not df_cand2.empty:
            for _, row in df_cand2.iterrows():
                senha_esp2 = gerar_senha_personalizada(
                    row["FILIAL"], row["LIDER2"], row["CPF_LIDER2"]
                )
                if pwd == senha_esp2:
                    valid = True
                    st.session_state.temp_dados = {
                        "LIDER":        row["LIDER2"],
                        "CPF_LIDER":    row["CPF_LIDER2"],
                        "EMAIL_LIDER":  row["EMAIL_LIDER2"]
                    }
                    # opcional: distinguir a role interna
                    st.session_state.role = "leader2"
                    break

    if not valid:
        st.error("Usuário não encontrado ou senha incorreta.")
        return

    # envia OTP ao Líder (1 ou 2)
    code = f"{random.randint(0, 999999):06d}"
    email = st.session_state.temp_dados["EMAIL_LIDER"]
    nome  = st.session_state.temp_dados["LIDER"]
    if enviar_codigo_email(email, nome, code):
        st.session_state.confirmation_code = code
        st.session_state.role              = st.session_state.role or "leader"
        st.session_state.login_stage       = 2
        st.info("Código de verificação enviado para seu e-mail.")
    else:
        st.error("Não foi possível enviar o código de verificação ao Líder.")
    return

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