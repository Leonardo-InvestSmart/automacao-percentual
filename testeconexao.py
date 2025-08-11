import time
import logging
import pandas as pd
from supabase import create_client

# --- CONFIG ---------------------------------------------------------------
SUPABASE_URL = "https://lurmzommxpzqrqcscgwi.supabase.co"
ANON_KEY     = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imx1cm16b21teHB6cXJxY3NjZ3dpIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTEzOTU3MzEsImV4cCI6MjA2Njk3MTczMX0.U5KHz-8livKUl2HddJl9cP_4wCGW5QyDVrx7cqW8ekw"                        # mesma chave que o SmartC usa

EMAIL        = "felisberto.torres@investsmart.com.br"
PASSWORD     = "S3nh4F0rte!123"

TABLE      = "assessores"
CHUNK_SIZE = 1000
# -------------------------------------------------------------------------

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# 1) cliente (HTTPS)
sb = create_client(SUPABASE_URL, ANON_KEY)

# 2) login (gera token 'authenticated' => policy por UID entra em ação)
auth_res = sb.auth.sign_in_with_password({"email": EMAIL, "password": PASSWORD})
assert auth_res.user is not None, f"Falha de autenticação: {auth_res}"

# 3) leitura paginada
rows, start = [], 0
while True:
    end = start + CHUNK_SIZE - 1
    logging.info(f"Lendo {TABLE} linhas {start}..{end}")
    res = sb.table(TABLE).select("*").range(start, end).execute()

    # checagem de erro HTTP/RLS
    status = getattr(res, "status_code", 200)
    if status and status >= 400:
        raise RuntimeError(f"Erro HTTP {status}: {getattr(res, 'error', res)}")

    data = res.data or []
    rows.extend(data)
    if len(data) < CHUNK_SIZE:
        break
    start += CHUNK_SIZE
    time.sleep(0.1)  # pequeno respiro

df = pd.DataFrame(rows)
print("Total linhas:", len(df))
print(df.head())
