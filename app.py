import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import os
import re

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

# Funzione per estrarre i dati di un film da IMDb tramite Web Scraping
def recupera_dati_imdb(id_imdb):
    url = f"https://www.imdb.com/title/{id_imdb}/"
    # IMDb richiede un User-Agent realistico per non bloccare la richiesta
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7"
    }
    
    risposta = requests.get(url, headers=headers)
    if risposta.status_code != 200:
        return None
        
    soup = BeautifulSoup(risposta.text, "html.parser")
    
    try:
        # Estrai il titolo dal tag <title> o dagli open graph
        titolo_tag = soup.find("meta", property="og:title")
        if titolo_tag:
            titolo = titolo_tag["content"].split(" (")[0] # Rimuove l'anno dal titolo (es. "Inception (2010)" -> "Inception")
        else:
            titolo = soup.find("title").text.replace(" - IMDb", "")
            
        # Trova il voto (cercando nello schema JSON strutturato o nei tag specifici di IMDb)
        voto_tag = soup.find("span", {"class": "sc-bde20123-1 cCNeUe"}) # Classe standard attuale per il rating
        if voto_tag:
            voto = float(voto_tag.text)
        else:
            # Fallback se cambiano le classi
            voto_meta = soup.find("meta", itemprop="ratingValue")
            voto = float(voto_meta["content"]) if voto_meta else 0.0

        # Trova il numero di voti
        voti_count_tag = soup.find("div", {"class": "sc-bde20123-3 gZYLgH"}) # Classe standard attuale per il numero voti
        if voti_count_tag:
            testo_voti = voti_count_tag.text
            # Converte formati come "1.2M" o "450K" in numeri interi approssimativi
            moltiplicatore = 1
            if "M" in testo_voti:
                moltiplicatore = 1_000_000
                testo_voti = testo_voti.replace("M", "")
            elif "K" in testo_voti:
                moltiplicatore = 1_000
                testo_voti = testo_voti.replace("K", "")
            
            # Pulisce il testo lasciando solo numeri e punti/virgole decimali
            testo_voti = re.sub(r'[^\d.]', '', testo_voti.replace(',', '.'))
            num_voti = int(float(testo_voti) * moltiplicatore)
        else:
            num_voti = 0

        return {"Titolo": titolo, "Valutazione IMDb": voto, "Numero Voti": num_voti}
    except Exception as e:
        # Se fallisce il parsing avanzato, restituisce dati vuoti ma evita il crash
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
link_imdb = st.text_input("Incolla il link del film (es. https://www.imdb.com/title/tt0111161/) o l'ID (tt0111161):")

if st.button("Aggiungi Film"):
    if link_imdb:
        # Estrae l'ID usando una regex per prendere la parte "tt" seguita da numeri
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
                        st.error("Impossibile recuperare il film. Verifica che il link o l'ID siano corretti.")
        else:
            st.error("Non ho trovato un ID IMDb valido (deve contenere 'tt' seguito da numeri).")
    else:
        st.warning("Inserisci un link o un ID prima di premere il bottone.")

st.divider()

# --- VISUALIZZAZIONE DATI ---
st.subheader("📊 La tua classifica")

if df_film.empty:
    st.info("La tua lista è vuota. Aggiungi il tuo primo film qui sopra!")
else:
    tabella_da_mostrare = df_film[["Titolo", "Valutazione IMDb", "Numero Voti"]].copy()
    
    # Formatta il numero di voti inserendo i punti per i decimali (es: 1.250.000)
    tabella_da_mostrare["Numero Voti"] = tabella_da_mostrare["Numero Voti"].map(lambda x: f"{int(x):,}".replace(",", "."))
    
    st.dataframe(tabella_da_mostrare, use_container_width=True)
    
    if st.button("🔄 Forza Aggiornamento Ora"):
        with st.spinner("Aggiornamento in corso..."):
            df_film = aggiorna_valutazioni(df_film)
            st.success("Classifica aggiornata!")
            st.rerun()
                          
