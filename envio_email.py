# envio_email.py
import pandas as pd
import win32com.client as win32
import re
from typing import Dict, Tuple

# mantém o mesmo template visual do e-mail
from modules.email_service import _build_email_html

# -----------------------------------------------------------------------------
# Carrega secrets: tenta via Streamlit; se não houver, lê secrets.toml local
# -----------------------------------------------------------------------------
def _load_secrets() -> Dict:
    try:
        import streamlit as st  # type: ignore
        # st.secrets já funciona como dict
        return dict(st.secrets)
    except Exception:
        import tomllib  # Python 3.11+
        with open("secrets.toml", "rb") as f:
            return tomllib.load(f)

SECRETS = _load_secrets()
EMAIL_USER = SECRETS.get("EMAIL_USER", "comissoes@investsmart.com.br")

# Mapas: chaves do secrets por grupo
GROUP_MAP = {
    "rms": {
        "pwd_section": "rms",
        "email_section": "rm_emails",
        "assunto": "Comunicado Comissões - Acesso para RM",
        "template_texto": """
        <p>Olá, {NOME}, tudo bem?</p>
        <p>Você recebeu acesso à nova plataforma SmartC, com foco em acompanhamento e suporte às filiais da sua diretoria.</p>
        <p>Alguns pontos importantes:</p>
        <ol>
          <li>O acesso das RM's foi definido somente como leitura.</li>  
          <li>Prazo-limite para ajustes de percentual: <strong>todo dia 08</strong> de cada mês.</li>
          <li>O acesso exige confirmações por e-mail para garantir segurança nas mudanças de repasse.</li>
          <li>Reduções de repasse exigem aprovação do Diretor.</li>
          <li>Envie melhorias e dúvidas pelo página de sugestões.</li>
        </ol>
        <p>Link da plataforma: <a href="https://smartc.streamlit.app/">https://smartc.streamlit.app/</a></p>
        <p>Dúvidas/Solicitações: <a href="https://forms.cloud.microsoft/r/KWHcWDe61g">https://forms.cloud.microsoft/r/KWHcWDe61g</a></p>
        <p>Segue abaixo o seu acesso:</p>
        """
    },
    "superintendents": {
        "pwd_section": "superintendents",
        "email_section": "superintendent_emails",
        "assunto": "Comunicado Comissões - Acesso para Superintendência",
        "template_texto": """
        <p>Olá, {NOME}, tudo bem?</p>
        <p>Você recebeu acesso à nova plataforma SmartC para gestão e governança dos percentuais de repasse das filiais sob sua
        responsabilidade.</p>
        <p>Regras relevantes:</p>
        <ol>
          <li>Prazo-limite para ajustes de percentual: <strong>todo dia 08</strong> de cada mês.</li>
          <li>O acesso à plataforma e a confirmação das alterações exige confirmações por e-mail para garantir segurança.</li>
          <li>Reduções de repasse exigem aprovação do Diretor.</li>
          <li>Envie melhorias e dúvidas pela página de sugestões.</li>
        </ol>
        <p>Link da plataforma: <a href="https://smartc.streamlit.app/">https://smartc.streamlit.app/</a></p>
        <p>Dúvidas/Solicitações: <a href="https://forms.cloud.microsoft/r/KWHcWDe61g">https://forms.cloud.microsoft/r/KWHcWDe61g</a></p>
        <p>Segue abaixo o seu acesso:</p>
        """
    },
    # (opcional) você pode habilitar diretores aqui também, se quiser
    "directors": {
        "pwd_section": "directors",
        "email_section": "director_emails",
        "assunto": "Comunicado Comissões - Acesso para Diretoria",
        "template_texto": """
        <p>Olá, {NOME}, tudo bem?</p>
        <p>Concedemos seu acesso ao painel SmartC, com capacidade de aprovar reduções de repasse e acompanhar alterações de gestão.</p>
        <ol>
          <li>Prazo-limite para ajustes: <strong>dia 08</strong> de cada mês.</li>
          <li>Confirmações por e-mail para segurança e trilha de auditoria.</li>
          <li>Reduções dependem de sua aprovação.</li>
          <li>Envie melhorias e dúvidas pelo link de sugestões.</li>
        </ol>
        <p>Link da plataforma: <a href="https://smartc.streamlit.app/">https://smartc.streamlit.app/</a></p>
        <p>Dúvidas/Solicitações: <a href="https://forms.cloud.microsoft/r/KWHcWDe61g">https://forms.cloud.microsoft/r/KWHcWDe61g</a></p>
        <p>Segue abaixo o seu acesso:</p>
        """
    },
}

# -----------------------------------------------------------------------------
# Montadores de HTML
# -----------------------------------------------------------------------------
def _justificar_e_inserir_login(template_texto: str, nome: str, login: str, senha: str) -> str:
    # margens nos <li>
    corpo = re.sub(r"<li>", '<li style="margin-bottom:10px;">', template_texto)
    # bloco final com credenciais
    credenciais = f"""
    <p><strong>Login:</strong> {login}<br>
       <strong>Senha:</strong> {senha}</p>
    <p>Esse acesso é individual. Não compartilhe suas credenciais.</p>
    <p>Atenciosamente,<br>Equipe de Comissões</p>
    """
    return f'<div style="text-align:justify;">{corpo}{credenciais}</div>'

# -----------------------------------------------------------------------------
# Construção da lista por grupo (rms | superintendents | directors)
# -----------------------------------------------------------------------------
def construir_lista_por_grupo(grupo: str) -> Tuple[str, pd.DataFrame]:
    if grupo not in GROUP_MAP:
        raise ValueError(f"Grupo inválido: {grupo}. Use: {list(GROUP_MAP.keys())}")

    meta = GROUP_MAP[grupo]
    pwd_section = SECRETS.get(meta["pwd_section"], {})
    email_section = SECRETS.get(meta["email_section"], {})
    assunto = meta["assunto"]

    lista = []
    for nome, senha in pwd_section.items():
        email = email_section.get(nome)
        if not email:
            # se faltar e-mail para alguém, pula com aviso
            print(f"[AVISO] Sem e-mail para '{nome}' em [{meta['email_section']}]. Pulando.")
            continue

        # por padrão, usamos o próprio nome como login (mantém consistência com secrets)
        login = nome
        corpo = meta["template_texto"].format(NOME=nome)
        corpo_html = _justificar_e_inserir_login(corpo, nome, login, senha)
        html_final = _build_email_html(assunto, corpo_html)

        lista.append(
            {
                "perfil": grupo,
                "nome_destinatario": nome,
                "email_destinatario": email,
                "login": login,
                "senha": senha,
                "corpo_do_email": html_final,
            }
        )

    df = pd.DataFrame(lista)
    return assunto, df

# -----------------------------------------------------------------------------
# Utilidades: salvar Excel e enviar/abrir no Outlook
# -----------------------------------------------------------------------------
def salvar_excel_validacao(df: pd.DataFrame, path: str = "validacao_emails.xlsx"):
    cols = ["perfil", "nome_destinatario", "login", "senha", "corpo_do_email"]
    df[cols].to_excel(path, index=False)
    print(f"Arquivo de validação gerado: {path}")

def mostrar_exemplar_outlook(email: str, assunto: str, html: str):
    outlook = win32.Dispatch("Outlook.Application")
    mail = outlook.CreateItem(0)
    mail.SentOnBehalfOfName = EMAIL_USER
    mail.To = email
    mail.Subject = assunto
    mail.HTMLBody = html
    mail.Display()

def enviar_todos_outlook(df: pd.DataFrame, assunto: str, batch_size: int = 10):
    outlook = win32.Dispatch("Outlook.Application")
    total = len(df)
    for idx, row in enumerate(df.itertuples(index=False), start=1):
        mail = outlook.CreateItem(0)
        mail.SentOnBehalfOfName = EMAIL_USER
        mail.To = row.email_destinatario
        mail.Subject = assunto
        mail.HTMLBody = row.corpo_do_email
        mail.Display()

        print(f"[{idx}/{total}] E-mail preparado para {row.nome_destinatario} <{row.email_destinatario}>")

        if idx % batch_size == 0 and idx < total:
            resp = input(
                f"{idx} e-mails abertos. Digite 'CONTINUAR' para abrir os próximos {batch_size}, ou outra tecla para parar: "
            ).strip().upper()
            if resp != "CONTINUAR":
                print("Processo interrompido pelo usuário.")
                break

# -----------------------------------------------------------------------------
# Execução
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    # escolha aqui o grupo que deseja disparar:
    # opções: "rms", "superintendents", (opcional) "directors"
    grupo = "superintendents"  # <-- altere para "superintendents" quando quiser

    assunto, df_emails = construir_lista_por_grupo(grupo)
    salvar_excel_validacao(df_emails)
    enviar_todos_outlook(df_emails, assunto, batch_size=10)
