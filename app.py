import streamlit as st
import pandas as pd
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from collections import defaultdict
import random
from streamlit import column_config
import httpx
import random
from streamlit_option_menu import option_menu

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
from modules.email_service import (
    enviar_codigo_email,
    send_director_request,
    enviar_resumo_email,
    _build_email_html,
    send_approval_result,
    send_declaration_email
)
from modules.formatters import (
    parse_valor_percentual,
    formatar_percentual_para_planilha,
    formatar_para_exibir
)
from modules.admin_dashboard import display_admin_dashboard
from modules.analytics import display_analytics
from modules.comissoes import display_comissoes, _carregar_comissoes_filial
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

        # 🔥 Pré‑aquece o cache de comissões (1ª visita fica instantânea)
        try:
            _ = _carregar_comissoes_filial()
        except Exception:
            pass  # não quebra o app se falhar aqui
    except httpx.RemoteProtocolError:
        # 2) mostre erro amigável e pare o app sem stack-trace
        st.error(
            "Tivemos um erro inesperado na conexão. "
            "Por favor, reinicie o aplicativo."
        )
        st.stop()

    # — Define colunas fixas e percentuais —
    cols_fixos = ["SIGLA", "CPF", "NOME", "EMAIL", "FILIAL", "FUNCAO", "LAST_UPDATE"]
    col_perc = [
        c for c in df_assessores.columns
        if c not in cols_fixos       # tira as fixas
        and c != "ID"              # tira também o ID
        and isinstance(c, str)
        and c.strip() != ""
    ]

    # ── Filiais do usuário (Diretor, RM ou Líder) ──
    nome_usuario = st.session_state.dados_lider["LIDER"]
    role  = st.session_state.role
    level = st.session_state.get("level", 5)  # default mais restrito

    if level in (1, 2, 6):
        # Níveis 1 e 2 enxergam TODAS as filiais
        df_filial_lider = df_filial.copy()
    else:
        nome_usuario = st.session_state.dados_lider["LIDER"]
        nome_up = str(nome_usuario or "").strip().upper()

        if level == 3:  # Diretor
            df_filial_lider = df_filial[
                df_filial["DIRETOR"].astype(str).str.strip().str.upper() == nome_up
            ]
        elif level == 4:
            if role == "superintendent":
                df_filial_lider = df_filial[df_filial["SUPERINTENDENTE"].str.strip().str.upper() == nome_up]
            else:  # leader / leader2
                coluna = "LIDER" if role == "leader" else "LIDER2"
                df_filial_lider = df_filial[df_filial[coluna].str.strip().str.upper() == nome_up]
        elif level == 5:  # RM
            df_filial_lider = df_filial[df_filial["RM"].str.strip().str.upper() == nome_up]
        else:
            st.error("Nível de acesso desconhecido. Contate Comissões.")
            st.stop()



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
        "Spoiler BeSmart",
        "Comissões"
    ]
    if level == 1:
        pages.insert(0, "Dashboard Admin")

    # 🔒 páginas-teaser (apenas para aparecer na sidebar)
    coming_soon = [
        "Comissão detalhada",
        "Investimento de Filiais",
        "DRE Filiais",
        "Visão do Assessor",
        "Recebíveis",
    ]
    pages = pages + coming_soon  # exibidas no final do menu

    if "pagina" not in st.session_state:
        st.session_state.pagina = pages[0]

    # — Menu lateral personalizado —
    st.sidebar.markdown(
        """
        <div class="menu-nav">Menu de navegação</div>
        """,
        unsafe_allow_html=True
    )

    with st.sidebar:

        # ícones por página (ordem independente da inserção de novas páginas)
        sidebar_icon_map = {
            "Dashboard Admin": "speedometer2",
            "Gestão de Percentuais": "grid",
            "Validação": "check2-square",
            "Painel Analítico": "bar-chart-line",
            "Sugestão de Melhoria": "lightbulb",
            "Ajuda e FAQ": "question-circle",
            "Spoiler BeSmart": "megaphone",
            "Comissões": "currency-dollar",
            # 🔒 ícones para as páginas travadas
            "Comissão detalhada": "lock-fill",
            "Investimento de Filiais": "lock-fill",
            "DRE Filiais": "lock-fill",
            "Visão do Assessor": "lock-fill",
            "Recebíveis": "lock-fill",
        }
        icons_for_pages = [sidebar_icon_map.get(p, "circle") for p in pages]

        # menu customizado
        # 🔧 CSS: os 5 últimos itens do menu (coming_soon) ficam cinza + desabilitados
        st.sidebar.markdown("""
        <style>
        /* Itens "em breve" aparecem cinza, mas continuam clicáveis */
        section[data-testid="stSidebar"] ul.nav.nav-pills.flex-column li:nth-last-child(-n+5) a {
            color: #9aa !important;
            opacity: 0.85 !important;
        }
        section[data-testid="stSidebar"] ul.nav.nav-pills.flex-column li:nth-last-child(-n+5) a .bi {
            color: #9aa !important;
            opacity: 0.85 !important;
        }
        </style>
        """, unsafe_allow_html=True)

        pagina_escolhida = option_menu(
            menu_title=None,
            options=pages,
            icons=icons_for_pages,
            default_index=pages.index(st.session_state.get("pagina", pages[0])),
            styles={
                "container": {"padding": "0!important", "background-color": "#9966ff"},
                "icon":      {"font-size": "16px"},
                "nav-link":  {"font-size": "14px", "text-align": "left", "margin": "0px", "padding": "8px 16px"},
                "nav-link-selected": {"background-color": "#121212", "font-weight": "bold", "font-size": "14px"},
            },
        )

        # espaço e botão de logout (se já estiver logado)
        st.markdown("<br><br><br>", unsafe_allow_html=True)
        if st.session_state.get("user_name"):
            if st.button("Logout"):
                st.session_state.clear()
                st.rerun()

        # 🔒 guarda: se por qualquer motivo o clique passar, não troca de página
        if st.session_state.get("pagina") != pagina_escolhida:
            st.session_state.pagina = pagina_escolhida
            st.rerun()

    pagina = st.session_state.pagina


    # — Título dinâmico no topo da área principal —
    page_icons = {
        "Dashboard Admin":        "📊",
        "Gestão de Percentuais":  "💼",
        "Painel Analítico":       "📈",
        "Validação":              "✅",
        "Sugestão de Melhoria":   "💡",
        "Ajuda e FAQ":            "❓",
        "Spoiler BeSmart":        "📢",
        "Comissões":               "💲"
    }
    icon = page_icons.get(pagina, "")
    st.markdown(
        f"<h1 style='color: black; margin-bottom: 1rem;'>{icon} {pagina}</h1>",
        unsafe_allow_html=True
    )

    if pagina not in ["Ajuda e FAQ", "Sugestão de Melhoria", "Dashboard Admin"] and pagina not in coming_soon:
        # — Seletor de filial —
        st.markdown(
            """
            <div style="
                font-size:17px;color:#000;font-weight:600;margin: 0 0 -3.7rem 0;">
                Selecione a filial para gerenciar:
            </div>
            """,
            unsafe_allow_html=True
        )
        if not filiais_do_lider:
            st.warning("Nenhuma filial disponível para este usuário.")
            st.stop()

        # 🔎 Se for a página Validação, filtrar opções para 'filiais com pendência'
        if pagina == "Validação":
            df_alt_full = get_log()  # mesma fonte usada abaixo
            # Mapa FILIAL -> SEGMENTO (para regra de tipo por segmento)
            seg_por_filial = (
                df_filial.assign(FILIAL=df_filial["FILIAL"].astype(str).str.upper().str.strip())
                        .set_index("FILIAL")["SEGMENTO"]
                        .astype(str).str.upper().str.strip()
                        .to_dict()
            )
            # máscara base de pendência (independente de filial)
            base_mask = (
                (df_alt_full["VALIDACAO NECESSARIA"] == "SIM") &
                (df_alt_full["ALTERACAO APROVADA"] == "NAO") &
                (df_alt_full["COMENTARIO DIRETOR"].isna() | (df_alt_full["COMENTARIO DIRETOR"].str.strip() == ""))
            )
            df_alt_base = df_alt_full.loc[base_mask].copy()

            filiais_com_pend = []
            for f in filiais_do_lider:
                f_up = str(f).strip().upper()
                segmento = (seg_por_filial.get(f_up, "") or "").strip().upper()
                tipos_validos = ["REDUCAO", "AUMENTO"] if segmento == "B2C" else ["REDUCAO"]
                qtd = df_alt_base[
                    (df_alt_base["FILIAL"].str.strip().str.upper() == f_up) &
                    (df_alt_base["TIPO"].isin(tipos_validos))
                ].shape[0]
                if qtd > 0:
                    filiais_com_pend.append(f)

            opcoes_filial = filiais_com_pend if filiais_com_pend else filiais_do_lider
        else:
            opcoes_filial = filiais_do_lider

        default = st.session_state.get("filial_selecionada", opcoes_filial[0])
        initial_index = opcoes_filial.index(default) if default in opcoes_filial else 0

        selected_filial = st.selectbox(
            "",
            opcoes_filial,
            key="filial_selecionada",
            index=initial_index
        )
        # 🔧 normalize uma única vez e reutilize
        selected_filial_up = str(selected_filial or "").strip().upper()
        st.markdown(f"Olá, **{nome_usuario}**! Você está gerenciando a filial **{selected_filial}**.")
    else:
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
            df_filial_lider["FILIAL"].astype(str).str.strip().str.upper() == selected_filial_up
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
            df_assessores["FILIAL"].astype(str).str.strip().str.upper() == selected_filial_up
        ].copy()
        for p in col_perc:
            df_ass_filial[p] = df_ass_filial[p].apply(formatar_para_exibir)

        df_ass_filial = df_ass_filial.drop(columns=["ID", "LAST_UPDATE"], errors="ignore")

        fixed       = [c for c in cols_fixos if c not in ["CPF", "EMAIL", "ID", "LAST_UPDATE"]]
        percent     = col_perc.copy()
        display_cols = fixed + percent
        df_editor_initial = df_ass_filial[display_cols].copy()

        if ("last_filial" not in st.session_state
            or st.session_state.last_filial != selected_filial):
            st.session_state.last_filial = selected_filial
            st.session_state.df_current  = df_editor_initial.copy()

        # ── Leitura somente: RM (nível 5) e Comissões (nível 6) ──
        if level in (5, 6):
            st.info("Acesso apenas para visualização de percentuais.")
            st.dataframe(df_ass_filial[display_cols], use_container_width=True)
            return

        # 3) Editor dentro de um form: só reruna ao submeter
        with st.form("percentual_form"):
            disabled = [c for c in display_cols if c not in col_perc]
            df_edited = mostrar_data_editor(
                st.session_state.df_current,
                disabled_cols=disabled
            )
            st.session_state.df_current = df_edited

            submitted = st.form_submit_button("💾 Salvar alterações")
            reset_all  = st.form_submit_button("🧹 Limpar Alterações")

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
                            # ─ logo após obter teto_row, capture o segmento ─
                            segmento = teto_row.get("SEGMENTO", "").strip().upper()

                            # ─ agora, dentro do loop:
                            if segmento != "B2C" and new_f > teto_f:
                                # só bloqueia teto se NÃO for B2C
                                erros_teto.append(
                                    f"- {p} de {nome_ass} ({new}%) excede o teto de {teto_row[p]}%."
                                )
                            else:
                                # para B2C (ou abaixo do teto), registra a alteração
                                if st.session_state.role in ("leader", "leader2"):
                                    pend = df_log[
                                        (df_log["USUARIO"].astype(str).str.strip().str.upper() == str(nome_usuario or "").strip().upper()) &
                                        (df_log["FILIAL"].astype(str).str.strip().str.upper() == selected_filial_up) &
                                        (df_log["ASSESSOR"].astype(str) == str(nome_ass)) &
                                        (df_log["PRODUTO"].astype(str)  == str(p)) &
                                        (df_log["VALIDACAO NECESSARIA"] == "SIM") &
                                        (df_log["ALTERACAO APROVADA"]   == "NAO")
                                    ]
                                else:
                                    pend = df_log[
                                        (df_log["FILIAL"].astype(str).str.strip().str.upper() == selected_filial_up) &
                                        (df_log["ASSESSOR"].astype(str) == str(nome_ass)) &
                                        (df_log["PRODUTO"].astype(str)  == str(p)) &
                                        (df_log["VALIDACAO NECESSARIA"] == "SIM") &
                                        (df_log["ALTERACAO APROVADA"]   == "NAO")
                                    ]
                                if not pend.empty:
                                    st.error(
                                        f"O percentual **{p}** de **{nome_ass}** já está em análise e não pode ser alterado."
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
            # identifica segmento da filial selecionada
            # identifica segmento da filial selecionada (não pegue iloc[0]!)
            seg_row = df_filial_lider[
                df_filial_lider["FILIAL"].astype(str).str.strip().str.upper() == selected_filial_up
            ].iloc[0]
            segmento = str(seg_row.get("SEGMENTO") or "").strip().upper()

            # pendências só em B2C (tudo) ou em B2B (somente reduções)
            if segmento == "B2C":
                pendencias = [
                    f"{a['PRODUTO']} de {a['PERCENTUAL ANTES']} → {a['PERCENTUAL DEPOIS']}"
                    for a in st.session_state.pending_alteracoes
                ]
            else:
                pendencias = [
                    f"{a['PRODUTO']} de {a['PERCENTUAL ANTES']} → {a['PERCENTUAL DEPOIS']}"
                    for a in st.session_state.pending_alteracoes
                    if parse_valor_percentual(a["PERCENTUAL DEPOIS"]) <
                    parse_valor_percentual(a["PERCENTUAL ANTES"])
                ]

            # só mostra aviso quando houver pendências
            if pendencias:
                st.warning(
                    f"Essas alterações requerem aprovação do Diretor: " +
                    "; ".join(pendencias)
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

                    # 2) grava no log de Alterações ...
                    seg_row = df_filial_lider[
                        df_filial_lider["FILIAL"].astype(str).str.strip().str.upper() == selected_filial_up
                    ].iloc[0]
                    segmento = str(seg_row.get("SEGMENTO") or "").strip().upper()
                    linhas = []
                    for a in st.session_state.pending_alteracoes:
                        before_str = a["PERCENTUAL ANTES"]
                        after_str  = a["PERCENTUAL DEPOIS"]
                        is_reducao = parse_valor_percentual(after_str) < parse_valor_percentual(before_str)

                        # em B2C, qualquer mudança = validação obrigatória; fora, só reduções
                        if segmento == "B2C":
                            validacao = "SIM"
                        else:
                            validacao = "SIM" if is_reducao else "NAO"

                        tipo       = "REDUCAO" if is_reducao else "AUMENTO"
                        before_num = float(before_str.replace(",", "."))
                        after_num  = float(after_str.replace(",", "."))

                        linhas.append([
                            st.session_state.pending_agora_raw,
                            nome_usuario,
                            selected_filial,
                            a["NOME"],
                            a["PRODUTO"],
                            before_num,
                            after_num,
                            validacao,
                            "NAO",
                            tipo
                        ])
                    inserir_alteracao_log(linhas)
                    st.cache_data.clear()

                    # 3) separa solicitações (para aprovação) e aplicações imediatas
                    if segmento == "B2C":
                        solicitacoes      = st.session_state.pending_alteracoes
                        aplicacoes_rapidas = []
                    else:
                        solicitacoes = [
                            a for a in st.session_state.pending_alteracoes
                            if parse_valor_percentual(a["PERCENTUAL DEPOIS"]) <
                            parse_valor_percentual(a["PERCENTUAL ANTES"])
                        ]
                        aplicacoes_rapidas = [
                            a for a in st.session_state.pending_alteracoes
                            if parse_valor_percentual(a["PERCENTUAL DEPOIS"]) >=
                            parse_valor_percentual(a["PERCENTUAL ANTES"])
                        ]

                    # 4) envia ao Diretor todas as solicitações pendentes
                    if solicitacoes:
                        diretor_nome  = df_filial_lider.iloc[0]["DIRETOR"].strip().upper()
                        diretor_email = st.secrets["director_emails"][diretor_nome]
                        for alt in solicitacoes:
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

                    # 5) aplica imediatamente o que não requer aprovação
                    if aplicacoes_rapidas:
                        # 5a) atualiza no Supabase
                        for alt in aplicacoes_rapidas:
                            produto_col     = alt["PRODUTO"]
                            percent_decimal = parse_valor_percentual(alt["PERCENTUAL DEPOIS"])
                            novo_val_int    = int(round(percent_decimal * 100))

                            # encontra ID do assessor
                            try:
                                resp = (
                                    supabase
                                    .table("assessores")
                                    .select("ID")
                                    .eq("NOME", str(alt["NOME"] or "").strip())
                                    .eq("FILIAL", selected_filial_up)
                                    .single()
                                    .execute()
                                )
                                assessor_id = resp.data["ID"]
                            except Exception as e:
                                st.error(f"Erro ao buscar assessor {alt['NOME']}: {e}")
                                continue

                            # atualiza o percentual
                            try:
                                supabase.table("assessores") \
                                    .update({ produto_col: novo_val_int }) \
                                    .eq("ID", assessor_id) \
                                    .execute()
                            except Exception as e:
                                st.error(f"Falha ao atualizar {alt['NOME']} ({produto_col}): {e}")
                                continue

                        # 5b) envia resumo por e-mail ao Líder
                        subj_l = f"Resumo de alterações em {selected_filial}"
                        lista_html = "".join(
                            f"<li>{x['NOME']}: {x['PRODUTO']} de {x['PERCENTUAL ANTES']}% → {x['PERCENTUAL DEPOIS']}%</li>"
                            for x in aplicacoes_rapidas
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

                        # 5c) envia resumo para cada Assessor
                        agrup = defaultdict(list)
                        for x in aplicacoes_rapidas:
                            agrup[x["NOME"]].append(x)

                        for nome_a, alts in agrup.items():
                            filtro = (
                                (df_assessores["NOME"].astype(str).str.strip().str.upper() == str(nome_a or "").strip().upper())
                                & (df_assessores["FILIAL"].astype(str).str.strip().str.upper() == selected_filial_up)
                            )
                            df_sel = df_assessores.loc[filtro]
                            if df_sel.empty:
                                continue
                            email_a = df_sel["EMAIL"].iloc[0]

                            subj_a = f"Resumo de alterações em {selected_filial}"
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

                    st.success(
                        f"Alterações registradas com sucesso em {st.session_state.pending_agora_display}!"
                    )
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

    elif pagina == "Spoiler BeSmart":
        # normaliza a filial para bater com o padrão do banco
        sel_filial_up = (selected_filial or "").strip().upper()

        query = (
            supabase.table("recebiveis_futuros")
            .select("data_de_credito,cliente,nome,duracao_com,comissao_bruto,produto,seguradora")
            .eq("nome_filial_equipe", sel_filial_up)
        )
        result = query.execute()
        df = pd.DataFrame(result.data or [])

        if df.empty:
            st.info("Não há spoilers BeSmart para esta filial.")
        else:
            # Conversões
            df["data_de_credito"] = pd.to_datetime(df["data_de_credito"], errors="coerce")
            df["duracao_com"]     = pd.to_numeric(df["duracao_com"], errors="coerce")
            df["comissao_bruto"]  = pd.to_numeric(df["comissao_bruto"], errors="coerce")
            df = df.dropna(subset=["data_de_credito"])

            st.info(
                "As informações abaixo são as produções BeSmart vinculadas à sua filial, que estão em apuração. "
                "Qualquer erro ou divergência, entre em contato com Comissões."
            )

            # ---------- MÊS ATUAL TRAVADO (mas com liberdade dentro do mês) ----------
            hoje = datetime.now(ZoneInfo("America/Sao_Paulo")).date()
            primeiro_dia_mes = hoje.replace(day=1)
            ultimo_dia_mes   = pd.Timestamp(hoje).to_period("M").end_time.date()

            # Widgets de data limitados ao mês atual
            c1, c2 = st.columns(2)
            with c1:
                start_date = st.date_input(
                    "Data de Início",
                    value=primeiro_dia_mes,
                    min_value=primeiro_dia_mes,
                    max_value=ultimo_dia_mes,
                    key="besmart_start",
                )
            with c2:
                end_date = st.date_input(
                    "Data de Término",
                    value=ultimo_dia_mes,
                    min_value=primeiro_dia_mes,
                    max_value=ultimo_dia_mes,
                    key="besmart_end",
                )

            # Aplica filtro de período do mês atual
            start_dt = datetime.combine(start_date, datetime.min.time())
            end_dt   = datetime.combine(end_date,   datetime.max.time())

            df_filt = df[(df["data_de_credito"] >= start_dt) & (df["data_de_credito"] <= end_dt)].copy()

            # Filtro por assessor baseado no período aplicado
            assessores = ["Todos"] + sorted(df_filt["nome"].dropna().unique().tolist())
            selected_assessor = st.selectbox("Filtrar por Assessor", assessores)
            if selected_assessor != "Todos":
                df_filt = df_filt[df_filt["nome"] == selected_assessor]

            if df_filt.empty:
                st.info("Sem registros no período selecionado do mês atual.")
                st.stop()

            # ---------- KPIs (usando df_filt) ----------
            st.markdown("<br>", unsafe_allow_html=True)
            total_bruto = df_filt["comissao_bruto"].sum()
            total_bruto_br = (
                f"R$ {total_bruto:,.2f}"
                .replace(",", "X").replace(".", ",").replace("X", ".")
            )

            cols = st.columns(5)
            labels = [
                "💰 Faturamento Estimado",
                "📄 Quantidade de Registros",
                "👥 Clientes Únicos",
                "🧑‍💼 Assessores Únicos",
                "🤝🏻 Parceiros Únicos",
            ]
            values = [
                total_bruto_br,
                len(df_filt),
                df_filt["cliente"].nunique(),
                df_filt["nome"].nunique(),
                df_filt["seguradora"].nunique(),
            ]
            for c, lbl, val in zip(cols, labels, values):
                c.markdown(
                    f"<div style='font-size:17px; font-weight:bold; margin-bottom:4px;'>{lbl}</div>",
                    unsafe_allow_html=True,
                )
                c.markdown(
                    f"<div style='font-size:28px; color:#111;'>{val}</div>",
                    unsafe_allow_html=True,
                )

            st.markdown("---")

            # ---------- Tabela (usando df_filt) ----------
            st.markdown("**Detalhamento dos Spoilers BeSmart - Faturamento e Produções podem variar caso fornecedor ou relações cliente-assessor mudem.**")

            df_display = df_filt.rename(columns={
                "data_de_credito": "Data de Crédito",
                "cliente":         "Nome do Cliente",
                "nome":            "Assessor",
                "duracao_com":     "Parcela",
                "comissao_bruto":  "Faturamento Estimado",
                "produto":         "Produto",
                "seguradora":      "Seguradora",
            })

            df_display["Data de Crédito"] = df_display["Data de Crédito"].dt.strftime("%d/%m/%Y")
            df_display["Faturamento Estimado"] = (
                df_display["Faturamento Estimado"]
                .apply(lambda x: f"R$ {x:,.2f}")
                .str.replace(",", "X").str.replace(".", ",").str.replace("X", ".")
            )

            st.dataframe(df_display, use_container_width=True)

    elif pagina == "Comissões":
        # Usa a filial já selecionada no topo do app e o DF de assessores carregado
        display_comissoes(df_assessores=df_assessores, filial_selecionada=selected_filial)

    elif pagina in coming_soon:
        st.markdown("## 🚧 Página em construção")
        st.markdown(
            "Estamos trabalhando para entregar esta funcionalidade em breve. "
            "Obrigado pela paciência!"
        )
        st.image(
            "https://www.imagensanimadas.com/data/media/695/em-construcao-imagem-animada-0035.gif",
            width=240
        )

    elif pagina == "Painel Analítico":

        seg_row = df_filial_lider[
            df_filial_lider["FILIAL"].astype(str).str.strip().str.upper() == selected_filial_up
        ].iloc[0]
        is_b2c = ((seg_row.get("SEGMENTO", "") or "").strip().upper() == "B2C")

        sel_filial_up = (selected_filial or "").strip().upper()
        df_ass_filial = df_assessores[
            df_assessores["FILIAL"].astype(str).str.strip().str.upper() == sel_filial_up
        ].copy()

        display_analytics(
            df_log=df_log,
            df_assessores_filial=df_ass_filial,
            df_filial_do_lider=df_filial_lider,
            col_perc=col_perc,
            nome_lider=nome_usuario,
            filial_lider=selected_filial,
            is_b2c=is_b2c,
            role=st.session_state.role,
            level=st.session_state.level
        )

    elif pagina == "Ajuda e FAQ":
        pagina_ajuda()

    elif pagina == "Dashboard Admin":
        display_admin_dashboard()    

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

        # ===== Visão Geral – Filiais com alterações pendentes (após aprovar/recusar) =====
        if not df_alt.empty:
            seg_por_filial = (
                df_filial.assign(FILIAL=df_filial["FILIAL"].astype(str).str.upper().str.strip())
                        .set_index("FILIAL")["SEGMENTO"]
                        .astype(str).str.upper().str.strip()
                        .to_dict()
            )

            base_mask = (
                (df_alt["VALIDACAO NECESSARIA"] == "SIM") &
                (df_alt["ALTERACAO APROVADA"] == "NAO") &
                (df_alt["COMENTARIO DIRETOR"].isna() | (df_alt["COMENTARIO DIRETOR"].str.strip() == ""))
            )
            df_base = df_alt.loc[base_mask].copy()

            resultados = []
            for f in filiais_do_lider:
                f_up = str(f).strip().upper()
                segmento = (seg_por_filial.get(f_up, "") or "").strip().upper()
                tipos_validos = ["REDUCAO", "AUMENTO"] if segmento == "B2C" else ["REDUCAO"]
                qtd = df_base[
                    (df_base["FILIAL"].str.strip().str.upper() == f_up) &
                    (df_base["TIPO"].isin(tipos_validos))
                ].shape[0]
                # só guarda quem tem > 0
                if qtd > 0:
                    resultados.append({"FILIAL": f, "ALTERAÇÕES PENDENTES": int(qtd)})

            if resultados:
                df_quadro = (pd.DataFrame(resultados)
                            .sort_values(["ALTERAÇÕES PENDENTES","FILIAL"], ascending=[False, True])
                            .reset_index(drop=True))

                st.markdown("**Visão Geral – Filiais com alterações pendentes:**")
                st.dataframe(
                    df_quadro,
                    hide_index=True,
                    use_container_width=True
                )
                st.markdown("---")


        # ===== Fluxo atual por filial selecionada (mantido) =====
        # Captura segmento e define quais tipos incluir
        seg_row = df_filial_lider[
            df_filial_lider["FILIAL"].astype(str).str.strip().str.upper() == selected_filial_up
        ].iloc[0]
        segmento = str(seg_row.get("SEGMENTO") or "").strip().upper()
        tipos_validos = ["REDUCAO", "AUMENTO"] if segmento == "B2C" else ["REDUCAO"]


        # Filtra apenas registros pendentes de validação
        df_pend = df_alt[
            (df_alt["VALIDACAO NECESSARIA"] == "SIM") &
            (df_alt["ALTERACAO APROVADA"]   == "NAO") &
            df_alt["TIPO"].isin(tipos_validos) &
            (df_alt["FILIAL"].astype(str).str.strip().str.upper() == selected_filial_up) &
            (
                df_alt["COMENTARIO DIRETOR"].isna() |
                (df_alt["COMENTARIO DIRETOR"].astype(str).str.strip() == "")
            )
        ]

        # ── Fluxo do Diretor/Admin ──
        if level in (1, 2, 3):

            if df_pend.empty:
                st.info("Não há alterações pendentes para validação.")
            else:
                # Inicializa flag de declaração, se necessário
                if "declaration_pending" not in st.session_state:
                    st.session_state.declaration_pending = False

                # 1️⃣ Prepara Data Editor
                df_display = df_pend.copy()
                df_display["TIMESTAMP"] = (
                    pd.to_datetime(df_display["TIMESTAMP"], errors="coerce")
                    .dt.strftime("%d/%m/%Y às %H:%M")
                )
                df_display["Aprovado"] = False
                df_display["Recusado"] = False
                df_display["COMENTARIO DIRETOR"] = ""

                df_edit = st.data_editor(
                    df_display[[
                        "ID", "TIMESTAMP", "USUARIO", "ASSESSOR", "PRODUTO",
                        "PERCENTUAL ANTES", "PERCENTUAL DEPOIS", "Aprovado",
                        "Recusado", "COMENTARIO DIRETOR"
                    ]],
                    column_config={
                        "ID":                  column_config.TextColumn("ID", disabled=True),
                        "TIMESTAMP":           column_config.TextColumn("Data e Hora", disabled=True),
                        "USUARIO":             column_config.TextColumn("Líder", disabled=True),
                        "ASSESSOR":            column_config.TextColumn("Assessor", disabled=True),
                        "PRODUTO":             column_config.TextColumn("Produto", disabled=True),
                        "PERCENTUAL ANTES":    column_config.TextColumn("Percentual Antes", disabled=True),
                        "PERCENTUAL DEPOIS":   column_config.TextColumn("Percentual Depois", disabled=True),
                        "Aprovado":            column_config.CheckboxColumn("Aprovado"),
                        "Recusado":            column_config.CheckboxColumn("Recusado"),
                        "COMENTARIO DIRETOR":  column_config.TextColumn("Comentário do Diretor")
                    },
                    hide_index=True,
                    use_container_width=True
                )

                # 2️⃣ Confirmação inicial: Aprovados vs Recusados
                if st.button("Confirmar Validações", key="confirmar_validacoes"):
                    placeholder = st.empty()
                    try:
                        # Mostra GIF de loading
                        gif_choice = random.choice(gif_urls)
                        placeholder.image(gif_choice, width=90)

                        df_sel = df_edit.copy()
                        # Garante exclusividade entre Aprovado e Recusado
                        mask_both = df_sel["Aprovado"] & df_sel["Recusado"]
                        df_sel.loc[mask_both, "Recusado"] = False

                        aprovados = df_sel[df_sel["Aprovado"]].copy()
                        recusados = df_sel[df_sel["Recusado"]].copy()

                        # Comentário obrigatório para recusa
                        faltam = [
                            i+1 for i, row in recusados.iterrows()
                            if not (isinstance(row["COMENTARIO DIRETOR"], str) and row["COMENTARIO DIRETOR"].strip())
                        ]
                        if faltam:
                            st.error("Comentário do Diretor é obrigatório para recusa nas solicitações.")
                            st.stop()

                        # Processa recusas imediatamente
                        lider_email = st.session_state.dados_lider["EMAIL_LIDER"]
                        for _, row in recusados.iterrows():
                            log_id = int(row["ID"])
                            atualizar_alteracao_log(log_id, "ALTERACAO APROVADA", "NAO")
                            atualizar_alteracao_log(log_id, "COMENTARIO DIRETOR", row["COMENTARIO DIRETOR"])
                            atualizar_alteracao_log(log_id, "VALIDACAO NECESSARIA", "NAO")

                            assunto = f"Redução recusada em {selected_filial}"
                            conteudo_html = f"""
                            <p>Olá {row['USUARIO']},</p>
                            <p>Sua solicitação de redução do produto
                            <strong>{row['PRODUTO']}</strong>
                            de <strong>{row['PERCENTUAL ANTES']}% → {row['PERCENTUAL DEPOIS']}%</strong>
                            em <strong>{selected_filial}</strong> foi
                            <strong style="color:#dc3545;">recusada</strong> pelo Diretor.</p>
                            <p>Comentário do Diretor:<br/><em>{row['COMENTARIO DIRETOR']}</em></p>
                            """
                            enviar_resumo_email(
                                [lider_email],
                                assunto,
                                _build_email_html(assunto, conteudo_html),
                                content_type="HTML"
                            )

                        st.cache_data.clear()

                        # Se houver aprovações, armazena para a etapa da declaração
                        if not aprovados.empty:
                            st.session_state.declaration_pending = True
                            st.session_state.aprovados_para_declaracao = aprovados

                            # mapeia e-mail do assessor a partir do df_assessores
                            def _email_assessor(row):
                                mask = (
                                    (df_assessores["NOME"].str.strip().str.upper()   == str(row["ASSESSOR"]).strip().upper()) &
                                    (df_assessores["FILIAL"].str.strip().str.upper() == str(selected_filial).strip().upper())
                                )
                                sel = df_assessores.loc[mask]
                                return sel["EMAIL"].iloc[0] if not sel.empty else None

                            aprovados = aprovados.copy()
                            aprovados["EMAIL_ASSESSOR"]    = aprovados.apply(_email_assessor, axis=1)
                            aprovados["EMAIL_SOLICITANTE"] = st.session_state.dados_lider["EMAIL_LIDER"]

                            st.session_state.df_envio = aprovados.assign(FILIAL=selected_filial)

                        st.success(f"{len(aprovados)} aprovação(ões) e {len(recusados)} recusa(s) registradas!")
                    except Exception as err:
                        st.error(f"Ocorreu um erro ao validar alterações: {err}")
                    finally:
                        placeholder.empty()

                # 3️⃣ Se há declarações pendentes, exibe expander separado
                if st.session_state.get("declaration_pending", False):
                    aprovados = st.session_state.aprovados_para_declaracao.copy()
                    aprovados["TIMESTAMP"] = pd.to_datetime(
                        aprovados["TIMESTAMP"],
                        format="%d/%m/%Y às %H:%M",
                        dayfirst=True,
                        errors="coerce"
                    ).dt.strftime("%d/%m/%Y às %H:%M")
                    itens_html = "".join(
                        f"<tr>"
                        f"<td>{row['ASSESSOR']}</td>"
                        f"<td>{row['PRODUTO']}</td>"
                        f"<td>{row['PERCENTUAL ANTES']}%</td>"
                        f"<td>{row['PERCENTUAL DEPOIS']}%</td>"
                        f"<td>{row['TIMESTAMP']}</td>"
                        f"</tr>"
                        for _, row in aprovados.iterrows()
                    )
                    declaracao = f"""
                    <h3>Declaração de Revisão Contratual</h3>
                    <p>Eu, <strong>{st.session_state.dados_lider['LIDER']}</strong>,
                    declaro que a alteração do percentual de comissionamento ora aprovada por mim foi realizada em conformidade com a contratação 
                    existente e formalizada com o respectivo assessor, as diretrizes internas da companhia e com os princípios da boa-fé, legalidade e transparência.
                    </p> 
                    Segue abaixo a relação dos assessores e percentuais alterados:
                    </p>
                    <table border="1" cellpadding="4" cellspacing="0">
                        <tr>
                            <th>Assessor</th><th>Produto</th>
                            <th>Antes</th><th>Depois</th><th>Data e Hora</th>
                        </tr>
                        {itens_html}
                    </table>
                    <p>
                    Asseguro que li as cláusulas aplicáveis e assumo responsabilidade sob a ótica da conformidade.
                    </p>
                    """
                    with st.expander("Declaração de Revisão Contratual", expanded=True):
                        st.markdown(declaracao, unsafe_allow_html=True)
                        col_ok, col_cancel = st.columns(2)
                        aprovar_decl = col_ok.button("Aprovar Declaração", key="aprovar_decl")
                        recusar_decl = col_cancel.button("Recusar Declaração", key="recusar_decl")

                    # se recusou, fecha o expander e mostra a mensagem aqui
                    if recusar_decl:
                        st.session_state.declaration_pending = False
                        st.warning("Declaração rejeitada. As validações iniciais permanecem sem alteração.")
                        st.rerun()

                    # se aprovou, segue com a lógica normal de aprovação
                    if aprovar_decl:
                            try:
                                # Atualiza logs de aprovação
                                for _, row in aprovados.iterrows():
                                    log_id = int(row["ID"])
                                    atualizar_alteracao_log(log_id, "ALTERACAO APROVADA", "SIM")
                                    atualizar_alteracao_log(log_id, "COMENTARIO DIRETOR", "")
                                    atualizar_alteracao_log(log_id, "VALIDACAO NECESSARIA", "NAO")
                                # Envia e-mails de resultado e de declaração
                                send_approval_result(
                                    st.session_state.df_envio,
                                    lider_email=st.session_state.dados_lider["EMAIL_LIDER"]
                                )
                                items_html = "".join(
                                    f"<tr><td>{row['ASSESSOR']}</td>"
                                    f"<td>{row['PRODUTO']}</td>"
                                    f"<td>{row['PERCENTUAL ANTES']}%</td>"
                                    f"<td>{row['PERCENTUAL DEPOIS']}%</td>"
                                    f"<td>{row['TIMESTAMP']}</td></tr>"
                                    for _, row in st.session_state.df_envio.iterrows()
                                )
                                send_declaration_email(
                                    director_email=st.session_state.dados_lider["EMAIL_LIDER"],
                                    juridico_email="comissoes@investsmart.com.br",
                                    lider_name=st.session_state.dados_lider["LIDER"],
                                    filial=selected_filial,
                                    items_html=items_html,
                                    timestamp_display=None
                                )
                                # Atualiza percentuais na tabela assessores
                                for _, row in aprovados.iterrows():
                                    produto_col = row["PRODUTO"]
                                    novo_val = int(round(parse_valor_percentual(row["PERCENTUAL DEPOIS"]) * 100))

                                    resp = (
                                        supabase.table("assessores")
                                        .select("ID")
                                        .eq("NOME", str(row["ASSESSOR"] or "").strip())
                                        .eq("FILIAL", selected_filial_up)
                                        .single()
                                        .execute()
                                    )
                                    if resp.data:
                                        supabase.table("assessores") \
                                            .update({produto_col: novo_val}) \
                                            .eq("ID", resp.data["ID"]) \
                                            .execute()
                                st.success("Declaração aprovada.")

                                st.cache_data.clear()
                                st.rerun()
                            except Exception as err:
                                st.error(f"Erro ao aprovar declaração: {err}")
                            finally:
                                st.session_state.declaration_pending = False
                                st.session_state["refresh_validation"] = not st.session_state.get("refresh_validation", False)

        # ── Somente visualização: Super/Leaders, RM e Comissões ──
        elif level in (4, 5, 6):
            if df_pend.empty:
                st.info("Não há solicitações pendentes para validação.")
            else:
                df_view = df_pend.copy()
                df_view["Data e Hora"] = (
                    pd.to_datetime(df_view["TIMESTAMP"], errors="coerce")
                    .dt.strftime("%d/%m/%Y às %H:%M")
                )
                # captura o diretor da filial
                diretor_nome = df_filial_lider.iloc[0]["DIRETOR"]

                # mantém USUARIO original para gerar a coluna "Solicitante"
                df_view = df_view.rename(columns={
                    "USUARIO":            "Solicitante",
                    "ASSESSOR":           "Assessor",
                    "PRODUTO":            "Produto",
                    "PERCENTUAL ANTES":   "Percentual Antes",
                    "PERCENTUAL DEPOIS":  "Percentual Depois",
                    "COMENTARIO DIRETOR": "Comentário do Diretor",
                })

                # cria coluna Diretor com valor fixo da filial
                df_view["Diretor"] = diretor_nome

                # identifica o papel do solicitante
                def _identificar_papel(nome):
                    nome_up = nome.strip().upper()
                    if nome_up == str(df_filial_lider.iloc[0]["LIDER"]).strip().upper():
                        return "LÍDER"
                    elif nome_up == str(df_filial_lider.iloc[0].get("LIDER2","")).strip().upper():
                        return "LÍDER 2"
                    elif nome_up == str(df_filial_lider.iloc[0]["DIRETOR"]).strip().upper():
                        return "DIRETOR"
                    elif nome_up == str(df_filial_lider.iloc[0].get("SUPERINTENDENTE","")).strip().upper():
                        return "SUPERINTENDENTE"
                    return nome  # fallback

                df_view["Solicitante"] = df_view["Solicitante"].apply(lambda x: f"{_identificar_papel(x)} - {x}")

                # status
                def _status(row):
                    if row["ALTERACAO APROVADA"] == "SIM":
                        return "Aprovado"
                    if row["ALTERACAO APROVADA"] == "NAO" and isinstance(row["Comentário do Diretor"], str) and row["Comentário do Diretor"].strip():
                        return "Recusado"
                    return "Aguardando..."

                df_view["Resposta Diretor"] = df_view.apply(_status, axis=1)

                # nova ordem de colunas
                df_view = df_view[[
                    "Data e Hora", "Diretor", "Solicitante", "Assessor", "Produto",
                    "Percentual Antes", "Percentual Depois",
                    "Resposta Diretor", "Comentário do Diretor"
                ]]

                st.dataframe(df_view, use_container_width=True, hide_index=True)

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