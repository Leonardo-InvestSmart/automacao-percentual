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
    assunto = f"Validação de alteração em {filial}"
    conteudo_html = f"""
    <p>Olá,</p>
    <p>O líder <strong>{lider}</strong> solicitou alteração do produto <strong>{produto}</strong><br/>
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

def send_approval_result(df_changes, lider_email):
    """
    Envia o e-mail de confirmação de aprovação das reduções.
    Agora notifica: Líder (solicitante), Diretor (via lider_email como cópia se desejar),
    Assessor impactado e Solicitante (quando disponível em df_changes).
    Espera que df_changes contenha as colunas:
      - EMAIL_ASSESSOR
      - EMAIL_SOLICITANTE
    """
    if df_changes is None or df_changes.empty:
        return

    # constrói tabela HTML (mantém o que você já tem hoje)
    linhas = []
    for _, row in df_changes.iterrows():
        linhas.append(
            f"<tr>"
            f"<td>{row.get('ASSESSOR','')}</td>"
            f"<td>{row.get('PRODUTO','')}</td>"
            f"<td>{row.get('PERCENTUAL ANTES','')}%</td>"
            f"<td>{row.get('PERCENTUAL DEPOIS','')}%</td>"
            f"<td>{row.get('TIMESTAMP','')}</td>"
            f"</tr>"
        )
    items_html = "".join(linhas)

    subject = "Confirmação de aprovação de redução de percentual"
    conteudo_html = f"""
    <p>As reduções abaixo foram <strong>aprovadas</strong> pelo Diretor:</p>
    <table border="1" cellpadding="6" cellspacing="0">
      <thead>
        <tr>
          <th>Assessor</th><th>Produto</th><th>Antes</th><th>Depois</th><th>Data/Hora</th>
        </tr>
      </thead>
      <tbody>{items_html}</tbody>
    </table>
    """

    html = _build_email_html(subject, conteudo_html)

    # --- NOVO: destinatários ---
    destinatarios = set()
    # fallback: sempre inclui o líder logado
    if lider_email:
        destinatarios.add(lider_email)

    # pega por linha os e-mails do assessor e do solicitante
    for _, row in df_changes.iterrows():
        email_ass = (row.get("EMAIL_ASSESSOR") or "").strip()
        email_sol = (row.get("EMAIL_SOLICITANTE") or "").strip()
        if email_ass:
            destinatarios.add(email_ass)
        if email_sol:
            destinatarios.add(email_sol)

    # dispara (HTML)
    if destinatarios:
        enviar_resumo_email(list(destinatarios), subject, html, content_type="HTML")


def send_declaration_email(
    director_email: str,
    juridico_email: str,
    lider_name: str,
    filial: str,
    items_html: str,
    timestamp_display: str
) -> bool:
    """
    Envia e-mail de acato de declaração ao Diretor e ao Jurídico.
    """
    # email_service.py  (trecho corrigido)
    assunto = f"Declaração de Revisão Contratual em {filial} – {timestamp_display}"

    conteudo_html = f"""
    <h3>Declaração de Revisão Contratual</h3>
    <p>Eu, <strong>{lider_name}</strong>, declaro que a alteração do percentual de comissionamento ora aprovada por mim foi realizada
    em conformidade com a contratação existente e formalizada com o respectivo assessor, as diretrizes internas da companhia e
    com os princípios da boa-fé, legalidade e transparência.</p>

    <p>Segue abaixo a relação dos assessores e percentuais alterados:</p>

    <table border="1" cellpadding="4" cellspacing="0">
      <tr>
        <th>Assessor</th><th>Produto</th><th>Antes</th><th>Depois</th><th>Data e Hora</th>
      </tr>
      {items_html}
    </table>

    <p>Asseguro que li as cláusulas aplicáveis e assumo responsabilidade sob a ótica da conformidade.</p>
    <p>Este e-mail também foi enviado para o Departamento Jurídico.</p>
    """
    html = _build_email_html(assunto, conteudo_html)
    return enviar_resumo_email(
        [director_email, juridico_email],
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
