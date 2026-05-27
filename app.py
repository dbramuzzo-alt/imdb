import streamlit as st
import requests
import json

st.title("🧪 Test Avanzato API Interne IMDb")
st.write("Interroghiamo il server dei dettagli per estrarre la valutazione e il numero reale dei voti.")

id_input = st.text_input("Inserisci l'ID IMDb completo (es. tt30825738):", value="tt30825738")

if st.button("Avvia Estrazione Dettagliata"):
    # Utilizziamo l'endpoint GraphQL interno di IMDb (quello usato dalle app moderne)
    url = "https://api.graphql.imdb.com/"
    
    # Costruiamo la richiesta esatta per chiedere a IMDb solo Titolo, Voto e Numero Voti di quel film
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
        "variables": {"id": id_input}
    }
    
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"
    }
    
    with st.spinner("Interrogazione database centrale IMDb..."):
        try:
            risposta = requests.post(url, json=query_graphql, headers=headers, timeout=15)
            
            st.subheader("1. Stato della Risposta")
            st.write(f"Codice HTTP: `{risposta.status_code}`")
            
            if risposta.status_code == 200:
                risposta_json = risposta.json()
                data = risposta_json.get("data", {})
                title_data = data.get("title") if data else None
                
                if title_data:
                    st.success("✅ Film trovato nei registri centrali!")
                    
                    # Estrazione dei dati puliti
                    titolo = title_data.get("originalTitleText", {}).get("text", "Titolo Sconosciuto")
                    ratings = title_data.get("ratingsSummary", {})
                    
                    voto = ratings.get("aggregateRating", 0.0) if ratings else 0.0
                    voti = ratings.get("voteCount", 0) if ratings else 0
                    
                    st.subheader("2. Dati Reali Estratti:")
                    st.write(f"🎥 **Titolo Originale:** {titolo}")
                    st.write(f"⭐ **Voto IMDb:** {voto}")
                    st.write(f"📊 **Numero di Voti:** {voti:,}".replace(",", "."))
                    
                    st.subheader("3. Risposta JSON nativa ricevuta:")
                    st.json(risposta_json)
                else:
                    st.error("❌ Il server ha risposto ma non ha trovato questo ID film specifico.")
                    st.json(risposta_json)
            else:
                st.error(f"❌ Connessione rifiutata dal server GraphQL. Risposta: {risposta.text}")
                
        except Exception as e:
            st.error(f"💥 Errore di esecuzione del codice: {e}")
                                                                                  
