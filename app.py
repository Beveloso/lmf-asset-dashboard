import streamlit as st
import streamlit.components.v1 as components
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

# --- 1. CONFIGURAÇÃO VISUAL ---
st.set_page_config(page_title="LMF - ASSET", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #0b0b0b; color: #e0e0e0; }
    h1, h2, h3, h4, h5, h6 { color: #D4AF37 !important; }
    .stButton>button { background-color: #D4AF37; color: #000000; border: None; font-weight: bold; width: 100%; }
    .stButton>button:hover { background-color: #F1C40F; color: #000000; }
    div[data-testid="metric-container"] { background-color: #1a1a1a; border: 1px solid #D4AF37; padding: 15px; border-radius: 8px; }
    hr { border-color: #D4AF37; opacity: 0.3; }
    </style>
""", unsafe_allow_html=True)

if 'carteira' not in st.session_state or (st.session_state.carteira and not isinstance(list(st.session_state.carteira.values())[0], dict)):
    st.session_state['carteira'] = {}

# Formatação de Moeda Padrão Brasil
def formatar_moeda(valor):
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# --- 2. MOTOR DE DADOS ATUALIZADO ---
@st.cache_data(ttl=600)
def fetch_market_data(tickers, start, adj_close=True):
    if not tickers: return pd.DataFrame()
    try:
        df = yf.download(tickers, start=start, progress=False, auto_adjust=adj_close)
        if isinstance(df.columns, pd.MultiIndex):
            data = df['Close']
        elif 'Close' in df.columns:
            data = df['Close']
        else:
            data = df
            
        if isinstance(data, pd.Series): 
            data = data.to_frame(name=tickers[0])
        return data.ffill().bfill()
    except Exception: 
        return pd.DataFrame()

def calcular_metricas(ret_p, ret_m, cdi_a):
    if ret_p.empty or ret_m.empty: return [0]*8
    df = pd.concat([ret_p, ret_m], axis=1).dropna()
    if df.empty: return [0]*8
    rp, rm = df.iloc[:,0], df.iloc[:,1]
    
    ret_acum = (1 + rp).prod() - 1
    vol = rp.std() * np.sqrt(252)
    
    rf_d = (1 + cdi_a)**(1/252) - 1
    excesso = rp.mean() - rf_d
    sharpe = (excesso * 252) / vol if vol > 0 else 0
    neg = rp[rp < 0]
    sortino = (excesso * 252) / (neg.std() * np.sqrt(252)) if not neg.empty and neg.std() > 0 else 0
    
    cum = (1 + rp).cumprod()
    dd = (cum / cum.cummax() - 1).min()
    var95 = np.percentile(rp, 5) if not rp.empty else 0
    
    var_m = np.var(rm)
    beta = np.cov(rp, rm)[0,1] / var_m if var_m > 0 else 0
    alpha = ((1+ret_acum)**(252/len(rp))-1) - (cdi_a + beta * (((1+rm.prod()-1)**(252/len(rp))-1) - cdi_a))
    
    return ret_acum, vol, sharpe, sortino, dd, var95, beta, alpha

# --- 3. BARRA LATERAL ---
with st.sidebar:
    st.header("⚙️ Configuração Principal")
    
    modo_aporte = st.radio("Método de Alocação", ["Por Peso (%)", "Por Valor Financeiro (R$)"], horizontal=True)
    
    col_cap, col_dt = st.columns(2)
    if modo_aporte == "Por Peso (%)":
        capital_inicial_input = col_cap.number_input("Capital Total (R$)", min_value=100.0, value=10000.0, step=1000.0)
    else:
        capital_inicial_input = 0.0 
        col_cap.text_input("Capital Total (R$)", value="Soma Automática", disabled=True, help="O capital será a soma de todos os aportes.")
        
    data_inicio = col_dt.date_input("Data Inicial", datetime(2023,1,1))
    
    # Expansor para esconder configurações secundárias
    with st.expander("📊 Parâmetros de Mercado & Visualização", expanded=False):
        benchmark_sel = st.selectbox("Benchmark", [
            "Ibovespa", "IFIX", "S&P 500", "NASDAQ", "SMLL (Small Caps)", "Ouro", "IPCA + 6%", "CDI/Selic (Manual)"
        ])
        
        if benchmark_sel == "CDI/Selic (Manual)":
            taxa_selic_manual = st.number_input("Taxa Selic/CDI Anual (%)", value=10.5, step=0.1) / 100
        else:
            taxa_selic_manual = 10.5 / 100
            
        c_taxa1, c_taxa2 = st.columns(2)
        cdi_base = c_taxa1.number_input("CDI Base (%)", value=10.5, step=0.1, help="Para cálculo de Sharpe/Alpha") / 100
        ipca_base = c_taxa2.number_input("IPCA Base (%)", value=4.5, step=0.1) / 100
        reinvestir = st.checkbox("Reinvestir Dividendos (Gráficos)", value=True)
    
    st.markdown("---")
    st.subheader("➕ Adicionar Ativos")
    classe_ativo = st.radio("Classe do Ativo", ["Renda Variável", "Renda Fixa"], horizontal=True)
    
    if classe_ativo == "Renda Variável":
        c_rv1, c_rv2 = st.columns(2)
        ticker = c_rv1.text_input("Ticker", help="Ex: PETR4.SA, IVVB11.SA").upper().strip()
        
        if modo_aporte == "Por Peso (%)":
            aporte_val = c_rv2.number_input("Peso (%)", min_value=1.0, value=10.0, key="peso_rv")
        else:
            aporte_val = c_rv2.number_input("Valor (R$)", min_value=1.0, value=1000.0, step=100.0, key="valor_rv")
        
        c_dt1, c_dt2 = st.columns([1, 1.5])
        comprado_inicio_rv = c_dt1.checkbox("Desde o Início?", value=True, key="chk_rv")
        data_compra_rv = data_inicio if comprado_inicio_rv else c_dt2.date_input("Comprado em", value=data_inicio, min_value=data_inicio, key="dt_rv")
        
        if st.button("Inserir Renda Variável") and ticker:
            st.session_state.carteira[ticker] = {'tipo': 'RV', 'aporte': aporte_val, 'data_compra': data_compra_rv}
            st.rerun()
            
    else:
        nome_rf = st.text_input("Nome do Título", help="Ex: Tesouro IPCA+ 2035").strip()
        c_rf1, c_rf2, c_rf3 = st.columns([1.5, 1, 1])
        tipo_rf = c_rf1.selectbox("Indexador", ["Prefixado", "CDI", "IPCA+"])
        taxa = c_rf2.number_input("Taxa (%)", value=10.0, step=0.1, help="Ex: CDI a 110 (digite 110). IPCA+ 6 (digite 6).") / 100
        
        if modo_aporte == "Por Peso (%)":
            aporte_val_rf = c_rf3.number_input("Peso (%)", min_value=1.0, value=10.0, key="peso_rf")
        else:
            aporte_val_rf = c_rf3.number_input("Valor (R$)", min_value=1.0, value=1000.0, step=100.0, key="valor_rf")
        
        c_dt3, c_dt4 = st.columns([1, 1.5])
        comprado_inicio_rf = c_dt3.checkbox("Desde o Início?", value=True, key="chk_rf")
        data_compra_rf = data_inicio if comprado_inicio_rf else c_dt4.date_input("Aplicado em", value=data_inicio, min_value=data_inicio, key="dt_rf")
        
        if st.button("Inserir Renda Fixa") and nome_rf:
            st.session_state.carteira[nome_rf] = {'tipo': 'RF', 'indexador': tipo_rf, 'taxa': taxa, 'aporte': aporte_val_rf, 'data_compra': data_compra_rf}
            st.rerun()
            
    if st.button("🗑️ Limpar Carteira Completa"):
        st.session_state.carteira = {}
        st.rerun()

# --- 4. TELA PRINCIPAL ---
st.title("🏛️ LMF - ASSET")

if not st.session_state.carteira:
    st.info("👋 Configure os parâmetros na barra lateral e adicione ativos para montar sua estratégia.")
else:
    with st.spinner("Processando modelagens financeiras..."):
        ativos_rv = [k for k, v in st.session_state.carteira.items() if v['tipo'] == 'RV']
        
        df_rv_com = fetch_market_data(ativos_rv, data_inicio, adj_close=True)
        df_rv_sem = fetch_market_data(ativos_rv, data_inicio, adj_close=False) 
        
        if benchmark_sel == "Ibovespa":
            df_bench = fetch_market_data(['^BVSP'], data_inicio, adj_close=True)
            ticker_bench = '^BVSP'
        elif benchmark_sel == "IFIX":
            df_bench = fetch_market_data(['IFIX.SA'], data_inicio, adj_close=True)
            ticker_bench = 'IFIX.SA'
        elif benchmark_sel == "S&P 500":
            df_bench = fetch_market_data(['^GSPC'], data_inicio, adj_close=True)
            ticker_bench = '^GSPC'
        elif benchmark_sel == "NASDAQ":
            df_bench = fetch_market_data(['^IXIC'], data_inicio, adj_close=True)
            ticker_bench = '^IXIC'
        elif benchmark_sel == "SMLL (Small Caps)":
            df_bench = fetch_market_data(['SMLL.SA'], data_inicio, adj_close=True)
            ticker_bench = 'SMLL.SA'
        elif benchmark_sel == "Ouro":
            df_bench = fetch_market_data(['GC=F'], data_inicio, adj_close=True)
            ticker_bench = 'GC=F'
        else:
            df_bench = pd.DataFrame() 
            ticker_bench = benchmark_sel 
            
        idx_mestre = df_bench.dropna().index if not df_bench.empty else pd.Index([])
        if idx_mestre.empty and not df_rv_com.empty: idx_mestre = df_rv_com.dropna().index
            
        ret_ativos_com = pd.DataFrame(index=idx_mestre)
        ret_ativos_sem = pd.DataFrame(index=idx_mestre)
        tickers_validos = []
        
        if not df_rv_com.empty:
            for t in ativos_rv:
                if t in df_rv_com.columns:
                    rc = df_rv_com[t].reindex(idx_mestre).ffill().bfill().pct_change().fillna(0)
                    rs = df_rv_sem[t].reindex(idx_mestre).ffill().bfill().pct_change().fillna(0)
                    
                    data_c = pd.to_datetime(st.session_state.carteira[t]['data_compra'])
                    rc[rc.index < data_c] = 0.0
                    rs[rs.index < data_c] = 0.0
                    
                    ret_ativos_com[t] = rc
                    ret_ativos_sem[t] = rs
                    tickers_validos.append(t)
        
        for k, v in st.session_state.carteira.items():
            if v['tipo'] == 'RF':
                if v['indexador'] == "Prefixado": r_d = (1 + v['taxa'])**(1/252) - 1
                elif v['indexador'] == "CDI": r_d = (1 + (cdi_base * v['taxa']))**(1/252) - 1
                elif v['indexador'] == "IPCA+": r_d = ((1 + ipca_base) * (1 + v['taxa']))**(1/252) - 1
                
                ret_serie = pd.Series(r_d, index=idx_mestre)
                data_c = pd.to_datetime(v['data_compra'])
                ret_serie[ret_serie.index < data_c] = 0.0
                
                ret_ativos_com[k] = ret_serie
                ret_ativos_sem[k] = ret_serie
                tickers_validos.append(k)
        
        if benchmark_sel == "CDI/Selic (Manual)":
            ret_bench = pd.Series((1 + taxa_selic_manual)**(1/252) - 1, index=idx_mestre)
        elif benchmark_sel == "IPCA + 6%":
            ret_bench = pd.Series(((1 + ipca_base) * (1 + 0.06))**(1/252) - 1, index=idx_mestre)
        else:
            ret_bench = df_bench[ticker_bench].reindex(idx_mestre).ffill().pct_change().fillna(0) if ticker_bench in df_bench.columns else pd.Series(0, index=idx_mestre)
        
    if not tickers_validos:
        st.error("Erro na obtenção dos dados. Verifique a grafia dos tickers.")
    else:
        aportes_brutos = np.array([st.session_state.carteira[t]['aporte'] for t in tickers_validos])
        
        if modo_aporte == "Por Valor Financeiro (R$)":
            capital_inicial = aportes_brutos.sum() 
            pesos_norm = aportes_brutos / capital_inicial if capital_inicial > 0 else aportes_brutos * 0
        else:
            capital_inicial = capital_inicial_input
            pesos_norm = aportes_brutos / aportes_brutos.sum() if aportes_brutos.sum() > 0 else aportes_brutos * 0
        
        ret_port_com = (ret_ativos_com[tickers_validos] * pesos_norm).sum(axis=1)
        ret_port_sem = (ret_ativos_sem[tickers_validos] * pesos_norm).sum(axis=1)
        
        ret_portfolio_principal = ret_port_com if reinvestir else ret_port_sem
        ret_ativos_selecionados = ret_ativos_com if reinvestir else ret_ativos_sem

        # --- SEÇÃO 1: COMPOSIÇÃO ---
        st.header("🛒 Posições e Alocação")
        c_lista, c_grafico = st.columns([1, 1.5])
        with c_lista:
            for i, t in enumerate(tickers_validos):
                c1, c2, c3 = st.columns([3, 1, 1])
                dt_c = st.session_state.carteira[t]['data_compra'].strftime('%d/%m/%y')
                
                if modo_aporte == "Por Valor Financeiro (R$)":
                    valor_alocado = st.session_state.carteira[t]['aporte']
                    info_alocacao = f"{formatar_moeda(valor_alocado)} ({pesos_norm[i]:.1%})"
                else:
                    info_alocacao = f"{pesos_norm[i]:.1%}"
                    
                c1.markdown(f"**{t}** *(Início: {dt_c})*")
                c2.markdown(info_alocacao)
                if c3.button("❌", key=f"del_{t}"):
                    del st.session_state.carteira[t]
                    st.rerun()
                    
        with c_grafico:
            if len(tickers_validos) > 0:
                df_pizza = pd.DataFrame({'Ativo': tickers_validos, 'Peso': pesos_norm})
                fig = px.pie(df_pizza, values='Peso', names='Ativo', hole=0.5)
                fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', font=dict(color='#D4AF37'), margin=dict(t=0, b=0, l=0, r=0), showlegend=True)
                st.plotly_chart(fig, use_container_width=True)

        st.markdown("---")

        # --- SEÇÃO 2: MÉTRICAS GLOBAIS ---
        st.header("📊 Resumo de Desempenho")
        m = calcular_metricas(ret_portfolio_principal, ret_bench, cdi_base)
        
        st.subheader("Retorno & Eficiência", divider='gray')
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Rentabilidade Acumulada", f"{m[0]:.2%}")
        c2.metric("Alpha de Jensen", f"{m[7]:.2%}")
        c3.metric("Índice Sharpe", f"{m[2]:.2f}")
        c4.metric("Índice Sortino", f"{m[3]:.2f}")
        
        st.subheader("Risco & Mercado", divider='gray')
        c5, c6, c7, c8 = st.columns(4)
        c5.metric("Volatilidade Anual", f"{m[1]:.2%}")
        c6.metric("Max Drawdown", f"{m[4]:.2%}")
        c7.metric("VaR (95%)", f"{m[5]:.2%}")
        c8.metric(f"Beta vs {benchmark_sel}", f"{m[6]:.2f}")

        st.markdown("---")
        
        # --- SEÇÃO 3: SIMULAÇÃO FINANCEIRA DE DIVIDENDOS ---
        st.header("💸 Simulação Financeira (Efeito Dividendos)")
        acum_com = (1 + ret_port_com).prod() - 1
        acum_sem = (1 + ret_port_sem).prod() - 1
        
        cap_final_com = capital_inicial * (1 + acum_com)
        cap_final_sem = capital_inicial * (1 + acum_sem)
        ganho_div_reais = cap_final_com - cap_final_sem
        impacto_percentual = acum_com - acum_sem
        
        c_fin1, c_fin2, c_fin3, c_fin4 = st.columns(4)
        c_fin1.metric("Capital Inicial Total", formatar_moeda(capital_inicial))
        c_fin2.metric("Final (C/ Reinvestimento)", formatar_moeda(cap_final_com), f"{acum_com*100:.2f}%")
        c_fin3.metric("Final (S/ Reinvestimento)", formatar_moeda(cap_final_sem), f"{acum_sem*100:.2f}%")
        c_fin4.metric("Ganho Adicional (R$)", formatar_moeda(ganho_div_reais), f"+{impacto_percentual*100:.2f}%")

        st.markdown("---")
        
        # --- SEÇÃO 4: ABAS DE ANÁLISE ---
        tab_rent, tab_metrics, tab_candle = st.tabs(["📈 Rentabilidade Global", "⚙️ Estudo das Métricas", "🕯️ Candlestick (Ativos)"])
        
        with tab_rent:
            st.markdown(f"Comparativo de rentabilidade pura vs **{benchmark_sel}**.")
            df_grafico = pd.DataFrame(index=ret_portfolio_principal.index)
            df_grafico["LMF Asset (%)"] = ((1 + ret_portfolio_principal).cumprod() - 1) * 100
            df_grafico[f"{benchmark_sel} (%)"] = ((1 + ret_bench).cumprod() - 1) * 100
                
            fig_rent = px.line(df_grafico, color_discrete_sequence=["#D4AF37", "#555555"])
            fig_rent.update_layout(
                xaxis_title="", yaxis_title="Acumulado (%)",
                xaxis=dict(tickformat="%b %Y", dtick="M3"), 
                legend_title_text="", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color='#D4AF37')
            )
            st.plotly_chart(fig_rent, use_container_width=True)

        with tab_metrics:
            st.markdown("Analise o risco, o comportamento e a eficiência da sua carteira no detalhe.")
            
            # Novo menu principal de métricas
            metrica_sel = st.selectbox(
                "Selecione o Estudo:", 
                ["Fronteira Eficiente (Markowitz)", "Value at Risk (VaR)", "Drawdown Histórico", "Volatilidade Rolante", "Beta (Risco de Mercado)"]
            )
            
            df_roll = pd.DataFrame(index=ret_portfolio_principal.index)
            janela = 252 # Janela padrão anual para gráficos rolantes
            
            # --- FRONTEIRA EFICIENTE ---
            if metrica_sel == "Fronteira Eficiente (Markowitz)":
                ativos_rv_validos = [t for t in tickers_validos if st.session_state.carteira[t]['tipo'] == 'RV']
                
                if len(ativos_rv_validos) < 2:
                    st.warning("Adicione pelo menos 2 ativos de Renda Variável para simular a Fronteira Eficiente.")
                else:
                    st.markdown("Simulação de **5.000 carteiras aleatórias** usando os ativos de Renda Variável atuais para encontrar o portfólio de **Máximo Índice Sharpe**.")
                    
                    with st.spinner("Simulando portfólios..."):
                        # Matemática do Monte Carlo
                        ret_medios = ret_ativos_selecionados[ativos_rv_validos].mean() * 252
                        cov_mat = ret_ativos_selecionados[ativos_rv_validos].cov() * 252
                        
                        num_portfolios = 5000
                        resultados = np.zeros((3, num_portfolios))
                        
                        for i in range(num_portfolios):
                            pesos_simulados = np.random.random(len(ativos_rv_validos))
                            pesos_simulados /= np.sum(pesos_simulados)
                            
                            ret_esp = np.sum(pesos_simulados * ret_medios)
                            vol_esp = np.sqrt(np.dot(pesos_simulados.T, np.dot(cov_mat, pesos_simulados)))
                            
                            resultados[0,i] = ret_esp
                            resultados[1,i] = vol_esp
                            # Sharpe Ratio considerando a taxa livre de risco configurada na lateral
                            resultados[2,i] = (ret_esp - cdi_base) / vol_esp if vol_esp > 0 else 0
                            
                        # Preparar dados para o Plotly
                        df_ef = pd.DataFrame(resultados.T, columns=['Retorno', 'Volatilidade', 'Sharpe'])
                        idx_max_sharpe = df_ef['Sharpe'].idxmax()
                        max_sharpe_point = df_ef.iloc[idx_max_sharpe]
                        
                        # Gráfico Scatter Plot
                        fig_ef = px.scatter(
                            df_ef, x='Volatilidade', y='Retorno', color='Sharpe',
                            color_continuous_scale='Viridis', opacity=0.8
                        )
                        # Marcador para o Máximo Sharpe (Estrela Vermelha)
                        fig_ef.add_trace(go.Scatter(
                            x=[max_sharpe_point['Volatilidade']], y=[max_sharpe_point['Retorno']],
                            mode='markers', marker=dict(color='red', size=15, symbol='star'),
                            name='Máximo Sharpe'
                        ))
                        
                        fig_ef.update_layout(
                            xaxis_title="Volatilidade Anualizada", yaxis_title="Retorno Anualizado Esperado",
                            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color='#D4AF37')
                        )
                        st.plotly_chart(fig_ef, use_container_width=True)

            # --- VALUE AT RISK (VaR) ---
            elif metrica_sel == "Value at Risk (VaR)":
                # Submenu condicional apenas para o VaR
                tipo_var = st.radio("Selecione a visualização do VaR:", ["Histograma de Retornos (Estático)", "VaR Histórico Rolante (Janela 252d)"], horizontal=True)
                
                if tipo_var == "Histograma de Retornos (Estático)":
                    var_5 = np.percentile(ret_portfolio_principal, 5)
                    fig_var = px.histogram(ret_portfolio_principal, nbins=50, title="Distribuição de Retornos Diários")
                    # Linha vertical indicando o VaR
                    fig_var.add_vline(x=var_5, line_dash="dash", line_color="red", annotation_text=f"VaR 5% = {var_5:.4f}")
                    fig_var.update_layout(
                        xaxis_title="Retorno Diário", yaxis_title="Densidade", showlegend=False,
                        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color='#D4AF37')
                    )
                    st.plotly_chart(fig_var, use_container_width=True)
                    
                else:
                    df_roll["VaR 5% (Carteira)"] = ret_portfolio_principal.rolling(janela).quantile(0.05)
                    fig_var = px.line(df_roll.dropna(), color_discrete_sequence=["#D4AF37"])
                    fig_var.update_layout(
                        xaxis_title="", yaxis_title="VaR Diário (Quantil)", xaxis=dict(tickformat="%b %Y", dtick="M3"),
                        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color='#D4AF37')
                    )
                    st.plotly_chart(fig_var, use_container_width=True)

            # --- DRAWDOWN HISTÓRICO ---
            elif metrica_sel == "Drawdown Histórico":
                roll_cum = (1 + ret_portfolio_principal).cumprod()
                roll_max = roll_cum.cummax() # Usando cummax para pegar a máxima histórica total
                df_roll["Drawdown Carteira (%)"] = ((roll_cum / roll_max) - 1) * 100
                
                fig_dd = px.line(df_roll.dropna(), color_discrete_sequence=["#D4AF37"])
                fig_dd.update_layout(
                    xaxis_title="", yaxis_title="Queda a partir do Topo (%)", xaxis=dict(tickformat="%b %Y", dtick="M3"), 
                    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color='#D4AF37')
                )
                # Opcional: Pintar a área debaixo da linha de Drawdown para ficar igual à sua imagem
                fig_dd.update_traces(fill='tozeroy') 
                st.plotly_chart(fig_dd, use_container_width=True)

            # --- VOLATILIDADE ROLANTE ---
            elif metrica_sel == "Volatilidade Rolante":
                df_roll["Vol. Carteira (%)"] = ret_portfolio_principal.rolling(janela).std() * np.sqrt(252) * 100
                df_roll[f"Vol. {benchmark_sel} (%)"] = ret_bench.rolling(janela).std() * np.sqrt(252) * 100
                
                fig_vol = px.line(df_roll.dropna(), color_discrete_sequence=["#D4AF37", "#555555"])
                fig_vol.update_layout(
                    xaxis_title="", yaxis_title="Volatilidade Anualizada (%)", xaxis=dict(tickformat="%b %Y", dtick="M3"),
                    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color='#D4AF37'), legend_title_text=""
                )
                st.plotly_chart(fig_vol, use_container_width=True)

            # --- BETA (RISCO DE MERCADO) ---
            elif metrica_sel == "Beta (Risco de Mercado)":
                cov = ret_portfolio_principal.rolling(janela).cov(ret_bench)
                var = ret_bench.rolling(janela).var()
                df_roll["Beta Histórico"] = cov / var
                
                fig_beta = px.line(df_roll.dropna(), color_discrete_sequence=["#D4AF37"])
                fig_beta.update_layout(
                    xaxis_title="", yaxis_title=f"Beta vs {benchmark_sel}", xaxis=dict(tickformat="%b %Y", dtick="M3"),
                    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color='#D4AF37'), legend_title_text=""
                )
                st.plotly_chart(fig_beta, use_container_width=True)
            
        with tab_candle:
            st.markdown("Visualização de preços OHLC para ativos individuais da carteira.")
            ativos_na_carteira_rv = [t for t in tickers_validos if st.session_state.carteira[t]['tipo'] == 'RV']
            
            if not ativos_na_carteira_rv:
                st.warning("Adicione ativos de Renda Variável para visualizar o Candlestick.")
            else:
                ativo_candle = st.selectbox("Selecione o Ativo:", ativos_na_carteira_rv)
                try:
                    df_ohlc = yf.download(ativo_candle, start=data_inicio, progress=False)
                    if isinstance(df_ohlc.columns, pd.MultiIndex): df_ohlc.columns = df_ohlc.columns.get_level_values(0)
                    
                    fig_candle = go.Figure(data=[go.Candlestick(
                        x=df_ohlc.index, open=df_ohlc['Open'], high=df_ohlc['High'], low=df_ohlc['Low'], close=df_ohlc['Close'],
                        increasing_line_color='#D4AF37', decreasing_line_color='#555555'
                    )])
                    fig_candle.update_layout(
                        title=f"{ativo_candle}", xaxis_title="", yaxis_title="Preço (R$)",
                        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color='#D4AF37'), xaxis_rangeslider_visible=False
                    )
                    st.plotly_chart(fig_candle, use_container_width=True)
                except:
                    st.error("Erro ao carregar dados OHLC para este ativo.")

        st.markdown("---")
        
        # --- BOTÃO DE IMPRESSÃO / PDF ---
        c_espaco, c_botao, c_espaco2 = st.columns([1, 2, 1])
        with c_botao:
            if st.button("🖨️ Salvar Relatório em PDF", use_container_width=True):
                components.html("<script>window.parent.print();</script>", height=0)

        st.markdown(f"<div style='text-align:right; color:#D4AF37; opacity:0.6; margin-top: 20px;'>Desenvolvido por Bernardo V.</div>", unsafe_allow_html=True)