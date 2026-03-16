import streamlit as st
import pandas as pd
import sqlite3
import os
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Glicemia Pro Multi-User v11", layout="wide", page_icon="🩸")

# --- GESTIONE DATABASE SQLITE ---
DB_FILE = 'diario_v11.db'

def init_db():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    c = conn.cursor()
    # Tabella Diario: aggiunta colonna utente_id e macronutrienti
    c.execute('''CREATE TABLE IF NOT EXISTS diario 
                 (utente_id TEXT, data TEXT, ora_pasto TEXT, ora_glic_post TEXT, 
                  glic_pre INTEGER, glic_post INTEGER, delta INTEGER,
                  cibo TEXT, grammi REAL, kcal REAL, carbo REAL, prot REAL, grassi REAL, ig INTEGER, cg REAL)''')
    # Tabella Utenti Autorizzati
    c.execute('CREATE TABLE IF NOT EXISTS utenti_autorizzati (username TEXT PRIMARY KEY)')
    conn.commit()
    return conn

conn = init_db()
cursor = conn.cursor()

# --- LOGICA DI ACCESSO (LOGIN) ---
if 'utente' not in st.session_state:
    st.session_state['utente'] = None

if st.session_state['utente'] is None:
    st.title("🔐 Accesso al Diario Glicemico")
    st.info("Inserisci il tuo username per caricare i tuoi dati personali.")
    
    user_input = st.text_input("Username:").strip().lower()
    
    col_login, col_reg = st.columns(2)
    
    with col_login:
        if st.button("Accedi"):
            cursor.execute("SELECT username FROM utenti_autorizzati WHERE username = ?", (user_input,))
            if cursor.fetchone():
                st.session_state['utente'] = user_input
                st.rerun()
            else:
                st.error("❌ Username non autorizzato.")
                
    with col_reg:
        with st.expander("Registra nuovo profilo (Admin)"):
            nuovo_u = st.text_input("Nuovo Username:").strip().lower()
            admin_p = st.text_input("Password Admin:", type="password")
            if st.button("Autorizza"):
                if admin_p == "Mirkof87": # <--- CAMBIA QUESTA PASSWORD
                    try:
                        cursor.execute("INSERT INTO utenti_autorizzati VALUES (?)", (nuovo_u,))
                        conn.commit()
                        st.success(f"Utente {nuovo_u} creato!")
                    except:
                        st.warning("Esiste già.")
                else:
                    st.error("Password errata.")
    st.stop()

ID_UTENTE = st.session_state['utente']

# --- CARICAMENTO DATABASE ALIMENTI (CSV) ---
@st.cache_data
def load_food():
    if os.path.exists("database_cibi.csv"):
        df = pd.read_csv("database_cibi.csv")
        # Pulizia nomi colonne e dati
        df.columns = df.columns.str.strip()
        return df
    return pd.DataFrame(columns=["cibo","kcal","carbo","proteine","grassi","ig"])

food_db = load_food()

# --- INTERFACCIA PRINCIPALE ---
with st.sidebar:
    st.title(f"👤 {ID_UTENTE.upper()}")
    if st.button("Log-out"):
        st.session_state['utente'] = None
        st.rerun()
    st.divider()
    st.write("App v11.0 - MultiUser & Macro")

st.title("🩸 Monitoraggio Glicemia e Nutrizione")

t1, t2 = st.tabs(["➕ Nuovo Inserimento", "📊 Analisi e Storico"])

with t1:
    # Selezione Alimento
    cerca = st.selectbox("Seleziona alimento dal database:", [""] + food_db['cibo'].tolist())
    
    # Dati default se non selezionato
    f = {"kcal":0, "carbo":0, "prot":0, "grassi":0, "ig":0}
    if cerca:
        row = food_db[food_db['cibo'] == cerca].iloc[0]
        f = {"kcal":float(row['kcal']), "carbo":float(row['carbo']), 
             "prot":float(row['proteine']), "grassi":float(row['grassi']), "ig":int(row['ig'])}

    with st.form("pasto_form"):
        c1, c2, c3 = st.columns(3)
        
        with c1:
            st.subheader("💉 Glicemia")
            g_pre = st.number_input("Pre-Pasto (mg/dL)", 20, 500, 100)
            g_post = st.number_input("Post-Pasto (mg/dL)", 20, 500, 140)
            grammi = st.number_input("Quantità (g)", 1, 1000, 100)
            
        with c2:
            st.subheader("🕒 Orari")
            o_pasto = st.time_input("Inizio Pasto", (datetime.now() - timedelta(minutes=90)).time())
            o_glic = st.time_input("Misurazione Post", datetime.now().time())
            data_p = st.date_input("Data", datetime.now().date())
            
        with c3:
            st.subheader("⚖️ Calcolo Real-Time")
            kcal_t = (f['kcal'] * grammi) / 100
            carb_t = (f['carbo'] * grammi) / 100
            st.metric("Calorie Pasto", f"{kcal_t:.1f} kcal")
            st.metric("Carboidrati", f"{carb_t:.1f} g")
            nome_diario = st.text_input("Conferma nome cibo", value=cerca)

        if st.form_submit_button("💾 SALVA NEL DIARIO"):
            # Calcoli finali
            prot_t = (f['prot'] * grammi) / 100
            gras_t = (f['grassi'] * grammi) / 100
            cg_t = (carb_t * f['ig']) / 100
            diff = int((datetime.combine(data_p, o_glic) - datetime.combine(data_p, o_pasto)).total_seconds() / 60)
            
            cursor.execute("INSERT INTO diario VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", 
                          (ID_UTENTE, data_p.strftime("%Y-%m-%d"), o_pasto.strftime("%H:%M"), o_glic.strftime("%H:%M"),
                           g_pre, g_post, diff, nome_diario, grammi, kcal_t, carb_t, prot_t, gras_t, f['ig'], cg_t))
            conn.commit()
            st.success("Dati salvati correttamente!")
            st.rerun()

with t2:
    # Query filtrata per utente
    df = pd.read_sql_query("SELECT * FROM diario WHERE utente_id = ? ORDER BY data DESC, ora_glic_post DESC", conn, params=(ID_UTENTE,))
    
    if not df.empty:
        # Colonna Variazione
        df['Variazione'] = df['glic_post'] - df['glic_pre']
        
        # Grafico Macro Odierno
        st.subheader("🥧 Macronutrienti di Oggi")
        oggi = datetime.now().strftime("%Y-%m-%d")
        df_oggi = df[df['data'] == oggi]
        
        if not df_oggi.empty:
            c_m1, c_m2 = st.columns([1, 2])
            with c_m1:
                fig_pie = px.pie(names=['Carboidrati', 'Proteine', 'Grassi'], 
                                values=[df_oggi['carbo'].sum(), df_oggi['prot'].sum(), df_oggi['grassi'].sum()],
                                hole=0.4, color_discrete_sequence=px.colors.qualitative.Set3)
                st.plotly_chart(fig_pie, use_container_width=True)
            with c_m2:
                st.write(f"**Calorie totali oggi:** {df_oggi['kcal'].sum():.0f} kcal")
                st.write(f"**Carboidrati totali:** {df_oggi['carbo'].sum():.1f} g")
        
        st.divider()
        st.subheader("📋 Registro Storico")
        st.dataframe(df.drop(columns=['utente_id']), use_container_width=True)
        
        # Grafico a dispersione
        st.subheader("📈 Impatto Glicemico (Delta Tempo)")
        fig_scat = px.scatter(df, x="delta", y="glic_post", size="cg", color="Variazione",
                             hover_name="cibo", labels={"delta":"Minuti dal pasto", "glic_post":"Glicemia rilevata"})
        st.plotly_chart(fig_scat, use_container_width=True)

        if st.button("🗑️ Svuota il mio registro"):
            cursor.execute("DELETE FROM diario WHERE utente_id = ?", (ID_UTENTE,))
            conn.commit()
            st.rerun()
    else:
        st.info("Nessun dato presente. Inizia a registrare i tuoi pasti!")
