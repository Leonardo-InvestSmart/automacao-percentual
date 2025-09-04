# modules/comissoes.py
import pandas as pd
import streamlit as st
import altair as alt

from modules.db import _ler_tabela  # reusa o reader já existente (chunked)

def _fmt_brl(x: float) -> str:
    try:
        return ("R$ " + f"{float(x):,.2f}").replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return str(x)

# cache ~35 dias; sem spinner (não aparece a tarja "Running ...")
@st.cache_data(ttl=60*60*24*25, show_spinner=False, max_entries=1)
def _carregar_comissoes_filial() -> pd.DataFrame:
    """
    Carrega e unifica comissoes_ajuste + comissoes_origem
    Colunas (UPPER): DT_REF, NOME_FILIAL, QUEM_RECEBE, SIGLA_RECEBEDOR, 
                     VLR_COMISSAO_BRUTA, VLR_COMISSAO_LIQUIDA
    """
    cols = [
        "ID", "DT_REF", "NOME_FILIAL", "QUEM_RECEBE", "SIGLA_RECEBEDOR",
        "VLR_COMISSAO_BRUTA", "VLR_COMISSAO_LIQUIDA"
    ]
    a = _ler_tabela("comissoes_ajuste", columns=cols)
    b = _ler_tabela("comissoes_origem", columns=cols)
    df = pd.concat([a, b], ignore_index=True)

    if df.empty:
        return df

    # Tipagem / normalização
    df["DT_REF"]               = pd.to_datetime(df["DT_REF"], errors="coerce")
    df["NOME_FILIAL"]          = df["NOME_FILIAL"].astype(str).str.strip().str.upper()
    df["QUEM_RECEBE"]          = df["QUEM_RECEBE"].astype(str).str.strip().str.upper()
    df["SIGLA_RECEBEDOR"]      = df["SIGLA_RECEBEDOR"].astype(str).str.strip().str.upper()
    df["VLR_COMISSAO_BRUTA"]   = pd.to_numeric(df["VLR_COMISSAO_BRUTA"], errors="coerce").fillna(0.0)
    df["VLR_COMISSAO_LIQUIDA"] = pd.to_numeric(df["VLR_COMISSAO_LIQUIDA"], errors="coerce").fillna(0.0)
    df["MES"]                  = df["DT_REF"].dt.to_period("M").astype(str)

    return df.dropna(subset=["DT_REF"])


def display_comissoes(df_assessores: pd.DataFrame, filial_selecionada: str) -> None:
    """
    Página 'Comissões': join com assessores, filtros e visualizações.
    - df_assessores: DataFrame completo já carregado pelo app
    - filial_selecionada: string (ex.: 'TAMBORE')
    """
    title_ph = st.empty()

    # CSS para cards (mesma linha editorial dos seus dashboards)
    st.markdown("""
    <style>
    .metric-box{
    flex:1;
    background:#FFF;
    border:2px solid #8B5CF6;
    border-radius:12px;
    height:115px;                     /* ↑ aumenta a altura */
    padding:12px 16px 10px 16px;
    display:flex;
    flex-direction:column;
    justify-content:flex-start;
    align-items:center;               /* garante alinhamento horizontal */
    text-align:center;
    color:#111;
    }
    .metric-box h3{
    margin:0;
    font-size:1.4rem;                /* ↓ diminui o tamanho do valor */
    line-height:1.15;
    font-weight:700;
    }
    .metric-box .subline{
    margin-top:4px;                   /* aproxima do valor */
    font-size:.78rem;
    line-height:1.1;
    color:#6B7280;
    font-weight:600;
    }
    .metric-box p{
    margin:0;
    margin-top:auto;                  /* título sempre no rodapé do card */
    font-size:.72rem;
    color:#6B7280;
    text-transform:uppercase;
    letter-spacing:.02em;
    }

    /* Ajuste específico: subir mais o percentual do “Repasse Filial” */
    .metric-box--repasse .subline{
    transform:translateY(-4px);       /* sobe visualmente */
    font-weight:700;
    }
    </style>
    """, unsafe_allow_html=True)



    # 1) Carga (com GIF leve apenas na 1ª execução)
    ph_loader = st.empty()
    try:
        ph_loader.image("https://i.gifer.com/6md.gif", width=64)
        df_all = _carregar_comissoes_filial()
    finally:
        ph_loader.empty()

    if df_all.empty:
        st.info("Sem dados nas tabelas 'comissoes_ajuste' / 'comissoes_origem'.")
        return

    sel_filial_up = (filial_selecionada or "").strip().upper()
    m = df_all[df_all["NOME_FILIAL"] == sel_filial_up].copy()
    if m.empty:
        st.info(f"Não há registros para a filial **{filial_selecionada}**.")
        return

    # Normaliza assessores e adiciona NOME à base filtrada m
    df_ass = df_assessores[["SIGLA", "NOME", "FILIAL"]].copy()
    df_ass["SIGLA_MERGE"] = df_ass["SIGLA"].astype(str).str.strip().str.upper()
    df_ass["FILIAL"] = df_ass["FILIAL"].astype(str).str.strip().str.upper()

    m["SIGLA_MERGE"] = m["SIGLA_RECEBEDOR"].astype(str).str.strip().str.upper()
    m = m.merge(df_ass[["SIGLA_MERGE", "NOME"]], on="SIGLA_MERGE", how="left")

    # Para linhas de EQUIPE/ESCRITÓRIO que não são assessor, usamos o nome da FILIAL
    m["NOME"] = m.apply(
        lambda r: r["NOME"] if pd.notna(r["NOME"]) and r["QUEM_RECEBE"] == "ASSESSOR" else r["NOME_FILIAL"],
        axis=1
    )

    # Título fixo da página
    title_ph = st.empty()

    # Aviso importante em amarelo (igual Gestão de Percentuais)
    st.markdown("""
    <div style="
        background-color: #ebff70;
        color: #000000;
        font-weight: bold;
        text-transform: uppercase;
        padding: 0.75rem 1rem;
        border-radius: 0.25rem;
        border-left: 5px solid #ebff70;
        margin: 1rem 0;
        font-size: 0.75rem;
    ">
    AVISO IMPORTANTE: 100% DAS INFORMAÇÕES EXIBIDAS TEM POR ORIGEM O SPLITC, SISTEMA DE COMISSÕES E REFLETE O QUE FOI APURADO E PAGO PARA A FILIAL E ASSESSOR. LEMBRANDO QUE OS DADOS HISTORICOS NÃO SOFREM ALTERAÇÕES QUANDO HÁ MOVIMENTAÇÃO DE ASSESSORES ENTRE FILIAIS.<br><br>
    OS PAINÉIS BI, CAMPANHAS E SUPORTE AO PARTNERSHIP NÃO PERTENCEM À COMISSÕES E USAM BASES PRÓPRIAS PARA SUAS APURAÇÕES
    </div>
    """, unsafe_allow_html=True)

    title_ph.subheader("Visão de Comissões - Filial")


    # A base de trabalho agora é sempre 'm' (já filtrada por filial e mês)
    df = m.copy()

    # 3) Filtros adicionais (sem categoria)
    meses = ["Todos"] + sorted(df["MES"].dropna().unique().tolist())
    nomes = ["Todos"] + sorted(df["NOME"].dropna().unique().tolist())

    m = df.copy()
    c1, c2, c3 = st.columns(3)
    with c1:
        nome_sel = st.selectbox("Assessor", nomes, index=0, key="f_nome_comissoes")
    with c2:
        mes_sel  = st.selectbox("Mês de referência", meses, index=0, key="f_mes_comissoes")
    with c3:
        quem_opts = ["Todos"] + sorted(df["QUEM_RECEBE"].dropna().unique().tolist())
        quem_sel  = st.selectbox("Quem recebe", quem_opts, index=0, key="f_quem_comissoes")

    if nome_sel != "Todos":
        m = m[m["NOME"] == nome_sel]
    if mes_sel != "Todos":
        m = m[m["MES"] == mes_sel]
    if quem_sel != "Todos":
        m = m[m["QUEM_RECEBE"] == quem_sel]

    if nome_sel != "Todos":
        m = m[m["NOME"] == nome_sel]
    if mes_sel != "Todos":
        m = m[m["MES"] == mes_sel]

    if m.empty:
        st.warning("Nenhum registro para os filtros selecionados.")
        return
    
    st.markdown("---")

    # ==== KPIs versão Filial ====
    faturamento = float(m["VLR_COMISSAO_BRUTA"].sum())
    impostos    = faturamento * 0.20
    rl          = faturamento - impostos

    repasse_filial = float(m.loc[m["QUEM_RECEBE"].isin(["ASSESSOR","EQUIPE", "EXTERNO"]), "VLR_COMISSAO_LIQUIDA"].sum())
    comissoes      = float(m.loc[m["QUEM_RECEBE"].isin(["ASSESSOR", "EXTERNO"]), "VLR_COMISSAO_LIQUIDA"].sum())
    lucro_bruto    = repasse_filial - comissoes  # conforme solicitado

    # % do repasse sobre a RL (evita divisão por zero)
    perc_repasse_rl = (repasse_filial / rl) if rl else 0.0
    perc_repasse_txt = f"{perc_repasse_rl:.2%}".replace(".", ",")  # padrão BR

    # Bordas específicas solicitadas
    BORDAS = {
        "Faturamento": "#000000",                      # preto
        "(=) Receita Líquida “RL”": "#000000",         # preto
        "(-) Impostos": "#A9ABAF",                     # cinza claro
        "(-) Comissões": "#A9ABAF",                    # cinza claro
        # demais ficam com a cor padrão do CSS (roxo) se não especificado
    }

    # Monta estrutura rica por card
    cards = [
        {"title": "Faturamento",               "val": faturamento,   "neg": False, "mid": None},
        {"title": "(-) Impostos",              "val": impostos,      "neg": True,  "mid": None},
        {"title": "(=) Receita Líquida “RL”",  "val": rl,            "neg": False, "mid": None},
        # aqui entra a linha extra com percentual entre valor e título
        {"title": "(%) Repasse Filial",        "val": repasse_filial,"neg": False, "mid": f"{perc_repasse_txt} da RL"},
        {"title": "(-) Comissões",             "val": comissoes,     "neg": True,  "mid": None},
        {"title": "(=) Lucro Bruto Filial",    "val": lucro_bruto,   "neg": False, "mid": None},
    ]

    cols = st.columns(len(cards), gap="small")
    for card, col in zip(cards, cols):
        # Valor formatado (com “– ” quando for negativo por natureza do indicador)
        val_fmt = _fmt_brl(card["val"])
        if card.get("neg"):
            val_fmt = f"− {val_fmt}"  # usa traço “minus” visualmente consistente

        # Borda específica por card (fallback para roxo definido no CSS)
        borda = BORDAS.get(card["title"], None)
        style_border = f'style="border-color:{borda};"' if borda else ""

        # Linha intermediária (percentual) quando existir
        # marca se é o card de Repasse
        is_repasse = (card["title"] == "(%) Repasse Filial")
        box_class  = "metric-box metric-box--repasse" if is_repasse else "metric-box"

        mid_html = (
            f'<div class="subline">{card["mid"]}</div>'
            if card.get("mid") else ""
        )

        col.markdown(
            f"""
            <div class="{box_class}" {style_border}>
            <h3>{val_fmt}</h3>
            {mid_html}
            <p>{card["title"]}</p>
            </div>
            """,
            unsafe_allow_html=True
        )



    st.markdown("---")

    # 5) Pareto por Assessores

    st.markdown("**Pareto do 'Lucro Bruto' por Assessores**")

    df_ass_pareto = (
        m.loc[m["QUEM_RECEBE"].isin(["ASSESSOR","EXTERNO"])]
        .groupby("NOME", as_index=False)["VLR_COMISSAO_LIQUIDA"]
        .sum()
        .rename(columns={"VLR_COMISSAO_LIQUIDA": "VALOR"})
    )

    if df_ass_pareto.empty:
        st.info("Não há comissões de assessores no recorte selecionado.")
    else:
        df_ass_pareto = df_ass_pareto.sort_values("VALOR", ascending=False).reset_index(drop=True)
        total_val = float(df_ass_pareto["VALOR"].sum())
        df_ass_pareto["ACUM"]      = df_ass_pareto["VALOR"].cumsum()
        df_ass_pareto["ACUM_PCT"]  = (df_ass_pareto["ACUM"] / total_val).fillna(0.0)  # 0–1

        # Barras (VALOR) + Linha (ACUM_% com eixo secundário)
        bars = (
            alt.Chart(df_ass_pareto)
            .mark_bar(color="#9966FF")
            .encode(
                x=alt.X("NOME:N", sort="-y", title="Assessores (ordem decrescente)"),
                y=alt.Y("VALOR:Q", axis=alt.Axis(title="Valor absoluto (R$)", orient="left")),
                tooltip=[alt.Tooltip("NOME:N"), alt.Tooltip("VALOR:Q", format=",.2f")]
            )
        )

        # texto com os valores em cima das barras
        text_labels = (
            alt.Chart(df_ass_pareto)
            .mark_text(align="center", baseline="bottom", dy=-5, fontSize=12, color="black")
            .encode(
                x=alt.X("NOME:N", sort="-y"),
                y=alt.Y("VALOR:Q", axis=None),          # <- desliga o eixo deste layer
                text=alt.Text("VALOR:Q", format=",.0f")
            )
        )

        line = (
            alt.Chart(df_ass_pareto)
            .mark_line(
                color="#000000",
                strokeWidth=2.5,
                point=alt.OverlayMarkDef(filled=True, color="#000000")
            )
            .encode(
                x=alt.X("NOME:N", sort="-y"),
                y=alt.Y(
                    "ACUM_PCT:Q",
                    axis=alt.Axis(title="% acumulado", orient="right", format=".0%"),  # só mantém eixo da direita
                    scale=alt.Scale(domain=[0, 1], nice=False, clamp=True)
                ),
                tooltip=[
                    alt.Tooltip("NOME:N", title="Assessor"),
                    alt.Tooltip("ACUM_PCT:Q", format=".1%", title="% acumulado")
                ]
            )
        )


        st.altair_chart(
            alt.layer(bars, text_labels, line)
            .resolve_scale(y="independent")
            .properties(height=360),
            use_container_width=True
        )


    st.markdown("---")

    # ==== Representação do Lucro Bruto e Margem da Filial (competência) ====
    st.markdown("**Representação do Lucro Bruto e Margem da Filial no regime de competência (Liquidação no mês subsequente)**")

    g_mes = (
        m.groupby("MES", as_index=False)
        .agg(
            FATURAMENTO=("VLR_COMISSAO_BRUTA", "sum"),
            REPASSE=("VLR_COMISSAO_LIQUIDA", lambda s: float(m.loc[(m["MES"]==s.index.get_level_values(0)[0]) & (m["QUEM_RECEBE"].isin(["ASSESSOR","EQUIPE"])),"VLR_COMISSAO_LIQUIDA"].sum())),
            COMISSOES=("VLR_COMISSAO_LIQUIDA", lambda s: float(m.loc[(m["MES"]==s.index.get_level_values(0)[0]) & (m["QUEM_RECEBE"]=="ASSESSOR"),"VLR_COMISSAO_LIQUIDA"].sum()))
        )
        .sort_values("MES")
    )

    # Ajuste das agregações (mais explícito e estável)
    tmp = m.groupby(["MES","QUEM_RECEBE"], as_index=False)["VLR_COMISSAO_LIQUIDA"].sum()
    rep  = tmp[tmp["QUEM_RECEBE"].isin(["ASSESSOR","EQUIPE","EXTERNO"])].groupby("MES", as_index=False)["VLR_COMISSAO_LIQUIDA"].sum().rename(columns={"VLR_COMISSAO_LIQUIDA":"REPASSE"})
    com  = tmp[tmp["QUEM_RECEBE"].isin(["ASSESSOR","EXTERNO"])].groupby("MES", as_index=False)["VLR_COMISSAO_LIQUIDA"].sum().rename(columns={"VLR_COMISSAO_LIQUIDA":"COMISSOES"})
    fat  = m.groupby("MES", as_index=False)["VLR_COMISSAO_BRUTA"].sum().rename(columns={"VLR_COMISSAO_BRUTA":"FATURAMENTO"})

    g_mes = fat.merge(rep, on="MES", how="left").merge(com, on="MES", how="left").fillna(0.0)
    g_mes["LUCRO BRUTO FILIAL"]  = g_mes["REPASSE"] - g_mes["COMISSOES"]
    g_mes["MARGEM"] = (g_mes["LUCRO BRUTO FILIAL"] / g_mes["REPASSE"]).replace([float("inf"), -float("inf")], 0.0).fillna(0.0)
    # TOTAL agora representa apenas o que é exibido nas barras (COMISSÕES + LUCRO BRUTO FILIAL)
    g_mes["TOTAL"] = g_mes[["COMISSOES", "LUCRO BRUTO FILIAL"]].sum(axis=1)


    base = alt.Chart(g_mes).encode(x=alt.X("MES:N", title="Mês (YYYY-MM)"))

    bars = base.mark_bar().encode(
        y=alt.Y("value:Q", title="Valores (R$)"),
        color=alt.Color(
            "variavel:N",
            legend=alt.Legend(title="Séries"),
            scale=alt.Scale(                             # <- cores fixas por série
                domain=["COMISSOES", "LUCRO BRUTO FILIAL"],
                range=["#8B5CF6", "#887575"]            # COMISSÕES=preto | LBF=roxo SmartC
            )
        ),
        tooltip=[
            "MES",
            alt.Tooltip("variavel:N", title="Série"),
            alt.Tooltip("value:Q", format=",.2f", title="R$")
        ]
    ).transform_fold(
        fold=["COMISSOES","LUCRO BRUTO FILIAL"], as_=["variavel","value"]
    )

    line = (
        base
        .mark_line(
            color="#000000",
            point=alt.OverlayMarkDef(filled=True, color="#000000")
        )
        .encode(
            y=alt.Y(
                "MARGEM:Q",
                axis=alt.Axis(title="Margem Bruta (L/R)", orient="right"),
                scale=alt.Scale(domain=[0, 1.15], nice=False, clamp=True)
            ),
            tooltip=["MES", alt.Tooltip("MARGEM:Q", format=".0%")]
        )
    )

    # ===== labels =====
    # 1) label TOTAL no topo das barras (um por mês)
    total_labels = (
        alt.Chart(g_mes)
        .mark_text(align="center", baseline="bottom", dy=-6, fontSize=13, color="black")
        .encode(
            x="MES:N",
            y=alt.Y("TOTAL:Q", axis=None),           # não cria eixo extra
            text=alt.Text("TOTAL:Q", format=",.0f")
        )
    )

    # 2) label da linha (margem %) sobre cada ponto — usa a MESMA escala do eixo da direita
    line_labels = (
        alt.Chart(g_mes)
        .mark_text(align="center", baseline="bottom", dy=-6, fontSize=12, color="#FFFFFF")
        .encode(
            x="MES:N",
            y=alt.Y(
                "MARGEM:Q",
                axis=None,
                scale=alt.Scale(domain=[0, 1.15])   # mesmo domínio do eixo direito
            ),
            text=alt.Text("MARGEM:Q", format=".0%")
        )
    )

    ch = (
        alt.layer(bars, line, total_labels, line_labels)
        .resolve_scale(y="independent")   # mantém os eixos independentes
        .properties(height=460)           # aumenta a altura total do chart
    )

    st.altair_chart(ch, use_container_width=True)

    st.markdown("---")

    # 8) Pivot opcional — Assessor x Meses (soma comissão)
    st.markdown("**Comissão Mensal por Assessor**")
    pvt = (
        m.pivot_table(
            index="NOME",
            columns="MES",
            values="VLR_COMISSAO_LIQUIDA",
            aggfunc="sum",
            fill_value=0.0,
        )
        .sort_index()
    )
    pvt = pvt.applymap(_fmt_brl)
    st.dataframe(pvt, use_container_width=True)