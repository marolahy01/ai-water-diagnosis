#!/usr/bin/env python3
"""
Application en ligne de commande — Système d'aide au diagnostic de pannes
pour un réseau de distribution d'eau potable.

Deux modes d'utilisation :

1. Interactif (par défaut) :
       python app.py

2. Non interactif, observation fournie en JSON (fichier ou chaîne) :
       python app.py --json data/exemple_observation.json
       python app.py --json '{"pression": "basse", "debit": "nul", "pompe_etat": "ok"}'

Options :
    --config-only CONFIG   Force une configuration ("rules", "bayes" ou "hybrid").
                            Par défaut : "hybrid".
"""

from __future__ import annotations

import argparse
import json
import sys

from src.hybrid_engine import HybridDiagnosisEngine
from src.models import Observation

FIELDS = [
    ("pression", ["basse", "normale", "haute"]),
    ("debit", ["nul", "faible", "normal"]),
    ("turbidite", ["elevee", "normale"]),
    ("plaintes_gout", ["oui", "non"]),
    ("pompe_alarme", ["oui", "non"]),
    ("tension_anormale", ["oui", "non"]),
    ("pompe_etat", ["ok", "hs"]),
]


def ask_interactively() -> Observation:
    print("=== Saisie des observations (laisser vide si inconnu) ===")
    data = {}
    for field_name, choices in FIELDS:
        prompt = f"{field_name} [{'/'.join(choices)}] : "
        while True:
            value = input(prompt).strip().lower()
            if value == "":
                break
            if value in choices:
                data[field_name] = value
                break
            print(f"  Valeur invalide. Choix possibles : {', '.join(choices)} (ou vide).")
    return Observation.from_dict(data)


def load_observation_from_json(json_arg: str) -> Observation:
    try:
        # D'abord on essaie de lire un fichier...
        with open(json_arg, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, OSError):
        # ...sinon on interprète l'argument comme du JSON inline.
        data = json.loads(json_arg)
    return Observation.from_dict(data)


def print_diagnosis(diagnosis) -> None:
    print("\n" + "=" * 70)
    print("RÉSULTAT DU DIAGNOSTIC")
    print("=" * 70)
    print(diagnosis.explanation)
    print("-" * 70)
    print(f"Action recommandée : {diagnosis.recommended_action}")
    print(f"Latence : {diagnosis.latency_ms:.2f} ms")
    print("=" * 70)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--json", help="Observation au format JSON (fichier ou chaîne inline).")
    parser.add_argument(
        "--config-only",
        choices=["rules", "bayes", "hybrid"],
        default="hybrid",
        help="Configuration du moteur à utiliser (par défaut : hybrid).",
    )
    parser.add_argument(
        "--rules", default="config/rules.yaml", help="Chemin de la base de règles."
    )
    parser.add_argument(
        "--bayes", default="config/bayes_network.yaml", help="Chemin du réseau bayésien."
    )
    parser.add_argument("--as-json", action="store_true", help="Afficher le résultat au format JSON.")
    args = parser.parse_args()

    engine = HybridDiagnosisEngine(rules_path=args.rules, bayes_path=args.bayes)

    if args.json:
        observation = load_observation_from_json(args.json)
    else:
        try:
            observation = ask_interactively()
        except (EOFError, KeyboardInterrupt):
            print("\nSaisie interrompue.")
            sys.exit(1)

    diagnosis = engine.diagnose(observation, configuration=args.config_only)

    if args.as_json:
        print(json.dumps(diagnosis.to_dict(), ensure_ascii=False, indent=2))
    else:
        print_diagnosis(diagnosis)


if __name__ == "__main__":
    main()
