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

# ESTRAZIONE IBRIDA (STRUTTURATA + VISIVA)
def recupera_voti_reali_imdb(id_imdb, scraper_api_key):
    url_bersaglio = f"https://www.imdb.com/title/{id_imdb}/"
    url_proxy = f"http://api.scraperapi.com?api_key={scraper_api_key}&url={url_bersaglio}"
    
    # Intestazioni per forzare IMDb a mostrare la pagina completa in italiano/occidentale
    headers = {
        "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        risposta = requests.get(url_proxy, headers=headers, timeout=30)
        if risposta.status_code == 200:
            soup = BeautifulSoup(risposta.text, "html.parser")
            
            titolo = "Titolo Sconosciuto"
            voto = 0.0
            num_voti = 0
            
            # 1. ESTRAZIONE TITOLO E VOTO (Da OpenGraph, stabile e sicuro)
            meta_title = soup.find("meta", property="og:title")
            if meta_title and meta_title.get("content"):
                content_testo = meta_title["content"]
                if "⭐" in content_testo:
                    parti = content_testo.split(" ⭐ ")
                    titolo = parti[0].strip()
                    try:
                        voto = float(parti[1].split("|")[0].strip())
                    except:
                        pass
                else:
                    titolo = content_testo.split(" (")[0].strip()
            
            # Se OpenGraph fallisce il titolo, usiamo il tag title standard
            if titolo == "Titolo Sconosciuto" and soup.title:
                titolo = soup.title.text.replace(" - IMDb", "").strip()

            # 2. ESTRAZIONE NUMERO VOTI REALI (Scansione visiva del DOM)
            # Metodo A: Cerca l'elemento con la classe specifica del contatore voti IMDb (es. sc-7ebf4bfc-1 o simili sotto la valutazione)
            voti_elementi = soup.find_all(class_=re.compile(r"(vote-count|rating-count|sc-.*)", re.IGNORECASE))
            
            for elem in voti_elementi:
                testo = elem.get_text().strip().upper()
                # Cerca pattern come "35K", "35.4K", "1.2M", "35.000"
                if re.search(r'\d+\s*[KM]?', testo) and any(x in testo for x in ["VOTI", "VOTES", "K", "M"]):
                    match = re.search(r'([0-9.,]+)\s*([KM]?)', testo)
                    if match:
                        valore_str = match.group(1).replace(",", ".")
                        moltiplicatore = match.group(2)
                        
                        try:
                            valore_float = float(valore_str)
                            if moltiplicatore == "K":
                                num_voti = int(valore_float * 1000)
                            elif moltiplicatore == "M":
                                num_voti = int(valore_float * 1000000)
                            else:
                                # Se è un numero intero formattato con i punti (es. 35.123)
                                num_voti = int(valore_str.replace(".", ""))
                            break # Trovato, usciamo dal ciclo
                        except:
                            pass
            
            # Metodo B: Fallback se non ha trovato nulla (Scansione globale del testo della pagina per "35K votes")
            if num_voti == 0:
                testo_pagina = soup.get_text()
                match_globale = re.search(r'([0-9.,]+[KM]?)\s*(voti|votes)', testo_pagina, re.IGNORECASE)
                if match_globale:
                    stringa_voti = match_globale.group(1).upper()
                    try:
                        if "K" in stringa_voti:
                            num_voti = int(float(stringa_voti.replace("K", "").replace(",", ".")) * 1000)
                        elif "M" in stringa_voti:
                            num_voti = int(float(stringa_voti.replace("M", "").replace(",", ".")) * 1000000)
                        else:
                            num_voti = int(re.sub(r'[^\d]', '', stringa_voti))
                    except:
                        pass
                        
            return {"Titolo": titolo, "Valutazione IMDb": voto, "Numero Voti": num_voti}

    except Exception as e:
        print(f"Errore di estrazione: {e}")
        
    return None

# --- INTERFACCIA STREAMLIT ---
st.title("🎬 Tracker IMDb Chirurgico")
st.write("I dati visivi reali vengono estratti direttamente dalle metriche della pagina.")

df_film = carica_dati()

# --- AGGIUNTA NUOVO FILM ---
st.subheader("➕ Aggiungi un nuovo film")
link_imdb = st.text_input("Incolla il link o l'ID da IMDb (es. tt30825738):")

if st.button("Aggiungi Film"):
    if link_imdb:
        match = re.search(r'(tt\d+)', link_imdb)
        if match:
            id_estratto = match.group(1)
            df_film = df_film[df_film['id_imdb'] != id_estratto].reset_index(drop=True)
            
            with st.spinner("Estrazione metadati e voti reali in corso..."):
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
                    st.success(f"Aggiunto: **{dati_film['Titolo']}** (Voto: {dati_film['Valutazione IMDb']}, Voti: {dati_film['Numero Voti']:,})")
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
    tabella_da_mostrare = df_film[["Titolo", "Valutazione IMDb", "Numero Voti"]].copy()
    tabella_da_mostrare["Numero Voti"] = tabella_da_mostrare["Numero Voti"].map(
        lambda x: f"{int(x):,}".replace(",", ".") if pd.notnull(x) else "0"
    )
    st.dataframe(tabella_da_mostrare, use_container_width=True)
    
    st.divider()
    
    # --- PANNELLO DI GESTIONE CHIRURGICA ---
    st.subheader("⚙️ Gestione e Aggiornamento Manuale")
    
    for index, row in df_film.iterrows():
        col_titolo, col_update, col_delete = st.columns([3, 1, 1])
        
        with col_titolo:
            st.write(f"**{row['Titolo']}** (Voto: {row['Valutazione IMDb']} | Voti: {int(row['Numero Voti']):,})")
            
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
                        st.error("Errore di risposta. Riprova.")
                        
        with col_delete:
            if st.button("❌ Elimina", key=f"del_{row['id_imdb']}"):
                df_film = df_film.drop(index).reset_index(drop=True)
                salva_dati(df_film)
                st.warning("Rimosso.")
                st.rerun()
                                                 
