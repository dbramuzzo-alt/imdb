import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import os
import re
import json

# --- CONFIGURAZIONE ---
SCRAPER_API_KEY = "d09a651a095f55f0bd28f15a1bad8bd6"
DB_FILE = "film_db.csv"

def carica_dati():
    if os.path.exists(DB_FILE):
        return pd.read_csv(DB_FILE, dtype={'id_imdb': str})
    return pd.DataFrame(columns=["id_imdb", "Titolo", "Valutazione IMDb", "Numero Voti"])

def salva_dati(df):
    df.to_csv(DB_FILE, index=False)

# ESTRAZIONE IBRIDA (JSON + HTML GRAFICO) TRAMITE PROXY
def recupera_voti_reali_imdb(id_imdb, scraper_api_key):
    url_bersaglio = f"https://www.imdb.com/title/{id_imdb}/"
    url_proxy = f"http://api.scraperapi.com?api_key={scraper_api_key}&url={url_bersaglio}"
    
    try:
        risposta = requests.get(url_proxy, timeout=30)
        if risposta.status_code == 200:
            soup = BeautifulSoup(risposta.text, "html.parser")
            
            # --- METODO 1: JSON-LD STRUTTURATO ---
            script_tag = soup.find("script", type="application/ld+json")
            if script_tag:
                try:
                    dati_json = json.loads(script_tag.string)
                    titolo = dati_json.get("name")
                    aggregate_rating = dati_json.get("aggregateRating", {})
                    if aggregate_rating and titolo:
                        voto = float(aggregate_rating.get("ratingValue", 0.0))
                        num_voti = int(aggregate_rating.get("ratingCount", 0))
                        return {"Titolo": titolo, "Valutazione IMDb": voto, "Numero Voti": num_voti}
                except:
                    pass
            
            # --- METODO 2: FALLBACK HTML GRAFICO (Se il JSON fallisce o è parziale) ---
            titolo_tag = soup.find("h1") or soup.find("meta", property="og:title")
            titolo = "Titolo Sconosciuto"
            if titolo_tag:
                titolo = titolo_tag.text.strip() if titolo_tag.name == "h1" else titolo_tag["content"].split(" (")[0]

            # Cerca la casella del voto usando il testid ufficiale dell'interfaccia IMDb
            voto_box = soup.find("div", {"data-testid": "hero-rating-bar__aggregate-rating__score"})
            voto = 0.0
            if voto_box:
                voto_testo = voto_box.find("span")
                if voto_testo:
                    try:
                        voto = float(voto_testo.text.strip())
                    except:
                        pass
            
            # Cerca il numero dei voti nel testo adiacente
            num_voti = 0
            voti_box = soup.find("div", string=re.compile(r'^[0-9.,]+[KM]?\s*(voti|votes)?', re.IGNORECASE))
            if not voti_box and voto_box:
                # Se non lo trova con le espressioni regolari, prende il tag successivo al voto
                voti_box = voto_box.find_next_sibling("div")
                
            if voti_box:
                testo_voti = voti_box.text.strip().upper()
                moltiplicatore = 1
                if "M" in testo_voti:
                    moltiplicatore = 1_000_000
                    testo_voti = testo_voti.replace("M", "")
                elif "K" in testo_voti:
                    moltiplicatore = 1_000
                    testo_voti = testo_voti.replace("K", "")
                
                testo_voti = re.sub(r'[^\d.]', '', testo_voti.replace(',', '.'))
                if testo_voti:
                    try:
                        num_voti = int(float(testo_voti) * moltiplicatore)
                    except:
                        pass
            
            # Se abbiamo trovato almeno il titolo e un voto (o se è un film appena uscito senza voti strutturati)
            if titolo != "Titolo Sconosciuto":
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
            
            df_film = df_film[df_film['id_imdb'] != id_estratto].reset_index(drop=True)
            
            with st.spinner("Estrazione profonda tramite ScraperAPI..."):
                dati_film = recupera_voti_reali_imdb(id_estratto, SCRAPER_API_KEY)
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
                    st.success(f"Aggiunto direttamente da IMDb: **{dati_film['Titolo']}** (Voto: {dati_film['Valutazione IMDb']}, Voti: {dati_film['Numero Voti']})")
                    st.rerun()
                else:
                    st.error("Errore di estrazione. La pagina di IMDb non ha risposto correttamente o l'ID non è valido.")
        else:
            st.error("ID IMDb non valido.")
    else:
        st.warning("Inserisci un link.")

st.divider()

# --- VISUALIZZAZIONE DATI ---
st.subheader("📊 Classifica Ufficiale IMDb")

if df_film.empty:
    st.info("La tua lista è vuota. Aggiungi il tuo primo film qui sopra!")
else:
    tabella_da_mostrare = df_film[["Titolo", "Valutazione IMDb", "Numero Voti"]].copy()
    tabella_da_mostrare["Numero Voti"] = tabella_da_mostrare["Numero Voti"].map(
        lambda x: f"{int(x):,}".replace(",", ".") if pd.notnull(x) else "0"
    )
    
    st.dataframe(tabella_da_mostrare, use_container_width=True)
    
    if st.button("🔄 Forza Aggiornamento Ora"):
        with st.spinner("Aggiornamento in corso..."):
            df_film = aggiorna_valutazioni(df_film, SCRAPER_API_KEY)
            st.success("Classifica aggiornata!")
            st.rerun()
            
