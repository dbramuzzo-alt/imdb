import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import os
import re
import json

# --- CONFIGURAZIONE ---
# La tua API Key di ScraperAPI inserita direttamente nello script
SCRAPER_API_KEY = "d09a651a095f55f0bd28f15a1bad8bd6"
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

# ESTRAZIONE TRAMITE PROXY RESIDENZIALE (Bypassa i blocchi anti-bot di IMDb)
def recupera_voti_reali_imdb(id_imdb, scraper_api_key):
    url_bersaglio = f"https://www.imdb.com/title/{id_imdb}/"
    url_proxy = f"http://api.scraperapi.com?api_key={scraper_api_key}&url={url_bersaglio}"
    
    try:
        # ScraperAPI simula una connessione casalinga reale, aggirando i filtri di Amazon/Streamlit
        risposta = requests.get(url_proxy, timeout=30)
        if risposta.status_code == 200:
            soup = BeautifulSoup(risposta.text, "html.parser")
            
            # Leggiamo il blocco JSON strutturato nativo di IMDb (LD+JSON)
            script_tag = soup.find("script", type="application/ld+json")
            if script_tag:
                dati_json = json.loads(script_tag.string)
                
                titolo = dati_json.get("name", "Titolo Sconosciuto")
                aggregate_rating = dati_json.get("aggregateRating", {})
                
                if aggregate_rating:
                    voto = float(aggregate_rating.get("ratingValue", 0.0))
                    num_voti = int(aggregate_rating.get("ratingCount", 0))
                    return {"Titolo": titolo, "Valutazione IMDb": voto, "Numero Voti": num_voti}
    except Exception as e:
        pass
    return None

# Funzione per aggiornare l'intera classifica
def aggiorna_valutazioni(df, api_key):
    if df.empty or not api_key:
        return df
    
    progress_text = "Aggiornamento valutazioni reali da IMDb..."
    barrita = st.progress(0, text=progress_text)
    
    for index, row in df.iterrows():
        dati_aggiornati = recupera_voti_reali_imdb(row['id_imdb'], api_key)
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
st.title("🎬 Tracker Ufficiale IMDb (Anti-Blocco)")
st.write("Inserisci i tuoi film e ottieni le valutazioni reali estratte in tempo reale senza blocchi dei server.")

df_film = carica_dati()

# Aggiornamento automatico all'avvio usando la chiave cablata
if "aggiornato" not in st.session_state:
    if not df_film.empty:
        with st.spinner("Aggiornamento dati all'avvio..."):
            df_film = aggiorna_valutazioni(df_film, SCRAPER_API_KEY)
    st.session_state["aggiornato"] = True

# --- SEZIONE AGGIUNTA FILM ---
st.subheader("➕ Aggiungi un nuovo film")
link_imdb = st.text_input("Incolla il link o l'ID da IMDb (es. tt30825738):")

if st.button("Aggiungi Film"):
    if link_imdb:
        match = re.search(r'(tt\d+)', link_imdb)
        if match:
            id_estratto = match.group(1)
            
            # Rimuoviamo il vecchio record se già presente per aggiornarlo in modo pulito
            df_film = df_film[df_film['id_imdb'] != id_estratto].reset_index(drop=True)
            
            with st.spinner("Bypassando i blocchi di IMDb con proxy residenziale..."):
                dati_film = recupera_voti_reali_imdb(id_estratto, SCRAPER_API_KEY)
                if dati_film:
                    nuovo_film = {
                        "id_imdb": id_estratto,
                        "Titolo": dati_film["Titolo"],
                        "Valutazione IMDb": dati_film["Valutazione IMDb"],
                        "Numero Voti": dati_film["Numero Voti"]
                    }
                    df_film = pd.concat([df_film, pd.DataFrame([nuovo_film])], ignore_index=True)
                    
