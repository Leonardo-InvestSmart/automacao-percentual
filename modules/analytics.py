import pandas as pd
import altair as alt
import streamlit as st

from modules.formatters import parse_valor_percentual, formatar_para_exibir

def display_analytics(
    df_log,
    df_assessores_filial,
    df_filial_do_lider,
    col_perc,
    nome_lider,
    filial_lider,
    is_b2c
):
    # — parse de Timestamp, drop de timezone e eliminação de linhas inválidas —
    df_log["TIMESTAMP"] = df_log["TIMESTAMP"].astype(str).str.strip()
    df_log["DataHora"] = pd.to_datetime(
        df_log["TIMESTAMP"],
        dayfirst=True,
        errors="coerce"
    )
    # remove o timezone para que fique datetime64[ns] sem tz
    df_log["DataHora"] = df_log["DataHora"].dt.tz_localize(None)

    # remove quaisquer registros sem DataHora válida
    df_log = df_log.dropna(subset=["DataHora"])

    # — define automaticamente o menor e maior dia presente no log —
    min_date = df_log["DataHora"].dt.date.min()
    max_date = df_log["DataHora"].dt.date.max()

    # — espaçamento acima do filtro de datas —
    st.markdown("<div style='margin-top:1.5rem;'></div>", unsafe_allow_html=True)

    # — widget de período: Início e Término lado a lado —
    col_start, col_end = st.columns(2)
    with col_start:
        start_date = st.date_input(
            "Data de Início",
            value=min_date,
            min_value=min_date,
            max_value=max_date
        )
    with col_end:
        end_date = st.date_input(
            "Data de Término",
            value=max_date,
            min_value=min_date,
            max_value=max_date
        )

    # — validação de intervalo e espaçamento abaixo do filtro —
    if end_date < start_date:
        st.error("Data de término não pode ser anterior à de início")
    st.markdown("<div style='margin-bottom:2rem;'></div>", unsafe_allow_html=True)



    # — aplica o filtro dinâmico de usuário, filial e período —
    mask = (
        (df_log["USUARIO"].str.upper() == nome_lider.strip().upper()) &
        (df_log["FILIAL"].str.upper() == filial_lider.strip().upper()) &
        (df_log["DataHora"].dt.date >= start_date) &
        (df_log["DataHora"].dt.date <= end_date)
    )
    df_periodo = df_log.loc[mask].copy()


    total_alt      = df_periodo.shape[0]
    num_ass        = df_assessores_filial.shape[0]
    one_month_ago  = pd.to_datetime(end_date) - pd.DateOffset(months=1)
    alt_last_month = df_periodo[df_periodo["DataHora"] >= one_month_ago].shape[0]

    # — Média geral dos percentuais da filial —
    media_percentual = (
        df_assessores_filial[col_perc]
        .applymap(parse_valor_percentual)
        .stack()
        .mean()
    ) * 100

    # — Variação média (%) das alterações no período —
    variacoes = []
    for _, row in df_periodo.iterrows():
        old = parse_valor_percentual(str(row["PERCENTUAL ANTES"]))
        new = parse_valor_percentual(str(row["PERCENTUAL DEPOIS"]))
        if old != 0:
            variacoes.append((new - old) / old * 100)
    variacao_media = sum(variacoes) / len(variacoes) if variacoes else 0

    # Exibe 5 “cartões” customizados com títulos maiores
    cols = st.columns(5)
    labels = [
        "👥 Assessores ativos",
        "🔄 Alterações no período",
        "📅 Alterações nos Últimos 30 dias",
        "📊 Média Simples de % dos AAI",
        "📈 Variação Mensal de Alterações"
    ]
    values = [
        num_ass,
        total_alt,
        alt_last_month,
        f"{media_percentual:.1f}%",
        f"{'↑' if variacao_media>=0 else '↓'} {abs(variacao_media):.1f}%"
    ]

    for col, label, value in zip(cols, labels, values):
        col.markdown(
            f"<div style='font-size:15px; font-weight:bold; margin-bottom:4px;'>{label}</div>"
            f"<div style='font-size:28px; color:#111;'>{value}</div>",
            unsafe_allow_html=True
        )

    st.markdown("---")

    if not df_periodo.empty:
        # agrupa mensalmente e conta as alterações
        df_time = (
            df_periodo
            .groupby(pd.Grouper(key="DataHora", freq="M"))["PRODUTO"]
            .count()
            .reset_index()
            .rename(columns={"PRODUTO": "Qtd Alterações"})
        )

        bar = alt.Chart(df_time).mark_bar(
            color="black",
            size=60  # ajusta a largura da barra
        ).encode(
            x=alt.X(
                "DataHora:T",
                title="Mês",
                axis=alt.Axis(format="%b %Y")
            ),
            y=alt.Y("Qtd Alterações:Q", title="Alterações")
        )

        # texto no topo das barras
        text = alt.Chart(df_time).mark_text(
            dy=-12, # altura da barra
            color="black",
            fontSize=16 # tamanho da fonte
        ).encode(
            x=alt.X("DataHora:T", axis=alt.Axis(format="%b %Y")),
            y=alt.Y("Qtd Alterações:Q"),
            text=alt.Text("Qtd Alterações:Q")
        )

        # sobrepõe barra + texto e adiciona título
        chart_time = (
            (bar + text)
            .properties(
                height=280, # altura do gráfico
                title="Alterações por Mês"
            )
        )

        st.altair_chart(chart_time, use_container_width=True)




    df_medias = pd.DataFrame({
        "Produto": col_perc,
        "Média (%)": [
            df_assessores_filial[c].apply(parse_valor_percentual).mean() * 100
            for c in col_perc
        ]
    })
    chart_prod = (
        alt.Chart(df_medias)
        .mark_bar()
        .encode(
            x=alt.X("Produto:N", sort="-y"),
            y=alt.Y("Média (%):Q", title="Média (%)"),
            tooltip=["Produto", "Média (%)"]
        )
        .properties(height=300)
    )
    st.altair_chart(chart_prod, use_container_width=True)

    st.markdown("**Média de percentual por assessor**")
    df_ass_med = pd.DataFrame([
        {
            "Assessor": row["NOME"],
            "Média (%)": f"{(sum(parse_valor_percentual(row[c]) for c in col_perc)/len(col_perc))*100:.1f}"
        }
        for _, row in df_assessores_filial.iterrows()
    ])
    st.dataframe(df_ass_med, use_container_width=True)

    st.markdown("**Teto de percentuais da filial**")
    if is_b2c:
        st.info("Filial B2C: não se aplica teto de percentual.")
    else:
        teto_vals = df_filial_do_lider.iloc[0][col_perc]
        teto_display = {
            c: formatar_para_exibir(teto_vals[c])
            for c in col_perc
        }
        cols = st.columns(len(col_perc))
        for c, col_widget in zip(col_perc, cols):
            col_widget.metric(c, teto_display[c])

    st.markdown("---")
