import streamlit as st
import pandas as pd
import plotly.express as px
import requests
import sqlite3
from datetime import datetime

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Glicemia Pro Web", layout="wide", page_icon="🩸")

# --- CONNESSIONE DATABASE ---
conn = sqlite3.connect('diario_glicemia_v4.db', check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS utenti 
             (nome TEXT, peso REAL, altezza REAL, tipo_diabete TEXT, target_min INTEGER, target_max INTEGER)''')
c.execute('''CREATE TABLE IF NOT EXISTS voci_diario 
             (data TEXT, glicemia INTEGER, cibo TEXT, grammi REAL, kcal REAL, carbo REAL, note TEXT)''')
conn.commit()

# --- NUOVA FUNZIONE API (EDAMAM - PIÙ STABILE) ---
def get_food_data_edamam(nome_cibo):
    # Usiamo l'API di Edamam (Food Database)
    # Queste sono chiavi demo, per uso intensivo conviene crearne di proprie su developer.edamam.com
    APP_ID = "02f1a6f5" 
    APP_KEY = "36b579051465e9d9e6939ec1c741e974"
    
    url = "https://api.edamam.com/api/food-database/v2/parser"
    params = {
        "app_id": APP_ID,
        "app_key": APP_KEY,
        "ingr": nome_cibo,
        "nutrition-type": "logging"
    }
    
    try:
        r = requests.get(url, params=params, timeout=5)
        if r.status_code == 200:
            data = r.json()
            if data.get('parsed'):
                food = data['parsed'][0]['food']
                nutr = food.get('nutrients', {})
                return {
                    "nome": food.get('label'),
                    "kcal": nutr.get('ENERC_KCAL', 0),
                    "carbo": nutr.get('CHOCDF', 0)
                }
            elif data.get('hints'):
                food = data['hints'][0]['food']
                nutr = food.get('nutrients', {})
                return {
                    "nome": food.get('label'),
                    "kcal": nutr.get('ENERC_KCAL', 0),
                    "carbo": nutr.get('CHOCDF', 0)
                }
    except Exception as e:
        st.error(f"Errore connessione: {e}")
    return None

# --- LOGICA PROFILO ---
c.execute("SELECT * FROM utenti LIMIT 1")
user_data = c.fetchone()

if not user_data:
    st.info("Benvenuto! Crea il tuo profilo per iniziare.")
    with st.form("crea_profilo"):
        n = st.text_input("Nome")
        p = st.number_input("Peso (kg)", 40, 150, 70)
        a = st.number_input("Altezza (cm)", 100, 220, 170)
        if st.form_submit_button("Inizia"):
            c.execute("INSERT INTO utenti VALUES (?,?,?,?,?,?)", (n, p, a, "Tipo 1", 70, 140))
            conn.commit()
            st.rerun()
    st.stop()

# --- INTERFACCIA APP ---
st.title(f"🩸 Diario di {user_data[0]}")

t1, t2 = st.tabs(["➕ Registra", "📊 Analisi"])

with t1:
    # Ricerca Cibo
    query = st.text_input("🔍 Cosa hai mangiato?", placeholder="Es: Pasta, Apple, Chicken...")
    
    food_info = None
    if query:
        food_info = get_food_data_edamam(query)
        if food_info:
            st.success(f"Trovato: **{food_info['nome']}** ({food_info['kcal']:.0f} kcal/100g)")
        else:
            st.warning("Cibo non trovato. Inserimento manuale.")

    st.divider()

    with st.form("pasto_form"):
        col1, col2 = st.columns(2)
        with col1:
            g_val = st.number_input("Glicemia (mg/dL)", 20, 500, 100)
            gr_val = st.number_input("Grammi (g)", 1, 1000, 100)
        with col2:
            nome_f = st.text_input("Conferma Alimento", value=food_info['nome'] if food_info else query)
            ora_f = st.time_input("Ora", datetime.now().time())
        
        note = st.text_area("Note")
        
        if st.form_submit_button("💾 Salva nel Diario"):
            # Calcolo macro
            k100 = food_info['kcal'] if food_info else 0
            c100 = food_info['carbo'] if food_info else 0
            kcal_t = (k100 * gr_val) / 100
            carb_t = (c100 * gr_val) / 100
            data_t = datetime.now().strftime("%Y-%m-%d ") + ora_f.strftime("%H:%M")
            
            c.execute("INSERT INTO voci_diario VALUES (?,?,?,?,?,?,?)", 
                      (data_t, g_val, nome_f, gr_val, kcal_t, carb_t, note))
            conn.commit()
            st.rerun()

with t2:
    df = pd.read_sql_query("SELECT * FROM voci_diario ORDER BY data ASC", conn)
    if not df.empty:
        # Grafico
        fig = px.area(df, x="data", y="glicemia", title="Andamento Glicemia", line_shape="spline")
        fig.add_hline(y=user_data[5], line_dash="dash", line_color="red")
        st.plotly_chart(fig, use_container_width=True)
        
        # Storico
        st.subheader("Dati Registrati")
        st.dataframe(df.sort_values(by="data", ascending=False), use_container_width=True)
        
        if st.button("Svuota tutto"):
            c.execute("DELETE FROM voci_diario")
            conn.commit()
            st.rerun()
    else:
        st.info("Il diario è vuoto.")
