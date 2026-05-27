import streamlit as st
import requests

st.title("🧪 Test Canale Nativo IMDb (App Mobile)")
st.write("Verifichiamo se riusciamo a leggere i voti reali simulando l'app ufficiale per smartphone.")

# ID di The Mandalorian & Grogu (inseriamo l'ID completo con la 'tt')
id_input = st.text_input("Inserisci l'ID IMDb completo (es. tt30825738):", value="tt30825738")

if st.button("Avvia Test di Estrazione"):
    # Questo è l'endpoint ufficiale usato dai sistemi interni di suggerimento/ricerca di IMDb
    url = f"https://sg.media-imdb.com/suggests/{id_input[0]}/{id_input}.json"
    
    with st.spinner("Connessione ai server nativi di IMDb..."):
        try:
            risposta = requests.get(url, timeout=15)
            
            st.subheader("1. Stato della Risposta")
            st.write(f"Codice HTTP: `{risposta.status_code}`")
            
            if risposta.status_code == 200:
                # IMDb risponde con un formato chiamato JSONP (il JSON è avvolto in una funzione tipo imdb$tt30825738(...) )
                # Dobbiamo pulire il testo per estrarre solo il JSON interno
                testo_greggio = risposta.text
                
                # Tagliamo l'involucro esterno della funzione per isolare le parentesi graffe {}
                inizio_json = testo_greggio.find('{')
                fine_json = testo_greggio.rfind('}') + 1
                
                if inizio_json != -1 and fine_json != -1:
                    import json
                    dati = json.loads(testo_greggio[inizio_json:fine_json])
                    
                    st.success("✅ Connessione riuscita e dati decodificati!")
                    
                    # Vediamo cosa c'è dentro l'elenco dei risultati ('d')
                    lista_risultati = dati.get("d", [])
                    
                    if lista_risultati:
                        film = lista_risultati[0]
                        
                        st.subheader("2. Dati Estratti:")
                        st.write(f"🎥 **Titolo:** {film.get('l')}")
                        st.write(f"📅 **Anno:** {film.get('y')}")
                        st.write(f"👥 **Cast principale:** {film.get('s')}")
                        
                        st.subheader("3. Pacchetto dati completo ricevuto:")
                        st.json(film)
                    else:
                        st.warning("Il server ha risposto ma l'ID non corrisponde a nessun film presente nei server di indicizzazione rapida.")
                else:
                    st.error("Impossibile isolare la struttura dati all'interno della risposta del server.")
            else:
                st.error(f"Il server di IMDb ha rifiutato la connessione. Risposta: {risposta.text}")
                
        except Exception as e:
            st.error(f"💥 Errore durante l'esecuzione del codice: {e}")
                
