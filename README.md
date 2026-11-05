# ⚖️ Assistant conformité IA

**Un assistant qui répond aux questions des équipes métier sur l'AI Act, en citant l'article et la page du texte officiel, et qui refuse de répondre quand il ne sait pas.**

> 🔗 Démo en ligne : *(lien à ajouter après le déploiement)*
> 📸 *(capture d'écran à ajouter ici)*

---

## Le problème

Une entreprise ouvre l'IA générative à ses équipes. Avant chaque projet, les mêmes questions remontent à la conformité :
*« Mon cas d'usage est-il à haut risque ? Dois-je prévenir les utilisateurs qu'ils parlent à une IA ? »*
Le règlement fait 144 pages, les réponses arrivent lentement, et un chatbot généraliste peut inventer une réponse.

**Cet assistant répond en quelques secondes, à partir du texte officiel uniquement, avec la source exacte à vérifier.**
Le cadrage complet (besoin, user stories, choix) est dans [`docs/cadrage.md`](docs/cadrage.md).

## Les résultats

Évaluation sur **25 questions test** : 20 questions réglementaires dont l'article attendu est connu, et 5 questions hors sujet. Modèle : `ministral-8b-latest`.

| Indicateur | Version 1 | **Version 2 : priorité aux articles** |
| --- | --- | --- |
| Bon article retrouvé (hit@5) | 75 % | **95 %** |
| Réponses citant le bon article | 79 % | **100 %** |
| Questions hors sujet refusées | 100 % | **100 %** |
| Refus à tort | 5 % | 5 % |
| Latence moyenne | 8,9 s | 8,4 s |

**Ce que l'évaluation a montré :** en version 1, 4 échecs sur 5 venaient du même problème. Les 180 considérants (le préambule qui explique l'intention du texte) représentent près de la moitié des passages, et prenaient la place de l'article qui fixe réellement la règle. La version 2 garantit qu'au moins 3 des 5 passages viennent d'articles ou d'annexes : le bon article est retrouvé dans 95 % des cas, et cité dans 100 % des réponses.

**Calibrage du seuil de refus :** toutes les questions dans le sujet obtiennent un score de similarité ≥ 0,814, toutes les questions hors sujet ≤ 0,785. Le seuil est fixé à **0,79** : le hors-sujet est refusé avant même d'appeler le modèle.

Rapport complet : [`eval/report.md`](eval/report.md).

## Comment ça marche

```
Ingestion (une fois) : PDF → découpage par article → embeddings Mistral → index local
Question :            embedding → 5 passages les plus proches → score trop faible ? refus
                                → sinon : Mistral + passages → réponse sourcée → journal
```

## Les choix, et pourquoi

| Choix | Pourquoi |
| --- | --- |
| **Découpage par article** | La réponse peut citer « Article 5, p. 51 », ce qu'un juriste attend. |
| **Deux garde-fous contre les réponses inventées** | 1) Refus *avant* d'appeler le modèle si aucun passage n'est assez proche. 2) Consigne stricte au modèle de répondre uniquement à partir des extraits. Une consigne seule ne suffit pas. |
| **Priorité aux articles et annexes** | Hypothèse issue de l'analyse des échecs, puis vérifiée par l'évaluation : +20 points de bon article retrouvé. |
| **Seuil de refus calibré par l'évaluation** | Le seuil (0,79) est choisi en comparant les scores des questions dans le sujet et hors sujet, pas au hasard. |
| **Ministral 8B** | Le modèle Mistral Small n'est pas accessible avec l'offre gratuite ; Ministral 8B atteint 100 % de citations correctes sur le jeu de test. |
| **Index NumPy plutôt qu'une base vectorielle** | ~900 passages : une base dédiée serait surdimensionnée. Moins de dépendances, déploiement plus simple. |
| **Mistral** | Fournisseur européen, cohérent pour un sujet de conformité européenne. |
| **Journal JSONL** | Chaque requête (latence, tokens, refus, sources) est journalisée : de quoi suivre l'usage et le coût dans Power BI. |

## Limites assumées

- **Une seule source** : le texte de l'AI Act publié au Journal officiel en 2024. Les modifications ultérieures, les lignes directrices de la Commission et les recommandations de la CNIL ne sont pas encore intégrées.
- **Pas un avis juridique** : l'assistant donne une première orientation et renvoie toujours à la source.
- **Offre gratuite de Mistral** : les requêtes peuvent servir à entraîner leurs modèles. C'est acceptable pour des textes publics, mais pas pour des documents internes. En production, il faudrait une offre sans réutilisation des données ou un modèle hébergé en interne.
- **Jeu d'évaluation de 25 questions** : utile pour comparer des réglages, trop petit pour garantir la qualité en production. L'écart entre les scores dans le sujet et hors sujet est faible (0,785 contre 0,814) : le seuil est donc doublé d'un second garde-fou côté modèle.
- **Un échec restant** : à la question « Quelles amendes en cas de pratique interdite ? », la recherche par le sens se focalise sur « pratique interdite » (article 5) au lieu des sanctions (article 99).
- **Latence de 8 s en moyenne**, due surtout aux limites de débit de l'offre gratuite (pauses entre les appels).

## Prochaines étapes

- Ajouter les recommandations de la CNIL et une charte IA interne.
- Recherche hybride (mots-clés + sens), pour corriger le dernier échec (« amendes » → article 99).
- Élargir le jeu d'évaluation à 100 questions, rédigées avec des juristes.
- Brancher le service sur une gateway LLM commune (quotas, clés par équipe, masquage des données sensibles).

## Lancer le projet

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows  (Mac/Linux : source .venv/bin/activate)
pip install -r requirements.txt
copy .env.example .env          # puis coller sa clé Mistral dans .env
python ingest.py                # le PDF de l'AI Act doit être dans data/
streamlit run app.py
python evaluate.py              # rapport dans eval/report.md
```

---
Projet personnel de **Sarra Ben Messaoud** · [LinkedIn](https://www.linkedin.com/in/sarrabenmessaoud) · Python · Mistral AI · NumPy · Streamlit
