import streamlit as st
import pandas as pd
import plotly.express as px
import sqlite3
import os
from datetime import datetime

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="Glicemia Pro Elite", layout="wide", page_icon="🩸")

# --- PERSISTENZA DATI ---
# Utilizziamo un percorso specifico per il DB per stabilizzarlo su Streamlit Cloud
DB_FILE = 'diario_persistente_v1.db'

def get_connection():
    return sqlite3.connect(DB_FILE, check_same_thread=False)

conn = get_connection()
c = conn.cursor()
c.execute('CREATE TABLE IF NOT EXISTS utenti (nome TEXT, t_min INTEGER, t_max INTEGER)')
c.execute('''CREATE TABLE IF NOT EXISTS diario 
             (data TEXT, ora_pasto TEXT, ora_glicemia TEXT, diff_minuti INTEGER, 
              glicemia INTEGER, cibo TEXT, grammi REAL, kcal REAL, carbo REAL, ig INTEGER)''')
conn.commit()

# --- CARICAMENTO DATABASE CIBI ---
@st.cache_data
def carica_database_cibi():
    if os.path.exists("database_cibi.csv"):
        return pd.read_csv("database_cibi.csv").sort_values(by="cibo")
    return pd.DataFrame(columns=["cibo", "kcal", "carbo", "ig"])

db_cibi = carica_database_cibi()

# --- SIDEBAR: PROFILO ---
c.execute("SELECT * FROM utenti LIMIT 1")
user = c.fetchone()

with st.sidebar:
    st.title("⚙️ Impostazioni")
    if not user:
        with st.form("setup"):
            n = st.text_input("Nome")
            if st.form_submit_button("Crea Profilo"):
                c.execute("INSERT INTO utenti VALUES (?,?,?)", (n, 70, 140))
                conn.commit()
                st.rerun()
    else:
        st.write(f"Utente: **{user[0]}**")
        if st.button("Esporta Dati (CSV)"):
            df_export = pd.read_sql_query("SELECT * FROM diario", conn)
            st.download_button("Scarica", df_export.to_csv(index=False), "diario.csv")

# --- APP PRINCIPALE ---
st.title("🩸 Monitoraggio Avanzato Glicemia")

tab_ins, tab_stat = st.tabs(["📝 Inserimento Dati", "📈 Analisi Professionale"])

with tab_ins:
    col_a, col_b = st.columns([2, 1])
    
    with col_a:
        scelta = st.selectbox("Seleziona Alimento:", [""] + db_cibi['cibo'].tolist())
        
        info = {"kcal": 0, "carbo": 0, "ig": 0}
        if scelta:
            match = db_cibi[db_cibi['cibo'] == scelta].iloc[0]
            info = {"kcal": match['kcal'], "carbo": match['carbo'], "ig": match['ig']}
            
            # Calcolo Carico Glicemico (CG) teorico su 100g
            cg = (info['carbo'] * info['ig']) / 100
            st.info(f"🧬 **IG: {info['ig']}** | Carico Glicemico (100g): {cg:.1f}")

    with st.form("registro_completo"):
        c1, c2, c3 = st.columns(3)
        glic = c1.number_input("Glicemia (mg/dL)", 20, 500, 100)
        grammi = c1.number_input("Quantità (g)", 1, 1000, 100)
        
        o_pasto = c2.time_input("Ora Pasto", datetime.now().time())
        o_glic = c2.time_input("Ora Misurazione", datetime.now().time())
        
        data_ev = c3.date_input("Data", datetime.now().date())
        nome_c = c3.text_input("Etichetta Cibo", value=scelta)
        
        if st.form_submit_button("💾 Salva nel Database"):
            # Calcolo Delta Tempo
            dt_p = datetime.combine(data_ev, o_pasto)
            dt_g = datetime.combine(data_ev, o_glic)
            delta = int((dt_g - dt_p).total_seconds() / 60)
            
            # Calcolo Valori
            kcal_t = (info['kcal'] * grammi) / 100
            carb_t = (info['carbo'] * grammi) / 100
            
            c.execute("INSERT INTO diario VALUES (?,?,?,?,?,?,?,?,?,?)", 
                      (data_ev.strftime("%Y-%m-%d"), o_pasto.strftime("%H:%M"), 
                       o_glic.strftime("%H:%M"), delta, glic, nome_c, grammi, kcal_t, carb_t, info['ig']))
            conn.commit()
            st.success("Dati salvati in memoria permanente!")
            st.rerun()

with tab_stat:
    df = pd.read_sql_query("SELECT * FROM diario ORDER BY data DESC, ora_glicemia DESC", conn)
    
    if not df.empty:
        # Grafico Correlazione IG / Glicemia
        st.subheader("Impatto dell'Indice Glicemico")
        fig = px.scatter(df, x="diff_minuti", y="glicemia", color="ig", 
                         size="carbo", hover_name="cibo",
                         title="Relazione tra Tempo, IG e Picco Glicemico",
                         color_continuous_scale="Reds")
        st.plotly_chart(fig, use_container_width=True)
        
        # Tabella Storica
        st.subheader("📋 Registro Storico")
        st.dataframe(df, use_container_width=True)
    else:
        st.info("Nessun dato salvato. I tuoi inserimenti appariranno qui.")
