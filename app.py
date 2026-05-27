import streamlit as st
import pandas as pd
import requests
import os
import re

# --- CONFIGURAZIONE ---
# La tua API Key di OMDb inserita direttamente nello script
API_KEY = "a5055d8d"
# Nome del file dove salveremo i film
DB_FILE = "film_db.csv"

# Funzione per caricare i dati dal CSV
def carica_dati():
    if os.path.exists(DB_FILE):
        return pd.read_csv(DB_FILE, dtype={'id_imdb': str})
    return pd.DataFrame(columns=["id_imdb", "Titolo", "Valutazione IMDb", "Numero Voti"])

# Funzione per salvare i dati nel CSV
def salva_dati(df):
    df.to_csv(DB_FILE, index=False)

# Funzione per estrarre i dati usando OMDb API
def recupera_dati_omdb(id_imdb, api_key):
    url = f"http://www.omdbapi.com/?i={id_imdb}&apikey={api_key}"
    
    try:
        risposta = requests.get(url, timeout=10)
        if risposta.status_code != 200:
            return None
            
        dati = risposta.json()
        
        if dati.get("Response") == "True":
            titolo = dati.get("Title", "Titolo Sconosciuto")
            
            # Estrazione Voto IMDb (pulizia aggressiva)
            voto_str = dati.get("imdbRating", "0.0").strip()
            try:
                voto = float(voto_str) if voto_str and voto_str != "N/A" else 0.0
            except ValueError:
                voto = 0.0
            
            # Estrazione Numero Voti (rimuove virgole, punti e spazi)
            voti_str = dati.get("imdbVotes", "0").strip()
            try:
                if voti_str and voti_str != "N/A":
                    voti_puliti = re.sub(r'[^\d]', '', voti_str)
                    num_voti = int(voti_puliti) if voti_puliti else 0
                else:
                    num_voti = 0
            except ValueError:
                num_voti = 0
            
            return {"Titolo": titolo, "Valutazione IMDb": voto, "Numero Voti": num_voti}
        else:
            st.error(f"Errore API OMDb: {dati.get('Error', 'Errore sconosciuto')}")
            return None
    except Exception as e:
        st.error(f"Errore di connessione: {e}")
        return None

# Funzione per aggiornare la lista completa
def aggiorna_valutazioni(df, api_key):
    if df.empty or not api_key:
        return df
    
    progress_text = "Aggiornamento valutazioni tramite API..."
    barrita = st.progress(0, text=progress_text)
    
    for index, row in df.iterrows():
        dati_aggiornati = recupera_dati_omdb(row['id_imdb'], api_key)
        if dati_aggiornati:
            df.at[index, 'Valutazione IMDb'] = dati_aggiornati['Valutazione IMDb']
            df.at[index, 'Numero Voti'] = dati_aggiornati['Numero Voti']
            df.at[index, 'Titolo'] = dati_aggiornati['Titolo']
        
        barrita.progress((index + 1) / len(df), text=progress_text)
    
    barrita.empty()
    df = df.sort_values(by="Valutazione IMDb", ascending=False).reset_index(drop=True)
    salva_dati(df)
    return df

# --- INTERFACCIA STREAMLIT ---
st.title("🎬 Il mio Tracker di Film IMDb")
st.write("Inserisci i tuoi film e tieni traccia delle loro valutazioni senza blocchi!")

df_film = carica_dati()

# Aggior
