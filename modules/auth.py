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
from modules.db import registrar_acesso

LEVEL_BY_ROLE = {
    "admin": 1,
    "rh": 6,
    "director": 3,
    "superintendent": 4,
    "leader": 4,
    "leader2": 4,
    "rm": 5,
    "comissoes": 6,
}

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

    # 1) Tenta como ADMIN (OTP por e-mail)
    admins = st.secrets.get("admins", {})
    found_admin = next(
        (k for k in admins if k.strip().upper() == user.upper()),
        None
    )
    if found_admin:
        if pwd != admins[found_admin]:
            st.error("Senha de Admin inválida.")
            return
        code = f"{random.randint(0, 999999):06d}"
        admin_email = st.secrets["admin_emails"][found_admin]
        if enviar_codigo_email(admin_email, found_admin, code):
            st.session_state.confirmation_code = code
            st.session_state.temp_dados = {
                "LIDER":       found_admin.strip(),
                "EMAIL_LIDER": admin_email
            }
            st.session_state.role        = "admin"
            st.session_state.level = 1
            st.session_state.login_stage = 2
            st.info("Código de verificação enviado para seu e-mail de Admin.")
        else:
            st.error("Não foi possível enviar o código de verificação ao Admin.")
        return
    
    # 1.25) RH (OTP por e-mail) - nível 2
    rh_users = st.secrets.get("rh", {})
    found_rh = next((k for k in rh_users if k.strip().upper() == user.upper()), None)
    if found_rh:
        if pwd != rh_users[found_rh]:
            st.error("Senha de RH inválida.")
            return
        code = f"{random.randint(0, 999999):06d}"
        rh_email = st.secrets["rh_emails"][found_rh]
        if enviar_codigo_email(rh_email, found_rh, code):
            st.session_state.confirmation_code = code
            st.session_state.temp_dados = {
                "LIDER":       found_rh.strip(),
                "EMAIL_LIDER": rh_email
            }
            st.session_state.role        = "rh"
            st.session_state.level       = 6
            st.session_state.login_stage = 2
            st.info("Código de verificação enviado para seu e-mail (RH).")
        else:
            st.error("Não foi possível enviar o código de verificação (RH).")
        return
    
    # 1.3) Comissões (OTP por e-mail) - nível 6
    com_users = st.secrets.get("comissoes", {})
    found_com = next((k for k in com_users if k.strip().upper() == user.upper()), None)
    if found_com:
        if pwd != com_users[found_com]:
            st.error("Senha de Comissões inválida.")
            return
        code = f"{random.randint(0, 999999):06d}"
        com_email = st.secrets["comissoes_emails"][found_com]
        if enviar_codigo_email(com_email, found_com, code):
            st.session_state.confirmation_code = code
            st.session_state.temp_dados = {
                "LIDER":       found_com.strip(),
                "EMAIL_LIDER": com_email
            }
            st.session_state.role        = "comissoes"
            st.session_state.level       = 6   # ✅ Comissões = nível 6 (leitura global)
            st.session_state.login_stage = 2
            st.info("Código de verificação enviado para seu e-mail (Comissões).")
        else:
            st.error("Não foi possível enviar o código de verificação (Comissões).")
        return



    # 1.35) Diretor (OTP por e-mail)
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
            st.session_state.level = 3
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
            st.session_state.level = 5
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
            st.session_state.level = 4
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
                st.session_state.role = "leader"
                st.session_state.level = 4
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
                    # distinguir a role interna
                    st.session_state.role = "leader2"
                    st.session_state.level = 4
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
        # Garante que role exista; se já for "leader2" mantém, caso contrário define "leader"
        st.session_state.role        = st.session_state.get("role", "leader")
        st.session_state.login_stage = 2
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
            # salva quem é o usuário e role atual
            registrar_acesso(
                usuario=st.session_state.dados_lider["LIDER"],
                role=st.session_state.get("role", ""),
                nivel=st.session_state.get("level", None)
            )
            st.success("Login completo! Bem-vindo.")
            time.sleep(3)
            return        # sai e recarrega já logado, liberando o app
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