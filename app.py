import streamlit as st
import pandas as pd
import requests
import os
import re

# --- CONFIGURAZIONE ---
DB_FILE = "film_db.csv"
TMDB_API_KEY = "457bf64e912762e841262d0e74b2839c" # API stabile di backup

def carica_dati():
    if os.path.exists(DB_FILE):
        return pd.read_csv(DB_FILE, dtype={'id_imdb': str})
    return pd.DataFrame(columns=["id_imdb", "Titolo", "Valutazione IMDb", "Numero Voti"])

def salva_dati(df):
    df.to_csv(DB_FILE, index=False)

# Tenta il recupero automatico da TMDB (che non ha blocchi anti-bot)
def recupera_automatico_tmdb(id_imdb):
    try:
        url = f"https://api.themoviedb.org/3/find/{id_imdb}?api_key={TMDB_API_KEY}&external_source=imdb_id&language=it-IT"
        risposta = requests.get(url, timeout=5)
        if risposta.status_code == 200:
            dati = risposta.json()
            risultati = dati.get("movie_results", []) or dati.get("tv_results", [])
            if risultati:
                film = risultati[0]
                voto = float(film.get("vote_average", 0.0))
                voti = int(film.get("vote_count", 0))
                # Se i dati sono validi e non a zero, li prendiamo
                if voto > 0:
                    return {
                        "Titolo": film.get("title") or film.get("name"),
                        "Valutazione IMDb": voto,
                        "Numero Voti": voti
                    }
    except:
        pass
    return None

# --- INTERFACCIA STREAMLIT ---
st.title("🎬 Il mio Tracker di Film IMDb")
st.write("Inserisci i tuoi film senza lo stress dei blocchi dei server!")

df_film = carica_dati()

# --- SEZIONE AGGIUNTA FILM ---
st.subheader("➕ Aggiungi un nuovo film")
link_imdb = st.text_input("Incolla il link o l'ID da IMDb (es. tt30825738):")

if link_imdb:
    match = re.search(r'(tt\d+)', link_imdb)
    if match:
        id_estratto = match.group(1)
        st.info(f"ID Rilevato: **{id_estratto}**")
        
        # 1. Proviamo a fare il recupero automatico di base
        with st.spinner("Verifica database globale in corso..."):
            dati_auto = recupera_automatico_tmdb(id_estratto)
        
        # Prepariamo i campi precompilati se l'automatismo ha trovato qualcosa
        titolo_default = dati_auto["Titolo"] if dati_auto else ""
        voto_default = dati_auto["Valutazione IMDb"] if dati_auto else 0.0
        voti_default = dati_auto["Numero Voti"] if dati_auto else 0
        
        if not dati_auto:
            st.warning("⚠️ I server di IMDb o delle API sono protetti. Inserisci i dati manualmente qui sotto (li trovi guardando la pagina sul telefono):")
        else:
            st.success("✅ Dati trovati automaticamente! Puoi comunque modificarli prima di salvare.")
            
        # Form manuale/di controllo che appare dinamicamente
        with st.form("conferma_film"):
            titolo_inserito = st.text_input("Titolo del Film:", value=titolo_default)
            voto_inserito = st.number_input("Valutazione (es. 7.8):", min_value=0.0, max_value=10.0, value=voto_default, step=0.1)
            voti_inseriti = st.number_input("Numero di Voti:", min_value=0, value=voti_default, step=1)
            
            submit_button = st.form_submit_button("Salva Film in Classifica")
            
            if submit_button:
                if titolo_inserito:
                    # Rimuoviamo il vecchio duplicato se esiste
                    df_film = df_film[df_film['id_imdb'] != id_estratto].reset_index(drop=True)
                    
                    nuovo_film = {
                        "id_imdb": id_estratto,
                        "Titolo": titolo_inserito,
                        "Valutazione IMDb": voto_inserito,
                        "Numero Voti": voti_inseriti
                    }
                    
                    df_film = pd.concat([df_film, pd.DataFrame([nuovo_film])], ignore_index=True)
                    df_film = df_film.sort_values(by="Valutazione IMDb", ascending=False).reset_index(drop=True)
                    salva_dati(df_film)
                    st.success(f"Salvato con successo: **{titolo_inserito}**!")
                    st.rerun()
                else:
                    st.error("Il titolo non può essere vuoto.")
    else:
        st.error("Inserisci un link IMDb valido contenente 'ttXXXXXXX'")

st.divider()

# --- VISUALIZZAZIONE DATI ---
st.subheader("📊 La tua classifica")

if df_film.empty:
    st.info("La tua lista è vuota. Aggiungi il tuo primo film!")
else:
    tabella_da_mostrare = df_film[["Titolo", "Valutazione IMDb", "Numero Voti"]].copy()
    tabella_da_mostrare["Numero Voti"] = tabella_da_mostrare["Numero Voti"].map(
        lambda x: f"{int(x):,}".replace(",", ".") if pd.notnull(x) else "0"
    )
    
    st.dataframe(tabella_da_mostrare, use_container_width=True)
    
    # Rimosso il tasto di aggiornamento di massa automatico per evitare che i vecchi film salvati a mano 
    # vengano sovrascritti da zeri a causa dei blocchi IP di Streamlit.
    
