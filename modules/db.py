import pandas as pd
from datetime import datetime
from config import supabase
from postgrest import APIError
import numpy as np, math

def _ler_tabela(tabela: str) -> pd.DataFrame:
    chunk_size = 1000
    todos: list[dict] = []
    start = 0

    while True:
        # busca um “chunk” de até chunk_size linhas
        resp = (
            supabase
            .table(tabela)
            .select("*")
            .range(start, start + chunk_size - 1)
            .execute()
        )
        data = resp.data or []
        if not data:
            break
        todos.extend(data)
        # se veio menos que o tamanho do chunk, acabou
        if len(data) < chunk_size:
            break
        # senão, avança o ponteiro
        start += chunk_size

    # monta o DataFrame com tudo
    df = pd.DataFrame(todos)
    # garante que todos os nomes de coluna sejam strings antes de aplicar upper()
    df.columns = [ str(col).upper() for col in df.columns ]
    return df

def carregar_filial() -> pd.DataFrame:
    return _ler_tabela("filial")

def carregar_assessores() -> pd.DataFrame:
    return _ler_tabela("assessores")

def carregar_alteracoes() -> pd.DataFrame:
    return _ler_tabela("alteracoes")

def inserir_alteracao_log(linhas: list[list]) -> None:
    # 1) Defina as colunas do payload (sem ID)
    cols = [
        "TIMESTAMP",
        "USUARIO",
        "FILIAL",
        "ASSESSOR",
        "PRODUTO",
        "PERCENTUAL ANTES",
        "PERCENTUAL DEPOIS",
        "VALIDACAO NECESSARIA",
        "ALTERACAO APROVADA",
        "TIPO", 
    ]

    # 2) Busque o maior ID atual para gerar novos IDs sequenciais
    try:
        resp = (
            supabase
            .table("alteracoes")
            .select("ID")
            .order("ID", desc=True)
            .limit(1)
            .execute()
        )
        last_rows = resp.data or []
        last_id = last_rows[0]["ID"] if last_rows else 0
    except APIError as e:
        raise Exception(f"Erro ao buscar último ID em alteracoes: {e}")

    # 3) Monte cada registro incluindo o novo ID
    data = []
    for idx, row in enumerate(linhas, start=1):
        rec = dict(zip(cols, row))
        rec["ID"] = last_id + idx
        data.append(rec)

    # 4) Insira no Supabase
    try:
        supabase.table("alteracoes").insert(data).execute()
    except APIError as e:
        raise Exception(f"Erro ao inserir log de alteracoes: {e}")

def sobrescrever_assessores(df: pd.DataFrame) -> None:
    # 1) Troca inf e -inf por None
    df_clean = df.replace({ np.inf: None, -np.inf: None })
    # 2) Troca todos os NaN por None
    df_clean = df_clean.where(pd.notnull(df_clean), None)

    # 3) Se houver coluna ID, garante que seja int e **descarta** linhas sem ID
    if "ID" in df_clean.columns:
        # usa o pd já importado no topo do arquivo
        df_clean["ID"] = df_clean["ID"].apply(
            lambda x: int(x) if pd.notnull(x) else None
        )
        # só mantém quem já tinha ID (não queremos criar novos registros)
        df_clean = df_clean[df_clean["ID"].notnull()]

    # 4) Remove quaisquer floats inválidos antes de enviar
    records = []
    for rec in df_clean.to_dict(orient="records"):
        clean_rec = {}
        for k, v in rec.items():
            if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                clean_rec[k] = None
            else:
                clean_rec[k] = v
        records.append(clean_rec)

    # 5) upsert usando 'id' maiúsculo (é assim que a coluna existe no Postgres)
    for rec in records:
        # separa o ID (chave primária) e retira do dict de atualização
        record_id = rec.pop("ID")

        supabase.table("assessores") \
            .update(rec) \
            .eq("ID", record_id) \
            .execute()

def atualizar_alteracao_log(row_id: int, coluna: str, valor) -> None:
    try:
        supabase.table("alteracoes") \
            .update({coluna: valor}) \
            .eq("ID", row_id) \
            .execute()
    except APIError as e:
        raise Exception(f"Erro ao atualizar log de alteração: {e}")

def carregar_sugestoes() -> list[dict]:
    df = _ler_tabela("sugestoes")
    return df.to_dict(orient="records")

def adicionar_sugestao(texto: str, autor: str) -> None:
    # 1) Busca o maior ID atual
    try:
        resp = (
            supabase
            .table("sugestoes")
            .select("ID")
            .order("ID", desc=True)
            .limit(1)
            .execute()
        )
    except APIError as e:
        raise Exception(f"Erro ao buscar último ID: {e}")

    # 2) Calcula próximo ID
    rows = resp.data or []
    next_id = rows[0]["ID"] + 1 if rows else 1

    # 3) Monta o registro com ID explícito
    registro = {
      "ID": next_id,
      "SUGESTAO": texto,
      "AUTOR":    autor,
      "TIMESTAMP": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    # 4) Insere no Supabase
    try:
        supabase.table("sugestoes").insert(registro).execute()
    except APIError as e:
        raise Exception(f"Erro ao adicionar sugestão: {e}")

def usuario_votou_mes(usuario: str) -> bool:
    df = _ler_tabela("votos")
    agora = datetime.now()
    return any(
      v["USUARIO"] == usuario
      and datetime.fromisoformat(v["TIMESTAMP"]).year  == agora.year
      and datetime.fromisoformat(v["TIMESTAMP"]).month == agora.month
      for v in df.to_dict(orient="records")
    )

def carregar_votos_mensais() -> list[dict]:
    df = _ler_tabela("votos")
    agora = datetime.now()
    return [
      v for v in df.to_dict(orient="records")
      if datetime.fromisoformat(v["TIMESTAMP"]).year  == agora.year
      and datetime.fromisoformat(v["TIMESTAMP"]).month == agora.month
    ]

def adicionar_voto(sugestao_id: int, usuario: str) -> None:
    # Monta o registro usando nomes de coluna idênticos ao do Supabase
    registro = {
      "ID":        sugestao_id,
      "USUARIO":   usuario,
      "TIMESTAMP": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    try:
        supabase.table("votos").insert(registro).execute()
    except APIError as e:
        raise Exception(f"Erro ao adicionar voto: {e}")
