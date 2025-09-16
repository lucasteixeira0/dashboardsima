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
import json
import time, textwrap, io, requests

def carregar_csv_seguro(caminho, colunas_minimas=None):
    if os.path.exists(caminho):
        df = pd.read_csv(caminho)
        # Padronização de nomes de colunas problemáticas
        renomear_colunas = {
            "Taxa Inatividade (%)": "Inatividade_%",
            "Inatividade (%) ": "Inatividade_%",  # com espaço
            " Inatividade (%)": "Inatividade_%"   # com espaço antes
        }

        df.rename(columns=renomear_colunas, inplace=True)

        return df
    else:
        if colunas_minimas:
            return pd.DataFrame(columns=colunas_minimas)
        return pd.DataFrame()
def carregar_json_seguro(caminho, valor_padrao=None):
    """
    Carrega um arquivo JSON de forma segura.
    
    Parâmetros:
    - caminho (str): caminho completo do arquivo JSON.
    - valor_padrao (dict, opcional): valor de retorno caso o arquivo não exista ou esteja corrompido.
    
    Retorna:
    - dict: conteúdo do JSON ou valor_padrao.
    """
    if not os.path.exists(caminho):
        return valor_padrao if valor_padrao is not None else {}

    try:
        with open(caminho, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"[Erro ao carregar JSON] {e}")
        return valor_padrao if valor_padrao is not None else {}
def formatar_nome_fazenda(nome):
    return nome.lower().replace(" ", "").replace(".", "")
def exibir_painel_historico(df_historico, unidade_sel, formatar_nome_fazenda):
    st.subheader("Dados históricos")
    
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
    st.subheader("Produção Diária")
    prod_dia = df_faz.groupby("Dia")["Metragem"].sum().reset_index()
    st.plotly_chart(px.bar(prod_dia, x="Dia", y="Metragem", title="Produção Diária (m³)"), use_container_width=True)

    # Produção mensal
    st.subheader("Produção Mensal")
    prod_mes = df_faz.groupby(["Ano", "Mes"])["Metragem"].sum().reset_index()
    prod_mes["AnoMes"] = prod_mes["Ano"].astype(str) + "-" + prod_mes["Mes"].astype(str).str.zfill(2)
    st.plotly_chart(px.bar(prod_mes, x="AnoMes", y="Metragem", title="Produção Mensal (m³)", text_auto='.2f'), use_container_width=True)

    # Produção anual
    st.subheader("Produção Anual")
    prod_ano = df_faz.groupby("Ano")["Metragem"].sum().reset_index()
    st.plotly_chart(px.bar(prod_ano, x="Ano", y="Metragem", title="Produção Anual (m³)", text_auto='.2f'), use_container_width=True)

    # Densidade
    st.subheader("Densidade")
    prod_dia_dens = df_faz.groupby("Dia")["DensidadeSeca"].mean().reset_index()
    st.plotly_chart(px.line(prod_dia_dens, x="Dia", y="DensidadeSeca", title="Densidade média (kg/m³)"), use_container_width=True)

    colE, colF1 = st.columns(2)
    colE.metric("Densidade média pond. (kg/m³)", f"{wavg_dens:,.1f}" if wavg_dens else "N/D")
    colF1.metric("% dentro da densidade ideal (220–260 kg/m³)", f"{dentro_dens:.1f}%" if not pd.isna(dentro_dens) else "N/D")
    st.info(f"🔍 Dias com densidade anômala detectados: **{num_outliers}**")

    # Umidade
    st.subheader("Umidade")
    prod_dia_umid = df_faz.groupby("Dia")["Umidade"].mean().reset_index()
    st.plotly_chart(px.line(prod_dia_umid, x="Dia", y="Umidade", title="Umidade média (%)"), use_container_width=True)

    colF, colG = st.columns(2)
    colF.metric("Umidade média pond. (%)", f"{wavg_umid:,.1f}" if wavg_umid else "N/D")
    colG.metric("% com umidade ≤ 12%", f"{dentro_umid:.1f}%" if not pd.isna(dentro_umid) else "N/D")
    st.info(f"🔍 Dias com umidade anômala detectados: **{num_outliers_umd}**")
def faixa_disponibilidade(valor):
    if valor >= 90:
        return "Alta (≥90%)"
    elif valor >= 70:
        return "Média (70–90%)"
    else:
        return "Baixa (<70%)"
def faixa_inatividade(valor):
    if valor <= 10:
        return "Baixa (≤10%)"
    elif valor <= 30:
        return "Média (10–30%)"
    else:
        return "Alta (>30%)"

@st.cache_data(show_spinner=False)
def ler_planilha_publicada(url: str, expect_cols=None, timeout=15, bust_seconds=300) -> pd.DataFrame:
    """Lê CSV de planilha publicada (Google Sheets/AppSheet) com validações básicas."""
    if not isinstance(url, str) or not url.startswith(("http://", "https://")):
        st.error("URL inválida.")
        return pd.DataFrame(columns=expect_cols) if expect_cols else pd.DataFrame()

    # força output=csv e cache-buster
    sep = "&" if "?" in url else "?"
    base = url
    if "output=csv" not in url:
        base = f"{url}{sep}output=csv"
        sep = "&"
    url_final = f"{base}{sep}cachebust={int(time.time())//bust_seconds}"

    try:
        r = requests.get(url_final, timeout=timeout, headers={"User-Agent":"Mozilla/5.0"})
    except Exception as e:
        st.error(f"Falha de rede: {e}")
        return pd.DataFrame(columns=expect_cols) if expect_cols else pd.DataFrame()

    if r.status_code != 200:
        st.error(f"HTTP {r.status_code} no link publicado.")
        st.code((r.text or "")[:800])
        return pd.DataFrame(columns=expect_cols) if expect_cols else pd.DataFrame()

    txt = r.text or ""
    if txt.lstrip().startswith("<"):
        st.error("O link retornou HTML, não CSV. Publique a aba como CSV e use o gid correto.")
        st.code(textwrap.shorten(txt, width=800, placeholder=" [...] "))
        return pd.DataFrame(columns=expect_cols) if expect_cols else pd.DataFrame()

    # tenta separadores
    buf = io.StringIO(txt)
    for sep_try in [",", ";", "\t"]:
        buf.seek(0)
        try:
            df = pd.read_csv(buf, sep=sep_try, encoding="utf-8-sig")
            if df.shape[1] > 1 or sep_try == ",":
                df = df.dropna(how="all")
                return df if not expect_cols else df.reindex(columns=list(dict.fromkeys(expect_cols + list(df.columns))))
        except Exception:
            continue

    # fallback
    st.warning("CSV sem separador claro. Exibindo amostra bruta para diagnóstico.")
    st.code(txt[:800])
    return pd.DataFrame(columns=expect_cols) if expect_cols else pd.DataFrame()

base_2="data/auditoria"

fazendas_ativas = {
    "Mata Verde": True,
    "Gloria": True,
    "Proteção": True,
    "Santa Ana": False,
    "Mapal": False,
    "Alto da Serra": True,
    "CAB. COMP": False
}    

# -----------------------------------------------------------
# 🔀 NAVEGAÇÃO PELAS PÁGINAS DO DASHBOARD
# -----------------------------------------------------------
PAGES = {
    "Painel de Gestão":      "gestao",
    "Visão 360°":            "visao360",
    #"Indicadores Operacionais":"indicadores",
    "Simulador":             "simulador",
    "Monitoramento Cargas":     "auditoria",
    "Silvicultura" : "silvicultura",
    "Alertas" : "alertas"
}

# Configuração da página – deve ser a primeira chamada
st.set_page_config(page_title="Painel Fazendas Simasul", layout="wide")

usuarios = st.secrets["usuarios"]


# Inicializar session state
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False

if "username" not in st.session_state:
    st.session_state["username"] = ""

# Tela de login
if not st.session_state["logged_in"]:
    st.title("Login")
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

time.sleep(1)
mensagem.empty()

# valor inicial
if "page" not in st.session_state:
    st.session_state["page"] = "visao360"

# renderiza os botões
for nome, chave in PAGES.items():
    if st.sidebar.button(nome):
        st.session_state["page"] = chave
            
# ===================== PÁGINA PRINCIPAL (Gestão) =====================
if st.session_state["page"] == "gestao":
    st.sidebar.header("Selecione a Unidade")
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
            f"{caminho_absoluto_base}/taxa_inatividade_diaria.csv"
            
        )

        df_media_status = carregar_csv_seguro(
            f"{caminho_absoluto_base}/media_geral_por_status.csv"
        )

        df_alertas = carregar_csv_seguro(
            f"{caminho_absoluto_base}/fornos_alerta.csv"
        )

        df_perdas = carregar_csv_seguro(
            f"{caminho_absoluto_base}/perdas_por_vazios.csv",
            colunas_minimas=["Mes", "Dias_no_Status", "Perda_m3", "Data_Inicio","Data_Fim"]
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
        if not df_perdas.empty:
            df_perdas["Data_Fim"]=pd.to_datetime(df_perdas["Data_Fim"])
        


        # Filtro de data global
        st.sidebar.header("Filtro de Período")

        base = df_prod_em_processo.copy()
        if base.empty:
            base = df_prod_efetiva.copy()

        if base.empty:
            st.warning("Sem dados de datas para filtrar.")
            ini, fim = pd.Timestamp("1970-01-01"), pd.Timestamp("1970-01-02")
        else:
            base["Data"] = pd.to_datetime(base["Data"])
            dmin, dmax = base["Data"].min().normalize(), base["Data"].max().normalize()

            # Define opções
            opcoes = ["Mês atual", "Mês mais recente do dataset", "Intervalo personalizado"]

            # Sempre inicia com "Mês atual"
            modo = st.sidebar.selectbox("Período", opcoes, index=0)

            if modo == "Mês atual":
                hoje = pd.Timestamp.today().normalize()
                ini = hoje.replace(day=1)
                fim = (ini + pd.offsets.MonthEnd(1))

                ini = max(ini, dmin)
                fim = min(fim, dmax)

            elif modo == "Mês mais recente do dataset":
                ultimo = dmax
                ini = ultimo.replace(day=1)
                fim = (ini + pd.offsets.MonthEnd(1))

                ini = max(ini, dmin)
                fim = min(fim, dmax)

            else:  # Intervalo personalizado
                data_sel = st.sidebar.date_input(
                    "Selecione o intervalo:",
                    [dmin.date(), dmax.date()]
                )
                if isinstance(data_sel, (list, tuple)) and len(data_sel) == 2:
                    ini = pd.to_datetime(data_sel[0])
                    fim = pd.to_datetime(data_sel[1])
                else:
                    ini, fim = dmin, dmax

        # Função para aplicar v
        def _aplica_intervalo(df, col="Data"):
            if df.empty or col not in df.columns:
                return df
            return df[(df[col] >= ini) & (df[col] <= fim)]

        df_prod_efetiva      = _aplica_intervalo(df_prod_efetiva, "Data")
        df_prod_em_processo  = _aplica_intervalo(df_prod_em_processo, "Data")
        df_inatividade       = _aplica_intervalo(df_inatividade, "Data")
        if not df_perdas.empty and "Data_Fim" in df_perdas.columns:
            df_perdas = df_perdas[(df_perdas["Data_Fim"] >= ini) & (df_perdas["Data_Fim"] <= fim)]

        st.markdown(f"Período selecionado: **{ini.date()} a {fim.date()}**")

        # ------------------------------------------
        # 📊 RESUMO EXECUTIVO
        # ------------------------------------------

        st.header("Resumo Executivo")

        
        col1, col2, col3, col4 = st.columns(4)

        col1.metric("Produção no Período Selecionado (m³)", round(df_prod_efetiva["Estimativa_m3"].sum(), 2))
        if not df_inatividade.empty and "Inatividade_%"  in df_inatividade.columns:
            disponibilidade_media = round(100 - df_inatividade["Inatividade_%"].mean(), 2)
            col2.metric("Disponibilidade Média (%)", disponibilidade_media)
        else:
            col2.metric("Disponibilidade Média (%)", "N/D")
        col3.metric(" Fornos em Alerta", len(df_alertas))
        col4.metric("Perdas por ociosidade estimadas (m³)", round(df_perdas["Perda_m3"].sum(), 2))

        # 🔄 Carregar dados adicionais salvos em JSON
        caminho_json_resumo = f"{caminho_absoluto_base}/resumo_operacional.json"
        resumo = carregar_json_seguro(caminho_json_resumo)
        st.markdown(" ")
        st.markdown("---")
        st.markdown(" ")
        # Exibir indicadores adicionais se existirem
        if resumo:
            col5, col6, col7,col8 = st.columns(4)
            col5.metric("Estoque Atual (m³st)", f"{resumo.get('EstoqueAtual_m3st', 'N/D')}")
            col6.metric("Ciclo Médio (dias)", f"{resumo.get('DuracaoMediaCiclo_dias', 'N/D')}")
            col7.metric("Fornos Operacionais", f"{resumo.get('FornosOperacionais', 'N/D')}")
            col8.metric(" Conversão(mst/mca)", f"{resumo.get('Conversaost', 'N/D')}")

        # ------------------------------------------
        # 📈 PRODUÇÃO (Efetiva e em Processo)
        # ------------------------------------------
        tab1, tab2 , tab3, tab4 = st.tabs(["Desempenho", "Produção Efetiva", "Produção em Processamento","Transporte"])

        # Metas por unidade
        metas_unidade = {
            "Mata Verde": 500,
            "Gloria": 1400,
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
                {"range": [850, 1200], "cor_solida": "rgba(0,255,0,1)", "cor_clara": "rgba(0,255,0,0.2)"}
            ],
            "Gloria": [
                {"range": [0, 700], "cor_solida": "rgba(255,0,0,1)", "cor_clara": "rgba(255,0,0,0.2)"},
                {"range": [700, 950], "cor_solida": "rgba(255,255,0,1)", "cor_clara": "rgba(255,255,0,0.2)"},
                {"range": [950, 2000], "cor_solida": "rgba(0,255,0,1)", "cor_clara": "rgba(0,255,0,0.2)"}
            ]
        }

        with tab1:
            # Pega o valor da meta e faixas da unidade
            valor_desejado = metas_unidade.get(unidade_sel, )
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
                        "line": {"color": "rgba(0,0,0,0)", "width": 4},
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
            fig2 = px.bar(df_prod_em_processo, x="Data", y="Estimativa_m3",color_discrete_sequence=["#2ca02c"], title="Carvão em Produção (m³)",text_auto='.2f')
            st.plotly_chart(fig2, use_container_width=True)

        with tab4:
            st.subheader("Dados de Transporte")
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
        
        tabinat,tabdisp,tabcarregamento,tabdescarregamento= st.tabs(["Disponibilidade Operacional","Taxa de Inatividade","Carregamentos Diários", "Descarregamentos Diários"])
        with tabinat: 
            if df_inatividade.empty or "Inatividade_%" not in df_inatividade.columns:
               
                df_inatividade = pd.DataFrame({
                    "Data": pd.date_range(start=ini, end=fim, freq="D"),
                    "Inatividade_%": 0
                })

             # Calcular disponibilidade
            df_inatividade["Disponibilidade_%"] = 100 - df_inatividade["Inatividade_%"]
            df_inatividade["FaixaDisp"] = df_inatividade["Disponibilidade_%"].apply(faixa_disponibilidade)
            
            fig3 = px.bar(
                    df_inatividade,
                    x="Data",
                    y="Disponibilidade_%",
                    color="FaixaDisp",
                    title="Disponibilidade Diária (%)",
                    color_discrete_map={
                        "Alta (≥90%)": "#2ca02c",       # verde
                        "Média (70–90%)": "#ffbf00",    # amarelo
                        "Baixa (<70%)": "#d62728"       # vermelho
                    }
                )
            st.plotly_chart(fig3, use_container_width=True)
        
        with tabdisp:
            df_inatividade["FaixaInat"] = df_inatividade["Inatividade_%"].apply(faixa_inatividade)
            fig4 = px.bar(df_inatividade, x="Data", y="Inatividade_%",color="FaixaInat",color_discrete_map={
        "Baixa (≤10%)": "#2ca02c",       # verde
        "Média (10–30%)": "#ffbf00",     # amarelo
        "Alta (>30%)": "#d62728"        # vermelho
    }, title="Taxa de Inatividade Diária (%)")
            st.plotly_chart(fig4, use_container_width=True)

        with tabcarregamento:
            if "df_carregamentos" in locals() and not df_carregamentos.empty:
                media_carregamento = df_carregamentos["Qtde_Carregada"].mean()
                max_carregamentos = df_carregamentos["Qtde_Carregada"].max()
                
                fig5 = px.bar(df_carregamentos, x="Data", y="Qtde_Carregada",
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
                fig6 = px.bar(df_descarregamentos, x="Data", y="Qtde_Descarregada",
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
        tab_hist, tab_proj = st.tabs(["Análise Histórica", "Projeções"])
        
        with tab_hist:
                
            df_historico = carregar_csv_seguro(
            f"{caminho_absoluto_base}/fazendas.csv", 
            colunas_minimas=["FazendaNome", "Data", "Metragem"]
            )
            exibir_painel_historico(df_historico, unidade_sel, formatar_nome_fazenda)
            
        with tab_proj:    
            st.header("Projeções de Produção")
            
            tab3, tab4 = st.tabs(["Projeção Mês", "Projeção de Consumo"])
            
            # Caminhos dos arquivos
            caminho_proj_30 = f"{caminho_absoluto_base}/simulacao_30dias.csv"
            caminho_proj_meta = f"{caminho_absoluto_base}/simulacao_meta_volume.csv"
            
           
            with tab3:
                if os.path.exists(caminho_proj_30):
                    df_proj_30 = pd.read_csv(caminho_proj_30)

                    # garantir datetime e limpar
                    df_proj_30["Previsao_Descarregado"] = pd.to_datetime(
                        df_proj_30["Previsao_Descarregado"], errors="coerce"
                    )
                    df_proj_30 = df_proj_30.dropna(subset=["Previsao_Descarregado"])

                    if df_proj_30.empty:
                        st.info("Sem projeções válidas.")
                    else:
                        # período do mês atual
                        hoje = pd.Timestamp.today()
                        periodo_atual = hoje.to_period("M")

                        # períodos disponíveis no DF
                        periodos = df_proj_30["Previsao_Descarregado"].dt.to_period("M")

                        # escolha do período alvo
                        if (periodos == periodo_atual).any():
                            alvo = periodo_atual
                        else:
                            alvo = periodos.max()  # mês mais recente do DF

                        # filtrar para o mês alvo
                        dff = df_proj_30[periodos == alvo].copy()

                        if dff.empty:
                            st.info("Sem projeções no mês selecionado.")
                        else:
                            somaproj = dff["Estimativa_m3"].sum()
                            mes_legenda = f"{alvo.start_time:%Y-%m}"

                            fig5 = px.bar(
                                dff,
                                x="Previsao_Descarregado",
                                y="Estimativa_m3",
                                title=f"Projeção para o mês atual — {mes_legenda}",
                                text_auto=".2f",
                            )
                            st.plotly_chart(fig5, use_container_width=True)

                            st.metric("Volume Total :", f"{somaproj:.2f} m³")
                else:
                        st.warning("⛔ Dados de projeção para os próximos 30 dias não disponíveis para esta unidade .")
            
            with tab4:
                if os.path.exists(caminho_proj_meta):
                    df_proj_vol = pd.read_csv(caminho_proj_meta)

                    # Calcular intervalo de datas
                    data_min = pd.to_datetime(df_proj_vol["Previsao_Descarregado"].min())
                    data_max = pd.to_datetime(df_proj_vol["Previsao_Descarregado"].max())
                    dias_corridos = (data_max - data_min).days + 1

                    # Somar volume total projetado
                    volume_total = df_proj_vol["Estimativa_m3"].sum()

                

                    # Exibir gráfico0
                    fig6 = px.bar(
                        df_proj_vol,
                        x="Previsao_Descarregado",
                        y="Estimativa_m3",
                        title="Projeção até zerar estoque",
                        text_auto='.2f'
                    )
                    st.plotly_chart(fig6, use_container_width=True)
                    
                    col1, col2 = st.columns(2)
                    col1.metric("Intervalo de dias", f"{dias_corridos} dias")
                    col2.metric("Volume Total a Produzir", f"{volume_total:.2f} m³")
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

        if not df_perdas.empty and {"Data_Fim", "Perda_m3"}.issubset(df_perdas.columns):
            # Datas e coluna Mes
            df_perdas["Data_Fim"] = pd.to_datetime(df_perdas["Data_Fim"], errors="coerce")
            df_perdas = df_perdas.dropna(subset=["Data_Fim"])
            if "Mes" not in df_perdas.columns:
                df_perdas["Mes"] = df_perdas["Data_Fim"].dt.to_period("M").astype(str)  # ex: 2025-08

            # Filtro período
            df_perdas_filtrado = df_perdas[(df_perdas["Data_Fim"] >= ini) & (df_perdas["Data_Fim"] <= fim)]

            if not df_perdas_filtrado.empty:
                # Agrupamento correto
                perdas_agrupadas = (
                    df_perdas_filtrado.groupby("Mes", as_index=False)["Perda_m3"].sum()
                )

                # Ordena por mês cronológico
                perdas_agrupadas["Mes_ord"] = pd.to_datetime(perdas_agrupadas["Mes"], format="%Y-%m", errors="coerce")
                perdas_agrupadas = perdas_agrupadas.sort_values("Mes_ord").drop(columns=["Mes_ord"])

                fig_perdas = px.bar(
                    perdas_agrupadas,
                    x="Mes",
                    y="Perda_m3",
                    text_auto=".2f",
                    title="Perdas Estimadas por Mês (m³)",
                    labels={"Perda_m3": "Perda (m³)", "Mes": "Mês"},
                    color_discrete_sequence=["red"]
                )
                st.plotly_chart(fig_perdas, use_container_width=True)
            else:
                st.info("Não há perdas registradas no período selecionado.")
        else:
            st.warning("⛔ Dados de perdas por ociosidade indisponíveis ou incompletos.")
        # ------------------------------------------
        # 📥 DOWNLOAD RELATÓRIO PDF
        # ------------------------------------------
        st.header("Baixar Relatório Semanal")
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
        st.title(f"Histórico de Produção - Fazenda {unidade_sel} (Inativa)")
        
        # Carregar histórico geral
        df_historico = carregar_csv_seguro(
        f"{caminho_absoluto_base}/fazendas.csv", 
        colunas_minimas=["FazendaNome", "Data", "Metragem"]
    )
        exibir_painel_historico(df_historico, unidade_sel, formatar_nome_fazenda)
# ===================== VISÃO 360° ====================================
elif st.session_state["page"] == "visao360":
    st.title("Visão 360° – Comparativo entre Unidades")
    st.markdown("Esta página consolida os principais indicadores das unidades ativas para análise integrada de desempenho.")

    #  Unidades que deseja comparar
    unidades_ativas = [k for k, v in fazendas_ativas.items() if v]

    # Base de dados por unidade
    dados_unidades = {}
    dados_resumo = []

    for unidade in unidades_ativas:
        caminho = f"data/{unidade.lower().replace(' ', '').replace('.', '')}/producao_estimada_diaria.csv"
        df = carregar_csv_seguro(caminho, colunas_minimas=["Data", "Estimativa_m3"])
        caminho_json = f"data/{unidade.lower().replace(' ', '').replace('.', '')}/resumo_operacional.json"
        resumo = carregar_json_seguro(caminho_json)
        if not df.empty:
            df["Unidade"] = unidade
            df["Data"] = pd.to_datetime(df["Data"], errors="coerce")
            df["AnoMes"] = df["Data"].dt.to_period("M").astype(str)
            dados_unidades[unidade] = df
        if resumo:  # Se o JSON foi carregado corretamente
            dados_resumo.append({
                "Unidade": unidade,
                "Estoque (m³st)": resumo.get("EstoqueAtual_m3st", None),
                "Ciclo Médio (dias)": resumo.get("DuracaoMediaCiclo_dias", None),
                "Fornos Operacionais": resumo.get("FornosOperacionais", None),
                "Conversão (mst/mca)": resumo.get("Conversaost", None),
                "Capacidade Volumétrica Fornos (mst)": resumo.get("Capacidadevol",None)
            })
    
    # Transformar em DataFrame
    df_resumo = pd.DataFrame(dados_resumo)
    # Garantir que os valores sejam numéricos
    df_resumo["Conversão (mst/mca)"] = pd.to_numeric(df_resumo["Conversão (mst/mca)"], errors="coerce")
    df_resumo["Capacidade Volumétrica Fornos (mst)"] = pd.to_numeric(df_resumo["Capacidade Volumétrica Fornos (mst)"], errors="coerce")

    df_resumo["Capacidade Produtiva"] = (df_resumo["Capacidade Volumétrica Fornos (mst)"] / df_resumo["Conversão (mst/mca)"]).round(2)


    # Unir todos em um único DataFrame
    df_comparativo = pd.concat(dados_unidades.values(), ignore_index=True) if dados_unidades else pd.DataFrame()

    # Verificar se há dados
    if df_comparativo.empty:
        st.warning("❗ Nenhum dado disponível para exibir o comparativo.")
        st.stop()
    #---------------------------------------------------------------------------
    tab_diario, tab_semanal,tab_mensal,  tab_box = st.tabs(["Produção Diária","Produção Semanal","Produção Mensal","Distribuição (Boxplot)"])

    with tab_diario:
            st.subheader("Produção Diária Consolidada por Unidade")

            df_diario = df_comparativo.copy()
            df_diario["Dia"] = df_diario["Data"].dt.date
            df_diaria_agrupada = df_diario.groupby(["Dia", "Unidade"])["Estimativa_m3"].sum().reset_index()

            if st.button("Soma das Fazendas – Diária", key="btn_soma_diaria"):
                df_total_diaria = df_diaria_agrupada.groupby("Dia")["Estimativa_m3"].sum().reset_index()
                fig_soma_diaria = px.bar(
                    df_total_diaria,
                    x="Dia",
                    y="Estimativa_m3",
                    title="Produção Diária Total (m³) – Todas as Unidades",
                    labels={"Estimativa_m3": "Produção (m³)", "Dia": "Data"},
                    text_auto=".2s"
                )
                st.plotly_chart(fig_soma_diaria, use_container_width=True)
            else:
                fig_prod_diaria = px.bar(
                    df_diaria_agrupada,
                    x="Dia",
                    y="Estimativa_m3",
                    color="Unidade",
                    barmode="group",
                    title="Produção diária (m³) por unidade",
                    labels={"Estimativa_m3": "Produção (m³)", "Dia": "Data"},
                    text_auto=".2s"
                )
                st.plotly_chart(fig_prod_diaria, use_container_width=True) 


    with tab_semanal:
        st.subheader("Produção Semanal por Unidade")

        df_semanal = df_comparativo.copy()
        df_semanal["Semana"] = df_semanal["Data"].dt.to_period("W").apply(lambda r: r.start_time.date())
        df_semanal_agrupada = df_semanal.groupby(["Semana", "Unidade"])["Estimativa_m3"].sum().reset_index()

        if st.button("Soma das Fazendas – Semanal", key="btn_soma_semanal"):
            df_total_semanal = df_semanal_agrupada.groupby("Semana")["Estimativa_m3"].sum().reset_index()
            fig_soma_semanal = px.bar(
                df_total_semanal,
                x="Semana",
                y="Estimativa_m3",
                title="Produção Semanal Total (m³) – Todas as Unidades",
                labels={"Estimativa_m3": "Produção (m³)", "Semana": "Semana"},
                text_auto=".2s"
            )
            st.plotly_chart(fig_soma_semanal, use_container_width=True)
        else:
            fig_prod_semanal = px.bar(
                df_semanal_agrupada,
                x="Semana",
                y="Estimativa_m3",
                color="Unidade",
                barmode="group",
                title="Produção semanal (m³) por unidade",
                labels={"Estimativa_m3": "Produção (m³)", "Semana": "Semana"},
                text_auto=".2s"
            )
            st.plotly_chart(fig_prod_semanal, use_container_width=True)

    with tab_mensal:    
        st.subheader("Produção Mensal por Unidade")

        df_mensal = df_comparativo.groupby(["Unidade", "AnoMes"])["Estimativa_m3"].sum().reset_index()

        if st.button("Soma das Fazendas – Mensal", key="btn_soma_mensal"):
            df_total_mensal = df_mensal.groupby("AnoMes")["Estimativa_m3"].sum().reset_index()
            fig_soma_mensal = px.bar(
                df_total_mensal,
                x="AnoMes",
                y="Estimativa_m3",
                title="Produção Mensal Total (m³) – Todas as Unidades",
                labels={"Estimativa_m3": "Produção (m³)", "AnoMes": "Mês"},
                text_auto=".2s"
            )
            st.plotly_chart(fig_soma_mensal, use_container_width=True)
        else:
            fig_prod_mensal = px.bar(
                df_mensal,
                x="AnoMes",
                y="Estimativa_m3",
                color="Unidade",
                barmode="group",
                title="Produção mensal (m³) por unidade",
                labels={"Estimativa_m3": "Produção (m³)", "AnoMes": "Ano-Mês"},
                text_auto=".2s"
            )
            st.plotly_chart(fig_prod_mensal, use_container_width=True)

    

         
   

   
    with tab_box:
        st.subheader("Distribuição da Produção Diária por Unidade")

        df_diario_box = df_comparativo.copy()
        df_diario_box["Dia"] = df_diario_box["Data"].dt.date

        df_boxplot = df_diario_box.groupby(["Dia", "Unidade"])["Estimativa_m3"].sum().reset_index()

        fig_box = px.box(
            df_boxplot,
            x="Unidade",
            y="Estimativa_m3",
            points="outliers",  # ou "all" se quiser todos os pontos individuais
            color="Unidade",
            title="Distribuição da Produção Diária por Unidade",
            labels={"Estimativa_m3": "Produção (m³)"}
        )

        st.plotly_chart(fig_box, use_container_width=True) 
    
    
#------------------------------------------------------------------------
    st.subheader("Indicadores Consolidadados")
    
    df_disponibilidade_total = []

    for unidade in unidades_ativas:
        caminho_disp = f"data/{unidade.lower().replace(' ', '').replace('.', '')}/taxa_inatividade_diaria.csv"
        df_disp = carregar_csv_seguro(caminho_disp)
        if not df_disp.empty and "Inatividade_%" in df_disp.columns:
            disponibilidade = 100 - df_disp["Inatividade_%"].mean()
            df_disponibilidade_total.append({
                "Unidade": unidade,
                "Disponibilidade Média (%)": round(disponibilidade, 2)
            })

    df_disp_final = pd.DataFrame(df_disponibilidade_total)
    #------------------------------------------------------------------------
    # Juntar df_resumo com df_disp_final pela coluna "Unidade"
    df_merged = pd.merge(df_resumo, df_disp_final, on="Unidade", how="outer")

    # Reorganizar colunas, se desejar
    colunas_desejadas = [
        "Unidade",
        "Fornos Operacionais",
        "Ciclo Médio (dias)",
        "Estoque (m³st)",
        "Conversão (mst/mca)",
        "Capacidade Volumétrica Fornos (mst)",
        "Capacidade Produtiva",
        "Disponibilidade Média (%)"
    ]
    df_merged = df_merged[[col for col in colunas_desejadas if col in df_merged.columns]]

    # Exibir a tabela única
    st.dataframe(df_merged.style.format({
        "Ciclo Médio (dias)": "{:.1f}",
        "Estoque (m³st)": "{:,.2f}",
        "Conversão (mst/mca)": "{:.2f}",
        "Capacidade Volumétrica Fornos (mst)": "{:,.2f}",
        "Capacidade Produtiva": "{:,.2f}",
        "Disponibilidade Média (%)": "{:.2f}"
    }))

    #-----------------------------SPREAD DE PREÇO MERCADO-------------------------
    caminho_spread="data/variacao_mensal.csv"
    
    df_cotacao_mensal=carregar_csv_seguro(caminho_spread)

    custos_fixos = {
    "Mata Verde": 338,
    "Proteção": 160,
}   
    st.subheader("Custo de produção vs Cotação de mercado - Carvão Vegetal (m³)")
    # Garantir que o CSV foi carregado corretamente
    if not df_cotacao_mensal.empty:
        df_cotacao_mensal["Ano"] = df_cotacao_mensal["Ano"].astype(int)
        df_cotacao_mensal["Mes"] = df_cotacao_mensal["Mes"].astype(int)

        # Criar coluna de data para facilitar o eixo X do gráfico
        df_cotacao_mensal["Data"] = pd.to_datetime(df_cotacao_mensal["Ano"].astype(str) + "-" + df_cotacao_mensal["Mes"].astype(str) + "-01")
        df_cotacao_mensal = df_cotacao_mensal.sort_values("Data")

    else:
        st.warning("⚠️ O arquivo de variação mensal não foi encontrado ou está vazio.")
        st.stop()
    fig = go.Figure()

    # Linha do preço de mercado
    fig.add_trace(go.Scatter(
        x=df_cotacao_mensal["Data"],
        y=df_cotacao_mensal["PrecoUnitarioNota"],
        mode="lines+markers",
        name="Preço Mercado",
        line=dict(color="blue", width=3)
    ))

    # Adicionar custo fixo por unidade
    for unidade, custo in custos_fixos.items():
        fig.add_trace(go.Scatter(
            x=df_cotacao_mensal["Data"],
            y=[custo] * len(df_cotacao_mensal),
            mode="lines",
            name=f"Custo {unidade}",
            line=dict(dash="dash")  # Linha tracejada
        ))

    fig.update_layout(
        title="Preço de Mercado vs Custos Fixos por Unidade",
        xaxis_title="Data",
        yaxis_title="Preço (R$/m³st)",
        hovermode="x unified"
    )

    st.plotly_chart(fig, use_container_width=True)
# ===================== Alertas ======================
elif st.session_state["page"] == "alertas":
   st.title("Alertas")
# ===================== Silvicultura ======================
elif st.session_state["page"] == "silvicultura":
    import pandas as pd
    import numpy as np
    import plotly.express as px
    import streamlit as st

    # ----------------- Taxonomia canônica e mapa AppSheet->canônico -----------------
    ATIVIDADES = [
        "Todos",
        "Planejamento, licenciamento e mapas",
        "Viveiro: produção e aclimatação de mudas",
        "Preparo de solo e conservação (terraceamento, curvas de nível)",
        "Correção e adubação (calagem, fosfatagem, NPK)",
        "Plantio e replantio",
        "Irrigação inicial, sombreamento e tutoria",
        "Controle de formigas e outras pragas",
        "Controle de plantas daninhas (roçada manual, mecânica, química)",
        "Manutenção de aceiros e prevenção a incêndios",
        "Podas, desrama e condução de copas",
        "Desbastes e uniformização de povoamentos",
        "Adubação de cobertura e reposições",
        "Estradas florestais: abertura, drenagem e manutenção",
        "Cercas, marcos e proteção de áreas sensíveis",
        "Inventário florestal e mensurações dendrométricas",
        "Monitoramento de crescimento, sanidade e qualidade da madeira",
        "Conservação de APP/RL e restauração ecológica",
        "Colheita, baldeio e carregamento",
        "Transporte florestal e logística de pátio",
        "Manejo de resíduos e pós-colheita (restos culturais)",
        "Segurança, treinamento e certificações (FSC/PEFC)",
        "Silvicultura de precisão: drones, sensores, taxa variável",
        "Gestão de custos, orçamentos e indicadores",
    ]
    MAP_APP2CAN = {
        "Planejamento, licenciamento e mapas": "Planejamento, licenciamento e mapas",
        "Viveiro: produção e aclimatação de mudas": "Viveiro: produção e aclimatação de mudas",
        "Preparo de solo e conservação (terraceamento, curvas de nível)": "Preparo de solo e conservação (terraceamento, curvas de nível)",
        "Correção e adubação (calagem, fosfatagem, NPK)": "Correção e adubação (calagem, fosfatagem, NPK)",
        "Plantio e replantio": "Plantio e replantio",
        "Irrigação inicial, sombreamento e tutoria": "Irrigação inicial, sombreamento e tutoria",
        "Controle de plantas daninhas (roçada manual, mecânica, química)": "Controle de plantas daninhas (roçada manual, mecânica, química)",
        "Manutenção de aceiros e prevenção a incêndios": "Manutenção de aceiros e prevenção a incêndios",
        "Podas, desrama e condução de copas": "Podas, desrama e condução de copas",
        "Desbastes e uniformização de povoamentos": "Desbastes e uniformização de povoamentos",
        "Adubação de cobertura e reposições": "Adubação de cobertura e reposições",
        "Estradas florestais: abertura, drenagem e manutenção": "Estradas florestais: abertura, drenagem e manutenção",
        "Cercas, marcos e proteção de áreas sensíveis": "Cercas, marcos e proteção de áreas sensíveis",
        "Inventário florestal e mensurações dendrométricas": "Inventário florestal e mensurações dendrométricas",
        "Monitoramento de crescimento, sanidade e qualidade da madeira": "Monitoramento de crescimento, sanidade e qualidade da madeira",
        "Conservação de APP/RL e restauração ecológica": "Conservação de APP/RL e restauração ecológica",
        "Colheita, baldeio e carregamento": "Colheita, baldeio e carregamento",
        "Transporte florestal e logística de pátio": "Transporte florestal e logística de pátio",
        "Silvicultura de precisão: drones, sensores, taxa variável": "Silvicultura de precisão: drones, sensores, taxa variável",
        "Manejo de resíduos e pós-colheita (restos culturais)": "Manejo de resíduos e pós-colheita (restos culturais)",
        "Segurança, treinamento e certificações (FSC/PEFC)": "Segurança, treinamento e certificações (FSC/PEFC)",
        "Gestão de custos, orçamentos e indicadores": "Gestão de custos, orçamentos e indicadores",
        # agregações
        "Controle de formigas": "Controle de formigas e outras pragas",
        "Controle de pragas": "Controle de formigas e outras pragas",
    }
    def normaliza_atividade(s):
        if not isinstance(s, str): return s
        s = s.strip().rstrip(".")
        return MAP_APP2CAN.get(s, s)

    # ----------------- UI -----------------
    st.title("Silvicultura")
    st.sidebar.header("Filtros")

    fazendas_opts = ["Todas", "Mata Verde", "Gloria", "Proteção", "Santa Ana", "Mapal", "Alto da Serra", "Faz. Cabeceira Comprida"]
    fazenda_sel = st.sidebar.selectbox("Fazenda", fazendas_opts, index=0)
    atividade_sel = st.sidebar.selectbox("Atividade", ATIVIDADES, index=0)
    st.caption(f"Selecionado • Fazenda: {fazenda_sel} | Atividade: {atividade_sel}")

    # ----------------- Dados (mantém leitura via CSV) -----------------
    url_csv = st.secrets["silviculturadatabase"]["link"]
    df = ler_planilha_publicada(url_csv, expect_cols=[
    "ID","Data","Fazenda/Unidade","Talhão","Atividade","Fornecedor/Responsável",
    "Categoria Atividade","Unidade de medida","Quantidade","Insumo","Descrição",
    "Valor unitário(R$/X)","Custo diário(R$)","Colaboradores","Horário"
])
    if df.empty:
        st.warning("Sem dados de silvicultura.")
        st.stop()

    # ----------------- Padroniza nomes vindos da planilha AppSheet -----------------
    rename_map = {
        "ID": "ID",
        "Data": "Data",
        "Fazenda/Unidade": "Fazenda",
        "Talhão": "Talhão",
        "Atividade": "Atividade",
        "Fornecedor/Responsável": "Fornecedor",
        "Categoria Atividade": "Categoria",
        "Unidade de medida": "UM",
        "Quantidade": "Quantidade",
        "Insumo": "Insumo",
        "Descrição": "Descrição",
        "Valor unitário(R$/X)": "Valor unitário (R$/X)",
        "Custo diário(R$)": "Custo Diário (R$)",
        "Colaboradores": "Colaboradores",
        "Horário": "Horário (Início - Fim)",
    }
    # renomeia apenas colunas existentes
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})

    # tipos
    if "Data" not in df.columns:
        st.error("Coluna 'Data' ausente.")
        st.stop()
    df["Data"] = pd.to_datetime(df["Data"], errors="coerce")
    df = df.dropna(subset=["Data"]).sort_values("Data")

    for c in ["Talhão", "Quantidade", "Valor unitário (R$/X)", "Custo Diário (R$)", "Colaboradores"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    # normaliza atividade
    if "Atividade" in df.columns:
        df["Atividade"] = df["Atividade"].apply(normaliza_atividade)

    # se custo diário faltar, calcula
    if "Custo Diário (R$)" in df.columns and df["Custo Diário (R$)"].isna().all():
        if {"Quantidade", "Valor unitário (R$/X)"}.issubset(df.columns):
            df["Custo Diário (R$)"] = df["Quantidade"] * df["Valor unitário (R$/X)"]

    # cria coluna Total (kg) somente quando UM == kg
    if {"UM", "Quantidade"}.issubset(df.columns):
        mask_kg = df["UM"].astype(str).str.lower().isin(["kg", "quilograma", "quilogramas"])
        df["Total (kg)"] = np.where(mask_kg, df["Quantidade"], np.nan)

    # ----------------- Período -----------------
    dmin, dmax = df["Data"].min().normalize(), df["Data"].max().normalize()
    hoje = pd.Timestamp.today().normalize()
    ini = max(hoje.replace(day=1), dmin)
    fim = min(ini + pd.offsets.MonthEnd(1), dmax)

    modo = st.sidebar.selectbox("Período", ["Mês atual", "Mês mais recente", "Intervalo personalizado"], index=0)
    if modo == "Mês mais recente":
        ini = max(dmax.replace(day=1), dmin); fim = dmax
    elif modo == "Intervalo personalizado":
        di = st.sidebar.date_input("Intervalo:", [dmin.date(), dmax.date()])
        if isinstance(di, (list, tuple)) and len(di) == 2:
            ini, fim = pd.to_datetime(di[0]), pd.to_datetime(di[1])

    st.caption(f"Período: {ini.date()} a {fim.date()}")

    # ----------------- Filtros -----------------
    dff = df[(df["Data"] >= ini) & (df["Data"] <= fim)].copy()

    if fazenda_sel != "Todas" and "Fazenda" in dff.columns:
        dff = dff[dff["Fazenda"] == fazenda_sel]

    if atividade_sel != "Todos" and "Atividade" in dff.columns:
        dff = dff[dff["Atividade"] == atividade_sel]

    if "Talhão" in dff.columns:
        talhoes = sorted(dff["Talhão"].dropna().astype(str).unique())
        sel_t = st.multiselect("Talhões", talhoes, default=talhoes)
        if sel_t:
            dff = dff[dff["Talhão"].astype(str).isin(sel_t)]

    if dff.empty:
        st.warning("Sem registros no filtro atual.")
        st.stop()

    # ----------------- KPIs -----------------
    total_kg     = float(dff["Total (kg)"].sum()) if "Total (kg)" in dff.columns else 0.0
    custo_total  = float(dff["Custo Diário (R$)"].sum()) if "Custo Diário (R$)" in dff.columns else 0.0
    colab_total  = float(dff["Colaboradores"].sum()) if "Colaboradores" in dff.columns else 0.0

    # fallback de área não existe nessa planilha -> mostra só se existir
    area_total = float(dff["Área (ha)"].sum()) if "Área (ha)" in dff.columns else np.nan

    custo_kg     = (custo_total / total_kg) if total_kg > 0 else np.nan
    prod_kg_ha   = (total_kg / area_total) if (not np.isnan(area_total) and area_total > 0 and total_kg > 0) else np.nan
    kg_por_colab = (total_kg / colab_total) if colab_total > 0 and total_kg > 0 else np.nan

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Insumo (kg)", f"{total_kg:,.0f}" if total_kg > 0 else "—")
    c2.metric("Custo (R$)", f"{custo_total:,.2f}" if custo_total > 0 else "—")
    c3.metric("Custo por kg (R$/kg)", f"{custo_kg:,.2f}" if pd.notna(custo_kg) else "—")
    c4.metric("Produtividade (kg/ha)", f"{prod_kg_ha:,.1f}" if pd.notna(prod_kg_ha) else "—")

    c5, c6 = st.columns(2)
    c5.metric("Área trabalhada (ha)", f"{area_total:,.2f}" if pd.notna(area_total) else "—")
    c6.metric("kg por colaborador", f"{kg_por_colab:,.1f}" if pd.notna(kg_por_colab) else "—")

    # ----------------- Séries por dia -----------------
    agg = {"Custo Diário (R$)": "sum"}
    if "Total (kg)" in dff.columns:
        agg["Total (kg)"] = "sum"
    if "Quantidade" in dff.columns:
        agg["Quantidade"] = "sum"

    by_day = dff.groupby("Data", as_index=False).agg(agg)

    if "Total (kg)" in by_day.columns and not by_day["Total (kg)"].isna().all():
        st.subheader("Consumo de insumo (kg)")
        st.plotly_chart(px.bar(by_day, x="Data", y="Total (kg)", text_auto=True), use_container_width=True)
    else:
        st.subheader("Quantidade total (todas UMs)")
        st.plotly_chart(px.bar(by_day, x="Data", y="Quantidade"), use_container_width=True)

    if "Custo Diário (R$)" in by_day.columns:
        st.subheader("Custo diário (R$)")
        st.plotly_chart(px.line(by_day, x="Data", y="Custo Diário (R$)"), use_container_width=True)

    if {"Custo Diário (R$)", "Total (kg)"} <= set(by_day.columns):
        by_day["custo_kg"] = np.where(by_day["Total (kg)"] > 0,
                                      by_day["Custo Diário (R$)"] / by_day["Total (kg)"], np.nan)
        st.subheader("Custo por kg por dia (R$/kg)")
        st.plotly_chart(px.line(by_day, x="Data", y="custo_kg"), use_container_width=True)

    # ----------------- Por talhão -----------------
    if "Talhão" in dff.columns:
        cols = [c for c in ["Total (kg)", "Quantidade", "Custo Diário (R$)"] if c in dff.columns]
        if cols:
            by_talhao = dff.groupby("Talhão", as_index=False).agg({c: "sum" for c in cols})

            if "Total (kg)" in by_talhao.columns and not by_talhao["Total (kg)"].isna().all():
                st.subheader("Consumo de insumo por talhão (kg)")
                st.plotly_chart(px.bar(by_talhao.sort_values("Total (kg)", ascending=False).head(15),
                                       x="Talhão", y="Total (kg)", text_auto=True),
                                use_container_width=True)
            else:
                st.subheader("Quantidade por talhão")
                st.plotly_chart(px.bar(by_talhao.sort_values("Quantidade", ascending=False).head(15),
                                       x="Talhão", y="Quantidade", text_auto=True),
                                use_container_width=True)

            if "Custo Diário (R$)" in by_talhao.columns:
                st.subheader("Custo por talhão (R$)")
                st.plotly_chart(px.bar(by_talhao.sort_values("Custo Diário (R$)", ascending=False).head(15),
                                       x="Talhão", y="Custo Diário (R$)", text_auto=True),
                                use_container_width=True)

    # ----------------- Turnos -----------------
    if "Horário (Início - Fim)" in dff.columns:
        turnos = dff.groupby("Horário (Início - Fim)").size().reset_index(name="Registros").sort_values("Registros", ascending=False)
        st.subheader("Registros por turno")
        st.plotly_chart(px.bar(turnos, x="Horário (Início - Fim)", y="Registros", text_auto=True), use_container_width=True)

    # ----------------- Tabela -----------------
    st.subheader("Registros")
    st.dataframe(dff, use_container_width=True)

# ===================== SIMULADOR =====================================
elif st.session_state["page"] == "simulador":
    st.title("Simulador")
# ===================== AUDITORIA CUBAGEM ==============================
elif st.session_state["page"] == "auditoria":
    st.title("📋 Painel de Auditoria – Cubagem")

    # caminhos dos dois CSVs gerados pelo script de auditoria
    caminho_alertas_motorista  = os.path.join(base_2, "alertas_motorista.csv")
    caminho_ranking_motoristas = os.path.join(base_2, "ranking_motoristas.csv")
    caminho_alertas_carga=os.path.join(base_2,"alertas_carga.csv")
    caminho_fazendas=os.path.join(base_2,"fazendas_concatenadas.csv")

    df_alertas_mot = carregar_csv_seguro(caminho_alertas_motorista)
    df_ranking_mot = carregar_csv_seguro(caminho_ranking_motoristas)
    df_alertas_carga=carregar_csv_seguro(caminho_alertas_carga)
    df_fazendas=carregar_csv_seguro(caminho_fazendas)

    tab_rank, tab_alertas = st.tabs(["🏆 Ranking de Motoristas", "🚨 Cargas Suspeitas"])

    with tab_rank:
        if df_ranking_mot.empty:
            st.info("Nenhum dado de ranking disponível.")
        else:
            st.dataframe(df_ranking_mot)
            #fig_rank = px.bar(df_ranking_mot.reset_index(),
             #                 x="MotoristaVeiculo", y="Percentual",
              #                text_auto='.1f',
               #               title="Percentual de Alertas por Motorista",
                #              color_discrete_sequence=["#d62728"])
            #st.plotly_chart(fig_rank, use_container_width=True)

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
    st.markdown("### 📈 Densidade Seca por Fazenda com Alertas")

    if not df_alertas_carga.empty:
        df_alertas_carga = df_alertas_carga.rename(columns={"DataEntrada": "Data"})  # só na memória
        df_alertas_carga["Data"] = pd.to_datetime(df_alertas_carga["Data"], errors="coerce")

    if not df_fazendas.empty:
        df_fazendas["Data"] = pd.to_datetime(df_fazendas["Data"], errors="coerce")

    # 2 ▸ selectbox das fazendas disponíveis no CSV concatenado
    fazendas_disponiveis = sorted(df_fazendas["FazendaNome"].unique())
    fazenda_escolhida = st.selectbox("Selecione a fazenda:", fazendas_disponiveis)

    # 3 ▸ filtrar dados principais + alertas da fazenda
    df_faz_sel   = df_fazendas[df_fazendas["FazendaNome"] == fazenda_escolhida]
    df_alert_sel = df_alertas_carga[df_alertas_carga["FazendaNome"] == fazenda_escolhida]

    if df_faz_sel.empty:
        st.info("Nenhum registro encontrado para essa fazenda.")
    else:
        # 4 ▸ figura base – linha de densidade
        fig_faz = px.line(
            df_faz_sel.sort_values("Data"),
            x="Data", y="DensidadeSeca",
            title=f"Densidade Seca – {fazenda_escolhida}",
            labels={"DensidadeSeca": "kg/m³"},
            color_discrete_sequence=["#1f77b4"]
        )

        # 5 ▸ sobrepor pontos de alerta, se existirem
        if not df_alert_sel.empty:
            fig_alert = px.scatter(
                df_alert_sel,
                x="Data", y="DensidadeSeca",
                color_discrete_sequence=["#d62728"],
                symbol_sequence=["circle-open"],
                labels={"DensidadeSeca": "kg/m³"}
            )
            fig_faz.add_traces(fig_alert.data) 
            fig_faz.update_traces(marker=dict(size=10), selector=dict(mode="markers"))
            fig_faz.update_layout(legend=dict(title="Legenda"),
                                showlegend=False)  # esconde legenda duplicada

        st.plotly_chart(fig_faz, use_container_width=True)

    #=======================================================
    # 🔄  COMPARAÇÃO DE 2 FAZENDAS NO PERÍODO COMUM
    # =======================================================
    st.markdown("### 📊 Comparar Duas Fazendas – Período em Comum")

    # 1 ▸ Escolher exatamente 2 fazendas
    fazendas_mult = st.multiselect(
        "Escolha duas fazendas para comparar:",
        fazendas_disponiveis,
        max_selections=2
    )

    if len(fazendas_mult) != 2:
        st.info("Selecione exatamente duas fazendas.")
    else:
        f1, f2 = fazendas_mult

        # 2 ▸ Datas de cada fazenda
        min1, max1 = df_fazendas.query("FazendaNome == @f1")["Data"].min(), df_fazendas.query("FazendaNome == @f1")["Data"].max()
        min2, max2 = df_fazendas.query("FazendaNome == @f2")["Data"].min(), df_fazendas.query("FazendaNome == @f2")["Data"].max()

        # 3 ▸ Período em comum (interseção)
        ini_comum = max(min1, min2)
        fim_comum = min(max1, max2)

        if ini_comum >= fim_comum:
            st.warning("Essas fazendas não têm período de dados em comum.")
        else:
            # 4 ▸ Filtrar dados principais e alertas nesse intervalo
            mask_common = (df_fazendas["Data"].between(ini_comum, fim_comum)) & (df_fazendas["FazendaNome"].isin(fazendas_mult))
            df_common   = df_fazendas[mask_common]

            mask_alert  = (df_alertas_carga["Data"].between(ini_comum, fim_comum)) & (df_alertas_carga["FazendaNome"].isin(fazendas_mult))
            df_alert_cm = df_alertas_carga[mask_alert]

            # 5 ▸ Gráfico combinado
            fig_comb = px.line(
                df_common.sort_values("Data"),
                x="Data", y="DensidadeSeca",
                color="FazendaNome",
                labels={"DensidadeSeca": "kg/m³"},
                title=f"Período comum: {ini_comum.date()} a {fim_comum.date()}"
            )

            # 6 ▸ Adicionar pontos de alerta por fazenda
            for faz, cor in zip(fazendas_mult, ["#d62728", "#9467bd"]):   # 2 cores p/ marcadores
                df_alert_f = df_alert_cm[df_alert_cm["FazendaNome"] == faz]
                if not df_alert_f.empty:
                    fig_comb.add_scatter(
                        x=df_alert_f["Data"],
                        y=df_alert_f["DensidadeSeca"],
                        mode="markers",
                        marker=dict(symbol="circle-open", size=10, line=dict(width=2, color=cor)),
                        name=f"Alertas {faz}",
                        showlegend=True
                    )

            st.plotly_chart(fig_comb, use_container_width=True)
# ------------------------------------------
# 📝 FOOTER
# ------------------------------------------
st.markdown("---")
st.caption("Desenvolvido por Lucas Neves Teixeira")


