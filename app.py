import streamlit as st
import requests
from bs4 import BeautifulSoup

st.title("🧪 Laboratorio di Test IMDb")
st.write("Questo script serve a verificare cosa vede esattamente il server quando interroga IMDb.")

SCRAPER_API_KEY = "d09a651a095f55f0bd28f15a1bad8bd6"

# Un ID standard universale (es. Il Cavaliere Oscuro) per essere sicuri che esista
id_test = st.text_input("Inserisci l'ID IMDb da testare:", value="tt0468569")

if st.button("Avvia Test di Estrazione"):
    url_bersaglio = f"https://www.imdb.com/title/{id_test}/"
    url_proxy = f"http://api.scraperapi.com?api_key={SCRAPER_API_KEY}&url={url_bersaglio}"
    
    with st.spinner("Chiamata a ScraperAPI in corso..."):
        try:
            risposta = requests.get(url_proxy, timeout=30)
            
            st.subheader("1. Stato della Risposta")
            st.write(f"Codice di stato HTTP: `{risposta.status_code}`")
            
            if risposta.status_code == 200:
                st.success("✅ Il server ha risposto con successo!")
                
                soup = BeautifulSoup(risposta.text, "html.parser")
                
                st.subheader("2. Controllo Titolo della Pagina Browser")
                if soup.title:
                    st.code(soup.title.text)
                else:
                    st.warning("Nessun tag <title> trovato.")
                
                st.subheader("3. Controllo Meta-Tag Social (OpenGraph)")
                meta_title = soup.find("meta", property="og:title")
                if meta_title:
                    st.code(meta_title.get("content", "Tag presente ma vuoto"))
                else:
                    st.warning("Nessun meta-tag og:title trovato.")
                    
                st.subheader("4. Primi 1000 caratteri dell'HTML ricevuto")
                st.text(risposta.text[:1000])
                
            else:
                st.error(f"❌ ScraperAPI ha risposto con un errore. Messaggio: {risposta.text}")
                
        except Exception as e:
            st.error(f"💥 Errore critico nel codice Python: {e}")
            
