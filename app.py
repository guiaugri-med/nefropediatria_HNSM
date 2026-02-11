import streamlit as st
import math
import sqlite3
import pandas as pd
from datetime import datetime

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="NefroPed - Mercês", page_icon="🩺", layout="wide")

# --- INICIALIZAÇÃO DO BANCO DE DADOS ---
def init_db():
    conn = sqlite3.connect('nefroped_merces.db')
    c = conn.cursor()
    # Cadastro de Pacientes
    c.execute('''CREATE TABLE IF NOT EXISTS pacientes 
                 (id INTEGER PRIMARY KEY, nome TEXT, leito TEXT, data_admissao TEXT, 
                  anos INTEGER, meses INTEGER, dias INTEGER, sexo TEXT, k REAL, 
                  peso_seco REAL, estatura REAL, sc REAL, tfge REAL, 
                  dose_at REAL, dose_mn REAL, vol_alb REAL, dose_furo REAL)''')
    # Monitorização Diária - Agora com a coluna vol_24h incluída
    c.execute('''CREATE TABLE IF NOT EXISTS monitorizacao 
                 (id INTEGER PRIMARY KEY, paciente_id INTEGER, data TEXT, hora TEXT, 
                  peso REAL, pa TEXT, fc INTEGER, fr INTEGER, temp REAL, vol_24h REAL)''')
    conn.commit()
    conn.close()

init_db()

# --- BARRA LATERAL (ALERTAS E RESET) ---
with st.sidebar:
    st.header("🩺 Gestão HNSM")
    st.error("🚨 **Sinais de Alerta**")
    with st.expander("Notificar Nefropediatra se:"):
        st.write("- Oligúria (< 1 mL/kg/h)")
        st.write("- Hematúria Macroscópica")
        st.write("- Crise Hipertensiva")
    
    st.divider()
    # Este botão resolve o OperationalError das imagens 4667b9 e 466f1d
    if st.button("⚠️ Resetar Banco de Dados", help="Use para corrigir erros de colunas no banco"):
        conn = sqlite3.connect('nefroped_merces.db'); c = conn.cursor()
        c.execute("DROP TABLE IF EXISTS pacientes"); c.execute("DROP TABLE IF EXISTS monitorizacao")
        conn.commit(); conn.close()
        init_db()
        st.success("Banco de dados reiniciado!")
        st.rerun()

# --- INTERFACE PRINCIPAL ---
st.title("Calculadora de Nefrologia Pediátrica - HNSM")
tab1, tab2, tab3 = st.tabs(["🔢 Cadastro e Cálculos", "📋 Monitorização Diária", "📂 Histórico"])

# --- TAB 1: CADASTRO ---
with tab1:
    with st.container(border=True):
        st.subheader("👤 Identificação e Admissão")
        col_c1, col_c2 = st.columns(2)
        nome_in = col_c1.text_input("Nome do Paciente").upper()
        leito_in = col_c2.text_input("Leito")
        data_adm_in = st.date_input("Data de Admissão", value=datetime.now())
        
        c1, c2, c3 = st.columns(3)
        anos_in = c1.number_input("Anos", 0, 18, 5)
        meses_in = c2.number_input("Meses", 0, 11, 0)
        dias_in = c3.number_input("Dias", 0, 30, 0)
        sexo_in = st.radio("Sexo Biológico", ["Feminino", "Masculino"], horizontal=True)
        
        # Correção do SyntaxError (image_95bfe7 / image_9faa80)
        total_meses = (anos_in * 12) + meses_in
        if total_meses < 12:
            prematuro = st.checkbox("Nasceu prematuro?")
            k_val, cat = (0.33, "RN Pré-termo") if prematuro else (0.45, "RN a termo")
        else:
            if sexo_in == "Masculino" and anos_in >= 13:
                k_val, cat = 0.70, "Adolescente Masculino"
            else:
                k_val, cat = 0.55, "Criança / Adolescente Feminino"
            
        st.info(f"**Categoria:** {cat} | **K:** {k_val}")
        
        p_in = st.number_input("Peso na Admissão (kg)", 1.0, 150.0, 20.0)
        e_in = st.number_input("Estatura (cm)", 30.0, 200.0, 110.0)
        cr_in = st.number_input("Creatinina Jaffé (mg/dL)", 0.1, 10.0, 0.6)
        
        if st.button("Salvar Cadastro e Calcular", type="primary"):
            # Fórmulas
            sc_calc = math.sqrt((p_in * e_in) / 3600)
            tfge_calc = (k_val * e_in) / cr_in
            at, mn = min(sc_calc * 60, 60.0), min(sc_calc * 40, 40.0)
            alb, furo = (p_in * 0.5) * 5, p_in * 0.5
            
            conn = sqlite3.connect('nefroped_merces.db'); c = conn.cursor()
            c.execute("INSERT INTO pacientes VALUES (NULL,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", 
                      (nome_in, leito_in, data_adm_in.strftime("%d/%m/%Y"), anos_in, meses_in, dias_in, sexo_in, k_val, p_in, e_in, sc_calc, tfge_calc, at, mn, alb, furo))
            conn.commit(); conn.close()
            st.success(f"✅ Paciente {nome_in} cadastrado!")

# --- TAB 2: MONITORIZAÇÃO ---
with tab2:
    conn = sqlite3.connect('nefroped_merces.db')
    pacs = pd.read_sql("SELECT id, nome FROM pacientes", conn); conn.close()
    
    if not pacs.empty:
        escolha = st.selectbox("Paciente", pacs['nome'])
        pac_id = int(pacs[pacs['nome'] == escolha]['id'].iloc[0])
        with st.container(border=True):
            v1, v2, v3, v4, v5, v6 = st.columns(6)
            p_v = v1.number_input("Peso (kg)"); pa_v = v2.text_input("PA"); fc_v = v3.number_input("FC", 0)
            fr_v = v4.number_input("FR", 0); t_v = v5.number_input("Temp", 30.0, 42.0, 36.5); vol_v = v6.number_input("Vol. 24h (mL)", 0)
            
            if st.button("Salvar na Ficha"):
                conn = sqlite3.connect('nefroped_merces.db'); c = conn.cursor()
                # Correção do OperationalError (image_4667b9)
                c.execute("INSERT INTO monitorizacao (paciente_id, data, hora, peso, pa, fc, fr, temp, vol_24h) VALUES (?,?,?,?,?,?,?,?,?,?)",
                          (pac_id, datetime.now().strftime("%d/%m/%Y"), datetime.now().strftime("%H:%M"), p_v, pa_v, fc_v, fr_v, t_v, vol_v))
                conn.commit(); conn.close()
                st.success("Dados salvos!")

# --- TAB 3: HISTÓRICO ---
with tab3:
    busca = st.text_input("🔎 BUSCAR PACIENTE").upper()
    if busca:
        conn = sqlite3.connect('nefroped_merces.db')
        p_data = pd.read_sql(f"SELECT * FROM pacientes WHERE nome LIKE '%{busca}%'", conn)
        if not p_data.empty:
            p_sel = p_data.iloc[0]
            def destacar_pa(row):
                estilos = [''] * len(row)
                try:
                    pas = int(str(row['pa']).split('/')[0])
                    if pas >= 130: estilos[row.index.get_loc('pa')] = 'background-color: #ffcccc; color: red; font-weight: bold'
                except: pass
                return estilos

            query = f"SELECT data, hora, peso, pa, fc, fr, temp, vol_24h FROM monitorizacao WHERE paciente_id = {p_sel['id']} ORDER BY data DESC"
            h_data = pd.read_sql(query, conn)
            if not h_data.empty:
                st.dataframe(h_data.style.apply(destacar_pa, axis=1), use_container_width=True)
        conn.close()
