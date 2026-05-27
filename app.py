import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import os
import re
import json

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

# Funzione ROBUSTA per estrarre i dati di un film da IMDb
def recupera_dati_imdb(id_imdb):
    url = f"https://www.imdb.com/title/{id_imdb}/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7"
    }
    
    try:
        risposta = requests.get(url, headers=headers, timeout=10)
        if risposta.status_code != 200:
            return None
            
        soup = BeautifulSoup(risposta.text, "html.parser")
        
        # Cerchiamo il blocco di dati strutturati JSON-LD che IMDb usa per Google
        script_tag = soup.find("script", type="application/ld+json")
        
        if script_tag:
            dati_json = json.loads(script_tag.string)
            
            # Estraiamo il titolo
            titolo = dati_json.get("name", "Titolo Sconosciuto")
            
            # Estraiamo le valutazioni
            aggregate_rating = dati_json.get("aggregateRating", {})
            voto = float(aggregate_rating.get("ratingValue", 0.0)) if aggregate_rating else 0.0
            num_voti = int(aggregate_rating.get("ratingCount", 0)) if aggregate_rating else 0
            
            return {"Titolo": titolo, "Valutazione IMDb": voto, "Numero Voti": num_voti}
            
        # Fallback nel caso in cui il JSON-LD non sia presente
        titolo_tag = soup.find("meta", property="og:title")
        titolo = titolo_tag["content"].split(" (")[0] if titolo_tag else "Sconosciuto"
        return {"Titolo": titolo, "Valutazione IMDb": 0.0, "Numero Voti": 0}
        
    except Exception as e:
        return None

# Funzione per aggiornare la lista completa
def aggiorna_valutazioni(df):
    if df.empty:
        return df
    
    progress_text = "Aggiornamento valutazioni da IMDb..."
    barrita = st.progress(0, text=progress_text)
    
    for index, row in df.iterrows():
        dati_aggiornati = recupera_dati_imdb(row['id_imdb'])
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
st.write("Inserisci i tuoi film e tieni traccia delle loro valutazioni in tempo reale!")

df_film = carica_dati()

# Aggiornamento automatico all'avvio
if "aggiornato" not in st.session_state:
    if not df_film.empty:
        with st.spinner("Aggiornamento dati all'avvio..."):
            df_film = aggiorna_valutazioni(df_film)
    st.session_state["aggiornato"] = True

# --- SEZIONE AGGIUNTA FILM ---
st.subheader("➕ Aggiungi un nuovo film")
link_imdb = st.text_input("Incolla il link o l'ID da IMDb (es. tt0111161):")

if st.button("Aggiungi Film"):
    if link_imdb:
        # Estrae l'ID (cerca 'tt' seguito da numeri)
        match = re.search(r'(tt\d+)', link_imdb)
        if match:
            id_estratto = match.group(1)
            
            if id_estratto in df_film['id_imdb'].values:
                st.info("Questo film è già presente nella tua lista!")
            else:
                with st.spinner("Recupero informazioni da IMDb..."):
                    dati_film = recupera_dati_imdb(id_estratto)
                    if dati_film:
                        nuovo_film = {
                            "id_imdb": id_estratto,
                            "Titolo": dati_film["Titolo"],
                            "Valutazione IMDb": dati_film["Valutazione IMDb"],
                            "Numero Voti": dati_film["Numero Voti"]
                        }
                        df_film = pd.concat([df_film, pd.DataFrame([nuovo_film])], ignore_index=True)
                        df_film = df_film.sort_values(by="Valutazione IMDb", ascending=False).reset_index(drop=True)
                        salva_dati(df_film)
                        st.success(f"Aggiunto con successo: **{dati_film['Titolo']}**!")
                        st.rerun()
                    else:
                        st.error("Impossibile connettersi a IMDb. Riprova tra qualche istante.")
        else:
            st.error("Non ho trovato un ID IMDb valido. Assicurati che nel link ci sia una parte che inizia con 'tt' seguita da numeri.")
    else:
        st.warning("Inserisci un link o un ID prima di premere il bottone.")

st.divider()

# --- VISUALIZZAZIONE DATI ---
st.subheader("📊 La tua classifica")

if df_film.empty:
    st.info("La tua lista è vuota. Aggiungi il tuo primo film qui sopra!")
else:
    tabella_da_mostrare = df_film[["Titolo", "Valutazione IMDb", "Numero Voti"]].copy()
    
    # Formatta il numero di voti inserendo i punti (es: 1.250.000)
    tabella_da_mostrare["Numero Voti"] = tabella_da_mostrare["Numero Voti"].map(lambda x: f"{int(x):,}".replace(",", "."))
    
    st.dataframe(tabella_da_mostrare, use_container_width=True)
    
    if st.button("🔄 Forza Aggiornamento Ora"):
        with st.spinner("Aggiornamento in corso..."):
            df_film = aggiorna_valutazioni(df_film)
            st.success("Classifica aggiornata!")
            st.rerun()
    
