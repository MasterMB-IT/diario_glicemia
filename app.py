import streamlit as st
import pandas as pd
import sqlite3
import os
import plotly.express as px  # Risolve il NameError
from datetime import datetime, timedelta

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="Glicemia Pro Definitiva", layout="wide", page_icon="🩸")

# --- DATABASE PERSISTENTE V8 ---
DB_FILE = 'diario_v8.db'

def init_db():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS utenti (nome TEXT, t_min INTEGER, t_max INTEGER)')
    c.execute('''CREATE TABLE IF NOT EXISTS diario 
                 (data TEXT, ora_pasto TEXT, ora_glicemia TEXT, delta INTEGER, 
                  glicemia INTEGER, cibo TEXT, grammi REAL, carbo_tot REAL, ig INTEGER, cg REAL)''')
    conn.commit()
    return conn

conn = init_db()
cursor = conn.cursor()

# --- CARICAMENTO ALIMENTI ---
@st.cache_data
def load_food_db():
    if os.path.exists("database_cibi.csv"):
        df = pd.read_csv("database_cibi.csv")
        # Pulizia: togliamo spazi e rendiamo tutto minuscolo per la ricerca
        df.columns = df.columns.str.strip()
        return df
    return pd.DataFrame(columns=["cibo", "kcal", "carbo", "ig"])

food_db = load_food_db()

# --- GESTIONE UTENTE ---
cursor.execute("SELECT * FROM utenti LIMIT 1")
user_data = cursor.fetchone()

if not user_data:
    st.title("🩸 Benvenuto! Configurazione rapida")
    with st.form("setup"):
        nome = st.text_input("Inserisci il tuo nome")
        if st.form_submit_button("Salva e Inizia"):
            cursor.execute("INSERT INTO utenti VALUES (?,?,?)", (nome, 70, 140))
            conn.commit()
            st.rerun()
    st.stop()

# --- APP PRINCIPALE ---
st.title(f"🩸 Diario di {user_data[0]}")
t1, t2 = st.tabs(["➕ Registra", "📊 Storico"])

with t1:
    # Ricerca che non guarda maiuscole/minuscole
    cerca = st.selectbox("Seleziona Alimento:", [""] + food_db['cibo'].tolist())
    
    dati_cibo = {"kcal": 0, "carbo": 0, "ig": 0}
    if cerca:
        # Trova l'alimento esatto
        match = food_db[food_db['cibo'] == cerca].iloc[0]
        dati_cibo = {"kcal": float(match['kcal']), "carbo": float(match['carbo']), "ig": int(match['ig'])}
        st.success(f"📌 Selezionato: {cerca} (IG: {dati_cibo['ig']})")

    with st.form("inserimento"):
        c1, c2, c3 = st.columns(3)
        glic_val = c1.number_input("Glicemia (mg/dL)", 20, 500, 110)
        gr_val = c1.number_input("Grammi (g)", 1, 1000, 100)
        
        o_pasto = c2.time_input("Ora Pasto", (datetime.now() - timedelta(minutes=60)).time())
        o_glic = c2.time_input("Ora Misurazione", datetime.now().time())
        
        data_p = c3.date_input("Data", datetime.now().date())
        nome_f = c3.text_input("Alimento nel diario", value=cerca)

        if st.form_submit_button("💾 Salva nel Diario"):
            # Calcoli di sicurezza
            c_t = (dati_cibo['carbo'] * gr_val) / 100
            cg_t = (c_t * dati_cibo['ig']) / 100
            dt_p = datetime.combine(data_p, o_pasto)
            dt_g = datetime.combine(data_p, o_glic)
            diff = int((dt_g - dt_p).total_seconds() / 60)
            
            cursor.execute("INSERT INTO diario VALUES (?,?,?,?,?,?,?,?,?,?)", 
                          (data_p.strftime("%Y-%m-%d"), o_pasto.strftime("%H:%M"), 
                           o_glic.strftime("%H:%M"), diff, glic_val, nome_f, 
                           gr_val, c_t, dati_cibo['ig'], cg_t))
            conn.commit()
            st.success("Salvato!")
            st.rerun()

with t2:
    df_sql = pd.read_sql_query("SELECT * FROM diario ORDER BY data DESC, ora_glicemia DESC", conn)
    
    if not df_sql.empty:
        st.subheader("📋 Registro Pasti")
        # Visualizzazione pulita senza caratteri strani
        st.dataframe(df_sql, use_container_width=True)
        
        st.divider()
        st.subheader("📈 Analisi Grafica")
        fig = px.scatter(df_sql, x="delta", y="glicemia", color="cg", size="carbo_tot",
                         hover_name="cibo", title="Tempo vs Glicemia (Colore = Carico Glicemico)")
        st.plotly_chart(fig, use_container_width=True)
        
        if st.button("🗑️ Cancella tutto"):
            cursor.execute("DELETE FROM diario")
            conn.commit()
            st.rerun()
    else:
        st.info("Ancora nessun dato nel diario.")
