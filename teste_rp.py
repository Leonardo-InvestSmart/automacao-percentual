# rp_query_pessoas_periodo.py
import pandas as pd
import sqlalchemy as sa
from urllib.parse import quote_plus
import pyodbc
from datetime import date, timedelta

SERVER   = "tcp:192.168.1.251"
DATABASE = "DB_Bank"
USERNAME = "acesso_dados"
PASSWORD = "340$Uuxwp7XPTOd7Khy"

# ====== período desejado ======
# Deixe como None para usar o mês atual automaticamente
DATA_INICIO = None  # ex.: date(2025, 8, 1)
DATA_FIM    = None  # ex.: date(2025, 9, 1)  (limite superior exclusivo)

# === calcula mês atual se não informar ===
if DATA_INICIO is None or DATA_FIM is None:
    hoje = date.today()
    ini  = date(hoje.year, hoje.month, 1)
    # 1º dia do mês seguinte
    prox_mes = (ini.replace(day=28) + timedelta(days=4)).replace(day=1)
    if DATA_INICIO is None: DATA_INICIO = ini
    if DATA_FIM    is None: DATA_FIM    = prox_mes

# ===== engine (mesmo fix que deu certo) =====
drivers = pyodbc.drivers()
drv_name = next((d for d in drivers if "ODBC Driver 18 for SQL Server" in d), None) \
        or next((d for d in drivers if "ODBC Driver 17 for SQL Server" in d), None) \
        or "SQL Server"
drv_name = drv_name if drv_name.startswith("{") else f"{{{drv_name}}}"

odbc_str = (
    f"DRIVER={drv_name};"
    f"SERVER={SERVER};"
    f"DATABASE={DATABASE};"
    f"UID={USERNAME};"
    f"PWD={PASSWORD};"
    "Encrypt=yes;"
    "TrustServerCertificate=yes;"
    "Connection Timeout=8;"
)
engine = sa.create_engine(f"mssql+pyodbc:///?odbc_connect={quote_plus(odbc_str)}",
                          pool_pre_ping=True, future=True)

# ===== SQL: colunas + conversão robusta de data/hora =====
# dt_atz tenta: dd/mm/aaaa (103), ISO (126), ODBC canonical (121) e conversão padrão.
sql = f"""
WITH Q AS (
    SELECT
        [STATUS],
        [SIGLA],
        [NOME],
        [NOME SOCIAL],
        [NOME COMPLETO],
        [DATA DE ENTRADA],
        [FILIAL/EQUIPE],
        [FUNÇÃO],
        [CÓDIGO XP],
        [E-MAIL BNKRIO],
        [DATA/HORA ATUALIZAÇÃO],

        [% XP],
        [MESA],
        [MESA PRÓPRIA],
        [BULL COTIZADOR],
        [GLOBAL],
        [CâMBIO],
        [CORRETORA],
        [XP SEGUROS],
        [XP BANCOS],
        [ASSET],
        [CRÉDITO],
        [JURIDICO],
        [IMÓVEIS],
        [OUTROS],

        dt_atz = COALESCE(
            TRY_CONVERT(datetime2, [DATA/HORA ATUALIZAÇÃO], 103), -- dd/mm/aaaa ...
            TRY_CONVERT(datetime2, [DATA/HORA ATUALIZAÇÃO], 126), -- ISO8601
            TRY_CONVERT(datetime2, [DATA/HORA ATUALIZAÇÃO], 121), -- ODBC canonical
            TRY_CONVERT(datetime2, [DATA/HORA ATUALIZAÇÃO])       -- sem estilo
        )
    FROM query_pessoas
)
SELECT
    [STATUS],
    [SIGLA],
    [NOME],
    [NOME SOCIAL],
    [NOME COMPLETO],
    [DATA DE ENTRADA],
    [FILIAL/EQUIPE],
    [FUNÇÃO],
    [CÓDIGO XP],
    [E-MAIL BNKRIO],
    [DATA/HORA ATUALIZAÇÃO],

    [% XP],
    [MESA],
    [MESA PRÓPRIA],
    [BULL COTIZADOR],
    [GLOBAL],
    [CâMBIO],
    [CORRETORA],
    [XP SEGUROS],
    [XP BANCOS],
    [ASSET],
    [CRÉDITO],
    [JURIDICO],
    [IMÓVEIS],
    [OUTROS]
FROM Q
WHERE dt_atz >= '{DATA_INICIO:%Y-%m-%d}'
  AND dt_atz <  '{DATA_FIM:%Y-%m-%d}';
"""

with engine.connect() as cn:
    df = pd.read_sql(sql, cn)

print(f"Período: {DATA_INICIO} a {DATA_FIM} (exclusivo)")
print(f"Linhas retornadas: {len(df)}")
print(df.head())
df.to_excel("rp_query_pessoas_periodo.xlsx", index=False)