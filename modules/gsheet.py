import gspread
import pandas as pd
import unicodedata
import streamlit as st
import pygsheets
from oauth2client.service_account import ServiceAccountCredentials
from streamlit import error
from config import GOOGLE_SHEETS_KEYFILE, SPREADSHEET_ID

@st.cache_resource(show_spinner=False)
def autenticar_gsheets(keyfile_path: str):
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_name(keyfile_path, scope)
    return gspread.authorize(creds)

@st.cache_data(ttl=300)
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