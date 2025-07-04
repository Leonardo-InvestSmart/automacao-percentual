import streamlit as st
import pandas as pd
from datetime import datetime
from collections import defaultdict
import random
from streamlit import column_config
import httpx

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
        df_filial     = carregar_filial()
        df_assessores = carregar_assessores()
        df_log        = carregar_alteracoes()
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
        "Ajuda e FAQ"
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
        "Gestão de Percentuais": "💼",
        "Painel Analítico":       "📊",
        "Validação":              "✅",
        "Sugestão de Melhoria":  "💡",
        "Ajuda e FAQ":           "❓"
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
        # 1) Teto de Percentuais
        st.subheader("Teto de Percentuais para esta Filial")
        teto_row = df_filial_lider[
            df_filial_lider["FILIAL"].str.strip().str.upper() == selected_filial.strip().upper()
        ].iloc[0]
        # monta um DataFrame só com FILIAL + col_perc, sem DIRETOR
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
        # aplica formatação de exibição
        for p in col_perc:
            df_ass_filial[p] = df_ass_filial[p].apply(formatar_para_exibir)

        # (A) REMOVA A COLUNA ID do DataFrame de uma vez por todas
        df_ass_filial = df_ass_filial.drop(columns=["ID"], errors="ignore")

        # (B) defina fixed SEM mencionar ID
        fixed = [c for c in cols_fixos if c not in ["CPF", "EMAIL", "ID"]]

        # (C) use col_perc inteiro — ele já não contém "ID"
        percent = col_perc.copy()

        # (D) monte display_cols sem ID
        display_cols = fixed + percent

        # (E) copie só as colunas que você quer mostrar
        df_editor_initial = df_ass_filial[display_cols].copy()

        # inicializa ou reseta o estado atual do editor
        if ("last_filial" not in st.session_state
            or st.session_state.last_filial != selected_filial):
            st.session_state.last_filial   = selected_filial
            st.session_state.df_current    = df_editor_initial.copy()

        # exibe o editor com só as colunas de percentuais editáveis
        disabled = [c for c in display_cols if c not in col_perc]
        df_edited = mostrar_data_editor(
            st.session_state.df_current,
            disabled_cols=disabled
        )
        st.session_state.df_current = df_edited

        # 3) Botões Salvar / Limpar
        btn_salvar, btn_reset_all = st.columns(2)

        with btn_salvar:
            if st.button("💾 Salvar alterações", key="salvar"):
                agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                alteracoes, erros_teto = [], []

                # —— Alinha índices para evitar KeyError —— 
                df_initial = df_editor_initial.reset_index(drop=True)
                df_new     = df_edited.reset_index(drop=True)

                # validações de teto e coleta de alterações
                for i in range(len(df_new)):
                    nova = df_new.loc[i]
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
                                # ── NOVO: checa se já existe pedido pendente para este líder/assessor/produto
                                pend = df_log[
                                    (df_log["USUARIO"].str.strip().str.upper() == nome_usuario.strip().upper()) &
                                    (df_log["FILIAL"].str.strip().str.upper() == selected_filial.strip().upper()) &
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
                                    continue  # pula somente esta alteração
                                # ── Fim da checagem de pendência

                                alteracoes.append({
                                    "NOME":     nome_ass,
                                    "PRODUTO":  p,
                                    "PERCENTUAL ANTES": old,
                                    "PERCENTUAL DEPOIS": new
                                })

                if erros_teto:
                    st.session_state.show_limpar_erros = True
                    st.error("⚠️ Algumas alterações não foram salvas:\n" + "\n".join(erros_teto))
                    st.info("Ajuste os valores e tente novamente.")
                elif not alteracoes:
                    st.info("Nenhuma alteração detectada.")
                else:
                    # dispara código de verificação (fase 1)
                    if not st.session_state.awaiting_verification:
                        st.session_state.pending_alteracoes      = alteracoes
                        st.session_state.pending_agora           = agora
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

        with btn_reset_all:
            if st.button("🧹 Limpar Alterações", key="limpar_tudo"):
                st.session_state.df_current        = df_editor_initial.copy()
                st.session_state.show_limpar_erros = False

        # 4) Fase 2: confirmação do código e aplicação
        if st.session_state.awaiting_verification:
            # lista só as reduções
            pendencias = [
                f"{a['PRODUTO']} de {a['PERCENTUAL ANTES']} → {a['PERCENTUAL DEPOIS']}"
                for a in st.session_state.pending_alteracoes
                if parse_valor_percentual(a["PERCENTUAL DEPOIS"]) < parse_valor_percentual(a["PERCENTUAL ANTES"])
            ]
            if pendencias:
                st.warning(
                    f"Esse tipo de alteração {'; '.join(pendencias)} "
                    "precisa de aprovação do seu Diretor, por ser uma redução de percentual. "
                    "Prossiga com o código e aguarde a confirmação da alteração."
                )
            codigo_input = st.text_input(
                "Código de verificação", type="password", max_chars=6, key="confirm_code"
            )

            if st.button("Confirmar código", key="confirmar_verif"):
                # 1) valida OTP
                if codigo_input != st.session_state.verification_code:
                    st.error("Código inválido. Tente novamente.")
                    return

                # 2) grava no log de Alterações (todas as alterações), agora com TIPO
                linhas = []
                for a in st.session_state.pending_alteracoes:
                    before = a["PERCENTUAL ANTES"]
                    after  = a["PERCENTUAL DEPOIS"]
                    is_reducao = parse_valor_percentual(after) < parse_valor_percentual(before)
                    validacao = "SIM" if is_reducao else "NAO"
                    tipo      = "REDUCAO" if is_reducao else "AUMENTO"

                    linhas.append([
                        st.session_state.pending_agora,
                        nome_usuario,
                        selected_filial,
                        a["NOME"],
                        a["PRODUTO"],
                        before,
                        after,
                        validacao,
                        "NAO",     # ALTERACAO APROVADA
                        tipo       # ← novo campo TIPO
                    ])
                inserir_alteracao_log(linhas)

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
                    subj_l = f"[Líder] Resumo de alterações em {selected_filial}"
                    lista_html = "".join(
                        f"<li>{x['NOME']}: {x['PRODUTO']} de {x['PERCENTUAL ANTES']}% → {x['PERCENTUAL DEPOIS']}%</li>"
                        for x in nao_reducoes
                    )
                    conteudo_html_l = f"""
                    <p>Olá {nome_usuario},</p>
                    <p>Foram aplicadas as seguintes alterações em <strong>{selected_filial}</strong>
                    no dia <strong>{st.session_state.pending_agora}</strong>:</p>
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

                        subj_a  = f"[Você] Resumo de alterações em {selected_filial}"
                        lista_html_a = "".join(
                            f"<li>{y['PRODUTO']}: {y['PERCENTUAL ANTES']}% → {y['PERCENTUAL DEPOIS']}%</li>"
                            for y in alts
                        )
                        conteudo_html_a = f"""
                        <p>Olá {nome_a},</p>
                        <p>O líder <strong>{nome_usuario}</strong> realizou as seguintes alterações em
                        <strong>{selected_filial}</strong> no dia <strong>{st.session_state.pending_agora}</strong>:</p>
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


                    st.success(f"Alterações registradas com sucesso em {st.session_state.pending_agora}!")
                    st.subheader("Resumo das alterações:")
                    st.dataframe(pd.DataFrame(st.session_state.pending_alteracoes))

                # 6) limpa flags de sessão
                for k in (
                    "awaiting_verification",
                    "verification_code",
                    "pending_alteracoes",
                    "pending_agora",
                    "pending_selected_filial"
                ):
                    st.session_state.pop(k, None)
    

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
        if not st.session_state["suggestion_sent"]:
            if st.button("Enviar sugestão"):
                if nova.strip():
                    adicionar_sugestao(nova, user)
                    st.cache_data.clear()              # limpa cache do gsheet
                    st.session_state["suggestion_sent"] = True
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
                adicionar_voto(suggestions[selected_idx]["ID"], user)
                st.cache_data.clear()          # garante dados frescos
                st.success("✅ Seu voto foi registrado com sucesso!")

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

                # 1️⃣ formata TIMESTAMP para “dd/mm/YYYY às HH:MM”
                df_pend["Data e Hora"] = (
                    pd.to_datetime(
                        df_pend["TIMESTAMP"],
                        utc=True,            # aceita ISO-strings com offset
                        errors="coerce"
                    )
                    .dt.tz_localize(None)                # remove informação de fuso
                    .dt.strftime("%d/%m/%Y às %H:%M")    # formata para exibição
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
                        "ID":                  column_config.TextColumn("ID",                disabled=True),
                        "TIMESTAMP":           column_config.TextColumn("Data e Hora",       disabled=True),
                        "USUARIO":             column_config.TextColumn("Líder",             disabled=True),
                        "ASSESSOR":            column_config.TextColumn("Assessor",          disabled=True),
                        "PRODUTO":             column_config.TextColumn("Produto",           disabled=True),
                        "PERCENTUAL ANTES":    column_config.TextColumn("Percentual Antes",  disabled=True),
                        "PERCENTUAL DEPOIS":   column_config.TextColumn("Percentual Depois", disabled=True),
                        "Aprovado":            column_config.CheckboxColumn("Aprovado"),
                        "Recusado":            column_config.CheckboxColumn("Recusado"),
                        "COMENTARIO DIRETOR":  column_config.TextColumn("Comentário do Diretor")
                    },
                    hide_index=True,
                    use_container_width=True
                )

                if st.button("Confirmar Validações"):
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

                    lider_email = st.session_state.dados_lider["EMAIL_LIDER"]

                    # envia email de recusa
                    for _, row in recusados.iterrows():
                        assunto = f"[Validação] Redução recusada em {selected_filial}"
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
                    .dt.tz_localize(None)
                    .dt.strftime("%d/%m/%Y às %H:%M")
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
