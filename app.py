import streamlit as st
import pandas as pd
import sqlite3
import os
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="Glicemia & Nutrizione Pro", layout="wide", page_icon="🥗")

# --- DB V9 (Nuova struttura per doppia glicemia e macro) ---
DB_FILE = 'diario_v9.db'
conn = sqlite3.connect(DB_FILE, check_same_thread=False)
c = conn.cursor()
c.execute('CREATE TABLE IF NOT EXISTS utenti (nome TEXT, t_min INTEGER, t_max INTEGER)')
c.execute('''CREATE TABLE IF NOT EXISTS diario 
             (data TEXT, ora_pasto TEXT, ora_glic_post TEXT, 
              glic_pre INTEGER, glic_post INTEGER, delta INTEGER,
              cibo TEXT, grammi REAL, kcal REAL, carbo REAL, prot REAL, grassi REAL, ig INTEGER, cg REAL)''')
conn.commit()

# --- CARICAMENTO DATI ---
@st.cache_data
def load_food_db():
    if os.path.exists("database_cibi.csv"):
        return pd.read_csv("database_cibi.csv")
    return pd.DataFrame(columns=["cibo","kcal","carbo","proteine","grassi","ig"])

food_db = load_food_db()

# --- LOGIN ---
c.execute("SELECT * FROM utenti LIMIT 1")
user = c.fetchone()
if not user:
    st.title("🥗 Benvenuto")
    with st.form("set_u"):
        n = st.text_input("Nome")
        if st.form_submit_button("Inizia"):
            c.execute("INSERT INTO utenti VALUES (?,?,?)", (n, 70, 140))
            conn.commit()
            st.rerun()
    st.stop()

# --- INTERFACCIA ---
st.title(f"📊 Diario di {user[0]}")
t1, t2 = st.tabs(["📝 Inserimento Pasto", "📈 Analisi Avanzata"])

with t1:
    # Selezione cibo
    cerca = st.selectbox("Cerca alimento:", [""] + food_db['cibo'].tolist())
    
    f_data = {"kcal":0, "carbo":0, "prot":0, "grassi":0, "ig":0}
    if cerca:
        m = food_db[food_db['cibo'] == cerca].iloc[0]
        f_data = {"kcal":float(m['kcal']), "carbo":float(m['carbo']), 
                  "prot":float(m['proteine']), "grassi":float(m['grassi']), "ig":int(m['ig'])}

    with st.form("form_pasto"):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("### 💉 Glicemia")
            g_pre = st.number_input("Prima del pasto (mg/dL)", 20, 500, 100)
            g_post = st.number_input("Dopo il pasto (mg/dL)", 20, 500, 140)
            gr = st.number_input("Grammi (g)", 1, 1000, 100)
            
        with col2:
            st.markdown("### 🕒 Orari")
            o_pasto = st.time_input("Ora Inizio Pasto", (datetime.now() - timedelta(minutes=90)).time())
            o_glic = st.time_input("Ora Misurazione Post", datetime.now().time())
            data_p = st.date_input("Data", datetime.now().date())

        with col3:
            st.markdown("### ⚖️ Calcolo Real-Time")
            kcal_live = (f_data['kcal'] * gr) / 100
            carbo_live = (f_data['carbo'] * gr) / 100
            st.metric("Calorie Totali", f"{kcal_live:.1f} kcal")
            st.metric("Carboidrati", f"{carbo_live:.1f} g")
            nome_display = st.text_input("Nome Alimento", value=cerca)

        if st.form_submit_button("✅ Salva Pasto"):
            # Calcoli finali
            p_t = (f_data['prot'] * gr) / 100
            g_t = (f_data['grassi'] * gr) / 100
            cg_t = (carbo_live * f_data['ig']) / 100
            dt_p = datetime.combine(data_p, o_pasto)
            dt_g = datetime.combine(data_p, o_glic)
            diff = int((dt_g - dt_p).total_seconds() / 60)
            
            c.execute("INSERT INTO diario VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", 
                      (data_p.strftime("%Y-%m-%d"), o_pasto.strftime("%H:%M"), o_glic.strftime("%H:%M"),
                       g_pre, g_post, diff, nome_display, gr, kcal_live, carbo_live, p_t, g_t, f_data['ig'], cg_t))
            conn.commit()
            st.success("Pasto registrato!")
            st.rerun()

with t2:
    df = pd.read_sql_query("SELECT * FROM diario ORDER BY data DESC, ora_glic_post DESC", conn)
    
    if not df.empty:
        # --- GRAFICO MACRONUTRIENTI (GIORNATA ODIERNA) ---
        st.subheader("🥧 Bilancio Macronutrienti Odierno")
        oggi = datetime.now().strftime("%Y-%m-%d")
        df_oggi = df[df['data'] == oggi]
        
        if not df_oggi.empty:
            tot_carbo = df_oggi['carbo'].sum()
            tot_prot = df_oggi['prot'].sum()
            tot_grassi = df_oggi['grassi'].sum()
            
            fig_macro = px.pie(names=['Carboidrati', 'Proteine', 'Grassi'], 
                              values=[tot_carbo, tot_prot, tot_grassi],
                              color_discrete_sequence=px.colors.qualitative.Pastel)
            st.plotly_chart(fig_macro, use_container_width=True)
        
        # --- GRIGLIA STORICA ---
        st.subheader("📋 Registro Completo")
        # Calcolo differenza glicemica (Delta Glicemia)
        df['Variazione'] = df['glic_post'] - df['glic_pre']
        st.dataframe(df, use_container_width=True)
        
        # --- GRAFICO ANDAMENTO ---
        st.subheader("📈 Impatto dei Pasti sulla Glicemia")
        fig_evol = go.Figure()
        fig_evol.add_trace(go.Scatter(x=df['ora_pasto'], y=df['glic_pre'], name="Glicemia Pre", mode="markers+lines"))
        fig_evol.add_trace(go.Scatter(x=df['ora_glic_post'], y=df['glic_post'], name="Glicemia Post", mode="markers+lines"))
        st.plotly_chart(fig_evol, use_container_width=True)

        if st.button("🗑️ Svuota tutto"):
            c.execute("DELETE FROM diario"); conn.commit(); st.rerun()
    else:
        st.info("Nessun dato inserito.")
