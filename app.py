"""Étape 3 — Interface web.  Lancement : streamlit run app.py"""

import streamlit as st

from rag import ComplianceAssistant

st.set_page_config(page_title="Assistant conformité IA", page_icon="⚖️", layout="centered")

EXAMPLES = [
    "Quelles pratiques d'IA sont interdites ?",
    "Un outil de notation de crédit est-il un système à haut risque ?",
    "Un chatbot doit-il dire à l'utilisateur qu'il parle à une IA ?",
    "Quelles sanctions en cas de non-respect du règlement ?",
]


@st.cache_resource
def load_assistant() -> ComplianceAssistant:
    return ComplianceAssistant()


st.title("⚖️ Assistant conformité IA")
st.caption(
    "Posez une question sur l'AI Act (Règlement (UE) 2024/1689). "
    "Chaque réponse cite l'article et la page du texte officiel."
)
st.warning(
    "Prototype de démonstration : les réponses sont une première orientation, "
    "pas un avis juridique. Vérifiez toujours la source citée.",
    icon="⚠️",
)

# Exemples cliquables
st.write("**Exemples :**")
cols = st.columns(2)
for i, example in enumerate(EXAMPLES):
    if cols[i % 2].button(example, use_container_width=True):
        st.session_state["question"] = example

question = st.text_input("Votre question", key="question", placeholder="Ex. : Quelles obligations pour un déployeur ?")

if question:
    with st.spinner("Recherche dans le règlement…"):
        try:
            result = load_assistant().ask(question)
        except Exception as error:
            if "429" in str(error):
                st.error("Le service est très sollicité (limite de l'offre gratuite). Réessayez dans une minute.")
            else:
                st.error(f"Une erreur est survenue : {error}")
            st.stop()

    if result.refused:
        st.info(result.answer)
    else:
        st.markdown(result.answer)

    st.caption(
        f"⏱ {result.latency_s} s · "
        f"{result.prompt_tokens + result.completion_tokens} tokens · "
        f"meilleur score de similarité : {result.sources[0].score if result.sources else '—'}"
    )

    with st.expander(f"📄 Passages consultés ({len(result.sources)})"):
        for s in result.sources:
            title = f" — {s.title}" if s.title else ""
            st.markdown(f"**{s.section}**{title} · p. {s.page} · score {s.score}")
            st.text(s.text[:600] + ("…" if len(s.text) > 600 else ""))
            st.divider()

with st.sidebar:
    st.header("À propos")
    st.write(
        "Projet personnel de **Sarra Ben Messaoud** : un assistant RAG "
        "(Retrieval-Augmented Generation) qui répond à partir du texte officiel de l'AI Act."
    )
    st.write("**Garde-fous**")
    st.write(
        "- Refus automatique si aucun passage pertinent n'est trouvé\n"
        "- Sources citées (article + page)\n"
        "- Journal de chaque requête (latence, tokens, refus)"
    )
    st.write("**Stack** : Python · Mistral AI · NumPy · Streamlit")
