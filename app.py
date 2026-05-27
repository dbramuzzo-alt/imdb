import streamlit as st
from imdb import Cinemagoer

st.title("🧪 Test Infallibile con Cinemagoer (Gratis e Senza Chiavi)")
st.write("Verifichiamo se riusciamo a leggere i 35K voti senza usare proxy o carte di credito.")

# ID di The Mandalorian & Grogu (senza il 'tt', solo i numeri)
id_input = st.text_input("Inserisci solo i numeri dell'ID IMDb (es. 30825738):", value="30825738")

if st.button("Avvia Test di Estrazione"):
    with st.spinner("Connessione diretta ai server IMDb..."):
        try:
            # Inizializziamo il motore di Cinemagoer
            ia = Cinemagoer()
            
            # Scarichiamo i dati del film tramite il suo ID numerico
            film = ia.get_movie(id_input)
            
            st.success("✅ Connessione riuscita! I server di IMDb hanno risposto.")
            
            st.subheader("Dati Estratti:")
            
            # Estraiamo le informazioni principali
            titolo = film.get('title', 'Titolo Sconosciuto')
            voto = film.get('rating', 0.0)
            voti = film.get('votes', 0)
            
            st.write(f"🎥 **Titolo:** {titolo}")
            st.write(f"⭐ **Voto IMDb:** {voto}")
            st.write(f"📊 **Numero di Voti:** {voti:,}".replace(",", "."))
            
            # Mostriamo un'anteprima dei dati grezzi per sicurezza
            st.subheader("Anteprima dati tecnici ricevuti:")
            st.write({
                "titolo": titolo,
                "rating": voto,
                "votes": voti
            })
            
        except Exception as e:
            st.error(f"💥 Errore durante l'estrazione: {e}")
            
