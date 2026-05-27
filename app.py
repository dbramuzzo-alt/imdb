import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import os
import re

# --- CONFIGURAZIONE ---
OMDB_API_KEY = "a5055d8d"
DB_FILE = "film_db.csv"

# Funzione per caricare i dati dal CSV
def carica_dati():
    if os.path.exists(DB_FILE):
        return pd.read_csv(DB_FILE, dtype={'id_imdb': str})
    return pd.DataFrame(columns=["id_imdb", "Titolo", "Valutazione IMDb", "Numero Voti"])

# Funzione per salvare i dati nel CSV
def salva_dati(df):
    df.to_csv(DB_FILE, index=False)

# SCRAPING VISIVO DI PRECISIONE: Legge i dati direttamente dall'interfaccia di IMDb
def scraping_diretto_imdb(id_imdb):
    url = f"https://www.imdb.com/title/{id_imdb}/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "it-IT,it;q=0.9,en;q=0.8"
    }
    try:
        risposta = requests.get(url, headers=headers, timeout=8)
        if risposta.status_code == 200:
            soup = BeautifulSoup(risposta.text, "html.parser")
            
            # 1. Cerchiamo il titolo della pagina
            titolo_tag = soup.find("h1")
            titolo = titolo_tag.text.strip() if titolo_tag else "Titolo Sconosciuto"
            
            # 2. Cerchiamo il voto tramite l'attributo testID ufficiale di IMDb per la barra dei voti
            voto_box = soup.find("div", {"data-testid": "hero-rating-bar__aggregate-rating__score"})
            voto = 0.0
            if voto_box:
                # Estrae il primo numero prima dello slash (es: "7.5/10" -> "7.5")
                voto_testo = voto_box.find("span")
                if voto_testo:
                    voto = float(voto_testo.text.strip())
            
            # 3. Cerchiamo il numero di voti associato
            voti_box = soup.find("div", {"class": "sc-bde20123-3 gZYLgH"}) or soup.find("div", string=re.compile(r'^[0-8],\d+|^[0-9]+K|^[0-9]+M'))
            num_voti = 0
            if voti_box:
                testo_voti = voti_box.text.strip()
                moltiplicatore = 1
                if "M" in testo_voti:
                    moltiplicatore = 1_000_000
                    testo_voti = testo_voti.replace("M", "")
                elif "K" in testo_voti:
                    moltiplicatore = 1_000
                    testo_voti = testo_voti.replace("K", "")
                
                # Rimuove tutto ciò che non è un numero o un punto decimale
                testo_voti = re.sub(r'[^\d.]', '', testo_voti.replace(',', '.'))
                if testo_voti:
                    num_voti = int(float(testo_voti) * moltiplicatore)
                    
            return {"Titolo": titolo, "Valutazione IMDb": voto, "Numero Voti": num_voti}
    except Exception as e:
        pass
    return None

# Funzione principale mista
def recupera_dati_film(id_imdb):
    # Per i film freschi di uscita, saltiamo OMDb e andiamo dritti allo scraping visivo
    dati_diretti = scraping_diretto_imdb(id_imdb)
    if dati_diretti and dati_diretti["Valutazione IMDb"] > 0:
        return dati_diretti
        
    # Se lo scraping fallisce, usiamo l'API come paracadute
    url_omdb = f"http://www.omdbapi.com/?i={id_imdb}&apikey={OMDB_API_KEY}"
    try:
        risposta = requests.get(url_omdb, timeout=5)
        if risposta.status_code == 200:
            dati = risposta.json()
            if dati.get("Response") == "True":
                voto_str = dati.get("imdbRating", "0.0").strip()
                voto = float(voto_str) if voto_str and voto_str != "N/A" else 0.0
                voti_str = dati.get("imdbVotes", "0").strip()
                voti_puliti = re.sub(r'[^\d]', '', voti_str) if voti_str and voti_str != "N/A" else "0"
                num_voti = int(voti_puliti) if voti_puliti else 0
                return {"Titolo": dati.get("Title"), "Valutazione IMDb": voto, "Numero Voti": num_voti}
    except:
        pass
        
    return dati_diretti  # Restituisce comunque quello che ha trovato visivamente

# Funzione per aggiornare la lista completa
def aggiorna_valutazioni(df):
    if df.empty:
        return df
    
    progress_text = "Aggiornamento valutazioni live..."
    barrita = st.progress(0, text=progress_text)
    
    for index, row in df.iterrows():
        dati_aggiornati = recupera_dati_film(row['id_imdb'])
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
        match = re.search(r'(tt\d+)', link_imdb)
        if match:
            id_estratto = match.group(1)
            
            df_film = df_film[df_film['id_imdb'] != id_estratto].reset_index(drop=True)
            
            with st.spinner("Lettura dati in tempo reale da IMDb..."):
                dati_film = recupera_dati_film(id_estratto)
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
                    st.success(f"Aggiunto: **{dati_film['Titolo']}** (Voto: {dati_film['Valutazione IMDb']}, Voti: {dati_film['Numero Voti']})")
                    st.rerun()
                else:
                    st.error("Impossibile caricare il film. Riprova.")
        else:
            st.error("ID IMDb non valido.")
    else:
        st.warning("Inserisci un link.")

st.divider()

# --- VISUALIZZAZIONE DATI ---
st.subheader("📊 La tua classifica")

if df_film.empty:
    st.info("La tua lista è vuota.")
else:
    tabella_da_mostrare = df_film[["Titolo", "Valutazione IMDb", "Numero Voti"]].copy()
    tabella_da_mostrare["Numero Voti"] = tabella_da_mostrare["Numero Voti"].map(
        lambda x: f"{int(x):,}".replace(",", ".") if pd.notnull(x) else "0"
    )
    
    st.dataframe(tabella_da_mostrare, use_container_width=True)
    
    if st.button("🔄 Forza Aggiornamento Ora"):
        with st.spinner("Aggiornamento in corso..."):
            df_film = aggiorna_valutazioni(df_film)
            st.success("Classifica aggiornata!")
            st.rerun()
            
