import streamlit as st
import pandas as pd
import plotly.express as px
import requests
import sqlite3
from datetime import datetime

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Glicemia Pro Cloud", layout="wide", page_icon="🩸")

# --- CONNESSIONE DATABASE (SQLite) ---
conn = sqlite3.connect('diario_glicemia_v3.db', check_same_thread=False)
c = conn.cursor()

# Creazione Tabelle
c.execute('''CREATE TABLE IF NOT EXISTS utenti 
             (nome TEXT, peso REAL, altezza REAL, tipo_diabete TEXT, target_min INTEGER, target_max INTEGER)''')
c.execute('''CREATE TABLE IF NOT EXISTS voci_diario 
             (data TEXT, glicemia INTEGER, cibo TEXT, grammi REAL, kcal REAL, carbo REAL, note TEXT)''')
conn.commit()

# --- FUNZIONE API FOOD (Versione Definitiva e Robusta) ---
def get_food_data(nome_cibo):
    # Endpoint globale con filtri per migliorare la pertinenza
    url = "https://it.openfoodfacts.org/cgi/search.pl"
    params = {
        "search_terms": nome_cibo,
        "search_simple": 1,
        "action": "process",
        "json": 1,
        "page_size": 20,
        "fields": "product_name,product_name_it,nutriments,image_front_thumb_url"
    }
    headers = {'User-Agent': 'GlicemiaTracker/1.0 (https://streamlit.io)'}
    
    try:
        r = requests.get(url, params=params, headers=headers, timeout=10)
        if r.status_code == 200:
            data = r.json()
            products = data.get('products', [])
            if products:
                # Cerchiamo il prodotto che ha i carboidrati compilati tra i primi risultati
                for p in products:
                    n = p.get('nutriments', {})
                    # Preferiamo prodotti con dati sui carboidrati (essenziali per glicemia)
                    if 'carbohydrates_100g' in n:
                        return {
                            "nome": p.get('product_name_it') or p.get('product_name') or nome_cibo,
                            "kcal": n.get('energy-kcal_100g') or n.get('energy-kcal') or 0,
                            "carbo": n.get('carbohydrates_100g', 0),
                            "thumb": p.get('image_front_thumb_url', '')
                        }
    except Exception as e:
        st.error(f"Errore di connessione API: {e}")
    return None

# --- LOGICA PROFILO ---
c.execute("SELECT * FROM utenti LIMIT 1")
user_data = c.fetchone()

# Sidebar per impostazioni
st.sidebar.title("👤 Profilo Utente")
if not user_data:
    st.sidebar.warning("Configura il profilo per iniziare")
    with st.sidebar.form("primo_avvio"):
        n_in = st.text_input("Nome")
        p_in = st.number_input("Peso (kg)", 40.0, 150.0, 70.0)
        a_in = st.number_input("Altezza (cm)", 100, 220, 170)
        t_in = st.selectbox("Diabete", ["Nessuno", "Tipo 1", "Tipo 2"])
        if st.form_submit_button("Crea Profilo"):
            c.execute("INSERT INTO utenti VALUES (?,?,?,?,?,?)", (n_in, p_in, a_in, t_in, 70, 140))
            conn.commit()
            st.rerun()
else:
    with st.sidebar.form("update_profilo"):
        st.write(f"Ciao, **{user_data[0]}**")
        t_min = st.slider("Target Min", 50, 100, user_data[4])
        t_max = st.slider("Target Max", 110, 200, user_data[5])
        if st.form_submit_button("Aggiorna Target"):
            c.execute("UPDATE utenti SET target_min = ?, target_max = ?", (t_min, t_max))
            conn.commit()
            st.rerun()

# --- APP PRINCIPALE ---
st.title("🩸 Glicemia & Diario Alimentare")

t1, t2, t3 = st.tabs(["📝 Inserimento", "📈 Analisi", "📋 Storico"])

with t1:
    st.subheader("Nuova Misurazione")
    
    # Campo di ricerca interattivo
    query = st.text_input("🔍 Cerca cibo mangiato", placeholder="Esempio: Pasta Barilla, Mela, Pizza...")
    
    food_found = None
    if query:
        food_found = get_food_data(query)
        if food_found:
            col_img, col_txt = st.columns([1, 4])
            with col_txt:
                st.success(f"Trovato: **{food_found['nome']}**")
                st.caption(f"Valori per 100g: {food_found['kcal']} kcal | {food_found['carbo']}g Carboidrati")
        else:
            st.warning("Cibo non trovato. Inserimento manuale attivo.")

    st.divider()

    with st.form("pasto_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            glic_val = st.number_input("Glicemia (mg/dL)", 30, 500, 100)
            grammi = st.number_input("Grammi consumati", 1, 1000, 100)
        with c2:
            nome_final = st.text_input("Nome Alimento", value=food_found['nome'] if food_found else query)
            ora_val = st.time_input("Ora del pasto/misurazione", datetime.now().time())
        
        note = st.text_area("Note (es. 2 ore dopo il pranzo)")
        
        if st.form_submit_button("Salva nel diario"):
            # Calcoli
            k100 = food_found['kcal'] if food_found else 0
            c100 = food_found['carbo'] if food_found else 0
            kcal_t = (k100 * grammi) / 100
            carb_t = (c100 * grammi) / 100
            data_t = datetime.now().strftime("%Y-%m-%d ") + ora_val.strftime("%H:%M")
            
            c.execute("INSERT INTO voci_diario VALUES (?,?,?,?,?,?,?)", 
                      (data_t, glic_val, nome_final, grammi, kcal_t, carb_t, note))
            conn.commit()
            st.success("Registrato con successo!")
            st.rerun()

with t2:
    df = pd.read_sql_query("SELECT * FROM voci_diario ORDER BY data ASC", conn)
    if not df.empty:
        # Grafico
        fig = px.line(df, x="data", y="glicemia", title="Curva Glicemica", markers=True)
        if user_data:
            fig.add_hline(y=user_data[5], line_dash="dash", line_color="red")
            fig.add_hline(y=user_data[4], line_dash="dash", line_color="green")
        st.plotly_chart(fig, use_container_width=True)
        
        # Riassunto oggi
        oggi = datetime.now().strftime("%Y-%m-%d")
        df_oggi = df[df['data'].str.contains(oggi)]
        st.subheader("Resoconto Odierno")
        m1, m2, m3 = st.columns(3)
        m1.metric("Calorie", f"{df_oggi['kcal'].sum():.0f} kcal")
        m2.metric("Carboidrati", f"{df_oggi['carbo'].sum():.1f} g")
        m3.metric("Glicemia Media", f"{df_oggi['glicemia'].mean():.0f} mg/dL")
    else:
        st.info("Nessun dato da mostrare.")

with t3:
    df_storico = pd.read_sql_query("SELECT * FROM voci_diario ORDER BY data DESC", conn)
    st.dataframe(df_storico, use_container_width=True)
    if st.button("Svuota tutto il diario"):
        c.execute("DELETE FROM voci_diario")
        conn.commit()
        st.rerun()
