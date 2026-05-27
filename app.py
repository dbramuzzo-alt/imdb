import streamlit as st
import pandas as pd
import requests
import os
import re

# --- CONFIGURAZIONE CHIAVI ---
OMDB_API_KEY = "a5055d8d"
TMDB_API_KEY = "457bf64e912762e841262d0e74b2839c"  # Chiave di soccorso TMDB integrata
DB_FILE = "film_db.csv"

# Funzione per caricare i dati dal CSV
def carica_dati():
    if os.path.exists(DB_FILE):
        return pd.read_csv(DB_FILE, dtype={'id_imdb': str})
    return pd.DataFrame(columns=["id_imdb", "Titolo", "Valutazione IMDb", "Numero Voti"])

# Funzione per salvare i dati nel CSV
def salva_dati(df):
    df.to_csv(DB_FILE, index=False)

# API DI SOCCORSO TMDB: Interroga i server di TheMovieDB usando l'ID di IMDb
def recupero_emergenza_tmdb(id_imdb):
    try:
        # Cerchiamo il film su TMDB usando l'ID di IMDb (external_source)
        url = f"https://api.themoviedb.org/3/find/{id_imdb}?api_key={TMDB_API_KEY}&external_source=imdb_id&language=it-IT"
        risposta = requests.get(url, timeout=5)
        if risposta.status_code == 200:
            dati = risposta.json()
            
            # TMDB divide i risultati in categorie. Controlliamo i film (movie_results)
            risultati = dati.get("movie_results", [])
            if not risultati:
                # Se non è nei film, controlliamo se è registrato come serie o show (tv_results)
                risultati = dati.get("tv_results", [])
                
            if risultati:
                film_tmdb = risultati[0]
                titolo = film_tmdb.get("title") or film_tmdb.get("name") or "Titolo Sconosciuto"
                voto = float(film_tmdb.get("vote_average", 0.0))
                num_voti = int(film_tmdb.get("vote_count", 0))
                return {"Titolo": titolo, "Valutazione IMDb": voto, "Numero Voti": num_voti}
    except Exception as e:
        pass
    return None

# Funzione principale per estrarre i dati
def recupera_dati_film(id_imdb):
    # 1. Proviamo prima con l'API principale OMDb
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
                
                # Se OMDb ha funzionato e ha i voti, restituiamo questi dati
                if voto > 0.0 and num_voti > 0:
                    return {"Titolo": dati.get("Title"), "Valutazione IMDb": voto, "Numero Voti": num_voti}
    except:
        pass

    # 2. Se OMDb ha restituito 0 voti o è andata in errore, attiviamo il Soccorso TMDB
    dati_soccorso = recupero_emergenza_tmdb(id_imdb)
    if dati_soccorso:
        return dati_soccorso
        
    return None

# Funzione per aggiornare la lista completa
def aggiorna_valutazioni(df):
    if df.empty:
        return df
    
    progress_text = "Aggiornamento valutazioni in corso..."
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
st.write("Inserisci i tuoi film e tieni traccia delle loro valutazioni senza blocchi!")

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
            
            # Rimuoviamo il vecchio record se presente, per sovrascriverlo con i dati freschi
            df_film = df_film[df_film['id_imdb'] != id_estratto].reset_index(drop=True)
            
            with st.spinner("Recupero informazioni dal database globale..."):
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
                    st.error("Impossibile trovare il film. Verifica l'ID inserito.")
        else:
            st.error("Non ho trovato un ID IMDb valido.")
    else:
        st.warning("Inserisci un link o un ID prima di premere il bottone.")

st.divider()

# --- VISUALIZZAZIONE DATI ---
st.subheader("📊 La tua classifica")

if df_film.empty:
    st.info("La tua lista è vuota. Aggiungi il tuo primo film qui sopra!")
else:
    tabella_da_mostrare = df_film[["Titolo", "Valutazione IMDb", "Numero Voti"]].copy()
    
    # Formattazione sicura del numero di voti
    tabella_da_mostrare["Numero Voti"] = tabella_da_mostrare["Numero Voti"].map(
        lambda x: f"{int(x):,}".replace(",", ".") if pd.notnull(x) else "0"
    )
    
    st.dataframe(tabella_da_mostrare, use_container_width=True)
    
    if st.button("🔄 Forza Aggiornamento Ora"):
        with st.spinner("Aggiornamento in corso..."):
            df_film = aggiorna_valutazioni(df_film)
            st.success("Classifica aggiornata!")
            st.rerun()
                        
