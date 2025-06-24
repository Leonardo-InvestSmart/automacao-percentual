import os
import json
import re
import random
import pandas as pd
import streamlit as st
import msal
import requests
from dotenv import load_dotenv
import gspread
import altair as alt
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import unicodedata

# ------------------------------------------------
# 0) INJEÇÃO DE CSS PARA IDENTIDADE VISUAL PERSONALIZADA
# ------------------------------------------------
st.set_page_config(
    page_title="Comissões InvestSmart",
    page_icon="assets/simbolo_roxo.svg",
    layout="wide"
)

# 1) IMPORTAÇÃO DA FONTE E APLICAÇÃO DE CORES PERSONALIZADAS
st.markdown(
    """
    <style>
    /* 1. Importar Montserrat */ 
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;700&display=swap');

    /* 2. Fonte global, cor de fundo e cor de texto padrão */
    html, body, [class*="css"] {
        font-family: 'Montserrat', sans-serif !important;
        background-color: #111111; /* Fundo preto */
        color: #f9f1ee !important;  /* Texto branco contrastante */
    }

    /* 3. Barra de título (header) */
    header .stMarkdown {
        background-color: #9966ff; /* Roxo primário */
        color: #f9f1ee !important; /* Texto branco contrastante */
        padding: 0.5rem 1rem;
        border-bottom: 3px solid #ecff70; /* Amarelo auxiliar */
    }

    /* 4. Título principal */
    .title-text h1 {
        color: #9966ff !important; /* Roxo primário */
    }

    /* 5. Subtítulos (h2, h3) */
    h2, h3 {
        color: #9966ff; /* Roxo primário */
    }

    /* 6. Botões padrão do Streamlit */
    .stButton>button {
        background-color: #9966ff !important; /* Roxo primário */
        color: #f9f1ee !important;               /* Texto branco contrastante */
        border: none;
        border-radius: 0.25rem;
        padding: 0.5rem 1rem;
    }
    .stButton>button:hover {
        background-color: #ecff70 !important; /* Amarelo auxiliar no hover */
        color: #111111 !important;            /* Texto preto sobre amarelo */
    }

    /* 7. DataFrame headers (st.dataframe) */
    .stDataFrame th {
        background-color: #9966ff; /* Roxo primário */
        color: #f9f1ee;
    }
    .stDataFrame td {
        font-size: 0.95rem;
        color: #f9f1ee;
    }

    /* 8. DataFrame (novo seletor) para reforçar cabeçalho do st.dataframe */
    div[data-testid="stDataFrame"] th {
        background-color: #9966ff !important;
        color: #f9f1ee !important;
    }

    /* 9. Cabeçalhos do st.data_editor (AG-Grid) */
    div[data-testid="stDataEditor"] .ag-header-cell-label,
    div[data-testid="stDataEditor"] .ag-header-row {
        background-color: #9966ff !important;
        color: #f9f1ee !important;
    }

    /* 10. Alertas e mensagens de erro/sucesso */
    .stError, .stError p {
        background-color: #f8d7da !important;
        color: #721c24 !important;
        border-left: 5px solid #f5c6cb;
    }
    .stSuccess, .stSuccess p {
        background-color: #ecff70 !important; /* Amarelo auxiliar */
        color: #111111 !important;             /* Texto preto para contraste */
        border-left: 5px solid #abde4d;
    }
    </style>
    """,
    unsafe_allow_html=True
)


# Contêiner reservado para o título estilizado
with st.container():
    st.markdown("<div class='title-text'><h1>💼 Gestão de Percentuais - InvestSmart</h1></div>", unsafe_allow_html=True)


# ------------------------------------------------
# 2) CARREGA VARIÁVEIS DE AMBIENTE
# ------------------------------------------------
load_dotenv()

# ------------------------------------------------
# 3) CONFIGURAÇÕES E CREDENCIAIS
# ------------------------------------------------
GOOGLE_SHEETS_KEYFILE = os.getenv(
    "GOOGLE_SHEETS_KEYFILE", "percentual-streamlit-53d33f668e0c.json"
)
SPREADSHEET_ID = os.getenv(
    "SPREADSHEET_ID", "1ViUu0vOyBVknyVT1aQGqIu-LXLBDYfXZLs_YsWk6EEk"
)

# Graph API / OAuth2 settings
TENANT_ID     = os.getenv("AZURE_TENANT_ID")
CLIENT_ID     = os.getenv("AZURE_CLIENT_ID")
CLIENT_SECRET = os.getenv("AZURE_CLIENT_SECRET")
EMAIL_USER    = os.getenv("EMAIL_USER")  # comissoes@investsmart.com.br

# ------------------------------------------------
# 4) FUNÇÕES AUXILIARES DE GOOGLE SHEETS
# ------------------------------------------------
@st.cache_resource(show_spinner=False)
def autenticar_gsheets(keyfile_path: str):
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_name(keyfile_path, scope)
    return gspread.authorize(creds)

@st.cache_data(show_spinner=False)
def carregar_dataframe(worksheet_name: str) -> pd.DataFrame:
    try:
        gc = autenticar_gsheets(GOOGLE_SHEETS_KEYFILE)
        sh = gc.open_by_key(SPREADSHEET_ID)
        ws = sh.worksheet(worksheet_name)
        records = ws.get_all_records(value_render_option="FORMATTED_VALUE")
    except Exception as e:
        st.error(f"Não foi possível abrir a aba '{worksheet_name}': {e}")
        return pd.DataFrame()

    df = pd.DataFrame(records)

    def clean_header(col):
        s = str(col)
        # 1) separa acentos (NFKD) e remove combining chars
        s = unicodedata.normalize("NFKD", s)
        s = "".join(ch for ch in s if not unicodedata.combining(ch))
        # 2) remove todos os control characters (inclui BOM, zero-width, etc)
        s = "".join(ch for ch in s if unicodedata.category(ch)[0] != "C")
        # 3) finalmente strip para tirar espaços normais
        return s.strip()

    df.columns = [ clean_header(c) for c in df.columns ]
    return df

def sobrescrever_worksheet(df: pd.DataFrame, worksheet_name: str):
    try:
        gc = autenticar_gsheets(GOOGLE_SHEETS_KEYFILE)
        sh = gc.open_by_key(SPREADSHEET_ID)
        ws = sh.worksheet(worksheet_name)
        ws.clear()
        ws.update([df.columns.tolist()] + df.values.tolist())
    except Exception as e:
        st.error(f"Falha ao sobrescrever aba '{worksheet_name}': {e}")

def append_worksheet(linhas: list[list], worksheet_name: str):
    try:
        gc = autenticar_gsheets(GOOGLE_SHEETS_KEYFILE)
        sh = gc.open_by_key(SPREADSHEET_ID)
        ws = sh.worksheet(worksheet_name)
        ws.append_rows(linhas, value_input_option="USER_ENTERED")
    except Exception as e:
        st.error(f"Falha ao anexar linhas na aba '{worksheet_name}': {e}")

# ------------------------------------------------
# 5) FUNÇÕES DE TRATAMENTO E ENVIO DE E-MAIL VIA GRAPH
# ------------------------------------------------
def limpar_cpf(texto: str) -> str:
    return re.sub(r"\D", "", texto or "")

def gerar_senha_personalizada(filial: str, nome_lider: str, cpf: str) -> str:
    parte_filial = (filial or "").strip().upper()[:3]
    nome_limpo   = (nome_lider or "").strip().upper()
    parte_lider  = nome_limpo[-3:] if len(nome_limpo) >= 3 else nome_limpo
    cpf_limpo    = limpar_cpf(cpf)
    parte_cpf    = cpf_limpo[:6] if len(cpf_limpo) >= 6 else cpf_limpo
    return parte_filial + parte_lider + parte_cpf

def parse_valor_percentual(val) -> float:
    """
    Converte val (que pode vir como '50', '50%', '0,5', '0.5', 0.50 etc.)
    em float no intervalo [0.0, 1.0]:
      - Se for vazio ou NaN, retorna 0.0
      - Se for string com '%', retira '%' e vírgula/ponto → converte, se >1 divide por 100
      - Se for string sem '%', substitui ',' por '.' e converte; se >1 divide por 100
      - Se for int/float, se >1 divide por 100, senão retorna direto.
    """
    if pd.isna(val) or str(val).strip() == "":
        return 0.0
    if isinstance(val, str):
        s = val.strip().replace("%", "").replace(",", ".")
        if s == "":
            return 0.0
        try:
            num = float(s)
        except ValueError:
            return 0.0
        return (num / 100.0) if num > 1 else num
    try:
        f = float(val)
    except:
        return 0.0
    return (f / 100.0) if f > 1 else f

def formatar_percentual_para_planilha(val) -> str:
    """
    Recebe um valor que pode ser int, float ou string representando um percentual
    (ex.: 40, 40.5, "62,5", "62.5", ou até "625", "675"). Retorna uma string de
    percentual formatada:
      - Inteiros (0–100) → sem casas decimais, ex.: "40"
      - Floats (0.0–100.0) → exibe uma casa decimal com vírgula, ex.: "62,5"
      - Valores originalmente >100 são divididos por 10 antes de formatar:
        → ex.: "675" vira 67.5 e é exibido "67,5"
    """
    if pd.isna(val):
        return ""
    try:
        if isinstance(val, str):
            s = val.replace(",", ".").strip()
            num = float(s) if s != "" else 0.0
        else:
            num = float(val)
    except:
        return str(val)
    if num > 100:
        num = num / 10
    if num.is_integer():
        return str(int(num))
    return f"{num:.1f}".replace(".", ",")

def formatar_para_exibir(val) -> str:
    """
    Formata o valor tal como aparece na planilha (com vírgula e sem multiplicar).
    Objetivo: espelhar exatamente o valor “formatado” que vem do Google Sheets.
    """
    if pd.isna(val):
        return ""
    if isinstance(val, str):
        s = val.strip()
        if "," in s:
            return s
        if "." in s:
            return s.replace(".", ",")
        if s.isdigit():
            num = float(s)
        else:
            return s
    else:
        num = float(val)
    if num > 100:
        num = num / 10
    if num.is_integer():
        return str(int(num))
    return f"{num:.1f}".replace(".", ",")


def enviar_codigo_email(destino: str, codigo: str) -> bool:
    # 1) Obter token via Client Credentials Flow
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

    # 2) Montar payload do e-mail
    mail_payload = {
        "message": {
            "subject": "Seu código de confirmação",
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

    # 3) Enviar via Graph API
    endpoint = f"https://graph.microsoft.com/v1.0/users/{EMAIL_USER}/sendMail"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    resp = requests.post(endpoint, headers=headers, json=mail_payload)
    if resp.status_code == 202:
        return True
    else:
        st.error(f"Falha ao enviar e-mail de confirmação: {resp.status_code} – {resp.text}")
        return False

# ------------------------------------------------
# 6) FUNÇÃO PARA EXIBIR um DataEditor sem índice
# ------------------------------------------------
def mostrar_data_editor(df_base: pd.DataFrame, disabled_cols: list = None):
    """
    Exibe um DataEditor forçando todas as colunas a serem tratadas como texto,
    para permitir que o usuário digite '40.5', '67,5' ou qualquer outro caractere
    — sem que o Streamlit bloqueie entradas não-numéricas.

    Se disabled_cols for informado, essas colunas serão somente-leitura.
    """
    df = df_base.copy().astype(str)
    disabled = disabled_cols or []

    column_config = {}
    for col in df.columns:
        is_disabled = (col in disabled)
        column_config[col] = st.column_config.TextColumn(col, disabled=is_disabled)

    return st.data_editor(
        df,
        num_rows="fixed",
        use_container_width=True,
        hide_index=True,
        column_config=column_config
    )

# ------------------------------------------------
# 7) LÓGICA PRINCIPAL DO APP STREAMLIT
# ------------------------------------------------
def main():
    # inicializa session_state
    if "autenticado" not in st.session_state:
        st.session_state.autenticado = False
    if "login_stage" not in st.session_state:
        st.session_state.login_stage = 1
    if "temp_dados" not in st.session_state:
        st.session_state.temp_dados = {}
    if "dados_lider" not in st.session_state:
        st.session_state.dados_lider = {}
    if "confirmation_code" not in st.session_state:
        st.session_state.confirmation_code = ""

    # === FLUXO DE LOGIN ===
    if not st.session_state.autenticado:
        # Stage 1: usuário + senha
        if st.session_state.login_stage == 1:
            st.subheader("Faça login como Líder de Filial")
            with st.form("login_form"):
                usuario_input = st.text_input(
                    "Usuario", placeholder="Nome e sobrenome do líder"
                )
                senha_input = st.text_input(
                    "Senha", type="password",
                    placeholder="Senha única recebida por e-mail"
                )
                btn = st.form_submit_button("Entrar")
            if btn:
                if not usuario_input or not senha_input:
                    st.warning("Informe usuário e senha para prosseguir.")
                else:
                    df_filial_all = carregar_dataframe("Filial")
                    df_filial_all["CPF_LIDER_CLEAN"] = (
                        df_filial_all["CPF"].astype(str)
                        .apply(limpar_cpf)
                    )
                    nome_upper = usuario_input.strip().upper()
                    df_cand = df_filial_all[
                        df_filial_all["LIDER"].astype(str)
                        .str.strip().str.upper() == nome_upper
                    ]
                    if df_cand.empty:
                        st.error("Usuário não encontrado.")
                    else:
                        validou = False
                        for _, row in df_cand.iterrows():
                            senha_esp = gerar_senha_personalizada(
                                row["FILIAL"], row["LIDER"], row["CPF"]
                            )
                            if senha_input.strip() == senha_esp:
                                validou = True
                                st.session_state.temp_dados = {
                                    "LIDER": row["LIDER"],
                                    "CPF_LIDER": row["CPF"],
                                    "EMAIL_LIDER": row["EMAIL"]
                                }
                                break
                        if validou:
                            code = f"{random.randint(0, 999999):06d}"
                            # envia via Graph API e só avança se sucesso
                            if enviar_codigo_email(row["EMAIL"], code):
                                st.session_state.confirmation_code = code
                                st.info("Código de confirmação enviado para seu e-mail.")
                                st.session_state.login_stage = 2
                        else:
                            st.error("Senha incorreta para este usuário.")
            return

        # Stage 2: confirmação do código
        if st.session_state.login_stage == 2:
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
                else:
                    st.error("Código incorreto. Tente novamente.")
            return
        
    # === A PARTIR DAQUI, USUÁRIO AUTENTICADO ===
    dados = st.session_state.dados_lider
    nome_lider = dados["LIDER"]
    email_lider = dados["EMAIL_LIDER"]
    cpf_clean = limpar_cpf(dados["CPF_LIDER"])

    # Carrega todas as filiais associadas a este líder
    df_filial = carregar_dataframe("Filial")
    df_filial["CPF_LIDER_CLEAN"] = df_filial["CPF"].astype(str).apply(limpar_cpf)
    df_filiais_lider = df_filial[
        (df_filial["LIDER"].astype(str).str.strip().str.upper() == nome_lider.strip().upper()) &
        (df_filial["CPF_LIDER_CLEAN"] == cpf_clean)
    ]

    # Se houver mais de uma filial, apresentar selectbox
    if df_filiais_lider.shape[0] > 1:
        opcoes_filiais = df_filiais_lider["FILIAL"].tolist()
        st.markdown(
            """
            <p style="
                margin-top: 0.5rem;
                margin-bottom: -4rem;
                font-weight: 700;
                font-size: 1rem;
            ">
                Selecione a filial para gerenciar:
            </p>
            """,
            unsafe_allow_html=True
        )
        filial_selecionada = st.selectbox(
            "", 
            options=opcoes_filiais
        )
        filial_lider = filial_selecionada
    else:
        filial_lider = df_filiais_lider.iloc[0]["FILIAL"]

    st.markdown(f"**Olá, {nome_lider}!** Você está gerenciando a filial **{filial_lider}**.")

    # Carrega dados de Assessores e Filial do Líder
    df_assessores = carregar_dataframe("Assessores")
    df_assessores_filial = df_assessores[
        df_assessores["FILIAL"].astype(str).str.strip().str.upper() == filial_lider.strip().upper()
    ].copy()

    df_filial_do_lider = df_filiais_lider[
        df_filiais_lider["FILIAL"].astype(str).str.strip().str.upper() == filial_lider.strip().upper()
    ]
    if df_filial_do_lider.shape[0] != 1:
        st.error("Erro interno: não foi possível identificar sua filial para tetos.")
        st.stop()

    segmento = df_filial_do_lider.iloc[0].get("SEGMENTO", "").strip().upper()
    is_b2c = (segmento == "B2C")

    # === SIDEBAR NAVIGATION ===
    st.sidebar.title("Navegação")
    pagina = st.sidebar.radio(
        "Selecione a página:", 
        ["Gerenciar Percentuais", "Painel Analítico", "Extrato de Comissões (Em construção)", "Recebíveis Futuros (Em construção)"]
    )

    # -----------------------------
    # Aba 1: Gerenciar Percentuais
    # -----------------------------
    if pagina == "Gerenciar Percentuais":
        st.subheader("Teto de Percentuais para esta Filial")
        if is_b2c:
            st.info("Esta filial pertence ao segmento B2C. Não se aplica teto de percentual.")
        else:
            cols_fixos_teto = ["FILIAL","LIDER","EMAIL","CPF"]
            col_teto = [c for c in df_filial_do_lider.columns 
                        if c not in cols_fixos_teto + ["CPF_LIDER_CLEAN","SEGMENTO"]]
            df_teto = df_filial_do_lider[cols_fixos_teto + col_teto].drop(
                columns=["LIDER","EMAIL","CPF"]
            )
            mostrar_data_editor(df_teto, disabled_cols=df_teto.columns.tolist())

        st.subheader("Percentuais dos assessores da sua filial")
        st.info("Altere apenas os valores numéricos nos percentuais (Inteiro: 40 - Decimal: 40,5).")
        
        cols_fixos = ["SIGLA", "CPF", "NOME", "EMAIL", "FILIAL", "FUNCAO"]
        col_perc   = [c for c in df_assessores_filial.columns if c not in cols_fixos]

        # 1) Espelha valores formatados para exibição
        df_assessores_filial_display = df_assessores_filial.copy()
        for c in col_perc:
            df_assessores_filial_display[c] = df_assessores_filial_display[c].apply(formatar_para_exibir)

        # Remove colunas CPF e EMAIL antes de exibir
        display_cols = [c for c in cols_fixos if c not in ["CPF", "EMAIL"]] + col_perc
        df_editor_inicial = df_assessores_filial_display[display_cols].copy()

        df_edited = mostrar_data_editor(
            df_editor_inicial,
            disabled_cols=[c for c in cols_fixos if c not in ["CPF", "EMAIL"]]
        )

        # 2) Botão “Salvar Alterações”
        if st.button("💾 Salvar alterações"):
            erros = []

            # Validação de tetos (se não for B2C)
            if not is_b2c:
                teto_row = df_filial_do_lider.iloc[0]
                for c in col_perc:
                    raw_teto = teto_row[c]
                    teto_num = parse_valor_percentual(raw_teto)
                    for idx, val in df_edited[c].items():
                        num = parse_valor_percentual(val)
                        if num > teto_num:
                            nome_assessor = df_edited.loc[idx, "NOME"]
                            erros.append(
                                f"❌ O assessor '{nome_assessor}' tentou atribuir '{val}' em '{c}', mas o teto é '{raw_teto}'."
                            )

            if erros:
                st.error("Foram encontrados erros na validação de teto:")
                for e in erros:
                    st.write(e)
                st.stop()

            # Detecção de alterações
            df_original = df_assessores_filial.set_index("CPF")
            df_novo = df_edited.copy()
            df_novo["CPF"] = df_assessores_filial["CPF"].values
            df_novo = df_novo.set_index("CPF")

            alteracoes = []
            for cpf, linha_nova in df_novo.iterrows():
                linha_antiga = df_original.loc[cpf]
                for c in col_perc:
                    old_val = linha_antiga[c]
                    new_val = linha_nova[c]
                    old_str = "" if pd.isna(old_val) else str(old_val).strip()
                    new_str = "" if pd.isna(new_val) else str(new_val).strip()
                    if old_str != new_str:
                        alteracoes.append({
                            "CPF":      cpf,
                            "NOME":     linha_nova["NOME"],
                            "PRODUTO":  c,
                            "ANTERIOR": old_str if old_str else None,
                            "NOVO":     new_str if new_str else None
                        })

            if not alteracoes:
                st.info("Nenhuma alteração foi detectada nos percentuais.")
                return

            # Grava log na aba “Alterações”
            timestamp_atual = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            linhas_para_log = []
            for item in alteracoes:
                linhas_para_log.append([
                    timestamp_atual,           # Timestamp
                    nome_lider,                # Usuário (nome do líder)
                    filial_lider,              # Filial
                    item["NOME"],              # Assessor
                    item["PRODUTO"],           # Produto
                    item["ANTERIOR"],          # Percentual Antes
                    item["NOVO"]               # Percentual Depois
                ])
            append_worksheet(linhas_para_log, "Alterações")

            # Sobrescrever aba “Assessores”
            df_assessores_todas = df_assessores.copy()
            df_outras = df_assessores_todas[
                df_assessores_todas["FILIAL"].astype(str).str.strip().str.upper()
                != filial_lider.strip().upper()
            ]

            df_novo_reset = df_novo.reset_index()
            df_novo_reset["FILIAL"] = filial_lider

            # Reinsere EMAIL após edição
            df_email_original = df_assessores_filial.set_index("CPF")["EMAIL"]
            df_novo_reset["EMAIL"] = df_novo_reset["CPF"].map(df_email_original)

            # Formata percentuais para planilha
            for c in col_perc:
                df_novo_reset[c] = df_novo_reset[c].apply(formatar_percentual_para_planilha)

            cols_fixos = ["SIGLA", "CPF", "NOME", "EMAIL", "FILIAL", "FUNCAO"]
            df_completo_filial = df_novo_reset[cols_fixos + col_perc].copy()
            df_outros = df_outras[cols_fixos + col_perc].copy()
            df_atualizado = pd.concat([df_outros, df_completo_filial], ignore_index=True)

            sobrescrever_worksheet(df_atualizado, "Assessores")

            st.success(f"Alterações salvas com sucesso em {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}!")
            st.subheader("Resumo das alterações:")
            resumo_df = pd.DataFrame(alteracoes)
            st.dataframe(resumo_df)


    # -------------------------------
    # Aba 2: Painel Analítico
    # -------------------------------
    elif pagina == "Painel Analítico":
        st.subheader("📊 Painel Analítico da Filial")
        
        # --- 1) Filtro de período ---
        # converte Timestamp para datetime (uma única vez)
        df_log = carregar_dataframe("Alterações")
        df_log["DataHora"] = pd.to_datetime(
            df_log["Timestamp"], format="%d/%m/%Y %H:%M:%S", errors="coerce"
        )
        # seletor de período
        min_date = df_log["DataHora"].min().date()
        max_date = df_log["DataHora"].max().date()
        start_date, end_date = st.date_input(
            "Período de análise", 
            value=[min_date, max_date],
            min_value=min_date,
            max_value=max_date
        )
        # filtra só o que interessa deste líder e filial
        mask = (
            (df_log["Usuario"].str.upper() == nome_lider.strip().upper()) &
            (df_log["Filial"].str.upper()  == filial_lider.strip().upper()) &
            (df_log["DataHora"].dt.date >= start_date) &
            (df_log["DataHora"].dt.date <= end_date)
        )
        df_periodo = df_log.loc[mask].copy()

        # --- 2) KPIs principais ---
        total_alt = df_periodo.shape[0]
        num_ass  = df_assessores_filial.shape[0]
        # alterações no último mês do período selecionado
        one_month_ago = pd.to_datetime(end_date) - pd.DateOffset(months=1)
        alt_last_month = df_periodo[df_periodo["DataHora"] >= one_month_ago].shape[0]

        k1, k2, k3 = st.columns(3)
        k1.metric("🔄 Alterações no período", total_alt)
        k2.metric("👥 Assessores ativos", num_ass)
        k3.metric("📅 Alt. últimos 30 dias", alt_last_month)

        st.markdown("---")

        # --- 3) Gráfico: Alterações ao longo do tempo ---
        if not df_periodo.empty:
            df_time = (
                df_periodo
                .groupby(pd.Grouper(key="DataHora", freq="W"))["Produto"]
                .count()
                .reset_index()
                .rename(columns={"Produto": "Qtd Alterações"})
            )
            chart_time = (
                alt.Chart(df_time)
                .mark_line(point=True)
                .encode(
                    x=alt.X("DataHora:T", title="Semana"),
                    y=alt.Y("Qtd Alterações:Q", title="Alterações")
                )
                .properties(height=250)
            )
            st.altair_chart(chart_time, use_container_width=True)

        # --- 4) Gráfico: Média de percentual por produto ---
        cols_fixos = ["SIGLA","CPF","NOME","EMAIL","FILIAL","FUNCAO"]
        col_perc   = [c for c in df_assessores_filial.columns if c not in cols_fixos]
        df_medias = pd.DataFrame({
            "Produto": col_perc,
            "Média (%)": [
                df_assessores_filial[c].apply(parse_valor_percentual).mean()*100
                for c in col_perc
            ]
        })
        chart_prod = (
            alt.Chart(df_medias)
            .mark_bar()
            .encode(
                x=alt.X("Produto:N", sort="-y"),
                y=alt.Y("Média (%):Q", title="Média (%)"),
                tooltip=["Produto","Média (%)"]
            )
            .properties(height=300)
        )
        st.altair_chart(chart_prod, use_container_width=True)

        # --- 5) Tabela interativa: média por assessor ---
        st.markdown("**Média de percentual por assessor**")
        df_ass_med = pd.DataFrame([
            {
            "Assessor": row["NOME"],
            "Média (%)": f"{(sum(parse_valor_percentual(row[c]) for c in col_perc)/len(col_perc))*100:.1f}"
            }
            for _, row in df_assessores_filial.iterrows()
        ])
        st.dataframe(df_ass_med, use_container_width=True)

        # --- 6) Teto de percentual da filial (métrica) ---
        st.markdown("**Teto de percentuais da filial**")
        if is_b2c:
            st.info("Filial B2C: não se aplica teto de percentual.")
        else:
            teto_vals = df_filial_do_lider.iloc[0][col_perc]
            teto_display = {c: formatar_para_exibir(teto_vals[c]) for c in col_perc}
            # exibe cada produto e seu teto em métricas
            cols_teto = st.columns(len(col_perc))
            for c, col_widget in zip(col_perc, cols_teto):
                col_widget.metric(c, teto_display[c])

        st.markdown("---")
        st.caption("📈 Utilize o seletor de período acima para filtrar suas análises dinamicamente.")

    # -------------------------------
    # Aba 3: Extrato de Comissões
    # -------------------------------
    elif pagina == "Extrato de Comissões":
        st.info("Aqui vai aparecer o Extrato de Comissões — em construção.")

    # -------------------------------
    # Aba 4: Recebíveis Futuros
    # -------------------------------
    elif pagina == "Recebíveis Futuros":
        st.info("Aqui vai aparecer os Recebíveis Futuros — em construção.")

if __name__ == "__main__":
    main()
