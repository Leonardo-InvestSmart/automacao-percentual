import pandas as pd
import altair as alt
import plotly.express as px
import streamlit as st
from datetime import date

from modules.db import carregar_acessos, carregar_alteracoes, carregar_filial
from modules.formatters import parse_valor_percentual

def display_admin_dashboard():
    # guard rail: se não for admin, barra
    if st.session_state.get("level") not in (1, 6):
        st.error("Acesso restrito: apenas Admin (1) e Leitura Global (6).")
        st.stop()

    st.subheader("Visão Geral da Plataforma (Admin)")

    df_acc  = carregar_acessos()
    df_alt  = carregar_alteracoes()
    df_fil  = carregar_filial()

    # Conversão de datas
    for df in (df_acc, df_alt):
        if "TIMESTAMP" in df.columns:
            df["TS"] = pd.to_datetime(df["TIMESTAMP"], errors="coerce", utc=True).dt.tz_localize(None)

    # Período (data mínima/máxima dos registros)
    min_d = min([d.min() for d in [df_acc.get("TS"), df_alt.get("TS")] if d is not None])
    max_d = max([d.max() for d in [df_acc.get("TS"), df_alt.get("TS")] if d is not None])

    c1, c2 = st.columns(2)
    with c1:
        start = st.date_input("Início", value=min_d.date() if pd.notnull(min_d) else date.today())
    with c2:
        end   = st.date_input("Término", value=max_d.date() if pd.notnull(max_d) else date.today())
    if end < start:
        st.error("Data de término não pode ser anterior à de início")
        st.stop()

    # Filtros por período
    mask_acc = df_acc["TS"].dt.date.between(start, end) if "TS" in df_acc else pd.Series([], dtype=bool)
    mask_alt = df_alt["TS"].dt.date.between(start, end) if "TS" in df_alt else pd.Series([], dtype=bool)

    acc_period = df_acc.loc[mask_acc].copy() if not df_acc.empty else df_acc
    alt_period = df_alt.loc[mask_alt].copy() if not df_alt.empty else df_alt

    # ===== Prep: Segmento por filial + função de status + coluna STATUS =====
    seg_por_filial = {}
    if not df_fil.empty and {"FILIAL","SEGMENTO"}.issubset(df_fil.columns):
        seg_por_filial = (
            df_fil.assign(FILIAL=df_fil["FILIAL"].astype(str).str.upper().str.strip())
                .set_index("FILIAL")["SEGMENTO"]
                .astype(str).str.upper().str.strip()
                .to_dict()
        )

    if not alt_period.empty and "FILIAL" in alt_period.columns:
        alt_period["SEGMENTO_FILIAL"] = (
            alt_period["FILIAL"].astype(str).str.upper().str.strip()
                    .map(seg_por_filial).fillna("")
        )

    def status_aprov(row):
        valnec = str(row.get("VALIDACAO NECESSARIA", "")).upper().strip()
        aprov  = str(row.get("ALTERACAO APROVADA", "")).upper().strip()
        tipo   = str(row.get("TIPO", "")).upper().strip()
        seg    = str(row.get("SEGMENTO_FILIAL", "")).upper().strip()

        if valnec == "SIM":
            return "Pendente"
        if valnec == "NAO" and aprov == "SIM":
            return "Aprovado"
        if valnec == "NAO" and aprov == "NAO":
            if tipo == "REDUCAO":
                return "Recusado"
            if tipo == "AUMENTO" and seg == "B2C":
                return "Recusado"
        if tipo == "AUMENTO" and seg == "B2B":
            return "Não necessário"
        return "Não necessário"

    if not alt_period.empty:
        alt_period["STATUS"] = alt_period.apply(status_aprov, axis=1)


    # ---- KPIs principais ----
    total_acessos = len(acc_period)
    users_unicos  = acc_period["USUARIO"].nunique() if "USUARIO" in acc_period else 0
    total_alts    = len(alt_period)

    # variação mensal de alterações (MoM)
    def _monthly_counts(df):
        if df.empty: 
            return pd.DataFrame({"mes":[],"qtd":[]})
        g = df.groupby(pd.Grouper(key="TS", freq="M")).size().reset_index(name="qtd")
        g["mes"] = g["TS"].dt.to_period("M").astype(str)
        return g[["mes","qtd"]]
    mcounts = _monthly_counts(alt_period)
    if len(mcounts) >= 2:
        mom = ((mcounts["qtd"].iloc[-1] - mcounts["qtd"].iloc[-2]) / max(mcounts["qtd"].iloc[-2], 1)) * 100
    else:
        mom = 0.0

    cols = st.columns(5)
    cards = [
        ("👤 Usuários únicos", users_unicos),
        ("🔑 Acessos (período)", total_acessos),
        ("🔄 Alterações (período)", total_alts),
        ("📈 Variação MoM de alterações", f"{'↑' if mom>=0 else '↓'} {abs(mom):.1f}%"),
        ("🏢 Filiais ativas no período", alt_period["FILIAL"].nunique() if "FILIAL" in alt_period else 0)
    ]
    for c,(lbl,val) in zip(cols, cards):
        c.markdown(f"<div style='font-size:17px;font-weight:bold;margin-bottom:4px'>{lbl}</div>"
                   f"<div style='font-size:28px;color:#111'>{val}</div>", unsafe_allow_html=True)

    st.markdown("---")

    # ---- Acessos por mês  |  Alterações por mês (lado a lado) ----
    c1, c2 = st.columns(2)

    with c1:
        st.markdown("**Acessos por Mês**")
        acc_m = _monthly_counts(acc_period)
        if not acc_m.empty:
            # barras pretas + rótulo no topo
            bar_acc = (
                alt.Chart(acc_m)
                .mark_bar(color="black", size=60)
                .encode(
                    x=alt.X("mes:N", title="Mês"),
                    y=alt.Y("qtd:Q", title="Acessos"),
                    tooltip=["mes", "qtd"]
                )
            )
            text_acc = (
                alt.Chart(acc_m)
                .mark_text(dy=-8, fontSize=14)
                .encode(
                    x=alt.X("mes:N"),
                    y=alt.Y("qtd:Q"),
                    text=alt.Text("qtd:Q")
                )
            )
            chart_acc = (bar_acc + text_acc).properties(height=300)
            st.altair_chart(chart_acc, use_container_width=True)
        else:
            st.info("Sem dados de acesso no período.")

    with c2:
        st.markdown("**Alterações por Mês**")
        alt_m = _monthly_counts(alt_period)
        if not alt_m.empty:
            bar_alt = (
                alt.Chart(alt_m)
                .mark_bar(color="black", size=60)
                .encode(
                    x=alt.X("mes:N", title="Mês"),
                    y=alt.Y("qtd:Q", title="Alterações"),
                    tooltip=["mes", "qtd"]
                )
            )
            text_alt = (
                alt.Chart(alt_m)
                .mark_text(dy=-8, fontSize=14)
                .encode(
                    x=alt.X("mes:N"),
                    y=alt.Y("qtd:Q"),
                    text=alt.Text("qtd:Q")
                )
            )
            chart_alt = (bar_alt + text_alt).properties(height=300)
            st.altair_chart(chart_alt, use_container_width=True)
        else:
            st.info("Sem alterações no período.")

    st.markdown("---")


    # ---- Alterações por Filial (Top 20) à esquerda | Roscas empilhadas à direita ----
    col_esq, col_dir = st.columns(2)  # 50/50

    with col_esq:
        st.markdown("**Alterações por Filial (Top 20)**")

        # Garante STATUS (fallback caso não tenha sido criado antes)
        if "STATUS" not in alt_period.columns and not alt_period.empty:
            if "SEGMENTO_FILIAL" not in alt_period.columns:
                seg_por_filial = {}
                if not df_fil.empty and {"FILIAL", "SEGMENTO"}.issubset(df_fil.columns):
                    seg_por_filial = (
                        df_fil.assign(FILIAL=df_fil["FILIAL"].astype(str).str.upper().str.strip())
                            .set_index("FILIAL")["SEGMENTO"]
                            .astype(str).str.upper().str.strip()
                            .to_dict()
                    )
                if "FILIAL" in alt_period.columns:
                    alt_period["SEGMENTO_FILIAL"] = (
                        alt_period["FILIAL"].astype(str).str.upper().str.strip()
                                .map(seg_por_filial).fillna("")
                    )

            def status_aprov(row):
                valnec = str(row.get("VALIDACAO NECESSARIA", "")).upper().strip()
                aprov  = str(row.get("ALTERACAO APROVADA", "")).upper().strip()
                tipo   = str(row.get("TIPO", "")).upper().strip()
                seg    = str(row.get("SEGMENTO_FILIAL", "")).upper().strip()
                if valnec == "SIM": return "Pendente"
                if valnec == "NAO" and aprov == "SIM": return "Aprovado"
                if valnec == "NAO" and aprov == "NAO":
                    if tipo == "REDUCAO": return "Recusado"
                    if tipo == "AUMENTO" and seg == "B2C": return "Recusado"
                if tipo == "AUMENTO" and seg == "B2B": return "Não necessário"
                return "Não necessário"

            alt_period["STATUS"] = alt_period.apply(status_aprov, axis=1)

        if not alt_period.empty and {"FILIAL", "STATUS"}.issubset(alt_period.columns):
            base_filial = alt_period.assign(FILIAL=alt_period["FILIAL"].astype(str).str.strip())

            grp = (
                base_filial.groupby(["FILIAL", "STATUS"], dropna=False)
                        .size()
                        .reset_index(name="Qtd")
            )

            # Top 20 por volume total
            topN = (
                grp.groupby("FILIAL")["Qtd"].sum()
                .sort_values(ascending=False)
                .head(20).index
            )
            topf = grp[grp["FILIAL"].isin(topN)]
            dynamic_height = max(220, 34 * len(topN))
            # Salva altura no estado p/ sincronizar com o gráfico de Produtos
            st.session_state["height_filial_top20"] = dynamic_height

            # --- barras empilhadas por STATUS (ordenadas pelo TOTAL desc.) ---
            bars_filial = (
                alt.Chart(topf)
                .mark_bar()
                .encode(
                    y=alt.Y("FILIAL:N", sort="-x", title="Filial"),  # usa total agregado do eixo X
                    x=alt.X("sum(Qtd):Q", title="Qtd", stack="zero"),
                    color=alt.Color(
                        "STATUS:N",
                        scale=alt.Scale(
                            domain=["Aprovado", "Pendente", "Recusado", "Não necessário"],
                            range=["#27A017", "#ffa500", "#c9251c", "#9ec9ff"]
                        ),
                        legend=alt.Legend(title="Status de Aprovação")
                    ),
                    tooltip=["FILIAL", "STATUS", "Qtd"]
                )
                .properties(height=dynamic_height)
            )

            # totais por filial para rótulos do somatório
            totais = (
                topf.groupby("FILIAL", as_index=False)["Qtd"].sum()
                    .rename(columns={"Qtd": "Total"})
            )

            labels_total = (
                alt.Chart(totais)
                .mark_text(align="left", dx=6, fontSize=13)
                .encode(
                    y=alt.Y("FILIAL:N", sort=alt.SortField(field="Total", order="descending")),
                    x=alt.X("Total:Q"),
                    text=alt.Text("Total:Q")
                )
            )

            # (opcional) rótulos por STATUS dentro da barra (somente pedaços maiores)
            labels_segmento = (
                alt.Chart(topf)
                .transform_filter("datum.Qtd >= 8")
                .mark_text(align="right", dx=-4, fontSize=11, color="white")
                .encode(
                    y=alt.Y("FILIAL:N", sort="-x"),
                    x=alt.X("sum(Qtd):Q", stack="zero"),
                    detail="STATUS:N",
                    text=alt.Text("sum(Qtd):Q")
                )
            )

            chart_filial = bars_filial + labels_total + labels_segmento
            st.altair_chart(chart_filial, use_container_width=True)
        else:
            st.info("Sem dados por filial no período.")

    with col_dir:
        st.markdown("**Produtos efetivados por tipo (Aumento vs Redução)**")

        # somente efetivados (aprovados); pendentes/recusados ficam fora
        df_eff = alt_period.copy()
        if not df_eff.empty and {"PRODUTO", "TIPO", "STATUS"}.issubset(df_eff.columns):
            df_eff = df_eff[df_eff["STATUS"].isin(["Aprovado", "Não necessário"])]
            df_eff = df_eff[df_eff["TIPO"].isin(["AUMENTO", "REDUCAO"])]

            prod_grp = (
                df_eff
                .groupby(["PRODUTO", "TIPO"], dropna=False)
                .size()
                .reset_index(name="Qtd")
            )

            # Top N por volume total de efetivações
            top_prod = (
                prod_grp.groupby("PRODUTO")["Qtd"].sum()
                .sort_values(ascending=False)
                .head(20).index
            )
            prod_top = prod_grp[prod_grp["PRODUTO"].isin(top_prod)]

            # Altura igual à do gráfico "Alterações por Filial (Top 20)"
            height_left = st.session_state.get("height_filial_top20", max(240, 28*len(top_prod)))

            # --- barras empilhadas por TIPO (mesma arquitetura do gráfico de Filial) ---
            bars_prod = (
                alt.Chart(prod_top)
                .mark_bar()
                .encode(
                    y=alt.Y("PRODUTO:N", sort="-x", title="Produto"),
                    x=alt.X("sum(Qtd):Q", title="Qtd", stack="zero"),
                    color=alt.Color(
                        "TIPO:N",
                        scale=alt.Scale(domain=["AUMENTO","REDUCAO"], range=["#9966ff","#000000"]),
                        legend=alt.Legend(title="Tipo")
                    ),
                    tooltip=["PRODUTO","TIPO","Qtd"]
                )
            )

            # --- rótulos por segmento (AUMENTO/REDUCAO) ---
            # mantém a mesma régua do gráfico "Alterações por Filial (Top 20)"
            LABEL_MIN = 7  # ajuste aqui se quiser mais/menos rótulos

            labels_segmento_prod = (
                alt.Chart(prod_top)
                .transform_aggregate(Qtd="sum(Qtd)", groupby=["PRODUTO","TIPO"])
                .transform_filter(f"datum.Qtd >= {LABEL_MIN}")  # só rotula pedaços relevantes
                .mark_text(align="right", dx=-4, fontSize=11, color="white")
                .encode(
                    y=alt.Y("PRODUTO:N", sort="-x"),
                    x=alt.X("Qtd:Q", stack="zero"),
                    detail="TIPO:N",
                    text=alt.Text("Qtd:Q")
                )
            )

            # --- rótulo TOTAL no final da barra ---
            totais_prod = (
                prod_top.groupby("PRODUTO", as_index=False)["Qtd"].sum()
                .rename(columns={"Qtd": "Total"})
            )
            labels_total_prod = (
                alt.Chart(totais_prod)
                .mark_text(align="left", dx=6, fontSize=13)
                .encode(
                    y=alt.Y("PRODUTO:N", sort=alt.SortField(field="Total", order="descending")),
                    x=alt.X("Total:Q"),
                    text=alt.Text("Total:Q")
                )
            )

            # --- composição final sem padding customizado (espelha o gráfico de Filial) ---
            chart_prod = (bars_prod + labels_segmento_prod + labels_total_prod).properties(height=height_left)
            st.altair_chart(chart_prod, use_container_width=True)

        else:
            st.info("Sem dados de produtos efetivados no período.")

    # ---- linha inferior: roscas lado a lado ----
    st.markdown("---")
    rosc1, rosc2 = st.columns(2)

    with rosc1:
        st.markdown("**Distribuição por Tipo de Alteração**")
        if not alt_period.empty and "TIPO" in alt_period.columns:
            dist = alt_period["TIPO"].value_counts().reset_index()
            dist.columns = ["Tipo", "Qtd"]
            fig_tipo = px.pie(
                dist, names="Tipo", values="Qtd", hole=0.55,
                color="Tipo",
                color_discrete_map={"AUMENTO": "#9966ff", "REDUCAO": "#000000"}
            )
            fig_tipo.update_traces(
                texttemplate="<b>%{value} (%{percent:.1%})</b>",
                textposition="outside",
                marker=dict(line=dict(color="#ffffff", width=6))
            )
            fig_tipo.update_layout(
                height=260,
                margin=dict(t=10, b=50, l=0, r=0),
                legend=dict(orientation="h", y=-0.25, x=0.5, xanchor="center")
            )
            st.plotly_chart(fig_tipo, use_container_width=True)
        else:
            st.info("Sem tipos de alteração no período.")

    with rosc2:
        st.markdown("**Status de Aprovação**")
        if not alt_period.empty:
            ordem = ["Aprovado", "Pendente", "Recusado", "Não necessário"]
            d2 = (
                alt_period["STATUS"].value_counts(dropna=False)
                .rename_axis("Status")
                .reindex(ordem, fill_value=0)
                .reset_index(name="Qtd")
            )
            fig_status = px.pie(
                d2, names="Status", values="Qtd", hole=0.55,
                color="Status",
                color_discrete_map={
                    "Aprovado": "#27A017",
                    "Pendente": "#ffa500",
                    "Recusado": "#c9251c",
                    "Não necessário": "#9ec9ff"
                }
            )
            fig_status.update_traces(
                texttemplate="<b>%{value} (%{percent:.1%})</b>",
                textposition="outside",
                marker=dict(line=dict(color="#ffffff", width=6))
            )
            fig_status.update_layout(
                height=260,
                margin=dict(t=10, b=50, l=0, r=0),
                legend=dict(orientation="h", y=-0.25, x=0.5, xanchor="center")
            )
            st.plotly_chart(fig_status, use_container_width=True)
        else:
            st.info("Sem dados de aprovação.")


    # ---- Tabelas Top 10 (Assessores que sofreram alterações | Usuários que realizaram alterações) ----
    st.markdown("---")
    c1, c2 = st.columns(2)

    with c1:
        st.markdown("**Top 10 assessores que mais sofreram alterações**")
        if not alt_period.empty and {"ASSESSOR","FILIAL"}.issubset(alt_period.columns):
            top_assessores = (
                alt_period.groupby(["ASSESSOR","FILIAL"])
                        .size()
                        .reset_index(name="Alterações")
                        .sort_values("Alterações", ascending=False)
                        .head(10)
            )
            top_assessores = top_assessores.rename(columns={
                "ASSESSOR": "Assessores",
                "FILIAL": "Filial"
            })
            st.dataframe(top_assessores, use_container_width=True, hide_index=True)
        else:
            st.info("Sem dados de assessores no período.")

    with c2:
        st.markdown("**Top 10 usuários que mais realizaram alterações**")
        if not alt_period.empty and {"USUARIO","FILIAL"}.issubset(alt_period.columns):
            top_usuarios = (
                alt_period.groupby(["USUARIO","FILIAL"])
                        .size()
                        .reset_index(name="Alterações")
                        .sort_values("Alterações", ascending=False)
                        .head(10)
            )
            top_usuarios = top_usuarios.rename(columns={
                "USUARIO": "Usuários",
                "FILIAL": "Filial"
            })
            st.dataframe(top_usuarios, use_container_width=True, hide_index=True)
        else:
            st.info("Sem dados de usuários no período.")

    # ---- Novas Tabelas (reduções e aumentos detalhadas) ----
    st.markdown("---")
    t1, t2 = st.columns(2)

    def _tabela_top10_por_tipo(tipo):
        base = alt_period.copy()
        if base.empty or not {"ASSESSOR","FILIAL","STATUS","TIPO"}.issubset(base.columns):
            return None
        base = base[base["TIPO"].eq(tipo)]

        piv = (
            base.assign(_one=1)
            .pivot_table(
                index=["ASSESSOR","FILIAL"],
                columns="STATUS",
                values="_one",
                aggfunc="sum",
                fill_value=0
            )
            .reset_index()
            .rename(columns={
                "ASSESSOR":"Assessores",
                "FILIAL":"Filial",
                "Pendente":"Pendentes",
                "Aprovado":"Aprovadas",
                "Recusado":"Recusadas",
                "Não necessário":"Não necessário"
            })
        )

        # garante colunas ausentes
        base_cols = ["Pendentes","Aprovadas","Recusadas","Não necessário"]
        for c in base_cols:
            if c not in piv.columns:
                piv[c] = 0

        if str(tipo).upper() == "REDUCAO":
            # Redução: não exibir “Não necessário” e não somar no total
            piv["Totais"] = piv[["Pendentes","Aprovadas","Recusadas"]].sum(axis=1)
            cols_show = ["Assessores","Filial","Pendentes","Aprovadas","Recusadas","Totais"]
        else:
            # Aumento: incluir “Não necessário” e somar no total
            piv["Totais"] = piv[["Pendentes","Aprovadas","Recusadas","Não necessário"]].sum(axis=1)
            cols_show = ["Assessores","Filial","Pendentes","Aprovadas","Recusadas","Não necessário","Totais"]

        piv = piv.sort_values("Totais", ascending=False).head(20)
        return piv[cols_show]


    with t1:
        st.markdown("**Top 10 assessores que mais sofreram solicitações de redução**")
        tb_red = _tabela_top10_por_tipo("REDUCAO")
        if tb_red is not None and not tb_red.empty:
            st.dataframe(tb_red, use_container_width=True, hide_index=True)
        else:
            st.info("Sem reduções no período.")

    with t2:
        st.markdown("**Top 10 assessores que mais sofreram solicitações de aumento**")
        tb_aup = _tabela_top10_por_tipo("AUMENTO")
        if tb_aup is not None and not tb_aup.empty:
            st.dataframe(tb_aup, use_container_width=True, hide_index=True)
        else:
            st.info("Sem aumentos no período.")
