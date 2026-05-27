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

# Caricamento sicuro del CSV locale
def carica_dati():
    if os.path.exists(DB_FILE):
        return pd.read_csv(DB_FILE, dtype={'id_imdb': str})
    return pd.DataFrame(columns=["id_imdb", "Titolo", "Valutazione IMDb", "Numero Voti"])

# Salvataggio nel CSV locale
def salva_dati(df):
    df.to_csv(DB_FILE, index=False)

# ESTRAZIONE CHIRURGICA BASATA SULL'HTML FORNITO
def recupera_voti_reali_imdb(id_imdb, scraper_api_key):
    url_bersaglio = f"https://www.imdb.com/title/{id_imdb}/"
    url_proxy = f"http://api.scraperapi.com?api_key={scraper_api_key}&url={url_bersaglio}"
    
    try:
        risposta = requests.get(url_proxy, timeout=30)
        if risposta.status_code == 200:
            soup = BeautifulSoup(risposta.text, "html.parser")
            
            titolo = "Titolo Sconosciuto"
            voto = 0.0
            num_voti = 0
            
            # --- METODO PRINCIPALE: METADATI OPEN GRAPH (Infallibile) ---
            meta_title = soup.find("meta", property="og:title")
            if meta_title and meta_title.get("content"):
                content_testo = meta_title["content"]
                
                # Se è presente la stella dei metadati social, separiamo titolo e voto
                if "⭐" in content_testo:
                    parti = content_testo.split(" ⭐ ")
                    titolo = parti[0].strip()
                    try:
                        # Prende la valutazione numerica isolandola dalla barra dei generi
                        voto_estratto = parti[1].split("|")[0].strip()
                        voto = float(voto_estratto)
                    except:
                        pass
                else:
                    # Se non ha ancora un voto numerico (es. film non ancora uscito senza anteprima voti)
                    titolo = content_testo.split(" (")[0].strip()
            
            # --- METODO SECONDARIO: ESTRAZIONE NUMERO VOTI SE PRESENTI ---
            if titolo != "Titolo Sconosciuto":
                # Prova un fallback testuale morbido per cercare stringhe come "14K voti" o "12M votes"
                voti_box = soup.find(string=re.compile(r'^[0-9.,]+[KM]?\s*(voti|votes)?', re.IGNORECASE))
                if voti_box:
                    testo_voti = voti_box.strip().upper()
                    moltiplicatore = 1
                    if "M" in testo_voti: moltiplicatore = 1_000_000
                    elif "K" in testo_voti: moltiplicatore = 1_000
                    
                    testo_voti = re.sub(r'[^\d.]', '', testo_voti.replace(',', '.'))
                    try:
                        num_voti = int(float(testo_voti) * moltiplicatore)
                    except:
                        pass
                
                return {"Titolo": titolo, "Valutazione IMDb": voto, "Numero Voti": num_voti}
                
    except Exception as e:
        print(f"Errore di rete/parsing per ID {id_imdb}: {e}")
        
    return None

# --- INTERFACCIA STREAMLIT ---
st.title("🎬 Tracker IMDb Chirurgico")
st.write("I dati vengono caricati istantaneamente all'avvio. Decidi tu quando aggiornare il singolo film.")

# Caricamento istantaneo (Nessun controllo di rete all'avvio dell'app)
df_film = carica_dati()

# --- AGGIUNTA NUOVO FILM ---
st.subheader("➕ Aggiungi un nuovo film")
link_imdb = st.text_input("Incolla il link o l'ID da IMDb (es. tt30825738):")

if st.button("Aggiungi Film"):
    if link_imdb:
        match = re.search(r'(tt\d+)', link_imdb)
        if match:
            id_estratto = match.group(1)
            
            # Rimuove versioni obsolete dello stesso film se già presenti
            df_film = df_film[df_film['id_imdb'] != id_estratto].reset_index(drop=True)
            
            with st.spinner("Estrazione metadati in corso..."):
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
                    st.success(f"Aggiunto: **{dati_film['Titolo']}** (Voto: {dati_film['Valutazione IMDb']})")
                    st.rerun()
                else:
                    st.error("Errore di estrazione. Verifica l'ID del film o attendi la coda di ScraperAPI.")
        else:
            st.error("Formato ID IMDb non valido.")
    else:
        st.warning("Inserisci un link valido prima di premere invio.")

st.divider()

# --- CLASSIFICA PRINCIPALE ---
st.subheader("📊 Classifica Film")

if df_film.empty:
    st.info("Nessun film in lista. Incolla un link sopra per iniziare!")
else:
    # Mostra il DataFrame pulito e ordinato
    tabella_da_mostrare = df_film[["Titolo", "Valutazione IMDb", "Numero Voti"]].copy()
    tabella_da_mostrare["Numero Voti"] = tabella_da_mostrare["Numero Voti"].map(
        lambda x: f"{int(x):,}".replace(",", ".") if pd.notnull(x) else "0"
    )
    st.dataframe(tabella_da_mostrare, use_container_width=True)
    
    st.divider()
    
    # --- PANNELLO DI GESTIONE CHIRURGICA ---
    st.subheader("⚙️ Gestione e Aggiornamento Manuale")
    st.write("Clicca sul pulsante accanto al singolo film per interrogarlo in tempo reale:")
    
    for index, row in df_film.iterrows():
        col_titolo, col_update, col_delete = st.columns([3, 1, 1])
        
        with col_titolo:
            st.write(f"**{row['Titolo']}** (Attuale: {row['Valutazione IMDb']})")
            
        with col_update:
            if st.button("🔄 Aggiorna", key=f"up_{row['id_imdb']}"):
                with st.spinner(f"Aggiornamento {row['Titolo']}..."):
                    dati_freschi = recupera_voti_reali_imdb(row['id_imdb'], SCRAPER_API_KEY)
                    if dati_freschi:
                        df_film.at[index, 'Valutazione IMDb'] = dati_freschi['Valutazione IMDb']
                        df_film.at[index, 'Numero Voti'] = dati_freschi['Numero Voti']
                        df_film.at[index, 'Titolo'] = dati_freschi['Titolo']
                        df_film = df_film.sort_values(by="Valutazione IMDb", ascending=False).reset_index(drop=True)
                        salva_dati(df_film)
                        st.success("Fatto!")
                        st.rerun()
                    else:
                        st.error("ScraperAPI occupato. Riprova.")
                        
        with col_delete:
            if st.button("❌ Elimina", key=f"del_{row['id_imdb']}"):
                df_film = df_film.drop(index).reset_index(drop=True)
                salva_dati(df_film)
                st.warning("Rimosso.")
                st.rerun()
                        
