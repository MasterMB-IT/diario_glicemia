import streamlit as st
import pandas as pd
import plotly.express as px
import sqlite3
import os
from datetime import datetime

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="Glicemia Pro Local", layout="wide", page_icon="🩸")

# --- CARICAMENTO DATABASE CIBI (Dal tuo file nella repository) ---
@st.cache_data
def carica_database_cibi():
    file_path = "database_cibi.csv"
    if os.path.exists(file_path):
        # Carica il CSV e pulisce i nomi per la ricerca
        df_cibi = pd.read_csv(file_path)
        df_cibi['cibo_lower'] = df_cibi['cibo'].str.lower().str.strip()
        return df_cibi
    return pd.DataFrame(columns=["cibo", "kcal", "carbo", "cibo_lower"])

db_cibi = carica_database_cibi()

# --- DATABASE SQLITE (Per i tuoi dati personali) ---
conn = sqlite3.connect('diario_v_locale.db', check_same_thread=False)
c = conn.cursor()
c.execute('CREATE TABLE IF NOT EXISTS utenti (nome TEXT, t_min INTEGER, t_max INTEGER)')
c.execute('CREATE TABLE IF NOT EXISTS diario (data TEXT, glicemia INTEGER, cibo TEXT, grammi REAL, kcal REAL, carbo REAL)')
conn.commit()

# --- LOGICA UTENTE ---
c.execute("SELECT * FROM utenti LIMIT 1")
user = c.fetchone()
if not user:
    st.title("Benvenuto!")
    nome = st.text_input("Il tuo nome")
    if st.button("Configura"):
        c.execute("INSERT INTO utenti VALUES (?,?,?)", (nome, 70, 140))
        conn.commit()
        st.rerun()
    st.stop()

# --- INTERFACCIA ---
st.title(f"🩸 Diario di {user[0]}")
t1, t2 = st.tabs(["➕ Registra", "📊 Analisi"])

with t1:
    st.subheader("Cerca nel tuo database locale")
    
    # Ricerca con suggerimenti dal file CSV
    opzioni = db_cibi['cibo'].tolist()
    scelta = st.selectbox("Seleziona alimento (o scrivi per filtrare)", [""] + opzioni)
    
    dati_cibo = {"kcal": 0, "carbo": 0}
    if scelta:
        match = db_cibi[db_cibi['cibo'] == scelta].iloc[0]
        dati_cibo = {"kcal": match['kcal'], "carbo": match['carbo']}
        st.info(f"💡 Dati caricati: {match['kcal']} kcal e {match['carbo']}g carbo per 100g")

    with st.form("invio_pasto"):
        col1, col2 = st.columns(2)
        glic = col1.number_input("Glicemia (mg/dL)", 20, 500, 100)
        gr = col1.number_input("Grammi (g)", 1, 1000, 100)
        # Se non ha scelto nulla dal menu, può scrivere a mano
        nome_final = col2.text_input("Conferma Alimento", value=scelta)
        ora = col2.time_input("Ora", datetime.now().time())
        
        if st.form_submit_button("💾 Salva nel Diario"):
            kcal_t = (dati_cibo['kcal'] * gr) / 100
            carb_t = (dati_cibo['carbo'] * gr) / 100
            dt = datetime.now().strftime("%Y-%m-%d ") + ora.strftime("%H:%M")
            
            c.execute("INSERT INTO diario VALUES (?,?,?,?,?,?)", (dt, glic, nome_final, gr, kcal_t, carb_t))
            conn.commit()
            st.success("Registrato!")
            st.rerun()

with t2:
    df = pd.read_sql_query("SELECT * FROM diario ORDER BY data ASC", conn)
    if not df.empty:
        fig = px.line(df, x="data", y="glicemia", markers=True)
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(df.sort_values("data", ascending=False), use_container_width=True)
