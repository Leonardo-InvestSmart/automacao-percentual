import streamlit as st
from PIL import Image
import os

def apply_theme():
    st.set_page_config(
        page_title="Comissões InvestSmart",
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
