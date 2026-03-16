import streamlit as st
import pandas as pd
import sqlite3
import os
from datetime import datetime, timedelta

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="Glicemia Pro Italia", layout="wide", page_icon="🩸")

# --- GESTIONE DATABASE PERSONALE ---
# Usiamo un nome database solido
DB_FILE = 'diario_glicemico_v6.db'

def get_db():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    return conn

conn = get_db()
c = conn.cursor()
c.execute('CREATE TABLE IF NOT EXISTS utenti (nome TEXT, t_min INTEGER, t_max INTEGER)')
c.execute('''CREATE TABLE IF NOT EXISTS diario 
             (data TEXT, ora_pasto TEXT, ora_glicemia TEXT, delta INTEGER, 
              glicemia INTEGER, cibo TEXT, grammi REAL, carbo_tot REAL, ig INTEGER, cg REAL)''')
conn.commit()

# --- CARICAMENTO DATABASE ALIMENTI ---
@st.cache_data
def load_data():
    if os.path.exists("database_cibi.csv"):
        df = pd.read_csv("database_cibi.csv")
        return df.sort_values(by="cibo")
    return pd.DataFrame(columns=["cibo", "kcal", "carbo", "ig"])

food_db = load_data()

# --- UTENTE ---
c.execute("SELECT * FROM utenti LIMIT 1")
user = c.fetchone()

if not user:
    st.title("🩸 Benvenuto")
    with st.form("set"):
        n = st.text_input("Il tuo nome")
        if st.form_submit_button("Inizia"):
            c.execute("INSERT INTO utenti VALUES (?,?,?)", (n, 70, 140))
            conn.commit()
            st.rerun()
    st.stop()

# --- INTERFACCIA ---
st.title(f"🩸 Diario di {user[0]}")

tab_add, tab_view = st.tabs(["➕ Nuova Misurazione", "📊 Storico e Analisi"])

with tab_add:
    st.subheader("Cerca Alimento Semplice")
    # Selezione cibo
    scelta_cibo = st.selectbox("Cosa hai mangiato?", [""] + food_db['cibo'].tolist(), format_func=lambda x: 'Seleziona...' if x=='' else x)
    
    dati = {"kcal":0, "carbo":0, "ig":0}
    if scelta_cibo:
        r = food_db[food_db['cibo'] == scelta_cibo].iloc[0]
        dati = {"kcal": r['kcal'], "carbo": r['carbo'], "ig": r['ig']}
        st.info(f"✨ {scelta_cibo} (IG: {dati['ig']})")

    st.divider()

    with st.form("log_form"):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            val_glicemia = st.number_input("Glicemia (mg/dL)", 20, 500, 100)
            val_grammi = st.number_input("Quantità (grammi)", 0, 1000, 100)
        
        with col2:
            # Orari pre-impostati su ora attuale
            t_pasto = st.time_input("Ora del Pasto", (datetime.now() - timedelta(hours=1)).time())
            t_glicemia = st.time_input("Ora Misurazione", datetime.now().time())
            
        with col3:
            nome_cibo = st.text_input("Etichetta", value=scelta_cibo)
            data_corrente = st.date_input("Data", datetime.now().date())

        if st.form_submit_button("💾 Salva nel Diario"):
            # Calcoli
            c_effettivi = (dati['carbo'] * val_grammi) / 100
            cg_effettivo = (c_effettivi * dati['ig']) / 100
            
            dt_p = datetime.combine(data_corrente, t_pasto)
            dt_g = datetime.combine(data_corrente, t_glicemia)
            delta_m = int((dt_g - dt_p).total_seconds() / 60)
            
            c.execute("INSERT INTO diario VALUES (?,?,?,?,?,?,?,?,?,?)", 
                      (data_corrente.strftime("%Y-%m-%d"), t_pasto.strftime("%H:%M"), 
                       t_glicemia.strftime("%H:%M"), delta_m, val_glicemia, nome_cibo, 
                       val_grammi, round(c_effettivi, 1), dati['ig'], round(cg_effettivo, 1)))
            conn.commit()
            st.success(f"Registrato! CG: {round(cg_effettivo, 1)}")
            st.rerun()

with tab_view:
    df_raw = pd.read_sql_query("SELECT * FROM diario ORDER BY data DESC, ora_glicemia DESC", conn)
    
    if not df_raw.empty:
        # Mini statistiche
        avg_glic = df_raw['glicemia'].mean()
        st.write(f"📊 Glicemia Media: **{avg_glic:.0f} mg/dL**")
        
        # Griglia con colori
        def color_glic(val):
            color = 'red' if val > user[2] else 'green' if val >= user[1] else 'orange'
            return f'color: {color}; font-weight: bold'

        st.dataframe(df_raw.style.applymap(color_glic, subset=['glicemia']), use_container_width=True)
        
        # Download
        st.download_button("📥 Scarica in Excel/CSV", df_raw.to_csv(index=False), "diario_glicemia.csv")
        
        if st.button("🗑️ Svuota Tutto"):
            c.execute("DELETE FROM diario")
            conn.commit()
            st.rerun()
    else:
        st.info("Il diario è vuoto.")
