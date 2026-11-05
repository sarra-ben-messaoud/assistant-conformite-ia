"""Étape 2 — Question → recherche des passages → réponse sourcée (ou refus)."""

import json
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

import numpy as np

import config

SYSTEM_PROMPT = """Tu es l'assistant conformité IA d'une entreprise. Tu aides les équipes métier \
à comprendre le Règlement (UE) 2024/1689 sur l'intelligence artificielle (AI Act).

Règles strictes :
1. Réponds UNIQUEMENT à partir des extraits fournis. N'utilise jamais tes connaissances générales.
2. Cite tes sources entre crochets après chaque affirmation, avec la section et la page, \
par exemple [Article 5, p. 51].
3. Si les extraits ne permettent pas de répondre, réponds exactement : "{refusal}"
4. Réponds en français, de façon claire et concise (5 à 10 lignes maximum), \
avec des puces si plusieurs éléments.
5. Ne donne jamais d'avis juridique définitif : tu donnes une première orientation.
6. Quand un article ou une annexe répond à la question, cite-le en priorité : les considérants \
expliquent l'intention du texte, mais ce sont les articles et les annexes qui fixent les règles.
7. Mentionne les exceptions et conditions prévues par le texte, sans généraliser au-delà."""


@dataclass
class Source:
    section: str
    title: str
    page: int
    score: float
    text: str


@dataclass
class Answer:
    question: str
    answer: str
    refused: bool
    sources: list[Source] = field(default_factory=list)
    latency_s: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0


class ComplianceAssistant:
    def __init__(self, index_dir: str = "index", client=None, top_k: int = config.TOP_K,
                 min_score: float = config.MIN_SCORE, min_rule_sources: int = config.MIN_RULE_SOURCES,
                 log: bool = True):
        folder = config.ROOT / index_dir
        self.chunks = json.loads((folder / "chunks.json").read_text(encoding="utf-8"))
        self.vectors = np.load(folder / "embeddings.npy")
        self.top_k, self.min_score, self.log = top_k, min_score, log
        self.min_rule_sources = min_rule_sources
        self.is_rule = np.array([not c["section"].startswith(("Considérant", "Préambule"))
                                 for c in self.chunks])
        if client is None:
            from mistralai.client import Mistral
            client = Mistral(api_key=config.get_api_key())
        self.client = client

    # -- Recherche ---------------------------------------------------------

    @staticmethod
    def _with_retry(call, attempts: int = 6):
        """Réessaie quand l'API répond 429 (limite de débit de l'offre gratuite) :
        on patiente 1 s, puis 2 s, 4 s… au lieu de planter."""
        for attempt in range(attempts):
            try:
                return call()
            except Exception as error:
                if "429" not in str(error) or attempt == attempts - 1:
                    raise
                time.sleep(2 ** attempt)

    def _embed(self, text: str) -> np.ndarray:
        response = self._with_retry(
            lambda: self.client.embeddings.create(model=config.EMBED_MODEL, inputs=[text])
        )
        vector = np.array(response.data[0].embedding, dtype=np.float32)
        return vector / np.linalg.norm(vector)

    def search(self, question: str) -> list[Source]:
        """Les passages les plus proches de la question (similarité cosinus).

        Priorité aux règles : au moins `min_rule_sources` des passages retenus viennent
        d'articles ou d'annexes. Sans cela, les 180 considérants (près de la moitié du
        texte) prennent souvent la place de l'article qui fixe réellement la règle.
        """
        scores = self.vectors @ self._embed(question)
        order = np.argsort(scores)[::-1]
        rules = [i for i in order if self.is_rule[i]][: self.min_rule_sources]
        others = [i for i in order if i not in rules][: self.top_k - len(rules)]
        best = sorted(rules + others, key=lambda i: -scores[i])
        return [
            Source(
                section=self.chunks[i]["section"],
                title=self.chunks[i]["title"],
                page=self.chunks[i]["page"],
                score=round(float(scores[i]), 3),
                text=self.chunks[i]["text"],
            )
            for i in best
        ]

    # -- Réponse -----------------------------------------------------------

    def ask(self, question: str) -> Answer:
        start = time.perf_counter()
        sources = self.search(question)

        # Garde-fou n°1 : si aucun passage n'est assez proche, on refuse
        # AVANT d'appeler le modèle (pas de réponse inventée, pas de coût).
        if not sources or sources[0].score < self.min_score:
            result = Answer(question, config.REFUSAL_MESSAGE, True, sources)
        else:
            context = "\n\n".join(
                f"[{s.section}, p. {s.page}] {s.title}\n{s.text}" for s in sources
            )
            time.sleep(1)  # l'offre gratuite limite à environ 1 requête par seconde
            response = self._with_retry(lambda: self.client.chat.complete(
                model=config.CHAT_MODEL,
                temperature=0.1,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT.format(refusal=config.REFUSAL_MESSAGE)},
                    {"role": "user", "content": f"Extraits :\n{context}\n\nQuestion : {question}"},
                ],
            ))
            text = response.choices[0].message.content.strip()
            # Garde-fou n°2 : le modèle lui-même peut juger les extraits insuffisants
            refused = text.startswith(config.REFUSAL_MESSAGE[:40])
            result = Answer(
                question, text, refused, sources,
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
            )

        result.latency_s = round(time.perf_counter() - start, 2)
        if self.log:
            self._write_log(result)
        return result

    # -- Journal -----------------------------------------------------------

    @staticmethod
    def _write_log(result: Answer) -> None:
        """Une ligne JSON par question : la matière première des KPIs (Power BI)."""
        config.LOG_FILE.parent.mkdir(exist_ok=True)
        entry = asdict(result)
        entry["timestamp"] = datetime.now().isoformat(timespec="seconds")
        entry["model"] = config.CHAT_MODEL
        entry["sources"] = [
            {"section": s.section, "page": s.page, "score": s.score} for s in result.sources
        ]
        entry.pop("answer")  # on ne stocke pas les réponses complètes (minimisation)
        with open(config.LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    # Test rapide en ligne de commande : python rag.py "Ma question"
    import sys
    assistant = ComplianceAssistant()
    q = " ".join(sys.argv[1:]) or "Quelles pratiques d'IA sont interdites ?"
    r = assistant.ask(q)
    print(r.answer, "\n")
    for s in r.sources:
        print(f"- {s.section} (p. {s.page}) score {s.score}")
    print(f"\n{r.latency_s}s · {r.prompt_tokens}+{r.completion_tokens} tokens")
