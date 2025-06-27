import gspread
import pandas as pd
import unicodedata
import streamlit as st
import pygsheets
from oauth2client.service_account import ServiceAccountCredentials
from streamlit import error
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

@st.cache_data(ttl=60)
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
        gc = autenticar_gsheets()
        sh = gc.open_by_key(SPREADSHEET_ID)
        ws = sh.worksheet(worksheet_name)
        ws.clear()
        ws.update([df.columns.tolist()] + df.values.tolist())
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
