import streamlit as st
import pandas as pd
import sqlite3
import os
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="Glicemia Multi-User", layout="wide", page_icon="👥")

# --- DATABASE (V10 - Supporto Multi-utente) ---
DB_FILE = 'diario_v10.db'
conn = sqlite3.connect(DB_FILE, check_same_thread=False)
c = conn.cursor()
# Aggiungiamo la colonna 'utente_id' a tutte le tabelle
c.execute('''CREATE TABLE IF NOT EXISTS diario 
             (utente_id TEXT, data TEXT, ora_pasto TEXT, ora_glic_post TEXT, 
              glic_pre INTEGER, glic_post INTEGER, delta INTEGER,
              cibo TEXT, grammi REAL, kcal REAL, carbo REAL, prot REAL, grassi REAL, ig INTEGER, cg REAL)''')
conn.commit()

# --- LOGIN SEMPLIFICATO ---
if 'utente' not in st.session_state:
    st.session_state['utente'] = None

if st.session_state['utente'] is None:
    st.title("🔐 Accesso Personale")
    user_input = st.text_input("Inserisci il tuo nome o un codice (es: Marco82):", placeholder="Questo separerà i tuoi dati dagli altri")
    if st.button("Entra nel mio Diario"):
        if user_input:
            st.session_state['utente'] = user_input.strip().lower()
            st.rerun()
        else:
            st.warning("Inserisci un nome per continuare.")
    st.stop()

# Se arriviamo qui, l'utente è loggato nella sessione
ID_UTENTE = st.session_state['utente']

# --- LOGOUT ---
with st.sidebar:
    st.write(f"👤 Utente: **{ID_UTENTE.capitalize()}**")
    if st.button("Cambia Utente / Esci"):
        st.session_state['utente'] = None
        st.rerun()

# --- CARICAMENTO ALIMENTI ---
@st.cache_data
def load_food_db():
    if os.path.exists("database_cibi.csv"):
        return pd.read_csv("database_cibi.csv")
    return pd.DataFrame(columns=["cibo","kcal","carbo","proteine","grassi","ig"])

food_db = load_food_db()

# --- APP PRINCIPALE ---
st.title(f"📊 Diario Glicemico di {ID_UTENTE.capitalize()}")
t1, t2 = st.tabs(["📝 Inserimento Pasto", "📈 Analisi Avanzata"])

with t1:
    cerca = st.selectbox("Cerca alimento:", [""] + food_db['cibo'].tolist())
    
    f_data = {"kcal":0, "carbo":0, "prot":0, "grassi":0, "ig":0}
    if cerca:
        m = food_db[food_db['cibo'] == cerca].iloc[0]
        f_data = {"kcal":float(m['kcal']), "carbo":float(m['carbo']), 
                  "prot":float(m['proteine']), "grassi":float(m['grassi']), "ig":int(m['ig'])}

    with st.form("form_pasto"):
        col1, col2, col3 = st.columns(3)
        with col1:
            g_pre = st.number_input("Prima del pasto (mg/dL)", 20, 500, 100)
            g_post = st.number_input("Dopo il pasto (mg/dL)", 20, 500, 140)
            gr = st.number_input("Grammi (g)", 1, 1000, 100)
        with col2:
            o_pasto = st.time_input("Ora Inizio Pasto", (datetime.now() - timedelta(minutes=90)).time())
            o_glic = st.time_input("Ora Misurazione Post", datetime.now().time())
            data_p = st.date_input("Data", datetime.now().date())
        with col3:
            kcal_live = (f_data['kcal'] * gr) / 100
            carbo_live = (f_data['carbo'] * gr) / 100
            st.metric("Calorie Totali", f"{kcal_live:.1f} kcal")
            nome_display = st.text_input("Nome Alimento", value=cerca)

        if st.form_submit_button("✅ Salva nel MIO Diario"):
            p_t = (f_data['prot'] * gr) / 100
            g_t = (f_data['grassi'] * gr) / 100
            cg_t = (carbo_live * f_data['ig']) / 100
            diff = int((datetime.combine(data_p, o_glic) - datetime.combine(data_p, o_pasto)).total_seconds() / 60)
            
            # Salviamo con l'ID_UTENTE
            c.execute("INSERT INTO diario VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", 
                      (ID_UTENTE, data_p.strftime("%Y-%m-%d"), o_pasto.strftime("%H:%M"), o_glic.strftime("%H:%M"),
                       g_pre, g_post, diff, nome_display, gr, kcal_live, carbo_live, p_t, g_t, f_data['ig'], cg_t))
            conn.commit()
            st.success(f"Pasto salvato per {ID_UTENTE}!")
            st.rerun()

with t2:
    # FILTRIAMO LA QUERY PER L'UTENTE CORRENTE
    df = pd.read_sql_query("SELECT * FROM diario WHERE utente_id = ? ORDER BY data DESC, ora_glic_post DESC", conn, params=(ID_UTENTE,))
    
    if not df.empty:
        st.subheader("🥧 I tuoi Macronutrienti di oggi")
        oggi = datetime.now().strftime("%Y-%m-%d")
        df_oggi = df[df['data'] == oggi]
        
        if not df_oggi.empty:
            fig_macro = px.pie(names=['Carboidrati', 'Proteine', 'Grassi'], 
                              values=[df_oggi['carbo'].sum(), df_oggi['prot'].sum(), df_oggi['grassi'].sum()])
            st.plotly_chart(fig_macro, use_container_width=True)
        
        st.subheader("📋 Il tuo registro")
        df['Variazione'] = df['glic_post'] - df['glic_pre']
        st.dataframe(df.drop(columns=['utente_id']), use_container_width=True)
        
        if st.button("🗑️ Cancella solo i miei dati"):
            c.execute("DELETE FROM diario WHERE utente_id = ?", (ID_UTENTE,))
            conn.commit()
            st.rerun()
    else:
        st.info(f"Ciao {ID_UTENTE}, il tuo diario è ancora vuoto.")
