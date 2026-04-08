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

# --- 2. MOTOR DINÂMICO DE TEMAS E CORES ---
def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip('#')
    if len(hex_color) == 3:
        hex_color = ''.join([c*2 for c in hex_color])
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

def get_theme_colors(bg_hex):
    """Calcula a luminância e gera uma paleta adaptativa para contraste total"""
    try:
        r, g, b = hex_to_rgb(bg_hex)
        # Fórmula padrão de luminância perceptiva
        luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    except:
        bg_hex = "#0b0b0b"
        luminance = 0

    is_light = luminance > 0.5
    gold_accent = "#D4AF37"

    if is_light:
        return {
            "bg": bg_hex,
            "bg_card": "rgba(0, 0, 0, 0.04)", 
            "text_main": "#000000",  
            "text_sec": "#333333",
            "accent": "#A67B27",  
            "accent_comp": "#005C99",
            "grid": "rgba(0, 0, 0, 0.15)",
            "line_base": "#1a1a1a",
            "win": "#008000", 
            "loss": "#CC0000",
            "input_bg": "#ffffff",           
            "input_border": "#cccccc",       
            "chart_seq": ["#003f5c", "#d45087", "#2f4b7c", "#f95d6a", "#665191", "#ff7c43", "#a05195", "#ffa600"]
        }
    else:
        return {
            "bg": bg_hex,
            "bg_card": "rgba(255, 255, 255, 0.05)",
            "text_main": "#ffffff",  
            "text_sec": "#aaaaaa",
            "accent": gold_accent,  
            "accent_comp": "#00BFFF",
            "grid": "rgba(255, 255, 255, 0.1)",
            "line_base": "#ffffff",
            "win": "#4CAF50",
            "loss": "#F44336",
            "input_bg": "#1a1a1a",           
            "input_border": "#333333",       
            "chart_seq": ["#D4AF37", "#00BFFF", "#32CD32", "#FF6347", "#8A2BE2", "#FF69B4", "#00FA9A", "#FF4500"]
        }

# --- 3. CONFIGURAÇÃO VISUAL INICIAL E INJEÇÃO CSS ---
st.set_page_config(page_title="LMF - ASSET", layout="wide")

# Inicialização de Estados Primários
if 'bg_color' not in st.session_state: st.session_state['bg_color'] = "#0b0b0b"
if 'started' not in st.session_state: st.session_state['started'] = False
if 'carteira_alterada' not in st.session_state: st.session_state['carteira_alterada'] = False
if 'carteira' not in st.session_state: st.session_state['carteira'] = {}
if 'carteira_comparacao' not in st.session_state: st.session_state['carteira_comparacao'] = {}
if 'modo_impressao' not in st.session_state: st.session_state['modo_impressao'] = False
if 'nome_carteira' not in st.session_state: st.session_state['nome_carteira'] = "Minha Carteira"
if 'nome_carteira_comparacao' not in st.session_state: st.session_state['nome_carteira_comparacao'] = "Carteira Importada"
if 'usar_sliders' not in st.session_state: st.session_state['usar_sliders'] = False

# Carrega o tema baseado no estado atual da cor de fundo
theme = get_theme_colors(st.session_state['bg_color'])

st.markdown(f"""
    <style>
    /* CSS GLOBAL COM LÓGICA DE CONTRASTE FORÇADO */
    .stApp, [data-testid="stSidebar"] {{ background-color: {theme['bg']} !important; transition: 0.3s; }}
    .stApp p, .stApp span, .stApp label, div[data-testid="stMarkdownContainer"] {{ color: {theme['text_main']} !important; }}
    h1, h2, h3, h4, h5, h6 {{ color: {theme['accent']} !important; }}
    
    /* Botões sempre com padrão Ouro da Marca */
    .stButton>button {{ background-color: #D4AF37 !important; color: #000000 !important; border: None; font-weight: bold; width: 100%; transition: 0.3s; }}
    .stButton>button:hover {{ background-color: #F1C40F !important; color: #000000 !important; }}
    
    /* Força texto legível no sidebar independentemente do fundo */
    [data-testid="stSidebar"] p, [data-testid="stSidebar"] span, [data-testid="stSidebar"] label {{ color: {theme['text_main']} !important; opacity: 1 !important; }}
    [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {{ color: {theme['accent']} !important; }}
    
    /* Componentes Estruturais */
    div[data-testid="metric-container"] {{ background-color: {theme['bg_card']} !important; border: 1px solid {theme['accent']} !important; padding: 15px; border-radius: 8px; }}
    [data-testid="stMetricValue"] {{ color: {theme['text_main']} !important; }}
    [data-testid="stMetricLabel"] p, [data-testid="stMetricLabel"] span {{ color: {theme['text_sec']} !important; font-weight: bold; }}
    button[data-baseweb="tab"] p {{ color: {theme['text_sec']} !important; font-size: 1.1em; }}
    button[data-baseweb="tab"][aria-selected="true"] p {{ color: {theme['accent']} !important; font-weight: bold !important; }}
    button[data-baseweb="tab"][aria-selected="true"] {{ border-bottom-color: {theme['accent']} !important; }}
    
    /* CORREÇÃO DEFINITIVA DAS CAIXAS DE INPUT (SÓLIDAS) */
    .stTextInput input, 
    .stNumberInput input, 
    .stDateInput input,
    div[data-baseweb="base-input"],
    div[data-baseweb="select"] > div,
    ul[role="listbox"] {{
        background-color: {theme['input_bg']} !important;
        color: {theme['text_main']} !important;
        -webkit-text-fill-color: {theme['text_main']} !important;
        border: 1px solid {theme['input_border']} !important;
        border-radius: 6px !important;
    }}
    
    div[data-baseweb="base-input"] input {{
        background-color: transparent !important;
        border: none !important;
    }}
    
    div[data-baseweb="select"] span {{
        color: {theme['text_main']} !important;
    }}
    
    span[data-baseweb="tag"] {{
        background-color: {theme['accent']} !important; 
        color: #000000 !important; 
        border: none !important;
    }}
    span[data-baseweb="tag"] * {{
        color: #000000 !important; 
    }}
    
    hr {{ border-color: {theme['accent']} !important; opacity: 0.3; }}
    table {{ width: 100%; text-align: center; border-collapse: collapse; margin-bottom: 20px; color: {theme['text_main']} !important; }}
    th {{ border-bottom: 2px solid {theme['accent']}; color: {theme['accent']}; padding: 10px; }}
    td {{ border-bottom: 1px solid {theme['grid']}; padding: 10px; }}
    
    /* Oculta excessos na impressão PDF */
    @media print {{
        section[data-testid="stSidebar"] {{ display: none !important; }}
        header[data-testid="stHeader"] {{ display: none !important; }}
        div[data-testid="stToolbar"] {{ display: none !important; }}
        .stButton {{ display: none !important; }}
        .stTabs {{ display: none !important; }}
    }}
    </style>
""", unsafe_allow_html=True)

PLOTLY_CONFIG = {
    'displayModeBar': True,
    'displaylogo': False,
    'modeBarButtonsToRemove': ['lasso2d', 'select2d'],
    'toImageButtonOptions': {'format': 'png', 'filename': 'LMF_Asset_Export', 'height': 720, 'width': 1280, 'scale': 2 }
}

OPCOES_SETORES = [
    "Outros", "Consumo Cíclico", "Consumo não Cíclico", "Utilidade Pública", 
    "Bens Industriais", "Materiais Básicos", "Financeiro e Outros", 
    "Tecnologia da Informação", "Saúde", "Petróleo, Gás e Biocombustíveis", "Comunicações",
    "Conjunto 1", "Conjunto 2", "Conjunto 3", "Conjunto 4", 
    "Conjunto 5", "Conjunto 6", "Conjunto 7", "Conjunto 8"
]

# --- FUNÇÕES DE LÓGICA E DADOS ---
def formatar_moeda(valor): return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
def formatar_percentual(valor): return f"{'+' if valor >= 0 else ''}{valor*100:.2f}%"
def formatar_float(valor): return "N/A" if valor is None or pd.isna(valor) else f"{float(valor):.2f}"
def formatar_pct_api(valor):
    if valor is None or pd.isna(valor) or valor == 0: return "N/A"
    return f"{float(valor):.2f}%" if float(valor) > 10 else f"{float(valor)*100:.2f}%"
def formatar_dy(valor):
    if valor is None or pd.isna(valor) or valor == 0: return "N/A"
    return f"{float(valor):.2f}%" if float(valor) > 1 else f"{float(valor)*100:.2f}%"
def formatar_abrev(valor):
    if valor is None or pd.isna(valor) or valor == 0: return "N/A"
    try:
        v = float(valor)
        if v >= 1e9: return f"{v/1e9:.2f} B"
        if v >= 1e6: return f"{v/1e6:.2f} M"
        return f"{v:.2f}"
    except: return "N/A"

def dataclass_to_dict(obj):
    if isinstance(obj, (AtivoRV, AtivoRF)):
        data = obj.__dict__.copy()
        if 'data_compra' in data and data['data_compra']: data['data_compra'] = data['data_compra'].strftime('%Y-%m-%d')
        if 'data_vencimento' in data and data['data_vencimento']: data['data_vencimento'] = data['data_vencimento'].strftime('%Y-%m-%d')
        return data
    return obj

def exportar_codigo_carteira(carteira_dict, nome_carteira):
    if not carteira_dict: return ""
    cart_export = {}
    for k, v in carteira_dict.items():
        v_copy = v.__dict__.copy() if hasattr(v, '__dict__') else dict(v)
        if 'data_compra' in v_copy and v_copy['data_compra'] is not None:
            v_copy['data_compra'] = v_copy['data_compra'].strftime('%Y-%m-%d') if hasattr(v_copy['data_compra'], 'strftime') else str(v_copy['data_compra'])
        if 'data_vencimento' in v_copy and v_copy['data_vencimento'] is not None:
            v_copy['data_vencimento'] = v_copy['data_vencimento'].strftime('%Y-%m-%d') if hasattr(v_copy['data_vencimento'], 'strftime') else str(v_copy['data_vencimento'])
        cart_export[k] = v_copy
    cart_export['__meta_nome__'] = nome_carteira
    return base64.b64encode(json.dumps(cart_export).encode('utf-8')).decode('utf-8')

def importar_codigo_carteira(codigo_b64):
    try:
        cart_bruto = json.loads(base64.b64decode(codigo_b64.encode('utf-8')).decode('utf-8'))
        nome_importado = cart_bruto.pop('__meta_nome__', 'Carteira Importada')
        cart = {}
        for k, v in cart_bruto.items():
            dt_compra = datetime.strptime(v['data_compra'], '%Y-%m-%d').date()
            if v['tipo'] == 'RV': cart[k] = AtivoRV(ticker=v['ticker'], aporte=v['aporte'], data_compra=dt_compra, setor=v['setor'])
            else:
                dt_venc = datetime.strptime(v['data_vencimento'], '%Y-%m-%d').date() if v.get('data_vencimento') else None
                cart[k] = AtivoRF(nome=v['nome'], indexador=v['indexador'], taxa=v['taxa'], aporte=v['aporte'], data_compra=dt_compra, data_vencimento=dt_venc)
        return cart, nome_importado
    except Exception as e:
        logging.error(f"Erro importação: {e}")
        return None, "Carteira Importada"

def ativar_modo_impressao(): st.session_state['modo_impressao'] = True
def desativar_modo_impressao(): st.session_state['modo_impressao'] = False


# --- FUNÇÕES AUXILIARES DO MOTOR DE PESOS DINÂMICOS ---
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

def balancear_pesos(changed_ticker):
    """Lógica matemática que mantém a soma dos sliders sempre em 100%"""
    new_val = st.session_state[f"slider_{changed_ticker}"]
    
    outros_tickers = [k for k in st.session_state.carteira.keys() if k != changed_ticker]
    
    if not outros_tickers:
        st.session_state.carteira[changed_ticker].aporte = 100.0
        st.session_state[f"slider_{changed_ticker}"] = 100.0
        return
        
    soma_outros = sum([getattr(st.session_state.carteira[k], 'aporte', 0) for k in outros_tickers])
    restante = max(0.0, 100.0 - new_val)
    
    for k in outros_tickers:
        if soma_outros > 0:
            proporcao = getattr(st.session_state.carteira[k], 'aporte', 0) / soma_outros
            novo_peso = restante * proporcao
        else:
            novo_peso = restante / len(outros_tickers)
        
        st.session_state.carteira[k].aporte = novo_peso
        st.session_state[f"slider_{k}"] = novo_peso
        
    st.session_state.carteira[changed_ticker].aporte = new_val

def igualar_pesos():
    """Divide 100% igualmente entre todos os ativos da carteira"""
    if st.session_state.carteira:
        num_ativos = len(st.session_state.carteira)
        peso_igual = 100.0 / num_ativos
        for k, v in st.session_state.carteira.items():
            v.aporte = peso_igual
            if f"slider_{k}" in st.session_state:
                st.session_state[f"slider_{k}"] = peso_igual
        st.session_state['carteira_alterada'] = True


# --- 4. TELA DE "SPLASH SCREEN" (RODA ANTES DO SIDEBAR) ---
if not st.session_state['started']:
    st.title("🏛️ LMF - ASSET")
    
    st.markdown("<br><br>", unsafe_allow_html=True)
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
                
    st.markdown(f"<br><br><div style='text-align:center; color:{theme['accent']}; opacity:0.6'>Idealizado por Bernardo V.</div>", unsafe_allow_html=True)
    st.stop() 


# --- 5. BARRA LATERAL (SÓ APARECE DEPOIS DE INICIAR O SISTEMA) ---
with st.sidebar:
    st.header("⚙️ Configuração Principal")
    st.session_state['nome_carteira'] = st.text_input("Nome da sua Carteira:", value=st.session_state.get('nome_carteira', 'Minha Carteira'))
    
    with st.expander("🎨 Estilo e Apresentação (Cores)", expanded=False):
        st.write("Insira a cor do fundo para os gráficos se adaptarem perfeitamente na exportação.")
        st.text_input("Hexadecimal (Ex: #FFFFFF ou #0b0b0b)", key="bg_color")
    
    st.markdown("<hr style='margin:10px 0; opacity: 0.3;'>", unsafe_allow_html=True)
    modo_aporte = st.radio("Método de Alocação", ["Por Peso (%)", "Por Valor Financeiro (R$)"], horizontal=True)
    
    col_cap, col_dt = st.columns(2)
    if modo_aporte == "Por Peso (%)":
        capital_inicial_input = col_cap.number_input("Capital Total (R$)", min_value=100.0, value=10000.0, step=1000.0)
    else:
        capital_inicial_input = 0.0 
        col_cap.text_input("Capital Total (R$)", value="Soma Automática", disabled=True)
        
    data_inicio = col_dt.date_input("Data Inicial", value=datetime(2012,1,1), min_value=datetime(1900,1,1), max_value=datetime.today())
    
    modificar_data_final = st.checkbox("Definir Data Final Específica?", value=False)
    if modificar_data_final:
        data_fim = st.date_input("Data Final", value=datetime.today().date(), min_value=data_inicio, max_value=datetime.today().date())
    else:
        data_fim = datetime.today().date()
        
    with st.expander("📊 Parâmetros de Mercado & Benchmarks", expanded=False):
        opcoes_bench = ["Ibovespa", "IFIX", "S&P 500", "NASDAQ", "SMLL (Small Caps)", "Ouro", "IPCA + Taxa", "CDI (Percentual)", "Selic"]
        benchmarks_sel = st.multiselect("Selecione os Benchmarks:", opcoes_bench, default=["Ibovespa"])
        taxa_ipca_bench, taxa_cdi_bench = 0.06, 1.0
        if "IPCA + Taxa" in benchmarks_sel: 
            taxa_ipca_bench = st.number_input("Taxa Fixa do IPCA+ (%)", value=6.0, step=0.1) / 100
        if "CDI (Percentual)" in benchmarks_sel: 
            taxa_cdi_bench = st.number_input("Percentual do CDI (%)", value=100.0, step=1.0) / 100
            
        st.markdown("<hr style='margin:10px 0; opacity: 0.3;'>", unsafe_allow_html=True)
        taxas_personalizadas = st.checkbox("Deseja taxas personalizadas?")
        
        c_taxa1, c_taxa2 = st.columns(2)
        if taxas_personalizadas:
            cdi_base = c_taxa1.number_input("CDI Base Global (%)", value=10.5, step=0.1) / 100
            ipca_base = c_taxa2.number_input("IPCA Base Global (%)", value=4.5, step=0.1) / 100
        else:
            c_taxa1.number_input("CDI Atual BCB (%)", value=10.5, disabled=True)
            c_taxa2.number_input("IPCA Atual BCB (%)", value=4.5, disabled=True)
            
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
    
    if modo_aporte == "Por Peso (%)":
        st.session_state['usar_sliders'] = st.checkbox("Ativar Balanceamento Dinâmico (Sliders)", value=st.session_state.get('usar_sliders', False))
    else:
        st.session_state['usar_sliders'] = False

    classe_ativo = st.radio("Classe do Ativo", ["Renda Variável", "Renda Fixa"], horizontal=True)
    
    if classe_ativo == "Renda Variável":
        st.warning("⚠️ Ativos listados na B3 exigem o final **.SA**.")
        c_rv1, c_rv2 = st.columns(2)
        ticker_add = c_rv1.text_input("Ticker").upper().strip()
        aporte_val = c_rv2.number_input("Peso/Valor Inicial", min_value=1.0, value=10.0 if modo_aporte=="Por Peso (%)" else 1000.0)
        setor_rv = st.selectbox("Setor (Opcional)", OPCOES_SETORES)
        comprado_inicio_rv = st.checkbox("Desde o Início?", value=True, key="chk_rv")
        data_compra_rv = data_inicio if comprado_inicio_rv else st.date_input("Comprado em", value=data_inicio, min_value=data_inicio, max_value=data_fim)
        
        if st.button("Inserir Renda Variável") and ticker_add:
            if re.match(r'^[A-Z0-9\.\-\=]+$', ticker_add): 
                st.session_state.carteira[ticker_add] = AtivoRV(ticker=ticker_add, aporte=aporte_val, data_compra=data_compra_rv, setor=setor_rv)
                st.session_state['carteira_alterada'] = True
                st.rerun()
            else:
                st.error("Ticker inválido.")
    else:
        nome_rf = st.text_input("Nome do Título").strip()
        c_rf1, c_rf2, c_rf3 = st.columns([1.5, 1.5, 1])
        tipo_rf_add = c_rf1.selectbox("Indexador", ["Prefixado", "CDI", "IPCA+"])
        
        if tipo_rf_add == "CDI":
            taxa_input_add = c_rf2.number_input("Percentual do CDI (%)", value=100.0, step=1.0)
        elif tipo_rf_add == "IPCA+":
            taxa_input_add = c_rf2.number_input("Taxa Fixa (%)", value=6.0, step=0.1)
        else:
            taxa_input_add = c_rf2.number_input("Taxa Anual (%)", value=10.0, step=0.1)
            
        aporte_val_rf = c_rf3.number_input("Peso/Valor Inicial", min_value=1.0, value=10.0 if modo_aporte=="Por Peso (%)" else 1000.0)
        
        c_rf4, c_rf5 = st.columns(2)
        comprado_inicio_rf = c_rf4.checkbox("Desde o Início?", value=True, key="chk_rf")
        data_compra_rf = data_inicio if comprado_inicio_rf else c_rf4.date_input("Aplicado em", value=data_inicio, min_value=data_inicio, max_value=data_fim)
        data_vencimento_rf = c_rf5.date_input("Vencimento (MTM)", value=datetime(2030,1,1).date())

        if st.button("Inserir Renda Fixa") and nome_rf:
            st.session_state.carteira[nome_rf] = AtivoRF(nome=nome_rf, indexador=tipo_rf_add, taxa=taxa_input_add/100, aporte=aporte_val_rf, data_compra=data_compra_rf, data_vencimento=data_vencimento_rf)
            st.session_state['carteira_alterada'] = True
            st.rerun()
            
    if st.button("🗑️ Limpar Carteira Principal"):
        st.session_state.carteira = {}
        st.session_state['carteira_alterada'] = True
        st.rerun()

# --- NORMALIZAÇÃO INICIAL DE SEGURANÇA (CASO SLIDERS LIGADOS) ---
if st.session_state.carteira and modo_aporte == "Por Peso (%)" and st.session_state.get('usar_sliders', False):
    total_peso = sum([getattr(v, 'aporte', 0) for v in st.session_state.carteira.values()])
    if total_peso > 0 and abs(total_peso - 100.0) > 0.01:
        for k, v in st.session_state.carteira.items():
            v.aporte = (v.aporte / total_peso) * 100.0
            if f"slider_{k}" in st.session_state:
                st.session_state[f"slider_{k}"] = v.aporte

# --- MOTOR DE DADOS OTIMIZADO E BLINDADO ---
@st.cache_data(ttl=600)
def download_precos_limpos(tickers, start, end_date):
    if not tickers:
        return pd.DataFrame(), pd.DataFrame()
    with st.spinner("Baixando e otimizando dados..."):
        try:
            end_dt = pd.to_datetime(end_date) + timedelta(days=1)
            df = yf.download(tickers, start=start, end=end_dt, progress=False, auto_adjust=False)
            if df.empty:
                return pd.DataFrame(), pd.DataFrame()
                
            df_adj = df['Adj Close'] if 'Adj Close' in df.columns.levels[0] else df['Close']
            df_close = df['Close']
            
            if isinstance(df_adj, pd.Series):
                df_adj = df_adj.to_frame(name=tickers[0])
                df_close = df_close.to_frame(name=tickers[0])
                
            return df_adj.ffill().bfill(), df_close.ffill().bfill()
        except:
            return pd.DataFrame(), pd.DataFrame()

@st.cache_data(ttl=86400) 
def fetch_br_indicators(codigo, start_date, end_date):
    try:
        url = f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados?formato=json&dataInicial={start_date.strftime('%d/%m/%Y')}&dataFinal={end_date.strftime('%d/%m/%Y')}"
        df = pd.read_json(url)
        df['data'] = pd.to_datetime(df['data'], format='%d/%m/%Y')
        df.set_index('data', inplace=True)
        return df['valor'] / 100
    except:
        return pd.Series(dtype=float)

@st.cache_data(ttl=3600)
def fetch_fundamental_info(ticker):
    try:
        return yf.Ticker(ticker).info
    except:
        return {}

@st.cache_data(ttl=3600)
def fetch_historical_fundamentals(ticker):
    try:
        t = yf.Ticker(ticker)
        return t.financials, t.balance_sheet, t.cashflow
    except:
        return None, None, None

def calcular_metricas(ret_p, ret_m, cdi_s):
    if ret_p.empty:
        return [0]*8
    if ret_m.empty:
        ret_m = pd.Series(0, index=ret_p.index)
    if cdi_s.empty:
        cdi_s = pd.Series(0, index=ret_p.index)
        
    df = pd.concat([ret_p, ret_m, cdi_s], axis=1).dropna()
    if df.empty:
        return [0]*8
        
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
        rs_serie = pd.Series((1 + v.taxa)**(1/252) - 1, index=idx_m)
    elif v.indexador == "CDI":
        rs_serie = cdi_al * v.taxa
    elif v.indexador == "IPCA+":
        rs_serie = ((1 + ipca_al) * (1 + v.taxa)**(1/252)) - 1
        
    rs_serie[rs_serie.index < data_c] = 0.0
    
    if marcar_mercado and v.data_vencimento:
        dt_venc = pd.to_datetime(v.data_vencimento)
        anos_restantes = np.maximum((dt_venc - rs_serie.index).days, 0) / 365.25
        tx_anual_mercado = (1 + cdi_al)**252 - 1
        delta_yield = tx_anual_mercado.diff().fillna(0)
        choque_mtm = - (anos_restantes * delta_yield) / (1 + tx_anual_mercado)
        rs_serie = rs_serie + choque_mtm
        rs_serie[rs_serie.index < data_c] = 0.0
        
    return rs_serie

def processar_carteira(dict_carteira, df_rv_c, df_rv_s, cdi_al, ipca_al, idx_m, reinvest_flag, marcar_mercado, setor_filter="Carteira Completa"):
    if setor_filter != "Carteira Completa":
        dict_carteira = {k: v for k, v in dict_carteira.items() if (getattr(v, 'setor', 'Outros') if getattr(v, 'tipo', 'RV') == 'RV' else 'Renda Fixa') == setor_filter}
        
    if not dict_carteira:
        return pd.Series(0, index=idx_m), pd.Series(0, index=idx_m)
        
    ret_c = pd.DataFrame(index=idx_m)
    ret_s = pd.DataFrame(index=idx_m)
    tickers_val = []
    aportes_val = []
    
    for k, v in dict_carteira.items():
        data_c = pd.to_datetime(v.data_compra)
        if getattr(v, 'tipo', 'RV') == 'RV' and k in df_rv_c.columns:
            rc = df_rv_c[k].pct_change().fillna(0)
            rs = df_rv_s[k].pct_change().fillna(0)
            rc[rc.index < data_c] = 0.0
            rs[rs.index < data_c] = 0.0
            ret_c[k] = rc
            ret_s[k] = rs
            tickers_val.append(k)
            aportes_val.append(v.aporte)
        elif getattr(v, 'tipo', 'RV') == 'RF':
            rs_serie = calcular_serie_rf(v, cdi_al, ipca_al, idx_m, marcar_mercado)
            ret_c[k] = rs_serie
            ret_s[k] = rs_serie
            tickers_val.append(k)
            aportes_val.append(v.aporte)
            
    if not tickers_val:
        return pd.Series(0, index=idx_m), pd.Series(0, index=idx_m)
        
    aportes_array = np.array(aportes_val)
    if aportes_array.sum() == 0:
        return pd.Series(0, index=idx_m), pd.Series(0, index=idx_m)
        
    pesos = aportes_array / aportes_array.sum()
    return (ret_c[tickers_val] * pesos).sum(axis=1), (ret_s[tickers_val] * pesos).sum(axis=1)

def calcular_retorno_individual(config, df_rv_c, df_rv_s, cdi_al, ipca_al, idx_m, reinvest_flag, marcar_mercado):
    data_c = pd.to_datetime(config.data_compra)
    if getattr(config, 'tipo', 'RV') == 'RV':
        df_uso = df_rv_c if reinvest_flag else df_rv_s
        if config.ticker in df_uso.columns:
            r = df_uso[config.ticker].pct_change().fillna(0)
            r[r.index < data_c] = 0.0
            return (1 + r).prod() - 1
    elif getattr(config, 'tipo', 'RV') == 'RF':
        return (1 + calcular_serie_rf(config, cdi_al, ipca_al, idx_m, marcar_mercado)).prod() - 1
    return 0.0

def plot_markowitz(ativos_dict, df_rv_c, cdi_al, idx_m, th):
    ativos_rv_validos = [k for k, v in ativos_dict.items() if getattr(v, 'tipo', 'RV') == 'RV']
    if len(ativos_rv_validos) < 2:
        st.warning("É preciso 2 ativos de RV para simular a Fronteira.")
        return
        
    with st.spinner("Simulando 5.000 portfólios e calculando Fronteira Eficiente..."):
        ret_ativos = pd.DataFrame(index=idx_m)
        for t in ativos_rv_validos:
            rc = df_rv_c[t].pct_change().fillna(0)
            rc[rc.index < pd.to_datetime(ativos_dict[t].data_compra)] = 0.0
            ret_ativos[t] = rc
            
        ret_medios = ret_ativos.mean() * 252
        cov_mat = ret_ativos.cov() * 252
        
        np.random.seed(42)
        pesos = np.random.random((5000, len(ativos_rv_validos)))
        pesos = pesos / np.sum(pesos, axis=1)[:, np.newaxis]
        
        rets_esp = np.dot(pesos, ret_medios)
        vols_esp = np.sqrt(np.einsum('ij,jk,ik->i', pesos, cov_mat, pesos))
        cdi_medio = ((1 + cdi_al).prod() ** (252 / max(1, len(cdi_al))) - 1) if len(cdi_al) > 0 else 0.105
        sharpes_esp = (rets_esp - cdi_medio) / (vols_esp + 1e-8)
        
        df_ef = pd.DataFrame({'Retorno': rets_esp, 'Volatilidade': vols_esp, 'Sharpe': sharpes_esp})
        p_max = df_ef.iloc[df_ef['Sharpe'].idxmax()]
        
        fig = px.scatter(df_ef, x='Volatilidade', y='Retorno', color='Sharpe', color_continuous_scale='Viridis')
        fig.add_trace(go.Scatter(x=[p_max['Volatilidade']], y=[p_max['Retorno']], mode='markers', marker=dict(color='red', size=15, symbol='star'), name='Máximo Sharpe'))
        
        min_vol_idx = df_ef['Volatilidade'].idxmin()
        min_vol_ret = df_ef.loc[min_vol_idx, 'Retorno']
        
        df_upper = df_ef[df_ef['Retorno'] >= min_vol_ret].copy()
        df_upper['Vol_Bin'] = (df_upper['Volatilidade'] * 500).round() / 500
        
        fronteira = df_upper.groupby('Vol_Bin')['Retorno'].max().reset_index()
        fronteira = fronteira.sort_values('Vol_Bin')
        
        vols_linha = []
        rets_linha = []
        max_ret_atual = -np.inf
        
        for _, row in fronteira.iterrows():
            if row['Retorno'] >= max_ret_atual:
                vols_linha.append(row['Vol_Bin'])
                rets_linha.append(row['Retorno'])
                max_ret_atual = row['Retorno']
        
        fig.add_trace(go.Scatter(
            x=vols_linha, y=rets_linha, 
            mode='lines', 
            line=dict(color=th['text_main'], width=2, dash='dot'), 
            name='Fronteira Eficiente'
        ))
        
        fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color=th['text_main']))
        fig.update_xaxes(gridcolor=th['grid'], tickfont=dict(color=th['text_sec']))
        fig.update_yaxes(gridcolor=th['grid'], tickfont=dict(color=th['text_sec']))
        
        st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

def plot_var_histogram(ret_port, title, line_color, th):
    ret_valido = ret_port.dropna()
    if len(ret_valido) == 0:
        st.warning("Dados insuficientes.")
        return
        
    var_5 = np.percentile(ret_valido, 5)
    fig = px.histogram(ret_valido, nbins=50, title=title, color_discrete_sequence=[th['accent']])
    fig.add_vline(x=var_5, line_dash="dash", line_color=line_color, annotation_text=f"VaR 5% = {var_5:.4f}")
    
    fig.update_layout(showlegend=False, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color=th['text_main']))
    fig.update_xaxes(gridcolor=th['grid'], tickfont=dict(color=th['text_sec']))
    fig.update_yaxes(gridcolor=th['grid'], tickfont=dict(color=th['text_sec']))
    
    st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

def plot_correlation_matrix(ativos_dict, df_rv_c, idx_m, setor_filter, th):
    if setor_filter == "Carteira Completa":
        dict_uso = ativos_dict
    else:
        dict_uso = {k: v for k, v in ativos_dict.items() if (getattr(v, 'setor', 'Outros') if getattr(v, 'tipo', 'RV') == 'RV' else 'Renda Fixa') == setor_filter}
        
    ativos_rv = [k for k, v in dict_uso.items() if getattr(v, 'tipo', 'RV') == 'RV']
    
    if len(ativos_rv) < 2:
        st.warning(f"Precisa de 2 ativos RV no setor '{setor_filter}'.")
        return
        
    with st.spinner(f"Calculando matriz de correlação para {len(ativos_rv)} ativos..."):
        df_ret = pd.DataFrame(index=idx_m)
        for t in ativos_rv:
            r = df_rv_c[t].pct_change().fillna(0)
            r[r.index < pd.to_datetime(ativos_dict[t].data_compra)] = np.nan 
            df_ret[t] = r
            
        corr_matrix = df_ret.corr().fillna(0)
        
        fig = px.imshow(corr_matrix, text_auto=".2f", aspect="auto", color_continuous_scale="RdBu_r", zmin=-1, zmax=1, title=f"Correlação - {setor_filter}")
        
        fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color=th['text_main']))
        fig.update_xaxes(tickfont=dict(color=th['text_main']))
        fig.update_yaxes(tickfont=dict(color=th['text_main']))
        
        st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)
        
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(f"<h4 style='color: {th['accent']};'>🔍 Destaques da Matriz</h4>", unsafe_allow_html=True)
        
        if len(ativos_rv) > 2:
            upper_tri = corr_matrix.where(np.triu(np.ones(corr_matrix.shape), k=1).astype(bool))
            corr_pairs = upper_tri.unstack().dropna().sort_values(ascending=False)
            
            if len(corr_pairs) >= 2:
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown("**Maiores Correlações (Movimento Similar):**")
                    top_2 = corr_pairs.head(2)
                    for (ativo1, ativo2), val in top_2.items():
                        st.info(f"**{ativo1} & {ativo2}**: {val:.2f}")
                        
                with c2:
                    st.markdown("**Menores Correlações (Proteção/Movimento Oposto):**")
                    bottom_2 = corr_pairs.sort_values(ascending=True).head(2)
                    for (ativo1, ativo2), val in bottom_2.items():
                        st.error(f"**{ativo1} & {ativo2}**: {val:.2f}")
        elif len(ativos_rv) == 2:
            ativo1, ativo2 = ativos_rv[0], ativos_rv[1]
            val = corr_matrix.loc[ativo1, ativo2]
            if val >= 0:
                st.info(f"**{ativo1} & {ativo2}**: {val:.2f}")
            else:
                st.error(f"**{ativo1} & {ativo2}**: {val:.2f}")

def plot_monte_carlo(ret_portfolio, capital_inicial, th):
    if ret_portfolio.empty or ret_portfolio.std() == 0:
        st.warning("Dados inválidos para Monte Carlo.")
        return
        
    with st.spinner("Simulando 1.000 caminhos..."):
        mu = ret_portfolio.mean()
        vol = ret_portfolio.std()
        
        ret_simulados = np.exp((mu - 0.5 * vol**2) + vol * np.random.normal(0, 1, (252, 1000)))
        caminhos = capital_inicial * np.vstack([np.ones(1000), ret_simulados]).cumprod(axis=0)
        var_1_mc = np.percentile(caminhos[-1, :], 1) 
        
        fig = go.Figure()
        eixo_x = np.arange(253)
        for i in range(500):
            fig.add_trace(go.Scatter(x=eixo_x, y=caminhos[:, i], mode='lines', line=dict(width=1), opacity=0.15, showlegend=False, hoverinfo='skip'))
            
        fig.add_trace(go.Scatter(x=[0, 252], y=[capital_inicial, capital_inicial], mode='lines', line=dict(color=th['line_base'], width=3), name='Initial'))
        fig.add_trace(go.Scatter(x=[0, 252], y=[var_1_mc, var_1_mc], mode='lines', line=dict(color=th['loss'], width=3, dash='dash'), name=f'VaR 1% MC ({formatar_moeda(var_1_mc)})'))
        
        fig.update_layout(title=f"Monte Carlo (1 Ano) | VaR 1%: {formatar_moeda(var_1_mc)}", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color=th['text_main']), legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01, font=dict(color=th['text_main'])))
        fig.update_yaxes(gridcolor=th['grid'], tickfont=dict(color=th['text_sec']))
        fig.update_xaxes(gridcolor=th['grid'], tickfont=dict(color=th['text_sec']))
        
        st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

def compara_metrica(val_p, val_c, is_higher_better=True, is_pct=True):
    vp = f"{val_p:.2%}" if is_pct else f"{val_p:.2f}"
    vc = f"{val_c:.2%}" if is_pct else f"{val_c:.2f}"
    
    if val_p == val_c:
        return vp, vc, "Empate"
        
    if is_higher_better:
        venceu_p = val_p > val_c
    else:
        venceu_p = val_p < val_c
        
    if venceu_p:
        return f"⭐ {vp}", vc, "Principal"
    else:
        return vp, f"⭐ {vc}", "Comparada"

def plot_tabela_metricas(m_prin, nome_cart, th):
    fig = go.Figure(data=[go.Table(
        header=dict(values=['Métrica', nome_cart], fill_color=th['bg_card'], font=dict(color=th['accent'], size=16), align='center', height=40),
        cells=dict(values=[
            ['Rentabilidade Acumulada', 'Índice Sharpe', 'Índice Sortino', 'Volatilidade Anual', 'Max Drawdown', 'Alpha de Jensen', 'Beta vs Bench.'], 
            [f"{m_prin[0]:.2%}", f"{m_prin[2]:.2f}", f"{m_prin[3]:.2f}", f"{m_prin[1]:.2%}", f"{m_prin[4]:.2%}", f"{m_prin[7]:.2%}", f"{m_prin[6]:.2f}"]
        ], fill_color=th['bg'], line_color=th['grid'], font=dict(color=th['text_main'], size=15), align='center', height=35)
    )])
    
    fig.update_layout(margin=dict(l=0, r=0, t=0, b=0), paper_bgcolor='rgba(0,0,0,0)', height=300)
    return fig

if not st.session_state.carteira:
    st.info("🏛️ Adicione ativos na barra lateral para iniciar a análise.")

nome_cart = st.session_state.get('nome_carteira', 'Minha Carteira')
nome_comp = st.session_state.get('nome_carteira_comparacao', 'Carteira Importada')

# --- EXECUÇÃO DO MOTOR ---
garantir_dataclasses_state()

if st.session_state.carteira:
    ativos_rv_principal = [k for k, v in st.session_state.carteira.items() if getattr(v, 'tipo', 'RV') == 'RV']
    ativos_rv_comp = [k for k, v in st.session_state.carteira_comparacao.items() if getattr(v, 'tipo', 'RV') == 'RV']
    
    mapa_bench = {"Ibovespa": "^BVSP", "IFIX": "XFIX11.SA", "S&P 500": "^GSPC", "NASDAQ": "^IXIC", "SMLL (Small Caps)": "SMAL11.SA", "Ouro": "GC=F"}
    tickers_bench_b3 = [mapa_bench[b] for b in benchmarks_sel if b in mapa_bench]
    todos_tickers = list(set(ativos_rv_principal + ativos_rv_comp + tickers_bench_b3))

    df_rv_com, df_rv_sem = download_precos_limpos(todos_tickers, data_inicio, data_fim) 
    
    if not df_rv_com.empty:
        idx_mestre = df_rv_com.dropna(how='all').index
    else:
        idx_mestre = pd.bdate_range(start=data_inicio, end=data_fim)
        
    if len(idx_mestre) == 0:
        idx_mestre = pd.bdate_range(start=data_inicio, end=data_fim)
    
    cdi_series = fetch_br_indicators(12, data_inicio, data_fim)
    if cdi_series.empty:
        cdi_al = pd.Series((1 + 0.105)**(1/252) - 1, index=idx_mestre)
    else:
        cdi_al = cdi_series.reindex(idx_mestre).fillna(0)
        
    ipca_s = fetch_br_indicators(433, data_inicio, data_fim)
    if ipca_s.empty:
        ipca_al = pd.Series((1 + 0.045)**(1/252) - 1, index=idx_mestre)
    else:
        ipca_al = ((1 + ipca_s)**(1/21) - 1).reindex(pd.date_range(start=ipca_s.index.min(), end=data_fim)).ffill().reindex(idx_mestre).fillna(0)

    dict_ret_benchs = {}
    for b in benchmarks_sel:
        if b == "CDI (Percentual)":
            dict_ret_benchs[b] = cdi_al * taxa_cdi_bench
        elif b == "Selic":
            dict_ret_benchs[b] = fetch_br_indicators(11, data_inicio, data_fim).reindex(idx_mestre).fillna(0)
        elif b == "IPCA + Taxa":
            dict_ret_benchs[b] = (1 + ipca_al) * (1 + taxa_ipca_bench)**(1/252) - 1
        elif b in mapa_bench and mapa_bench[b] in df_rv_com.columns:
            dict_ret_benchs[b] = df_rv_com[mapa_bench[b]].pct_change().fillna(0)
            
    nome_bench_principal = benchmarks_sel[0] if benchmarks_sel else "Benchmark Padrão"
    ret_bench_principal = dict_ret_benchs.get(nome_bench_principal, pd.Series(0, index=idx_mestre))

    ret_port_com, ret_port_sem = processar_carteira(st.session_state.carteira, df_rv_com, df_rv_sem, cdi_al, ipca_al, idx_mestre, reinvestir, marcar_mercado_ativado)
    ret_portfolio_principal = ret_port_com if reinvestir else ret_port_sem
    
    if st.session_state.carteira_comparacao:
        garantir_dataclasses_state_comparacao()
        ret_comp_com, ret_comp_sem = processar_carteira(st.session_state.carteira_comparacao, df_rv_com, df_rv_sem, cdi_al, ipca_al, idx_mestre, reinvestir_comp, False)
        ret_portfolio_comparacao = ret_comp_com if reinvestir_comp else ret_comp_sem

    aportes_brutos = np.array([getattr(v, 'aporte', 0) for v in st.session_state.carteira.values()])
    capital_inicial = aportes_brutos.sum() if modo_aporte == "Por Valor Financeiro (R$)" else capital_inicial_input
    
    if aportes_brutos.sum() > 0:
        pesos_norm = aportes_brutos / aportes_brutos.sum()
    else:
        pesos_norm = aportes_brutos * 0
        
    m_prin = calcular_metricas(ret_portfolio_principal, ret_bench_principal, cdi_al)

    # Gráficos Base
    df_pizza = pd.DataFrame({'Ativo': list(st.session_state.carteira.keys()), 'Peso': pesos_norm})
    fig_pizza_base = px.pie(df_pizza, values='Peso', names='Ativo', hole=0.5, color_discrete_sequence=theme['chart_seq'])
    fig_pizza_base.update_layout(paper_bgcolor='rgba(0,0,0,0)', font=dict(color=theme['text_main']), margin=dict(t=0, b=0, l=0, r=0))

    html_table_rx = f"<table><tr><th>Ativo</th><th>Classe</th><th>Setor</th><th>Capital Alocado</th><th>Retorno (Sem Div)</th><th>Retorno (Com Div)</th><th>Saldo Atualizado</th></tr>"
    for i, (t, config) in enumerate(st.session_state.carteira.items()):
        ret_c = calcular_retorno_individual(config, df_rv_com, df_rv_sem, cdi_al, ipca_al, idx_mestre, True, marcar_mercado_ativado)
        ret_s = calcular_retorno_individual(config, df_rv_com, df_rv_sem, cdi_al, ipca_al, idx_mestre, False, marcar_mercado_ativado)
        
        val_inicial = getattr(config, 'aporte', 0) if modo_aporte == "Por Valor Financeiro (R$)" else capital_inicial * pesos_norm[i]
        val_final = val_inicial * (1 + (ret_c if reinvestir else ret_s))
        
        color_s = theme['win'] if ret_s >= 0 else theme['loss']
        color_c = theme['win'] if ret_c >= 0 else theme['loss']
        
        setor_rx = getattr(config, 'setor', 'Outros') if getattr(config, 'tipo', 'RV')=='RV' else 'Renda Fixa'
        
        html_table_rx += f"<tr><td><b>{t}</b></td><td>{getattr(config, 'tipo', 'RV')}</td><td>{setor_rx}</td><td>{formatar_moeda(val_inicial)}</td><td style='color:{color_s}'><b>{formatar_percentual(ret_s)}</b></td><td style='color:{color_c}'><b>{formatar_percentual(ret_c)}</b></td><td><b>{formatar_moeda(val_final)}</b></td></tr>"
    html_table_rx += "</table>"

    df_rent = pd.DataFrame({f"{nome_cart} (%)": ((1 + ret_portfolio_principal).cumprod() - 1) * 100}, index=idx_mestre)
    color_map = {f"{nome_cart} (%)": theme['accent']}
    
    if st.session_state.carteira_comparacao:
        df_rent[f"{nome_comp} (%)"] = ((1 + ret_portfolio_comparacao).cumprod() - 1) * 100
        color_map[f"{nome_comp} (%)"] = theme['accent_comp']
        
    for nb, serie in dict_ret_benchs.items():
        df_rent[f"{nb} (%)"] = ((1 + serie).cumprod() - 1) * 100
        
    fig_rent_global = px.line(df_rent, color_discrete_map=color_map)
    fig_rent_global.update_layout(xaxis_title="", yaxis_title="Acumulado (%)", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color=theme['text_main']))
    fig_rent_global.update_xaxes(gridcolor=theme['grid'], tickfont=dict(color=theme['text_sec']))
    fig_rent_global.update_yaxes(gridcolor=theme['grid'], tickfont=dict(color=theme['text_sec']))

    # --- MODO DE IMPRESSÃO ---
    if st.session_state.get('modo_impressao', False):
        st.button("⬅️ VOLTAR AO DASHBOARD NORMAL", on_click=desativar_modo_impressao)
        
        st.markdown(f"<h1 style='text-align: center; color: {theme['accent']}; font-size: 3em;'>{nome_cart}</h1>", unsafe_allow_html=True)
        st.markdown(f"<h3 style='text-align: center; color: {theme['text_sec']}; margin-top: -15px;'>Relatório de Desempenho | Powered by LMF - ASSET</h3>", unsafe_allow_html=True)
        st.markdown("---")
        
        if st.session_state.get('rel_comp', True):
            st.subheader("1. Composição")
            st.plotly_chart(fig_pizza_base, use_container_width=True, config=PLOTLY_CONFIG, key="print_p")
            
        if st.session_state.get('rel_metr', True):
            st.subheader("2. Quadro de Métricas")
            st.plotly_chart(plot_tabela_metricas(m_prin, nome_cart, theme), use_container_width=True, config=PLOTLY_CONFIG, key="print_t")
            
        if st.session_state.get('rel_rent', True):
            st.subheader("3. Evolução Histórica")
            st.plotly_chart(fig_rent_global, use_container_width=True, config=PLOTLY_CONFIG, key="print_r")
            
        if st.session_state.get('rel_rx', False):
            st.subheader("4. Raio-X Individual")
            st.markdown(html_table_rx, unsafe_allow_html=True)
            
        c_b1, c_b2, c_b3 = st.columns([1,2,1])
        with c_b2:
            if st.button("🖨️ CONFIRMAR IMPRESSÃO / SALVAR PDF", use_container_width=True):
                components.html("<script>window.parent.print();</script>", height=0)
        st.stop()

    # --- MODO DASHBOARD NORMAL ---
    st.markdown(f"<h1 style='color: {theme['accent']}; font-size: 3rem; margin-bottom: -15px;'>🏛️ {nome_cart}</h1>", unsafe_allow_html=True)
    st.markdown(f"<h4 style='color: {theme['text_sec']}; margin-bottom: 30px; opacity: 0.8;'>Portfólio Management System | LMF ASSET</h4>", unsafe_allow_html=True)

    st.header("📊 Resumo de Desempenho")
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Capital Inicial", formatar_moeda(capital_inicial))
    
    patrimonio_final = capital_inicial * (1 + m_prin[0])
    c2.metric("Saldo Atualizado", formatar_moeda(patrimonio_final), formatar_moeda(capital_inicial * m_prin[0]))
    
    ret_port_com_acum = (1 + ret_port_com).prod() - 1
    ret_port_sem_acum = (1 + ret_port_sem).prod() - 1
    c3.metric("Impacto dos Dividendos", f"{(ret_port_com_acum - ret_port_sem_acum):.2%}")
    
    c4, c5, c6, c7 = st.columns(4)
    c4.metric("Rentabilidade Acumulada", f"{m_prin[0]:.2%}")
    c5.metric("Alpha de Jensen", f"{m_prin[7]:.2%}")
    c6.metric("Índice Sharpe", f"{m_prin[2]:.2f}")
    c7.metric("Índice Sortino", f"{m_prin[3]:.2f}")
    
    c8, c9, c10, c11 = st.columns(4)
    c8.metric("Volatilidade Anual", f"{m_prin[1]:.2%}")
    c9.metric("Max Drawdown", f"{m_prin[4]:.2%}")
    c10.metric("VaR Histórico 5%", f"{m_prin[5]:.2%}")
    c11.metric(f"Beta vs {nome_bench_principal}", f"{m_prin[6]:.2f}")
    
    st.divider()

    abas = ["📈 Alocação e Rentabilidade", "🔎 Raio-X Individual", "⚙️ Estudo das Métricas", "📊 Comparação Setorial"]
    if st.session_state.carteira_comparacao:
        abas.append("🆚 Análise de Comparação")
    abas.extend(["🔍 Análise de Ativos", "📑 Relatório Exportável"])
    
    tabs = st.tabs(abas)

    with tabs[0]:
        c_a, c_b = st.columns([1.2, 1.5])
        
        with c_a:
            if st.session_state.get('usar_sliders', False) and modo_aporte == "Por Peso (%)":
                st.markdown("### 🛒 Rebalanceamento Dinâmico")
                st.caption("Deslize as barras para alterar o peso da carteira. A soma é forçada automaticamente a 100%.")
                
                st.button("⚖️ Igualar Pesos", on_click=igualar_pesos, use_container_width=True)
                st.markdown("<br>", unsafe_allow_html=True)
                
                for t, config in st.session_state.carteira.items():
                    c_1, c_2, c_3 = st.columns([3, 5, 1])
                    
                    data_inicio_ativo = getattr(config, 'data_compra').strftime('%d/%m/%y') if hasattr(config, 'data_compra') else ''
                    setor_str = getattr(config, 'setor', 'Outros') if getattr(config, 'tipo', 'RV') == 'RV' else 'Renda Fixa'
                    peso_atual = st.session_state.get(f"slider_{t}", float(getattr(config, 'aporte', 0)))
                    
                    c_1.markdown(f"**{t}** ({peso_atual:.1f}%)<br><span style='font-size:0.8em; opacity:0.7;'>{setor_str}</span>", unsafe_allow_html=True)
                    
                    if f"slider_{t}" not in st.session_state:
                        st.session_state[f"slider_{t}"] = peso_atual
                    
                    with c_2:
                        st.slider(
                            "Peso", 
                            min_value=0.0, 
                            max_value=100.0, 
                            value=peso_atual, 
                            step=0.1, 
                            key=f"slider_{t}", 
                            on_change=balancear_pesos, 
                            args=(t,), 
                            label_visibility="collapsed"
                        )
                        
                    if c_3.button("❌", key=f"del_{t}"):
                        del st.session_state.carteira[t]
                        if f"slider_{t}" in st.session_state:
                            del st.session_state[f"slider_{t}"]
                        st.rerun()
            else:
                st.markdown("### 🛒 Posições Atuais")
                
                if modo_aporte == "Por Peso (%)":
                    st.button("⚖️ Igualar Pesos", on_click=igualar_pesos, use_container_width=True)
                    st.markdown("<br>", unsafe_allow_html=True)
                
                for i, (t, config) in enumerate(st.session_state.carteira.items()):
                    c_1, c_2, c_3 = st.columns([3, 2, 1])
                    
                    dt_str = getattr(config, 'data_compra').strftime('%d/%m/%y') if hasattr(config, 'data_compra') and hasattr(getattr(config, 'data_compra'), 'strftime') else str(getattr(config, 'data_compra', ''))
                    setor_str = getattr(config, 'setor', 'Outros') if getattr(config, 'tipo', 'RV') == 'RV' else 'Renda Fixa'
                    
                    c_1.markdown(f"**{t}** *(Início: {dt_str} | {setor_str})*")
                    
                    info_peso = f"{pesos_norm[i]:.1%}" if modo_aporte == "Por Peso (%)" else formatar_moeda(getattr(config, 'aporte', 0))
                    c_2.markdown(info_peso)
                    
                    if c_3.button("❌", key=f"del_{t}"):
                        del st.session_state.carteira[t]
                        st.session_state['carteira_alterada'] = True
                        st.rerun()
                        
        with c_b:
            visao_grafico = st.radio("Visualizar Alocação:", ["Ativos", "Setores"], horizontal=True)
            if visao_grafico == "Ativos":
                st.plotly_chart(fig_pizza_base, use_container_width=True, config=PLOTLY_CONFIG, key="p1")
            else:
                lista_setores = [getattr(v, 'setor', 'Outros') if getattr(v, 'tipo', 'RV') == 'RV' else 'Renda Fixa' for v in st.session_state.carteira.values()]
                df_sec = pd.DataFrame({'Setor': lista_setores, 'Peso': pesos_norm}).groupby('Setor', as_index=False).sum()
                
                fig_sec = px.pie(df_sec, values='Peso', names='Setor', hole=0.5, color_discrete_sequence=theme['chart_seq'])
                fig_sec.update_layout(paper_bgcolor='rgba(0,0,0,0)', font=dict(color=theme['text_main']), margin=dict(t=0,b=0,l=0,r=0))
                st.plotly_chart(fig_sec, use_container_width=True, config=PLOTLY_CONFIG, key="p2")
                
        st.markdown("### 📈 Evolução de Rentabilidade")
        st.plotly_chart(fig_rent_global, use_container_width=True, config=PLOTLY_CONFIG, key="r1")

    with tabs[1]:
        st.markdown("### 🔎 Análise Individual de Performance")
        st.markdown(html_table_rx, unsafe_allow_html=True)

    with tabs[2]:
        cm1, cm2 = st.columns(2)
        metrica_sel = cm1.selectbox("Estudo Avançado:", ["Fronteira Eficiente (Markowitz)", "Value at Risk (VaR Histórico)", "Drawdown Histórico", "Volatilidade Rolante", "Beta (Risco de Mercado)", "Matriz de Correlação", "Simulação de Monte Carlo"])
        
        lista_setores_filtro = list(set([getattr(v, 'setor', 'Outros') if getattr(v, 'tipo', 'RV') == 'RV' else 'Renda Fixa' for v in st.session_state.carteira.values()]))
        setor_filtro = cm2.selectbox("Filtro Setorial:", ["Carteira Completa"] + lista_setores_filtro)
        
        if setor_filtro == "Carteira Completa":
            dict_estudo = st.session_state.carteira
            ret_estudo = ret_portfolio_principal
        else:
            dict_estudo = {k: v for k, v in st.session_state.carteira.items() if (getattr(v, 'setor', 'Outros') if getattr(v, 'tipo', 'RV') == 'RV' else 'Renda Fixa') == setor_filtro}
            ret_estudo_com_f, ret_estudo_sem_f = processar_carteira(st.session_state.carteira, df_rv_com, df_rv_sem, cdi_al, ipca_al, idx_mestre, reinvestir, marcar_mercado_ativado, setor_filter=setor_filtro)
            ret_estudo = ret_estudo_com_f if reinvestir else ret_estudo_sem_f

        if metrica_sel == "Matriz de Correlação":
            plot_correlation_matrix(st.session_state.carteira, df_rv_com, idx_mestre, setor_filtro, theme)
            
        elif metrica_sel == "Simulação de Monte Carlo":
            plot_monte_carlo(ret_estudo, capital_inicial, theme)
            
        elif metrica_sel == "Fronteira Eficiente (Markowitz)":
            plot_markowitz(dict_estudo, df_rv_com, cdi_al, idx_mestre, theme)
            
        elif metrica_sel == "Value at Risk (VaR Histórico)":
            visao_var = st.radio("Visão:", ["Histograma", "Rolante"], horizontal=True)
            if visao_var == "Histograma":
                plot_var_histogram(ret_estudo, f"VaR ({setor_filtro})", theme['loss'], theme)
            else:
                df_r = pd.DataFrame(index=idx_mestre)
                df_r["VaR 5%"] = ret_estudo.rolling(252).quantile(0.05)
                
                fig_var_r = px.line(df_r.dropna(), color_discrete_sequence=[theme['accent']])
                fig_var_r.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color=theme['text_main']))
                fig_var_r.update_xaxes(gridcolor=theme['grid'])
                fig_var_r.update_yaxes(gridcolor=theme['grid'])
                st.plotly_chart(fig_var_r, use_container_width=True, config=PLOTLY_CONFIG)
                
        elif metrica_sel == "Drawdown Histórico":
            dd_acumulado = (1 + ret_estudo).cumprod()
            dd_maximo = dd_acumulado.cummax()
            dd_serie = ((dd_acumulado / dd_maximo) - 1) * 100
            
            fig_dd_estudo = px.area(dd_serie, title="Drawdown")
            fig_dd_estudo.update_traces(line_color=theme['loss'], fillcolor=theme['loss'], opacity=0.2)
            fig_dd_estudo.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color=theme['text_main']))
            fig_dd_estudo.update_xaxes(gridcolor=theme['grid'])
            fig_dd_estudo.update_yaxes(gridcolor=theme['grid'])
            st.plotly_chart(fig_dd_estudo, use_container_width=True, config=PLOTLY_CONFIG)
            
        elif metrica_sel == "Volatilidade Rolante":
            df_r = pd.DataFrame(index=idx_mestre)
            df_r[nome_cart] = ret_estudo.rolling(252).std() * np.sqrt(252) * 100
            
            for b_name, b_serie in dict_ret_benchs.items():
                df_r[b_name] = b_serie.rolling(252).std() * np.sqrt(252) * 100
                
            fig_vol_r = px.line(df_r.dropna(), color_discrete_sequence=theme['chart_seq'])
            fig_vol_r.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color=theme['text_main']))
            fig_vol_r.update_xaxes(gridcolor=theme['grid'])
            fig_vol_r.update_yaxes(gridcolor=theme['grid'])
            st.plotly_chart(fig_vol_r, use_container_width=True, config=PLOTLY_CONFIG)
            
        elif metrica_sel == "Beta (Risco de Mercado)":
            var_b = ret_bench_principal.rolling(252).var().where(lambda x: x > 1e-8, np.nan)
            df_r = pd.DataFrame(index=idx_mestre)
            df_r["Beta"] = ret_estudo.rolling(252).cov(ret_bench_principal) / var_b
            
            df_r_clean = df_r.dropna()
            if df_r_clean.empty:
                st.warning("Sem volatilidade para calcular o Beta.")
            else:
                fig_beta_r = px.line(df_r_clean, color_discrete_sequence=[theme['accent']])
                fig_beta_r.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color=theme['text_main']))
                fig_beta_r.update_xaxes(gridcolor=theme['grid'])
                fig_beta_r.update_yaxes(gridcolor=theme['grid'])
                st.plotly_chart(fig_beta_r, use_container_width=True, config=PLOTLY_CONFIG)

    with tabs[3]:
        st.markdown("### 📊 Análise Setorial")
        c_d1, c_d2 = st.columns(2)
        dt_s = c_d1.date_input("Início:", value=data_inicio)
        dt_e = c_d2.date_input("Fim:", value=data_fim)
        
        setores_totais = list(set([getattr(v, 'setor', 'Outros') if getattr(v, 'tipo', 'RV') == 'RV' else 'Renda Fixa' for v in st.session_state.carteira.values()]))
        set_sel = st.multiselect("Setores:", setores_totais, default=setores_totais[:3] if len(setores_totais)>=3 else setores_totais)
        
        if set_sel:
            mask = (idx_mestre >= pd.to_datetime(dt_s)) & (idx_mestre <= pd.to_datetime(dt_e))
            idx_p = idx_mestre[mask]
            
            df_p = pd.DataFrame(index=idx_p)
            for s in set_sel:
                ret_sec_com, ret_sec_sem = processar_carteira(st.session_state.carteira, df_rv_com, df_rv_sem, cdi_al, ipca_al, idx_mestre, reinvestir, marcar_mercado_ativado, setor_filter=s)
                ret_sec_final = ret_sec_com if reinvestir else ret_sec_sem
                df_p[s] = ((1 + ret_sec_final.loc[idx_p]).cumprod() - 1) * 100
                
            fig_sec_line = px.line(df_p, color_discrete_sequence=theme['chart_seq'])
            fig_sec_line.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color=theme['text_main']))
            fig_sec_line.update_xaxes(gridcolor=theme['grid'])
            fig_sec_line.update_yaxes(gridcolor=theme['grid'])
            st.plotly_chart(fig_sec_line, use_container_width=True, config=PLOTLY_CONFIG)

    tab_idx = 4
    if st.session_state.carteira_comparacao:
        with tabs[tab_idx]:
            st.markdown("### 🏆 Confronto Direto")
            m_c = calcular_metricas(ret_portfolio_comparacao, ret_bench_principal, cdi_al)
            
            html_comp = f"""
            <table>
                <tr><th>Métrica</th><th>{nome_cart}</th><th>{nome_comp}</th></tr>
                <tr><td>Retorno</td><td>{m_prin[0]:.2%}</td><td>{m_c[0]:.2%}</td></tr>
                <tr><td>Sharpe</td><td>{m_prin[2]:.2f}</td><td>{m_c[2]:.2f}</td></tr>
                <tr><td>Volatilidade</td><td>{m_prin[1]:.2%}</td><td>{m_c[1]:.2%}</td></tr>
            </table>
            """
            st.markdown(html_comp, unsafe_allow_html=True)
            
        tab_idx += 1

    with tabs[tab_idx]:
        if not ativos_rv_principal:
            st.warning("Adicione Renda Variável na sua carteira para ver os fundamentos.")
        else:
            ativo_selecionado = st.selectbox("Ativo para Análise:", ativos_rv_principal)
            if ativo_selecionado:
                info_fund = fetch_fundamental_info(ativo_selecionado)
                
                if info_fund:
                    st.markdown(f"### 📊 Raio-X Fundamentalista: {ativo_selecionado}")
                    st.caption("⚠️ **Aviso de Dados:** As métricas abaixo são extraídas de provedores públicos globais. (API Gratuita)")
                    st.markdown("---")
                    
                    st.subheader("💰 Valuation & Preço", divider='gray')
                    v1, v2, v3, v4, v5 = st.columns(5)
                    v1.metric("P/L (Preço/Lucro)", formatar_float(info_fund.get('trailingPE') or info_fund.get('forwardPE')))
                    v2.metric("P/VP", formatar_float(info_fund.get('priceToBook')))
                    v3.metric("EV/EBITDA", formatar_float(info_fund.get('enterpriseToEbitda')))
                    v4.metric("P/SR (Receita)", formatar_float(info_fund.get('priceToSalesTrailing12Months')))
                    v5.metric("Dividend Yield", formatar_dy(info_fund.get('trailingAnnualDividendYield') or info_fund.get('dividendYield')))
                    
                    st.subheader("📈 Rentabilidade & Eficiência", divider='gray')
                    r1, r2, r3, r4, r5 = st.columns(5)
                    r1.metric("ROE (Retorno s/ PL)", formatar_pct_api(info_fund.get('returnOnEquity')))
                    r2.metric("ROA (Retorno s/ Ativos)", formatar_pct_api(info_fund.get('returnOnAssets')))
                    r3.metric("Margem Bruta", formatar_pct_api(info_fund.get('grossMargins')))
                    r4.metric("Margem EBITDA", formatar_pct_api(info_fund.get('ebitdaMargins')))
                    r5.metric("Margem Líquida", formatar_pct_api(info_fund.get('profitMargins')))
                    
                    st.subheader("🏛️ Saúde Financeira & Estrutura", divider='gray')
                    s1, s2, s3, s4, s5 = st.columns(5)
                    s1.metric("Liquidez Corrente", formatar_float(info_fund.get('currentRatio')))
                    div_pat_val = info_fund.get('debtToEquity')
                    div_pat_str = formatar_float(div_pat_val / 100) if div_pat_val and div_pat_val != 0 else "N/A"
                    s2.metric("Dívida/Patrimônio", div_pat_str)
                    s3.metric("VPA (Val. Patr. Ação)", formatar_float(info_fund.get('bookValue')))
                    s4.metric("LPA (Lucro Ação)", formatar_float(info_fund.get('trailingEps') or info_fund.get('forwardEps')))
                    s5.metric("Valor de Mercado", formatar_abrev(info_fund.get('marketCap')))
                    
                    st.markdown("<br>", unsafe_allow_html=True)
                    st.markdown("### 📈 Evolução Histórica Contábil")
                    
                    fin, bs, cf = fetch_historical_fundamentals(ativo_selecionado)
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
                            fig_hist.update_traces(marker_color=theme['accent'], textfont_color=theme['bg'], textposition='outside')
                            fig_hist.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color=theme['text_main']), yaxis=dict(showticklabels=False))
                            fig_hist.update_xaxes(gridcolor=theme['grid'], tickfont=dict(color=theme['text_sec']))
                            fig_hist.update_yaxes(gridcolor=theme['grid'], tickfont=dict(color=theme['text_sec']))
                            st.plotly_chart(fig_hist, use_container_width=True, config=PLOTLY_CONFIG)
                        
                st.markdown("---")
                st.markdown("### 📉 Cotação Histórica")
                tipo_grafico_ativo = st.radio("Formato:", ["Linha", "Candlestick"], horizontal=True)
                df_cotacao = yf.download(ativo_selecionado, start=data_inicio, end=pd.to_datetime(data_fim) + timedelta(days=1), progress=False)
                
                if not df_cotacao.empty and 'Close' in df_cotacao:
                    if tipo_grafico_ativo == "Candlestick" and 'Open' in df_cotacao:
                        o = df_cotacao['Open'].squeeze()
                        h = df_cotacao['High'].squeeze()
                        l = df_cotacao['Low'].squeeze()
                        c = df_cotacao['Close'].squeeze()
                        fig_cot = go.Figure(data=[go.Candlestick(x=df_cotacao.index, open=o, high=h, low=l, close=c)])
                    else:
                        fig_cot = px.line(x=df_cotacao.index, y=df_cotacao['Close'].squeeze())
                        fig_cot.update_traces(line_color=theme['accent'])
                        
                    fig_cot.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color=theme['text_main']), xaxis_rangeslider_visible=False)
                    fig_cot.update_xaxes(gridcolor=theme['grid'], tickfont=dict(color=theme['text_sec']))
                    fig_cot.update_yaxes(gridcolor=theme['grid'], tickfont=dict(color=theme['text_sec']))
                    st.plotly_chart(fig_cot, use_container_width=True, config=PLOTLY_CONFIG)

    with tabs[tab_idx+1]:
        st.markdown("### 📑 Relatório Dinâmico em PDF/PPT")
        st.info("O sistema ajustará as cores dos gráficos para a cor selecionada na barra lateral. Ideal para colar direto no PowerPoint.")
        
        if st.button("📄 ACESSAR MODO DE IMPRESSÃO LIMPO", use_container_width=True):
            ativar_modo_impressao()
            st.rerun()
            
        st.markdown("---")
        st.markdown("### 📊 Tabela Transparente (Exportar via Câmera)")
        st.plotly_chart(plot_tabela_metricas(m_prin, nome_cart, theme), use_container_width=True, config=PLOTLY_CONFIG)

st.markdown(f"<div style='text-align:right; color:{theme['accent']}; opacity:0.6; margin-top: 50px;'>Idealizado por Bernardo V.</div>", unsafe_allow_html=True)
