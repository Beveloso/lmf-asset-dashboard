import streamlit as st
import streamlit.components.v1 as components
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from dataclasses import dataclass
import json
import base64
import re
import logging

# Configuração Básica de Logs
logging.basicConfig(level=logging.ERROR)

# --- 1. DEFINIÇÃO DE ESTRUTURAS DE DADOS (SAÚDE DO CÓDIGO) ---
@dataclass
class AtivoRV:
    ticker: str
    aporte: float
    data_compra: datetime.date
    setor: str = "Outros"
    tipo: str = "RV"

@dataclass
class AtivoRF:
    nome: str
    indexador: str  
    taxa: float      
    aporte: float
    data_compra: datetime.date
    data_vencimento: datetime.date = None
    tipo: str = "RF"

# --- 2. CONFIGURAÇÃO VISUAL E EXPORTAÇÃO DE GRÁFICOS ---
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
    
    /* Magia Negra do CSS para Impressão: Esconde botões e barras no PDF */
    @media print {
        section[data-testid="stSidebar"] { display: none !important; }
        header[data-testid="stHeader"] { display: none !important; }
        div[data-testid="stToolbar"] { display: none !important; }
        .stButton { display: none !important; }
        .stTabs { display: none !important; }
    }
    </style>
""", unsafe_allow_html=True)

# Configuração de Alta Resolução para Slides (Plotly)
PLOTLY_CONFIG = {
    'displayModeBar': True,
    'displaylogo': False,
    'modeBarButtonsToRemove': ['lasso2d', 'select2d'],
    'toImageButtonOptions': {
        'format': 'png',
        'filename': 'LMF_Asset_Export',
        'height': 720,
        'width': 1280,
        'scale': 2 
    }
}

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
    if valor is None or pd.isna(valor) or valor == 0: return "N/A"
    val = float(valor)
    if val > 10: return f"{val:.2f}%" 
    return f"{val*100:.2f}%"

def formatar_dy(valor):
    if valor is None or pd.isna(valor) or valor == 0: return "N/A"
    val = float(valor)
    if val > 1: return f"{val:.2f}%" 
    return f"{val*100:.2f}%"

def formatar_abrev(valor):
    if valor is None or pd.isna(valor) or valor == 0: return "N/A"
    try:
        val = float(valor)
        if val >= 1e9: return f"{val/1e9:.2f} B"
        if val >= 1e6: return f"{val/1e6:.2f} M"
        return f"{val:.2f}"
    except: return "N/A"

def dataclass_to_dict(obj):
    if isinstance(obj, (AtivoRV, AtivoRF)):
        data = obj.__dict__.copy()
        if 'data_compra' in data and data['data_compra']:
            data['data_compra'] = data['data_compra'].strftime('%Y-%m-%d')
        if 'data_vencimento' in data and data['data_vencimento']:
            data['data_vencimento'] = data['data_vencimento'].strftime('%Y-%m-%d')
        return data
    return obj

def exportar_codigo_carteira(carteira_dict, nome_carteira):
    if not carteira_dict: return ""
    cart_export = {}
    for k, v in carteira_dict.items():
        if hasattr(v, '__dict__'):
            v_copy = v.__dict__.copy()
        else:
            v_copy = dict(v)
            
        if 'data_compra' in v_copy and v_copy['data_compra'] is not None:
            if hasattr(v_copy['data_compra'], 'strftime'):
                v_copy['data_compra'] = v_copy['data_compra'].strftime('%Y-%m-%d')
            else:
                v_copy['data_compra'] = str(v_copy['data_compra'])
                
        if 'data_vencimento' in v_copy and v_copy['data_vencimento'] is not None:
            if hasattr(v_copy['data_vencimento'], 'strftime'):
                v_copy['data_vencimento'] = v_copy['data_vencimento'].strftime('%Y-%m-%d')
            else:
                v_copy['data_vencimento'] = str(v_copy['data_vencimento'])
                
        cart_export[k] = v_copy
    
    cart_export['__meta_nome__'] = nome_carteira
    json_str = json.dumps(cart_export)
    return base64.b64encode(json_str.encode('utf-8')).decode('utf-8')

def importar_codigo_carteira(codigo_b64):
    try:
        json_str = base64.b64decode(codigo_b64.encode('utf-8')).decode('utf-8')
        cart_bruto = json.loads(json_str)
        nome_importado = cart_bruto.pop('__meta_nome__', 'Carteira Importada')
        
        cart = {}
        for k, v in cart_bruto.items():
            dt_compra = datetime.strptime(v['data_compra'], '%Y-%m-%d').date()
            if v['tipo'] == 'RV':
                cart[k] = AtivoRV(ticker=v['ticker'], aporte=v['aporte'], data_compra=dt_compra, setor=v['setor'])
            else:
                dt_venc = datetime.strptime(v['data_vencimento'], '%Y-%m-%d').date() if v.get('data_vencimento') else None
                cart[k] = AtivoRF(nome=v['nome'], indexador=v['indexador'], taxa=v['taxa'], aporte=v['aporte'], data_compra=dt_compra, data_vencimento=dt_venc)
        return cart, nome_importado
    except Exception as e:
        logging.error(f"Erro na importação: {e}")
        return None, "Carteira Importada"

def ativar_modo_impressao():
    st.session_state['modo_impressao'] = True

def desativar_modo_impressao():
    st.session_state['modo_impressao'] = False

# --- INICIALIZAÇÃO DE ESTADOS ---
if 'started' not in st.session_state:
    st.session_state['started'] = False
    st.session_state['carteira_alterada'] = False
    st.session_state['carteira'] = {}
    st.session_state['carteira_comparacao'] = {}
    st.session_state['modo_impressao'] = False

if 'rel_comp' not in st.session_state: st.session_state['rel_comp'] = True
if 'rel_metr' not in st.session_state: st.session_state['rel_metr'] = True
if 'rel_rent' not in st.session_state: st.session_state['rel_rent'] = True
if 'rel_rx' not in st.session_state: st.session_state['rel_rx'] = False
    
if 'nome_carteira' not in st.session_state:
    st.session_state['nome_carteira'] = "Minha Carteira"
if 'nome_carteira_comparacao' not in st.session_state:
    st.session_state['nome_carteira_comparacao'] = "Carteira Importada"

OPCOES_SETORES = [
    "Outros", "Consumo Cíclico", "Consumo não Cíclico", "Utilidade Pública",
    "Bens Industriais", "Materiais Básicos", "Financeiro e Outros",
    "Tecnologia da Informação", "Saúde", "Petróleo, Gás e Biocombustíveis", "Comunicações"
]

# --- TELA DE "SPLASH SCREEN" (LOGIN / NOVO TRABALHO) ---
if not st.session_state['started']:
    st.title("🏛️ LMF - ASSET")
    
    if 'banner_closed' not in st.session_state:
        st.session_state['banner_closed'] = False

    if not st.session_state['banner_closed']:
        st.markdown("<br><br>", unsafe_allow_html=True)
        c1, c2, c3 = st.columns([1, 2, 1])
        with c2:
            st.markdown("""
            <div style="background-color: #1a1a1a; border: 2px solid #D4AF37; padding: 40px; border-radius: 12px; box-shadow: 0px 0px 20px rgba(212, 175, 55, 0.2);">
                <h1 style="color: #D4AF37; margin-top: 0; text-align: center;">🚀 Update 1.01</h1>
                <hr style="border-color: #D4AF37; opacity: 0.3;">
                <p style="color: #e0e0e0; font-size: 1.1em; line-height: 1.8;">
                <b>O que há de novo no sistema:</b><br><br>
                • Adição de opção para modificação de título da carteira<br>
                • Melhoria no salvamento de relatório<br>
                • Melhorias na renda fixa<br>
                • Melhorias na analise fundamentalista<br>
                • Melhoria na visualização de gráfico em "candle"<br>
                • Novas métricas de análise
                </p>
            </div>
            <br>
            """, unsafe_allow_html=True)
            if st.button("✅ COMPREENDIDO - ACESSAR O SISTEMA", use_container_width=True):
                st.session_state['banner_closed'] = True
                st.rerun()
        st.stop()

    st.markdown("### Bem-vindo ao Sistema de Gestão de Portfólio")
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 📄 Iniciar Nova Carteira")
        st.info("Inicie uma nova análise utilizando nossa carteira modelo pré-definida e altere conforme desejar.")
        if st.button("Criar Nova Carteira", use_container_width=True):
            st.session_state['started'] = True
            st.session_state['carteira_alterada'] = False
            st.session_state['nome_carteira'] = "Minha Carteira"
            dt_padrao = datetime(2012, 1, 1).date()
            dt_venc_padrao = datetime(2030, 1, 1).date()
            st.session_state['carteira'] = {
                'QQQ': AtivoRV(ticker='QQQ', aporte=10.0, data_compra=dt_padrao, setor='Tecnologia da Informação'),
                'JEPI': AtivoRV(ticker='JEPI', aporte=10.0, data_compra=dt_padrao, setor='Outros'),
                'PETR4.SA': AtivoRV(ticker='PETR4.SA', aporte=10.0, data_compra=dt_padrao, setor='Petróleo, Gás e Biocombustíveis'),
                'IVV': AtivoRV(ticker='IVV', aporte=10.0, data_compra=dt_padrao, setor='Outros'),
                'CDI 100%': AtivoRF(nome='CDI 100%', indexador='CDI', taxa=1.0, aporte=10.0, data_compra=dt_padrao, data_vencimento=dt_venc_padrao),
                'IPCA+ 7%': AtivoRF(nome='IPCA+ 7%', indexador='IPCA+', taxa=0.07, aporte=10.0, data_compra=dt_padrao, data_vencimento=dt_venc_padrao),
                'VALE3.SA': AtivoRV(ticker='VALE3.SA', aporte=10.0, data_compra=dt_padrao, setor='Materiais Básicos'),
                'BBDC4.SA': AtivoRV(ticker='BBDC4.SA', aporte=10.0, data_compra=dt_padrao, setor='Financeiro e Outros'),
                'BBSE3.SA': AtivoRV(ticker='BBSE3.SA', aporte=10.0, data_compra=dt_padrao, setor='Financeiro e Outros'),
                'BRSR6.SA': AtivoRV(ticker='BRSR6.SA', aporte=10.0, data_compra=dt_padrao, setor='Financeiro e Outros')
            }
            st.rerun()
            
    with col2:
        st.markdown("#### 💾 Continuar Trabalho")
        st.success("Cole abaixo o código da carteira que você salvou anteriormente para restaurar todo o seu progresso.")
        codigo_salvo = st.text_input("Cole seu código de salvamento aqui:")
        if st.button("Carregar Trabalho", use_container_width=True):
            if codigo_salvo:
                cart_importada, nome_imp = importar_codigo_carteira(codigo_salvo)
                if cart_importada:
                    st.session_state['carteira'] = cart_importada
                    st.session_state['nome_carteira'] = nome_imp
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
def download_precos_limpos(tickers, start):
    if not tickers: return pd.DataFrame(), pd.DataFrame()
    with st.spinner("Baixando e otimizando dados de mercado..."):
        try:
            df = yf.download(tickers, start=start, progress=False, auto_adjust=False)
            if df.empty: return pd.DataFrame(), pd.DataFrame()
            
            df_adj = df['Adj Close'] if 'Adj Close' in df.columns.levels[0] else df['Close']
            df_close = df['Close']
            
            if isinstance(df_adj, pd.Series):
                ticker_unico = tickers[0]
                df_adj = df_adj.to_frame(name=ticker_unico)
                df_close = df_close.to_frame(name=ticker_unico)

            return df_adj.ffill().bfill(), df_close.ffill().bfill()
        except Exception as e:
            logging.error(f"Erro no download de preços: {e}")
            return pd.DataFrame(), pd.DataFrame()

@st.cache_data(ttl=86400) 
def fetch_br_indicators(codigo, start_date):
    try:
        url = f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados?formato=json&dataInicial={start_date.strftime('%d/%m/%Y')}&dataFinal={datetime.today().strftime('%d/%m/%Y')}"
        df = pd.read_json(url)
        df['data'] = pd.to_datetime(df['data'], format='%d/%m/%Y')
        df.set_index('data', inplace=True)
        return df['valor'] / 100
    except Exception as e:
        logging.error(f"Erro BCB: {e}")
        return pd.Series(dtype=float)

@st.cache_data(ttl=3600)
def fetch_fundamental_info(ticker):
    try:
        return yf.Ticker(ticker).info
    except Exception as e:
        logging.error(f"Erro Info Fundamental: {e}")
        return {}

@st.cache_data(ttl=3600)
def fetch_historical_fundamentals(ticker):
    try:
        t = yf.Ticker(ticker)
        return t.financials, t.balance_sheet, t.cashflow
    except Exception as e:
        logging.error(f"Erro Histórico Fundamental: {e}")
        return None, None, None

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

def calcular_serie_rf(v: AtivoRF, cdi_al, ipca_al, idx_m, marcar_mercado):
    data_c = pd.to_datetime(v.data_compra)
    
    if v.indexador == "Prefixado": 
        r_d = (1 + v.taxa)**(1/252) - 1
        rs_serie = pd.Series(r_d, index=idx_m)
    elif v.indexador == "CDI": 
        r_d = ((1 + cdi_al) ** v.taxa) - 1
        rs_serie = r_d
    elif v.indexador == "IPCA+": 
        r_d = ((1 + ipca_al) * (1 + v.taxa)**(1/252)) - 1
        rs_serie = r_d
        
    rs_serie[rs_serie.index < data_c] = 0.0
    
    if marcar_mercado and v.data_vencimento:
        dt_venc = pd.to_datetime(v.data_vencimento)
        dias_restantes = (dt_venc - rs_serie.index).days
        dias_restantes = np.maximum(dias_restantes, 0)
        anos_restantes = dias_restantes / 365.25
        
        tx_anual_mercado = (1 + cdi_al)**252 - 1
        delta_yield = tx_anual_mercado.diff().fillna(0)
        
        choque_mtm = - (anos_restantes * delta_yield) / (1 + tx_anual_mercado)
        rs_serie = rs_serie + choque_mtm
        rs_serie[rs_serie.index < data_c] = 0.0
        
    return rs_serie

def processar_carteira(dict_carteira, df_rv_c, df_rv_s, cdi_al, ipca_al, idx_m, reinvest_flag, marcar_mercado, setor_filter="Carteira Completa"):
    if setor_filter != "Carteira Completa":
        filtered_dict = {k: v for k, v in dict_carteira.items() if (v.setor if v.tipo == 'RV' else 'Renda Fixa') == setor_filter}
        dict_carteira = filtered_dict

    if not dict_carteira: return pd.Series(0, index=idx_m), pd.Series(0, index=idx_m)
    
    ret_ativos_c = pd.DataFrame(index=idx_m)
    ret_ativos_s = pd.DataFrame(index=idx_m)
    tickers_validos = []
    aportes_validos = []
    
    for k, v in dict_carteira.items():
        data_c = pd.to_datetime(v.data_compra)
        if v.tipo == 'RV':
            if k in df_rv_c.columns:
                rc = df_rv_c[k].pct_change().fillna(0)
                rs = df_rv_s[k].pct_change().fillna(0)
                rc[rc.index < data_c] = 0.0
                rs[rs.index < data_c] = 0.0
                ret_ativos_c[k] = rc
                ret_ativos_s[k] = rs
                tickers_validos.append(k)
                aportes_validos.append(v.aporte)
        elif v.tipo == 'RF':
            rs_serie = calcular_serie_rf(v, cdi_al, ipca_al, idx_m, marcar_mercado)
            ret_ativos_c[k] = rs_serie
            ret_ativos_s[k] = rs_serie
            tickers_validos.append(k)
            aportes_validos.append(v.aporte)
    
    if not tickers_validos: return pd.Series(0, index=idx_m), pd.Series(0, index=idx_m)
    
    aportes_array = np.array(aportes_validos)
    if aportes_array.sum() == 0: 
        return pd.Series(0, index=idx_m), pd.Series(0, index=idx_m)
        
    pesos = aportes_array / aportes_array.sum()
    ret_com = (ret_ativos_c[tickers_validos] * pesos).sum(axis=1)
    ret_sem = (ret_ativos_s[tickers_validos] * pesos).sum(axis=1)
    return ret_com, ret_sem

def calcular_retorno_individual(config, df_rv_c, df_rv_s, cdi_al, ipca_al, idx_m, reinvest_flag, marcar_mercado):
    data_c = pd.to_datetime(config.data_compra)
    if config.tipo == 'RV':
        df_uso = df_rv_c if reinvest_flag else df_rv_s
        if config.ticker in df_uso.columns:
            r = df_uso[config.ticker].pct_change().fillna(0)
            r[r.index < data_c] = 0.0
            return (1 + r).prod() - 1
    elif config.tipo == 'RF':
        rs_serie = calcular_serie_rf(config, cdi_al, ipca_al, idx_m, marcar_mercado)
        return (1 + rs_serie).prod() - 1
    return 0.0

# === FUNÇÕES DE PLOTAGEM RECUPERADAS ===

def plot_markowitz(ativos_dict, df_rv_c, cdi_al, idx_m):
    ativos_rv_validos = [k for k, v in ativos_dict.items() if v.tipo == 'RV']
    if len(ativos_rv_validos) < 2:
        st.warning("Para simular a Fronteira Eficiente, o recorte precisa ter pelo menos 2 ativos de Renda Variável.")
        return
        
    with st.spinner("Simulando 2.000 portfólios..."):
        ret_ativos = pd.DataFrame(index=idx_m)
        for t in ativos_rv_validos:
            rc = df_rv_c[t].pct_change().fillna(0)
            data_c = pd.to_datetime(ativos_dict[t].data_compra)
            rc[rc.index < data_c] = 0.0
            ret_ativos[t] = rc
            
        ret_medios = ret_ativos.mean() * 252
        cov_mat = ret_ativos.cov() * 252
        num_portfolios = 2000 
        
        np.random.seed(42)
        todos_pesos = np.random.random((num_portfolios, len(ativos_rv_validos)))
        todos_pesos = todos_pesos / np.sum(todos_pesos, axis=1)[:, np.newaxis]
        
        rets_esp = np.dot(todos_pesos, ret_medios)
        vols_esp = np.sqrt(np.einsum('ij,jk,ik->i', todos_pesos, cov_mat, todos_pesos))
        cdi_anualizado_medio = ((1 + cdi_al).prod() ** (252 / max(1, len(cdi_al))) - 1) if len(cdi_al) > 0 else 0.105
        sharpes_esp = (rets_esp - cdi_anualizado_medio) / (vols_esp + 1e-8)
        
        df_ef = pd.DataFrame({'Retorno': rets_esp, 'Volatilidade': vols_esp, 'Sharpe': sharpes_esp})
        idx_max = df_ef['Sharpe'].idxmax()
        p_max = df_ef.iloc[idx_max]
        
        fig = px.scatter(df_ef, x='Volatilidade', y='Retorno', color='Sharpe', color_continuous_scale='Viridis', opacity=0.8)
        fig.add_trace(go.Scatter(x=[p_max['Volatilidade']], y=[p_max['Retorno']], mode='markers', marker=dict(color='red', size=15, symbol='star'), name='Máximo Sharpe'))
        fig.update_layout(xaxis_title="Volatilidade Anual", yaxis_title="Retorno Anual", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color='#D4AF37'))
        st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

def plot_var_histogram(ret_port, title="Distribuição de Retornos Diários", line_color="red"):
    ret_valido = ret_port.dropna()
    if len(ret_valido) == 0:
        st.warning("Dados insuficientes para plotar o VaR.")
        return
    var_5 = np.percentile(ret_valido, 5)
    fig = px.histogram(ret_valido, nbins=50, title=title)
    fig.add_vline(x=var_5, line_dash="dash", line_color=line_color, annotation_text=f"VaR 5% = {var_5:.4f}")
    fig.update_layout(xaxis_title="Retorno Diário", yaxis_title="Densidade", showlegend=False, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color='#D4AF37'))
    st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

def plot_correlation_matrix(ativos_dict, df_rv_c, idx_m, setor_filter):
    dict_uso = ativos_dict
    if setor_filter != "Carteira Completa":
        dict_uso = {k: v for k, v in ativos_dict.items() if (v.setor if v.tipo == 'RV' else 'Renda Fixa') == setor_filter}

    ativos_rv = [k for k, v in dict_uso.items() if v.tipo == 'RV']
    
    if len(ativos_rv) < 2:
        st.warning(f"Selecione pelo menos 2 ativos de Renda Variável no setor '{setor_filter}' para gerar a correlação.")
        return

    with st.spinner(f"Calculando matriz de correlação para {len(ativos_rv)} ativos..."):
        df_retornos = pd.DataFrame(index=idx_m)
        for t in ativos_rv:
            r = df_rv_c[t].pct_change().fillna(0)
            data_c = pd.to_datetime(ativos_dict[t].data_compra)
            r[r.index < data_c] = np.nan 
            df_retornos[t] = r
            
        corr_matrix = df_retornos.corr().fillna(0) 

        fig = px.imshow(corr_matrix, 
                        text_auto=".2f", 
                        aspect="auto", 
                        color_continuous_scale="RdBu_r", 
                        zmin=-1, zmax=1,
                        title=f"Matriz de Correlação - {setor_filter}")
        fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color='#D4AF37'))
        st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

def plot_monte_carlo(ret_portfolio, capital_inicial):
    if ret_portfolio.empty or ret_portfolio.std() == 0:
        st.warning("Dados insuficientes ou portfólio sem volatilidade (apenas RF fixa) para simulação de Monte Carlo.")
        return
        
    with st.spinner("Gerando simulação de Monte Carlo (1.000 caminhos)..."):
        dias_projetados = 252 
        num_simulacoes = 1000
        
        mu_diario = ret_portfolio.mean()
        vol_diaria = ret_portfolio.std()
        
        choques = np.random.normal(0, 1, (dias_projetados, num_simulacoes))
        drift = (mu_diario - 0.5 * vol_diaria**2)
        random_shock = vol_diaria * choques
        
        retornos_simulados = np.exp(drift + random_shock)
        caminhos_capital = capital_inicial * np.vstack([np.ones(num_simulacoes), retornos_simulados]).cumprod(axis=0)
        
        capital_final = caminhos_capital[-1, :]
        var_1_mc_rs = np.percentile(capital_final, 1) 
        
        fig = go.Figure()
        eixo_x = np.arange(dias_projetados + 1)
        for i in range(min(num_simulacoes, 500)): 
            fig.add_trace(go.Scatter(x=eixo_x, y=caminhos_capital[:, i], 
                                     mode='lines', line=dict(width=1), opacity=0.2, 
                                     showlegend=False, hoverinfo='skip'))

        fig.add_trace(go.Scatter(x=[0, dias_projetados], y=[capital_inicial, capital_inicial],
                                 mode='lines', line=dict(color='white', width=3), name='Initial'))

        fig.add_trace(go.Scatter(x=[0, dias_projetados], y=[var_1_mc_rs, var_1_mc_rs],
                                 mode='lines', line=dict(color='#ff4b4b', width=3, dash='dash'), 
                                 name=f'VaR 1% MC ({formatar_moeda(var_1_mc_rs)})'))

        fig.update_layout(title=f"Simulação de Monte Carlo - Capital Evolution (Projeção 1 Ano)<br>VaR 1% MC: {formatar_moeda(var_1_mc_rs)}",
                          xaxis_title="Days", yaxis_title="Capital Evolution",
                          paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', 
                          font=dict(color='#D4AF37'),
                          legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01, bgcolor='rgba(26,26,26,0.8)'))
                          
        fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='rgba(212, 175, 55, 0.15)') 
        fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='rgba(212, 175, 55, 0.15)')
        
        st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

def compara_metrica(val_p, val_c, is_higher_better=True, is_pct=True):
    vp_str = f"{val_p:.2%}" if is_pct else f"{val_p:.2f}"
    vc_str = f"{val_c:.2%}" if is_pct else f"{val_c:.2f}"
    if val_p == val_c: return vp_str, vc_str, "Empate"
    win = val_p > val_c if is_higher_better else val_p < val_c
    if win: return f"⭐ {vp_str}", vc_str, "Principal"
    else: return vp_str, f"⭐ {vc_str}", "Comparada"

def plot_tabela_metricas(m_prin, nome_cart):
    fig = go.Figure(data=[go.Table(
        header=dict(values=['Métrica', nome_cart],
                    fill_color='#1a1a1a',
                    font=dict(color='#D4AF37', size=16, family='Arial'),
                    align='center',
                    height=40),
        cells=dict(values=[
            ['Rentabilidade Acumulada', 'Índice Sharpe', 'Índice Sortino', 'Volatilidade Anual', 'Max Drawdown', 'Alpha de Jensen', 'Beta vs Bench.'],
            [f"{m_prin[0]:.2%}", f"{m_prin[2]:.2f}", f"{m_prin[3]:.2f}", f"{m_prin[1]:.2%}", f"{m_prin[4]:.2%}", f"{m_prin[7]:.2%}", f"{m_prin[6]:.2f}"]
        ],
        fill_color='#0b0b0b',
        font=dict(color='#e0e0e0', size=15, family='Arial'),
        align='center',
        height=35))
    ])
    fig.update_layout(margin=dict(l=0, r=0, t=0, b=0), paper_bgcolor='rgba(0,0,0,0)', height=300)
    return fig

def garantir_dataclasses_state():
    if st.session_state.carteira:
        nova_carteira = {}
        alterou = False
        for k, v in st.session_state.carteira.items():
            if isinstance(v, dict):
                alterou = True
                dt_compra = datetime.strptime(v['data_compra'], '%Y-%m-%d').date() if isinstance(v['data_compra'], str) else v['data_compra']
                if v['tipo'] == 'RV':
                    nova_carteira[k] = AtivoRV(ticker=v.get('ticker', k), aporte=v['aporte'], data_compra=dt_compra, setor=v['setor'])
                else:
                    dt_venc = None
                    if v.get('data_vencimento'):
                        dt_venc = datetime.strptime(v['data_vencimento'], '%Y-%m-%d').date() if isinstance(v['data_vencimento'], str) else v['data_vencimento']
                    nova_carteira[k] = AtivoRF(nome=v.get('nome', k), indexador=v['indexador'], taxa=v['taxa'], aporte=v['aporte'], data_compra=dt_compra, data_vencimento=dt_venc)
            else:
                nova_carteira[k] = v
        if alterou:
            st.session_state.carteira = nova_carteira
            st.session_state['carteira_alterada'] = True

def garantir_dataclasses_state_comparacao():
    if st.session_state.carteira_comparacao:
        nova_carteira = {}
        for k, v in st.session_state.carteira_comparacao.items():
            if isinstance(v, dict):
                dt_compra = datetime.strptime(v['data_compra'], '%Y-%m-%d').date() if isinstance(v['data_compra'], str) else v['data_compra']
                if v['tipo'] == 'RV':
                    nova_carteira[k] = AtivoRV(ticker=v.get('ticker', k), aporte=v['aporte'], data_compra=dt_compra, setor=v['setor'])
                else:
                    dt_venc = None
                    if v.get('data_vencimento'):
                        dt_venc = datetime.strptime(v['data_vencimento'], '%Y-%m-%d').date() if isinstance(v['data_vencimento'], str) else v['data_vencimento']
                    nova_carteira[k] = AtivoRF(nome=v.get('nome', k), indexador=v['indexador'], taxa=v['taxa'], aporte=v['aporte'], data_compra=dt_compra, data_vencimento=dt_venc)
            else:
                nova_carteira[k] = v
        st.session_state.carteira_comparacao = nova_carteira

# --- 3. BARRA LATERAL ---
with st.sidebar:
    st.header("⚙️ Configuração Principal")
    st.session_state['nome_carteira'] = st.text_input("Nome da sua Carteira:", value=st.session_state.get('nome_carteira', 'Minha Carteira'))
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
            cdi_base = c_taxa1.number_input("CDI Base Global (%)", value=10.5, step=0.1, help="Taxa livre de risco") / 100
            ipca_base = c_taxa2.number_input("IPCA Base Global (%)", value=4.5, step=0.1, help="Inflação base") / 100
        else:
            c_taxa1.number_input("CDI Atual BCB (%)", value=10.5, disabled=True, help="Taxa diária anualizada puxada do Banco Central")
            c_taxa2.number_input("IPCA Atual BCB (%)", value=4.5, disabled=True, help="Inflação acumulada puxada do Banco Central")
            
        reinvestir = st.checkbox("Reinvestir Dividendos na Carteira Principal", value=True)
        marcar_mercado_ativado = st.checkbox("Ativar Marcação a Mercado (Aproximação RF)", value=False)
        
    with st.expander("💾 Salvar Trabalho & Comparar", expanded=False):
        st.markdown("<span style='font-size:0.85em; opacity:0.8;'>**O SEU SAVE:** Copie o código abaixo.</span>", unsafe_allow_html=True)
        codigo_export = exportar_codigo_carteira(st.session_state.carteira, st.session_state.nome_carteira)
        st.code(codigo_export if codigo_export else "Adicione ativos.")
        
        st.markdown("<hr style='margin:10px 0;'>", unsafe_allow_html=True)
        codigo_import = st.text_input("Código de Comparação:")
        reinvestir_comp = st.checkbox("Reinvestir Div. (Carteira Importada)", value=True)
        if st.button("Carregar Comparação", use_container_width=True):
            cart_importada, nome_imp = importar_codigo_carteira(codigo_import)
            if cart_importada:
                st.session_state.carteira_comparacao = cart_importada
                st.session_state.nome_carteira_comparacao = nome_imp
                st.success(f"'{nome_imp}' carregada!")
                st.rerun()
        if st.session_state.carteira_comparacao:
            if st.button("Limpar Comparação", use_container_width=True):
                st.session_state.carteira_comparacao = {}
                st.rerun()
    
    st.markdown("---")
    st.subheader("➕ Adicionar Ativos")
    classe_ativo = st.radio("Classe do Ativo", ["Renda Variável", "Renda Fixa"], horizontal=True)
    
    if classe_ativo == "Renda Variável":
        st.warning("⚠️ Ativos listados na B3 exigem o final **.SA**.")
        c_rv1, c_rv2 = st.columns(2)
        ticker_add = c_rv1.text_input("Ticker", help="Ex: PETR4.SA").upper().strip()
        aporte_val = c_rv2.number_input("Peso/Valor", min_value=1.0, value=10.0 if modo_aporte=="Por Peso (%)" else 1000.0)
        setor_rv = st.selectbox("Setor do Ativo (Opcional)", OPCOES_SETORES)
        comprado_inicio_rv = st.checkbox("Desde o Início?", value=True, key="chk_rv")
        data_compra_rv = data_inicio if comprado_inicio_rv else st.date_input("Comprado em", value=data_inicio, min_value=data_inicio, max_value=datetime.today(), key="dt_rv")
        
        if st.button("Inserir Renda Variável") and ticker_add:
            if re.match(r'^[A-Z0-9\.\-\=]+$', ticker_add): 
                st.session_state.carteira[ticker_add] = AtivoRV(ticker=ticker_add, aporte=aporte_val, data_compra=data_compra_rv, setor=setor_rv)
                st.session_state['carteira_alterada'] = True
                st.rerun()
            else: st.error("Ticker inválido.")
    else:
        nome_rf = st.text_input("Nome do Título").strip()
        c_rf1, c_rf2, c_rf3 = st.columns([1.5, 1.5, 1])
        tipo_rf_add = c_rf1.selectbox("Indexador", ["Prefixado", "CDI", "IPCA+"])
        taxa_input_add = c_rf2.number_input("Taxa Anual (%)", value=10.0, step=0.1)
        aporte_val_rf = c_rf3.number_input("Peso/Valor", min_value=1.0, value=10.0 if modo_aporte=="Por Peso (%)" else 1000.0)
        c_rf4, c_rf5 = st.columns(2)
        comprado_inicio_rf = c_rf4.checkbox("Desde o Início?", value=True, key="chk_rf")
        data_compra_rf = data_inicio if comprado_inicio_rf else c_rf4.date_input("Aplicado em", value=data_inicio, min_value=data_inicio, max_value=datetime.today(), key="dt_rf")
        data_vencimento_rf = c_rf5.date_input("Vencimento (MTM)", value=datetime(2030,1,1).date())

        if st.button("Inserir Renda Fixa") and nome_rf:
            st.session_state.carteira[nome_rf] = AtivoRF(nome=nome_rf, indexador=tipo_rf_add, taxa=taxa_input_add/100, aporte=aporte_val_rf, data_compra=data_compra_rf, data_vencimento=data_vencimento_rf)
            st.session_state['carteira_alterada'] = True
            st.rerun()
            
    if st.button("🗑️ Limpar Carteira Principal"):
        st.session_state.carteira = {}
        st.session_state['carteira_alterada'] = True
        st.rerun()

nome_cart = st.session_state.get('nome_carteira', 'Minha Carteira')
nome_comp = st.session_state.get('nome_carteira_comparacao', 'Carteira Importada')

if not st.session_state.carteira:
    st.info("🏛️ Bem-vindo ao LMF Asset. Adicione ativos na barra lateral para começar a análise de alocação.")
    st.stop()

# --- MOTOR PRINCIPAL ---
garantir_dataclasses_state()

ativos_rv_principal = [k for k, v in st.session_state.carteira.items() if getattr(v, 'tipo', 'RV') == 'RV']
ativos_rv_comp = [k for k, v in st.session_state.carteira_comparacao.items() if getattr(v, 'tipo', 'RV') == 'RV']
    
mapa_bench = {"Ibovespa": "^BVSP", "IFIX": "XFIX11.SA", "S&P 500": "^GSPC", "NASDAQ": "^IXIC", "SMLL (Small Caps)": "SMAL11.SA", "Ouro": "GC=F"}
tickers_bench_b3 = [mapa_bench[b] for b in benchmarks_sel if b in mapa_bench]

todos_tickers_rv_necessarios = list(set(ativos_rv_principal + ativos_rv_comp + tickers_bench_b3))

df_rv_com, df_rv_sem = download_precos_limpos(todos_tickers_rv_necessarios, data_inicio) 

if not df_rv_com.empty:
    idx_mestre = df_rv_com.dropna(how='all').index
else:
    idx_mestre = pd.bdate_range(start=data_inicio, end=datetime.today())
    
if len(idx_mestre) == 0:
    idx_mestre = pd.bdate_range(start=data_inicio, end=datetime.today())
    
cdi_series = fetch_br_indicators(12, data_inicio)
ipca_series = fetch_br_indicators(433, data_inicio)

cdi_aligned = cdi_series.reindex(idx_mestre).fillna(0) if not cdi_series.empty else pd.Series((1 + 0.105)**(1/252) - 1, index=idx_mestre)

if ipca_series.empty: ipca_daily_aligned = pd.Series((1 + 0.045)**(1/252) - 1, index=idx_mestre)
else:
    ipca_daily_val = (1 + ipca_series)**(1/21) - 1
    ipca_daily_aligned = ipca_daily_val.reindex(pd.date_range(start=ipca_daily_val.index.min(), end=datetime.today())).ffill().reindex(idx_mestre).fillna(0)

dict_ret_benchs = {}
for b in benchmarks_sel:
    if b == "CDI (Percentual)": dict_ret_benchs[b] = cdi_aligned * taxa_cdi_bench
    elif b == "Selic": 
        selic_series = fetch_br_indicators(11, data_inicio)
        dict_ret_benchs[b] = selic_series.reindex(idx_mestre).fillna(0) if not selic_series.empty else cdi_aligned
    elif b == "IPCA + Taxa": dict_ret_benchs[b] = (1 + ipca_daily_aligned) * (1 + taxa_ipca_bench)**(1/252) - 1
    elif b in mapa_bench:
        tb = mapa_bench[b]
        dict_ret_benchs[b] = df_rv_com[tb].pct_change().fillna(0) if tb in df_rv_com.columns else pd.Series(0, index=idx_mestre)

nome_bench_principal = benchmarks_sel[0] if benchmarks_sel else "Benchmark Padrão"
ret_bench_principal = dict_ret_benchs.get(nome_bench_principal, pd.Series(0, index=idx_mestre))

ret_port_com_full, ret_port_sem_full = processar_carteira(st.session_state.carteira, df_rv_com, df_rv_sem, cdi_aligned, ipca_daily_aligned, idx_mestre, reinvestir, marcar_mercado_ativado)
ret_portfolio_principal = ret_port_com_full if reinvestir else ret_port_sem_full

if st.session_state.carteira_comparacao:
    garantir_dataclasses_state_comparacao()
    ret_comp_com_full, ret_comp_sem_full = processar_carteira(st.session_state.carteira_comparacao, df_rv_com, df_rv_sem, cdi_aligned, ipca_daily_aligned, idx_mestre, reinvestir_comp, False)
    ret_portfolio_comparacao = ret_comp_com_full if reinvestir_comp else ret_comp_sem_full

aportes_brutos = np.array([getattr(v, 'aporte', 0) for v in st.session_state.carteira.values()])
capital_inicial = aportes_brutos.sum() if modo_aporte == "Por Valor Financeiro (R$)" else capital_inicial_input
pesos_norm = aportes_brutos / aportes_brutos.sum() if aportes_brutos.sum() > 0 else aportes_brutos * 0
m_prin = calcular_metricas(ret_portfolio_principal, ret_bench_principal, cdi_aligned)

df_pizza = pd.DataFrame({'Ativo': list(st.session_state.carteira.keys()), 'Peso': pesos_norm})
fig_pizza_base = px.pie(df_pizza, values='Peso', names='Ativo', hole=0.5)
fig_pizza_base.update_layout(paper_bgcolor='rgba(0,0,0,0)', font=dict(color='#D4AF37'), margin=dict(t=0, b=0, l=0, r=0))

html_table_rx = "<table><tr><th>Ativo</th><th>Classe</th><th>Setor</th><th>Capital Alocado</th><th>Retorno (Sem Div)</th><th>Retorno (Com Div)</th><th>Saldo Atualizado</th></tr>"
for i, (t, config) in enumerate(st.session_state.carteira.items()):
    ret_ind_c = calcular_retorno_individual(config, df_rv_com, df_rv_sem, cdi_aligned, ipca_daily_aligned, idx_mestre, True, marcar_mercado_ativado)
    ret_ind_s = calcular_retorno_individual(config, df_rv_com, df_rv_sem, cdi_aligned, ipca_daily_aligned, idx_mestre, False, marcar_mercado_ativado)
    
    val_inicial = getattr(config, 'aporte', 0) if modo_aporte == "Por Valor Financeiro (R$)" else capital_inicial * pesos_norm[i]
    val_final = val_inicial * (1 + (ret_ind_c if reinvestir else ret_ind_s))
    color_s = "#4CAF50" if ret_ind_s >= 0 else "#F44336" 
    color_c = "#4CAF50" if ret_ind_c >= 0 else "#F44336"
    setor_rx = getattr(config, 'setor', 'Outros') if getattr(config, 'tipo', 'RV') == 'RV' else 'Renda Fixa'
    html_table_rx += f"<tr><td><b>{t}</b></td><td>{getattr(config, 'tipo', 'RV')}</td><td>{setor_rx}</td><td>{formatar_moeda(val_inicial)}</td><td style='color:{color_s}'><b>{formatar_percentual(ret_ind_s)}</b></td><td style='color:{color_c}'><b>{formatar_percentual(ret_ind_c)}</b></td><td><b>{formatar_moeda(val_final)}</b></td></tr>"
html_table_rx += "</table>"

df_grafico_rentabilidade = pd.DataFrame(index=idx_mestre)
df_grafico_rentabilidade[f"{nome_cart} (%)"] = ((1 + ret_portfolio_principal).cumprod() - 1) * 100
color_map_rent = {f"{nome_cart} (%)": "#D4AF37"}

if st.session_state.carteira_comparacao:
    df_grafico_rentabilidade[f"{nome_comp} (%)"] = ((1 + ret_portfolio_comparacao).cumprod() - 1) * 100
    color_map_rent[f"{nome_comp} (%)"] = "#00BFFF"
    
for nb, serie_bench in dict_ret_benchs.items():
    df_grafico_rentabilidade[f"{nb} (%)"] = ((1 + serie_bench).cumprod() - 1) * 100
    
fig_rent_global_memoria = px.line(df_grafico_rentabilidade, color_discrete_map=color_map_rent)
fig_rent_global_memoria.update_layout(xaxis_title="", yaxis_title="Acumulado (%)", xaxis=dict(tickformat="%b %Y", dtick="M3"), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color='#D4AF37'))

# --- 5. RENDERIZAÇÃO: MODO IMPRESSÃO LIMPA VS MODO DASHBOARD NORMAL ---
if st.session_state.get('modo_impressao', False):
    st.button("⬅️ VOLTAR AO DASHBOARD NORMAL", on_click=desativar_modo_impressao)
    st.markdown(f"<h1 style='text-align: center; color: #D4AF37; font-size: 3em;'>{nome_cart}</h1>", unsafe_allow_html=True)
    st.markdown("<h3 style='text-align: center; color: #e0e0e0; margin-top: -15px;'>Relatório de Desempenho | Powered by LMF - ASSET</h3>", unsafe_allow_html=True)
    st.markdown("---")
    
    if st.session_state.get('rel_comp', True):
        st.subheader("1. Composição da Carteira e Pesos")
        st.plotly_chart(fig_pizza_base, use_container_width=True, config=PLOTLY_CONFIG, key="pizza_print")
        st.write("")
        
    if st.session_state.get('rel_metr', True):
        st.subheader("2. Quadro de Métricas de Risco/Retorno")
        fig_tbl_met = plot_tabela_metricas(m_prin, nome_cart)
        st.plotly_chart(fig_tbl_met, use_container_width=True, config=PLOTLY_CONFIG, key="tbl_print")
        st.write("")
        
    if st.session_state.get('rel_rent', True):
        st.subheader("3. Evolução Patrimonial Histórica")
        st.plotly_chart(fig_rent_global_memoria, use_container_width=True, config=PLOTLY_CONFIG, key="rent_print")
        st.write("")
        
    if st.session_state.get('rel_rx', False):
        st.subheader("4. Raio-X Individual de Ativos")
        st.markdown(html_table_rx, unsafe_allow_html=True)
        st.write("")
        
    st.divider()
    c_b1, c_b2, c_b3 = st.columns([1,2,1])
    with c_b2:
        if st.button("🖨️ CONFIRMAR IMPRESSÃO / SALVAR PDF", use_container_width=True):
            components.html("<script>window.parent.print();</script>", height=0)
    st.stop()


# ==============================================================================
# ======================== MODO DASHBOARD NORMAL ===============================
# ==============================================================================

st.markdown(f"<h1 style='color: #D4AF37; font-size: 3rem; margin-bottom: -15px;'>🏛️ {nome_cart}</h1>", unsafe_allow_html=True)
st.markdown("<h4 style='color: #e0e0e0; margin-bottom: 30px; opacity: 0.8;'>Portfólio Management System | LMF ASSET</h4>", unsafe_allow_html=True)

# --- RESUMO GLOBAL ---
st.header("📊 Resumo de Desempenho")
ret_port_com_acum = (1 + ret_port_com_full).prod() - 1
ret_port_sem_acum = (1 + ret_port_sem_full).prod() - 1
patrimonio_final = capital_inicial * (1 + m_prin[0])
lucro_rs = capital_inicial * m_prin[0]

# Restauração do Layout de 8 métricas divididas nas linhas corretas
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

st.divider()

# --- ABAS DE ANÁLISE ---
abas_nomes = ["📈 Alocação e Rentabilidade", "🔎 Raio-X Individual", "⚙️ Estudo das Métricas", "📊 Comparação Setorial"]
if st.session_state.carteira_comparacao: abas_nomes.append("🆚 Análise de Comparação")
abas_nomes.extend(["🔍 Análise de Ativos", "📑 Gerador de Relatório"])

tabs = st.tabs(abas_nomes)

# --- ABA 1: ALOCAÇÃO E RENTABILIDADE ---
with tabs[0]:
    c1, c2 = st.columns([1, 1.5])
    with c1:
        st.markdown("### 🛒 Posições Atuais")
        for i, (t, config) in enumerate(st.session_state.carteira.items()):
            cola, colb, colc = st.columns([3, 2, 1])
            info_aloc = f"{pesos_norm[i]:.1%}" if modo_aporte == "Por Peso (%)" else formatar_moeda(getattr(config, 'aporte', 0))
            setor_str = getattr(config, 'setor', 'Outros') if getattr(config, 'tipo', 'RV') == 'RV' else 'Renda Fixa'
            dt_str = getattr(config, 'data_compra').strftime('%d/%m/%y') if hasattr(config, 'data_compra') and hasattr(getattr(config, 'data_compra'), 'strftime') else str(getattr(config, 'data_compra', ''))
            cola.markdown(f"**{t}** *(Início: {dt_str} | {setor_str})*")
            colb.markdown(info_aloc)
            if colc.button("❌", key=f"del_{t}"):
                del st.session_state.carteira[t]
                st.session_state['carteira_alterada'] = True
                st.rerun()
    with c2:
        visao_grafico = st.radio("Visualizar Alocação por:", ["Ativos", "Setores"], horizontal=True)
        if visao_grafico == "Ativos":
            st.plotly_chart(fig_pizza_base, use_container_width=True, config=PLOTLY_CONFIG, key="dash_pizza")
        else:
            setores_lista = [getattr(v, 'setor', 'Outros') if getattr(v, 'tipo', 'RV') == 'RV' else 'Renda Fixa' for v in st.session_state.carteira.values()]
            df_pizza_sec = pd.DataFrame({'Setor': setores_lista, 'Peso': pesos_norm})
            df_pizza_sec = df_pizza_sec.groupby('Setor', as_index=False).sum()
            fig_pizza_sec = px.pie(df_pizza_sec, values='Peso', names='Setor', hole=0.5)
            fig_pizza_sec.update_layout(paper_bgcolor='rgba(0,0,0,0)', font=dict(color='#D4AF37'), margin=dict(t=0, b=0, l=0, r=0))
            st.plotly_chart(fig_pizza_sec, use_container_width=True, config=PLOTLY_CONFIG, key="dash_pizza_setor")
        
    st.markdown("### 📈 Evolução de Rentabilidade")
    st.plotly_chart(fig_rent_global_memoria, use_container_width=True, config=PLOTLY_CONFIG, key="dash_rent_glob")

# --- ABA 2: RAIO-X ---
with tabs[1]:
    st.markdown("### 🔎 Análise Financeira Individual")
    st.markdown("Confira o capital injetado, o retorno com e sem os dividendos embutidos e o patrimônio exato final de cada ativo na sua carteira.")
    st.markdown(html_table_rx, unsafe_allow_html=True)

# --- ABA 3: ESTUDO DAS MÉTRICAS ---
with tabs[2]:
    c_m1, c_m2 = st.columns(2)
    
    opcoes_metricas = [
        "Fronteira Eficiente (Markowitz)", 
        "Value at Risk (VaR Histórico)", 
        "Drawdown Histórico",
        "Volatilidade Rolante",
        "Beta (Risco de Mercado)",
        "Matriz de Correlação", 
        "Simulação de Monte Carlo"
    ]
    
    metrica_sel = c_m1.selectbox("Selecione o Estudo Avançado:", opcoes_metricas)
    
    setores_disp = list(set([getattr(v, 'setor', 'Outros') if getattr(v, 'tipo', 'RV') == 'RV' else 'Renda Fixa' for v in st.session_state.carteira.values()]))
    setor_filtro = c_m2.selectbox("Filtrar Setor para Estudo:", ["Carteira Completa"] + setores_disp)
    
    if setor_filtro != "Carteira Completa":
        ret_estudo_com, ret_estudo_sem = processar_carteira(st.session_state.carteira, df_rv_com, df_rv_sem, cdi_aligned, ipca_daily_aligned, idx_mestre, reinvestir, marcar_mercado_ativado, setor_filter=setor_filtro)
        ret_estudo = ret_estudo_com if reinvestir else ret_estudo_sem
        dict_estudo = {k: v for k, v in st.session_state.carteira.items() if (getattr(v, 'setor', 'Outros') if getattr(v, 'tipo', 'RV') == 'RV' else 'Renda Fixa') == setor_filtro}
    else:
        ret_estudo = ret_portfolio_principal
        dict_estudo = st.session_state.carteira

    janela = 252 
    df_roll = pd.DataFrame(index=idx_mestre)

    if metrica_sel == "Matriz de Correlação":
        st.divider()
        plot_correlation_matrix(st.session_state.carteira, df_rv_com, idx_mestre, setor_filtro)
        
    elif metrica_sel == "Simulação de Monte Carlo":
        st.divider()
        plot_monte_carlo(ret_estudo, capital_inicial)
        
    elif metrica_sel == "Fronteira Eficiente (Markowitz)":
        st.divider()
        plot_markowitz(dict_estudo, df_rv_com, cdi_aligned, idx_mestre)
        
    elif metrica_sel == "Value at Risk (VaR Histórico)":
        st.divider()
        tipo_var = st.radio("Selecione a visualização do VaR:", ["Histograma de Retornos (Estático)", "VaR Histórico Rolante"], horizontal=True)
        if tipo_var == "Histograma de Retornos (Estático)":
            plot_var_histogram(ret_estudo, f"Distribuição de Retornos ({setor_filtro})")
        else:
            df_roll[f"VaR 5% ({setor_filtro})"] = ret_estudo.rolling(janela).quantile(0.05)
            fig_var = px.line(df_roll.dropna(), color_discrete_sequence=["#D4AF37"])
            fig_var.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color='#D4AF37'))
            st.plotly_chart(fig_var, use_container_width=True, config=PLOTLY_CONFIG, key="dash_var_roll")
            
    elif metrica_sel == "Drawdown Histórico":
        st.divider()
        cum = (1 + ret_estudo).cumprod()
        dd = ((cum / cum.cummax() - 1) * 100)
        fig_dd = px.area(dd, title=f"Drawdown Histórico (%) - {setor_filtro}")
        fig_dd.update_traces(line_color='#ff4b4b', fillcolor='rgba(255, 75, 75, 0.2)')
        fig_dd.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color='#D4AF37'))
        st.plotly_chart(fig_dd, use_container_width=True, config=PLOTLY_CONFIG)
        
    elif metrica_sel == "Volatilidade Rolante":
        st.divider()
        df_roll[f"{nome_cart} (%)"] = ret_estudo.rolling(janela).std() * np.sqrt(252) * 100
        for b_name in benchmarks_sel:
            b_serie = dict_ret_benchs.get(b_name)
            if b_serie is not None:
                df_roll[f"{b_name} (%)"] = b_serie.rolling(janela).std() * np.sqrt(252) * 100
        fig_vol = px.line(df_roll.dropna())
        fig_vol.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color='#D4AF37'))
        st.plotly_chart(fig_vol, use_container_width=True, config=PLOTLY_CONFIG, key="dash_vol_roll")
        
    elif metrica_sel == "Beta (Risco de Mercado)":
        st.divider()
        var_bench = ret_bench_principal.rolling(janela).var()
        var_bench = var_bench.where(var_bench > 1e-8, np.nan)
        df_roll[f"Beta ({setor_filtro})"] = ret_estudo.rolling(janela).cov(ret_bench_principal) / var_bench
        df_plot = df_roll.dropna()
        if df_plot.empty:
            st.warning(f"O benchmark atual não possui volatilidade suficiente para Beta.")
        else:
            fig_beta = px.line(df_plot, color_discrete_sequence=["#D4AF37"])
            fig_beta.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color='#D4AF37'))
            st.plotly_chart(fig_beta, use_container_width=True, config=PLOTLY_CONFIG, key="dash_beta")

# --- ABA 4: COMPARAÇÃO SETORIAL ---
with tabs[3]:
    st.markdown("### 📊 Análise Setorial Personalizada")
    st.markdown("Filtre janelas de tempo específicas e compare o risco/retorno dos setores presentes na sua carteira.")
    
    c_dates1, c_dates2 = st.columns(2)
    dt_start = c_dates1.date_input("Data de Início:", value=data_inicio, min_value=data_inicio, max_value=datetime.today())
    dt_end = c_dates2.date_input("Data de Fim:", value=datetime.today().date(), min_value=dt_start, max_value=datetime.today())
    
    setores_disponiveis = list(set([getattr(v, 'setor', 'Outros') if getattr(v, 'tipo', 'RV') == 'RV' else 'Renda Fixa' for v in st.session_state.carteira.values()]))
    setores_selecionados = st.multiselect("Selecione os Setores para Comparar:", setores_disponiveis, default=setores_disponiveis[:3] if len(setores_disponiveis) >= 3 else setores_disponiveis)
    
    if not setores_selecionados:
        st.warning("Selecione ao menos um setor para gerar a comparação.")
    else:
        ts_start = pd.to_datetime(dt_start)
        ts_end = pd.to_datetime(dt_end)
        mask_dates = (idx_mestre >= ts_start) & (idx_mestre <= ts_end)
        idx_periodo = idx_mestre[mask_dates]
        
        if len(idx_periodo) < 2:
            st.warning("O período selecionado é muito curto para gerar métricas consistentes.")
        else:
            retornos_setores = {}
            metricas_setores = {}
            cdi_periodo = cdi_aligned.loc[idx_periodo]
            bench_periodo = ret_bench_principal.loc[idx_periodo] if not ret_bench_principal.empty else pd.Series(0, index=idx_periodo)
            
            for setor in setores_selecionados:
                ret_c_sect, ret_s_sect = processar_carteira(st.session_state.carteira, df_rv_com, df_rv_sem, cdi_aligned, ipca_daily_aligned, idx_mestre, reinvestir, marcar_mercado_ativado, setor_filter=setor)
                ret_periodo = (ret_c_sect if reinvestir else ret_s_sect).loc[idx_periodo]
                retornos_setores[setor] = ret_periodo
                metricas_setores[setor] = calcular_metricas(ret_periodo, bench_periodo, cdi_periodo)
                
            df_plot_setores = pd.DataFrame(index=idx_periodo)
            for setor, ret_serie in retornos_setores.items():
                df_plot_setores[setor] = ((1 + ret_serie).cumprod() - 1) * 100
                
            fig_setores = px.line(df_plot_setores)
            fig_setores.update_layout(xaxis_title="Data", yaxis_title="Acumulado (%)", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color='#D4AF37'), legend_title_text='Setor')
            st.plotly_chart(fig_setores, use_container_width=True, config=PLOTLY_CONFIG, key="dash_analise_sec")
            
            st.markdown("#### 🏆 Métricas do Período por Setor")
            html_met_sect = "<table><tr><th>Setor</th><th>Retorno Acumulado</th><th>Volatilidade Anual</th><th>Índice Sharpe</th><th>Índice Sortino</th><th>Max Drawdown</th><th>Beta</th></tr>"
            for setor, m in metricas_setores.items():
                html_met_sect += f"<tr><td><b>{setor}</b></td><td>{m[0]:.2%}</td><td>{m[1]:.2%}</td><td>{m[2]:.2f}</td><td>{m[3]:.2f}</td><td>{m[4]:.2%}</td><td>{m[6]:.2f}</td></tr>"
            html_met_sect += "</table>"
            st.markdown(html_met_sect, unsafe_allow_html=True)

if st.session_state.carteira_comparacao:
    tab_comp_idx = 4
    tab_fund_idx = 5
    tab_rel_idx = 6
else:
    tab_fund_idx = 4
    tab_rel_idx = 5

# --- ABA 5: COMPARAÇÃO (SE EXISTIR) ---
if st.session_state.carteira_comparacao:
    with tabs[tab_comp_idx]:
        m_comp = calcular_metricas(ret_portfolio_comparacao, ret_bench_principal, cdi_aligned)
        st.markdown("### 🏆 Confronto Direto de Métricas")
        r_p, r_c, win_r = compara_metrica(m_prin[0], m_comp[0], True, True)
        a_p, a_c, win_a = compara_metrica(m_prin[7], m_comp[7], True, True)
        s_p, s_c, win_s = compara_metrica(m_prin[2], m_comp[2], True, False)
        v_p, v_c, win_v = compara_metrica(m_prin[1], m_comp[1], False, True)
        d_p, d_c, win_d = compara_metrica(m_prin[4], m_comp[4], True, True) 
        
        st.markdown(f"""
        <table>
            <tr><th>Métrica</th><th>{nome_cart}</th><th>{nome_comp}</th><th>Vencedor</th></tr>
            <tr><td>Retorno Acumulado</td><td>{r_p}</td><td>{r_c}</td><td>{win_r}</td></tr>
            <tr><td>Alpha de Jensen</td><td>{a_p}</td><td>{a_c}</td><td>{win_a}</td></tr>
            <tr><td>Índice Sharpe</td><td>{s_p}</td><td>{s_c}</td><td>{win_s}</td></tr>
            <tr><td>Volatilidade Anual</td><td>{v_p}</td><td>{v_c}</td><td>{win_v}</td></tr>
            <tr><td>Drawdown Máximo</td><td>{d_p}</td><td>{d_c}</td><td>{win_d}</td></tr>
        </table>
        """, unsafe_allow_html=True)
        
        st.markdown(f"### 📈 Estudo Profundo ({nome_comp})")
        c_est_c, c_filt_c = st.columns(2)
        est_comp = c_est_c.selectbox(f"Análise ({nome_comp}):", ["Fronteira Eficiente (Markowitz)", "Value at Risk (VaR)", "Drawdown Histórico", "Volatilidade Rolante"])
        
        setores_presentes_comp = list(set([getattr(v, 'setor', 'Outros') if getattr(v, 'tipo', 'RV') == 'RV' else 'Renda Fixa' for v in st.session_state.carteira_comparacao.values()]))
        setor_filtro_comp = c_filt_c.selectbox("Filtrar por Setor (Importada):", ["Carteira Completa"] + setores_presentes_comp)
        
        if setor_filtro_comp != "Carteira Completa":
            ret_estudo_comp_com, ret_estudo_comp_sem = processar_carteira(st.session_state.carteira_comparacao, df_rv_com, df_rv_sem, cdi_aligned, ipca_daily_aligned, idx_mestre, reinvestir_comp, False, setor_filter=setor_filtro_comp)
            ret_estudo_comp = ret_estudo_comp_com if reinvestir_comp else ret_estudo_comp_sem
            dict_estudo_comp = {k: v for k, v in st.session_state.carteira_comparacao.items() if (getattr(v, 'setor', 'Outros') if getattr(v, 'tipo', 'RV') == 'RV' else 'Renda Fixa') == setor_filtro_comp}
        else:
            ret_estudo_comp = ret_portfolio_comparacao
            dict_estudo_comp = st.session_state.carteira_comparacao
        
        df_roll_comp = pd.DataFrame(index=idx_mestre)
        janela = 252

        if est_comp == "Fronteira Eficiente (Markowitz)":
            plot_markowitz(dict_estudo_comp, df_rv_com, cdi_aligned, idx_mestre)
        
        elif est_comp == "Value at Risk (VaR)":
            df_roll_comp[f"VaR 5% ({setor_filtro_comp})"] = ret_estudo_comp.rolling(janela).quantile(0.05)
            fig_var_c = px.line(df_roll_comp.dropna(), color_discrete_sequence=["#00BFFF"])
            fig_var_c.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color='#D4AF37'))
            st.plotly_chart(fig_var_c, use_container_width=True, config=PLOTLY_CONFIG, key="dash_comp_var")
        
        elif est_comp == "Drawdown Histórico":
            df_roll_comp[f"{nome_comp} %"] = (((1 + ret_estudo_comp).cumprod() / (1 + ret_estudo_comp).cumprod().cummax()) - 1) * 100
            fig_dd_c = px.line(df_roll_comp.dropna(), color_discrete_sequence=["#00BFFF"])
            fig_dd_c.update_traces(fill='tozeroy') 
            fig_dd_c.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color='#D4AF37'))
            st.plotly_chart(fig_dd_c, use_container_width=True, config=PLOTLY_CONFIG, key="dash_comp_dd")
        
        elif est_comp == "Volatilidade Rolante":
            df_roll_comp[f"{nome_comp} %"] = ret_estudo_comp.rolling(janela).std() * np.sqrt(252) * 100
            df_roll_comp[f"{nome_bench_principal} (%)"] = ret_bench_principal.rolling(janela).std() * np.sqrt(252) * 100
            fig_vol_c = px.line(df_roll_comp.dropna(), color_discrete_sequence=["#00BFFF", "#555555"])
            fig_vol_c.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color='#D4AF37'))
            st.plotly_chart(fig_vol_c, use_container_width=True, config=PLOTLY_CONFIG, key="dash_comp_vol")

# --- ABA 6: ANÁLISE DE ATIVOS (FUNDAMENTOS + GRÁFICO) ---
with tabs[tab_fund_idx]:
    if not ativos_rv_principal:
        st.warning("Adicione ativos de Renda Variável na carteira para visualizar a análise individual.")
    else:
        ativo_fund = st.selectbox("Selecione o Ativo para Análise Individual:", ativos_rv_principal)
        if ativo_fund:
            with st.spinner(f"Extraindo dados de {ativo_fund}..."):
                info = fetch_fundamental_info(ativo_fund)
                fin, bs, cf = fetch_historical_fundamentals(ativo_fund)
                
                if not info or ('trailingPE' not in info and 'marketCap' not in info and 'priceToBook' not in info):
                    st.warning(f"Dados fundamentalistas não estão disponíveis na API global para o ativo {ativo_fund} no momento.")
                else:
                    st.markdown(f"### 📊 Raio-X Fundamentalista: {ativo_fund}")
                    st.caption("⚠️ **Aviso de Dados:** As métricas abaixo são extraídas de provedores públicos globais.")
                    st.markdown("---")
                    
                    st.subheader("💰 Valuation & Preço", divider='gray')
                    v1, v2, v3, v4, v5 = st.columns(5)
                    v1.metric("P/L (Preço/Lucro)", formatar_float(info.get('trailingPE') or info.get('forwardPE')))
                    v2.metric("P/VP", formatar_float(info.get('priceToBook')))
                    v3.metric("EV/EBITDA", formatar_float(info.get('enterpriseToEbitda')))
                    v4.metric("P/SR (Receita)", formatar_float(info.get('priceToSalesTrailing12Months')))
                    v5.metric("Dividend Yield", formatar_dy(info.get('trailingAnnualDividendYield') or info.get('dividendYield')))
                    
                    st.subheader("📈 Rentabilidade & Eficiência", divider='gray')
                    r1, r2, r3, r4, r5 = st.columns(5)
                    r1.metric("ROE (Retorno s/ PL)", formatar_pct_api(info.get('returnOnEquity')))
                    r2.metric("ROA (Retorno s/ Ativos)", formatar_pct_api(info.get('returnOnAssets')))
                    r3.metric("Margem Bruta", formatar_pct_api(info.get('grossMargins')))
                    r4.metric("Margem EBITDA", formatar_pct_api(info.get('ebitdaMargins')))
                    r5.metric("Margem Líquida", formatar_pct_api(info.get('profitMargins')))
                    
                    st.subheader("🏛️ Saúde Financeira & Estrutura", divider='gray')
                    s1, s2, s3, s4, s5 = st.columns(5)
                    s1.metric("Liquidez Corrente", formatar_float(info.get('currentRatio')))
                    div_pat_val = info.get('debtToEquity')
                    div_pat_str = formatar_float(div_pat_val / 100) if div_pat_val and div_pat_val != 0 else "N/A"
                    s2.metric("Dívida/Patrimônio", div_pat_str)
                    s3.metric("VPA (Val. Patr. Ação)", formatar_float(info.get('bookValue')))
                    s4.metric("LPA (Lucro Ação)", formatar_float(info.get('trailingEps') or info.get('forwardEps')))
                    s5.metric("Valor de Mercado", formatar_abrev(info.get('marketCap')))
                    
                    st.markdown("<br>", unsafe_allow_html=True)
                    st.markdown("### 📈 Evolução Histórica Contábil")
                    
                    opcoes_historico = {}
                    if fin is not None and not fin.empty:
                        if "Total Revenue" in fin.index: opcoes_historico["Receita Total"] = ("Total Revenue", fin)
                        if "Gross Profit" in fin.index: opcoes_historico["Lucro Bruto"] = ("Gross Profit", fin)
                        if "EBIT" in fin.index: opcoes_historico["EBIT"] = ("EBIT", fin)
                        if "Normalized EBITDA" in fin.index: opcoes_historico["EBITDA"] = ("Normalized EBITDA", fin)
                        elif "EBITDA" in fin.index: opcoes_historico["EBITDA"] = ("EBITDA", fin)
                        if "Net Income" in fin.index: opcoes_historico["Lucro Líquido"] = ("Net Income", fin)
                        
                    if bs is not None and not bs.empty:
                        if "Total Assets" in bs.index: opcoes_historico["Ativos Totais"] = ("Total Assets", bs)
                        if "Total Liabilities Net Minority Interest" in bs.index: opcoes_historico["Passivos Totais"] = ("Total Liabilities Net Minority Interest", bs)
                        elif "Total Liabilities" in bs.index: opcoes_historico["Passivos Totais"] = ("Total Liabilities", bs)
                        if "Stockholders Equity" in bs.index: opcoes_historico["Patrimônio Líquido"] = ("Stockholders Equity", bs)
                        if "Total Debt" in bs.index: opcoes_historico["Dívida Total"] = ("Total Debt", bs)
                        if "Cash And Cash Equivalents" in bs.index: opcoes_historico["Caixa e Equivalentes"] = ("Cash And Cash Equivalents", bs)
                        
                    if cf is not None and not cf.empty:
                        if "Operating Cash Flow" in cf.index: opcoes_historico["Caixa Operacional"] = ("Operating Cash Flow", cf)
                        if "Free Cash Flow" in cf.index: opcoes_historico["Fluxo de Caixa Livre"] = ("Free Cash Flow", cf)
                    
                    if opcoes_historico:
                        metrica_hist = st.selectbox("Selecione a métrica contábil:", list(opcoes_historico.keys()))
                        nome_api, df_fonte = opcoes_historico[metrica_hist]
                        serie_hist = df_fonte.loc[nome_api].dropna().sort_index()
                        
                        if not serie_hist.empty:
                            def formata_br(v):
                                if pd.isna(v) or v == 0: return "0"
                                sinal = "-" if v < 0 else ""
                                abs_v = abs(v)
                                if abs_v >= 1e9: return f"{sinal}{abs_v/1e9:.2f} B"
                                if abs_v >= 1e6: return f"{sinal}{abs_v/1e6:.2f} M"
                                return f"{sinal}{abs_v:,.0f}"
                                
                            df_plot = pd.DataFrame({
                                "Ano": serie_hist.index.year.astype(str),
                                "Valor": serie_hist.values
                            })
                            df_plot["Texto"] = df_plot["Valor"].apply(formata_br)
                            
                            fig_hist = px.bar(df_plot, x="Ano", y="Valor", text="Texto")
                            fig_hist.update_traces(marker_color='#D4AF37', textfont_color='white', textposition='outside')
                            fig_hist.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color='#D4AF37'), xaxis_title="", yaxis_title="Valor Nominal", yaxis=dict(showticklabels=False))
                            st.plotly_chart(fig_hist, use_container_width=True, config=PLOTLY_CONFIG, key="dash_fund_hist")
                        
                st.markdown("<br>", unsafe_allow_html=True)
                st.markdown("### 📉 Gráfico de Preços do Ativo")
                tipo_grafico_ativo = st.radio("Formato de visualização:", ["Linha", "Candlestick"], horizontal=True)
                
                df_ohlc = yf.download(ativo_fund, start=data_inicio, progress=False, auto_adjust=False)
                if df_ohlc.empty or 'Close' not in df_ohlc:
                    st.warning("Dados de cotação diária indisponíveis.")
                else:
                    if tipo_grafico_ativo == "Candlestick" and 'Open' in df_ohlc:
                        o = df_ohlc['Open'].squeeze()
                        h = df_ohlc['High'].squeeze()
                        l = df_ohlc['Low'].squeeze()
                        c = df_ohlc['Close'].squeeze()
                        fig_ativo = go.Figure(data=[go.Candlestick(x=df_ohlc.index, open=o, high=h, low=l, close=c)])
                    else:
                        fig_ativo = px.line(x=df_ohlc.index, y=df_ohlc['Close'].squeeze())
                        fig_ativo.update_traces(line_color='#D4AF37')
                        
                    fig_ativo.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color='#D4AF37'), xaxis_title="Data", yaxis_title="Cotação / Preço", xaxis_rangeslider_visible=False)
                    st.plotly_chart(fig_ativo, use_container_width=True, config=PLOTLY_CONFIG, key="dash_ativo_chart")

with tabs[tab_rel_idx]: # RELATÓRIO
    st.markdown("### 📑 Painel de Exportação")
    st.info("Aqui você configura o que deseja imprimir no seu relatório em PDF. Exporte gráficos individualmente clicando no ícone de câmera (PNG).")
    
    c_rel1, c_rel2 = st.columns(2)
    st.session_state['rel_comp'] = c_rel1.checkbox("Incluir Gráfico de Alocação e Pesos", value=st.session_state.get('rel_comp', True))
    st.session_state['rel_metr'] = c_rel1.checkbox("Incluir Tabela Gráfica de Métricas", value=st.session_state.get('rel_metr', True))
    st.session_state['rel_rent'] = c_rel2.checkbox("Incluir Gráfico de Evolução Patrimonial", value=st.session_state.get('rel_rent', True))
    st.session_state['rel_rx'] = c_rel2.checkbox("Incluir Tabela Analítica (Raio-X de Ativos)", value=st.session_state.get('rel_rx', False))
    
    st.divider()
    c_b1, c_b2, c_b3 = st.columns([1,2,1])
    with c_b2:
        st.button("📄 ACESSAR MODO DE IMPRESSÃO (PDF LIMPO)", use_container_width=True, on_click=ativar_modo_impressao)

    st.markdown("<br><br>", unsafe_allow_html=True)
    st.markdown("### 📊 Exportador de Métricas Individuais (Para Slides/PPT)")
    fig_export_metr = plot_tabela_metricas(m_prin, nome_cart)
    st.plotly_chart(fig_export_metr, use_container_width=True, config=PLOTLY_CONFIG, key="dash_export_metr")

st.markdown("<div style='text-align:right; color:#D4AF37; opacity:0.6; margin-top: 50px;'>Idealizado por Bernardo V.</div>", unsafe_allow_html=True)
