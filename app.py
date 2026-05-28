import streamlit as st
import pandas as pd
import requests
import json
import os
import re
from datetime import datetime
import urllib.parse
from github import Github, GithubException
import io

# --- CONFIGURAZIONE GITHUB ---
# ⚠️ SOSTITUISCI CON IL TUO USERNAME E NOME REPOSITORY (es. "mario-rossi/imdb-tracker")
REPO_NAME = "dbramuzzo-alt/imdb" 
DB_FILE = "film_db.csv"
DB_FUTURI_FILE = "film_futuri_db.csv"

# Recupero del Token dai Secrets di Streamlit
if "GITHUB_TOKEN" not in st.secrets:
    st.error("Errore: GITHUB_TOKEN non trovato nei Secrets di Streamlit!")
    st.stop()

GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]

# Inizializzazione client GitHub
try:
    g = Github(GITHUB_TOKEN)
    repo = g.get_repo(REPO_NAME)
except Exception as e:
    st.error(f"Impossibile connettersi a GitHub. Verifica il Token e il nome del repository. Errore: {e}")
    st.stop()

# --- FUNZIONI DI CARICAMENTO E SALVATAGGIO DA GITHUB ---
def carica_da_github(file_path, colonne_default, dtypes=None):
    try:
        file_content = repo.get_contents(file_path)
        csv_data = file_content.decoded_content.decode('utf-8')
        return pd.read_csv(io.StringIO(csv_data), dtype=dtypes)
    except GithubException as e:
        if e.status == 404:
            # Se il file non esiste sul repository, ritorna un dataframe vuoto con le colonne corrette
            return pd.DataFrame(columns=colonne_default)
        else:
            st.error(f"Errore GitHub nel caricamento di {file_path}: {e}")
            return pd.DataFrame(columns=colonne_default)

def salva_su_github(df, file_path, commit_message):
    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False)
    content_to_upload = csv_buffer.getvalue()
    
    try:
        # Cerca il file per ottenere il suo SHA (necessario per sovrascriverlo)
        file_contents = repo.get_contents(file_path)
        repo.update_file(
            path=file_path,
            message=commit_message,
            content=content_to_upload,
            sha=file_contents.sha
        )
    except GithubException as e:
        if e.status == 404:
            # Se il file non esiste ancora su GitHub, lo crea
            repo.create_file(
                path=file_path,
                message=commit_message,
                content=content_to_upload
            )
        else:
            st.error(f"Errore GitHub nel salvataggio di {file_path}: {e}")

# Interfacce per il vecchio schema di funzioni dello script
def carica_dati():
    return carica_da_github(DB_FILE, ["id_imdb", "Titolo", "Valutazione IMDb", "Numero Voti", "Ultimo Aggiornamento"], {'id_imdb': str})

def carica_dati_futuri():
    return carica_da_github(DB_FUTURI_FILE, ["Titolo", "Anno Presunto", "Note"], str)

def salva_dati(df):
    salva_su_github(df, DB_FILE, "Aggiornato database film esistenti [Streamlit]")

def salva_dati_futuri(df):
    salva_su_github(df, DB_FUTURI_FILE, "Aggiornato database film futuri [Streamlit]")


# --- RECUPERO DATI IMDB (GRAPHQL) ---
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
st.title("🎬 Classifica Film - IMDb Tracker (GitHub Cloud)")

# Caricamento dinamico dei database da GitHub
df_film = carica_dati()
df_futuri = carica_dati_futuri()

if "Ultimo Aggiornamento" not in df_film.columns:
    df_film["Ultimo Aggiornamento"] = ""

# --- CREAZIONE DELLE SCHEDE (TABS) ---
tab1, tab2 = st.tabs(["📊 Classifica Film (Con ID)", "📌 Promemoria Film Futuri (Senza ID)"])

# ==========================================
# SCHEDA 1: CLASSIFICA FILM ESISTENTI
# ==========================================
with tab1:
    st.subheader("➕ Aggiungi un film esistente")
    link_imdb = st.text_input("Incolla il link o l'ID completo da IMDb (es. tt30825738):", key="add_exist")

    col_btn1, col_btn2 = st.columns([1, 1])

    with col_btn1:
        if st.button("Aggiungi Film", use_container_width=True):
            if link_imdb:
                match = re.search(r'(tt\d+)', link_imdb)
                if match:
                    id_estratto = match.group(1)
                    df_film = df_film[df_film['id_imdb'] != id_estratto].reset_index(drop=True)
                    
                    with st.spinner("Interrogazione database IMDb e sincronizzazione GitHub..."):
                        dati_film = recupera_voti_reali_imdb(id_estratto)
                        if dati_film:
                            ora_attuale = datetime.now().strftime("%d/%m/%Y %H:%M")
                            nuovo_film = {
                                "id_imdb": id_estratto,
                                "Titolo": dati_film["Titolo"],
                                "Valutazione IMDb": dati_film["Valutazione IMDb"],
                                "Numero Voti": dati_film["Numero Voti"],
                                "Ultimo Aggiornamento": ora_attuale
                            }
                            df_film = pd.concat([df_film, pd.DataFrame([nuovo_film])], ignore_index=True)
                            df_film = df_film.sort_values(by="Numero Voti", ascending=False).reset_index(drop=True)
                            salva_dati(df_film)
                            st.success(f"Aggiunto e salvato su GitHub: **{dati_film['Titolo']}**")
                            st.rerun()
                        else:
                            st.error("Impossibile recuperare i dati. Verifica l'ID o riprova.")
                else:
                    st.error("Formato ID IMDb non valido (es. tt30825738).")
            else:
                st.warning("Inserisci un link prima di premere il pulsante.")

    with col_btn2:
        if st.button("🔄 Aggiorna Tutta la Classifica", use_container_width=True):
            if df_film.empty:
                st.warning("La lista è vuota, non c'è nulla da aggiornare!")
            else:
                progress_bar = st.progress(0)
                totale_film = len(df_film)
                
                with st.spinner("Aggiornamento globale e push su GitHub in corso..."):
                    for index, row in df_film.iterrows():
                        dati_freschi = recupera_voti_reali_imdb(row['id_imdb'])
                        if dati_freschi:
                            ora_attuale = datetime.now().strftime("%d/%m/%Y %H:%M")
                            df_film.at[index, 'Valutazione IMDb'] = dati_freschi['Valutazione IMDb']
                            df_film.at[index, 'Numero Voti'] = dati_freschi['Numero Voti']
                            df_film.at[index, 'Titolo'] = dati_freschi['Titolo']
                            df_film.at[index, 'Ultimo Aggiornamento'] = ora_attuale
                        progress_bar.progress((index + 1) / totale_film)
                    
                    df_film = df_film.sort_values(by="Numero Voti", ascending=False).reset_index(drop=True)
                    salva_dati(df_film)
                    st.success("Tutti i film sono stati aggiornati e salvati su GitHub!")
                    st.rerun()

    st.divider()

    st.subheader("📊 Classifica Generale (Ordinata per Numero Voti)")
    if df_film.empty:
        st.info("La tua lista è vuota. Incolla un link qui sopra per iniziare!")
    else:
        tabella_da_mostrare = df_film[["id_imdb", "Titolo", "Valutazione IMDb", "Numero Voti", "Ultimo Aggiornamento"]].copy()
        tabella_da_mostrare.columns = ["ID IMDb", "Titolo", "Valutazione IMDb", "Numero Voti", "Ultimo Aggiornamento"]
        tabella_da_mostrare["Numero Voti"] = tabella_da_mostrare["Numero Voti"].map(
            lambda x: f"{int(x):,}".replace(",", ".") if pd.notnull(x) else "0"
        )
        tabella_da_mostrare["Ultimo Aggiornamento"] = tabella_da_mostrare["Ultimo Aggiornamento"].fillna("N/D")
        st.dataframe(tabella_da_mostrare, use_container_width=True)
        
        st.divider()
        st.subheader("⚙️ Gestione e Aggiornamenti Manuali")
        
        for index, row in df_film.iterrows():
            col_titolo, col_update, col_delete = st.columns([3, 1, 1])
            data_mostrata = row['Ultimo Aggiornamento'] if pd.notnull(row['Ultimo Aggiornamento']) and row['Ultimo Aggiornamento'] != "" else "N/D"
            
            with col_titolo:
                st.write(f"**{row['Titolo']}** `({row['id_imdb']})`")
                st.caption(f"Voto: {row['Valutazione IMDb']} | Voti: {int(row['Numero Voti']):,} | *Aggiornato: {data_mostrata}*")
                
            with col_update:
                if st.button("🔄 Aggiorna", key=f"up_{row['id_imdb']}"):
                    with st.spinner(f"Aggiornamento {row['id_imdb']}..."):
                        dati_freschi = recupera_voti_reali_imdb(row['id_imdb'])
                        if dati_freschi:
                            ora_attuale = datetime.now().strftime("%d/%m/%Y %H:%M")
                            df_film.at[index, 'Valutazione IMDb'] = dati_freschi['Valutazione IMDb']
                            df_film.at[index, 'Numero Voti'] = dati_freschi['Numero Voti']
                            df_film.at[index, 'Titolo'] = dati_freschi['Titolo']
                            df_film.at[index, 'Ultimo Aggiornamento'] = ora_attuale
                            df_film = df_film.sort_values(by="Numero Voti", ascending=False).reset_index(drop=True)
                            salva_dati(df_film)
                            st.success("Fatto!")
                            st.rerun()
                        else:
                            st.error("Errore di connessione.")
                            
            with col_delete:
                if st.button("❌ Elimina", key=f"del_{row['id_imdb']}"):
                    df_film = df_film.drop(index).reset_index(drop=True)
                    salva_dati(df_film)
                    st.warning("Film rimosso da GitHub.")
                    st.rerun()

# ==========================================
# SCHEDA 2: SEZIONE PROMEMORIA FILM FUTURI
# ==========================================
with tab2:
    st.subheader("📌 Promemoria Nuovi Film (Senza ancora una scheda IMDb)")
    st.write("Usa questa sezione per annotare i film appena annunciati che vuoi tenere d'occhio.")
    
    with st.form("form_film_futuro", clear_on_submit=True):
        f_titolo = st.text_input("Titolo del Film:")
        f_anno = st.text_input("Anno di uscita presunto (es. 2027 o 2028):")
        f_note = st.text_area("Note / Perchè ti interessa (es. Regista, Attori, Rumors):")
        submit_futuro = st.form_submit_button("Salva nei Promemoria")
        
        if submit_futuro:
            if f_titolo:
                nuovo_futuro = {
                    "Titolo": f_titolo.strip(),
                    "Anno Presunto": f_anno.strip() if f_anno else "TBD",
                    "Note": f_note.strip() if f_note else "-"
                }
                df_futuri = pd.concat([df_futuri, pd.DataFrame([nuovo_futuro])], ignore_index=True)
                salva_dati_futuri(df_futuri)
                st.success(f"Promemoria salvato su GitHub per: **{f_titolo}**")
                st.rerun()
            else:
                st.error("Il titolo del film è obbligatorio per salvare il promemoria.")

    st.divider()
    st.subheader("📋 Lista dei Promemoria Salvati")
    
    if df_futuri.empty:
        st.info("Nessun promemoria salvato al momento.")
    else:
        st.dataframe(df_futuri, use_container_width=True)
        st.divider()
        
        for index, row in df_futuri.iterrows():
            col_info, col_search, col_del_futuro = st.columns([3, 1, 1])
            
            with col_info:
                st.write(f"📌 **{row['Titolo']}** ({row['Anno Presunto']})")
                st.caption(f"Note: {row['Note']}")
                
            with col_search:
                query_string = urllib.parse.quote(row['Titolo'])
                url_ricerca_imdb = f"https://www.imdb.com/find/?q={query_string}"
                st.link_button("🔍 Cerca su IMDb", url_ricerca_imdb, use_container_width=True)
                
            with col_del_futuro:
                if st.button("❌ Elimina", key=f"del_futuro_{index}", use_container_width=True):
                    df_futuri = df_futuri.drop(index).reset_index(drop=True)
                    salva_dati_futuri(df_futuri)
                    st.warning("Promemoria eliminato da GitHub.")
                    st.rerun()
        
