import streamlit as st
import pandas as pd
import requests
import json
import os
import re
from datetime import datetime

# --- CONFIGURAZIONE ---
DB_FILE = "film_db.csv"

# Caricamento sicuro del CSV locale (istantaneo all'avvio)
def carica_dati():
    if os.path.exists(DB_FILE):
        return pd.read_csv(DB_FILE, dtype={'id_imdb': str})
    # Se il file non esiste, creiamo la struttura includendo la nuova colonna temporale
    return pd.DataFrame(columns=["id_imdb", "Titolo", "Valutazione IMDb", "Numero Voti", "Ultimo Aggiornamento"])

# Salvataggio nel CSV locale
def salva_dati(df):
    df.to_csv(DB_FILE, index=False)

# Sfrutta le API GraphQL native di IMDb (Simula App Mobile)
def recupera_voti_reali_imdb(id_imdb):
    url = "https://api.graphql.imdb.com/"
    
    query_graphql = {
        "query": """
        query GetMovieRating($id: ID!) {
          title(id: $id) {
            originalTitleText {
              text
            }
            ratingsSummary {
              aggregateRating
              voteCount
            }
          }
        }
        """,
        "variables": {"id": id_imdb}
    }
    
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"
    }
    
    try:
        risposta = requests.post(url, json=query_graphql, headers=headers, timeout=15)
        if risposta.status_code == 200:
            risposta_json = risposta.json()
            data = risposta_json.get("data", {})
            title_data = data.get("title") if data else None
            
            if title_data:
                titolo = title_data.get("originalTitleText", {}).get("text", "Titolo Sconosciuto")
                ratings = title_data.get("ratingsSummary", {})
                
                voto = ratings.get("aggregateRating", 0.0) if ratings else 0.0
                voti = ratings.get("voteCount", 0) if ratings else 0
                
                return {"Titolo": titolo, "Valutazione IMDb": voto, "Numero Voti": voti}
    except Exception as e:
        pass
    return None

# --- INTERFACCIA STREAMLIT ---
st.title("🎬 Classifica Film - IMDb Tracker")
st.write("I film sono ordinati in base al numero di voti complessivi ricevuti su IMDb.")

# Carichiamo i dati subito (velocissimo, legge solo il file locale)
df_film = carica_dati()

# Se nel vecchio database non esiste la colonna dei timestamp, la creiamo al volo compilando con stringhe vuote
if "Ultimo Aggiornamento" not in df_film.columns:
    df_film["Ultimo Aggiornamento"] = ""

# --- SEZIONE AGGIUNTA FILM ---
st.subheader("➕ Aggiungi un nuovo film")
link_imdb = st.text_input("Incolla il link o l'ID completo da IMDb (es. tt30825738):")

if st.button("Aggiungi Film"):
    if link_imdb:
        match = re.search(r'(tt\d+)', link_imdb)
        if match:
            id_estratto = match.group(1)
            
            # Rimuove versioni obsolete dello stesso film se già in lista
            df_film = df_film[df_film['id_imdb'] != id_estratto].reset_index(drop=True)
            
            with st.spinner("Interrogazione database IMDb..."):
                dati_film = recupera_voti_reali_imdb(id_estratto)
                if dati_film:
                    # Cattura il momento esatto in formato Giorno/Mese/Anno Ore:Minuti
                    ora_attuale = datetime.now().strftime("%d/%m/%Y %H:%M")
                    
                    nuovo_film = {
                        "id_imdb": id_estratto,
                        "Titolo": dati_film["Titolo"],
                        "Valutazione IMDb": dati_film["Valutazione IMDb"],
                        "Numero Voti": dati_film["Numero Voti"],
                        "Ultimo Aggiornamento": ora_attuale
                    }
                    df_film = pd.concat([df_film, pd.DataFrame([nuovo_film])], ignore_index=True)
                    
                    # MODIFICA: Ordina la classifica per NUMERO VOTI (Decrescente)
                    df_film = df_film.sort_values(by="Numero Voti", ascending=False).reset_index(drop=True)
                    salva_dati(df_film)
                    st.success(f"Aggiunto: **{dati_film['Titolo']}** (Voto: {dati_film['Valutazione IMDb']} | Voti: {dati_film['Numero Voti']:,})")
                    st.rerun()
                else:
                    st.error("Impossibile recuperare i dati. Verifica l'ID o riprova.")
        else:
            st.error("Formato ID IMDb non valido (deve contenere 'tt' seguito dai numeri).")
    else:
        st.warning("Inserisci un link prima di premere il pulsante.")

st.divider()

# --- CLASSIFICA PRINCIPALE ---
st.subheader("📊 Classifica Generale (Ordinata per Numero Voti)")

if df_film.empty:
    st.info("La tua lista è vuota. Incolla un link qui sopra per iniziare!")
else:
    # Mostra la tabella formattata, includendo la colonna dell'ultimo aggiornamento
    tabella_da_mostrare = df_film[["Titolo", "Valutazione IMDb", "Numero Voti", "Ultimo Aggiornamento"]].copy()
    tabella_da_mostrare["Numero Voti"] = tabella_da_mostrare["Numero Voti"].map(
        lambda x: f"{int(x):,}".replace(",", ".") if pd.notnull(x) else "0"
    )
    # Riempie eventuali celle vuote con un valore di default testuale
    tabella_da_mostrare["Ultimo Aggiornamento"] = tabella_da_mostrare["Ultimo Aggiornamento"].fillna("N/D")
    
    st.dataframe(tabella_da_mostrare, use_container_width=True)
    
    st.divider()
    
    # --- PANNELLO DI GESTIONE CHIRURGICA ---
    st.subheader("⚙️ Gestione e Aggiornamenti Manuali")
    st.write("Aggiorna i dati o elimina i titoli singolarmente quando vuoi:")
    
    for index, row in df_film.iterrows():
        col_titolo, col_update, col_delete = st.columns([3, 1, 1])
        
        # Gestione elegante della stringa temporale per i vecchi dati
        data_mostrata = row['Ultimo Aggiornamento'] if pd.notnull(row['Ultimo Aggiornamento']) and row['Ultimo Aggiornamento'] != "" else "N/D"
        
        with col_titolo:
            st.write(f"**{row['Titolo']}**")
            st.caption(f"Voto: {row['Valutazione IMDb']} | Voti: {int(row['Numero Voti']):,} | *Aggiornato il: {data_mostrata}*")
            
        with col_update:
            if st.button("🔄 Aggiorna", key=f"up_{row['id_imdb']}"):
                with st.spinner(f"Aggiornamento {row['Titolo']}..."):
                    dati_freschi = recupera_voti_reali_imdb(row['id_imdb'])
                    if dati_freschi:
                        # Sovrascrive i dati e cattura il nuovo timestamp di aggiornamento
                        ora_attuale = datetime.now().strftime("%d/%m/%Y %H:%M")
                        
                        df_film.at[index, 'Valutazione IMDb'] = dati_freschi['Valutazione IMDb']
                        df_film.at[index, 'Numero Voti'] = dati_freschi['Numero Voti']
                        df_film.at[index, 'Titolo'] = dati_freschi['Titolo']
                        df_film.at[index, 'Ultimo Aggiornamento'] = ora_attuale
                        
                        # MODIFICA: Riordina la classifica per NUMERO VOTI (Decrescente)
                        df_film = df_film.sort_values(by="Numero Voti", ascending=False).reset_index(drop=True)
                        salva_dati(df_film)
                        st.success("Aggiornato!")
                        st.rerun()
                    else:
                        st.error("Errore di connessione.")
                        
        with col_delete:
            if st.button("❌ Elimina", key=f"del_{row['id_imdb']}"):
                df_film = df_film.drop(index).reset_index(drop=True)
                salva_dati(df_film)
                st.warning("Film rimosso.")
                st.rerun()
        
