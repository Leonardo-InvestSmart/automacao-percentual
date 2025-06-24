import re
from datetime import datetime
import msal
import requests
import streamlit as st

from config import CLIENT_ID, TENANT_ID, CLIENT_SECRET, EMAIL_USER

def limpar_cpf(texto: str) -> str:
    return re.sub(r"\D", "", texto or "")

def gerar_senha_personalizada(filial: str, nome_lider: str, cpf: str) -> str:
    parte_filial = (filial or "").strip().upper()[:3]
    nome_limpo   = (nome_lider or "").strip().upper()
    parte_lider  = nome_limpo[-3:] if len(nome_limpo) >= 3 else nome_limpo
    cpf_limpo    = limpar_cpf(cpf)
    parte_cpf    = cpf_limpo[:6] if len(cpf_limpo) >= 6 else cpf_limpo
    return parte_filial + parte_lider + parte_cpf

def enviar_codigo_email(destino: str, codigo: str) -> bool:
    app = msal.ConfidentialClientApplication(
        CLIENT_ID,
        authority=f"https://login.microsoftonline.com/{TENANT_ID}",
        client_credential=CLIENT_SECRET
    )
    token_response = app.acquire_token_for_client(
        scopes=["https://graph.microsoft.com/.default"]
    )
    if "access_token" not in token_response:
        st.error(
            f"Erro ao obter token de autenticação: "
            f"{token_response.get('error_description', token_response.get('error'))}"
        )
        return False
    access_token = token_response["access_token"]

    mail_payload = {
        "message": {
            "subject": "Código de confirmação - Login",
            "body": {
                "contentType": "Text",
                "content": (
                    f"Olá,\n\nSeu código de confirmação para acesso é: {codigo}\n"
                    "\nSe não foi você, ignore este e-mail."
                )
            },
            "toRecipients": [
                {"emailAddress": {"address": destino}}
            ],
            "from": {"emailAddress": {"address": EMAIL_USER}}
        },
        "saveToSentItems": "true"
    }

    endpoint = f"https://graph.microsoft.com/v1.0/users/{EMAIL_USER}/sendMail"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    resp = requests.post(endpoint, headers=headers, json=mail_payload)
    if resp.status_code == 202:
        return True

    st.error(f"Falha ao enviar e-mail de confirmação: {resp.status_code} – {resp.text}")
    return False
