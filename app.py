import streamlit as st
import pandas as pd
import requests
import os
import re

# --- CONFIGURAZIONE ---
API_KEY = "a5055d8d"
DB_FILE = "film_db.csv"

# Funzione per caricare i dati dal CSV
def carica_dati():
    if os.path.exists(DB_FILE):
        return pd.read_csv(DB_FILE, dtype={'id_imdb': str})
    return pd.DataFrame(columns=["id_imdb", "Titolo", "Valutazione IMDb", "Numero Voti"])

# Funzione per salvare i dati nel CSV
def salva_dati(df):
    df.to_csv(DB_FILE, index=False)

# API DI SOCCORSO: Se OMDb fallisce sui film nuovi/futuri, interviene questa
def recupero_emergenza_imdb(id_imdb):
    try:
        # Usiamo un'API di fallback speculare per i dati grezzi live di IMDb
        url_fallback = f"https://api.themoviedb.org/3/find/{id_imdb}?api_key=apple&external_source=imdb_id&language=it-IT"
        # Tentativo alternativo via worker leggero
        url_alt = f"https://imdb-api.tprojects.workers.dev/title/{id_imdb}"
        risposta = requests.get(url_alt, timeout=5)
        if risposta.status_code == 200:
            dati = risposta.json()
            if dati.get("rating"):
                voto = float(dati.get("rating", 0.0))
                # Estrae solo i numeri dal testo dei voti (es: "2.3K" o "1,500")
                voti_txt = dati.get("ratingCount", "0")
                moltiplicatore = 1
                if "K" in voti_txt: moltiplicatore = 1000
                if "M" in voti_txt: moltiplicatore = 1000000
                voti_puliti = re.sub(r'[^\d.]', '', voti_txt.replace(',', '.'))
                num_voti = int(float(voti_puliti) * moltiplicatore) if voti_puliti else 0
                return voto, num_voti
    except:
        pass
    return None

# Funzione principale per estrarre i dati usando OMDb API + Soccorso Live
def recupera_dati_omdb(id_imdb, api_key):
    url = f"http://www.omdbapi.com/?i={id_imdb}&apikey={api_key}"
    
    try:
        risposta = requests.get(url, timeout=10)
        if risposta.status_code != 200:
            return None
            
        dati = risposta.json()
        
        if dati.get("Response") == "True":
            titolo = dati.get("Title", "Titolo Sconosciuto")
            
            # Estrazione Voto IMDb 
            voto_str = dati.get("imdbRating", "0.0").strip()
            voto = float(voto_str) if voto_str and voto_str != "N/A" else 0.0
            
            # Estrazione Numero Voti
            voti_str = dati.get("imdbVotes", "0").strip()
            if voti_str and voti_str != "N/A":
                voti_puliti = re.sub(r'[^\d]', '', voti_str)
                num_voti = int(voti_puliti) if voti_puliti else 0
            else:
                num_voti = 0
            
            # --- LOGICA DI SOCCORSO ---
            # Se il voto è 0 o N/A (tipico dei film non ancora usciti su OMDb), proviamo il recupero live
            if voto == 0.0 or num_voti == 0:
                dati_soccorso = recupero_emergenza_imdb(id_imdb)
                if dati_soccorso:
                    voto, num_voti = dati_soccorso
            
            return {"Titolo": titolo, "Valutazione IMDb": voto, "Numero Voti": num_voti}
        else:
            # Se OMDb non trova proprio il film, proviamo comunque il soccorso prima di arrenderci
            dati_soccorso = recupero_emergenza_imdb(id_imdb)
            if dati_soccorso:
                return {"Titolo": f"Film ({id_imdb})", "Valutazione IMDb": dati_soccorso[0], "Numero Voti": dati_soccorso[1]}
            return None
    except Exception as e:
        return None

# Funzione per aggiornare la lista completa
def aggiorna_valutazioni(df, api_key):
    if df.empty or not api_key:
        return df
    
    progress_text = "Aggiornamento classifiche in corso..."
    barrita = st.progress(0, text=progress_text)
    
    for index, row in df.iterrows():
        dati_aggiornati = recupera_dati_omdb(row['id_imdb'], api_key)
        if dati_aggiornati:
            df.at[index, 'Valutazione IMDb'] = dati_aggiornati['Valutazione IMDb']
            df.at[index, 'Numero Voti'] = dati_aggiornati['Numero Voti']
            # Evita di sovrascrivere il titolo se il soccorso ha usato un nome generico
            if "Film (tt" not in dati_aggiornati['Titolo']:
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
            df_film = aggiorna_valutazioni(df_film, API_KEY)
    st.session_state["aggiornato"] = True

# --- SEZIONE AGGIUNTA FILM ---
st.subheader("➕ Aggiungi un nuovo film")
link_imdb = st.text_input("Incolla il link o l'ID da IMDb (es. tt0111161):")

if st.button("Aggiungi Film"):
    if link_imdb:
        match = re.search(r'(tt\d+)', link_imdb)
        if match:
            id_estratto = match.group(1)
            
            # Rimuoviamo il vecchio record per aggiornarlo in modo pulito
            df_film = df_film[df_film['id_imdb'] != id_estratto].reset_index(drop=True)
            
            with st.spinner("Recupero informazioni (OMDb + Live Smart)..."):
                dati_film = recupera_dati_omdb(id_estratto, API_KEY)
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
                    st.error("Impossibile recuperare i dettagli del film dal network. Riprova.")
        else:
            st.error("Non ho trovato un ID IMDb valido.")
    else:
        st.warning("Inserisci un link prima di premere il bottone.")

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
            df_film = aggiorna_valutazioni(df_film, API_KEY)
            st.success("Classifica aggiornata!")
            st.rerun()
                
