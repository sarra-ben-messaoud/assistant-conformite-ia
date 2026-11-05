# Guide de démarrage — Windows

À suivre une seule fois, dans l'ordre. Durée : environ 20 minutes.

## 1. Ouvrir le projet

1. Dézippe le dossier `assistant-conformite-ia` (par exemple dans `Documents`).
2. Ouvre **VS Code** → menu **Fichier → Ouvrir le dossier…** → choisis `assistant-conformite-ia`.
3. Ouvre un terminal : menu **Terminal → Nouveau terminal**. Toutes les commandes ci-dessous se tapent là.

Vérifie que Python est bien installé :

```
python --version
```

Tu dois voir `Python 3.x.x`. Si tu as une erreur, réinstalle Python en cochant **« Add python.exe to PATH »**.

## 2. Créer l'environnement du projet

Un « environnement virtuel », c'est une boîte qui contient les bibliothèques de ce projet, sans toucher au reste de l'ordinateur.

```
python -m venv .venv
.venv\Scripts\activate
```

Tu dois maintenant voir `(.venv)` au début de la ligne du terminal.

> **Si tu as une erreur rouge « l'exécution de scripts est désactivée »**, tape cette commande, réponds `O` (Oui), puis relance `.venv\Scripts\activate` :
> ```
> Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
> ```

Puis installe les bibliothèques (1 à 2 minutes) :

```
pip install -r requirements.txt
```

## 3. Placer ta clé API

1. Dans VS Code, fais un clic droit sur `.env.example` → **Copier**, puis clic droit dans la liste → **Coller**.
2. Renomme la copie en `.env` (exactement, avec le point devant).
3. Ouvre `.env` et remplace `colle_ta_cle_ici` par ta clé Mistral. Enregistre (Ctrl+S).

Le fichier `.env` ne partira jamais sur GitHub : il est listé dans `.gitignore`.

## 4. Ajouter le texte de l'AI Act

Rien à faire : le PDF est déjà dans le dossier `data/`.

## 5. Construire l'index (une seule fois)

```
python ingest.py
```

Tu dois voir le nombre d'articles trouvés (180 considérants, 113 articles, 13 annexes), puis le calcul des embeddings, qui prend environ 2 à 3 minutes.

## 6. Lancer l'assistant

```
streamlit run app.py
```

Une page s'ouvre dans ton navigateur. Clique sur un exemple de question. Pour arrêter, reviens dans le terminal et tape **Ctrl+C**.

## 7. Lancer l'évaluation

```
python evaluate.py
```

Le rapport est enregistré dans `eval/report.md`. On l'analysera ensemble pour régler le seuil de refus.

---

**Les prochaines fois**, seules ces deux commandes sont nécessaires :

```
.venv\Scripts\activate
streamlit run app.py
```
