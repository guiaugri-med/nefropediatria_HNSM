import streamlit as st
import math
import sqlite3
import pandas as pd
from datetime import datetime

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="NefroPed - HNSM", page_icon="🩺", layout="wide")

# --- 2. GERENCIAMENTO DO BANCO DE DADOS ---
def init_db():
    """Inicializa as tabelas se não existirem."""
    conn = sqlite3.connect('nefroped_merces.db')
    c = conn.cursor()
    
    # Tabela de Pacientes (Dados fixos da admissão e cálculos iniciais)
    c.execute('''CREATE TABLE IF NOT EXISTS pacientes 
                 (id INTEGER PRIMARY KEY, 
                  nome TEXT, leito TEXT, data_admissao TEXT, 
                  anos INTEGER, meses INTEGER, dias INTEGER, sexo TEXT, k REAL, 
                  peso_seco REAL, estatura REAL, sc REAL, tfge REAL, 
                  dose_at REAL, dose_mn REAL, vol_alb REAL, dose_furo REAL)''')
    
    # Tabela de Monitorização (Dados variáveis dia a dia)
    c.execute('''CREATE TABLE IF NOT EXISTS monitorizacao 
                 (id INTEGER PRIMARY KEY, 
                  paciente_id INTEGER, 
                  data TEXT, hora TEXT, 
                  peso REAL, pa TEXT, fc INTEGER, fr INTEGER, temp REAL, vol_24h REAL)''')
    
    conn.commit()
    conn.close()

# Executa a criação do banco ao iniciar o app
init_db()

# --- 3. BARRA LATERAL (FERRAMENTAS) ---
with st.sidebar:
    st.header("🏥 Gestão HNSM")
    st.info("Internato de Pediatria - 2026")
    
    st.divider()
    st.error("🚨 **Sinais de Alerta**")
    with st.expander("Critérios de Gravidade"):
        st.write("- **Oligúria:** < 1 mL/kg/h")
        st.write("- **Hipertensão:** PAS ≥ P95")
        st.write("- **Hematúria:** Macroscópica")
        st.write("- **PBE:** Dor abdominal + Febre")
    
    st.divider()
    # Botão de emergência para corrigir erros de coluna no banco de dados
    if st.button("⚠️ Resetar Banco de Dados", help="Clique aqui caso apareça erro de 'no column named vol_24h'"):
        conn = sqlite3.connect('nefroped_merces.db')
        c = conn.cursor()
        c.execute("DROP TABLE IF EXISTS pacientes")
        c.execute("DROP TABLE IF EXISTS monitorizacao")
        conn.commit()
        conn.close()
        init_db() # Recria as tabelas do zero
        st.success("Banco de dados reiniciado e corrigido!")
        st.rerun()

# --- 4. INTERFACE PRINCIPAL ---
st.title("Calculadora de Nefrologia Pediátrica")
st.caption("Protocolo: Schwartz 1 (Jaffé) | ICr-HCFMUSP & HNSM")

tab1, tab2, tab3 = st.tabs(["🔢 Cadastro e Conduta", "📋 Monitorização Diária", "📂 Histórico e Alertas"])

# ==============================================================================
# TAB 1: CADASTRO E CÁLCULOS INICIAIS
# ==============================================================================
with tab1:
    # Usamos container com borda em vez de form para evitar envio com "Enter"
    with st.container(border=True):
        st.subheader("👤 Identificação e Admissão")
        col_c1, col_c2 = st.columns(2)
        nome_in = col_c1.text_input("Nome do Paciente").upper()
        leito_in = col_c2.text_input("Leito")
        data_adm_in = st.date_input("Data de Admissão", value=datetime.now())
        
        st.write("---")
        st.write("**Dados Antropométricos:**")
        c1, c2, c3 = st.columns(3)
        anos_in = c1.number_input("Anos", 0, 18, 5)
        meses_in = c2.number_input("Meses", 0, 11, 0)
        dias_in = c3.number_input("Dias", 0, 30, 0)
        sexo_in = st.radio("Sexo Biológico", ["Feminino", "Masculino"], horizontal=True)
        
        # Lógica Automática de K (Schwartz 1)
        total_meses = (anos_in * 12) + meses_in
        k_val = 0.55 # Valor padrão
        cat = "Indefinido"

        if total_meses < 12:
            prematuro = st.checkbox("Nasceu prematuro?")
            if prematuro:
                k_val, cat = 0.33, "RN Pré-termo"
            else:
                k_val, cat = 0.45, "RN a termo"
        else:
            if sexo_in == "Masculino" and anos_in >= 13:
                k_val, cat = 0.70, "Adolescente Masculino"
            else:
                k_val, cat = 0.55, "Criança / Adolescente Feminino"
            
        st.info(f"**Constante K:** {k_val} ({cat})")
        
        st.write("---")
        st.write("**Parâmetros Clínicos:**")
        col_p1, col_p2, col_p3 = st.columns(3)
        p_in = col_p1.number_input("Peso Seco (kg)", 1.0, 150.0, 20.0)
        e_in = col_p2.number_input("Estatura (cm)", 30.0, 200.0, 110.0)
        cr_in = col_p3.number_input("Creatinina (mg/dL)", 0.1, 15.0, 0.6)
        
        # Botão de ação (não salva com Enter)
        btn_calc = st.button("💾 Salvar Cadastro e Calcular", type="primary")

    if btn_calc:
        if not nome_in:
            st.error("Por favor, insira o nome do paciente.")
        else:
            # Cálculos Nefrológicos
            sc_calc = math.sqrt((p_in * e_in) / 3600) # Mosteller
            tfge_calc = (k_val * e_in) / cr_in # Schwartz 1
            
            # Doses (Teto: Prednisolona ataque max 60mg, manut max 40mg)
            dose_at = min(sc_calc * 60, 60.0)
            dose_mn = min(sc_calc * 40, 40.0)
            vol_alb = (p_in * 0.5) * 5 # 0.5 g/kg -> 2.5 mL/kg (Albumina 20%)
            dose_furo = p_in * 0.5     # 0.5 mg/kg

            # Salvar no SQLite
            conn = sqlite3.connect('nefroped_merces.db')
            c = conn.cursor()
            c.execute("""INSERT INTO pacientes VALUES 
                         (NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", 
                      (nome_in, leito_in, data_adm_in.strftime("%d/%m/%Y"), 
                       anos_in, meses_in, dias_in, sexo_in, k_val, 
                       p_in, e_in, sc_calc, tfge_calc, 
                       dose_at, dose_mn, vol_alb, dose_furo))
            conn.commit()
            conn.close()
            
            st.success(f"Paciente {nome_in} cadastrado com sucesso!")
            
            # Exibição Imediata dos Resultados
            st.divider()
            st.subheader("📊 Resultados Calculados")
            m1, m2, m3 = st.columns(3)
            m1.metric("Superfície Corporal", f"{sc_calc:.2f} m²")
            m2.metric("TFGe (Schwartz)", f"{tfge_calc:.1f} mL/min")
            m3.metric("K Utilizado", f"{k_val}")
            
            st.warning(f"💊 **Corticoterapia:** Ataque: {dose_at:.1f} mg/dia | Manutenção: {dose_mn:.1f} mg (D.A.)")
            st.info(f"💧 **Manejo de Edema:** Albumina 20%: {vol_alb:.1f} mL | Furosemida IV: {dose_furo:.1f} mg")

# ==============================================================================
# TAB 2: MONITORIZAÇÃO DIÁRIA
# ==============================================================================
with tab2:
    conn = sqlite3.connect('nefroped_merces.db')
    pacs = pd.read_sql("SELECT id, nome, leito FROM pacientes", conn)
    conn.close()
    
    if pacs.empty:
        st.warning("Nenhum paciente cadastrado. Vá para a aba 'Cadastro' primeiro.")
    else:
        # Seleção do paciente
        escolha = st.selectbox("Selecione o Paciente:", pacs['nome'] + " - Leito: " + pacs['leito'])
        pac_id = int(pacs[pacs['nome'] == escolha.split(" - ")[0]]['id'].iloc[0])
        
        st.subheader("🩺 Registro de Sinais Vitais")
        with st.container(border=True):
            col_d, col_h = st.columns(2)
            data_reg = col_d.date_input("Data", value=datetime.now())
            hora_reg = col_h.selectbox("Hora", ["08:00", "14:00", "20:00", "Extra"])
            
            c1, c2, c3, c4, c5, c6 = st.columns(6)
            p_v = c1.number_input("Peso Jejum (kg)", format="%.2f")
            pa_v = c2.text_input("PA (mmHg)", placeholder="110/70")
            fc_v = c3.number_input("FC (bpm)", 0)
            fr_v = c4.number_input("FR (irpm)", 0)
            t_v = c5.number_input("Temp (ºC)", format="%.1f")
            vol_v = c6.number_input("Diurese 24h (mL)", 0)
            
            if st.button("💾 Salvar Evolução"):
                conn = sqlite3.connect('nefroped_merces.db')
                c = conn.cursor()
                c.execute("""INSERT INTO monitorizacao 
                             (paciente_id, data, hora, peso, pa, fc, fr, temp, vol_24h) 
                             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                          (pac_id, data_reg.strftime("%d/%m/%Y"), hora_reg, 
                           p_v, pa_v, fc_v, fr_v, t_v, vol_v))
                conn.commit()
                conn.close()
                st.success("Sinais vitais registrados com sucesso!")

# ==============================================================================
# TAB 3: HISTÓRICO E ALERTAS VISUAIS
# ==============================================================================
with tab3:
    st.subheader("🔎 Busca e Análise")
    busca = st.text_input("Buscar Paciente (Nome):").upper()
    
    if busca:
        conn = sqlite3.connect('nefroped_merces.db')
        # Busca parcial pelo nome
        p_data = pd.read_sql(f"SELECT * FROM pacientes WHERE nome LIKE '%{busca}%'", conn)
        
        if not p_data.empty:
            p_sel = p_data.iloc[0] # Pega o primeiro paciente encontrado
            
            st.markdown(f"### 🏥 {p_sel['nome']} | Leito: {p_sel['leito']}")
            st.write(f"**SC:** {p_sel['sc']:.2f} m² | **Peso Seco:** {p_sel['peso_seco']} kg")
            
            # --- FUNÇÃO DE ESTILO (DESTAQUES VISUAIS) ---
            def destacar_alertas(row):
                estilos = [''] * len(row)
                
                # 1. Alerta de PA Alta (Sistólica >= 130)
                try:
                    pas = int(str(row['pa']).split('/')[0])
                    if pas >= 130:
                        idx_pa = row.index.get_loc('pa')
                        estilos[idx_pa] = 'background-color: #ffcccc; color: red; font-weight: bold'
                except:
                    pass
                
                # 2. Alerta de Oligúria (Débito < 1.0)
                # Verifica se a coluna 'debito' existe e se o valor é baixo (mas maior que 0)
                try:
                    if 'debito' in row and 0 < row['debito'] < 1.0:
                        idx_deb = row.index.get_loc('debito')
                        estilos[idx_deb] = 'background-color: #fff3cd; color: #856404; font-weight: bold'
                except:
                    pass
                    
                return estilos

            st.divider()
            st.write("**Histórico de Monitorização:**")
            
            # Busca histórico
            query_hist = f"""SELECT data, hora, peso, pa, fc, fr, temp, vol_24h 
                             FROM monitorizacao 
                             WHERE paciente_id = {p_sel['id']} 
                             ORDER BY data DESC, hora DESC"""
            h_data = pd.read_sql(query_hist, conn)
            
            if not h_data.empty:
                # Cálculo automático do Débito Urinário (mL/kg/h)
                # Fórmula: Volume / Peso Seco / 24h
                h_data['debito'] = h_data['vol_24h'] / p_sel['peso_seco'] / 24
                
                # Formata a coluna de débito para 2 casas decimais
                # Aplica o estilo visual
                st.dataframe(h_data.style.apply(destacar_alertas, axis=1)
                                       .format({'debito': '{:.2f}', 'peso': '{:.2f}', 'temp': '{:.1f}'}), 
                             use_container_width=True)
                
                st.caption("*Legenda: Células vermelhas indicam PAS ≥ 130 mmHg. Células amarelas indicam débito urinário < 1 mL/kg/h (Oligúria).*")
            else:
                st.info("Nenhum registro de sinais vitais encontrado para este paciente.")

        else:
            st.warning("Paciente não encontrado.")
        
        conn.close()
