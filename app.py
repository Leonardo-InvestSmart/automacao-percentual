import streamlit as st
import pandas as pd
from datetime import datetime
from collections import defaultdict
import random
import base64

from config import *
from modules.ui_helpers import apply_theme, mostrar_data_editor, adicionar_logo_sidebar, rodape_customizado, mostrar_tutorial_inicial, pagina_ajuda
from modules.auth import do_login_stage1, do_login_stage2
from modules.email_service import enviar_codigo_email, send_director_request, enviar_resumo_email
from modules.gsheet import carregar_dataframe, append_worksheet, sobrescrever_worksheet, update_worksheet_cell
from modules.formatters import (
    parse_valor_percentual,
    formatar_percentual_para_planilha,
    formatar_para_exibir
)
from modules.analytics import display_analytics


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

    # — Carrega dados do Google Sheets —
    df_filial     = carregar_dataframe("Filial")
    df_assessores = carregar_dataframe("Assessores")
    df_log        = carregar_dataframe("Alterações")

    # — Define colunas fixas e percentuais —
    cols_fixos = ["SIGLA", "CPF", "NOME", "EMAIL", "FILIAL", "FUNCAO"]
    col_perc   = [c for c in df_assessores.columns if c not in cols_fixos]

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
        "Extrato de Comissões",
        "Recebíveis Futuros",
        "Descontos",
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
        "Extrato de Comissões":   "🧾",
        "Recebíveis Futuros":     "💰",
        "Descontos":              "🏷️",
        "Validação":              "✅",
        "Ajuda e FAQ":           "❓"
    }
    icon = page_icons.get(pagina, "")
    st.markdown(
        f"<h1 style='color: black; margin-bottom: 1rem;'>{icon} {pagina}</h1>",
        unsafe_allow_html=True
    )

    if pagina != "Ajuda e FAQ":
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
            **{"FILIAL": teto_row["FILIAL"]},
            **{p: formatar_para_exibir(teto_row[p]) for p in col_perc}
        }])
        # exibe via DataEditor (índice oculto por padrão)
        mostrar_data_editor(df_teto, disabled_cols=df_teto.columns.tolist())

        # 2) Percentuais dos assessores (sem CPF nem EMAIL)
        st.subheader("Percentuais dos Assessores da sua Filial")
        df_ass_filial = df_assessores[
            df_assessores["FILIAL"].str.strip().str.upper() == selected_filial.strip().upper()
        ].copy()
        # aplica formatação de exibição
        for p in col_perc:
            df_ass_filial[p] = df_ass_filial[p].apply(formatar_para_exibir)
        # backup_principal: remove CPF e EMAIL antes de exibir :contentReference[oaicite:1]{index=1}
        display_cols = [c for c in cols_fixos if c not in ["CPF","EMAIL"]] + col_perc
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
        btn_salvar, btn_reset_all, btn_reset_err = st.columns(3)

        with btn_salvar:
            if st.button("💾 Salvar alterações", key="salvar"):
                agora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                alteracoes, erros_teto = [], []

                # validações de teto e coleta de alterações
                for idx, nova in df_edited.iterrows():
                    nome_ass = nova["NOME"]
                    for p in col_perc:
                        old = str(df_editor_initial.at[idx, p]).strip()
                        new = str(nova[p]).strip()
                        if old != new:
                            new_f  = parse_valor_percentual(new)
                            teto_f = parse_valor_percentual(str(teto_row[p]).strip())
                            if new_f > teto_f:
                                erros_teto.append(
                                    f"- {p} de {nome_ass} ({new}%) excede o teto de {teto_row[p]}%."
                                )
                            else:
                                alteracoes.append({
                                    "NOME":     nome_ass,
                                    "PRODUTO":  p,
                                    "ANTERIOR": old,
                                    "NOVO":     new
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
                            code
                        )
                        st.session_state.awaiting_verification = True
                        st.info("Para prosseguir, insira o código enviado ao seu e-mail.")

        with btn_reset_all:
            if st.button("🧹 Limpar Alterações", key="limpar_tudo"):
                st.session_state.df_current        = df_editor_initial.copy()
                st.session_state.show_limpar_erros = False

        with btn_reset_err:
            if st.session_state.show_limpar_erros and st.button("Limpar Erros", key="limpar_erros"):
                df_tmp = st.session_state.df_current.copy()
                for p in col_perc:
                    teto_val = parse_valor_percentual(str(teto_row[p]).strip())
                    for i in df_tmp.index:
                        if parse_valor_percentual(str(df_tmp.at[i, p])) > teto_val:
                            df_tmp.at[i, p] = df_editor_initial.at[i, p]
                st.session_state.df_current = df_tmp

        # 4) Fase 2: confirmação do código e aplicação
        if st.session_state.awaiting_verification:
            # lista só as reduções
            pendencias = [
                f"{a['PRODUTO']} de {a['ANTERIOR']} → {a['NOVO']}"
                for a in st.session_state.pending_alteracoes
                if parse_valor_percentual(a["NOVO"]) < parse_valor_percentual(a["ANTERIOR"])
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

                # 2) grava no log de Alterações (todas as alterações)
                linhas = [
                    [
                        st.session_state.pending_agora,
                        nome_usuario,
                        st.session_state.pending_selected_filial,
                        a["NOME"],
                        a["PRODUTO"],
                        a["ANTERIOR"],
                        a["NOVO"],
                        # só “SIM” se for redução
                        "SIM" if parse_valor_percentual(a["NOVO"]) < parse_valor_percentual(a["ANTERIOR"]) else "NAO",
                        "NAO"  # ainda não aprovado
                    ]
                    for a in st.session_state.pending_alteracoes
                ]
                append_worksheet(linhas, "Alterações")

                # 3) separa reduções de não-reduções
                reducoes = [
                    a for a in st.session_state.pending_alteracoes
                    if parse_valor_percentual(a["NOVO"]) < parse_valor_percentual(a["ANTERIOR"])
                ]
                nao_reducoes = [
                    a for a in st.session_state.pending_alteracoes
                    if parse_valor_percentual(a["NOVO"]) >= parse_valor_percentual(a["ANTERIOR"])
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
                            alt["ANTERIOR"],
                            alt["NOVO"],
                            "https://share.streamlit.io/seu-usuario/seu-repo/main/Validação"
                        )
                    st.info("As alterações foram encaminhadas ao Diretor para validação.")

                # 5) para não-reduções, aplica imediatamente:
                if nao_reducoes:
                    # recarrega planilha Assessores e separa as outras filiais
                    df_all    = carregar_dataframe("Assessores")
                    df_others = df_all[
                        df_all["FILIAL"].str.strip().str.upper()
                        != selected_filial.strip().upper()
                    ]
                    # toma o DataFrame editado que você já tem em session_state
                    df_new = st.session_state.df_current.copy()
                    # carrega os dados originais de CPF/EMAIL daquela filial
                    df_ass_filial = carregar_dataframe("Assessores")[
                        lambda df: df["FILIAL"].str.strip().str.upper()
                        == selected_filial.strip().upper()
                    ]
                    df_new["CPF"]   = df_ass_filial["CPF"].values
                    df_new["EMAIL"] = df_ass_filial.set_index("CPF")["EMAIL"].reindex(df_new["CPF"]).values
                    df_new["FILIAL"] = selected_filial
                    # formata percentuais antes de enviar ao Sheets
                    for c in col_perc:
                        df_new[c] = df_new[c].apply(formatar_percentual_para_planilha)
                    full = pd.concat([df_others, df_new[cols_fixos + col_perc]], ignore_index=True)
                    sobrescrever_worksheet(full, "Assessores")

                    # 5a) envia resumo por e-mail ao Líder
                    subj_l = f"[Líder] Resumo de alterações em {selected_filial}"
                    txt_l  = "\n".join(
                        f"- {x['NOME']}: {x['PRODUTO']} de {x['ANTERIOR']} → {x['NOVO']}"
                        for x in nao_reducoes
                    )
                    body_l = (
                        f"Olá {nome_usuario},\n\nForam aplicadas as seguintes alterações "
                        f"em {selected_filial} no dia {st.session_state.pending_agora}:\n\n{txt_l}"
                    )
                    enviar_resumo_email([st.session_state.dados_lider["EMAIL_LIDER"]], subj_l, body_l)

                    # 5b) envia resumo para cada Assessor
                    agrup = defaultdict(list)
                    for x in nao_reducoes:
                        agrup[x["NOME"]].append(x)
                    for nome_a, alts in agrup.items():
                        email_a = df_ass_filial.loc[df_ass_filial["NOME"] == nome_a, "EMAIL"].iloc[0]
                        subj_a  = f"[Você] Resumo de alterações em {selected_filial}"
                        txt_a   = "\n".join(
                            f"- {y['PRODUTO']}: {y['ANTERIOR']} → {y['NOVO']}"
                            for y in alts
                        )
                        body_a  = (
                            f"Olá {nome_a},\n\nO líder {nome_usuario} realizou as seguintes alterações "
                            f"em {selected_filial} no dia {st.session_state.pending_agora}:\n\n{txt_a}"
                        )
                        enviar_resumo_email([email_a], subj_a, body_a)

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

    elif pagina == "Validação":
        st.subheader("Pendências de Validação")
        df_alt = carregar_dataframe("Alterações")
        df_pend = df_alt[
            (df_alt["Alteracao Necessaria"] == "SIM")
            & (df_alt["Alteracao Aprovada"] == "NAO")
            & (df_alt["Filial"].astype(str).str.strip().str.upper()
            == selected_filial.strip().upper())
        ]

        # ── Diretor ──
        if st.session_state.role == "director":
            if df_pend.empty:
                st.info("Não há alterações pendentes para validação.")
            else:
                df_pend = df_pend.copy()
                df_pend["Aprovado"] = False
                df_pend["Recusado"] = False
                df_pend["Comentario Diretor"] = ""

                from streamlit import column_config
                df_edit = st.data_editor(
                    df_pend[[
                        "Timestamp",
                        "Usuario",
                        "Assessor",
                        "Produto",
                        "Percentual Antes",
                        "Percentual Depois",
                        "Aprovado",
                        "Recusado",
                        "Comentario Diretor"
                    ]],
                    column_config={
                        "Timestamp":           column_config.TextColumn("Data e Hora",       disabled=True),
                        "Usuario":             column_config.TextColumn("Líder",             disabled=True),
                        "Assessor":            column_config.TextColumn("Assessor",          disabled=True),
                        "Produto":             column_config.TextColumn("Produto",           disabled=True),
                        "Percentual Antes":    column_config.TextColumn("Percentual Antes",  disabled=True),
                        "Percentual Depois":   column_config.TextColumn("Percentual Depois", disabled=True),
                        "Aprovado":            column_config.CheckboxColumn("Aprovado"),
                        "Recusado":            column_config.CheckboxColumn("Recusado"),
                        "Comentario Diretor":  column_config.TextColumn("Comentário do Diretor")
                    },
                    hide_index=True,
                    use_container_width=True
                )

                if st.button("Confirmar Validações"):
                    aprovados = df_edit[df_edit["Aprovado"]]
                    recusados = df_edit[df_edit["Recusado"]]

                    # atualiza planilha Alterações
                    for i, row in df_edit.iterrows():
                        sheet_row = i + 2
                        update_worksheet_cell(
                            worksheet_name="Alterações",
                            row=sheet_row,
                            col="Alteracao Aprovada",
                            value="SIM" if row["Aprovado"] else "NAO"
                        )
                        update_worksheet_cell(
                            worksheet_name="Alterações",
                            row=sheet_row,
                            col="Comentario Diretor",
                            value=row["Comentario Diretor"]
                        )

                    lider_email = st.session_state.dados_lider["EMAIL_LIDER"]

                    # envia email de recusa
                    for _, row in recusados.iterrows():
                        assunto = f"[Validação] Redução recusada em {selected_filial}"
                        corpo = (
                            f"Olá {row['Usuario']},\n\n"
                            f"Sua solicitação de redução do produto {row['Produto']} "
                            f"de {row['Percentual Antes']}% → {row['Percentual Depois']}% em "
                            f"{selected_filial} foi *recusada* pelo Diretor.\n\n"
                            f"Comentário do Diretor:\n{row['Comentario Diretor']}"
                        )
                        enviar_resumo_email([lider_email], assunto, corpo)

                    # envia email de aprovação
                    if not aprovados.empty:
                        from modules.email_service import send_approval_result
                        send_approval_result(
                            aprovados,
                            lider_email=lider_email,
                            diretor_email=st.session_state.user
                        )

                    st.success(
                        f"{len(aprovados)} aprovação(ões) e {len(recusados)} recusa(s) registradas!"
                    )

        # ── Líder ──
        else:
            if df_pend.empty:
                st.info("Nenhuma solicitação de redução pendente.")
            else:
                df_leader = df_pend.copy()
                df_leader = df_leader.rename(columns={
                    "Timestamp": "Data e Hora",
                    "Usuario":   "Diretor",
                    "Assessor":  "Assessor",
                    "Produto":   "Produto",
                    "Percentual Antes":  "Percentual Antes",
                    "Percentual Depois": "Percentual Depois",
                    "Comentario Diretor":"Comentário do Diretor"
                })

                def _status(row):
                    if row["Alteracao Aprovada"] == "SIM":
                        return "Aprovado"
                    if str(row["Comentário do Diretor"]).strip():
                        return "Recusado"
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

                st.dataframe(df_leader, use_container_width=True)

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
