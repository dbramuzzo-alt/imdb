import streamlit as st
import pandas as pd
from imdb import Cinemagoer
import os

# Inizializziamo Cinemagoer per connetterci a IMDb
ia = Cinemagoer()

# Nome del file dove salveremo i film
DB_FILE = "film_db.csv"

# Funzione per caricare i dati dal CSV
def carica_dati():
    if os.path.exists(DB_FILE):
        return pd.read_csv(DB_FILE, dtype={'id_imdb': str})
    return pd.DataFrame(columns=["id_imdb", "Titolo", "Valutazione IMDb", "Numero Voti"])

# Funzione per salvare i dati nel CSV
def salva_dati(df):
    df.to_csv(DB_FILE, index=False)

# Funzione per aggiornare i dati da IMDb
def aggiorna_valutazioni(df):
    if df.empty:
        return df
    
    progress_text = "Aggiornamento valutazioni in corso..."
    barrita = st.progress(0, text=progress_text)
    
    for index, row in df.iterrows():
        try:
            # Recuperiamo il film usando il suo ID IMDb
            movie = ia.get_movie(row['id_imdb'])
            
            # Aggiorniamo voto e numero di voti
            df.at[index, 'Valutazione IMDb'] = movie.get('rating', 0.0)
            df.at[index, 'Numero Voti'] = movie.get('votes', 0)
            df.at[index, 'Titolo'] = movie.get('title', row['Titolo'])
        except Exception as e:
            st.warning(f"Impossibile aggiornare il film con ID {row['id_imdb']}: {e}")
        
        # Aggiorna la barra di progresso
        barrita.progress((index + 1) / len(df), text=progress_text)
    
    barrita.empty()
    # Ordina i film per valutazione (dal più alto al più basso)
    df = df.sort_values(by="Valutazione IMDb", ascending=False).reset_index(drop=True)
    salva_dati(df)
    return df

# --- INTERFACCIA STREAMLIT ---
st.title("🎬 Il mio Tracker di Film IMDb")
st.write("Inserisci i tuoi film e tieni traccia delle loro valutazioni in tempo reale!")

# Carica il database all'avvio
df_film = carica_dati()

# Esegui l'aggiornamento automatico all'avvio se il database non è vuoto
if "aggiornato" not in st.session_state:
    if not df_film.empty:
        with st.spinner("Aggiornamento dati da IMDb all'avvio..."):
            df_film = aggiorna_valutazioni(df_film)
    st.session_state["aggiornato"] = True

# --- SEZIONE AGGIUNTA FILM ---
st.subheader("➕ Aggiungi un nuovo film")
link_imdb = st.text_input("Incolla il link del film su IMDb o direttamente l'ID (es. tt0111161):")

if st.button("Aggiungi Film"):
    if link_imdb:
        # Estraiamo l'ID dal link (es. se inserisce https://www.imdb.com/title/tt0111161/ prende tt0111161)
        id_estratto = "".join(filter(str.isdigit, link_imdb))
        
        if id_estratto:
            if id_estratto in df_film['id_imdb'].values:
                st.info("Questo film è già presente nella tua lista!")
            else:
                with st.spinner("Cercando il film su IMDb..."):
                    try:
                        movie = ia.get_movie(id_estratto)
                        nuovo_film = {
                            "id_imdb": id_estratto,
                            "Titolo": movie.get('title', 'Sconosciuto'),
                            "Valutazione IMDb": movie.get('rating', 0.0),
                            "Numero Voti": movie.get('votes', 0)
                        }
                        # Aggiungiamo il film al DataFrame
                        df_film = pd.concat([df_film, pd.DataFrame([nuovo_film])], ignore_index=True)
                        # Riordiniamo subito
                        df_film = df_film.sort_values(by="Valutazione IMDb", ascending=False).reset_index(drop=True)
                        salva_dati(df_film)
                        st.success(f"Aggiunto con successo: **{movie.get('title')}**!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Errore nel recupero del film. Controlla il link/ID. Dettaglio: {e}")
        else:
            st.error("Non sono riuscito a trovare un ID valido nel testo inserito.")
    else:
        st.warning("Inserisci un link o un ID prima di premere il bottone.")

# Linea di separazione visiva corretta in Streamlit
st.divider()

# --- VISUALIZZAZIONE DATI ---
st.subheader("📊 La tua classifica")

if df_film.empty:
    st.info("La tua lista è vuota. Aggiungi il tuo primo film qui sopra!")
else:
    # Mostriamo una versione pulita della tabella
    tabella_da_mostrare = df_film[["Titolo", "Valutazione IMDb", "Numero Voti"]].copy()
    
    # Formattiamo il numero di voti per renderlo più leggibile
    tabella_da_mostrare["Numero Voti"] = tabella_da_mostrare["Numero Voti"].map(lambda x: f"{int(x):,}".replace(",", "."))
    
    st.dataframe(tabella_da_mostrare, use_container_width=True)
    
    # Bottone per aggiornare manualmente
    if st.button("🔄 Forza Aggiornamento Ora"):
        with st.spinner("Aggiornamento in corso..."):
            df_film = aggiorna_valutazioni(df_film)
            st.success("Classifica aggiornata!")
            st.rerun()
    
