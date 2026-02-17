import streamlit as st
import math
import sqlite3
import pandas as pd
from datetime import datetime

# --- 1. DADOS DE REFERÊNCIA SBP 2019 (CÉREBRO DA CLASSIFICAÇÃO) ---
# [cite_start]Fonte: Manual de Orientação SBP 2019 [cite: 36]
BP_DATA = {
    'M': { 
        1: {'ht': [77, 78, 80, 82, 85, 87, 88], 'pas90': [98,99,99,100,101,101,102], 'pas95': [102,102,103,103,104,105,105], 'pad90': [52,52,53,53,54,54,54], 'pad95': [54,54,55,55,56,57,57]},
        5: {'ht': [104,106,109,112,116,119,120], 'pas90': [103,104,105,106,107,108,109], 'pas95': [107,107,108,109,110,111,112], 'pad90': [63,63,64,65,66,66,67], 'pad95': [69,69,70,71,72,72,73]},
        10: {'ht': [130,133,137,141,146,150,153], 'pas90': [108,109,111,113,115,116,117], 'pas95': [113,113,115,117,119,120,121], 'pad90': [72,73,73,74,75,76,76], 'pad95': [77,77,78,79,80,80,81]},
        13: {'ht': [148,152,158,164,170,175,179], 'pas90': [113,114,115,117,119,121,122], 'pas95': [116,117,118,124,124,121,128], 'pad90': [74,74,74,75,76,76,77], 'pad95': [78,78,78,78,79,79,80]},
    },
    'F': { 
        1: {'ht': [75,77,79,81,83,85,86], 'pas90': [98,99,99,100,101,102,102], 'pas95': [101,102,102,103,104,105,105], 'pad90': [54,55,56,57,58,58,58], 'pad95': [59,59,60,60,61,61,62]},
        5: {'ht': [104,105,108,112,115,118,120], 'pas90': [103,104,105,106,107,108,109], 'pas95': [107,108,109,110,111,112,112], 'pad90': [64,64,65,66,67,68,69], 'pad95': [69,69,70,71,72,72,73]},
        10: {'ht': [130,132,136,141,146,150,153], 'pas90': [109,110,111,112,113,115,116], 'pas95': [113,114,115,116,117,119,120], 'pad90': [72,73,73,73,74,75,75], 'pad95': [76,77,77,77,78,79,80]},
        13: {'ht': [149,152,156,160,164,168,171], 'pas90': [114,115,116,118,119,120,121], 'pas95': [118,119,120,122,123,124,125], 'pad90': [75,76,76,76,77,78,78], 'pad95': [79,80,80,80,81,82,82]},
    }
}

def get_bp_limits(sexo, idade, altura_cm):
    # BLINDAGEM: Converte "Masculino" para "M" e "Feminino" para "F" se necessário
    sexo_tratado = 'M' if sexo.upper().startswith('M') else 'F'
    
    # Regra Adolescente >= 13 anos (Critérios Fixos - Quadro 4 SBP 2019)
    if idade >= 13: 
        return {'p90s': 120, 'p95s': 130, 'p99s': 140, 'p90d': 80, 'p95d': 80, 'p99d': 90}
    
    # Regra Criança < 13 anos (Percentis - Tabelas 1 e 2 SBP 2019)
    idades_disp = [1, 5, 10, 13]
    idade_prox = min(idades_disp, key=lambda x: abs(x - idade))
    
    # Usa o sexo tratado para buscar na tabela
    table = BP_DATA[sexo_tratado][idade_prox]
    
    # Encontra a coluna da estatura mais próxima
    closest_idx = min(range(len(table['ht'])), key=lambda i: abs(table['ht'][i] - altura_cm))
    
    p95s = table['pas95'][closest_idx]
    p95d = table['pad95'][closest_idx]
    
    return {'p90s': table['pas90'][closest_idx], 'p95s': p95s, 'p99s': p95s + 12, 
            'p90d': table['pad90'][closest_idx], 'p95d': p95d, 'p99d': p95d + 12}

def classificar_pa_auto(pas, pad, limites):
    # [cite_start]Lógica de Classificação SBP 2019 [cite: 36]
    if (pas >= limites['p99s']) or (pad >= limites['p99d']): return "ESTÁGIO 2", "red"
    elif (pas >= limites['p95s']) or (pad >= limites['p95d']): return "ESTÁGIO 1", "orange"
    elif (pas >= limites['p90s']) or (pad >= limites['p90d']): return "ELEVADA", "yellow"
    else: return "NORMOTENSO", "green"

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- CONFIGURAÇÃO DE E-MAIL (PREENCHA AQUI) ---
EMAIL_REMETENTE = "seu_email_aqui@gmail.com" # <--- SUBSTITUA PELO SEU GMAIL
SENHA_APP = "sua_senha_de_app_aqui"          # <--- SUBSTITUA PELA SENHA DE APP

# --- FUNÇÃO DE ENVIO DE E-MAIL ---
def enviar_relatorio(destinatario, paciente, historico):
    if "seu_email" in EMAIL_REMETENTE:
        st.error("⚠️ Configure o e-mail no código para funcionar!")
        return
    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_REMETENTE
        msg['To'] = destinatario
        msg['Subject'] = f"Relatório Médico: {paciente['nome']} - HNSM"

        html = f"""
        <html><body>
            <h2 style="color:#2c3e50">Hospital Nossa Senhora das Mercês</h2>
            <p><strong>Paciente:</strong> {paciente['nome']} | <strong>Idade:</strong> {paciente['anos']} anos</p>
            <p><strong>SC:</strong> {paciente['sc']:.2f} m² | <strong>TFGe:</strong> {paciente['tfge']:.1f}</p>
            <h4>Conduta:</h4>
            <ul><li>Prednisolona Ataque: {paciente['dose_at']:.1f} mg</li></ul>
            <h4>Últimos Sinais Vitais:</h4>
            {historico[['data','hora','pa','classif_pa','peso','vol_24h']].to_html(index=False, border=1)}
        </body></html>
        """
        msg.attach(MIMEText(html, 'html'))
        
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(EMAIL_REMETENTE, SENHA_APP)
        server.sendmail(EMAIL_REMETENTE, destinatario, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        return str(e)

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
    
    # Tabela Completa com todos os sinais vitais incluindo FR
    c.execute('''CREATE TABLE IF NOT EXISTS monitorizacao 
                 (id INTEGER PRIMARY KEY, paciente_id INTEGER, data TEXT, hora TEXT, 
                  peso REAL, pa TEXT, fc INTEGER, fr INTEGER, temp REAL, vol_24h REAL,
                  classif_pa TEXT)''')
    conn.commit(); conn.close()

init_db()

# --- 3. BARRA LATERAL COM LOGIN ---
with st.sidebar:
    st.image("https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcRA56LAYwChMUASMvAiUzJovteq8vizuaUn6A&s", width=150)
    st.title("Pediatria - Hospital de Nossa Senhora das Mercês")
    
    # SE NÃO ESTIVER LOGADO
    if 'usuario_email' not in st.session_state:
        st.markdown("### 🔐 Acesso Médico")
        email = st.text_input("E-mail")
        senha = st.text_input("Senha", type="password")
        if st.button("Entrar"):
            if email and senha: # Adicione validação de senha real aqui se quiser
                st.session_state['usuario_email'] = email
                st.rerun()
            else:
                st.error("Preencha os dados.")
        st.stop() # PARA A EXECUÇÃO DO RESTO DA PÁGINA AQUI

    # SE ESTIVER LOGADO (MOSTRA AS FERRAMENTAS)
    else:
        st.success(f"Logado: {st.session_state['usuario_email']}")
        if st.button("Sair"):
            del st.session_state['usuario_email']
            st.rerun()
            
        st.markdown("---")
        st.error("🚨 **Sinais de Alerta**")
        with st.expander("Quando acionar a Nefropediatria", expanded=True):
            st.markdown("""
            - **Oligúria:** < 1 mL/kg/h
            - **Hipertensão:** PAS ≥ P95
            - **Hematúria:** Macroscópica
            - **PBE:** Dor abdominal + Febre
            """)
        
        st.divider()
        if st.button("⚠️ Resetar Banco de Dados"):
            conn = sqlite3.connect('nefroped_merces.db'); c = conn.cursor()
            c.execute("DROP TABLE IF EXISTS pacientes"); c.execute("DROP TABLE IF EXISTS monitorizacao")
            conn.commit(); conn.close(); init_db(); st.rerun()

# --- 4. INTERFACE PRINCIPAL ---
st.image("https://alfred.alboompro.com/resize/width/370/height/150/quality/99/url/storage.alboom.ninja/sites/261239/img/logo/logo_hor.png?t=1741614330", width=300)
st.title("Calculadora de Nefrologia Pediátrica")

# VERIFICAÇÃO DE SEGURANÇA
if 'usuario_email' not in st.session_state:
    st.warning("👈 Por favor, faça login na barra lateral para acessar o sistema.")
    st.stop()

# (O restante do seu código original começa aqui: tab1, tab2, tab3...)
tab1, tab2, tab3 = st.tabs(["🔢 Cadastro e Cálculos", "📋 Monitorização Diária", "📂 Prontuário"])


# --- TAB 1: CADASTRO ---
with tab1:
    with st.container(border=True):
        st.subheader("👤 Identificação")
        c1, c2 = st.columns(2)
        nome_in = c1.text_input("Nome Completo").upper()
        leito_in = c2.text_input("Leito")
        
        st.write("---")
        st.write("**Dados Antropométricos:**")
        c1, c2, c3 = st.columns(3)
        anos = c1.number_input("Anos", 0, 18, 5)
        meses = c2.number_input("Meses", 0, 11, 0)
        sexo = c3.radio("Sexo", ["M", "F"], horizontal=True)
        
        # K Schwartz Automático
        k_val = 0.55
        cat = "Criança / Adolescente Fem."
        if (anos * 12 + meses) < 12: 
            if st.checkbox("Prematuro?"): k_val, cat = 0.33, "RN Pré-termo"
            else: k_val, cat = 0.45, "RN a Termo"
        elif sexo == "M" and anos >= 13: k_val, cat = 0.70, "Adolescente Masc."
        
        st.success(f"**Categoria:** {cat} | **Constante K:** {k_val}")
        
        c1, c2, c3 = st.columns(3)
        p_in = c1.number_input("Peso Seco (kg)", 1.0, 150.0, 20.0)
        e_in = c2.number_input("Estatura (cm)", 30.0, 200.0, 110.0)
        cr_in = c3.number_input("Creatinina (mg/dL)", 0.1, 15.0, 0.6)
        
        if st.button("💾 Salvar e Calcular", type="primary"):
            # 1. Cálculos Gerais
            sc = math.sqrt((p_in * e_in) / 3600)
            tfge = (k_val * e_in) / cr_in
            
            # 2. Novo Cálculo Prednisolona (HNSM: 2mg/kg | Conc: 3mg/mL)
            # Dose Ataque: 2 mg/kg (Teto 60mg diários)
            dose_at_mg = min(p_in * 2.0, 60.0) 
            vol_at_ml = dose_at_mg / 3.0       # Converte mg para mL (Concentração 3mg/mL)
            
            # Dose Manutenção: 1.5 mg/kg (Teto 40mg diários - Dias Alternados)
            dose_mn_mg = min(p_in * 1.5, 40.0)
            vol_mn_ml = dose_mn_mg / 3.0       # Converte mg para mL
            
            # 3. Outros medicamentos
            alb = (p_in * 0.5) * 5 # Albumina 20%
            furo = p_in * 0.5      # Furosemida
            
            # 4. Salvar no Banco (Salvamos em mg para registro clínico universal)
            conn = sqlite3.connect('nefroped_merces.db'); c = conn.cursor()
            c.execute("INSERT INTO pacientes VALUES (NULL,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", 
                      (nome_in, leito_in, datetime.now().strftime("%d/%m"), anos, meses, 0, sexo, k_val, p_in, e_in, sc, tfge, dose_at_mg, dose_mn_mg, alb, furo))
            conn.commit(); conn.close()
            st.toast(f"Paciente {nome_in} cadastrado com sucesso!")

            # 5. Exibição de Resultados (EM ML)
            st.write("---")
            st.subheader("📊 Resultados Clínicos")
            m1, m2, m3 = st.columns(3)
            m1.metric("Superfície Corporal", f"{sc:.2f} m²")
            m2.metric("TFGe (Schwartz)", f"{tfge:.1f} mL/min")
            m3.metric("Peso Utilizado", f"{p_in:.1f} kg")
            
            c1, c2 = st.columns(2)
            # Mostra o mL em destaque e o mg entre parênteses
            c1.warning(f"💊 **Prednisolona (3 mg/mL)**\n\n- Ataque: **{vol_at_ml:.1f} mL** ({dose_at_mg:.0f} mg)\n- Manut.: **{vol_mn_ml:.1f} mL** ({dose_mn_mg:.0f} mg)")
            c2.info(f"💧 **Manejo de Edema**\n\n- Albumina 20%: **{alb:.1f} mL**\n- Furosemida: **{furo:.1f} mg**")
# --- TAB 2: MONITORIZAÇÃO COMPLETA ---
with tab2:
    conn = sqlite3.connect('nefroped_merces.db')
    pacs = pd.read_sql("SELECT id, nome, anos, sexo, estatura FROM pacientes", conn); conn.close()
    
    if not pacs.empty:
        escolha = st.selectbox("Selecione o Paciente:", pacs['nome'])
        p_data = pacs[pacs['nome'] == escolha].iloc[0]
        
        with st.container(border=True):
            st.subheader("🩺 Registro de Sinais Vitais")
            
            # Linha 1: Data e Hora
            c1, c2 = st.columns(2)
            d_reg = c1.date_input("Data")
            h_reg = c2.selectbox("Hora", ["08:00", "14:00", "20:00", "Extra"])
            
            st.write("---")
            
            # Linha 2: Avaliação Hemodinâmica (PA)
            st.write("**Hemodinâmica:**")
            col_pa1, col_pa2 = st.columns(2)
            pas = col_pa1.number_input("PAS (Sistólica)", 0, 300, 110)
            pad = col_pa2.number_input("PAD (Diastólica)", 0, 200, 70)
            
            # Automação SBP 2019
            limites = get_bp_limits(p_data['sexo'], p_data['anos'], p_data['estatura'])
            status_pa, cor_pa = classificar_pa_auto(pas, pad, limites)
            st.caption(f"Referência SBP: P95={limites['p95s']}/{limites['p95d']} | P99+5={limites['p99s']}/{limites['p99d']}")
            st.markdown(f"#### Classificação: :{cor_pa}[{status_pa}]")
            
            st.write("---")
            
            # Linha 3: Outros Sinais Vitais (TODOS INCLUÍDOS)
            st.write("**Dados Clínicos e Hídricos:**")
            v1, v2, v3, v4, v5 = st.columns(5)
            p_v = v1.number_input("Peso (kg)", format="%.2f")
            fc = v2.number_input("FC (bpm)", 0)
            fr = v3.number_input("FR (irpm)", 0) # Campo recuperado
            temp = v4.number_input("Temp (ºC)", 36.5)
            vol = v5.number_input("Diurese 24h (mL)", 0)
            
            if st.button("💾 Salvar Evolução"):
                conn = sqlite3.connect('nefroped_merces.db'); c = conn.cursor()
                
                # CORREÇÃO PONTUAL: 10 colunas = 10 interrogações (?)
                c.execute("""INSERT INTO monitorizacao 
                             (paciente_id, data, hora, peso, pa, fc, fr, temp, vol_24h, classif_pa) 
                             VALUES (?,?,?,?,?,?,?,?,?,?)""",
                          (int(p_data['id']), d_reg.strftime("%d/%m"), h_reg, p_v, f"{pas}/{pad}", fc, fr, temp, vol, status_pa))
                
                conn.commit(); conn.close()
                st.success("Dados salvos!")
    else:
        st.warning("Nenhum paciente cadastrado.")

# --- TAB 3: PRONTUÁRIO ---
with tab3:
    busca = st.text_input("🔎 Buscar Paciente").upper()
    if busca:
        conn = sqlite3.connect('nefroped_merces.db')
        p_res = pd.read_sql(f"SELECT * FROM pacientes WHERE nome LIKE '%{busca}%'", conn)
        
        if not p_res.empty:
            p_sel = p_res.iloc[0]
            st.markdown(f"### 🏥 {p_sel['nome']} | Leito: {p_sel['leito']}")
            
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Idade", f"{p_sel['anos']} anos")
            c2.metric("SC", f"{p_sel['sc']:.2f} m²")
            c3.metric("TFGe", f"{p_sel['tfge']:.1f}")
            c4.metric("Dose Ataque", f"{p_sel['dose_at']:.1f} mg")
            
            st.divider()
            st.markdown("#### 📊 Histórico de Monitorização")
            
            # Query completa
            h_data = pd.read_sql(f"SELECT data, hora, pa, classif_pa, peso, fc, fr, temp, vol_24h FROM monitorizacao WHERE paciente_id = {p_sel['id']} ORDER BY id DESC", conn)
            
            if not h_data.empty:
                h_data['debito'] = h_data['vol_24h'] / p_sel['peso_seco'] / 24
                
                def colorir(row):
                    estilos = [''] * len(row)
                    # Cor da PA
                    mapa = {"ESTÁGIO 2": "#ffcccc", "ESTÁGIO 1": "#ffe5cc", "ELEVADA": "#ffffcc"}
                    for k, v in mapa.items():
                        if k in str(row['classif_pa']): estilos[row.index.get_loc('pa')] = f'background-color: {v}; color: black; font-weight: bold'
                    # Cor da Oligúria
                    if 0 < row['debito'] < 1.0: estilos[row.index.get_loc('vol_24h')] = 'background-color: #ffffcc; color: red; font-weight: bold'
                    return estilos

                st.dataframe(h_data.style.apply(colorir, axis=1).format({'debito': '{:.2f}', 'peso': '{:.2f}', 'temp': '{:.1f}'}), use_container_width=True)
                st.caption("Legenda: 🟥 Estágio 2 | 🟧 Estágio 1 | 🟨 Elevada/Oligúria")
        conn.close()
