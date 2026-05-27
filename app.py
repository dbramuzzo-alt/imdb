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

# Funzione per caricare i dati dal CSV
def carica_dati():
    if os.path.exists(DB_FILE):
        return pd.read_csv(DB_FILE, dtype={'id_imdb': str})
    return pd.DataFrame(columns=["id_imdb", "Titolo", "Valutazione IMDb", "Numero Voti"])

# Funzione per salvare i dati nel CSV
def salva_dati(df):
    df.to_csv(DB_FILE, index=False)

# Funzione di estrazione basata sull'HTML reale di IMDb
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
            
            # METODO 1: METADATI OPEN GRAPH
            meta_title = soup.find("meta", property="og:title")
            if meta_title and meta_title.get("content"):
                content_testo = meta_title["content"]
                if "⭐" in content_testo:
                    parti = content_testo.split(" ⭐ ")
                    titolo = parti[0].strip()
                    try:
                        voto_estratto = parti[1].split("|")[0].strip()
                        voto = float(voto_estratto)
                    except:
                        pass
                else:
                    titolo = content_testo.split(" (")[0].strip()
            
            # Estrazione Numero Voti (dal JSON-LD interno o dall'HTML)
            if titolo != "Titolo Sconosciuto":
                script_tag = soup.find("script", type="application/ld+json")
                if script_tag:
                    try:
                        dati_json = json.loads(script_tag.string)
                        aggregate_rating = dati_json.get("aggregateRating", {})
                        if aggregate_rating:
                            num_voti = int(aggregate_rating.get("ratingCount", 0))
                    except:
                        pass
                
                if num_voti == 0:
                    voti_box = soup.find("div", string=re.compile(r'^[0-9.,]+[KM]?\s*(voti|votes)?', re.IGNORECASE))
                    if voti_box:
                        testo_voti = voti_box.text.strip().upper()
                        moltiplicatore = 1
                        if "M" in testo_voti: moltiplicatore = 1_000_000
                        elif "K" in testo_voti: moltiplicatore = 1_000
                        
                        testo_voti = re.sub(r'[^\d.]', '', testo_voti.replace(',', '.'))
                        try:
                            num_voti = int(float(testo_voti) * moltiplicatore)
                        except:
                            pass
                            
                return {"Titolo": titolo, "Valutazione IMDb": voto, "Numero Voti": num_voti}
    except:
        pass
    return None

# --- INTERFACCIA STREAMLIT ---
st.title("🎬 Tracker Ufficiale IMDb")
st.write("Aggiungi i tuoi film e gestisci gli aggiornamenti in modo manuale e mirato.")

# Carichiamo i dati (L'aggiornamento automatico all'avvio è stato COMPLETAMENTE rimosso)
df_film = carica_dati()

# --- SEZIONE AGGIUNTA FILM ---
st.subheader("➕ Aggiungi un nuovo film")
link_imdb = st.text_input("Incolla il link o l'ID da IMDb (es. tt30825738):")

if st.button("Aggiungi Film"):
    if link_imdb:
        match = re.search(r'(tt\d+)', link_imdb)
        if match:
            id_estratto = match.group(1)
            
            # Rimuoviamo eventuali vecchi record duplicati prima dell'inserimento
            df_film = df_film[df_film['id_imdb'] != id_estratto].reset_index(drop=True)
            
            with st.spinner("Estrazione dati da IMDb in corso..."):
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
                    st.success(f"Aggiunto: **{dati_film['Titolo']}** (Voto: {dati_film['Valutazione IMDb']}, Voti: {dati_film['Numero Voti']})")
                    st.rerun()
                else:
                    st.error("Errore di estrazione. Verifica l'ID o riprova tra un istante.")
        else:
            st.error("ID IMDb non valido.")
    else:
        st.warning("Inserisci un link.")

st.divider()

# --- VISUALIZZAZIONE DATI ---
st.subheader("📊 Classifica Film")

if df_film.empty:
    st.info("La tua lista è vuota. Aggiungi il tuo primo film qui sopra!")
else:
    # 1. Mostra la tabella ordinata delle valutazioni
    tabella_da_mostrare = df_film[["Titolo", "Valutazione IMDb", "Numero Voti"]].copy()
    tabella_da_mostrare["Numero Voti"] = tabella_da_mostrare["Numero Voti"].map(
        lambda x: f"{int(x):,}".replace(",", ".") if pd.notnull(x) else "0"
    )
    st.dataframe(tabella_da_mostrare, use_container_width=True)
    
    st.divider()
    
    # 2. Sezione Pannello di Controllo Singolo Film
    st.subheader("⚙️ Azioni Veloci per Singolo Film")
    st.write("Usa i pulsanti qui sotto per aggiornare i dati o eliminare un titolo specifico senza attendere il caricamento globale.")
    
    for index, row in df_film.iterrows():
        # Creiamo 3 colonne visive: Titolo del film, Bottone Aggiorna, Bottone Elimina
        col_titolo, col_update, col_delete = st.columns([3, 1, 1])
        
        with col_titolo:
            st.write(f"**{row['Titolo']}** (Voto: {row['Valutazione IMDb']})")
            
        with col_update:
            # Generiamo una chiave unica per ogni bottone basata sull'ID IMDb
            if st.button("🔄 Aggiorna", key=f"up_{row['id_imdb']}"):
                with st.spinner(f"Aggiornamento {row['Titolo']}..."):
                    dati_freschi = recupera_voti_reali_imdb(row['id_imdb'], SCRAPER_API_KEY)
                    if dati_freschi:
                        df_film.at[index, 'Valutazione IMDb'] = dati_freschi['Valutazione IMDb']
                        df_film.at[index, 'Numero Voti'] = dati_freschi['Numero Voti']
                        df_film.at[index, 'Titolo'] = dati_freschi['Titolo']
                        # Ordina nuovamente la lista globale dopo l'aggiornamento del singolo voto
                        df_film = df_film.sort_values(by="Valutazione IMDb", ascending=False).reset_index(drop=True)
                        salva_dati(df_film)
                        st.success(f"Aggiornato!")
                        st.rerun()
                    else:
                        st.error("Impossibile aggiornare questo titolo.")
                        
        with col_delete:
            if st.button("❌ Elimina", key=f"del_{row['id_imdb']}"):
                df_film = df_film.drop(index).reset_index(drop=True)
                salva_dati(df_film)
                st.warning("Film rimosso!")
                st.rerun()
                                   
