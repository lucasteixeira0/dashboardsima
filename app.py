# -*- coding: utf-8 -*-
"""
Created on Mon Jul  7 12:02:12 2025

@author: Pichau
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


import hashlib

import streamlit as st


# Configuração da página – deve ser a primeira chamada
st.set_page_config(page_title="Dashboard Fornos UPC-Mata Verde", layout="wide")

# Inicializar session state
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False

if "username" not in st.session_state:
    st.session_state["username"] = ""

# Tela de login
if not st.session_state["logged_in"]:
    st.title("🔐 Login")
    username = st.text_input("Usuário")
    password = st.text_input("Senha", type="password")

    if st.button("Entrar"):
        if username == "Emerson" and password == "sima1234":  # Substitua com segurança depois
            st.session_state["logged_in"] = True
            st.session_state["username"] = username
            st.success("Login realizado com sucesso.")
            st.rerun()
        else:
            st.error("Usuário ou senha inválidos.")
    st.stop()  # Impede que o restante do dashboard carregue sem login

# Exibir mensagem no dashboard
st.success(f"✅ Bem-vindo, {st.session_state.username}!")


# Título do dashboard
st.title("Dashboard Operacional - UPC Mata Verde")

# Carregar os dados
df_prod_efetiva = pd.read_csv(r"data/producao_estimada_diaria.csv")
df_prod_em_processo = pd.read_csv(r"data/Qnt_emprodução_diaria.csv")
df_inatividade = pd.read_csv(r"data/taxa_inatividade_diaria.csv")
df_media_status = pd.read_csv(r"data/media_geral_por_status.csv")
df_alertas = pd.read_csv(r"data/fornos_alerta.csv")
df_perdas = pd.read_csv(r"data/perdas_por_vazios.csv")

# Converter datas
df_prod_efetiva["Data"] = pd.to_datetime(df_prod_efetiva["Data"])
df_prod_em_processo["Data"] = pd.to_datetime(df_prod_em_processo["Data"])
df_inatividade["Data"] = pd.to_datetime(df_inatividade["Data"])

# Filtro de data global
st.sidebar.header("📅 Filtro de Período")
data_inicio = df_prod_efetiva["Data"].min()
data_fim = df_prod_efetiva["Data"].max()
data_sel = st.sidebar.date_input("Selecione o intervalo:", [data_inicio, data_fim])

# Aplicar o filtro
if len(data_sel) == 2:
    ini, fim = pd.to_datetime(data_sel[0]), pd.to_datetime(data_sel[1])
    df_prod_efetiva = df_prod_efetiva[(df_prod_efetiva["Data"] >= ini) & (df_prod_efetiva["Data"] <= fim)]
    df_prod_em_processo = df_prod_em_processo[(df_prod_em_processo["Data"] >= ini) & (df_prod_em_processo["Data"] <= fim)]
    df_inatividade = df_inatividade[(df_inatividade["Data"] >= ini) & (df_inatividade["Data"] <= fim)]

st.markdown(f"📆 Período selecionado: **{ini.date()} a {fim.date()}**")

# ------------------------------------------
# 📊 RESUMO EXECUTIVO
# ------------------------------------------
st.header("Resumo Executivo")
col1, col2, col3, col4 = st.columns(4)

col1.metric("📦 Produção (últimos 7 dias, m³)", round(df_prod_efetiva.tail(7)["Estimativa_m3"].sum(),2))
col2.metric("✅ Disponibilidade Média (%)", round(100 - df_inatividade["Inatividade_%"].mean(),2))
col3.metric("🚨 Fornos em Alerta", len(df_alertas))
col4 = st.columns(1)[0]
col4.metric("💸 Perdas por ociosidade estimadas (m³)", round(df_perdas["Perda_m3"].sum(), 2))

# ------------------------------------------
# 📈 PRODUÇÃO (Efetiva e em Processo)
# ------------------------------------------
st.header("Produção")

tab1, tab2 , tab3 = st.tabs(["📈 Meta", "📅 Produção Efetiva", "⚙️ Produção em Processamento"])



with tab1:
    valor_atual = df_prod_em_processo.tail(1)["Estimativa_m3"].iloc[0]
    valor_desejado = 500  # meta

    # Define as faixas
    faixas = [
        {"range": [0, 400], "cor_solida": "rgba(255,0,0,1)", "cor_clara": "rgba(255,0,0,0.2)"},
        {"range": [400, 600], "cor_solida": "rgba(255,255,0,1)", "cor_clara": "rgba(255,255,0,0.2)"},
        {"range": [600, 680], "cor_solida": "rgba(0,255,0,1)", "cor_clara": "rgba(0,255,0,0.2)"}
    ]

    # Montar os steps com base no valor atual
    steps_config = []
    for faixa in faixas:
        cor = faixa["cor_solida"] if valor_atual >= faixa["range"][0] else faixa["cor_clara"]
        steps_config.append({"range": faixa["range"], "color": cor})

    # Criar o gráfico
    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=valor_atual,
        delta={"reference": valor_desejado, "increasing": {"color": "green"}, "decreasing": {"color": "red"}},
        gauge={
            "axis": {"range": [0, 680]},
            "bar": {"color": "rgba(0,102,204,0.8)"},  # azul com leve transparência
            "steps": steps_config,
            "threshold": {
                "line": {"color": "black", "width": 4},
                "thickness": 0.75,
                "value": valor_desejado
            }
        },
        title={"text": "Desempenho Operacional (m³)"}
    ))

    st.plotly_chart(fig, use_container_width=True)


with tab2:
    fig1 = px.bar(df_prod_efetiva, x="Data", y="Estimativa_m3",color_discrete_sequence=["#2ca02c"], title="Produção Diária Efetiva (m³)")
    st.plotly_chart(fig1, use_container_width=True)

with tab3:
    fig2 = px.line(df_prod_em_processo, x="Data", y="Estimativa_m3",color_discrete_sequence=["#2ca02c"], title="Carvão em Produção (m³)")
    st.plotly_chart(fig2, use_container_width=True)

# ------------------------------------------
# 🚦 DISPONIBILIDADE OPERACIONAL
# ------------------------------------------
st.header("Disponibilidade Operacional")

df_inatividade["Disponibilidade_%"] = 100 - df_inatividade["Inatividade_%"]
fig3 = px.line(df_inatividade, x="Data", y="Disponibilidade_%",color_discrete_sequence=["#2ca02c"], title="Disponibilidade Diária (%)", markers=True)
st.plotly_chart(fig3, use_container_width=True)

# ------------------------------------------
# 📉 TAXA DE INATIVIDADE
# ------------------------------------------

st.header("Taxa de Inatividade")

fig4 = px.line(df_inatividade, x="Data", y="Inatividade_%",color_discrete_sequence=["#2ca02c"], title="Taxa de Inatividade Diária (%)")
st.plotly_chart(fig4, use_container_width=True)

# ------------------------------------------
# 🔮 PREVISÕES DE PRODUÇÃO (PROJEÇÕES)
# ------------------------------------------
st.header("Projeções de Produção")

tab3, tab4 = st.tabs(["📆 Próximos 30 dias", "🎯 Meta de Volume"])

with tab3:
    df_proj_30 = pd.read_csv(r"data/simulacao_30dias.csv")
    fig5 = px.bar(df_proj_30, x="Previsao_Descarregado", y="Estimativa_m3",
                  title="Projeção próximos 30 dias", text_auto='.2f')
    st.plotly_chart(fig5, use_container_width=True)

with tab4:
    df_proj_vol = pd.read_csv(r"data/simulacao_meta_volume.csv")
    fig6 = px.bar(df_proj_vol, x="Previsao_Descarregado", y="Estimativa_m3",
                  title="Projeção até atingir Meta", text_auto='.2f')
    st.plotly_chart(fig6, use_container_width=True)

# ------------------------------------------
# 📅 HISTÓRICO INDIVIDUAL POR FORNO
# ------------------------------------------
st.header("Histórico Individual por Forno")

fornos = [str(f).zfill(2) for f in range(1, 61)]

forno_sel = st.selectbox("Escolha um forno para exibir histórico:", fornos)

try:
    df_forno = pd.read_csv(fr"data/forno_{forno_sel}.csv")
    df_forno["Data"] = pd.to_datetime(df_forno["Data"])
    st.dataframe(df_forno)
except FileNotFoundError:
    st.error("Dados não encontrados para o forno selecionado!")
    

# ------------------------------------------
# 📥 Perdas
# ------------------------------------------    
    
st.header("Estimativa de Perdas por Ociosidade")

df_perdas["Data_Inicio"] = pd.to_datetime(df_perdas["Data_Inicio"])

# Filtro de período
df_perdas_filtrado = df_perdas[(df_perdas["Data_Inicio"] >= ini) & (df_perdas["Data_Inicio"] <= fim)]
perdas_agrupadas = df_perdas_filtrado.groupby("Mes")[["Dias_no_Status", "Perda_m3"]].sum().reset_index()

fig_perdas = px.bar(perdas_agrupadas, x="Mes", y="Perda_m3", text_auto='.2f',
                    title="Perdas Estimadas por Mês (m³)",
                    labels={"Perda_m3": "Perda (m³)", "Mes": "Mês"},
                    color_discrete_sequence=["red"])

st.plotly_chart(fig_perdas, use_container_width=True)
    

# ------------------------------------------
# 📥 DOWNLOAD RELATÓRIO PDF
# ------------------------------------------
st.header("📥 Baixar Relatório Semanal")
with open(r"data/relatorio_Mata_Verde_operacional_semana.pdf", "rb") as file:
    btn = st.download_button(
        label="📥 Baixar PDF",
        data=file,
        file_name="Relatorio_Semanal_Fornos.pdf",
        mime="application/pdf"
    )
    
    


# ------------------------------------------
# 📝 FOOTER
# ------------------------------------------
st.markdown("---")
st.caption("Desenvolvido por Lucas Neves Teixeira")