# config.py
import json
import streamlit as st

# 1) Credenciais do Google Sheets (Service Account JSON)
#    Espera-se que você tenha colado seu JSON em st.secrets["GOOGLE_CLOUD_CREDENTIALS"]
GOOGLE_SHEETS_CREDENTIALS = json.loads(
    st.secrets["GOOGLE_CLOUD_CREDENTIALS"]
)

# 2) ID da planilha
SPREADSHEET_ID = st.secrets["SPREADSHEET_ID"]

# 3) Azure / OAuth
TENANT_ID     = st.secrets["AZURE_TENANT_ID"]
CLIENT_ID     = st.secrets["AZURE_CLIENT_ID"]
CLIENT_SECRET = st.secrets["AZURE_CLIENT_SECRET"]

# 4) E-mail de envio
EMAIL_USER    = st.secrets["EMAIL_USER"]
