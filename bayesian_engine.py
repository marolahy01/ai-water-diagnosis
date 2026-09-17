"""
Moteur probabiliste — inférence bayésienne légère.

Hypothèse du cadrage : les causes sont mutuellement exclusives en première
approximation. Le réseau est donc modélisé sous forme "naïve" :

    P(Cause | E1..En) ∝ P(Cause) × Π_i P(Ei | Cause)

où E1..En sont les observations connues. Les observations manquantes sont
simplement absentes du produit (aucune valeur n'est forcée), ce qui gère
l'incomplétude sans biaiser le résultat. L'implémentation est volontairement
indépendante de bibliothèques lourdes (pgmpy/pomegranate) afin de rester
démontrable sans dépendances complexes ; le code reste néanmoins compatible
avec un remplacement par pgmpy si le groupe souhaite un graphe plus riche.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

import yaml

from src.models import BayesResult, CauseScore, Observation


class BayesianEngine:
    def __init__(self, network_path: str | Path):
        self.network_path = Path(network_path)
        self._data = self._load_network()
        self.causes: Dict[str, dict] = self._data.get("causes", {})
        self.actions: Dict[str, str] = self._data.get("actions", {})

    def _load_network(self) -> dict:
        with open(self.network_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    @property
    def all_causes(self) -> List[str]:
        return list(self.causes.keys())

    def action_for(self, cause: str) -> str:
        return self.actions.get(
            cause, "Faire confirmer le diagnostic par un technicien avant intervention."
        )

    # ------------------------------------------------------------------ #
    # Inférence : P(Cause | Observations) restreinte à un sous-ensemble
    # de causes candidates (fourni par le moteur symbolique).
    # ------------------------------------------------------------------ #
    def infer(
        self,
        observation: Observation,
        candidate_causes: Optional[List[str]] = None,
    ) -> BayesResult:
        facts = observation.to_facts()
        considered = candidate_causes if candidate_causes else self.all_causes
        considered = [c for c in considered if c in self.causes]
        if not considered:
            considered = self.all_causes

        raw_scores: Dict[str, float] = {}
        for cause in considered:
            cause_def = self.causes[cause]
            prob = float(cause_def.get("prior", 1.0 / max(len(considered), 1)))
            cpt = cause_def.get("cpt", {})
            for fact_name, observed_value in facts.items():
                fact_cpt = cpt.get(fact_name)
                if not fact_cpt:
                    # Observation non modélisée pour cette cause => neutre
                    continue
                likelihood = fact_cpt.get(observed_value)
                if likelihood is None:
                    # Valeur jamais vue dans la CPT : on applique un
                    # lissage (Laplace léger) plutôt que d'annuler la cause.
                    likelihood = 0.01
                prob *= likelihood
            raw_scores[cause] = prob

        total = sum(raw_scores.values())
        if total <= 0:
            # Toutes les probabilités se sont effondrées (cas extrême) :
            # on retombe sur une distribution uniforme informative plutôt
            # que sur une division par zéro.
            uniform = 1.0 / len(considered)
            ranked = sorted(
                [CauseScore(c, uniform) for c in considered],
                key=lambda cs: cs.cause,
            )
        else:
            ranked = sorted(
                [CauseScore(c, raw_scores[c] / total) for c in considered],
                key=lambda cs: cs.probability,
                reverse=True,
            )

        return BayesResult(ranked_causes=ranked, considered_causes=considered)
