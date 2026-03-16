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

# Creazione tabelle (Se esistono già, le lasciamo stare, ma aggiungiamo le colonne se mancano)
c.execute('''CREATE TABLE IF NOT EXISTS utenti 
             (nome TEXT, peso REAL, altezza REAL, tipo_diabete TEXT, target_min INTEGER, target_max INTEGER)''')
c.execute('''CREATE TABLE IF NOT EXISTS voci_diario 
             (data TEXT, glicemia INTEGER, cibo TEXT, grammi REAL, kcal REAL, carbo REAL, note TEXT)''')

# FIX PER L'ERRORE DI INDICE: Se la tabella utenti è vecchia, la resettiamo
c.execute("PRAGMA table_info(utenti)")
colonne = [info[1] for info in c.fetchall()]
if "target_min" not in colonne:
    c.execute("DROP TABLE utenti")
    c.execute('''CREATE TABLE utenti 
                 (nome TEXT, peso REAL, altezza REAL, tipo_diabete TEXT, target_min INTEGER, target_max INTEGER)''')
conn.commit()

# --- FUNZIONI DI SUPPORTO ---
def get_food_data(nome_cibo):
    url = f"https://it.openfoodfacts.org/cgi/search.pl?search_terms={nome_cibo}&search_simple=1&action=process&json=1"
    try:
        r = requests.get(url, timeout=5).json()
        if r.get('products') and len(r['products']) > 0:
            p = r['products'][0]
            nutr = p.get('nutriments', {})
            return {
                "nome": p.get('product_name', nome_cibo),
                "kcal": nutr.get('energy-kcal_100g', 0),
                "carbo": nutr.get('carbohydrates_100g', 0)
            }
    except: return None
    return None

# --- SIDEBAR: PROFILO UTENTE ---
st.sidebar.title("👤 Profilo Utente")
c.execute("SELECT * FROM utenti LIMIT 1")
user_data = c.fetchone()

# Gestione valori di default per evitare IndexError
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
        st.sidebar.success("Profilo aggiornato! Ricarica la pagina.")
        st.rerun()

# --- CORPO PRINCIPALE ---
st.title("🩸 Glicemia & Nutrizione Smart")

tab1, tab2, tab3 = st.tabs(["➕ Nuovo Inserimento", "📊 Grafici", "📜 Storico Dati"])

with tab1:
    with st.form("entry_form"):
        col1, col2 = st.columns(2)
        with col1:
            glic = st.number_input("Glicemia rilevata (mg/dL)", 20, 500, 100)
            cibo = st.text_input("Cibo consumato")
            grammi = st.number_input("Grammi (g)", 0, 2000, 100)
        with col2:
            data_custom = st.text_input("Ora (HH:MM) - Vuoto per ora attuale", "")
            note = st.text_area("Note")
        
        if st.form_submit_button("Registra nel Diario"):
            ora_ins = datetime.now().strftime("%Y-%m-%d ") + data_custom if data_custom else datetime.now().strftime("%Y-%m-%d %H:%M")
            food_info = get_food_data(cibo) if cibo else None
            
            nome_f = food_info['nome'] if food_info else (cibo if cibo else "Nessun pasto")
            k_tot = (food_info['kcal'] * grammi / 100) if food_info else 0.0
            c_tot = (food_info['carbo'] * grammi / 100) if food_info else 0.0
            
            c.execute("INSERT INTO voci_diario VALUES (?,?,?,?,?,?,?)", (ora_ins, glic, nome_f, grammi, k_tot, c_tot, note))
            conn.commit()
            st.success("Dati salvati!")

with tab2:
    df = pd.read_sql_query("SELECT * FROM voci_diario ORDER BY data ASC", conn)
    if not df.empty:
        fig = px.line(df, x="data", y="glicemia", title="Andamento Glicemico", markers=True)
        fig.add_hline(y=d_max, line_dash="dash", line_color="red")
        fig.add_hline(y=d_min, line_dash="dash", line_color="green")
        st.plotly_chart(fig, use_container_width=True)
        
        c1, c2 = st.columns(2)
        oggi = datetime.now().strftime("%Y-%m-%d")
        df_oggi = df[df['data'].str.contains(oggi)]
        c1.metric("Calorie Oggi", f"{df_oggi['kcal'].sum():.0f} kcal")
        c2.metric("Carbo Oggi", f"{df_oggi['carbo'].sum():.1f} g")
    else:
        st.info("Nessun dato presente.")

with tab3:
    df_view = pd.read_sql_query("SELECT * FROM voci_diario ORDER BY data DESC", conn)
    st.dataframe(df_view, use_container_width=True)
    if st.button("Svuota Diario"):
        c.execute("DELETE FROM voci_diario")
        conn.commit()
        st.rerun()
