import pandas as pd
import win32com.client as win32
import re

from modules.db import carregar_filial
from modules.email_service import _build_email_html

def construir_lista_emails():
    # carrega todas as filiais e filtra um único registro por líder
    df = (
        carregar_filial()
        .dropna(subset=["LIDER", "EMAIL"])
        .drop_duplicates(subset=["LIDER"], keep="first")
    )  # :contentReference[oaicite:5]{index=5}

    assunto = "Comunicado Comissões - Lançamento da Plataforma SmartC"

    # texto completo conforme fornecido
    corpo_base = """
    <p>Prezados líderes, tudo bem?</p>
    <p>As 3 diretorias comerciais convidaram vocês para demonstração do novo painel de cadastro de percentuais
    (repasses) desenvolvido pelo time de comissões. No primeiro momento o foco está 100% na gestão do % dos
    assessores das filiais e, com o tempo, adicionaremos mais informações úteis aos gestores. Abaixo alguns
    pontos que vocês devem prestar muita atenção!!!</p>
    <ol>
      <li>O prazo limite para ajustes é todo dia 08 do mês. Esse prazo não será possível estender em nenhuma hipótese,
          então fiquem atentos. Caso você perca esse prazo por qualquer razão, o ajuste do % na plataforma deverá ser
          acompanhado da abertura de um card via Bitrix. Esse painel envia informações já integradas ao nosso novo
          processo interno.</li>
      <li>O acesso à plataforma e seu manuseio exigirá múltiplas confirmações por e-mail. Esse mecanismo, apesar de
          chato, tem por objetivo dar segurança no manuseio de uma informação tão importante que é o % de repasse.
          Todas as alterações mandarão e-mails de confirmação e comprovantes, bem como gerarão o log do responsável
          pela mudança.</li>
      <li>É possível aumentar o repasse sem aprovação do Diretor, porém a redução se dará somente com aprovação do Diretor.
          Ainda não temos um mecanismo de integração automática com o jurídico, então qualquer alteração de repasse nesse
          momento, especialmente a redução, irá requerer do gestor informar ao jurídico para ajuste de contrato via forms.
          Tentaremos melhorar esse processo o quanto antes para trazer mais comodidade.</li>
      <li>Não esqueçam que as sugestões de melhoria podem ser inseridas e votadas na plataforma. É uma forma democrática
          de direcionarmos melhorias.</li>
    </ol>
    <p>Link para acessar a plataforma: <a href="https://smartc.streamlit.app/">
        https://smartc.streamlit.app/<a></p>
    <p>Deixaremos abaixo um link para dúvidas e solicitações sobre a plataforma. Responderemos o mais rápido possível.</p>
    <p>Link para dúvidas: <a href="https://forms.cloud.microsoft/r/KWHcWDe61g">
        https://forms.cloud.microsoft/r/KWHcWDe61g</a></p>
    <p>Segue abaixo o seu login e senha para acesso à plataforma:</p>
    """

    lista = []
    for _, row in df.iterrows():
        nome  = row["LIDER"].strip()
        email = row["EMAIL"].strip()

        # agora login = nome do líder (coluna LIDER)
        login = nome
        # gera senha personalizada (mesmo algoritmo anterior)
        from modules.email_service import gerar_senha_personalizada
        senha = gerar_senha_personalizada(row["FILIAL"], nome, row["CPF"])

        # 1) coloca margem entre itens da lista
        corpo_base_just = re.sub(
            r'<li>',
            '<li style="margin-bottom:10px;">',
            corpo_base
        )

        # 2) envolve o corpo em DIV justificado
        corpo_justificado = f'''
        <div style="text-align:justify;">
        {corpo_base_just}
        <p><strong>Login:</strong> {login}<br>
            <strong>Senha:</strong> {senha}</p>
        <p>Esse acesso é único e exclusivo da filial, por isso pedimos que não compartilhe com terceiros.</p>
        <p>Atenciosamente,</p>
        <p>Equipe de Comissões.</p>
        </div>
        '''

        # 3) usa o template padrão (inclui header e rodapé originais)
        html_email = _build_email_html(assunto, corpo_justificado)



        lista.append({
            "nome_lider": nome,
            "email_lider": email,
            "senha_lider": senha,
            "corpo_do_email": html_email
        })

    return assunto, pd.DataFrame(lista)

def salvar_excel_validacao(df: pd.DataFrame, path: str = "validacao_emails.xlsx"):
    df[["nome_lider", "senha_lider", "corpo_do_email"]].to_excel(path, index=False)
    print(f"Arquivo de validação gerado: {path}")

def mostrar_exemplar_outlook(email: str, assunto: str, html: str):
    outlook = win32.Dispatch('Outlook.Application')
    mail    = outlook.CreateItem(0)

    # envia em nome de comissoes@investsmart.com.br
    mail.SentOnBehalfOfName = "comissoes@investsmart.com.br"

    recipient = mail.Recipients.Add(email)
    recipient.Type = 1   # olTo
    mail.Subject  = assunto
    mail.HTMLBody = html
    mail.Display()



def enviar_todos_outlook(df: pd.DataFrame, assunto: str, batch_size: int = 10):
    outlook = win32.Dispatch('Outlook.Application')
    total = len(df)
    for idx, row in enumerate(df.itertuples(index=False), start=1):
        mail = outlook.CreateItem(0)
        # …lógica de remetente, se houver…
        mail.To       = row.email_lider
        mail.Subject  = assunto
        mail.HTMLBody = row.corpo_do_email
        mail.Display()
        print(f"[{idx}/{total}] E-mail preparado para {row.nome_lider} <{row.email_lider}>")

        # a cada batch_size e-mails, pausa e pergunta
        if idx % batch_size == 0 and idx < total:
            resp = input(f"{idx} e-mails abertos. Digite 'CONTINUAR' para abrir os próximos {batch_size}, ou outra tecla para parar: ").strip().upper()
            if resp != "CONTINUAR":
                print("Processo interrompido pelo usuário.")
                break



if __name__ == "__main__":
    assunto, df_emails = construir_lista_emails()
    salvar_excel_validacao(df_emails)

    # abre todos os e-mails em lotes de 10 e pausa por input entre cada lote
    enviar_todos_outlook(df_emails, assunto, batch_size=10)

