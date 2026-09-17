#!/usr/bin/env python3
"""
Script d'évaluation automatique — compare les trois configurations
(règles seules / bayes seul / hybride) sur le jeu de 12 cas de test,
selon les métriques du protocole d'évaluation (section 4 du cadrage) :

  - Exactitude       : diagnostic principal correct.
  - Cohérence        : justification présente et non contradictoire.
  - Latence moyenne  : temps moyen de traitement d'un cas (ms).
  - Cas limites OK   : nombre de cas de type "limite" correctement traités.

Usage :
    python evaluate.py
    python evaluate.py --data data/test_cases.json --verbose
"""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path
from typing import Dict, List

from src.hybrid_engine import HybridDiagnosisEngine
from src.models import Observation

CONFIGURATIONS = ["rules", "bayes", "hybrid"]
CONFIG_LABELS = {
    "rules": "Règles seules",
    "bayes": "Bayes seul",
    "hybrid": "Hybride (C)",
}


def load_cases(path: str | Path) -> List[dict]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def evaluate_configuration(
    engine: HybridDiagnosisEngine, cases: List[dict], configuration: str, verbose: bool
) -> Dict[str, object]:
    correct = 0
    coherent = 0
    limit_ok = 0
    limit_total = 0
    latencies: List[float] = []
    details = []

    for case in cases:
        obs = Observation.from_dict(case["observation"])
        diagnosis = engine.diagnose(obs, configuration=configuration)
        latencies.append(diagnosis.latency_ms)

        is_correct = diagnosis.top_cause == case["diagnostic_attendu"]
        is_coherent = bool(diagnosis.explanation.strip()) and not (
            diagnosis.top_cause in diagnosis.excluded_causes
        )

        if is_correct:
            correct += 1
        if is_coherent:
            coherent += 1
        if case.get("type") == "limite":
            limit_total += 1
            if is_correct:
                limit_ok += 1

        details.append(
            {
                "id": case["id"],
                "type": case.get("type"),
                "attendu": case["diagnostic_attendu"],
                "obtenu": diagnosis.top_cause,
                "confiance": round(diagnosis.confidence, 2),
                "correct": is_correct,
            }
        )

        if verbose:
            status = "OK " if is_correct else "ERR"
            print(
                f"  [{status}] {case['id']:8s} attendu={case['diagnostic_attendu']:24s} "
                f"obtenu={diagnosis.top_cause:24s} confiance={diagnosis.confidence:.2f}"
            )

    n = len(cases)
    return {
        "configuration": configuration,
        "exactitude": correct / n,
        "exactitude_frac": f"{correct}/{n}",
        "coherence": coherent / n,
        "latence_moy_ms": statistics.mean(latencies) if latencies else 0.0,
        "cas_limites_ok": f"{limit_ok}/{limit_total}",
        "details": details,
    }


def print_report(results: List[Dict[str, object]]) -> None:
    header = f"{'Configuration':<18}{'Exactitude':<16}{'Cohérence':<14}{'Latence moy.':<16}{'Cas limites OK':<16}"
    print(header)
    print("-" * len(header))
    for r in results:
        print(
            f"{CONFIG_LABELS[r['configuration']]:<18}"
            f"{r['exactitude_frac']:<8}({r['exactitude']:.0%}){'':<4}"
            f"{r['coherence']:.0%}{'':<10}"
            f"{r['latence_moy_ms']:.3f} ms{'':<9}"
            f"{r['cas_limites_ok']:<16}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Évaluation du système de diagnostic hybride.")
    parser.add_argument("--data", default="data/test_cases.json", help="Chemin du jeu de test JSON.")
    parser.add_argument("--rules", default="config/rules.yaml", help="Chemin de la base de règles.")
    parser.add_argument("--bayes", default="config/bayes_network.yaml", help="Chemin du réseau bayésien.")
    parser.add_argument("--verbose", action="store_true", help="Afficher le détail par cas.")
    parser.add_argument("--json-out", default=None, help="Chemin optionnel pour sauvegarder le rapport en JSON.")
    args = parser.parse_args()

    engine = HybridDiagnosisEngine(rules_path=args.rules, bayes_path=args.bayes)
    cases = load_cases(args.data)

    print(f"Évaluation sur {len(cases)} cas ({args.data})\n")

    results = []
    for config in CONFIGURATIONS:
        if args.verbose:
            print(f"--- {CONFIG_LABELS[config]} ---")
        results.append(evaluate_configuration(engine, cases, config, args.verbose))
        if args.verbose:
            print()

    print_report(results)

    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"\nRapport détaillé sauvegardé dans {args.json_out}")


if __name__ == "__main__":
    main()
