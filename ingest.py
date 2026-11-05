"""Étape 1 — Ingestion : PDF → passages découpés par article → embeddings → index local.

À lancer une seule fois (ou à chaque changement de document / de réglage) :
    python ingest.py
    python ingest.py --chunk-size 600 --out index_600   # pour comparer un autre réglage
"""

import argparse
import json
import re
import time
from datetime import date
from pathlib import Path

import numpy as np
from pypdf import PdfReader

import config

# --- 1. Extraction du texte -------------------------------------------------

# Lignes répétées en haut / bas de chaque page du Journal officiel, à ignorer
NOISE_PATTERNS = [
    re.compile(r"^FR$"),
    re.compile(r"^ELI\s*:"),
    re.compile(r"^\d+\s*/\s*\d+$"),                     # numéro de page « 12/144 »
    re.compile(r"JO\s+L\s+du\s+\d"),                     # en-tête « FR JO L du 12.7.2024 2/144 ELI: … »
    re.compile(r"ELI\s*:\s*http"),
    re.compile(r"^Journal officiel de l.Union européenne", re.I),
    re.compile(r"^(CHAPITRE|SECTION)\s+[IVXLC0-9]+$"),        # titres de chapitre, sans contenu
]
MIN_CHUNK_CHARS = 50   # on écarte les fragments trop courts pour avoir du sens

ARTICLE_RE = re.compile(r"^Article\s+(\d+|premier)$")
ANNEX_RE = re.compile(r"^ANNEXE\s+([IVXLC]+)$")
RECITAL_RE = re.compile(r"^\((\d{1,3})\)\s+(.*)")      # « (12) Texte… » : considérant OU note de bas de page
FOOTNOTE_START = re.compile(r"^(JO\s|Règlement|Directive|Décision|Recommandation|Communication|Avis|Position|Résolution|Conclusions)")
ADOPTION_RE = re.compile(r"ONT ADOPTÉ LE PRÉSENT RÈGLEMENT", re.I)


def read_lines(pdf_path: Path) -> list[tuple[int, str]]:
    """Renvoie toutes les lignes utiles du PDF, avec leur numéro de page."""
    lines = []
    for page_number, page in enumerate(PdfReader(pdf_path).pages, start=1):
        for raw in (page.extract_text() or "").splitlines():
            line = raw.strip()
            if line and not any(p.search(line) for p in NOISE_PATTERNS):
                lines.append((page_number, line))
    return lines


# --- 2. Découpage en sections (considérants, articles, annexes) ------------

def split_sections(lines: list[tuple[int, str]]) -> list[dict]:
    """Regroupe les lignes par section juridique : Considérant N, Article N, Annexe N."""
    sections = []
    current = {"section": "Préambule", "title": "", "page": 1, "lines": []}
    in_body = False          # False tant qu'on est dans les considérants
    expect_title = False     # la ligne qui suit « Article 5 » est son titre

    def start(name, page):
        nonlocal current
        if current["lines"]:
            sections.append(current)
        current = {"section": name, "title": "", "page": page, "lines": []}

    last_recital = 0
    footnote_page = None     # page d'une note de bas de page en cours (lignes ignorées)

    for page, line in lines:
        # Une note de bas de page s'arrête au changement de page
        if footnote_page is not None and page != footnote_page:
            footnote_page = None

        if not in_body and ADOPTION_RE.search(line):
            in_body = True
            start("Préambule", page)
            continue

        if in_body and (m := ARTICLE_RE.match(line)):
            number = "1" if m.group(1) == "premier" else m.group(1)
            footnote_page = None
            start(f"Article {number}", page)
            expect_title = True
            continue
        if in_body and (m := ANNEX_RE.match(line)):
            footnote_page = None
            start(f"Annexe {m.group(1)}", page)
            expect_title = True
            continue

        if (m := RECITAL_RE.match(line)):
            number, rest = int(m.group(1)), m.group(2)
            # Un considérant suit toujours le précédent (n+1) ; sinon c'est une note
            # de bas de page (« (1) JO C 517 du… »), qu'on ignore.
            if not in_body and number == last_recital + 1 and not FOOTNOTE_START.match(rest):
                last_recital = number
                footnote_page = None
                start(f"Considérant {number}", page)
                current["lines"].append((page, rest))
            else:
                footnote_page = page
            continue

        if footnote_page is not None:
            continue
        if expect_title:
            current["title"] = line
            expect_title = False
            continue
        current["lines"].append((page, line))

    if current["lines"]:
        sections.append(current)
    return sections


# --- 3. Découpage en passages de taille limitée -----------------------------

def chunk_section(section: dict, size: int, overlap: int) -> list[dict]:
    """Coupe une section trop longue en passages qui se chevauchent légèrement."""
    chunks, buffer, buffer_page = [], "", section["page"]

    def flush():
        if buffer.strip():
            chunks.append({"page": buffer_page, "text": buffer.strip()})

    for page, line in section["lines"]:
        # On recolle les mots coupés en fin de ligne (« intelli- gence »)
        joined = buffer[:-1] + line if buffer.endswith("-") else (buffer + " " + line if buffer else line)
        if len(joined) > size and buffer:
            flush()
            tail = buffer[-overlap:] if overlap else ""
            buffer, buffer_page = (tail + " " + line).strip(), page
        else:
            if not buffer:
                buffer_page = page
            buffer = joined
    flush()

    for c in chunks:
        c["section"] = section["section"]
        c["title"] = section["title"]
    return chunks


# --- 4. Embeddings ----------------------------------------------------------

def embed_texts(texts: list[str], client, batch_size: int = 16) -> np.ndarray:
    """Calcule les embeddings par lots, en patientant si l'API limite le débit."""
    vectors = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        for attempt in range(6):
            try:
                response = client.embeddings.create(model=config.EMBED_MODEL, inputs=batch)
                vectors.extend(item.embedding for item in response.data)
                break
            except Exception as error:  # limite de débit de l'offre gratuite
                wait = 2 ** attempt
                print(f"  Pause de {wait}s ({error.__class__.__name__})…")
                time.sleep(wait)
        else:
            raise RuntimeError("L'API Mistral ne répond pas, réessaie plus tard.")
        print(f"  {min(i + batch_size, len(texts))}/{len(texts)} passages traités")
        time.sleep(1)
    matrix = np.array(vectors, dtype=np.float32)
    return matrix / np.linalg.norm(matrix, axis=1, keepdims=True)


def embedding_text(chunk: dict) -> str:
    """Le texte envoyé au modèle d'embedding inclut l'article et son titre,
    ce qui aide la recherche (« pratiques interdites » → Article 5)."""
    header = chunk["section"] + (f" — {chunk['title']}" if chunk["title"] else "")
    return f"{header}\n{chunk['text']}"


# --- Programme principal ----------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", default=None, help="Chemin du PDF (par défaut : le premier PDF de data/)")
    parser.add_argument("--chunk-size", type=int, default=config.CHUNK_SIZE)
    parser.add_argument("--overlap", type=int, default=config.CHUNK_OVERLAP)
    parser.add_argument("--out", default="index")
    parser.add_argument("--dry-run", action="store_true", help="Découpe sans appeler l'API")
    args = parser.parse_args()

    pdf = Path(args.pdf) if args.pdf else next(config.DATA_DIR.glob("*.pdf"), None)
    if not pdf or not pdf.exists():
        raise SystemExit("Aucun PDF trouvé : place le PDF de l'AI Act dans le dossier data/.")

    print(f"1. Lecture de {pdf.name}…")
    lines = read_lines(pdf)
    sections = split_sections(lines)
    n_articles = sum(s["section"].startswith("Article") for s in sections)
    n_annexes = sum(s["section"].startswith("Annexe") for s in sections)
    n_recitals = sum(s["section"].startswith("Considérant") for s in sections)
    print(f"   {n_recitals} considérants, {n_articles} articles, {n_annexes} annexes")

    chunks = [c for s in sections for c in chunk_section(s, args.chunk_size, args.overlap)
              if len(c["text"]) >= MIN_CHUNK_CHARS]
    for i, c in enumerate(chunks):
        c["id"] = i
    print(f"2. {len(chunks)} passages (taille max {args.chunk_size} caractères)")

    out = config.ROOT / args.out
    out.mkdir(exist_ok=True)
    (out / "chunks.json").write_text(json.dumps(chunks, ensure_ascii=False, indent=1), encoding="utf-8")
    if args.dry_run:
        print("   Mode test : pas d'embeddings calculés.")
        return

    from mistralai.client import Mistral
    client = Mistral(api_key=config.get_api_key())
    print("3. Calcul des embeddings…")
    vectors = embed_texts([embedding_text(c) for c in chunks], client)
    np.save(out / "embeddings.npy", vectors)

    meta = {
        "source": pdf.name,
        "chunk_size": args.chunk_size,
        "overlap": args.overlap,
        "embed_model": config.EMBED_MODEL,
        "n_chunks": len(chunks),
        "built_on": date.today().isoformat(),
    }
    (out / "meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    print(f"4. Index enregistré dans {out.name}/ — terminé.")


if __name__ == "__main__":
    main()
