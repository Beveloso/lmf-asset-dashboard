import streamlit as st
import streamlit.components.v1 as components
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import json
import base64import streamlit as st
import streamlit.components.v1 as components
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import json
import base64
import re

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
    table { width: 100%; text-align: center; border-collapse: collapse; margin-bottom: 20px; }
    th { border-bottom: 2px solid #D4AF37; color: #D4AF37; padding: 10px; }
    td { border-bottom: 1px solid #333; padding: 10px; }
    </style>
""", unsafe_allow_html=True)

# --- FUNÇÕES DE IMPORTAÇÃO E FORMATAÇÃO ---
def formatar_moeda(valor):
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def formatar_percentual(valor):
    sinal = "+" if valor >= 0 else ""
    return f"{sinal}{valor*100:.2f}%"

def formatar_float(valor):
    if valor is None or pd.isna(valor): return "N/A"
    return f"{float(valor):.2f}"

def formatar_pct_api(valor):
    if valor is None or pd.isna(valor): return "N/A"
    return f"{float(valor)*100:.2f}%"

def formatar_abrev(valor):
    if valor is None or pd.isna(valor): return "N/A"
    try:
        val = float(valor)
        if val >= 1e9: return f"{val/1e9:.2f} B"
        if val >= 1e6: return f"{val/1e6:.2f} M"
        return f"{val:.2f}"
    except: return "N/A"

def exportar_codigo_carteira(carteira_dict):
    if not carteira_dict: return ""
    cart_copy = {}
    for k, v in carteira_dict.items():
        v_copy = v.copy()
        if isinstance(v_copy.get('data_compra'), datetime) or hasattr(v_copy.get('data_compra'), 'strftime'):
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

# --- INICIALIZAÇÃO DE ESTADOS ---
if 'started' not in st.session_state:
    st.session_state['started'] = False
    st.session_state['carteira_alterada'] = False
    st.session_state['carteira'] = {}
    st.session_state['carteira_comparacao'] = {}

OPCOES_SETORES = [
    "Não Informado", "Consumo Cíclico", "Consumo não Cíclico", "Utilidade Pública",
    "Bens Industriais", "Materiais Básicos", "Financeiro e Outros",
    "Tecnologia da Informação", "Saúde", "Petróleo, Gás e Biocombustíveis", "Comunicações"
]

# --- TELA DE "SPLASH SCREEN" (LOGIN / NOVO TRABALHO) ---
if not st.session_state['started']:
    st.title("🏛️ LMF - ASSET")
    st.markdown("### Bem-vindo ao Sistema de Gestão de Portfólio")
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 📄 Iniciar Nova Carteira")
        st.info("Inicie uma nova análise utilizando nossa carteira modelo pré-definida e altere conforme desejar.")
        if st.button("Criar Nova Carteira", use_container_width=True):
            st.session_state['started'] = True
            st.session_state['carteira_alterada'] = False
            dt_padrao = datetime(2012, 1, 1).date()
            st.session_state['carteira'] = {
                'QQQ': {'tipo': 'RV', 'aporte': 10.0, 'data_compra': dt_padrao, 'setor': 'Tecnologia da Informação'},
                'JEPI': {'tipo': 'RV', 'aporte': 10.0, 'data_compra': dt_padrao, 'setor': 'Não Informado'},
                'PETR4.SA': {'tipo': 'RV', 'aporte': 10.0, 'data_compra': dt_padrao, 'setor': 'Petróleo, Gás e Biocombustíveis'},
                'IVV': {'tipo': 'RV', 'aporte': 10.0, 'data_compra': dt_padrao, 'setor': 'Não Informado'},
                'CDI 100%': {'tipo': 'RF', 'indexador': 'CDI', 'taxa': 1.0, 'aporte': 10.0, 'data_compra': dt_padrao},
                'IPCA+ 7%': {'tipo': 'RF', 'indexador': 'IPCA+', 'taxa': 0.07, 'aporte': 10.0, 'data_compra': dt_padrao},
                'VALE3.SA': {'tipo': 'RV', 'aporte': 10.0, 'data_compra': dt_padrao, 'setor': 'Materiais Básicos'},
                'BBDC4.SA': {'tipo': 'RV', 'aporte': 10.0, 'data_compra': dt_padrao, 'setor': 'Financeiro e Outros'},
                'BBSE3.SA': {'tipo': 'RV', 'aporte': 10.0, 'data_compra': dt_padrao, 'setor': 'Financeiro e Outros'},
                'BRSR6.SA': {'tipo': 'RV', 'aporte': 10.0, 'data_compra': dt_padrao, 'setor': 'Financeiro e Outros'}
            }
            st.rerun()
            
    with col2:
        st.markdown("#### 💾 Continuar Trabalho")
        st.success("Cole abaixo o código da carteira que você salvou anteriormente para restaurar todo o seu progresso.")
        codigo_salvo = st.text_input("Cole seu código de salvamento aqui:")
        if st.button("Carregar Trabalho", use_container_width=True):
            if codigo_salvo:
                cart_importada = importar_codigo_carteira(codigo_salvo)
                if cart_importada:
                    st.session_state['carteira'] = cart_importada
                    st.session_state['started'] = True
                    st.session_state['carteira_alterada'] = True 
                    st.rerun()
                else:
                    st.error("Código inválido. Verifique se copiou corretamente.")
            else:
                st.warning("Por favor, cole um código antes de continuar.")
                
    st.markdown(f"<br><br><div style='text-align:center; color:#D4AF37; opacity:0.6'>Idealizado por Bernardo V.</div>", unsafe_allow_html=True)
    st.stop() 

# --- 2. MOTOR DE DADOS OTIMIZADO E BLINDADO ---
@st.cache_data(ttl=600)
def fetch_market_data_both(tickers, start):
    if not tickers: return pd.DataFrame(), pd.DataFrame()
    try:
        df = yf.download(tickers, start=start, progress=False, auto_adjust=False)
        if df.empty: return pd.DataFrame(), pd.DataFrame()
        
        if isinstance(df.columns, pd.MultiIndex):
            df_adj = df['Adj Close'] if 'Adj Close' in df.columns.levels[0] else df['Close']
            df_close = df['Close']
        else:
            ticker = tickers[0]
            df_adj = df[['Adj Close']].rename(columns={'Adj Close': ticker}) if 'Adj Close' in df else df[['Close']].rename(columns={'Close': ticker})
            df_close = df[['Close']].rename(columns={'Close': ticker})
            
        return df_adj.ffill().bfill(), df_close.ffill().bfill()
    except Exception: 
        return pd.DataFrame(), pd.DataFrame()

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

@st.cache_data(ttl=3600)
def fetch_fundamental_info(ticker):
    try:
        return yf.Ticker(ticker).info
    except:
        return {}

def calcular_metricas(ret_p, ret_m, cdi_s):
    if ret_p.empty: return [0]*8
    if ret_m.empty: ret_m = pd.Series(0, index=ret_p.index)
    if cdi_s.empty: cdi_s = pd.Series(0, index=ret_p.index)
    
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
    beta = np.cov(rp, rm)[0,1] / (var_m + 1e-8) 
    
    ret_p_anual = (1 + ret_acum)**(252/max(1, len(rp))) - 1
    ret_m_anual = (1 + (1+rm).prod()-1)**(252/max(1, len(rm))) - 1
    rf_anual = (1 + (1+rf).prod()-1)**(252/max(1, len(rf))) - 1
    alpha = ret_p_anual - (rf_anual + beta * (ret_m_anual - rf_anual))
    return ret_acum, vol, sharpe, sortino, dd, var95, beta, alpha

def processar_carteira(dict_carteira, df_rv_c, df_rv_s, cdi_al, ipca_al, idx_m, reinvest_flag, setor_filter="Carteira Completa"):
    if setor_filter != "Carteira Completa":
        filtered_dict = {k: v for k, v in dict_carteira.items() if (v.get('setor', 'Não Informado') if v['tipo'] == 'RV' else 'Renda Fixa') == setor_filter}
        dict_carteira = filtered_dict

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
    
    if aportes.sum() == 0: 
        return pd.Series(0, index=idx_m), pd.Series(0, index=idx_m)
        
    pesos = aportes / aportes.sum()
    ret_com = (ret_ativos_c[tickers_v] * pesos).sum(axis=1)
    ret_sem = (ret_ativos_s[tickers_v] * pesos).sum(axis=1)
    return ret_com, ret_sem

def calcular_retorno_individual(ticker, config, df_rv_c, df_rv_s, cdi_al, ipca_al, idx_m, reinvest_flag):
    data_c = pd.to_datetime(config['data_compra'])
    if config['tipo'] == 'RV':
        df_uso = df_rv_c if reinvest_flag else df_rv_s
        if ticker in df_uso.columns:
            r = df_uso[ticker].reindex(idx_m).ffill().bfill().pct_change().fillna(0)
            r[r.index < data_c] = 0.0
            return (1 + r).prod() - 1
    elif config['tipo'] == 'RF':
        if config['indexador'] == "Prefixado": r_d = (1 + config['taxa'])**(1/252) - 1
        elif config['indexador'] == "CDI": r_d = cdi_al * config['taxa']
        elif config['indexador'] == "IPCA+": r_d = (1 + ipca_al) * (1 + config['taxa'])**(1/252) - 1
        r = pd.Series(r_d, index=idx_m)
        r[r.index < data_c] = 0.0
        return (1 + r).prod() - 1
    return 0.0

def plot_markowitz(ativos_dict, df_rv_c, df_rv_s, cdi_al, idx_m, reinvestir_flag):
    ativos_rv_validos = [k for k, v in ativos_dict.items() if v['tipo'] == 'RV']
    if len(ativos_rv_validos) < 2:
        st.warning("Para simular a Fronteira Eficiente, o recorte precisa ter pelo menos 2 ativos de Renda Variável.")
        return
        
    with st.spinner("Simulando 2.000 portfólios..."):
        ret_ativos = pd.DataFrame(index=idx_m)
        for t in ativos_rv_validos:
            r = df_rv_c[t] if reinvestir_flag else df_rv_s[t]
            rc = r.reindex(idx_m).ffill().bfill().pct_change().fillna(0)
            data_c = pd.to_datetime(ativos_dict[t]['data_compra'])
            rc[rc.index < data_c] = 0.0
            ret_ativos[t] = rc
            
        ret_medios = ret_ativos.mean() * 252
        cov_mat = ret_ativos.cov() * 252
        num_portfolios = 2000 
        resultados = np.zeros((3, num_portfolios))
        cdi_anualizado_medio = ((1 + cdi_al).prod() ** (252 / max(1, len(cdi_al))) - 1) if len(cdi_al) > 0 else 0.105
        
        for i in range(num_portfolios):
            pesos = np.random.random(len(ativos_rv_validos))
            pesos /= np.sum(pesos)
            ret_esp = np.sum(pesos * ret_medios)
            vol_esp = np.sqrt(np.dot(pesos.T, np.dot(cov_mat, pesos)))
            resultados[0,i] = ret_esp
            resultados[1,i] = vol_esp
            resultados[2,i] = (ret_esp - cdi_anualizado_medio) / (vol_esp + 1e-8)
            
        df_ef = pd.DataFrame(resultados.T, columns=['Retorno', 'Volatilidade', 'Sharpe'])
        idx_max = df_ef['Sharpe'].idxmax()
        p_max = df_ef.iloc[idx_max]
        
        fig = px.scatter(df_ef, x='Volatilidade', y='Retorno', color='Sharpe', color_continuous_scale='Viridis', opacity=0.8)
        fig.add_trace(go.Scatter(x=[p_max['Volatilidade']], y=[p_max['Retorno']], mode='markers', marker=dict(color='red', size=15, symbol='star'), name='Máximo Sharpe'))
        fig.update_layout(xaxis_title="Volatilidade Anual", yaxis_title="Retorno Anual", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color='#D4AF37'))
        st.plotly_chart(fig, use_container_width=True)

def plot_var_histogram(ret_port, title="Distribuição de Retornos Diários", line_color="red"):
    ret_valido = ret_port.dropna()
    if len(ret_valido) == 0:
        st.warning("Dados insuficientes para plotar o VaR.")
        return
    var_5 = np.percentile(ret_valido, 5)
    fig = px.histogram(ret_valido, nbins=50, title=title)
    fig.add_vline(x=var_5, line_dash="dash", line_color=line_color, annotation_text=f"VaR 5% = {var_5:.4f}")
    fig.update_layout(xaxis_title="Retorno Diário", yaxis_title="Densidade", showlegend=False, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color='#D4AF37'))
    st.plotly_chart(fig, use_container_width=True)

def compara_metrica(val_p, val_c, is_higher_better=True, is_pct=True):
    vp_str = f"{val_p:.2%}" if is_pct else f"{val_p:.2f}"
    vc_str = f"{val_c:.2%}" if is_pct else f"{val_c:.2f}"
    if val_p == val_c: return vp_str, vc_str, "Empate"
    win = val_p > val_c if is_higher_better else val_p < val_c
    if win: return f"⭐ {vp_str}", vc_str, "Principal"
    else: return vp_str, f"⭐ {vc_str}", "Comparada"

try:
    data_1ano_atras = datetime.today() - pd.DateOffset(years=1)
    cdi_recente = fetch_br_indicators(12, data_1ano_atras)
    ipca_recente = fetch_br_indicators(433, data_1ano_atras)
    cdi_auto = ((1 + cdi_recente.iloc[-1])**252 - 1) if not cdi_recente.empty else 0.105
    ipca_auto = ((1 + ipca_recente.tail(12)).prod() - 1) if not ipca_recente.empty else 0.045
except:
    cdi_auto, ipca_auto = 0.105, 0.045

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
    
    with st.expander("📊 Parâmetros de Mercado & Benchmarks", expanded=False):
        opcoes_bench = ["Ibovespa", "IFIX", "S&P 500", "NASDAQ", "SMLL (Small Caps)", "Ouro", "IPCA + Taxa", "CDI (Percentual)", "Selic"]
        benchmarks_sel = st.multiselect("Selecione os Benchmarks de Comparação:", opcoes_bench, default=["Ibovespa"])
        
        taxa_ipca_bench, taxa_cdi_bench = 0.06, 1.0
        if "IPCA + Taxa" in benchmarks_sel:
            taxa_ipca_bench = st.number_input("Taxa Fixa do IPCA+ (%)", value=6.0, step=0.1) / 100
        if "CDI (Percentual)" in benchmarks_sel:
            taxa_cdi_bench = st.number_input("Percentual do CDI (%)", value=100.0, step=1.0) / 100
            
        st.markdown("<hr style='margin:10px 0; opacity: 0.3;'>", unsafe_allow_html=True)
        taxas_personalizadas = st.checkbox("Deseja taxas personalizadas?")
        c_taxa1, c_taxa2 = st.columns(2)
        
        if taxas_personalizadas:
            cdi_base = c_taxa1.number_input("CDI Base Global (%)", value=cdi_auto*100, step=0.1, help="Taxa livre de risco") / 100
            ipca_base = c_taxa2.number_input("IPCA Base Global (%)", value=ipca_auto*100, step=0.1, help="Inflação base") / 100
        else:
            c_taxa1.number_input("CDI Atual BCB (%)", value=cdi_auto*100, disabled=True, help="Taxa diária anualizada puxada hoje do Banco Central")
            c_taxa2.number_input("IPCA Atual BCB (%)", value=ipca_auto*100, disabled=True, help="Inflação acumulada dos últimos 12 meses puxada do Banco Central")
            cdi_base, ipca_base = cdi_auto, ipca_auto
            
        reinvestir = st.checkbox("Reinvestir Dividendos na Carteira Principal", value=True)
        
    with st.expander("💾 Salvar Trabalho & Comparar", expanded=False):
        st.markdown("<span style='font-size:0.85em; opacity:0.8;'>**O SEU SAVE:** Copie o código abaixo para salvar o trabalho ou compartilhar.</span>", unsafe_allow_html=True)
        codigo_export = exportar_codigo_carteira(st.session_state.carteira)
        st.code(codigo_export if codigo_export else "Adicione ativos para gerar.")
        
        st.markdown("<hr style='margin:10px 0;'>", unsafe_allow_html=True)
        st.markdown("<span style='font-size:0.85em; opacity:0.8;'>**COMPARAR:** Cole o código de outra pessoa abaixo para bater as metas.</span>", unsafe_allow_html=True)
        codigo_import = st.text_input("Código de Comparação:")
        reinvestir_comp = st.checkbox("Reinvestir Div. (Carteira Importada)", value=True)
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
        st.warning("⚠️ Ativos listados na B3 exigem o final **.SA** (ex: VALE3.SA).")
        c_rv1, c_rv2 = st.columns(2)
        ticker = c_rv1.text_input("Ticker", help="Ex: PETR4.SA").upper().strip()
        aporte_val = c_rv2.number_input("Peso/Valor", min_value=1.0, value=10.0 if modo_aporte=="Por Peso (%)" else 1000.0)
        setor_rv = st.selectbox("Setor do Ativo (Opcional)", OPCOES_SETORES)
        comprado_inicio_rv = st.checkbox("Desde o Início?", value=True, key="chk_rv")
        data_compra_rv = data_inicio if comprado_inicio_rv else st.date_input("Comprado em", value=data_inicio, min_value=data_inicio, max_value=datetime.today(), key="dt_rv")
        
        if st.button("Inserir Renda Variável") and ticker:
            if re.match(r'^[A-Z0-9\.\-\=]+$', ticker): 
                st.session_state.carteira[ticker] = {'tipo': 'RV', 'aporte': aporte_val, 'data_compra': data_compra_rv, 'setor': setor_rv}
                st.session_state['carteira_alterada'] = True
                st.rerun()
            else:
                st.error("Ticker com formato inválido. Use letras maiúsculas, números e '.SA'.")
    else:
        nome_rf = st.text_input("Nome do Título").strip()
        c_rf1, c_rf2, c_rf3 = st.columns([1.5, 1.5, 1])
        tipo_rf = c_rf1.selectbox("Indexador", ["Prefixado", "CDI", "IPCA+"])
        
        if tipo_rf == "CDI":
            menos_100 = c_rf1.checkbox("Menos de 100% do CDI?")
            if menos_100:
                taxa_input = c_rf2.number_input("Taxa (% do CDI)", value=90.0, step=1.0)
                taxa = taxa_input / 100
            else:
                taxa_input = c_rf2.number_input("100% + qual %? (Ex: 10 = 110%)", value=10.0, step=1.0)
                taxa = (100 + taxa_input) / 100
        elif tipo_rf == "IPCA+":
            taxa_input = c_rf2.number_input("Qual o + do IPCA? (%)", value=6.0, step=0.1, help="Insira apenas a taxa fixa acima do IPCA. Ex: 6.0 para IPCA+6%")
            taxa = taxa_input / 100
        else:
            taxa_input = c_rf2.number_input("Taxa Prefixada ao ano (%)", value=10.0, step=0.1)
            taxa = taxa_input / 100
            
        aporte_val_rf = c_rf3.number_input("Peso/Valor", min_value=1.0, value=10.0 if modo_aporte=="Por Peso (%)" else 1000.0)
        comprado_inicio_rf = st.checkbox("Desde o Início?", value=True, key="chk_rf")
        data_compra_rf = data_inicio if comprado_inicio_rf else st.date_input("Aplicado em", value=data_inicio, min_value=data_inicio, max_value=datetime.today(), key="dt_rf")
        
        if st.button("Inserir Renda Fixa") and nome_rf:
            st.session_state.carteira[nome_rf] = {'tipo': 'RF', 'indexador': tipo_rf, 'taxa': taxa, 'aporte': aporte_val_rf, 'data_compra': data_compra_rf}
            st.session_state['carteira_alterada'] = True
            st.rerun()
            
    if st.button("🗑️ Limpar Carteira Principal"):
        st.session_state.carteira = {}
        st.session_state['carteira_alterada'] = True
        st.rerun()

# --- 4. TELA PRINCIPAL ---
st.title("🏛️ LMF - ASSET")

if not st.session_state.get('carteira_alterada', False):
    st.markdown("""
    <div style="background-color: rgba(212, 175, 55, 0.1); border-left: 5px solid #D4AF37; padding: 15px; border-radius: 5px; margin-bottom: 20px;">
        <h4 style="color: #D4AF37; margin-top: 0;">📌 Diretrizes Operacionais do Sistema</h4>
        Para garantir a precisão da extração de dados, utilize o sufixo <b>.SA</b> em ativos da B3 (ex: PETR4.SA), enquanto ativos globais recebem o ticker original. A data inicial do fundo não deve anteceder o IPO dos ativos selecionados para manter a coesão matemática do VaR e da Fronteira Eficiente. Na seleção de Renda Fixa, siga as instruções dinâmicas de cada indexador para garantir o cálculo preciso dos juros.
    </div>
    """, unsafe_allow_html=True)

if not st.session_state.carteira:
    st.info("👋 Sua carteira está vazia. Utilize a barra lateral para adicionar ativos e iniciar as análises de portfólio.")
else:
    with st.spinner("Sincronizando Mercado Global e Processando Modelagens..."):
        ativos_rv_principal = [k for k, v in st.session_state.carteira.items() if v['tipo'] == 'RV']
        ativos_rv_comp = [k for k, v in st.session_state.carteira_comparacao.items() if v['tipo'] == 'RV']
        
        mapa_bench = {"Ibovespa": "^BVSP", "IFIX": "XFIX11.SA", "S&P 500": "^GSPC", "NASDAQ": "^IXIC", "SMLL (Small Caps)": "SMAL11.SA", "Ouro": "GC=F"}
        tickers_bench_b3 = [mapa_bench[b] for b in benchmarks_sel if b in mapa_bench]
        
        todos_ativos_rv = list(set(ativos_rv_principal + ativos_rv_comp + tickers_bench_b3))
        
        df_rv_com, df_rv_sem = fetch_market_data_both(todos_ativos_rv, data_inicio) 
        
        if not df_rv_com.empty:
            idx_mestre = df_rv_com.dropna(how='all').index
        else:
            idx_mestre = pd.bdate_range(start=data_inicio, end=datetime.today())
            
        if len(idx_mestre) == 0:
            idx_mestre = pd.bdate_range(start=data_inicio, end=datetime.today())
            
        cdi_series = fetch_br_indicators(12, data_inicio)
        selic_series = fetch_br_indicators(11, data_inicio)
        ipca_series = fetch_br_indicators(433, data_inicio)
        
        cdi_aligned = cdi_series.reindex(idx_mestre).fillna(0) if not cdi_series.empty else pd.Series((1 + 0.105)**(1/252) - 1, index=idx_mestre)
        selic_aligned = selic_series.reindex(idx_mestre).fillna(0) if not selic_series.empty else pd.Series((1 + 0.105)**(1/252) - 1, index=idx_mestre)
        
        if ipca_series.empty: ipca_daily_aligned = pd.Series((1 + 0.045)**(1/252) - 1, index=idx_mestre)
        else:
            ipca_daily_val = (1 + ipca_series)**(1/21) - 1
            ipca_daily_aligned = ipca_daily_val.reindex(pd.date_range(start=ipca_daily_val.index.min(), end=datetime.today())).ffill().reindex(idx_mestre).fillna(0)

        dict_ret_benchs = {}
        for b in benchmarks_sel:
            if b == "CDI (Percentual)": dict_ret_benchs[b] = cdi_aligned * taxa_cdi_bench
            elif b == "Selic": dict_ret_benchs[b] = selic_aligned
            elif b == "IPCA + Taxa": dict_ret_benchs[b] = (1 + ipca_daily_aligned) * (1 + taxa_ipca_bench)**(1/252) - 1
            elif b in mapa_bench:
                tb = mapa_bench[b]
                dict_ret_benchs[b] = df_rv_com[tb].reindex(idx_mestre).ffill().pct_change().fillna(0) if tb in df_rv_com.columns else pd.Series(0, index=idx_mestre)
        
        nome_bench_principal = benchmarks_sel[0] if benchmarks_sel else "Benchmark Padrão"
        ret_bench_principal = dict_ret_benchs[nome_bench_principal] if benchmarks_sel else pd.Series(0, index=idx_mestre)

        ret_port_com_full, ret_port_sem_full = processar_carteira(st.session_state.carteira, df_rv_com, df_rv_sem, cdi_aligned, ipca_daily_aligned, idx_mestre, reinvestir)
        ret_portfolio_principal = ret_port_com_full if reinvestir else ret_port_sem_full
        
        if st.session_state.carteira_comparacao:
            ret_comp_com_full, ret_comp_sem_full = processar_carteira(st.session_state.carteira_comparacao, df_rv_com, df_rv_sem, cdi_aligned, ipca_daily_aligned, idx_mestre, reinvestir_comp)
            ret_portfolio_comparacao = ret_comp_com_full if reinvestir_comp else ret_comp_sem_full

        aportes_brutos = np.array([v['aporte'] for v in st.session_state.carteira.values()])
        capital_inicial = aportes_brutos.sum() if modo_aporte == "Por Valor Financeiro (R$)" else capital_inicial_input
        pesos_norm = aportes_brutos / aportes_brutos.sum() if aportes_brutos.sum() > 0 else aportes_brutos * 0

        # --- SEÇÃO 1: COMPOSIÇÃO ---
        st.header("🛒 Posições e Alocação")
        c_lista, c_grafico = st.columns([1, 1.5])
        with c_lista:
            for i, (t, config) in enumerate(st.session_state.carteira.items()):
                c1, c2, c3 = st.columns([3, 1, 1])
                dt_c = config['data_compra'].strftime('%d/%m/%y')
                setor_str = config.get('setor', 'Não Informado') if config['tipo'] == 'RV' else 'Renda Fixa'
                info_alocacao = f"{formatar_moeda(config['aporte'])} ({pesos_norm[i]:.1%})" if modo_aporte == "Por Valor Financeiro (R$)" else f"{pesos_norm[i]:.1%}"
                c1.markdown(f"**{t}** *(Início: {dt_c} | {setor_str})*")
                c2.markdown(info_alocacao)
                if c3.button("❌", key=f"del_{t}"):
                    del st.session_state.carteira[t]
                    st.session_state['carteira_alterada'] = True
                    st.rerun()
                    
        with c_grafico:
            if len(st.session_state.carteira) > 0:
                visao_grafico = st.radio("Visualizar Alocação por:", ["Ativos", "Setores"], horizontal=True)
                if visao_grafico == "Ativos":
                    df_pizza = pd.DataFrame({'Ativo': list(st.session_state.carteira.keys()), 'Peso': pesos_norm})
                    fig = px.pie(df_pizza, values='Peso', names='Ativo', hole=0.5)
                else:
                    setores_lista = [v.get('setor', 'Não Informado') if v['tipo'] == 'RV' else 'Renda Fixa' for v in st.session_state.carteira.values()]
                    df_pizza = pd.DataFrame({'Setor': setores_lista, 'Peso': pesos_norm})
                    df_pizza = df_pizza.groupby('Setor', as_index=False).sum()
                    fig = px.pie(df_pizza, values='Peso', names='Setor', hole=0.5)
                
                fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', font=dict(color='#D4AF37'), margin=dict(t=0, b=0, l=0, r=0))
                st.plotly_chart(fig, use_container_width=True)

        st.markdown("---")

        # --- SEÇÃO 2: MÉTRICAS GLOBAIS ---
        st.header("📊 Resumo de Desempenho (Carteira Completa)")
        m_prin = calcular_metricas(ret_portfolio_principal, ret_bench_principal, cdi_aligned)
        
        # Cálculos de Representação Numérica e Diferença de Dividendos
        ret_port_com_acum = (1 + ret_port_com_full).prod() - 1
        ret_port_sem_acum = (1 + ret_port_sem_full).prod() - 1
        patrimonio_final = capital_inicial * (1 + m_prin[0])
        lucro_rs = capital_inicial * m_prin[0]

        cm1, cm2, cm3 = st.columns(3)
        cm1.metric("Capital Inicial Alocado", formatar_moeda(capital_inicial))
        cm2.metric("Patrimônio Atualizado (R$)", formatar_moeda(patrimonio_final), formatar_moeda(lucro_rs))
        cm3.metric("Impacto dos Dividendos (Yield Extra)", f"{(ret_port_com_acum - ret_port_sem_acum):.2%}", help="Diferença total de rentabilidade (Com Dividendos vs Sem Dividendos)")

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Rentabilidade Acumulada", f"{m_prin[0]:.2%}")
        c2.metric("Alpha de Jensen", f"{m_prin[7]:.2%}")
        c3.metric("Índice Sharpe", f"{m_prin[2]:.2f}")
        c4.metric("Índice Sortino", f"{m_prin[3]:.2f}")
        
        c5, c6, c7, c8 = st.columns(4)
        c5.metric("Volatilidade Anual", f"{m_prin[1]:.2%}")
        c6.metric("Max Drawdown", f"{m_prin[4]:.2%}")
        c7.metric("VaR (95%)", f"{m_prin[5]:.2%}")
        c8.metric(f"Beta vs {nome_bench_principal}", f"{m_prin[6]:.2f}")

        st.markdown("---")
        
        # --- ABAS DE ANÁLISE ---
        abas_nomes = ["📈 Rentabilidade Global", "🔎 Raio-X da Carteira", "⚙️ Estudo das Métricas"]
        if st.session_state.carteira_comparacao: abas_nomes.append("🆚 Análise de Comparação")
        abas_nomes.extend(["🔍 Análise Fundamentalista", "🕯️ Candlestick (Ativos)"])
        
        tabs = st.tabs(abas_nomes)
        tab_idx = 0
        
        with tabs[tab_idx]: # Rentabilidade Global
            c_rent_title, c_rent_filt = st.columns([2, 1])
            c_rent_title.markdown("Comparativo de rentabilidade contra os múltiplos benchmarks.")
            
            setores_presentes_rent = list(set([v.get('setor', 'Não Informado') if v['tipo'] == 'RV' else 'Renda Fixa' for v in st.session_state.carteira.values()]))
            if st.session_state.carteira_comparacao:
                setores_presentes_rent.extend(list(set([v.get('setor', 'Não Informado') if v['tipo'] == 'RV' else 'Renda Fixa' for v in st.session_state.carteira_comparacao.values()])))
                setores_presentes_rent = list(set(setores_presentes_rent))
                
            setor_filtro_rent = c_rent_filt.selectbox("Filtrar por Setor (Gráfico):", ["Carteira Completa"] + setores_presentes_rent, key="filt_rent")
            
            df_grafico = pd.DataFrame(index=idx_mestre)
            
            if setor_filtro_rent != "Carteira Completa":
                ret_rent_com_sect, ret_rent_sem_sect = processar_carteira(st.session_state.carteira, df_rv_com, df_rv_sem, cdi_aligned, ipca_daily_aligned, idx_mestre, reinvestir, setor_filter=setor_filtro_rent)
                ret_rent_sect = ret_rent_com_sect if reinvestir else ret_rent_sem_sect
                df_grafico[f"Sua Carteira - {setor_filtro_rent} (%)"] = ((1 + ret_rent_sect).cumprod() - 1) * 100
                color_map = {f"Sua Carteira - {setor_filtro_rent} (%)": "#D4AF37"}
                
                if st.session_state.carteira_comparacao:
                    ret_rent_comp_com_sect, ret_rent_comp_sem_sect = processar_carteira(st.session_state.carteira_comparacao, df_rv_com, df_rv_sem, cdi_aligned, ipca_daily_aligned, idx_mestre, reinvestir_comp, setor_filter=setor_filtro_rent)
                    ret_rent_comp_sect = ret_rent_comp_com_sect if reinvestir_comp else ret_rent_comp_sem_sect
                    df_grafico[f"Comparação - {setor_filtro_rent} (%)"] = ((1 + ret_rent_comp_sect).cumprod() - 1) * 100
                    color_map[f"Comparação - {setor_filtro_rent} (%)"] = "#00BFFF"
            else:
                df_grafico["Sua Carteira (%)"] = ((1 + ret_portfolio_principal).cumprod() - 1) * 100
                color_map = {"Sua Carteira (%)": "#D4AF37"}
                if st.session_state.carteira_comparacao:
                    df_grafico["Carteira Comparação (%)"] = ((1 + ret_portfolio_comparacao).cumprod() - 1) * 100
                    color_map["Carteira Comparação (%)"] = "#00BFFF"
            
            for nome_bench, serie_bench in dict_ret_benchs.items():
                df_grafico[f"{nome_bench} (%)"] = ((1 + serie_bench).cumprod() - 1) * 100
                
            fig_rent = px.line(df_grafico, color_discrete_map=color_map)
            fig_rent.update_layout(xaxis_title="", yaxis_title="Acumulado (%)", xaxis=dict(tickformat="%b %Y", dtick="M3"), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color='#D4AF37'))
            st.plotly_chart(fig_rent, use_container_width=True)

        tab_idx += 1
        with tabs[tab_idx]: # Raio-X da Carteira
            st.markdown("### 🔎 Análise Financeira Individual")
            st.markdown("Confira o capital injetado, o retorno com e sem os dividendos embutidos e o patrimônio exato final de cada ativo na sua carteira.")
            
            html_table = "<table><tr><th>Ativo</th><th>Classe</th><th>Setor</th><th>Capital Alocado</th><th>Retorno (Sem Div)</th><th>Retorno (Com Div)</th><th>Saldo Atualizado</th></tr>"
            
            for i, (t, config) in enumerate(st.session_state.carteira.items()):
                ret_ind_c = calcular_retorno_individual(t, config, df_rv_com, df_rv_sem, cdi_aligned, ipca_daily_aligned, idx_mestre, True)
                ret_ind_s = calcular_retorno_individual(t, config, df_rv_com, df_rv_sem, cdi_aligned, ipca_daily_aligned, idx_mestre, False)
                
                val_inicial = config['aporte'] if modo_aporte == "Por Valor Financeiro (R$)" else capital_inicial * pesos_norm[i]
                val_final = val_inicial * (1 + (ret_ind_c if reinvestir else ret_ind_s))
                
                color_s = "#4CAF50" if ret_ind_s >= 0 else "#F44336" 
                color_c = "#4CAF50" if ret_ind_c >= 0 else "#F44336"
                setor_rx = config.get('setor', 'Renda Fixa' if config['tipo'] == 'RF' else 'Não Informado')
                
                html_table += f"<tr><td><b>{t}</b></td><td>{config['tipo']}</td><td>{setor_rx}</td><td>{formatar_moeda(val_inicial)}</td><td style='color:{color_s}'><b>{formatar_percentual(ret_ind_s)}</b></td><td style='color:{color_c}'><b>{formatar_percentual(ret_ind_c)}</b></td><td><b>{formatar_moeda(val_final)}</b></td></tr>"
            
            html_table += "</table>"
            st.markdown(html_table, unsafe_allow_html=True)

        tab_idx += 1
        with tabs[tab_idx]: # Estudo das Métricas
            c_estudo, c_filtro = st.columns(2)
            metrica_sel = c_estudo.selectbox("Selecione o Estudo (Sua Carteira):", ["Fronteira Eficiente (Markowitz)", "Value at Risk (VaR)", "Drawdown Histórico", "Volatilidade Rolante", "Beta (Risco de Mercado)"])
            
            setores_presentes = list(set([v.get('setor', 'Não Informado') if v['tipo'] == 'RV' else 'Renda Fixa' for v in st.session_state.carteira.values()]))
            setor_filtro = c_filtro.selectbox("Filtrar por Setor:", ["Carteira Completa"] + setores_presentes)
            
            if setor_filtro != "Carteira Completa":
                ret_estudo_com, ret_estudo_sem = processar_carteira(st.session_state.carteira, df_rv_com, df_rv_sem, cdi_aligned, ipca_daily_aligned, idx_mestre, reinvestir, setor_filter=setor_filtro)
                ret_estudo = ret_estudo_com if reinvestir else ret_estudo_sem
                dict_estudo = {k: v for k, v in st.session_state.carteira.items() if (v.get('setor', 'Não Informado') if v['tipo'] == 'RV' else 'Renda Fixa') == setor_filtro}
            else:
                ret_estudo = ret_portfolio_principal
                dict_estudo = st.session_state.carteira

            janela = 252 
            df_roll = pd.DataFrame(index=idx_mestre)
            
            if metrica_sel == "Fronteira Eficiente (Markowitz)":
                plot_markowitz(dict_estudo, df_rv_com, df_rv_sem, cdi_aligned, idx_mestre, reinvestir)
            elif metrica_sel == "Value at Risk (VaR)":
                tipo_var = st.radio("Selecione a visualização do VaR:", ["Histograma de Retornos (Estático)", "VaR Histórico Rolante"], horizontal=True)
                if tipo_var == "Histograma de Retornos (Estático)":
                    plot_var_histogram(ret_estudo, f"Distribuição de Retornos ({setor_filtro})")
                else:
                    df_roll[f"VaR 5% ({setor_filtro})"] = ret_estudo.rolling(janela).quantile(0.05)
                    fig_var = px.line(df_roll.dropna(), color_discrete_sequence=["#D4AF37"])
                    fig_var.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color='#D4AF37'))
                    st.plotly_chart(fig_var, use_container_width=True)
            elif metrica_sel == "Drawdown Histórico":
                df_roll[f"{setor_filtro} (%)"] = (((1 + ret_estudo).cumprod() / (1 + ret_estudo).cumprod().cummax()) - 1) * 100
                fig_dd = px.line(df_roll.dropna(), color_discrete_sequence=["#D4AF37"])
                fig_dd.update_traces(fill='tozeroy') 
                fig_dd.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color='#D4AF37'))
                st.plotly_chart(fig_dd, use_container_width=True)
            elif metrica_sel == "Volatilidade Rolante":
                df_roll[f"{setor_filtro} (%)"] = ret_estudo.rolling(janela).std() * np.sqrt(252) * 100
                df_roll[f"{nome_bench_principal} (%)"] = ret_bench_principal.rolling(janela).std() * np.sqrt(252) * 100
                fig_vol = px.line(df_roll.dropna(), color_discrete_sequence=["#D4AF37", "#555555"])
                fig_vol.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color='#D4AF37'))
                st.plotly_chart(fig_vol, use_container_width=True)
            elif metrica_sel == "Beta (Risco de Mercado)":
                var_bench = ret_bench_principal.rolling(janela).var()
                var_bench = var_bench.where(var_bench > 1e-8, 1e-8) 
                df_roll[f"Beta ({setor_filtro})"] = ret_estudo.rolling(janela).cov(ret_bench_principal) / var_bench
                
                df_plot = df_roll.dropna()
                if df_plot.empty:
                    st.warning(f"O benchmark atual ({nome_bench_principal}) não possui volatilidade suficiente para o cálculo de Beta (Risco de Mercado é exclusivo para renda variável).")
                else:
                    fig_beta = px.line(df_plot, color_discrete_sequence=["#D4AF37"])
                    fig_beta.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color='#D4AF37'))
                    st.plotly_chart(fig_beta, use_container_width=True)

        if st.session_state.carteira_comparacao:
            tab_idx += 1
            with tabs[tab_idx]: # Análise Comparação
                m_comp = calcular_metricas(ret_portfolio_comparacao, ret_bench_principal, cdi_aligned)
                st.markdown("### 🏆 Confronto Direto de Métricas (Carteiras Completas)")
                r_p, r_c, win_r = compara_metrica(m_prin[0], m_comp[0], True, True)
                a_p, a_c, win_a = compara_metrica(m_prin[7], m_comp[7], True, True)
                s_p, s_c, win_s = compara_metrica(m_prin[2], m_comp[2], True, False)
                v_p, v_c, win_v = compara_metrica(m_prin[1], m_comp[1], False, True)
                d_p, d_c, win_d = compara_metrica(m_prin[4], m_comp[4], True, True) 
                
                st.markdown(f"""
                <table>
                    <tr><th>Métrica</th><th>Sua Carteira</th><th>Carteira Importada</th><th>Vencedor</th></tr>
                    <tr><td>Retorno Acumulado</td><td>{r_p}</td><td>{r_c}</td><td>{win_r}</td></tr>
                    <tr><td>Alpha de Jensen</td><td>{a_p}</td><td>{a_c}</td><td>{win_a}</td></tr>
                    <tr><td>Índice Sharpe</td><td>{s_p}</td><td>{s_c}</td><td>{win_s}</td></tr>
                    <tr><td>Volatilidade Anual</td><td>{v_p}</td><td>{v_c}</td><td>{win_v}</td></tr>
                    <tr><td>Drawdown Máximo</td><td>{d_p}</td><td>{d_c}</td><td>{win_d}</td></tr>
                </table>
                """, unsafe_allow_html=True)
                
                st.markdown("### 📈 Estudo Profundo (Carteira Importada)")
                c_est_c, c_filt_c = st.columns(2)
                est_comp = c_est_c.selectbox("Análise Específica do Colega:", ["Fronteira Eficiente (Markowitz)", "Value at Risk (VaR)", "Drawdown Histórico", "Volatilidade Rolante", "Beta (Risco de Mercado)"])
                
                setores_presentes_comp = list(set([v.get('setor', 'Não Informado') if v['tipo'] == 'RV' else 'Renda Fixa' for v in st.session_state.carteira_comparacao.values()]))
                setor_filtro_comp = c_filt_c.selectbox("Filtrar por Setor (Importada):", ["Carteira Completa"] + setores_presentes_comp)
                
                if setor_filtro_comp != "Carteira Completa":
                    ret_estudo_comp_com, ret_estudo_comp_sem = processar_carteira(st.session_state.carteira_comparacao, df_rv_com, df_rv_sem, cdi_aligned, ipca_daily_aligned, idx_mestre, reinvestir_comp, setor_filter=setor_filtro_comp)
                    ret_estudo_comp = ret_estudo_comp_com if reinvestir_comp else ret_estudo_comp_sem
                    dict_estudo_comp = {k: v for k, v in st.session_state.carteira_comparacao.items() if (v.get('setor', 'Não Informado') if v['tipo'] == 'RV' else 'Renda Fixa') == setor_filtro_comp}
                else:
                    ret_estudo_comp = ret_portfolio_comparacao
                    dict_estudo_comp = st.session_state.carteira_comparacao
                
                df_roll_comp = pd.DataFrame(index=idx_mestre)
                janela = 252

                if est_comp == "Fronteira Eficiente (Markowitz)":
                    plot_markowitz(dict_estudo_comp, df_rv_com, df_rv_sem, cdi_aligned, idx_mestre, reinvestir_comp)
                
                elif est_comp == "Value at Risk (VaR)":
                    tipo_var_comp = st.radio("Selecione a visualização do VaR (Importada):", ["Histograma de Retornos (Estático)", "VaR Histórico Rolante"], horizontal=True)
                    if tipo_var_comp == "Histograma de Retornos (Estático)":
                        plot_var_histogram(ret_estudo_comp, f"Distribuição de Retornos (Importada - {setor_filtro_comp})", "#00BFFF")
                    else:
                        df_roll_comp[f"VaR 5% ({setor_filtro_comp})"] = ret_estudo_comp.rolling(janela).quantile(0.05)
                        fig_var_c = px.line(df_roll_comp.dropna(), color_discrete_sequence=["#00BFFF"])
                        fig_var_c.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color='#D4AF37'))
                        st.plotly_chart(fig_var_c, use_container_width=True)
                
                elif est_comp == "Drawdown Histórico":
                    df_roll_comp[f"Importada ({setor_filtro_comp}) %"] = (((1 + ret_estudo_comp).cumprod() / (1 + ret_estudo_comp).cumprod().cummax()) - 1) * 100
                    fig_dd_c = px.line(df_roll_comp.dropna(), color_discrete_sequence=["#00BFFF"])
                    fig_dd_c.update_traces(fill='tozeroy') 
                    fig_dd_c.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color='#D4AF37'))
                    st.plotly_chart(fig_dd_c, use_container_width=True)
                
                elif est_comp == "Volatilidade Rolante":
                    df_roll_comp[f"Importada ({setor_filtro_comp}) %"] = ret_estudo_comp.rolling(janela).std() * np.sqrt(252) * 100
                    df_roll_comp[f"{nome_bench_principal} (%)"] = ret_bench_principal.rolling(janela).std() * np.sqrt(252) * 100
                    fig_vol_c = px.line(df_roll_comp.dropna(), color_discrete_sequence=["#00BFFF", "#555555"])
                    fig_vol_c.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color='#D4AF37'))
                    st.plotly_chart(fig_vol_c, use_container_width=True)
                
                elif est_comp == "Beta (Risco de Mercado)":
                    var_bench = ret_bench_principal.rolling(janela).var()
                    var_bench = var_bench.where(var_bench > 1e-8, 1e-8)
                    df_roll_comp[f"Beta ({setor_filtro_comp})"] = ret_estudo_comp.rolling(janela).cov(ret_bench_principal) / var_bench
                    
                    df_plot_c = df_roll_comp.dropna()
                    if df_plot_c.empty:
                        st.warning(f"O benchmark atual ({nome_bench_principal}) não possui volatilidade suficiente para o cálculo de Beta (Risco de Mercado é exclusivo para renda variável).")
                    else:
                        fig_beta_c = px.line(df_plot_c, color_discrete_sequence=["#00BFFF"])
                        fig_beta_c.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color='#D4AF37'))
                        st.plotly_chart(fig_beta_c, use_container_width=True)
                
                st.markdown("### 🔎 RX dos Ativos Importados")
                st.write(f"Cálculo de Dividendos: **{'Reinvestidos' if reinvestir_comp else 'Não Reinvestidos'}**")
                
                html_table_comp = "<table><tr><th>Ativo</th><th>Classe</th><th>Setor</th><th>Capital Alocado</th><th>Retorno (Sem Div)</th><th>Retorno (Com Div)</th></tr>"
                for t, config in st.session_state.carteira_comparacao.items():
                    ret_ind_c = calcular_retorno_individual(t, config, df_rv_com, df_rv_sem, cdi_aligned, ipca_daily_aligned, idx_mestre, True)
                    ret_ind_s = calcular_retorno_individual(t, config, df_rv_com, df_rv_sem, cdi_aligned, ipca_daily_aligned, idx_mestre, False)
                    
                    color_s = "#4CAF50" if ret_ind_s >= 0 else "#F44336" 
                    color_c = "#4CAF50" if ret_ind_c >= 0 else "#F44336"
                    setor_c = config.get('setor', 'Não Informado') if config['tipo'] == 'RV' else 'Renda Fixa'
                    peso_inicial_str = formatar_moeda(config['aporte']) if modo_aporte == 'Por Valor Financeiro (R$)' else str(config['aporte']) + '%'
                    
                    html_table_comp += f"<tr><td><b>{t}</b></td><td>{config['tipo']}</td><td>{setor_c}</td><td>{peso_inicial_str}</td><td style='color:{color_s}'><b>{formatar_percentual(ret_ind_s)}</b></td><td style='color:{color_c}'><b>{formatar_percentual(ret_ind_c)}</b></td></tr>"
                html_table_comp += "</table>"
                st.markdown(html_table_comp, unsafe_allow_html=True)

        tab_idx += 1
        with tabs[tab_idx]: # Análise Fundamentalista
            if not ativos_rv_principal:
                st.warning("Adicione ativos de Renda Variável na carteira principal para visualizar a análise fundamentalista.")
            else:
                ativo_fund = st.selectbox("Selecione o Ativo para Análise Fundamentalista:", ativos_rv_principal)
                if ativo_fund:
                    with st.spinner(f"Extraindo dados fundamentalistas de {ativo_fund}..."):
                        info = fetch_fundamental_info(ativo_fund)
                        
                        if not info or ('trailingPE' not in info and 'marketCap' not in info and 'priceToBook' not in info):
                            st.warning(f"Dados fundamentalistas não estão disponíveis na API global para o ativo {ativo_fund} no momento.")
                        else:
                            st.markdown(f"### 📊 Raio-X Fundamentalista: {ativo_fund}")
                            st.markdown("---")
                            
                            st.subheader("💰 Valuation & Preço", divider='gray')
                            v1, v2, v3, v4 = st.columns(4)
                            v1.metric("P/L (Preço/Lucro)", formatar_float(info.get('trailingPE')))
                            v2.metric("P/VP (Preço/Valor Patrimonial)", formatar_float(info.get('priceToBook')))
                            v3.metric("Dividend Yield (DY)", formatar_pct_api(info.get('dividendYield')))
                            v4.metric("PEG Ratio", formatar_float(info.get('pegRatio')))
                            
                            st.subheader("📈 Rentabilidade & Eficiência", divider='gray')
                            r1, r2, r3, r4 = st.columns(4)
                            r1.metric("ROE (Retorno s/ Patrimônio)", formatar_pct_api(info.get('returnOnEquity')))
                            r2.metric("ROA (Retorno s/ Ativos)", formatar_pct_api(info.get('returnOnAssets')))
                            r3.metric("Margem Líquida", formatar_pct_api(info.get('profitMargins')))
                            r4.metric("Margem Bruta", formatar_pct_api(info.get('grossMargins')))
                            
                            st.subheader("🏛️ Saúde Financeira & Estrutura", divider='gray')
                            s1, s2, s3, s4 = st.columns(4)
                            s1.metric("Liquidez Corrente", formatar_float(info.get('currentRatio')))
                            s2.metric("Dívida/Patrimônio", formatar_float(info.get('debtToEquity', 0) / 100 if info.get('debtToEquity') else None))
                            s3.metric("LPA (Lucro por Ação)", formatar_float(info.get('trailingEps')))
                            s4.metric("Valor de Mercado", formatar_abrev(info.get('marketCap')))

        tab_idx += 1
        with tabs[tab_idx]: # Candlestick
            ativo_candle = st.selectbox("Ativo (Gráfico de Preço):", [t for t in ativos_rv_principal])
            if ativo_candle:
                df_ohlc = yf.download(ativo_candle, start=data_inicio, progress=False, auto_adjust=False)
                if df_ohlc.empty or 'Open' not in df_ohlc:
                    st.warning("Dados indisponíveis para o carregamento do gráfico deste ativo no momento.")
                else:
                    o = df_ohlc['Open'].squeeze()
                    h = df_ohlc['High'].squeeze()
                    l = df_ohlc['Low'].squeeze()
                    c = df_ohlc['Close'].squeeze()
                    fig_c = go.Figure(data=[go.Candlestick(x=df_ohlc.index, open=o, high=h, low=l, close=c)])
                    fig_c.update_layout(
                        paper_bgcolor='rgba(0,0,0,0)', 
                        plot_bgcolor='rgba(0,0,0,0)', 
                        font=dict(color='#D4AF37'),
                        xaxis_title="Data",
                        yaxis_title="Cotação / Preço",
                        xaxis_rangeslider_visible=False
                    )
                    st.plotly_chart(fig_c, use_container_width=True)

        if st.button("🖨️ Salvar Relatório em PDF", use_container_width=True):
            components.html("<script>window.parent.print();</script>", height=0)
        st.markdown(f"<div style='text-align:right; color:#D4AF37; opacity:0.6'>Idealizado por Bernardo V.</div>", unsafe_allow_html=True)

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
    table { width: 100%; text-align: center; border-collapse: collapse; margin-bottom: 20px; }
    th { border-bottom: 2px solid #D4AF37; color: #D4AF37; padding: 10px; }
    td { border-bottom: 1px solid #333; padding: 10px; }
    </style>
""", unsafe_allow_html=True)

# --- INICIALIZAÇÃO DE ESTADO E CARTEIRA PADRÃO ---
if 'carteira_alterada' not in st.session_state:
    st.session_state['carteira_alterada'] = False

if 'carteira' not in st.session_state or (st.session_state.carteira and not isinstance(list(st.session_state.carteira.values())[0], dict)):
    if not st.session_state['carteira_alterada']:
        dt_padrao = datetime(2012, 1, 1).date()
        st.session_state['carteira'] = {
            'QQQ': {'tipo': 'RV', 'aporte': 10.0, 'data_compra': dt_padrao, 'setor': 'Tecnologia da Informação'},
            'JEPI': {'tipo': 'RV', 'aporte': 10.0, 'data_compra': dt_padrao, 'setor': 'Não Informado'},
            'PETR4.SA': {'tipo': 'RV', 'aporte': 10.0, 'data_compra': dt_padrao, 'setor': 'Petróleo, Gás e Biocombustíveis'},
            'IVV': {'tipo': 'RV', 'aporte': 10.0, 'data_compra': dt_padrao, 'setor': 'Não Informado'},
            'CDI 100%': {'tipo': 'RF', 'indexador': 'CDI', 'taxa': 1.0, 'aporte': 10.0, 'data_compra': dt_padrao},
            'IPCA+ 7%': {'tipo': 'RF', 'indexador': 'IPCA+', 'taxa': 0.07, 'aporte': 10.0, 'data_compra': dt_padrao},
            'VALE3.SA': {'tipo': 'RV', 'aporte': 10.0, 'data_compra': dt_padrao, 'setor': 'Materiais Básicos'},
            'BBDC4.SA': {'tipo': 'RV', 'aporte': 10.0, 'data_compra': dt_padrao, 'setor': 'Financeiro e Outros'},
            'BBSE3.SA': {'tipo': 'RV', 'aporte': 10.0, 'data_compra': dt_padrao, 'setor': 'Financeiro e Outros'},
            'BRSR6.SA': {'tipo': 'RV', 'aporte': 10.0, 'data_compra': dt_padrao, 'setor': 'Financeiro e Outros'}
        }
    else:
        st.session_state['carteira'] = {}

if 'carteira_comparacao' not in st.session_state:
    st.session_state['carteira_comparacao'] = {}

OPCOES_SETORES = [
    "Não Informado", "Consumo Cíclico", "Consumo não Cíclico", "Utilidade Pública",
    "Bens Industriais", "Materiais Básicos", "Financeiro e Outros",
    "Tecnologia da Informação", "Saúde", "Petróleo, Gás e Biocombustíveis", "Comunicações"
]

# --- FUNÇÕES DE FORMATAÇÃO E IMPORTAÇÃO ---
def formatar_moeda(valor):
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def formatar_percentual(valor):
    sinal = "+" if valor >= 0 else ""
    return f"{sinal}{valor*100:.2f}%"

def formatar_float(valor):
    if valor is None or pd.isna(valor): return "N/A"
    return f"{float(valor):.2f}"

def formatar_pct_api(valor):
    if valor is None or pd.isna(valor): return "N/A"
    return f"{float(valor)*100:.2f}%"

def formatar_abrev(valor):
    if valor is None or pd.isna(valor): return "N/A"
    try:
        val = float(valor)
        if val >= 1e9: return f"{val/1e9:.2f} B"
        if val >= 1e6: return f"{val/1e6:.2f} M"
        return f"{val:.2f}"
    except: return "N/A"

def exportar_codigo_carteira(carteira_dict):
    if not carteira_dict: return ""
    cart_copy = {}
    for k, v in carteira_dict.items():
        v_copy = v.copy()
        if isinstance(v_copy.get('data_compra'), datetime) or hasattr(v_copy.get('data_compra'), 'strftime'):
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

@st.cache_data(ttl=3600)
def fetch_fundamental_info(ticker):
    try:
        return yf.Ticker(ticker).info
    except:
        return {}

def calcular_metricas(ret_p, ret_m, cdi_s):
    if ret_p.empty: return [0]*8
    if ret_m.empty: ret_m = pd.Series(0, index=ret_p.index)
    if cdi_s.empty: cdi_s = pd.Series(0, index=ret_p.index)
    
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

def processar_carteira(dict_carteira, df_rv_c, df_rv_s, cdi_al, ipca_al, idx_m, reinvest_flag, setor_filter="Carteira Completa"):
    if setor_filter != "Carteira Completa":
        filtered_dict = {}
        for k, v in dict_carteira.items():
            s = v.get('setor', 'Não Informado') if v['tipo'] == 'RV' else 'Renda Fixa'
            if s == setor_filter:
                filtered_dict[k] = v
        dict_carteira = filtered_dict

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

def calcular_retorno_individual(ticker, config, df_rv_c, df_rv_s, cdi_al, ipca_al, idx_m, reinvest_flag):
    data_c = pd.to_datetime(config['data_compra'])
    if config['tipo'] == 'RV':
        df_uso = df_rv_c if reinvest_flag else df_rv_s
        if ticker in df_uso.columns:
            r = df_uso[ticker].reindex(idx_m).ffill().bfill().pct_change().fillna(0)
            r[r.index < data_c] = 0.0
            return (1 + r).prod() - 1
    elif config['tipo'] == 'RF':
        if config['indexador'] == "Prefixado": r_d = (1 + config['taxa'])**(1/252) - 1
        elif config['indexador'] == "CDI": r_d = cdi_al * config['taxa']
        elif config['indexador'] == "IPCA+": r_d = (1 + ipca_al) * (1 + config['taxa'])**(1/252) - 1
        r = pd.Series(r_d, index=idx_m)
        r[r.index < data_c] = 0.0
        return (1 + r).prod() - 1
    return 0.0

def plot_markowitz(ativos_dict, df_rv_c, df_rv_s, cdi_al, idx_m, reinvestir_flag):
    ativos_rv_validos = [k for k, v in ativos_dict.items() if v['tipo'] == 'RV']
    if len(ativos_rv_validos) < 2:
        st.warning("Para simular a Fronteira Eficiente, o recorte precisa ter pelo menos 2 ativos de Renda Variável.")
        return
        
    with st.spinner("Simulando 5.000 portfólios..."):
        ret_ativos = pd.DataFrame(index=idx_m)
        for t in ativos_rv_validos:
            r = df_rv_c[t] if reinvestir_flag else df_rv_s[t]
            rc = r.reindex(idx_m).ffill().bfill().pct_change().fillna(0)
            data_c = pd.to_datetime(ativos_dict[t]['data_compra'])
            rc[rc.index < data_c] = 0.0
            ret_ativos[t] = rc
            
        ret_medios = ret_ativos.mean() * 252
        cov_mat = ret_ativos.cov() * 252
        num_portfolios = 5000
        resultados = np.zeros((3, num_portfolios))
        cdi_anualizado_medio = ((1 + cdi_al).prod() ** (252 / len(cdi_al)) - 1) if len(cdi_al) > 0 else 0.105
        
        for i in range(num_portfolios):
            pesos = np.random.random(len(ativos_rv_validos))
            pesos /= np.sum(pesos)
            ret_esp = np.sum(pesos * ret_medios)
            vol_esp = np.sqrt(np.dot(pesos.T, np.dot(cov_mat, pesos)))
            resultados[0,i] = ret_esp
            resultados[1,i] = vol_esp
            resultados[2,i] = (ret_esp - cdi_anualizado_medio) / vol_esp if vol_esp > 0 else 0
            
        df_ef = pd.DataFrame(resultados.T, columns=['Retorno', 'Volatilidade', 'Sharpe'])
        idx_max = df_ef['Sharpe'].idxmax()
        p_max = df_ef.iloc[idx_max]
        
        fig = px.scatter(df_ef, x='Volatilidade', y='Retorno', color='Sharpe', color_continuous_scale='Viridis', opacity=0.8)
        fig.add_trace(go.Scatter(x=[p_max['Volatilidade']], y=[p_max['Retorno']], mode='markers', marker=dict(color='red', size=15, symbol='star'), name='Máximo Sharpe'))
        fig.update_layout(xaxis_title="Volatilidade Anual", yaxis_title="Retorno Anual", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color='#D4AF37'))
        st.plotly_chart(fig, use_container_width=True)

def plot_var_histogram(ret_port, title="Distribuição de Retornos Diários", line_color="red"):
    ret_valido = ret_port.dropna()
    if len(ret_valido) == 0:
        st.warning("Dados insuficientes para plotar o histograma de VaR.")
        return
    var_5 = np.percentile(ret_valido, 5)
    fig = px.histogram(ret_valido, nbins=50, title=title)
    fig.add_vline(x=var_5, line_dash="dash", line_color=line_color, annotation_text=f"VaR 5% = {var_5:.4f}")
    fig.update_layout(xaxis_title="Retorno Diário", yaxis_title="Densidade", showlegend=False, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color='#D4AF37'))
    st.plotly_chart(fig, use_container_width=True)

def compara_metrica(val_p, val_c, is_higher_better=True, is_pct=True):
    vp_str = f"{val_p:.2%}" if is_pct else f"{val_p:.2f}"
    vc_str = f"{val_c:.2%}" if is_pct else f"{val_c:.2f}"
    if val_p == val_c: return vp_str, vc_str, "Empate"
    win = val_p > val_c if is_higher_better else val_p < val_c
    if win: return f"⭐ {vp_str}", vc_str, "Principal"
    else: return vp_str, f"⭐ {vc_str}", "Comparada"

# --- TELA INICIAL (SPLASH SCREEN / SAVE STATE) ---
if 'started' not in st.session_state:
    st.session_state['started'] = False

if not st.session_state['started']:
    st.title("🏛️ LMF - ASSET")
    st.markdown("### Bem-vindo ao Sistema de Gestão de Portfólio")
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### 📄 Iniciar Nova Carteira")
        st.info("Inicie uma nova análise utilizando nossa carteira modelo pré-definida e altere conforme desejar.")
        if st.button("Criar Nova Carteira", use_container_width=True):
            st.session_state['started'] = True
            st.rerun()
            
    with col2:
        st.markdown("#### 💾 Continuar Trabalho")
        st.success("Cole abaixo o código da carteira que você salvou anteriormente para restaurar todo o seu progresso.")
        codigo_salvo = st.text_input("Cole seu código de salvamento aqui:")
        if st.button("Carregar Trabalho", use_container_width=True):
            if codigo_salvo:
                cart_importada = importar_codigo_carteira(codigo_salvo)
                if cart_importada:
                    st.session_state['carteira'] = cart_importada
                    st.session_state['started'] = True
                    st.session_state['carteira_alterada'] = True 
                    st.rerun()
                else:
                    st.error("Código inválido. Verifique se copiou corretamente.")
            else:
                st.warning("Por favor, cole um código antes de continuar.")
                
    st.markdown(f"<br><br><div style='text-align:center; color:#D4AF37; opacity:0.6'>Idealizado por Bernardo V.</div>", unsafe_allow_html=True)
    st.stop() 

try:
    data_1ano_atras = datetime.today() - pd.DateOffset(years=1)
    cdi_recente = fetch_br_indicators(12, data_1ano_atras)
    ipca_recente = fetch_br_indicators(433, data_1ano_atras)
    cdi_auto = ((1 + cdi_recente.iloc[-1])**252 - 1) if not cdi_recente.empty else 0.105
    ipca_auto = ((1 + ipca_recente.tail(12)).prod() - 1) if not ipca_recente.empty else 0.045
except:
    cdi_auto, ipca_auto = 0.105, 0.045

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
    
    with st.expander("📊 Parâmetros de Mercado & Benchmarks", expanded=False):
        opcoes_bench = ["Ibovespa", "IFIX", "S&P 500", "NASDAQ", "SMLL (Small Caps)", "Ouro", "IPCA + Taxa", "CDI (Percentual)", "Selic"]
        benchmarks_sel = st.multiselect("Selecione os Benchmarks de Comparação:", opcoes_bench, default=["Ibovespa"])
        
        taxa_ipca_bench, taxa_cdi_bench = 0.06, 1.0
        if "IPCA + Taxa" in benchmarks_sel:
            taxa_ipca_bench = st.number_input("Taxa Fixa do IPCA+ (%)", value=6.0, step=0.1) / 100
        if "CDI (Percentual)" in benchmarks_sel:
            taxa_cdi_bench = st.number_input("Percentual do CDI (%)", value=100.0, step=1.0) / 100
            
        st.markdown("<hr style='margin:10px 0; opacity: 0.3;'>", unsafe_allow_html=True)
        taxas_personalizadas = st.checkbox("Deseja taxas personalizadas?")
        c_taxa1, c_taxa2 = st.columns(2)
        
        if taxas_personalizadas:
            cdi_base = c_taxa1.number_input("CDI Base Global (%)", value=cdi_auto*100, step=0.1, help="Taxa livre de risco") / 100
            ipca_base = c_taxa2.number_input("IPCA Base Global (%)", value=ipca_auto*100, step=0.1, help="Inflação base") / 100
        else:
            c_taxa1.number_input("CDI Atual BCB (%)", value=cdi_auto*100, disabled=True, help="Taxa diária anualizada puxada hoje do Banco Central")
            c_taxa2.number_input("IPCA Atual BCB (%)", value=ipca_auto*100, disabled=True, help="Inflação acumulada dos últimos 12 meses puxada do Banco Central")
            cdi_base, ipca_base = cdi_auto, ipca_auto
            
        reinvestir = st.checkbox("Reinvestir Dividendos na Carteira Principal", value=True)
        
    with st.expander("💾 Salvar Trabalho & Comparar", expanded=False):
        st.markdown("<span style='font-size:0.85em; opacity:0.8;'>**O SEU SAVE:** Copie o código abaixo para salvar o trabalho ou compartilhar.</span>", unsafe_allow_html=True)
        codigo_export = exportar_codigo_carteira(st.session_state.carteira)
        st.code(codigo_export if codigo_export else "Adicione ativos para gerar.")
        
        st.markdown("<hr style='margin:10px 0;'>", unsafe_allow_html=True)
        st.markdown("<span style='font-size:0.85em; opacity:0.8;'>**COMPARAR:** Cole o código de outra pessoa abaixo para bater as metas.</span>", unsafe_allow_html=True)
        codigo_import = st.text_input("Código de Comparação:")
        reinvestir_comp = st.checkbox("Reinvestir Div. (Carteira Importada)", value=True)
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
        st.warning("⚠️ Ativos listados na B3 exigem o final **.SA** (ex: VALE3.SA).")
        c_rv1, c_rv2 = st.columns(2)
        ticker = c_rv1.text_input("Ticker", help="Ex: PETR4.SA").upper().strip()
        aporte_val = c_rv2.number_input("Peso/Valor", min_value=1.0, value=10.0 if modo_aporte=="Por Peso (%)" else 1000.0)
        setor_rv = st.selectbox("Setor do Ativo (Opcional)", OPCOES_SETORES)
        comprado_inicio_rv = st.checkbox("Desde o Início?", value=True, key="chk_rv")
        data_compra_rv = data_inicio if comprado_inicio_rv else st.date_input("Comprado em", value=data_inicio, min_value=data_inicio, max_value=datetime.today(), key="dt_rv")
        
        if st.button("Inserir Renda Variável") and ticker:
            st.session_state.carteira[ticker] = {'tipo': 'RV', 'aporte': aporte_val, 'data_compra': data_compra_rv, 'setor': setor_rv}
            st.session_state['carteira_alterada'] = True
            st.rerun()
    else:
        nome_rf = st.text_input("Nome do Título").strip()
        c_rf1, c_rf2, c_rf3 = st.columns([1.5, 1.5, 1])
        tipo_rf = c_rf1.selectbox("Indexador", ["Prefixado", "CDI", "IPCA+"])
        
        if tipo_rf == "CDI":
            menos_100 = c_rf1.checkbox("Menos de 100% do CDI?")
            if menos_100:
                taxa_input = c_rf2.number_input("Taxa (% do CDI)", value=90.0, step=1.0)
                taxa = taxa_input / 100
            else:
                taxa_input = c_rf2.number_input("100% + qual %? (Ex: 10 = 110%)", value=10.0, step=1.0)
                taxa = (100 + taxa_input) / 100
        elif tipo_rf == "IPCA+":
            taxa_input = c_rf2.number_input("Qual o + do IPCA? (%)", value=6.0, step=0.1, help="Insira apenas a taxa fixa acima do IPCA. Ex: 6.0 para IPCA+6%")
            taxa = taxa_input / 100
        else:
            taxa_input = c_rf2.number_input("Taxa Prefixada ao ano (%)", value=10.0, step=0.1)
            taxa = taxa_input / 100
            
        aporte_val_rf = c_rf3.number_input("Peso/Valor", min_value=1.0, value=10.0 if modo_aporte=="Por Peso (%)" else 1000.0)
        comprado_inicio_rf = st.checkbox("Desde o Início?", value=True, key="chk_rf")
        data_compra_rf = data_inicio if comprado_inicio_rf else st.date_input("Aplicado em", value=data_inicio, min_value=data_inicio, max_value=datetime.today(), key="dt_rf")
        
        if st.button("Inserir Renda Fixa") and nome_rf:
            st.session_state.carteira[nome_rf] = {'tipo': 'RF', 'indexador': tipo_rf, 'taxa': taxa, 'aporte': aporte_val_rf, 'data_compra': data_compra_rf}
            st.session_state['carteira_alterada'] = True
            st.rerun()
            
    if st.button("🗑️ Limpar Carteira Principal"):
        st.session_state.carteira = {}
        st.session_state['carteira_alterada'] = True
        st.rerun()

# --- 4. TELA PRINCIPAL ---
st.title("🏛️ LMF - ASSET")

if not st.session_state.get('carteira_alterada', False):
    st.markdown("""
    <div style="background-color: rgba(212, 175, 55, 0.1); border-left: 5px solid #D4AF37; padding: 15px; border-radius: 5px; margin-bottom: 20px;">
        <h4 style="color: #D4AF37; margin-top: 0;">📌 Diretrizes Operacionais do Sistema</h4>
        Para garantir a precisão da extração de dados, utilize o sufixo <b>.SA</b> em ativos da B3 (ex: PETR4.SA), enquanto ativos globais recebem o ticker original. A data inicial do fundo não deve anteceder o IPO dos ativos selecionados para manter a coesão matemática do VaR e da Fronteira Eficiente. Na seleção de Renda Fixa, siga as instruções dinâmicas de cada indexador para garantir o cálculo preciso dos juros.
    </div>
    """, unsafe_allow_html=True)

if not st.session_state.carteira:
    st.info("👋 Sua carteira está vazia. Utilize a barra lateral para adicionar ativos e iniciar as análises de portfólio.")
else:
    with st.spinner("Sincronizando Mercado Global e Processando Modelagens..."):
        ativos_rv_principal = [k for k, v in st.session_state.carteira.items() if v['tipo'] == 'RV']
        ativos_rv_comp = [k for k, v in st.session_state.carteira_comparacao.items() if v['tipo'] == 'RV']
        
        mapa_bench = {"Ibovespa": "^BVSP", "IFIX": "XFIX11.SA", "S&P 500": "^GSPC", "NASDAQ": "^IXIC", "SMLL (Small Caps)": "SMAL11.SA", "Ouro": "GC=F"}
        tickers_bench_b3 = [mapa_bench[b] for b in benchmarks_sel if b in mapa_bench]
        
        todos_ativos_rv = list(set(ativos_rv_principal + ativos_rv_comp + tickers_bench_b3))
        
        df_rv_com = fetch_market_data(todos_ativos_rv, data_inicio, adj_close=True)
        df_rv_sem = fetch_market_data(todos_ativos_rv, data_inicio, adj_close=False) 
        
        if not df_rv_com.empty:
            idx_mestre = df_rv_com.dropna(how='all').index
        else:
            idx_mestre = pd.bdate_range(start=data_inicio, end=datetime.today())
            
        if len(idx_mestre) == 0:
            idx_mestre = pd.bdate_range(start=data_inicio, end=datetime.today())
            
        cdi_series = fetch_br_indicators(12, data_inicio)
        selic_series = fetch_br_indicators(11, data_inicio)
        ipca_series = fetch_br_indicators(433, data_inicio)
        
        cdi_aligned = cdi_series.reindex(idx_mestre).fillna(0) if not cdi_series.empty else pd.Series((1 + 0.105)**(1/252) - 1, index=idx_mestre)
        selic_aligned = selic_series.reindex(idx_mestre).fillna(0) if not selic_series.empty else pd.Series((1 + 0.105)**(1/252) - 1, index=idx_mestre)
        
        if ipca_series.empty: ipca_daily_aligned = pd.Series((1 + 0.045)**(1/252) - 1, index=idx_mestre)
        else:
            ipca_daily_val = (1 + ipca_series)**(1/21) - 1
            ipca_daily_aligned = ipca_daily_val.reindex(pd.date_range(start=ipca_daily_val.index.min(), end=datetime.today())).ffill().reindex(idx_mestre).fillna(0)

        dict_ret_benchs = {}
        for b in benchmarks_sel:
            if b == "CDI (Percentual)": dict_ret_benchs[b] = cdi_aligned * taxa_cdi_bench
            elif b == "Selic": dict_ret_benchs[b] = selic_aligned
            elif b == "IPCA + Taxa": dict_ret_benchs[b] = (1 + ipca_daily_aligned) * (1 + taxa_ipca_bench)**(1/252) - 1
            elif b in mapa_bench:
                tb = mapa_bench[b]
                dict_ret_benchs[b] = df_rv_com[tb].reindex(idx_mestre).ffill().pct_change().fillna(0) if tb in df_rv_com.columns else pd.Series(0, index=idx_mestre)
        
        nome_bench_principal = benchmarks_sel[0] if benchmarks_sel else "Benchmark Padrão"
        ret_bench_principal = dict_ret_benchs[nome_bench_principal] if benchmarks_sel else pd.Series(0, index=idx_mestre)

        ret_port_com, ret_port_sem = processar_carteira(st.session_state.carteira, df_rv_com, df_rv_sem, cdi_aligned, ipca_daily_aligned, idx_mestre, reinvestir)
        ret_portfolio_principal = ret_port_com if reinvestir else ret_port_sem
        
        if st.session_state.carteira_comparacao:
            ret_comp_com, ret_comp_sem = processar_carteira(st.session_state.carteira_comparacao, df_rv_com, df_rv_sem, cdi_aligned, ipca_daily_aligned, idx_mestre, reinvestir_comp)
            ret_portfolio_comparacao = ret_comp_com if reinvestir_comp else ret_comp_sem

        aportes_brutos = np.array([v['aporte'] for v in st.session_state.carteira.values()])
        capital_inicial = aportes_brutos.sum() if modo_aporte == "Por Valor Financeiro (R$)" else capital_inicial_input
        pesos_norm = aportes_brutos / aportes_brutos.sum() if aportes_brutos.sum() > 0 else aportes_brutos * 0

        # --- SEÇÃO 1: COMPOSIÇÃO ---
        st.header("🛒 Posições e Alocação")
        c_lista, c_grafico = st.columns([1, 1.5])
        with c_lista:
            for i, (t, config) in enumerate(st.session_state.carteira.items()):
                c1, c2, c3 = st.columns([3, 1, 1])
                dt_c = config['data_compra'].strftime('%d/%m/%y')
                setor_str = config.get('setor', 'Não Informado') if config['tipo'] == 'RV' else 'Renda Fixa'
                info_alocacao = f"{formatar_moeda(config['aporte'])} ({pesos_norm[i]:.1%})" if modo_aporte == "Por Valor Financeiro (R$)" else f"{pesos_norm[i]:.1%}"
                c1.markdown(f"**{t}** *(Início: {dt_c} | {setor_str})*")
                c2.markdown(info_alocacao)
                if c3.button("❌", key=f"del_{t}"):
                    del st.session_state.carteira[t]
                    st.session_state['carteira_alterada'] = True
                    st.rerun()
                    
        with c_grafico:
            if len(st.session_state.carteira) > 0:
                visao_grafico = st.radio("Visualizar Alocação por:", ["Ativos", "Setores"], horizontal=True)
                if visao_grafico == "Ativos":
                    df_pizza = pd.DataFrame({'Ativo': list(st.session_state.carteira.keys()), 'Peso': pesos_norm})
                    fig = px.pie(df_pizza, values='Peso', names='Ativo', hole=0.5)
                else:
                    setores_lista = [v.get('setor', 'Não Informado') if v['tipo'] == 'RV' else 'Renda Fixa' for v in st.session_state.carteira.values()]
                    df_pizza = pd.DataFrame({'Setor': setores_lista, 'Peso': pesos_norm})
                    df_pizza = df_pizza.groupby('Setor', as_index=False).sum()
                    fig = px.pie(df_pizza, values='Peso', names='Setor', hole=0.5)
                
                fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', font=dict(color='#D4AF37'), margin=dict(t=0, b=0, l=0, r=0))
                st.plotly_chart(fig, use_container_width=True)

        st.markdown("---")

        # --- SEÇÃO 2: MÉTRICAS GLOBAIS ---
        st.header("📊 Resumo de Desempenho (Carteira Completa)")
        m_prin = calcular_metricas(ret_portfolio_principal, ret_bench_principal, cdi_aligned)
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Rentabilidade Acumulada", f"{m_prin[0]:.2%}")
        c2.metric("Alpha de Jensen", f"{m_prin[7]:.2%}")
        c3.metric("Índice Sharpe", f"{m_prin[2]:.2f}")
        c4.metric("Índice Sortino", f"{m_prin[3]:.2f}")
        
        c5, c6, c7, c8 = st.columns(4)
        c5.metric("Volatilidade Anual", f"{m_prin[1]:.2%}")
        c6.metric("Max Drawdown", f"{m_prin[4]:.2%}")
        c7.metric("VaR (95%)", f"{m_prin[5]:.2%}")
        c8.metric(f"Beta vs {nome_bench_principal}", f"{m_prin[6]:.2f}")

        st.markdown("---")
        
        # --- ABAS DE ANÁLISE ---
        abas_nomes = ["📈 Rentabilidade Global", "⚙️ Estudo das Métricas"]
        if st.session_state.carteira_comparacao: abas_nomes.append("🆚 Análise de Comparação")
        abas_nomes.extend(["🔍 Análise Fundamentalista", "🕯️ Candlestick (Ativos)"])
        
        tabs = st.tabs(abas_nomes)
        
        tab_idx = 0
        with tabs[tab_idx]: # Rentabilidade Global
            c_rent_title, c_rent_filt = st.columns([2, 1])
            c_rent_title.markdown("Comparativo de rentabilidade contra os múltiplos benchmarks.")
            
            setores_presentes_rent = list(set([v.get('setor', 'Não Informado') if v['tipo'] == 'RV' else 'Renda Fixa' for v in st.session_state.carteira.values()]))
            if st.session_state.carteira_comparacao:
                setores_presentes_rent.extend(list(set([v.get('setor', 'Não Informado') if v['tipo'] == 'RV' else 'Renda Fixa' for v in st.session_state.carteira_comparacao.values()])))
                setores_presentes_rent = list(set(setores_presentes_rent))
                
            setor_filtro_rent = c_rent_filt.selectbox("Filtrar por Setor (Gráfico):", ["Carteira Completa"] + setores_presentes_rent, key="filt_rent")
            
            df_grafico = pd.DataFrame(index=idx_mestre)
            
            if setor_filtro_rent != "Carteira Completa":
                ret_rent_com, ret_rent_sem = processar_carteira(st.session_state.carteira, df_rv_com, df_rv_sem, cdi_aligned, ipca_daily_aligned, idx_mestre, reinvestir, setor_filter=setor_filtro_rent)
                ret_rent = ret_rent_com if reinvestir else ret_rent_sem
                df_grafico[f"Sua Carteira - {setor_filtro_rent} (%)"] = ((1 + ret_rent).cumprod() - 1) * 100
                color_map = {f"Sua Carteira - {setor_filtro_rent} (%)": "#D4AF37"}
                
                if st.session_state.carteira_comparacao:
                    ret_rent_comp_com, ret_rent_comp_sem = processar_carteira(st.session_state.carteira_comparacao, df_rv_com, df_rv_sem, cdi_aligned, ipca_daily_aligned, idx_mestre, reinvestir_comp, setor_filter=setor_filtro_rent)
                    ret_rent_comp = ret_rent_comp_com if reinvestir_comp else ret_rent_comp_sem
                    df_grafico[f"Comparação - {setor_filtro_rent} (%)"] = ((1 + ret_rent_comp).cumprod() - 1) * 100
                    color_map[f"Comparação - {setor_filtro_rent} (%)"] = "#00BFFF"
            else:
                df_grafico["Sua Carteira (%)"] = ((1 + ret_portfolio_principal).cumprod() - 1) * 100
                color_map = {"Sua Carteira (%)": "#D4AF37"}
                if st.session_state.carteira_comparacao:
                    df_grafico["Carteira Comparação (%)"] = ((1 + ret_portfolio_comparacao).cumprod() - 1) * 100
                    color_map["Carteira Comparação (%)"] = "#00BFFF"
            
            for nome_bench, serie_bench in dict_ret_benchs.items():
                df_grafico[f"{nome_bench} (%)"] = ((1 + serie_bench).cumprod() - 1) * 100
                
            fig_rent = px.line(df_grafico, color_discrete_map=color_map)
            fig_rent.update_layout(xaxis_title="", yaxis_title="Acumulado (%)", xaxis=dict(tickformat="%b %Y", dtick="M3"), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color='#D4AF37'))
            st.plotly_chart(fig_rent, use_container_width=True)

        tab_idx += 1
        with tabs[tab_idx]: # Estudo das Métricas
            c_estudo, c_filtro = st.columns(2)
            metrica_sel = c_estudo.selectbox("Selecione o Estudo (Sua Carteira):", ["Fronteira Eficiente (Markowitz)", "Value at Risk (VaR)", "Drawdown Histórico", "Volatilidade Rolante", "Beta (Risco de Mercado)"])
            
            setores_presentes = list(set([v.get('setor', 'Não Informado') if v['tipo'] == 'RV' else 'Renda Fixa' for v in st.session_state.carteira.values()]))
            setor_filtro = c_filtro.selectbox("Filtrar por Setor:", ["Carteira Completa"] + setores_presentes)
            
            if setor_filtro != "Carteira Completa":
                ret_estudo_com, ret_estudo_sem = processar_carteira(st.session_state.carteira, df_rv_com, df_rv_sem, cdi_aligned, ipca_daily_aligned, idx_mestre, reinvestir, setor_filter=setor_filtro)
                ret_estudo = ret_estudo_com if reinvestir else ret_estudo_sem
                dict_estudo = {k: v for k, v in st.session_state.carteira.items() if (v.get('setor', 'Não Informado') if v['tipo'] == 'RV' else 'Renda Fixa') == setor_filtro}
            else:
                ret_estudo = ret_portfolio_principal
                dict_estudo = st.session_state.carteira

            janela = 252 
            df_roll = pd.DataFrame(index=idx_mestre)
            
            if metrica_sel == "Fronteira Eficiente (Markowitz)":
                plot_markowitz(dict_estudo, df_rv_com, df_rv_sem, cdi_aligned, idx_mestre, reinvestir)
            elif metrica_sel == "Value at Risk (VaR)":
                tipo_var = st.radio("Selecione a visualização do VaR:", ["Histograma de Retornos (Estático)", "VaR Histórico Rolante"], horizontal=True)
                if tipo_var == "Histograma de Retornos (Estático)":
                    plot_var_histogram(ret_estudo, f"Distribuição de Retornos ({setor_filtro})")
                else:
                    df_roll[f"VaR 5% ({setor_filtro})"] = ret_estudo.rolling(janela).quantile(0.05)
                    fig_var = px.line(df_roll.dropna(), color_discrete_sequence=["#D4AF37"])
                    fig_var.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color='#D4AF37'))
                    st.plotly_chart(fig_var, use_container_width=True)
            elif metrica_sel == "Drawdown Histórico":
                df_roll[f"{setor_filtro} (%)"] = (((1 + ret_estudo).cumprod() / (1 + ret_estudo).cumprod().cummax()) - 1) * 100
                fig_dd = px.line(df_roll.dropna(), color_discrete_sequence=["#D4AF37"])
                fig_dd.update_traces(fill='tozeroy') 
                fig_dd.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color='#D4AF37'))
                st.plotly_chart(fig_dd, use_container_width=True)
            elif metrica_sel == "Volatilidade Rolante":
                df_roll[f"{setor_filtro} (%)"] = ret_estudo.rolling(janela).std() * np.sqrt(252) * 100
                df_roll[f"{nome_bench_principal} (%)"] = ret_bench_principal.rolling(janela).std() * np.sqrt(252) * 100
                fig_vol = px.line(df_roll.dropna(), color_discrete_sequence=["#D4AF37", "#555555"])
                fig_vol.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color='#D4AF37'))
                st.plotly_chart(fig_vol, use_container_width=True)
            elif metrica_sel == "Beta (Risco de Mercado)":
                var_bench = ret_bench_principal.rolling(janela).var()
                var_bench = var_bench.where(var_bench > 1e-8, np.nan)
                df_roll[f"Beta ({setor_filtro})"] = ret_estudo.rolling(janela).cov(ret_bench_principal) / var_bench
                
                df_plot = df_roll.dropna()
                if df_plot.empty:
                    st.warning(f"O benchmark atual ({nome_bench_principal}) não possui volatilidade suficiente para o cálculo de Beta (Risco de Mercado é exclusivo para renda variável).")
                else:
                    fig_beta = px.line(df_plot, color_discrete_sequence=["#D4AF37"])
                    fig_beta.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color='#D4AF37'))
                    st.plotly_chart(fig_beta, use_container_width=True)

        if st.session_state.carteira_comparacao:
            tab_idx += 1
            with tabs[tab_idx]: # Análise Comparação
                m_comp = calcular_metricas(ret_portfolio_comparacao, ret_bench_principal, cdi_aligned)
                st.markdown("### 🏆 Confronto Direto de Métricas (Carteiras Completas)")
                r_p, r_c, win_r = compara_metrica(m_prin[0], m_comp[0], True, True)
                a_p, a_c, win_a = compara_metrica(m_prin[7], m_comp[7], True, True)
                s_p, s_c, win_s = compara_metrica(m_prin[2], m_comp[2], True, False)
                v_p, v_c, win_v = compara_metrica(m_prin[1], m_comp[1], False, True)
                d_p, d_c, win_d = compara_metrica(m_prin[4], m_comp[4], True, True) 
                
                st.markdown(f"""
                <table>
                    <tr><th>Métrica</th><th>Sua Carteira</th><th>Carteira Importada</th><th>Vencedor</th></tr>
                    <tr><td>Retorno Acumulado</td><td>{r_p}</td><td>{r_c}</td><td>{win_r}</td></tr>
                    <tr><td>Alpha de Jensen</td><td>{a_p}</td><td>{a_c}</td><td>{win_a}</td></tr>
                    <tr><td>Índice Sharpe</td><td>{s_p}</td><td>{s_c}</td><td>{win_s}</td></tr>
                    <tr><td>Volatilidade Anual</td><td>{v_p}</td><td>{v_c}</td><td>{win_v}</td></tr>
                    <tr><td>Drawdown Máximo</td><td>{d_p}</td><td>{d_c}</td><td>{win_d}</td></tr>
                </table>
                """, unsafe_allow_html=True)
                
                st.markdown("### 📈 Estudo Profundo (Carteira Importada)")
                c_est_c, c_filt_c = st.columns(2)
                est_comp = c_est_c.selectbox("Análise Específica do Colega:", ["Fronteira Eficiente (Markowitz)", "Value at Risk (VaR)", "Drawdown Histórico", "Volatilidade Rolante", "Beta (Risco de Mercado)"])
                
                setores_presentes_comp = list(set([v.get('setor', 'Não Informado') if v['tipo'] == 'RV' else 'Renda Fixa' for v in st.session_state.carteira_comparacao.values()]))
                setor_filtro_comp = c_filt_c.selectbox("Filtrar por Setor (Importada):", ["Carteira Completa"] + setores_presentes_comp)
                
                if setor_filtro_comp != "Carteira Completa":
                    ret_estudo_comp_com, ret_estudo_comp_sem = processar_carteira(st.session_state.carteira_comparacao, df_rv_com, df_rv_sem, cdi_aligned, ipca_daily_aligned, idx_mestre, reinvestir_comp, setor_filter=setor_filtro_comp)
                    ret_estudo_comp = ret_estudo_comp_com if reinvestir_comp else ret_estudo_comp_sem
                    dict_estudo_comp = {k: v for k, v in st.session_state.carteira_comparacao.items() if (v.get('setor', 'Não Informado') if v['tipo'] == 'RV' else 'Renda Fixa') == setor_filtro_comp}
                else:
                    ret_estudo_comp = ret_portfolio_comparacao
                    dict_estudo_comp = st.session_state.carteira_comparacao
                
                df_roll_comp = pd.DataFrame(index=idx_mestre)
                janela = 252

                if est_comp == "Fronteira Eficiente (Markowitz)":
                    plot_markowitz(dict_estudo_comp, df_rv_com, df_rv_sem, cdi_aligned, idx_mestre, reinvestir_comp)
                
                elif est_comp == "Value at Risk (VaR)":
                    tipo_var_comp = st.radio("Selecione a visualização do VaR (Importada):", ["Histograma de Retornos (Estático)", "VaR Histórico Rolante"], horizontal=True)
                    if tipo_var_comp == "Histograma de Retornos (Estático)":
                        plot_var_histogram(ret_estudo_comp, f"Distribuição de Retornos (Importada - {setor_filtro_comp})", "#00BFFF")
                    else:
                        df_roll_comp[f"VaR 5% ({setor_filtro_comp})"] = ret_estudo_comp.rolling(janela).quantile(0.05)
                        fig_var_c = px.line(df_roll_comp.dropna(), color_discrete_sequence=["#00BFFF"])
                        fig_var_c.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color='#D4AF37'))
                        st.plotly_chart(fig_var_c, use_container_width=True)
                
                elif est_comp == "Drawdown Histórico":
                    df_roll_comp[f"Importada ({setor_filtro_comp}) %"] = (((1 + ret_estudo_comp).cumprod() / (1 + ret_estudo_comp).cumprod().cummax()) - 1) * 100
                    fig_dd_c = px.line(df_roll_comp.dropna(), color_discrete_sequence=["#00BFFF"])
                    fig_dd_c.update_traces(fill='tozeroy') 
                    fig_dd_c.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color='#D4AF37'))
                    st.plotly_chart(fig_dd_c, use_container_width=True)
                
                elif est_comp == "Volatilidade Rolante":
                    df_roll_comp[f"Importada ({setor_filtro_comp}) %"] = ret_estudo_comp.rolling(janela).std() * np.sqrt(252) * 100
                    df_roll_comp[f"{nome_bench_principal} (%)"] = ret_bench_principal.rolling(janela).std() * np.sqrt(252) * 100
                    fig_vol_c = px.line(df_roll_comp.dropna(), color_discrete_sequence=["#00BFFF", "#555555"])
                    fig_vol_c.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color='#D4AF37'))
                    st.plotly_chart(fig_vol_c, use_container_width=True)
                
                elif est_comp == "Beta (Risco de Mercado)":
                    var_bench = ret_bench_principal.rolling(janela).var()
                    var_bench = var_bench.where(var_bench > 1e-8, np.nan)
                    df_roll_comp[f"Beta ({setor_filtro_comp})"] = ret_estudo_comp.rolling(janela).cov(ret_bench_principal) / var_bench
                    
                    df_plot_c = df_roll_comp.dropna()
                    if df_plot_c.empty:
                        st.warning(f"O benchmark atual ({nome_bench_principal}) não possui volatilidade suficiente para o cálculo de Beta (Risco de Mercado é exclusivo para renda variável).")
                    else:
                        fig_beta_c = px.line(df_plot_c, color_discrete_sequence=["#00BFFF"])
                        fig_beta_c.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color='#D4AF37'))
                        st.plotly_chart(fig_beta_c, use_container_width=True)
                
                st.markdown("### 🔎 RX dos Ativos Importados")
                st.write(f"Cálculo de Dividendos: **{'Reinvestidos' if reinvestir_comp else 'Não Reinvestidos'}**")
                for t, config in st.session_state.carteira_comparacao.items():
                    ret_ind = calcular_retorno_individual(t, config, df_rv_com, df_rv_sem, cdi_aligned, ipca_daily_aligned, idx_mestre, reinvestir_comp)
                    cc1, cc2, cc3 = st.columns([2, 1, 1])
                    setor_c = config.get('setor', 'Não Informado') if config['tipo'] == 'RV' else 'Renda Fixa'
                    cc1.markdown(f"**{t}** *(Setor: {setor_c})*")
                    cc2.markdown(f"Peso Inicial: **{formatar_moeda(config['aporte']) if modo_aporte == 'Por Valor Financeiro (R$)' else str(config['aporte']) + '%'}**")
                    cc3.markdown(f"Desempenho: **<span style='color:{'#00FF00' if ret_ind >= 0 else '#FF0000'}'>{formatar_percentual(ret_ind)}</span>**", unsafe_allow_html=True)
                    st.divider()

        tab_idx += 1
        with tabs[tab_idx]: # Análise Fundamentalista
            if not ativos_rv_principal:
                st.warning("Adicione ativos de Renda Variável na carteira principal para visualizar a análise fundamentalista.")
            else:
                ativo_fund = st.selectbox("Selecione o Ativo para Análise Fundamentalista:", ativos_rv_principal)
                if ativo_fund:
                    with st.spinner(f"Extraindo dados fundamentalistas de {ativo_fund}..."):
                        info = fetch_fundamental_info(ativo_fund)
                        
                        if not info or ('trailingPE' not in info and 'marketCap' not in info and 'priceToBook' not in info):
                            st.warning(f"Dados fundamentalistas não estão disponíveis na API global para o ativo {ativo_fund} no momento.")
                        else:
                            st.markdown(f"### 📊 Raio-X Fundamentalista: {ativo_fund}")
                            st.markdown("---")
                            
                            st.subheader("💰 Valuation & Preço", divider='gray')
                            v1, v2, v3, v4 = st.columns(4)
                            v1.metric("P/L (Preço/Lucro)", formatar_float(info.get('trailingPE')))
                            v2.metric("P/VP (Preço/Valor Patrimonial)", formatar_float(info.get('priceToBook')))
                            v3.metric("Dividend Yield (DY)", formatar_pct_api(info.get('dividendYield')))
                            v4.metric("PEG Ratio", formatar_float(info.get('pegRatio')))
                            
                            st.subheader("📈 Rentabilidade & Eficiência", divider='gray')
                            r1, r2, r3, r4 = st.columns(4)
                            r1.metric("ROE (Retorno s/ Patrimônio)", formatar_pct_api(info.get('returnOnEquity')))
                            r2.metric("ROA (Retorno s/ Ativos)", formatar_pct_api(info.get('returnOnAssets')))
                            r3.metric("Margem Líquida", formatar_pct_api(info.get('profitMargins')))
                            r4.metric("Margem Bruta", formatar_pct_api(info.get('grossMargins')))
                            
                            st.subheader("🏛️ Saúde Financeira & Estrutura", divider='gray')
                            s1, s2, s3, s4 = st.columns(4)
                            s1.metric("Liquidez Corrente", formatar_float(info.get('currentRatio')))
                            s2.metric("Dívida/Patrimônio", formatar_float(info.get('debtToEquity', 0) / 100 if info.get('debtToEquity') else None))
                            s3.metric("LPA (Lucro por Ação)", formatar_float(info.get('trailingEps')))
                            s4.metric("Valor de Mercado", formatar_abrev(info.get('marketCap')))

        tab_idx += 1
        with tabs[tab_idx]: # Candlestick
            ativo_candle = st.selectbox("Ativo (Gráfico de Preço):", [t for t in ativos_rv_principal])
            if ativo_candle:
                df_ohlc = yf.download(ativo_candle, start=data_inicio, progress=False)
                if not df_ohlc.empty:
                    o = df_ohlc['Open'].squeeze()
                    h = df_ohlc['High'].squeeze()
                    l = df_ohlc['Low'].squeeze()
                    c = df_ohlc['Close'].squeeze()
                    fig_c = go.Figure(data=[go.Candlestick(x=df_ohlc.index, open=o, high=h, low=l, close=c)])
                    fig_c.update_layout(
                        paper_bgcolor='rgba(0,0,0,0)', 
                        plot_bgcolor='rgba(0,0,0,0)', 
                        font=dict(color='#D4AF37'),
                        xaxis_title="Data",
                        yaxis_title="Cotação / Preço",
                        xaxis_rangeslider_visible=False
                    )
                    st.plotly_chart(fig_c, use_container_width=True)

        if st.button("🖨️ Salvar Relatório em PDF", use_container_width=True):
            components.html("<script>window.parent.print();</script>", height=0)
        st.markdown(f"<div style='text-align:right; color:#D4AF37; opacity:0.6'>Idealizado por Bernardo V.</div>", unsafe_allow_html=True)
