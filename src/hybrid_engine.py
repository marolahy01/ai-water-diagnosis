"""
Moteur hybride — orchestre le moteur symbolique et le moteur bayésien,
gère les conflits et produit un diagnostic final justifié.

Trois configurations sont exposées pour le protocole d'évaluation
(cf. section 4 du cadrage) :

  - "rules"  : règles seules (chaînage avant). La confiance est dérivée
               du nombre de causes candidates restantes (1 candidat =
               confiance élevée, plusieurs candidats = confiance partagée).
  - "bayes"  : réseau bayésien seul, sur l'ensemble des causes (aucun
               filtrage symbolique).
  - "hybrid" : pipeline complet (règles -> filtrage -> bayes -> explication).
               C'est la configuration principale du système.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import List, Literal

from src.bayesian_engine import BayesianEngine
from src.explanation import build_explanation, confidence_level
from src.models import CauseScore, Diagnosis, Observation, RuleEngineResult
from src.rules_engine import RulesEngine

Configuration = Literal["rules", "bayes", "hybrid"]


class HybridDiagnosisEngine:
    def __init__(
        self,
        rules_path: str | Path = "config/rules.yaml",
        bayes_path: str | Path = "config/bayes_network.yaml",
    ):
        self.bayes_engine = BayesianEngine(bayes_path)
        self.rules_engine = RulesEngine(rules_path, all_causes=self.bayes_engine.all_causes)

    # ------------------------------------------------------------------ #
    def diagnose(
        self, observation: Observation, configuration: Configuration = "hybrid"
    ) -> Diagnosis:
        start = time.perf_counter()

        if configuration == "rules":
            diagnosis = self._diagnose_rules_only(observation)
        elif configuration == "bayes":
            diagnosis = self._diagnose_bayes_only(observation)
        else:
            diagnosis = self._diagnose_hybrid(observation)

        diagnosis.latency_ms = (time.perf_counter() - start) * 1000
        return diagnosis

    # ------------------------------------------------------------------ #
    def _diagnose_hybrid(self, observation: Observation) -> Diagnosis:
        rule_result = self.rules_engine.run(observation)
        bayes_result = self.bayes_engine.infer(
            observation, candidate_causes=rule_result.candidate_causes
        )
        return self._build_diagnosis(rule_result, bayes_result.ranked_causes)

    # ------------------------------------------------------------------ #
    def _diagnose_bayes_only(self, observation: Observation) -> Diagnosis:
        bayes_result = self.bayes_engine.infer(observation, candidate_causes=None)
        empty_rule_result = RuleEngineResult(
            candidate_causes=self.bayes_engine.all_causes,
            excluded_causes=[],
            fired_rules=[],
            conflicts=[],
            fallback_used=True,
        )
        return self._build_diagnosis(empty_rule_result, bayes_result.ranked_causes)

    # ------------------------------------------------------------------ #
    def _diagnose_rules_only(self, observation: Observation) -> Diagnosis:
        rule_result = self.rules_engine.run(observation)
        n = max(len(rule_result.candidate_causes), 1)
        # Sans étage probabiliste, on répartit une confiance uniforme
        # entre les causes candidates retenues par les règles (proxy simple
        # utilisé uniquement pour la configuration de comparaison "rules seules").
        ranked = sorted(
            [CauseScore(c, 1.0 / n) for c in rule_result.candidate_causes],
            key=lambda cs: cs.cause,
        )
        if rule_result.fallback_used:
            # Aucune règle déclenchée => le système ne peut conclure seul.
            ranked = [CauseScore(c, 1.0 / n) for c in rule_result.candidate_causes]
        return self._build_diagnosis(rule_result, ranked)

    # ------------------------------------------------------------------ #
    def _build_diagnosis(
        self, rule_result: RuleEngineResult, ranked_causes: List[CauseScore]
    ) -> Diagnosis:
        if not ranked_causes:
            top_cause = "indetermine"
            top_prob = 0.0
        else:
            top_cause = ranked_causes[0].cause
            top_prob = ranked_causes[0].probability

        explanation = build_explanation(
            ranked_causes=ranked_causes,
            fired_rules=rule_result.fired_rules,
            excluded_causes=rule_result.excluded_causes,
            fallback_used=rule_result.fallback_used,
            conflicts=rule_result.conflicts,
        )

        return Diagnosis(
            ranked_causes=ranked_causes,
            top_cause=top_cause,
            confidence=top_prob,
            confidence_level=confidence_level(top_prob),
            fired_rules=rule_result.fired_rules,
            excluded_causes=rule_result.excluded_causes,
            recommended_action=self.bayes_engine.action_for(top_cause),
            explanation=explanation,
            conflicts=rule_result.conflicts,
            fallback_used=rule_result.fallback_used,
        )
