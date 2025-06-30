import gspread
import pandas as pd
import unicodedata
import streamlit as st
import pygsheets
from datetime import datetime
from oauth2client.service_account import ServiceAccountCredentials
from streamlit import error
import numpy as np
from config import GOOGLE_SHEETS_CREDENTIALS, SPREADSHEET_ID

@st.cache_resource(show_spinner=False)
def autenticar_gsheets():
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(
        GOOGLE_SHEETS_CREDENTIALS, scope
    )
    return gspread.authorize(creds)

@st.cache_data(ttl=30)
def carregar_dataframe(worksheet_name: str) -> pd.DataFrame:
    try:
        gc = autenticar_gsheets()
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
        # 1) Substitui ±inf por NaN, depois troca tudo por string vazia
        df_clean = (
            df
            .replace([np.inf, -np.inf], np.nan)
            .fillna("")          # ou .fillna(0) se preferir zeros
        )
        # 2) Prepara lista de listas sem valores inválidos
        payload = [df_clean.columns.tolist()] + df_clean.values.tolist()

        gc = autenticar_gsheets()
        sh = gc.open_by_key(SPREADSHEET_ID)
        ws = sh.worksheet(worksheet_name)

        ws.clear()
        ws.update(payload)
    except Exception as e:
        st.error(f"Falha ao sobrescrever aba '{worksheet_name}': {e}")

def append_worksheet(linhas: list[list], worksheet_name: str):
    try:
        gc = autenticar_gsheets()
        sh = gc.open_by_key(SPREADSHEET_ID)
        ws = sh.worksheet(worksheet_name)
        ws.append_rows(linhas, value_input_option="USER_ENTERED")
    except Exception as e:
        st.error(f"Falha ao anexar linhas na aba '{worksheet_name}': {e}")

def update_worksheet_cell(
    worksheet_name: str,
    row: int,
    col: str | int,
    value
):
    try:
        gc = autenticar_gsheets()
        sh = gc.open_by_key(SPREADSHEET_ID)
        ws = sh.worksheet(worksheet_name)
        # se passou nome de coluna, resolve índice
        if isinstance(col, str):
            headers = ws.row_values(1)
            col_index = headers.index(col) + 1
        else:
            col_index = col
        ws.update_cell(row, col_index, value)
    except Exception as e:
        st.error(f"Falha ao atualizar célula em '{worksheet_name}': {e}")

def get_all_suggestions() -> list[dict]:
    df = carregar_dataframe("Sugestões")
    # espera colunas: id, texto, autor, timestamp
    return df.to_dict(orient="records")

def add_suggestion(texto: str, autor: str) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # id = próximo inteiro (baseado em contagem atual)
    sugestoes = get_all_suggestions()
    novo_id = max((s["ID"] for s in sugestoes), default=0) + 1
    append_worksheet([[novo_id, texto, autor, timestamp]], "Sugestões")

def user_voted_this_month(usuario: str) -> bool:
    agora = datetime.now()
    votos = carregar_dataframe("Votos")
    # filtra votos do usuário no mês/ano correntes
    return any(
        (v["Usuario"] == usuario)
        and datetime.fromisoformat(v["Timestamp"]).year == agora.year
        and datetime.fromisoformat(v["Timestamp"]).month == agora.month
        for v in votos.to_dict(orient="records")
    )

def get_monthly_votes() -> list[dict]:
    agora = datetime.now()
    votos = carregar_dataframe("Votos")
    return [
        v for v in votos.to_dict(orient="records")
        if datetime.fromisoformat(v["Timestamp"]).year == agora.year
        and datetime.fromisoformat(v["Timestamp"]).month == agora.month
    ]

def add_vote(sugestao_id: int, usuario: str) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    append_worksheet([[sugestao_id, usuario, timestamp]], "Votos")