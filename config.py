# config.py
import json
import streamlit as st
from supabase import create_client

# 1) Credenciais do SUPABASE
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# 3) Azure / OAuth
TENANT_ID     = st.secrets["AZURE_TENANT_ID"]
CLIENT_ID     = st.secrets["AZURE_CLIENT_ID"]
CLIENT_SECRET = st.secrets["AZURE_CLIENT_SECRET"]

# 4) E-mail de envio
EMAIL_USER    = st.secrets["EMAIL_USER"]
