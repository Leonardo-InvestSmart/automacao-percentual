import re
from datetime import datetime
import msal
import requests
import streamlit as st
import base64

from config import CLIENT_ID, TENANT_ID, CLIENT_SECRET, EMAIL_USER


def enviar_resumo_email(
    destinatarios: list[str],
    assunto: str,
    corpo: str,
    content_type: str = "Text"
) -> bool:
    """
    Envia um e-mail com assunto e corpo para uma lista de destinatários via Microsoft Graph.

    Parâmetros:
    - destinatarios: lista de endereços de e-mail
    - assunto: assunto do e-mail
    - corpo: conteúdo (plain text ou HTML)
    - content_type: "Text" ou "HTML"
    """
    # Autenticação MSAL
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

    # Monta payload
    mail = {
        "message": {
            "subject": assunto,
            "body": {
                "contentType": content_type,
                "content": corpo
            },
            "toRecipients": [
                {"emailAddress": {"address": email}} for email in destinatarios
            ],
            "from": {"emailAddress": {"address": EMAIL_USER}}
        },
        "saveToSentItems": "true"
    }

    # Envio via Graph API
    endpoint = f"https://graph.microsoft.com/v1.0/users/{EMAIL_USER}/sendMail"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    resp = requests.post(endpoint, headers=headers, json=mail)
    if resp.status_code == 202:
        return True

    st.error(f"Falha ao enviar e-mail: {resp.status_code} – {resp.text}")
    return False

def limpar_cpf(texto: str) -> str:
    return re.sub(r"\D", "", texto or "")

def gerar_senha_personalizada(filial: str, nome_lider: str, cpf: str) -> str:
    parte_filial = (filial or "").strip().upper()[:3]
    nome_limpo   = (nome_lider or "").strip().upper()
    parte_lider  = nome_limpo[-3:] if len(nome_limpo) >= 3 else nome_limpo
    cpf_limpo    = limpar_cpf(cpf)
    parte_cpf    = cpf_limpo[:6] if len(cpf_limpo) >= 6 else cpf_limpo
    return parte_filial + parte_lider + parte_cpf

def enviar_codigo_email(destino: str, nome: str, codigo: str) -> bool:
    """
    Envia um código OTP de acesso em formato HTML estilizado.
    """
    # Define assunto e corpo em HTML
    assunto = "🔐 Código de confirmação • SmartC"
    conteudo_html = f"""
    <p>Olá {nome} 👋,</p>
    <p>Seu código de confirmação para acesso é:</p>
    <p style=\"font-size:1.8em;color:#9966ff;\"><strong>{codigo}</strong></p>
    <p style=\"color:#888;font-size:0.9em;\">Caso não tenha sido você, basta ignorar esta mensagem.</p>
    """
    html = _build_email_html(assunto, conteudo_html)
    return enviar_resumo_email(
        [destino],
        assunto,
        html,
        content_type="HTML"
    )

def send_director_request(
    director_email: str,
    lider: str,
    filial: str,
    assessor: str,
    produto: str,
    antigo: float,
    novo: float,
    link: str
) -> bool:
    """
    Envia ao Diretor um pedido de validação de redução, com botão e layout da marca.
    Utiliza o mesmo helper (enviar_resumo_email) para garantir autenticação e envio.
    """
    assunto = f"Validação de redução em {filial}"
    conteudo_html = f"""
    <p>Olá,</p>
    <p>O líder <strong>{lider}</strong> solicitou redução do produto <strong>{produto}</strong><br/>
    de <strong>{antigo}% → {novo}%</strong> para <strong>{assessor}</strong> em <strong>{filial}</strong>.</p>
    <p style=\"text-align:center;margin:2rem 0;\">
      <a href=\"{link}\" style=\"display:inline-block;padding:12px 24px;
         background-color:#9966ff;color:#ffffff;text-decoration:none;border-radius:4px;\">
        Ver página de Validação
      </a>
    </p>
    <p>Obrigado!</p>
    """
    html = _build_email_html(assunto, conteudo_html)
    return enviar_resumo_email(
        [director_email],
        assunto,
        html,
        content_type="HTML"
    )

def send_approval_result(df_changes, lider_email, director_email):
    for _, row in df_changes.iterrows():
        # Define o status com base na checkbox "Aprovado"
        status = "APROVADA" if row["Aprovado"] else "REJEITADA"

        # Assunto do e-mail incluindo o nome da filial
        assunto = f"Alteração {status} em {row['FILIAL']}"

        # Monta o corpo HTML da mensagem
        conteudo_html = f"""
        <p>Olá,</p>
        <p>
          Sua solicitação de alteração foi processada.
        </p>
        <p>
          A alteração de 
          <strong>{row['PERCENTUAL ANTES']}% → {row['PERCENTUAL DEPOIS']}%</strong>
          para <strong>{row['ASSESSOR']}</strong> em
          <strong>{row['FILIAL']}</strong> foi
          <strong style="color:{'#28a745' if status=='APROVADA' else '#dc3545'};">
            {status}
          </strong> pelo Diretor.
        </p>
        <p>Obrigado!</p>
        """

        # Constrói o HTML completo e envia
        html = _build_email_html(assunto, conteudo_html)
        enviar_resumo_email(
            [lider_email, director_email],
            assunto,
            html,
            content_type="HTML"
        )

def _get_logo_data_uri() -> str:
    with open("assets/investsmart_horizontal_branco.png", "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    return f"data:image/png;base64,{b64}"

def _build_email_html(titulo: str, conteudo_html: str) -> str:
    logo_data_uri = _get_logo_data_uri()
    return f"""
    <html>
      <body style="margin:0;padding:0;font-family:Montserrat,sans-serif;background-color:#f4f4f4;">
        <table align="center" width="600" cellpadding="0" cellspacing="0"
               style="background-color:#ffffff;border-radius:8px;overflow:hidden;">
          <!-- header com logo -->
          <tr>
            <td style="background-color:#9966ff;padding:20px;text-align:center;">
              <div style="max-width:300px; margin:0 auto;">
                <img src="{logo_data_uri}" alt="SmartC" width="170" style="display:block;margin:0 auto;" />
              </div>
            </td>
          </tr>
          <!-- título -->
          <tr>
            <td style="padding:20px;">
              <h2 style="color:#4A4A4A;margin-bottom:1rem;">{titulo}</h2>
              {conteudo_html}
            </td>
          </tr>
          <!-- rodapé -->
          <tr>
            <td style="background-color:#f0f0f0;padding:10px;text-align:center;font-size:12px;color:#666;">
              Este é um e-mail automático, por favor não responda.<br/>
              © 2025 InvestSmart – Todos os direitos reservados.
            </td>
          </tr>
        </table>
      </body>
    </html>
    """
