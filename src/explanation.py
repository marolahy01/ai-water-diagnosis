"""
Module d'explication — combine la trace du moteur de règles et les
probabilités a posteriori du moteur bayésien pour produire une
justification lisible par un technicien non informaticien.
"""

from __future__ import annotations

from typing import List

from src.models import CauseScore, RuleFiring

CAUSE_LABELS = {
    "fuite_majeure": "Fuite majeure",
    "fuite_secondaire": "Fuite secondaire",
    "vanne_fermee": "Vanne fermée",
    "panne_pompe_mecanique": "Panne mécanique de la pompe",
    "panne_electrique_pompe": "Panne électrique de la pompe",
    "contamination": "Contamination de l'eau",
    "capteur_defaillant": "Capteur défaillant",
    "ras": "Rien à signaler",
}


def cause_label(cause: str) -> str:
    return CAUSE_LABELS.get(cause, cause.replace("_", " ").capitalize())


def confidence_level(probability: float) -> str:
    if probability >= 0.70:
        return "élevée"
    if probability >= 0.45:
        return "moyenne"
    return "faible"


def build_explanation(
    ranked_causes: List[CauseScore],
    fired_rules: List[RuleFiring],
    excluded_causes: List[str],
    fallback_used: bool,
    conflicts: List[str],
) -> str:
    lines: List[str] = []

    if not ranked_causes:
        return "Aucune cause candidate n'a pu être évaluée avec les observations fournies."

    top = ranked_causes[0]
    lines.append(
        f"Diagnostic principal : {cause_label(top.cause)} "
        f"(probabilité estimée {top.probability:.0%}, niveau de confiance {confidence_level(top.probability)})."
    )

    if fired_rules:
        rule_ids = ", ".join(r.rule_id for r in fired_rules)
        lines.append(f"Règles activées : {rule_ids}.")
        for r in fired_rules:
            lines.append(f"  - {r.rule_id} : {r.description}")
    elif fallback_used:
        lines.append(
            "Aucune règle métier ne s'est déclenchée sur ces observations "
            "(cas incomplet ou atypique) : le classement ci-dessous repose "
            "uniquement sur le réseau bayésien, sur l'ensemble des causes non écartées."
        )

    if excluded_causes:
        excluded_labels = ", ".join(cause_label(c) for c in excluded_causes)
        lines.append(f"Causes écartées par les règles : {excluded_labels}.")

    if conflicts:
        lines.append("Conflits détectés et résolus automatiquement :")
        for c in conflicts:
            lines.append(f"  - {c}")

    if len(ranked_causes) > 1:
        alt = ", ".join(
            f"{cause_label(c.cause)} ({c.probability:.0%})" for c in ranked_causes[1:4]
        )
        lines.append(f"Autres causes envisagées, par ordre de probabilité : {alt}.")

    return "\n".join(lines)
