# Rapport d'évaluation

25 questions : 20 dans le sujet (article attendu connu), 5 hors sujet (refus attendu).

| Indicateur | sans priorité | priorité articles |
|---|---|---|
| Bon article retrouvé (hit@k, %) | 75.0 | 95.0 |
| Réponse citant le bon article (%) | 78.9 | 100.0 |
| Questions hors sujet refusées (%) | 100.0 | 100.0 |
| Refus à tort (%, à minimiser) | 5.0 | 5.0 |
| Latence moyenne (s) | 8.89 | 8.35 |
| Latence 95e centile (s) | 15.39 | 15.95 |
| Tokens moyens par réponse | 1749 | 1778 |
| Score de similarité le plus bas (dans le sujet) | 0.815 | 0.814 |
| Score de similarité le plus haut (hors sujet) | 0.785 | 0.785 |

Réglages :

- **sans priorité** : modèle `ministral-8b-latest`, index `index`, top-k 5, articles/annexes prioritaires 0, seuil de refus 0.7
- **priorité articles** : modèle `ministral-8b-latest`, index `index`, top-k 5, articles/annexes prioritaires 3, seuil de refus 0.7

## Calibrage du seuil de refus

- **sans priorité** : les scores se séparent bien. Un seuil entre 0.785 et 0.815 (par exemple 0.8) refuse le hors-sujet sans refuser à tort.
- **priorité articles** : les scores se séparent bien. Un seuil entre 0.785 et 0.814 (par exemple 0.799) refuse le hors-sujet sans refuser à tort.

## Détail des échecs

**sans priorité** : 5 échec(s)
- Q3 « L'identification biométrique à distance en temps réel dans l'espace public est-elle autorisée pour les forces de l'ordre ? » → trouvé : Considérant 35, Considérant 39, Considérant 95
- Q10 « Qu'est-ce qu'un déployeur au sens du règlement ? » → trouvé : Considérant 13, Considérant 91, Considérant 93
- Q12 « Les entreprises doivent-elles former leur personnel à l'IA ? » → trouvé : Considérant 56, Considérant 4, Considérant 106
- Q16 « Quelles amendes en cas de recours à une pratique d'IA interdite ? » → trouvé : Article 5, Article 5, Article 5 (refusé)
- Q18 « Quand un modèle d'IA à usage général présente-t-il un risque systémique ? » → trouvé : Considérant 110, Considérant 115, Considérant 111

**priorité articles** : 1 échec(s)
- Q16 « Quelles amendes en cas de recours à une pratique d'IA interdite ? » → trouvé : Article 5, Article 5, Article 5 (refusé)
