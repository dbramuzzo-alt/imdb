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

# ESTRAZIONE AD AMPIO SPETTRO (IMPERMEABILE AGLI ERRORI E AI CAMBIAMENTI)
def recupera_voti_reali_imdb(id_imdb, scraper_api_key):
    url_bersaglio = f"https://www.imdb.com/title/{id_imdb}/"
    url_proxy = f"http://api.scraperapi.com?api_key={scraper_api_key}&url={url_bersaglio}"
    
    headers = {
        "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        risposta = requests.get(url_proxy, headers=headers, timeout=30)
        if risposta.status_code != 200:
            return None
            
        soup = BeautifulSoup(risposta.text, "html.parser")
        testo_completo_pagina = soup.get_text()
        
        # 1. RECUPERO DEL TITOLO (Strategie multiple)
        titolo = "Titolo Sconosciuto"
        
        # Tentativo A: OpenGraph Meta
        meta_title = soup.find("meta", property="og:title")
        if meta_title and meta_title.get("content"):
            content = meta_title["content"]
            titolo = content.split(" ⭐ ")[0].split(" (")[0].strip()
            
        # Tentativo B: Tag h1 standard
        if titolo == "Titolo Sconosciuto" or not titolo:
            h1_tag = soup.find("h1")
            if h1_tag:
                titolo = h1_tag.text.strip()
                
        # Tentativo C: Tag title del browser
        if (titolo == "Titolo Sconosciuto" or not titolo) and soup.title:
            titolo = soup.title.text.replace(" - IMDb", "").strip()

        # 2. RECUPERO DELLA VALUTAZIONE IMDB (Strategie multiple)
        voto = 0.0
        
        # Tentativo A: Sempre dal meta og:title (es: "⭐ 7.0")
        if meta_title and meta_title.get("content") and "⭐" in meta_title["content"]:
            try:
                voto = float(meta_title["content"].split(" ⭐ ")[1].split("|")[0].strip())
            except:
                pass
                
        # Tentativo B: Dal tag grafico ufficiale di IMDb
        if voto == 0.0:
            voto_box = soup.find("div", {"data-testid": "hero-rating-bar__aggregate-rating__score"})
            if voto_box and voto_box.find("span"):
                try:
                    voto = float(voto_box.find("span").text.strip())
                except:
                    pass
                    
        # Tentativo C: Estrazione via regex dal testo grezzo (__NEXT_DATA__ o nodi di testo)
        if voto == 0.0:
            match_voto = re.search(r'"aggregateRating":\s*([0-9.]+)', risposta.text)
            if match_voto:
                try:
                    voto = float(match_voto.group(1))
                except:
                    pass

        # 3. RECUPERO DEL NUMERO DI VOTI (Ricerca testuale aggressiva per stanare il "35K")
        num_voti = 0
        
        # Cerchiamo stringhe nel testo come "35K", "35.123", "35K voti" o "35K votes"
        # Questo pattern intercetta numeri seguiti opzionalmente da K o M e dalle parole chiave dei voti
        matches_voti = re.findall(r'([0-9.,]+)\s*([KM]?)\s*(?:voti|votes|valutazioni|ratings)', testo_completo_pagina, re.IGNORECASE)
        
        if matches_voti:
            for match in matches_voti:
                valore_str = match[0].strip()
                moltiplicatore = match[1].upper().strip()
                
                try:
                    # Puliamo la stringa numerica da virgole o punti usati come separatori
                    valore_str = valore_str.replace(",", ".")
                    valore_float = float(valore_str)
                    
                    if moltiplicatore == "K":
                        num_voti = int(valore_float * 1000)
                    elif moltiplicatore == "M":
                        num_voti = int(valore_float * 1000000)
                    else:
                        num_voti = int(valore_str.replace(".", "").replace(",", ""))
                    
                    if num_voti > 0:
                        break # Abbiamo trovato un contatore valido, usciamo dal ciclo
                except:
                    pass
                    
        # Fallback estremo se la regex testuale fallisce: estrazione dal JSON grezzo se presente
        if num_voti == 0:
            match_json_voti = re.search(r'"voteCount":\s*(\d+)', risposta.text)
            if match_json_voti:
                try:
                    num_voti = int(match_json_voti.group(1))
                except:
                    pass

        # Restituiamo l'oggetto solo se siamo riusciti a identificare almeno il titolo del film
        if titolo != "Titolo Sconosciuto" and titolo:
            return {"Titolo": titolo, "Valutazione IMDb": voto, "Numero Voti": num_voti}
            
    except Exception as e:
        pass
        
    return None

# --- INTERFACCIA STREAMLIT ---
st.title("🎬 Tracker IMDb Chirurgico")
st.write("I dati visivi reali vengono estratti in modo sicuro analizzando l'intera pagina.")

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
            
            with st.spinner("Estrazione e analisi profonda della pagina in corso..."):
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
                    st.error("Errore di estrazione. ScraperAPI non è riuscito a superare le barriere di sicurezza in questo momento o l'ID è errato. Riprova tra pochi istanti.")
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
                        st.error("Errore di risposta del proxy. Riprova.")
                        
        with col_delete:
            if st.button("❌ Elimina", key=f"del_{row['id_imdb']}"):
                df_film = df_film.drop(index).reset_index(drop=True)
                salva_dati(df_film)
                st.warning("Rimosso.")
                st.rerun()
                    
