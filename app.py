import streamlit as st
import pandas as pd
import plotly.express as px
import requests
import sqlite3
from datetime import datetime

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Glicemia Pro Cloud", layout="wide", page_icon="🩸")

# --- CONNESSIONE DATABASE (SQLite) ---
# Questo file verrà creato nella stessa cartella dell'app
conn = sqlite3.connect('diario_glicemia.db', check_same_thread=False)
c = conn.cursor()

# Creazione tabelle
c.execute('''CREATE TABLE IF NOT EXISTS utenti 
             (nome TEXT, peso REAL, altezza REAL, tipo_diabete TEXT, target_min INTEGER, target_max INTEGER)''')
c.execute('''CREATE TABLE IF NOT EXISTS voci_diario 
             (data TEXT, glicemia INTEGER, cibo TEXT, grammi REAL, kcal REAL, carbo REAL, note TEXT)''')
conn.commit()

# --- FUNZIONI DI SUPPORTO ---
def get_food_data(nome_cibo):
    """Interroga l'API di Open Food Facts"""
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
    except Exception:
        return None
    return None

# --- SIDEBAR: PROFILO UTENTE ---
st.sidebar.title("👤 Profilo Utente")
c.execute("SELECT * FROM utenti LIMIT 1")
user_data = c.fetchone()

with st.sidebar.form("profilo_form"):
    n = st.text_input("Nome", value=user_data[0] if user_data else "Utente")
    p = st.number_input("Peso (kg)", value=user_data[1] if user_data else 70.0)
    a = st.number_input("Altezza (cm)", value=user_data[2] if user_data else 170.0)
    t = st.selectbox("Tipo Diabete", ["Tipo 1", "Tipo 2", "Gestazionale", "Nessuno"], 
                     index=["Tipo 1", "Tipo 2", "Gestazionale", "Nessuno"].index(user_data[3] if user_data else "Nessuno"))
    t_min = st.slider("Target Min (mg/dL)", 60, 100, user_data[4] if user_data else 70)
    t_max = st.slider("Target Max (mg/dL)", 120, 200, user_data[5] if user_data else 140)
    
    if st.form_submit_button("Salva Impostazioni"):
        c.execute("DELETE FROM utenti")
        c.execute("INSERT INTO utenti VALUES (?,?,?,?,?,?)", (n, p, a, t, t_min, t_max))
        conn.commit()
        st.sidebar.success("Profilo aggiornato!")

# --- CORPO PRINCIPALE ---
st.title("🩸 Glicemia & Nutrizione Smart")

tab1, tab2, tab3 = st.tabs(["➕ Nuovo Inserimento", "📊 Grafici", "📜 Storico Dati"])

# --- TAB 1: INSERIMENTO ---
with tab1:
    with st.form("entry_form"):
        col1, col2 = st.columns(2)
        with col1:
            glic = st.number_input("Glicemia rilevata (mg/dL)", 20, 500, 100)
            cibo = st.text_input("Cibo consumato", help="Es: Mela, Pasta, Pane...")
            grammi = st.number_input("Grammi (g)", 0, 2000, 100)
        with col2:
            data_custom = st.text_input("Ora (HH:MM) - Vuoto per ora attuale", "")
            note = st.text_area("Note (attività fisica, stress, farmaci...)")
        
        submit = st.form_submit_button("Registra nel Diario")
        
        if submit:
            # Gestione Orario
            ora_inserimento = datetime.now().strftime("%Y-%m-%d ") + data_custom if data_custom else datetime.now().strftime("%Y-%m-%d %H:%M")
            
            # Recupero dati cibo con gestione errore (il fix per il tuo TypeError)
            food_info = get_food_data(cibo) if cibo else None
            
            if food_info:
                nome_f = food_info['nome']
                k_tot = (food_info['kcal'] * grammi) / 100
                c_tot = (food_info['carbo'] * grammi) / 100
            else:
                nome_f = cibo if cibo else "Nessun pasto"
                k_tot, c_tot = 0.0, 0.0
                if cibo:
                    st.warning(f"'{cibo}' non trovato nel database. Valori nutrizionali impostati a 0.")

            # Salvataggio nel database
            c.execute("INSERT INTO voci_diario VALUES (?,?,?,?,?,?,?)", 
                      (ora_inserimento, glic, nome_f, grammi, k_tot, c_tot, note))
            conn.commit()
            st.success("Dati salvati correttamente!")

# --- TAB 2: GRAFICI ---
with tab2:
    df = pd.read_sql_query("SELECT * FROM voci_diario ORDER BY data ASC", conn)
    if not df.empty:
        # Grafico Glicemia
        fig = px.line(df, x="data", y="glicemia", title="Andamento Glicemico", markers=True)
        # Linee di target basate sul profilo
        t_max_val = user_data[5] if user_data else 140
        fig.add_hline(y=t_max_val, line_dash="dash", line_color="red", annotation_text="Limite Target")
        st.plotly_chart(fig, use_container_width=True)
        
        # Riepilogo Macro
        col_m1, col_m2 = st.columns(2)
        oggi = datetime.now().strftime("%Y-%m-%d")
        df_oggi = df[df['data'].str.contains(oggi)]
        col_m1.metric("Calorie Oggi", f"{df_oggi['kcal'].sum():.0f} kcal")
        col_m2.metric("Carboidrati Oggi", f"{df_oggi['carbo'].sum():.1f} g")
    else:
        st.info("Nessun dato disponibile per i grafici.")

# --- TAB 3: STORICO ---
with tab3:
    df_view = pd.read_sql_query("SELECT * FROM voci_diario ORDER BY data DESC", conn)
    if not df_view.empty:
        st.dataframe(df_view, use_container_width=True)
        if st.button("Cancella tutto lo storico"):
            c.execute("DELETE FROM voci_diario")
            conn.commit()
            st.rerun()
    else:
        st.write("Il diario è ancora vuoto.")
