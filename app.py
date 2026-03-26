import streamlit as st
import streamlit.components.v1 as components
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import json
import base64

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
if 'carteira_comparacao' not in st.session_state:
    st.session_state['carteira_comparacao'] = {}

def formatar_moeda(valor):
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def exportar_codigo_carteira(carteira_dict):
    if not carteira_dict: return ""
    cart_copy = {}
    for k, v in carteira_dict.items():
        v_copy = v.copy()
        if isinstance(v_copy.get('data_compra'), datetime):
            v_copy['data_compra'] = v_copy['data_compra'].strftime('%Y-%m-%d')
        else:
            v_copy['data_compra'] = str(v_copy['data_compra'])
        cart_copy[k] = v_copy
    json_str = json.dumps(cart_copy)
    return base64.b64encode(json_str.encode('utf-8')).decode('utf-8')

def importar_codigo_carteira(codigo_b64):
    try:
        json_str = base64.b64decode(codigo_b64.encode('utf-8')).decode('utf-8')
        cart = json.loads(json_str)
        for k, v in cart.items():
            v['data_compra'] = datetime.strptime(v['data_compra'], '%Y-%m-%d').date()
        return cart
    except:
        return None

# --- 2. MOTOR DE DADOS ATUALIZADO ---
@st.cache_data(ttl=600)
def fetch_market_data(tickers, start, adj_close=True):
    if not tickers: return pd.DataFrame()
    try:
        df = yf.download(tickers, start=start, progress=False, auto_adjust=adj_close)
        if isinstance(df.columns, pd.MultiIndex): data = df['Close']
        elif 'Close' in df.columns: data = df['Close']
        else: data = df
        if isinstance(data, pd.Series): data = data.to_frame(name=tickers[0])
        return data.ffill().bfill()
    except Exception: 
        return pd.DataFrame()

@st.cache_data(ttl=3600)
def fetch_br_indicators(codigo, start_date):
    try:
        url = f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados?formato=json&dataInicial={start_date.strftime('%d/%m/%Y')}&dataFinal={datetime.today().strftime('%d/%m/%Y')}"
        df = pd.read_json(url)
        df['data'] = pd.to_datetime(df['data'], format='%d/%m/%Y')
        df.set_index('data', inplace=True)
        return df['valor'] / 100
    except Exception:
        return pd.Series(dtype=float)

def calcular_metricas(ret_p, ret_m, cdi_s):
    if ret_p.empty or ret_m.empty: return [0]*8
    df = pd.concat([ret_p, ret_m, cdi_s], axis=1).dropna()
    if df.empty: return [0]*8
    rp, rm, rf = df.iloc[:,0], df.iloc[:,1], df.iloc[:,2]
    ret_acum = (1 + rp).prod() - 1
    vol = rp.std() * np.sqrt(252)
    excesso_diario = rp - rf
    excesso_anualizado = excesso_diario.mean() * 252
    sharpe = excesso_anualizado / vol if vol > 0 else 0
    neg = excesso_diario[excesso_diario < 0]
    sortino = excesso_anualizado / (neg.std() * np.sqrt(252)) if not neg.empty and neg.std() > 0 else 0
    cum = (1 + rp).cumprod()
    dd = (cum / cum.cummax() - 1).min()
    var95 = np.percentile(rp, 5) if not rp.empty else 0
    var_m = np.var(rm)
    beta = np.cov(rp, rm)[0,1] / var_m if var_m > 0 else 0
    ret_p_anual = (1 + ret_acum)**(252/len(rp)) - 1
    ret_m_anual = (1 + (1+rm).prod()-1)**(252/len(rm)) - 1
    rf_anual = (1 + (1+rf).prod()-1)**(252/len(rf)) - 1
    alpha = ret_p_anual - (rf_anual + beta * (ret_m_anual - rf_anual))
    return ret_acum, vol, sharpe, sortino, dd, var95, beta, alpha

def processar_carteira(dict_carteira, df_rv_c, df_rv_s, cdi_al, ipca_al, idx_m, reinvest_flag):
    if not dict_carteira: return pd.Series(0, index=idx_m), pd.Series(0, index=idx_m)
    ret_ativos_c = pd.DataFrame(index=idx_m)
    ret_ativos_s = pd.DataFrame(index=idx_m)
    tickers_v = []
    for k, v in dict_carteira.items():
        data_c = pd.to_datetime(v['data_compra'])
        if v['tipo'] == 'RV':
            if k in df_rv_c.columns:
                rc = df_rv_c[k].reindex(idx_m).ffill().bfill().pct_change().fillna(0)
                rs = df_rv_s[k].reindex(idx_m).ffill().bfill().pct_change().fillna(0)
                rc[rc.index < data_c] = 0.0
                rs[rs.index < data_c] = 0.0
                ret_ativos_c[k] = rc
                ret_ativos_s[k] = rs
                tickers_v.append(k)
        elif v['tipo'] == 'RF':
            if v['indexador'] == "Prefixado": r_d = (1 + v['taxa'])**(1/252) - 1
            elif v['indexador'] == "CDI": r_d = cdi_al * v['taxa']
            elif v['indexador'] == "IPCA+": r_d = (1 + ipca_al) * (1 + v['taxa'])**(1/252) - 1
            rs_serie = pd.Series(r_d, index=idx_m)
            rs_serie[rs_serie.index < data_c] = 0.0
            ret_ativos_c[k] = rs_serie
            ret_ativos_s[k] = rs_serie
            tickers_v.append(k)
    
    if not tickers_v: return pd.Series(0, index=idx_m), pd.Series(0, index=idx_m)
    aportes = np.array([dict_carteira[t]['aporte'] for t in tickers_v])
    pesos = aportes / aportes.sum() if aportes.sum() > 0 else aportes * 0
    ret_com = (ret_ativos_c[tickers_v] * pesos).sum(axis=1)
    ret_sem = (ret_ativos_s[tickers_v] * pesos).sum(axis=1)
    return ret_com, ret_sem

# --- 3. BARRA LATERAL ---
with st.sidebar:
    st.header("⚙️ Configuração Principal")
    modo_aporte = st.radio("Método de Alocação", ["Por Peso (%)", "Por Valor Financeiro (R$)"], horizontal=True)
    
    col_cap, col_dt = st.columns(2)
    if modo_aporte == "Por Peso (%)":
        capital_inicial_input = col_cap.number_input("Capital Total (R$)", min_value=100.0, value=10000.0, step=1000.0)
    else:
        capital_inicial_input = 0.0 
        col_cap.text_input("Capital Total (R$)", value="Soma Automática", disabled=True)
        
    data_inicio = col_dt.date_input("Data Inicial", value=datetime(2012,1,1), min_value=datetime(1900,1,1), max_value=datetime.today())
    
    with st.expander("📊 Parâmetros de Mercado & Visualização", expanded=False):
        benchmark_sel = st.selectbox("Benchmark", [
            "Ibovespa", "IFIX", "S&P 500", "NASDAQ", "SMLL (Small Caps)", "Ouro", "IPCA + Taxa", "CDI (Percentual)", "Selic"
        ])
        
        taxa_ipca_bench, taxa_cdi_bench = 0.06, 1.0
        if benchmark_sel == "IPCA + Taxa":
            taxa_ipca_bench = st.number_input("Taxa Fixa do IPCA+ (%)", value=6.0, step=0.1) / 100
        elif benchmark_sel == "CDI (Percentual)":
            taxa_cdi_bench = st.number_input("Percentual do CDI (%)", value=100.0, step=1.0) / 100
            
        c_taxa1, c_taxa2 = st.columns(2)
        cdi_base = c_taxa1.number_input("CDI Base (%)", value=10.5, step=0.1) / 100
        ipca_base = c_taxa2.number_input("IPCA Base (%)", value=4.5, step=0.1) / 100
        reinvestir = st.checkbox("Reinvestir Dividendos (Gráficos)", value=True)
        
    with st.expander("🔗 Compartilhamento de Carteiras", expanded=False):
        st.markdown("<span style='font-size:0.85em; opacity:0.8;'>Copie o código abaixo para compartilhar sua alocação:</span>", unsafe_allow_html=True)
        codigo_export = exportar_codigo_carteira(st.session_state.carteira)
        st.code(codigo_export if codigo_export else "Adicione ativos para gerar o código.")
        
        st.markdown("<hr style='margin:10px 0;'>", unsafe_allow_html=True)
        codigo_import = st.text_input("Código de Comparação:", placeholder="Cole o código do colega aqui...")
        if st.button("Carregar Comparação", use_container_width=True):
            cart_importada = importar_codigo_carteira(codigo_import)
            if cart_importada:
                st.session_state.carteira_comparacao = cart_importada
                st.success("Carteira de comparação carregada!")
                st.rerun()
            else:
                st.error("Código inválido.")
        if st.session_state.carteira_comparacao:
            if st.button("Limpar Comparação", use_container_width=True):
                st.session_state.carteira_comparacao = {}
                st.rerun()
    
    st.markdown("---")
    st.subheader("➕ Adicionar Ativos")
    classe_ativo = st.radio("Classe do Ativo", ["Renda Variável", "Renda Fixa"], horizontal=True)
    
    if classe_ativo == "Renda Variável":
        c_rv1, c_rv2 = st.columns(2)
        ticker = c_rv1.text_input("Ticker", help="Ex: PETR4.SA").upper().strip()
        aporte_val = c_rv2.number_input("Peso/Valor", min_value=1.0, value=10.0 if modo_aporte=="Por Peso (%)" else 1000.0)
        comprado_inicio_rv = st.checkbox("Desde o Início?", value=True, key="chk_rv")
        data_compra_rv = data_inicio if comprado_inicio_rv else st.date_input("Comprado em", value=data_inicio, min_value=data_inicio, max_value=datetime.today(), key="dt_rv")
        if st.button("Inserir Renda Variável") and ticker:
            st.session_state.carteira[ticker] = {'tipo': 'RV', 'aporte': aporte_val, 'data_compra': data_compra_rv}
            st.rerun()
    else:
        nome_rf = st.text_input("Nome do Título").strip()
        c_rf1, c_rf2, c_rf3 = st.columns([1.5, 1, 1])
        tipo_rf = c_rf1.selectbox("Indexador", ["Prefixado", "CDI", "IPCA+"])
        if tipo_rf == "CDI": val_def = 110.0
        elif tipo_rf == "IPCA+": val_def = 6.0
        else: val_def = 10.0
        taxa = c_rf2.number_input("Taxa (%)", value=val_def, step=0.1) / 100
        aporte_val_rf = c_rf3.number_input("Peso/Valor", min_value=1.0, value=10.0 if modo_aporte=="Por Peso (%)" else 1000.0)
        comprado_inicio_rf = st.checkbox("Desde o Início?", value=True, key="chk_rf")
        data_compra_rf = data_inicio if comprado_inicio_rf else st.date_input("Aplicado em", value=data_inicio, min_value=data_inicio, max_value=datetime.today(), key="dt_rf")
        if st.button("Inserir Renda Fixa") and nome_rf:
            st.session_state.carteira[nome_rf] = {'tipo': 'RF', 'indexador': tipo_rf, 'taxa': taxa, 'aporte': aporte_val_rf, 'data_compra': data_compra_rf}
            st.rerun()
    if st.button("🗑️ Limpar Carteira Principal"):
        st.session_state.carteira = {}
        st.rerun()

# --- 4. TELA PRINCIPAL ---
st.title("🏛️ LMF - ASSET")

if not st.session_state.carteira:
    st.info("👋 Configure os parâmetros na barra lateral e adicione ativos para montar sua estratégia.")
else:
    with st.spinner("Sincronizando Mercado Global e Processando Modelagens..."):
        # Puxa ativos da carteira principal e da comparação em lote
        ativos_rv_principal = [k for k, v in st.session_state.carteira.items() if v['tipo'] == 'RV']
        ativos_rv_comp = [k for k, v in st.session_state.carteira_comparacao.items() if v['tipo'] == 'RV']
        todos_ativos_rv = list(set(ativos_rv_principal + ativos_rv_comp))
        
        df_rv_com = fetch_market_data(todos_ativos_rv, data_inicio, adj_close=True)
        df_rv_sem = fetch_market_data(todos_ativos_rv, data_inicio, adj_close=False) 
        
        if benchmark_sel == "Ibovespa": df_bench, ticker_bench = fetch_market_data(['^BVSP'], data_inicio, adj_close=True), '^BVSP'
        elif benchmark_sel == "IFIX": df_bench, ticker_bench = fetch_market_data(['XFIX11.SA'], data_inicio, adj_close=True), 'XFIX11.SA'
        elif benchmark_sel == "S&P 500": df_bench, ticker_bench = fetch_market_data(['^GSPC'], data_inicio, adj_close=True), '^GSPC'
        elif benchmark_sel == "NASDAQ": df_bench, ticker_bench = fetch_market_data(['^IXIC'], data_inicio, adj_close=True), '^IXIC'
        elif benchmark_sel == "SMLL (Small Caps)": df_bench, ticker_bench = fetch_market_data(['SMAL11.SA'], data_inicio, adj_close=True), 'SMAL11.SA'
        elif benchmark_sel == "Ouro": df_bench, ticker_bench = fetch_market_data(['GC=F'], data_inicio, adj_close=True), 'GC=F'
        else: df_bench, ticker_bench = pd.DataFrame(), benchmark_sel 
            
        idx_mestre = df_bench.dropna().index if not df_bench.empty else pd.Index([])
        if idx_mestre.empty and not df_rv_com.empty: idx_mestre = df_rv_com.dropna().index
        if idx_mestre.empty: idx_mestre = pd.bdate_range(start=data_inicio, end=datetime.today())
            
        cdi_series = fetch_br_indicators(12, data_inicio)
        selic_series = fetch_br_indicators(11, data_inicio)
        ipca_series = fetch_br_indicators(433, data_inicio)
        
        cdi_aligned = cdi_series.reindex(idx_mestre).fillna(0) if not cdi_series.empty else pd.Series((1 + 0.105)**(1/252) - 1, index=idx_mestre)
        selic_aligned = selic_series.reindex(idx_mestre).fillna(0) if not selic_series.empty else pd.Series((1 + 0.105)**(1/252) - 1, index=idx_mestre)
        
        if ipca_series.empty: ipca_daily_aligned = pd.Series((1 + 0.045)**(1/252) - 1, index=idx_mestre)
        else:
            ipca_daily_val = (1 + ipca_series)**(1/21) - 1
            all_days = pd.date_range(start=ipca_daily_val.index.min(), end=datetime.today())
            ipca_daily_aligned = ipca_daily_val.reindex(all_days).ffill().reindex(idx_mestre).fillna(0)

        # Benchmark Condicional
        if benchmark_sel == "CDI (Percentual)": ret_bench = cdi_aligned * taxa_cdi_bench
        elif benchmark_sel == "Selic": ret_bench = selic_aligned
        elif benchmark_sel == "IPCA + Taxa": ret_bench = (1 + ipca_daily_aligned) * (1 + taxa_ipca_bench)**(1/252) - 1
        else: ret_bench = df_bench[ticker_bench].reindex(idx_mestre).ffill().pct_change().fillna(0) if not df_bench.empty else pd.Series(0, index=idx_mestre)

        # Processamento Principal
        ret_port_com, ret_port_sem = processar_carteira(st.session_state.carteira, df_rv_com, df_rv_sem, cdi_aligned, ipca_daily_aligned, idx_mestre, reinvestir)
        ret_portfolio_principal = ret_port_com if reinvestir else ret_port_sem
        
        # Processamento Comparação
        if st.session_state.carteira_comparacao:
            ret_comp_com, ret_comp_sem = processar_carteira(st.session_state.carteira_comparacao, df_rv_com, df_rv_sem, cdi_aligned, ipca_daily_aligned, idx_mestre, reinvestir)
            ret_portfolio_comparacao = ret_comp_com if reinvestir else ret_comp_sem

        # Cálculo Inicial do Principal
        aportes_brutos = np.array([v['aporte'] for v in st.session_state.carteira.values()])
        if modo_aporte == "Por Valor Financeiro (R$)": capital_inicial = aportes_brutos.sum() 
        else: capital_inicial = capital_inicial_input
        pesos_norm = aportes_brutos / aportes_brutos.sum() if aportes_brutos.sum() > 0 else aportes_brutos * 0

        # --- SEÇÃO 1: COMPOSIÇÃO ---
        st.header("🛒 Posições e Alocação")
        c_lista, c_grafico = st.columns([1, 1.5])
        with c_lista:
            for i, (t, config) in enumerate(st.session_state.carteira.items()):
                c1, c2, c3 = st.columns([3, 1, 1])
                dt_c = config['data_compra'].strftime('%d/%m/%y')
                info_alocacao = f"{formatar_moeda(config['aporte'])} ({pesos_norm[i]:.1%})" if modo_aporte == "Por Valor Financeiro (R$)" else f"{pesos_norm[i]:.1%}"
                c1.markdown(f"**{t}** *(Início: {dt_c})*")
                c2.markdown(info_alocacao)
                if c3.button("❌", key=f"del_{t}"):
                    del st.session_state.carteira[t]
                    st.rerun()
                    
        with c_grafico:
            if len(st.session_state.carteira) > 0:
                df_pizza = pd.DataFrame({'Ativo': list(st.session_state.carteira.keys()), 'Peso': pesos_norm})
                fig = px.pie(df_pizza, values='Peso', names='Ativo', hole=0.5)
                fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', font=dict(color='#D4AF37'), margin=dict(t=0, b=0, l=0, r=0))
                st.plotly_chart(fig, use_container_width=True)

        st.markdown("---")

        # --- SEÇÃO 2: MÉTRICAS GLOBAIS ---
        st.header("📊 Resumo de Desempenho")
        m = calcular_metricas(ret_portfolio_principal, ret_bench, cdi_aligned)
        
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
        
        # --- SEÇÃO 3: SIMULAÇÃO FINANCEIRA ---
        st.header("💸 Simulação Financeira")
        acum_com = (1 + ret_port_com).prod() - 1
        acum_sem = (1 + ret_port_sem).prod() - 1
        cap_final_com = capital_inicial * (1 + acum_com)
        cap_final_sem = capital_inicial * (1 + acum_sem)
        ganho_div_reais = cap_final_com - cap_final_sem
        
        c_fin1, c_fin2, c_fin3, c_fin4 = st.columns(4)
        c_fin1.metric("Capital Inicial Total", formatar_moeda(capital_inicial))
        c_fin2.metric("Final (C/ Reinvestimento)", formatar_moeda(cap_final_com), f"{acum_com*100:.2f}%")
        c_fin3.metric("Final (S/ Reinvestimento)", formatar_moeda(cap_final_sem), f"{acum_sem*100:.2f}%")
        c_fin4.metric("Ganho Adicional (R$)", formatar_moeda(ganho_div_reais), f"+{(acum_com - acum_sem)*100:.2f}%")

        st.markdown("---")
        
        # --- SEÇÃO 4: ABAS DE ANÁLISE ---
        tab_rent, tab_metrics, tab_candle = st.tabs(["📈 Rentabilidade Global", "⚙️ Estudo das Métricas", "🕯️ Candlestick (Ativos)"])
        
        with tab_rent:
            st.markdown(f"Comparativo de rentabilidade pura vs **{benchmark_sel}**.")
            df_grafico = pd.DataFrame(index=ret_portfolio_principal.index)
            df_grafico["Sua Carteira (%)"] = ((1 + ret_portfolio_principal).cumprod() - 1) * 100
            
            if st.session_state.carteira_comparacao:
                df_grafico["Carteira Comparação (%)"] = ((1 + ret_portfolio_comparacao).cumprod() - 1) * 100
                
            df_grafico[f"{benchmark_sel} (%)"] = ((1 + ret_bench.reindex(idx_mestre).fillna(0)).cumprod() - 1) * 100
            
            fig_rent = px.line(df_grafico, color_discrete_sequence=["#D4AF37", "#00BFFF", "#555555"])
            fig_rent.update_layout(
                xaxis_title="", yaxis_title="Acumulado (%)",
                xaxis=dict(tickformat="%b %Y", dtick="M3"), 
                legend_title_text="", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color='#D4AF37')
            )
            st.plotly_chart(fig_rent, use_container_width=True)

        with tab_metrics:
            metrica_sel = st.selectbox("Selecione o Estudo:", ["Value at Risk (VaR)", "Drawdown Histórico", "Volatilidade Rolante", "Beta (Risco de Mercado)"])
            janela = 252 
            df_roll = pd.DataFrame(index=ret_portfolio_principal.index)
            
            if metrica_sel == "Value at Risk (VaR)":
                df_roll["VaR 5% (Sua Carteira)"] = ret_portfolio_principal.rolling(janela).quantile(0.05)
                if st.session_state.carteira_comparacao:
                    df_roll["VaR 5% (Comparação)"] = ret_portfolio_comparacao.rolling(janela).quantile(0.05)
                fig_var = px.line(df_roll.dropna(), color_discrete_sequence=["#D4AF37", "#00BFFF"])
                fig_var.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color='#D4AF37'))
                st.plotly_chart(fig_var, use_container_width=True)

            elif metrica_sel == "Drawdown Histórico":
                roll_cum = (1 + ret_portfolio_principal).cumprod()
                df_roll["Sua Carteira (%)"] = ((roll_cum / roll_cum.cummax()) - 1) * 100
                if st.session_state.carteira_comparacao:
                    roll_cum_comp = (1 + ret_portfolio_comparacao).cumprod()
                    df_roll["Comparação (%)"] = ((roll_cum_comp / roll_cum_comp.cummax()) - 1) * 100
                
                fig_dd = px.line(df_roll.dropna(), color_discrete_sequence=["#D4AF37", "#00BFFF"])
                fig_dd.update_traces(fill='tozeroy') 
                fig_dd.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color='#D4AF37'))
                st.plotly_chart(fig_dd, use_container_width=True)

            elif metrica_sel == "Volatilidade Rolante":
                df_roll["Sua Carteira (%)"] = ret_portfolio_principal.rolling(janela).std() * np.sqrt(252) * 100
                if st.session_state.carteira_comparacao:
                    df_roll["Comparação (%)"] = ret_portfolio_comparacao.rolling(janela).std() * np.sqrt(252) * 100
                df_roll[f"Bench {benchmark_sel} (%)"] = ret_bench.rolling(janela).std() * np.sqrt(252) * 100
                fig_vol = px.line(df_roll.dropna(), color_discrete_sequence=["#D4AF37", "#00BFFF", "#555555"])
                fig_vol.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color='#D4AF37'))
                st.plotly_chart(fig_vol, use_container_width=True)

            elif metrica_sel == "Beta (Risco de Mercado)":
                df_roll["Sua Carteira"] = ret_portfolio_principal.rolling(janela).cov(ret_bench) / ret_bench.rolling(janela).var()
                if st.session_state.carteira_comparacao:
                    df_roll["Comparação"] = ret_portfolio_comparacao.rolling(janela).cov(ret_bench) / ret_bench.rolling(janela).var()
                fig_beta = px.line(df_roll.dropna(), color_discrete_sequence=["#D4AF37", "#00BFFF"])
                fig_beta.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color='#D4AF37'))
                st.plotly_chart(fig_beta, use_container_width=True)

        with tab_candle:
            ativo_candle = st.selectbox("Ativo:", [t for t in ativos_rv_principal])
            if ativo_candle:
                df_ohlc = yf.download(ativo_candle, start=data_inicio, progress=False)
                fig_c = go.Figure(data=[go.Candlestick(x=df_ohlc.index, open=df_ohlc['Open'], high=df_ohlc['High'], low=df_ohlc['Low'], close=df_ohlc['Close'])])
                fig_c.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color='#D4AF37'))
                st.plotly_chart(fig_c, use_container_width=True)

        if st.button("🖨️ Salvar Relatório em PDF", use_container_width=True):
            components.html("<script>window.parent.print();</script>", height=0)

        st.markdown(f"<div style='text-align:right; color:#D4AF37; opacity:0.6'>Desenvolvido por Bernardo V.</div>", unsafe_allow_html=True)
