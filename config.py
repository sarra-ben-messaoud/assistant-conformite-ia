"""Réglages du projet, regroupés à un seul endroit."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).parent
DATA_DIR = ROOT / "data"
INDEX_DIR = ROOT / "index"
LOG_FILE = ROOT / "logs" / "requests.jsonl"

# Modèles Mistral
CHAT_MODEL = os.getenv("CHAT_MODEL", "ministral-8b-latest")
EMBED_MODEL = "mistral-embed"

# Découpage du texte
CHUNK_SIZE = 1000      # nombre maximal de caractères par passage
CHUNK_OVERLAP = 150    # caractères repris du passage précédent, pour ne pas couper une idée

# Recherche
TOP_K = 5              # nombre de passages envoyés au modèle
MIN_RULE_SOURCES = 3   # dont au moins 3 issus d'articles ou d'annexes (0 = pas de priorité)
MIN_SCORE = 0.79       # en dessous de ce score de similarité, on refuse de répondre.
                       # Calibré avec evaluate.py : questions dans le sujet ≥ 0,814,
                       # questions hors sujet ≤ 0,785 (eval/report.md)

REFUSAL_MESSAGE = (
    "Je ne trouve pas cette information dans les textes de référence "
    "(AI Act, Règlement (UE) 2024/1689). Pour cette question, adressez-vous "
    "à l'équipe conformité."
)


def get_api_key() -> str:
    """Lit la clé API dans le fichier .env (ou dans les secrets Streamlit en ligne)."""
    key = os.getenv("MISTRAL_API_KEY")
    if not key:
        try:
            import streamlit as st
            key = st.secrets.get("MISTRAL_API_KEY")
        except Exception:
            key = None
    if not key:
        raise RuntimeError(
            "Clé API introuvable. Crée un fichier .env avec la ligne : MISTRAL_API_KEY=ta_cle"
        )
    return key
