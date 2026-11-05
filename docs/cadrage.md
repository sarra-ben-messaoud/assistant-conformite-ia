# Cadrage — Assistant conformité IA

## 1. Le besoin

Une entreprise (ici, une banque fictive) ouvre l'IA générative à ses équipes métier.
Avant de lancer un projet IA, chaque équipe se pose les mêmes questions réglementaires :

- « Mon cas d'usage est-il interdit, à haut risque, ou libre ? »
- « Dois-je informer les utilisateurs qu'ils parlent à une IA ? »
- « Quelles obligations s'appliquent à nous en tant qu'utilisateur (déployeur) d'un système d'IA ? »

Aujourd'hui, ces questions remontent à l'équipe conformité par e-mail. Les réponses sont
lentes, et les équipes lisent rarement un règlement de 144 pages.

**Objectif :** donner aux équipes une réponse immédiate, sourcée et vérifiable, tirée
directement des textes officiels — sans remplacer l'avis de l'équipe conformité.

## 2. Utilisateurs

| Utilisateur | Ce qu'il attend |
| --- | --- |
| Chef de projet métier | Savoir rapidement si son projet pose un problème réglementaire |
| Équipe conformité | Moins de questions simples, plus de temps pour les cas complexes |
| Équipe plateforme IA | Un service fiable, mesuré et documenté |

## 3. User stories

| # | En tant que… | Je veux… | Afin de… | Critères d'acceptation |
| --- | --- | --- | --- | --- |
| US1 | chef de projet métier | poser une question en français sur l'AI Act | obtenir une réponse sans lire le règlement | Réponse en moins de 10 secondes, en français |
| US2 | chef de projet métier | voir l'article et la page d'où vient la réponse | vérifier par moi-même | Chaque réponse cite au moins une source (article + page) |
| US3 | équipe conformité | que l'assistant refuse de répondre hors de son périmètre | éviter les réponses inventées | Une question hors sujet reçoit un refus explicite, sans appel au modèle si aucun passage n'est pertinent |
| US4 | équipe conformité | un avertissement clair « ceci n'est pas un avis juridique » | limiter le risque d'usage abusif | Avertissement visible sur chaque page |
| US5 | équipe plateforme IA | un journal de chaque question (latence, tokens, refus) | suivre l'usage et le coût | Chaque appel est écrit dans `logs/requests.jsonl` |
| US6 | équipe plateforme IA | mesurer la qualité sur un jeu de questions test | décider des réglages avec des chiffres | Un script produit un rapport de scores comparable entre deux réglages |

## 4. Périmètre

**Dans le périmètre (v1) :** le Règlement (UE) 2024/1689 (AI Act), version publiée au Journal officiel.

**Hors périmètre (v1) :** les modifications ultérieures du règlement, les lignes directrices de la
Commission, les recommandations de la CNIL, les textes nationaux. Ce sont les prochaines sources à ajouter.

## 5. Architecture

```
            ┌────────────── Ingestion (une seule fois) ──────────────┐
 PDF AI Act → Extraction du texte → Découpage par article → Embeddings → Index local
            └─────────────────────────────────────────────────────────┘

            ┌────────────── Question (à chaque requête) ─────────────┐
 Question → Embedding → Recherche des passages les plus proches
          → Score trop faible ? → Refus (pas d'appel au modèle)
          → Sinon : modèle Mistral + passages → Réponse sourcée
          → Journal (latence, tokens, sources, refus)
            └─────────────────────────────────────────────────────────┘
```

## 6. Choix techniques et pourquoi

| Choix | Pourquoi |
| --- | --- |
| Mistral (API) | Fournisseur européen, cohérent avec un sujet de conformité européenne ; offre gratuite pour le prototype |
| Découpage par article | La réponse peut citer un article précis, ce que les juristes attendent |
| Index local (NumPy) plutôt qu'une base vectorielle | ~900 passages : une base dédiée serait surdimensionnée. Moins de dépendances, plus simple à déployer |
| Refus avant l'appel au modèle | Une consigne dans le prompt ne suffit pas : on filtre en amont |
| Journal JSONL | Format simple, lisible directement dans Power BI pour les KPIs |

## 7. Données et sécurité

- Le corpus ne contient que des textes publics : aucune donnée personnelle n'est indexée.
- L'offre gratuite de Mistral peut utiliser les requêtes pour entraîner ses modèles. Acceptable ici
  (textes publics, questions génériques), **inacceptable** pour des documents internes : en production,
  il faudrait une offre payante sans réutilisation des données, ou un modèle hébergé en interne.
- La clé API est stockée dans un fichier `.env`, exclu du dépôt Git.

## 8. KPIs suivis

| KPI | Mesure |
| --- | --- |
| Qualité de la recherche | % de questions où le bon article est retrouvé (hit@k) |
| Fiabilité des refus | % de questions hors sujet correctement refusées |
| Citation | % de réponses qui citent le bon article |
| Latence | Temps de réponse moyen et 95e centile |
| Coût | Tokens consommés par question |
