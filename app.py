import streamlit as st
import pandas as pd
import plotly.express as px
import requests
import sqlite3
from datetime import datetime

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Glicemia Pro Cloud", layout="wide", page_icon="🩸")

# --- CONNESSIONE DATABASE (SQLite) ---
conn = sqlite3.connect('diario_glicemia.db', check_same_thread=False)
c = conn.cursor()

# Inizializzazione Tabelle
c.execute('''CREATE TABLE IF NOT EXISTS utenti 
             (nome TEXT, peso REAL, altezza REAL, tipo_diabete TEXT, target_min INTEGER, target_max INTEGER)''')
c.execute('''CREATE TABLE IF NOT EXISTS voci_diario 
             (data TEXT, glicemia INTEGER, cibo TEXT, grammi REAL, kcal REAL, carbo REAL, note TEXT)''')

# Fix Struttura Database (se necessario)
c.execute("PRAGMA table_info(utenti)")
colonne = [info[1] for info in c.fetchall()]
if "target_min" not in colonne:
    c.execute("DROP TABLE utenti")
    c.execute('''CREATE TABLE utenti 
                 (nome TEXT, peso REAL, altezza REAL, tipo_diabete TEXT, target_min INTEGER, target_max INTEGER)''')
conn.commit()

# --- FUNZIONE API FOOD (Migliorata) ---
def get_food_data(nome_cibo):
    # User-Agent necessario per evitare blocchi dalle API di Open Food Facts
    headers = {'User-Agent': 'GlicemiaApp - WebApp - Version 1.1'}
    url = f"https://it.openfoodfacts.org/cgi/search.pl?search_terms={nome_cibo}&search_simple=1&action=process&json=1&page_size=10"
    
    try:
        r = requests.get(url, headers=headers, timeout=10).json()
        if r.get('products'):
            # Cerchiamo il primo prodotto che abbia i dati nutrizionali essenziali
            for p in r['products']:
                nutr = p.get('nutriments', {})
                # Verifichiamo che esistano i carboidrati (essenziali per la glicemia)
                if 'carbohydrates_100g' in nutr:
                    return {
                        "nome": p.get('product_name_it') or p.get('product_name') or nome_cibo,
                        "kcal": nutr.get('energy-kcal_100g', 0),
                        "carbo": nutr.get('carbohydrates_100g', 0)
                    }
    except Exception:
        return None
    return None

# --- SIDEBAR: PROFILO UTENTE ---
st.sidebar.title("👤 Profilo Utente")
c.execute("SELECT * FROM utenti LIMIT 1")
user_data = c.fetchone()

# Valori di default
d_nome = user_data[0] if user_data else "Utente"
d_peso = user_data[1] if user_data else 70.0
d_alt = user_data[2] if user_data else 170.0
d_tipo = user_data[3] if user_data else "Nessuno"
d_min = user_data[4] if user_data else 70
d_max = user_data[5] if user_data else 140

with st.sidebar.form("profilo_form"):
    n = st.text_input("Nome", value=d_nome)
    p = st.number_input("Peso (kg)", value=d_peso)
    a = st.number_input("Altezza (cm)", value=d_alt)
    t = st.selectbox("Tipo Diabete", ["Tipo 1", "Tipo 2", "Gestazionale", "Nessuno"], 
                     index=["Tipo 1", "Tipo 2", "Gestazionale", "Nessuno"].index(d_tipo))
    t_min = st.slider("Target Min (mg/dL)", 60, 100, d_min)
    t_max = st.slider("Target Max (mg/dL)", 120, 200, d_max)
    
    if st.form_submit_button("Salva Impostazioni"):
        c.execute("DELETE FROM utenti")
        c.execute("INSERT INTO utenti VALUES (?,?,?,?,?,?)", (n, p, a, t, t_min, t_max))
        conn.commit()
        st.sidebar.success("Profilo salvato!")
        st.rerun()

# --- CORPO PRINCIPALE ---
st.title("🩸 Glicemia & Nutrizione Smart")

tab1, tab2, tab3 = st.tabs(["➕ Nuovo Inserimento", "📊 Analisi Grafiche", "📜 Diario Storico"])

# --- TAB 1: INSERIMENTO ---
with tab1:
    st.subheader("Registra Valori")
    
    # 1. Ricerca Cibo (FUORI dal form per essere interattiva)
    cibo_query = st.text_input("🔍 Cerca cibo mangiato (es: 'Pane integrale')", help="Premi invio per cercare")
    
    info_temp = None
    if cibo_query:
        with st.spinner('Ricerca dati nutrizionali...'):
            info_temp = get_food_data(cibo_query)
        
        if info_temp:
            st.success(f"✅ Prodotto trovato: **{info_temp['nome']}**")
            st.info(f"Valori per 100g: {info_temp['kcal']} kcal | {info_temp['carbo']}g Carboidrati")
        else:
            st.warning("⚠️ Cibo non trovato nel database. Inserimento manuale attivo.")

    st.divider()

    # 2. Form di Salvataggio
    with st.form("main_entry_form"):
        col_dx, col_sx = st.columns(2)
        
        with col_dx:
            glic_val = st.number_input("Glicemia attuale (mg/dL)", 20, 500, 100)
            grammi_val = st.number_input("Grammi consumati (g)", 1, 2000, 100)
        
        with col_sx:
            # Pre-compila con il nome trovato dall'API o con quello scritto dall'utente
            nome_confermato = st.text_input("Conferma nome alimento", value=info_temp['nome'] if info_temp else cibo_query)
            ora_custom = st.text_input("Ora (HH:MM) - Lascia vuoto per ora attuale", "")
            
        nota_val = st.text_area("Note (es: 30min post-pasto, dopo corsa, ecc.)")
        
        if st.form_submit_button("💾 Salva nel Diario"):
            # Gestione timestamp
            data_str = datetime.now().strftime("%Y-%m-%d ") + ora_custom if ora_custom else datetime.now().strftime("%Y-%m-%d %H:%M")
            
            # Calcolo macronutrienti
            k_100 = info_temp['kcal'] if info_temp else 0
            c_100 = info_temp['carbo'] if info_temp else 0
            
            kcal_tot = (k_100 * grammi_val) / 100
            carbo_tot = (c_100 * grammi_val) / 100
            
            c.execute("INSERT INTO voci_diario VALUES (?,?,?,?,?,?,?)", 
                      (data_str, glic_val, nome_confermato, grammi_val, kcal_tot, carbo_tot, nota_val))
            conn.commit()
            st.balloons()
            st.success(f"Dati registrati correttamente per {nome_confermato}!")

# --- TAB 2: GRAFICI ---
with tab2:
    df = pd.read_sql_query("SELECT * FROM voci_diario ORDER BY data ASC", conn)
    if not df.empty:
        # Grafico Linee
        fig = px.line(df, x="data", y="glicemia", title="Andamento dei livelli di glucosio", markers=True)
        fig.add_hline(y=d_max, line_dash="dash", line_color="red", annotation_text="Target Max")
        fig.add_hline(y=d_min, line_dash="dash", line_color="green", annotation_text="Target Min")
        st.plotly_chart(fig, use_container_width=True)
        
        # Statistiche Oggi
        st.divider()
        c1, c2, c3 = st.columns(3)
        oggi_str = datetime.now().strftime("%Y-%m-%d")
        df_oggi = df[df['data'].str.contains(oggi_str)]
        
        c1.metric("Pasti Registrati oggi", len(df_oggi))
        c2.metric("Calorie Totali", f"{df_oggi['kcal'].sum():.0f} kcal")
        c3.metric("Carboidrati Totali", f"{df_oggi['carbo'].sum():.1f} g")
    else:
        st.info("Aggiungi la tua prima misurazione per vedere le statistiche.")

# --- TAB 3: STORICO ---
with tab3:
    df_history = pd.read_sql_query("SELECT * FROM voci_diario ORDER BY data DESC", conn)
    if not df_history.empty:
        st.dataframe(df_history, use_container_width=True)
        
        # Esportazione CSV (extra "accattivante")
        csv = df_history.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Scarica Diario (CSV)", data=csv, file_name="diario_glicemia.csv", mime="text/csv")
        
        if st.button("🗑️ Cancella tutto lo storico"):
            c.execute("DELETE FROM voci_diario")
            conn.commit()
            st.rerun()
    else:
        st.write("Nessun dato salvato.")
