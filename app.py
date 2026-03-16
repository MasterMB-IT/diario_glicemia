import streamlit as st
import pandas as pd
import plotly.express as px
import sqlite3
import os
from datetime import datetime

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="Glicemia Pro Post-Prandiale", layout="wide", page_icon="🩸")

# --- CARICAMENTO DATABASE CIBI ---
@st.cache_data
def carica_database_cibi():
    file_path = "database_cibi.csv"
    if os.path.exists(file_path):
        df = pd.read_csv(file_path)
        return df.sort_values(by="cibo")
    return pd.DataFrame(columns=["cibo", "kcal", "carbo"])

db_cibi = carica_database_cibi()

# --- DATABASE SQLITE (Versione con Orari Separati) ---
conn = sqlite3.connect('diario_v_orari.db', check_same_thread=False)
c = conn.cursor()
c.execute('CREATE TABLE IF NOT EXISTS utenti (nome TEXT, t_min INTEGER, t_max INTEGER)')
c.execute('''CREATE TABLE IF NOT EXISTS diario 
             (data TEXT, ora_pasto TEXT, ora_glicemia TEXT, diff_minuti INTEGER, 
              glicemia INTEGER, cibo TEXT, grammi REAL, kcal REAL, carbo REAL)''')
conn.commit()

# Controllo Utente
c.execute("SELECT * FROM utenti LIMIT 1")
user = c.fetchone()
if not user:
    st.title("🩸 Configurazione Iniziale")
    nome = st.text_input("Il tuo nome")
    if st.button("Salva"):
        c.execute("INSERT INTO utenti VALUES (?,?,?)", (nome, 70, 140))
        conn.commit()
        st.rerun()
    st.stop()

# --- INTERFACCIA ---
st.title(f"🩸 Diario di {user[0]}")
t1, t2 = st.tabs(["➕ Nuova Misurazione", "📊 Analisi e Storico"])

with t1:
    st.subheader("1. Seleziona Alimento")
    search_query = st.selectbox(
        "Cerca nel database locale:", 
        options=[""] + db_cibi['cibo'].tolist()
    )
    
    dati_f = {"kcal": 0, "carbo": 0}
    if search_query:
        match = db_cibi[db_cibi['cibo'] == search_query].iloc[0]
        dati_f = {"kcal": match['kcal'], "carbo": match['carbo']}
        st.info(f"💡 {search_query}: {match['kcal']} kcal | {match['carbo']}g carbo per 100g")

    st.divider()
    st.subheader("2. Dettagli Misurazione")
    
    with st.form("form_avanzato"):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            glic = st.number_input("Glicemia (mg/dL)", 20, 500, 100)
            grammi = st.number_input("Grammi cibo (g)", 1, 1000, 100)
        
        with col2:
            # Qui separiamo i due orari
            ora_pasto = st.time_input("Ora del Pasto", datetime.now().time())
            ora_glicemia = st.time_input("Ora della Glicemia", datetime.now().time())
        
        with col3:
            nome_c = st.text_input("Nome Alimento", value=search_query)
            data_evento = st.date_input("Data", datetime.now().date())

        if st.form_submit_button("💾 Salva nel Diario"):
            # Calcolo della differenza di tempo
            dt_pasto = datetime.combine(data_evento, ora_pasto)
            dt_glicemia = datetime.combine(data_evento, ora_glicemia)
            diff = dt_glicemia - dt_pasto
            diff_minuti = int(diff.total_seconds() / 60)
            
            # Calcolo Nutrienti
            k_tot = (dati_f['kcal'] * grammi) / 100
            c_tot = (dati_f['carbo'] * grammi) / 100
            
            c.execute('''INSERT INTO diario VALUES (?,?,?,?,?,?,?,?,?)''', 
                      (data_evento.strftime("%Y-%m-%d"), 
                       ora_pasto.strftime("%H:%M"), 
                       ora_glicemia.strftime("%H:%M"), 
                       diff_minuti, glic, nome_c, grammi, k_tot, c_tot))
            conn.commit()
            st.success(f"Registrato! Differenza: {diff_minuti} minuti dal pasto.")
            st.rerun()

with t2:
    df = pd.read_sql_query("SELECT * FROM diario ORDER BY data DESC, ora_glicemia DESC", conn)
    
    if not df.empty:
        # Funzione per colorare la differenza di tempo
        def format_diff(val):
            return f"{val} min"

        st.subheader("📜 Griglia Storica")
        
        # Rinominiamo le colonne per renderle più leggibili in tabella
        df_view = df.rename(columns={
            'ora_pasto': '🕒 Ora Pasto',
            'ora_glicemia': '💉 Ora Glicemia',
            'diff_minuti': '⏱️ Delta (min)',
            'glicemia': '🩸 Glicemia',
            'cibo': '🍕 Alimento',
            'carbo': '🍞 Carbo (g)'
        })
        
        st.dataframe(df_view, use_container_width=True)

        st.divider()
        st.subheader("📈 Analisi Post-Prandiale")
        st.write("Questo grafico mostra come varia la glicemia in base ai minuti passati dal pasto.")
        
        # Grafico a dispersione: Minuti dal pasto vs Glicemia
        fig = px.scatter(df, x="diff_minuti", y="glicemia", 
                         color="glicemia", size="carbo",
                         hover_name="cibo", 
                         labels={"diff_minuti": "Minuti dopo il pasto", "glicemia": "Valore Glicemico"},
                         title="Impatto dei Carboidrati nel tempo")
        fig.add_hline(y=user[2], line_dash="dash", line_color="red")
        st.plotly_chart(fig, use_container_width=True)

        if st.button("Svuota Diario"):
            c.execute("DELETE FROM diario")
            conn.commit()
            st.rerun()
    else:
        st.info("Nessun dato disponibile.")
