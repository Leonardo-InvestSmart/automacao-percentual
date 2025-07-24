import streamlit as st
import pandas as pd
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from collections import defaultdict
import random
from streamlit import column_config
import httpx
import random

from config import *
from modules.ui_helpers import (
  apply_theme,
  mostrar_data_editor,
  adicionar_logo_sidebar,
  rodape_customizado,
  mostrar_tutorial_inicial,
  pagina_ajuda
)
from modules.auth import do_login_stage1, do_login_stage2
from modules.email_service import enviar_codigo_email, send_director_request, enviar_resumo_email, _build_email_html, send_approval_result
from modules.formatters import (
    parse_valor_percentual,
    formatar_percentual_para_planilha,
    formatar_para_exibir
)

from modules.analytics import display_analytics
from modules.db import (
  carregar_filial,
  carregar_assessores,
  carregar_alteracoes,
  inserir_alteracao_log,
  sobrescrever_assessores,
  atualizar_alteracao_log,
  carregar_sugestoes,
  adicionar_sugestao,
  usuario_votou_mes,
  carregar_votos_mensais,
  adicionar_voto,
  supabase
)

gif_urls = [
    "https://i.gifer.com/6md.gif",
    "https://i.gifer.com/yH.gif",
    "https://i.gifer.com/xw.gif",
    "https://i.gifer.com/XOsX.gif",
    "https://i.gifer.com/ZIb4.gif",
    "https://i.gifer.com/14Um.gif",
    "https://i.gifer.com/xt.gif",
    "https://i.gifer.com/VIjf.gif",
    "https://i.gifer.com/bfR.gif",
    "https://i.gifer.com/6ov.gif",
]

@st.cache_data(show_spinner=False)
def get_filiais():
    return carregar_filial()

@st.cache_data(show_spinner=False)
def get_assessores():
    return carregar_assessores()

@st.cache_data(show_spinner=False)
def get_log():
    return carregar_alteracoes()

def main():
    # — Tema e CSS global e sidebar —
    apply_theme()
    adicionar_logo_sidebar()

    # — Inicializa session_state para autenticação e página ativa —
    st.session_state.setdefault("autenticado", False)
    st.session_state.setdefault("login_stage", 1)
    st.session_state.setdefault("show_limpar_erros", False)
    st.session_state.setdefault("awaiting_verification", False)

    # — Login em 2 etapas —  
    if not st.session_state.get("autenticado", False):
        if st.session_state.login_stage == 1:
            do_login_stage1()
        else:
            do_login_stage2()
        return 
    
    # — Tutorial inicial (primeiro acesso) —
    if "first_login" not in st.session_state:
        st.session_state.first_login = True

    if st.session_state.first_login:
        mostrar_tutorial_inicial()
        return

    # 1) tente carregar tudo do banco…
    try:
        df_filial     = get_filiais()
        df_assessores = get_assessores()
        df_log        = get_log()
    except httpx.RemoteProtocolError:
        # 2) mostre erro amigável e pare o app sem stack-trace
        st.error(
            "Tivemos um erro inesperado na conexão. "
            "Por favor, reinicie o aplicativo."
        )
        st.stop()

    # — Define colunas fixas e percentuais —
    cols_fixos = ["SIGLA", "CPF", "NOME", "EMAIL", "FILIAL", "FUNCAO"]
    col_perc = [
        c for c in df_assessores.columns
        if c not in cols_fixos       # tira as fixas
        and c != "ID"              # tira também o ID
        and isinstance(c, str)
        and c.strip() != ""
    ]

    # — Filiais do usuário (Líder ou Diretor) e DataFrame de filiais correspondentes —
    nome_usuario = st.session_state.dados_lider["LIDER"]
    if st.session_state.role == "director":
        df_filial_lider = df_filial[
            df_filial["DIRETOR"].str.strip().str.upper() == nome_usuario.strip().upper()
        ]
    else:
        df_filial_lider = df_filial[
            df_filial["LIDER"].str.strip().str.upper() == nome_usuario.strip().upper()
        ]
    filiais_do_lider = (
        df_filial_lider["FILIAL"]
        .dropna()
        .str.strip()
        .unique()
        .tolist()
    )
    filiais_do_lider.sort()

    # — Define lista de páginas e estado padrão —
    pages = [
        "Gestão de Percentuais",
        "Validação",
        "Painel Analítico",
        "Sugestão de Melhoria",
        "Ajuda e FAQ",
        "Spoiler BeSmart (Em Construção)"
    ]
    if "pagina" not in st.session_state:
        st.session_state.pagina = pages[0]

    # — Menu lateral personalizado —
    st.sidebar.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Barlow:wght@600&display=swap');
        .menu-nav {
            font-family: 'Barlow', sans-serif;
            font-size: 18px;
            font-weight: 600;
            color: white;
            margin-top: 1rem;
            margin-bottom: 1rem;
            text-align: center;
        }
        /* Faz cada botão ocupar 100% e ter borda preta */
        section[data-testid="stSidebar"] .stButton > button {
            width: 100% !important;
            margin-bottom: 0.5rem !important;
            border: 1px solid #000 !important;
        }
        </style>
        <div class="menu-nav">Menu de navegação</div>
        """,
        unsafe_allow_html=True
    )
    for p in pages:
        if st.sidebar.button(p, key=p):
            st.session_state.pagina = p
    pagina = st.session_state.pagina

    # — Título dinâmico no topo da área principal —
    page_icons = {
        "Gestão de Percentuais":  "💼",
        "Painel Analítico":       "📊",
        "Validação":              "✅",
        "Sugestão de Melhoria":   "💡",
        "Ajuda e FAQ":            "❓",
        "Spoiler BeSmart (Em Construção)":        "📢"
    }
    icon = page_icons.get(pagina, "")
    st.markdown(
        f"<h1 style='color: black; margin-bottom: 1rem;'>{icon} {pagina}</h1>",
        unsafe_allow_html=True
    )

    if pagina not in ["Ajuda e FAQ", "Sugestão de Melhoria"]:
        # — Seletor de filial com label no mesmo estilo da saudação —
        st.markdown(
            """
            <h4 style="
                font-family: 'Barlow', sans-serif;
                font-size: 18px;
                margin-top: 0rem;
                margin-bottom: -2.7rem;  /* diminui espaçamento */
                font-weight: 200;
            ">
            Selecione a filial para gerenciar
            </h4>
            """,
            unsafe_allow_html=True
        )
        # — se não tiver nenhuma, avisa e para o fluxo —
        if not filiais_do_lider:
            st.warning("Nenhuma filial disponível para este usuário.")
            st.stop()

        # — selectbox com a primeira filial já selecionada por padrão —
        selected_filial = st.selectbox(
            "", 
            filiais_do_lider,
            key="filial_selecionada",
            index=0   # pré-seleciona a primeira da lista ordenada
        )
        # — Saudação —
        st.markdown(f"Olá, **{nome_usuario}**! Você está gerenciando a filial **{selected_filial}**.")
    else:
        # Em “Ajuda” não precisamos de filial
        selected_filial = None



    if pagina == "Gestão de Percentuais":

        html = """
        <div style="
            background-color: #ebff70;
            color: #000;
            padding: 0.75rem 1rem;
            border-radius: 0.25rem;
            border-left: 5px solid #ebff70;
            margin-bottom: 1rem;
        ">
        As alterações de percentuais só serão aceitas até o <strong>dia 08</strong> do mês corrente.
        Após essa data, as alterações só serão aplicadas no próximo mês.
        </div>
        """
        st.markdown(html, unsafe_allow_html=True)


        # 1) Teto de Percentuais
        st.subheader("Teto de Percentuais para esta Filial")
        teto_row = df_filial_lider[
            df_filial_lider["FILIAL"].str.strip().str.upper() == selected_filial.strip().upper()
        ].iloc[0]
        df_teto = pd.DataFrame([{
            "FILIAL": teto_row["FILIAL"],
            **{
                p: formatar_para_exibir(teto_row[p])
                for p in col_perc
                if p in teto_row.index and p != "ID"
            }
        }])
        mostrar_data_editor(df_teto, disabled_cols=df_teto.columns.tolist())

        # 2) Percentuais dos assessores (sem CPF, EMAIL nem ID)
        st.subheader("Percentuais dos Assessores da sua Filial")
        df_ass_filial = df_assessores[
            df_assessores["FILIAL"].str.strip().str.upper() == selected_filial.strip().upper()
        ].copy()
        for p in col_perc:
            df_ass_filial[p] = df_ass_filial[p].apply(formatar_para_exibir)

        df_ass_filial = df_ass_filial.drop(columns=["ID"], errors="ignore")
        fixed       = [c for c in cols_fixos if c not in ["CPF", "EMAIL", "ID"]]
        percent     = col_perc.copy()
        display_cols = fixed + percent
        df_editor_initial = df_ass_filial[display_cols].copy()

        if ("last_filial" not in st.session_state
            or st.session_state.last_filial != selected_filial):
            st.session_state.last_filial = selected_filial
            st.session_state.df_current  = df_editor_initial.copy()

        # 3) Editor dentro de um form: só reruna ao submeter
        with st.form("percentual_form"):
            disabled = [c for c in display_cols if c not in col_perc]
            df_edited = mostrar_data_editor(
                st.session_state.df_current,
                disabled_cols=disabled
            )
            st.session_state.df_current = df_edited

            submitted = st.form_submit_button("💾 Salvar alterações")
            reset_all = st.form_submit_button("🧹 Limpar Alterações")

        # 4) Ao clicar em Salvar alterações
        if submitted:
            gif_placeholder = st.empty()
            try:
                gif_choice = random.choice(gif_urls)
                gif_placeholder.image(gif_choice, width=90)

                agora, alteracoes, erros_teto = (
                    datetime.now().strftime("%d/%m/%Y às %H:%M"),  # ✅ dd/mm/YYYY às HH:MM
                    [],
                    []
                )
                df_initial = df_editor_initial.reset_index(drop=True)
                df_new     = st.session_state.df_current.reset_index(drop=True)

                for i in range(len(df_new)):
                    nova     = df_new.loc[i]
                    nome_ass = nova["NOME"]
                    for p in col_perc:
                        old = str(df_initial.at[i, p]).strip()
                        new = str(nova[p]).strip()
                        if old != new:
                            new_f  = parse_valor_percentual(new)
                            teto_f = parse_valor_percentual(str(teto_row[p]).strip())
                            if new_f > teto_f:
                                erros_teto.append(
                                    f"- {p} de {nome_ass} ({new}%) excede o teto de {teto_row[p]}%."
                                )
                            else:
                                pend = df_log[
                                    (df_log["USUARIO"].str.upper() == nome_usuario.strip().upper()) &
                                    (df_log["FILIAL"].str.upper() == selected_filial.strip().upper()) &
                                    (df_log["ASSESSOR"] == nome_ass) &
                                    (df_log["PRODUTO"] == p) &
                                    (df_log["VALIDACAO NECESSARIA"] == "SIM") &
                                    (df_log["ALTERACAO APROVADA"] == "NAO")
                                ]
                                if not pend.empty:
                                    st.error(
                                        f"O percentual **{p}** de **{nome_ass}** "
                                        "já está em análise pelo Diretor e não pode ser alterado."
                                    )
                                    continue
                                alteracoes.append({
                                    "NOME":              nome_ass,
                                    "PRODUTO":           p,
                                    "PERCENTUAL ANTES":  old,
                                    "PERCENTUAL DEPOIS": new
                                })

                if erros_teto:
                    st.session_state.show_limpar_erros = True
                    st.error("⚠️ Algumas alterações não foram salvas:\n" + "\n".join(erros_teto))
                    st.error("Ajuste os valores e tente novamente.")
                elif not alteracoes:
                    st.error("Nenhuma alteração detectada.")
                else:
                    st.session_state.pending_alteracoes = alteracoes

                    # 1) pega agora em SP
                    agora_sp    = datetime.now(ZoneInfo("America/Sao_Paulo")).replace(microsecond=0)
                    # 2) remove o tzinfo para que a string resultante não tenha offset
                    agora_local = agora_sp.replace(tzinfo=None)
                    # 3) monta a string sem offset e armazena
                    st.session_state.pending_agora_raw     = agora_local.isoformat()  
                    st.session_state.pending_agora_display = agora_sp.strftime("%d/%m/%Y às %H:%M")
                    st.session_state.pending_selected_filial = selected_filial
                    code = f"{random.randint(0,999999):06d}"
                    st.session_state.verification_code      = code
                    enviar_codigo_email(
                        st.session_state.dados_lider["EMAIL_LIDER"],
                        nome_usuario,
                        code
                    )
                    st.session_state.awaiting_verification = True
                    st.info("Para prosseguir, insira o código enviado ao seu e-mail.")

            except Exception as err:
                st.error(f"Ocorreu um erro ao salvar alterações: {err}")
            finally:
                gif_placeholder.empty()

        # 5) Ao clicar em Limpar Alterações
        if reset_all:
            st.session_state.df_current        = df_editor_initial.copy()
            st.session_state.show_limpar_erros = False

        # 6) Fase 2: confirmação do código
        if st.session_state.awaiting_verification:
            pendencias = [
                f"{a['PRODUTO']} de {a['PERCENTUAL ANTES']} → {a['PERCENTUAL DEPOIS']}"
                for a in st.session_state.pending_alteracoes
                if parse_valor_percentual(a["PERCENTUAL DEPOIS"]) <
                parse_valor_percentual(a["PERCENTUAL ANTES"])
            ]
            if pendencias:
                st.warning(
                    f"Esse tipo de alteração {'; '.join(pendencias)} "
                    "precisa de aprovação do seu Diretor."
                )
            codigo_input = st.text_input(
                "Código de verificação",
                type="password",
                max_chars=6,
                key="confirm_code"
            )
            if st.button("Confirmar código", key="confirmar_verif"):
                gif_placeholder = st.empty()
                try:
                    gif_choice = random.choice(gif_urls)
                    gif_placeholder.image(gif_choice, width=90)

                    if codigo_input != st.session_state.verification_code:
                        st.error("Código inválido. Tente novamente.")
                        return


                    # 2) grava no log de Alterações (todas as alterações), agora com TIPO
                    linhas = []
                    for a in st.session_state.pending_alteracoes:
                        before_str = a["PERCENTUAL ANTES"]
                        after_str  = a["PERCENTUAL DEPOIS"]
                        is_reducao = parse_valor_percentual(after_str) < parse_valor_percentual(before_str)
                        validacao  = "SIM" if is_reducao else "NAO"
                        tipo       = "REDUCAO" if is_reducao else "AUMENTO"

                        # converte "35,5" → 35.5
                        before_num = float(before_str.replace(",", "."))
                        after_num  = float(after_str.replace(",", "."))

                        linhas.append([
                            st.session_state.pending_agora_raw,
                            nome_usuario,
                            selected_filial,
                            a["NOME"],
                            a["PRODUTO"],
                            before_num,  # agora um número compatível com numeric(5,2)
                            after_num,   # agora um número compatível com numeric(5,2)
                            validacao,
                            "NAO",
                            tipo
                        ])
                    inserir_alteracao_log(linhas)
                    st.cache_data.clear()

                    # 3) separa reduções de não-reduções
                    reducoes = [
                        a for a in st.session_state.pending_alteracoes
                        if parse_valor_percentual(a["PERCENTUAL DEPOIS"]) < parse_valor_percentual(a["PERCENTUAL ANTES"])
                    ]
                    nao_reducoes = [
                        a for a in st.session_state.pending_alteracoes
                        if parse_valor_percentual(a["PERCENTUAL DEPOIS"]) >= parse_valor_percentual(a["PERCENTUAL ANTES"])
                    ]

                    # 4) para reduções, envia pedido ao Diretor (não aplica ainda)
                    if reducoes:
                        # identifica Diretor da filial
                        diretor_nome = df_filial[
                            df_filial["FILIAL"].str.strip().str.upper()
                            == selected_filial.strip().upper()
                        ]["DIRETOR"].iloc[0].strip().upper()
                        diretor_email = st.secrets["director_emails"][diretor_nome]
                        for alt in reducoes:
                            send_director_request(
                                diretor_email,
                                nome_usuario,
                                selected_filial,
                                alt["NOME"],
                                alt["PRODUTO"],
                                alt["PERCENTUAL ANTES"],
                                alt["PERCENTUAL DEPOIS"],
                                "https://smartc.streamlit.app/"
                            )
                        st.info("As alterações foram encaminhadas ao Diretor para validação.")

                    # 5) para não-reduções, aplica imediatamente:
                    if nao_reducoes:
                        for alt in nao_reducoes:
                            produto_col     = alt["PRODUTO"]
                            # 1) parse em decimal (ex: 0.52)
                            percent_decimal = parse_valor_percentual(alt["PERCENTUAL DEPOIS"])
                            # 2) converte para inteiro (ex: 0.52 * 100 → 52)
                            novo_val_int    = int(round(percent_decimal * 100))

                            # 1) Busca ID do assessor pelo nome + filial
                            try:
                                resp = (
                                    supabase
                                    .table("assessores")
                                    .select("ID")
                                    .eq("NOME", alt["NOME"].strip())
                                    .eq("FILIAL", selected_filial.strip().upper())
                                    .single()
                                    .execute()
                                )
                            except Exception as e:
                                st.error(f"Erro ao buscar assessor {alt['NOME']}: {e}")
                                continue

                            # Se não retornou dados, pula
                            if not resp.data:
                                st.error(f"Não achei {alt['NOME']} na filial {selected_filial}.")
                                continue

                            assessor_id = resp.data["ID"]

                            # 2) Atualiza apenas a coluna do produto modificado
                            try:
                                supabase.table("assessores") \
                                    .update({ produto_col: novo_val_int }) \
                                    .eq("ID", assessor_id) \
                                    .execute()
                            except Exception as e:
                                st.error(f"Falha ao atualizar {alt['NOME']} ({produto_col}): {e}")
                                continue

                        # 5a) envia resumo por e-mail ao Líder (HTML)
                        subj_l = f"Resumo de alterações em {selected_filial}"
                        lista_html = "".join(
                            f"<li>{x['NOME']}: {x['PRODUTO']} de {x['PERCENTUAL ANTES']}% → {x['PERCENTUAL DEPOIS']}%</li>"
                            for x in nao_reducoes
                        )
                        conteudo_html_l = f"""
                        <p>Olá {nome_usuario},</p>
                        <p>Foram aplicadas as seguintes alterações em <strong>{selected_filial}</strong>
                        no dia <strong>{st.session_state.pending_agora_display}</strong>:</p>
                        <ul>
                        {lista_html}
                        </ul>
                        """
                        html_l = _build_email_html(subj_l, conteudo_html_l)
                        enviar_resumo_email(
                            [st.session_state.dados_lider["EMAIL_LIDER"]],
                            subj_l,
                            html_l,
                            content_type="HTML"
                        )   

                        # 5b) envia resumo para cada Assessor (com lookup de e-mail)
                        agrup = defaultdict(list)
                        for x in nao_reducoes:
                            agrup[x["NOME"]].append(x)

                        for nome_a, alts in agrup.items():
                            # — Busca o e-mail do assessor no DataFrame original —
                            filtro = (
                                (df_assessores["NOME"].str.strip().str.upper() == nome_a.strip().upper())
                                & (df_assessores["FILIAL"].str.strip().str.upper() == selected_filial.strip().upper())
                            )
                            df_sel = df_assessores.loc[filtro]
                            if df_sel.empty:
                                continue  # se não encontrar, pula este assessor
                            email_a = df_sel["EMAIL"].iloc[0]

                            subj_a  = f"Resumo de alterações em {selected_filial}"
                            lista_html_a = "".join(
                                f"<li>{y['PRODUTO']}: {y['PERCENTUAL ANTES']}% → {y['PERCENTUAL DEPOIS']}%</li>"
                                for y in alts
                            )
                            conteudo_html_a = f"""
                            <p>Olá {nome_a},</p>
                            <p>O líder <strong>{nome_usuario}</strong> realizou as seguintes alterações em
                            <strong>{selected_filial}</strong> no dia <strong>{st.session_state.pending_agora_display}</strong>:</p>
                            <ul>
                            {lista_html_a}
                            </ul>
                            """
                            html_a = _build_email_html(subj_a, conteudo_html_a)
                            enviar_resumo_email(
                                [email_a],
                                subj_a,
                                html_a,
                                content_type="HTML"
                            )


                    st.success(f"Alterações registradas com sucesso em {st.session_state.pending_agora_display}!")
                    st.subheader("Resumo das alterações:")
                    st.dataframe(pd.DataFrame(st.session_state.pending_alteracoes))

                except Exception as err:
                    st.error(f"Ocorreu um erro ao confirmar código: {err}")
                finally:
                    gif_placeholder.empty()

                # 6) limpa flags de sessão
                for k in (
                    "awaiting_verification",
                    "verification_code",
                    "pending_alteracoes",
                    "pending_agora_display",
                    "pending_selected_filial"
                ):
                    st.session_state.pop(k, None)

    elif pagina == "Spoiler BeSmart (Em Construção)":
        # 1) Busca os dados brutos do Supabase
        query = supabase.table("recebiveis_futuros") \
                        .select("data_de_credito,cliente,nome,duracao_com,comissao_bruto,produto,seguradora") \
                        .eq("nome_filial_equipe", selected_filial)
        if st.session_state.role == "director":
            nome_dir = st.session_state.dados_lider["LIDER"]
            query = query.eq("diretor", nome_dir)
        result = query.execute()
        df = pd.DataFrame(result.data)

        # Verifica se o DataFrame está vazio antes de converter colunas
        if df.empty:
            st.info("Não há spoilers BeSmart para esta filial.")
        else:
            # 1) Converte a data
            df['data_de_credito'] = pd.to_datetime(df['data_de_credito'], errors='coerce').dt.date

            # 2) Converte colunas numéricas para float
            df['duracao_com']    = pd.to_numeric(df['duracao_com'],    errors='coerce')
            df['comissao_bruto'] = pd.to_numeric(df['comissao_bruto'], errors='coerce')

            st.info("As informações abaixo são as produções BeSmart vinculadas à sua filial, que estão em apuração. Qualquer erro ou divergência, entre em contato com Comissões.")

            # 3) Filtros — Data & Assessor (estilo Painel Analítico)
            col1, col2 = st.columns(2)
            with col1:
                start_date = st.date_input(
                    "Data de Início",
                    min_value=df['data_de_credito'].min(),
                    max_value=df['data_de_credito'].max(),
                    value=df['data_de_credito'].min()
                )
            with col2:
                end_date = st.date_input(
                    "Data de Término",
                    min_value=df['data_de_credito'].min(),
                    max_value=df['data_de_credito'].max(),
                    value=df['data_de_credito'].max()
                )

            assessores = ["Todos"] + sorted(df['nome'].dropna().unique().tolist())
            selected_assessor = st.selectbox("Filtrar por Assessor", assessores)

            # Aplica filtros
            df = df[
                (df['data_de_credito'] >= start_date) &
                (df['data_de_credito'] <= end_date)
            ]
            if selected_assessor != "Todos":
                df = df[df['nome'] == selected_assessor]

            # Espaçamento antes dos cartões
            st.markdown("<br>", unsafe_allow_html=True)

            # 4) Cartões métricos customizados
            cols = st.columns(5)
            labels = [
                "💰 Faturamento Estimado",
                "📄 Quantidade de Registros",
                "👥 Clientes Únicos",
                "🧑‍💼 Assessores Únicos",
                "🫱🏾‍🫲🏼 Parceiros Únicos"
            ]
            values = [
                f"R$ {df['comissao_bruto'].sum():,.2f}",     # agora somatório numérico
                len(df),
                df['cliente'].nunique(),
                df['nome'].nunique(),
                df['seguradora'].nunique()           # agora média numérica
            ]
            for c, lbl, val in zip(cols, labels, values):
                # Título grande
                c.markdown(
                    f"<div style='font-size:17px; font-weight:bold; margin-bottom:4px;'>{lbl}</div>",
                    unsafe_allow_html=True
                )
                # Valor menor
                c.markdown(
                    f"<div style='font-size:28px; color:#111;'>{val}</div>",
                    unsafe_allow_html=True
                )

            # 5) Linha separadora
            st.markdown("---")

            # 6) Título da tabela
            st.markdown("**Detalhamento dos Spoilers BeSmart - Faturamento e Produções podem variar caso fornecedor ou relações cliente-assessor mudem.**")

            # 7) Renomeia colunas para exibição
            df_display = df.rename(columns={
                'data_de_credito':  'Data de Crédito',
                'cliente':          'Nome do Cliente',
                'nome':             'Assessor',
                'duracao_com':      'Parcela',
                'comissao_bruto':   'Faturamento Estimado',
                'produto':          'Produto',
                'seguradora':       'Seguradora'
            })

            # 8) Formata Faturamento Estimado para “R$ 650,00”
            df_display['Faturamento Estimado'] = (
                df_display['Faturamento Estimado']
                .apply(lambda x: f"R$ {x:,.2f}")
                # converte “,” de milhar → temporário “X”, “.” decimal → “,”, e “X” → “.”
                .str.replace(",", "X")
                .str.replace(".", ",")
                .str.replace("X", ".")
            )

            # 8) Exibe tabela UMA ÚNICA VEZ
            st.dataframe(df_display, use_container_width=True)

    elif pagina == "Painel Analítico":
        display_analytics(
            df_log=df_log,
            df_assessores_filial=df_assessores[
                df_assessores["FILIAL"].str.strip().str.upper() == selected_filial.strip().upper()
            ],
            df_filial_do_lider=df_filial_lider,
            col_perc=col_perc,
            nome_lider=nome_usuario,
            filial_lider=selected_filial,
            is_b2c=False
        )

    elif pagina == "Ajuda e FAQ":
        pagina_ajuda()

    elif pagina == "Sugestão de Melhoria":
        st.markdown("### Deixe sua sugestão de melhoria")
        user = nome_usuario  # já inicializado no topo do app

        # ── 1) Envio de novas sugestões (com reload automático) ──
        if "suggestion_sent" not in st.session_state:
            st.session_state["suggestion_sent"] = False

        nova = st.text_area("Escreva abaixo:")
        # Sugestão de Melhoria (com GIF de loading)
        if not st.session_state["suggestion_sent"]:
            if st.button("Enviar sugestão"):
                gif_placeholder = st.empty()
                try:
                    gif_choice = random.choice(gif_urls)
                    gif_placeholder.image(gif_choice, width=90)
                    if nova.strip():
                        adicionar_sugestao(nova, user)
                        st.cache_data.clear()
                        st.session_state["suggestion_sent"] = True
                        st.success("✅ Sugestão enviada!")
                except Exception as err:
                    st.error(f"Ocorreu um erro ao enviar sugestão: {err}")
                finally:
                    gif_placeholder.empty()
        else:
            st.success("✅ Sugestão enviada!")
            # limpa o flag para que, após este run, o form volte ao normal
            st.session_state["suggestion_sent"] = False

        # ── 2) Votação mensal (voto único por usuário) ──
        suggestions = carregar_sugestoes()              # já puxadas do banco
        options     = [s["SUGESTAO"] for s in suggestions]

        if not usuario_votou_mes(user):
            st.markdown("### Vote na sua sugestão favorita")
            selected_idx = st.radio(
                "Escolha uma opção:",
                list(range(len(options))),
                format_func=lambda i: options[i],
                key="vote_choice"
            )
            if st.button("Confirmar Voto"):
                gif_placeholder = st.empty()
                try:
                    gif_choice = random.choice(gif_urls)
                    gif_placeholder.image(gif_choice, width=90)
                    adicionar_voto(suggestions[selected_idx]["ID"], user)
                    st.cache_data.clear()
                    st.success("✅ Seu voto foi registrado com sucesso!")
                except Exception as err:
                    st.error(f"Ocorreu um erro ao registrar seu voto: {err}")
                finally:
                    gif_placeholder.empty()

        # ── 3) Resultados da votação (após votar) ──
        if usuario_votou_mes(user):
            st.info("Você já votou neste mês! Acompanhe abaixo o ranking dos votos nas sugestões de melhoria")
            st.markdown("### 🏆 Resultados da Votação")

            votos = carregar_votos_mensais()
            total = len(votos)

            # prepara lista de resultados
            results = []
            for s in suggestions:
                cnt = sum(1 for v in votos if v["ID"] == s["ID"])
                pct = (cnt / total * 100) if total else 0
                results.append({
                    "Sugestão":   s["SUGESTAO"],
                    "Votos":      cnt,
                    "Percentual": f"{pct:.1f}%"
                })

            # monta e exibe o DataFrame ordenado
            df_rank = (
                pd.DataFrame(results)
                .sort_values("Votos", ascending=False)
                .reset_index(drop=True)
            )
            df_rank.insert(0, "Posição", [f"{i+1}º" for i in df_rank.index])

            styled = df_rank.style.set_table_styles([
                {"selector": "th.blank",                      "props": [("display", "none")]},
                {"selector": "th.row_heading, td.row_heading", "props": [("display", "none")]},
                {"selector": "th, td",                        "props": [("text-align", "center")]}
            ])

            st.table(styled)


    elif pagina == "Validação":
        st.subheader("Pendências de Validação")
        df_alt = carregar_alteracoes()

        # Exibe só os registros pendentes: redução solicitada, ainda não aprovada,
        # na filial certa, e que NÃO tenham recebido comentário do Diretor
        df_pend = df_alt[
            (df_alt["VALIDACAO NECESSARIA"] == "SIM")
            & (df_alt["ALTERACAO APROVADA"] == "NAO")
            & (df_alt["TIPO"]                == "REDUCAO")  # ← só reduções
            & (df_alt["FILIAL"].astype(str).str.strip().str.upper()
            == selected_filial.strip().upper())
            & (
                df_alt["COMENTARIO DIRETOR"].isna()
                | (df_alt["COMENTARIO DIRETOR"].str.strip() == "")
            )
        ]

        # ── Diretor ──
        if st.session_state.role == "director":
            if df_pend.empty:
                st.info("Não há alterações pendentes para validação.")
            else:
                df_pend = df_pend.copy()

                # 1️⃣ formata TIMESTAMP: converte de UTC para São Paulo e formata
                df_pend["TIMESTAMP"] = (
                    pd.to_datetime(
                        df_pend["TIMESTAMP"],
                        utc=True,
                        errors="coerce"
                    )
                    .dt.tz_convert("America/Sao_Paulo")   # converte de UTC para horário de Brasília
                    .dt.tz_localize(None)                 # remove informação de fuso
                    .dt.strftime("%d/%m/%Y às %H:%M")
                )
                df_pend["Aprovado"] = False
                df_pend["Recusado"] = False
                df_pend["COMENTARIO DIRETOR"] = ""

                df_edit = st.data_editor(
                    df_pend[[
                        "ID",
                        "TIMESTAMP",
                        "USUARIO",
                        "ASSESSOR",
                        "PRODUTO",
                        "PERCENTUAL ANTES",
                        "PERCENTUAL DEPOIS",
                        "Aprovado",
                        "Recusado",
                        "COMENTARIO DIRETOR"
                    ]],
                    column_config={
                        "ID":                  column_config.TextColumn("ID",                 disabled=True),
                        "TIMESTAMP":           column_config.TextColumn("Data e Hora",        disabled=True),
                        "USUARIO":             column_config.TextColumn("Líder",              disabled=True),
                        "ASSESSOR":            column_config.TextColumn("Assessor",           disabled=True),
                        "PRODUTO":             column_config.TextColumn("Produto",            disabled=True),
                        "PERCENTUAL ANTES":    column_config.TextColumn("Percentual Antes",   disabled=True),
                        "PERCENTUAL DEPOIS":   column_config.TextColumn("Percentual Depois",  disabled=True),
                        "Aprovado":            column_config.CheckboxColumn("Aprovado"),
                        "Recusado":            column_config.CheckboxColumn("Recusado"),
                        "COMENTARIO DIRETOR":  column_config.TextColumn("Comentário do Diretor")
                    },
                    hide_index=True,
                    use_container_width=True
                )


                if st.button("Confirmar Validações"):
                    gif_placeholder = st.empty()
                    try:
                        gif_choice = random.choice(gif_urls)
                        gif_placeholder.image(gif_choice, width=90)
                        # 🔄 1) força exclusividade: nunca ambos True
                        df_edit = df_edit.copy()
                        mask_both = df_edit["Aprovado"] & df_edit["Recusado"]
                        # prefere manter “Aprovado” como definitivo em caso de empate
                        df_edit.loc[mask_both, "Recusado"] = False

                        aprovados = df_edit[df_edit["Aprovado"]]
                        recusados = df_edit[df_edit["Recusado"]]

                        # 🔒 2) checa comentário obrigatório para recusa
                        faltam = [
                            i+1
                            for i, row in recusados.iterrows()
                            if not (isinstance(row["COMENTARIO DIRETOR"], str) 
                                    and row["COMENTARIO DIRETOR"].strip())
                        ]
                        if faltam:
                            st.error("Comentário do Diretor é obrigatório para recusa nas solicitações.")
                            st.stop()

                        # 2) Se passou na validação, atualiza planilha Alterações
                        for _, row in df_edit.iterrows():
                            log_id = int(row["ID"])

                            # 1) marca aprovação ou recusa
                            atualizar_alteracao_log(
                                row_id=log_id,
                                coluna="ALTERACAO APROVADA",
                                valor="SIM" if row["Aprovado"] else "NAO"
                            )
                            # 2) anota o comentário do Diretor
                            atualizar_alteracao_log(
                                row_id=log_id,
                                coluna="COMENTARIO DIRETOR",
                                valor=row["COMENTARIO DIRETOR"]
                            )
                            # 3) sinaliza que já não precisa mais de validação
                            atualizar_alteracao_log(
                                row_id=log_id,
                                coluna="VALIDACAO NECESSARIA",
                                valor="NAO"
                            )
                        st.cache_data.clear()
                        lider_email = st.session_state.dados_lider["EMAIL_LIDER"]

                        # envia email de recusa
                        for _, row in recusados.iterrows():
                            assunto = f"Redução recusada em {selected_filial}"
                            conteudo_html_r = f"""
                            <p>Olá {row['USUARIO']},</p>
                            <p>
                            Sua solicitação de redução do produto
                            <strong>{row['PRODUTO']}</strong>
                            de <strong>{row['PERCENTUAL ANTES']}% → {row['PERCENTUAL DEPOIS']}%</strong>
                            em <strong>{selected_filial}</strong> foi
                            <strong style="color:#dc3545;">recusada</strong> pelo Diretor.
                            </p>
                            <p>Comentário do Diretor:<br/>
                            <em>{row['COMENTARIO DIRETOR']}</em>
                            </p>
                            """
                            html_r = _build_email_html(assunto, conteudo_html_r)
                            enviar_resumo_email(
                                [lider_email],
                                assunto,
                                html_r,
                                content_type="HTML"
                            )

                        # envia email de aprovação (HTML)
                        if not aprovados.empty:
                            df_envio = aprovados.copy()
                            df_envio["FILIAL"] = selected_filial

                            # 1) dispara e-mail de aprovação
                            send_approval_result(
                                df_envio,
                                lider_email=lider_email,
                                director_email=st.session_state.dados_lider["EMAIL_LIDER"]
                            )

                            # 2) **ATUALIZA** os percentuais aprovados na tabela Assessores
                            for _, row in df_envio.iterrows():
                                produto_col     = row["PRODUTO"]
                                # 1) parse em decimal
                                percent_decimal = parse_valor_percentual(row["PERCENTUAL DEPOIS"])
                                # 2) inteiro para o DB
                                novo_val_int    = int(round(percent_decimal * 100))

                                try:
                                    resp = (
                                        supabase
                                        .table("assessores")
                                        .select("ID")
                                        .eq("NOME", row["ASSESSOR"].strip())
                                        .eq("FILIAL", selected_filial.strip().upper())
                                        .single()
                                        .execute()
                                    )
                                except Exception as e:
                                    st.error(f"Erro ao buscar assessor {row['ASSESSOR']}: {e}")
                                    continue

                                # Se não retornou dados, pula
                                if not resp.data:
                                    st.error(f"Não achei {row['ASSESSOR']} na filial {selected_filial}.")
                                    continue

                                assessor_id = resp.data["ID"]

                                # agora sim, atualiza pelo ID correto
                                supabase.table("assessores") \
                                    .update({ produto_col: novo_val_int }) \
                                    .eq("ID", assessor_id) \
                                    .execute()

                        st.success(
                            f"{len(aprovados)} aprovação(ões) e {len(recusados)} recusa(s) registradas!"
                        )
                        st.session_state.last_filial = None

                        st.session_state["refresh_validation"] = not st.session_state.get("refresh_validation", False)

                    except Exception as err:
                        st.error(f"Ocorreu um erro ao validar alterações: {err}")
                    finally:
                        gif_placeholder.empty()


        # ── Líder ──
        else:
            if df_pend.empty:
                st.info("Nenhuma solicitação de redução pendente.")
            else:
                df_leader = df_pend.copy()
                # 1. Converte e formata a coluna de timestamp  
                df_leader["Data e Hora"] = (
                    pd.to_datetime(
                        df_leader["TIMESTAMP"],
                        utc=True,
                        errors="coerce"
                    )
                    .dt.tz_convert("America/Sao_Paulo")   # ajusta fuso
                    .dt.tz_localize(None)                 # remove o timezone
                    .dt.strftime("%d/%m/%Y às %H:%M")     # formata dd/mm/YYYY às HH:MM
                )

                # 2. Renomeia as demais colunas
                df_leader = df_leader.rename(columns={
                    "USUARIO":             "Diretor",
                    "ASSESSOR":            "Assessor",
                    "PRODUTO":             "Produto",
                    "PERCENTUAL ANTES":    "Percentual Antes",
                    "PERCENTUAL DEPOIS":   "Percentual Depois",
                    "COMENTARIO DIRETOR":  "Comentário do Diretor",
                })
                def _status(row):
                    # 1) Se já aprovado
                    if row["ALTERACAO APROVADA"] == "SIM":
                        return "Aprovado"
                    # 2) Se reprovado de fato (NAO + comentário não-vazio)
                    comment = row["Comentário do Diretor"]
                    if row["ALTERACAO APROVADA"] == "NAO" and isinstance(comment, str) and comment.strip() != "":
                        return "Recusado"
                    # 3) Senão, continua aguardando  
                    return "Aguardando..."

                df_leader["Resposta Diretor"] = df_leader.apply(_status, axis=1)

                df_leader = df_leader[[
                    "Data e Hora",
                    "Diretor",
                    "Assessor",
                    "Produto",
                    "Percentual Antes",
                    "Percentual Depois",
                    "Resposta Diretor",
                    "Comentário do Diretor"
                ]]

                st.dataframe(
                    df_leader,
                    use_container_width=True,
                    hide_index=True
                )

    else:
        st.markdown(
            """
            <div style="
                background-color: #d5bfff;
                color: #000000;
                border-left: 5px solid #9966ff;
                padding: 0.75rem 1rem;
                border-radius: 0.25rem;
                margin: 1rem 0;
                font-size: 1rem;
            ">
                Página em construção…
            </div>
            """,
            unsafe_allow_html=True
        )

    rodape_customizado()

if __name__ == "__main__":
    main()