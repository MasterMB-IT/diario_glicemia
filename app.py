import streamlit as st
import pandas as pd
import plotly.express as px
import requests
import sqlite3
from datetime import datetime

# --- CONFIGURAZIONE DATABASE ---
conn = sqlite3.connect('diario_glicemia.db', check_same_thread=False)
c = conn.cursor()

# Creazione tabelle se non esistono
c.execute('''CREATE TABLE IF NOT EXISTS utenti 
             (nome TEXT, peso REAL, altezza REAL, tipo_diabete TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS voci_diario 
             (data TEXT, glicemia INTEGER, cibo TEXT, grammi REAL, kcal REAL, carbo REAL, note TEXT)''')
conn.commit()

st.set_page_config(page_title="Glicemia Web Tracker", layout="wide")

# --- FUNZIONE API FOOD ---
def get_food_data(nome_cibo):
    url = f"https://it.openfoodfacts.org/cgi/search.pl?search_terms={nome_cibo}&search_simple=1&action=process&json=1"
    try:
        r = requests.get(url, timeout=5).json()
        if r.get('products'):
            p = r['products'][0]
            return {
                "nome": p.get('product_name', 'Sconosciuto'),
                "kcal": p.get('nutriments', {}).get('energy-kcal_100g', 0),
                "carbo": p.get('nutriments', {}).get('carbohydrates_100g', 0)
            }
    except: return None
    return None

# --- SIDEBAR PROFILO ---
st.sidebar.title("👤 Profilo Cloud")
# Carica dati utente esistenti
c.execute("SELECT * FROM utenti LIMIT 1")
user_data = c.fetchone()

with st.sidebar.form("profilo_form"):
    n = st.text_input("Nome", value=user_data[0] if user_data else "")
    p = st.number_input("Peso (kg)", value=user_data[1] if user_data else 70.0)
    a = st.number_input("Altezza (cm)", value=user_data[2] if user_data else 170.0)
    t = st.selectbox("Tipo", ["Tipo 1", "Tipo 2", "Gestazionale", "Nessuno"])
    if st.form_submit_button("Aggiorna Profilo"):
        c.execute("DELETE FROM utenti")
        c.execute("INSERT INTO utenti VALUES (?,?,?,?)", (n, p, a, t))
        conn.commit()
        st.success("Profilo salvato online!")

# --- MAIN APP ---
st.title("🩸 Glicemia & Nutrizione Web")

tab1, tab2 = st.tabs(["➕ Inserimento", "📊 Analisi e Storico"])

with tab1:
    with st.form("inserimento_form"):
        col_a, col_b = st.columns(2)
        val_glic = col_a.number_input("Glicemia (mg/dL)", 40, 400, 100)
        cibo_in = col_b.text_input("Cosa hai mangiato?")
        gr = col_a.number_input("Grammi", 0, 1000, 100)
        ora_man = col_b.text_input("Ora (lascia vuoto per ora attuale)", "")
        note = st.text_area("Note e sensazioni")
        
        if st.form_submit_button("Registra nel Diario"):
            data_inserimento = ora_man if ora_man else datetime.now().strftime("%Y-%m-%d %H:%M")
            food = get_food_data(cibo_in) if cibo_in else {"nome": "Nessuno", "kcal": 0, "carbo": 0}
            
            # Calcolo macro
            k = (food['kcal'] * gr) / 100
            carb = (food['carbo'] * gr) / 100
            
            c.execute("INSERT INTO voci_diario VALUES (?,?,?,?,?,?,?)", 
                      (data_inserimento, val_glic, food['nome'], gr, k, carb, note))
            conn.commit()
            st.balloons()

with tab2:
    df = pd.read_sql_query("SELECT * FROM voci_diario ORDER BY data DESC", conn)
    if not df.empty:
        st.subheader("Andamento ultimi inserimenti")
        fig = px.area(df, x="data", y="glicemia", title="Livelli Glicemici", color_discrete_sequence=['#ff4b4b'])
        st.plotly_chart(fig, use_container_width=True)
        
        st.subheader("Dati salvati")
        st.dataframe(df)
        
        # Totale oggi
        oggi = datetime.now().strftime("%Y-%m-%d")
        df_oggi = df[df['data'].str.contains(oggi)]
        st.metric("Kcal odierne", f"{df_oggi['kcal'].sum()} kcal")
    else:
        st.info("Il diario è vuoto. Inizia dal tab Inserimento!")
