import streamlit as st
import pandas as pd
import sqlite3
import os
from datetime import datetime, timedelta

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="Glicemia Pro Italia v7", layout="wide", page_icon="🩸")

# --- DATABASE PERSONALE (Nuova versione per evitare dati corrotti) ---
DB_FILE = 'diario_glicemico_v7.db'

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
        # Leggiamo forzando i tipi di dato per evitare errori
        df = pd.read_csv("database_cibi.csv", dtype={'ig': int, 'carbo': float, 'kcal': float})
        return df.sort_values(by="cibo")
    return pd.DataFrame(columns=["cibo", "kcal", "carbo", "ig"])

food_db = load_data()

# --- LOGIN UTENTE ---
c.execute("SELECT * FROM utenti LIMIT 1")
user = c.fetchone()

if not user:
    st.title("🩸 Benvenuto")
    with st.form("set_user"):
        n = st.text_input("Inserisci il tuo nome")
        if st.form_submit_button("Configura App"):
            c.execute("INSERT INTO utenti VALUES (?,?,?)", (n, 70, 140))
            conn.commit()
            st.rerun()
    st.stop()

# --- INTERFACCIA ---
st.title(f"🩸 Diario di {user[0]}")
t1, t2 = st.tabs(["➕ Nuova Registrazione", "📊 Storico e Griglia"])

with t1:
    # Ricerca alimento nel CSV
    cibo_scelto = st.selectbox("Cerca alimento:", [""] + food_db['cibo'].tolist())
    
    dati_cibo = {"kcal": 0, "carbo": 0, "ig": 0}
    if cibo_scelto:
        row = food_db[food_db['cibo'] == cibo_scelto].iloc[0]
        # Forziamo la conversione per sicurezza
        dati_cibo = {
            "kcal": float(row['kcal']),
            "carbo": float(row['carbo']),
            "ig": int(row['ig'])
        }
        st.success(f"✅ Selezionato: {cibo_scelto} | IG: {dati_cibo['ig']}")

    with st.form("form_inserimento"):
        c1, c2, c3 = st.columns(3)
        with c1:
            glic = st.number_input("Glicemia (mg/dL)", 20, 500, 100)
            gr = st.number_input("Grammi consumati", 1, 1000, 100)
        with c2:
            ora_p = st.time_input("Ora del Pasto", (datetime.now() - timedelta(minutes=60)).time())
            ora_g = st.time_input("Ora Misurazione", datetime.now().time())
        with c3:
            data_p = st.date_input("Data", datetime.now().date())
            nome_display = st.text_input("Nome nel diario", value=cibo_scelto)

        if st.form_submit_button("💾 Salva nel Diario"):
            # Calcolo Carico Glicemico e Delta
            carb_t = (dati_cibo['carbo'] * gr) / 100
            cg_t = (carb_t * dati_cibo['ig']) / 100
            
            dt_p = datetime.combine(data_p, ora_p)
            dt_g = datetime.combine(data_p, ora_g)
            diff_min = int((dt_g - dt_p).total_seconds() / 60)
            
            # Salvataggio con tipi di dato espliciti
            c.execute("INSERT INTO diario (data, ora_pasto, ora_glicemia, delta, glicemia, cibo, grammi, carbo_tot, ig, cg) VALUES (?,?,?,?,?,?,?,?,?,?)", 
                      (data_p.strftime("%Y-%m-%d"), ora_p.strftime("%H:%M"), 
                       ora_g.strftime("%H:%M"), int(diff_min), int(glic), str(nome_display), 
                       float(gr), float(carb_t), int(dati_cibo['ig']), float(cg_t)))
            conn.commit()
            st.success("Dato registrato correttamente!")
            st.rerun()

with t2:
    df_sql = pd.read_sql_query("SELECT * FROM diario ORDER BY data DESC, ora_glicemia DESC", conn)
    
    if not df_sql.empty:
        # Pulizia forzata per la visualizzazione (rimuove i b'\x00')
        df_sql['ig'] = pd.to_numeric(df_sql['ig'], errors='coerce').fillna(0).astype(int)
        df_sql['cg'] = pd.to_numeric(df_sql['cg'], errors='coerce').fillna(0).round(1)
        
        st.subheader("📋 Registro Pasti")
        st.dataframe(df_sql, use_container_width=True)
        
        # Grafico semplice
        fig = px.scatter(df_sql, x="delta", y="glicemia", color="cg", size="cg",
                         labels={"delta": "Minuti dal pasto", "glicemia": "Glicemia"},
                         title="Andamento Glicemico vs Carico Glicemico")
        st.plotly_chart(fig, use_container_width=True)

        if st.button("🗑️ Cancella tutto il diario"):
            c.execute("DELETE FROM diario")
            conn.commit()
            st.rerun()
