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
                  peso REAL, pa TEXT, fc INTEGER, fr INTEGER, temp REAL)''')
    conn.commit()
    conn.close()

init_db()

# --- CLASSE PARA GERAÇÃO DE PDF ---
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
    
    # Cabeçalho da Ficha
    pdf.cell(0, 8, f"Nome do Doente: {p['nome']} | Leito: {p['leito']}", ln=True)
    pdf.cell(0, 8, f"Data de Admissao: {p['data_admissao']} | Peso Admissao: {p['peso_seco']} kg", ln=True)
    pdf.cell(0, 8, f"Superficie Corporal: {p['sc']:.2f} m2 | TFGe Inicial: {p['tfge']:.1f}", ln=True)
    pdf.ln(5)
    
    pdf.set_font("helvetica", 'B', 11)
    pdf.cell(0, 10, "1. Controle de Sinais Vitais e Antropometria", ln=True)
    pdf.set_font("helvetica", size=9)
    pdf.multi_cell(0, 5, "Monitorizar a Pressao Arterial (PA) pelo menos 3x ao dia devido ao risco de hipertensao associada a corticoterapia e doenca renal.")
    pdf.ln(5)
    
    # Tabela de Monitorização
    pdf.set_font('helvetica', 'B', 8)
    cols = [('Data', 25), ('Hora', 20), ('Peso (kg)', 25), ('PA', 30), ('FC', 25), ('FR', 25), ('Temp', 25)]
    for head, width in cols: pdf.cell(width, 8, head, 1, 0, 'C')
    pdf.ln()
    
    pdf.set_font('helvetica', '', 8)
    for _, row in hist.iterrows():
        pdf.cell(25, 8, str(row['data']), 1, 0, 'C'); pdf.cell(20, 8, str(row['hora']), 1, 0, 'C')
        pdf.cell(25, 8, f"{row['peso']:.2f}", 1, 0, 'C'); pdf.cell(30, 8, str(row['pa']), 1, 0, 'C')
        pdf.cell(25, 8, str(row['fc']), 1, 0, 'C'); pdf.cell(25, 8, str(row['fr']), 1, 0, 'C')
        pdf.cell(25, 8, f"{row['temp']:.1f}", 1, 1, 'C')
        
    return bytes(pdf.output())

# --- INTERFACE ---
st.title("🩺 Nefropediatria - HNSM (2026)")
tab1, tab2, tab3 = st.tabs(["🔢 Cadastro e Cálculos", "📋 Monitorização Diária", "📂 Histórico e PDF"])

# --- TAB 1: CADASTRO E CÁLCULOS ---
with tab1:
    with st.form("cadastro_form"):
        col_c1, col_c2 = st.columns(2)
        n_in = col_c1.text_input("Nome do Paciente").upper()
        l_in = col_c2.text_input("Leito")
        d_adm_in = st.date_input("Data de Admissão", value=datetime.now())
        
        st.write("**Idade do Paciente:**")
        c1, c2, c3 = st.columns(3)
        anos_in = c1.number_input("Anos", 0, 18, 5)
        meses_in = c2.number_input("Meses", 0, 11, 0)
        dias_in = c3.number_input("Dias", 0, 30, 0)
        sexo_in = st.radio("Sexo Biológico", ["Feminino", "Masculino"], horizontal=True)
        
        # Lógica de K automática (Schwartz 1) - Resolvendo SyntaxError
        idade_total_meses = (anos_in * 12) + meses_in
        if idade_total_meses < 12:
            prematuro = st.checkbox("Nasceu prematuro?")
            k_val, cat = (0.33, "RN Pré-termo") if prematuro else (0.45, "RN a termo")
        else:
            if sexo_in == "Masculino" and anos_in >= 13: k_val, cat = 0.70, "Adolescente Masculino"
            else: k_val, cat = 0.55, "Criança / Adolescente Feminino"
            
        st.info(f"Categoria: {cat} (K = {k_val})")
        
        # Resolvendo NameError: Sincronizando nomes de entrada
        p_in = st.number_input("Peso na Admissão (kg)", 1.0, 150.0, 20.0)
        e_in = st.number_input("Estatura (cm)", 30.0, 200.0, 110.0)
        cr_in = st.number_input("Creatinina Jaffé (mg/dL)", 0.1, 10.0, 0.6)
        
        btn_calc = st.form_submit_button("Salvar e Calcular Conduta")

    if btn_calc:
        # Cálculos Técnicos
        sc_calc = math.sqrt((p_in * e_in) / 3600)
        tfge_calc = (k_val * e_in) / cr_in
        dose_at = min(sc_calc * 60, 60.0)
        dose_mn = min(sc_calc * 40, 40.0)
        vol_alb = (p_in * 0.5) * 5
        dose_furo = p_in * 0.5
        
        conn = sqlite3.connect('nefroped_merces.db'); c = conn.cursor()
        c.execute("INSERT INTO pacientes VALUES (NULL,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", 
                  (n_in, l_in, d_adm_in.strftime("%d/%m/%Y"), anos_in, meses_in, dias_in, sexo_in, k_val, p_in, e_in, sc_calc, tfge_calc, dose_at, dose_mn, vol_alb, dose_furo))
        conn.commit(); conn.close()
        
        st.divider()
        st.subheader("📋 Resultados e Conduta")
        r1, r2, r3 = st.columns(3)
        r1.metric("Superfície Corporal", f"{sc_calc:.2f} m²")
        r2.metric("TFGe (Schwartz 1)", f"{tfge_calc:.1f} mL/min")
        r3.metric("K Utilizado", f"{k_val}")
        
        st.warning(f"**Corticoterapia:** Ataque: {dose_at:.1f} mg/dia | Manutenção: {dose_mn:.1f} mg (D.A.)")
        st.info(f"**Suporte:** Albumina 20%: {vol_alb:.1f} mL | Furosemida IV: {dose_furo:.1f} mg")

# --- TAB 2: MONITORIZAÇÃO ---
with tab2:
    conn = sqlite3.connect('nefroped_merces.db')
    pacs = pd.read_sql("SELECT id, nome, leito FROM pacientes", conn); conn.close()
    if not pacs.empty:
        escolha = st.selectbox("Paciente", pacs['nome'] + " (Leito: " + pacs['leito'] + ")")
        pac_id = int(pacs[pacs['nome'] == escolha.split(" (")[0]]['id'].iloc[0])
        with st.form("vitais"):
            d_sv, h_sv = st.columns(2)
            data_r = d_sv.date_input("Data"); hora_r = h_sv.selectbox("Hora", ["08:00", "14:00", "20:00"])
            v1, v2, v3, v4, v5 = st.columns(5)
            p_v = v1.number_input("Peso (kg)"); pa_v = v2.text_input("PA (mmHg)"); fc_v = v3.number_input("FC", 0); fr_v = v4.number_input("FR", 0); t_v = v5.number_input("Temp", 30.0, 42.0, 36.5)
            if st.form_submit_button("Salvar Registro"):
                conn = sqlite3.connect('nefroped_merces.db'); c = conn.cursor()
                c.execute("INSERT INTO monitorizacao (paciente_id, data, hora, peso, pa, fc, fr, temp) VALUES (?,?,?,?,?,?,?,?)", (pac_id, data_r.strftime("%d/%m/%Y"), hora_r, p_v, pa_v, fc_v, fr_v, t_v))
                conn.commit(); conn.close(); st.success("Salvo!")

# --- TAB 3: HISTÓRICO E PDF ---
with tab3:
    busca = st.text_input("🔎 BUSCAR PACIENTE").upper()
    if busca:
        conn = sqlite3.connect('nefroped_merces.db')
        p_data = pd.read_sql(f"SELECT * FROM pacientes WHERE nome LIKE '%{busca}%'", conn)
        if not p_data.empty:
            p_sel = p_data.iloc[0]
            h_data = pd.read_sql(f"SELECT * FROM monitorizacao WHERE paciente_id = {p_sel['id']} ORDER BY data DESC, hora DESC", conn)
            st.dataframe(h_data[['data', 'hora', 'peso', 'pa', 'fc', 'fr', 'temp']])
            
            # Resolvendo AttributeError do PDF
            pdf_bytes = gerar_pdf(p_sel, h_data)
            st.download_button("📥 Baixar PDF", data=pdf_bytes, file_name=f"Ficha_{p_sel['nome']}.pdf", mime="application/pdf")
        conn.close()

with st.sidebar:
    st.error("🚨 **Sinais de Alerta**")
    with st.expander("Notificar Nefropediatra se:"):
        st.write("- Oligúria (< 1 mL/kg/h)\n- Hematúria Macroscópica\n- Crise Hipertensiva\n- Abdome Agudo (PBE)")
