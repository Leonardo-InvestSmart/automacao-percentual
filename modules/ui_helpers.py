import streamlit as st
from PIL import Image
import os
import base64

def apply_theme():
    st.set_page_config(
        page_title="My Commission",
        page_icon="assets/simbolo_roxo.svg",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;700&display=swap');
        html, body, [class*="css"] {
            font-family: 'Montserrat', sans-serif !important;
            background-color: #111111;
            color: #f9f1ee !important;
        }
        /* 1) Centraliza st.dataframe e st.table */
        div[data-testid="stDataFrame"] th,
        div[data-testid="stDataFrame"] td,
        div[data-testid="stTable"] th,
        div[data-testid="stTable"] td {
        text-align: center !important;
        }

        /* 2) Centraliza o DataEditor (ag-Grid) */
        div[data-testid="stDataEditor"] .ag-cell,
        div[data-testid="stDataEditor"] .ag-header-cell-label {
        justify-content: center !important;
        }
        header .stMarkdown {
            background-color: #9966ff;
            color: #f9f1ee !important;
            padding: 0.5rem 1rem;
            border-bottom: 3px solid #ecff70;
        }
        /* Remove o botão de fechar a sidebar */
        button[title="Close sidebar"] {
            display: none !important;
        }
        .title-text h1 {
            color: #9966ff !important;
        }
        h2, h3 {
            color: #9966ff;
        }
        .stButton>button {
            background-color: #9966ff !important;
            color: #f9f1ee !important;
            border: 1px solid #121212 !important;
            border-radius: 0.25rem;
            padding: 0.5rem 1rem;
            margin: 0 0.25rem;
        }

        .stButton>button:hover {
            background-color: #ecff70 !important;
            color: #111111 !important;
            border: 1px solid #121212 !important;
        }
        div[data-testid="stHorizontalBlock"] {
            gap: 0.5rem !important;
        }
        div[data-testid="stDataEditor"] .ag-header-cell,
        div[data-testid="stDataEditor"] .ag-header-cell-label,
        div[data-testid="stDataEditor"] .ag-header {
            background-color: white !important;
            color: black !important;
            font-weight: bold;
            justify-content: center !important;
        }
        .stDataFrame td {
            font-size: 0.95rem;
            color: #f9f1ee;
        }
        div[data-testid="stDataEditor"] .ag-header-cell-label,
        div[data-testid="stDataEditor"] .ag-header-row {
            background-color: #9966ff !important;
            color: #f9f1ee !important;
        }
        /* Realça células modificadas em amarelo com texto preto */
        div[data-testid="stDataEditor"] .ag-cell.ag-cell--modified {
            background-color: #ecff70 !important;
            color: #111111 !important;
        }
        .stError, .stError p {
            background-color: #f8d7da !important;
            color: #721c24 !important;
            border-left: 5px solid #f5c6cb;
        }
        .stSuccess, .stSuccess p {
            background-color: #ecff70 !important;
            color: #111111 !important;
            border-left: 5px solid #abde4d;
        }
        .stInfo, .stInfo p {
            background-color: #d5bfff !important;
            color: #000000 !important;
            border-left: 5px solid #d5bfff !important;
        }
        /* Centraliza os itens do menu lateral (radio) */
        section[data-testid="stSidebar"] .block-container {
            display: flex;
            flex-direction: column;
            align-items: center;
        }

        section[data-testid="stSidebar"] .stRadio {
            text-align: center;
        }

        /* Faz cada botão da sidebar ocupar toda a largura e dar espaçamento */
        section[data-testid="stSidebar"] .stButton > button {
            width: 100% !important;
            margin-bottom: 0.1rem !important;
        }

        </style>
        """,
        unsafe_allow_html=True
    )

def rodape_customizado():
    st.markdown(
        """
        <style>
        section.main {
            padding-bottom: 90px; /* garante espaço para o rodapé fixo */
        }

        .custom-footer {
            position: fixed;
            bottom: 0;
            left: calc(14rem + 1rem); /* alinha com o conteúdo, não com a tela */
            right: 0;
            background-color: #d5bfff;
            color: #000000;
            text-align: center;
            font-size: 15px;
            padding: 10px 0 4px;
            z-index: 999;
            line-height: 1.4;
        }

        .custom-footer b {
            font-size: 15px;
            font-weight: 700;
        }
        </style>

        <div class="custom-footer">
            © 2025 InvestSmart – Todos os direitos reservados. <br>
            <b>Made by Comissões</b>
        </div>
        """,
        unsafe_allow_html=True
    )

def adicionar_logo_sidebar():
    caminho_logo = os.path.join("assets", "investsmart_horizontal_branco.png")
    if os.path.exists(caminho_logo):
        logo = Image.open(caminho_logo)
        with st.sidebar:
            st.image(logo, use_container_width=True)

def mostrar_data_editor(df_base, disabled_cols=None):
    df = df_base.copy().astype(str)
    disabled = disabled_cols or []
    column_config = {}
    for col in df.columns:
        column_config[col] = st.column_config.TextColumn(
            col, disabled=(col in disabled)
        )
    return st.data_editor(
        df,
        num_rows="fixed",
        use_container_width=True,
        hide_index=True,
        column_config=column_config
    )

def mostrar_tutorial_inicial():
    st.title("Bem-vindo ao InvestSmart Percentuais!")
    st.write("Assista ao vídeo abaixo para aprender a usar a plataforma:")

    # 1) lê os bytes
    with open("assets/Tutorial_1.mp4", "rb") as f:
        video_bytes = f.read()

    # 2) converte para base64
    b64 = base64.b64encode(video_bytes).decode()

    # 3) monta um HTML <video> inline
    video_html = f"""
    <video controls style="max-width: 100%; height: auto;">
      <source src="data:video/mp4;base64,{b64}" type="video/mp4">
      Seu navegador não suporta vídeo em HTML5.
    </video>
    """

    # 4) injeta o HTML diretamente
    st.markdown(video_html, unsafe_allow_html=True)

    st.write("---")
    st.subheader("Visão Geral das Funcionalidades")
    st.markdown("""
    - **Gestão de Percentuais:** Ajuste taxas de cada assessor  
    - **Validação:** Diretores aprovam reduções  
    - **Painel Analítico:** Métricas e gráficos  
    """)
    if st.button("Entendi, continuar"):
        st.session_state.first_login = False

def pagina_ajuda():
    
    st.write("Reveja o tutorial e encontre respostas às dúvidas mais comuns.")

    # Vídeo Tutorial embutido via HTML5
    st.subheader("Vídeo Tutorial")
    with open("assets/Tutorial_1.mp4", "rb") as f:
        video_bytes = f.read()
    b64 = base64.b64encode(video_bytes).decode()
    video_html = f"""
    <video controls style="max-width:100%;height:auto;">
      <source src="data:video/mp4;base64,{b64}" type="video/mp4">
      Seu navegador não suporta vídeo em HTML5.
    </video>
    """
    st.markdown(video_html, unsafe_allow_html=True)

    # Busca no FAQ
    search_term = st.text_input("🔍 Buscar no FAQ")

    # Estrutura de FAQ
    faqs = [
        {"section": "1. Login e Autenticação",
         "question": "Como faço login na plataforma?",
         "answer": "Informe seu **nome e sobrenome** (como cadastrado) e a **senha**:\n"
                   "- Líder: código OTP enviado por e-mail\n"
                   "- Diretor: senha fixa"},
        {"section": "1. Login e Autenticação",
         "question": "Esqueci ou não recebi o código OTP.",
         "answer": "Clique em **Limpar Alterações** na tela de login para reiniciar o fluxo, solicite novo código e verifique spam. Se persistir, contate suporte@investsmart.com.br."},
        {"section": "1. Login e Autenticação",
         "question": "Posso alterar minha senha de Diretor?",
         "answer": "Não há autoatendimento; solicite troca ao time de TI."},
        {"section": "2. Gestão de Percentuais",
         "question": "O que é “Teto de Percentuais”?",
         "answer": "Limite máximo permitido para cada produto em sua filial."},
        {"section": "2. Gestão de Percentuais",
         "question": "Como altero o percentual de um assessor?",
         "answer": "1. Acesse **Gestão de Percentuais**\n"
                   "2. Selecione sua filial\n"
                   "3. Altere o valor na célula desejada\n"
                   "4. Clique em **💾 Salvar alterações**"},
        {"section": "2. Gestão de Percentuais",
         "question": "Por que aparece “excede o teto”?",
         "answer": "Você tentou usar valor acima do teto. Use **Limpar Erros** ou ajuste para ≤ teto."},
        {"section": "2. Gestão de Percentuais",
         "question": "Qual a diferença entre “Limpar Alterações” e “Limpar Erros”?",
         "answer": "- **Limpar Alterações:** desfaz **todas** as mudanças desde o último salvar.\n"
                   "- **Limpar Erros:** reverte apenas células fora do teto, mantendo alterações válidas."},
        {"section": "3. Validação de Reduções",
         "question": "Por que reduções não são aplicadas imediatamente?",
         "answer": "Toda redução (valor menor que o atual) precisa de aprovação do Diretor."},
        {"section": "3. Validação de Reduções",
         "question": "Como acompanho o status da solicitação?",
         "answer": "1. Após inserir o OTP, verá mensagem de encaminhamento ao Diretor.\n"
                   "2. Diretor aprova/recusa em **Validação**.\n"
                   "3. Você recebe e-mail com resultado."},
        {"section": "3. Validação de Reduções",
         "question": "Recebi e-mail de recusa — e agora?",
         "answer": "Verifique o comentário do Diretor, renegocie se necessário e faça nova solicitação em **Gestão de Percentuais**."},
        {"section": "4. Painel Analítico",
         "question": "Como usar o Painel Analítico?",
         "answer": "1. Clique em **Painel Analítico**\n"
                   "2. Escolha sua filial (ou todas, se Diretor)\n"
                   "3. Explore gráficos de performance e tendências."},
        {"section": "4. Painel Analítico",
         "question": "Dá para exportar os gráficos?",
         "answer": "Não há exportação nativa; use printscreen ou ferramentas do navegador."},
        {"section": "5. Extrato de Comissões, Recebíveis Futuros e Descontos",
         "question": "O que mostra “Extrato de Comissões”?",
         "answer": "Lista de comissões pendentes e pagas por produto e período."},
        {"section": "5. Extrato de Comissões, Recebíveis Futuros e Descontos",
         "question": "Como vejo “Recebíveis Futuros”?",
         "answer": "Projeção de valores a receber, baseada em vendas e prazos."},
        {"section": "5. Extrato de Comissões, Recebíveis Futuros e Descontos",
         "question": "Para que serve “Descontos”?",
         "answer": "Aplica descontos em comissões (ex.: bonificações) conforme políticas internas."},
        {"section": "6. Vídeo Tutorial e Ajuda",
         "question": "Onde encontro o tutorial em vídeo?",
         "answer": "- Na **tela inicial** após o primeiro login\n- Na página **Ajuda** do menu lateral"},
        {"section": "6. Vídeo Tutorial e Ajuda",
         "question": "Posso rever o tutorial depois?",
         "answer": "Sim, acesse **Ajuda** a qualquer momento."},
        {"section": "7. Notificações por E-mail",
         "question": "Quais e-mails receberei?",
         "answer": "- **Líder:** OTP de login, resumo de alterações, recusa de reduções\n"
                   "- **Diretor:** pedido de validação, confirmação de aprovação\n"
                   "- **Assessor:** resumo de alterações que afetam seus percentuais"},
        {"section": "7. Notificações por E-mail",
         "question": "Não recebi e-mail — o que faço?",
         "answer": "Verifique spam, confirme seu e-mail no Google Sheets e contate suporte."},
        {"section": "8. Suporte e Contato",
         "question": "Onde reporto bugs ou solicito melhorias?",
         "answer": "Envie detalhes para **suporte@investsmart.com.br**."},
        {"section": "8. Suporte e Contato",
         "question": "Preciso de ajuda urgente — com quem falo?",
         "answer": "Contate seu gestor ou equipe de TI via Teams/Slack/WhatsApp corporativo."},
    ]

    # Filtra itens de FAQ pelo termo de busca
    filtered = [
        item for item in faqs
        if search_term.lower() in (item["section"] + item["question"] + item["answer"]).lower()
    ]

    if not filtered:
        st.info("Nenhum resultado encontrado para sua busca.")
    else:
        current_section = None
        for item in filtered:
            if item["section"] != current_section:
                st.markdown(f"### {item['section']}")
                current_section = item["section"]
            st.markdown(
                f"**Q:** {item['question']}  \n"
                f"**A:** {item['answer']}  \n\n"
                f"---"
            )

