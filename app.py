import streamlit as st
import math
import sqlite3
import pandas as pd
from datetime import datetime

# --- 1. DADOS DE REFERÊNCIA SBP 2019 (TABELAS 1 e 2) ---
# Estrutura: { Sexo: { Idade: { 'ht': [alturas_percentis], 'pas': [p95_sist], 'pad': [p95_diast] } } }
# Simplificação: Usamos os valores médios de referência para os percentis de altura 5, 10, 25, 50, 75, 90, 95
# Fonte: Extraído do PDF 21635c-MO... SBP 2019

BP_DATA = {
    'M': { # MENINOS
        1: {'ht': [77, 78, 80, 82, 85, 87, 88], 'pas90': [98,99,99,100,101,101,102], 'pas95': [102,102,103,103,104,105,105], 'pad90': [52,52,53,53,54,54,54], 'pad95': [54,54,55,55,56,57,57]},
        5: {'ht': [104,106,109,112,116,119,120], 'pas90': [103,104,105,106,107,108,109], 'pas95': [107,107,108,109,110,111,112], 'pad90': [63,63,64,65,66,66,67], 'pad95': [69,69,70,71,72,72,73]},
        10: {'ht': [130,133,137,141,146,150,153], 'pas90': [108,109,111,113,115,116,117], 'pas95': [113,113,115,117,119,120,121], 'pad90': [72,73,73,74,75,76,76], 'pad95': [77,77,78,79,80,80,81]},
        13: {'ht': [148,152,158,164,170,175,179], 'pas90': [113,114,115,117,119,121,122], 'pas95': [116,117,118,124,124,121,128], 'pad90': [74,74,74,75,76,76,77], 'pad95': [78,78,78,78,79,79,80]},
        # ... (Dados interpolados para outras idades seriam ideais, aqui usamos lógica de aproximação para brevidade do código)
    },
    'F': { # MENINAS
        1: {'ht': [75,77,79,81,83,85,86], 'pas90': [98,99,99,100,101,102,102], 'pas95': [101,102,102,103,104,105,105], 'pad90': [54,55,56,57,58,58,58], 'pad95': [59,59,60,60,61,61,62]},
        5: {'ht': [104,105,108,112,115,118,120], 'pas90': [103,104,105,106,107,108,109], 'pas95': [107,108,109,110,111,112,112], 'pad90': [64,64,65,66,67,68,69], 'pad95': [69,69,70,71,72,72,73]},
        10: {'ht': [130,132,136,141,146,150,153], 'pas90': [109,110,111,112,113,115,116], 'pas95': [113,114,115,116,117,119,120], 'pad90': [72,73,73,73,74,75,75], 'pad95': [76,77,77,77,78,79,80]},
        13: {'ht': [149,152,156,160,164,168,171], 'pas90': [114,115,116,118,119,120,121], 'pas95': [118,119,120,122,123,124,125], 'pad90': [75,76,76,76,77,78,78], 'pad95': [79,80,80,80,81,82,82]},
    }
}

# Função auxiliar para pegar dados da tabela (com fallback para idades não mapeadas explicitamente acima)
# Nota: Em um app final, todas as idades de 1-17 devem estar no dicionário. Aqui usamos uma lógica simplificada.
def get_bp_limits(sexo, idade, altura_cm):
    # Regra Adolescente >= 13 anos (Critérios Fixos Adulto - SBP 2019)
    if idade >= 13:
        return {'p90s': 120, 'p95s': 130, 'p99s': 140, 'p90d': 80, 'p95d': 80, 'p99d': 90}
    
    # Regra Criança < 13 anos (Baseada em Percentil)
    # Busca a idade mais próxima disponível na tabela simplificada acima
    idades_disp = [1, 5, 10, 13]
    idade_prox = min(idades_disp, key=lambda x: abs(x - idade))
    
    table = BP_DATA[sexo][idade_prox]
    
    # Encontrar a coluna de estatura mais próxima
    # Posições: 0=5%, 1=10%, 2=25%, 3=50%, 4=75%, 5=90%, 6=95%
    heights = table['ht']
    closest_idx = min(range(len(heights)), key=lambda i: abs(heights[i] - altura_cm))
    
    p90s = table['pas90'][closest_idx]
    p95s = table['pas95'][closest_idx]
    p90d = table['pad90'][closest_idx]
    p95d = table['pad95'][closest_idx]
    
    # Cálculo do Estágio 2 (P95 + 12mmHg)
    p99s_plus = p95s + 12
    p99d_plus = p95d + 12
    
    return {'p90s': p90s, 'p95s': p95s, 'p99s': p99s_plus, 
            'p90d': p90d, 'p95d': p95d, 'p99d': p99d_plus}

def classificar_pa_auto(pas, pad, limites):
    # Regras SBP 2019
    # Estágio 2
    if (pas >= limites['p99s']) or (pad >= limites['p99d']):
        return "HIPERTENSÃO ESTÁGIO 2", "red"
    # Estágio 1
    elif (pas >= limites['p95s']) or (pad >= limites['p95d']):
        return "HIPERTENSÃO ESTÁGIO 1", "orange"
    # Elevada
    elif (pas >= limites['p90s']) or (pad >= limites['p90d']):
        return "PA ELEVADA", "yellow"
    # Normal
    else:
        return "Normotenso", "green"

# --- 2. CONFIGURAÇÃO E BANCO ---
st.set_page_config(page_title="NefroPed - HNSM", page_icon="🩺", layout="wide")

def init_db():
    conn = sqlite3.connect('nefroped_merces.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS pacientes 
                 (id INTEGER PRIMARY KEY, nome TEXT, leito TEXT, data_admissao TEXT, 
                  anos INTEGER, meses INTEGER, dias INTEGER, sexo TEXT, k REAL, 
                  peso_seco REAL, estatura REAL, sc REAL, tfge REAL, 
                  dose_at REAL, dose_mn REAL, vol_alb REAL, dose_furo REAL)''')
    
    # Tabela Monitorização (agora salvamos a classificação automática)
    c.execute('''CREATE TABLE IF NOT EXISTS monitorizacao 
                 (id INTEGER PRIMARY KEY, paciente_id INTEGER, data TEXT, hora TEXT, 
                  peso REAL, pa TEXT, fc INTEGER, fr INTEGER, temp REAL, vol_24h REAL,
                  classif_pa TEXT)''') # Nova coluna classif_pa
    conn.commit(); conn.close()

init_db()

# --- 3. INTERFACE ---
with st.sidebar:
    st.header("🏥 Gestão HNSM")
    if st.button("⚠️ Resetar Banco de Dados", help="Use se der erro de coluna"):
        conn = sqlite3.connect('nefroped_merces.db'); c = conn.cursor()
        c.execute("DROP TABLE IF EXISTS pacientes"); c.execute("DROP TABLE IF EXISTS monitorizacao")
        conn.commit(); conn.close(); init_db(); st.rerun()

st.title("Calculadora de Nefrologia Pediátrica")
tab1, tab2, tab3 = st.tabs(["🔢 Cadastro", "📋 Monitorização Automática", "📂 Prontuário"])

# --- TAB 1: CADASTRO ---
with tab1:
    with st.container(border=True):
        col1, col2 = st.columns(2)
        nome_in = col1.text_input("Nome").upper()
        leito_in = col2.text_input("Leito")
        
        c1, c2, c3 = st.columns(3)
        anos = c1.number_input("Anos", 0, 18, 5)
        meses = c2.number_input("Meses", 0, 11, 0)
        sexo = c3.radio("Sexo", ["M", "F"], horizontal=True)
        
        # K Schwartz
        k_val = 0.55
        if (anos * 12 + meses) < 12: k_val = 0.33 if st.checkbox("Prematuro?") else 0.45
        elif sexo == "M" and anos >= 13: k_val = 0.70
        st.caption(f"K Automático: {k_val}")
        
        p_in = st.number_input("Peso (kg)", 1.0, 150.0, 20.0)
        e_in = st.number_input("Estatura (cm)", 30.0, 200.0, 110.0)
        cr_in = st.number_input("Creatinina", 0.1, 15.0, 0.6)
        
        if st.button("Salvar Paciente", type="primary"):
            sc = math.sqrt((p_in * e_in) / 3600)
            tfge = (k_val * e_in) / cr_in
            dose_at = min(sc * 60, 60.0); dose_mn = min(sc * 40, 40.0)
            vol_alb = (p_in * 0.5) * 5; dose_furo = p_in * 0.5
            
            conn = sqlite3.connect('nefroped_merces.db'); c = conn.cursor()
            c.execute("INSERT INTO pacientes VALUES (NULL,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", 
                      (nome_in, leito_in, datetime.now().strftime("%d/%m"), anos, meses, 0, sexo, k_val, p_in, e_in, sc, tfge, dose_at, dose_mn, vol_alb, dose_furo))
            conn.commit(); conn.close()
            st.success("Cadastrado!")

# --- TAB 2: MONITORIZAÇÃO AUTOMÁTICA ---
with tab2:
    conn = sqlite3.connect('nefroped_merces.db')
    pacs = pd.read_sql("SELECT id, nome, anos, sexo, estatura FROM pacientes", conn); conn.close()
    
    if not pacs.empty:
        escolha = st.selectbox("Paciente", pacs['nome'])
        p_data = pacs[pacs['nome'] == escolha].iloc[0]
        
        st.subheader("🩺 Sinais Vitais")
        with st.container(border=True):
            c1, c2 = st.columns(2)
            pas = c1.number_input("PAS (Sistólica)", 0, 300, 110)
            pad = c2.number_input("PAD (Diastólica)", 0, 200, 70)
            
            # --- CÉREBRO DA CLASSIFICAÇÃO AUTOMÁTICA ---
            # 1. Busca os limites baseados na idade/sexo/altura do cadastro
            limites = get_bp_limits(p_data['sexo'], p_data['anos'], p_data['estatura'])
            # 2. Classifica
            status_pa, cor_pa = classificar_pa_auto(pas, pad, limites)
            
            st.markdown(f"**Classificação Automática (SBP 2019):** :{cor_pa}[{status_pa}]")
            st.caption(f"Limites usados: P95 = {limites['p95s']}/{limites['p95d']} | P99+5 = {limites['p99s']}/{limites['p99d']}")
            
            v1, v2, v3, v4 = st.columns(4)
            p_v = v1.number_input("Peso Hoje", format="%.2f")
            fc = v2.number_input("FC", 0); temp = v3.number_input("Temp", 36.5)
            vol = v4.number_input("Diurese 24h", 0)
            
            if st.button("Salvar Evolução"):
                conn = sqlite3.connect('nefroped_merces.db'); c = conn.cursor()
                c.execute("INSERT INTO monitorizacao (paciente_id, data, hora, peso, pa, fc, fr, temp, vol_24h, classif_pa) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                          (int(p_data['id']), datetime.now().strftime("%d/%m"), datetime.now().strftime("%H:%M"), p_v, f"{pas}/{pad}", fc, 0, temp, vol, status_pa))
                conn.commit(); conn.close()
                st.success("Salvo!")

# --- TAB 3: PRONTUÁRIO ---
with tab3:
    busca = st.text_input("Buscar").upper()
    if busca:
        conn = sqlite3.connect('nefroped_merces.db')
        p_res = pd.read_sql(f"SELECT * FROM pacientes WHERE nome LIKE '%{busca}%'", conn)
        
        if not p_res.empty:
            p_sel = p_res.iloc[0]
            st.write(f"### {p_sel['nome']} | {p_sel['anos']} anos")
            st.info(f"Conduta: Prednisolona {p_sel['dose_at']:.1f}mg (Ataque)")
            
            # Histórico com Cores
            h_data = pd.read_sql(f"SELECT data, hora, pa, classif_pa, peso, vol_24h FROM monitorizacao WHERE paciente_id = {p_sel['id']} ORDER BY id DESC", conn)
            
            if not h_data.empty:
                # Estilização
                def colorir(row):
                    estilos = [''] * len(row)
                    # Cor da PA baseada na classificação salva
                    if "ESTÁGIO 2" in str(row['classif_pa']):
                        estilos[row.index.get_loc('pa')] = 'background-color: #ffcccc; color: red; font-weight: bold'
                    elif "ESTÁGIO 1" in str(row['classif_pa']):
                        estilos[row.index.get_loc('pa')] = 'background-color: #ffe5cc; color: #cc5500'
                    elif "ELEVADA" in str(row['classif_pa']):
                        estilos[row.index.get_loc('pa')] = 'background-color: #ffffcc; color: #856404'
                    
                    # Oligúria
                    debito = row['vol_24h'] / p_sel['peso_seco'] / 24
                    if 0 < debito < 1.0:
                        estilos[row.index.get_loc('vol_24h')] = 'background-color: #ffffcc; color: red; font-weight: bold'
                    return estilos

                st.dataframe(h_data.style.apply(colorir, axis=1), use_container_width=True)
        conn.close()
