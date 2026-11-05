"""Étape 4 — Évaluation : mesurer la qualité au lieu de « faire confiance ».

    python evaluate.py                                  # réglage actuel (config.py / .env)
    python evaluate.py --rules 0 3                      # avec ou sans priorité aux articles
    python evaluate.py --models ministral-8b-latest open-mistral-nemo   # compare deux modèles
    python evaluate.py --min-score 0.75                 # teste un autre seuil de refus

Chaque combinaison de réglages est évaluée sur les 25 questions de eval/questions.json.
Questions avec "expected" vide = hors sujet : l'assistant doit refuser.
Résultats : eval/report.md (lisible) et eval/results.json (détail complet).
"""

import argparse
import itertools
import json
import re
import time

import numpy as np

import config
from rag import ComplianceAssistant

QUESTIONS = json.loads((config.ROOT / "eval" / "questions.json").read_text(encoding="utf-8"))


def evaluate(label: str, index_dir: str = "index", model: str = config.CHAT_MODEL,
             min_rule_sources: int = config.MIN_RULE_SOURCES, min_score: float = config.MIN_SCORE,
             client=None, pause: float = 1.2) -> dict:
    config.CHAT_MODEL = model  # le modèle utilisé par rag.py pour cette série
    assistant = ComplianceAssistant(index_dir, client=client, min_score=min_score,
                                    min_rule_sources=min_rule_sources, log=False)
    rows = []
    for q in QUESTIONS:
        r = assistant.ask(q["question"])
        found = [s.section for s in r.sources]
        in_scope = bool(q["expected"])
        rows.append({
            "id": q["id"],
            "question": q["question"],
            "in_scope": in_scope,
            "top_score": r.sources[0].score if r.sources else 0.0,
            "retrieved": found,
            "hit": in_scope and any(e in found for e in q["expected"]),
            "refused": r.refused,
            "cited": in_scope and any(re.search(rf"\b{re.escape(e)}\b", r.answer) for e in q["expected"]),
            "latency_s": r.latency_s,
            "tokens": r.prompt_tokens + r.completion_tokens,
            "answer": r.answer,
        })
        mark = "refus" if r.refused else ("ok" if rows[-1]["hit"] else "—")
        print(f"  Q{q['id']:>2} [{mark:>5}] score {rows[-1]['top_score']:.3f}  {q['question'][:60]}")
        time.sleep(pause)
    settings = {"index": index_dir, "model": model, "min_rule_sources": min_rule_sources,
                "min_score": min_score, "top_k": config.TOP_K}
    return {"label": label, "settings": settings, "metrics": summarize(rows), "rows": rows}


def summarize(rows: list[dict]) -> dict:
    ins = [r for r in rows if r["in_scope"]]
    outs = [r for r in rows if not r["in_scope"]]
    answered = [r for r in ins if not r["refused"]]
    lat = [r["latency_s"] for r in rows]
    pct = lambda n, d: round(100 * n / d, 1) if d else 0.0
    return {
        "hit_at_k_%": pct(sum(r["hit"] for r in ins), len(ins)),
        "citation_correcte_%": pct(sum(r["cited"] for r in answered), len(answered)),
        "refus_hors_sujet_%": pct(sum(r["refused"] for r in outs), len(outs)),
        "faux_refus_%": pct(sum(r["refused"] for r in ins), len(ins)),
        "latence_moy_s": round(float(np.mean(lat)), 2),
        "latence_p95_s": round(float(np.percentile(lat, 95)), 2),
        "tokens_moy": round(float(np.mean([r["tokens"] for r in answered])) if answered else 0.0),
        "score_min_dans_le_sujet": min(r["top_score"] for r in ins),
        "score_max_hors_sujet": max(r["top_score"] for r in outs) if outs else None,
    }


LABELS = {
    "hit_at_k_%": "Bon article retrouvé (hit@k, %)",
    "citation_correcte_%": "Réponse citant le bon article (%)",
    "refus_hors_sujet_%": "Questions hors sujet refusées (%)",
    "faux_refus_%": "Refus à tort (%, à minimiser)",
    "latence_moy_s": "Latence moyenne (s)",
    "latence_p95_s": "Latence 95e centile (s)",
    "tokens_moy": "Tokens moyens par réponse",
    "score_min_dans_le_sujet": "Score de similarité le plus bas (dans le sujet)",
    "score_max_hors_sujet": "Score de similarité le plus haut (hors sujet)",
}


def write_report(results: list[dict]) -> str:
    n_in = sum(bool(q["expected"]) for q in QUESTIONS)
    lines = [
        "# Rapport d'évaluation", "",
        f"{len(QUESTIONS)} questions : {n_in} dans le sujet (article attendu connu), "
        f"{len(QUESTIONS) - n_in} hors sujet (refus attendu).", "",
        "| Indicateur | " + " | ".join(r["label"] for r in results) + " |",
        "|---" * (len(results) + 1) + "|",
    ]
    for key, label in LABELS.items():
        lines.append(f"| {label} | " + " | ".join(str(r["metrics"][key]) for r in results) + " |")

    lines += ["", "Réglages :", ""]
    for r in results:
        s = r["settings"]
        lines.append(f"- **{r['label']}** : modèle `{s['model']}`, index `{s['index']}`, "
                     f"top-k {s['top_k']}, articles/annexes prioritaires {s['min_rule_sources']}, "
                     f"seuil de refus {s['min_score']}")

    lines += ["", "## Calibrage du seuil de refus", ""]
    for r in results:
        m = r["metrics"]
        lo, hi = m["score_min_dans_le_sujet"], m["score_max_hors_sujet"]
        if hi is not None and lo > hi:
            lines.append(f"- **{r['label']}** : les scores se séparent bien. Un seuil entre {hi} et {lo} "
                         f"(par exemple {round((lo + hi) / 2, 3)}) refuse le hors-sujet sans refuser à tort.")
        else:
            lines.append(f"- **{r['label']}** : les scores se chevauchent ({hi} hors sujet, {lo} dans le sujet). "
                         "Le seuil seul ne suffit pas : le refus repose aussi sur le modèle (garde-fou n°2).")

    lines += ["", "## Détail des échecs", ""]
    for r in results:
        misses = [x for x in r["rows"] if (x["in_scope"] and (not x["hit"] or x["refused"]))
                  or (not x["in_scope"] and not x["refused"])]
        lines.append(f"**{r['label']}** : {len(misses)} échec(s)")
        for x in misses:
            lines.append(f"- Q{x['id']} « {x['question']} » → trouvé : {', '.join(x['retrieved'][:3])}"
                         + (" (refusé)" if x["refused"] else ""))
        lines.append("")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", nargs="+", default=["index"])
    parser.add_argument("--models", nargs="+", default=[config.CHAT_MODEL])
    parser.add_argument("--rules", nargs="+", type=int, default=[config.MIN_RULE_SOURCES],
                        help="Nombre minimal de passages issus d'articles/annexes (0 = aucune priorité)")
    parser.add_argument("--min-score", type=float, default=config.MIN_SCORE,
                        help="Seuil de refus à tester (par défaut : celui de config.py)")
    args = parser.parse_args()

    combos = list(itertools.product(args.index, args.models, args.rules))
    results = []
    for index_dir, model, rules in combos:
        parts = []
        if len(args.index) > 1:
            parts.append(index_dir)
        if len(args.models) > 1:
            parts.append(model)
        if len(args.rules) > 1:
            parts.append("priorité articles" if rules else "sans priorité")
        label = " · ".join(parts) or "réglage actuel"
        print(f"\nÉvaluation : {label} …")
        results.append(evaluate(label, index_dir, model, rules, args.min_score))

    out = config.ROOT / "eval"
    (out / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    report = write_report(results)
    (out / "report.md").write_text(report, encoding="utf-8")
    print("\n" + report)


if __name__ == "__main__":
    main()
