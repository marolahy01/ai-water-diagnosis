"""
Modèles de données partagés par les moteurs symbolique, probabiliste
et hybride.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# Valeur utilisée pour représenter une observation manquante / inconnue.
UNKNOWN = "inconnue"


@dataclass
class Observation:
    """
    Ensemble des observations transmises par un opérateur ou un capteur.

    Les champs absents ou valant None/"inconnue" sont traités comme
    manquants : ils ne forcent aucune règle et ne pénalisent aucune
    cause dans le calcul bayésien (gestion explicite de l'incomplétude).
    """

    pression: Optional[str] = None          # basse | normale | haute
    debit: Optional[str] = None             # nul | faible | normal
    turbidite: Optional[str] = None         # elevee | normale
    plaintes_gout: Optional[str] = None     # oui | non
    pompe_alarme: Optional[str] = None      # oui | non
    tension_anormale: Optional[str] = None  # oui | non
    pompe_etat: Optional[str] = None        # ok | hs
    heure: Optional[str] = None             # information contextuelle
    meteo: Optional[str] = None             # information contextuelle
    notes: Optional[str] = None             # commentaire libre opérateur

    def to_facts(self) -> Dict[str, str]:
        """Retourne uniquement les faits réellement connus (non None/'inconnue')."""
        facts = {}
        for k, v in self.__dict__.items():
            if v is not None and v != UNKNOWN:
                facts[k] = v
        return facts

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Observation":
        known_fields = {f for f in cls.__dataclass_fields__}
        filtered = {k: v for k, v in data.items() if k in known_fields}
        return cls(**filtered)


@dataclass
class RuleFiring:
    """Trace d'une règle qui s'est déclenchée."""

    rule_id: str
    description: str
    conclusions: List[str]
    excludes: List[str]
    specificity: int


@dataclass
class RuleEngineResult:
    """Résultat du moteur symbolique (chaînage avant)."""

    candidate_causes: List[str]
    excluded_causes: List[str]
    fired_rules: List[RuleFiring]
    conflicts: List[str] = field(default_factory=list)
    fallback_used: bool = False  # True si aucune règle ne s'est déclenchée


@dataclass
class CauseScore:
    """Score final (probabilité a posteriori) attribué à une cause."""

    cause: str
    probability: float


@dataclass
class BayesResult:
    """Résultat du moteur probabiliste."""

    ranked_causes: List[CauseScore]
    considered_causes: List[str]


@dataclass
class Diagnosis:
    """Résultat final produit par le pipeline hybride."""

    ranked_causes: List[CauseScore]
    top_cause: str
    confidence: float
    confidence_level: str          # "faible" | "moyenne" | "élevée"
    fired_rules: List[RuleFiring]
    excluded_causes: List[str]
    recommended_action: str
    explanation: str
    conflicts: List[str] = field(default_factory=list)
    fallback_used: bool = False
    latency_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "diagnostic_principal": self.top_cause,
            "confiance": round(self.confidence, 3),
            "niveau_confiance": self.confidence_level,
            "causes_classees": [
                {"cause": c.cause, "probabilite": round(c.probability, 3)}
                for c in self.ranked_causes
            ],
            "regles_activees": [r.rule_id for r in self.fired_rules],
            "causes_ecartees": self.excluded_causes,
            "action_recommandee": self.recommended_action,
            "explication": self.explanation,
            "conflits": self.conflicts,
            "mode_secours": self.fallback_used,
            "latence_ms": round(self.latency_ms, 2),
        }
