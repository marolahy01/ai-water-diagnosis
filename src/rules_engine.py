"""
Moteur symbolique — chaînage avant (forward chaining) sur une base de
règles en logique propositionnelle.

Le moteur :
1. Évalue chaque règle par rapport aux faits observés.
2. Déclenche toutes les règles applicables (chaînage avant complet, pas
   de coupure au premier succès).
3. Construit l'ensemble des causes candidates (union des conclusions des
   règles déclenchées) et l'ensemble des causes explicitement écartées
   ("excludes"), ce qui réalise le filtrage rapide décrit dans le cadrage.
4. Détecte les conflits (une même cause à la fois proposée et écartée
   par des règles différentes) et les résout par un principe de
   spécificité : la règle ayant le plus grand nombre de conditions
   (la plus spécifique) l'emporte ; en cas d'égalité, priorité à
   l'exclusion (principe de prudence sanitaire).
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Set

import yaml

from src.models import Observation, RuleEngineResult, RuleFiring


class RulesEngine:
    def __init__(self, rules_path: str | Path, all_causes: List[str]):
        self.rules_path = Path(rules_path)
        self.all_causes = list(all_causes)
        self.rules = self._load_rules()

    # ------------------------------------------------------------------ #
    # Chargement
    # ------------------------------------------------------------------ #
    def _load_rules(self) -> List[dict]:
        with open(self.rules_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        rules = data.get("rules", [])
        for r in rules:
            r.setdefault("conclusions", [])
            r.setdefault("excludes", [])
            r.setdefault("priority", len(r.get("conditions", {})))
        return rules

    # ------------------------------------------------------------------ #
    # Évaluation d'une règle
    # ------------------------------------------------------------------ #
    @staticmethod
    def _rule_matches(conditions: Dict[str, object], facts: Dict[str, str]) -> bool:
        for fact_name, expected in conditions.items():
            observed = facts.get(fact_name)
            if observed is None:
                return False  # fait inconnu => la règle ne peut pas se déclencher
            if isinstance(expected, list):
                if observed not in expected:
                    return False
            else:
                if observed != expected:
                    return False
        return True

    # ------------------------------------------------------------------ #
    # Chaînage avant
    # ------------------------------------------------------------------ #
    def run(self, observation: Observation) -> RuleEngineResult:
        facts = observation.to_facts()

        fired: List[RuleFiring] = []
        for rule in self.rules:
            if self._rule_matches(rule.get("conditions", {}), facts):
                fired.append(
                    RuleFiring(
                        rule_id=rule["id"],
                        description=rule.get("description", "").strip(),
                        conclusions=list(rule.get("conclusions", [])),
                        excludes=list(rule.get("excludes", [])),
                        specificity=rule.get("priority", len(rule.get("conditions", {}))),
                    )
                )

        proposed: Set[str] = set()
        excluded: Set[str] = set()
        conflicts: List[str] = []

        # Première passe : on agrège brut, en gardant la trace de la
        # spécificité maximale ayant proposé / écarté chaque cause.
        propose_specificity: Dict[str, int] = {}
        exclude_specificity: Dict[str, int] = {}

        for firing in fired:
            for cause in firing.conclusions:
                proposed.add(cause)
                propose_specificity[cause] = max(
                    propose_specificity.get(cause, 0), firing.specificity
                )
            for cause in firing.excludes:
                excluded.add(cause)
                exclude_specificity[cause] = max(
                    exclude_specificity.get(cause, 0), firing.specificity
                )

        # Résolution des conflits (cause à la fois proposée et écartée).
        for cause in proposed & excluded:
            if propose_specificity[cause] > exclude_specificity[cause]:
                excluded.discard(cause)
                conflicts.append(
                    f"Conflit sur '{cause}' résolu en faveur de la proposition "
                    f"(règle plus spécifique)."
                )
            else:
                proposed.discard(cause)
                conflicts.append(
                    f"Conflit sur '{cause}' résolu en faveur de l'exclusion "
                    f"(principe de prudence / spécificité égale ou supérieure)."
                )

        fallback_used = False
        if proposed:
            candidate_causes = sorted(proposed - excluded)
        else:
            # Aucune règle n'a proposé de cause : on laisse le moteur
            # bayésien statuer sur l'ensemble des causes non explicitement
            # écartées (mode de secours explicite, tracé dans le résultat).
            fallback_used = True
            candidate_causes = sorted(set(self.all_causes) - excluded)

        if not candidate_causes:
            # Sécurité : si tout a été écarté par erreur de configuration,
            # on retombe sur l'ensemble complet plutôt que de ne rien retourner.
            candidate_causes = list(self.all_causes)

        return RuleEngineResult(
            candidate_causes=candidate_causes,
            excluded_causes=sorted(excluded),
            fired_rules=fired,
            conflicts=conflicts,
            fallback_used=fallback_used,
        )
