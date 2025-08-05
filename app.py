# -*- coding: utf-8 -*-
"""
Created on Mon Jul  7 12:02:12 2025

@author: Pichau
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
import hashlib
import streamlit as st
import time 

def carregar_csv_seguro(caminho, colunas_minimas=None):
    if os.path.exists(caminho):
        return pd.read_csv(caminho)
    else:
        if colunas_minimas:
            return pd.DataFrame(columns=colunas_minimas)
        return pd.DataFrame()
def formatar_nome_fazenda(nome):
    return nome.lower().replace(" ", "").replace(".", "")
def exibir_painel_historico(df_historico, unidade_sel, formatar_nome_fazenda):
    st.subheader("📅 Dados históricos")
    
    df_historico["Data"] = pd.to_datetime(df_historico["Data"], errors='coerce')
    df_historico["FazendaNomeSanitizada"] = df_historico["FazendaNome"].apply(formatar_nome_fazenda)
    unidade_sanitizada = formatar_nome_fazenda(unidade_sel)

    df_faz = df_historico[df_historico["FazendaNomeSanitizada"] == unidade_sanitizada].copy()

    if df_faz.empty:
        st.warning("❗ Nenhum dado histórico disponível para esta fazenda.")
        return

    df_faz["Ano"] = df_faz["Data"].dt.year
    df_faz["Mes"] = df_faz["Data"].dt.month
    df_faz["Dia"] = df_faz["Data"].dt.date

    LIM_DMIN, LIM_DMAX = 220, 260  # kg/m³
    LIM_UMID_MAX = 12              # %

    dentro_dens = df_faz["DensidadeSeca"].between(LIM_DMIN, LIM_DMAX).mean() * 100
    dentro_umid = (df_faz["Umidade"] <= LIM_UMID_MAX).mean() * 100

    dens_dia = df_faz.groupby("Dia")["DensidadeSeca"].mean()
    z = (dens_dia - dens_dia.mean()) / dens_dia.std(ddof=0)
    num_outliers = (z.abs() > 3).sum()

    umd_dia = df_faz.groupby("Dia")["Umidade"].mean()
    z_umd = (umd_dia - umd_dia.mean()) / umd_dia.std(ddof=0)
    num_outliers_umd = (z_umd.abs() > 3).sum()

    # Filtros
    data_min, data_max = df_faz["Data"].min(), df_faz["Data"].max()
    periodo = st.date_input("Selecione o intervalo:", [data_min, data_max])
    if len(periodo) == 2:
        ini, fim = pd.to_datetime(periodo[0]), pd.to_datetime(periodo[1])
        df_faz = df_faz[(df_faz["Data"] >= ini) & (df_faz["Data"] <= fim)]

    wavg_dens = (df_faz["DensidadeSeca"] * df_faz["Metragem"]).sum() / df_faz["Metragem"].sum() if df_faz["Metragem"].sum() else None
    wavg_umid = (df_faz["Umidade"] * df_faz["Metragem"]).sum() / df_faz["Metragem"].sum() if df_faz["Metragem"].sum() else None

    # Produção diária
    st.subheader("📈 Produção Diária")
    prod_dia = df_faz.groupby("Dia")["Metragem"].sum().reset_index()
    st.plotly_chart(px.bar(prod_dia, x="Dia", y="Metragem", title="Produção Diária (m³)"), use_container_width=True)

    # Produção mensal
    st.subheader("📆 Produção Mensal")
    prod_mes = df_faz.groupby(["Ano", "Mes"])["Metragem"].sum().reset_index()
    prod_mes["AnoMes"] = prod_mes["Ano"].astype(str) + "-" + prod_mes["Mes"].astype(str).str.zfill(2)
    st.plotly_chart(px.bar(prod_mes, x="AnoMes", y="Metragem", title="Produção Mensal (m³)", text_auto='.2f'), use_container_width=True)

    # Produção anual
    st.subheader("📅 Produção Anual")
    prod_ano = df_faz.groupby("Ano")["Metragem"].sum().reset_index()
    st.plotly_chart(px.bar(prod_ano, x="Ano", y="Metragem", title="Produção Anual (m³)", text_auto='.2f'), use_container_width=True)

    # Densidade
    st.subheader("📈 Densidade")
    prod_dia_dens = df_faz.groupby("Dia")["DensidadeSeca"].mean().reset_index()
    st.plotly_chart(px.line(prod_dia_dens, x="Dia", y="DensidadeSeca", title="Densidade média (kg/m³)"), use_container_width=True)

    colE, colF1 = st.columns(2)
    colE.metric("Densidade média pond. (kg/m³)", f"{wavg_dens:,.1f}" if wavg_dens else "N/D")
    colF1.metric("% dentro da densidade ideal (220–260 kg/m³)", f"{dentro_dens:.1f}%" if not pd.isna(dentro_dens) else "N/D")
    st.info(f"🔍 Dias com densidade anômala detectados: **{num_outliers}**")

    # Umidade
    st.subheader("📈 Umidade")
    prod_dia_umid = df_faz.groupby("Dia")["Umidade"].mean().reset_index()
    st.plotly_chart(px.line(prod_dia_umid, x="Dia", y="Umidade", title="Umidade média (%)"), use_container_width=True)

    colF, colG = st.columns(2)
    colF.metric("Umidade média pond. (%)", f"{wavg_umid:,.1f}" if wavg_umid else "N/D")
    colG.metric("% com umidade ≤ 12%", f"{dentro_umid:.1f}%" if not pd.isna(dentro_umid) else "N/D")
    st.info(f"🔍 Dias com umidade anômala detectados: **{num_outliers_umd}**")


base_2="data/auditoria"

fazendas_ativas = {
    "Mata Verde": True,
    "Gloria": True,
    "Proteção": True,
    "Santa Ana": False,
    "Mapal": False,
    "Alto da Serra": False,
    "CAB. COMP": False
}    

usuarios = st.secrets["usuarios"]
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
        if username in usuarios and password == usuarios[username]:  # Substitua com segurança depois
            st.session_state["logged_in"] = True
            st.session_state["username"] = username
            st.success("Login realizado com sucesso.")
            st.rerun()
        else:
            st.error("Usuário ou senha inválidos.")
    st.stop()  # Impede que o restante do dashboard carregue sem login

# Exibir mensagem no dashboard
mensagem = st.empty()
mensagem.success(f"✅ Bem-vindo, {st.session_state.username}!")

time.sleep(2)
mensagem.empty()

# -----------------------------------------------------------
# 🔀 NAVEGAÇÃO PELAS PÁGINAS DO DASHBOARD
# -----------------------------------------------------------
PAGES = {
    "Painel de Gestão":      "gestao",
    "Visão 360°":            "visao360",
    "Indicadores Operacionais":"indicadores",
    "Simulador":             "simulador",
    "Auditoria Cubagem":     "auditoria"      # << NOVA PÁGINA
}

# valor inicial
if "page" not in st.session_state:
    st.session_state["page"] = "gestao"

# renderiza os botões
for nome, chave in PAGES.items():
    if st.sidebar.button(nome):
        st.session_state["page"] = chave





            
# ===================== PÁGINA PRINCIPAL (Gestão) =====================
if st.session_state["page"] == "gestao":
    st.sidebar.header("🏭 Selecione a Unidade")
    todas_fazendas = list(fazendas_ativas.keys())
    unidade_sel = st.sidebar.selectbox("Unidade:", todas_fazendas)
    caminho_base = f"data/{unidade_sel.lower().replace(' ', '').replace('.', '')}"
    ativa = fazendas_ativas[unidade_sel]
    caminho_absoluto_base = f"{caminho_base}"

 
    if ativa:
        st.title(f"Dashboard Operacional - UPC {unidade_sel}")

        df_prod_efetiva = carregar_csv_seguro(
            f"{caminho_absoluto_base}/producao_estimada_diaria.csv",
            colunas_minimas=["Data", "Estimativa_m3"]
        )

        df_prod_em_processo = carregar_csv_seguro(
            f"{caminho_absoluto_base}/Qnt_emprodução_diaria.csv",
            colunas_minimas=["Data", "Estimativa_m3"]
        )

        df_inatividade = carregar_csv_seguro(
            f"{caminho_absoluto_base}/taxa_inatividade_diaria.csv",
            colunas_minimas=["Data", "Inatividade_%"]
        )

        df_media_status = carregar_csv_seguro(
            f"{caminho_absoluto_base}/media_geral_por_status.csv"
        )

        df_alertas = carregar_csv_seguro(
            f"{caminho_absoluto_base}/fornos_alerta.csv"
        )

        df_perdas = carregar_csv_seguro(
            f"{caminho_absoluto_base}/perdas_por_vazios.csv",
            colunas_minimas=["Mes", "Dias_no_Status", "Perda_m3", "Data_Inicio"]
        )

        df_transporte = carregar_csv_seguro(
            f"{caminho_absoluto_base}/df_transporte.csv",
            colunas_minimas=["Data Transporte", "Fazenda Origem","Volume medido (m³st)","Transportadora", "Placa Caminhão", "Tipo Entrega", "Observações" ]
        )

        df_carregamentos = carregar_csv_seguro(
            f"{caminho_absoluto_base}/carregamentos.csv"
        )

        df_descarregamentos = carregar_csv_seguro(
            f"{caminho_absoluto_base}/descarregamentos.csv"
        )
        # Converter datas
        df_prod_efetiva["Data"] = pd.to_datetime(df_prod_efetiva["Data"])
        df_prod_em_processo["Data"] = pd.to_datetime(df_prod_em_processo["Data"])
        df_inatividade["Data"] = pd.to_datetime(df_inatividade["Data"])


        # Filtro de data global
        st.sidebar.header("📅 Filtro de Período")
        data_inicio = df_prod_em_processo["Data"].min().date()
        data_fim = df_prod_em_processo["Data"].max().date()
        if not df_prod_em_processo.empty: 
            data_sel = st.sidebar.date_input("Selecione o intervalo:", [data_inicio, data_fim])
        else:     
            data_sel=[1,2]

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

        col1.metric("📦 Produção no Período Selecionado (m³)", round(df_prod_efetiva["Estimativa_m3"].sum(), 2))
        if not df_inatividade.empty and "Inatividade_%" in df_inatividade.columns:
            disponibilidade_media = round(100 - df_inatividade["Inatividade_%"].mean(), 2)
            col2.metric("✅ Disponibilidade Média (%)", disponibilidade_media)
        else:
            col2.metric("✅ Disponibilidade Média (%)", "N/D")
        col3.metric("🚨 Fornos em Alerta", len(df_alertas))
        col4 = st.columns(1)[0]
        col4.metric("💸 Perdas por ociosidade estimadas (m³)", round(df_perdas["Perda_m3"].sum(), 2))
        # ------------------------------------------
        # 📈 PRODUÇÃO (Efetiva e em Processo)
        # ------------------------------------------
        tab1, tab2 , tab3, tab4 = st.tabs(["📈 Meta", "📅 Produção Efetiva", "⚙️ Produção em Processamento","🚛 Transporte"])

        # Metas por unidade
        metas_unidade = {
            "Mata Verde": 500,
            "Glória": 1000,
            "Proteção": 900
        }

        # Faixas de cor por unidade
        faixas_por_unidade = {
            "Mata Verde": [
                {"range": [0, 400], "cor_solida": "rgba(255,0,0,1)", "cor_clara": "rgba(255,0,0,0.2)"},
                {"range": [400, 600], "cor_solida": "rgba(255,255,0,1)", "cor_clara": "rgba(255,255,0,0.2)"},
                {"range": [600, 680], "cor_solida": "rgba(0,255,0,1)", "cor_clara": "rgba(0,255,0,0.2)"}
            ],
            "Proteção": [
                {"range": [0, 600], "cor_solida": "rgba(255,0,0,1)", "cor_clara": "rgba(255,0,0,0.2)"},
                {"range": [600, 850], "cor_solida": "rgba(255,255,0,1)", "cor_clara": "rgba(255,255,0,0.2)"},
                {"range": [850, 1000], "cor_solida": "rgba(0,255,0,1)", "cor_clara": "rgba(0,255,0,0.2)"}
            ],
            "Glória": [
                {"range": [0, 700], "cor_solida": "rgba(255,0,0,1)", "cor_clara": "rgba(255,0,0,0.2)"},
                {"range": [700, 950], "cor_solida": "rgba(255,255,0,1)", "cor_clara": "rgba(255,255,0,0.2)"},
                {"range": [950, 1100], "cor_solida": "rgba(0,255,0,1)", "cor_clara": "rgba(0,255,0,0.2)"}
            ]
        }

        with tab1:
            # Pega o valor da meta e faixas da unidade
            valor_desejado = metas_unidade.get(unidade_sel, 500)
            faixas = faixas_por_unidade.get(unidade_sel, [])

            # Garante valor mesmo com df vazio
            if not df_prod_em_processo.empty and "Estimativa_m3" in df_prod_em_processo.columns:
                valor_atual = df_prod_em_processo.tail(1)["Estimativa_m3"].iloc[0]
            else:
                valor_atual = 0

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
                    "axis": {"range": [0, faixas[-1]["range"][1] if faixas else 1000]},
                    "bar": {"color": "rgba(0,102,204,0.8)"},
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
            fig1 = px.bar(df_prod_efetiva, x="Data", y="Estimativa_m3",color_discrete_sequence=["#2ca02c"], title="Produção Diária Efetiva (m³)", text_auto='.2f')
            st.plotly_chart(fig1, use_container_width=True)

        with tab3:
            fig2 = px.line(df_prod_em_processo, x="Data", y="Estimativa_m3",color_discrete_sequence=["#2ca02c"], title="Carvão em Produção (m³)")
            st.plotly_chart(fig2, use_container_width=True)

        with tab4:
            st.subheader("🚛 Dados de Transporte")
            try:
                colunas=["Data Transporte", "Fazenda Origem","Volume medido (m³st)","Transportadora", "Placa Caminhão", "Tipo Entrega", "Observações", ]
                df_transporte = df_transporte[[col for col in colunas if col in df_transporte.columns]]
                st.dataframe(df_transporte)
            except Exception as e:
                st.error(f"Erro ao carregar dados de transporte: {e}")

        # ------------------------------------------
        # 🚦 DISPONIBILIDADE OPERACIONAL
        # ------------------------------------------
        st.header(" Saúde Operacional")
        
        tabinat,tabdisp,tabcarregamento,tabdescarregamento= st.tabs(["Taxa de Inatividade","Disponibilidade Operacional","Carregamentos Diários", "Descarregamentos Diários"])
        with tabinat: 
            if df_inatividade.empty or "Inatividade_%" not in df_inatividade.columns:
                df_inatividade = pd.DataFrame({
                    "Data": pd.date_range(start=ini, end=fim, freq="D"),
                    "Inatividade_%": 0
                })
            
            # Calcular disponibilidade
            df_inatividade["Disponibilidade_%"] = 100 - df_inatividade["Inatividade_%"]
            fig3 = px.line(df_inatividade, x="Data", y="Disponibilidade_%",color_discrete_sequence=["#2ca02c"], title="Disponibilidade Diária (%)", markers=True)
            st.plotly_chart(fig3, use_container_width=True)
        
        with tabdisp:
            fig4 = px.line(df_inatividade, x="Data", y="Inatividade_%",color_discrete_sequence=["#2ca02c"], title="Taxa de Inatividade Diária (%)")
            st.plotly_chart(fig4, use_container_width=True)
        with tabcarregamento:
            if "df_carregamentos" in locals() and not df_carregamentos.empty:
                media_carregamento = df_carregamentos["Qtde_Carregada"].mean()
                max_carregamentos = df_carregamentos["Qtde_Carregada"].max()
                
                fig5 = px.line(df_carregamentos, x="Data", y="Qtde_Carregada",
                            color_discrete_sequence=["#2ca02c"],
                            title="Fornos Carregados (Qtde)")
                fig5.add_hline(y=media_carregamento, line_dash="dash", line_color="gray",
                            annotation_text=f"Média: {media_carregamento:.1f}", annotation_position="top left")
                st.plotly_chart(fig5, use_container_width=True)
                colca,colcamax =st.columns(2)
                colca.metric("Quantidade média de carregamentos diários ", f"{media_carregamento:.2f}" if media_carregamento else "N/D")
                colcamax.metric("Máximo de  fornos carregados em um dia  ", f"{max_carregamentos}" if max_carregamentos else "N/D")
            else:
                st.info("Nenhum dado de carregamento disponível para exibir.")
            

        with tabdescarregamento:
            if "df_descarregamentos" in locals() and not df_descarregamentos.empty:
                media_descarregamento = df_descarregamentos["Qtde_Descarregada"].mean()
                max_descarregamentos = df_descarregamentos["Qtde_Descarregada"].max()
                fig6 = px.line(df_descarregamentos, x="Data", y="Qtde_Descarregada",
                            color_discrete_sequence=["#2ca02c"],
                            title="Fornos Descarregados (Qtde)")
                fig6.add_hline(y=media_descarregamento, line_dash="dash", line_color="gray",
                            annotation_text=f"Média: {media_descarregamento:.1f}", annotation_position="top left")
                st.plotly_chart(fig6, use_container_width=True)
                coldca,coldcamax =st.columns(2)
                coldca.metric("Quantidade média de descarregamentos diários ", f"{media_descarregamento:.2f}" if media_descarregamento else "N/D")
                coldcamax.metric("Máximo de  fornos descarregados em um dia  ", f"{max_descarregamentos}" if max_descarregamentos else "N/D")
            else:
                st.info("Nenhum dado de descarregamento disponível para exibir.")
        # ------------------------------------------
        # 🔮 PREVISÕES DE PRODUÇÃO (PROJEÇÕES)
        # ------------------------------------------
        st.header("Detalhes Avançados")
        tab_hist, tab_proj = st.tabs(["📜 Análise Histórica", "🔮 Projeções"])
        
        with tab_hist:
                
            df_historico = carregar_csv_seguro(
            f"{caminho_absoluto_base}/fazendas.csv", 
            colunas_minimas=["FazendaNome", "Data", "Metragem"]
            )
            exibir_painel_historico(df_historico, unidade_sel, formatar_nome_fazenda)
            
        with tab_proj:    
            st.header("Projeções de Produção")
            
            tab3, tab4 = st.tabs(["Próximos 30 dias", "Meta de Volume"])
            
            # Caminhos dos arquivos
            caminho_proj_30 = f"{caminho_absoluto_base}/simulacao_30dias.csv"
            caminho_proj_meta = f"{caminho_absoluto_base}/simulacao_meta_volume.csv"
            
            with tab3:
                if os.path.exists(caminho_proj_30):
                    df_proj_30 = pd.read_csv(caminho_proj_30)
                    fig5 = px.bar(
                        df_proj_30,
                        x="Previsao_Descarregado",
                        y="Estimativa_m3",
                        title="Projeção próximos 30 dias",
                        text_auto='.2f'
                    )
                    st.plotly_chart(fig5, use_container_width=True)
                else:
                    st.warning("⛔ Dados de projeção para os próximos 30 dias não disponíveis para esta unidade.")
            
            with tab4:
                if os.path.exists(caminho_proj_meta):
                    df_proj_vol = pd.read_csv(caminho_proj_meta)

                    # Calcular intervalo de datas
                    data_min = pd.to_datetime(df_proj_vol["Previsao_Descarregado"].min())
                    data_max = pd.to_datetime(df_proj_vol["Previsao_Descarregado"].max())
                    dias_corridos = (data_max - data_min).days + 1

                    # Somar volume total projetado
                    volume_total = df_proj_vol["Estimativa_m3"].sum()

                

                    # Exibir gráfico
                    fig6 = px.bar(
                        df_proj_vol,
                        x="Previsao_Descarregado",
                        y="Estimativa_m3",
                        title="Projeção até zerar estoque",
                        text_auto='.2f'
                    )
                    st.plotly_chart(fig6, use_container_width=True)
                    
                    col1, col2 = st.columns(2)
                    col1.metric("⏳ Intervalo de dias", f"{dias_corridos} dias")
                    col2.metric("📦 Volume Total", f"{volume_total:.2f} m³")
                else:
                    st.warning("⛔ Projeção de volume até atingir a meta não disponível para esta unidade.")

        # ------------------------------------------
        # 📅 HISTÓRICO INDIVIDUAL POR FORNO
        # ------------------------------------------
        st.header("Histórico Individual por Forno")

        fornos = [str(f).zfill(2) for f in range(1, 61)]

        forno_sel = st.selectbox("Escolha um forno para exibir histórico:", fornos)

        caminho_forno = f"{caminho_absoluto_base}/forno_{forno_sel}.csv"

        if os.path.exists(caminho_forno):
            df_forno = pd.read_csv(caminho_forno)
            if not df_forno.empty and "Data" in df_forno.columns:
                df_forno["Data"] = pd.to_datetime(df_forno["Data"])
            st.dataframe(df_forno)
        else:
            st.warning("⛔ Dados não encontrados para o forno selecionado nesta unidade.")



        # ------------------------------------------
        # 📥 Atrasos de Produção
        # ------------------------------------------    
            
        st.header("Estimativa de Perdas por Ociosidade")

        if not df_perdas.empty and {"Data_Inicio", "Mes", "Perda_m3"}.issubset(df_perdas.columns):
            df_perdas["Data_Inicio"] = pd.to_datetime(df_perdas["Data_Inicio"])
            
            # Filtro de período
            df_perdas_filtrado = df_perdas[(df_perdas["Data_Inicio"] >= ini) & (df_perdas["Data_Inicio"] <= fim)]
            
            if not df_perdas_filtrado.empty:
                perdas_agrupadas = df_perdas_filtrado.groupby("Mes")[["Dias_no_Status", "Perda_m3"]].sum().reset_index()

                fig_perdas = px.bar(
                    perdas_agrupadas,
                    x="Mes",
                    y="Perda_m3",
                    text_auto='.2f',
                    title="Perdas Estimadas por Mês (m³)",
                    labels={"Perda_m3": "Perda (m³)", "Mes": "Mês"},
                    color_discrete_sequence=["red"]
                )

                st.plotly_chart(fig_perdas, use_container_width=True)
            else:
                st.info("Não há perdas registradas no período selecionado.")
        else:
            st.warning("⛔ Dados de perdas por ociosidade não estão disponíveis ou incompletos para esta unidade.")
        
        # ------------------------------------------
        # 📥 DOWNLOAD RELATÓRIO PDF
        # ------------------------------------------
        st.header("📥 Baixar Relatório Semanal")
        caminho_pdf = f"{caminho_absoluto_base}/Relatorio_Semanal_{unidade_sel.replace(' ', '_')}.pdf"
        try:
            with open(caminho_pdf, "rb") as file:
                st.download_button(
                    label="📥 Baixar PDF",
                    data=file,
                    file_name=f"Relatorio_Semanal_{unidade_sel}.pdf",
                    mime="application/pdf"
                )
        except FileNotFoundError:
            st.warning("Relatório ainda não disponível para esta unidade.")
            
    else:
        st.title(f"📊 Histórico de Produção - Fazenda {unidade_sel} (Inativa)")
        
        # Carregar histórico geral
        df_historico = carregar_csv_seguro(
        f"{caminho_absoluto_base}/fazendas.csv", 
        colunas_minimas=["FazendaNome", "Data", "Metragem"]
    )
        exibir_painel_historico(df_historico, unidade_sel, formatar_nome_fazenda)

# ===================== VISÃO 360° ====================================
elif st.session_state["page"] == "visao360":
    st.title("Visão 360°")
    #  código da Visão 360°

# ===================== INDICADORES OPERACIONAIS ======================
elif st.session_state["page"] == "indicadores":
    st.title("Indicadores Operacionais")
    #  código correspondente

# ===================== SIMULADOR =====================================
elif st.session_state["page"] == "simulador":
    st.title("Simulador")
    #  código do simulador

# ===================== AUDITORIA CUBAGEM ==============================
elif st.session_state["page"] == "auditoria":
    st.title("📋 Painel de Auditoria – Cubagem")

    # caminhos dos dois CSVs gerados pelo script de auditoria
    caminho_alertas_motorista  = os.path.join(base_2, "alertas_motorista.csv")
    caminho_ranking_motoristas = os.path.join(base_2, "ranking_motoristas.csv")

    df_alertas_mot = carregar_csv_seguro(caminho_alertas_motorista)
    df_ranking_mot = carregar_csv_seguro(caminho_ranking_motoristas)

    tab_rank, tab_alertas = st.tabs(["🏆 Ranking de Motoristas", "🚨 Cargas Suspeitas"])

    with tab_rank:
        if df_ranking_mot.empty:
            st.info("Nenhum dado de ranking disponível.")
        else:
            st.dataframe(df_ranking_mot)
            fig_rank = px.bar(df_ranking_mot.reset_index(),
                              x="MotoristaVeiculo", y="Percentual",
                              text_auto='.1f',
                              title="Percentual de Alertas por Motorista",
                              color_discrete_sequence=["#d62728"])
            st.plotly_chart(fig_rank, use_container_width=True)

    with tab_alertas:
        if "MOTIVO_MOT" in df_alertas_mot.columns and not df_alertas_mot.empty:
                motivos = (
                    df_alertas_mot["MOTIVO_MOT"]              # série de textos
                    .value_counts()                         # série: motivo → contagem
                    .reset_index(name="Qtd")               # -> DataFrame: index=Motivo, Qtd=contagem
                    .rename(columns={"index": "Motivo"})    # renomeia a coluna gerada pelo index
                )
        else:
                motivos = pd.DataFrame(columns=["Motivo", "Qtd"])

        # ------------------------------------------------------------------
        # 🚨 Gráfico só se houver dados
        # ------------------------------------------------------------------
        if motivos.empty:
            st.info("Nenhum motivo de alerta encontrado.")
        else:
            fig_mot = px.bar(
                motivos,
                x="MOTIVO_MOT",
                y="Qtd",
                title="Frequência dos Motivos de Alerta",
                text_auto=True,
                color_discrete_sequence=["#ff7f0e"]
            )
            st.plotly_chart(fig_mot, use_container_width=True)
# ------------------------------------------
# 📝 FOOTER
# ------------------------------------------
st.markdown("---")
st.caption("Desenvolvido por Lucas Neves Teixeira")
