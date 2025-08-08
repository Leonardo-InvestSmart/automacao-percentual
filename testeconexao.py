# -*- coding: utf-8 -*-
import os
import logging
import pandas as pd
import psycopg2
from psycopg2 import sql

# Configuração do logging
logging.basicConfig(level=logging.DEBUG,
                   format="%(asctime)s [%(levelname)s] %(message)s",
                   datefmt="%Y-%m-%d %H:%M:%S")

def conectar_banco_dados():
    """Estabelece conexão com o banco de dados PostgreSQL"""
    try:
        # (A) Remove variáveis de ambiente PG* que podem causar conflitos
        for k in os.environ:
            if k.startswith('PG'):
                os.environ.pop(k, None)

        # (B) Configurações de conexão - verifique cuidadosamente cada valor
        config = {
            'host': "db.lurmzommxpzqrqcscgwi.supabase.co",
            'port': 5432,  # como número inteiro
            'dbname': "postgres",
            'user': "reader_assessores",
            'password': "S3nh4F0rte!123",  # ATENÇÃO: verifique caractere por caractere
            'sslmode': "require",
            'client_encoding': 'UTF-8'  # força encoding UTF-8
        }

        # (C) Verificação manual dos parâmetros
        logging.debug("Parâmetros de conexão:")
        for k, v in config.items():
            if k != 'password':
                logging.debug(f"{k}: {v}")
            else:
                logging.debug(f"{k}: {'*' * len(v)}")

        # (D) Tentativa de conexão com tratamento extra de encoding
        logging.debug("Tentando conexão com o banco de dados...")
        
        # Tentativa 1: Conexão direta
        try:
            conn = psycopg2.connect(**config)
            logging.debug("Conexão estabelecida com sucesso (método direto)!")
            return conn
        except UnicodeError:
            # Tentativa 2: Conexão com string codificada manualmente
            logging.debug("Tentando método alternativo para evitar problemas de encoding...")
            conn_str = (
                f"host={config['host']} "
                f"port={config['port']} "
                f"dbname={config['dbname']} "
                f"user={config['user']} "
                f"password={config['password']} "
                f"sslmode={config['sslmode']}"
            )
            conn = psycopg2.connect(conn_str.encode('ascii', errors='ignore').decode('ascii'))
            logging.debug("Conexão estabelecida com sucesso (método alternativo)!")
            return conn

    except Exception as e:
        logging.error(f"Erro ao conectar ao banco de dados: {str(e)}")
        return None

def consultar_assessores(conn):
    """Executa consulta na tabela de assessores"""
    try:
        query = sql.SQL("SELECT * FROM public.assessores LIMIT 5;")
        df = pd.read_sql(query, conn)
        return df
    except Exception as e:
        logging.error(f"Erro na consulta SQL: {str(e)}")
        return None

# Programa principal
if __name__ == "__main__":
    logging.debug("Iniciando script de conexão...")
    
    conexao = conectar_banco_dados()
    
    if conexao:
        try:
            logging.debug("Obtendo dados dos assessores...")
            dados_assessores = consultar_assessores(conexao)
            if dados_assessores is not None:
                print("\nPrimeiras linhas da tabela de assessores:")
                print(dados_assessores)
            else:
                print("Nenhum dado foi retornado da consulta.")
        finally:
            conexao.close()
            logging.debug("Conexão encerrada com sucesso.")
    else:
        print("Não foi possível estabelecer conexão com o banco de dados.")