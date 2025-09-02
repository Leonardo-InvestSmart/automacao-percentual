import pandas as pd
import altair as alt
import streamlit as st
import textwrap

from modules.formatters import parse_valor_percentual, formatar_para_exibir

def display_analytics(
    df_log,
    df_assessores_filial,
    df_filial_do_lider,
    col_perc,
    nome_lider,
    filial_lider,
    is_b2c,
    role,
    level
):
    
    
    # — parse de Timestamp, drop de timezone e eliminação de linhas inválidas —
    df_log["TIMESTAMP"] = df_log["TIMESTAMP"].astype(str).str.strip()
    df_log["DataHora"] = pd.to_datetime(
        df_log["TIMESTAMP"],
        utc=True,            # lê igual "2025-07-04T11:28:16+00:00"
        errors="coerce"
    ).dt.tz_localize(None)
    df_log = df_log.dropna(subset=["DataHora"])

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

    base_mask = (
        (df_log["FILIAL"].str.upper() == filial_lider.strip().upper()) &
        (df_log["DataHora"].dt.date >= start_date) &
        (df_log["DataHora"].dt.date <= end_date)
    )

    mask = base_mask

    df_periodo = df_log.loc[mask].copy()


    total_alt      = df_periodo.shape[0]
    num_ass        = df_assessores_filial.shape[0]
    one_month_ago  = pd.to_datetime(end_date) - pd.DateOffset(months=1)
    alt_last_month = df_periodo[df_periodo["DataHora"] >= one_month_ago].shape[0]

    # Média geral dos percentuais da filial (robusto a falta de colunas)
    cols_validos = [c for c in col_perc if c in df_assessores_filial.columns]

    if cols_validos:
        media_percentual = (
            df_assessores_filial[cols_validos]
            .applymap(parse_valor_percentual)
            .stack()
            .mean()
        ) * 100
    else:
        media_percentual = 0.0

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
            f"<div style='font-size:17px; font-weight:bold; margin-bottom:4px;'>{label}</div>"
            f"<div style='font-size:28px; color:#111;'>{value}</div>",
            unsafe_allow_html=True
        )

    st.markdown("---")

    # — Histórico de alterações da filial (com quem fez) —
    st.markdown("**Histórico de Alterações de Percentual da Filial**")

    # inclui TODAS as alterações do período/filial (sem filtrar VALIDACAO)
    df_hist = df_log.loc[
        base_mask,
        [
            "DataHora", "USUARIO", "ASSESSOR", "PRODUTO",
            "PERCENTUAL ANTES", "PERCENTUAL DEPOIS",
            "VALIDACAO NECESSARIA", "ALTERACAO APROVADA", "COMENTARIO DIRETOR"
        ]
    ].copy()

    # formata data e hora
    df_hist["Data e Hora"] = df_hist["DataHora"].dt.strftime("%d/%m/%Y às %H:%M:%S")

    # status de aprovação do diretor (cobre pendente/aprovado/recusado/não necessário)
    def _status(row):
        if str(row["VALIDACAO NECESSARIA"]).upper() == "SIM":
            return "Aguardando aprovação"
        # VALIDACAO == NAO
        if str(row["ALTERACAO APROVADA"]).upper() == "SIM":
            return "Aprovado"
        # Não aprovado e não precisa mais de validação → ou foi recusado, ou não era necessário
        old_v = parse_valor_percentual(str(row["PERCENTUAL ANTES"]))
        new_v = parse_valor_percentual(str(row["PERCENTUAL DEPOIS"]))
        if new_v >= old_v:
            return "Não foi necessário"
        return "Recusado"

    df_hist["Aprovação do Diretor"] = df_hist.apply(_status, axis=1)

    # organiza, renomeia e ordena por DataHora (mais recente primeiro)
    df_hist = df_hist[[
        "Data e Hora", "USUARIO", "ASSESSOR", "PRODUTO",
        "PERCENTUAL ANTES", "PERCENTUAL DEPOIS", "Aprovação do Diretor"
    ]].rename(columns={
        "USUARIO": "Usuário",
        "ASSESSOR": "Nome do Assessor",
        "PRODUTO": "Produto",
        "PERCENTUAL ANTES": "Percentual Antes",
        "PERCENTUAL DEPOIS": "Percentual Depois"
    }).sort_values("Data e Hora", ascending=False)

    st.dataframe(df_hist, use_container_width=True, hide_index=True)



    st.markdown("---")

    st.markdown("**Alterações por Mês**")

    if not df_periodo.empty:
        # agrupa mensalmente e conta as alterações
        df_time = (
            df_periodo
            .groupby(pd.Grouper(key="DataHora", freq="M"))["PRODUTO"]
            .count()
            .reset_index()
            .rename(columns={"PRODUTO": "Qtd Alterações"})
        )

        # — barras com largura fixa e tooltip igual ao gráfico de produto —
        bar_time = (
            alt.Chart(df_time)
            .mark_bar(color="black", size=60)  # força largura de 600px
            .encode(
                x=alt.X("DataHora:T", title="Mês", axis=alt.Axis(format="%b %Y")),
                y=alt.Y("Qtd Alterações:Q", title="Alterações"),
                tooltip=["Qtd Alterações"]
            )
        )

        # texto no topo da barra
        text_time = (
            alt.Chart(df_time)
            .mark_text(dy=-8, fontSize=14)
            .encode(
                x=alt.X("DataHora:T", axis=alt.Axis(format="%b %Y")),
                y=alt.Y("Qtd Alterações:Q"),
                text=alt.Text("Qtd Alterações:Q")
            )
        )

        chart_time = (
            (bar_time + text_time)
            .properties(height=300)
        )

        st.altair_chart(chart_time, use_container_width=True)


    st.markdown("---")

    st.markdown("**Média de percentual por assessor**")
    df_ass_med = pd.DataFrame([
        {
            "Assessor": row["NOME"],
            "Média (%)": f"{(sum(parse_valor_percentual(row[c]) for c in col_perc)/len(col_perc))*100:.1f}"
        }
        for _, row in df_assessores_filial.iterrows()
    ])
    st.dataframe(df_ass_med, use_container_width=True)

    st.markdown("---")

    st.markdown("**Média (%) por Produto**")

    df_medias = pd.DataFrame({
        "Produto": col_perc,
        "Média (%)": [
            df_assessores_filial[c].apply(parse_valor_percentual).mean() * 100
            for c in col_perc
        ]
    })
    bar_prod = (
        alt.Chart(df_medias)
        .mark_bar(color="black")
        .encode(
            x=alt.X("Produto:N", sort="-y", title="Produto"),
            y=alt.Y("Média (%):Q", title="Média (%)"),
            tooltip=["Produto", "Média (%)"]
        )
    )

    # texto com valor no topo
    text_prod = (
        alt.Chart(df_medias)
        .mark_text(
            dy=-8,        # posiciona acima da barra
            fontSize=14
        )
        .encode(
            x=alt.X("Produto:N", sort="-y"),
            y=alt.Y("Média (%):Q"),
            text=alt.Text("Média (%):Q", format=".1f")
        )
    )

    # calcula o valor máximo para definir altura dinâmica
    max_val = df_medias["Média (%)"].max()
    # usa 6px por ponto percentual + 20px de folga para o texto
    dynamic_height = int(max_val * 6) + 20

    # combina barras e texto, ajustando apenas a altura
    chart_prod = (
        (bar_prod + text_prod)
        .properties(height=dynamic_height)
    )
    st.altair_chart(chart_prod, use_container_width=True)


    st.markdown("---")

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
            # quebra em linhas de até 12 caracteres
            label = "\n".join(textwrap.wrap(c, width=12))
            col_widget.metric(label, teto_display[c])

        # use <hr> customizado para controlar margens
        st.markdown(
            "<hr style='margin-top:0.5rem; margin-bottom:1rem;'/>",
            unsafe_allow_html=True
        )
