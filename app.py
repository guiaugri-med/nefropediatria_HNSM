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
    # Tabela de Cadastro e Condutas Iniciais
    c.execute('''CREATE TABLE IF NOT EXISTS pacientes 
                 (id INTEGER PRIMARY KEY, nome TEXT, leito TEXT, data_admissao TEXT, 
                  anos INTEGER, meses INTEGER, dias INTEGER, sexo TEXT, k REAL, 
                  peso_seco REAL, estatura REAL, sc REAL, tfge REAL, 
                  dose_at REAL, dose_mn REAL, vol_alb REAL, dose_furo REAL)''')
    # Tabela de Monitorização Diária
    c.execute('''CREATE TABLE IF NOT EXISTS monitorizacao 
                 (id INTEGER PRIMARY KEY, paciente_id INTEGER, data TEXT, hora TEXT, 
                  peso REAL, pa TEXT, fc INTEGER, fr INTEGER, temp REAL)''')
    conn.commit()
    conn.close()

init_db()

# --- INTERFACE ---
st.title("🩺Nefrologia Pediátrica - HNSM")
st.caption("Protocolo: Schwartz 1 (Jaffé) | Unidade: Hospital Nossa Senhora das Mercês")

tab1, tab2, tab3 = st.tabs(["🔢 Cadastro e Cálculos", "📋 Monitorização Diária", "📂 Histórico de Pacientes"])

# --- TAB 1: CADASTRO E CÁLCULOS ---
with tab1:
    with st.container(border=True):
        st.subheader("👤 Identificação e Admissão")
        col_c1, col_c2 = st.columns(2)
        nome_in = col_c1.text_input("Nome do Paciente").upper()
        leito_in = col_c2.text_input("Leito")
        data_adm_in = st.date_input("Data de Admissão", value=datetime.now())
        
        st.write("**Idade do Paciente:**")
        c1, c2, c3 = st.columns(3)
        anos_in = c1.number_input("Anos", 0, 18, 5)
        meses_in = c2.number_input("Meses", 0, 11, 0)
        dias_in = c3.number_input("Dias", 0, 30, 0)
        sexo_in = st.radio("Sexo Biológico", ["Feminino", "Masculino"], horizontal=True)
        
        # Lógica de K automatizada (Schwartz 1 - Jaffé)
        idade_meses_total = (anos_in * 12) + meses_in
        if idade_meses_total < 12:
            prematuro = st.checkbox("Nasceu prematuro?")
            k_val, cat = (0.33, "RN Pré-termo") if prematuro else (0.45, "RN a termo")
        else:
            if sexo_in == "Masculino" and anos_in >= 13:
                k_val, cat = 0.70, "Adolescente Masculino"
            else:
                k_val, cat = 0.55, "Criança / Adolescente Feminino"
            
        st.info(f"**Categoria Detectada:** {cat} | **K utilizado:** {k_val}")
        
        st.divider()
        st.subheader("🧪 Parâmetros Clínicos")
        p_in = st.number_input("Peso na Admissão - Seco (kg)", 1.0, 150.0, 20.0)
        e_in = st.number_input("Estatura (cm)", 30.0, 200.0, 110.0)
        cr_in = st.number_input("Creatinina Jaffé (mg/dL)", 0.1, 10.0, 0.6)
        
        btn_calc = st.button("Salvar Cadastro e Calcular", type="primary")

    if btn_calc:
        # Fórmulas e Doses
        sc_calc = math.sqrt((p_in * e_in) / 3600) # Mosteller
        tfge_calc = (k_val * e_in) / cr_in # Schwartz 1
        dose_at = min(sc_calc * 60, 60.0) # 60mg/m2 (teto 60mg)
        dose_mn = min(sc_calc * 40, 40.0) # 40mg/m2 (teto 40mg)
        vol_alb = (p_in * 0.5) * 5 # 0.5g/kg (1g = 5ml)
        dose_furo = p_in * 0.5 # 0.5mg/kg
        
        # Salvar no Banco
        conn = sqlite3.connect('nefroped_merces.db')
        c = conn.cursor()
        c.execute("INSERT INTO pacientes VALUES (NULL,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", 
                  (nome_in, leito_in, data_adm_in.strftime("%d/%m/%Y"), anos_in, meses_in, dias_in, sexo_in, k_val, p_in, e_in, sc_calc, tfge_calc, dose_at, dose_mn, vol_alb, dose_furo))
        conn.commit()
        conn.close()
        
        st.success(f"✅ Paciente {nome_in} cadastrado com sucesso!")
        
        # Exibição de Resultados
        st.divider()
        st.subheader("📋 Resumo de Admissão e Conduta")
        r1, r2, r3 = st.columns(3)
        r1.metric("Superfície Corporal", f"{sc_calc:.2f} m²")
        r2.metric("TFGe (Schwartz 1)", f"{tfge_calc:.1f} mL/min")
        r3.metric("K Utilizado", f"{k_val}")
        
        st.warning(f"💊 **Corticoterapia:** Ataque: {dose_at:.1f} mg/dia | Manutenção: {dose_mn:.1f} mg (D.A.)")
        st.info(f"💧 **Manejo de Edema:** Albumina 20%: {vol_alb:.1f} mL | Furosemida IV: {dose_furo:.1f} mg")

# --- TAB 2: MONITORIZAÇÃO DIÁRIA ---
with tab2:
    conn = sqlite3.connect('nefroped_merces.db')
    pacs = pd.read_sql("SELECT id, nome, leito FROM pacientes", conn)
    conn.close()
    
    if not pacs.empty:
        escolha = st.selectbox("Selecione o Paciente para Evolução", pacs['nome'] + " (Leito: " + pacs['leito'] + ")")
        pac_id = int(pacs[pacs['nome'] == escolha.split(" (")[0]]['id'].iloc[0])
        
        st.subheader("🩺 Registro de Sinais Vitais")
        with st.form("monitor_form"):
            c_m1, c_m2 = st.columns(2)
            d_v = c_m1.date_input("Data do Registro")
            h_v = c_m2.selectbox("Hora", ["08:00", "14:00", "20:00"])
            
            v1, v2, v3, v4, v5 = st.columns(5)
            p_v = v1.number_input("Peso jejum (kg)")
            pa_v = v2.text_input("PA (mmHg)")
            fc_v = v3.number_input("FC (bpm)", 0)
            fr_v = v4.number_input("FR (irpm)", 0)
            t_v = v5.number_input("Temp (ºC)", 30.0, 42.0, 36.5)
            
            if st.form_submit_button("Salvar na Ficha de Monitorização"):
                conn = sqlite3.connect('nefroped_merces.db')
                c = conn.cursor()
                c.execute("INSERT INTO monitorizacao (paciente_id, data, hora, peso, pa, fc, fr, temp) VALUES (?,?,?,?,?,?,?,?)",
                          (pac_id, d_v.strftime("%d/%m/%Y"), h_v, p_v, pa_v, fc_v, fr_v, t_v))
                conn.commit()
                conn.close()
                st.success("Dados salvos na ficha do paciente!")
    else:
        st.warning("Cadastre um paciente na primeira aba para iniciar a monitorização.")

# --- TAB 3: HISTÓRICO ---
with tab3:
    busca = st.text_input("🔎 BUSCAR PACIENTE (Nome)").upper()
    if busca:
        conn = sqlite3.connect('nefroped_merces.db')
        p_data = pd.read_sql(f"SELECT * FROM pacientes WHERE nome LIKE '%{busca}%'", conn)
        if not p_data.empty:
            p_sel = p_data.iloc[0]
            st.write(f"### {p_sel['nome']} | Leito: {p_sel['leito']}")
            st.write(f"**Data Admissão:** {p_sel['data_admissao']} | **SC:** {p_sel['sc']:.2f} m² | **TFGe Admissão:** {p_sel['tfge']:.1f}")
            
            st.divider()
            st.write("**📊 Ficha de Monitorização Vascular e Metabólica**")
            h_data = pd.read_sql(f"SELECT data, hora, peso, pa, fc, fr, temp FROM monitorizacao WHERE paciente_id = {p_sel['id']} ORDER BY data DESC, hora DESC", conn)
            st.dataframe(h_data, use_container_width=True)
            
            st.divider()
            st.write("**💊 Conduta Inicial Gravada:**")
            st.write(f"- Prednisolona: {p_sel['dose_at']:.1f} mg (Ataque) / {p_sel['dose_mn']:.1f} mg (Manut)")
            st.write(f"- Edema: Albumina 20% {p_sel['vol_alb']:.1f} mL / Furosemida {p_sel['dose_furo']:.1f} mg")
        else:
            st.warning("Paciente não encontrado no banco de dados.")
        conn.close()

# SIDEBAR DE SEGURANÇA
with st.sidebar:
    st.error("🚨 **Sinais de Alerta**")
    with st.expander("Chamar Nefropediatra se:"):
        st.write("- Oligúria (< 1 mL/kg/h)")
        st.write("- Hematúria Macroscópica")
        st.write("- Crise Hipertensiva")
        st.write("- Dor Abdominal (Suspeita de PBE)")
