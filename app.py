import streamlit as st
import math
import sqlite3
import pandas as pd
from datetime import datetime
from fpdf import FPDF

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="NefroPed - Mercês", page_icon="🩺", layout="wide")

# --- INICIALIZAÇÃO DO BANCO DE DADOS ---
def init_db():
    conn = sqlite3.connect('nefroped_merces.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS pacientes 
                 (id INTEGER PRIMARY KEY, nome TEXT, leito TEXT, data_admissao TEXT, 
                  anos INTEGER, meses INTEGER, dias INTEGER, sexo TEXT, k REAL, 
                  peso_seco REAL, estatura REAL, sc REAL, tfge REAL, 
                  dose_at REAL, dose_mn REAL, vol_alb REAL, dose_furo REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS monitorizacao 
                 (id INTEGER PRIMARY KEY, paciente_id INTEGER, data TEXT, hora TEXT, 
                  peso REAL, pa TEXT, fc INTEGER, fr INTEGER, temp REAL, vol_24h REAL)''')
    conn.commit()
    conn.close()

init_db()

# --- CLASSE PARA GERAÇÃO DE PDF (Corrigida) ---
class PDF(FPDF):
    def header(self):
        self.set_font('helvetica', 'B', 12)
        self.cell(0, 10, 'Ficha de Monitorização Vascular e Metabólica', 0, 1, 'C')
        self.set_font('helvetica', '', 10)
        self.cell(0, 5, 'Setor: Pediatria - Hospital Nossa Senhora das Mercês', 0, 1, 'C')
        self.ln(10)

def gerar_pdf(p, hist):
    pdf = PDF()
    pdf.add_page()
    pdf.set_font("helvetica", size=10)
    pdf.cell(0, 8, f"Nome do Doente: {p['nome']} | Leito: {p['leito']}", ln=True)
    pdf.cell(0, 8, f"Peso Admissão: {p['peso_seco']} kg | SC: {p['sc']:.2f} m2", ln=True)
    pdf.ln(5)
    
    pdf.set_font('helvetica', 'B', 8)
    cols = [('Data', 25), ('Hora', 20), ('Peso (kg)', 25), ('PA', 30), ('FC', 25), ('FR', 25), ('Temp', 25)]
    for head, width in cols: pdf.cell(width, 8, head, 1, 0, 'C')
    pdf.ln()
    
    pdf.set_font('helvetica', '', 8)
    for _, row in hist.iterrows():
        pdf.cell(25, 8, str(row['data']), 1); pdf.cell(20, 8, str(row['hora']), 1)
        pdf.cell(25, 8, f"{row['peso']:.2f}", 1); pdf.cell(30, 8, str(row['pa']), 1)
        pdf.cell(25, 8, str(row['fc']), 1); pdf.cell(25, 8, str(row['fr']), 1)
        pdf.cell(25, 8, f"{row['temp']:.1f}", 1, 1)
        
    return bytes(pdf.output())

# --- BARRA LATERAL ---
with st.sidebar:
    st.header("🩺 Gestão HNSM")
    if st.button("⚠️ Resetar Banco de Dados", help="Use para corrigir erros de colunas no banco"):
        conn = sqlite3.connect('nefroped_merces.db'); c = conn.cursor()
        c.execute("DROP TABLE IF EXISTS pacientes"); c.execute("DROP TABLE IF EXISTS monitorizacao")
        conn.commit(); conn.close()
        init_db(); st.rerun()

# --- INTERFACE ---
tab1, tab2, tab3 = st.tabs(["🔢 Cadastro", "📋 Monitorização", "📂 Histórico"])

with tab1:
    with st.container(border=True):
        nome_in = st.text_input("Nome do Paciente").upper()
        leito_in = st.text_input("Leito")
        data_adm_in = st.date_input("Data de Admissão", value=datetime.now())
        
        c1, c2, c3 = st.columns(3)
        anos_in = c1.number_input("Anos", 0, 18, 5)
        meses_in = c2.number_input("Meses", 0, 11, 0)
        dias_in = c3.number_input("Dias", 0, 30, 0)
        sexo_in = st.radio("Sexo Biológico", ["Feminino", "Masculino"], horizontal=True)
        
        # Lógica de K automatizada (Schwartz 1)
        total_meses = (anos_in * 12) + meses_in
        if total_meses < 12:
            prematuro = st.checkbox("Nasceu prematuro?")
            k_val, cat = (0.33, "RN Pré-termo") if prematuro else (0.45, "RN a termo")
        else:
            if sexo_in == "Masculino" and anos_in >= 13: k_val, cat = 0.70, "Adolescente Masculino"
            else: k_val, cat = 0.55, "Criança / Adolescente Feminino"
            
        st.info(f"Categoria: {cat} (K = {k_val})")
        p_in = st.number_input("Peso na Admissão (kg)", 1.0, 150.0, 20.0)
        e_in = st.number_input("Estatura (cm)", 30.0, 200.0, 110.0)
        cr_in = st.number_input("Creatinina Jaffé (mg/dL)", 0.1, 10.0, 0.6)
        
        if st.button("Salvar Cadastro e Calcular", type="primary"):
            sc_calc = math.sqrt((p_in * e_in) / 3600) # Mosteller
            tfge_calc = (k_val * e_in) / cr_in # Schwartz 1
            at, mn = min(sc_calc * 60, 60.0), min(sc_calc * 40, 40.0)
            alb, furo = (p_in * 0.5) * 5, p_in * 0.5
            
            conn = sqlite3.connect('nefroped_merces.db'); c = conn.cursor()
            c.execute("INSERT INTO pacientes VALUES (NULL,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", 
                      (nome_in, leito_in, data_adm_in.strftime("%d/%m/%Y"), anos_in, meses_in, dias_in, sexo_in, k_val, p_in, e_in, sc_calc, tfge_calc, at, mn, alb, furo))
            conn.commit(); conn.close()
            st.success(f"Paciente {nome_in} cadastrado!")

with tab2:
    # (Interface de sinais vitais incluindo vol_24h conforme solicitado anteriormente)
    conn = sqlite3.connect('nefroped_merces.db')
    pacs = pd.read_sql("SELECT id, nome FROM pacientes", conn); conn.close()
    if not pacs.empty:
        escolha = st.selectbox("Paciente", pacs['nome'])
        pac_id = int(pacs[pacs['nome'] == escolha]['id'].iloc[0])
        v1, v2, v3, v4, v5, v6 = st.columns(6)
        p_v = v1.number_input("Peso (kg)"); pa_v = v2.text_input("PA"); fc_v = v3.number_input("FC", 0)
        fr_v = v4.number_input("FR", 0); t_v = v5.number_input("Temp", 30.0, 42.0, 36.5); vol_v = v6.number_input("Vol. 24h", 0)
        if st.button("Salvar Registro"):
            conn = sqlite3.connect('nefroped_merces.db'); c = conn.cursor()
            c.execute("INSERT INTO monitorizacao (paciente_id, data, hora, peso, pa, fc, fr, temp, vol_24h) VALUES (?,?,?,?,?,?,?,?,?,?)",
                      (pac_id, datetime.now().strftime("%d/%m/%Y"), datetime.now().strftime("%H:%M"), p_v, pa_v, fc_v, fr_v, t_v, vol_v))
            conn.commit(); conn.close(); st.success("Salvo!")

with tab3:
    busca = st.text_input("🔎 BUSCAR").upper()
    if busca:
        conn = sqlite3.connect('nefroped_merces.db')
        p_data = pd.read_sql(f"SELECT * FROM pacientes WHERE nome LIKE '%{busca}%'", conn)
        if not p_data.empty:
            p_sel = p_data.iloc[0]
            h_data = pd.read_sql(f"SELECT * FROM monitorizacao WHERE paciente_id = {p_sel['id']}", conn)
            st.dataframe(h_data); pdf_b = gerar_pdf(p_sel, h_data)
            st.download_button("📥 Baixar PDF", data=pdf_b, file_name=f"Ficha_{p_sel['nome']}.pdf", mime="application/pdf")
        conn.close()
